from datetime import timedelta

from bot.backtest import ejecutar as backtest
from bot.config import Config, Riesgo
from bot.estrategia import Parametros
from bot.paper import Estado, cargar_estado, guardar, paso_diario, reiniciar_si_cambia_capital, resumen
from sinteticos import cierres

P = Parametros()


def simular(c, desde, dias, riesgo=None):
    cfg = Config(riesgo=riesgo or Riesgo())
    fechas = c.index[desde:desde + dias]
    estado = None
    todas = []
    for f in fechas:
        hoy = (f + timedelta(days=1)).date()  # se ejecuta justo después del cierre del día f
        precios = c.loc[f].to_dict()
        estado = estado or Estado.nuevo(cfg, hoy, precios)
        todas += paso_diario(estado, c.loc[:f], precios, hoy, P, cfg)
    return estado, todas, precios, fechas


def test_paper_reproduce_el_backtest():
    # Sin límite mensual (en paper el cambio de mes cae un día después), el resultado es idéntico.
    c = cierres()
    sin_limite = Riesgo(perdida_maxima_mensual=0.5)
    estado, ops, precios, fechas = simular(c, 200, 400, sin_limite)
    bt = backtest(c, P, sin_limite, 1000, desde=fechas[0], hasta=fechas[-1] + timedelta(days=1))
    assert len(ops) == len(bt.operaciones) > 10
    assert abs(estado.capital(precios) - bt.curva.iloc[-1]) < 1e-6


def test_no_repite_el_mismo_dia():
    c = cierres()
    cfg = Config()
    f = c.index[300]
    hoy = (f + timedelta(days=1)).date()
    estado = Estado.nuevo(cfg, hoy, c.loc[f].to_dict())
    paso_diario(estado, c.loc[:f], c.loc[f].to_dict(), hoy, P, cfg)
    antes = (estado.efectivo, dict(estado.unidades))
    assert paso_diario(estado, c.loc[:f], c.loc[f].to_dict(), hoy, P, cfg) == []
    assert (estado.efectivo, estado.unidades) == antes


def test_guardar_y_cargar(tmp_path):
    c = cierres()
    estado, ops, precios, fechas = simular(c, 200, 60)
    guardar(estado, ops, precios, fechas[-1].date(), tmp_path)
    assert cargar_estado(tmp_path) == estado
    texto = resumen(estado, precios, tmp_path)
    assert "Capital simulado" in texto and "BTC/EUR" in texto
    assert (tmp_path / "operaciones.csv").exists() and (tmp_path / "diario.csv").exists()


def test_cambiar_capital_reinicia_la_simulacion(tmp_path):
    c = cierres()
    estado, ops, precios, fechas = simular(c, 200, 10)
    guardar(estado, ops, precios, fechas[-1].date(), tmp_path)
    assert reiniciar_si_cambia_capital(Config(capital_inicial=estado.capital_inicial), tmp_path) == estado
    assert reiniciar_si_cambia_capital(Config(capital_inicial=200), tmp_path) is None
    assert not (tmp_path / "estado.json").exists() and not (tmp_path / "diario.csv").exists()
    archivado = tmp_path / "anteriores" / f"{estado.inicio}_{estado.capital_inicial:g}eur"
    assert (archivado / "estado.json").exists() and (archivado / "diario.csv").exists()
