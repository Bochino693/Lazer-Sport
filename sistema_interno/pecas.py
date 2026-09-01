"""Cadastrar uma peça sem sair do documento que precisa dela.

POR QUE ISTO É UM MÓDULO, E NÃO UM MÉTODO DA TELA DE ORÇAMENTOS.

A ação nasceu lá, quando só a proposta montava lista de itens. Mas a
Ordem de Serviço tem exatamente o mesmo problema, e maior: o técnico
está com o equipamento aberto na frente dele e descobre que precisa
cobrar um retentor que ninguém cadastrou. Mandá-lo abrir a tela de
produtos, cadastrar e voltar significa perder a O.S. pela metade -- e,
na prática, significa escrever "retentor" na descrição e seguir, o que
deixa a peça fora de qualquer controle.

As duas telas fazem a mesma coisa e não podem divergir: se a regra de
"nasce fora da vitrine" valesse só num dos dois caminhos, o outro
voltaria a publicar peça no site sem ninguém pedir. Então a regra mora
aqui, e as duas telas chamam.

O que muda entre elas é só QUEM pode: o orçamento é do Comercial, a O.S.
é da Produção. Essa checagem fica em cada tela, que é onde ela pertence.
"""

from decimal import Decimal

from core.models import CategoriaPeca, PecasReposicao

from .utils import ErroDeFormulario, decimal_br, texto


def cadastrar(request):
    """Cria a peça e devolve o resumo que a linha do documento usa.

    O QUE NASCE AQUI NÃO VAI PARA O SITE.

    Nascia. A peça era criada com `ativo=True`, que é o padrão da tabela,
    e no mesmo segundo passava a ser anunciada na loja: sem foto, sem
    descrição de verdade, com um nome digitado às pressas no meio de um
    atendimento e um preço que valia para aquele cliente. Ninguém
    escolheu publicar aquilo -- foi só o efeito colateral de precisar
    cobrar um item.

    Agora nasce desligada. Publicar continua sendo uma decisão, tomada na
    tela de produtos por quem cuida da vitrine, depois de a peça ter foto
    e texto. Enquanto isso ela já serve para o que foi criada: entrar
    nesta linha e ser cobrada.

    E `uso` decide o que ela é. Item de manutenção é o caso comum daqui
    -- a bucha que só serve num modelo, a hora de solda, o retentor que a
    loja não vende -- e ele nunca vai à vitrine, nem se alguém o ativar.
    """
    nome = texto(
        request, "nome", obrigatorio=True, rotulo="o nome da peça", limite=120,
    )

    if PecasReposicao.objects.filter(nome__iexact=nome).exists():
        raise ErroDeFormulario(
            f"Já existe uma peça chamada \u201c{nome}\u201d. Procure na lista."
        )

    uso = (request.POST.get("uso") or "").strip()
    if uso not in PecasReposicao.Uso.values:
        # O caminho de dentro do documento é, quase sempre, o item que a
        # loja não vende. Quem quer o outro escolhe.
        uso = PecasReposicao.Uso.MANUTENCAO

    peca = PecasReposicao.objects.create(
        nome=nome,
        uso=uso,
        ativo=False,
        descricao_peca=texto(request, "descricao", limite=999) or nome,
        preco_venda=decimal_br(
            request.POST.get("preco_venda"), "Preço de venda",
            limite=Decimal("9999999.99"),
        ),
        preco_fornecedor=decimal_br(
            request.POST.get("preco_fornecedor"), "Preço do fornecedor",
            limite=Decimal("9999999.99"),
        ),
    )

    categoria_id = (request.POST.get("categoria") or "").strip()
    if categoria_id.isdigit():
        categoria = CategoriaPeca.objects.filter(pk=categoria_id).first()
        if categoria:
            peca.categoria_peca.add(categoria)

    return peca


def resumo(peca):
    """O que a linha do documento precisa saber da peça recém-criada."""
    de_manutencao = peca.uso == PecasReposicao.Uso.MANUTENCAO
    return {
        "id": peca.id,
        "nome": peca.nome,
        "uso": peca.uso,
        "grupo": "Itens de manutenção" if de_manutencao else "Peças de reposição",
        "valor": (
            f"{peca.preco_venda:.2f}".replace(".", ",")
            if peca.preco_venda is not None else ""
        ),
    }


def recado(peca):
    if peca.uso == PecasReposicao.Uso.MANUTENCAO:
        return (
            f"\u201c{peca.nome}\u201d entrou como item de manutenção e já pode "
            f"ser usado aqui. Ele não vai para o site."
        )
    return (
        f"\u201c{peca.nome}\u201d entrou nas peças de reposição e já pode ser "
        f"usada aqui. Para anunciá-la no site, publique-a em Produtos."
    )
