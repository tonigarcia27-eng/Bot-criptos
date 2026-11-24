import pandas as pd

from bot.backtest import ejecutar
from bot.config import Riesgo
from bot.estrategia import Parametros
from sinteticos import serie

P = Parametros()


def datos(**kw):
    return {f"{m}/EUR": serie(semilla=i, **kw) for i, m in enumerate(["BTC", "ETH", "LTC"])}


def test_capital_cuadra_con_operaciones():
    r = ejecutar(datos(), P, Riesgo())
    assert len(r.operaciones) > 0
    assert abs(r.curva.iloc[-1] - (1000 + r.operaciones["beneficio"].sum())) < 1e-6


def test_perdida_por_operacion_limitada_al_riesgo():
    # Riesgo 1%: salvo huecos de precio, ninguna operación pierde mucho más del 1% del capital.
    r = ejecutar(datos(vol=0.03), P, Riesgo(por_operacion=0.01))
    sin_hueco = r.operaciones[r.operaciones["motivo"] != "stop (hueco)"]
    assert sin_hueco["beneficio"].min() > -1000 * 0.02 * 1.5


def test_limite_mensual_bloquea_entradas():
    # Mercado bajista: con un límite mensual muy estricto se opera menos.
    d = datos(deriva=-0.0005, vol=0.03)
    normal = ejecutar(d, P, Riesgo(perdida_maxima_mensual=0.5))
    estricto = ejecutar(d, P, Riesgo(perdida_maxima_mensual=0.01))
    assert len(estricto.operaciones) < len(normal.operaciones)


def test_nunca_mas_posiciones_que_el_maximo_ni_efectivo_negativo():
    r = ejecutar(datos(), P, Riesgo(max_posiciones_abiertas=1))
    ops = r.operaciones.sort_values("entrada")
    for _, a in ops.iterrows():
        solapadas = ops[(ops["entrada"] < a["salida"]) & (ops["salida"] > a["entrada"])]
        assert len(solapadas) <= 1


def test_ventana_de_fechas():
    r = ejecutar(datos(), P, Riesgo(), desde="2022-06-01", hasta="2022-09-01")
    assert r.curva.index[0] >= pd.Timestamp("2022-06-01", tz="UTC")
    assert r.curva.index[-1] < pd.Timestamp("2022-09-01", tz="UTC")
