"""COM OU SEM MOEDEIRO: a regra e a conta do preço (LEIA-ME-V10, seção 143).

O dono: "entenda também que os moedeiros nas máquinas, que não são
brinquedões, arenas esportivas nem esses brinquedões grandes, têm dois
preços com moedeiro ou sem." Decidido por ele:

  * o preço do cadastro é o SEM moedeiro;
  * o preço COM moedeiro é o do cadastro + um ACRÉSCIMO FIXO, um valor só
    para todas as máquinas (`DadosContrato.acrescimo_moedeiro`, que a
    Gestão digita na tela "Dados do contrato");
  * enquanto o acréscimo estiver vazio ou zero, a opção NÃO APARECE em
    lugar nenhum (`ativo()` é a única pergunta que as telas fazem);
  * vale só para as MÁQUINAS: brinquedão, espaço, arena e brinquedo grande
    não têm a opção. A distinção é a mesma que a lista de montagem já usa
    (`montagem.Regras.e_projeto`: a categoria marcada nas regras da
    produção, ou a palavra no nome) -- uma regra só, num lugar só. Kit
    eletrônico e peça também não têm;
  * a Gestão liga ou desliga POR MÁQUINA (`Brinquedos.moedeiro`: "sim",
    "nao" ou vazio = a regra decide).

ESTA É A PRIMEIRA FATIA: a regra, a configuração e a conta. O PREÇO É
SEMPRE CALCULADO AQUI, no servidor -- nenhuma tela manda preço. As telas
que vão oferecer a escolha (o orçamento do painel, a página do produto, o
carrinho, os documentos, a lista de montagem) entram na fatia seguinte e
perguntam a este módulo.
"""

from __future__ import annotations

from decimal import Decimal

ZERO = Decimal("0.00")


def acrescimo() -> Decimal:
    """O acréscimo único do moedeiro; R$ 0,00 quando a Gestão ainda não digitou."""
    from .models import DadosContrato

    valor = DadosContrato.atual().acrescimo_moedeiro
    if valor is None or valor <= 0:
        return ZERO
    return Decimal(valor).quantize(Decimal("0.01"))


def ativo() -> bool:
    """Existe a opção "com moedeiro"? Só com o acréscimo definido."""
    return acrescimo() > ZERO


def aceita(brinquedo, regras=None) -> bool:
    """Esta máquina pode sair com moedeiro? (Não olha se o acréscimo está definido.)

    A palavra da Gestão para a máquina vale primeiro; sem ela, a regra:
    máquina aceita; brinquedão/espaço (a regra da lista de montagem), kit
    eletrônico e brinquedo fora de linha não.
    """
    if brinquedo is None:
        return False
    escolha = (getattr(brinquedo, "moedeiro", "") or "").strip().lower()
    if escolha == "sim":
        return True
    if escolha == "nao":
        return False
    if getattr(brinquedo, "eh_kit", False):
        return False
    if regras is None:
        from . import montagem

        regras = montagem.Regras.agora()
    return not regras.e_projeto(brinquedo)


def oferece(brinquedo, regras=None) -> bool:
    """A tela mostra os chips "Sem moedeiro / Com moedeiro" para esta máquina?"""
    return ativo() and aceita(brinquedo, regras)


def preco(brinquedo, com_moedeiro=False, regras=None):
    """O preço da máquina, sem ou com moedeiro. None quando ela não tem preço.

    Pedir "com moedeiro" de quem não oferece a opção devolve o preço do
    cadastro: o servidor nunca soma um acréscimo que a tela não podia ter
    oferecido (um POST feito à mão não inventa preço).
    """
    base = getattr(brinquedo, "valor_brinquedo", None)
    if base is None:
        return None
    base = Decimal(base).quantize(Decimal("0.01"))
    if com_moedeiro and oferece(brinquedo, regras):
        return base + acrescimo()
    return base


def opcoes(brinquedo, regras=None) -> list[dict]:
    """Os dois chips, com o preço de cada um; [] quando a máquina não oferece."""
    if not oferece(brinquedo, regras):
        return []
    return [
        {"chave": "sem", "rotulo": "Sem moedeiro", "com_moedeiro": False, "preco": preco(brinquedo, False, regras)},
        {"chave": "com", "rotulo": "Com moedeiro", "com_moedeiro": True, "preco": preco(brinquedo, True, regras)},
    ]
