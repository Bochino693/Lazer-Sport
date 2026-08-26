"""Roteiro padrão de fabricação, por tipo de produto.

POR QUE ISTO EXISTE. Escrever o manual de um brinquedo do zero é o passo
que trava a produção: são oito etapas parecidas em quase todo produto, e
quem está com a ordem para abrir hoje não vai parar para escrever tudo.
Sem manual, a ordem sai sem etapa e o acompanhamento não existe.

Então o painel gera o roteiro base com um toque e a pessoa corrige o que
é específico daquele brinquedo. É rascunho bom, não verdade absoluta: o
texto é propositalmente concreto para ser editado, e não genérico a ponto
de não dizer nada.

Os tempos são estimativas iniciais de uma unidade, em minutos.
"""

from __future__ import annotations

from .models import GuiaEtapaProducao, ProdutoInterno


def _etapa(titulo, instrucoes, criterio, minutos):
    return {
        "titulo": titulo,
        "instrucoes": instrucoes,
        "criterio_conclusao": criterio,
        "tempo_estimado_min": minutos,
    }


SEPARAR = _etapa(
    "Separar material e conferir a ficha",
    "Puxe a ficha técnica do produto e separe cada material na bancada, "
    "na quantidade indicada.\n"
    "Confira lote e estado do material: tecido rasgado, tubo amassado ou "
    "componente vencido não entra na produção.\n"
    "Faltando alguma coisa, avise a gerência ANTES de começar — parar no "
    "meio custa mais que atrasar o início.",
    "Todos os itens da ficha estão na bancada, conferidos e na quantidade "
    "certa.",
    20,
)

TESTE = _etapa(
    "Teste de segurança e qualidade",
    "Monte o produto completo como o cliente vai receber.\n"
    "Verifique costuras, soldas, parafusos e travas: nada pode ceder com "
    "força de uso.\n"
    "Ligue e opere por pelo menos 10 minutos, procurando ruído, folga, "
    "aquecimento e ponta exposta.\n"
    "Qualquer falha volta para a etapa de origem — não se corrige defeito "
    "de estrutura no acabamento.",
    "O produto operou sem falha no teste e não há ponta, folga ou ruído "
    "fora do normal.",
    30,
)

EMBALAR = _etapa(
    "Limpeza, identificação e embalagem",
    "Limpe o produto por inteiro e retire etiqueta de fábrica, sobra de "
    "cola e resíduo de corte.\n"
    "Coloque a identificação da Lazer & Sport e o código de produção.\n"
    "Embale protegendo os cantos e as partes móveis, e separe manual e "
    "acessórios junto.",
    "Produto limpo, identificado, embalado e pronto para carregar.",
    25,
)


ROTEIROS = {
    ProdutoInterno.Categoria.BRINQUEDO: [
        SEPARAR,
        _etapa(
            "Corte das peças",
            "Marque o tecido ou a chapa seguindo o molde do produto.\n"
            "Corte com folga de costura onde o molde indicar.\n"
            "Separe as peças cortadas por parte do brinquedo e identifique "
            "cada conjunto — peça sem identificação vira retrabalho na "
            "montagem.",
            "Todas as peças do molde estão cortadas, sem falha de medida e "
            "identificadas.",
            60,
        ),
        _etapa(
            "Costura e solda das partes",
            "Una as peças na sequência do molde, começando pelas partes "
            "internas.\n"
            "Reforce os pontos de tensão: alças, cantos, encaixes e a base.\n"
            "Confira o alinhamento a cada conjunto fechado; corrigir depois "
            "significa abrir tudo de novo.",
            "As partes estão unidas, alinhadas e com reforço nos pontos de "
            "tensão.",
            90,
        ),
        _etapa(
            "Montagem da estrutura",
            "Monte a estrutura de apoio e encaixe as partes já costuradas.\n"
            "Aperte na sequência cruzada, sem forçar rosca.\n"
            "Verifique se o conjunto fica firme e nivelado apoiado no chão.",
            "Estrutura montada, firme, nivelada e sem peça sobrando.",
            75,
        ),
        _etapa(
            "Acabamento",
            "Retire rebarba, sobra de linha e excesso de cola.\n"
            "Proteja quina e ponto de contato com a criança.\n"
            "Faça o retoque de pintura ou de tecido onde ficou marca de "
            "produção.",
            "Nenhuma rebarba, ponta ou marca de produção visível ao toque.",
            40,
        ),
        TESTE,
        EMBALAR,
    ],
    ProdutoInterno.Categoria.MAQUINA: [
        SEPARAR,
        _etapa(
            "Corte e preparação da estrutura",
            "Corte perfis e chapas nas medidas do projeto.\n"
            "Fure os pontos de fixação antes de montar: furar com a máquina "
            "montada desalinha o conjunto.\n"
            "Lixe as bordas cortadas.",
            "Peças cortadas nas medidas do projeto, furadas e sem rebarba.",
            70,
        ),
        _etapa(
            "Montagem mecânica",
            "Monte o gabinete e fixe os conjuntos móveis.\n"
            "Confira folga e alinhamento de cada parte que gira ou desliza.\n"
            "Aperte a fixação em sequência cruzada e confira o esquadro do "
            "gabinete.",
            "Gabinete montado no esquadro, partes móveis livres e sem folga "
            "excessiva.",
            90,
        ),
        _etapa(
            "Instalação elétrica",
            "Passe a fiação pelos caminhos previstos, longe de parte móvel e "
            "de calor.\n"
            "Confira a voltagem do produto antes de ligar qualquer "
            "componente.\n"
            "Identifique os cabos e feche as emendas — emenda solta dentro "
            "do gabinete é falha que só aparece no cliente.",
            "Fiação presa, identificada, na voltagem correta e sem emenda "
            "exposta.",
            60,
        ),
        _etapa(
            "Ajuste e configuração",
            "Ligue a máquina e configure os parâmetros de operação: tempo, "
            "sensor, moeda ou ficha, som e iluminação.\n"
            "Rode o ciclo completo algumas vezes e ajuste o que estiver "
            "fora.",
            "A máquina roda o ciclo completo com os parâmetros ajustados.",
            45,
        ),
        TESTE,
        EMBALAR,
    ],
    ProdutoInterno.Categoria.PECA: [
        SEPARAR,
        _etapa(
            "Corte e usinagem",
            "Corte o material na medida da peça, conferindo com o gabarito.\n"
            "Faça furos e recortes antes do acabamento.",
            "Peça na medida do gabarito, com furos e recortes prontos.",
            35,
        ),
        _etapa(
            "Acabamento e conferência",
            "Retire rebarba, lixe e aplique a proteção prevista.\n"
            "Confira a medida final e o encaixe na peça de destino.",
            "Peça encaixa no destino e está com o acabamento previsto.",
            25,
        ),
        EMBALAR,
    ],
}

# Produto "Outro" segue o roteiro do brinquedo, que é o mais completo dos
# que servem para qualquer coisa montada na bancada.
ROTEIROS[ProdutoInterno.Categoria.OUTRO] = ROTEIROS[
    ProdutoInterno.Categoria.BRINQUEDO
]


def roteiro_de(produto: ProdutoInterno) -> list[dict]:
    return ROTEIROS.get(
        produto.categoria,
        ROTEIROS[ProdutoInterno.Categoria.BRINQUEDO],
    )


def gerar(produto: ProdutoInterno) -> int:
    """Cria as etapas do roteiro que ainda faltam. Devolve quantas entraram.

    Etapa com o mesmo título é pulada: gerar de novo depois de editar não
    pode duplicar o manual nem sobrescrever o que a fábrica ajustou.
    """
    existentes = {
        titulo.strip().lower()
        for titulo in produto.guias_producao.values_list("titulo", flat=True)
    }

    ordem = (
        produto.guias_producao
        .order_by("-ordem")
        .values_list("ordem", flat=True)
        .first()
        or 0
    )

    criadas = 0
    for etapa in roteiro_de(produto):
        if etapa["titulo"].strip().lower() in existentes:
            continue

        ordem += 1
        GuiaEtapaProducao.objects.create(
            produto=produto,
            ordem=ordem,
            titulo=etapa["titulo"],
            instrucoes=etapa["instrucoes"],
            criterio_conclusao=etapa["criterio_conclusao"],
            tempo_estimado_min=etapa["tempo_estimado_min"],
        )
        criadas += 1

    return criadas


def copiar(origem: ProdutoInterno, destino: ProdutoInterno) -> int:
    """Copia o manual de um produto parecido. Devolve quantas etapas vieram.

    As imagens NÃO vêm junto de propósito: foto de outro produto no manual
    engana quem está montando, que é o oposto do que um guia visual serve.
    """
    if origem.pk == destino.pk:
        return 0

    existentes = {
        titulo.strip().lower()
        for titulo in destino.guias_producao.values_list("titulo", flat=True)
    }

    ordem = (
        destino.guias_producao
        .order_by("-ordem")
        .values_list("ordem", flat=True)
        .first()
        or 0
    )

    copiadas = 0
    for etapa in origem.guias_producao.filter(ativo=True).order_by("ordem", "id"):
        if etapa.titulo.strip().lower() in existentes:
            continue

        ordem += 1
        GuiaEtapaProducao.objects.create(
            produto=destino,
            ordem=ordem,
            titulo=etapa.titulo,
            instrucoes=etapa.instrucoes,
            criterio_conclusao=etapa.criterio_conclusao,
            tempo_estimado_min=etapa.tempo_estimado_min,
        )
        copiadas += 1

    return copiadas
