"""O adesivo é dono das fotos e do 3D dele (a 0168; LEIA-ME, seção 72). Só o esquema.

O cliente: "DEVE MUDAR A ESTRUTURA DOS OBJETOS, DEIXAR SOMENTE UM MAS COM O
OUTRO ADESIVO E SEU RESPECTIVO OBJETO 3D". Entram:
  * na `ImagemBrinquedo`, o `variante`: a foto de um adesivo do produto;
  * no `VarianteAdesivo`, o 3D dele (`arquivo_3d`, `arquivo_estatico_3d`,
    `codigo_3d`, `cores_3d`, `medidas_3d`) e o `id_antigo` (o id do produto
    à parte que ele era, para o endereço antigo redirecionar).
A 0169 (dados) passa para o produto o que era da ficha à parte e a apaga; a
0170 (esquema) tira o `origem`. Esquema e dados em arquivos separados
(sistema_interno/tests_migracoes.py).
"""

import core.models
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0167_jogadas_registradas"),
    ]

    operations = [
        migrations.AddField(
            model_name="imagembrinquedo",
            name="variante",
            field=models.ForeignKey(
                blank=True,
                help_text="A foto de um adesivo do produto (a outra arte); vazio, a foto do próprio produto.",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="fotos",
                to="core.varianteadesivo",
                verbose_name="Adesivo",
            ),
        ),
        migrations.AddField(
            model_name="varianteadesivo",
            name="arquivo_3d",
            field=models.FileField(
                blank=True,
                storage=core.models._armazenamento_3d,
                upload_to="objetos_3d/",
                verbose_name="Arquivo 3D (.glb)",
            ),
        ),
        migrations.AddField(
            model_name="varianteadesivo",
            name="arquivo_estatico_3d",
            field=models.CharField(
                blank=True,
                help_text="Caminho em static (ex.: site/arena/modelos/air-game-kids-alienigenas.glb), sem arquivo enviado.",
                max_length=200,
                verbose_name="Objeto 3D do site",
            ),
        ),
        migrations.AddField(
            model_name="varianteadesivo",
            name="codigo_3d",
            field=models.SlugField(
                blank=True, max_length=60, verbose_name="Código na Arena"
            ),
        ),
        migrations.AddField(
            model_name="varianteadesivo",
            name="cores_3d",
            field=models.JSONField(
                blank=True, default=list, verbose_name="Cores do 3D"
            ),
        ),
        migrations.AddField(
            model_name="varianteadesivo",
            name="id_antigo",
            field=models.PositiveIntegerField(
                blank=True,
                db_index=True,
                help_text="O id do produto à parte que este adesivo era (o endereço antigo redireciona para o produto).",
                null=True,
                verbose_name="Id antigo",
            ),
        ),
        migrations.AddField(
            model_name="varianteadesivo",
            name="medidas_3d",
            field=models.JSONField(
                blank=True, default=list, verbose_name="Medidas do 3D"
            ),
        ),
    ]
