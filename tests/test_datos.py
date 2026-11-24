from bot import datos

HORA = 3_600_000


class ExchangeFalso:
    """Simula un exchange con una vela por hora y un máximo de `lote` velas por petición."""

    def __init__(self, n_velas=50, lote=7):
        self.velas = [[i * HORA, 1, 2, 0.5, 1.5, 10] for i in range(n_velas)]
        self.lote = lote
        self.peticiones = 0

    def parse_timeframe(self, tf):
        return 3600

    def milliseconds(self):
        return len(self.velas) * HORA

    def fetch_ohlcv(self, par, tf, since=0, limit=1000):
        self.peticiones += 1
        return [v for v in self.velas if v[0] >= since][: min(limit, self.lote)]


def test_descarga_pagina_hasta_el_final_sin_duplicados():
    ex = ExchangeFalso(n_velas=50, lote=7)
    df = datos.descargar_ohlcv(ex, "BTC/EUR", "1h", desde_ms=0)
    assert len(df) == 50
    assert df["timestamp"].is_unique
    assert ex.peticiones >= 8


def test_actualizar_es_incremental(tmp_path, monkeypatch):
    monkeypatch.setattr(datos, "CARPETA_DATOS", tmp_path)
    ex = ExchangeFalso(n_velas=30, lote=10)
    monkeypatch.setattr(datos.time, "time", lambda: 20 * HORA / 1000)
    primero = datos.actualizar(ex, "falso", "BTC/EUR", "1h", dias=10)
    assert len(primero) == 20
    monkeypatch.setattr(datos.time, "time", lambda: 30 * HORA / 1000)
    segundo = datos.actualizar(ex, "falso", "BTC/EUR", "1h", dias=10)
    assert len(segundo) == 30
    assert segundo["timestamp"].is_unique
