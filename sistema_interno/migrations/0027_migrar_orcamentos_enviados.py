from django.db import migrations


def migrar_status_enviado(apps, schema_editor):
    Orcamento = apps.get_model("sistema_interno", "Orcamento")
    Orcamento.objects.filter(status="enviado").update(
        status="aguardando_resposta"
    )


def reverter_status_aguardando(apps, schema_editor):
    Orcamento = apps.get_model("sistema_interno", "Orcamento")
    Orcamento.objects.filter(status="aguardando_resposta").update(
        status="enviado"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("sistema_interno", "0026_orcamento_motivo_negociacao_and_more"),
    ]

    operations = [
        migrations.RunPython(
            migrar_status_enviado,
            reverter_status_aguardando,
        ),
    ]
