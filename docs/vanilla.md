# Vanilla / AS3 con Ruffle

Vanilla usa el mismo runtime local Ruffle 0.7.1 y el mismo puente Websockify que
Legacy. No hay nuevos puertos publicados ni cambios en Houdini, Dash o SQL.

## Configuración en Dokploy

```dotenv
VANILLA_PLAYER=ruffle
WEB_VANILLA_PLAY=https://play.tudominio.com
WEB_VANILLA_MEDIA=https://media.tudominio.com
```

`VANILLA_PLAYER` usa Ruffle por defecto si está ausente. `flash` restaura la
incrustación anterior. Mantén las URLs Legacy existentes; el proxy permite los
dos orígenes exactos. Cada dominio se configura en Dokploy hacia `web:80` con
HTTPS. Reconstruye **web y websocket** al desplegar estos cambios: el proxy debe
recibir también `WEB_VANILLA_PLAY`. Los dominios pueden intercambiarse según las
variables, sin depender de que un host se llame `old` o `play`.

## Arranque y compatibilidad

La página original usa SWFObject para crear `club_penguin.swf`. El adaptador
`web/ruffle/vanilla.js` reemplaza su comprobación del plugin y su método de
incrustación antes del arranque de la página; crea un reproductor Ruffle con los
FlashVars, ID, tamaño y callbacks originales, salvo la decodificación de
`queryString` de Nieve descrita abajo. Conserva los scripts, estilos y
ExternalInterface originales. No carga `boots.swf`, que pertenece a Legacy.

Se mantienen los parámetros originales `play`, `client`, `content`, `games`,
`connectionID`, `lang`, `phrasechat`, versiones e `isAS3WebServicesOn`. El cliente
lee `environment_data.xml`, los módulos de mundo/shell y `servers.xml`. Las
conexiones usan los mismos cinco sockets Houdini; cada vhost Nginx acepta solo
su propio origen y Websockify permite explícitamente ambos.

El servidor de medios permite CORS solo para el origen Vanilla configurado.
Se atiende localmente con 204 el endpoint histórico de telemetría Disney
`/datatech/serverlog/v1/json`; no representa una API del juego. Los enlaces de
registro de los cuatro idiomas se dirigen al Dash local, evitando los dominios
históricos externos que permanecían en algunas plantillas.

Card-Jitsu Snow usa otra incrustación y protocolo. Su reproductor recibe una
entrada adicional en `socketProxy` con `SNOWFLAKE_HOST` y `SNOWFLAKE_PORT` (los
mismos valores que anuncia Dash). La ruta WSS `/__wand/ws/snow` del host Vanilla
conecta exclusivamente con `snowflake:SNOWFLAKE_PORT` dentro de Docker; no hace
falta publicar ese puerto. El servicio websocket recibe ahora también el puerto
configurado. Es necesario reconstruir web/websocket y regenerar las páginas al
desplegar. No se ha validado una partida completa con Ruffle.
Tampoco se garantiza el funcionamiento de todos los minijuegos, amigos,
activación, reCAPTCHA, módulos AS3 o puentes AS2/AS3 solo por llegar al login.

### Rechazo al entrar en Nieve

El JavaScript original codifica `queryString` con `encodeURIComponent` para
insertarlo en la cadena `flashvars` de SWFObject. Flash decodificaba esa cadena
una vez; Ruffle conserva literalmente los valores de su objeto `parameters`.
Sin adaptar ese paso, el SWF enviaba
`/place_context "snow_lobby" battleMode%3D0%26base_asset_url%3D...` y Snowflake
no encontraba `battleMode` ni `base_asset_url`, devolvía `user code 900` y cerraba
la conexión antes del login. El manejador de errores del cliente producía a su
vez `Error #1009` y dejaba un panel «Already Logged In» que no respondía.

El adaptador decodifica una vez solo `queryString` de `mpProduct=cjsnow`, sin
modificar el objeto original de la página ni los FlashVars del cliente principal.
Se contrastaron ambos formatos con el servidor usando únicamente contexto y
versión, sin autenticar cuentas: el codificado fue rechazado y el normal recibió
`S_VERSION`. Una prueba con el SWF real reproduce el rechazo antes del cambio y
verifica el paquete correcto después. Esto no verifica una partida completa ni
resuelve por sí solo el fallo comunicado en Card-Jitsu Agua.

## Registro de cuentas Legacy

Se corrigió el proxy `/create_account/create_account.php` para llegar a la ruta
canónica `/create/legacy/` de Dash. También se sirve en el host de medios, ya
que el SWF puede resolver allí la petición. Se conserva el POST y su cuerpo,
sin desactivar validaciones de reglas, términos o reCAPTCHA.

La prueba de integración usa un backend HTTP de comprobación y verifica que
ambos hosts transmiten el acuerdo a la ruta correcta con todos los campos.
No crea cuentas ni sustituye una prueba real con Dash y PostgreSQL. Si el error
original persiste, hay que consultar su respuesta HTTP y los logs de Dash; no
se ha confirmado la causa exacta en la instalación del usuario.

## Validación

```sh
node --test tests/legacy-player.test.cjs tests/vanilla-player.test.cjs
python -m unittest discover -s tests -p 'test_*.py' -v
sh tests/check-nginx.sh
python tests/check-proxy-chain.py
```

Hay siete pruebas Node y siete Python. Las pruebas Docker comprueban ambos
vhosts, rutas, plantillas e incrustación Flash/Ruffle; la cadena de proxies
cubre ambos clientes, el destino Snowflake y el POST Legacy. La prueba de
Snowflake en esta cadena usa un servidor TCP de eco; no valida el protocolo de
una partida. `tests/snow-browser-smoke.cjs` usa Chromium, Ruffle y los medios
reales de Nieve contra un WebSocket de prueba; comprueba el formato de
`place_context` y la ausencia del error de ejecución antes de autenticar.
Requiere Playwright 1.56.1 instalado en `.validation` y su Chromium, igual que
la prueba Vanilla. Ejecutar con
`PLAYWRIGHT_BROWSERS_PATH=.validation/browsers node tests/snow-browser-smoke.cjs`.
No conecta con el servidor real y no crea cuentas; guarda captura e informe en
`.validation/snow-transport.png` y `.validation/snow-transport-report.json`.
El fallo de Agua sigue pendiente de diagnóstico.
`tests/vanilla-browser-smoke.cjs` sirve
el HTML original y los medios Vanilla desde el checkout, con una sustitución
de variables para la prueba; las plantillas Go se validan por separado con
Dockerize real. Requiere los mismos Playwright/Chromium y runtime de la prueba
Legacy. Guarda `.validation/vanilla-boot.png` e informe JSON.

El arranque local llegó visualmente al formulario de login. **Queda pendiente
autenticar una cuenta, seleccionar servidor y entrar a una sala**, además de la
verificación de HTTPS/WSS real en Dokploy y Firefox/Edge. No se ha desplegado
ni modificado la instalación de producción.
