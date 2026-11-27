"""O ACRÉSCIMO DO SISTEMA DE FICHA: R$ 999,00 (LEIA-ME-V10, seção 148).

O dono: "o acréscimo do moedeiro é 999 reais e deve se chamar sistema de
ficha". O campo continua sendo da Gestão (Dados do contrato); esta migração
só preenche o valor que ele já deu -- e SÓ quando o campo está vazio ou
zero. Um valor que a Gestão já tenha digitado não é tocado, e rodar de novo
não muda nada.

Só dados (o esquema é a 0083; os textos, a 0085).
"""

from decimal import Decimal

from django.db import migrations

VALOR = Decimal("999.00")


def preencher(apps, schema_editor):
    DadosContrato = apps.get_model("sistema_interno", "DadosContrato")
    vazios = DadosContrato.objects.filter(acrescimo_moedeiro__isnull=True) | DadosContrato.objects.filter(
        acrescimo_moedeiro__lte=0
    )
    quantos = vazios.update(acrescimo_moedeiro=VALOR)
    if quantos:
        print(f"\n  Sistema de ficha: acréscimo de R$ 999,00 gravado em {quantos} linha(s) de Dados do contrato.")
    elif DadosContrato.objects.exists():
        atual = DadosContrato.objects.order_by("id").values_list("acrescimo_moedeiro", flat=True).first()
        print(f"\n  Sistema de ficha: o acréscimo já estava definido (R$ {atual}); nada mudou.")


class Migration(migrations.Migration):

    dependencies = [
        ("sistema_interno", "0085_textos_do_sistema_de_ficha"),
    ]

    operations = [
        migrations.RunPython(preencher, migrations.RunPython.noop),
    ]
