"""Stage B — multilingual transformer experiments (OPTIONAL, CPU-friendly defaults).

    python -m ml.training.train_transformer                  # both experiments
    python -m ml.training.train_transformer --mode frozen    # fast (~1 min)
    python -m ml.training.train_transformer --mode finetune --epochs 3 --batch-size 16

Backbone: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
(118M params, XLM-R tokenizer). Chosen because it is already downloaded for
retrieval, runs on a laptop CPU and is Apache-2.0. Larger candidates
(IndicBERT-v2, MuRIL, XLM-R base) are better for Indic languages but need
~1–2 GB of disk and a GPU for reasonable fine-tuning time — documented as
future work, not silently skipped.

Two experiments, SAME group-aware splits as the classical models:
1. frozen  — mean-pooled sentence embeddings + logistic regression
2. finetune — full fine-tuning with a classification head (AdamW, linear
   warm-up/decay, early stopping on validation macro-F1, best checkpoint saved)
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import torch

from ml.config import ARTIFACTS_DIR, PROCESSED_DATASET, RANDOM_SEED
from ml.evaluation.metrics import classification_metrics
from ml.training.features import prepare_training_frame
from ml.training.splits import group_split

log = logging.getLogger("train_transformer")
BACKBONE = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
OUT_DIR = ARTIFACTS_DIR / "transformer"


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def run_frozen(train, val, test, classes) -> dict:
    from sentence_transformers import SentenceTransformer
    from sklearn.linear_model import LogisticRegression

    t0 = time.time()
    enc = SentenceTransformer(BACKBONE, device=str(device()))
    emb = {k: enc.encode(d["claim_text"].tolist(), batch_size=64, normalize_embeddings=True)
           for k, d in (("train", train), ("val", val), ("test", test))}
    clf = LogisticRegression(C=2.0, max_iter=3000, class_weight="balanced", random_state=RANDOM_SEED)
    clf.fit(emb["train"], train["label"])
    out = {"seconds": round(time.time() - t0, 1)}
    for split, d in (("validation", val), ("test", test)):
        proba = clf.predict_proba(emb["val" if split == "validation" else "test"])
        out[split] = classification_metrics(d["label"], clf.classes_[proba.argmax(1)], classes, proba)
    log.info("frozen: val macro-F1=%.3f test macro-F1=%.3f", out["validation"]["f1_macro"], out["test"]["f1_macro"])
    return out


class TextDataset(torch.utils.data.Dataset):
    def __init__(self, texts, labels, tok, max_len):
        self.enc = tok(list(texts), truncation=True, max_length=max_len, padding=False)
        self.labels = list(labels)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, i):
        item = {k: v[i] for k, v in self.enc.items()}
        item["labels"] = self.labels[i]
        return item


def evaluate_model(model, loader, classes, dev) -> dict:
    model.eval()
    probs, gold = [], []
    with torch.no_grad():
        for batch in loader:
            labels = batch.pop("labels")
            logits = model(**{k: v.to(dev) for k, v in batch.items()}).logits
            probs.append(torch.softmax(logits, -1).cpu().numpy())
            gold.extend(labels.tolist())
    proba = np.concatenate(probs)
    y_true = [classes[i] for i in gold]
    return classification_metrics(y_true, np.array(classes)[proba.argmax(1)], classes, proba)


def run_finetune(train, val, test, classes, epochs: int, batch_size: int, lr: float, max_len: int,
                 patience: int, save: bool) -> dict:
    from transformers import (AutoModelForSequenceClassification, AutoTokenizer, DataCollatorWithPadding,
                              get_linear_schedule_with_warmup)

    dev = device()
    lab2id = {c: i for i, c in enumerate(classes)}
    tok = AutoTokenizer.from_pretrained(BACKBONE)
    model = AutoModelForSequenceClassification.from_pretrained(
        BACKBONE, num_labels=len(classes), id2label=dict(enumerate(classes)), label2id=lab2id).to(dev)
    collate = DataCollatorWithPadding(tok)
    mk = lambda d, shuffle: torch.utils.data.DataLoader(  # noqa: E731
        TextDataset(d["claim_text"], d["label"].map(lab2id), tok, max_len), batch_size=batch_size,
        shuffle=shuffle, collate_fn=collate, generator=torch.Generator().manual_seed(RANDOM_SEED))
    tr_dl, va_dl, te_dl = mk(train, True), mk(val, False), mk(test, False)

    # class-weighted loss (same imbalance handling as class_weight="balanced")
    counts = train["label"].value_counts().reindex(classes).to_numpy()
    weights = torch.tensor(len(train) / (len(classes) * counts), dtype=torch.float, device=dev)
    loss_fn = torch.nn.CrossEntropyLoss(weight=weights)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    total = epochs * len(tr_dl)
    sched = get_linear_schedule_with_warmup(opt, int(0.1 * total), total)

    history, best_f1, best_epoch, bad = [], -1.0, -1, 0
    ckpt = OUT_DIR / "checkpoint"
    best_state = None
    t0 = time.time()
    for epoch in range(1, epochs + 1):
        model.train()
        running = 0.0
        for step, batch in enumerate(tr_dl, 1):
            labels = batch.pop("labels").to(dev)
            logits = model(**{k: v.to(dev) for k, v in batch.items()}).logits
            loss = loss_fn(logits, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step(), sched.step(), opt.zero_grad()
            running += loss.item()
            if step % 50 == 0:
                log.info("epoch %d step %d/%d loss %.4f (%.0fs)", epoch, step, len(tr_dl), running / step,
                         time.time() - t0)
        val_m = evaluate_model(model, va_dl, classes, dev)
        history.append({"epoch": epoch, "train_loss": round(running / len(tr_dl), 4),
                        "val_f1_macro": val_m["f1_macro"], "val_accuracy": val_m["accuracy"]})
        log.info("epoch %d: train loss %.4f, val macro-F1 %.3f", epoch, running / len(tr_dl), val_m["f1_macro"])
        # persist progress every epoch so a crash (e.g. out of memory) never loses finished epochs
        (OUT_DIR / "finetune_progress.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
        if val_m["f1_macro"] > best_f1:
            best_f1, best_epoch, bad = val_m["f1_macro"], epoch, 0
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            if save:
                model.save_pretrained(ckpt), tok.save_pretrained(ckpt)
        else:
            bad += 1
            if bad >= patience:
                log.info("early stopping (no improvement for %d epoch(s))", patience)
                break
    model.load_state_dict(best_state)
    out = {"history": history, "best_epoch": best_epoch, "seconds": round(time.time() - t0, 1),
           "validation": evaluate_model(model, va_dl, classes, dev),
           "test": evaluate_model(model, te_dl, classes, dev),
           "checkpoint": str(ckpt) if save else None}
    log.info("finetune: best epoch %d, val macro-F1=%.3f test macro-F1=%.3f", best_epoch,
             out["validation"]["f1_macro"], out["test"]["f1_macro"])
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for noisy in ("httpx", "huggingface_hub", "sentence_transformers"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["frozen", "finetune", "both"], default="both")
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--lr", type=float, default=3e-5)
    ap.add_argument("--max-len", type=int, default=96)
    ap.add_argument("--patience", type=int, default=1)
    ap.add_argument("--no-save", action="store_true", help="do not write the ~470 MB checkpoint")
    ap.add_argument("--seed", type=int, default=RANDOM_SEED)
    args = ap.parse_args()
    set_seed(args.seed)
    torch.set_num_threads(max(1, torch.get_num_threads()))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    data = prepare_training_frame(pd.read_csv(PROCESSED_DATASET), min_class_size=30, include_titles=True)
    # same model input as the classical models (cleaned, casefolded; verdict cues masked in titles)
    data["claim_text"] = data["text"]
    classes = sorted(data["label"].unique())
    train, val, test = group_split(data)
    log.info("device=%s train=%d val=%d test=%d", device(), len(train), len(val), len(test))

    results = {"backbone": BACKBONE, "device": str(device()), "seed": args.seed, "classes": classes,
               "n_train": len(train), "n_val": len(val), "n_test": len(test),
               "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "args": vars(args)}
    if args.mode in ("frozen", "both"):
        results["frozen_embeddings_lr"] = run_frozen(train, val, test, classes)
    if args.mode in ("finetune", "both"):
        results["finetune"] = run_finetune(train, val, test, classes, args.epochs, args.batch_size, args.lr,
                                           args.max_len, args.patience, save=not args.no_save)
    meta_path = ARTIFACTS_DIR / "classifier_metadata.json"
    if meta_path.exists():
        cm = json.loads(meta_path.read_text(encoding="utf-8"))
        results["classical_reference"] = {
            "model": cm["deployed_model"],
            "validation_macro_f1": cm["results"][cm["deployed_model"]]["validation"]["f1_macro"],
            "test_macro_f1": cm["results"][cm["deployed_model"]]["test"]["f1_macro"]}
    (OUT_DIR / "transformer_metrics.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    log.info("saved %s", OUT_DIR / "transformer_metrics.json")


if __name__ == "__main__":
    main()
