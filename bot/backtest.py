"""Simulador de cartera para probar la estrategia con datos históricos.

Simula las tres monedas a la vez con un único capital compartido, comisiones
y deslizamiento de Kraken, tamaño de posición según el riesgo y el límite de
pérdida mensual de config.yaml.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import Riesgo
from .estrategia import Parametros, calcular_senales

COMISION = 0.0026      # comisión taker de Kraken (0,26%) por lado
DESLIZAMIENTO = 0.0005 # 0,05% de deslizamiento estimado por lado
MAX_FRACCION_POSICION = 0.5  # ninguna posición supera el 50% del capital


@dataclass
class Posicion:
    par: str
    cantidad: float
    precio_entrada: float
    fecha_entrada: pd.Timestamp
    stop: float
    maximo: float
    coste: float  # euros pagados incluida la comisión


@dataclass
class Resultado:
    curva: pd.Series                       # capital al cierre de cada vela
    operaciones: pd.DataFrame
    capital_inicial: float
    metricas: dict = field(default_factory=dict)


def a_utc(fecha) -> pd.Timestamp:
    t = pd.Timestamp(fecha)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


COLUMNAS_SIM = ["open", "high", "low", "close", "atr", "entrada", "salida_tendencia"]


def preparar(datos: dict[str, pd.DataFrame], p: Parametros) -> dict[str, pd.DataFrame]:
    return {par: calcular_senales(df, p).set_index("fecha")[COLUMNAS_SIM] for par, df in datos.items()}


def ejecutar(datos: dict[str, pd.DataFrame], p: Parametros, riesgo: Riesgo,
             capital_inicial: float = 1000.0, desde=None, hasta=None,
             comision: float = COMISION, deslizamiento: float = DESLIZAMIENTO,
             senales: dict[str, pd.DataFrame] | None = None) -> Resultado:
    """`datos`: par -> DataFrame con columnas timestamp/open/high/low/close/fecha.

    Los indicadores se calculan con todo el histórico (para que estén "calientes")
    pero solo se opera entre `desde` y `hasta`. `senales` permite reutilizar
    las señales ya calculadas con `preparar` (acelera la optimización).
    """
    senales = senales if senales is not None else preparar(datos, p)
    if desde is not None:
        senales = {par: s[s.index >= a_utc(desde)] for par, s in senales.items()}
    if hasta is not None:
        senales = {par: s[s.index < a_utc(hasta)] for par, s in senales.items()}
    fechas = pd.DatetimeIndex(sorted(set().union(*(s.index for s in senales.values()))))
    filas = {par: s.to_dict("index") for par, s in senales.items()}
    efectivo = capital_inicial
    posiciones: dict[str, Posicion] = {}
    ultimo_cierre: dict[str, float] = {}
    operaciones: list[dict] = []
    curva: list[float] = []
    mes_actual = None
    capital_inicio_mes = capital_inicial
    bloqueado = False

    def cerrar(pos: Posicion, precio: float, fecha, motivo: str) -> None:
        nonlocal efectivo
        precio_real = precio * (1 - deslizamiento)
        ingreso = pos.cantidad * precio_real * (1 - comision)
        efectivo += ingreso
        operaciones.append({
            "par": pos.par, "entrada": pos.fecha_entrada, "salida": fecha,
            "precio_entrada": pos.precio_entrada, "precio_salida": precio_real,
            "beneficio": ingreso - pos.coste, "rentabilidad": ingreso / pos.coste - 1,
            "motivo": motivo,
        })
        del posiciones[pos.par]

    for fecha in fechas:
        mes = (fecha.year, fecha.month)
        if mes != mes_actual:
            mes_actual = mes
            capital_inicio_mes = efectivo + sum(
                pos.cantidad * ultimo_cierre[par] for par, pos in posiciones.items())
            bloqueado = False

        # 1) Gestionar posiciones abiertas con la vela actual.
        for par in list(posiciones):
            f = filas[par].get(fecha)
            if f is None:
                continue
            pos = posiciones[par]
            if f["open"] <= pos.stop:
                cerrar(pos, f["open"], fecha, "stop (hueco)")
            elif f["low"] <= pos.stop:
                cerrar(pos, pos.stop, fecha, "stop")
            elif f["salida_tendencia"]:
                cerrar(pos, f["close"], fecha, "tendencia")
            else:
                pos.maximo = max(pos.maximo, f["high"])
                pos.stop = max(pos.stop, pos.maximo - p.atr_trailing * f["atr"])

        for par, s in filas.items():
            f = s.get(fecha)
            if f is not None:
                ultimo_cierre[par] = f["close"]

        capital = efectivo + sum(pos.cantidad * ultimo_cierre[par] for par, pos in posiciones.items())
        if capital <= capital_inicio_mes * (1 - riesgo.perdida_maxima_mensual):
            bloqueado = True

        # 2) Nuevas entradas al cierre de la vela.
        if not bloqueado:
            for par, s in filas.items():
                f = s.get(fecha)
                if (f is None or par in posiciones or not f["entrada"]
                        or len(posiciones) >= riesgo.max_posiciones_abiertas):
                    continue
                precio = f["close"] * (1 + deslizamiento)
                stop = f["close"] - p.atr_stop * f["atr"]
                distancia = precio - stop
                if distancia <= 0:
                    continue
                cantidad = capital * riesgo.por_operacion / distancia
                coste = cantidad * precio * (1 + comision)
                limite = min(efectivo, capital * MAX_FRACCION_POSICION)
                if coste > limite:
                    cantidad *= limite / coste
                    coste = limite
                if coste < 10:  # mínimo razonable de orden en Kraken
                    continue
                efectivo -= coste
                posiciones[par] = Posicion(par, cantidad, precio, fecha, stop, f["high"], coste)

        curva.append(efectivo + sum(pos.cantidad * ultimo_cierre[par] for par, pos in posiciones.items()))

    # Cerrar lo que quede abierto al final para medir el resultado.
    if len(fechas):
        for par in list(posiciones):
            cerrar(posiciones[par], ultimo_cierre[par], fechas[-1], "fin del periodo")
        curva[-1] = efectivo

    serie = pd.Series(curva, index=fechas, name="capital")
    ops = pd.DataFrame(operaciones)
    res = Resultado(serie, ops, capital_inicial)
    res.metricas = metricas(serie, ops, capital_inicial)
    return res


def metricas(curva: pd.Series, ops: pd.DataFrame, capital_inicial: float) -> dict:
    if curva.empty:
        return {}
    final = float(curva.iloc[-1])
    dias = max((curva.index[-1] - curva.index[0]).days, 1)
    caida = float((curva / curva.cummax() - 1).min())
    mensual = rentabilidad_mensual(curva, capital_inicial)
    diaria = curva.resample("1D").last().ffill().pct_change().dropna()
    sharpe = float(diaria.mean() / diaria.std() * np.sqrt(365)) if diaria.std() > 0 else 0.0
    n = len(ops)
    ganadoras = int((ops["beneficio"] > 0).sum()) if n else 0
    bruto_g = float(ops.loc[ops["beneficio"] > 0, "beneficio"].sum()) if n else 0.0
    bruto_p = float(-ops.loc[ops["beneficio"] <= 0, "beneficio"].sum()) if n else 0.0
    return {
        "capital_final": final,
        "rentabilidad_total": final / capital_inicial - 1,
        "rentabilidad_anual": (final / capital_inicial) ** (365 / dias) - 1,
        "caida_maxima": caida,
        "sharpe": sharpe,
        "operaciones": n,
        "porcentaje_aciertos": ganadoras / n if n else 0.0,
        "factor_beneficio": bruto_g / bruto_p if bruto_p > 0 else float("inf") if bruto_g > 0 else 0.0,
        "meses_positivos": float((mensual > 0).mean()) if len(mensual) else 0.0,
        "peor_mes": float(mensual.min()) if len(mensual) else 0.0,
        "mejor_mes": float(mensual.max()) if len(mensual) else 0.0,
    }


def rentabilidad_mensual(curva: pd.Series, capital_inicial: float) -> pd.Series:
    fin_mes = curva.resample("ME").last()
    previo = fin_mes.shift().fillna(capital_inicial)
    return fin_mes / previo - 1


def comprar_y_mantener(datos: dict[str, pd.DataFrame], desde=None, hasta=None) -> float:
    """Rentabilidad de repartir el capital a partes iguales y no tocarlo (referencia)."""
    rents = []
    for df in datos.values():
        d = df.set_index("fecha")["close"]
        if desde is not None:
            d = d[d.index >= a_utc(desde)]
        if hasta is not None:
            d = d[d.index < a_utc(hasta)]
        if len(d) > 1:
            rents.append(d.iloc[-1] / d.iloc[0] - 1)
    return float(np.mean(rents)) if rents else 0.0
