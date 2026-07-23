import requests
import math
import re
import logging

logger = logging.getLogger(__name__)
from functools import lru_cache

CEP_EMPRESA = "02679-110"
VALOR_KM = 3.50

LAT_EMPRESA = -23.459889
LON_EMPRESA = -46.689654


def cep_valido(cep):
    """CEP brasileiro válido = exatamente 8 dígitos depois de tirar
    traço/espaço. Usado pra recusar CEP incompleto/errado ANTES de
    consultar ViaCEP/Nominatim -- evita geocodificação ambígua a partir
    de um CEP que nem existe."""
    if not cep:
        return False
    return bool(re.fullmatch(r"\d{8}", cep.replace("-", "").replace(" ", "")))


def buscar_endereco(cep):

    try:

        if not cep_valido(cep):
            logger.warning(f"[FRETE] CEP inválido (precisa ter 8 dígitos): {cep}")
            return None

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
def buscar_dados_cep(cep):
    """
    Mesma fonte (ViaCEP) que o buscar_endereco(), mas devolve os campos
    separados (rua/bairro/cidade/estado) em vez de uma string só --
    usado pra preencher o endereço dos Clientes automaticamente a
    partir do CEP, sem precisar digitar cidade/estado na mão.
    """
    try:
        if not cep_valido(cep):
            logger.warning(f"[CLIENTES] CEP inválido (precisa ter 8 dígitos): {cep}")
            return None

        cep_limpo = cep.replace("-", "")
        url = f"https://viacep.com.br/ws/{cep_limpo}/json/"

        r = requests.get(url, timeout=5)
        data = r.json()

        if "erro" in data:
            logger.error(f"[CLIENTES] CEP não encontrado no ViaCEP: {cep}")
            return None

        return {
            "rua": data.get("logradouro") or "",
            "bairro": data.get("bairro") or "",
            "cidade": data.get("localidade") or "",
            "estado": data.get("uf") or "",
        }

    except Exception as e:
        logger.error(f"[CLIENTES] Erro ViaCEP {cep}: {e}")
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

        # tentativa 1 — endereço completo (rua + bairro + cidade + estado)
        params = {
            "q": endereco,
            "format": "json",
            "limit": 1
        }

        r = requests.get(url, params=params, headers=headers, timeout=5)
        data = r.json()

        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])

        # A partir daqui a rua exata não foi encontrada -- os parts vêm
        # de "logradouro, bairro, cidade, estado, Brazil".
        parts = endereco.split(",")

        bairro = parts[-4].strip() if len(parts) >= 4 else ""
        cidade = parts[-3].strip()
        estado = parts[-2].strip()

        # tentativa 2 — bairro + cidade + estado. Isso é o que faltava:
        # sem essa etapa intermediária, qualquer CEP cuja rua exata o
        # Nominatim não reconhecesse caía direto pro centro genérico da
        # cidade (ex: Praça da Sé em São Paulo) mesmo quando o bairro
        # certo (ex: Vila Prudente) era perfeitamente geocodificável.
        if bairro:
            params = {
                "q": f"{bairro}, {cidade}, {estado}, Brazil",
                "format": "json",
                "limit": 1
            }

            r = requests.get(url, params=params, headers=headers, timeout=5)
            data = r.json()

            if data:
                logger.warning(
                    f"[FRETE] CEP {cep}: rua exata não encontrada, "
                    f"geocodificado pelo bairro '{bairro}'"
                )
                return float(data[0]["lat"]), float(data[0]["lon"])

        # tentativa 3 — só cidade + estado (último recurso; impreciso,
        # pode cair no centro/marco-zero da cidade)
        params = {
            "q": f"{cidade}, {estado}, Brazil",
            "format": "json",
            "limit": 1
        }

        r = requests.get(url, params=params, headers=headers, timeout=5)
        data = r.json()

        if data:
            logger.warning(
                f"[FRETE] CEP {cep}: nem rua nem bairro encontrados, "
                f"geocodificado só pela cidade -- pode ficar impreciso"
            )
            return float(data[0]["lat"]), float(data[0]["lon"])

        logger.error(f"[FRETE] Não foi possível geocodificar CEP: {cep}")

        return None, None

    except Exception as e:
        logger.error(f"[FRETE] erro geocode {cep}: {e}")
        return None, None


@lru_cache(maxsize=2000)
def buscar_coordenadas_por_cidade(cidade, estado="", pais="Brasil"):
    """
    Geocodifica por cidade/estado/país (Nominatim), sem depender de CEP.
    Usado pro mapa de Clientes -- cobre tanto clientes brasileiros sem
    CEP exato quanto clientes de fora do Brasil (onde ViaCEP não serve).
    """
    try:
        partes = [p.strip() for p in (cidade, estado, pais) if p and p.strip()]
        if not partes:
            return None, None

        query = ", ".join(partes)

        url = "https://nominatim.openstreetmap.org/search"

        headers = {
            "User-Agent": "lazersport-clientes"
        }

        params = {
            "q": query,
            "format": "json",
            "limit": 1
        }

        r = requests.get(url, params=params, headers=headers, timeout=5)
        data = r.json()

        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])

        logger.error(f"[CLIENTES] Não foi possível geocodificar: {query}")

        return None, None

    except Exception as e:
        logger.error(f"[CLIENTES] erro geocode cidade '{cidade}': {e}")
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
    # Se o CEP for igual ao da empresa, frete simbólico
    cep_limpo_cliente = cep_cliente.replace("-", "")
    cep_limpo_empresa = CEP_EMPRESA.replace("-", "")

    if cep_limpo_cliente == cep_limpo_empresa:
        print("CEP do cliente é igual ao da empresa. Frete simbólico.")
        return 0.01, 0.0  # frete mínimo e distância 0 km

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
