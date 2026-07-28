import logging
import math
import re
from functools import lru_cache

import requests


logger = logging.getLogger(__name__)

CEP_EMPRESA = "02679-110"
VALOR_KM = 3.50

LAT_EMPRESA = -23.459889
LON_EMPRESA = -46.689654

HTTP_TIMEOUT = (3.05, 9)
USER_AGENT = (
    "LazerSportBrinquedos/1.0 "
    "(https://www.lazersport.com.br; contato@lazersport.com.br)"
)


class FreteCalculoError(ValueError):
    """Erro seguro e esperado durante o cálculo de frete."""


def _somente_digitos(valor):
    return "".join(char for char in str(valor or "") if char.isdigit())


def _request_json(url, *, params=None, headers=None):
    resposta = requests.get(
        url,
        params=params,
        headers=headers or {"User-Agent": USER_AGENT},
        timeout=HTTP_TIMEOUT,
    )
    resposta.raise_for_status()
    return resposta.json()


def cep_valido(cep):
    """Retorna True somente para um CEP brasileiro com oito dígitos."""
    return bool(re.fullmatch(r"\d{8}", _somente_digitos(cep)))


@lru_cache(maxsize=2000)
def buscar_dados_cep(cep):
    """Consulta o ViaCEP e devolve os campos normalizados do endereço."""
    cep_limpo = _somente_digitos(cep)
    if not cep_valido(cep_limpo):
        logger.warning("[FRETE] CEP inválido: %s", cep)
        return None

    try:
        data = _request_json(
            f"https://viacep.com.br/ws/{cep_limpo}/json/"
        )
    except (requests.RequestException, ValueError) as exc:
        logger.error("[FRETE] Falha no ViaCEP para %s: %s", cep_limpo, exc)
        return None

    if data.get("erro"):
        logger.warning("[FRETE] CEP não encontrado: %s", cep_limpo)
        return None

    return {
        "cep": cep_limpo,
        "rua": (data.get("logradouro") or "").strip(),
        "bairro": (data.get("bairro") or "").strip(),
        "cidade": (data.get("localidade") or "").strip(),
        "estado": (data.get("uf") or "").strip(),
    }


def buscar_endereco(cep):
    dados = buscar_dados_cep(cep)
    if not dados:
        return None

    return ", ".join(
        parte
        for parte in (
            dados["rua"],
            dados["bairro"],
            dados["cidade"],
            dados["estado"],
            "Brasil",
        )
        if parte
    )


@lru_cache(maxsize=2000)
def buscar_coordenadas(cep, numero=""):
    """
    Geocodifica o destino por níveis de precisão.

    Tenta endereço com número, rua, bairro e somente então cidade. As
    consultas usam um User-Agent identificável e ficam armazenadas em cache.
    """
    dados = buscar_dados_cep(cep)
    if not dados or not dados.get("cidade"):
        return None, None

    rua = dados["rua"]
    bairro = dados["bairro"]
    cidade = dados["cidade"]
    estado = dados["estado"]
    numero = str(numero or "").strip()

    consultas = []
    if rua and numero:
        consultas.append((
            "endereco",
            f"{rua}, {numero}, {bairro}, {cidade}, {estado}, Brasil",
        ))
    if rua:
        consultas.append((
            "rua",
            f"{rua}, {bairro}, {cidade}, {estado}, Brasil",
        ))
    if bairro:
        consultas.append((
            "bairro",
            f"{bairro}, {cidade}, {estado}, Brasil",
        ))
    consultas.append(("cidade", f"{cidade}, {estado}, Brasil"))

    for nivel, consulta in consultas:
        try:
            resultados = _request_json(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": consulta,
                    "format": "jsonv2",
                    "limit": 1,
                    "countrycodes": "br",
                    "addressdetails": 1,
                },
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept-Language": "pt-BR,pt;q=0.9",
                },
            )
        except (requests.RequestException, ValueError) as exc:
            logger.warning(
                "[FRETE] Nominatim indisponível para %s: %s",
                consulta,
                exc,
            )
            continue

        if not resultados:
            continue

        try:
            latitude = float(resultados[0]["lat"])
            longitude = float(resultados[0]["lon"])
        except (KeyError, TypeError, ValueError):
            continue

        if nivel != "endereco":
            logger.warning(
                "[FRETE] CEP %s geocodificado no nível %s.",
                cep,
                nivel,
            )

        return latitude, longitude

    logger.error("[FRETE] Não foi possível geocodificar o CEP %s.", cep)
    return None, None


@lru_cache(maxsize=2000)
def buscar_coordenadas_por_cidade(cidade, estado="", pais="Brasil"):
    partes = [
        str(parte).strip()
        for parte in (cidade, estado, pais)
        if parte and str(parte).strip()
    ]
    if not partes:
        return None, None

    try:
        resultados = _request_json(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": ", ".join(partes),
                "format": "jsonv2",
                "limit": 1,
                "addressdetails": 1,
            },
            headers={
                "User-Agent": USER_AGENT,
                "Accept-Language": "pt-BR,pt;q=0.9",
            },
        )
    except (requests.RequestException, ValueError) as exc:
        logger.warning("[CLIENTES] Falha ao geocodificar cidade: %s", exc)
        return None, None

    if not resultados:
        return None, None

    try:
        return (
            float(resultados[0]["lat"]),
            float(resultados[0]["lon"]),
        )
    except (KeyError, TypeError, ValueError):
        return None, None


def distancia_km(lat1, lon1, lat2, lon2):
    """Distância geodésica em linha reta; usada somente como fallback."""
    if None in (lat1, lon1, lat2, lon2):
        raise FreteCalculoError(
            "Não foi possível localizar o endereço informado."
        )

    raio_terra_km = 6371.0088
    dlat = math.radians(float(lat2) - float(lat1))
    dlon = math.radians(float(lon2) - float(lon1))
    lat1_rad = math.radians(float(lat1))
    lat2_rad = math.radians(float(lat2))

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_rad)
        * math.cos(lat2_rad)
        * math.sin(dlon / 2) ** 2
    )
    return raio_terra_km * 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a),
    )


@lru_cache(maxsize=2000)
def buscar_rota_rodoviaria(lat1, lon1, lat2, lon2):
    """
    Consulta uma rota de automóvel e devolve distância, duração e traçado.

    As coordenadas do GeoJSON permanecem no padrão [longitude, latitude],
    que é convertido para Leaflet apenas no navegador.
    """
    coordenadas = (
        f"{float(lon1):.6f},{float(lat1):.6f};"
        f"{float(lon2):.6f},{float(lat2):.6f}"
    )

    try:
        data = _request_json(
            f"https://router.project-osrm.org/route/v1/driving/{coordenadas}",
            params={
                "overview": "simplified",
                "geometries": "geojson",
                "steps": "false",
                "alternatives": "false",
            },
        )
    except (requests.RequestException, ValueError) as exc:
        logger.warning("[FRETE] Serviço de rotas indisponível: %s", exc)
        return None

    rotas = data.get("routes") or []
    if data.get("code") != "Ok" or not rotas:
        logger.warning("[FRETE] Nenhuma rota rodoviária encontrada.")
        return None

    rota = rotas[0]
    try:
        distancia = float(rota["distance"]) / 1000
        duracao = max(1, math.ceil(float(rota["duration"]) / 60))
        geometria = rota["geometry"]["coordinates"]
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None

    return {
        "distancia_km": round(distancia, 2),
        "tempo_estimado_min": duracao,
        "geometria": geometria,
        "fonte": "rota_rodoviaria",
        "estimado": False,
    }


def calcular_frete_detalhado(
    cep_cliente,
    numero_cliente="",
    lat_origem=LAT_EMPRESA,
    lon_origem=LON_EMPRESA,
):
    """
    Calcula o frete com rota rodoviária e fornece todos os dados do mapa.

    Quando a API de rotas estiver temporariamente indisponível, usa distância
    geográfica identificada explicitamente como estimativa. Nunca transforma
    falha de endereço em frete zero.
    """
    cep_limpo_cliente = _somente_digitos(cep_cliente)
    cep_limpo_empresa = _somente_digitos(CEP_EMPRESA)

    if not cep_valido(cep_limpo_cliente):
        raise FreteCalculoError("Informe um CEP válido com oito dígitos.")

    lat_destino, lon_destino = buscar_coordenadas(
        cep_limpo_cliente,
        str(numero_cliente or "").strip(),
    )
    if lat_destino is None or lon_destino is None:
        raise FreteCalculoError(
            "Não foi possível localizar esse endereço. "
            "Confira o CEP e o número."
        )

    origem = {
        "lat": float(lat_origem),
        "lng": float(lon_origem),
    }
    destino = {
        "lat": float(lat_destino),
        "lng": float(lon_destino),
    }

    if cep_limpo_cliente == cep_limpo_empresa:
        rota = {
            "distancia_km": 0.0,
            "tempo_estimado_min": 0,
            "geometria": [
                [origem["lng"], origem["lat"]],
                [destino["lng"], destino["lat"]],
            ],
            "fonte": "mesmo_cep",
            "estimado": False,
        }
        valor_frete = 0.01
    else:
        rota = buscar_rota_rodoviaria(
            origem["lat"],
            origem["lng"],
            destino["lat"],
            destino["lng"],
        )

        if rota is None:
            distancia_reta = distancia_km(
                origem["lat"],
                origem["lng"],
                destino["lat"],
                destino["lng"],
            )
            rota = {
                "distancia_km": round(distancia_reta, 2),
                "tempo_estimado_min": None,
                "geometria": [
                    [origem["lng"], origem["lat"]],
                    [destino["lng"], destino["lat"]],
                ],
                "fonte": "linha_reta",
                "estimado": True,
            }

        valor_frete = round(rota["distancia_km"] * VALOR_KM, 2)

    return {
        "valor_frete": valor_frete,
        "distancia_km": rota["distancia_km"],
        "tempo_estimado_min": rota["tempo_estimado_min"],
        "origem": origem,
        "destino": destino,
        "geometria": rota["geometria"],
        "fonte": rota["fonte"],
        "estimado": rota["estimado"],
    }


def calcular_frete_por_cep(cep_cliente, numero_cliente=""):
    """
    Compatibilidade com o restante do projeto.

    Novos pontos devem preferir calcular_frete_detalhado(), mas este retorno
    em tupla mantém funcionando todo código que espera (valor, distância).
    """
    resultado = calcular_frete_detalhado(
        cep_cliente,
        numero_cliente,
    )
    return resultado["valor_frete"], resultado["distancia_km"]
