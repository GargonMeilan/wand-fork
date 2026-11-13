# Validación local con Docker — 13 de noviembre de 2026

Se construyó y arrancó un stack aislado a partir de
`docker-compose.dokploy.yml`: PostgreSQL, Redis, login, cuatro mundos Houdini,
Dash, Nginx, Websockify y Snowflake. Se usaron credenciales de prueba, un puerto
publicado solo en `127.0.0.1` y volúmenes con un nombre aleatorio exclusivo.
No se accedió a Dokploy ni a los datos de ninguna instalación existente.

## Ampliación posterior: catálogo y panel unificado

Las comprobaciones por CLI de esta ampliación pasaron **34 pruebas Python y
12 JavaScript**, la verificación de integridad de los 377 archivos del catálogo
y una prueba de navegador headless con 16 eventos, 13 diseños de Town y cero
publicaciones al usar la vista previa. Se inspeccionaron las vistas reales de
Marvel y Halloween y el diseño adaptable a 390 px.

Tras un reinicio de Docker Desktop por CLI autorizado por el usuario, se
reconstruyeron y arrancaron los once servicios del stack aislado. La nueva
integración comprobó:

- Activación de los 16 paquetes y entrega de las 303 variantes y 76 referencias
  complementarias por Nginx, con hashes coincidentes.
- Persistencia al recrear Dash, restauración de JSON y ZIP, protección CSRF y
  acceso restringido al manager.
- Dos jugadores autenticados en mundos distintos, movimientos, desconexión y
  caducidad/recuperación del estado de un mundo.
- Vista previa autenticada, páginas de jugadores, ficha de jugador, revisión
  de nombres, contraseña y correo con navegación común y `lang="en"`.
- Partida real con Ruffle: login, entrada en Blizzard, Town decorado de Marvel
  y carga de la música 325. Sin errores JavaScript ni recursos inesperados
  fallidos; se mantienen los errores heredados enumerados más abajo.
- Cinco configuraciones de Nginx: dominios separados, subrutas, dominio
  compartido, Flash y CAPTCHA.

Esto valida los recursos de los paquetes y la partida descrita. No certifica
compras de catálogos históricos, recorridos por todas las salas ni poderes,
transformaciones, misiones o recompensas de cada evento. No se ha desplegado
en Dokploy.

## Integración comprobada anteriormente

La regresión terminó con **28 pruebas Python y 12 JavaScript correctas**,
además de las comprobaciones Docker y de navegador enumeradas a continuación.

- Arranque de los once servicios. Login y mundos responden al handshake real.
- Acceso de moderador al manager; rechazo de cuentas sin permiso y peticiones
  sin sesión. CSS y JavaScript del panel responden correctamente.
- Cambio de música por sala, subida de SWF, entrega de la variante por su hash,
  aplicación de paquetes y rechazo de formularios con token incorrecto.
- Configuración efectiva del cliente en JSON, JSONP y `game_configs.bin`.
  Se verificó que modificar las salas conserva los demás miembros del ZIP y
  restaurar todo recupera el ZIP original byte a byte.
- Persistencia de selecciones y recursos al recrear Dash.
- Dos sesiones autenticadas a través de Nginx/Websockify/Houdini en Blizzard y
  Glaciar; aparición en el manager, movimientos entre salas y retirada al salir.
- Caducidad del estado al detener Yeti; diferencia entre cero jugadores y sin
  datos recientes; recuperación al arrancarlo de nuevo.
- Chromium con los paneles reales y el cliente Vanilla/Ruffle: login, selección
  de Blizzard y entrada visual a una sala. Se seleccionó desde el manager una
  variante subida de la ciudad y música `9`; el cliente solicitó ambas y recibió
  HTTP 200. El SWF de muestra es una copia de la ciudad original: se prueba el
  mecanismo de selección y entrega, no un evento artístico externo completo.
- Los cinco escenarios de Nginx existentes: dominios separados, prefijos de
  ruta, host compartido, Flash y reCAPTCHA; `nginx -t`, recursos y MIME WASM.
- Persistencia de una fila PostgreSQL y una clave Redis al recrear contenedores.
- Arranque en frío, reinicio coordinado de los cinco Houdini tras recrear una
  base de datos temporal y arranque de mundos detenidos con un solo Compose up.

## Correcciones encontradas durante las pruebas

1. Sanic 21.12 añadía una barra a la ruta estática y registraba `//archivo`.
   Se corrigieron los recursos de la ampliación y se registró una ruta normal
   para los recursos del manager heredado, sin editar el submódulo.
2. El login heredado intentaba ejecutar reCAPTCHA incluso sin claves. La
   plantilla de acceso de la ampliación solo lo carga cuando está configurado;
   conserva la validación del backend y espera el token cuando corresponde.
3. El cliente Flash consume un ZIP llamado `game_configs.bin`; los JSON sueltos
   no bastaban para cambiar su música y decoraciones. Ahora también se sirve
   ese paquete con las selecciones aplicadas, conservando su configuración base.
4. Se añadió disponibilidad HTTP a Dash y Nginx espera `service_healthy`, para
   evitar arrancar el proxy antes de que termine de iniciarse el backend.

## Límites observados

La entrada a la sala fue correcta, pero el cliente original aún intenta tres
servicios que no quedaron validados ni implementados por esta ampliación:

| Petición | Resultado local |
| --- | --- |
| `/social/autocomplete/v2/search/clientRules` | Preflight sin respuesta válida; bloqueo CORS |
| `/play//web_service/activate_player.php` | HTTP 404; las cuentas de prueba ya estaban activadas |
| `/web-service/membership` | La URL histórica omitió el puerto local no estándar y falló la conexión |

Estos fallos no impidieron la sesión ni las comprobaciones nuevas. No se han
ocultado devolviendo respuestas ficticias. No se afirma que toda activación,
membresía, autocompletado, minijuegos o eventos históricos funcionen. Snowflake
arrancó, pero no se jugó una partida completa de Card-Jitsu Nieve.

La prueba es HTTP local. HTTPS, certificados, Traefik y los dominios reales de
Dokploy requieren una comprobación posterior al despliegue. Esta ejecución no
publicó cambios ni realizó ese despliegue.

## Repetir la prueba en Windows

Con Docker Desktop en ejecución, los submódulos presentes, las dependencias de
`websocket/requirements.txt`, `websocket-client==1.9.0` y el Playwright/Chromium
local descrito en las otras guías:

```sh
python tests/local-stack.py prepare
python tests/local-stack.py up
python tests/check-manager-live.py
node tests/local-browser-smoke.cjs
python tests/check-nginx-local.py
python tests/check-data-persistence.py
python tests/check-backend-startup.py
python tests/local-stack.py down
```

`prepare` se ejecuta una vez: la configuración se guarda en
`.validation/local-stack/compose.json` y se puede volver a usar con `up`.
`down` elimina solo los contenedores, red y volúmenes del proyecto de prueba
registrado. Las pruebas que usan sus cuentas o modifican las salas deben
ejecutarse **en secuencia**, no simultáneamente.

Los informes y capturas están en `.validation/local-stack/` (ignorados por Git):
`integration-results.json`, `browser-report.json`, `manager-online.png`,
`manager-world.png`, `vanilla-auth.png` y `vanilla-room.png`.
