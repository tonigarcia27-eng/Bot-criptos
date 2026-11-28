"""Estudio del freno automático de pérdidas.

Pregunta: si el capital cae mucho desde su máximo, ¿conviene que el bot venda todo,
espere un tiempo y vuelva solo cuando el mercado mejore? ¿Con qué caída, cuánto
tiempo y con qué condición?

Método:
  1. Se prueban todas las combinaciones de caída, pausa y condición de reactivación,
     con la estrategia de estrategia.json, comisiones y el límite mensual.
  2. Intento "de libro": elegir solo con la primera mitad del histórico y probar en
     la segunda. Se deja en el informe como aviso: lo que mejor fue en la primera
     mitad falló en la segunda.
  3. El freno depende mucho del día en que el bot empieza (el máximo desde el que se
     mide la caída es distinto). Por eso la elección final se hace arrancando el bot
     en cada uno de los meses del histórico y comparando, para cada arranque, con no
     tener freno. Se elige la combinación cuyo PEOR 10% de arranques sale mejor, tanto
     en rentabilidad anual como en caída máxima: un freno que casi nunca perjudica.
  4. Robustez: se aplica el freno elegido a las 48 variantes de la estrategia.
"""
from __future__ import annotations

import itertools
from dataclasses import replace

import numpy as np
import pandas as pd

from .backtest import ejecutar
from .config import Freno, Riesgo
from .estrategia import Parametros, pesos_objetivo
from .optimizar import _pct, combinaciones, inicio_operable

CAIDAS = [0.10, 0.15, 0.20, 0.25, 0.30]
PAUSAS = [0, 7, 14, 30, 60, 90, 120, 180]
REACTIVACIONES = ["tiempo", "amplia", "btc", "curva"]
NOMBRES = {
    "tiempo": "solo esperar",
    "amplia": "2 de 3 monedas en tendencia alcista",
    "btc": "BTC por encima de su media de 100 días",
    "curva": "la estrategia simulada vuelve a ir bien",
}
AÑOS_MINIMOS = 2.5  # cada arranque se prueba al menos este tiempo


def _f(f: Freno) -> str:
    if not f.activo:
        return "sin freno"
    return f"caída {f.caida_maxima:.0%}, pausa {f.pausa_dias} días, {NOMBRES[f.reactivar]}"


def calmar(m: dict) -> float:
    return m["rentabilidad_anual"] / -m["caida_maxima"] if m.get("caida_maxima", 0) < 0 else np.inf


def _correr(cierres, p, pesos, riesgo: Riesgo, f: Freno, capital, desde, hasta=None):
    return ejecutar(cierres, p, replace(riesgo, freno=f), capital, desde=desde, hasta=hasta, pesos=pesos)


def episodios(res) -> list[dict]:
    """Cada vez que saltó el freno: fecha, vuelta y capital en ese momento."""
    ops = res.operaciones
    saltos = sorted(ops.loc[ops.motivo == "freno", "fecha"].unique())
    vueltas = sorted(ops.loc[ops.motivo == "fin del freno", "fecha"].unique())
    filas = []
    for s in saltos:
        v = next((x for x in vueltas if x > s), None)
        filas.append({"salta": pd.Timestamp(s), "vuelve": pd.Timestamp(v) if v is not None else None,
                      "capital": float(res.curva.loc[s])})
    return filas


def arranques(cierres: pd.DataFrame, inicio: pd.Timestamp) -> pd.DatetimeIndex:
    fin = cierres.index[-1] - pd.DateOffset(days=int(365 * AÑOS_MINIMOS))
    return pd.date_range(inicio.normalize() + pd.offsets.MonthBegin(1), fin, freq="MS", tz="UTC")


def estudiar(cierres: pd.DataFrame, p: Parametros, riesgo: Riesgo, capital: float) -> dict:
    pesos = pesos_objetivo(cierres, p)
    inicio = inicio_operable(cierres, combinaciones())
    corte = pd.Timestamp((inicio + (cierres.index[-1] - inicio) / 2).date(), tz="UTC")
    tramos = {"entreno": (inicio, corte), "prueba": (corte, None), "todo": (inicio, None)}
    fechas = arranques(cierres, inicio)

    sin = Freno(activo=False)
    base = {k: _correr(cierres, p, pesos, riesgo, sin, capital, a, b).metricas for k, (a, b) in tramos.items()}
    base_arr = [_correr(cierres, p, pesos, riesgo, sin, capital, d).metricas for d in fechas]

    filas = []
    for caida, pausa, re in itertools.product(CAIDAS, PAUSAS, REACTIVACIONES):
        f = Freno(True, caida, pausa, re)
        fila: dict = {"freno": f}
        for k, (a, b) in tramos.items():
            r = _correr(cierres, p, pesos, riesgo, f, capital, a, b)
            fila[k], fila[f"{k}_saltos"] = r.metricas, len(episodios(r))
        da, dd = [], []
        for d, b in zip(fechas, base_arr):
            m = _correr(cierres, p, pesos, riesgo, f, capital, d).metricas
            da.append(m["rentabilidad_anual"] - b["rentabilidad_anual"])
            dd.append(m["caida_maxima"] - b["caida_maxima"])  # positivo = cae menos que sin freno
        fila["d_anual"], fila["d_caida"] = np.array(da), np.array(dd)
        fila["puntos"] = float(min(np.percentile(da, 10), np.percentile(dd, 10)))
        filas.append(fila)

    de_libro = max(filas, key=lambda r: calmar(r["entreno"]))
    filas.sort(key=lambda r: (r["puntos"], np.median(r["d_caida"])), reverse=True)
    elegido = filas[0]

    completo = _correr(cierres, p, pesos, riesgo, elegido["freno"], capital, inicio)
    referencia = _correr(cierres, p, pesos, riesgo, sin, capital, inicio)
    eps = episodios(completo)
    for x in eps:  # qué pasó mientras estaba parado, con y sin freno
        fin = x["vuelve"] or referencia.curva.index[-1]
        x["sin_freno"] = float(referencia.curva.loc[fin] / referencia.curva.loc[x["salta"]] - 1)
        x["con_freno"] = float(completo.curva.loc[fin] / completo.curva.loc[x["salta"]] - 1)

    variantes = []
    for q in combinaciones():
        wq = pesos_objetivo(cierres, q)
        variantes.append((_correr(cierres, q, wq, riesgo, sin, capital, inicio).metricas,
                          _correr(cierres, q, wq, riesgo, elegido["freno"], capital, inicio).metricas))

    return {"inicio": inicio, "corte": corte, "fin": cierres.index[-1], "base": base, "filas": filas,
            "elegido": elegido, "de_libro": de_libro, "episodios": eps, "variantes": variantes,
            "arranques": fechas}


def _tabla(a: dict, b: dict) -> list[str]:
    l = ["| | Sin freno | Con freno |", "|---|---|---|"]
    for k, n in [("rentabilidad_anual", "Rentabilidad anual"), ("rentabilidad_total", "Rentabilidad total"),
                 ("caida_maxima", "Caída máxima"), ("peor_mes", "Peor mes")]:
        l.append(f"| {n} | {_pct(a[k])} | {_pct(b[k])} |")
    l.append(f"| Sharpe | {a['sharpe']:.2f} | {b['sharpe']:.2f} |")
    return l


def _resumen_arranques(r: dict) -> str:
    da, dd = r["d_anual"], r["d_caida"]
    return (f"{_pct(np.median(da))} | {_pct(np.percentile(da, 10))} | {_pct(np.median(dd))} | "
            f"{_pct(np.percentile(dd, 10))} | {(dd > 1e-9).mean():.0%} | {(dd < -1e-9).mean():.0%}")


def informe(e: dict, riesgo: Riesgo, capital: float) -> str:
    el, base = e["elegido"], e["base"]
    f = el["freno"]
    n_arr = len(e["arranques"])
    l = [
        "# Informe del freno automático de pérdidas",
        "",
        f"Datos diarios del {e['inicio']:%Y-%m-%d} al {e['fin']:%Y-%m-%d}, con comisiones, deslizamiento y el límite "
        f"mensual del {riesgo.perdida_maxima_mensual:.0%}. Se probaron {len(e['filas'])} combinaciones: caída desde "
        f"el máximo de {', '.join(f'{c:.0%}' for c in CAIDAS)}; pausa mínima de {', '.join(map(str, PAUSAS))} días; "
        "y cuatro condiciones para volver: " + "; ".join(NOMBRES.values()) + ".",
        "",
        "Cuando salta, el bot vende todo y se queda en euros. Al volver, la caída se vuelve a medir desde el capital "
        "de ese día.",
        "",
        "## 1. Freno elegido",
        "",
        f"**{_f(f)}.**",
        "",
        f"Se arrancó el bot en cada uno de los {n_arr} meses entre {e['arranques'][0]:%Y-%m} y "
        f"{e['arranques'][-1]:%Y-%m} (cada arranque hasta hoy) y se comparó con el mismo arranque sin freno. "
        "Se eligió la combinación cuyo peor 10% de arranques sale mejor, en rentabilidad y en caída máxima.",
        "",
        "| | Diferencia con no tener freno |",
        "|---|---|",
        f"| Rentabilidad anual, caso típico (mediana) | {_pct(np.median(el['d_anual']))} |",
        f"| Rentabilidad anual, peor 10% de arranques | {_pct(np.percentile(el['d_anual'], 10))} |",
        f"| Rentabilidad anual, peor arranque | {_pct(el['d_anual'].min())} |",
        f"| Caída máxima, caso típico (positivo = cae menos) | {_pct(np.median(el['d_caida']))} |",
        f"| Caída máxima, peor 10% de arranques | {_pct(np.percentile(el['d_caida'], 10))} |",
        f"| Caída máxima, peor arranque | {_pct(el['d_caida'].min())} |",
        f"| Arranques en que cae menos / más que sin freno | {(el['d_caida'] > 1e-9).mean():.0%} / "
        f"{(el['d_caida'] < -1e-9).mean():.0%} |",
        "",
        f"### Todo el histórico, arrancando el {e['inicio']:%Y-%m-%d}",
        "",
    ]
    l += _tabla(base["todo"], el["todo"])
    l += ["", f"### Solo los últimos años ({e['corte']:%Y-%m-%d} a hoy)", ""]
    l += _tabla(base["prueba"], el["prueba"])

    l += ["", f"## 2. Cuándo habría saltado (arrancando el {e['inicio']:%Y-%m-%d})", "",
          "| Salta | Vuelve | Capital al saltar | Con freno mientras estuvo parado | Sin freno en ese tiempo |",
          "|---|---|---|---|---|"]
    for x in e["episodios"]:
        vuelve = f"{x['vuelve']:%Y-%m-%d}" if x["vuelve"] is not None else "sigue parado"
        l.append(f"| {x['salta']:%Y-%m-%d} | {vuelve} | {x['capital']:,.0f} EUR | {_pct(x['con_freno'])} | "
                 f"{_pct(x['sin_freno'])} |")
    if not e["episodios"]:
        l.append("| nunca | | | | |")

    l += ["", "## 3. Las 15 mejores combinaciones", "",
          "Diferencias con no tener freno, sobre todos los arranques. \"Peor 10%\" es el resultado que solo un 10% de "
          "arranques empeora.", "",
          "| Freno | Rent. anual típica | Rent. anual peor 10% | Caída típica | Caída peor 10% | Cae menos | Cae más |",
          "|---|---|---|---|---|---|---|"]
    l += [f"| {_f(r['freno'])} | {_resumen_arranques(r)} |" for r in e["filas"][:15]]

    # Vecinas: misma condición, caída o pausa inmediatamente por encima o por debajo.
    ic, ip = CAIDAS.index(f.caida_maxima), PAUSAS.index(f.pausa_dias)
    vecinas = {(CAIDAS[i], f.pausa_dias) for i in (ic - 1, ic + 1) if 0 <= i < len(CAIDAS)}
    vecinas |= {(f.caida_maxima, PAUSAS[j]) for j in (ip - 1, ip + 1) if 0 <= j < len(PAUSAS)}
    filas_v = [r for r in e["filas"] if r["freno"].reactivar == f.reactivar
               and (r["freno"].caida_maxima, r["freno"].pausa_dias) in vecinas]
    l += ["", "Combinaciones vecinas de la elegida (para ver si el resultado depende de un ajuste fino):", "",
          "| Freno | Rent. anual típica | Rent. anual peor 10% | Caída típica | Caída peor 10% | Cae menos | Cae más |",
          "|---|---|---|---|---|---|---|"]
    l += [f"| {_f(r['freno'])} | {_resumen_arranques(r)} |"
          for r in sorted(filas_v, key=lambda r: (r["freno"].caida_maxima, r["freno"].pausa_dias))]

    df = pd.DataFrame([{"caida": r["freno"].caida_maxima, "pausa": r["freno"].pausa_dias, "re": r["freno"].reactivar,
                        "puntos": r["puntos"]} for r in e["filas"]])
    l += ["", "## 4. Qué funciona en general", "",
          "Mediana de la puntuación (el peor 10% de arranques; más alto es mejor, 0 = igual que sin freno):", "",
          "Por caída: " + ", ".join(f"{c:.0%} {_pct(v)}" for c, v in df.groupby("caida").puntos.median().items()), "",
          "Por pausa: " + ", ".join(f"{c} días {_pct(v)}" for c, v in df.groupby("pausa").puntos.median().items()), "",
          "Por condición: " + ", ".join(f"{NOMBRES[c]} {_pct(v)}" for c, v in df.groupby("re").puntos.median().items())]

    lib = e["de_libro"]
    l += ["", "## 5. Aviso: elegir con una sola fecha de inicio engaña", "",
          f"Si se elige el freno que mejor fue en la primera mitad ({e['inicio']:%Y-%m-%d} a {e['corte']:%Y-%m-%d}) "
          f"sale **{_f(lib['freno'])}**, que en la segunda mitad hizo esto:", ""]
    l += _tabla(base["prueba"], lib["prueba"])
    l += ["", "Con pausas largas el bot vende cerca del fondo y se pierde la recuperación. Por eso la elección se hizo "
          "con todos los arranques y buscando el freno que casi nunca perjudica, no el que más gana."]

    v = e["variantes"]
    l += ["", "## 6. Robustez: el mismo freno en las 48 variantes de la estrategia", "",
          f"Arrancando el {e['inicio']:%Y-%m-%d}, el freno reduce la caída máxima en "
          f"{sum(b['caida_maxima'] > a['caida_maxima'] + 1e-9 for a, b in v)} de {len(v)} variantes, la empeora en "
          f"{sum(b['caida_maxima'] < a['caida_maxima'] - 1e-9 for a, b in v)}, y mejora la rentabilidad anual en "
          f"{sum(b['rentabilidad_anual'] > a['rentabilidad_anual'] + 1e-9 for a, b in v)}.",
          f"Mediana de la caída máxima: sin freno {_pct(np.median([a['caida_maxima'] for a, _ in v]))}, "
          f"con freno {_pct(np.median([b['caida_maxima'] for _, b in v]))}. Mediana de la rentabilidad anual: "
          f"sin freno {_pct(np.median([a['rentabilidad_anual'] for a, _ in v]))}, "
          f"con freno {_pct(np.median([b['rentabilidad_anual'] for _, b in v]))}.",
          "",
          "## Limitaciones",
          "",
          "- El freno salta pocas veces (unas pocas en 8 años), así que todo se apoya en pocos episodios. "
          "Es un seguro contra una racha mala, no una forma de ganar más.",
          "- Se eligió mirando todo el histórico (no queda un periodo sin usar para comprobarlo). Lo compensa en parte "
          "que se exige que funcione con cualquier fecha de arranque; las vecinas también mejoran en el caso típico, "
          "aunque sus peores casos son algo peores, así que la ventaja exacta puede ser en parte suerte.",
          "- La estrategia ya pasa a euros cuando una moneda deja de estar en tendencia, y existe el límite mensual; "
          "el freno añade una tercera protección para cuando eso no basta.",
          "- Resultados pasados no garantizan resultados futuros.",
          ""]
    return "\n".join(l)
