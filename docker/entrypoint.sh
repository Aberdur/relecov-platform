#!/bin/bash
set -euo pipefail

cd /opt/relecov-platform

STATIC_DIR="/opt/relecov-platform/static"

# Si el volumen de estáticos está vacío (o solo tiene .gitkeep), generar los ficheros
if [ -d "$STATIC_DIR" ] && ! find "$STATIC_DIR" -mindepth 1 -maxdepth 1 ! -name '.gitkeep' -print -quit 2>/dev/null | grep -q .; then
  echo "Static directory is empty; running collectstatic..."
  /opt/relecov-platform/virtualenv/bin/python manage.py collectstatic --noinput
fi

exec "$@"
