# Bot-criptos

Bot de trading que opera **solo BTC, ETH y LTC** contra EUR en **Kraken**.
Empieza en **paper trading** (operaciones simuladas con precios reales) y solo
pasará a dinero real cuando lo decidas tú.

> Aviso: ninguna estrategia garantiza beneficios. El bot prioriza limitar pérdidas
> (riesgo máximo por operación y límite de pérdida mensual).

## Plan

1. **Base del bot** (este paso): configuración, conexión a Kraken y descarga de datos.
2. **Estrategia y backtesting**: seguimiento de tendencia en 4h con gestión de riesgo, validada con datos no usados para ajustarla.
3. **Paper trading** 24/7 con registro de operaciones y resumen mensual.
4. **Dinero real** con poco capital, tras 1–2 meses de paper trading.

## Uso

```bash
pip install -r requirements.txt
python -m bot precios                  # precio actual de BTC, ETH y LTC en Kraken
python -m bot descargar --dias 3000    # ~8 años de velas de 4h en data/
python -m pytest -q                    # tests
```

Todo se ajusta en [`config.yaml`](config.yaml): pares, temporalidad, capital y riesgo.

### Desde GitHub, sin instalar nada

En la pestaña **Actions → Descargar datos → Run workflow** se comprueba la
conexión con Kraken y se descarga el histórico como archivo adjunto.

## Datos históricos

La API pública de Kraken solo devuelve las últimas ~720 velas, así que el
histórico largo para el backtesting se toma de **Bitstamp** (mismos pares en EUR,
precios prácticamente idénticos). El bot opera siempre en Kraken.

## Claves de API

El modo paper **no necesita claves**. Para el modo real, copia `.env.example`
a `.env` (o crea *secrets* en GitHub) con `KRAKEN_API_KEY` y `KRAKEN_API_SECRET`.
Crea las claves en Kraken **sin permiso de retirada de fondos**.
