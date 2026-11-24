"""Carga y valida config.yaml."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

MONEDAS_PERMITIDAS = {"BTC", "ETH", "LTC"}
RAIZ = Path(__file__).resolve().parent.parent


@dataclass
class Riesgo:
    por_operacion: float = 0.01
    perdida_maxima_mensual: float = 0.06
    max_posiciones_abiertas: int = 3


@dataclass
class Config:
    modo: str = "paper"
    exchange: str = "kraken"
    fuente_historica: str = "bitstamp"
    pares: list[str] = field(default_factory=lambda: ["BTC/EUR", "ETH/EUR", "LTC/EUR"])
    timeframe: str = "4h"
    capital_inicial: float = 1000.0
    riesgo: Riesgo = field(default_factory=Riesgo)

    def validar(self) -> "Config":
        if self.modo not in {"paper", "real"}:
            raise ValueError(f"modo debe ser 'paper' o 'real', no '{self.modo}'")
        for par in self.pares:
            base = par.split("/")[0]
            if base not in MONEDAS_PERMITIDAS:
                raise ValueError(f"{par} no está permitido: el bot solo opera BTC, ETH y LTC")
        if not 0 < self.riesgo.por_operacion <= 0.05:
            raise ValueError("riesgo.por_operacion debe estar entre 0 y 0.05 (5%)")
        if not 0 < self.riesgo.perdida_maxima_mensual <= 0.5:
            raise ValueError("riesgo.perdida_maxima_mensual debe estar entre 0 y 0.5")
        if self.capital_inicial <= 0:
            raise ValueError("capital_inicial debe ser positivo")
        return self


def cargar_config(ruta: str | Path | None = None) -> Config:
    ruta = Path(ruta) if ruta else RAIZ / "config.yaml"
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    riesgo = Riesgo(**(datos.pop("riesgo", None) or {}))
    return Config(**datos, riesgo=riesgo).validar()
