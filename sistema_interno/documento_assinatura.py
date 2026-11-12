"""O documento para assinatura do orçamento pago, e o link de 5 minutos.

O PEDIDO, nas palavras do cliente: "após o orçamento estar como pago, vc
deve analisar o seguinte: como já está pago, finalizado, vc deve pôr uma
opção de gerar documento, no qual vc gera um documento de assinatura
digital para o cliente assinar no telefone dele em um link que vai ser
gerado a cada 5 minutos, para o usuário assinar, com validações de tempo e
tudo, sem muita burocracia e muita programação."

COMO FICOU, EM QUATRO PEÇAS:

  1. O RETRATO (`retrato`). Na hora de gerar, o orçamento é copiado para um
     JSON: empresa, cliente, itens, valores, pagamento, condições de
     entrega e a declaração. Esse JSON é o documento -- o orçamento pode
     ser editado depois que o papel não muda -- e o SHA-256 dele
     (`hash_do_retrato`) é a impressão digital que vai na auditoria.

  2. O LINK (`emitir_link` / `ler_link`). É um `TimestampSigner` do Django
     com sal próprio, sobre "id do documento + começo do hash". Não há
     tabela de tokens: a assinatura HMAC garante que ninguém fabrica um
     link, o carimbo de tempo dentro dele diz quando ele nasceu, e o
     servidor recusa o que tiver mais de 5 minutos. Gerar o documento de
     novo muda o hash (e o id): todos os links velhos morrem juntos.

  3. A ASSINATURA (`assinar`). Nome completo, CPF/CNPJ (conferido com o do
     cadastro, quando o cadastro tem), "Li e concordo" e o traço do dedo,
     em PNG, com teto de tamanho. Fica gravado com data, IP, navegador e o
     hash conferido naquele instante. Assinado, não se assina de novo.

  4. O FREIO (`tentativas_estouradas`). Um teto curto de envios por IP no
     cache, como o do "Monte seu projeto": quem erra o CPF três vezes não
     é barrado, quem martela o formulário é.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import re
import time
from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.crypto import salted_hmac

from core.email_utils import cnpj_empresa, nome_empresa

from .models import AtividadeOrcamento, DocumentoAssinatura, Orcamento
from .utils import ErroDeFormulario
from .validacoes import (
    chave_documento,
    documento_valido,
    mascarar_documento,
    tipo_documento,
)


#: Quanto tempo um link vale, em segundos. É o número do pedido ("um link
#: que vai ser gerado a cada 5 minutos"): o painel renova o link nesse
#: ritmo e o servidor recusa o que passar dele -- na abertura E no envio.
VALIDADE_DO_LINK = 5 * 60

#: O sal separa estes links de qualquer outra coisa que o projeto assine
#: com a mesma SECRET_KEY: um valor assinado para outro fim nunca passa
#: por link de documento.
SAL_DO_LINK = "sistema_interno.documento_assinatura.link"

#: Quantos caracteres do hash viajam no link. 16 hexadecimais (64 bits)
#: bastam para amarrar o link à VERSÃO do documento -- quem garante que o
#: link não foi fabricado é a assinatura HMAC, não este pedaço.
PEDACO_DO_HASH = 16

#: O PNG do traço, depois de decodificado. Um traço de dedo num quadro de
#: celular dá 10-40 KB; 300 KB é folga para tela grande e densa, e corta
#: qualquer tentativa de usar o campo como depósito.
TAMANHO_MAXIMO_DA_ASSINATURA = 300 * 1024
LADO_MAXIMO_DA_ASSINATURA = 2400

#: O freio do envio público: tentativas por IP numa janela.
TENTATIVAS_POR_JANELA = 12
JANELA_DAS_TENTATIVAS = 10 * 60

#: Muda quando o TEXTO da declaração mudar: o retrato guarda a versão, e
#: um documento antigo continua dizendo o que dizia.
VERSAO_DO_MODELO = "2026-11"


# ======================================================================
# 1. O RETRATO
# ======================================================================
def _dinheiro(valor) -> str:
    return f"{Decimal(valor or 0).quantize(Decimal('0.01')):.2f}"


def _linha_do_endereco(endereco, rua_campo="endereco") -> str:
    if not endereco:
        return ""
    rua = getattr(endereco, rua_campo, "") or getattr(endereco, "rua", "") or ""
    numero = getattr(endereco, "numero", "") or ""
    partes = [
        ", ".join(p for p in (rua, numero) if p),
        getattr(endereco, "bairro", "") or "",
        "/".join(p for p in (
            getattr(endereco, "cidade", "") or "",
            getattr(endereco, "estado", "") or "",
        ) if p),
        f"CEP {endereco.cep}" if getattr(endereco, "cep", "") else "",
    ]
    return " · ".join(p for p in partes if p)


def _data_br(quando) -> str:
    if not quando:
        return ""
    if hasattr(quando, "hour"):
        quando = timezone.localtime(quando)
    return quando.strftime("%d/%m/%Y")


def _empresa() -> dict:
    """Os "Dados da empresa" que a proposta já usa, no mesmo lugar."""
    from core.models import EnderecoEmpresa

    cadastro = EnderecoEmpresa.objects.filter(ativo=True).order_by("id").first()
    return {
        "nome": nome_empresa(),
        "cnpj": cnpj_empresa(),
        "endereco": _linha_do_endereco(cadastro, rua_campo="rua"),
        "telefone": (
            getattr(settings, "ORCAMENTO_TELEFONE", "")
            or (cadastro.telefone if cadastro and cadastro.telefone else "")
        ),
        "email": getattr(settings, "ORCAMENTO_EMAIL", "") or "",
    }


def _declaracao(orcamento, empresa) -> list[str]:
    """O texto que o cliente assina: curto, sem juridiquês, e verdadeiro.

    Diz o que aconteceu (comprou, pagou, recebe nas condições do orçamento)
    e o que fica registrado da assinatura. Não promete nada que a tela não
    faça: o registro é exatamente o da auditoria do documento.
    """
    pago_em = _data_br(orcamento.pago_em)
    forma = (orcamento.forma_pagamento or "").strip()
    pagamento = f"R$ {_moeda(orcamento.valor_pago)}"
    if pago_em:
        pagamento += f", recebido em {pago_em}"
    if forma:
        pagamento += f" ({forma})"
    envio = (orcamento.forma_envio or "").strip()
    return [
        (
            f"Declaro que comprei de {empresa['nome']} (CNPJ {empresa['cnpj']}) "
            f"os itens descritos neste termo, referentes ao orçamento nº "
            f"{orcamento.numero_documento} (versão {orcamento.versao}), pelo "
            f"valor total de R$ {_moeda(orcamento.total)}."
        ),
        f"Declaro que o pagamento foi feito e está quitado: {pagamento}.",
        (
            "A produção, a entrega e a garantia seguem as condições escritas "
            "neste orçamento"
            + (f" (forma de envio: {envio})" if envio else "")
            + "."
        ),
        (
            "Conferi os dados acima. Assino este termo eletronicamente, no meu "
            "aparelho, e sei que ficam registrados a data e a hora, o endereço "
            "de internet (IP), o aparelho usado e o código de integridade "
            "(SHA-256) deste documento."
        ),
    ]


def _moeda(valor) -> str:
    from core.formatos import dinheiro

    return dinheiro(valor)


def retrato(orcamento) -> dict:
    """O documento inteiro, como ele será assinado.

    Só texto e números já formatados para a leitura -- nada de id interno
    de cadastro, token ou link. O retrato é o que vai para a tela do
    cliente, para o PDF e para o hash, e os três têm de ser a mesma coisa.
    """
    empresa = _empresa()
    cliente = orcamento.cliente if orcamento.cliente_id else None
    endereco_cliente = cliente.endereco_principal if cliente else None
    responsavel = ""
    if orcamento.responsavel_id and orcamento.responsavel:
        responsavel = (
            orcamento.responsavel.get_full_name().strip()
            or orcamento.responsavel.get_username()
        )

    itens = []
    for item in orcamento.itens.all():
        itens.append({
            "descricao": item.descricao,
            "detalhes": list(item.ficha),
            "quantidade": item.quantidade,
            "valor_unitario": _dinheiro(item.valor_unitario),
            "subtotal": _dinheiro(item.subtotal),
        })

    agora = timezone.localtime()
    return {
        "modelo": VERSAO_DO_MODELO,
        "titulo": "Termo de compra e recibo",
        "emitido_em": agora.isoformat(timespec="seconds"),
        "emitido_em_texto": agora.strftime("%d/%m/%Y às %H:%M"),
        "empresa": empresa,
        "cliente": {
            "nome": orcamento.destinatario,
            "documento": (cliente.documento or "").strip() if cliente else "",
            "telefone": orcamento.whatsapp_destinatario or "",
            "email": orcamento.email_destinatario or "",
            "endereco": _linha_do_endereco(endereco_cliente),
        },
        "orcamento": {
            "id": orcamento.pk,
            "numero": orcamento.numero_documento,
            "versao": orcamento.versao,
            "data": _data_br(orcamento.criacao),
            "responsavel": responsavel or "Equipe Lazer & Sport",
        },
        "itens": itens,
        "valores": {
            "subtotal": _dinheiro(orcamento.subtotal),
            "frete": _dinheiro(orcamento.frete),
            "desconto": _dinheiro(orcamento.desconto_aplicado),
            "acrescimo": _dinheiro(orcamento.acrescimo_aplicado),
            "total": _dinheiro(orcamento.total),
            "pago": _dinheiro(orcamento.valor_pago),
        },
        "pagamento": {
            "situacao": orcamento.get_status_pagamento_display(),
            "pago_em": _data_br(orcamento.pago_em),
            "forma": (orcamento.forma_pagamento or "").strip(),
            "observacao": (orcamento.observacao_pagamento or "").strip(),
        },
        "condicoes": {
            "forma_envio": (orcamento.forma_envio or "").strip(),
            "observacoes": (orcamento.observacoes or "").strip(),
        },
        "declaracao": _declaracao(orcamento, empresa),
    }


def hash_do_retrato(conteudo: dict) -> str:
    """SHA-256 do retrato em JSON canônico (chaves ordenadas, sem espaço).

    Canônico porque o mesmo conteúdo tem de dar o mesmo hash amanhã, em
    outro servidor e depois de ir e voltar do banco: a ordem das chaves e
    os espaços não podem entrar na conta.
    """
    serializado = json.dumps(
        conteudo, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serializado).hexdigest()


# ======================================================================
# GERAR
# ======================================================================
def documento_atual(orcamento):
    """O documento que vale agora: o assinado, ou o que espera assinatura."""
    return (
        DocumentoAssinatura.objects
        .filter(orcamento=orcamento)
        .exclude(situacao=DocumentoAssinatura.Situacao.SUBSTITUIDO)
        .order_by("-id")
        .first()
    )


def registrar_no_historico(orcamento, autor, tipo, resumo, *, autor_nome=""):
    """Uma linha no histórico do orçamento (o sino da equipe lê daqui).

    Como `registrar_atividade_orcamento` do painel: o histórico é o rastro,
    não o trabalho. Se ele falhar, o documento continua gerado e assinado.
    """
    import logging

    try:
        if autor_nome:
            return AtividadeOrcamento.objects.create(
                orcamento=orcamento,
                orcamento_numero=orcamento.pk,
                cliente=orcamento.destinatario[:120],
                autor=None,
                autor_nome=autor_nome[:150],
                tipo=tipo,
                resumo=(resumo or "")[:240],
            )
        return AtividadeOrcamento.registrar(orcamento, autor, tipo, resumo=resumo)
    except Exception:
        logging.getLogger(__name__).exception(
            "Não consegui registrar no histórico do orçamento %s", orcamento.pk,
        )
        return None


def gerar(orcamento, usuario):
    """Congela o orçamento num documento novo. Só para orçamento PAGO.

    O anterior que ainda esperava assinatura vira "substituído" na mesma
    transação, e com isso todos os links dele morrem (ver `ler_link`).
    Depois de assinado não há "gerar de novo": o assinado é o documento.
    """
    with transaction.atomic():
        # A linha do orçamento travada: dois cliques em "Gerar" de duas
        # abas não produzem dois documentos esperando assinatura.
        # Sem select_related: no PostgreSQL o FOR UPDATE não aceita o lado
        # anulável de um LEFT JOIN (o cliente é opcional no orçamento).
        orcamento = Orcamento.objects.select_for_update().get(pk=orcamento.pk)
        if orcamento.status_pagamento != Orcamento.StatusPagamento.PAGO:
            raise ErroDeFormulario(
                "O documento para assinatura só é gerado depois que o "
                "orçamento está pago. Registre o pagamento primeiro."
            )
        if not orcamento.itens.exists():
            raise ErroDeFormulario("Este orçamento não tem itens para o documento.")

        anteriores = list(
            DocumentoAssinatura.objects.select_for_update()
            .filter(orcamento=orcamento)
            .exclude(situacao=DocumentoAssinatura.Situacao.SUBSTITUIDO)
        )
        if any(doc.assinado for doc in anteriores):
            raise ErroDeFormulario(
                "Este orçamento já tem um documento assinado. Ele é o "
                "documento que vale; baixe o PDF pelo cartão."
            )
        links_antes = sum(doc.links_gerados for doc in anteriores)
        for doc in anteriores:
            doc.situacao = DocumentoAssinatura.Situacao.SUBSTITUIDO
            doc.save(update_fields=["situacao", "atualizado"])

        conteudo = retrato(orcamento)
        documento = DocumentoAssinatura.objects.create(
            orcamento=orcamento,
            conteudo=conteudo,
            hash_conteudo=hash_do_retrato(conteudo),
            criado_por=usuario if getattr(usuario, "is_authenticated", False) else None,
        )

    resumo = f"Termo de compra e recibo · integridade {documento.hash_conteudo[:12]}…"
    if anteriores:
        resumo = (
            f"Documento refeito (o anterior saiu com {links_antes} "
            f"link{'s' if links_antes != 1 else ''} gerado{'s' if links_antes != 1 else ''}) · "
            f"integridade {documento.hash_conteudo[:12]}…"
        )
    registrar_no_historico(orcamento, usuario, AtividadeOrcamento.Tipo.DOCUMENTO, resumo)
    return documento


# ======================================================================
# 2. O LINK DE 5 MINUTOS
# ======================================================================
class _AssinadorDoLink(signing.TimestampSigner):
    """O `TimestampSigner` do Django, com a assinatura em letras e números.

    POR QUE TROCAR O FORMATO DA ASSINATURA. O padrão do Django escreve o
    HMAC em base64 de URL, que usa "-" e "_". O "_" já derrubou o link da
    proposta no WhatsApp: o aplicativo o trata como marca de itálico e o
    cliente recebia o endereço sem os sublinhados -- um 404 (ver
    `gerar_token_orcamento`). Aqui o mesmo HMAC sai em base 62, e o
    separador é o ponto: o link inteiro é feito de [0-9A-Za-z.].

    Só a forma muda. A chave, o sal, o algoritmo, a conferência em tempo
    constante e a checagem de idade são os do Django.
    """

    def signature(self, value, key=None):
        key = key or self.key
        digest = salted_hmac(
            self.salt + "signer", value, key, algorithm=self.algorithm,
        ).digest()
        return signing.b62_encode(int.from_bytes(digest, "big"))


def _assinador():
    return _AssinadorDoLink(salt=SAL_DO_LINK, sep=".")


def _carga(documento) -> str:
    return f"{documento.pk}.{documento.hash_conteudo[:PEDACO_DO_HASH]}"


def emitir_link(documento):
    """Um token novo, que vale 5 minutos a partir de agora.

    Conta no documento quantos links já saíram (o histórico mostra o
    número, não uma linha por link). `F()` para dois painéis abertos não
    perderem a conta um do outro.
    """
    token = _assinador().sign(_carga(documento))
    agora = timezone.now()
    DocumentoAssinatura.objects.filter(pk=documento.pk).update(
        links_gerados=F("links_gerados") + 1,
        ultimo_link_em=agora,
    )
    documento.refresh_from_db(fields=["links_gerados", "ultimo_link_em"])
    return token, _nasceu_em(token) + VALIDADE_DO_LINK


def _nasceu_em(token) -> int:
    """O carimbo de tempo de dentro do token (só depois de conferido)."""
    try:
        return signing.b62_decode(token.rsplit(".", 2)[1])
    except (IndexError, ValueError):
        return 0


@dataclass
class LeituraDoLink:
    """O que o link aberto pelo cliente quer dizer.

    `situacao` é uma de: "valido", "expirado", "substituido", "suspenso"
    (o orçamento deixou de estar pago), "assinado" ou "invalido". `expira_em` é o instante (segundos desde 1970) em que
    ele deixa de valer -- é dele que sai o relógio da página.
    """

    situacao: str
    documento: DocumentoAssinatura | None = None
    expira_em: int = 0

    @property
    def valido(self):
        return self.situacao == "valido"

    @property
    def segundos_restantes(self):
        return max(0, int(self.expira_em - time.time()))


_FORMATO_DO_TOKEN = re.compile(r"^[0-9]+\.[0-9a-f]{%d}\.[0-9A-Za-z]+\.[0-9A-Za-z]+$" % PEDACO_DO_HASH)


def ler_link(token, *, bloquear=False) -> LeituraDoLink:
    """Confere o token e devolve o documento dele, com o veredito.

    A ORDEM IMPORTA. Primeiro a assinatura (link fabricado ou cortado é
    "invalido", e nada do banco é consultado). Depois o documento: o já
    assinado responde "assinado" mesmo com o link vencido -- quem tem o
    link é quem assinou, e merece o comprovante, não um "expirou". Só então
    a versão (hash) e por último o relógio.
    """
    token = (token or "").strip()
    if len(token) > 200 or not _FORMATO_DO_TOKEN.match(token):
        return LeituraDoLink("invalido")
    assinador = _assinador()
    try:
        carga = assinador.unsign(token, max_age=VALIDADE_DO_LINK)
        expirado = False
    except signing.SignatureExpired:
        carga = assinador.unsign(token)
        expirado = True
    except signing.BadSignature:
        return LeituraDoLink("invalido")

    pk, _, pedaco = carga.partition(".")
    consulta = DocumentoAssinatura.objects.select_related(
        "orcamento", "orcamento__cliente",
    )
    if bloquear:
        consulta = consulta.select_for_update(of=("self",))
    documento = consulta.filter(pk=pk).first() if pk.isdigit() else None
    if documento is None:
        return LeituraDoLink("invalido")

    expira_em = _nasceu_em(token) + VALIDADE_DO_LINK
    if documento.assinado:
        return LeituraDoLink("assinado", documento, expira_em)
    if (
        documento.situacao == DocumentoAssinatura.Situacao.SUBSTITUIDO
        or documento.hash_conteudo[:PEDACO_DO_HASH] != pedaco
    ):
        return LeituraDoLink("substituido", documento, expira_em)
    # O pagamento foi desfeito depois de o documento sair (estorno, valor
    # corrigido): o papel diz "pago" e isso deixou de ser verdade.
    if documento.orcamento.status_pagamento != Orcamento.StatusPagamento.PAGO:
        return LeituraDoLink("suspenso", documento, expira_em)
    if expirado:
        return LeituraDoLink("expirado", documento, expira_em)
    return LeituraDoLink("valido", documento, expira_em)


def qr_svg(texto: str) -> str:
    """O QR do link em SVG, desenhado aqui (sem rede, sem imagem gravada).

    Uma linha de caminho por corrida de módulos escuros: o QR de um link de
    ~90 caracteres sai com 3-4 KB, leve o bastante para viajar a cada
    renovação dentro do JSON, e nítido em qualquer tamanho de tela -- o
    cliente aponta a câmera para o monitor do balcão.
    """
    import qrcode
    from qrcode.constants import ERROR_CORRECT_M

    qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_M, border=2)
    qr.add_data(texto)
    qr.make(fit=True)
    matriz = qr.get_matrix()
    lado = len(matriz)
    trechos = []
    for y, linha in enumerate(matriz):
        x = 0
        while x < lado:
            if linha[x]:
                inicio = x
                while x < lado and linha[x]:
                    x += 1
                trechos.append(f"M{inicio} {y}h{x - inicio}v1h-{x - inicio}z")
            else:
                x += 1
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {lado} {lado}" '
        f'shape-rendering="crispEdges" role="img" aria-label="QR Code do link de assinatura">'
        f'<rect width="{lado}" height="{lado}" fill="#fff"/>'
        f'<path fill="#0b0712" d="{"".join(trechos)}"/></svg>'
    )


def mensagem_whatsapp(documento, link) -> str:
    """O texto pronto da conversa, com o link de 5 minutos."""
    conteudo = documento.conteudo or {}
    numero = (conteudo.get("orcamento") or {}).get("numero", "")
    nome = (conteudo.get("cliente") or {}).get("nome", "")
    return "\n".join([
        f"Olá, {nome}! 👋" if nome else "Olá! 👋",
        "",
        f"Seu pedido nº {numero} está *pago*. Obrigado! ✅",
        "Falta só assinar o termo de compra, direto no seu celular:",
        link,
        "",
        "⏱️ O link vale por *5 minutos*. Se passar, é só pedir outro aqui.",
        f"{nome_empresa()} · CNPJ {cnpj_empresa()}",
    ])


# ======================================================================
# 3. A ASSINATURA
# ======================================================================
class AssinaturaRecusada(Exception):
    """Um campo do formulário não passou. `campo` diz qual."""

    def __init__(self, mensagem, campo=""):
        super().__init__(mensagem)
        self.campo = campo


def png_da_assinatura(data_url: str) -> bytes:
    """O traço do dedo, conferido e regravado como um PNG limpo.

    O navegador manda `data:image/png;base64,...`. Aqui se confere tudo o
    que dá para conferir sem confiar no aparelho: o tamanho antes de
    decodificar, que é mesmo um PNG, as medidas, e que há traço (um quadro
    em branco não é assinatura). Regravar pelo Pillow tira qualquer pedaço
    extra que viesse dentro do arquivo.
    """
    from PIL import Image, UnidentifiedImageError

    texto = (data_url or "").strip()
    prefixo = "data:image/png;base64,"
    if not texto.startswith(prefixo):
        raise AssinaturaRecusada("Assine no quadro com o dedo (ou o mouse).", "assinatura")
    corpo = texto[len(prefixo):]
    # base64 tem 4 caracteres para cada 3 bytes: conferir antes de abrir.
    if len(corpo) > TAMANHO_MAXIMO_DA_ASSINATURA * 4 // 3 + 8:
        raise AssinaturaRecusada("A imagem da assinatura ficou grande demais. Limpe e assine de novo.", "assinatura")
    try:
        bruto = base64.b64decode(corpo, validate=True)
    except (binascii.Error, ValueError):
        raise AssinaturaRecusada("A assinatura não chegou inteira. Assine de novo.", "assinatura")
    if len(bruto) > TAMANHO_MAXIMO_DA_ASSINATURA or not bruto.startswith(b"\x89PNG\r\n\x1a\n"):
        raise AssinaturaRecusada("A assinatura não chegou inteira. Assine de novo.", "assinatura")
    try:
        imagem = Image.open(io.BytesIO(bruto))
        if imagem.format != "PNG":
            raise AssinaturaRecusada("A assinatura não chegou inteira. Assine de novo.", "assinatura")
        largura, altura = imagem.size
        if not (40 <= largura <= LADO_MAXIMO_DA_ASSINATURA and 20 <= altura <= LADO_MAXIMO_DA_ASSINATURA):
            raise AssinaturaRecusada("A assinatura não chegou inteira. Assine de novo.", "assinatura")
        imagem = imagem.convert("RGBA")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise AssinaturaRecusada("A assinatura não chegou inteira. Assine de novo.", "assinatura")

    # Traço = pixel visível e escuro. O quadro manda o fundo transparente;
    # se vier branco, o escuro ainda separa o traço do papel.
    cinza = imagem.convert("LA")
    tinta = Image.eval(cinza.getchannel("L"), lambda v: 255 if v < 160 else 0)
    visivel = Image.eval(cinza.getchannel("A"), lambda v: 255 if v > 40 else 0)
    from PIL import ImageChops

    traco = ImageChops.multiply(tinta, visivel)
    caixa = traco.getbbox()
    if not caixa or (caixa[2] - caixa[0]) < 12 and (caixa[3] - caixa[1]) < 12:
        raise AssinaturaRecusada("O quadro está em branco. Assine com o dedo antes de enviar.", "assinatura")

    saida = io.BytesIO()
    imagem.save(saida, format="PNG", optimize=True)
    return saida.getvalue()


def conferir_campos(documento, *, nome, cpf_cnpj, concordo):
    """Nome completo, CPF/CNPJ que confere e o "Li e concordo".

    O CPF/CNPJ é conferido pelos dígitos e, quando o cadastro do cliente
    tem um documento válido, tem de ser ESSE: é o que impede um terceiro
    com o link na mão de assinar no nome do cliente com um CPF qualquer.
    """
    nome = re.sub(r"\s+", " ", (nome or "").strip())[:160]
    palavras = [p for p in nome.split(" ") if len(p.strip(".")) >= 2]
    if len(palavras) < 2:
        raise AssinaturaRecusada("Escreva o nome completo (nome e sobrenome).", "nome")

    chave = chave_documento(cpf_cnpj)
    if not documento_valido(chave):
        rotulo = tipo_documento(chave)
        raise AssinaturaRecusada(
            f"{'CPF ou CNPJ' if rotulo == 'documento' else rotulo} inválido. "
            "Confira os números.",
            "documento",
        )
    do_cadastro = chave_documento(((documento.conteudo or {}).get("cliente") or {}).get("documento", ""))
    if documento_valido(do_cadastro) and do_cadastro != chave:
        raise AssinaturaRecusada(
            f"Este {tipo_documento(chave)} não confere com o do cadastro "
            f"({mascarar_documento(do_cadastro)}). Confira os números ou "
            "fale com o atendente.",
            "documento",
        )
    if not concordo:
        raise AssinaturaRecusada("Marque “Li e concordo” para assinar.", "concordo")
    return nome, chave


def assinar(documento, *, nome, cpf_cnpj, png, ip, navegador):
    """Grava a assinatura. Quem chama já travou a linha e conferiu o link."""
    documento.situacao = DocumentoAssinatura.Situacao.ASSINADO
    documento.assinado_em = timezone.now()
    documento.assinante_nome = nome
    documento.assinante_documento = cpf_cnpj
    documento.assinatura_png = png
    documento.assinatura_ip = ip or None
    documento.assinatura_navegador = (navegador or "")[:400]
    documento.hash_assinado = hash_do_retrato(documento.conteudo)
    documento.save(update_fields=[
        "situacao", "assinado_em", "assinante_nome", "assinante_documento",
        "assinatura_png", "assinatura_ip", "assinatura_navegador",
        "hash_assinado", "atualizado",
    ])
    links = documento.links_gerados
    registrar_no_historico(
        documento.orcamento,
        None,
        AtividadeOrcamento.Tipo.ASSINATURA,
        (
            f"Termo de compra assinado no celular · "
            f"{mascarar_documento(cpf_cnpj)} · {links} link{'s' if links != 1 else ''} "
            f"gerado{'s' if links != 1 else ''} até a assinatura"
        ),
        autor_nome=f"{nome} (cliente)",
    )
    return documento


def documento_pontuado(valor) -> str:
    """52998224725 -> 529.982.247-25 (e o CNPJ com barra). O resto, como veio."""
    chave = chave_documento(valor)
    if len(chave) == 11 and chave.isdigit():
        return f"{chave[:3]}.{chave[3:6]}.{chave[6:9]}-{chave[9:]}"
    if len(chave) == 14:
        return f"{chave[:2]}.{chave[2:5]}.{chave[5:8]}/{chave[8:12]}-{chave[12:]}"
    return (valor or "").strip()


def assinatura_data_url(documento) -> str:
    """O PNG gravado, pronto para um <img src>."""
    if not documento.assinatura_png:
        return ""
    return "data:image/png;base64," + base64.b64encode(bytes(documento.assinatura_png)).decode("ascii")


# ======================================================================
# 4. O FREIO
# ======================================================================
def tentativas_estouradas(ip) -> bool:
    """Conta um envio deste IP e diz se passou do teto da janela.

    No cache, e só o resumo do IP, como o freio do "Monte seu projeto": o
    número some sozinho quando a janela passa. Sem cache que funcione, não
    freia -- o freio é conforto, a validação de verdade é a do link.
    """
    chave = "doc-assinatura:envios:" + hashlib.sha256((ip or "sem-ip").encode()).hexdigest()[:24]
    try:
        if cache.add(chave, 1, JANELA_DAS_TENTATIVAS):
            return False
        return cache.incr(chave) > TENTATIVAS_POR_JANELA
    except Exception:  # noqa: BLE001
        return False
