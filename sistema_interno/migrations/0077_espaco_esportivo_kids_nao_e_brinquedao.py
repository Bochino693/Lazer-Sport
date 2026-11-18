# "ESPAÇO ESPORTIVO KIDS" NÃO É CATEGORIA DE BRINQUEDÃO (LEIA-ME-V10, seção 112) -- SÓ DADOS.
#
# A 0073 marcou como "de brinquedão" toda categoria cujo NOME tinha uma das
# palavras -- e "espaço esportivo" pegou a categoria "Espaço Esportivo
# Kids", que reúne ~40 máquinas comuns (as que vão num espaço esportivo:
# Air Game, basquete, simuladores...). Com ela marcada, quase toda máquina
# virava brinquedão: 30 dias úteis, uma por vez (o Simulador Top Racer
# mostrava "Fica pronto em 30 dias úteis").
#
# Daqui em diante as palavras valem só no nome do brinquedo (montagem.
# Regras.e_projeto); aqui sai a marca das categorias que só tinham sido
# marcadas por "espaço esportivo", "quadra" ou "parque" -- as de TIPO de
# brinquedo (Brinquedão, Trampolins, Área Ninja, Casinhas Cenográficas...)
# continuam. As máquinas que já estavam na lista voltam à trilha certa
# logo depois do migrate (apps.py -> montagem.reclassificar).
# Rodar de novo não muda nada.

import unicodedata

from django.db import migrations

#: Palavras de categoria que É de brinquedão / estrutura.
DE_TIPO = (
    "brinquedao", "brinquedoes", "trampolim", "trampolins", "cama elastica",
    "escalada", "ninja", "casinha", "cenografica", "playground",
)
#: Palavras que marcaram categoria de USO, e não de tipo.
DE_USO = ("espaco esportivo", "quadra", "parque")


def _sem_acento(texto):
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(letra for letra in texto if not unicodedata.combining(letra)).lower().strip()


def desmarcar(apps, schema_editor):
    Configuracao = apps.get_model("sistema_interno", "ConfiguracaoProducao")
    for config in Configuracao.objects.all():
        for categoria in list(config.categorias_projeto.all()):
            nome = _sem_acento(categoria.nome_categoria)
            if any(p in nome for p in DE_USO) and not any(p in nome for p in DE_TIPO):
                config.categorias_projeto.remove(categoria)


class Migration(migrations.Migration):

    dependencies = [
        ("sistema_interno", "0076_palavras_so_no_nome_do_brinquedo"),
    ]

    operations = [
        migrations.RunPython(desmarcar, migrations.RunPython.noop),
    ]
