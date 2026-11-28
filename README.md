# Bot-criptos

Bot de trading que opera **solo BTC, ETH y LTC** contra EUR en **Kraken**.
Empieza en **paper trading** (operaciones simuladas con precios reales) y solo
pasará a dinero real cuando lo decidas tú.

> Aviso: ninguna estrategia garantiza beneficios. El bot prioriza limitar pérdidas
> (riesgo máximo por operación y límite de pérdida mensual).

## Estrategia

**Rotación por momentum con filtro de tendencia** (detalles en [`bot/estrategia.py`](bot/estrategia.py)):

- Una vez por semana, con el cierre diario, el bot decide cuánto tener de cada moneda (máximo 1/3 del capital en cada una).
- Solo mantiene una moneda si está por encima de su media de 50 días **y** ha subido en los últimos 60 días. Si no, esa parte queda en euros.
- Si una moneda está muy volátil, compra menos de ella (volatilidad objetivo del 50% anual).
- Si en un mes el capital cae un 6%, vende todo y espera al mes siguiente.
- **Freno automático**: si el capital cae un 20% desde su máximo, vende todo y se queda en euros. Pasados
  al menos 30 días, vuelve a operar solo cuando al menos 2 de las 3 monedas están en tendencia alcista.
  No hace falta reactivarlo a mano. Estudio en [`docs/informe-freno.md`](docs/informe-freno.md).

Resultado en la prueba fuera de muestra (diciembre 2022 a noviembre 2026, con datos que no se usaron para elegir los parámetros):
**+12,6% anual con una caída máxima del -25%**, frente a +14,2% anual y -58% de caída de comprar y mantener.
El informe completo está en [`docs/informe-backtesting.md`](docs/informe-backtesting.md).

Lo que **no** hace: ganar todos los meses. Gana en pocas rachas fuertes (38% de meses en positivo) y en los
mercados bajistas se queda en euros. Para retirar beneficios conviene hacerlo solo cuando el capital esté
por encima de su máximo anterior.

## Plan

1. ✅ Base del bot: configuración, conexión a Kraken y descarga de datos.
2. ✅ Estrategia y backtesting con 8 años de datos y validación fuera de muestra.
3. ✅ **Paper trading** diario con precios reales de Kraken, registro de operaciones y resumen mensual.
4. **Dinero real** con poco capital, tras 1–2 meses de paper trading.

## Uso

```bash
pip install -r requirements.txt
python -m bot precios                  # precio actual de BTC, ETH y LTC en Kraken
python -m bot descargar --dias 3000    # ~8 años de velas de 4h en data/
python -m bot backtest                 # prueba los parámetros de estrategia.json
python -m bot optimizar                # busca parámetros y escribe resultados/informe.md
python -m bot freno                    # estudia el freno automático y escribe resultados/informe-freno.md
python -m bot paper                    # un día de paper trading (estado en paper/)
python -m bot kraken                   # comprueba las claves de Kraken (no opera)
python -m pytest -q                    # tests
```

Todo se ajusta en [`config.yaml`](config.yaml) (pares, capital y riesgo) y [`estrategia.json`](estrategia.json) (parámetros de la estrategia). Para un bot más prudente, baja `vol_objetivo` a 0.3: gana algo menos y cae menos.
Si cambias `capital_inicial`, el paper trading empieza de nuevo con ese capital y la simulación anterior se guarda en `anteriores/` dentro de la rama `paper`.

### Desde GitHub, sin instalar nada

- **Actions → Descargar datos → Run workflow**: comprueba la conexión con Kraken y guarda el histórico en la rama `datos`.
- **Actions → Backtesting → Run workflow**: repite la optimización y publica el informe en el resumen de la ejecución.

## Paper trading

Cada día a las 00:15 UTC, GitHub Actions ejecuta `python -m bot paper`: descarga las velas
diarias de Kraken, decide y simula las órdenes al precio real con la comisión de Kraken.
El estado se guarda en la rama [`paper`](../../tree/paper):

- [`RESUMEN.md`](../../blob/paper/RESUMEN.md): capital, cartera, rentabilidad frente a comprar y mantener,
  meses cerrados y **beneficio retirable** (lo que el capital supera su mejor cierre de mes anterior).
- `operaciones.csv`: cada compra y venta simulada.
- `diario.csv`: capital y precios de cada día.

Para lanzarlo a mano: **Actions → Paper trading → Run workflow** (si ya se ejecutó ese día, no repite operaciones).
Para empezar de cero, borra la rama `paper`.

## Datos históricos

La API pública de Kraken solo devuelve las últimas ~720 velas, así que el
histórico largo para el backtesting se toma de **Bitstamp** (mismos pares en EUR,
precios prácticamente idénticos). El bot opera siempre en Kraken.

## Conexión con Kraken (dinero real apagado)

El modo paper **no necesita claves**. Para conectar el bot a tu cuenta de Kraken sigue
[`docs/claves-kraken.md`](docs/claves-kraken.md): crea una clave **sin permiso de retirada**
y guárdala en GitHub como *secrets* `KRAKEN_API_KEY` y `KRAKEN_API_SECRET` (o en un `.env`
local, copiando `.env.example`; el `.env` nunca se sube).

```bash
python -m bot kraken   # comprueba las claves, muestra saldos y avisa si la clave puede retirar
python -m bot real     # ensayo: calcula las órdenes de hoy y Kraken las valida sin ejecutarlas
```

El dinero real solo se activa con **dos llaves a la vez**: `modo: real` en `config.yaml`
**y** la variable `BOT_DINERO_REAL=si`. Aun así, el bot no opera si la clave puede retirar
fondos y nunca gestiona más de `real.capital_maximo` euros. Ningún workflow de GitHub
activa el dinero real; **Actions → Comprobar Kraken** solo hace la comprobación y el ensayo.
