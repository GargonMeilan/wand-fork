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

Usa **`docker-compose.dokploy.yml` como Compose Path**. Es un archivo completo,
generado desde el Compose base, sin publicaciones de puertos ni tags `!reset`.
Dokploy lee ese mismo archivo al añadir dominios y redes; no necesitas overlays
ni un comando personalizado. `docker-compose.ruffle-only.yml` queda como opción
para Compose directo fuera de este flujo.

1. Conserva la aplicación Compose existente, su nombre de proyecto y sus datos.
   En GitHub/Git selecciona `feature/ruffle-support` (o master tras el merge) y
   activa **Enable Submodules**. Esa opción hace el clon recursivo antes del
   build; requiere acceso HTTPS a GitHub y `git.solero.me`. Los historiales de
   medios ocupan varios GB. Usa modo **Docker Compose**, no Stack/Swarm.
2. Configura **Compose Path: `docker-compose.dokploy.yml`**. Restablece Command
   al valor predeterminado de Dokploy. No pongas `sh scripts/prepare-sources.sh`
   en ese campo: Dokploy antepone `docker` y no es un hook de shell. El script
   queda disponible para checkouts gestionados fuera de Dokploy.
3. Conserva todo el entorno actual, incluidas credenciales. Activa la creación
   de `.env` de Dokploy y fusiona las URLs públicas HTTPS del ejemplo anterior.
   Añade `POSTGRES_DATA_PATH` y `REDIS_DATA_PATH` con las **rutas existentes de
   datos persistentes en el host**, fuera del directorio Git `code/`. Deben ser
   directorios absolutos existentes. El Compose exige ambas variables y no crea
   directorios vacíos si hay un error en la ruta.
4. **Antes de redesplegar**, inspecciona Mounts de los contenedores actuales o
   ejecuta en el servidor estos comandos de solo lectura:

   ```sh
   docker inspect --format '{{json .Mounts}}' NOMBRE_CONTENEDOR_DB
   docker inspect --format '{{json .Mounts}}' NOMBRE_CONTENEDOR_REDIS
   ```

   Identifica `Source` del montaje que apunta a `/var/lib/postgresql/data` y
   `/data`. No introduzcas una ruta nueva vacía para un despliegue existente.
   Si los datos actuales están dentro de `code/`, **hace falta migrarlos fuera
   del checkout antes de redesplegar**, con los servicios detenidos y backup:
   el proveedor Git de Dokploy puede borrar y reclonar `code/`. Esta PR no migra
   datos automáticamente. Si usas volúmenes Docker o montajes gestionados por
   Dokploy, conserva esos mismos montajes en ambos destinos y adapta la
   configuración de almacenamiento a ese tipo; no cambies a bind mounts vacíos.
5. En **Domains**, añade cada host al servicio **web**, puerto de contenedor
   **80**, ruta `/`, sin Strip Path ni Internal Path, con certificado HTTPS.
   Enruta los hosts completos de juego y medios; también los Vanilla si los
   usas. DNS A/AAAA debe apuntar al servidor. No publiques `websocket:8080` ni los
   puertos de Houdini. WSS usa el mismo host y certificado del juego.
6. Comprueba **Preview Compose**: `web` debe seguir en la red interna `wand`
   además de la red de Traefik que añade Dokploy; los backends deben conservar
   `wand`. El archivo añade aliases DNS estables para que nombres como
   `websocket`, `db` y `houdini_login` sigan resolviendo si Dokploy renombra
   servicios. No hace falta conectar las bases de datos a la red de Traefik.
   No cambies el aislamiento ni randomización de la aplicación existente como
   parte de este despliegue; revisa el resultado de Preview.
7. Despliega con build. Dockerize regenera configuraciones y HTML al arrancar.
   No hay comandos dentro de contenedores tras cada despliegue. Comprueba los
   logs y el recorrido completo de login/selección/sala como se indica abajo.

Ejemplo de las variables adicionales, **solo para una instalación cuyos datos
ya estén en esos directorios**:

```dotenv
POSTGRES_DATA_PATH=/srv/penguins/postgres
REDIS_DATA_PATH=/srv/penguins/redis
```

No ejecutes `down -v`, no borres datos y no reinicialices PostgreSQL. Esta revisión
no modifica producción ni mueve los datos de la aplicación existente.

El archivo específico se mantiene con:

```sh
pip install PyYAML==6.0.3
python scripts/generate-dokploy-compose.py
```

CI comprueba que el generado coincide con el base. El comando de despliegue
predeterminado de Dokploy aplica únicamente el archivo seleccionado.

## Verificación y diagnóstico

Comandos desde el checkout, usando los mismos flags de Compose/proyecto del
despliegue cuando corresponda:

```sh
docker compose config --quiet
docker compose -f docker-compose.dokploy.yml config --quiet
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
python tests/check-proxy-chain.py
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
`check-proxy-chain.py` usa esas imágenes para comprobar además la cadena real
Nginx -> Websockify -> TCP en los cinco destinos y el rechazo de origen, sin
servicios Houdini ni datos persistentes.

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
los usuarios necesitarán un reproductor compatible como antes. El archivo Dokploy no publica puertos TCP: para clientes Flash externos tendrás
que restaurar explícitamente las publicaciones anteriores o el Compose base.
Para revertir toda la integración, vuelve al commit anterior mediante el flujo
de Git/Dokploy, con el mismo nombre de proyecto, directorio y montajes de datos.
No elimines volúmenes. Los datos y el esquema no han cambiado.
Si vuelves al Compose anterior, conserva los montajes persistentes que uses en
producción; no vuelvas por accidente a los directorios relativos del checkout.

## Archivos y referencias

- `web/Dockerfile`, `web/.dockerignore`, `web/ruffle/*`: runtime fijado, cargador,
  aspecto y controles de tamaño/idioma; evita el script Flash `0.js` en Ruffle.
- `templates/legacy-media/play/**/index.html.template`: cuatro idiomas y modo Flash.
- `templates/sites/legacy.conf.template`: rutas, prefijos, CORS y upgrade WebSocket.
- `websocket/*`, `docker-compose.yml`: puente interno; overlay opcional de puertos.
- `.env`, `README.md`, `.gitignore`, `.gitattributes`, `scripts/prepare-sources.sh`:
  configuración, documentación, exclusiones y preparación de fuentes.
- `docker-compose.dokploy.yml`, `scripts/generate-dokploy-compose.py`: archivo
  de despliegue único, aliases internos y almacenamiento persistente explícito.
- `tests/*`, `.github/workflows/ruffle-validation.yml`: validaciones reproducibles.
- No se edita código de submódulos, SQL, servidores Houdini ni `servers.xml`.

Fuentes primarias consultadas:
[Wand #46](https://github.com/solero/wand/issues/46),
[Ruffle: sockets web](https://github.com/ruffle-rs/ruffle/wiki/Frequently-Asked-Questions-For-Users#how-can-i-connect-to-a-tcpsocket-or-xmlsocket-from-the-web),
[Ruffle: configuración](https://ruffle.rs/js-docs/master/interfaces/Config.URLLoadOptions.html),
[Websockify 0.13](https://github.com/novnc/websockify/tree/v0.13.0),
[Dokploy Compose](https://docs.dokploy.com/docs/core/docker-compose),
[Dominios Dokploy](https://docs.dokploy.com/docs/core/docker-compose/domains).

Revisión de Dokploy: [submódulos GitHub](https://github.com/Dokploy/dokploy/blob/canary/packages/server/src/utils/providers/github.ts), [Command](https://docs.dokploy.com/docs/core/docker-compose#advanced).
