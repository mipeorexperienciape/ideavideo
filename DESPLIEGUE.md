# Poner IdeaVideo en línea (gratis, en ~15 minutos)

No necesitas comprar dominio para empezar: Railway te da una URL gratis
(como el ejemplo que viste, `tuapp.up.railway.app`).

## Paso 1 — Crear cuenta en GitHub (gratis)
Entra a https://github.com y crea una cuenta.

## Paso 2 — Subir el proyecto a GitHub
1. En GitHub, botón **New** (nuevo repositorio). Ponle un nombre (ej. `ideavideo`) y créalo.
2. En la página del repo, clic en **"uploading an existing file"**.
3. Descomprime `2-SaaS-Completo.zip` en tu computadora y **arrastra TODOS los archivos y carpetas** de adentro (app.py, static, requirements.txt, Procfile, nixpacks.toml, etc.) a esa página.
4. Clic en **Commit changes**.

## Paso 3 — Crear cuenta en Railway y desplegar
1. Entra a https://railway.app y regístrate con tu cuenta de GitHub.
2. **New Project → Deploy from GitHub repo →** elige el repositorio `ideavideo`.
3. Railway instala solo ffmpeg (por `nixpacks.toml`) y arranca la app (por `Procfile`). Espera a que diga *Success*.

## Paso 4 — Configurar y publicar la URL
1. En tu proyecto → pestaña **Variables**, agrega:
   - `SECRET_KEY` = una frase larga cualquiera (seguridad).
   - Deja `PAYMENTS_TEST` = `1` por ahora (modo prueba, sin cobrar).
2. Pestaña **Settings → Networking → Generate Domain**. Railway te da tu URL pública.
3. Abre esa URL: **¡tu web ya está en línea!** Regístrate y prueba crear un video.

## Paso 5 — Que los datos no se borren (recomendado)
En **Settings → Volumes**, agrega un volumen montado en `/app` para que la base de datos
y los videos se conserven entre actualizaciones.

## Paso 6 — Cuando quieras cobrar de verdad
Agrega tus claves reales y cambia `PAYMENTS_TEST` a `0`:
- `STRIPE_SECRET_KEY` (Stripe) · `MP_ACCESS_TOKEN` (Mercado Pago)
- `PEXELS_API_KEY` (imágenes), `SMTP_*` (correos). Detalle en `Checklist-Lanzamiento.docx`.

> Consejo: primero déjala en modo prueba, verifica que todo funciona, y recién
> después conecta los pagos reales.
