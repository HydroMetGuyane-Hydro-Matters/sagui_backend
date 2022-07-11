FROM python:3.9-slim

LABEL project="sagui"
LABEL org.opencontainers.image.authors="jeanpommier@pi-geosolutions.fr"

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        binutils \
        libproj-dev \
        gdal-bin \
        netcat \
        postgresql-client \
#        postgresql-10-postgis-3-scripts \
#        postgresql-plpython-10 \
#        python3-psycopg2 \
        && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app && chown www-data:www-data /app
WORKDIR /app
#RUN groupadd -r www-data && useradd -r -g www-data www-data

RUN pip install --no-cache-dir --upgrade pip setuptools gunicorn
COPY --chown=www-data:www-data src/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY --chown=www-data:www-data src/ /app/
# Create static folder to store django static apps
# Make www-data the owner (will be kept even if we mount a volume instead
RUN mkdir /static && \
    chown www-data:www-data /static

COPY --chown=www-data:www-data data/ /data/

USER www-data

# Django service
EXPOSE 8000

COPY --chown=www-data:www-data docker/ /
RUN chmod +x /entrypoint.sh &&\
    chmod +x /docker-entrypoint.d/*

ENTRYPOINT ["/entrypoint.sh"]

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "sagui_backend.wsgi:application"]