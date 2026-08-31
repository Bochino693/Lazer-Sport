"""Interface interna e página pública das campanhas comerciais."""

from urllib.parse import quote

from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from .campanhas import (
    ErroCampanha,
    conteudo_do_objeto,
    criar_campanha,
    destinatarios,
    mensagem_whatsapp,
    url_publica,
)
from .models import CampanhaDivulgacao, EntregaCampanha
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
                for o in Promocoes.objects.filter(ativo=True).order_by("descricao")[:100]
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
        return JsonResponse({
            "status": "sucesso",
            "msg": "Campanha criada. Os e-mails entraram na fila e o WhatsApp está pronto para atendimento assistido.",
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


class CampanhaDetalheView(CriacaoInternoRequiredMixin, View):
    def get(self, request, token):
        campanha = get_object_or_404(
            CampanhaDivulgacao.objects.select_related("responsavel"),
            token=token,
        )
        campanha.recalcular()
        entregas = campanha.entregas.select_related("cliente")
        return render(request, "campanha_detalhe_inner.html", {
            "campanha": campanha,
            "emails": entregas.filter(canal=EntregaCampanha.Canal.EMAIL),
            "whatsapps": entregas.filter(canal=EntregaCampanha.Canal.WHATSAPP),
            "url_publica": url_publica(campanha),
        })

    @transaction.atomic
    def post(self, request, token):
        campanha = get_object_or_404(
            CampanhaDivulgacao.objects.select_for_update(), token=token,
        )
        acao = request.POST.get("acao", "")
        if acao == "repetir_falhas":
            quantidade = campanha.entregas.filter(
                canal=EntregaCampanha.Canal.EMAIL,
                status=EntregaCampanha.Status.FALHOU,
            ).update(
                status=EntregaCampanha.Status.PENDENTE,
                tentativas=0,
                erro="",
                proxima_tentativa_em=None,
                processando_desde=None,
            )
            campanha.recalcular()
            messages.success(request, f"{quantidade} e-mail(s) recolocado(s) na fila.")
        elif acao == "cancelar":
            campanha.status = CampanhaDivulgacao.Status.CANCELADA
            campanha.save(update_fields=("status", "atualizado"))
            campanha.entregas.filter(status__in=(
                EntregaCampanha.Status.PENDENTE,
                EntregaCampanha.Status.AGUARDANDO_ACAO,
            )).update(status=EntregaCampanha.Status.IGNORADO)
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
