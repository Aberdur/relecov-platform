#!/usr/bin/env bash

set -euo pipefail

RELECOV_VERSION="1.0.0"

usage() {
cat << EOF
Script de ayuda para desplegar relecov-platform con Docker.

Uso: $0 [--mode clean|dump] [--install_type full|app] [--git_revision rama]

Opciones:
  --mode           Modo de despliegue:
                   - clean: ejecuta migraciones y carga tablas iniciales (sin dump).
                   - dump: asume que ya has restaurado un dump en MySQL (no ejecuta migrate).
  --install_type   Tipo de instalación que se pasará a install.sh (por defecto: full).
  --git_revision   Revisión de git a usar en la build (por defecto: develop).
  -h, --help       Muestra esta ayuda.
  -v, --version    Muestra la versión del asistente.

Ejemplos:
  bash $0 --mode clean
  bash $0 --mode dump
  bash $0 --install_type app --git_revision develop
EOF
}

install_type="full"
git_revision="develop"
mode="dump"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)
            mode="$2"
            shift 2
            ;;
        --install_type)
            install_type="$2"
            shift 2
            ;;
        --git_revision)
            git_revision="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        -v|--version)
            echo "$RELECOV_VERSION"
            exit 0
            ;;
        *)
            echo "Opción no reconocida: $1"
            usage
            exit 1
            ;;
    esac
done

if [[ "$mode" != "clean" && "$mode" != "dump" ]]; then
    echo "Valor inválido para --mode: $mode (usa clean|dump)"
    exit 1
fi

echo "Construyendo contenedores (install_type=$install_type, git_revision=$git_revision)..."
docker compose build --build-arg INSTALL_TYPE="$install_type" --build-arg GIT_REVISION="$git_revision"

echo "Levantando servicios..."
docker compose up -d

if [[ "$mode" == "clean" ]]; then
    echo "Generando migraciones (por si faltan iniciales)..."
    docker compose exec -T app python manage.py makemigrations core dashboard django_plotly_dash --noinput || true

    echo "Aplicando migraciones de Django (fake-initial si ya hay esquema del dump)..."
    docker compose exec -T app python manage.py migrate --fake-initial

    echo "Cargando tablas iniciales..."
    docker compose exec -T app python manage.py loaddata conf/first_install_tables.json
else
    echo "Modo dump: se omiten migraciones y carga inicial (se asume dump ya restaurado en MySQL)."
fi

echo "Generando estáticos en el volumen compartido..."
docker compose exec -T app python manage.py collectstatic --noinput

echo "collectstatic listo; si cambias ficheros estáticos, relanza:"
echo "  docker compose exec -T app python manage.py collectstatic --noinput"

echo "Despliegue listo. Acceso web: http://localhost:8000"
