import logging
import math
import re
from functools import lru_cache

import requests


logger = logging.getLogger(__name__)

CEP_EMPRESA = "02679-110"
VALOR_KM = 3.50

# Ponto de partida da empresa: origem do frete E alfinete da fábrica no
# mapa. Estes valores são só o último recurso -- o endereço de verdade
# fica em EnderecoEmpresa, editável pelo admin. Use origem_da_empresa()
# em vez de ler as constantes direto: era daí que vinha a incoerência de
# o mapa mostrar um lugar e o frete calcular de outro.
LAT_EMPRESA = -23.459889
LON_EMPRESA = -46.689654


def origem_da_empresa():
    """(latitude, longitude) de onde a empresa despacha e aparece no mapa.

    Lê o cadastro do admin; sem cadastro, cai nas constantes. Uma função só
    para os dois usos: antes o mapa lia EnderecoEmpresa e o frete lia a
    constante, então corrigir o alfinete no admin não corrigia o frete --
    e ninguém percebia, porque os dois números continuavam plausíveis.
    """
    try:
        from .models import EnderecoEmpresa

        endereco = (
            EnderecoEmpresa.objects
            .filter(ativo=True, latitude__isnull=False, longitude__isnull=False)
            .first()
        )
        if endereco:
            return float(endereco.latitude), float(endereco.longitude)
    except Exception:  # noqa: BLE001 - frete nunca cai por causa do cadastro
        logger.warning("[FRETE] Não foi possível ler EnderecoEmpresa.", exc_info=True)

    return LAT_EMPRESA, LON_EMPRESA

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


# Níveis de precisão, do melhor para o pior. Guardar qual deles foi
# alcançado é o que evita o defeito antigo: a busca caía de endereço para
# rua, de rua para bairro e de bairro para o centro da cidade, e o
# resultado era gravado como se fosse o endereço exato. Em São Paulo, o
# nível "cidade" fica na Sé -- quilômetros de distância de quase qualquer
# endereço real.
PRECISAO_EXATO = "exato"
PRECISAO_RUA = "rua"
PRECISAO_BAIRRO = "bairro"
PRECISAO_CIDADE = "cidade"

# Acima deste nível a coordenada não representa o endereço, e sim uma
# região. Serve para desenhar um mapa aproximado, nunca para dizer "é aqui".
PRECISAO_CONFIAVEL = (PRECISAO_EXATO, PRECISAO_RUA)


def _consultar_nominatim(params):
    """Uma consulta ao Nominatim, já com cabeçalhos e tratamento de erro."""
    try:
        return _request_json(
            "https://nominatim.openstreetmap.org/search",
            params={
                "format": "jsonv2",
                "limit": 1,
                "countrycodes": "br",
                "addressdetails": 1,
                **params,
            },
            headers={
                "User-Agent": USER_AGENT,
                "Accept-Language": "pt-BR,pt;q=0.9",
            },
        )
    except (requests.RequestException, ValueError) as exc:
        logger.warning("[GEO] Nominatim indisponível para %s: %s", params, exc)
        return None


def _ler_ponto(resultados):
    if not resultados:
        return None
    try:
        primeiro = resultados[0]
        return (
            float(primeiro["lat"]),
            float(primeiro["lon"]),
            (primeiro.get("address") or {}),
        )
    except (KeyError, IndexError, TypeError, ValueError):
        return None


@lru_cache(maxsize=2000)
def geocodificar_endereco(cep, numero=""):
    """Devolve (latitude, longitude, precisao) para um CEP e número.

    A consulta é estruturada (street/city/state/postalcode em campos
    separados) e não um texto único: para endereço brasileiro o Nominatim
    acerta bem mais assim do que recebendo tudo espremido em ``q``.

    A precisão nunca é presumida. Só devolve "exato" quando o resultado
    volta com o número da casa -- se a rua não tem numeração mapeada, o
    Nominatim responde com o meio da rua, e numa via longa isso já são
    centenas de metros.
    """
    dados = buscar_dados_cep(cep)
    if not dados or not dados.get("cidade"):
        return None, None, None

    rua = dados["rua"]
    bairro = dados["bairro"]
    cidade = dados["cidade"]
    estado = dados["estado"]
    numero = str(numero or "").strip()
    cep_limpo = _somente_digitos(cep)

    tentativas = []

    if rua and numero:
        # O Nominatim espera "numero nome-da-rua" no campo street.
        tentativas.append((PRECISAO_EXATO, {
            "street": f"{numero} {rua}",
            "city": cidade,
            "state": estado,
            "postalcode": cep_limpo,
            "country": "Brasil",
        }))

    if rua:
        tentativas.append((PRECISAO_RUA, {
            "street": rua,
            "city": cidade,
            "state": estado,
            "postalcode": cep_limpo,
            "country": "Brasil",
        }))

    if bairro:
        tentativas.append((PRECISAO_BAIRRO, {
            "q": f"{bairro}, {cidade}, {estado}, Brasil",
        }))

    tentativas.append((PRECISAO_CIDADE, {
        "q": f"{cidade}, {estado}, Brasil",
    }))

    for nivel, params in tentativas:
        ponto = _ler_ponto(_consultar_nominatim(params))
        if not ponto:
            continue

        latitude, longitude, endereco = ponto

        # Pedimos o número, mas veio a rua inteira: é rua, não é exato.
        if nivel == PRECISAO_EXATO and not endereco.get("house_number"):
            logger.info(
                "[GEO] CEP %s número %s: sem numeração no mapa, caiu para rua.",
                cep_limpo, numero,
            )
            nivel = PRECISAO_RUA

        if nivel not in PRECISAO_CONFIAVEL:
            logger.warning(
                "[GEO] CEP %s resolvido só no nível %s -- o ponto é a região, "
                "não o endereço.",
                cep_limpo, nivel,
            )

        return latitude, longitude, nivel

    logger.error("[GEO] Não foi possível geocodificar o CEP %s.", cep_limpo)
    return None, None, None


def buscar_coordenadas(cep, numero=""):
    """Compatibilidade: só as coordenadas, sem o nível de precisão.

    Usada pelo frete, que precisa de um ponto de destino mesmo quando ele
    é aproximado -- um frete estimado é melhor do que recusar a venda.
    Quem coloca alfinete em mapa deve usar geocodificar_endereco e olhar a
    precisão antes de afirmar onde o lugar fica.
    """
    latitude, longitude, _ = geocodificar_endereco(cep, numero)
    return latitude, longitude


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
    lat_origem=None,
    lon_origem=None,
):
    """
    Calcula o frete com rota rodoviária e fornece todos os dados do mapa.

    Quando a API de rotas estiver temporariamente indisponível, usa distância
    geográfica identificada explicitamente como estimativa. Nunca transforma
    falha de endereço em frete zero.
    """
    # Resolvido aqui, e não no valor padrão do parâmetro: padrão de função
    # é avaliado uma vez, na importação do módulo, e congelaria a origem
    # até o processo reiniciar -- corrigir o endereço no admin não teria
    # efeito nenhum no frete.
    if lat_origem is None or lon_origem is None:
        lat_padrao, lon_padrao = origem_da_empresa()
        lat_origem = lat_padrao if lat_origem is None else lat_origem
        lon_origem = lon_padrao if lon_origem is None else lon_origem

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
