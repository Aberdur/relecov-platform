FROM ubuntu:24.04

ENV TZ=Europe/Madrid
ARG DEBIAN_FRONTEND=noninteractive

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Base system and build dependencies
# NOTE: Some Ubuntu mirrors occasionally serve inconsistent package indexes (Hash Sum mismatch).
# We avoid `apt-get upgrade` to reduce churn and add retries around `apt-get update`.
RUN set -eux; \
    rm -rf /var/lib/apt/lists/*; \
    for i in 1 2 3; do \
      apt-get update -o Acquire::Retries=5 && break; \
      echo "apt-get update failed (attempt $i), retrying..."; \
      sleep 5; \
    done; \
    apt-get install -y --no-install-recommends \
      git lsb-release \
      python3 python3-dev python3-pip python3-venv python3-wheel \
      libmysqlclient-dev \
      build-essential \
      apache2-dev pkg-config rsync && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /srv/relecov-platform
COPY . /srv/relecov-platform

RUN export MYSQLCLIENT_CFLAGS="$(pkg-config --libs mysqlclient)" && \
    export MYSQLCLIENT_LDFLAGS="$(pkg-config --cflags mysqlclient)"

# Install Django project into the image
ARG INSTALL_TYPE=full
ARG GIT_REVISION=develop

RUN /bin/bash install.sh --install $INSTALL_TYPE --git_revision $GIT_REVISION --conf conf/docker_install_settings.txt --docker

# Extra runtime deps
RUN /opt/relecov-platform/virtualenv/bin/pip install gunicorn

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Use the virtualenv created by install.sh
ENV PATH="/opt/relecov-platform/virtualenv/bin:${PATH}"
ENV DJANGO_SETTINGS_MODULE="relecov_platform.settings"

WORKDIR /opt/relecov-platform
EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
# NOTE: django-plotly-dash registers apps in-process; with multiple Gunicorn workers
# it's possible that a worker receives a request for a Dash app before it's been
# registered in that worker, causing "Unable to find stateless DjangoApp".
CMD ["gunicorn", "relecov_platform.wsgi:application", "-b", "0.0.0.0:8000", "--workers", "1", "--timeout", "120"]
