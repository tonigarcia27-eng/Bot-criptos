"""Conexión con la cuenta de Kraken y modo real (desactivado por defecto).

El bot solo envía órdenes de verdad si se cumplen LAS DOS condiciones:
  1. `modo: real` en config.yaml.
  2. La variable de entorno BOT_DINERO_REAL vale exactamente "si".

En cualquier otro caso trabaja en *ensayo*: lee los saldos reales, calcula qué
compraría o vendería y manda las órdenes a Kraken con `validate`, que hace que
Kraken las revise sin ejecutarlas. No se mueve ni un euro.

Las órdenes son límite (maker), que en Kraken pagan la mitad de comisión que las
de mercado; si no se llenan en unos minutos, el resto se ejecuta a mercado.

Además, el bot se niega a operar si la clave de API tiene permiso de retirada
de fondos, y nunca gestiona más de `real.capital_maximo` euros.
"""
from __future__ import annotations

import json
import time
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


INTENTOS_LIMITE = 5   # veces que se coloca la orden límite antes de pasar a mercado
ESPERA_SEGUNDOS = 60  # tiempo que se deja cada orden límite en el libro


def _precio_libro(exchange, par: str, lado: str) -> float:
    """Mejor precio del lado propio del libro: el de compra más alto o el de venta más bajo.

    Poner ahí la orden la deja esperando en el libro (maker), que en Kraken paga la mitad
    de comisión que una orden a mercado.
    """
    libro = exchange.fetch_order_book(par, 5)
    return float((libro["bids"] if lado == "buy" else libro["asks"])[0][0])


def _limite_con_plan_b(exchange, par: str, lado: str, cantidad: float, minimo: float,
                       dormir, intentos: int, espera: float) -> str:
    """Intenta llenar `cantidad` con órdenes límite post-only; lo que quede, a mercado."""
    pendiente, limite = cantidad, 0.0
    for _ in range(intentos):
        q = float(exchange.amount_to_precision(par, pendiente))
        if q <= 0 or q < minimo:
            break
        precio = float(exchange.price_to_precision(par, _precio_libro(exchange, par, lado)))
        try:
            orden = exchange.create_order(par, "limit", lado, q, precio, {"postOnly": True})
        except ccxt.InvalidOrder:
            continue  # el precio se movió y la orden habría cruzado: se vuelve a intentar
        dormir(espera)
        info = exchange.fetch_order(orden["id"], par)
        if info.get("status") not in ("closed", "canceled", "expired", "rejected"):
            try:
                exchange.cancel_order(orden["id"], par)
            except ccxt.OrderNotFound:
                pass  # se llenó justo antes de cancelarla
            info = exchange.fetch_order(orden["id"], par)
        lleno = float(info.get("filled") or 0.0)
        limite += lleno
        pendiente -= lleno
    texto = f"límite {limite:.8f}"
    q = float(exchange.amount_to_precision(par, max(pendiente, 0.0)))
    if q > 0 and q >= minimo:
        orden = exchange.create_order(par, "market", lado, q, None, {})
        texto += f", resto a mercado {q:.8f} ({orden.get('id')})"
    return texto


def enviar(exchange, ops: list[dict], real: bool, dormir=time.sleep,
           intentos: int = INTENTOS_LIMITE, espera: float = ESPERA_SEGUNDOS) -> list[dict]:
    """Manda las órdenes como límite (maker, comisión 0,40%) en vez de a mercado (0,80%).

    Cada orden se coloca al mejor precio de su lado del libro y se deja `espera` segundos;
    si no se ha llenado, se cancela y se vuelve a colocar al nuevo precio, hasta `intentos`
    veces. Lo que quede sin llenar se compra o vende a mercado, para que el bot nunca se
    quede a medias. Con real=False, Kraken solo valida la orden límite y no espera nada.
    """
    exchange.load_markets()
    resultado = []
    for op in ops:
        mercado = exchange.market(op["par"])
        minimo = (mercado.get("limits", {}).get("amount", {}) or {}).get("min") or 0.0
        cantidad = float(exchange.amount_to_precision(op["par"], op["cantidad"]))
        fila = {**op, "cantidad": cantidad, "real": real}
        lado = "sell" if op["lado"] == "venta" else "buy"
        if cantidad <= 0 or cantidad < minimo:
            fila["resultado"] = f"omitida: menor que el mínimo de Kraken ({minimo})"
        else:
            try:
                if real:
                    fila["resultado"] = "enviada: " + _limite_con_plan_b(
                        exchange, op["par"], lado, cantidad, minimo, dormir, intentos, espera)
                else:
                    precio = float(exchange.price_to_precision(
                        op["par"], _precio_libro(exchange, op["par"], lado)))
                    exchange.create_order(op["par"], "limit", lado, cantidad, precio,
                                          {"postOnly": True, "validate": True})
                    fila["resultado"] = "orden límite validada por Kraken (no ejecutada)"
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
