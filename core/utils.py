import math

def calcular_distancia_km(lat1, lon1, lat2, lon2):
    R = 6371  # raio da Terra em km

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2 +
        math.cos(phi1) * math.cos(phi2) *
        math.sin(delta_lambda / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def estimar_tempo_minutos(distancia_km, velocidade_media_kmh=30):
    return int((distancia_km / velocidade_media_kmh) * 60)


# utils/frete.py
import requests
from decimal import Decimal
from math import radians, sin, cos, sqrt, atan2

VALOR_POR_KM = Decimal("7.50")

# CEP da empresa (origem)
CEP_EMPRESA = "01001-000"  # ajustar conforme necessário

def buscar_lat_lon(cep):
    """Retorna (lat, lon) do CEP usando ViaCEP + API Nominatim"""
    cep = cep.replace("-", "")
    res = requests.get(f"https://viacep.com.br/ws/{cep}/json/")
    res.raise_for_status()
    dados = res.json()
    if dados.get("erro"):
        return None, None

    # Monta endereço completo
    logradouro = dados.get("logradouro", "")
    bairro = dados.get("bairro", "")
    cidade = dados.get("localidade", "")
    uf = dados.get("uf", "")
    endereco = f"{logradouro}, {bairro}, {cidade} - {uf}, Brasil"

    # Geocoding via Nominatim OpenStreetMap
    geo_res = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": endereco, "format": "json"},
        headers={"User-Agent": "MeuEcommerceApp"}
    )
    geo_res.raise_for_status()
    geo_dados = geo_res.json()
    if not geo_dados:
        return None, None

    lat = float(geo_dados[0]["lat"])
    lon = float(geo_dados[0]["lon"])
    return lat, lon

def calcular_distancia_km(lat1, lon1, lat2, lon2):
    """Calcula distância em km usando Haversine"""
    R = 6371  # km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

def calcular_frete_por_cep(cep_cliente):
    """Retorna valor do frete e distância estimada"""
    lat_origem, lon_origem = buscar_lat_lon(CEP_EMPRESA)
    lat_dest, lon_dest = buscar_lat_lon(cep_cliente)
    if None in (lat_origem, lon_origem, lat_dest, lon_dest):
        return Decimal("0.00"), None

    distancia = calcular_distancia_km(lat_origem, lon_origem, lat_dest, lon_dest)
    valor_frete = (Decimal(distancia) * VALOR_POR_KM).quantize(Decimal("0.01"))
    return valor_frete, Decimal(distancia).quantize(Decimal("0.01"))