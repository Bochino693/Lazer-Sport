"""O kit eletrônico vira produto (LEIA-ME-V10, seção 107). 1/3: SÓ O ESQUEMA.

O dono, ao ver o kit numa vitrine à parte: "vc criou outra sub section e nem
sei se outro objeto, mas eles devem estar junto com os produtos". O kit deixa
de ser uma peça marcada (PecasReposicao.eh_kit) e passa a ser um `Brinquedos`
marcado -- o mesmo objeto das máquinas.

Esta migração só PREPARA, sem tocar em linha nenhuma:
  * Brinquedos ganha `eh_kit`, `maquina` (a máquina do kit) e
    `id_kit_antigo` (o número da peça-kit de antes, para os endereços
    antigos);
  * ComponenteKit ganha `kit_produto` (o kit novo, vazio por enquanto) e o
    `kit` antigo (a peça) passa a aceitar vazio -- assim a volta da 0213
    consegue recriá-lo;
  * o `maquina` da peça perde o nome reverso "kits_eletronicos", que passa a
    ser do Brinquedos (nenhum SQL: o nome reverso não mora no banco).

A 0212 (só dados) converte os kits; a 0213 (só esquema) tira o que sobrou e
acerta os nomes. Esquema e dados nunca no mesmo arquivo
(sistema_interno/tests_migracoes.py: no PostgreSQL, "pending trigger events").
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0210_datas_das_fases_dos_pedidos"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pecasreposicao",
            name="maquina",
            field=models.ForeignKey(
                blank=True,
                help_text="A máquina em que o kit é instalado (a página dela chama para o kit).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="core.brinquedos",
                verbose_name="Máquina do kit",
            ),
        ),
        migrations.AlterField(
            model_name="componentekit",
            name="kit",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="componentes_kit",
                to="core.pecasreposicao",
                verbose_name="Kit",
            ),
        ),
        migrations.AddField(
            model_name="brinquedos",
            name="eh_kit",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text='A parte eletrônica de uma máquina, sem a máquina: o card ganha o selo "Kit" e a página, "O que vem no kit".',
                verbose_name="É um kit eletrônico",
            ),
        ),
        migrations.AddField(
            model_name="brinquedos",
            name="maquina",
            field=models.ForeignKey(
                blank=True,
                help_text="A máquina em que o kit é instalado (a página dela chama para o kit).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="kits_eletronicos",
                to="core.brinquedos",
                verbose_name="Máquina do kit",
            ),
        ),
        migrations.AddField(
            model_name="brinquedos",
            name="id_kit_antigo",
            field=models.PositiveIntegerField(
                blank=True,
                db_index=True,
                editable=False,
                help_text="O número da peça-kit de antes (LEIA-ME 107): o endereço antigo leva para cá.",
                null=True,
                verbose_name="Número do kit antigo",
            ),
        ),
        migrations.AddField(
            model_name="componentekit",
            name="kit_produto",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="core.brinquedos",
                verbose_name="Kit",
            ),
        ),
    ]
