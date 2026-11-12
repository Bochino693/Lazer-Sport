"""A conferência do fundo das fotos (a 0184; LEIA-ME 72). Só esquema.

O cliente: "me diga sobre as imagens de fundo branco dos brinquedos, por que
ainda aparecem? elas devem ficar de fora dos carrosseis e cards, ficando
somente para outras finalidades." Entram:
  * `ImagemBrinquedo.fundo`: "" (ainda não conferida), "com" ou "sem" fundo
    (core.conferir_fotos; a varredura só olha as ainda não conferidas);
  * `Brinquedos.capa_sem_fundo`: a capa de antes, quando ela era sem fundo e
    deu lugar a uma foto com fundo (guardada; a volta a põe de novo).
Os dados vêm na 0185 (só no Render).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0183_posicoes_do_3d_dos_adesivos"),
    ]

    operations = [
        migrations.AddField(
            model_name="brinquedos",
            name="capa_sem_fundo",
            field=models.CharField(
                blank=True,
                default="",
                help_text="A capa sem fundo que saiu do site (guardada para as artes; core.conferir_fotos).",
                max_length=255,
                verbose_name="Capa de antes, sem fundo",
            ),
        ),
        migrations.AddField(
            model_name="imagembrinquedo",
            name="fundo",
            field=models.CharField(
                blank=True,
                choices=[("", "Não conferida"), ("com", "Com fundo"), ("sem", "Sem fundo")],
                default="",
                help_text="Conferido sozinho (core.conferir_fotos): a foto sem fundo vira recorte para artes.",
                max_length=3,
                verbose_name="Fundo",
            ),
        ),
    ]
