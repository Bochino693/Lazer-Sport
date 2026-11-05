"""Arquivo grande de jogo em PEDAÇOS, no armazenamento que o site já tem (o Cloudinary).

O PROBLEMA. Um disco de PS1 tem de 300 a 700 MB, e o Cloudinary aceita, no
plano gratuito, no máximo 10 MB por arquivo que não é imagem. Sem outro
armazenamento (o S3/R2 de `core/armazenamento_grande.py`), o .bin não cabia
-- e o painel barrava o disco ("o armazenamento aceita até 200 MB").

A SAÍDA. O navegador de quem cadastra corta cada arquivo em pedaços de até
`JOGOS_PEDACO_MB` (padrão 9 MB) e manda cada pedaço DIRETO para o Cloudinary
(a API de envio aceita o navegador), com uma assinatura que o site gera por
pedaço -- o arquivo não passa pelo Render. A resposta do Cloudinary vem
assinada também; o site confere cada uma antes de guardar a lista de
pedaços. Na hora de jogar, a página do emulador baixa os pedaços e junta na
memória, na ordem: o emulador recebe o .bin inteiro, byte a byte.

SEM O CLOUDINARY (no computador de quem desenvolve, nos testes) os pedaços
vão para o próprio site, que guarda no armazenamento padrão. O caminho é o
mesmo; só muda o endereço de cada envio.

O CUSTO. O Cloudinary gratuito tem 25 créditos por mês (1 crédito = 1 GB
guardado ou 1 GB baixado). Um disco de 500 MB ocupa meio crédito guardado, e
cada partida baixa mais meio. Para muitos jogos de disco ou muitas partidas,
o R2 (`armazenamento_grande`) não cobra pelo download.
"""

from __future__ import annotations

import time

from django.conf import settings
from django.core import signing

MB = 1024 * 1024
SAL = "core.jogos.emulador.pedaco"


def tamanho_do_pedaco():
    """Bytes por pedaço (JOGOS_PEDACO_MB, padrão 9: o Cloudinary gratuito aceita até 10 MB)."""
    try:
        valor = float(getattr(settings, "JOGOS_PEDACO_MB", 9) or 9)
    except (TypeError, ValueError):
        valor = 9
    return max(16 * 1024, int(valor * MB))


def limite_por_arquivo():
    """O teto de cada arquivo do jogo em pedaços (JOGOS_PEDACOS_MAX_MB, padrão 1000: um CD cabe)."""
    try:
        return max(1024, int(float(getattr(settings, "JOGOS_PEDACOS_MAX_MB", 1000)) * MB))
    except (TypeError, ValueError):
        return 1000 * MB


def destino():
    """"cloudinary" (o navegador manda direto para lá) ou "site" (o site guarda os pedaços)."""
    forcado = str(getattr(settings, "JOGOS_PEDACOS_DESTINO", "") or "").strip().lower()
    if forcado in ("cloudinary", "site"):
        return forcado
    config = getattr(settings, "CLOUDINARY_STORAGE", {}) or {}
    padrao = settings.STORAGES.get("default", {}).get("BACKEND", "")
    if all(config.get(c) for c in ("CLOUD_NAME", "API_KEY", "API_SECRET")) and "cloudinary" in padrao.lower():
        return "cloudinary"
    return "site"


def dividir(tamanho):
    """[(início, fim)] de cada pedaço."""
    passo = tamanho_do_pedaco()
    return [(inicio, min(inicio + passo, tamanho)) for inicio in range(0, tamanho, passo)]


# ---------------------------------------------------------------- Cloudinary


def _config_cloudinary():
    config = getattr(settings, "CLOUDINARY_STORAGE", {}) or {}
    return config.get("CLOUD_NAME", ""), config.get("API_KEY", ""), config.get("API_SECRET", "")


def envio_cloudinary(public_id):
    """O que o navegador manda junto com o pedaço para a API de envio do Cloudinary (assinado aqui)."""
    from cloudinary.utils import api_sign_request

    nuvem, chave, segredo = _config_cloudinary()
    momento = int(time.time())
    parametros = {"public_id": public_id, "timestamp": momento}
    base = str(getattr(settings, "JOGOS_CLOUDINARY_API", "") or "https://api.cloudinary.com").rstrip("/")
    return {
        "url": f"{base}/v1_1/{nuvem}/raw/upload",
        "metodo": "POST",
        "campos": {**parametros, "api_key": chave, "signature": api_sign_request(parametros, segredo)},
    }


def conferir_cloudinary(resposta, public_id, tamanho):
    """A resposta do Cloudinary a um pedaço é dele mesmo (assinatura) e do tamanho certo? -> {url, tamanho, id}."""
    from cloudinary.utils import verify_api_response_signature

    if not isinstance(resposta, dict):
        raise ValueError("resposta vazia")
    if resposta.get("public_id") != public_id:
        raise ValueError("pedaço trocado")
    if int(resposta.get("bytes", -1)) != tamanho:
        raise ValueError("pedaço chegou com outro tamanho")
    if not verify_api_response_signature(public_id, resposta.get("version"), resposta.get("signature")):
        raise ValueError("resposta sem a assinatura do Cloudinary")
    url = str(resposta.get("secure_url") or "")
    # http só com a API apontada para um servidor local (o teste de ponta a ponta)
    local = str(getattr(settings, "JOGOS_CLOUDINARY_API", "") or "").startswith("http://")
    if not (url.startswith("https://") or (local and url.startswith("http://"))):
        raise ValueError("endereço do pedaço inválido")
    return {"url": url, "tamanho": tamanho, "id": public_id}


# ---------------------------------------------------------------- no site


def envio_site(url_do_painel, jogo_id, caminho, tamanho):
    """O pedaço vai para o próprio site: o painel guarda no armazenamento padrão."""
    ficha = signing.dumps({"jogo": jogo_id, "caminho": caminho, "tamanho": tamanho}, salt=SAL)
    return {"url": url_do_painel, "metodo": "POST", "campos": {"action": "emulador_pedaco", "pedaco": ficha}}


def guardar_no_site(ficha, arquivo):
    """Guarda um pedaço que veio para o site; devolve a resposta no formato da do Cloudinary."""
    from django.core.files.storage import default_storage

    dados = signing.loads(ficha, salt=SAL, max_age=8 * 3600)
    if arquivo.size != dados["tamanho"]:
        raise ValueError("O pedaço chegou com outro tamanho.")
    nome = default_storage.save(dados["caminho"], arquivo)
    return dados["jogo"], {
        "public_id": nome,
        "bytes": arquivo.size,
        "secure_url": default_storage.url(nome),
        "signature": signing.dumps({"nome": nome, "bytes": arquivo.size}, salt=SAL),
        "version": 0,
    }


def conferir_site(resposta, caminho, tamanho):
    from django.core.files.storage import default_storage

    if not isinstance(resposta, dict):
        raise ValueError("resposta vazia")
    try:
        dados = signing.loads(str(resposta.get("signature") or ""), salt=SAL, max_age=8 * 3600)
    except signing.BadSignature as exc:
        raise ValueError("resposta sem a assinatura do site") from exc
    nome = dados["nome"]
    # o armazenamento pode acrescentar letras ao nome; a pasta e o começo têm de bater
    if not nome.startswith(caminho.rsplit("/", 1)[0] + "/") or dados["bytes"] != tamanho:
        raise ValueError("pedaço trocado")
    if not default_storage.exists(nome) or default_storage.size(nome) != tamanho:
        raise ValueError("o pedaço não está guardado")
    return {"url": default_storage.url(nome), "tamanho": tamanho, "id": nome, "local": True}


# ---------------------------------------------------------------- leitura e limpeza


def ler(pedacos, inicio, quantos):
    """Um trecho do arquivo inteiro, lendo dos pedaços (para conferir o conteúdo depois do envio)."""
    from django.core.files.storage import default_storage

    saida = bytearray()
    deslocamento = 0
    fim = inicio + quantos
    for pedaco in pedacos:
        tamanho = pedaco["tamanho"]
        comeco, termino = deslocamento, deslocamento + tamanho
        deslocamento = termino
        if termino <= inicio or comeco >= fim:
            continue
        de, ate = max(inicio, comeco) - comeco, min(fim, termino) - comeco
        if pedaco.get("local"):
            with default_storage.open(pedaco["id"]) as arquivo:
                arquivo.seek(de)
                saida += arquivo.read(ate - de)
        else:
            import requests

            resposta = requests.get(pedaco["url"], headers={"Range": f"bytes={de}-{ate - 1}"}, timeout=20)
            resposta.raise_for_status()
            corpo = resposta.content
            saida += corpo if resposta.status_code == 206 else corpo[de:ate]
    return bytes(saida)


def apagar(pedacos):
    """Apaga os pedaços (melhor esforço; quem chama registra a falha)."""
    from django.core.files.storage import default_storage

    nuvem = [p["id"] for p in pedacos if not p.get("local")]
    for pedaco in pedacos:
        if pedaco.get("local"):
            default_storage.delete(pedaco["id"])
    if nuvem:
        import cloudinary.api

        for i in range(0, len(nuvem), 100):
            cloudinary.api.delete_resources(nuvem[i:i + 100], resource_type="raw")
