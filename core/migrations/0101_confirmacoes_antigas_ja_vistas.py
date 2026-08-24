"""Marca como já avisados os pedidos que existiam antes do aviso na tela.

A 0100 criou `confirmacao_notificada` com default False. Isso vale para um
pedido novo, mas aplicado ao histórico significa que TODO pedido pago que o
cliente já recebeu há meses entrou na fila de "pagamento aprovado!" — o
aviso passou a aparecer para pedidos antigos a cada visita.

Esta migration fecha o histórico: só pedidos confirmados a partir de agora
geram aviso.
"""

from django.db import migrations


def marcar_historico_como_visto(apps, schema_editor):
    Pedido = apps.get_model("core", "Pedido")
    Pedido.objects.filter(confirmacao_notificada=False).update(
        confirmacao_notificada=True,
    )


def reverter(apps, schema_editor):
    """Sem volta útil: não há como saber quais avisos eram realmente
    pendentes antes desta migration. Deixar tudo como visto é o estado
    seguro — o contrário reabriria a enxurrada de avisos antigos."""


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0100_pedido_confirmacao_assincrona"),
    ]

    operations = [
        migrations.RunPython(marcar_historico_como_visto, reverter),
    ]
