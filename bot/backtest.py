"""Simulador de cartera para probar la estrategia con datos históricos.

Simula las tres monedas con un único capital, comisiones y deslizamiento de
Kraken, rebalanceo periódico y el límite de pérdida mensual de config.yaml.
La decisión se toma con el cierre diario y se ejecuta a ese precio.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import Riesgo
from .estrategia import Parametros, pesos_objetivo

COMISION = 0.0026       # comisión taker de Kraken (0,26%) por operación
DESLIZAMIENTO = 0.0005  # 0,05% de deslizamiento estimado
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
            actual = unidades * precio
            diferencia = deseado * capital - actual
            # Primero ventas (liberan euros), luego compras.
            for j in sorted(range(len(pares)), key=lambda j: diferencia[j]):
                d = diferencia[j]
                cerrar_todo = deseado[j] == 0 and actual[j] > 0
                if not cerrar_todo and (abs(d) < ORDEN_MINIMA or abs(d) < UMBRAL_AJUSTE * capital):
                    continue
                if d < 0:  # vender
                    vender = unidades[j] if cerrar_todo else min(-d / precio[j], unidades[j])
                    efectivo += vender * precio[j] * (1 - coste)
                    unidades[j] -= vender
                    lado, importe = "venta", vender * precio[j]
                else:  # comprar
                    importe = min(d, efectivo / (1 + coste))
                    if importe < ORDEN_MINIMA:
                        continue
                    unidades[j] += importe / precio[j]
                    efectivo -= importe * (1 + coste)
                    lado = "compra"
                operaciones.append({"fecha": fecha, "par": pares[j], "lado": lado,
                                    "precio": precio[j], "importe": importe,
                                    "motivo": "stop mensual" if stop_mensual else "rebalanceo"})
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
