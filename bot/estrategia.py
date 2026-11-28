"""Estrategia: rotación por momentum con filtro de tendencia y control de volatilidad.

Una vez a la semana, con velas diarias:
  1. Cada moneda (BTC, ETH, LTC) puede ocupar como máximo 1/3 del capital.
  2. Solo se mantiene una moneda si está en tendencia alcista: su precio está
     por encima de su media de `media` días Y ha subido en los últimos
     `momentum` días. Si no, esa parte del capital queda en euros.
  3. Control de volatilidad: si una moneda se mueve mucho (volatilidad anual
     por encima de `vol_objetivo`), se compra menos de ella en proporción.

En mercados bajistas el bot acaba casi todo en euros, que es lo que limita
las pérdidas. En mercados alcistas va invertido y captura la subida.

Se probó primero un cruce de medias en velas de 4h; con 8 años de datos
reales no superó la validación walk-forward y se descartó.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Parametros:
    media: int = 50            # días de la media móvil (filtro de tendencia)
    momentum: int = 30         # días para medir si la moneda está subiendo
    vol_objetivo: float = 0.5  # volatilidad anual objetivo por moneda (0 = sin control)
    vol_ventana: int = 20      # días para medir la volatilidad
    rebalanceo_dias: int = 7   # cada cuántos días se ajusta la cartera

    def como_dict(self) -> dict:
        return asdict(self)

    @property
    def dias_minimos(self) -> int:
        return max(self.media, self.momentum, self.vol_ventana) + 1


def a_diario(df: pd.DataFrame) -> pd.Series:
    """Cierre diario (UTC) a partir de velas de cualquier temporalidad."""
    return df.set_index("fecha")["close"].resample("1D").last().dropna()


def cierres_diarios(datos: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return pd.DataFrame({par: a_diario(df) for par, df in datos.items()}).dropna()


def en_tendencia(cierres: pd.DataFrame, p: Parametros) -> pd.DataFrame:
    """True el día en que la moneda está por encima de su media y ha subido en `momentum` días."""
    media = cierres.rolling(p.media).mean()
    subida = cierres / cierres.shift(p.momentum) - 1
    return (cierres > media) & (subida > 0)


def pesos_objetivo(cierres: pd.DataFrame, p: Parametros) -> pd.DataFrame:
    """Peso objetivo de cada moneda (0 a 1/n) calculado con el cierre de cada día."""
    n = cierres.shape[1]
    media = cierres.rolling(p.media).mean()
    subida = cierres / cierres.shift(p.momentum) - 1
    pesos = en_tendencia(cierres, p).astype(float) / n
    if p.vol_objetivo > 0:
        vol = cierres.pct_change().rolling(p.vol_ventana).std() * np.sqrt(365)
        pesos = pesos * (p.vol_objetivo / vol).clip(upper=1.0)
    pesos[media.isna() | subida.isna()] = 0.0
    return pesos.fillna(0.0)


def curva_sin_dinero(cierres: pd.DataFrame, pesos: pd.DataFrame) -> pd.Series:
    """Cómo habría evolucionado la estrategia (sin comisiones, ajustando a diario) con los pesos dados.

    Sirve para saber si la estrategia "vuelve a funcionar" mientras el freno la tiene parada.
    """
    rend = (pesos.shift().fillna(0.0) * cierres.pct_change().fillna(0.0)).sum(axis=1)
    return (1 + rend).cumprod()


def mercado_permite_reanudar(cierres: pd.DataFrame, p: Parametros, modo: str,
                             pesos: pd.DataFrame | None = None) -> pd.Series:
    """Para cada día, si se cumple la condición de reactivación del freno (ver config.Freno)."""
    if modo == "tiempo":
        return pd.Series(True, index=cierres.index)
    if modo == "amplia":
        return en_tendencia(cierres, p).sum(axis=1) >= 2
    if modo == "btc":
        btc = next(c for c in cierres.columns if c.startswith("BTC"))
        return cierres[btc] > cierres[btc].rolling(100).mean()
    if modo == "curva":
        curva = curva_sin_dinero(cierres, pesos if pesos is not None else pesos_objetivo(cierres, p))
        return curva > curva.rolling(30).mean()
    raise ValueError(f"reactivación desconocida: {modo}")
