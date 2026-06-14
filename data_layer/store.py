"""Parquet cache for fetched history: data/cache/{source}/{name}.parquet."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pandas as pd

DEFAULT_ROOT = Path(__file__).resolve().parent.parent / "data" / "cache"


def cache_path(source: str, name: str, root: Path | None = None) -> Path:
    return (root or DEFAULT_ROOT) / source / f"{name}.parquet"


def save(df: pd.DataFrame, source: str, name: str, root: Path | None = None) -> Path:
    p = cache_path(source, name, root)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p)
    return p


def load(source: str, name: str, root: Path | None = None) -> pd.DataFrame | None:
    p = cache_path(source, name, root)
    return pd.read_parquet(p) if p.exists() else None


def load_or_fetch(source: str, name: str, fetch: Callable[[], pd.DataFrame],
                  root: Path | None = None, refresh: bool = False) -> pd.DataFrame:
    """Idempotent: return cached frame unless missing/refresh; fetch saves through."""
    if not refresh:
        cached = load(source, name, root)
        if cached is not None and len(cached):
            return cached
    df = fetch()
    if len(df):
        save(df, source, name, root)
    return df
