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
    def __init__(self, retirar=False, saldo=None, llenado=None):
        self.retirar = retirar
        self.saldo = saldo or {"EUR": 200.0, "BTC": 0.0, "ETH": 0.0, "LTC": 0.0}
        self.ordenes = []
        self.canceladas = []
        self.precios = []
        # fracción de cada orden límite que se llena, por intento (por defecto, toda)
        self.llenado = list(llenado) if llenado is not None else None
        self._abiertas = {}

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

    def price_to_precision(self, _par, precio):
        return f"{precio:.2f}"

    def fetch_order_book(self, _par, _limite=None):
        return {"bids": [[99.0, 1.0]], "asks": [[101.0, 1.0]]}

    def create_order(self, par, tipo, lado, cantidad, precio, params):
        self.ordenes.append((par, tipo, lado, cantidad, params))
        self.precios.append(precio)
        if params.get("validate"):
            return {"id": None}
        oid = f"TX{len(self.ordenes)}"
        if tipo == "limit":
            fr = self.llenado.pop(0) if self.llenado else (0.0 if self.llenado == [] else 1.0)
            self._abiertas[oid] = {"status": "closed" if fr >= 1 else "open", "filled": cantidad * fr}
        return {"id": oid}

    def fetch_order(self, oid, _par):
        return dict(self._abiertas[oid])

    def cancel_order(self, oid, _par):
        self.canceladas.append(oid)
        self._abiertas[oid]["status"] = "canceled"


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
    assert ex.ordenes and all(o[1] == "limit" and o[4] == {"postOnly": True, "validate": True}
                              for o in ex.ordenes)
    assert all("no ejecutada" in h["resultado"] or "omitida" in h["resultado"] for h in hechas)


def test_omite_ordenes_por_debajo_del_minimo():
    ex = KrakenFalso()
    hechas = enviar(ex, [{"par": "LTC/EUR", "lado": "compra", "importe_eur": 1.0, "cantidad": 0.01}], real=True)
    assert not ex.ordenes and "omitida" in hechas[0]["resultado"]


def test_no_opera_si_la_clave_puede_retirar(tmp_path):
    from bot.real import ejecutar

    with pytest.raises(SystemExit, match="retirar"):
        ejecutar(Config(), P, KrakenFalso(retirar=True), {}, tmp_path)


def test_ignora_saltos_de_linea_al_pegar_las_claves(monkeypatch):
    from bot.exchange import crear_exchange

    monkeypatch.setenv("KRAKEN_API_KEY", "  clave\n")
    monkeypatch.setenv("KRAKEN_API_SECRET", "c2VjcmV0bw==\r\n")
    ex = crear_exchange("kraken", con_claves=True)
    assert ex.apiKey == "clave" and ex.secret == "c2VjcmV0bw=="


def _real(ex, cantidad=0.01):
    return enviar(ex, [{"par": "BTC/EUR", "lado": "compra", "importe_eur": 600.0, "cantidad": cantidad}],
                  real=True, dormir=lambda _s: None, intentos=3, espera=0)


def test_orden_limite_llena_no_va_a_mercado():
    ex = KrakenFalso()
    hechas = _real(ex)
    assert [o[1] for o in ex.ordenes] == ["limit"]
    par, _, lado, cantidad, params = ex.ordenes[0]
    assert lado == "buy" and params == {"postOnly": True} and cantidad == 0.01
    assert "mercado" not in hechas[0]["resultado"]


def test_compra_al_mejor_precio_de_compra_y_vende_al_de_venta():
    ex = KrakenFalso()
    _real(ex)
    enviar(ex, [{"par": "BTC/EUR", "lado": "venta", "importe_eur": 600.0, "cantidad": 0.01}],
           real=True, dormir=lambda _s: None, intentos=1, espera=0)
    assert [o[2] for o in ex.ordenes] == ["buy", "sell"] and ex.precios == [99.0, 101.0]


def test_si_no_se_llena_cancela_reintenta_y_el_resto_va_a_mercado():
    ex = KrakenFalso(llenado=[0.5, 0.0, 0.0])
    hechas = _real(ex)
    tipos = [o[1] for o in ex.ordenes]
    assert tipos == ["limit", "limit", "limit", "market"]
    assert len(ex.canceladas) == 3
    assert ex.ordenes[1][3] == pytest.approx(0.005)   # el segundo intento solo pide lo que falta
    assert ex.ordenes[-1][3] == pytest.approx(0.005)  # y a mercado va solo el resto
    assert "resto a mercado" in hechas[0]["resultado"]


def test_no_manda_a_mercado_restos_por_debajo_del_minimo():
    ex = KrakenFalso(llenado=[0.999])
    _real(ex, cantidad=0.01)
    assert [o[1] for o in ex.ordenes] == ["limit"]
