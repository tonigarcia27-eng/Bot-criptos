"""Simulador de cartera para probar la estrategia con datos históricos.

Simula las tres monedas con un único capital, comisiones (órdenes límite) y
deslizamiento de Kraken, rebalanceo periódico y el límite de pérdida mensual de config.yaml.
La decisión se toma con el cierre diario y se ejecuta a ese precio.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import Riesgo
from .estrategia import Parametros, pesos_objetivo

# Comisiones de Kraken Pro en el nivel inicial (menos de 10.000 $ al mes), nov-2026.
# El bot opera con órdenes límite (maker); si no se llenan a tiempo, el resto va a mercado (taker).
COMISION = 0.0040          # orden límite (maker): 0,40%
COMISION_MERCADO = 0.0080  # orden a mercado (taker): 0,80%, solo como plan B
DESLIZAMIENTO = 0.0005     # 0,05% de margen por precio peor o restos que acaban a mercado
ORDEN_MINIMA = 10.0     # EUR; ajustes menores no se ejecutan
UMBRAL_AJUSTE = 0.02    # no se reajusta una moneda si la diferencia es < 2% del capital


@dataclass
class Resultado:
    curva: pd.Series
    operaciones: pd.DataFrame
    capital_inicial: float
    metricas: dict = field(default_factory=dict)


def a_utc(fecha) -> pd.Timestamp:
    t = pd.Timestamp(fecha)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def rebalancear(unidades: np.ndarray, efectivo: float, precio: np.ndarray, deseado: np.ndarray,
                coste: float) -> tuple[np.ndarray, float, list[tuple[int, str, float]]]:
    """Ajusta la cartera a los pesos `deseado`. Devuelve unidades, efectivo y operaciones (índice, lado, importe EUR).

    Primero vende (libera euros) y luego compra. Ignora ajustes pequeños para ahorrar comisiones,
    salvo cerrar del todo una moneda.
    """
    unidades = unidades.astype(float).copy()
    capital = efectivo + float(unidades @ precio)
    actual = unidades * precio
    diferencia = deseado * capital - actual
    hechas: list[tuple[int, str, float]] = []
    for j in sorted(range(len(precio)), key=lambda j: diferencia[j]):
        d = diferencia[j]
        cerrar_todo = deseado[j] == 0 and actual[j] > 0
        if not cerrar_todo and (abs(d) < ORDEN_MINIMA or abs(d) < UMBRAL_AJUSTE * capital):
            continue
        if d < 0:
            vender = unidades[j] if cerrar_todo else min(-d / precio[j], unidades[j])
            efectivo += vender * precio[j] * (1 - coste)
            unidades[j] -= vender
            hechas.append((j, "venta", vender * precio[j]))
        else:
            importe = min(d, efectivo / (1 + coste))
            if importe < ORDEN_MINIMA:
                continue
            unidades[j] += importe / precio[j]
            efectivo -= importe * (1 + coste)
            hechas.append((j, "compra", importe))
    return unidades, efectivo, hechas


def ejecutar(cierres: pd.DataFrame, p: Parametros, riesgo: Riesgo, capital_inicial: float = 1000.0,
             desde=None, hasta=None, comision: float = COMISION,
             deslizamiento: float = DESLIZAMIENTO, pesos: pd.DataFrame | None = None) -> Resultado:
    """`cierres`: DataFrame diario (índice fecha UTC, una columna por par).

    Los indicadores se calculan con todo el histórico y solo se opera entre
    `desde` y `hasta`. `pesos` permite reutilizar pesos ya calculados.
    """
    pesos = pesos if pesos is not None else pesos_objetivo(cierres, p)
    fechas = cierres.index
    if desde is not None:
        fechas = fechas[fechas >= a_utc(desde)]
    if hasta is not None:
        fechas = fechas[fechas < a_utc(hasta)]
    pares = list(cierres.columns)
    precios = cierres.loc[fechas].to_numpy()
    objetivo = pesos.loc[fechas].to_numpy()
    coste = comision + deslizamiento

    efectivo = capital_inicial
    unidades = np.zeros(len(pares))
    curva = np.empty(len(fechas))
    operaciones: list[dict] = []
    mes_actual = None
    capital_inicio_mes = capital_inicial
    bloqueado = False

    for i, fecha in enumerate(fechas):
        precio = precios[i]
        capital = efectivo + float(unidades @ precio)
        mes = (fecha.year, fecha.month)
        if mes != mes_actual:
            mes_actual, capital_inicio_mes, bloqueado = mes, capital, False

        stop_mensual = (not bloqueado
                        and capital <= capital_inicio_mes * (1 - riesgo.perdida_maxima_mensual))
        if stop_mensual:
            bloqueado = True
        toca_rebalanceo = i % p.rebalanceo_dias == 0 or stop_mensual
        if toca_rebalanceo:
            deseado = np.zeros(len(pares)) if bloqueado else objetivo[i]
            unidades, efectivo, hechas = rebalancear(unidades, efectivo, precio, deseado, coste)
            motivo = "stop mensual" if stop_mensual else "rebalanceo"
            operaciones += [{"fecha": fecha, "par": pares[j], "lado": lado, "precio": precio[j],
                             "importe": importe, "motivo": motivo} for j, lado, importe in hechas]
        curva[i] = efectivo + float(unidades @ precio)

    serie = pd.Series(curva, index=fechas, name="capital")
    ops = pd.DataFrame(operaciones, columns=["fecha", "par", "lado", "precio", "importe", "motivo"])
    res = Resultado(serie, ops, capital_inicial)
    res.metricas = metricas(serie, ops, capital_inicial)
    return res


def metricas(curva: pd.Series, ops: pd.DataFrame, capital_inicial: float) -> dict:
    if len(curva) < 2:
        return {}
    final = float(curva.iloc[-1])
    dias = max((curva.index[-1] - curva.index[0]).days, 1)
    diaria = curva.pct_change().dropna()
    mensual = rentabilidad_mensual(curva, capital_inicial)
    return {
        "capital_final": final,
        "rentabilidad_total": final / capital_inicial - 1,
        "rentabilidad_anual": (final / capital_inicial) ** (365 / dias) - 1,
        "caida_maxima": float((curva / curva.cummax() - 1).min()),
        "sharpe": float(diaria.mean() / diaria.std() * np.sqrt(365)) if diaria.std() > 0 else 0.0,
        "operaciones": int(len(ops)),
        "meses_positivos": float((mensual > 0).mean()) if len(mensual) else 0.0,
        "peor_mes": float(mensual.min()) if len(mensual) else 0.0,
        "mejor_mes": float(mensual.max()) if len(mensual) else 0.0,
    }


def rentabilidad_mensual(curva: pd.Series, capital_inicial: float) -> pd.Series:
    fin_mes = curva.resample("ME").last()
    return fin_mes / fin_mes.shift().fillna(capital_inicial) - 1


def comprar_y_mantener(cierres: pd.DataFrame, desde=None, hasta=None) -> pd.Series:
    """Curva de repartir el capital a partes iguales al inicio y no tocarlo (referencia)."""
    c = cierres
    if desde is not None:
        c = c[c.index >= a_utc(desde)]
    if hasta is not None:
        c = c[c.index < a_utc(hasta)]
    return (c / c.iloc[0]).mean(axis=1)
