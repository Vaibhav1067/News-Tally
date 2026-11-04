"""Group-aware, stratified train/validation/test splitting.

Plain ``train_test_split`` would put near-duplicate claims on both sides of
the split (leakage). ``StratifiedGroupKFold`` keeps every ``group_id`` on one
side while approximately preserving the label distribution.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

from ml.config import RANDOM_SEED


def group_split(df: pd.DataFrame, label_col: str = "label", group_col: str = "group_id",
                test_frac: float = 0.15, val_frac: float = 0.15, seed: int = RANDOM_SEED
                ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    def one_split(frame: pd.DataFrame, frac: float) -> tuple[np.ndarray, np.ndarray]:
        n_splits = max(2, round(1 / frac))
        sgkf = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
        rest_idx, held_idx = next(sgkf.split(frame, frame[label_col], frame[group_col]))
        return rest_idx, held_idx

    rest_idx, test_idx = one_split(df, test_frac)
    rest, test = df.iloc[rest_idx], df.iloc[test_idx]
    # val fraction relative to the remaining data
    tr_idx, val_idx = one_split(rest, val_frac / (1 - test_frac))
    train, val = rest.iloc[tr_idx], rest.iloc[val_idx]

    # sanity: no group crosses a boundary
    g_tr, g_va, g_te = set(train[group_col]), set(val[group_col]), set(test[group_col])
    assert not (g_tr & g_te) and not (g_tr & g_va) and not (g_va & g_te), "group leakage across splits"
    return train.reset_index(drop=True), val.reset_index(drop=True), test.reset_index(drop=True)
