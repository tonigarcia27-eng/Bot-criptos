# Cómo crear las claves de API de Kraken

Las claves permiten que el bot vea tu saldo y, cuando tú lo decidas, compre y venda.
**Nunca deben poder retirar dinero.** Así, aunque alguien las robara, no podría sacar
fondos de tu cuenta. El bot lo comprueba y se niega a funcionar con una clave que pueda retirar.

## 1. Crear la clave en Kraken

1. Entra en [kraken.com](https://www.kraken.com) con tu cuenta (versión web, no la app *Kraken* sencilla).
2. Arriba a la derecha, pulsa tu icono → **Settings** (Ajustes) → **API**.
3. Pulsa **Create API key** (Crear clave de API).
4. Ponle un nombre, por ejemplo `bot-criptos`.
5. En **Permissions** (Permisos) marca **solo** estas casillas:
   - ✅ **Query Funds** (consultar fondos)
   - ✅ **Query Open Orders & Trades** (consultar órdenes abiertas y operaciones)
   - ✅ **Query Closed Orders & Trades** (consultar órdenes cerradas y operaciones)
   - ✅ **Create & Modify Orders** (crear y modificar órdenes)
   - ✅ **Cancel/Close Orders** (cancelar órdenes)
6. Deja **sin marcar** todo lo demás, y sobre todo:
   - ❌ **Withdraw Funds** (retirar fondos)
   - ❌ **Deposit Funds** (depositar fondos)
   - ❌ **Export Data**, **Access WebSockets API** y lo relacionado con *Earn/Staking*
7. Pulsa **Generate key** (Generar clave). Kraken te enseñará dos textos:
   - **API Key** (la clave)
   - **Private Key** (el secreto)

   El secreto **solo se ve una vez**. Cópialos en un sitio seguro hasta el paso 2.
   No los mandes por chat, email ni los pegues en ningún archivo del repositorio.

## 2. Guardarlas en GitHub (como *secrets*)

1. Abre el repositorio en GitHub → **Settings** → **Secrets and variables** → **Actions**.
2. Pulsa **New repository secret** y crea:
   - Nombre `KRAKEN_API_KEY`, valor: la **API Key**.
3. Otra vez **New repository secret**:
   - Nombre `KRAKEN_API_SECRET`, valor: la **Private Key**.

GitHub las guarda cifradas: nadie (ni tú) puede volver a verlas, solo usarlas el bot.

## 3. Comprobar que funciona

En GitHub: **Actions → Comprobar Kraken → Run workflow**. En un minuto verás:

- Tus saldos de EUR, BTC, ETH y LTC.
- "Bien: la clave no puede retirar fondos."
- Un **ensayo** de las órdenes que el bot haría hoy. Kraken las revisa pero **no las ejecuta**.

Si sale "PELIGRO: esta clave PUEDE RETIRAR FONDOS", borra la clave en Kraken
(Settings → API → la clave → Delete) y crea otra siguiendo el paso 1.

## El dinero real sigue apagado

El bot **no opera con dinero real** aunque tenga las claves. Para eso harían falta
dos cosas a la vez, y ninguna está puesta:

1. `modo: real` en `config.yaml`.
2. La variable `BOT_DINERO_REAL=si`.

Además, en modo real nunca gestionaría más de `real.capital_maximo` euros (200 por defecto).
Cuando quieras dar ese paso (tras 1–2 meses de paper trading), se hará en un cambio aparte.
