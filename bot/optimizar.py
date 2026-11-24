"""Búsqueda de parámetros con validación walk-forward.

Para no "sobreoptimizar" (quedarse con lo que mejor encaja con el pasado por casualidad):
  1. Prueba fuera de muestra: se eligen los parámetros con la primera mitad del
     histórico y se prueban, sin tocarlos, en la segunda mitad.
  2. Walk-forward: se eligen parámetros con 24 meses de datos y se prueban en los
     6 meses siguientes, que no se usaron para elegir. Se avanza 6 meses y se
     repite. Encadenando esos tramos de prueba se obtiene una estimación honesta.
  3. Parámetros finales: los elegidos en el paso 1, que ya demostraron funcionar
     en datos que no se usaron para elegirlos.
"""
from __future__ import annotations

import itertools
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from .backtest import comprar_y_mantener, ejecutar, metricas, rentabilidad_mensual
from .config import RAIZ, Riesgo
from .estrategia import Parametros, pesos_objetivo

REJILLA = {
    "media": [20, 50, 100],
    "momentum": [14, 30, 60, 90],
    "vol_objetivo": [0.0, 0.3, 0.5, 0.8],
}
RUTA_PARAMETROS = RAIZ / "estrategia.json"


def combinaciones(rejilla: dict = REJILLA) -> list[Parametros]:
    claves = list(rejilla)
    return [replace(Parametros(), **dict(zip(claves, v)))
            for v in itertools.product(*(rejilla[c] for c in claves))]


def puntuacion(m: dict) -> float:
    """Sharpe: rentabilidad por unidad de riesgo."""
    return m.get("sharpe", -np.inf) if m else -np.inf


def inicio_operable(cierres: pd.DataFrame, candidatos: list[Parametros]) -> pd.Timestamp:
    dias = max(p.dias_minimos for p in candidatos)
    return cierres.index[min(dias, len(cierres) - 1)]


def walk_forward(cierres, riesgo: Riesgo, capital: float, candidatos: list[Parametros],
                 meses_entreno: int = 24, meses_prueba: int = 6):
    inicio, fin = inicio_operable(cierres, candidatos), cierres.index[-1]
    ventanas, t0 = [], inicio
    while t0 + pd.DateOffset(months=meses_entreno) < fin:
        t1 = t0 + pd.DateOffset(months=meses_entreno)
        ventanas.append((t0, t1, min(t1 + pd.DateOffset(months=meses_prueba), fin + pd.Timedelta(days=1))))
        t0 += pd.DateOffset(months=meses_prueba)
    if not ventanas:
        return None
    mejores = [(-np.inf, candidatos[0])] * len(ventanas)
    for p in candidatos:
        pesos = pesos_objetivo(cierres, p)
        for i, (a, b, _) in enumerate(ventanas):
            s = puntuacion(ejecutar(cierres, p, riesgo, capital, desde=a, hasta=b, pesos=pesos).metricas)
            if s > mejores[i][0]:
                mejores[i] = (s, p)
    tramos, curvas, ops, cap = [], [], [], capital
    for (t0, t1, t2), (_, p) in zip(ventanas, mejores):
        prueba = ejecutar(cierres, p, riesgo, cap, desde=t1, hasta=t2)
        curvas.append(prueba.curva)
        ops.append(prueba.operaciones)
        ref = comprar_y_mantener(cierres, t1, t2)
        tramos.append({"entreno": f"{t0:%Y-%m} a {t1:%Y-%m}", "prueba": f"{t1:%Y-%m-%d} a {t2:%Y-%m-%d}",
                       "parametros": p, "rentabilidad": prueba.metricas["rentabilidad_total"],
                       "referencia": float(ref.iloc[-1] - 1)})
        cap = float(prueba.curva.iloc[-1])
    curva = pd.concat(curvas)
    operaciones = pd.concat(ops, ignore_index=True)
    ref = comprar_y_mantener(cierres, curva.index[0]) * capital
    return {"curva": curva, "operaciones": operaciones, "tramos": tramos,
            "metricas": metricas(curva, operaciones, capital),
            "referencia": metricas(ref, operaciones.iloc[:0], capital)}


def fuera_de_muestra(cierres, riesgo: Riesgo, capital: float, candidatos: list[Parametros]):
    """Elige con la primera mitad del histórico y prueba sin cambios en la segunda."""
    inicio = inicio_operable(cierres, candidatos)
    corte = inicio + (cierres.index[-1] - inicio) / 2
    corte = pd.Timestamp(corte.date(), tz="UTC")
    mejor = max(candidatos, key=lambda p: puntuacion(
        ejecutar(cierres, p, riesgo, capital, desde=inicio, hasta=corte).metricas))
    prueba = ejecutar(cierres, mejor, riesgo, capital, desde=corte)
    ref = comprar_y_mantener(cierres, corte) * capital
    medianas = pd.DataFrame([ejecutar(cierres, p, riesgo, capital, desde=corte).metricas
                             for p in candidatos]).median()
    return {"corte": corte, "inicio": inicio, "parametros": mejor, "curva": prueba.curva,
            "metricas": prueba.metricas, "referencia": metricas(ref, prueba.operaciones.iloc[:0], capital),
            "mediana_todas": medianas.to_dict()}


def parametros_consistentes(cierres, riesgo: Riesgo, capital: float, candidatos: list[Parametros]):
    inicio = inicio_operable(cierres, candidatos)
    tabla = []
    for p in candidatos:
        r = ejecutar(cierres, p, riesgo, capital, desde=inicio)
        anual = r.curva.resample("YE").last()
        anual = anual / anual.shift().fillna(capital) - 1
        tabla.append({"parametros": p, "peor_año": float(anual.min()), "media_anual": float(anual.mean()),
                      "consistencia": float(anual.mean() - anual.std()), **r.metricas})
    tabla.sort(key=lambda r: r["sharpe"], reverse=True)
    return tabla


def guardar_parametros(p: Parametros, ruta: Path = RUTA_PARAMETROS) -> None:
    ruta.write_text(json.dumps(p.como_dict(), indent=2) + "\n", encoding="utf-8")


def cargar_parametros(ruta: Path = RUTA_PARAMETROS) -> Parametros:
    if ruta.exists():
        return Parametros(**json.loads(ruta.read_text(encoding="utf-8")))
    return Parametros()


def _pct(x: float) -> str:
    return f"{x * 100:+.1f}%"


def _p(p: Parametros) -> str:
    vol = f"{p.vol_objetivo:.0%}" if p.vol_objetivo else "sin control"
    return f"media {p.media}d, momentum {p.momentum}d, volatilidad {vol}"


def _tabla_comparada(m: dict, r: dict, operaciones: bool = True) -> list[str]:
    l = ["| Métrica | Bot | Comprar y mantener |", "|---|---|---|"]
    for clave, nombre in [("rentabilidad_total", "Rentabilidad total"), ("rentabilidad_anual", "Rentabilidad anual"),
                          ("caida_maxima", "Caída máxima"), ("peor_mes", "Peor mes"), ("mejor_mes", "Mejor mes")]:
        l.append(f"| {nombre} | {_pct(m[clave])} | {_pct(r[clave])} |")
    l += [f"| Meses en positivo | {m['meses_positivos']:.0%} | {r['meses_positivos']:.0%} |",
          f"| Sharpe | {m['sharpe']:.2f} | {r['sharpe']:.2f} |"]
    if operaciones:
        l.append(f"| Operaciones | {m['operaciones']} | |")
    return l


def informe(oos: dict, wf: dict | None, tabla: list[dict], elegido: dict, cierres: pd.DataFrame,
            riesgo: Riesgo, capital: float) -> str:
    l = [
        "# Informe de backtesting",
        "",
        f"Datos diarios de {', '.join(cierres.columns)} del {cierres.index[0]:%Y-%m-%d} al "
        f"{cierres.index[-1]:%Y-%m-%d}. Capital inicial {capital:,.0f} EUR. Incluye comisión "
        "de Kraken (0,26%) y deslizamiento (0,05%) en cada operación, y el límite de pérdida "
        f"mensual del {riesgo.perdida_maxima_mensual:.0%}.",
        "",
        "## 1. Prueba fuera de muestra (la más importante)",
        "",
        f"Parámetros elegidos solo con datos del {oos['inicio']:%Y-%m-%d} al {oos['corte']:%Y-%m-%d} "
        f"({_p(oos['parametros'])}) y probados sin cambios del {oos['corte']:%Y-%m-%d} hasta hoy, "
        "un periodo que no se usó para elegirlos.",
        "",
    ]
    l += _tabla_comparada(oos["metricas"], oos["referencia"])
    med = oos["mediana_todas"]
    l += ["", f"Mediana de las {len(tabla)} combinaciones en ese mismo periodo: rentabilidad anual "
          f"{_pct(med['rentabilidad_anual'])}, caída máxima {_pct(med['caida_maxima'])}, Sharpe {med['sharpe']:.2f}.",
          "", "Por año: " + ", ".join(
              f"{f:%Y} {_pct(v)}" for f, v in (lambda a: a / a.shift().fillna(capital) - 1)(
                  oos["curva"].resample("YE").last()).items()),
          "",
          "## 2. Walk-forward (reoptimizando cada 6 meses)",
          "",
          "Parámetros elegidos con 24 meses de datos y probados en los 6 meses siguientes. Sirve para "
          "ver si conviene reajustar los parámetros a menudo.",
          ""]
    if wf:
        l += _tabla_comparada(wf["metricas"], wf["referencia"])
        l += ["", "| Entreno | Prueba | Bot | Comprar y mantener | Parámetros |", "|---|---|---|---|---|"]
        l += [f"| {t['entreno']} | {t['prueba']} | {_pct(t['rentabilidad'])} | {_pct(t['referencia'])} | {_p(t['parametros'])} |"
              for t in wf["tramos"]]
        anual = wf["curva"].resample("YE").last()
        anual = anual / anual.shift().fillna(capital) - 1
        l += ["", "Por año: " + ", ".join(f"{f:%Y} {_pct(v)}" for f, v in anual.items())]
        mens = rentabilidad_mensual(wf["curva"], capital)
        l += ["", "Últimos 12 meses: " + ", ".join(f"{f:%Y-%m} {_pct(v)}" for f, v in mens.tail(12).items())]
    else:
        l.append("No hay datos suficientes para el walk-forward.")

    e = elegido
    l += ["", "## 3. Parámetros elegidos para el bot", "",
          f"**{_p(e['parametros'])}**, rebalanceo cada {e['parametros'].rebalanceo_dias} días. "
          "Son los de la prueba fuera de muestra: ya demostraron funcionar con datos que no se usaron para elegirlos.",
          "",
          f"En todo el histórico (dentro de muestra, optimista): rentabilidad anual {_pct(e['rentabilidad_anual'])}, "
          f"caída máxima {_pct(e['caida_maxima'])}, peor año {_pct(e['peor_año'])}, Sharpe {e['sharpe']:.2f}.",
          f"Puesto {next(i for i, r in enumerate(tabla, 1) if r is e)} de {len(tabla)} por Sharpe en todo el histórico.", "", "Las 10 mejores combinaciones por Sharpe:", "",
          "| Parámetros | Rent. anual | Caída máx | Peor año | Sharpe |", "|---|---|---|---|---|"]
    l += [f"| {_p(r['parametros'])} | {_pct(r['rentabilidad_anual'])} | {_pct(r['caida_maxima'])} | "
          f"{_pct(r['peor_año'])} | {r['sharpe']:.2f} |" for r in tabla[:10]]
    l += ["", f"Mediana del Sharpe de las {len(tabla)} combinaciones: {np.median([r['sharpe'] for r in tabla]):.2f} "
          "(si casi todas funcionan parecido, la estrategia es robusta y no depende de un ajuste fino).",
          "", f"Guardado en `estrategia.json`: `{json.dumps(e['parametros'].como_dict())}`", ""]
    return "\n".join(l)
