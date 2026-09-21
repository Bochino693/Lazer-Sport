"""
WSGI config for lazer project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lazer.settings')

from core.healthcheck import HealthcheckWSGI
from core.traffic_shield import TrafficShieldWSGI

# O health check fica por fora para continuar respondendo mesmo quando o
# catálogo público está no limite. O escudo rejeita lixo antes do Django.
application = HealthcheckWSGI(TrafficShieldWSGI(get_wsgi_application()))
