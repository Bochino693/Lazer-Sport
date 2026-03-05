import requests
import math
import logging

logger = logging.getLogger(__name__)

CEP_EMPRESA = "02679-110"
VALOR_KM = 3.50


def buscar_endereco(cep):

    try:

        cep_limpo = cep.replace("-", "")

        url = f"https://viacep.com.br/ws/{cep_limpo}/json/"

        r = requests.get(url, timeout=5)
        data = r.json()

        if "erro" in data:
            logger.error(f"[FRETE] CEP não encontrado no ViaCEP: {cep}")
            return None

        endereco = f"{data.get('logradouro','')}, {data.get('bairro','')}, {data.get('localidade','')}, {data.get('uf')}, Brazil"

        logger.info(f"[FRETE] Endereço encontrado: {endereco}")

        return endereco

    except Exception as e:

        logger.error(f"[FRETE] Erro ViaCEP {cep}: {e}")

        return None


def buscar_coordenadas(endereco):

    try:

        url = "https://nominatim.openstreetmap.org/search"

        params = {
            "q": endereco,
            "format": "json",
            "limit": 1
        }

        headers = {
            "User-Agent": "lazersport-frete"
        }

        r = requests.get(url, params=params, headers=headers, timeout=5)

        data = r.json()

        if not data:
            logger.error(f"[FRETE] Coordenadas não encontradas para: {endereco}")
            return None, None

        lat = float(data[0]["lat"])
        lon = float(data[0]["lon"])

        logger.info(f"[FRETE] Coordenadas: {lat}, {lon}")

        return lat, lon

    except Exception as e:

        logger.error(f"[FRETE] Erro ao buscar coordenadas: {e}")

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

    logger.info(f"[FRETE] Calculando frete para CEP {cep_cliente}")

    endereco_empresa = buscar_endereco(CEP_EMPRESA)
    endereco_cliente = buscar_endereco(cep_cliente)

    if not endereco_empresa or not endereco_cliente:
        logger.error("[FRETE] Não foi possível obter endereços")
        return 0, 0

    lat1, lon1 = buscar_coordenadas(endereco_empresa)
    lat2, lon2 = buscar_coordenadas(endereco_cliente)

    distancia = distancia_km(lat1, lon1, lat2, lon2)

    valor_frete = distancia * VALOR_KM

    logger.info(
        f"[FRETE] Resultado -> {distancia:.2f} km | Frete R$ {valor_frete:.2f}"
    )

    return valor_frete, distancia


