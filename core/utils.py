import math



def estimar_tempo_minutos(distancia_km, velocidade_media_kmh=30):
    return int((distancia_km / velocidade_media_kmh) * 60)

import requests
from decimal import Decimal
from math import radians, sin, cos, sqrt, atan2

VALOR_POR_KM = Decimal("3.50")

CEP_EMPRESA = "02679-110"


def buscar_lat_lon(cep):
    url = f"https://nominatim.openstreetmap.org/search"
    params = {
        "postalcode": cep,
        "country": "Brazil",
        "format": "json"
    }

    r = requests.get(url, params=params, headers={"User-Agent": "django-app"})
    data = r.json()

    if not data:
        return None, None

    return float(data[0]["lat"]), float(data[0]["lon"])


def calcular_distancia_km(lat1, lon1, lat2, lon2):

    R = 6371

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1))
        * cos(radians(lat2))
        * sin(dlon / 2) ** 2
    )

    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c


def calcular_frete_por_cep(cep_cliente):

    lat1, lon1 = buscar_lat_lon(CEP_EMPRESA)
    lat2, lon2 = buscar_lat_lon(cep_cliente)

    if not lat1 or not lat2:
        return Decimal("0.00"), Decimal("0.00")

    distancia = Decimal(calcular_distancia_km(lat1, lon1, lat2, lon2))

    valor = (distancia * VALOR_POR_KM).quantize(Decimal("0.01"))

    return valor, distancia.quantize(Decimal("0.01"))


