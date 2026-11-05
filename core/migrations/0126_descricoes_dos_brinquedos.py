"""As descrições novas dos brinquedos do catálogo (core/migrations/_descricoes_brinquedos.py).

SÓ DADOS (a regra do projeto: dado e esquema não moram na mesma migração).

O QUE ELA FAZ. Para cada brinquedo do site no ar -- conferido pelo id E
pelo nome --, troca a descrição pela nova, mas SÓ se o texto atual ainda
for o antigo. Se alguém da equipe reescreveu a descrição pelo painel
depois do levantamento, a dela vale e não é tocada. Em qualquer outro
banco (o computador, os testes), onde os ids não são desses brinquedos, o
nome não confere e nada muda. Comparação de texto sem ligar para espaços
e quebras de linha (o banco pode guardar \\r\\n).

Desfazer volta o texto antigo, com a mesma cautela: só onde o texto
ainda é o novo.
"""

from django.db import migrations

from core.migrations._descricoes_brinquedos import DESCRICOES


def _texto(valor):
    return " ".join((valor or "").split())


def _nome(valor):
    return _texto(valor).casefold()


def _trocar(apps, de, para):
    Brinquedos = apps.get_model("core", "Brinquedos")
    trocados = 0
    for pk, dados in DESCRICOES.items():
        brinquedo = Brinquedos.objects.filter(pk=pk).only("id", "nome_brinquedo", "descricao").first()
        if brinquedo is None or _nome(brinquedo.nome_brinquedo) != _nome(dados["nome"]):
            continue
        atual = _texto(brinquedo.descricao)
        if atual == _texto(dados[para]) or atual != _texto(dados[de]):
            continue
        Brinquedos.objects.filter(pk=pk).update(descricao=dados[para])
        trocados += 1
    return trocados


def aplicar(apps, schema_editor):
    _trocar(apps, "antiga", "nova")


def desfazer(apps, schema_editor):
    _trocar(apps, "nova", "antiga")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0125_modulo_tres_d"),
    ]

    operations = [
        migrations.RunPython(aplicar, desfazer),
    ]
