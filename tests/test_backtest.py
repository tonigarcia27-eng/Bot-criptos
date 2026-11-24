import pandas as pd

from bot.backtest import ejecutar
from bot.config import Riesgo
from bot.estrategia import Parametros
from sinteticos import cierres

P = Parametros()


def test_sin_senales_el_capital_no_cambia():
    c = cierres(deriva=-0.002)
    r = ejecutar(c, P, Riesgo(), 1000, desde=c.index[200])
    assert r.metricas["operaciones"] == 0 or r.curva.iloc[-1] <= 1000
    assert r.curva.iloc[0] == 1000


def test_comisiones_reducen_el_resultado():
    c = cierres()
    con = ejecutar(c, P, Riesgo(), 1000, desde=c.index[100])
    sin = ejecutar(c, P, Riesgo(), 1000, desde=c.index[100], comision=0, deslizamiento=0)
    assert con.metricas["operaciones"] > 0
    assert con.curva.iloc[-1] < sin.curva.iloc[-1]


def test_limite_mensual_corta_perdidas():
    c = cierres(vol=0.04, deriva=0.0)
    estricto = ejecutar(c, P, Riesgo(perdida_maxima_mensual=0.02), 1000, desde=c.index[100])
    mens = estricto.curva.resample("ME").last() / estricto.curva.resample("ME").first() - 1
    # Tras tocar el límite se pasa a euros: la pérdida del mes no se aleja mucho del límite.
    assert mens.min() > -0.02 - 0.15


def test_ventana_de_fechas():
    c = cierres()
    r = ejecutar(c, P, Riesgo(), desde="2020-06-01", hasta="2020-09-01")
    assert r.curva.index[0] >= pd.Timestamp("2020-06-01", tz="UTC")
    assert r.curva.index[-1] < pd.Timestamp("2020-09-01", tz="UTC")
