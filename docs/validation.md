# Validación de Ruffle — 11 de noviembre de 2026

## Persistencia y redespliegue coordinado

Se confirmó Auto Deploy activo y una instalación de prueba sin datos importantes
que conservar. El usuario lo ha desactivado antes de publicar la corrección de
almacenamiento. Ambos Compose usan ahora volúmenes Docker estables, fuera de
`code/`, en lugar de `./.data` y `./.redis`. Esto inicia una base nueva en esos
volúmenes; no migra datos ni elimina almacenamiento anterior.

El [workflow de coordinación](https://github.com/GargonMeilan/wand-fork/actions/runs/43093354638)
pasó con PostgreSQL, Redis y los cinco Houdini reales: arranque en frío, respuesta
de protocolo apiOK, reinicio automático tras recrear la DB de prueba y arranque
de los cuatro mundos detenidos con un único Compose up. Los datos de esa prueba
eran temporales y no se usó la instalación de producción.

Se añade una comprobación separada de persistencia con volúmenes desechables
exclusivos del test: una fila SQL y una clave Redis deben sobrevivir a
`--force-recreate`. Consultar el workflow de la corrección de persistencia.

## Redis: comprobación de salud

Se corrigió el healthcheck heredado `CMD-SHELL, redis-cli, ping` a la forma exec
`CMD, redis-cli, ping`. El shell anterior interpretaba `ping` como argumento del
shell, sin pasarlo a redis-cli. El log de despliegue mostraba imágenes
construidas y Redis unhealthy bloqueando el arranque.

`tests/check-redis-health.py` verifica la imagen, comando y healthcheck reales
en un servicio aislado con `/data` en tmpfs, sin montar datos del proyecto ni
publicar puertos. Comprueba que pasa a healthy y responde PONG.

## Ampliación Vanilla / AS3

- Seis pruebas Node y seis Python correctas, incluidos FlashVars/callback de
  Vanilla, HTTPS/WSS y allowlist explícito de ambos clientes.
- Chromium 141 con el HTML, scripts, CSS y SWF originales de Vanilla: formulario
  de login visible; `club_penguin.swf`, `environment_data.xml`, world, shell,
  módulos AS2 y `servers.xml` cargados, sin recursos fallidos ni errores en la
  prueba final. Captura e informe en `.validation/vanilla-*` (ignorados por Git).
- Corrección del proxy Legacy de registro en host de juego y medios hacia la
  ruta canónica de Dash. Se añade a la prueba Docker la conservación del POST
  y su cuerpo. Falta confirmar el error original en producción con sus logs.
- Nginx y el recorrido de proxies ampliados están preparados para ambos
  clientes y se ejecutan en el workflow de esta ampliación.
- Pendientes login real, selección de servidor y sala. No se ha modificado la
  instalación de producción. Detalles en [vanilla.md](vanilla.md).

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

El [segundo workflow](https://github.com/GargonMeilan/wand-fork/actions/runs/43049718521)
también terminó **correctamente**, incluida `tests/check-proxy-chain.py`: cadena
completa Nginx -> Websockify -> TCP con los cinco destinos, mensajes binarios y
rechazo de origen, bajo las restricciones del contenedor de producción y sin
base de datos.

`scripts/prepare-sources.sh` se ejecutó correctamente con los cinco submódulos
en sus commits fijados. El checkout local de Vanilla requirió recuperar un fallo
de permisos de Git en Windows; no se cambió su URL, commit ni código versionado.

## Pendiente de integración real

- Build y arranque del stack completo con sus servicios y base de datos.
- Nginx generado y tráfico de WebSocket a través de Traefik/Dokploy con TLS real.
- Login de una cuenta, elección de servidor y entrada a una sala.
- Firefox y Edge, idiomas adicionales, registro/activación y reCAPTCHA real.
- Minijuegos, sonido, LocalConnection entre instancias y demás compatibilidad AS2.

## Revisión específica de despliegue Dokploy

Se retiraron también las diez secciones `ports` del `docker-compose.yml`
principal para evitar colisiones incluso si Dokploy selecciona ese archivo.
Se trasladaron sin cambiar sus valores a `docker-compose.direct.yml`, opcional
para acceso directo. Ambos modos pasan `docker compose config --quiet`; las
instrucciones e instalador de uso directo incluyen ahora ese archivo opcional.

Se añadió `docker-compose.dokploy.yml`, generado desde el base y comprobado en
CI para evitar divergencias. Configuración Compose validada: ningún puerto
publicado, aliases internos estables, sin links y montajes de datos explícitos
con `create_host_path: false`. La configuración falla si faltan las variables
de directorios persistentes, antes de crear contenedores.

Se corrigió la guía: activar **Enable Submodules** en el proveedor Git de
Dokploy y usar su comando predeterminado. Command no es un hook de shell.
El checkout Git puede borrarse al redesplegar; los directorios de PostgreSQL y
Redis deben verificarse fuera de ese checkout. No se inspeccionó ni migró el
almacenamiento real del servidor de producción.

El [workflow de revisión Dokploy](https://github.com/GargonMeilan/wand-fork/actions/runs/43051909194)
terminó **correctamente**, incluidos el archivo generado, su sintaxis Compose,
las pruebas anteriores y los builds de **Houdini, Dash y Snowflake**. Se
comprobó además localmente que la ausencia de cada variable de persistencia
bloquea por separado la configuración. Esto no implica que se haya arrancado
el stack con datos reales ni inspeccionado la instalación del usuario.

No se ha cambiado el despliegue de producción, ni se han borrado volúmenes o
alterado datos. La prueba de navegador es una prueba de arranque del cliente;
la prueba de eco verifica transporte. Ninguna demuestra por sí sola que se
puede completar una sesión de juego.
