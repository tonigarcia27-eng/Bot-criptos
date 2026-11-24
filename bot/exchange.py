"""Conexión con los exchanges a través de ccxt."""
from __future__ import annotations

import os

import ccxt


def crear_exchange(nombre: str = "kraken", con_claves: bool = False) -> ccxt.Exchange:
    """Crea el cliente del exchange.

    Sin claves solo se pueden leer datos públicos (precios, velas), que es todo lo
    que necesita el modo paper. Las claves se leen de variables de entorno
    (KRAKEN_API_KEY / KRAKEN_API_SECRET) y solo se usan en modo real.
    """
    clase = getattr(ccxt, nombre)
    opciones: dict = {"enableRateLimit": True}
    if con_claves:
        prefijo = nombre.upper()
        clave = os.environ.get(f"{prefijo}_API_KEY")
        secreto = os.environ.get(f"{prefijo}_API_SECRET")
        if not clave or not secreto:
            raise RuntimeError(
                f"Faltan {prefijo}_API_KEY y {prefijo}_API_SECRET en las variables de entorno"
            )
        opciones.update(apiKey=clave, secret=secreto)
    return clase(opciones)


def precio_actual(exchange: ccxt.Exchange, par: str) -> float:
    ticker = exchange.fetch_ticker(par)
    return float(ticker["last"])
