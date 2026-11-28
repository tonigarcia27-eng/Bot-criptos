from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from bot.backtest import ejecutar as backtest
from bot.config import Config, Freno, Riesgo, cargar_config
from bot.estrategia import Parametros, mercado_permite_reanudar
from bot.paper import Estado, paso_diario, resumen

P = Parametros(media=20, momentum=20, vol_objetivo=0.0)
SIN_LIMITE = 0.5


def cierres_con_caida():
    """Sube 200 días, se desploma un 40% en 3 días, baja 60 días más y vuelve a subir 200 días."""
    fondo = 0.8 + np.log(0.6)
    tramo = np.concatenate([np.linspace(0, 0.8, 200), np.linspace(0.8, fondo, 4)[1:],
                            np.linspace(fondo, fondo - 0.2, 60)[1:], np.linspace(fondo - 0.2, 1.5, 200)[1:]])
    fechas = pd.date_range("2021-01-01", periods=len(tramo), freq="D", tz="UTC")
    return pd.DataFrame({par: 100 * np.exp(tramo) * k for par, k in
                         [("BTC/EUR", 300), ("ETH/EUR", 20), ("LTC/EUR", 1)]}, index=fechas)


def riesgo(**kw):
    return Riesgo(perdida_maxima_mensual=SIN_LIMITE, freno=Freno(activo=True, **kw))


def test_config_carga_el_freno():
    f = cargar_config().riesgo.freno
    assert f.activo and 0 < f.caida_maxima < 1 and f.reactivar in {"tiempo", "amplia", "btc", "curva"}


def test_config_rechaza_reactivacion_desconocida(tmp_path):
    ruta = tmp_path / "config.yaml"
    ruta.write_text("riesgo:\n  freno:\n    reactivar: cuando_quiera\n")
    with pytest.raises(ValueError, match="reactivar"):
        cargar_config(ruta)


def test_backtest_salta_y_vuelve_solo():
    c = cierres_con_caida()
    r = backtest(c, P, riesgo(caida_maxima=0.15, pausa_dias=20, reactivar="amplia"), 1000, desde=c.index[30])
    ops = r.operaciones
    salto = ops.loc[ops.motivo == "freno", "fecha"].min()
    vuelta = ops.loc[ops.motivo == "fin del freno", "fecha"].min()
    assert pd.notna(salto) and pd.notna(vuelta)
    assert (vuelta - salto).days >= 20
    # Mientras está frenado no compra nada y el capital no se mueve (está en euros).
    entre = ops[(ops.fecha > salto) & (ops.fecha < vuelta)]
    assert entre.empty
    tramo = r.curva[(r.curva.index > salto) & (r.curva.index < vuelta)]
    assert tramo.max() - tramo.min() < 1e-6


def test_freno_limita_la_caida():
    c = cierres_con_caida()
    sin = backtest(c, P, Riesgo(perdida_maxima_mensual=SIN_LIMITE), 1000, desde=c.index[30])
    con = backtest(c, P, riesgo(caida_maxima=0.10, pausa_dias=10), 1000, desde=c.index[30])
    assert con.metricas["caida_maxima"] > sin.metricas["caida_maxima"]


def test_condiciones_de_reactivacion():
    c = cierres_con_caida()
    for modo in ("tiempo", "amplia", "btc", "curva"):
        s = mercado_permite_reanudar(c, P, modo)
        assert s.dtype == bool and len(s) == len(c)
    amplia = mercado_permite_reanudar(c, P, "amplia")
    assert not amplia.iloc[240] and amplia.iloc[-1]  # en plena caída no, al final de la subida sí


def test_paper_salta_y_vuelve_solo():
    c = cierres_con_caida()
    cfg = Config(riesgo=riesgo(caida_maxima=0.15, pausa_dias=20, reactivar="amplia"))
    estado, todas = None, []
    for f in c.index[30:]:
        hoy = (f + timedelta(days=1)).date()
        precios = c.loc[f].to_dict()
        estado = estado or Estado.nuevo(cfg, hoy, precios)
        todas += paso_diario(estado, c.loc[:f], precios, hoy, P, cfg)
        if estado.frenado_desde:
            assert sum(estado.unidades.values()) == 0  # frenado = todo en euros
    motivos = [o["motivo"] for o in todas]
    assert "freno" in motivos and "fin del freno" in motivos
    salto = next(o["fecha"] for o in todas if o["motivo"] == "freno")
    vuelta = next(o["fecha"] for o in todas if o["motivo"] == "fin del freno")
    assert (pd.Timestamp(vuelta) - pd.Timestamp(salto)).days >= 20
    assert not estado.frenado_desde


def test_resumen_muestra_el_freno(tmp_path):
    c = cierres_con_caida()
    cfg = Config(riesgo=riesgo())
    f = c.index[100]
    hoy = (f + timedelta(days=1)).date()
    precios = c.loc[f].to_dict()
    estado = Estado.nuevo(cfg, hoy, precios)
    paso_diario(estado, c.loc[:f], precios, hoy, P, cfg)
    assert "Freno automático" in resumen(estado, precios, tmp_path, cfg)
    estado.frenado_desde = hoy.isoformat()
    assert "ACTIVADO" in resumen(estado, precios, tmp_path, cfg)


def test_estado_antiguo_sin_campos_del_freno_sigue_funcionando():
    # La simulación de la rama paper se creó antes del freno: su estado.json no tiene esos campos.
    c = cierres_con_caida()
    cfg = Config(riesgo=riesgo())
    f = c.index[100]
    hoy = (f + timedelta(days=1)).date()
    antiguo = {"inicio": hoy.isoformat(), "capital_inicial": 200.0, "efectivo": 200.0,
               "unidades": {par: 0.0 for par in c.columns}, "precios_inicio": c.loc[f].to_dict()}
    estado = Estado(**antiguo)
    paso_diario(estado, c.loc[:f], c.loc[f].to_dict(), hoy, P, cfg)
    assert estado.maximo_freno >= 200.0
