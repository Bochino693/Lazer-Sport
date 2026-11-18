"""As fotos das peças sem o fundo branco, de novo (LEIA-ME, seção 102).

A 0205 não recortou nada no primeiro deploy: o nome do recorte da foto dos
bonecos de pebolim passava dos 100 caracteres da coluna e, no PostgreSQL,
esse erro aborta a transação inteira da migração (as outras fotos voltaram
junto). Agora o nome é curto e cada foto tem o seu ponto de salvamento.

Esta migração roda a mesma conferência: se a 0205 não chegou a ser marcada
como aplicada, ela roda antes e esta só confere; se chegou, esta recorta as
que ficaram. SÓ DADOS e SÓ NO RENDER. Rodar de novo não refaz nada.
"""

from django.db import migrations


def recortar(apps, schema_editor):
    from django.conf import settings

    if not getattr(settings, "IS_RENDER", False):
        return
    from core import recorte_peca

    resumo = recorte_peca.processar_todas(apps.get_model("core", "ImagemPeca"))
    print(f"Fotos de peça (de novo): {resumo}")
    recorte_peca._limpar_cache()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0205_pecas_sem_fundo_branco"),
    ]

    operations = [
        migrations.RunPython(recortar, migrations.RunPython.noop),
    ]
