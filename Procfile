web: gunicorn lazer.wsgi:application --bind 0.0.0.0:$PORT --worker-class gthread --workers 1 --threads 4 --timeout 90 --graceful-timeout 30 --keep-alive 5 --max-requests 600 --max-requests-jitter 60 --worker-tmp-dir /dev/shm --capture-output --access-logfile - --error-logfile -
worker: python manage.py observar_pendencias --intervalo 60
