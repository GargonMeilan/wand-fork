# Biblioteca preinstalada y vistas previas

El manager está en inglés y comparte navegación, tipografía, colores y controles
entre Overview, Rooms & events, Online players, Players, Username review y las
páginas de cuenta. Las plantillas adaptadas viven en `world_manager/templates`;
no se han editado los submódulos.

## Recursos incluidos

La instalación incluye **16 eventos de 2012, 303 variantes de salas y 76
referencias a recursos complementarios**. Hay 377 archivos únicos referenciados,
aproximadamente 62 MiB. Town dispone de **13 variantes históricas**, además del
original. Los archivos están incluidos en el repositorio, no solo sus enlaces;
no hay que subirlos al manager ni descargarlos al iniciar el servidor.

Los paquetes incluyen Underwater Expedition, Fashion Show, Rockhopper's Quest,
Puffle Party, April Fools' Party, Easter Egg Hunt, Earth Day, Medieval Party,
Marvel Super Hero Takeover, Ultimate Jam, Adventure Party: Temple of Fruit,
The Fair, Halloween, 7th Anniversary, Operation: Blackout y Holiday Party.

Cada paquete indica sus salas y recursos concretos. Las salas de otras ediciones
que no se han recuperado no se presentan como variantes disponibles.

## Vista previa de una sala

1. Abre **Rooms & events**, elige la sala y pulsa **Open**.
2. En **Design**, selecciona una variante histórica o un archivo propio.
3. Pulsa **Load preview**. La imagen de la sala se reproduce con Ruffle en el
   propio panel. La vista previa es independiente del mundo activo: no publica
   una revisión, no cambia la sala y no inicia una sesión de jugador.
4. Para publicar solo esa sala, usa **Apply room design**. La música propuesta
   corresponde a los datos recuperados cuando existe esa información; se puede
   cambiar antes de aplicar. Si no hay música documentada se propone silencio.

El reproductor de vista previa no recibe claves del jugador, tiene deshabilitado
el acceso JavaScript del SWF y bloquea sus peticiones de red. Es una vista visual:
los botones, minijuegos y demás interacciones pueden necesitar el motor completo.
Se verificó visualmente que Town de Marvel muestra su ciudad y Town de Halloween
sus edificios decorados; no se usaron copias del Town original como sustituto.

## Activar un evento

En **Event library**, **Activate [event]** aplica en una transacción todas las
salas, músicas y recursos recuperados del paquete, sustituyendo el paquete
anterior. También se sirven los catálogos, notas y demás recursos incluidos en
sus rutas del cliente. Los catálogos recuperados están en inglés y utilizan el
inventario y los paquetes de compra existentes del servidor.

**Restore all original rooms & resources** restaura las selecciones originales
y desactiva los recursos complementarios del paquete. Los jugadores deben
recargar el juego para recibir la nueva configuración.

Los paquetes están marcados **Resource package**. Esto no equivale a tener
implementadas todas las mecánicas del evento: poderes, transformaciones,
misiones y recompensas específicas necesitan soporte y pruebas adicionales.
Ninguno de los dieciséis paquetes está certificado como evento completo con
todas sus mecánicas. No hay un botón que afirme falsamente habilitarlas.
**Included content & limitations** enumera las salas omitidas o pendientes.

Elegir una variante histórica individual activa también sus recursos
complementarios. Si se mezclan variantes de distintos eventos, los recursos
comunes, como `catalogues/party.swf`, corresponden al último evento elegido.
Para mantener un conjunto coherente, activa el paquete entero.

## Procedencia e integridad

Los archivos provienen del espejo público de
[Waddle Forever](https://github.com/nhaar/Waddle-Forever/tree/02a9df8be1f33d570690d8a59a726a9bcc9d34df/media/default/archives),
con asociaciones históricas de su línea temporal de 2012. El manifest fija el
commit, la URL y los hashes Git/SHA-256 de cada archivo. Los SWF originales son
de Disney/Club Penguin; la licencia MIT de los metadatos no transfiere los
derechos de los recursos originales. Se conservan los avisos de atribución en
`world_manager/catalog/UPSTREAM-LICENSE.txt` y `world_manager/DASH-LICENSE.md`.

```sh
python scripts/import-event-catalog.py --verify
```

Comprueba los hashes, tamaños y cabeceras sin hacer peticiones de red. Si un
archivo falta o está dañado, `--repair` permite restaurarlo desde su URL fijada;
no consulta ramas móviles ni ejecuta código descargado.

## Pruebas y límites de esta revisión

Las pruebas del almacén cubren la disponibilidad en una instalación sin subidas,
la activación conjunta de salas y catálogos, la persistencia al reabrir el estado,
la restauración y el rechazo de paquetes incompletos o rutas ajenas. La prueba
de navegador comprueba las vistas previas reales, la propuesta de música, el
diseño móvil y la ausencia de peticiones de publicación al previsualizar.

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/legacy-player.test.cjs tests/vanilla-player.test.cjs tests/world-notice.test.cjs tests/online-panel.test.cjs
node tests/catalog-browser-smoke.cjs
```

Las pruebas de navegador requieren Jinja2, los medios Vanilla, Playwright en
`.validation/node_modules`, Chromium en
`.validation/browsers/chromium-1194/chrome-win/chrome.exe` y el runtime instalado
en `web/ruffle/node_modules/@ruffle-rs/ruffle`. El script genera su propia página
de prueba usando las plantillas reales; no necesita levantar Docker.

La integración real con Docker verificó la activación de los 16 paquetes y la
entrega de todas sus salas y recursos complementarios a través de Nginx, con
hashes coincidentes. Una partida autenticada con Ruffle cargó Town de Marvel y
su música 325. También se comprobaron la vista previa autenticada y las páginas
de jugadores, ficha de jugador, revisión de nombres y cuenta.

La compra desde catálogos históricos, los recorridos completos de todas las
salas y las mecánicas específicas de cada fiesta siguen sin certificarse. Véase
[el informe de validación](local-validation.md) para los errores heredados del
cliente y los límites de la prueba.
