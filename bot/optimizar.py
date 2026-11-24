"""Búsqueda de parámetros con validación walk-forward.

Para no "sobreoptimizar" (elegir lo que mejor encaja con el pasado por casualidad):
  1. Walk-forward: se eligen parámetros con 12 meses de datos y se prueban en los
     3 meses siguientes, que no se usaron para elegir. Se avanza 3 meses y se
     repite. Encadenando esos tramos de prueba se obtiene una estimación honesta
     de lo que habría ganado el bot.
  2. Parámetros finales: los que dan resultados más consistentes en todos los
     semestres del histórico, no los que más ganan en total.
"""
from __future__ import annotations

import itertools
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from .backtest import comprar_y_mantener, ejecutar, metricas, preparar
from .config import RAIZ, Riesgo
from .estrategia import Parametros

REJILLA = {
    "ema_rapida": [10, 20, 30],
    "ema_lenta": [50, 80],
    "ema_tendencia": [100, 200],
    "atr_stop": [2.0, 3.0],
    "atr_trailing": [3.0, 4.0, 5.0],
    "rsi_max": [70.0, 80.0],
}
RUTA_PARAMETROS = RAIZ / "estrategia.json"


def combinaciones(rejilla: dict = REJILLA) -> list[Parametros]:
    claves = list(rejilla)
    return [replace(Parametros(), **dict(zip(claves, vals)))
            for vals in itertools.product(*(rejilla[c] for c in claves))
            if dict(zip(claves, vals)).get("ema_rapida", 0) < dict(zip(claves, vals)).get("ema_lenta", 1)]


def puntuacion(m: dict, min_operaciones: int = 6) -> float:
    """Rentabilidad ajustada al riesgo: premia ganar y castiga las caídas."""
    if not m or m["operaciones"] < min_operaciones:
        return -np.inf
    return m["rentabilidad_total"] / max(abs(m["caida_maxima"]), 0.02)


def rango_fechas(datos: dict[str, pd.DataFrame]) -> tuple[pd.Timestamp, pd.Timestamp]:
    inicio = max(df["fecha"].iloc[0] for df in datos.values())
    fin = min(df["fecha"].iloc[-1] for df in datos.values())
    return inicio, fin


def walk_forward(datos, riesgo: Riesgo, capital: float, candidatos: list[Parametros],
                 meses_entreno: int = 12, meses_prueba: int = 3, calentamiento_meses: int = 2):
    inicio, fin = rango_fechas(datos)
    inicio = (inicio + pd.DateOffset(months=calentamiento_meses)).normalize()
    ventanas = []
    t0 = inicio
    while t0 + pd.DateOffset(months=meses_entreno) < fin:
        t1 = t0 + pd.DateOffset(months=meses_entreno)
        t2 = min(t1 + pd.DateOffset(months=meses_prueba), fin + pd.Timedelta(hours=1))
        ventanas.append((t0, t1, t2))
        t0 = t0 + pd.DateOffset(months=meses_prueba)
    # Puntuar cada candidato en cada ventana de entrenamiento (señales calculadas una vez).
    mejores = [(-np.inf, candidatos[0])] * len(ventanas)
    for p in candidatos:
        sen = preparar(datos, p)
        for i, (a, b, _) in enumerate(ventanas):
            s = puntuacion(ejecutar(datos, p, riesgo, capital, desde=a, hasta=b, senales=sen).metricas)
            if s > mejores[i][0]:
                mejores[i] = (s, p)
    tramos, curvas, ops = [], [], []
    cap = capital
    for (t0, t1, t2), (_, mejor_p) in zip(ventanas, mejores):
        prueba = ejecutar(datos, mejor_p, riesgo, cap, desde=t1, hasta=t2)
        if prueba.curva.empty:
            break
        curvas.append(prueba.curva)
        if not prueba.operaciones.empty:
            ops.append(prueba.operaciones)
        tramos.append({"entreno": f"{t0:%Y-%m} a {t1:%Y-%m}", "prueba": f"{t1:%Y-%m-%d} a {t2:%Y-%m-%d}",
                       "parametros": mejor_p, "rentabilidad": prueba.metricas["rentabilidad_total"]})
        cap = float(prueba.curva.iloc[-1])
    if not curvas:
        return None
    curva = pd.concat(curvas)
    operaciones = pd.concat(ops, ignore_index=True) if ops else pd.DataFrame(columns=["beneficio"])
    return {"curva": curva, "operaciones": operaciones, "tramos": tramos,
            "metricas": metricas(curva, operaciones, capital),
            "comprar_y_mantener": comprar_y_mantener(datos, curva.index[0], curva.index[-1] + pd.Timedelta(hours=1))}


def parametros_consistentes(datos, riesgo: Riesgo, capital: float, candidatos: list[Parametros],
                            meses_segmento: int = 6, calentamiento_meses: int = 2):
    inicio, fin = rango_fechas(datos)
    inicio = (inicio + pd.DateOffset(months=calentamiento_meses)).normalize()
    cortes = []
    t = inicio
    while t < fin:
        cortes.append((t, min(t + pd.DateOffset(months=meses_segmento), fin + pd.Timedelta(hours=1))))
        t += pd.DateOffset(months=meses_segmento)
    tabla = []
    for p in candidatos:
        sen = preparar(datos, p)
        total = ejecutar(datos, p, riesgo, capital, desde=inicio, senales=sen).metricas
        rents = [ejecutar(datos, p, riesgo, capital, desde=a, hasta=b, senales=sen).metricas.get("rentabilidad_total", 0.0)
                 for a, b in cortes]
        tabla.append({"parametros": p, "media_semestral": float(np.mean(rents)),
                      "peor_semestre": float(np.min(rents)),
                      "consistencia": float(np.mean(rents) - np.std(rents)), **total})
    tabla.sort(key=lambda r: (r["operaciones"] >= 10, r["consistencia"]), reverse=True)
    return tabla


def guardar_parametros(p: Parametros, ruta: Path = RUTA_PARAMETROS) -> None:
    ruta.write_text(json.dumps(p.como_dict(), indent=2) + "\n", encoding="utf-8")


def cargar_parametros(ruta: Path = RUTA_PARAMETROS) -> Parametros:
    if ruta.exists():
        return Parametros(**json.loads(ruta.read_text(encoding="utf-8")))
    return Parametros()


def _pct(x: float) -> str:
    return f"{x * 100:+.1f}%"


def informe(wf: dict | None, tabla: list[dict], datos, capital: float) -> str:
    inicio, fin = rango_fechas(datos)
    lineas = [
        "# Informe de backtesting",
        "",
        f"Datos: {', '.join(datos)} en velas de 4h, del {inicio:%Y-%m-%d} al {fin:%Y-%m-%d}. "
        f"Capital inicial {capital:,.0f} EUR. Incluye comisiones (0,26% por lado) y deslizamiento (0,05%).",
        "",
        "## 1. Resultado honesto (walk-forward)",
        "",
        "Parámetros elegidos con 12 meses de datos y probados en los 3 meses siguientes, que no se "
        "usaron para elegirlos. Es la mejor estimación de lo que habría pasado operando de verdad.",
        "",
    ]
    if wf:
        m = wf["metricas"]
        lineas += [
            "| Métrica | Bot | Comprar y mantener |",
            "|---|---|---|",
            f"| Rentabilidad total | {_pct(m['rentabilidad_total'])} | {_pct(wf['comprar_y_mantener'])} |",
            f"| Rentabilidad anual | {_pct(m['rentabilidad_anual'])} | |",
            f"| Caída máxima | {_pct(m['caida_maxima'])} | |",
            f"| Meses en positivo | {m['meses_positivos'] * 100:.0f}% | |",
            f"| Mejor / peor mes | {_pct(m['mejor_mes'])} / {_pct(m['peor_mes'])} | |",
            f"| Operaciones | {m['operaciones']} | |",
            f"| Aciertos | {m['porcentaje_aciertos'] * 100:.0f}% | |",
            f"| Factor de beneficio | {m['factor_beneficio']:.2f} | |",
            f"| Sharpe | {m['sharpe']:.2f} | |",
            "",
            "Tramos de prueba:",
            "",
            "| Entreno | Prueba | Rentabilidad | EMAs | Stop / trailing (ATR) |",
            "|---|---|---|---|---|",
        ]
        for t in wf["tramos"]:
            p = t["parametros"]
            lineas.append(f"| {t['entreno']} | {t['prueba']} | {_pct(t['rentabilidad'])} | "
                          f"{p.ema_rapida}/{p.ema_lenta}/{p.ema_tendencia} | {p.atr_stop}/{p.atr_trailing} |")
        mens = (wf["curva"].resample("ME").last() / wf["curva"].resample("ME").last().shift().fillna(capital) - 1)
        lineas += ["", "Rentabilidad mes a mes:", "", "| Mes | Rentabilidad |", "|---|---|"]
        lineas += [f"| {f:%Y-%m} | {_pct(r)} |" for f, r in mens.items()]
    else:
        lineas.append("No hay datos suficientes para el walk-forward (hacen falta más de 15 meses).")

    lineas += ["", "## 2. Parámetros más consistentes", "",
               "Ordenados por consistencia entre semestres (media menos desviación), no por el máximo beneficio.",
               "", "| EMAs | RSI máx | Stop/trailing | Rent. total | Caída máx | Media semestral | Peor semestre | Ops |",
               "|---|---|---|---|---|---|---|---|"]
    for r in tabla[:10]:
        p = r["parametros"]
        lineas.append(f"| {p.ema_rapida}/{p.ema_lenta}/{p.ema_tendencia} | {p.rsi_max:.0f} | {p.atr_stop}/{p.atr_trailing} | "
                      f"{_pct(r['rentabilidad_total'])} | {_pct(r['caida_maxima'])} | {_pct(r['media_semestral'])} | "
                      f"{_pct(r['peor_semestre'])} | {r['operaciones']} |")
    lineas += ["", f"Parámetros guardados en `estrategia.json`: `{json.dumps(tabla[0]['parametros'].como_dict())}`", ""]
    return "\n".join(lineas)
