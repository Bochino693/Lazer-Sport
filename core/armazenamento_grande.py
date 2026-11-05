"""Onde moram os arquivos grandes dos jogos de console (discos de PS1...).

POR QUE UM ARMAZENAMENTO À PARTE. Um disco de PlayStation tem de 300 a 700
MB. O Cloudinary do site aceita, no plano gratuito, 10 MB por arquivo que
não é imagem; e um arquivo desses passando pelo Render (o navegador manda
para o servidor, o servidor manda para o armazenamento) levaria minutos
segurando um processo do site. Aqui o caminho é outro: o navegador de quem
cadastra manda cada arquivo DIRETO para um balde compatível com S3
(Cloudflare R2, Backblaze B2, AWS S3, o S3 do Supabase), por um link
assinado que vale poucas horas. O site só confere depois -- o tamanho e o
começo de cada arquivo, por leitura de trecho -- sem baixar o disco.

O QUE PRECISA. As cinco variáveis abaixo, no Render. Sem elas, os jogos de
console continuam funcionando com o armazenamento de sempre, no limite dele
(cartucho de NES, Game Boy... cabe; disco de PS1, não). O passo a passo
(Cloudflare R2, CORS do balde) está no LEIA-ME.

  JOGOS_S3_ENDPOINT     https://<conta>.r2.cloudflarestorage.com
  JOGOS_S3_BUCKET       o nome do balde
  JOGOS_S3_ACCESS_KEY   a chave de acesso (só leitura e escrita neste balde)
  JOGOS_S3_SECRET_KEY   o segredo da chave
  JOGOS_S3_URL_PUBLICA  o endereço público do balde (https://pub-xxx.r2.dev
                        ou um domínio de vocês) -- é por ele que o jogo baixa

POR QUE O ENDEREÇO PÚBLICO, E NÃO LINK ASSINADO PARA BAIXAR. O emulador pede
o arquivo principal primeiro com HEAD, e link assinado de S3 vale só para o
método com que foi assinado (GET): o HEAD volta 403 e o jogo não abre. E um
endereço fixo deixa o navegador guardar o disco em cache entre uma visita e
outra -- link assinado muda a cada página e baixaria tudo de novo. As chaves
levam um código aleatório no caminho: o endereço não se adivinha, e o balde
público do R2 não lista o que tem dentro.
"""

from __future__ import annotations

from urllib.parse import quote

from django.conf import settings

CAMPOS = (
    "JOGOS_S3_ENDPOINT",
    "JOGOS_S3_BUCKET",
    "JOGOS_S3_ACCESS_KEY",
    "JOGOS_S3_SECRET_KEY",
    "JOGOS_S3_URL_PUBLICA",
)

#: Quanto tempo o link de envio vale (um disco grande numa internet lenta leva).
VALIDADE_DO_ENVIO = 6 * 3600

#: O tipo com que o navegador envia (o link é assinado para este tipo).
TIPO_DO_ENVIO = "application/octet-stream"


def _config():
    return {campo: str(getattr(settings, campo, "") or "").strip() for campo in CAMPOS}


def configurado():
    """As cinco variáveis estão preenchidas."""
    return all(_config().values())


def faltando():
    """Os nomes das variáveis que faltam (para o painel dizer o que preencher)."""
    return [campo for campo, valor in _config().items() if not valor]


def limite_por_arquivo():
    """O teto de cada arquivo neste armazenamento, em bytes (JOGOS_S3_MAX_MB, padrão 2000)."""
    try:
        return max(1, int(getattr(settings, "JOGOS_S3_MAX_MB", 2000))) * 1024 * 1024
    except (TypeError, ValueError):
        return 2000 * 1024 * 1024


_cliente_cache = {}


def _cliente():
    config = _config()
    chave = tuple(config.values())
    cliente = _cliente_cache.get(chave)
    if cliente is None:
        import boto3
        from botocore.config import Config

        cliente = boto3.client(
            "s3",
            endpoint_url=config["JOGOS_S3_ENDPOINT"],
            aws_access_key_id=config["JOGOS_S3_ACCESS_KEY"],
            aws_secret_access_key=config["JOGOS_S3_SECRET_KEY"],
            region_name=str(getattr(settings, "JOGOS_S3_REGIAO", "") or "auto"),
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                retries={"max_attempts": 3, "mode": "standard"},
                connect_timeout=5,
                read_timeout=20,
            ),
        )
        _cliente_cache.clear()
        _cliente_cache[chave] = cliente
    return cliente


def _balde():
    return _config()["JOGOS_S3_BUCKET"]


def url_para_enviar(chave):
    """O link assinado para o navegador mandar o arquivo (PUT), válido por algumas horas."""
    return _cliente().generate_presigned_url(
        "put_object",
        Params={"Bucket": _balde(), "Key": chave, "ContentType": TIPO_DO_ENVIO},
        ExpiresIn=VALIDADE_DO_ENVIO,
        HttpMethod="PUT",
    )


def url_publica(chave):
    """O endereço fixo por onde o jogo baixa o arquivo."""
    base = _config()["JOGOS_S3_URL_PUBLICA"].rstrip("/")
    return f"{base}/{quote(chave, safe='/')}"


def tamanho(chave):
    """O tamanho do arquivo no balde, ou None se ele não está lá."""
    from botocore.exceptions import ClientError

    try:
        resposta = _cliente().head_object(Bucket=_balde(), Key=chave)
    except ClientError as erro:
        if str(erro.response.get("Error", {}).get("Code")) in ("404", "NoSuchKey", "NotFound"):
            return None
        raise
    return int(resposta["ContentLength"])


def ler(chave, inicio, quantos):
    """Um trecho do arquivo (leitura por faixa: não baixa o arquivo inteiro)."""
    if quantos <= 0:
        return b""
    resposta = _cliente().get_object(Bucket=_balde(), Key=chave, Range=f"bytes={inicio}-{inicio + quantos - 1}")
    return resposta["Body"].read()


def apagar(chaves):
    """Apaga as chaves do balde (melhor esforço, de mil em mil)."""
    chaves = [c for c in chaves if c]
    for i in range(0, len(chaves), 1000):
        lote = chaves[i:i + 1000]
        _cliente().delete_objects(Bucket=_balde(), Delete={"Objects": [{"Key": c} for c in lote], "Quiet": True})


def entrada_remota(nome, chave, tamanho_conhecido):
    """Uma `Entrada` (de `core.jogos_emulador`) que lê o arquivo do balde por trechos.

    O começo (onde mora o que reconhece o sistema) vem numa leitura só e fica
    guardado; o resto, se alguém pedir (o fim de um .zip), vem por faixa.
    """
    from .jogos_emulador import CABECA, Entrada

    guardado = {}

    def ler_trecho(inicio, quantos):
        if inicio + quantos <= CABECA:
            if "cabeca" not in guardado:
                guardado["cabeca"] = ler(chave, 0, min(CABECA, tamanho_conhecido))
            return guardado["cabeca"][inicio:inicio + quantos]
        return ler(chave, inicio, quantos)

    return Entrada(nome, int(tamanho_conhecido), ler_trecho, chave)


def diagnosticar(chave, origem_do_site, chave_principal=None):
    """Confere o arquivo como o navegador do visitante vai pedir; devolve os problemas ([] = tudo certo).

    Dois erros de configuração deixam o jogo abrir SEM as faixas, sem aviso
    nenhum na tela (o emulador só pula o arquivo que não veio): o balde sem
    acesso público (403) e o balde sem a regra de CORS para o site (o
    navegador baixa e descarta). Aqui o painel pergunta do mesmo jeito que o
    visitante pergunta -- com o cabeçalho Origin do site -- e diz o que ligar.
    """
    import requests

    url = url_publica(chave)
    cabecalhos = {"Origin": origem_do_site}
    try:
        # o emulador baixa as faixas com GET: pede o primeiro byte, do mesmo jeito
        resposta = requests.get(url, headers={**cabecalhos, "Range": "bytes=0-0"}, timeout=6, allow_redirects=True)
    except requests.RequestException as erro:
        return [f"O endereço público do balde não respondeu ({erro.__class__.__name__}): confira JOGOS_S3_URL_PUBLICA."]
    if resposta.status_code not in (200, 206):
        return [
            f"O endereço público do balde respondeu {resposta.status_code}: ligue o acesso público do balde "
            "(no Cloudflare R2: Settings > Public access) e confira JOGOS_S3_URL_PUBLICA."
        ]
    permitido = resposta.headers.get("Access-Control-Allow-Origin", "")
    if permitido not in ("*", origem_do_site):
        return [
            f"O balde não deixa o site ({origem_do_site}) baixar os arquivos: falta a regra de CORS do balde "
            "(passo a passo no LEIA-ME). Sem ela, o jogo abre sem as faixas."
        ]
    if not chave_principal:
        return []  # o arquivo que o emulador abre primeiro é o índice, que o site serve
    try:
        # o arquivo que o emulador abre primeiro (a ROM, o .pbp) ele pede antes com HEAD
        cabeca = requests.head(url_publica(chave_principal), headers=cabecalhos, timeout=6, allow_redirects=True)
    except requests.RequestException:
        cabeca = None
    if cabeca is None or cabeca.status_code != 200:
        return ["O balde não responde ao pedido HEAD: jogo de um arquivo só (ROM, .pbp) não abre. Confira o acesso público do balde."]
    return []
