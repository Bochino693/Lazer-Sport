from django.db import migrations


NOVAS_FUNCOES = (
    "Equipe · Vendedor ambulante",
    "Equipe · Financeiro",
)


def criar_funcoes(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for nome in NOVAS_FUNCOES:
        Group.objects.get_or_create(name=nome)


def remover_funcoes(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=NOVAS_FUNCOES).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("sistema_interno", "0023_orcamento_origem_alter_centralvendas_origem_and_more"),
    ]

    operations = [
        migrations.RunPython(criar_funcoes, remover_funcoes),
    ]
