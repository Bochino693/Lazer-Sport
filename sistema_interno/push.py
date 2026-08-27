"""Notificação no celular de quem instalou o painel.

O QUE ISSO RESOLVE. O painel avisa muito bem quem está com ele aberto --
as bolinhas se atualizam sozinhas. Mas quem está na estrada, montando um
brinquedo, não está com o painel aberto: para essa pessoa o aviso só
existe se o telefone tocar. É o caso do orçamento que o cliente acabou de
aprovar, que precisa virar agenda antes de a data ser vendida de novo.

COMO FUNCIONA, EM UMA FRASE. O navegador de cada pessoa dá ao painel um
endereço próprio ("endpoint") no serviço do fabricante -- Google para o
Android, Apple para o iPhone. Mandar um aviso é fazer um POST nesse
endereço, com o texto CIFRADO de ponta a ponta: o serviço do fabricante
entrega, mas não lê.

POR QUE ESCRITO AQUI, E NÃO COM UMA BIBLIOTECA. O que o padrão pede --
ECDH em P-256, HKDF-SHA256 e AES-128-GCM (RFC 8291), mais um JWT ES256
para se identificar (RFC 8292) -- já está inteiro em `cryptography` e
`PyJWT`, que o projeto usa desde sempre. Trazer três dependências novas
para uma hospedagem que já falhou em `migrate` seria trocar um risco que
não existe por outro que existe. Os vetores de teste do próprio RFC 8291
estão na suíte: se algum dia isto parar de cifrar certo, o teste avisa
antes do celular de alguém.

O IPHONE TEM UMA REGRA A MAIS. Só entrega notificação para site que a
pessoa adicionou à tela de início -- no Safari comum não existe. É por
isso que a tela pede a instalação antes de oferecer o aviso, em vez de
mostrar um botão que não faria nada.
"""

import base64
import json
import logging
import os
import time
from urllib.parse import urlsplit

import jwt
import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings

log = logging.getLogger(__name__)

#: Tempo de vida do JWT que nos identifica ao serviço do fabricante. O
#: padrão recusa acima de 24h; 12h dá folga sem beirar o limite.
VALIDADE_DO_JWT = 12 * 60 * 60

#: Um registro só por mensagem: um aviso não chega perto de 4 KB.
TAMANHO_DE_REGISTRO = 4096

#: Quanto tempo esperar pelo serviço do fabricante. Avisar é importante,
#: mas nunca ao ponto de segurar a tela de quem está trabalhando.
ESPERA = 8


# ----------------------------------------------------------------------
# base64url sem "=" -- é como o padrão inteiro conversa.
# ----------------------------------------------------------------------
def b64(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode("ascii")


def deb64(texto: str) -> bytes:
    texto = (texto or "").strip()
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


# ----------------------------------------------------------------------
# As chaves da aplicação (VAPID)
# ----------------------------------------------------------------------
def chave_privada():
    """A chave da aplicação, lida da hospedagem.

    Sem ela nada é enviado -- e isso é silêncio de propósito: uma
    hospedagem sem a variável configurada não pode virar erro em toda tela
    que salva alguma coisa.
    """
    bruto = (getattr(settings, "PUSH_VAPID_PRIVADA", "") or "").strip()
    if not bruto:
        return None
    try:
        segredo = deb64(bruto)
        return ec.derive_private_key(
            int.from_bytes(segredo, "big"), ec.SECP256R1()
        )
    except Exception:
        log.exception("PUSH_VAPID_PRIVADA não é uma chave P-256 válida")
        return None


def chave_publica() -> str:
    """A chave que o navegador precisa para se inscrever."""
    configurada = (getattr(settings, "PUSH_VAPID_PUBLICA", "") or "").strip()
    if configurada:
        return configurada

    privada = chave_privada()
    if privada is None:
        return ""
    return b64(_bytes_publicos(privada.public_key()))


def configurado() -> bool:
    return bool(chave_privada() and chave_publica())


def gerar_par():
    """Gera um par novo. Usado uma vez, para preencher a hospedagem."""
    privada = ec.generate_private_key(ec.SECP256R1())
    segredo = privada.private_numbers().private_value.to_bytes(32, "big")
    return b64(segredo), b64(_bytes_publicos(privada.public_key()))


def _bytes_publicos(publica) -> bytes:
    return publica.public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )


# ----------------------------------------------------------------------
# O cabeçalho que nos identifica (RFC 8292)
# ----------------------------------------------------------------------
def cabecalho_vapid(endpoint: str) -> dict:
    privada = chave_privada()
    if privada is None:
        return {}

    partes = urlsplit(endpoint)
    origem = f"{partes.scheme}://{partes.netloc}"
    contato = (getattr(settings, "PUSH_CONTATO", "") or "").strip()
    if not contato:
        contato = "mailto:" + (
            getattr(settings, "EMPRESA_EMAIL", "") or "contato@lazersport.com"
        )

    token = jwt.encode(
        {
            "aud": origem,
            "exp": int(time.time()) + VALIDADE_DO_JWT,
            # Quem manda. Se um serviço de push precisar falar conosco
            # sobre volume ou abuso, é por aqui.
            "sub": contato,
        },
        privada,
        algorithm="ES256",
    )
    return {
        "Authorization": f"vapid t={token}, k={chave_publica()}",
    }


# ----------------------------------------------------------------------
# O corpo cifrado (RFC 8291, aes128gcm)
# ----------------------------------------------------------------------
def cifrar(mensagem: bytes, p256dh: str, auth: str, efemera=None) -> bytes:
    """Cifra para UM destinatário, com a chave que o navegador dele deu.

    O serviço do fabricante entrega este pacote sem conseguir lê-lo: só o
    navegador que gerou o par tem como abrir. É por isso que dá para
    mandar o nome do cliente e o valor da proposta por aqui.
    """
    destino = ec.EllipticCurvePublicKey.from_encoded_point(
        ec.SECP256R1(), deb64(p256dh)
    )
    segredo_do_par = deb64(auth)

    efemera = efemera or ec.generate_private_key(ec.SECP256R1())
    compartilhado = efemera.exchange(ec.ECDH(), destino)

    bytes_destino = deb64(p256dh)
    bytes_efemera = _bytes_publicos(efemera.public_key())

    # Passo 1: do segredo ECDH e do "auth" do navegador sai a chave-mãe.
    # O rótulo carrega as duas chaves públicas, e é isso que amarra o
    # pacote a este par de interlocutores.
    info = b"WebPush: info\x00" + bytes_destino + bytes_efemera
    prk = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=segredo_do_par, info=info,
    ).derive(compartilhado)

    # Passo 2: dela saem a chave de conteúdo e o nonce, cada um com seu
    # rótulo -- reaproveitar bytes entre os dois quebraria o AES-GCM.
    sal = os.urandom(16)
    chave = HKDF(
        algorithm=hashes.SHA256(), length=16, salt=sal,
        info=b"Content-Encoding: aes128gcm\x00",
    ).derive(prk)
    nonce = HKDF(
        algorithm=hashes.SHA256(), length=12, salt=sal,
        info=b"Content-Encoding: nonce\x00",
    ).derive(prk)

    # O 0x02 no fim é o delimitador de "último registro" que o padrão
    # exige; sem ele o navegador descarta a mensagem em silêncio.
    corpo = AESGCM(chave).encrypt(nonce, mensagem + b"\x02", None)

    # Cabeçalho do aes128gcm: sal, tamanho de registro, e a chave pública
    # efêmera (que o navegador precisa para refazer o ECDH do outro lado).
    # O tamanho de registro é 4096 porque a mensagem cabe num registro só
    # -- é o valor do exemplo do próprio RFC, e o que todo navegador
    # espera de uma notificação.
    cabecalho = (
        sal
        + TAMANHO_DE_REGISTRO.to_bytes(4, "big")
        + len(bytes_efemera).to_bytes(1, "big")
        + bytes_efemera
    )
    return cabecalho + corpo


# ----------------------------------------------------------------------
# O envio
# ----------------------------------------------------------------------
class InscricaoMorta(Exception):
    """O navegador do outro lado não existe mais.

    Acontece o tempo todo: aplicativo desinstalado, dados do site
    limpos, telefone trocado. Quem chama apaga a inscrição em vez de
    tentar de novo para sempre.
    """


def enviar(endpoint: str, p256dh: str, auth: str, dados: dict) -> bool:
    """Entrega um aviso. Devolve se saiu.

    Nunca levanta por falha de rede: um serviço de push fora do ar não
    pode derrubar o salvamento de um orçamento.
    """
    if not configurado():
        return False

    corpo = cifrar(json.dumps(dados).encode("utf-8"), p256dh, auth)
    cabecalhos = {
        "Content-Encoding": "aes128gcm",
        "Content-Type": "application/octet-stream",
        # Urgência normal: é aviso de trabalho, não alarme. "high"
        # atravessa a economia de bateria e é para o que não pode esperar.
        "Urgency": "normal",
        # Quanto tempo o serviço guarda se o aparelho estiver desligado.
        # Meia hora: aviso de operação que chega no dia seguinte só
        # confunde.
        "TTL": "1800",
    }
    cabecalhos.update(cabecalho_vapid(endpoint))

    try:
        resposta = requests.post(
            endpoint, data=corpo, headers=cabecalhos, timeout=ESPERA,
        )
    except requests.RequestException:
        log.warning("Push não saiu (rede) para %s", endpoint[:60])
        return False

    if resposta.status_code in (404, 410):
        raise InscricaoMorta(endpoint)
    if resposta.status_code >= 400:
        log.warning(
            "Push recusado (%s) por %s: %s",
            resposta.status_code, endpoint[:60], resposta.text[:200],
        )
        return False
    return True
