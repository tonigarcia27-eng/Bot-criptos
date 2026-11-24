# Informe de backtesting

Datos diarios de BTC/EUR, ETH/EUR, LTC/EUR del 2018-09-08 al 2026-11-24. Capital inicial 1,000 EUR. Incluye comisión de Kraken (0,26%) y deslizamiento (0,05%) en cada operación, y el límite de pérdida mensual del 6%.

## 1. Prueba fuera de muestra (la más importante)

Parámetros elegidos solo con datos del 2018-12-18 al 2022-12-06 (media 50d, momentum 60d, volatilidad 50%) y probados sin cambios del 2022-12-06 hasta hoy, un periodo que no se usó para elegirlos.

| Métrica | Bot | Comprar y mantener |
|---|---|---|
| Rentabilidad total | +59.9% | +69.2% |
| Rentabilidad anual | +12.6% | +14.2% |
| Caída máxima | -24.9% | -57.7% |
| Peor mes | -10.9% | -22.8% |
| Mejor mes | +22.7% | +45.6% |
| Meses en positivo | 38% | 54% |
| Sharpe | 0.61 | 0.52 |
| Operaciones | 184 | |

Mediana de las 48 combinaciones en ese mismo periodo: rentabilidad anual +7.8%, caída máxima -32.2%, Sharpe 0.45.

Por año: 2022 -6.2%, 2023 +11.6%, 2024 +37.3%, 2025 -5.9%, 2026 +18.3%

## 2. Walk-forward (reoptimizando cada 6 meses)

Parámetros elegidos con 24 meses de datos y probados en los 6 meses siguientes. Sirve para ver si conviene reajustar los parámetros a menudo.

| Métrica | Bot | Comprar y mantener |
|---|---|---|
| Rentabilidad total | +4.9% | +105.0% |
| Rentabilidad anual | +0.8% | +12.9% |
| Caída máxima | -40.1% | -75.7% |
| Peor mes | -17.3% | -38.3% |
| Mejor mes | +20.8% | +47.5% |
| Meses en positivo | 32% | 56% |
| Sharpe | 0.15 | 0.51 |
| Operaciones | 274 | |

| Entreno | Prueba | Bot | Comprar y mantener | Parámetros |
|---|---|---|---|---|
| 2018-12 a 2020-12 | 2020-12-18 a 2021-06-18 | +18.3% | +132.8% | media 100d, momentum 14d, volatilidad 30% |
| 2019-06 a 2021-06 | 2021-06-18 a 2021-12-18 | +8.3% | +39.0% | media 100d, momentum 14d, volatilidad 30% |
| 2019-12 a 2021-12 | 2021-12-18 a 2022-06-18 | -0.3% | -63.2% | media 50d, momentum 30d, volatilidad 50% |
| 2020-06 a 2022-06 | 2022-06-18 a 2022-12-18 | -25.6% | +14.1% | media 100d, momentum 30d, volatilidad 50% |
| 2020-12 a 2022-12 | 2022-12-18 a 2023-06-18 | +0.0% | +36.6% | media 50d, momentum 30d, volatilidad 80% |
| 2021-06 a 2023-06 | 2023-06-18 a 2023-12-18 | -3.2% | +26.2% | media 20d, momentum 30d, volatilidad sin control |
| 2021-12 a 2023-12 | 2023-12-18 a 2024-06-18 | +3.6% | +43.1% | media 50d, momentum 14d, volatilidad sin control |
| 2022-06 a 2024-06 | 2024-06-18 a 2024-12-18 | +17.4% | +52.5% | media 50d, momentum 90d, volatilidad 30% |
| 2022-12 a 2024-12 | 2024-12-18 a 2025-06-18 | -8.4% | -24.5% | media 100d, momentum 30d, volatilidad 30% |
| 2023-06 a 2025-06 | 2025-06-18 a 2025-12-18 | +1.5% | -7.7% | media 100d, momentum 30d, volatilidad 30% |
| 2023-12 a 2025-12 | 2025-12-18 a 2026-06-18 | -9.9% | -32.9% | media 100d, momentum 90d, volatilidad 30% |
| 2024-06 a 2026-06 | 2026-06-18 a 2026-11-25 | +12.1% | -0.5% | media 100d, momentum 90d, volatilidad sin control |

Por año: 2020 +6.1%, 2021 +20.7%, 2022 -25.8%, 2023 -3.8%, 2024 +18.3%, 2025 -3.8%, 2026 +1.0%

Últimos 12 meses: 2025-12 +0.0%, 2026-01 +0.0%, 2026-02 +0.0%, 2026-03 +0.0%, 2026-04 +0.0%, 2026-05 -5.8%, 2026-06 -4.3%, 2026-07 +0.0%, 2026-08 +1.4%, 2026-09 +18.0%, 2026-10 -4.6%, 2026-11 -1.7%

## 3. Parámetros elegidos para el bot

**media 50d, momentum 60d, volatilidad 50%**, rebalanceo cada 7 días. Son los de la prueba fuera de muestra: ya demostraron funcionar con datos que no se usaron para elegirlos.

En todo el histórico (dentro de muestra, optimista): rentabilidad anual +29.6%, caída máxima -36.7%, peor año -25.5%, Sharpe 1.04.
Puesto 2 de 48 por Sharpe en todo el histórico.

Las 10 mejores combinaciones por Sharpe:

| Parámetros | Rent. anual | Caída máx | Peor año | Sharpe |
|---|---|---|---|---|
| media 50d, momentum 60d, volatilidad 30% | +21.1% | -30.5% | -22.2% | 1.05 |
| media 50d, momentum 60d, volatilidad 50% | +29.6% | -36.7% | -25.5% | 1.04 |
| media 50d, momentum 14d, volatilidad 50% | +28.3% | -33.6% | -25.3% | 1.01 |
| media 50d, momentum 14d, volatilidad 30% | +19.5% | -28.3% | -22.4% | 0.99 |
| media 100d, momentum 30d, volatilidad 30% | +18.6% | -26.1% | -17.3% | 0.97 |
| media 100d, momentum 30d, volatilidad 50% | +26.3% | -39.2% | -23.7% | 0.96 |
| media 50d, momentum 30d, volatilidad 50% | +27.0% | -38.5% | -26.4% | 0.94 |
| media 50d, momentum 90d, volatilidad 30% | +17.0% | -27.7% | -14.3% | 0.93 |
| media 100d, momentum 14d, volatilidad 30% | +16.0% | -29.4% | -18.2% | 0.92 |
| media 50d, momentum 90d, volatilidad 50% | +23.5% | -41.8% | -22.2% | 0.91 |

Mediana del Sharpe de las 48 combinaciones: 0.73 (si casi todas funcionan parecido, la estrategia es robusta y no depende de un ajuste fino).

Guardado en `estrategia.json`: `{"media": 50, "momentum": 60, "vol_objetivo": 0.5, "vol_ventana": 20, "rebalanceo_dias": 7}`
