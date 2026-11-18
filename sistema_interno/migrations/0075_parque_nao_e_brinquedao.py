# "PARQUE" NÃO É BRINQUEDÃO (LEIA-ME-V10, seção 112) -- SÓ DADOS.
#
# A palavra "parque" das regras da produção pegava a categoria "Para
# Parques" (um público, não um tipo de brinquedo): o Simulador de Corrida
# Top Racer saía como brinquedão, com 30 dias úteis, em vez dos 4 a 5 da
# máquina. Aqui:
#   1. a palavra sai da linha de regras gravada (o padrão já saiu, 0074);
#   2. a categoria marcada SÓ por causa dela é desmarcada (uma categoria
#      com outra palavra no nome, "Trampolim Park", continua marcada);
#   3. a máquina que já esperava na fila como brinquedão volta para a fila
#      das máquinas, com os dias dela (4 até o limite de m³, 5 acima). A
#      previsão é refeita quando a lista abre (montagem.distribuir). Quem
#      já está em produção não é mexido: o painel decide.
# Rodar de novo não muda nada.

import re
import unicodedata

from django.db import migrations

TIRAR = {"parque", "parques"}


def _sem_acento(texto):
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(letra for letra in texto if not unicodedata.combining(letra)).lower().strip()


def _palavras(texto):
    return [p.strip() for p in re.split(r"[,;\n]", texto or "") if p.strip()]


def _volume(brinquedo):
    medidas = (brinquedo.altura_m, brinquedo.largura_m, brinquedo.profundidade_m)
    if all(medidas):
        a, l, p = (float(m) for m in medidas)
        return a * l * p
    return None


def acertar(apps, schema_editor):
    Configuracao = apps.get_model("sistema_interno", "ConfiguracaoProducao")
    Unidade = apps.get_model("sistema_interno", "UnidadeMontagem")
    Ligacao = apps.get_model("core", "Brinquedos").categorias_brinquedos.through

    config = Configuracao.objects.order_by("pk").first()
    if config is None:
        return

    ficam = [p for p in _palavras(config.palavras_projeto) if _sem_acento(p) not in TIRAR]
    texto = ", ".join(ficam)
    if texto != (config.palavras_projeto or "").strip():
        config.palavras_projeto = texto
        config.save(update_fields=["palavras_projeto"])
    palavras = [_sem_acento(p) for p in ficam]

    def por_palavra(nome):
        nome = _sem_acento(nome)
        return any(palavra in nome for palavra in palavras if palavra)

    for categoria in list(config.categorias_projeto.all()):
        nome = _sem_acento(categoria.nome_categoria)
        if "parque" in nome and not por_palavra(nome):
            config.categorias_projeto.remove(categoria)

    marcadas = set(config.categorias_projeto.values_list("pk", flat=True))

    def e_projeto(brinquedo):
        if por_palavra(brinquedo.nome_brinquedo):
            return True
        for categoria_id, nome in Ligacao.objects.filter(brinquedos_id=brinquedo.pk).values_list(
            "categoriasbrinquedos_id", "categoriasbrinquedos__nome_categoria",
        ):
            if categoria_id in marcadas or por_palavra(nome):
                return True
        return False

    esperando = Unidade.objects.filter(trilha="projeto", situacao="fila", brinquedo__isnull=False).select_related("brinquedo")
    for unidade in esperando:
        brinquedo = unidade.brinquedo
        if getattr(brinquedo, "eh_kit", False) or e_projeto(brinquedo) or por_palavra(unidade.nome):
            continue
        volume = _volume(brinquedo)
        if volume is not None and volume <= float(config.limite_m3):
            dias = config.dias_ate_limite
        else:
            dias = config.dias_acima_limite
        unidade.trilha = "maquina"
        unidade.dias = dias
        unidade.posicao = None
        unidade.previstas = {}
        unidade.save(update_fields=["trilha", "dias", "posicao", "previstas"])


class Migration(migrations.Migration):

    dependencies = [
        ("sistema_interno", "0074_palavras_de_brinquedao_sem_parque"),
    ]

    operations = [
        migrations.RunPython(acertar, migrations.RunPython.noop),
    ]
