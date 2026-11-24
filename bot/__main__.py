"""Línea de comandos: python -m bot <comando>."""
from __future__ import annotations

import argparse

from .config import cargar_config
from .datos import actualizar
from .exchange import crear_exchange, precio_actual


def cmd_precios(cfg, _args) -> None:
    ex = crear_exchange(cfg.exchange)
    for par in cfg.pares:
        print(f"{par}: {precio_actual(ex, par):,.2f}")


def cmd_descargar(cfg, args) -> None:
    fuente = args.fuente or cfg.fuente_historica
    ex = crear_exchange(fuente)
    for par in cfg.pares:
        df = actualizar(ex, fuente, par, args.timeframe or cfg.timeframe, args.dias)
        print(f"{par}: {len(df)} velas desde {df['fecha'].iloc[0]:%Y-%m-%d} hasta {df['fecha'].iloc[-1]:%Y-%m-%d %H:%M}")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="bot", description="Bot de trading BTC/ETH/LTC")
    p.add_argument("--config", help="ruta a config.yaml")
    sub = p.add_subparsers(dest="comando", required=True)

    sub.add_parser("precios", help="muestra el precio actual de cada par en el exchange")

    d = sub.add_parser("descargar", help="descarga velas históricas a data/")
    d.add_argument("--dias", type=int, default=1095, help="días de histórico (por defecto 3 años)")
    d.add_argument("--fuente", help="exchange de origen (por defecto fuente_historica)")
    d.add_argument("--timeframe", help="por defecto el de config.yaml")

    args = p.parse_args(argv)
    cfg = cargar_config(args.config)
    {"precios": cmd_precios, "descargar": cmd_descargar}[args.comando](cfg, args)


if __name__ == "__main__":
    main()
