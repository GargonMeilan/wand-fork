# Decoración y música desde /manager

Actualización: la [biblioteca preinstalada](event-catalogue.md) incluye ahora
decoraciones históricas reales, catálogos y vistas previas. La subida manual es
opcional; los paquetes incluidos ya aparecen al instalar la ampliación.

La ampliación está en `world_manager/`, fuera de los submódulos. Añade el enlace
**Rooms & events** al panel de Dash y la página `/manager/world`. Esta ampliación gestiona **Vanilla/AS3**. Legacy conserva sus recursos originales.

## Primer despliegue

Despliega el Compose actualizado y reconstruye **web**. Recrea también **dash**:
su arranque registra la ampliación y monta los medios Vanilla en modo lectura y
el nuevo volumen persistente `world_data`. Conserva el mismo nombre de proyecto
Compose. Para Dokploy usa `docker-compose.dokploy.yml`, generado desde el Compose
principal con `python scripts/generate-dokploy-compose.py` (PyYAML 6.0.3).

Este despliegue inicial sí requiere recrear servicios. Después, seleccionar
variantes, subir salas, aplicar paquetes y restaurar la configuración se hace
durante la ejecución, sin compilaciones ni reinicios.

Accede con una cuenta moderadora. La autorización se comprueba en cada petición;
las escrituras necesitan el token de sesión del formulario. Los cambios no
modifican los SWF ni los JSON originales del checkout.

## Cambiar una sala

1. Selecciona la sala y pulsa **Open**.
2. Elige una variante y un ID de música disponible, o `0` para silencio.
3. Pulsa **Apply room design**.
4. Para volver al estado del repositorio, pulsa **Restore room**.

Las variantes históricas ya están incluidas. Para diseños propios, abre
**Upload custom designs** y asigna al SWF un nombre, un paquete y su música. Se admiten SWF FWS/CWS de hasta 16 MiB, con un tamaño descomprimido
máximo de 64 MiB. La subida solo lo registra: no lo publica hasta pulsar aplicar.
Las músicas se seleccionan entre los archivos numerados ya presentes en
`vanilla-media/media/play/v2/content/global/music/`. Esta versión no importa
música nueva ni identifica sus títulos; los números son los IDs originales.

Una variante debe corresponder a esa sala y ser compatible con el cliente:
salidas, coordenadas, símbolos y dependencias deben coincidir. Validar la
cabecera del archivo no certifica sus gráficos ni su comportamiento. La
decoración está integrada en el SWF; el panel no edita árboles o edificios
individualmente. El botón **Load preview** reproduce una vista visual con Ruffle sin publicar cambios.

## Paquetes de decoración

Los 16 paquetes preinstalados se activan desde **Event library**. Para crear
un paquete propio, sube cada sala usando el mismo nombre de paquete y su música. El paquete se podrá aplicar si contiene exactamente una variante por
sala. Si hay duplicados, vuelve a subir una de esas variantes con un nombre de
paquete distinto. Al aplicar se sustituye **todo** el conjunto de cambios de
salas anterior mediante una única transacción; las salas no incluidas vuelven
al original. **Restore all original rooms & resources** vacía las selecciones.

Los paquetes históricos sirven también los catálogos y recursos complementarios
listados en su ficha. No activan por sí mismos objetivos, poderes,
transformaciones ni recompensas exclusivas. Esas mecánicas dependen del
módulo Flash de la fiesta, de sus recursos auxiliares y del protocolo del
servidor. Solo se sustituyen los recursos enumerados en el paquete; las fechas y opciones
generales del cliente no se cambian automáticamente. Un evento completo debe implementar y verificar
también esas partes antes de poder presentarse como tal.

## Cuándo ven el cambio los jugadores

El panel publica la configuración inmediatamente. El cliente Flash conserva
su configuración desde el arranque; no hay una API de recarga expuesta al
adaptador actual. Además del JSON/JSONP que usa la página, el cliente carga
`game_configs.bin`: es un ZIP con `rooms.json` y otros archivos. El manager
aplica los cambios también a ese ZIP. Su contenido original puede tener músicas
distintas de los JSON sueltos; el panel toma el ZIP como referencia cuando existe.

Las páginas Vanilla consultan una revisión pública cada 15 segundos. Cuando
cambia, muestran **Recargar juego** o **Más tarde**. Recargar vuelve al login;
no se expulsa automáticamente a los jugadores. Entrar y salir de una sala con
el cliente anterior **no garantiza** recoger los cambios, porque conserva su
configuración y sus objetos Flash en memoria.

Nginx deriva las configuraciones JSON, JSONP, ZIP y los SWF de sala a Dash. La variante
se sirve en la URL original del SWF con parámetros de versión y un hash del
contenido; así mantiene su directorio base para dependencias relativas. Las
configuraciones llevan `Cache-Control: no-store`, y las subidas tienen URLs
inmutables. El mismo cambio se refleja en los idiomas configurados, manteniendo
las demás propiedades de cada sala. Los demás miembros del ZIP se conservan
byte a byte. Al restaurar todo se devuelve el ZIP original sin modificar.

## Persistencia y concurrencia

`world_data` contiene `world.sqlite3` y `assets/`. El volumen usa el nombre
`${COMPOSE_PROJECT_NAME:-wand}_world_data`. Copia **todo** el volumen para hacer
backup y conserva el nombre del proyecto en los despliegues. No borres este
volumen para actualizar la aplicación.

Las publicaciones son transaccionales y generan una revisión y un registro
con el nombre del moderador. Si otro moderador publicó mientras tenías abierto
el formulario, se rechaza la edición antigua y se pide recargar el panel.
Los archivos subidos se guardan por hash; restaurar una sala no los elimina.

Para ejecutar Dash fuera de Compose, establece `WAND_VANILLA_ROOT` con la ruta
del submódulo Vanilla y `WAND_WORLD_STATE` con un directorio persistente, añade
el repositorio al `PYTHONPATH`, entra en `dash/` y arranca
`python ../world_manager/boot.py -c config.py`.

## Investigación de eventos incluidos

Ejecuta `python scripts/audit-events.py` para actualizar
`world_manager/event-audit.json`. Este inventario técnico es independiente de la
biblioteca recuperada de 2012 que muestra el panel. La auditoría
lee los alias históricos de `paths.json`, las clases incrustadas en los SWF de
salas y cliente, y las definiciones de objetos de Marvel. No ejecuta los SWF.
`python scripts/audit-events.py --check` detecta si el inventario quedó obsoleto.

En este checkout se examinaron **169 SWF** y se encontraron **27 grupos** de
referencias/módulos. Los grupos no son 27 eventos completos ni necesariamente
27 fiestas distintas: una misma fiesta aparece en varias ediciones o como
alias histórico y como módulo compilado.

Entre las evidencias encontradas:

| Evento o módulo | Qué hay | Qué falta acreditar para activarlo completo |
| --- | --- | --- |
| Marvel / Superhéroes | Alias de 2012, clases de 2012/2013 y objetos como Iron Man, Spider-Man y Capitán América | Verificar módulo de fiesta, poderes, objetivos y compras; el paquete de 2012 ya incluye salas y catálogos |
| Music Jam | Clases de 2014 en `party1` a `party6`, entre otros recursos, y alias de 2012 | Conciertos, horarios, servicios de actuaciones, cookie y recompensas |
| Frozen | Clases en ocho SWF de salas/cliente | Conjunto de escenarios, transformaciones, congelación, tareas y recompensas |
| Muppets | Clases en varios SWF, incluidos `cove` y `dock` | Actuaciones, dependencias, tareas y protocolo específico |
| Medieval | Alias de 2012 y clases de 2013 en `schoolsolo.swf` | Verificar módulo, transformaciones/objetos, tareas y recompensas; salas de 2012 recuperadas |
| Prehistoria | Clases en siete SWF | Identificación de salas, excavaciones, dinosaurios, huevos y recompensas |
| Teen Beach Movie | Clases en `party10.swf` | Conciertos, dependencias y protocolo de esa edición |
| EPF / Operación Salsa Picante | Módulos y clases EPF de 2013 | Confirmar cada edición, navegación y objetivos con el servidor |
| Navidad / Coins for Change | Alias de transformaciones y clases CFC | Tren, donaciones y conjunto de recursos de una misma edición |
| Halloween | Alias de fantasmas y clases históricas | Verificar transformaciones y objetivos; salas y recursos de 2012 recuperados |
| Escuela, SoundStudio y fiestas automatizadas | Módulos incrustados en determinados SWF | Ajustes, dependencias, servicios y flujo completo |
| Rockhopper, puffles, bromas, Día de la Tierra y misiones PSA | Alias de configuración | Comprobar qué archivo real ocupa cada ruta y completar la edición |

Los alias apuntan a nombres reutilizados como `party.swf`, `party2.swf` o
`poster.swf`. Que exista ese archivo no demuestra que siga conteniendo el
evento del alias. También aparecen clases compartidas incrustadas en salas
que pueden no mostrar la decoración del evento. Por eso **ningún evento se
ha marcado como completo ni se ha habilitado un botón engañoso de activación
total**. El inventario enumera evidencias y pendientes por grupo.

## Validación

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/legacy-player.test.cjs tests/vanilla-player.test.cjs tests/world-notice.test.cjs
python scripts/audit-events.py --check
python scripts/generate-dokploy-compose.py --check
docker compose config --quiet
```

Las pruebas cubren publicaciones, persistencia tras reabrir el almacén,
restauración, paquetes atómicos, conflictos entre moderadores, recursos
ausentes, aislamiento por sala, rutas y archivos inválidos y el aviso de
recarga. La [validación local con Docker](local-validation.md) comprobó también
la entrada de una cuenta real desde Ruffle y la carga de una variante y música
seleccionadas en la implementación anterior. El estado de validación del catálogo
y panel nuevos se documenta por separado en ese informe. Persisten las limitaciones heredadas recogidas en ese informe.
