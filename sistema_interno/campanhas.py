"""Campanhas comerciais com outbox idempotente.

O CRUD do catálogo só descreve o que será divulgado. Este módulo cuida de
destinatários, deduplicação, fila, tentativas e mensagens; assim promoção,
combo e cupom usam exatamente as mesmas garantias.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urljoin

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from core.email_utils import remetente, responder_para, smtp_configurado
from core.models import Combos, Cupom, Promocoes

from .models import CampanhaDivulgacao, Cliente, EntregaCampanha
from .validacoes import somente_digitos, telefone_valido


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


def conteudo_do_objeto(tipo, objeto_id):
    """Transforma os três modelos do catálogo em um contrato único."""
    if tipo == CampanhaDivulgacao.Tipo.PROMOCAO:
        objeto = Promocoes.objects.select_related("brinquedos").filter(pk=objeto_id).first()
        if not objeto:
            raise ErroCampanha("Promoção não encontrada.")
        if not objeto.ativo:
            raise ErroCampanha("Ative a promoção antes de divulgá-la.")
        titulo = objeto.descricao
        mensagem = (
            f"Oferta especial da Lazer & Sport: {objeto.descricao}. "
            f"{objeto.brinquedos.nome_brinquedo} por R$ "
            f"{_moeda(objeto.preco_promocao)}."
        )
        imagem = _url_imagem(objeto.imagem_promocao or objeto.brinquedos.imagem_brinquedo)
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
        if not objeto.todos_usuarios:
            raise ErroCampanha(
                "Este cupom é exclusivo de contas selecionadas. Para não enviá-lo "
                "ao público errado, divulgue apenas cupons liberados para todos."
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


def destinatarios(segmento, *, email, whatsapp):
    """Entrega snapshots únicos e contabiliza cadastros sem canal útil."""
    vistos = set()
    saida = []
    clientes = list(_clientes_do_segmento(segmento))
    for cliente in clientes:
        canais = []
        if email:
            endereco = _email_valido(cliente.email)
            if endereco:
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
def criar_campanha(*, tipo, objeto_id, segmento, email, whatsapp, titulo, mensagem, usuario):
    if not email and not whatsapp:
        raise ErroCampanha("Escolha e-mail, WhatsApp ou os dois canais.")
    conteudo = conteudo_do_objeto(tipo, objeto_id)
    titulo = (titulo or conteudo.titulo).strip()[:140]
    mensagem = (mensagem or conteudo.mensagem).strip()[:1200]
    if len(titulo) < 3 or len(mensagem) < 12:
        raise ErroCampanha("Revise o título e a mensagem antes de criar a campanha.")

    linhas, ignorados = destinatarios(segmento, email=email, whatsapp=whatsapp)
    if not linhas:
        raise ErroCampanha("Nenhum cliente ativo possui os canais escolhidos e confirmados.")

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


def url_publica(campanha):
    return _site_url(campanha.caminho_publico)


def mensagem_whatsapp(entrega):
    campanha = entrega.campanha
    nome = (entrega.nome_destinatario or "").split()[0]
    saudacao = f"Olá, {nome}! " if nome else "Olá! "
    return f"{saudacao}{campanha.mensagem}\n\nVeja os detalhes: {url_publica(campanha)}"


def _recolocar_processamentos_abandonados():
    limite = timezone.now() - timedelta(minutes=15)
    EntregaCampanha.objects.filter(
        canal=EntregaCampanha.Canal.EMAIL,
        status=EntregaCampanha.Status.PROCESSANDO,
        processando_desde__lt=limite,
    ).update(
        status=EntregaCampanha.Status.PENDENTE,
        processando_desde=None,
        erro="Tentativa anterior interrompida; recolocada na fila.",
    )


def processar_emails_pendentes(limite=20):
    """Processa um lote curto; seguro para múltiplos ciclos do observador."""
    if not smtp_configurado():
        return 0
    _recolocar_processamentos_abandonados()
    agora = timezone.now()
    ids = list(
        EntregaCampanha.objects.filter(
            canal=EntregaCampanha.Canal.EMAIL,
            status=EntregaCampanha.Status.PENDENTE,
        ).filter(
            Q(proxima_tentativa_em__isnull=True) | Q(proxima_tentativa_em__lte=agora)
        ).order_by("criacao", "id").values_list("id", flat=True)[:max(1, int(limite))]
    )
    processados = 0
    campanhas = set()
    for entrega_id in ids:
        with transaction.atomic():
            entrega = (
                EntregaCampanha.objects.select_for_update()
                .select_related("campanha", "campanha__responsavel")
                .filter(pk=entrega_id, status=EntregaCampanha.Status.PENDENTE)
                .first()
            )
            if not entrega:
                continue
            entrega.status = EntregaCampanha.Status.PROCESSANDO
            entrega.processando_desde = timezone.now()
            entrega.tentativas += 1
            entrega.save(update_fields=("status", "processando_desde", "tentativas", "atualizado"))

        campanha = entrega.campanha
        campanhas.add(campanha.pk)
        contexto = {
            "campanha": campanha,
            "entrega": entrega,
            "url_publica": url_publica(campanha),
        }
        texto = render_to_string("emails/campanha_divulgacao.txt", contexto)
        html = render_to_string("emails/campanha_divulgacao.html", contexto)
        email = EmailMultiAlternatives(
            subject=campanha.titulo,
            body=texto,
            from_email=remetente(),
            to=[entrega.destino],
            reply_to=responder_para(campanha.responsavel),
        )
        email.attach_alternative(html, "text/html")
        try:
            quantidade = email.send(fail_silently=False)
            if quantidade != 1:
                raise RuntimeError("O provedor não confirmou a entrega.")
        except Exception as erro:  # erro fica no painel; o worker continua.
            entrega.erro = str(erro).strip()[:300] or erro.__class__.__name__
            entrega.processando_desde = None
            if entrega.tentativas >= 4:
                entrega.status = EntregaCampanha.Status.FALHOU
                entrega.proxima_tentativa_em = None
            else:
                entrega.status = EntregaCampanha.Status.PENDENTE
                entrega.proxima_tentativa_em = timezone.now() + timedelta(
                    minutes=2 ** entrega.tentativas
                )
            entrega.save(update_fields=(
                "status", "erro", "processando_desde", "proxima_tentativa_em", "atualizado",
            ))
        else:
            entrega.status = EntregaCampanha.Status.ENVIADO
            entrega.enviado_em = timezone.now()
            entrega.erro = ""
            entrega.processando_desde = None
            entrega.proxima_tentativa_em = None
            entrega.save(update_fields=(
                "status", "enviado_em", "erro", "processando_desde",
                "proxima_tentativa_em", "atualizado",
            ))
        processados += 1

    for campanha in CampanhaDivulgacao.objects.filter(pk__in=campanhas):
        campanha.recalcular()
    return processados
