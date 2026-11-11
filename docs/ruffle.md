# Legacy con Ruffle y Dokploy

## Alcance y arquitectura

El cliente Legacy AS2 usa Ruffle Web **0.7.1**, con URL e integridad SHA-512
fijadas en `web/ruffle/package-lock.json`. El build descarga el paquete y copia
JavaScript, WASM y licencias a `/opt/wand/ruffle` en la imagen Nginx. Durante el
juego no se consulta ningún CDN. Websockify **0.13.0** y sus dependencias están
fijados en `websocket/requirements.txt`.

```text
Navegador -- HTTPS/WSS --> Traefik de Dokploy -- HTTP/WS --> web:80
  |                                                        |
  +-- Ruffle + boots.swf + medios originales                +--> websocket:8080
                                                                 |
                                                             TCP interno
                                                                 |
                                           houdini_login / houdini_<mundo>
```

Wand conserva PostgreSQL, Redis, Houdini, Dash y Snowflake. La base de datos no
cambia. Dash sigue atendiendo registro, activación y administración por las rutas
Nginx existentes; Snowflake corresponde a Card-Jitsu Snow/Vanilla, fuera de esta
integración. Vanilla conserva su HTML Flash. Las rutas y puertos TCP anteriores
siguen disponibles en el Compose base para compatibilidad.

Antes del cambio, cuatro plantillas Legacy incrustaban un `<object>` Flash con
`boots.swf` y `lang`. Dockerize v0.7.0 genera esos HTML, ambos sitios Nginx y
`servers.xml` al arrancar `web`. Los volúmenes de medios son submódulos Git y
reciben los archivos generados. Los recursos nuevos de Ruffle quedan fuera de
esos volúmenes para que el montaje no los oculte.

Se inspeccionaron los SWF del commit Legacy fijado por el repositorio:

1. `boots.swf` inicia `play/v2/client/load.swf`; le pasa `basePath`, las rutas de
   cliente/contenido/juegos y el idioma. Se conserva ese arranque.
2. Obtiene el host inicial mediante `LocalConnection.domain()`. Esto pierde
   puertos y devuelve `localhost` con determinadas IP. `urlRewriteRules` redirige
   **solo** la URL absoluta `/play/v2/client/load.swf` al medio configurado.
   El FlashVar `base` pasa a `shell.swf` el prefijo completo de medios.
3. `servers.swf` lee `<base>/servers.xml`; `airtower.swf` implementa conexiones
   `XMLSocket`. Houdini usa mensajes XML/XT delimitados por `\0` y ofrece una
   respuesta de política Flash en el mismo puerto. No hace falta publicar 843.
4. Ruffle busca un `socketProxy` con coincidencia **exacta** de `host` y `port`.
   Los valores deben coincidir con `servers.xml`, aunque el navegador conecta
   realmente a la URL `proxyUrl`, nunca directamente por TCP.

| Socket solicitado en GAME_ADDRESS | Ruta WebSocket en el dominio del juego | Destino interno |
| --- | --- | --- |
| GAME_LOGIN_PORT (6112 por defecto) | `/__wand/ws/login` | `houdini_login:GAME_LOGIN_PORT` |
| 9875 (Blizzard, 3100, en; también redemption) | `/__wand/ws/blizzard` | `houdini_blizzard:9875` |
| 9876 (Glaciar, 3101, es) | `/__wand/ws/glaciar` | `houdini_glaciar:9876` |
| 9877 (Avalanche, 3102, pt) | `/__wand/ws/avalanche` | `houdini_avalanche:9877` |
| 9878 (Yeti, 3103, fr) | `/__wand/ws/yeti` | `houdini_yeti:9878` |

Un solo Websockify usa `ReadOnlyTokenFile` con esos cinco destinos fijos. Nginx
traduce la ruta a un token; el token es un selector público, no una contraseña.
No se admite que el cliente elija un host TCP arbitrario. Nginx y `ExpectOrigin`
validan el origen público exacto del juego. La autenticación sigue a cargo de
Houdini. El servicio no publica puertos, corre sin privilegios y con filesystem
de solo lectura salvo un tmpfs para el mapa de destinos.

## Variables y ejemplo de producción

No se requieren nuevas variables obligatorias. `LEGACY_PLAYER=ruffle` es el
valor predeterminado incluso si falta; `LEGACY_PLAYER=flash` restaura el HTML
anterior. Las demás variables conservan su significado.

Ejemplo para **fusionar con el entorno existente**, sin sustituir las credenciales
ni el resto de la configuración:

```dotenv
WEB_PORT=8080
WEB_HOSTNAME=penguins.example.com
WEB_LEGACY_PLAY=https://old.penguins.example.com
WEB_LEGACY_MEDIA=https://legacy.penguins.example.com
WEB_VANILLA_PLAY=https://play.penguins.example.com
WEB_VANILLA_MEDIA=https://media.penguins.example.com
GAME_ADDRESS=game.penguins.example.com
GAME_LOGIN_PORT=6112
LEGACY_PLAYER=ruffle
```

`GAME_ADDRESS` debe ser un nombre público, sin esquema, ruta ni puerto. En modo
Ruffle solo identifica el socket para el mapa; no necesita resolver al backend.
Para Flash externo sí debe resolver al servidor con TCP accesible. No envíes
`127.0.0.1`, nombres Docker ni IP privadas como `GAME_ADDRESS` en producción.
La configuración local original de `.env` sigue siendo válida para desarrollo.

URLs sin barra final. También se admiten, por ejemplo,
`WEB_LEGACY_PLAY=https://penguins.example.com/game` y
`WEB_LEGACY_MEDIA=https://penguins.example.com/media`. En un mismo host, usa un
prefijo de medios no vacío y distinto del prefijo de juego; ambos no pueden
ocupar `/`. No reutilices ese host para los vhosts Vanilla existentes.
Los recursos de página conservan `/css`, `/scripts`, `/images` y los JSON de
`/<idioma>/web_service/`; enruta el host completo al servicio `web`.

Todos los medios deben usar HTTPS cuando el juego sea HTTPS. El cargador muestra
un error si se configura HTTP. Los medios en otro dominio permiten CORS solo
para el origen configurado del juego, sin comodines ni credenciales. No se
desactivan TLS, CORS ni las comprobaciones de origen.

## Despliegue desde GitHub en Dokploy

1. Usa la aplicación **Compose existente**, su directorio y su nombre de
   proyecto actuales. Selecciona la rama revisada (o `master` tras aprobar el PR).
   No cambies producción para probar esta rama sin revisar antes los cambios.
2. Conserva todo el entorno actual de Dokploy, especialmente credenciales,
   `.data` y `.redis`. Dokploy escribe el entorno en `.env`; `web` lo recibe
   mediante `env_file`, y el proxy recibe solo sus dos variables necesarias.
3. Inicializa los submódulos **antes** de que Compose evalúe los contextos de
   build y los bind mounts. Configura una vez el comando personalizado de
   despliegue de Dokploy para anteponer:

   ```sh
   sh scripts/prepare-sources.sh && <comando Compose actual de Dokploy>
   ```

   Sustituye el marcador por el comando real mostrado por tu instalación,
   preservando sus flags de proyecto, archivos generados y configuración de
   dominios. No pegues el marcador literalmente. El script usa los commits
   fijados por los gitlinks, nunca `--remote`, y falla antes de arrancar
   contenedores si faltan medios. Requiere Git y acceso HTTPS a GitHub y
   `git.solero.me`. Los medios incluyen historiales grandes: reserva disco y
   tiempo de descarga. Un Dockerfile no puede reparar por sí solo submódulos
   vacíos usados como contextos y bind mounts del host.
4. En **Domains**, añade cada host web al servicio `web`, **puerto de contenedor
   80**, con HTTPS/certificado de Dokploy. Los registros DNS A/AAAA deben apuntar
   al servidor. Traefik termina TLS y conserva `Host`, `Origin` y el upgrade
   WebSocket. No hace falta otro dominio ni certificado para WSS.
5. Para producción exclusivamente Ruffle, usa Compose >= 2.24.4 y añade
   `-f docker-compose.ruffle-only.yml` después del archivo base, conservando los
   demás argumentos que usa Dokploy. Comprueba **Preview Compose**: este overlay
   elimina publicaciones de puertos, incluidos DB, TCP de juego y web; Traefik
   accede a `web:80` por la red de Dokploy. Los volúmenes y puertos internos no
   cambian. No uses el overlay si necesitas clientes Flash/TCP externos o
   Snowflake externo. Si conservas el Compose base, administra explícitamente
   sus publicaciones anteriores con el firewall del servidor.
6. Despliega con build de las imágenes nuevas `web` y `websocket`. Dockerize
   regenera las configuraciones al arrancar. No hay comandos dentro de los
   contenedores tras cada despliegue. Comprueba el resultado con Preview Compose
   antes de usar el comando personalizado: el modo de inyección de dominios
   puede variar entre versiones de Dokploy.

No ejecutes `down -v`, no borres `.data`/`.redis` y no reinicialices PostgreSQL.
La persistencia sigue exactamente en los bind mounts anteriores. No se toca
directamente la configuración de producción con esta implementación.

## Verificación y diagnóstico

Comandos desde el checkout, usando los mismos flags de Compose/proyecto del
despliegue cuando corresponda:

```sh
docker compose config --quiet
docker compose -f docker-compose.yml -f docker-compose.ruffle-only.yml config --quiet
docker compose exec web nginx -t
docker compose logs --tail=100 web websocket houdini_login houdini_blizzard houdini_glaciar
```

En DevTools > Network, comprueba `ruffle.js`, un `core.ruffle.*.js`, `.wasm` con
MIME `application/wasm`, `boots.swf`, `load.swf`, `shell.swf`, `servers.xml` y
los medios. Deben responder 200, sin contenido mixto ni errores CORS. La regla
del primer cargador debe evitar solicitudes a `localhost` en un sitio público.

Pulsa Start. En la conexión WebSocket de login debe aparecer **101 Switching
Protocols**, con URL `wss://<host-juego>/__wand/ws/login`. Tras autenticarse y
seleccionar servidor, debe abrirse la ruta del mundo correspondiente. Comprueba
que se entra a una sala y se reciben actualizaciones antes de dar por validada
la integración completa. Prueba en Chrome, Firefox y Edge, varios idiomas,
redimensionado y audio tras un gesto del usuario.

| Síntoma | Comprobación |
| --- | --- |
| Error al iniciar Ruffle | Rutas `/__wand/ruffle/`, JS/WASM y logs web; rebuild de `web` |
| Pantalla vacía | Primer cargador reescrito, `base`, recursos SWF/JSON y consola Ruffle |
| CORS / contenido mixto | HTTPS en ambas URLs, origen exacto del juego y vhost de medios correcto |
| WS 403 | `Origin` debe coincidir con esquema/host/puerto de WEB_LEGACY_PLAY; no elimines la validación |
| WS 502 | Servicio websocket, resolución Docker y red `wand`; luego disponibilidad de Houdini |
| Missing WebSocket proxy | Host/puerto solicitados deben coincidir con GAME_ADDRESS, GAME_LOGIN_PORT y servers.xml |
| Login funciona, mundo falla | Ruta de mundo, ID/idioma/puerto en servers.xml y logs del Houdini correspondiente |
| Build sin Dockerfile o medios | Inicialización automática de submódulos y conectividad a sus repositorios |

`servers.xml` conserva su formato TCP para Flash. Si añades mundos o cambias sus
puertos/hosts, actualiza también el mapa de `web/ruffle/legacy.js`, los destinos
de `websocket/start.py` y la lista permitida de Nginx. El mapa no se deriva de
datos controlados por el navegador.

## Pruebas reproducibles y límites

```sh
node --test tests/legacy-player.test.cjs
pip install -r websocket/requirements.txt websocket-client==1.9.0
python -m unittest discover -s tests -p 'test_*.py' -v
sh tests/check-nginx.sh
```

Las primeras cuatro pruebas cubren las opciones Ruffle, los cinco sockets,
HTTPS/WSS, el prefijo de medios, la regla de arranque y errores visibles. Las
cinco pruebas Python verifican destinos, validación de configuración y un
Websockify real contra TCP de eco: mensajes binarios XML/XT con bytes nulos,
rechazo de origen y de token desconocido. **No prueban login de Houdini.**

`tests/check-nginx.sh` construye la imagen web y comprueba con Dockerize/Nginx
reales dominios distintos, prefijos de rutas, host compartido, rollback Flash y
reCAPTCHA; comprueba también rutas SWF/JS y MIME WASM. Usa contenedores
desechables sin montar datos. El workflow `ruffle-validation.yml` ejecuta estas
comprobaciones en los PR, junto con el build del proxy.

Prueba opcional de navegador con los medios fijados ya descargados:

```sh
npm --prefix web/ruffle ci --ignore-scripts --no-audit --no-fund
npm install --prefix .validation playwright@1.56.1
PLAYWRIGHT_BROWSERS_PATH=.validation/browsers node .validation/node_modules/playwright/cli.js install chromium
PLAYWRIGHT_BROWSERS_PATH=.validation/browsers node tests/browser-smoke.cjs
```

El servidor de esta prueba sirve los medios originales desde el gitlink, con un
HTML mínimo; no sustituye la comprobación del HTML generado, Nginx, TLS ni
Traefik. Guarda captura e informe en `.validation/`, ignorado por Git.

Estado de validación de esta implementación: ver [validation.md](validation.md).
Ruffle todavía tiene incompatibilidades AS2; pueden afectar minijuegos, audio,
LocalConnection, fuentes y ExternalInterface. El callback de reCAPTCHA se
conserva mediante `allowScriptAccess`, pero necesita validarse con claves reales.
No se garantiza compatibilidad completa por alcanzar la pantalla de inicio.

## Rollback

Para volver al HTML Flash, configura `LEGACY_PLAYER=flash` y redespliega `web`;
los usuarios necesitarán un reproductor compatible como antes. Si usaste el
overlay Ruffle, retíralo para restaurar los puertos TCP externos necesarios.
Para revertir toda la integración, vuelve al commit anterior mediante el flujo
de Git/Dokploy, con el mismo nombre de proyecto, directorio y montajes de datos.
No elimines volúmenes. Los datos y el esquema no han cambiado.

## Archivos y referencias

- `web/Dockerfile`, `web/.dockerignore`, `web/ruffle/*`: runtime fijado, cargador,
  aspecto y controles de tamaño/idioma; evita el script Flash `0.js` en Ruffle.
- `templates/legacy-media/play/**/index.html.template`: cuatro idiomas y modo Flash.
- `templates/sites/legacy.conf.template`: rutas, prefijos, CORS y upgrade WebSocket.
- `websocket/*`, `docker-compose.yml`: puente interno; overlay opcional de puertos.
- `.env`, `README.md`, `.gitignore`, `.gitattributes`, `scripts/prepare-sources.sh`:
  configuración, documentación, exclusiones y preparación de fuentes.
- `tests/*`, `.github/workflows/ruffle-validation.yml`: validaciones reproducibles.
- No se edita código de submódulos, SQL, servidores Houdini ni `servers.xml`.

Fuentes primarias consultadas:
[Wand #46](https://github.com/solero/wand/issues/46),
[Ruffle: sockets web](https://github.com/ruffle-rs/ruffle/wiki/Frequently-Asked-Questions-For-Users#how-can-i-connect-to-a-tcpsocket-or-xmlsocket-from-the-web),
[Ruffle: configuración](https://ruffle.rs/js-docs/master/interfaces/Config.URLLoadOptions.html),
[Websockify 0.13](https://github.com/novnc/websockify/tree/v0.13.0),
[Dokploy Compose](https://docs.dokploy.com/docs/core/docker-compose),
[Dominios Dokploy](https://docs.dokploy.com/docs/core/docker-compose/domains).
