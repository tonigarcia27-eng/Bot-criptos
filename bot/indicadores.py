"""Indicadores técnicos sobre series de pandas."""
from __future__ import annotations

import pandas as pd


def ema(serie: pd.Series, periodo: int) -> pd.Series:
    return serie.ewm(span=periodo, adjust=False, min_periods=periodo).mean()


def rsi(cierre: pd.Series, periodo: int = 14) -> pd.Series:
    delta = cierre.diff()
    subida = delta.clip(lower=0).ewm(alpha=1 / periodo, adjust=False, min_periods=periodo).mean()
    bajada = (-delta.clip(upper=0)).ewm(alpha=1 / periodo, adjust=False, min_periods=periodo).mean()
    rs = subida / bajada.replace(0, float("nan"))
    return (100 - 100 / (1 + rs)).fillna(100.0).where(subida.notna())


def atr(df: pd.DataFrame, periodo: int = 14) -> pd.Series:
    cierre_prev = df["close"].shift()
    rango = pd.concat([
        df["high"] - df["low"],
        (df["high"] - cierre_prev).abs(),
        (df["low"] - cierre_prev).abs(),
    ], axis=1).max(axis=1)
    return rango.ewm(alpha=1 / periodo, adjust=False, min_periods=periodo).mean()
