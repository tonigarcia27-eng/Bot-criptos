from datetime import timedelta

import ccxt
import pytest

from bot.config import Config, Real
from bot.estrategia import Parametros
from bot.paper import Estado
from bot.real import comprobar, dinero_real_activado, enviar, ordenes_del_dia, puede_retirar
from sinteticos import cierres

P = Parametros()


class KrakenFalso:
    def __init__(self, retirar=False, saldo=None):
        self.retirar = retirar
        self.saldo = saldo or {"EUR": 200.0, "BTC": 0.0, "ETH": 0.0, "LTC": 0.0}
        self.ordenes = []

    def privatePostWithdrawMethods(self, _params):
        if self.retirar is None:
            raise ccxt.NetworkError("sin conexión")
        if not self.retirar:
            raise ccxt.PermissionDenied("EGeneral:Permission denied")
        return {"result": []}

    def fetch_balance(self):
        return {"total": dict(self.saldo)}

    def load_markets(self):
        pass

    def market(self, par):
        return {"limits": {"amount": {"min": {"BTC/EUR": 0.00005, "ETH/EUR": 0.002, "LTC/EUR": 0.05}[par]}}}

    def amount_to_precision(self, _par, cantidad):
        return f"{cantidad:.8f}"

    def create_order(self, par, tipo, lado, cantidad, precio, params):
        self.ordenes.append((par, tipo, lado, cantidad, params))
        return {"id": None if params.get("validate") else "TX1"}


def test_dinero_real_necesita_las_dos_llaves():
    assert not dinero_real_activado(Config(), {})
    assert not dinero_real_activado(Config(), {"BOT_DINERO_REAL": "si"})
    assert not dinero_real_activado(Config(modo="real"), {})
    assert not dinero_real_activado(Config(modo="real"), {"BOT_DINERO_REAL": "true"})
    assert dinero_real_activado(Config(modo="real"), {"BOT_DINERO_REAL": "si"})


def test_detecta_permiso_de_retirada():
    assert puede_retirar(KrakenFalso(retirar=True)) is True
    assert puede_retirar(KrakenFalso(retirar=False)) is False
    assert puede_retirar(KrakenFalso(retirar=None)) is None
    assert "PELIGRO" in comprobar(Config(), KrakenFalso(retirar=True))
    assert "no puede retirar" in comprobar(Config(), KrakenFalso())


def _ordenes(cfg, efectivo, unidades):
    c = cierres()
    f = c.index[550]  # día en que la estrategia quiere comprar
    hoy = (f + timedelta(days=1)).date()
    precios = c.loc[f].to_dict()
    estado = Estado.nuevo(cfg, hoy, precios)
    return ordenes_del_dia(estado, c.loc[:f], precios, hoy, P, cfg, efectivo, unidades), precios


def test_nunca_gestiona_mas_del_capital_maximo():
    cfg = Config(real=Real(capital_maximo=100))
    ops, _ = _ordenes(cfg, 5000.0, {"BTC/EUR": 0.0, "ETH/EUR": 0.0, "LTC/EUR": 0.0})
    compras = sum(o["importe_eur"] for o in ops if o["lado"] == "compra")
    assert 0 < compras <= 100


def test_en_ensayo_kraken_solo_valida():
    cfg = Config()
    ops, _ = _ordenes(cfg, 200.0, {"BTC/EUR": 0.0, "ETH/EUR": 0.0, "LTC/EUR": 0.0})
    ex = KrakenFalso()
    hechas = enviar(ex, ops, real=False)
    assert ex.ordenes and all(o[4] == {"validate": True} for o in ex.ordenes)
    assert all("no ejecutada" in h["resultado"] or "omitida" in h["resultado"] for h in hechas)


def test_omite_ordenes_por_debajo_del_minimo():
    ex = KrakenFalso()
    hechas = enviar(ex, [{"par": "LTC/EUR", "lado": "compra", "importe_eur": 1.0, "cantidad": 0.01}], real=True)
    assert not ex.ordenes and "omitida" in hechas[0]["resultado"]


def test_no_opera_si_la_clave_puede_retirar(tmp_path):
    from bot.real import ejecutar

    with pytest.raises(SystemExit, match="retirar"):
        ejecutar(Config(), P, KrakenFalso(retirar=True), {}, tmp_path)
