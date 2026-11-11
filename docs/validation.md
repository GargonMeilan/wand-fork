# Validación de Ruffle — 11 de noviembre de 2026

## Ejecutado en desarrollo (Windows)

- `docker compose config --quiet`: correcto para el archivo base y para la
  combinación con `docker-compose.ruffle-only.yml`.
- `node --test tests/legacy-player.test.cjs`: **4/4 correctas**.
- `python -m unittest discover -s tests -p 'test_*.py' -v`: **5/5 correctas**,
  incluido Websockify 0.13.0 real contra un servidor TCP de eco.
- `node tests/browser-smoke.cjs` con Playwright 1.56.1 y Chromium 141:
  **correcto**. Ruffle 0.7.1 carga JS y WASM; boots, loader, shell, lista de
  servidores, módulos de comunicación/login, SWF de contenido y JSON originales
  responden sin fallos. Se observó visualmente la pantalla inicial con Start.
  El caso usa un prefijo `/media` y puerto HTTP no estándar, lo que verifica la
  corrección del primer cargador. No usa un backend Houdini simulado como prueba
  de login.
- Los manifiestos de las imágenes Node, Nginx y Python fijadas existen en el
  registro. El lockfile de Ruffle y su descarga mediante `npm ci` se verificaron.
- `git diff --check`: correcto.

## Ejecutado en GitHub Actions con Docker

El [workflow inicial](https://github.com/GargonMeilan/wand-fork/actions/runs/43049286101)
terminó **correctamente**. Ejecutó builds web/proxy y `tests/check-nginx.sh` para
renderizar las plantillas con Dockerize y comprobarlas con `nginx -t`, rutas y
MIME WASM en cinco escenarios. También repitió correctamente las pruebas Node y
Python y la validación de ambos Compose. No se pudo ejecutar Docker localmente:
el CLI está instalado pero no hay motor accesible/iniciado.

Se añadió además `tests/check-proxy-chain.py` para verificar la cadena completa
Nginx -> Websockify -> TCP con los cinco destinos, bajo las restricciones del
contenedor de producción y sin base de datos. Pendiente del siguiente workflow.

## Pendiente de integración real

- Build y arranque del stack completo con sus servicios y base de datos.
- Nginx generado y tráfico de WebSocket a través de Traefik/Dokploy con TLS real.
- Login de una cuenta, elección de servidor y entrada a una sala.
- Firefox y Edge, idiomas adicionales, registro/activación y reCAPTCHA real.
- Minijuegos, sonido, LocalConnection entre instancias y demás compatibilidad AS2.

No se ha cambiado el despliegue de producción, ni se han borrado volúmenes o
alterado datos. La prueba de navegador es una prueba de arranque del cliente;
la prueba de eco verifica transporte. Ninguna demuestra por sí sola que se
puede completar una sesión de juego.
