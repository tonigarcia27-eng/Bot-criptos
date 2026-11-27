"""Conexión con la cuenta de Kraken y modo real (desactivado por defecto).

El bot solo envía órdenes de verdad si se cumplen LAS DOS condiciones:
  1. `modo: real` en config.yaml.
  2. La variable de entorno BOT_DINERO_REAL vale exactamente "si".

En cualquier otro caso trabaja en *ensayo*: lee los saldos reales, calcula qué
compraría o vendería y manda las órdenes a Kraken con `validate`, que hace que
Kraken las revise sin ejecutarlas. No se mueve ni un euro.

Además, el bot se niega a operar si la clave de API tiene permiso de retirada
de fondos, y nunca gestiona más de `real.capital_maximo` euros.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path

import ccxt

from .config import RAIZ, Config
from .estrategia import Parametros
from .paper import Estado, _anexar_csv, cierres_kraken, paso_diario

CARPETA = RAIZ / "real"
VARIABLE_ACTIVACION = "BOT_DINERO_REAL"


def dinero_real_activado(cfg: Config, entorno: dict[str, str]) -> bool:
    return cfg.modo == "real" and entorno.get(VARIABLE_ACTIVACION, "").strip().lower() == "si"


def puede_retirar(exchange) -> bool | None:
    """True si la clave puede retirar fondos (peligroso), False si no, None si no se sabe.

    Consulta los métodos de retirada, que solo responde con permiso de retirada.
    Es una consulta: no retira nada.
    """
    try:
        exchange.privatePostWithdrawMethods({})
        return True
    except ccxt.PermissionDenied:
        return False
    except ccxt.BaseError:
        return None


def saldos(exchange, pares: list[str]) -> tuple[float, dict[str, float]]:
    """Euros libres y unidades de cada moneda del bot en la cuenta."""
    total = exchange.fetch_balance().get("total", {})
    efectivo = float(total.get("EUR") or 0.0)
    unidades = {par: float(total.get(par.split("/")[0]) or 0.0) for par in pares}
    return efectivo, unidades


def comprobar(cfg: Config, exchange) -> str:
    """Comprueba que las claves funcionan y que no pueden retirar fondos. No opera."""
    efectivo, unidades = saldos(exchange, cfg.pares)
    retirar = puede_retirar(exchange)
    l = ["Conexión con Kraken correcta.", "", "Saldos en la cuenta:", f"  EUR: {efectivo:,.2f}"]
    l += [f"  {par.split('/')[0]}: {u:.8f}" for par, u in unidades.items()]
    l.append("")
    if retirar is True:
        l.append("PELIGRO: esta clave PUEDE RETIRAR FONDOS. Bórrala en Kraken y crea otra sin ese permiso.")
    elif retirar is False:
        l.append("Bien: la clave no puede retirar fondos.")
    else:
        l.append("Aviso: no se ha podido comprobar el permiso de retirada.")
    return "\n".join(l)


def _cargar(carpeta: Path) -> Estado | None:
    ruta = carpeta / "estado.json"
    return Estado(**json.loads(ruta.read_text(encoding="utf-8"))) if ruta.exists() else None


def ordenes_del_dia(estado: Estado, cierres, precios: dict[str, float], hoy: date, p: Parametros,
                    cfg: Config, efectivo: float, unidades: dict[str, float]) -> list[dict]:
    """Aplica la misma lógica que el paper trading sobre los saldos reales.

    Solo se tienen en cuenta hasta `real.capital_maximo` euros: si la cuenta tiene
    más, el resto no se toca.
    """
    valor_cripto = sum(u * precios[par] for par, u in unidades.items())
    estado.efectivo = max(0.0, min(efectivo, cfg.real.capital_maximo - valor_cripto))
    estado.unidades = dict(unidades)
    ops = paso_diario(estado, cierres, precios, hoy, p, cfg)
    for op in ops:
        cantidad = op["importe_eur"] / precios[op["par"]]
        if op["lado"] == "venta":
            cantidad = min(cantidad, unidades[op["par"]])
        op["cantidad"] = cantidad
    return ops


def enviar(exchange, ops: list[dict], real: bool) -> list[dict]:
    """Manda las órdenes a mercado. Con real=False, Kraken solo las valida."""
    exchange.load_markets()
    resultado = []
    for op in ops:
        mercado = exchange.market(op["par"])
        minimo = (mercado.get("limits", {}).get("amount", {}) or {}).get("min") or 0.0
        cantidad = float(exchange.amount_to_precision(op["par"], op["cantidad"]))
        fila = {**op, "cantidad": cantidad, "real": real}
        if cantidad <= 0 or cantidad < minimo:
            fila["resultado"] = f"omitida: menor que el mínimo de Kraken ({minimo})"
        else:
            lado = "sell" if op["lado"] == "venta" else "buy"
            params = {} if real else {"validate": True}
            try:
                orden = exchange.create_order(op["par"], "market", lado, cantidad, None, params)
                fila["resultado"] = f"enviada ({orden.get('id')})" if real else "validada por Kraken (no ejecutada)"
            except ccxt.BaseError as e:
                fila["resultado"] = f"error: {e}"
        resultado.append(fila)
    return resultado


def ejecutar(cfg: Config, p: Parametros, exchange, entorno: dict[str, str],
             carpeta: Path = CARPETA) -> str:
    real = dinero_real_activado(cfg, entorno)
    if puede_retirar(exchange) is not False:
        raise SystemExit("La clave de Kraken puede retirar fondos (o no se ha podido comprobar). "
                         "El bot no opera con ella. Crea una clave solo con permisos de consulta y trading.")
    hoy = datetime.now(timezone.utc).date()
    cierres = cierres_kraken(exchange, cfg.pares, dias=max(200, p.dias_minimos + 10))
    precios = {par: float(exchange.fetch_ticker(par)["last"]) for par in cfg.pares}
    efectivo, unidades = saldos(exchange, cfg.pares)

    estado = _cargar(carpeta) if real else None
    if estado is None:
        estado = Estado.nuevo(cfg, hoy, precios)
        estado.capital_inicial = min(efectivo + sum(u * precios[par] for par, u in unidades.items()),
                                     cfg.real.capital_maximo)
        estado.maximo_fin_de_mes = estado.capital_inicial
    ops = ordenes_del_dia(estado, cierres, precios, hoy, p, cfg, efectivo, unidades)
    hechas = enviar(exchange, ops, real)

    if real:  # en ensayo no se guarda nada
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / "estado.json").write_text(json.dumps(asdict(estado), indent=2) + "\n", encoding="utf-8")
        _anexar_csv(carpeta / "operaciones.csv", hechas)

    l = ["# Kraken: " + ("DINERO REAL" if real else "ensayo (no se ejecuta ninguna orden)"), "",
         f"Capital que gestiona el bot: {estado.capital(precios):,.2f} EUR "
         f"(máximo permitido {cfg.real.capital_maximo:,.2f} EUR)", ""]
    if not hechas:
        l.append("Hoy no toca ninguna orden.")
    else:
        l += ["| Par | Lado | Cantidad | Importe | Resultado |", "|---|---|---|---|---|"]
        l += [f"| {h['par']} | {h['lado']} | {h['cantidad']:.8f} | {h['importe_eur']:,.2f} EUR | {h['resultado']} |"
              for h in hechas]
    l.append("")
    return "\n".join(l)
