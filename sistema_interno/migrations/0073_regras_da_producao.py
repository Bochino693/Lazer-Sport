# A LISTA DE MONTAGEM (LEIA-ME-V10, seção 112) -- SÓ DADOS.
#
# A linha das regras da produção, com os padrões do dono: 4 dias úteis até
# 2,5 m³ e 5 acima (e sem medida); 3 máquinas em montagem ao mesmo tempo;
# 15 a 30 dias úteis de fila; brinquedões um por vez, 30 dias cada; peças
# em 3 dias. As categorias de brinquedão / espaço já vêm marcadas pelas
# palavras do padrão (Brinquedões, Trampolins, Escaladas, Área Ninja,
# Casinhas Cenográficas...); o painel desmarca ou marca outras.
#
# Os pedidos pagos e os orçamentos aprovados que JÁ existiam entram na
# lista pela própria lista (montagem.sincronizar_tudo, ao abrir), em
# silêncio: quem comprou há semanas não recebe "entrou em produção" do
# nada. Rodar de novo não cria uma segunda linha nem muda o que o painel
# acertou.

import re
import unicodedata

from django.db import migrations

PALAVRAS = (
    "brinquedão, brinquedões, trampolim, trampolins, cama elástica, escalada, "
    "ninja, espaço esportivo, quadra, playground, parque, casinha, cenográfica"
)


def _sem_acento(texto):
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(letra for letra in texto if not unicodedata.combining(letra)).lower()


def criar_regras(apps, schema_editor):
    Configuracao = apps.get_model("sistema_interno", "ConfiguracaoProducao")
    Categoria = apps.get_model("core", "CategoriasBrinquedos")
    if Configuracao.objects.exists():
        return
    config = Configuracao.objects.create(palavras_projeto=PALAVRAS)
    palavras = [_sem_acento(p).strip() for p in re.split(r"[,;]", PALAVRAS) if p.strip()]
    marcadas = [
        categoria.pk for categoria in Categoria.objects.all()
        if any(palavra in _sem_acento(categoria.nome_categoria) for palavra in palavras)
    ]
    if marcadas:
        config.categorias_projeto.set(marcadas)


def desfazer(apps, schema_editor):
    apps.get_model("sistema_interno", "ConfiguracaoProducao").objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("sistema_interno", "0072_lista_de_montagem"),
    ]

    operations = [
        migrations.RunPython(criar_regras, desfazer),
    ]
