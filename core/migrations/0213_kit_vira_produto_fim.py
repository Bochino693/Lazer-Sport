"""O kit eletrônico vira produto (LEIA-ME-V10, seção 107). 3/3: SÓ O ESQUEMA.

Depois da 0212 (os kits já são produtos e cada item já aponta para o
produto em `kit_produto`), sai o que era da peça-kit e os nomes se acertam:
  * ComponenteKit: sai o `kit` antigo (a peça) e `kit_produto` passa a se
    chamar `kit` (obrigatório, nome reverso "componentes_kit" no Brinquedos);
  * PecasReposicao: saem `eh_kit` e `maquina` -- a peça volta a ser só peça.

A 0212 garante que nenhum item ficou sem o produto (o item solto, de uma
peça que deixou de ser kit, é apagado lá): o `kit` obrigatório daqui não
encontra linha vazia.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0212_kits_viram_produtos"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="componentekit",
            name="kit",
        ),
        migrations.RenameField(
            model_name="componentekit",
            old_name="kit_produto",
            new_name="kit",
        ),
        migrations.AlterField(
            model_name="componentekit",
            name="kit",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="componentes_kit",
                to="core.brinquedos",
                verbose_name="Kit",
            ),
        ),
        migrations.RemoveField(
            model_name="pecasreposicao",
            name="eh_kit",
        ),
        migrations.RemoveField(
            model_name="pecasreposicao",
            name="maquina",
        ),
    ]
