# Un despliegue debe arrancar todos los servicios

En Dokploy se usa **General -> Deploy** para ejecutar el Compose completo.
Reiniciar un contenedor desde Containers solo actúa sobre ese contenedor; no
reanuda la operación Compose que había abortado por una dependencia unhealthy.
Los reinicios individuales sugeridos durante el diagnóstico eran recuperación
puntual, no el procedimiento normal después de cada push.

`docker compose up -d --build` puede conservar contenedores que no necesitan
recrearse. Por eso una antigüedad de varias horas no demuestra duplicados.
`restart: always` reinicia procesos que terminan, pero no procesos que siguen
vivos con estado unhealthy.

## Cambios de coordinación

- Login espera PostgreSQL y Redis healthy y declara `depends_on.restart: true`.
- Los cuatro mundos esperan DB, Redis y login healthy y se reinician cuando
  Compose actualiza o reinicia explícitamente esas dependencias.
- Dash y Snowflake esperan DB/Redis healthy y reciben la misma propagación.
- Web depende explícitamente de Dash y del proxy; se reinicia cuando Compose
  actualiza esos servicios para resolver otra vez sus direcciones internas.
- Login y mundos deben responder `apiOK` a una comprobación de versión del
  protocolo antes de marcarse healthy. Houdini abre el puerto TCP antes de
  terminar su arranque, por lo que un socket abierto por sí solo no basta.

Esto se aplica a operaciones coordinadas de Compose. No convierte el estado
unhealthy en un reinicio automático de Docker, no sustituye la recuperación de
datos y no oculta fallos de credenciales, redes o almacenamiento.

## Persistencia antes de desplegar

Conserva el nombre del proyecto y usa `docker-compose.dokploy.yml`, con los
directorios **existentes** de PostgreSQL y Redis fuera del checkout Git. Si los
datos actuales están dentro de `code/.data` o `code/.redis`, preservarlos y
migrarlos es un requisito previo: Dokploy puede borrar code al clonar.
No cambies a directorios vacíos, no uses Fresh Volumes y no elimines volúmenes.
Ver [guía Dokploy](ruffle.md).

## Prueba de integración

`tests/check-backend-startup.py` crea un proyecto Docker único con PostgreSQL y
Redis sobre tmpfs y los cinco Houdini reales. No monta los datos del proyecto
ni publica puertos. Comprueba el arranque en frío, reemplaza la DB de prueba
para verificar la propagación de reinicios y ejecuta un único `up` después de
detener los mundos. Las fuentes y SQL son los commits fijados del repositorio.

La prueba se ejecuta en el job backend de GitHub Actions. No valida el estado
de las redes, rutas persistentes ni copias de seguridad del servidor real.

Referencia: [orden de arranque y restart de dependencias en Compose](https://docs.docker.com/compose/how-tos/startup-order/).
