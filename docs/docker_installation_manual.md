# Instalación completa desde cero (relecov-platform + iSkyLIMS + Nextstrain) con Docker y MySQL en el host

Objetivo: desplegar las aplicaciones en contenedores, usando MySQL instalado en el host (no se crean contenedores de base de datos). Guía pensada para alguien que parte de cero.

## 0. Prerrequisitos
- Docker y docker compose instalados.
- MySQL instalado en el host (Ubuntu/Debian/CentOS).
- Repositorios clonados en el host:
  - `~/relecov-platform` (este repo).
  - `~/iskylims` (repo hermano, porque el `docker-compose` construye la imagen de iSkyLIMS desde `../iskylims`).
- (Opcional) Apache en el host si quieres servir estáticos/proxy/SSL desde el host.

## 1. Configura MySQL en el host
1) Permite conexiones desde la red de Docker:
   - Edita `/etc/mysql/mysql.conf.d/mysqld.cnf` (o tu fichero de MySQL) y deja:
     ```
     bind-address = 0.0.0.0
     ```
   - Reinicia MySQL: `sudo systemctl restart mysql`.
2) Crea bases y usuarios (ajusta contraseñas a tu gusto):
   ```sql
   CREATE DATABASE IF NOT EXISTS relecov;
   CREATE DATABASE IF NOT EXISTS relecovlims;

   CREATE USER IF NOT EXISTS 'relecov_user'@'%' IDENTIFIED WITH mysql_native_password BY '<clave_relecov>';
   CREATE USER IF NOT EXISTS 'relecov_lims'@'%' IDENTIFIED WITH mysql_native_password BY '<clave_lims>';

   GRANT ALL ON relecov.* TO 'relecov_user'@'%';
   GRANT ALL ON relecovlims.* TO 'relecov_lims'@'%';
   FLUSH PRIVILEGES;
   ```
   - Si ya tienes usuarios/bases válidos y accesibles desde la red de Docker, reutilízalos y omite este paso.
3) Importa los dumps en esas bases (usa la IP real de tu host, por ejemplo la que te da `hostname -I | awk '{print $1}'`):
   ```bash
   mysql -h <IP_host> -P 3306 -u relecov_user -p relecov     < /ruta/al_dump_relecov.sql
   mysql -h <IP_host> -P 3306 -u relecov_lims -p relecovlims < /ruta/al_dump_iskylims.sql
   ```

## 2. Ajusta los settings de conexión
Edita estos dos ficheros con la IP y credenciales que usas en MySQL del host:

### 2.1 relecov-platform/conf/docker_install_settings.txt
```
DB_SERVER_IP=<IP_host>
DB_PORT=3306
DB_NAME=relecov
DB_USER=relecov_user
DB_PASS=<clave_relecov>
LOCAL_SERVER_IP=<IP_local>        # ej. 127.0.0.1 en local, o la IP del host
DNS_URL=<host_o_dominio>          # el nombre con el que accederás (coincide con ServerName si usas Apache)
SUPERUSER=<admin_user>
```

### 2.2 ~/iskylims/conf/docker_install_settings.txt
```
DB_HOST=<IP_host>
DB_PORT=3306
DB_NAME=relecovlims
DB_USER=relecov_lims
DB_PASS=<clave_lims>
```

## 3. Revisa/edita `docker-compose.yml` (relecov-platform)
- Confirmar que **no** hay servicios `db` ni `iskylims_db`. Solo `app`, `iskylims_app`, `redis`, `nextstrain`.
- En Linux, el compose ya usa `host-gateway` para que `host.docker.internal` resuelva al host:
  ```yaml
  extra_hosts:
    - "host.docker.internal:host-gateway"
  ```
  Si tu versión de Docker no soporta `host-gateway`, sustituye esa línea por la IP real del host.
- Puertos expuestos por defecto:
  - Plataforma: `8000:8000`
  - iSkyLIMS: `8001:8001`
  - Nextstrain: `8100:8100`
- Si quieres otros puertos, cambia los `ports` en el compose de cada servicio.

## 4. Ajusta ALLOWED_HOSTS si lo necesitas
En `relecov-platform/conf/template_settings.py` ya se incluye `localhost`, `host.docker.internal`, `*`. Si deseas limitarlo, añade ahí los hostnames que vayas a usar.
En `~/iskylims/conf/template_settings.txt` (repo iSkyLIMS), revisa `ALLOWED_HOSTS` y añade `iskylims_app`, `localhost`, el dominio/IP que uses.

## 5. Configura Apache del host (solo si vas a usarlo)
- Edita `relecov-platform/conf/relecov_apache_proxy_docker.conf`:
  - `ServerName` con tu dominio/host.
  - Rutas absolutas a los bind mounts:
    - `/ruta/al/repo/docker/data/static`
    - `/ruta/al/repo/docker/data/documents`
- Activa site y módulos:
  ```bash
  sudo cp conf/relecov_apache_proxy_docker.conf /etc/apache2/sites-available/relecov-platform.conf
  sudo a2enmod proxy proxy_http headers
  sudo a2ensite relecov-platform.conf
  sudo systemctl restart apache2
  ```
  (en RHEL/CentOS, copia a `/etc/httpd/conf.d/` y `systemctl restart httpd`).

## 6. Construye las imágenes
```bash
cd ~/relecov-platform
docker compose build app iskylims_app
```

## 7. Arranca los servicios
```bash
docker compose up -d app iskylims_app redis nextstrain
```

Alternativa: usar el asistente `docker_install.sh`:
```bash
# Si partes de una DB ya restaurada con dump
./docker_install.sh --mode dump

# Si haces un setup en limpio (migraciones + datos iniciales)
./docker_install.sh --mode clean
```

## 8. Comprueba conexión a MySQL desde Docker
```bash
docker run --rm --network relecov-platform_relecov_net mysql:8.0 \
  mysqladmin -h <IP_host> -P 3306 -u relecov_user -p'<clave_relecov>' ping
```
Debe responder `mysqld is alive`. Repite con el usuario de iSkyLIMS si quieres.

## 9. Estáticos de relecov-platform
Si ves la web sin CSS/JS, genera los estáticos:
```bash
docker compose exec -T app bash -lc \
  "cd /opt/relecov-platform && /opt/relecov-platform/virtualenv/bin/python manage.py collectstatic --noinput"
```

## 10. Configuración dentro de la plataforma
- En Config Settings (admin):
  - `ISKYLIMS_SERVER = http://iskylimsapp:8001` (URL interna en la red de Docker).
  - `NEXTSTRAIN_URL = http://localhost:8100/<dataset_valido>` (elige uno del listado de Auspice, p. ej. `SARS-CoV-2/2025-10-06`).

## 11. Nextstrain
- Datasets en `docker/data/nextstrain`, servidos en `http://localhost:8100`.
- Usa las rutas que Auspice muestra en “Available datasets”. Si una URL devuelve 404, ajusta el enlace a un dataset existente.

## 12. Accesos de prueba
- Plataforma: `http://localhost:8000` (o el host/Apache que configures).
- Admin plataforma: `http://localhost:8000/admin` (crea superusuario si el dump no lo trae).
- iSkyLIMS: `http://localhost:8001` / `http://localhost:8001/admin`.
- Nextstrain: `http://localhost:8100` y selecciona un dataset del listado inicial.

## 13. Problemas típicos y soluciones
- **No conecta a la DB**: revisa que MySQL escuche en 0.0.0.0, la IP/puerto en los settings y que el usuario tenga permisos desde `%`.
- **DisallowedHost**: añade el host usado a `ALLOWED_HOSTS` (ya incluimos `localhost`, `host.docker.internal` y `*`).
- **Sin CSS/JS**: ejecuta `collectstatic` (paso 7).
- **404 en Nextstrain**: la URL apunta a un dataset inexistente; elige una ruta válida de Auspice.
- **Error KeyError: Unable to find stateless DjangoApp**: con `django-plotly-dash`, los Dash apps se registran en memoria del proceso; si usas múltiples workers de Gunicorn puede fallar. En el Dockerfile se usa `--workers 1` para evitarlo.
