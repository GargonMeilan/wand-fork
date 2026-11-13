# Usuarios conectados

El enlace **Usuarios conectados** de `/manager` abre `/manager/online`.
Requiere una cuenta moderadora; la página y su API `/manager/online/data`
comprueban la sesión y el permiso en cada consulta y no se guardan en caché.

La tabla muestra usuario e ID, servidor, sala, tipo de cliente (Legacy o
Vanilla) y tiempo conectado. En los iglús y patios aparece el ID del propietario.
Se puede filtrar por servidor y buscar por nombre, ID o localización. Se
actualiza automáticamente cada cinco segundos y tiene un botón de actualización.

## Instalación

Usa el Compose actualizado y recrea **dash** y los cuatro mundos
**houdini_blizzard, houdini_glaciar, houdini_avalanche y houdini_yeti**. No es
necesario modificar los submódulos ni la base de datos. No se ha ejecutado este
despliegue automáticamente.

Cada mundo usa `world_manager/houdini_boot.py` para incorporar una tarea de
monitorización a su arranque original. Publica una instantánea en Redis cada
cinco segundos, con una caducidad de veinte segundos. No se cambian los
paquetes del juego ni se escribe en sus colecciones de población existentes.

Los errores de publicación se registran y se reintentan sin detener el mundo.
Si el proceso termina de golpe, la instantánea caduca sola. El panel distingue
un servidor con **cero jugadores** de otro **sin datos recientes**. Si la API
falla, elimina el listado anterior para no presentarlo como actualizado.

La lista incluye los cuatro mundos actuales de Compose (IDs 3100–3103). Si se
añaden mundos, actualiza `SERVERS` en `world_manager/presence.py` e instala el
mismo arranque en ellos. Snowflake/Card-Jitsu Nieve no publica su ubicación
interna aquí; durante esas partidas la vista solo dispone de la ubicación que
mantenga Houdini. No se publican IP, correos, claves de acceso ni contraseñas.

Las ubicaciones son instantáneas con un retraso habitual de hasta diez segundos
(publicación más consulta), no seguimiento de movimientos en cada paquete.
Los datos del monitor no añaden un historial persistente de ubicaciones.

## Validación

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/online-panel.test.cjs
```

Las pruebas cubren salas, cambios de ubicación, iglús, patios, minijuegos,
desconexiones, publicaciones con caducidad, caídas de Redis, cancelación de la
tarea, permisos de la API, filtros y eliminación de datos obsoletos de la
pantalla. La [validación local con Docker](local-validation.md) comprobó dos
sesiones reales en mundos distintos, sus movimientos y desconexiones y la
caducidad y recuperación de un mundo detenido.
