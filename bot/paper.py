"""Paper trading: el bot opera con dinero simulado y precios reales de Kraken.

Se ejecuta una vez al día (GitHub Actions, poco después de las 00:00 UTC):
  1. Descarga las velas diarias cerradas de Kraken.
  2. Calcula los pesos de la estrategia con el último cierre.
  3. Si toca (cada `rebalanceo_dias` o por el límite de pérdida mensual),
     ajusta la cartera simulada al precio actual, con la comisión de Kraken.
  4. Guarda el estado, las operaciones y el resumen en la carpeta `paper/`.

La lógica es la misma que la del backtesting (bot/backtest.py), para que lo
que se ve en simulado se parezca a lo que se probó.
"""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .backtest import COMISION, DESLIZAMIENTO, rebalancear
from .config import RAIZ, Config
from .estrategia import Parametros, pesos_objetivo

CARPETA = RAIZ / "paper"


@dataclass
class Estado:
    inicio: str
    capital_inicial: float
    efectivo: float
    unidades: dict[str, float]
    precios_inicio: dict[str, float]          # para comparar con comprar y mantener
    mes: str = ""
    capital_inicio_mes: float = 0.0
    bloqueado: bool = False
    ultimo_rebalanceo: str = ""
    maximo_fin_de_mes: float = 0.0            # referencia para saber qué beneficio es retirable
    ultima_ejecucion: str = ""
    historial_mensual: dict[str, float] = field(default_factory=dict)  # mes -> capital al cierre

    @classmethod
    def nuevo(cls, cfg: Config, hoy: date, precios: dict[str, float]) -> "Estado":
        return cls(inicio=hoy.isoformat(), capital_inicial=cfg.capital_inicial, efectivo=cfg.capital_inicial,
                   unidades={par: 0.0 for par in cfg.pares}, precios_inicio=dict(precios),
                   maximo_fin_de_mes=cfg.capital_inicial)

    def capital(self, precios: dict[str, float]) -> float:
        return self.efectivo + sum(u * precios[par] for par, u in self.unidades.items())


def paso_diario(estado: Estado, cierres: pd.DataFrame, precios: dict[str, float], hoy: date,
                p: Parametros, cfg: Config) -> list[dict]:
    """Un día de paper trading. Modifica `estado` y devuelve las operaciones hechas.

    `cierres`: velas diarias YA CERRADAS (índice fecha UTC, una columna por par).
    `precios`: precio actual de cada par, al que se ejecutan las órdenes simuladas.
    """
    if estado.ultima_ejecucion == hoy.isoformat():
        return []  # ya se ejecutó hoy
    pares = list(cierres.columns)
    precio = np.array([precios[par] for par in pares])
    capital = estado.capital(precios)

    mes = hoy.strftime("%Y-%m")
    if mes != estado.mes:
        if estado.mes:
            estado.historial_mensual[estado.mes] = capital
            estado.maximo_fin_de_mes = max(estado.maximo_fin_de_mes, capital)
        estado.mes, estado.capital_inicio_mes, estado.bloqueado = mes, capital, False

    stop_mensual = (not estado.bloqueado
                    and capital <= estado.capital_inicio_mes * (1 - cfg.riesgo.perdida_maxima_mensual))
    if stop_mensual:
        estado.bloqueado = True
    dias = (hoy - date.fromisoformat(estado.ultimo_rebalanceo)).days if estado.ultimo_rebalanceo else None
    toca = dias is None or dias >= p.rebalanceo_dias or stop_mensual

    operaciones: list[dict] = []
    if toca:
        pesos = pesos_objetivo(cierres, p).iloc[-1].reindex(pares).fillna(0.0).to_numpy()
        deseado = np.zeros(len(pares)) if estado.bloqueado else pesos
        unidades = np.array([estado.unidades.get(par, 0.0) for par in pares])
        # El deslizamiento se aplica al precio: se compra algo más caro y se vende algo más barato.
        unidades, estado.efectivo, hechas = rebalancear(unidades, estado.efectivo, precio, deseado,
                                                        COMISION + DESLIZAMIENTO)
        estado.unidades = dict(zip(pares, map(float, unidades)))
        estado.ultimo_rebalanceo = hoy.isoformat()
        motivo = "stop mensual" if stop_mensual else "rebalanceo"
        operaciones = [{"fecha": hoy.isoformat(), "par": pares[j], "lado": lado, "precio": round(precio[j], 2),
                        "importe_eur": round(importe, 2), "peso_objetivo": round(float(deseado[j]), 4),
                        "motivo": motivo} for j, lado, importe in hechas]
    estado.ultima_ejecucion = hoy.isoformat()
    return operaciones


# ---------------------------------------------------------------- E/S y resumen

def cargar_estado(carpeta: Path = CARPETA) -> Estado | None:
    ruta = carpeta / "estado.json"
    return Estado(**json.loads(ruta.read_text(encoding="utf-8"))) if ruta.exists() else None


def reiniciar_si_cambia_capital(cfg: Config, carpeta: Path = CARPETA) -> Estado | None:
    """Si `capital_inicial` de config.yaml no coincide con el de la simulación en curso,
    archiva la simulación anterior en `carpeta/anteriores/` y devuelve None para empezar
    otra desde cero con el capital nuevo."""
    estado = cargar_estado(carpeta)
    if estado is None or estado.capital_inicial == cfg.capital_inicial:
        return estado
    destino = carpeta / "anteriores" / f"{estado.inicio}_{estado.capital_inicial:g}eur"
    destino.mkdir(parents=True, exist_ok=True)
    for nombre in ("estado.json", "diario.csv", "operaciones.csv", "RESUMEN.md"):
        if (carpeta / nombre).exists():
            (carpeta / nombre).replace(destino / nombre)
    return None


def guardar(estado: Estado, operaciones: list[dict], precios: dict[str, float], hoy: date,
            carpeta: Path = CARPETA) -> None:
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "estado.json").write_text(json.dumps(asdict(estado), indent=2) + "\n", encoding="utf-8")
    _anexar_csv(carpeta / "operaciones.csv", operaciones)
    fila = {"fecha": hoy.isoformat(), "capital": round(estado.capital(precios), 2),
            "efectivo": round(estado.efectivo, 2),
            **{f"precio_{par.split('/')[0]}": precios[par] for par in estado.unidades},
            **{f"valor_{par.split('/')[0]}": round(u * precios[par], 2) for par, u in estado.unidades.items()}}
    _anexar_csv(carpeta / "diario.csv", [fila])


def _anexar_csv(ruta: Path, filas: list[dict]) -> None:
    if not filas:
        return
    nuevo = not ruta.exists()
    with ruta.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        if nuevo:
            w.writeheader()
        w.writerows(filas)


def resumen(estado: Estado, precios: dict[str, float], carpeta: Path = CARPETA) -> str:
    capital = estado.capital(precios)
    ref = np.mean([precios[par] / estado.precios_inicio[par] for par in estado.unidades]) * estado.capital_inicial
    retirable = max(0.0, capital - estado.maximo_fin_de_mes)
    mes_pct = capital / estado.capital_inicio_mes - 1 if estado.capital_inicio_mes else 0.0
    l = [
        "# Paper trading",
        "",
        f"Actualizado: {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC · en marcha desde {estado.inicio}",
        "",
        "| | |",
        "|---|---|",
        f"| Capital simulado | **{capital:,.2f} EUR** |",
        f"| Rentabilidad desde el inicio | {capital / estado.capital_inicial - 1:+.2%} |",
        f"| Comprar y mantener (referencia) | {ref / estado.capital_inicial - 1:+.2%} |",
        f"| Este mes | {mes_pct:+.2%}{' (límite mensual alcanzado: en euros hasta el mes que viene)' if estado.bloqueado else ''} |",
        f"| Beneficio retirable (sobre el máximo de cierre de mes) | {retirable:,.2f} EUR |",
        f"| Euros sin invertir | {estado.efectivo:,.2f} EUR |",
        "",
        "## Cartera",
        "",
        "| Moneda | Cantidad | Precio | Valor | % del capital |",
        "|---|---|---|---|---|",
    ]
    for par, u in estado.unidades.items():
        v = u * precios[par]
        l.append(f"| {par} | {u:.6f} | {precios[par]:,.2f} | {v:,.2f} EUR | {v / capital:.1%} |")
    if estado.historial_mensual:
        l += ["", "## Meses cerrados", "", "| Mes | Capital al cierre | Rentabilidad |", "|---|---|---|"]
        previo = estado.capital_inicial
        for mes, cap in estado.historial_mensual.items():
            l.append(f"| {mes} | {cap:,.2f} EUR | {cap / previo - 1:+.2%} |")
            previo = cap
    ops = carpeta / "operaciones.csv"
    if ops.exists():
        ultimas = pd.read_csv(ops).tail(10)
        l += ["", "## Últimas operaciones", "", "| Fecha | Par | Lado | Precio | Importe | Motivo |",
              "|---|---|---|---|---|---|"]
        l += [f"| {r.fecha} | {r.par} | {r.lado} | {r.precio:,.2f} | {r.importe_eur:,.2f} EUR | {r.motivo} |"
              for r in ultimas.itertuples()]
    l.append("")
    return "\n".join(l)


def cierres_kraken(exchange, pares: list[str], dias: int = 200) -> pd.DataFrame:
    """Velas diarias cerradas de Kraken (se descarta la de hoy, que aún no ha cerrado)."""
    hoy = pd.Timestamp.now(tz="UTC").normalize()
    series = {}
    for par in pares:
        velas = exchange.fetch_ohlcv(par, "1d", limit=dias)
        df = pd.DataFrame(velas, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df.index = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        series[par] = df.loc[df.index < hoy, "close"]
    return pd.DataFrame(series).dropna()


def ejecutar(cfg: Config, p: Parametros, exchange, carpeta: Path = CARPETA) -> str:
    from .exchange import precio_actual

    hoy = datetime.now(timezone.utc).date()
    cierres = cierres_kraken(exchange, cfg.pares, dias=max(200, p.dias_minimos + 10))
    precios = {par: precio_actual(exchange, par) for par in cfg.pares}
    estado = reiniciar_si_cambia_capital(cfg, carpeta) or Estado.nuevo(cfg, hoy, precios)
    operaciones = paso_diario(estado, cierres, precios, hoy, p, cfg)
    guardar(estado, operaciones, precios, hoy, carpeta)
    texto = resumen(estado, precios, carpeta)
    (carpeta / "RESUMEN.md").write_text(texto, encoding="utf-8")
    return texto
