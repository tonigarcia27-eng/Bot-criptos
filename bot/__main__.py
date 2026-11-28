"""Línea de comandos: python -m bot <comando>."""
from __future__ import annotations

import argparse

from .config import cargar_config
from .datos import actualizar, cargar, ruta_csv
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


def cargar_historico(cfg, fuente=None) -> dict:
    fuente = fuente or cfg.fuente_historica
    datos = {}
    for par in cfg.pares:
        ruta = ruta_csv(fuente, par, cfg.timeframe)
        if not ruta.exists():
            raise SystemExit(f"Falta {ruta}. Ejecuta antes: python -m bot descargar")
        datos[par] = cargar(ruta)
    return datos


def cmd_backtest(cfg, args) -> None:
    from .backtest import comprar_y_mantener, ejecutar
    from .estrategia import cierres_diarios
    from .optimizar import cargar_parametros

    cierres = cierres_diarios(cargar_historico(cfg, args.fuente))
    p = cargar_parametros()
    desde = args.desde or cierres.index[p.dias_minimos]
    r = ejecutar(cierres, p, cfg.riesgo, cfg.capital_inicial, desde=desde, hasta=args.hasta)
    print(f"Parámetros: {p.como_dict()}")
    for k, v in r.metricas.items():
        print(f"  {k}: {v:.4f}")
    ref = comprar_y_mantener(cierres, desde, args.hasta)
    print(f"  comprar_y_mantener: {ref.iloc[-1] - 1:.4f}")


def cmd_optimizar(cfg, args) -> None:
    from pathlib import Path

    from .estrategia import cierres_diarios
    from .optimizar import (combinaciones, fuera_de_muestra, guardar_parametros, informe,
                            parametros_consistentes, walk_forward)

    cierres = cierres_diarios(cargar_historico(cfg, args.fuente))
    candidatos = combinaciones()
    print(f"Probando {len(candidatos)} combinaciones de parámetros...")
    oos = fuera_de_muestra(cierres, cfg.riesgo, cfg.capital_inicial, candidatos)
    wf = walk_forward(cierres, cfg.riesgo, cfg.capital_inicial, candidatos)
    tabla = parametros_consistentes(cierres, cfg.riesgo, cfg.capital_inicial, candidatos)
    elegido = next(r for r in tabla if r["parametros"] == oos["parametros"])
    guardar_parametros(elegido["parametros"])
    texto = informe(oos, wf, tabla, elegido, cierres, cfg.riesgo, cfg.capital_inicial)
    salida = Path(args.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(texto, encoding="utf-8")
    print(texto)


def cmd_freno(cfg, args) -> None:
    from pathlib import Path

    from .estrategia import cierres_diarios
    from .freno import estudiar, informe
    from .optimizar import cargar_parametros

    cierres = cierres_diarios(cargar_historico(cfg, args.fuente))
    texto = informe(estudiar(cierres, cargar_parametros(), cfg.riesgo, 1000.0), cfg.riesgo, 1000.0)
    salida = Path(args.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(texto, encoding="utf-8")
    print(texto)


def cmd_paper(cfg, args) -> None:
    from pathlib import Path

    from .optimizar import cargar_parametros
    from .paper import CARPETA, ejecutar

    if cfg.modo != "paper":
        raise SystemExit("config.yaml no está en modo paper")
    print(ejecutar(cfg, cargar_parametros(), crear_exchange(cfg.exchange), Path(args.carpeta or CARPETA)))


def cmd_kraken(cfg, _args) -> None:
    from .real import comprobar

    print(comprobar(cfg, crear_exchange(cfg.exchange, con_claves=True)))


def cmd_real(cfg, args) -> None:
    import os
    from pathlib import Path

    from .optimizar import cargar_parametros
    from .real import CARPETA, ejecutar

    ex = crear_exchange(cfg.exchange, con_claves=True)
    print(ejecutar(cfg, cargar_parametros(), ex, dict(os.environ), Path(args.carpeta or CARPETA)))


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="bot", description="Bot de trading BTC/ETH/LTC")
    p.add_argument("--config", help="ruta a config.yaml")
    sub = p.add_subparsers(dest="comando", required=True)

    sub.add_parser("precios", help="muestra el precio actual de cada par en el exchange")

    d = sub.add_parser("descargar", help="descarga velas históricas a data/")
    d.add_argument("--dias", type=int, default=3000, help="días de histórico (por defecto ~8 años)")
    d.add_argument("--fuente", help="exchange de origen (por defecto fuente_historica)")
    d.add_argument("--timeframe", help="por defecto el de config.yaml")

    b = sub.add_parser("backtest", help="prueba la estrategia (estrategia.json) con el histórico")
    b.add_argument("--fuente")
    b.add_argument("--desde", help="AAAA-MM-DD")
    b.add_argument("--hasta", help="AAAA-MM-DD")

    o = sub.add_parser("optimizar", help="busca parámetros con walk-forward y escribe el informe")
    o.add_argument("--fuente")
    o.add_argument("--salida", default="resultados/informe.md")

    fr = sub.add_parser("freno", help="estudia el freno automático de pérdidas y escribe el informe")
    fr.add_argument("--fuente")
    fr.add_argument("--salida", default="resultados/informe-freno.md")

    pt = sub.add_parser("paper", help="ejecuta un día de paper trading con precios reales de Kraken")
    pt.add_argument("--carpeta", help="dónde guardar el estado (por defecto paper/)")

    sub.add_parser("kraken", help="comprueba las claves de Kraken y muestra los saldos (no opera)")
    r = sub.add_parser("real", help="calcula las órdenes del día sobre la cuenta de Kraken; "
                                    "solo las ejecuta con modo: real y BOT_DINERO_REAL=si")
    r.add_argument("--carpeta", help="dónde guardar el estado del modo real (por defecto real/)")

    args = p.parse_args(argv)
    cfg = cargar_config(args.config)
    {"precios": cmd_precios, "descargar": cmd_descargar,
     "backtest": cmd_backtest, "optimizar": cmd_optimizar, "freno": cmd_freno,
     "paper": cmd_paper, "kraken": cmd_kraken, "real": cmd_real}[args.comando](cfg, args)


if __name__ == "__main__":
    main()
