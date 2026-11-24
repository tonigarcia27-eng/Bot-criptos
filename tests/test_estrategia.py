import numpy as np
import pandas as pd

from bot.estrategia import Parametros, pesos_objetivo
from sinteticos import cierres


def test_pesos_entre_0_y_un_tercio_y_suman_como_mucho_1():
    w = pesos_objetivo(cierres(), Parametros())
    assert (w >= 0).all().all()
    assert (w <= 1 / 3 + 1e-12).all().all()
    assert (w.sum(axis=1) <= 1 + 1e-9).all()


def test_mercado_bajista_queda_en_euros():
    fechas = pd.date_range("2020-01-01", periods=300, tz="UTC")
    bajando = pd.DataFrame({m: 100 * np.exp(-0.01 * np.arange(300)) for m in ["BTC/EUR", "ETH/EUR", "LTC/EUR"]},
                           index=fechas)
    assert pesos_objetivo(bajando, Parametros()).iloc[100:].sum().sum() == 0


def test_mercado_alcista_invierte():
    fechas = pd.date_range("2020-01-01", periods=300, tz="UTC")
    rng = np.random.default_rng(0)
    subiendo = pd.DataFrame({m: 100 * np.exp(np.cumsum(0.01 + rng.normal(0, 0.005, 300)))
                             for m in ["BTC/EUR", "ETH/EUR", "LTC/EUR"]}, index=fechas)
    w = pesos_objetivo(subiendo, Parametros(vol_objetivo=0))
    assert np.allclose(w.iloc[-1], 1 / 3)


def test_sin_mirar_al_futuro():
    c = cierres()
    completo = pesos_objetivo(c, Parametros())
    cortado = pesos_objetivo(c.iloc[:500], Parametros())
    pd.testing.assert_frame_equal(completo.iloc[:500], cortado)
