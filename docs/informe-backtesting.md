# Informe de backtesting

Datos diarios de BTC/EUR, ETH/EUR, LTC/EUR del 2018-09-08 al 2026-11-24. Capital inicial 200 EUR. Incluye comisión de Kraken con órdenes límite (0.40%) y deslizamiento (0.05%) en cada operación, y el límite de pérdida mensual del 6%.

## 1. Prueba fuera de muestra (la más importante)

Parámetros elegidos solo con datos del 2018-12-18 al 2022-12-06 (media 50d, momentum 60d, volatilidad 50%) y probados sin cambios del 2022-12-06 hasta hoy, un periodo que no se usó para elegirlos.

| Métrica | Bot | Comprar y mantener |
|---|---|---|
| Rentabilidad total | +53.4% | +69.2% |
| Rentabilidad anual | +11.4% | +14.2% |
| Caída máxima | -25.3% | -57.7% |
| Peor mes | -11.6% | -22.8% |
| Mejor mes | +22.9% | +45.6% |
| Meses en positivo | 35% | 54% |
| Sharpe | 0.56 | 0.52 |
| Operaciones | 159 | |

Mediana de las 48 combinaciones en ese mismo periodo: rentabilidad anual +7.0%, caída máxima -32.7%, Sharpe 0.42.

Por año: 2022 -6.3%, 2023 +9.2%, 2024 +36.3%, 2025 -6.1%, 2026 +17.2%

## 2. Walk-forward (reoptimizando cada 6 meses)

Parámetros elegidos con 24 meses de datos y probados en los 6 meses siguientes. Sirve para ver si conviene reajustar los parámetros a menudo.

| Métrica | Bot | Comprar y mantener |
|---|---|---|
| Rentabilidad total | +26.7% | +105.0% |
| Rentabilidad anual | +4.1% | +12.9% |
| Caída máxima | -41.6% | -75.7% |
| Peor mes | -17.5% | -38.3% |
| Mejor mes | +21.8% | +47.5% |
| Meses en positivo | 31% | 56% |
| Sharpe | 0.30 | 0.51 |
| Operaciones | 245 | |

| Entreno | Prueba | Bot | Comprar y mantener | Parámetros |
|---|---|---|---|---|
| 2018-12 a 2020-12 | 2020-12-18 a 2021-06-18 | +18.7% | +132.8% | media 100d, momentum 14d, volatilidad 30% |
| 2019-06 a 2021-06 | 2021-06-18 a 2021-12-18 | +9.0% | +39.0% | media 100d, momentum 14d, volatilidad 30% |
| 2019-12 a 2021-12 | 2021-12-18 a 2022-06-18 | -0.2% | -63.2% | media 50d, momentum 30d, volatilidad 50% |
| 2020-06 a 2022-06 | 2022-06-18 a 2022-12-18 | -26.2% | +14.1% | media 100d, momentum 30d, volatilidad 50% |
| 2020-12 a 2022-12 | 2022-12-18 a 2023-06-18 | -1.2% | +36.6% | media 50d, momentum 30d, volatilidad 80% |
| 2021-06 a 2023-06 | 2023-06-18 a 2023-12-18 | -4.3% | +26.2% | media 20d, momentum 30d, volatilidad sin control |
| 2021-12 a 2023-12 | 2023-12-18 a 2024-06-18 | +22.6% | +43.1% | media 50d, momentum 90d, volatilidad 30% |
| 2022-06 a 2024-06 | 2024-06-18 a 2024-12-18 | +17.7% | +52.5% | media 50d, momentum 90d, volatilidad 30% |
| 2022-12 a 2024-12 | 2024-12-18 a 2025-06-18 | -9.0% | -24.5% | media 100d, momentum 30d, volatilidad 30% |
| 2023-06 a 2025-06 | 2025-06-18 a 2025-12-18 | +1.7% | -7.7% | media 100d, momentum 30d, volatilidad 30% |
| 2023-12 a 2025-12 | 2025-12-18 a 2026-06-18 | -6.1% | -32.9% | media 100d, momentum 90d, volatilidad 30% |
| 2024-06 a 2026-06 | 2026-06-18 a 2026-11-25 | +12.2% | -0.5% | media 100d, momentum 60d, volatilidad 30% |

Por año: 2020 +6.0%, 2021 +22.0%, 2022 -26.3%, 2023 -5.5%, 2024 +39.4%, 2025 -4.2%, 2026 +5.3%

Últimos 12 meses: 2025-12 +0.0%, 2026-01 +0.0%, 2026-02 +0.0%, 2026-03 +0.0%, 2026-04 +0.0%, 2026-05 -6.1%, 2026-06 +0.0%, 2026-07 +0.0%, 2026-08 +4.0%, 2026-09 +14.3%, 2026-10 -5.6%, 2026-11 +0.0%

## 3. Parámetros elegidos para el bot

**media 50d, momentum 60d, volatilidad 50%**, rebalanceo cada 7 días. Son los de la prueba fuera de muestra: ya demostraron funcionar con datos que no se usaron para elegirlos.

En todo el histórico (dentro de muestra, optimista): rentabilidad anual +28.1%, caída máxima -38.2%, peor año -26.2%, Sharpe 1.00.
Puesto 2 de 48 por Sharpe en todo el histórico.

Las 10 mejores combinaciones por Sharpe:

| Parámetros | Rent. anual | Caída máx | Peor año | Sharpe |
|---|---|---|---|---|
| media 50d, momentum 60d, volatilidad 30% | +20.4% | -31.1% | -22.7% | 1.02 |
| media 50d, momentum 60d, volatilidad 50% | +28.1% | -38.2% | -26.2% | 1.00 |
| media 50d, momentum 14d, volatilidad 50% | +26.0% | -33.8% | -26.2% | 0.95 |
| media 100d, momentum 30d, volatilidad 30% | +17.9% | -27.2% | -17.6% | 0.93 |
| media 50d, momentum 14d, volatilidad 30% | +18.1% | -29.1% | -23.1% | 0.93 |
| media 100d, momentum 30d, volatilidad 50% | +25.2% | -40.3% | -24.1% | 0.93 |
| media 50d, momentum 30d, volatilidad 50% | +25.9% | -39.9% | -27.3% | 0.91 |
| media 50d, momentum 90d, volatilidad 30% | +16.2% | -28.8% | -14.6% | 0.90 |
| media 50d, momentum 90d, volatilidad 50% | +22.1% | -42.9% | -22.6% | 0.87 |
| media 100d, momentum 14d, volatilidad 30% | +14.9% | -30.7% | -18.6% | 0.86 |

Mediana del Sharpe de las 48 combinaciones: 0.68 (si casi todas funcionan parecido, la estrategia es robusta y no depende de un ajuste fino).

Guardado en `estrategia.json`: `{"media": 50, "momentum": 60, "vol_objetivo": 0.5, "vol_ventana": 20, "rebalanceo_dias": 7}`
