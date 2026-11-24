import pytest

from bot.config import cargar_config


def test_config_por_defecto_es_valida():
    cfg = cargar_config()
    assert cfg.modo == "paper"
    assert {p.split("/")[0] for p in cfg.pares} == {"BTC", "ETH", "LTC"}


def test_rechaza_monedas_no_permitidas(tmp_path):
    ruta = tmp_path / "config.yaml"
    ruta.write_text("pares: [BTC/EUR, DOGE/EUR]\n")
    with pytest.raises(ValueError, match="DOGE"):
        cargar_config(ruta)


def test_rechaza_riesgo_excesivo(tmp_path):
    ruta = tmp_path / "config.yaml"
    ruta.write_text("riesgo:\n  por_operacion: 0.2\n")
    with pytest.raises(ValueError):
        cargar_config(ruta)
