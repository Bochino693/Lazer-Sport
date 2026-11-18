"""As fotos das peças de reposição sem o fundo branco (LEIA-ME, seção 102).

O dono: "o site deve estar tinindo ... as apresentações de produtos, os
fundos". A foto de catálogo da peça (o produto num fundo branco) vira um PNG
sem fundo, que a vitrine da peça (o palco azul da página, o estúdio do card)
mostra com sombra; a foto que a equipe subiu fica em `imagem_original`.

SÓ DADOS e SÓ NO RENDER (as fotos estão no Cloudinary). Uma foto que falha não
para o deploy: `python manage.py pecas_sem_fundo` refaz. Rodar de novo não
refaz a que já foi conferida. Para voltar: `python manage.py pecas_sem_fundo --desfazer`.
"""

from django.db import migrations


def recortar(apps, schema_editor):
    from django.conf import settings

    if not getattr(settings, "IS_RENDER", False):
        return
    from core import recorte_peca

    resumo = recorte_peca.processar_todas(apps.get_model("core", "ImagemPeca"))
    print(f"Fotos de peça: {resumo}")
    recorte_peca._limpar_cache()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0204_imagem_da_peca_sem_fundo"),
    ]

    operations = [
        migrations.RunPython(recortar, migrations.RunPython.noop),
    ]
