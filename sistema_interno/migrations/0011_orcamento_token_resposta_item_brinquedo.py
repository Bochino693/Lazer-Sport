"""Token público do orçamento, resposta do cliente e item vindo do catálogo.

O token entra em TRÊS PASSOS, e não em um só. Ele é único, e um campo
único com valor padrão não pode ser adicionado de uma vez a uma tabela que
já tem linhas: o Django avalia o padrão uma única vez e grava o MESMO
valor em todas elas, o que estoura a restrição de unicidade no mesmo
instante em que ela é criada.

Então: cria sem unicidade, preenche linha a linha, e só aí aperta a
restrição.
"""

import django.db.models.deletion
from django.db import migrations, models

import sistema_interno.models


def preencher_tokens(apps, schema_editor):
    """Dá um token distinto a cada orçamento que já existia.

    Vai em lote de 200 para não montar uma transação gigante em base
    grande; `only` evita trazer o resto das colunas, que não interessam.
    """
    Orcamento = apps.get_model("sistema_interno", "Orcamento")

    pendentes = Orcamento.objects.filter(token="").only("id")
    lote = []

    for orcamento in pendentes.iterator(chunk_size=200):
        orcamento.token = sistema_interno.models.gerar_token_orcamento()
        lote.append(orcamento)

        if len(lote) >= 200:
            Orcamento.objects.bulk_update(lote, ["token"])
            lote = []

    if lote:
        Orcamento.objects.bulk_update(lote, ["token"])


def limpar_tokens(apps, schema_editor):
    """Volta os tokens para vazio ao desfazer.

    Precisa existir para a migração ser reversível: sem isto, desfazer
    pararia no meio e deixaria o banco entre dois estados.
    """
    Orcamento = apps.get_model("sistema_interno", "Orcamento")
    Orcamento.objects.update(token="")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
        ("sistema_interno", "0010_ordemproducao_colaborador_alter_ordemproducao_status_and_more"),
    ]

    operations = [
        # ---------- 1. token, ainda sem unicidade ----------
        migrations.AddField(
            model_name="orcamento",
            name="token",
            field=models.CharField(
                default="",
                editable=False,
                help_text="Chave do link público. Não aparece em nenhuma tela interna.",
                max_length=64,
            ),
        ),
        migrations.RunPython(preencher_tokens, limpar_tokens),
        # ---------- 2. agora sim, único e indexado ----------
        migrations.AlterField(
            model_name="orcamento",
            name="token",
            field=models.CharField(
                db_index=True,
                default=sistema_interno.models.gerar_token_orcamento,
                editable=False,
                help_text="Chave do link público. Não aparece em nenhuma tela interna.",
                max_length=64,
                unique=True,
            ),
        ),
        # ---------- 3. a resposta do cliente ----------
        migrations.AddField(
            model_name="orcamento",
            name="enviado_em",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="orcamento",
            name="respondido_em",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="orcamento",
            name="respondido_por",
            field=models.CharField(
                blank=True,
                help_text="Nome que o cliente digitou ao aprovar ou recusar.",
                max_length=120,
            ),
        ),
        migrations.AddField(
            model_name="orcamento",
            name="motivo_recusa",
            field=models.TextField(
                blank=True,
                help_text="O que o cliente escreveu ao recusar, quando escreveu.",
            ),
        ),
        # ---------- 4. o item passa a poder vir do catálogo ----------
        migrations.AddField(
            model_name="itemorcamento",
            name="brinquedo",
            field=models.ForeignKey(
                blank=True,
                help_text="Item do catálogo do site.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="itens_orcamento",
                to="core.brinquedos",
            ),
        ),
        migrations.AlterField(
            model_name="itemorcamento",
            name="produto",
            field=models.ForeignKey(
                blank=True,
                help_text="Item de produção, quando não está no catálogo.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="itens_orcamento",
                to="sistema_interno.produtointerno",
            ),
        ),
    ]
