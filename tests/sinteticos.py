import numpy as np
import pandas as pd


def serie(n=3000, deriva=0.0004, vol=0.02, semilla=0, inicio=100.0, freq="4h"):
    rng = np.random.default_rng(semilla)
    rets = rng.normal(deriva, vol, n)
    cierre = inicio * np.exp(np.cumsum(rets))
    apertura = np.concatenate([[inicio], cierre[:-1]])
    alto = np.maximum(apertura, cierre) * (1 + np.abs(rng.normal(0, vol / 2, n)))
    bajo = np.minimum(apertura, cierre) * (1 - np.abs(rng.normal(0, vol / 2, n)))
    ts = pd.date_range("2020-01-01", periods=n, freq=freq, tz="UTC")
    return pd.DataFrame({
        "timestamp": (ts - pd.Timestamp(0, tz="UTC")) // pd.Timedelta("1ms"), "open": apertura,
        "high": alto, "low": bajo, "close": cierre, "volume": 1.0, "fecha": ts,
    })


def cierres(n=900, semillas=(0, 1, 2), **kw):
    from bot.estrategia import cierres_diarios
    datos = {f"{m}/EUR": serie(n=n * 6, semilla=s, **kw) for m, s in zip(["BTC", "ETH", "LTC"], semillas)}
    return cierres_diarios(datos)
