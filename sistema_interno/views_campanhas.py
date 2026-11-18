"""Interface interna e página pública das campanhas comerciais."""

from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .campanhas import (
    ErroCampanha,
    conteudo_do_objeto,
    criar_campanha,
    descadastrar,
    destinatarios,
    estado_da_fila,
    mensagem_whatsapp,
    progresso,
    retomar_fila,
    url_publica,
)
from .models import CampanhaDivulgacao, DescadastroEmail, EntregaCampanha
from .views import CriacaoInternoRequiredMixin


def _sim(valor):
    return str(valor or "").strip().lower() in {"1", "true", "on", "sim"}


class OfertasDisponiveisView(CriacaoInternoRequiredMixin, View):
    """As ofertas ativas, para escolher uma na ficha do cliente.

    A tela de campanhas dispara a partir do cartão da própria oferta, no
    catálogo -- ali o id já está na mão. Na ficha do cliente o caminho é o
    inverso: sabe-se para QUEM mandar e falta escolher O QUÊ. Daí esta
    lista.

    Só o que está ativo entra: oferecer ao atendente uma promoção
    desligada é deixá-lo escolher algo que a criação da campanha vai
    recusar depois, com o cliente esperando do outro lado da linha.
    """

    def get(self, request):
        from core.models import Combos, Cupom, Promocoes

        tipo = (request.GET.get("tipo") or "").strip()

        if tipo == CampanhaDivulgacao.Tipo.PROMOCAO:
            itens = [
                {"id": o.pk, "rotulo": o.descricao}
                for o in Promocoes.objects.vigentes().order_by("descricao")[:100]
            ]
        elif tipo == CampanhaDivulgacao.Tipo.COMBO:
            itens = [
                {"id": o.pk, "rotulo": o.descricao}
                for o in Combos.objects.filter(ativo=True).order_by("descricao")[:100]
            ]
        elif tipo == CampanhaDivulgacao.Tipo.CUPOM:
            # `todos_usuarios=False` é cupom exclusivo de contas
            # escolhidas, e a criação da campanha recusa. Oferecê-lo aqui
            # seria deixar o atendente escolher algo que vai falhar
            # depois, com o cliente esperando na linha.
            itens = [
                {
                    "id": o.pk,
                    "rotulo": f"{o.codigo} — {o.desconto_percentual:.0f}% de desconto",
                }
                for o in Cupom.objects.filter(
                    ativo=True, todos_usuarios=True,
                ).order_by("codigo")[:100]
            ]
        else:
            return JsonResponse(
                {"status": "erro", "msg": "Escolha promoção, combo ou cupom."},
                status=400,
            )

        return JsonResponse({"status": "sucesso", "itens": itens})


class PrepararCampanhaView(CriacaoInternoRequiredMixin, View):
    """Prévia e contagem antes de qualquer gravação ou envio."""

    def get(self, request):
        tipo = request.GET.get("tipo", "").strip()
        objeto_id = request.GET.get("objeto", "").strip()
        segmento = request.GET.get("segmento", CampanhaDivulgacao.Segmento.TODOS).strip()
        email = _sim(request.GET.get("email", "1"))
        whatsapp = _sim(request.GET.get("whatsapp", "1"))
        try:
            conteudo = conteudo_do_objeto(tipo, objeto_id)
            linhas, ignorados = destinatarios(
                segmento, email=email, whatsapp=whatsapp,
                cliente_id=(request.GET.get("cliente") or "").strip() or None,
            )
        except ErroCampanha as erro:
            return JsonResponse({"status": "erro", "msg": str(erro)}, status=400)
        canais = {
            EntregaCampanha.Canal.EMAIL: 0,
            EntregaCampanha.Canal.WHATSAPP: 0,
        }
        for _cliente, canal, _destino in linhas:
            canais[canal] += 1
        return JsonResponse({
            "status": "sucesso",
            "titulo": conteudo.titulo,
            "mensagem": conteudo.mensagem,
            "imagem": conteudo.imagem_url,
            "email": canais[EntregaCampanha.Canal.EMAIL],
            "whatsapp": canais[EntregaCampanha.Canal.WHATSAPP],
            "ignorados": ignorados,
            "total": len(linhas),
        })


class CriarCampanhaView(CriacaoInternoRequiredMixin, View):
    def post(self, request):
        try:
            campanha = criar_campanha(
                tipo=request.POST.get("tipo", "").strip(),
                objeto_id=request.POST.get("objeto", "").strip(),
                segmento=request.POST.get("segmento", CampanhaDivulgacao.Segmento.TODOS).strip(),
                email=_sim(request.POST.get("email")),
                whatsapp=_sim(request.POST.get("whatsapp")),
                titulo=request.POST.get("titulo", ""),
                mensagem=request.POST.get("mensagem", ""),
                usuario=request.user,
                cliente_id=(request.POST.get("cliente") or "").strip() or None,
            )
        except ErroCampanha as erro:
            return JsonResponse({"status": "erro", "msg": str(erro)}, status=400)

        detalhe = reverse("campanha_detalhe", args=[campanha.token])
        # os e-mails começam a sair agora, sem prender o clique (fila_de_emails.py)
        from .fila_de_emails import disparar_agora

        transaction.on_commit(disparar_agora)
        return JsonResponse({
            "status": "sucesso",
            "msg": "Campanha criada. Os e-mails já estão saindo e o WhatsApp está pronto para atendimento assistido.",
            "detalhe": detalhe,
            "total": campanha.total_destinatarios,
            "ignorados": getattr(campanha, "ignorados_sem_canal", 0),
        }, status=201)


class CampanhasInnerView(CriacaoInternoRequiredMixin, View):
    def get(self, request):
        campanhas = (
            CampanhaDivulgacao.objects.select_related("responsavel")
            .all()[:80]
        )
        return render(request, "campanhas_inner.html", {
            "campanhas": campanhas,
            "fila": estado_da_fila(),
            "total_fila": CampanhaDivulgacao.objects.filter(
                status__in=(
                    CampanhaDivulgacao.Status.FILA,
                    CampanhaDivulgacao.Status.EM_ANDAMENTO,
                )
            ).count(),
            "total_concluidas": CampanhaDivulgacao.objects.filter(
                status=CampanhaDivulgacao.Status.CONCLUIDA
            ).count(),
            "total_com_falha": CampanhaDivulgacao.objects.filter(
                status__in=(CampanhaDivulgacao.Status.PARCIAL, CampanhaDivulgacao.Status.FALHA)
            ).count(),
        })


def _hora(valor):
    return timezone.localtime(valor).strftime("%d/%m %H:%M") if valor else ""


def _observacao(entrega, agora):
    """O que a tabela mostra na coluna "Observação" de cada e-mail."""
    S = EntregaCampanha.Status
    if entrega.status == S.ENVIADO:
        return f"Enviado em {_hora(entrega.enviado_em)}"
    if entrega.status == S.PENDENTE and entrega.proxima_tentativa_em and entrega.proxima_tentativa_em > agora:
        texto = f"Nova tentativa às {timezone.localtime(entrega.proxima_tentativa_em):%H:%M}."
        return f"{texto} {entrega.erro}" if entrega.erro else texto
    return entrega.erro or "—"


class CampanhaDetalheView(CriacaoInternoRequiredMixin, View):
    """O acompanhamento da campanha: os números reais da fila, e-mail por e-mail.

    Com `?formato=json` devolve só os números, para a tela se atualizar
    sozinha enquanto a campanha anda (sem recarregar a página).
    """

    def get(self, request, token):
        campanha = get_object_or_404(
            CampanhaDivulgacao.objects.select_related("responsavel"),
            token=token,
        )
        campanha.recalcular()
        agora = timezone.now()
        numeros = progresso(campanha, agora)
        fila = estado_da_fila(agora)
        entregas = campanha.entregas.select_related("cliente")
        emails = list(entregas.filter(canal=EntregaCampanha.Canal.EMAIL))
        for entrega in emails:
            entrega.observacao = _observacao(entrega, agora)

        if request.GET.get("formato") == "json":
            return JsonResponse({
                "status": campanha.status,
                "status_rotulo": campanha.get_status_display(),
                # a campanha inteira (e-mail + WhatsApp) e só a fila de e-mails
                "campanha": {
                    "total": campanha.total_destinatarios,
                    "enviados": campanha.total_enviados,
                    "falhas": campanha.total_falhas,
                    "ignorados": campanha.total_ignorados,
                    "percentual": campanha.progresso_percentual,
                },
                "emails": {
                    chave: valor for chave, valor in numeros.items()
                    if chave not in ("motivos", "proxima_tentativa_em")
                },
                "proxima_tentativa": _hora(numeros["proxima_tentativa_em"]),
                "motivos": numeros["motivos"],
                "fila": {
                    "smtp_ok": fila["smtp_ok"],
                    "pausada": fila["pausada"],
                    "pausada_ate": _hora(fila["pausada_ate"]),
                    "motivo_pausa": fila["motivo_pausa"],
                    "parada": fila["parada"],
                    "ultima_rodada": _hora(fila["ultima_rodada_em"]),
                },
                "entregas": [
                    {
                        "token": str(entrega.token),
                        "status": entrega.status,
                        "rotulo": entrega.get_status_display(),
                        "tentativas": entrega.tentativas,
                        "observacao": entrega.observacao,
                    }
                    for entrega in emails
                ],
            })

        return render(request, "campanha_detalhe_inner.html", {
            "campanha": campanha,
            "emails": emails,
            "whatsapps": entregas.filter(canal=EntregaCampanha.Canal.WHATSAPP),
            "url_publica": url_publica(campanha),
            "numeros": numeros,
            "fila": fila,
            # sem as credenciais do SMTP no servidor, nenhum e-mail sai: a tela diz
            "smtp_ok": fila["smtp_ok"],
            "emails_pendentes": numeros["pendentes"] + numeros["processando"],
            "proxima_tentativa": _hora(numeros["proxima_tentativa_em"]),
            "tentativas_max": settings.CAMPANHA_EMAIL_TENTATIVAS,
        })

    @transaction.atomic
    def post(self, request, token):
        campanha = get_object_or_404(
            CampanhaDivulgacao.objects.select_for_update(), token=token,
        )
        acao = request.POST.get("acao", "")
        if acao in ("reenviar_falhas", "repetir_falhas"):
            if campanha.status == CampanhaDivulgacao.Status.CANCELADA:
                messages.error(request, "A campanha foi cancelada: crie outra para mandar de novo.")
                return redirect("campanha_detalhe", token=campanha.token)
            falhas = campanha.entregas.filter(
                canal=EntregaCampanha.Canal.EMAIL,
                status=EntregaCampanha.Status.FALHOU,
            )
            # quem se descadastrou depois da falha não volta para a fila
            fora = set(DescadastroEmail.objects.filter(
                email_chave__in=list(falhas.values_list("destino_chave", flat=True)),
            ).values_list("email_chave", flat=True))
            quantidade = falhas.exclude(destino_chave__in=fora).update(
                status=EntregaCampanha.Status.PENDENTE,
                tentativas=0,
                erro="",
                proxima_tentativa_em=None,
                processando_desde=None,
                atualizado=timezone.now(),
            )
            campanha.recalcular()
            if quantidade:
                retomar_fila()
                from .fila_de_emails import disparar_agora

                transaction.on_commit(disparar_agora)
            if quantidade == 1:
                messages.success(request, "1 e-mail com falha voltou para a fila e já está saindo.")
            else:
                messages.success(request, f"{quantidade} e-mails com falha voltaram para a fila e já estão saindo.")
        elif acao == "enviar_agora":
            retomar_fila()
            from .fila_de_emails import disparar_agora

            transaction.on_commit(disparar_agora)
            messages.success(request, "Enviando os e-mails pendentes agora. A tela mostra o andamento.")
        elif acao == "cancelar":
            campanha.status = CampanhaDivulgacao.Status.CANCELADA
            campanha.save(update_fields=("status", "atualizado"))
            campanha.entregas.filter(status__in=(
                EntregaCampanha.Status.PENDENTE,
                EntregaCampanha.Status.AGUARDANDO_ACAO,
            )).update(
                status=EntregaCampanha.Status.IGNORADO,
                erro="Campanha cancelada antes do envio.",
                proxima_tentativa_em=None,
                atualizado=timezone.now(),
            )
            campanha.recalcular()
            messages.success(request, "Campanha cancelada. Nenhuma entrega pendente será processada.")
        else:
            messages.error(request, "Ação de campanha inválida.")
        return redirect("campanha_detalhe", token=campanha.token)


class AcionarWhatsAppCampanhaView(CriacaoInternoRequiredMixin, View):
    """Registra o clique e abre a conversa; não finge automação inexistente."""

    @transaction.atomic
    def post(self, request, token, entrega_token):
        entrega = get_object_or_404(
            EntregaCampanha.objects.select_for_update().select_related("campanha"),
            token=entrega_token,
            campanha__token=token,
            canal=EntregaCampanha.Canal.WHATSAPP,
        )
        if entrega.status == EntregaCampanha.Status.AGUARDANDO_ACAO:
            entrega.status = EntregaCampanha.Status.ENVIADO
            entrega.enviado_em = timezone.now()
            entrega.save(update_fields=("status", "enviado_em", "atualizado"))
            entrega.campanha.recalcular()
        texto = quote(mensagem_whatsapp(entrega))
        return redirect(f"https://wa.me/{entrega.destino}?text={texto}")


class CampanhaPublicaView(View):
    """Landing page por UUID; não revela PK de produto ou cliente."""

    def get(self, request, token):
        campanha = get_object_or_404(CampanhaDivulgacao, token=token)
        resposta = render(request, "campanha_publica.html", {
            "campanha": campanha,
            "destino": reverse("campanha_publica_destino", args=[campanha.token]),
        })
        resposta["Cache-Control"] = "public, max-age=300, stale-while-revalidate=900"
        return resposta


class CampanhaPublicaDestinoView(View):
    """Mantém o id sequencial do item fora do HTML e do link enviado."""

    def get(self, request, token):
        campanha = get_object_or_404(CampanhaDivulgacao, token=token)
        return redirect(campanha.destino_url or "/")


def _mascarar(email):
    """cliente@x.com -> cl•••••@x.com: a página confirma sem expor o endereço inteiro."""
    usuario, _, dominio = (email or "").partition("@")
    if not dominio:
        return email
    visivel = usuario[:2] if len(usuario) > 2 else usuario[:1]
    return f"{visivel}{'•' * max(1, len(usuario) - len(visivel))}@{dominio}"


@method_decorator(csrf_exempt, name="dispatch")
class DescadastroCampanhaView(View):
    """O link "não quero mais receber" do rodapé de cada e-mail de campanha.

    GET mostra a pergunta e um botão: o link sozinho não descadastra,
    porque antivírus e pré-visualização de e-mail abrem links sem ninguém
    clicar. POST descadastra -- é também o que o Gmail e o Yahoo mandam no
    "Cancelar inscrição" (List-Unsubscribe-Post, RFC 8058), sem cookie nem
    token de formulário: por isso sem CSRF. Quem autoriza é o token da
    entrega, um UUID que só o destinatário recebeu.
    """

    def _entrega(self, token):
        return get_object_or_404(
            EntregaCampanha.objects.select_related("campanha"),
            token=token,
            canal=EntregaCampanha.Canal.EMAIL,
        )

    def _responder(self, request, entrega, feito):
        resposta = render(request, "campanha_descadastro.html", {
            "entrega": entrega,
            "email_mascarado": _mascarar(entrega.destino),
            "feito": feito,
        })
        resposta["Cache-Control"] = "no-store"
        resposta["X-Robots-Tag"] = "noindex, nofollow"
        return resposta

    def get(self, request, token):
        entrega = self._entrega(token)
        feito = DescadastroEmail.objects.filter(email_chave=entrega.destino_chave).exists()
        return self._responder(request, entrega, feito)

    def post(self, request, token):
        entrega = self._entrega(token)
        um_clique = request.POST.get("List-Unsubscribe") == "One-Click"
        descadastrar(
            entrega,
            origem=(DescadastroEmail.Origem.UM_CLIQUE if um_clique else DescadastroEmail.Origem.LINK),
        )
        return self._responder(request, entrega, True)
