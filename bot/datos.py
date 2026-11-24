"""Descarga y guarda velas (OHLCV) en CSV."""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

from .config import RAIZ

COLUMNAS = ["timestamp", "open", "high", "low", "close", "volume"]
CARPETA_DATOS = RAIZ / "data"


def descargar_ohlcv(exchange, par: str, timeframe: str, desde_ms: int,
                    hasta_ms: int | None = None, lote: int = 1000) -> pd.DataFrame:
    """Descarga velas desde `desde_ms` paginando hasta llegar al presente (o a `hasta_ms`)."""
    paso_ms = exchange.parse_timeframe(timeframe) * 1000
    hasta_ms = hasta_ms or exchange.milliseconds()
    filas: list[list] = []
    cursor = desde_ms
    while cursor < hasta_ms:
        velas = exchange.fetch_ohlcv(par, timeframe, since=cursor, limit=lote)
        if not velas:
            break
        filas.extend(velas)
        siguiente = velas[-1][0] + paso_ms
        if siguiente <= cursor:
            break
        cursor = siguiente
        if len(velas) < 2:
            break
    return a_dataframe(filas, hasta_ms)


def a_dataframe(filas: list[list], hasta_ms: int | None = None) -> pd.DataFrame:
    df = pd.DataFrame(filas, columns=COLUMNAS)
    if hasta_ms is not None:
        df = df[df["timestamp"] < hasta_ms]
    df = df.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
    df["fecha"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df


def ruta_csv(fuente: str, par: str, timeframe: str) -> Path:
    return CARPETA_DATOS / f"{fuente}_{par.replace('/', '-')}_{timeframe}.csv"


def guardar(df: pd.DataFrame, ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df[COLUMNAS].to_csv(ruta, index=False)


def cargar(ruta: Path) -> pd.DataFrame:
    df = pd.read_csv(ruta)
    df["fecha"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df


def actualizar(exchange, fuente: str, par: str, timeframe: str, dias: int) -> pd.DataFrame:
    """Descarga solo lo que falta respecto al CSV guardado (o `dias` de histórico si no existe)."""
    ruta = ruta_csv(fuente, par, timeframe)
    ahora = int(time.time() * 1000)
    previo = cargar(ruta) if ruta.exists() else None
    if previo is not None and len(previo):
        desde = int(previo["timestamp"].iloc[-1])
    else:
        desde = ahora - dias * 86_400_000
    # La última vela aún no ha cerrado: se excluye para no operar con datos incompletos.
    paso_ms = exchange.parse_timeframe(timeframe) * 1000
    nuevo = descargar_ohlcv(exchange, par, timeframe, desde, hasta_ms=ahora - ahora % paso_ms)
    if previo is not None:
        nuevo = a_dataframe(pd.concat([previo[COLUMNAS], nuevo[COLUMNAS]]).values.tolist())
    guardar(nuevo, ruta)
    return nuevo
