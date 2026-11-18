"""Campanhas comerciais com outbox idempotente.

O CRUD do catálogo só descreve o que será divulgado. Este módulo cuida de
destinatários, deduplicação, fila, tentativas e mensagens; assim promoção,
combo e cupom usam exatamente as mesmas garantias.
"""

from __future__ import annotations

import hashlib
import logging
import random
import smtplib
import ssl
import time
from collections import namedtuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.utils import parseaddr
from urllib.parse import urljoin

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Count, F, Min, Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from core.email_utils import diagnostico_smtp, remetente, responder_para, smtp_configurado
from core.models import ClientePerfil, Combos, Cupom, Promocoes

from .models import (
    CampanhaDivulgacao,
    Cliente,
    DescadastroEmail,
    EntregaCampanha,
    EstadoFilaEmails,
)
from .validacoes import somente_digitos, telefone_valido

log = logging.getLogger(__name__)


class ErroCampanha(ValueError):
    pass


@dataclass(frozen=True)
class ConteudoCampanha:
    tipo: str
    objeto: object
    titulo: str
    mensagem: str
    imagem_url: str
    destino_url: str
    codigo_cupom: str = ""


def _site_url(caminho=""):
    base = (getattr(settings, "SITE_URL", "") or "https://www.lazersport.com.br").strip()
    return urljoin(base.rstrip("/") + "/", str(caminho or "").lstrip("/"))


def _url_imagem(campo):
    try:
        valor = campo.url if campo else ""
    except (AttributeError, ValueError):
        valor = ""
    if not valor:
        return ""
    return valor if valor.startswith(("http://", "https://")) else _site_url(valor)


def _moeda(valor):
    return f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def conteudo_do_objeto(tipo, objeto_id, *, perfil_cupom=None):
    """Transforma os três modelos do catálogo em um contrato único."""
    if tipo == CampanhaDivulgacao.Tipo.PROMOCAO:
        objeto = Promocoes.objects.select_related("brinquedos").filter(pk=objeto_id).first()
        if not objeto:
            raise ErroCampanha("Promoção não encontrada.")
        if not objeto.ativo:
            raise ErroCampanha("Ative a promoção antes de divulgá-la.")
        if not objeto.vigente:
            raise ErroCampanha("Esta promoção já terminou: mude a validade antes de divulgá-la.")
        titulo = objeto.descricao
        nomes = [b.nome_brinquedo for b in objeto.todos_brinquedos]
        lista = (", ".join(nomes[:-1]) + f" e {nomes[-1]}") if len(nomes) > 1 else nomes[0]
        if objeto.preco_promocao:
            if len(nomes) > 1:
                oferta = f"{lista}: os {len(nomes)} por R$ {_moeda(objeto.preco_promocao)}."
            else:
                oferta = f"{lista} por R$ {_moeda(objeto.preco_promocao)}."
        else:
            # a promoção sem preço (brinde, leve 4 pague 3): a condição é a oferta
            oferta = f"{lista}."
        extras = " ".join(
            condicao if condicao.endswith((".", "!", "?")) else condicao + "."
            for condicao in objeto.lista_condicoes
        )
        if extras:
            oferta = f"{oferta} {extras}"
        if objeto.valida_ate:
            oferta = f"{oferta} Válida até {objeto.valida_ate:%d/%m/%Y}."
        mensagem = f"Oferta especial da Lazer & Sport: {objeto.descricao}. {oferta}"
        # a arte da campanha (o cartaz inteiro) é a melhor imagem para divulgar
        imagem = _url_imagem(objeto.arte_promocao or objeto.imagem_promocao or objeto.brinquedos.imagem_brinquedo)
        destino = _site_url(reverse(
            "promocao", args=[objeto.pk], urlconf=settings.ROOT_URLCONF,
        ))
        return ConteudoCampanha(tipo, objeto, titulo, mensagem, imagem, destino)

    if tipo == CampanhaDivulgacao.Tipo.COMBO:
        objeto = Combos.objects.prefetch_related("brinquedos").filter(pk=objeto_id).first()
        if not objeto:
            raise ErroCampanha("Combo não encontrado.")
        if not objeto.ativo:
            raise ErroCampanha("Ative o combo antes de divulgá-lo.")
        titulo = objeto.descricao
        nomes = ", ".join(objeto.brinquedos.values_list("nome_brinquedo", flat=True)[:4])
        valor = _moeda(objeto.valor_combo)
        mensagem = f"Combo Lazer & Sport: {titulo}. {nomes}. Valor especial: R$ {valor}."
        return ConteudoCampanha(
            tipo, objeto, titulo, mensagem, _url_imagem(objeto.imagem_combo),
            _site_url(reverse(
                "combo", args=[objeto.pk], urlconf=settings.ROOT_URLCONF,
            )),
        )

    if tipo == CampanhaDivulgacao.Tipo.CUPOM:
        objeto = Cupom.objects.select_related("brinquedo", "categoria").filter(pk=objeto_id).first()
        if not objeto:
            raise ErroCampanha("Cupom não encontrado.")
        if not objeto.ativo:
            raise ErroCampanha("Ative o cupom antes de divulgá-lo.")
        if not objeto.todos_usuarios and not (
            perfil_cupom
            and objeto.cliente.filter(pk=perfil_cupom.pk).exists()
        ):
            raise ErroCampanha(
                "Este cupom é exclusivo de contas selecionadas. Para não enviá-lo "
                "ao público errado, escolha primeiro a conta que poderá usá-lo."
            )
        desconto = f"{objeto.desconto_percentual:.2f}".replace(".", ",")
        titulo = f"Cupom {objeto.codigo}"
        mensagem = (
            f"Ganhe {desconto}% de desconto na Lazer & Sport com o cupom "
            f"{objeto.codigo}. Aproveite enquanto estiver ativo."
        )
        return ConteudoCampanha(
            tipo, objeto, titulo, mensagem, "", _site_url(""), objeto.codigo,
        )

    raise ErroCampanha("Tipo de divulgação inválido.")


def _clientes_do_segmento(segmento):
    consulta = Cliente.objects.filter(ativo=True).only(
        "id", "nome_cliente", "email", "telefone", "telefone_digitos", "canal_telefone", "tipo",
    )
    if segmento != CampanhaDivulgacao.Segmento.TODOS:
        permitidos = {valor for valor, _ in CampanhaDivulgacao.Segmento.choices}
        if segmento not in permitidos:
            raise ErroCampanha("Segmento de clientes inválido.")
        consulta = consulta.filter(tipo=segmento)
    return consulta.order_by("nome_cliente", "id")


def _email_valido(valor):
    valor = (valor or "").strip().casefold()
    if not valor:
        return ""
    try:
        validate_email(valor)
    except ValidationError:
        return ""
    return valor


def _whatsapp_valido(cliente):
    if cliente.canal_telefone != Cliente.CanalTelefone.WHATSAPP:
        return ""
    if not telefone_valido(cliente.telefone):
        return ""
    numero = somente_digitos(cliente.telefone)
    if len(numero) in (10, 11):
        numero = "55" + numero
    return numero if len(numero) in (12, 13) and numero.startswith("55") else ""


def destinatarios(segmento, *, email, whatsapp, cliente_id=None):
    """Entrega snapshots únicos e contabiliza cadastros sem canal útil.

    `cliente_id` restringe a UM cliente. A divulgação nasceu em massa --
    "todos os buffets parceiros" --, mas a conversa comercial de verdade
    é um a um: o atendente está olhando a ficha de alguém que ligou e
    quer mandar aquela promoção para AQUELA pessoa. Sem isso, a única
    saída era disparar para o segmento inteiro ou copiar o texto na mão.

    O caminho é o mesmo dos dois jeitos, de propósito: mesma validação de
    canal, mesmo registro de entrega, mesmo histórico. Um envio
    individual é uma campanha de um destinatário só, e não um atalho por
    fora que ninguém depois consegue auditar.
    """
    vistos = set()
    saida = []
    if cliente_id:
        clientes = list(
            Cliente.objects.filter(pk=cliente_id, ativo=True)
        )
    else:
        clientes = list(_clientes_do_segmento(segmento))
    # quem pediu para sair da lista (link do rodapé) não entra de novo
    fora = descadastrados() if email else set()
    for cliente in clientes:
        canais = []
        if email:
            endereco = _email_valido(cliente.email)
            if endereco and DescadastroEmail.chave(endereco) not in fora:
                canais.append((EntregaCampanha.Canal.EMAIL, endereco))
        if whatsapp:
            numero = _whatsapp_valido(cliente)
            if numero:
                canais.append((EntregaCampanha.Canal.WHATSAPP, numero))
        for canal, destino in canais:
            chave = (canal, destino.casefold())
            if chave in vistos:
                continue
            vistos.add(chave)
            saida.append((cliente, canal, destino))
    clientes_com_canal = len({cliente.pk for cliente, _canal, _destino in saida})
    return saida, max(0, len(clientes) - clientes_com_canal)


@transaction.atomic
def criar_campanha(
    *, tipo, objeto_id, segmento, email, whatsapp, titulo, mensagem, usuario,
    cliente_id=None,
):
    if not email and not whatsapp:
        raise ErroCampanha("Escolha e-mail, WhatsApp ou os dois canais.")
    conteudo = conteudo_do_objeto(tipo, objeto_id)
    titulo = (titulo or conteudo.titulo).strip()[:140]
    mensagem = (mensagem or conteudo.mensagem).strip()[:1200]
    if len(titulo) < 3 or len(mensagem) < 12:
        raise ErroCampanha("Revise o título e a mensagem antes de criar a campanha.")

    linhas, ignorados = destinatarios(
        segmento, email=email, whatsapp=whatsapp, cliente_id=cliente_id,
    )
    if not linhas:
        raise ErroCampanha(
            "Este cliente não tem e-mail nem WhatsApp confirmado no cadastro."
            if cliente_id else
            "Nenhum cliente ativo possui os canais escolhidos e confirmados."
        )

    campanha = CampanhaDivulgacao.objects.create(
        tipo=tipo,
        segmento=segmento,
        titulo=titulo,
        mensagem=mensagem,
        imagem_url=conteudo.imagem_url,
        destino_url=conteudo.destino_url,
        codigo_cupom=conteudo.codigo_cupom,
        canal_email=email,
        canal_whatsapp=whatsapp,
        responsavel=usuario,
        promocao=conteudo.objeto if tipo == CampanhaDivulgacao.Tipo.PROMOCAO else None,
        combo=conteudo.objeto if tipo == CampanhaDivulgacao.Tipo.COMBO else None,
        cupom=conteudo.objeto if tipo == CampanhaDivulgacao.Tipo.CUPOM else None,
    )
    entregas = [
        EntregaCampanha(
            campanha=campanha,
            cliente=cliente,
            canal=canal,
            nome_destinatario=cliente.nome_cliente,
            destino=destino,
            destino_chave=hashlib.sha256(
                destino.strip().casefold().encode("utf-8")
            ).hexdigest(),
            status=(
                EntregaCampanha.Status.PENDENTE
                if canal == EntregaCampanha.Canal.EMAIL
                else EntregaCampanha.Status.AGUARDANDO_ACAO
            ),
        )
        for cliente, canal, destino in linhas
    ]
    EntregaCampanha.objects.bulk_create(entregas, batch_size=500)
    campanha.recalcular()
    campanha.ignorados_sem_canal = ignorados
    return campanha


def _whatsapp_da_conta(perfil):
    """Telefone da conta no formato aceito pelo WhatsApp.

    ``ClientePerfil`` é o cadastro público, anterior ao cadastro comercial
    do painel, e não possui o campo de confirmação de canal. Nesta tela o
    superusuário escolhe conscientemente usar o telefone como WhatsApp; ainda
    assim o formato é validado antes de criar qualquer entrega.
    """
    if not perfil or not telefone_valido(perfil.telefone):
        return ""
    numero = somente_digitos(perfil.telefone)
    if len(numero) in (10, 11):
        numero = "55" + numero
    return numero if len(numero) in (12, 13) and numero.startswith("55") else ""


@transaction.atomic
def criar_campanha_para_conta(
    *, tipo, objeto_id, email, whatsapp, usuario, conta_id,
):
    """Envia uma oferta para uma conta pública sem inventar outro fluxo.

    A entrega usa a mesma campanha, fila de e-mail, página por token e
    acompanhamento já usados pela carteira comercial. A diferença é apenas
    a origem do destinatário: aqui ele é ``auth.User``/``ClientePerfil``, não
    ``sistema_interno.Cliente``.

    Cupom exclusivo é ligado ao perfil dentro da mesma transação. Se o
    destinatário não tiver canal válido, tudo volta atrás e o cupom não fica
    liberado por uma tentativa que nunca pôde ser enviada.
    """
    if not email and not whatsapp:
        raise ErroCampanha("Escolha e-mail, WhatsApp ou os dois canais.")

    User = get_user_model()
    conta = (
        User.objects.select_related("perfil")
        .filter(pk=conta_id, is_active=True, is_staff=False)
        .first()
    )
    if not conta:
        raise ErroCampanha(
            "A oferta só pode ser enviada para uma conta de cliente ativa."
        )

    perfil, _ = ClientePerfil.objects.get_or_create(user=conta)

    # Cupom pessoal precisa pertencer à conta antes de a mensagem sair.
    # A transação impede a liberação sem entrega em caso de validação.
    if tipo == CampanhaDivulgacao.Tipo.CUPOM:
        cupom = Cupom.objects.filter(pk=objeto_id).first()
        if cupom and not cupom.todos_usuarios:
            cupom.cliente.add(perfil)

    conteudo = conteudo_do_objeto(
        tipo, objeto_id, perfil_cupom=perfil,
    )
    nome = (
        (perfil.nome_completo or "").strip()
        or conta.get_full_name().strip()
        or conta.username
    )

    canais = []
    saiu_da_lista = False
    if email:
        endereco = _email_valido(conta.email)
        if endereco and descadastrados([DescadastroEmail.chave(endereco)]):
            saiu_da_lista = True
        elif endereco:
            canais.append((EntregaCampanha.Canal.EMAIL, endereco))
    if whatsapp:
        numero = _whatsapp_da_conta(perfil)
        if numero:
            canais.append((EntregaCampanha.Canal.WHATSAPP, numero))
    if not canais:
        raise ErroCampanha(
            "Este e-mail pediu para não receber divulgações (link de descadastro)."
            if saiu_da_lista else
            "Esta conta não possui e-mail ou telefone válido nos canais escolhidos."
        )

    tem_email = any(
        canal == EntregaCampanha.Canal.EMAIL for canal, _destino in canais
    )
    tem_whatsapp = any(
        canal == EntregaCampanha.Canal.WHATSAPP for canal, _destino in canais
    )

    campanha = CampanhaDivulgacao.objects.create(
        tipo=tipo,
        segmento=CampanhaDivulgacao.Segmento.TODOS,
        titulo=conteudo.titulo,
        mensagem=conteudo.mensagem,
        imagem_url=conteudo.imagem_url,
        destino_url=conteudo.destino_url,
        codigo_cupom=conteudo.codigo_cupom,
        # Os indicadores refletem entregas realmente criadas. Um e-mail
        # apenas preenchido, mas inválido, não pode aparecer no histórico
        # como canal preparado.
        canal_email=tem_email,
        canal_whatsapp=tem_whatsapp,
        responsavel=usuario,
        promocao=(
            conteudo.objeto
            if tipo == CampanhaDivulgacao.Tipo.PROMOCAO else None
        ),
        combo=(
            conteudo.objeto
            if tipo == CampanhaDivulgacao.Tipo.COMBO else None
        ),
        cupom=(
            conteudo.objeto
            if tipo == CampanhaDivulgacao.Tipo.CUPOM else None
        ),
    )
    EntregaCampanha.objects.bulk_create([
        EntregaCampanha(
            campanha=campanha,
            cliente=None,
            canal=canal,
            nome_destinatario=nome,
            destino=destino,
            destino_chave=hashlib.sha256(
                destino.strip().casefold().encode("utf-8")
            ).hexdigest(),
            status=(
                EntregaCampanha.Status.PENDENTE
                if canal == EntregaCampanha.Canal.EMAIL
                else EntregaCampanha.Status.AGUARDANDO_ACAO
            ),
        )
        for canal, destino in canais
    ])
    campanha.recalcular()
    return campanha


def url_publica(campanha):
    return _site_url(campanha.caminho_publico)


def mensagem_whatsapp(entrega):
    campanha = entrega.campanha
    nome = (entrega.nome_destinatario or "").split()[0]
    saudacao = f"Olá, {nome}! " if nome else "Olá! "
    return f"{saudacao}{campanha.mensagem}\n\nVeja os detalhes: {url_publica(campanha)}"


# ======================================================================
# O ENVIO DOS E-MAILS (LEIA-ME seção 107)
# ======================================================================
#
# POR QUE NADA SAÍA. A versão anterior reservava cada e-mail com
#
#     EntregaCampanha.objects.select_for_update()
#         .select_related("campanha", "campanha__responsavel")
#
# `responsavel` é chave estrangeira que aceita vazio: o Django junta
# auth_user com LEFT OUTER JOIN, e o PostgreSQL (o Supabase do site)
# recusa a consulta inteira -- "FOR UPDATE cannot be applied to the
# nullable side of an outer join". O erro estourava no PRIMEIRO e-mail de
# toda rodada, antes de qualquer envio; a ronda o engolia num
# `log.exception` e o e-mail continuava "pendente" para sempre, sem motivo
# na tela. Os testes rodam em SQLite, onde `select_for_update` não faz
# nada -- por isso passavam.
#
# AGORA a reserva é um UPDATE condicional (status pendente -> processando,
# só se ainda estiver pendente): o mesmo SQL no SQLite e no PostgreSQL, sem
# trava de linha, sem JOIN. Dois processos nunca pegam o mesmo e-mail.
#
# O RESTO DO ENVIO, na ordem em que acontece:
#   * lote pequeno (CAMPANHA_EMAIL_LOTE), UMA conexão SMTP por lote (um login
#     só, aberta no lote e fechada no fim dele -- nunca guardada até cair),
#     pausa entre um e-mail e outro (CAMPANHA_EMAIL_PAUSA);
#   * cada falha vira um motivo legível no painel e é classificada:
#       - DEFINITIVA: o provedor recusou o ENDEREÇO (550 user unknown...):
#         falhou, sem nova tentativa;
#       - TEMPORARIA: problema só deste e-mail: nova tentativa com espera
#         crescente (2, 10, 30, 90, 240 min) até CAMPANHA_EMAIL_TENTATIVAS;
#       - PROVEDOR: conexão, timeout, login, remetente recusado, "421 try
#         again later", cota: o problema não é do cliente. A fila INTEIRA
#         pausa (1, 2, 4... até 60 min) e a tentativa não conta para ninguém;
#   * descadastrado ou oferta encerrada no meio do caminho: não sai (ignorado,
#     com o motivo);
#   * processo derrubado no meio (deploy, reinício): o e-mail preso em
#     "processando" volta para a fila depois de PRAZO_PROCESSANDO;
#   * mesmo backend (settings.EMAIL_BACKEND, o decorador com o logo) e mesmo
#     remetente (core.email_utils.remetente) dos e-mails de pedido, que chegam.

PRAZO_PROCESSANDO = timedelta(minutes=5)
ESPERAS_MINUTOS = (2, 10, 30, 90, 240)
PAUSA_PROVEDOR_INICIAL = timedelta(minutes=1)
PAUSA_PROVEDOR_MAXIMA = timedelta(minutes=60)

DEFINITIVA = "definitiva"
TEMPORARIA = "temporaria"
PROVEDOR = "provedor"

Falha = namedtuple("Falha", "tipo motivo")

# 5xx que não são do endereço: cota, política, autenticação do domínio.
_SINAIS_DE_PROVEDOR = (
    "quota", "limit", "too many", "try again", "5.4.5", "5.7.0",
    "spam", "policy", "unauthenticated", "dmarc", "spf", "dkim",
    "not authorized", "relay", "sender",
)


def _texto(valor, limite=180):
    if isinstance(valor, bytes):
        valor = valor.decode("utf-8", "replace")
    return " ".join(str(valor or "").split())[:limite]


def classificar_falha(erro):
    """Diz de quem é a culpa da falha e escreve o motivo para o painel."""
    if isinstance(erro, smtplib.SMTPRecipientsRefused):
        codigo, resposta = next(iter(erro.recipients.values()), (0, b""))
        detalhe = f"{codigo} {_texto(resposta)}".strip()
        if 500 <= int(codigo or 0) < 600:
            return Falha(DEFINITIVA, f"O provedor recusou este endereço ({detalhe}).")
        return Falha(TEMPORARIA, f"O provedor adiou a entrega para este endereço ({detalhe}).")
    if isinstance(erro, smtplib.SMTPAuthenticationError):
        return Falha(PROVEDOR, (
            f"O servidor de e-mail recusou o login ({erro.smtp_code} {_texto(erro.smtp_error, 120)}). "
            "Confira EMAIL_HOST_USER e EMAIL_HOST_PASSWORD no Render (no Gmail, senha de app)."
        ))
    if isinstance(erro, smtplib.SMTPSenderRefused):
        return Falha(PROVEDOR, (
            f"O servidor de e-mail recusou o remetente ({erro.smtp_code} {_texto(erro.smtp_error, 120)}). "
            "O DEFAULT_FROM_EMAIL precisa ser a conta do SMTP ou um endereço do domínio verificado no provedor."
        ))
    if isinstance(erro, smtplib.SMTPConnectError):
        return Falha(PROVEDOR, f"O servidor de e-mail recusou a conexão ({erro.smtp_code} {_texto(erro.smtp_error)}).")
    if isinstance(erro, smtplib.SMTPServerDisconnected):
        return Falha(PROVEDOR, f"O servidor de e-mail encerrou a conexão ({_texto(erro) or 'sem resposta'}).")
    if isinstance(erro, smtplib.SMTPNotSupportedError):
        return Falha(PROVEDOR, f"O servidor de e-mail não aceita a configuração usada ({_texto(erro)}). Confira EMAIL_PORT, EMAIL_USE_TLS e EMAIL_USE_SSL.")
    if isinstance(erro, smtplib.SMTPResponseException):
        codigo = int(erro.smtp_code or 0)
        detalhe = f"{codigo} {_texto(erro.smtp_error)}".strip()
        if codigo in (421, 451, 452, 454):
            return Falha(PROVEDOR, f"O provedor pediu para esperar ({detalhe}).")
        if 400 <= codigo < 500:
            return Falha(TEMPORARIA, f"O provedor adiou este e-mail ({detalhe}).")
        if any(sinal in detalhe.casefold() for sinal in _SINAIS_DE_PROVEDOR):
            return Falha(PROVEDOR, f"O provedor recusou o envio ({detalhe}).")
        return Falha(DEFINITIVA, f"O provedor recusou este e-mail ({detalhe}).")
    if isinstance(erro, TimeoutError):
        return Falha(PROVEDOR, (
            f"O servidor de e-mail não respondeu em {getattr(settings, 'EMAIL_TIMEOUT', 10)} s (timeout)."
        ))
    if isinstance(erro, ssl.SSLError):
        return Falha(PROVEDOR, f"Falha na conexão segura com o servidor de e-mail ({_texto(erro)}). Confira EMAIL_PORT, EMAIL_USE_TLS e EMAIL_USE_SSL.")
    if isinstance(erro, OSError):  # ConnectionError, DNS, rede
        return Falha(PROVEDOR, f"Sem conexão com o servidor de e-mail ({erro.__class__.__name__}: {_texto(erro, 120)}).")
    return Falha(TEMPORARIA, f"Erro ao enviar ({erro.__class__.__name__}: {_texto(erro, 200)}).")


# ----------------------------------------------------------------------
# Descadastro
# ----------------------------------------------------------------------
def url_descadastro(entrega):
    return _site_url(reverse(
        "campanha_descadastro", args=[entrega.token], urlconf=settings.ROOT_URLCONF,
    ))


def descadastrados(chaves=None):
    consulta = DescadastroEmail.objects.all()
    if chaves is not None:
        consulta = consulta.filter(email_chave__in=list(chaves))
    return set(consulta.values_list("email_chave", flat=True))


def descadastrar(entrega, origem=DescadastroEmail.Origem.LINK):
    """Marca o endereço desta entrega como 'não quero mais'. Idempotente."""
    if entrega.canal != EntregaCampanha.Canal.EMAIL:
        return None
    registro, _criado = DescadastroEmail.objects.get_or_create(
        email_chave=entrega.destino_chave,
        defaults={"email": entrega.destino, "origem": origem, "entrega": entrega},
    )
    # O que ainda estava na fila para este endereço não sai mais, em campanha nenhuma.
    pendentes = EntregaCampanha.objects.filter(
        canal=EntregaCampanha.Canal.EMAIL,
        destino_chave=entrega.destino_chave,
        status=EntregaCampanha.Status.PENDENTE,
    )
    campanhas = set(pendentes.values_list("campanha_id", flat=True))
    pendentes.update(
        status=EntregaCampanha.Status.IGNORADO,
        erro="Pediu para não receber divulgações por e-mail.",
        proxima_tentativa_em=None,
        atualizado=timezone.now(),
    )
    for campanha in CampanhaDivulgacao.objects.filter(pk__in=campanhas):
        campanha.recalcular()
    return registro


# ----------------------------------------------------------------------
# A mensagem
# ----------------------------------------------------------------------
def montar_email(entrega):
    """O e-mail da campanha, com o remetente e o backend dos e-mails de pedido."""
    campanha = entrega.campanha
    sair = url_descadastro(entrega)
    contexto = {
        "campanha": campanha,
        "entrega": entrega,
        "url_publica": url_publica(campanha),
        "url_descadastro": sair,
    }
    texto = render_to_string("emails/campanha_divulgacao.txt", contexto)
    html = render_to_string("emails/campanha_divulgacao.html", contexto)
    # Descadastro de um clique (RFC 8058): Gmail e Yahoo mostram "Cancelar
    # inscrição" ao lado do remetente e pedem isso de quem manda em massa.
    lista = [f"<{sair}>"]
    resposta = (getattr(settings, "EMAIL_RESPOSTA", "") or "").strip()
    if "@" in resposta and " " not in resposta:
        lista.append(f"<mailto:{resposta}?subject=Descadastrar>")
    email = EmailMultiAlternatives(
        subject=campanha.titulo,
        body=texto,
        from_email=remetente(),
        to=[entrega.destino],
        reply_to=responder_para(campanha.responsavel),
        headers={
            "List-Unsubscribe": ", ".join(lista),
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
    )
    email.attach_alternative(html, "text/html")
    return email


class _Conexao:
    """Uma conexão do backend padrão (o mesmo dos e-mails de pedido) por lote.

    Abre no primeiro e-mail do lote e fecha no fim dele. Depois de qualquer
    erro, é descartada: a seguinte abre limpa, sem herdar uma sessão SMTP
    quebrada. Nunca atravessa a pausa entre lotes, então não "cai parada".
    """

    def __init__(self):
        self.backend = None

    def enviar(self, mensagem):
        if self.backend is None:
            self.backend = get_connection(fail_silently=False)
            self.backend.open()
        if self.backend.send_messages([mensagem]) != 1:
            raise RuntimeError("O provedor não confirmou a entrega.")

    def descartar(self):
        backend, self.backend = self.backend, None
        if backend is None:
            return
        try:
            backend.close()
        except Exception:  # fechar uma conexão já quebrada não é erro de ninguém
            pass


# ----------------------------------------------------------------------
# A fila
# ----------------------------------------------------------------------
def _estado():
    return EstadoFilaEmails.atual()


def _atualizar_estado(**campos):
    linha = EstadoFilaEmails.objects.filter(chave=EstadoFilaEmails.CHAVE)
    if not linha.update(**campos):
        EstadoFilaEmails.atual()  # a primeira vez: a linha nasce aqui
        linha.update(**campos)


def fila_pausada(agora=None):
    estado = EstadoFilaEmails.objects.filter(chave=EstadoFilaEmails.CHAVE).first()
    agora = agora or timezone.now()
    return bool(estado and estado.pausada_ate and estado.pausada_ate > agora)


def _pausar_fila(motivo):
    estado = _estado()
    falhas = estado.falhas_seguidas + 1
    espera = min(PAUSA_PROVEDOR_MAXIMA, PAUSA_PROVEDOR_INICIAL * (2 ** (falhas - 1)))
    espera = espera * random.uniform(0.9, 1.1)
    _atualizar_estado(
        falhas_seguidas=min(falhas, 30),
        pausada_ate=timezone.now() + espera,
        motivo_pausa=_texto(motivo, 300),
    )


def _pausar_ate_amanha(teto):
    amanha = timezone.localdate() + timedelta(days=1)
    reabre = timezone.make_aware(datetime.combine(amanha, datetime.min.time())) + timedelta(minutes=5)
    _atualizar_estado(
        pausada_ate=reabre,
        motivo_pausa=(
            f"Limite de {teto} e-mails de campanha por dia atingido (CAMPANHA_EMAILS_POR_DIA). "
            "O resto sai amanhã, a partir de 00:05."
        ),
    )


def retomar_fila():
    """Tira a pausa (o botão "Enviar agora" / "Reenviar falhas"). Se o provedor
    recusar de novo, a pausa volta maior, porque `falhas_seguidas` continua."""
    _atualizar_estado(pausada_ate=None, motivo_pausa="")


def registrar_erro_da_fila(erro):
    try:
        _atualizar_estado(
            ultimo_erro=_texto(f"{erro.__class__.__name__}: {erro}", 300),
            ultimo_erro_em=timezone.now(),
        )
    except Exception:  # o banco pode ser justamente o problema
        pass


def _espera(tentativas):
    minutos = ESPERAS_MINUTOS[min(max(tentativas, 1), len(ESPERAS_MINUTOS)) - 1]
    return timedelta(minutes=minutos * random.uniform(0.85, 1.15))


def _oferta_encerrada(campanha):
    if campanha.tipo == CampanhaDivulgacao.Tipo.PROMOCAO:
        oferta = campanha.promocao
        return oferta is None or not oferta.vigente
    if campanha.tipo == CampanhaDivulgacao.Tipo.COMBO:
        return campanha.combo is None or not campanha.combo.ativo
    if campanha.tipo == CampanhaDivulgacao.Tipo.CUPOM:
        return campanha.cupom is None or not campanha.cupom.ativo
    return False


def _devidos(agora):
    return Q(proxima_tentativa_em__isnull=True) | Q(proxima_tentativa_em__lte=agora)


def _recolocar_processamentos_abandonados(agora=None):
    """O processo caiu no meio (deploy, reinício): o e-mail preso volta para a fila."""
    agora = agora or timezone.now()
    presos = EntregaCampanha.objects.filter(
        canal=EntregaCampanha.Canal.EMAIL,
        status=EntregaCampanha.Status.PROCESSANDO,
    ).filter(Q(processando_desde__lt=agora - PRAZO_PROCESSANDO) | Q(processando_desde__isnull=True))
    campanhas = set(presos.values_list("campanha_id", flat=True))
    if not campanhas:
        return 0
    maximo = settings.CAMPANHA_EMAIL_TENTATIVAS
    presos.filter(tentativas__gte=maximo).update(
        status=EntregaCampanha.Status.FALHOU,
        processando_desde=None,
        proxima_tentativa_em=None,
        erro=f"O envio foi interrompido {maximo} vezes no meio (o servidor reiniciou).",
        atualizado=agora,
    )
    voltaram = presos.update(
        status=EntregaCampanha.Status.PENDENTE,
        processando_desde=None,
        proxima_tentativa_em=None,
        erro="O envio foi interrompido no meio (o servidor reiniciou); voltou para a fila.",
        atualizado=agora,
    )
    for campanha in CampanhaDivulgacao.objects.filter(pk__in=campanhas):
        campanha.recalcular()
    return voltaram


def _reservar(entrega_id, agora):
    """Pendente -> processando, só se ninguém pegou antes (UPDATE condicional)."""
    return EntregaCampanha.objects.filter(
        pk=entrega_id,
        canal=EntregaCampanha.Canal.EMAIL,
        status=EntregaCampanha.Status.PENDENTE,
    ).filter(_devidos(agora)).update(
        status=EntregaCampanha.Status.PROCESSANDO,
        processando_desde=agora,
        tentativas=F("tentativas") + 1,
        atualizado=agora,
    ) == 1


def _gravar(entrega, **campos):
    campos.setdefault("processando_desde", None)
    campos["atualizado"] = timezone.now()
    EntregaCampanha.objects.filter(pk=entrega.pk).update(**campos)


def _registrar_falha(entrega, falha):
    if falha.tipo == PROVEDOR:
        # não é do cliente: a tentativa não conta, a fila inteira espera
        _gravar(
            entrega,
            status=EntregaCampanha.Status.PENDENTE,
            tentativas=F("tentativas") - 1,
            proxima_tentativa_em=None,
            erro=_texto(f"Aguardando o provedor: {falha.motivo}", 300),
        )
        return
    maximo = settings.CAMPANHA_EMAIL_TENTATIVAS
    if falha.tipo == DEFINITIVA or entrega.tentativas >= maximo:
        motivo = falha.motivo
        if falha.tipo == TEMPORARIA:
            motivo = f"{motivo} Desistiu depois de {entrega.tentativas} tentativas."
        _gravar(
            entrega,
            status=EntregaCampanha.Status.FALHOU,
            proxima_tentativa_em=None,
            erro=_texto(motivo, 300),
        )
        return
    _gravar(
        entrega,
        status=EntregaCampanha.Status.PENDENTE,
        proxima_tentativa_em=timezone.now() + _espera(entrega.tentativas),
        erro=_texto(falha.motivo, 300),
    )


def _registrar_envio(entrega):
    agora = timezone.now()
    _gravar(
        entrega,
        status=EntregaCampanha.Status.ENVIADO,
        enviado_em=agora,
        proxima_tentativa_em=None,
        erro="",
    )
    hoje = timezone.localdate()
    contou = EstadoFilaEmails.objects.filter(chave=EstadoFilaEmails.CHAVE, dia=hoje).update(
        enviados_no_dia=F("enviados_no_dia") + 1, ultimo_envio_em=agora,
    )
    if not contou:
        _atualizar_estado(dia=hoje, enviados_no_dia=1, ultimo_envio_em=agora)


def _ignorar(entrega, motivo):
    _gravar(
        entrega,
        status=EntregaCampanha.Status.IGNORADO,
        tentativas=F("tentativas") - 1,
        proxima_tentativa_em=None,
        erro=_texto(motivo, 300),
    )


def processar_emails_pendentes(limite=None):
    """Manda UM lote da fila. Devolve quantos e-mails foram resolvidos nele.

    Pode rodar em vários processos ao mesmo tempo (a ronda do site, o
    "Enviar agora", um worker): cada e-mail é reservado antes de sair.
    """
    agora = timezone.now()
    estado = _estado()
    _atualizar_estado(ultima_rodada_em=agora)
    if not smtp_configurado():
        return 0
    _recolocar_processamentos_abandonados(agora)
    if estado.pausada_ate and estado.pausada_ate > agora:
        return 0

    tamanho = max(1, int(limite or settings.CAMPANHA_EMAIL_LOTE))
    ids = list(
        EntregaCampanha.objects.filter(
            canal=EntregaCampanha.Canal.EMAIL,
            status=EntregaCampanha.Status.PENDENTE,
        ).exclude(
            campanha__status=CampanhaDivulgacao.Status.CANCELADA,
        ).filter(_devidos(agora)).order_by("criacao", "id").values_list("id", flat=True)[:tamanho]
    )
    if not ids:
        return 0

    teto = int(getattr(settings, "CAMPANHA_EMAILS_POR_DIA", 0) or 0)
    enviados_hoje = estado.enviados_no_dia if estado.dia == timezone.localdate() else 0
    pausa = float(getattr(settings, "CAMPANHA_EMAIL_PAUSA", 0) or 0)
    sem_recado = not (estado.falhas_seguidas or estado.motivo_pausa)
    conexao = _Conexao()
    processados = 0
    campanhas = set()
    try:
        for entrega_id in ids:
            if teto and enviados_hoje >= teto:
                _pausar_ate_amanha(teto)
                break
            if processados and pausa:
                time.sleep(pausa)
            if not _reservar(entrega_id, timezone.now()):
                continue  # outro processo pegou
            entrega = EntregaCampanha.objects.select_related(
                "campanha", "campanha__responsavel", "campanha__promocao",
                "campanha__combo", "campanha__cupom",
            ).get(pk=entrega_id)
            campanhas.add(entrega.campanha_id)
            processados += 1

            if descadastrados([entrega.destino_chave]):
                _ignorar(entrega, "Pediu para não receber divulgações por e-mail.")
                continue
            if _oferta_encerrada(entrega.campanha):
                motivo = "A oferta foi desativada ou venceu antes do envio; este e-mail não saiu."
                _ignorar(entrega, motivo)
                EntregaCampanha.objects.filter(
                    campanha_id=entrega.campanha_id,
                    canal=EntregaCampanha.Canal.EMAIL,
                    status=EntregaCampanha.Status.PENDENTE,
                ).update(
                    status=EntregaCampanha.Status.IGNORADO, erro=motivo,
                    proxima_tentativa_em=None, atualizado=timezone.now(),
                )
                continue

            try:
                mensagem = montar_email(entrega)
            except Exception as erro:
                log.exception("Campanha %s: e-mail %s não foi montado.", entrega.campanha_id, entrega.pk)
                _registrar_falha(entrega, Falha(TEMPORARIA, f"Erro ao montar o e-mail ({erro.__class__.__name__}: {_texto(erro, 160)})."))
                continue

            try:
                conexao.enviar(mensagem)
            except Exception as erro:
                conexao.descartar()
                falha = classificar_falha(erro)
                log.warning(
                    "Campanha %s: e-mail %s não saiu (%s): %s",
                    entrega.campanha_id, entrega.pk, falha.tipo, falha.motivo,
                )
                _registrar_falha(entrega, falha)
                if falha.tipo == PROVEDOR:
                    _pausar_fila(falha.motivo)
                    break
            else:
                _registrar_envio(entrega)
                enviados_hoje += 1
                if not sem_recado:
                    _atualizar_estado(falhas_seguidas=0, pausada_ate=None, motivo_pausa="")
                    sem_recado = True
    finally:
        conexao.descartar()
        for campanha in CampanhaDivulgacao.objects.filter(pk__in=campanhas):
            campanha.recalcular()
    return processados


# ----------------------------------------------------------------------
# O que o painel mostra
# ----------------------------------------------------------------------
def aviso_de_remetente():
    """No Gmail, remetente de outro domínio é trocado pela conta do login."""
    host = (getattr(settings, "EMAIL_HOST", "") or "").lower()
    usuario = (getattr(settings, "EMAIL_HOST_USER", "") or "").strip().lower()
    _nome, de = parseaddr(remetente())
    if "gmail" not in host or "@" not in usuario or "@" not in de:
        return ""
    if de.lower().rsplit("@", 1)[1] == usuario.rsplit("@", 1)[1]:
        return ""
    return (
        "O remetente (DEFAULT_FROM_EMAIL) é de outro domínio que a conta do Gmail "
        "(EMAIL_HOST_USER): o Gmail troca o remetente pela conta, e o e-mail pode "
        "cair no spam. Use o mesmo endereço nas duas, ou um alias verificado no Gmail."
    )


def estado_da_fila(agora=None):
    agora = agora or timezone.now()
    estado = EstadoFilaEmails.objects.filter(chave=EstadoFilaEmails.CHAVE).first()
    pausada = bool(estado and estado.pausada_ate and estado.pausada_ate > agora)
    ultima = estado.ultima_rodada_em if estado else None
    intervalo = max(30, int(getattr(settings, "FILA_DE_EMAILS_INTERVALO", 60)))
    teto = int(getattr(settings, "CAMPANHA_EMAILS_POR_DIA", 0) or 0)
    return {
        "smtp_ok": smtp_configurado(),
        "diagnostico_smtp": diagnostico_smtp(),
        "pausada": pausada,
        "pausada_ate": estado.pausada_ate if pausada else None,
        "motivo_pausa": estado.motivo_pausa if pausada else "",
        "ultima_rodada_em": ultima,
        # parada = a ronda não bate há mais de 3 intervalos (thread morta,
        # FILA_DE_EMAILS_NO_SITE=false sem worker, site dormindo)
        "parada": bool(ultima is None or agora - ultima > timedelta(seconds=intervalo * 3)),
        "ligada_no_site": bool(getattr(settings, "FILA_DE_EMAILS_NO_SITE", True)),
        "ultimo_erro": (estado.ultimo_erro if estado else ""),
        "ultimo_erro_em": (estado.ultimo_erro_em if estado else None),
        "enviados_hoje": (estado.enviados_no_dia if estado and estado.dia == timezone.localdate() else 0),
        "teto_diario": teto,
        "lote": settings.CAMPANHA_EMAIL_LOTE,
        "aviso_remetente": aviso_de_remetente(),
    }


def progresso(campanha, agora=None):
    """Os números reais da campanha, por situação, e os motivos das falhas."""
    agora = agora or timezone.now()
    S = EntregaCampanha.Status
    emails = campanha.entregas.filter(canal=EntregaCampanha.Canal.EMAIL)
    por_status = dict(emails.values_list("status").annotate(n=Count("id")).order_by())
    motivos = [
        {"situacao": dict(S.choices).get(linha["status"], linha["status"]), "motivo": linha["erro"], "quantidade": linha["n"]}
        for linha in emails.filter(status__in=(S.FALHOU, S.IGNORADO)).exclude(erro="")
        .values("status", "erro").annotate(n=Count("id")).order_by("-n", "erro")[:8]
    ]
    proxima = emails.filter(status=S.PENDENTE, proxima_tentativa_em__gt=agora).aggregate(
        quando=Min("proxima_tentativa_em"),
    )["quando"]
    return {
        "total": sum(por_status.values()),
        "enviados": por_status.get(S.ENVIADO, 0),
        "pendentes": por_status.get(S.PENDENTE, 0),
        "processando": por_status.get(S.PROCESSANDO, 0),
        "falhas": por_status.get(S.FALHOU, 0),
        "ignorados": por_status.get(S.IGNORADO, 0),
        "proxima_tentativa_em": proxima,
        "motivos": motivos,
    }
