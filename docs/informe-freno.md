# Informe del freno automático de pérdidas

Datos diarios del 2018-12-18 al 2026-11-24, con comisiones, deslizamiento y el límite mensual del 6%. Se probaron 160 combinaciones: caída desde el máximo de 10%, 15%, 20%, 25%, 30%; pausa mínima de 0, 7, 14, 30, 60, 90, 120, 180 días; y cuatro condiciones para volver: solo esperar; 2 de 3 monedas en tendencia alcista; BTC por encima de su media de 100 días; la estrategia simulada vuelve a ir bien.

Cuando salta, el bot vende todo y se queda en euros. Al volver, la caída se vuelve a medir desde el capital de ese día.

## 1. Freno elegido

**caída 20%, pausa 30 días, 2 de 3 monedas en tendencia alcista.**

Se arrancó el bot en cada uno de los 65 meses entre 2019-01 y 2024-05 (cada arranque hasta hoy) y se comparó con el mismo arranque sin freno. Se eligió la combinación cuyo peor 10% de arranques sale mejor, en rentabilidad y en caída máxima.

| | Diferencia con no tener freno |
|---|---|
| Rentabilidad anual, caso típico (mediana) | +2.3% |
| Rentabilidad anual, peor 10% de arranques | +0.4% |
| Rentabilidad anual, peor arranque | -2.2% |
| Caída máxima, caso típico (positivo = cae menos) | +3.4% |
| Caída máxima, peor 10% de arranques | +1.3% |
| Caída máxima, peor arranque | -5.0% |
| Arranques en que cae menos / más que sin freno | 91% / 9% |

### Todo el histórico, arrancando el 2018-12-18

| | Sin freno | Con freno |
|---|---|---|
| Rentabilidad anual | +29.6% | +27.4% |
| Rentabilidad total | +684.8% | +584.3% |
| Caída máxima | -36.7% | -33.9% |
| Peor mes | -10.9% | -11.3% |
| Sharpe | 1.04 | 0.98 |

### Solo los últimos años (2022-12-06 a hoy)

| | Sin freno | Con freno |
|---|---|---|
| Rentabilidad anual | +12.6% | +14.4% |
| Rentabilidad total | +59.9% | +70.5% |
| Caída máxima | -24.9% | -22.8% |
| Peor mes | -10.9% | -10.9% |
| Sharpe | 0.61 | 0.67 |

## 2. Cuándo habría saltado (arrancando el 2018-12-18)

| Salta | Vuelve | Capital al saltar | Con freno mientras estuvo parado | Sin freno en ese tiempo |
|---|---|---|---|---|
| 2020-01-16 | 2020-02-15 | 1,865 EUR | -0.2% | +27.3% |
| 2022-08-19 | 2022-10-26 | 4,392 EUR | -0.3% | -2.7% |
| 2023-07-24 | 2023-10-21 | 3,706 EUR | -0.3% | +1.6% |
| 2024-06-23 | 2024-10-04 | 4,808 EUR | -0.2% | -0.4% |
| 2026-01-20 | 2026-04-06 | 5,225 EUR | -0.2% | +0.0% |

## 3. Las 15 mejores combinaciones

Diferencias con no tener freno, sobre todos los arranques. "Peor 10%" es el resultado que solo un 10% de arranques empeora.

| Freno | Rent. anual típica | Rent. anual peor 10% | Caída típica | Caída peor 10% | Cae menos | Cae más |
|---|---|---|---|---|---|---|
| caída 20%, pausa 30 días, 2 de 3 monedas en tendencia alcista | +2.3% | +0.4% | +3.4% | +1.3% | 91% | 9% |
| caída 30%, pausa 60 días, 2 de 3 monedas en tendencia alcista | +0.8% | +0.0% | +1.6% | +0.0% | 75% | 5% |
| caída 30%, pausa 30 días, 2 de 3 monedas en tendencia alcista | +0.6% | +0.0% | +1.2% | +0.0% | 75% | 5% |
| caída 30%, pausa 14 días, 2 de 3 monedas en tendencia alcista | +0.6% | +0.0% | +1.2% | +0.0% | 72% | 8% |
| caída 30%, pausa 0 días, 2 de 3 monedas en tendencia alcista | +0.5% | +0.0% | +1.2% | +0.0% | 71% | 2% |
| caída 30%, pausa 60 días, solo esperar | +0.5% | +0.0% | +0.8% | +0.0% | 60% | 5% |
| caída 30%, pausa 0 días, solo esperar | +0.0% | +0.0% | +0.0% | +0.0% | 12% | 2% |
| caída 30%, pausa 7 días, solo esperar | +0.0% | +0.0% | +0.0% | +0.0% | 12% | 3% |
| caída 30%, pausa 14 días, solo esperar | +0.0% | +0.0% | +0.0% | +0.0% | 14% | 8% |
| caída 30%, pausa 30 días, solo esperar | +0.0% | -0.1% | +0.0% | -0.2% | 26% | 29% |
| caída 25%, pausa 0 días, 2 de 3 monedas en tendencia alcista | +0.9% | +0.0% | +0.1% | -0.2% | 55% | 31% |
| caída 25%, pausa 0 días, solo esperar | +0.0% | -0.2% | +0.0% | -0.3% | 28% | 22% |
| caída 30%, pausa 7 días, 2 de 3 monedas en tendencia alcista | +0.6% | +0.0% | +1.2% | -0.3% | 69% | 11% |
| caída 15%, pausa 0 días, 2 de 3 monedas en tendencia alcista | +1.2% | -0.4% | +2.5% | +0.0% | 91% | 5% |
| caída 20%, pausa 14 días, la estrategia simulada vuelve a ir bien | +0.9% | -0.6% | +1.7% | -0.4% | 72% | 23% |

Combinaciones vecinas de la elegida (para ver si el resultado depende de un ajuste fino):

| Freno | Rent. anual típica | Rent. anual peor 10% | Caída típica | Caída peor 10% | Cae menos | Cae más |
|---|---|---|---|---|---|---|
| caída 15%, pausa 30 días, 2 de 3 monedas en tendencia alcista | +2.7% | -1.4% | +2.7% | -1.1% | 78% | 18% |
| caída 20%, pausa 14 días, 2 de 3 monedas en tendencia alcista | +1.7% | +0.9% | +3.2% | -0.7% | 78% | 22% |
| caída 20%, pausa 60 días, 2 de 3 monedas en tendencia alcista | +3.3% | -1.9% | +4.0% | -6.3% | 82% | 18% |
| caída 25%, pausa 30 días, 2 de 3 monedas en tendencia alcista | +0.7% | -4.4% | +1.1% | -7.1% | 72% | 20% |

## 4. Qué funciona en general

Mediana de la puntuación (el peor 10% de arranques; más alto es mejor, 0 = igual que sin freno):

Por caída: 10% -13.9%, 15% -2.9%, 20% -5.2%, 25% -5.5%, 30% -4.2%

Por pausa: 0 días -2.3%, 7 días -3.7%, 14 días -2.1%, 30 días -4.5%, 60 días -6.2%, 90 días -7.8%, 120 días -5.1%, 180 días -7.9%

Por condición: 2 de 3 monedas en tendencia alcista -4.1%, BTC por encima de su media de 100 días -5.5%, la estrategia simulada vuelve a ir bien -4.5%, solo esperar -4.2%

## 5. Aviso: elegir con una sola fecha de inicio engaña

Si se elige el freno que mejor fue en la primera mitad (2018-12-18 a 2022-12-06) sale **caída 15%, pausa 120 días, 2 de 3 monedas en tendencia alcista**, que en la segunda mitad hizo esto:

| | Sin freno | Con freno |
|---|---|---|
| Rentabilidad anual | +12.6% | +14.5% |
| Rentabilidad total | +59.9% | +71.3% |
| Caída máxima | -24.9% | -30.0% |
| Peor mes | -10.9% | -10.9% |
| Sharpe | 0.61 | 0.72 |

Con pausas largas el bot vende cerca del fondo y se pierde la recuperación. Por eso la elección se hizo con todos los arranques y buscando el freno que casi nunca perjudica, no el que más gana.

## 6. Robustez: el mismo freno en las 48 variantes de la estrategia

Arrancando el 2018-12-18, el freno reduce la caída máxima en 33 de 48 variantes, la empeora en 15, y mejora la rentabilidad anual en 33.
Mediana de la caída máxima: sin freno -42.0%, con freno -38.4%. Mediana de la rentabilidad anual: sin freno +17.7%, con freno +17.8%.

## Limitaciones

- El freno salta pocas veces (unas pocas en 8 años), así que todo se apoya en pocos episodios. Es un seguro contra una racha mala, no una forma de ganar más.
- Se eligió mirando todo el histórico (no queda un periodo sin usar para comprobarlo). Lo compensa en parte que se exige que funcione con cualquier fecha de arranque; las vecinas también mejoran en el caso típico, aunque sus peores casos son algo peores, así que la ventaja exacta puede ser en parte suerte.
- La estrategia ya pasa a euros cuando una moneda deja de estar en tendencia, y existe el límite mensual; el freno añade una tercera protección para cuando eso no basta.
- Resultados pasados no garantizan resultados futuros.
