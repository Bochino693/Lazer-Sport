# O envio robusto dos e-mails de campanha (LEIA-ME-V10, seção 107).
#
# SÓ DADOS: o esquema nasce na 0068. Separadas de propósito -- ver
# tests_migracoes.py.
#
# A FILA ANTIGA. Até aqui nenhum e-mail de campanha saía no ar: a reserva de
# cada e-mail usava uma consulta que o PostgreSQL recusa (seção 107), e tudo
# ficava "pendente". Com a correção, a fila voltaria a andar -- e mandaria de
# uma vez, de surpresa, campanhas de semanas atrás, talvez de oferta que nem
# vale mais. Então, ao subir:
#   * o que está pendente em campanha criada há MAIS DE 3 DIAS fica RETIDO:
#     vira "falhou" com o motivo escrito. Se a oferta ainda vale, o botão
#     "Reenviar falhas" da campanha manda tudo, no ritmo novo;
#   * o que é mais novo sai sozinho (a oferta encerrada é barrada na hora do
#     envio, com o motivo);
#   * o que um processo largou "processando" volta para a fila;
#   * os contadores de todas as campanhas são refeitos (total_ignorados é novo);
#   * a linha do estado da fila é criada.
# Rodar de novo não muda nada: o que já foi retido não está mais pendente.
# Desfazer não devolve nada à fila (não dá para saber o que era retido).

from datetime import timedelta

from django.db import migrations
from django.db.models import Count
from django.utils import timezone

RETER_DEPOIS_DE = timedelta(days=3)
MOTIVO_RETIDO = (
    "Retido: ficou parado na fila antiga, que não mandava nada (defeito "
    "corrigido em 18/11/2026). Se a oferta ainda vale, use Reenviar falhas."
)
ABERTOS = ("pendente", "processando", "aguardando")


def _recalcular(Campanha, Entrega):
    for campanha in Campanha.objects.all().iterator():
        contagem = dict(
            Entrega.objects.filter(campanha_id=campanha.pk)
            .values_list("status").annotate(n=Count("id")).order_by()
        )
        total = sum(contagem.values())
        enviados = contagem.get("enviado", 0)
        falhas = contagem.get("falhou", 0)
        ignorados = contagem.get("ignorado", 0)
        estado = campanha.status
        if estado != "cancelada":
            if not total:
                estado = "falha"
            elif any(contagem.get(s) for s in ABERTOS):
                estado = "andamento"
            elif falhas:
                estado = "parcial" if enviados else "falha"
            else:
                estado = "concluida"
        Campanha.objects.filter(pk=campanha.pk).update(
            status=estado,
            total_destinatarios=total,
            total_enviados=enviados,
            total_falhas=falhas,
            total_ignorados=ignorados,
        )


def preparar_fila(apps, schema_editor):
    Estado = apps.get_model("sistema_interno", "EstadoFilaEmails")
    Entrega = apps.get_model("sistema_interno", "EntregaCampanha")
    Campanha = apps.get_model("sistema_interno", "CampanhaDivulgacao")

    Estado.objects.get_or_create(chave="campanhas")
    agora = timezone.now()

    Entrega.objects.filter(canal="email", status="processando").update(
        status="pendente", processando_desde=None,
    )
    antigas = list(
        Campanha.objects.filter(criacao__lt=agora - RETER_DEPOIS_DE)
        .exclude(status="cancelada").values_list("pk", flat=True)
    )
    Entrega.objects.filter(
        canal="email", status="pendente", campanha_id__in=antigas,
    ).update(status="falhou", erro=MOTIVO_RETIDO, proxima_tentativa_em=None)

    _recalcular(Campanha, Entrega)


class Migration(migrations.Migration):

    dependencies = [
        ("sistema_interno", "0068_fila_emails_campanhas_esquema"),
    ]

    operations = [
        migrations.RunPython(preparar_fila, migrations.RunPython.noop),
    ]
