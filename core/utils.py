import requests
import math
import logging

logger = logging.getLogger(__name__)
from functools import lru_cache

CEP_EMPRESA = "02679-110"
VALOR_KM = 3.50

LAT_EMPRESA = -23.459889
LON_EMPRESA = -46.689654


def buscar_endereco(cep):

    try:

        cep_limpo = cep.replace("-", "")

        url = f"https://viacep.com.br/ws/{cep_limpo}/json/"

        r = requests.get(url, timeout=5)
        data = r.json()

        if "erro" in data:
            logger.error(f"[FRETE] CEP não encontrado no ViaCEP: {cep}")
            return None

        logradouro = data.get("logradouro") or ""
        bairro = data.get("bairro") or ""
        cidade = data.get("localidade") or ""
        estado = data.get("uf") or ""

        endereco = f"{logradouro}, {bairro}, {cidade}, {estado}, Brazil"

        logger.info(f"[FRETE] Endereço encontrado: {endereco}")

        return endereco

    except Exception as e:

        logger.error(f"[FRETE] Erro ViaCEP {cep}: {e}")

        return None


@lru_cache(maxsize=2000)
def buscar_coordenadas(cep):

    try:

        endereco = buscar_endereco(cep)

        if not endereco:
            return None, None

        url = "https://nominatim.openstreetmap.org/search"

        headers = {
            "User-Agent": "lazersport-frete"
        }

        # tentativa 1 — endereço completo
        params = {
            "q": endereco,
            "format": "json",
            "limit": 1
        }

        r = requests.get(url, params=params, headers=headers, timeout=5)
        data = r.json()

        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])

        # tentativa 2 — cidade + estado
        parts = endereco.split(",")

        cidade = parts[-3].strip()
        estado = parts[-2].strip()

        params = {
            "q": f"{cidade}, {estado}, Brazil",
            "format": "json",
            "limit": 1
        }

        r = requests.get(url, params=params, headers=headers, timeout=5)
        data = r.json()

        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])

        logger.error(f"[FRETE] Não foi possível geocodificar CEP: {cep}")

        return None, None

    except Exception as e:
        logger.error(f"[FRETE] erro geocode {cep}: {e}")
        return None, None


def distancia_km(lat1, lon1, lat2, lon2):

    if None in (lat1, lon1, lat2, lon2):
        logger.warning("[FRETE] Coordenadas inválidas")
        return 0

    R = 6371

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distancia = R * c

    logger.info(f"[FRETE] Distância calculada: {distancia:.2f} km")

    return distancia


def calcular_frete_por_cep(cep_cliente):

    print("CEP CLIENTE:", cep_cliente)

    lat1 = LAT_EMPRESA
    lon1 = LON_EMPRESA

    lat2, lon2 = buscar_coordenadas(cep_cliente)

    print("COORD EMPRESA:", lat1, lon1)
    print("COORD CLIENTE:", lat2, lon2)

    distancia = distancia_km(lat1, lon1, lat2, lon2)

    print("DISTANCIA:", distancia)

    valor_frete = round(distancia * VALOR_KM, 2)

    print("FRETE:", valor_frete)

    return valor_frete, distancia