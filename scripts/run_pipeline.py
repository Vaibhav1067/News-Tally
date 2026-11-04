"""Run the whole ML pipeline end to end, in order.

    python scripts/run_pipeline.py                 # use existing raw data
    python scripts/run_pipeline.py --collect 10    # first collect 10 pages per source (~5 min)
    python scripts/run_pipeline.py --transformer   # also run the optional transformer experiment

Stages: [collect] -> build dataset -> train classical -> build retrieval index
        -> evaluate retrieval -> seed database -> [transformer]
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def step(title: str, args: list[str], cwd: Path = ROOT) -> None:
    print(f"\n=== {title} ===", flush=True)
    t0 = time.time()
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONPATH": str(ROOT)}
    subprocess.run([sys.executable, *args], cwd=cwd, check=True, env=env)
    print(f"--- {title}: {time.time() - t0:.0f}s", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--collect", type=int, default=0, metavar="PAGES", help="collect N pages per source first")
    ap.add_argument("--transformer", action="store_true")
    a = ap.parse_args()
    if a.collect:
        step("Collect fact-checks", ["-m", "ml.data_collection.run_collection", "--pages", str(a.collect)])
    step("Build processed dataset", ["-m", "ml.preprocessing.build_dataset"])
    step("Train classical models", ["-m", "ml.training.train_classical"])
    step("Build retrieval index", ["-m", "ml.retrieval.index"])
    step("Evaluate retrieval", ["-m", "ml.evaluation.retrieval_eval"])
    step("Seed database", ["-m", "app.services.seed"], cwd=ROOT / "backend")
    if a.transformer:
        step("Transformer experiment", ["-m", "ml.training.train_transformer"])
    print("\nDone. Start the API with: uvicorn app.main:app --app-dir backend --port 8000")


if __name__ == "__main__":
    main()
