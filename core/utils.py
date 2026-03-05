import requests
import math
import logging

logger = logging.getLogger(__name__)

CEP_EMPRESA = "02679-110"
VALOR_KM = 3.50

import requests
import logging

logger = logging.getLogger(__name__)


def buscar_coordenadas(cep):

    try:

        cep_limpo = cep.replace("-", "")

        url = "https://nominatim.openstreetmap.org/search"

        params = {
            "postalcode": cep_limpo,
            "country": "Brazil",
            "format": "json"
        }

        headers = {
            "User-Agent": "lazersport-frete"
        }

        r = requests.get(url, params=params, headers=headers, timeout=5)

        data = r.json()

        if not data:
            logger.error(f"[FRETE] Nenhum resultado para CEP {cep}")
            return None, None

        lat = float(data[0]["lat"])
        lon = float(data[0]["lon"])

        logger.info(f"[FRETE] Coordenadas obtidas para CEP {cep}: {lat}, {lon}")

        return lat, lon

    except Exception as e:

        logger.error(f"[FRETE] Erro ao buscar coordenadas do CEP {cep}: {e}")

        return None, None


def distancia_km(lat1, lon1, lat2, lon2):

    if None in (lat1, lon1, lat2, lon2):
        logger.warning("[FRETE] Coordenadas inválidas para cálculo de distância")
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

    logger.info(f"[FRETE] Calculando frete para CEP {cep_cliente}")

    lat1, lon1 = buscar_coordenadas(CEP_EMPRESA)
    lat2, lon2 = buscar_coordenadas(cep_cliente)

    distancia = distancia_km(lat1, lon1, lat2, lon2)

    valor_frete = distancia * VALOR_KM

    logger.info(
        f"[FRETE] Resultado -> distância: {distancia:.2f} km | frete: R$ {valor_frete:.2f}"
    )

    return valor_frete, distancia

