"""Estrategia de seguimiento de tendencia (solo compras, mercado spot).

Entrada (al cierre de la vela):
  - Tendencia de fondo alcista: cierre por encima de la EMA larga.
  - Impulso: la EMA rápida cruza por encima de la EMA lenta en esta vela
    o en las `ventana_cruce` anteriores.
  - RSI entre `rsi_min` y `rsi_max` (hay fuerza, pero no está sobrecomprado).

Salida:
  - Stop-loss inicial a `atr_stop` ATR por debajo del precio de entrada.
  - Stop dinámico (trailing): `atr_trailing` ATR por debajo del máximo
    alcanzado desde la entrada. Solo sube, nunca baja.
  - Cierre por tendencia: la EMA rápida cae por debajo de la lenta.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from .indicadores import atr, ema, rsi


@dataclass(frozen=True)
class Parametros:
    ema_rapida: int = 20
    ema_lenta: int = 50
    ema_tendencia: int = 200
    rsi_periodo: int = 14
    rsi_min: float = 50.0
    rsi_max: float = 72.0
    ventana_cruce: int = 3
    atr_periodo: int = 14
    atr_stop: float = 2.5
    atr_trailing: float = 3.5

    def como_dict(self) -> dict:
        return asdict(self)


def calcular_senales(df: pd.DataFrame, p: Parametros) -> pd.DataFrame:
    out = df.copy()
    out["ema_r"] = ema(out["close"], p.ema_rapida)
    out["ema_l"] = ema(out["close"], p.ema_lenta)
    out["ema_t"] = ema(out["close"], p.ema_tendencia)
    out["rsi"] = rsi(out["close"], p.rsi_periodo)
    out["atr"] = atr(out, p.atr_periodo)

    encima = out["ema_r"] > out["ema_l"]
    cruce = encima & ~encima.shift(fill_value=False)
    cruce_reciente = cruce.rolling(p.ventana_cruce + 1, min_periods=1).max().astype(bool)
    out["entrada"] = (
        cruce_reciente
        & encima
        & (out["close"] > out["ema_t"])
        & out["rsi"].between(p.rsi_min, p.rsi_max)
        & out["atr"].notna()
    )
    out["salida_tendencia"] = ~encima & out["ema_l"].notna()
    return out
