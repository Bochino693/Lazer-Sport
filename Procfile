web: gunicorn lazer.wsgi:application -c gunicorn.conf.py
worker: python manage.py observar_pendencias --intervalo 60
