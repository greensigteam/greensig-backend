#!/bin/bash
set -e

echo "==> Waiting for database to be ready..."
python << END
import sys
import time
import psycopg2
from decouple import config

max_attempts = 30
attempt = 0

while attempt < max_attempts:
    try:
        conn = psycopg2.connect(
            dbname=config('DB_NAME'),
            user=config('DB_USER'),
            password=config('DB_PASSWORD'),
            host=config('DB_HOST'),
            port=config('DB_PORT', default='5432')
        )
        conn.close()
        print("✓ Database is ready!")
        sys.exit(0)
    except psycopg2.OperationalError:
        attempt += 1
        print(f"Attempt {attempt}/{max_attempts}: Database not ready yet, waiting...")
        time.sleep(2)

print("✗ Database connection failed after maximum attempts")
sys.exit(1)
END

echo "==> Running database migrations..."
python manage.py migrate --noinput

echo "==> Collecting static files..."
python manage.py collectstatic --noinput

echo "==> Starting Daphne ASGI server..."
exec daphne -b 0.0.0.0 -p 8000 greensig_web.asgi:application
