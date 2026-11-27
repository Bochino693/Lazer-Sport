"""COM OU SEM SISTEMA DE FICHA: a regra e a conta do preço (LEIA-ME-V10, seções 143 e 148).

O NOME. O dono (seção 148): "deve se chamar sistema de ficha, não mais
moedeiro, para operações, eventos e afins". Em tudo o que a pessoa lê é
"Sistema de ficha". Os nomes internos ficaram (este módulo, os campos
`acrescimo_moedeiro`, `Brinquedos.moedeiro`, `com_moedeiro`): já estavam
publicados, e renomear coluna só trocaria um risco de deploy por nada que
a pessoa veja. O valor que ele deu: R$ 999,00 (a Gestão pode mudar).

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

#: O nome que a pessoa lê, em todas as telas e documentos.
NOME = "Sistema de ficha"
ROTULO_SEM = "Sem sistema de ficha"
ROTULO_COM = "Com sistema de ficha"
#: A linha de explicação, onde couber.
EXPLICACAO = "Para operações, eventos e afins: a máquina funciona por ficha."
#: O que o nome do item ganha quando a máquina sai com o sistema de ficha.
#: Vai NO NOME do item (como o adesivo), para todo documento -- proposta,
#: contrato, O.S., lista de montagem, etiqueta -- dizer sem depender de
#: cada tela lembrar de um campo.
MARCA = "com sistema de ficha"
SUFIXO = " — " + MARCA


#: O acréscimo fica um minuto no cache: toda tela pergunta por ele, e o
#: banco fica longe (~170 ms por consulta). Salvar em Dados do contrato
#: limpa o cache na hora (`esquecer`); a outra máquina do servidor vê a
#: mudança em até um minuto.
CHAVE_DO_ACRESCIMO = "sistema-de-ficha:acrescimo:v1"
VIDA_DO_ACRESCIMO = 60


def esquecer() -> None:
    """Joga fora o acréscimo guardado (quem muda o valor chama)."""
    from django.core.cache import cache

    try:
        cache.delete(CHAVE_DO_ACRESCIMO)
    except Exception:  # noqa: BLE001 -- sem cache, nada a esquecer
        pass


def acrescimo() -> Decimal:
    """O acréscimo único do sistema de ficha; R$ 0,00 quando não está definido."""
    from django.core.cache import cache

    from .models import DadosContrato

    try:
        guardado = cache.get(CHAVE_DO_ACRESCIMO)
    except Exception:  # noqa: BLE001
        guardado = None
    if guardado is not None:
        return Decimal(guardado)
    valor = DadosContrato.objects.order_by("id").values_list("acrescimo_moedeiro", flat=True).first()
    valor = ZERO if (valor is None or valor <= 0) else Decimal(valor).quantize(Decimal("0.01"))
    try:
        cache.set(CHAVE_DO_ACRESCIMO, str(valor), VIDA_DO_ACRESCIMO)
    except Exception:  # noqa: BLE001
        pass
    return valor


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
        {"chave": "sem", "rotulo": ROTULO_SEM, "com_moedeiro": False, "preco": preco(brinquedo, False, regras)},
        {"chave": "com", "rotulo": ROTULO_COM, "com_moedeiro": True, "preco": preco(brinquedo, True, regras)},
    ]


def tem_a_marca(texto) -> bool:
    """O nome do item já diz "com sistema de ficha"?"""
    return MARCA in (texto or "").casefold()


def nome_com_a_escolha(nome, com_ficha, limite=None) -> str:
    """O nome do item com (ou sem) a marca do sistema de ficha no fim.

    Com a escolha, o nome termina em " — com sistema de ficha" (sem
    repetir); sem ela, a marca sai. `limite` é o tamanho do campo: quem
    encurta é o nome, nunca a marca.
    """
    nome = (nome or "").strip()
    if tem_a_marca(nome):
        posicao = nome.casefold().rfind(MARCA)
        nome = (nome[:posicao] + nome[posicao + len(MARCA):]).strip().rstrip("—-–").strip()
    if not com_ficha:
        return nome[:limite] if limite else nome
    if limite:
        nome = nome[: max(limite - len(SUFIXO), 0)].rstrip()
    return nome + SUFIXO


class Tabela:
    """A conta do sistema de ficha para MUITAS máquinas de uma vez.

    Quem monta uma tela inteira (a lista de orçamentos, a busca de itens, o
    carrinho) cria uma tabela por pedido: o acréscimo é lido uma vez, as
    regras vêm do cache e as categorias de todas as máquinas numa consulta
    só (`carregar`). As funções do módulo continuam valendo para uma máquina.
    """

    def __init__(self, acrescimo_=None, regras=None):
        self.acrescimo = acrescimo() if acrescimo_ is None else acrescimo_
        self._regras = regras

    @property
    def regras(self):
        if self._regras is None:
            from . import montagem

            self._regras = montagem.Regras.agora()
        return self._regras

    @property
    def ativo(self) -> bool:
        return self.acrescimo > ZERO

    def carregar(self, brinquedos) -> None:
        """As categorias destas máquinas numa consulta (antes de perguntar uma a uma).

        Só interessa a categoria MARCADA como brinquedão nas regras da
        produção: sem nenhuma marcada, a regra é só a palavra no nome e não
        há o que perguntar ao banco. Máquina com a palavra da Gestão ("sim"
        ou "nao") e kit também não precisam.
        """
        if not self.ativo:
            return
        regras = self.regras
        faltam = [
            b for b in brinquedos
            if b is not None and b.pk not in regras._categorias
            and not (getattr(b, "moedeiro", "") or "").strip() and not getattr(b, "eh_kit", False)
        ]
        if not faltam:
            return
        if not regras.categorias_projeto:
            for brinquedo in faltam:
                regras._categorias[brinquedo.pk] = []
            return
        regras.carregar_categorias(faltam)

    def oferece(self, brinquedo) -> bool:
        return self.ativo and aceita(brinquedo, self.regras if self.ativo else None)

    def preco(self, brinquedo, com_ficha=False):
        base = getattr(brinquedo, "valor_brinquedo", None)
        if base is None:
            return None
        base = Decimal(base).quantize(Decimal("0.01"))
        return base + self.acrescimo if (com_ficha and self.oferece(brinquedo)) else base

    def para_a_opcao(self, brinquedo):
        """O que a busca de itens do orçamento manda junto da máquina; None sem a opção."""
        if not self.oferece(brinquedo):
            return None
        com = self.preco(brinquedo, True)
        return {
            "acrescimo": f"{self.acrescimo:.2f}".replace(".", ","),
            "preco_com": f"{com:.2f}".replace(".", ",") if com is not None else "",
            "rotulo_sem": ROTULO_SEM,
            "rotulo_com": ROTULO_COM,
            "sufixo": SUFIXO,
        }
