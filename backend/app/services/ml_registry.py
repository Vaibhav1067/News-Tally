"""Loads ML artifacts once and reports honestly what is (un)available.

If an artifact is missing (e.g. you haven't trained yet), the API still runs
and every response states which component is unavailable — it never
substitutes a fake prediction.
"""
from __future__ import annotations

import json
import logging
import threading
from typing import Optional

import joblib
import numpy as np

from ml.config import ARTIFACTS_DIR

log = logging.getLogger(__name__)


class Registry:
    def __init__(self):
        self._lock = threading.Lock()
        self.loaded = False
        self.classifier = None
        self.classifier_meta: dict = {}
        self.explainer = None
        self.index = None
        self.errors: dict[str, str] = {}

    def load(self) -> None:
        with self._lock:
            if self.loaded:
                return
            self._load_classifier()
            self._load_index()
            self.loaded = True

    def _load_classifier(self) -> None:
        path = ARTIFACTS_DIR / "classifier.joblib"
        if not path.exists():
            self.errors["classifier"] = "classifier.joblib not found — run `python -m ml.training.train_classical`"
            return
        try:
            self.classifier = joblib.load(path)
            meta_path = ARTIFACTS_DIR / "classifier_metadata.json"
            self.classifier_meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
            from ml.explainability.explain import LinearExplainer

            mean_path = ARTIFACTS_DIR / "explainer_background_mean.npy"
            mean = np.load(mean_path) if mean_path.exists() else None
            self.explainer = LinearExplainer(self.classifier, background_mean=mean)
        except Exception as exc:
            log.exception("classifier load failed")
            self.errors["classifier"] = f"failed to load: {exc}"

    def _load_index(self) -> None:
        try:
            from ml.retrieval.index import FactCheckIndex

            self.index = FactCheckIndex.load()
        except FileNotFoundError:
            self.errors["retrieval"] = "retrieval index not found — run `python -m ml.retrieval.index`"
        except Exception as exc:
            log.exception("index load failed")
            self.errors["retrieval"] = f"failed to load: {exc}"

    def status(self) -> dict:
        return {
            "classifier": {"available": self.classifier is not None,
                           "model": self.classifier_meta.get("deployed_model"),
                           "classes": self.classifier_meta.get("classes"),
                           "error": self.errors.get("classifier")},
            "retrieval": {"available": self.index is not None,
                          "backend": self.index.backend if self.index else None,
                          "size": len(self.index.ids) if self.index else 0,
                          "error": self.errors.get("retrieval")},
            "explainer": {"available": bool(self.explainer and self.explainer.available),
                          "method": self.explainer.method if self.explainer else None},
        }


registry = Registry()


def get_registry() -> Registry:
    if not registry.loaded:
        registry.load()
    return registry


def reset_registry(new: Optional[Registry] = None) -> None:
    """Used by tests."""
    global registry
    registry = new or Registry()
