FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libcairo2 libpango-1.0-0 libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 libffi-dev shared-mime-info \
    postgresql-client curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x /app/scripts/docker-entrypoint.sh /app/scripts/backup_db.sh /app/scripts/restore_db.sh
RUN addgroup --system facilerp && adduser --system --ingroup facilerp facilerp \
    && mkdir -p /app/instance /app/backups /app/uploads/brand \
    && chown -R facilerp:facilerp /app

EXPOSE 5000

USER facilerp

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:create_app('production')"]
