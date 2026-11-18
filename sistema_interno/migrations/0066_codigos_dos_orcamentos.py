# O CÓDIGO DO ORÇAMENTO (LEIA-ME-V10, seção 104).
#
# SÓ DADOS: cada orçamento que já existia ganha o código dele ("LS-" e
# seis sinais sorteados), para a proposta antiga também poder ser
# vinculada em Meus pedidos. A coluna nasceu nula na 0065; a 0067 a torna
# única e obrigatória. Separada das duas de propósito -- ver
# tests_migracoes.py ("pending trigger events" no PostgreSQL).
#
# O ALFABETO ESTÁ COPIADO, e não importado de `sistema_interno.models`: a
# migração roda igual daqui a um ano, mesmo que o código de hoje mude.
#
# RODAR DE NOVO NÃO TROCA NADA: só recebe código quem ainda não tem. Os
# sorteados não repetem entre si nem com os que já estavam no banco.
# Desfazer não apaga nada (a 0065 desfeita leva a coluna inteira).

import secrets

from django.db import migrations
from django.db.models import Q

ALFABETO = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
TAMANHO = 6
PREFIXO = "LS-"


def _sortear():
    return PREFIXO + "".join(secrets.choice(ALFABETO) for _ in range(TAMANHO))


def preencher_codigos(apps, schema_editor):
    banco = schema_editor.connection.alias
    Orcamento = apps.get_model("sistema_interno", "Orcamento")
    usados = set(
        Orcamento.objects.using(banco)
        .exclude(codigo__isnull=True).exclude(codigo="")
        .values_list("codigo", flat=True)
    )
    pendentes = (
        Orcamento.objects.using(banco)
        .filter(Q(codigo__isnull=True) | Q(codigo=""))
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    for pk in list(pendentes):
        codigo = _sortear()
        while codigo in usados:
            codigo = _sortear()
        usados.add(codigo)
        Orcamento.objects.using(banco).filter(pk=pk).update(codigo=codigo)


class Migration(migrations.Migration):

    dependencies = [
        ("sistema_interno", "0065_orcamento_codigo_e_conta"),
    ]

    operations = [
        migrations.RunPython(preencher_codigos, migrations.RunPython.noop),
    ]
