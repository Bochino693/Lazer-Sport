"""A lista de montagem: a fila, as etapas e o prazo de entrega (LEIA-ME-V10, seção 112).

O PEDIDO DO DONO, EM TRÊS RECADOS.

  1. "Lista de montagem com todos os brinquedos que tem pra montar": dos
     pedidos pagos do site E dos orçamentos aprovados do painel, uma linha
     por unidade (quantidade 3 = 3 máquinas), juntas numa lista só.
  2. "Todo brinquedo que sair, estiver aprovado, o prazo de montagem são de
     4 a 5 dias, dependendo do m cúbico (...) dividido por 7 etapas, corte
     de MDF, montagem, adesivo, eletrônica, finalização, teste de qualidade
     e embalagem, para ir notificando os usuários, peças de reposição 3 dias
     para a entrega". Brinquedões e espaços esportivos ficam fora dessa
     regra.
  3. "Tem uma fila de espera: se já tiver sendo montado 3 brinquedos, deve
     entrar na fila e ter uma previsão de 15 a 30 dias mais os da produção
     (...) brinquedões entre outros só podem ser montados um por vez, com
     prazo de 30 dias a cada um na fila."

AS QUATRO TRILHAS (cada unidade anda por uma):

  * MÁQUINA (o brinquedo normal): 7 etapas em 4 dias úteis até o limite de
    m³ (padrão 2,5 m³) e 5 acima ou sem medida. No máximo 3 ao mesmo tempo
    (a "linha das máquinas"); o resto espera na fila, com a previsão de 15
    a 30 dias de fila + a montagem;
  * PROJETO (brinquedão, trampolim, escalada, área ninja, espaço esportivo,
    casinha cenográfica -- pela categoria ou por palavras, no painel): uma
    linha à parte, um por vez, 30 dias cada (ou o prazo que a equipe deu ao
    orçamento); o da fila espera os da frente: posição × 30 dias;
  * PEÇA de reposição: 3 dias úteis, separação e embalagem, sem fila;
  * KIT ELETRÔNICO: é peça (3 dias, sem fila), mas com a eletrônica e o
    teste no meio -- é a parte elétrica da máquina, sai testada.

QUEM ENTRA, E QUANDO. A mesma regra que o sistema já usa para "começar a
produção" (seção 89): o pedido do site PAGO e o orçamento APROVADO. Entram
sozinhos -- o sinal da situação (signals_montagem.py) e, de rede de
segurança, a própria lista ao abrir --, com a data prevista de cada etapa
calculada no dia em que a máquina pega a vaga. Quando uma vaga libera (a
máquina termina a última etapa), o primeiro da fila entra sozinho e o
cliente é avisado.

O PRAZO NUM LUGAR SÓ. `prazo_de_entrega(origem)` é a resposta para "quando
fica pronto?": antes da compra (a fila de agora + a montagem) e depois (as
datas das máquinas). O prazo de produção da origem (`prazo_producao_dias`,
o campo da seção 89) é escrito pela lista enquanto a equipe não digitar
outro -- é dele que saem a proposta, Meus pedidos, as etiquetas, a tela de
Vendas e o contrato.
"""

from __future__ import annotations

import logging
import math
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.producao import dia_util, somar_dias_uteis, texto_dos_dias

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# AS ETAPAS DE CADA TRILHA
# ----------------------------------------------------------------------
#: (chave, nome, ícone do Bootstrap Icons) -- na ordem em que a fábrica faz.
ETAPAS = {
    "maquina": (
        ("corte", "Corte de MDF", "bi-rulers"),
        ("montagem", "Montagem", "bi-tools"),
        ("adesivo", "Adesivo", "bi-palette"),
        ("eletronica", "Eletrônica", "bi-cpu"),
        ("finalizacao", "Finalização", "bi-stars"),
        ("teste", "Teste de qualidade", "bi-patch-check"),
        ("embalagem", "Embalagem", "bi-box-seam"),
    ),
    "projeto": (
        ("fabricacao", "Fabricação", "bi-hammer"),
        ("finalizacao", "Finalização", "bi-stars"),
        ("teste", "Teste de qualidade", "bi-patch-check"),
    ),
    "kit": (
        ("separacao", "Separação", "bi-list-check"),
        ("eletronica", "Eletrônica", "bi-cpu"),
        ("teste", "Teste de qualidade", "bi-patch-check"),
        ("embalagem", "Embalagem", "bi-box-seam"),
    ),
    "peca": (
        ("separacao", "Separação", "bi-list-check"),
        ("embalagem", "Embalagem", "bi-box-seam"),
    ),
}
#: A ordem de todas as etapas, para a linha do tempo de uma origem com
#: trilhas misturadas (a máquina e a peça do mesmo pedido).
ORDEM_GERAL = (
    "separacao", "corte", "fabricacao", "montagem", "adesivo",
    "eletronica", "finalizacao", "teste", "embalagem",
)
NOME_DA_ETAPA = {chave: nome for etapas in ETAPAS.values() for chave, nome, _ in etapas}
ICONE_DA_ETAPA = {chave: icone for etapas in ETAPAS.values() for chave, _, icone in etapas}

#: As trilhas que disputam vaga (a "linha" de cada uma). Peça e kit não.
COM_FILA = ("maquina", "projeto")

#: Origem que chega à lista mais de 6 horas depois de paga ou aprovada é de
#: antes (a carga da primeira vez): entra sem o aviso de "entrou".
ANTIGA = timedelta(hours=6)

#: Linhas do orçamento que são serviço, e não algo a montar ("Montagem e
#: instalação", "Frete", "Visita técnica"...). Sem acento, em minúsculas.
_SERVICO = re.compile(
    r"\b(instalacao|instalar|frete|transporte|entrega|servico|mao de obra|visita|"
    r"manutencao|taxa|desconto|garantia|treinamento|deslocamento|hospedagem|"
    r"alimentacao|locacao|aluguel|projeto 3d|layout)\b"
)


def sem_acento(texto) -> str:
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(letra for letra in texto if not unicodedata.combining(letra)).lower().strip()


def etapas_da(trilha):
    return ETAPAS.get(trilha, ETAPAS["maquina"])


def ultima_etapa(trilha) -> str:
    return etapas_da(trilha)[-1][0]


# ----------------------------------------------------------------------
# AS REGRAS (a linha do painel)
# ----------------------------------------------------------------------
def configuracao():
    """As regras da produção (a linha única; nasce com os padrões do dono)."""
    from .models import ConfiguracaoProducao

    config = ConfiguracaoProducao.objects.order_by("pk").first()
    if config is None:
        config = ConfiguracaoProducao.objects.create()
    return config


# ----------------------------------------------------------------------
# O CACHE: a página do produto e o carrinho não vão ao banco à toa
# ----------------------------------------------------------------------
# A previsão antes da compra aparece na página do produto, que a segunda
# visita serve sem banco nenhum (core/tests_desempenho). As regras, o estado
# das linhas e a previsão de cada produto ficam no cache com uma VERSÃO:
# qualquer mudança na lista (`distribuir`) ou nas regras troca a versão, e
# a próxima conta é feita de novo. O tempo curto garante o resto (a fila
# anda com o calendário).
CHAVE_DA_VERSAO = "montagem:versao"
VIDA_DO_CACHE = 120


def _versao():
    from django.core.cache import cache

    try:
        return cache.get(CHAVE_DA_VERSAO) or 1
    except Exception:  # noqa: BLE001 -- sem cache, sem atalho
        return 1


def mudou():
    """A lista ou as regras mudaram: as previsões guardadas deixam de valer."""
    from django.core.cache import cache

    try:
        cache.set(CHAVE_DA_VERSAO, _versao() + 1, None)
    except Exception:  # noqa: BLE001
        pass


def _guardado(chave, calcular):
    from django.core.cache import cache

    chave = f"montagem:{_versao()}:{hoje().isoformat()}:{chave}"
    try:
        valor = cache.get(chave)
    except Exception:  # noqa: BLE001
        valor = None
    if valor is None:
        valor = calcular()
        try:
            cache.set(chave, valor, VIDA_DO_CACHE)
        except Exception:  # noqa: BLE001
            pass
    return valor


@dataclass
class Regras:
    """As regras lidas uma vez (a classificação de uma origem não pergunta de novo)."""

    config: object
    categorias_projeto: set = field(default_factory=set)
    palavras_projeto: tuple = ()
    _catalogo: list | None = None
    #: {id do brinquedo: [(id, nome) das categorias]} -- lidas em lote
    _categorias: dict = field(default_factory=dict)

    @classmethod
    def agora(cls, config=None):
        if config is not None:
            return cls._ler(config)
        guardadas = _guardado("regras", lambda: cls._ler(configuracao()))
        # uma cópia: o que esta conta aprender das categorias não vai para o cache
        return cls(config=guardadas.config, categorias_projeto=set(guardadas.categorias_projeto),
                   palavras_projeto=guardadas.palavras_projeto)

    @classmethod
    def _ler(cls, config):
        palavras = tuple(
            sem_acento(p) for p in re.split(r"[,;\n]", config.palavras_projeto or "") if sem_acento(p)
        )
        ids = set(config.categorias_projeto.values_list("pk", flat=True)) if config.pk else set()
        return cls(config=config, categorias_projeto=ids, palavras_projeto=palavras)

    def carregar_categorias(self, brinquedos):
        """As categorias de vários brinquedos numa consulta só (nunca uma por brinquedo)."""
        from core.models import Brinquedos

        faltam = {b.pk for b in brinquedos if b is not None and b.pk not in self._categorias}
        if not faltam:
            return
        ligacoes = Brinquedos.categorias_brinquedos.through.objects.filter(brinquedos_id__in=faltam).values_list(
            "brinquedos_id", "categoriasbrinquedos_id", "categoriasbrinquedos__nome_categoria",
        )
        for pk in faltam:
            self._categorias[pk] = []
        for brinquedo_id, categoria_id, nome in ligacoes:
            self._categorias[brinquedo_id].append((categoria_id, nome or ""))

    # ---------------- o brinquedo ----------------
    def e_projeto(self, brinquedo=None, nome="") -> bool:
        """Brinquedão, espaço esportivo, trampolim, escalada, ninja, casinha...

        Pela CATEGORIA marcada no painel ou por uma das PALAVRAS no nome do
        brinquedo ou da categoria. Sem cadastro, só pelo nome da linha.
        """
        textos = [sem_acento(nome)]
        if brinquedo is not None:
            textos.append(sem_acento(brinquedo.nome_brinquedo))
            if brinquedo.pk not in self._categorias:
                self.carregar_categorias([brinquedo])
            for categoria_id, nome_categoria in self._categorias.get(brinquedo.pk, []):
                if categoria_id in self.categorias_projeto:
                    return True
                textos.append(sem_acento(nome_categoria))
        return any(palavra in texto for palavra in self.palavras_projeto for texto in textos if texto)

    def dias_da_maquina(self, brinquedo=None) -> int:
        """4 dias úteis até o limite de m³; 5 acima dele, e 5 sem medida."""
        volume = getattr(brinquedo, "metros_cubicos", None) if brinquedo is not None else None
        if volume is None:
            return self.config.dias_acima_limite
        if volume <= float(self.config.limite_m3):
            return self.config.dias_ate_limite
        return self.config.dias_acima_limite

    def catalogo(self):
        """Os nomes do catálogo, do mais comprido ao mais curto (para a linha escrita à mão)."""
        if self._catalogo is None:
            from core.models import Brinquedos

            self._catalogo = sorted(
                Brinquedos.objects.only("pk", "nome_brinquedo", "eh_kit", "altura_m", "largura_m", "profundidade_m"),
                key=lambda b: -len(b.nome_brinquedo or ""),
            )
            self.carregar_categorias(self._catalogo)
        return self._catalogo

    def do_catalogo(self, descricao):
        """O brinquedo cujo nome começa a linha ("Air Game Kids Alienígenas") e o resto."""
        alvo = sem_acento(descricao)
        for brinquedo in self.catalogo():
            nome = sem_acento(brinquedo.nome_brinquedo)
            if nome and (alvo == nome or alvo.startswith(nome + " ")):
                resto = (descricao or "")[len(brinquedo.nome_brinquedo):].strip(" -—·")
                return brinquedo, resto
        return None, ""


@dataclass
class Linha:
    """O que vira unidade: um brinquedo (ou peça) e quantas."""

    nome: str
    quantidade: int
    trilha: str
    dias: int
    variante: str = ""
    brinquedo: object = None
    peca: object = None
    item_pedido: object = None
    item_orcamento: object = None


def _linha_do_brinquedo(regras, brinquedo, quantidade, variante="", nome="", dias_projeto=None, **origem):
    nome = nome or brinquedo.nome_brinquedo
    # o kit eletrônico é um produto (LEIA-ME 107), mas sai como peça: separado,
    # com a eletrônica testada e embalado, em 3 dias, sem a fila das máquinas
    if getattr(brinquedo, "eh_kit", False):
        return Linha(nome, quantidade, "kit", regras.config.dias_pecas, variante, brinquedo=brinquedo, **origem)
    if regras.e_projeto(brinquedo, nome):
        return Linha(nome, quantidade, "projeto", dias_projeto or regras.config.dias_projeto,
                     variante, brinquedo=brinquedo, **origem)
    return Linha(nome, quantidade, "maquina", regras.dias_da_maquina(brinquedo), variante,
                 brinquedo=brinquedo, **origem)


def _linha_da_peca(regras, peca, quantidade, nome="", **origem):
    return Linha(nome or str(peca), quantidade, "peca", regras.config.dias_pecas, peca=peca, **origem)


def _linha_pelo_nome(regras, descricao, quantidade, dias_projeto=None, **origem):
    """A linha escrita à mão: serviço fica de fora; o resto é máquina ou projeto."""
    if not sem_acento(descricao) or _SERVICO.search(sem_acento(descricao)):
        return None
    brinquedo, resto = regras.do_catalogo(descricao)
    if brinquedo is not None:
        return _linha_do_brinquedo(regras, brinquedo, quantidade, resto, brinquedo.nome_brinquedo,
                                   dias_projeto, **origem)
    if regras.e_projeto(None, descricao):
        return Linha(descricao, quantidade, "projeto", dias_projeto or regras.config.dias_projeto, **origem)
    return Linha(descricao, quantidade, "maquina", regras.dias_da_maquina(None), **origem)


def linhas_do_pedido(pedido, regras=None) -> list[Linha]:
    """As máquinas de um pedido do site (o combo e a promoção abrem nos brinquedos)."""
    regras = regras or Regras.agora()
    linhas = []
    itens = list(pedido.itens.all())
    regras.carregar_categorias([
        i.item_original for i in itens
        if i.content_type_id and i.object_id and i.content_type.model == "brinquedos"
    ])
    for item in itens:
        quantidade = max(int(item.quantidade or 1), 1)
        nome, _, adesivo = (item.nome_item or "").partition(" — adesivo ")
        modelo = item.content_type.model if item.content_type_id else ""
        objeto = item.item_original if item.content_type_id and item.object_id else None
        origem = {"item_pedido": item}
        if modelo == "brinquedos" and objeto is not None:
            linhas.append(_linha_do_brinquedo(regras, objeto, quantidade, adesivo, **origem))
        elif modelo == "combos" and objeto is not None:
            for brinquedo in objeto.brinquedos.all():
                linhas.append(_linha_do_brinquedo(regras, brinquedo, quantidade, **origem))
        elif modelo == "promocoes" and objeto is not None:
            for brinquedo in [objeto.brinquedos, *objeto.brinquedos_extras.all()]:
                if brinquedo is not None:
                    linhas.append(_linha_do_brinquedo(regras, brinquedo, quantidade, **origem))
        elif modelo == "pecasreposicao" and objeto is not None:
            linhas.append(_linha_da_peca(regras, objeto, quantidade, nome, **origem))
        else:
            linha = _linha_pelo_nome(regras, nome, quantidade, **origem)
            if linha is not None:
                linha.variante = linha.variante or adesivo
                linhas.append(linha)
    return linhas


def linhas_do_orcamento(orcamento, regras=None, dias_projeto=None) -> list[Linha]:
    """As máquinas de um orçamento (serviço e frete ficam de fora)."""
    regras = regras or Regras.agora()
    linhas = []
    for item in orcamento.itens.all():
        quantidade = max(int(item.quantidade or 1), 1)
        origem = {"item_orcamento": item}
        if item.brinquedo_id and item.brinquedo is not None:
            resto = ""
            nome_cadastro = item.brinquedo.nome_brinquedo or ""
            if sem_acento(item.descricao).startswith(sem_acento(nome_cadastro) + " "):
                resto = item.descricao[len(nome_cadastro):].strip(" -—·")
            linhas.append(_linha_do_brinquedo(regras, item.brinquedo, quantidade, resto,
                                              dias_projeto=dias_projeto, **origem))
        elif item.peca_id and item.peca is not None:
            linhas.append(_linha_da_peca(regras, item.peca, quantidade, item.descricao, **origem))
        elif item.produto_id and item.produto is not None:
            produto = item.produto
            if produto.brinquedo_id and produto.brinquedo is not None:
                linhas.append(_linha_do_brinquedo(regras, produto.brinquedo, quantidade, nome=item.descricao,
                                                  dias_projeto=dias_projeto, **origem))
            elif produto.categoria == "peca":
                linhas.append(Linha(item.descricao, quantidade, "peca", regras.config.dias_pecas, **origem))
            elif produto.categoria != "outro":
                linha = _linha_pelo_nome(regras, item.descricao, quantidade, dias_projeto, **origem)
                if linha is not None:
                    linhas.append(linha)
        else:
            linha = _linha_pelo_nome(regras, item.descricao, quantidade, dias_projeto, **origem)
            if linha is not None:
                linhas.append(linha)
    return linhas


def dias_de_projeto_do_orcamento(orcamento, producao=None):
    """O prazo que a equipe deu ao orçamento vale para o brinquedão dele.

    O escrito pela própria lista (automático) não conta: seria a lista
    lendo a si mesma.
    """
    if orcamento is None or orcamento.prazo_producao_dias in (None, 0):
        return None
    if producao is not None and producao.prazo_automatico:
        return None
    return orcamento.prazo_producao_dias


# ----------------------------------------------------------------------
# AS DATAS
# ----------------------------------------------------------------------
def hoje():
    return timezone.localdate()


def dia_local(momento):
    if momento is None:
        return None
    if isinstance(momento, datetime):
        return timezone.localtime(momento).date() if timezone.is_aware(momento) else momento.date()
    return momento


def dias_uteis_entre(inicio, fim) -> int:
    """Quantos dias úteis depois de `inicio` até `fim` (o mesmo critério de `somar_dias_uteis`)."""
    if inicio is None or fim is None or fim <= inicio:
        return 0
    contagem, dia = 0, inicio
    while dia < fim:
        dia = date.fromordinal(dia.toordinal() + 1)
        if dia_util(dia):
            contagem += 1
    return contagem


def datas_das_etapas(trilha, inicio, dias) -> dict:
    """O prazo dividido pelas etapas: a etapa i de n termina em ceil(i × D / n) dias úteis."""
    etapas = etapas_da(trilha)
    total = max(int(dias or 1), 1)
    n = len(etapas)
    return {
        chave: somar_dias_uteis(inicio, math.ceil(indice * total / n)).isoformat()
        for indice, (chave, _, _) in enumerate(etapas, start=1)
    }


def _data(texto):
    if not texto:
        return None
    if isinstance(texto, date):
        return texto
    try:
        return date.fromisoformat(str(texto)[:10])
    except ValueError:
        return None


def _momento(texto):
    if not texto:
        return None
    try:
        return datetime.fromisoformat(str(texto))
    except ValueError:
        return None


# ----------------------------------------------------------------------
# A FILA
# ----------------------------------------------------------------------
def _ordem_da_fila(unidade):
    return (unidade.posicao if unidade.posicao is not None else 10 ** 9, unidade.chegada, unidade.pk or 0)


def _entrar(unidade, agora):
    """A máquina pega a vaga: as datas das etapas são calculadas AGORA."""
    from .models import UnidadeMontagem

    unidade.situacao = UnidadeMontagem.Situacao.PRODUCAO
    unidade.entrou_em = agora
    unidade.posicao = None
    unidade.previstas = datas_das_etapas(unidade.trilha, dia_local(agora), unidade.dias)
    fim = _data(unidade.previstas.get(ultima_etapa(unidade.trilha)))
    unidade.previsao_de = unidade.previsao_ate = fim


def distribuir(agora=None, config=None) -> list:
    """Enche as vagas livres com a fila, em ordem, e recalcula as previsões.

    Devolve as unidades que acabaram de entrar em produção (para o aviso).
    Trava as linhas da fila: duas telas mudando ao mesmo tempo não põem a
    mesma máquina duas vezes na vaga.
    """
    from .models import UnidadeMontagem

    agora = agora or timezone.now()
    config = config or configuracao()
    S = UnidadeMontagem.Situacao
    entraram = []
    campos = ["situacao", "entrou_em", "posicao", "previstas", "previsao_de", "previsao_ate", "atualizado"]
    with transaction.atomic():
        for trilha, capacidade in (("maquina", config.capacidade_maquinas), ("projeto", config.capacidade_projetos)):
            ativas = list(
                UnidadeMontagem.objects.select_for_update()
                .filter(trilha=trilha, situacao__in=(S.FILA, S.PRODUCAO))
            )
            producao = [u for u in ativas if u.situacao == S.PRODUCAO]
            fila = sorted((u for u in ativas if u.situacao == S.FILA), key=_ordem_da_fila)
            vagas = capacidade - len(producao)
            while vagas > 0 and fila:
                unidade = fila.pop(0)
                _entrar(unidade, agora)
                producao.append(unidade)
                entraram.append(unidade)
                vagas -= 1
            for posicao, unidade in enumerate(fila, start=1):
                unidade.posicao = posicao
            _prever_fila(trilha, producao, fila, config)
            for unidade in producao + fila:
                unidade.atualizado = agora
            if producao or fila:
                UnidadeMontagem.objects.bulk_update(producao + fila, campos)
    mudou()
    return entraram


def _prever_fila(trilha, producao, fila, config):
    """A previsão de quem espera.

    Máquinas: a faixa do dono -- 15 a 30 dias úteis de fila, contados da
    chegada, + a montagem dela (a fila de máquinas anda por vários
    caminhos ao mesmo tempo, e o dono preferiu a faixa a uma conta exata).
    Brinquedões: um depois do outro -- cada um começa quando a vaga dele
    libera (posição × 30 dias).
    """
    dia = hoje()
    for unidade in producao:
        if unidade.previsao_ate is None:
            fim = _data((unidade.previstas or {}).get(ultima_etapa(unidade.trilha)))
            unidade.previsao_de = unidade.previsao_ate = fim
    if trilha == "maquina":
        for unidade in fila:
            base = dia_local(unidade.chegada) or dia
            comeco_de = max(somar_dias_uteis(base, config.fila_min_dias), dia)
            comeco_ate = max(somar_dias_uteis(base, config.fila_max_dias), dia)
            unidade.previsao_de = somar_dias_uteis(comeco_de, unidade.dias)
            unidade.previsao_ate = somar_dias_uteis(comeco_ate, unidade.dias)
        return
    vagas = sorted(max(u.previsao_ate or dia, dia) for u in producao)
    vagas += [dia] * max(config.capacidade_projetos - len(vagas), 0)
    for unidade in fila:
        vagas.sort()
        comeco = vagas.pop(0) if vagas else dia
        fim = somar_dias_uteis(comeco, unidade.dias)
        unidade.previsao_de = unidade.previsao_ate = fim
        vagas.append(fim)


def mover_na_fila(unidade, direcao) -> bool:
    """Sobe (-1) ou desce (+1) uma posição na fila da linha dela."""
    from .models import UnidadeMontagem

    S = UnidadeMontagem.Situacao
    with transaction.atomic():
        fila = sorted(
            UnidadeMontagem.objects.select_for_update().filter(trilha=unidade.trilha, situacao=S.FILA),
            key=_ordem_da_fila,
        )
        indices = {u.pk: i for i, u in enumerate(fila)}
        if unidade.pk not in indices:
            return False
        i = indices[unidade.pk]
        j = i + (1 if direcao > 0 else -1)
        if j < 0 or j >= len(fila):
            return False
        fila[i], fila[j] = fila[j], fila[i]
        for posicao, item in enumerate(fila, start=1):
            item.posicao = posicao
        UnidadeMontagem.objects.bulk_update(fila, ["posicao"])
    distribuir()
    return True


# ----------------------------------------------------------------------
# A ORIGEM ENTRA, ANDA, FICA PRONTA, É ENTREGUE OU CANCELADA
# ----------------------------------------------------------------------
def _chegada_do_pedido(pedido):
    return pedido.pago_em or pedido.criacao or timezone.now()


def _chegada_do_orcamento(orcamento):
    if orcamento.respondido_em:
        return orcamento.respondido_em
    if orcamento.producao_inicio:
        return timezone.make_aware(datetime.combine(orcamento.producao_inicio, datetime.min.time()).replace(hour=12))
    return timezone.now()


def criar_producao(*, pedido=None, orcamento=None, agora=None, silencioso=False):
    """Põe as máquinas da origem na lista (e, havendo vaga, já em produção).

    `silencioso`: a carga dos pedidos que já existiam (a migração) não
    manda "sua máquina entrou em produção" a quem comprou há semanas.
    """
    from .models import ProducaoOrigem, UnidadeMontagem

    agora = agora or timezone.now()
    regras = Regras.agora()
    if pedido is not None:
        linhas = linhas_do_pedido(pedido, regras)
        chegada = _chegada_do_pedido(pedido)
        origem = {"pedido": pedido}
    else:
        linhas = linhas_do_orcamento(orcamento, regras, dias_de_projeto_do_orcamento(orcamento))
        chegada = _chegada_do_orcamento(orcamento)
        origem = {"orcamento": orcamento}
    if not linhas:
        return None
    # A ORIGEM DE ANTES (a carga da primeira vez, ou um pedido pago há dias
    # que só agora chegou à lista) entra em silêncio: o que acontecer com
    # ela daqui em diante é avisado, o "entrou" de semanas atrás não.
    silencioso = silencioso or (agora - chegada) > ANTIGA
    S = UnidadeMontagem.Situacao
    with transaction.atomic():
        producao = ProducaoOrigem.objects.create(
            chegada=chegada, avisos={"silencio": True} if silencioso else {}, **origem,
        )
        unidades = []
        for linha in linhas:
            for numero in range(1, linha.quantidade + 1):
                unidade = UnidadeMontagem(
                    producao=producao, numero=numero, de=linha.quantidade,
                    nome=linha.nome[:200], variante=(linha.variante or "")[:80],
                    brinquedo=linha.brinquedo, peca=linha.peca, trilha=linha.trilha,
                    dias=linha.dias, chegada=chegada, situacao=S.FILA,
                    item_pedido=linha.item_pedido, item_orcamento=linha.item_orcamento,
                )
                if linha.trilha not in COM_FILA:
                    _entrar(unidade, agora)
                unidades.append(unidade)
        UnidadeMontagem.objects.bulk_create(unidades)
    entraram = distribuir(agora, regras.config)
    _depois_de_mudar(producao, entraram=entraram, agora=agora)
    if silencioso:
        producao.refresh_from_db()
        avisos = _avisos(producao)
        avisos.pop("silencio", None)
        producao.avisos = avisos
        producao.save(update_fields=["avisos"])
    return producao


def _todas(producao):
    from .models import UnidadeMontagem

    return [u for u in producao.unidades.all() if u.situacao != UnidadeMontagem.Situacao.CANCELADA]


def concluir_ate(unidade, etapa, *, usuario=None, agora=None):
    """Marca a unidade com as etapas feitas ATÉ `etapa` ("" = nenhuma).

    Para a frente, as etapas puladas ganham o mesmo instante (nenhuma fica
    "feita" sem dia); para trás é correção: as da frente perdem o dia.
    """
    from .models import UnidadeMontagem

    S = UnidadeMontagem.Situacao
    agora = agora or timezone.now()
    chaves = [chave for chave, _, _ in etapas_da(unidade.trilha)]
    if etapa and etapa not in chaves:
        raise ValueError("Esta etapa não é desta máquina.")
    if unidade.situacao in (S.FILA, S.CANCELADA, S.ENTREGUE):
        raise ValueError({
            S.FILA: "Esta máquina ainda está na fila: ela entra em produção quando abrir uma vaga.",
            S.CANCELADA: "O pedido desta máquina foi cancelado.",
            S.ENTREGUE: "Esta máquina já foi entregue.",
        }[unidade.situacao])
    feitas = dict(unidade.etapas_em or {})
    ate = chaves.index(etapa) if etapa else -1
    for indice, chave in enumerate(chaves):
        if indice <= ate:
            feitas.setdefault(chave, agora.isoformat())
        else:
            feitas.pop(chave, None)
    unidade.etapas_em = feitas
    unidade.etapa = etapa
    pronta_antes = unidade.situacao == S.PRONTA
    if etapa == chaves[-1]:
        unidade.situacao = S.PRONTA
        unidade.previsao_de = unidade.previsao_ate = dia_local(agora)
    else:
        unidade.situacao = S.PRODUCAO
        if pronta_antes:
            fim = _data((unidade.previstas or {}).get(chaves[-1]))
            unidade.previsao_de = unidade.previsao_ate = max(fim or hoje(), hoje())
    if usuario is not None and getattr(usuario, "is_authenticated", False):
        unidade.atualizado_por = usuario
    unidade.save(update_fields=[
        "etapas_em", "etapa", "situacao", "previsao_de", "previsao_ate", "atualizado_por", "atualizado",
    ])
    entraram = distribuir(agora) if unidade.situacao == S.PRONTA else []
    _depois_de_mudar(unidade.producao, entraram=entraram, agora=agora)
    return unidade


def marcar_prontas(producao, agora=None):
    """Todas as máquinas da origem prontas (o pedido saiu pelo painel de Pedidos)."""
    from .models import UnidadeMontagem

    S = UnidadeMontagem.Situacao
    agora = agora or timezone.now()
    mudou = False
    for unidade in _todas(producao):
        if unidade.situacao in (S.FILA, S.PRODUCAO):
            chaves = [chave for chave, _, _ in etapas_da(unidade.trilha)]
            feitas = dict(unidade.etapas_em or {})
            for chave in chaves:
                feitas.setdefault(chave, agora.isoformat())
            unidade.etapas_em, unidade.etapa, unidade.situacao = feitas, chaves[-1], S.PRONTA
            unidade.posicao = None
            unidade.entrou_em = unidade.entrou_em or agora
            unidade.previsao_de = unidade.previsao_ate = dia_local(agora)
            unidade.save()
            mudou = True
    entraram = distribuir(agora) if mudou else []
    _depois_de_mudar(producao, entraram=entraram, agora=agora)


def marcar_entregue(producao, agora=None):
    """A origem foi entregue (o pedido finalizado, ou o "Entregue" da lista)."""
    from .models import UnidadeMontagem

    S = UnidadeMontagem.Situacao
    agora = agora or timezone.now()
    marcar_prontas(producao, agora)
    UnidadeMontagem.objects.filter(producao=producao, situacao=S.PRONTA).update(situacao=S.ENTREGUE, atualizado=agora)
    producao.refresh_from_db()
    _depois_de_mudar(producao, agora=agora)


def cancelar(producao, agora=None):
    """A origem deixou de valer (cancelada, recusada, substituída): a vaga libera."""
    from .models import UnidadeMontagem

    S = UnidadeMontagem.Situacao
    agora = agora or timezone.now()
    UnidadeMontagem.objects.filter(producao=producao).exclude(situacao=S.ENTREGUE).update(
        situacao=S.CANCELADA, posicao=None, atualizado=agora,
    )
    producao.situacao = producao.Situacao.CANCELADA
    producao.cancelada_em = agora
    producao.save(update_fields=["situacao", "cancelada_em", "atualizado"])
    distribuir(agora)


def reativar(producao, agora=None):
    """A origem voltou a valer (o pedido descancelado pelo admin): de volta à fila."""
    origem = {"pedido": producao.pedido} if producao.pedido_id else {"orcamento": producao.orcamento}
    avisos = producao.avisos
    producao.delete()
    nova = criar_producao(agora=agora, **origem)
    if nova is not None:
        nova.avisos = avisos
        nova.save(update_fields=["avisos"])
    return nova


def _depois_de_mudar(producao, *, entraram=(), agora=None):
    """Acerta a origem depois de qualquer mudança nas máquinas dela.

    A situação da origem, as etapas feitas por TODAS as máquinas (é o que
    o cliente acompanha), os avisos, o prazo e a fase do pedido. Também a
    das outras origens cujas máquinas acabaram de pegar vaga.
    """
    origens = {producao.pk: producao}
    for unidade in entraram:
        origens.setdefault(unidade.producao_id, None)
    from .models import ProducaoOrigem

    faltam = [pk for pk, objeto in origens.items() if objeto is None]
    if faltam:
        for outra in ProducaoOrigem.objects.filter(pk__in=faltam):
            origens[outra.pk] = outra
    for objeto in origens.values():
        if objeto is not None:
            acertar_origem(objeto, agora=agora)
            sincronizar_tarefas(objeto)


def sincronizar_tarefas(producao):
    """A etapa da vez de cada máquina vira TAREFA no RH (LEIA-ME 113).

    O dono: "associar à produção e tarefas e manter o controle". A próxima
    etapa de cada unidade em produção vai para quem é do setor e tem a
    especialidade dela, o menos ocupado antes (`rh.tarefas.sugerir_responsaveis`);
    a etapa feita conclui a tarefa dela. Cada um vê em "Minhas tarefas".
    Sem colaborador ativo no RH, nada é criado (sem tarefa órfã); e o RH
    nunca derruba a produção: qualquer erro aqui só vai para o log.
    """
    try:
        from rh import tarefas as tarefas_do_rh
        from rh.models import Colaborador as ColaboradorRH, Situacao as SituacaoRH
    except Exception:  # noqa: BLE001 -- o RH é opcional para a produção
        return
    try:
        if not ColaboradorRH.objects.filter(situacao=SituacaoRH.ATIVO).exists():
            return
        from django.urls import reverse

        from .models import UnidadeMontagem

        S = UnidadeMontagem.Situacao
        try:
            endereco = reverse("lista_montagem")
        except Exception:  # noqa: BLE001
            endereco = ""
        for unidade in producao.unidades.all():
            etapas = etapas_da(unidade.trilha)
            feitas = unidade.etapas_em or {}
            for chave, rotulo, _icone in etapas:
                if chave in feitas:
                    tarefas_do_rh.concluir(unidade, etapa=rotulo)
            if unidade.situacao != S.PRODUCAO:
                continue
            proxima = next(((chave, rotulo) for chave, rotulo, _ in etapas if chave not in feitas), None)
            if proxima is None:
                continue
            chave, rotulo = proxima
            if tarefas_do_rh.tarefas_do_objeto(unidade).filter(etapa=rotulo).exists():
                continue
            nome = unidade.nome + (f" ({unidade.variante})" if unidade.variante else "")
            tarefas_do_rh.atribuir(
                None, unidade, etapa=rotulo, prazo=_data((unidade.previstas or {}).get(chave)),
                titulo=f"{rotulo} · {nome} · unidade {unidade.numero} de {unidade.de}"[:160],
                url=endereco,
            )
    except Exception:  # noqa: BLE001
        logger.exception("Tarefas do RH da produção %s", getattr(producao, "pk", None))


def acertar_origem(producao, agora=None):
    """A origem acompanha as máquinas dela: situação, etapas, avisos, prazo e fase."""
    from .models import ProducaoOrigem, UnidadeMontagem

    S = UnidadeMontagem.Situacao
    P = ProducaoOrigem.Situacao
    agora = agora or timezone.now()
    producao.refresh_from_db()
    if producao.situacao == P.CANCELADA:
        return producao
    unidades = _todas(producao)
    if not unidades:
        return producao
    situacoes = {u.situacao for u in unidades}
    antes = producao.situacao
    if situacoes == {S.ENTREGUE}:
        nova = P.ENTREGUE
    elif situacoes <= {S.PRONTA, S.ENTREGUE}:
        nova = P.PRONTA
    elif situacoes & {S.PRODUCAO, S.PRONTA, S.ENTREGUE}:
        nova = P.PRODUCAO
    else:
        nova = P.FILA

    # as etapas da ORIGEM: feitas quando todas as máquinas que têm a etapa a fizeram
    etapas_antes = dict(producao.etapas_em or {})
    etapas = {}
    for chave in ORDEM_GERAL:
        com_etapa = [u for u in unidades if chave in {c for c, _, _ in etapas_da(u.trilha)}]
        if com_etapa and all(chave in (u.etapas_em or {}) for u in com_etapa):
            etapas[chave] = max(u.etapas_em[chave] for u in com_etapa)
    producao.etapas_em = etapas
    producao.situacao = nova
    if nova in (P.PRONTA, P.ENTREGUE):
        producao.pronto_em = producao.pronto_em or agora
    else:
        producao.pronto_em = None
    producao.entregue_em = (producao.entregue_em or agora) if nova == P.ENTREGUE else None

    # os avisos ao cliente: uma vez por fato, agrupados no dia (ver `avisar`)
    if nova != P.FILA:
        registrar_aviso(producao, "producao")  # uma vez só (registrar_aviso não repete)
    for chave in etapas:
        if chave not in etapas_antes:
            registrar_aviso(producao, chave)
    if nova == P.PRONTA and antes != P.PRONTA:
        registrar_aviso(producao, "pronta")
    producao.save(update_fields=[
        "etapas_em", "situacao", "pronto_em", "entregue_em", "avisos", "atualizado",
    ])
    _acertar_prazo(producao, unidades)
    _acertar_fase_da_origem(producao, unidades)
    avisar(producao)
    return producao


def _acertar_prazo(producao, unidades):
    """O prazo de produção da origem acompanha a previsão -- enquanto for da lista.

    A equipe que digitou um prazo no pedido ou no orçamento manda nele (a
    lista não escreve por cima). Vazio, ou escrito pela lista, ele vira os
    dias úteis do começo da produção até a última máquina pronta: é dele
    que a proposta, Meus pedidos, as etiquetas, Vendas e o contrato leem.
    """
    origem = producao.pedido if producao.pedido_id else producao.orcamento
    if origem is None:
        return
    if origem.prazo_producao_dias is not None and not producao.prazo_automatico:
        return
    fim = max((u.previsao_ate for u in unidades if u.previsao_ate), default=None)
    inicio = origem.inicio_da_producao
    if fim is None or inicio is None:
        return
    dias = dias_uteis_entre(inicio, fim)
    campos = []
    if origem.prazo_producao_dias != dias:
        type(origem).objects.filter(pk=origem.pk).update(prazo_producao_dias=dias)
        origem.prazo_producao_dias = dias
    if origem.producao_inicio is None:
        type(origem).objects.filter(pk=origem.pk).update(producao_inicio=inicio)
        origem.producao_inicio = inicio
    if not producao.prazo_automatico:
        producao.prazo_automatico = True
        campos.append("prazo_automatico")
    if campos:
        producao.save(update_fields=campos)


def _acertar_fase_da_origem(producao, unidades):
    """O pedido do site anda junto (seção 106, as datas entram sozinhas).

    * a primeira etapa feita: "Pago" vira "Em preparação";
    * tudo pronto na RETIRADA: "Pronto para retirada" (o cliente já pode
      buscar); no FRETE o pedido fica "Em preparação" -- quem marca "Saiu
      para entrega" é a equipe, com a transportadora (seção 106);
    * uma máquina voltou atrás depois do "Pronto para retirada" que a lista
      deu: o pedido volta a "Em preparação".
    O orçamento não tem fase de produção na situação dele: a linha do tempo
    do cliente lê a produção daqui.
    """
    from .models import ProducaoOrigem

    if not producao.pedido_id:
        return
    pedido = producao.pedido
    P = ProducaoOrigem.Situacao
    comecou = any(u.etapa for u in unidades)
    try:
        if producao.situacao in (P.PRONTA, P.ENTREGUE):
            if pedido.retirada and pedido.status in ("pago", "em_preparacao"):
                pedido.mudar_situacao("saiu_entrega")
                producao.avancou_origem = True
                producao.save(update_fields=["avancou_origem"])
            elif pedido.status == "pago":
                pedido.mudar_situacao("em_preparacao")
        else:
            if producao.avancou_origem and pedido.retirada and pedido.status == "saiu_entrega":
                pedido.mudar_situacao("em_preparacao")
                producao.avancou_origem = False
                producao.save(update_fields=["avancou_origem"])
            elif comecou and pedido.status == "pago":
                pedido.mudar_situacao("em_preparacao")
    except ValueError:
        logger.warning("montagem: o pedido %s não pôde mudar de fase", pedido.pk, exc_info=True)


# ----------------------------------------------------------------------
# A ORIGEM MUDOU DE SITUAÇÃO (o sinal, e a rede de segurança da lista)
# ----------------------------------------------------------------------
PEDIDO_NA_PRODUCAO = ("pago", "em_preparacao")


def sincronizar_pedido(pedido_id, *, silencioso=False):
    from core.models import Pedido

    from .models import ProducaoOrigem

    pedido = Pedido.objects.prefetch_related("itens").filter(pk=pedido_id).first()
    if pedido is None:
        return None
    producao = ProducaoOrigem.objects.filter(pedido=pedido).first()
    if pedido.status in PEDIDO_NA_PRODUCAO:
        if producao is None:
            return criar_producao(pedido=pedido, silencioso=silencioso)
        if producao.situacao == ProducaoOrigem.Situacao.CANCELADA:
            return reativar(producao)
        return producao
    if producao is None or producao.situacao == ProducaoOrigem.Situacao.CANCELADA:
        return producao
    if pedido.status == "saiu_entrega":
        marcar_prontas(producao)
    elif pedido.status == "finalizado":
        if producao.situacao != ProducaoOrigem.Situacao.ENTREGUE:
            marcar_entregue(producao)
    else:  # aguardando pagamento (estorno) ou cancelado
        cancelar(producao)
    return producao


def sincronizar_orcamento(orcamento_id, *, silencioso=False):
    from .models import Orcamento, ProducaoOrigem

    orcamento = Orcamento.objects.prefetch_related("itens").filter(pk=orcamento_id).first()
    if orcamento is None:
        return None
    producao = ProducaoOrigem.objects.filter(orcamento=orcamento).first()
    if orcamento.status == Orcamento.Status.APROVADO:
        if producao is None:
            return criar_producao(orcamento=orcamento, silencioso=silencioso)
        if producao.situacao == ProducaoOrigem.Situacao.CANCELADA:
            return reativar(producao)
        return producao
    if producao is not None and producao.situacao not in (
        ProducaoOrigem.Situacao.CANCELADA, ProducaoOrigem.Situacao.ENTREGUE,
    ):
        cancelar(producao)
    return producao


def sincronizar_tudo():
    """A rede de segurança: o que devia estar na lista e não está (e o contrário).

    Roda ao abrir a lista. O normal é o sinal já ter feito tudo; isto pega
    o que entrou por um caminho sem sinal (um `update()` em massa, o banco
    restaurado) e custa duas consultas quando não há nada a fazer.
    """
    from core.models import Pedido

    from .models import Orcamento, ProducaoOrigem

    faltam_pedidos = Pedido.objects.filter(status__in=PEDIDO_NA_PRODUCAO, producao__isnull=True).values_list("pk", flat=True)
    faltam_orcamentos = Orcamento.objects.filter(
        status=Orcamento.Status.APROVADO, producao__isnull=True,
    ).values_list("pk", flat=True)
    for pk in list(faltam_pedidos):
        sincronizar_pedido(pk)
    for pk in list(faltam_orcamentos):
        sincronizar_orcamento(pk)
    vivas = ProducaoOrigem.objects.exclude(
        situacao__in=(ProducaoOrigem.Situacao.CANCELADA, ProducaoOrigem.Situacao.ENTREGUE),
    )
    for pk in vivas.filter(pedido__status__in=("cancelado", "aguardando_pagamento")).values_list("pedido_id", flat=True):
        sincronizar_pedido(pk)
    for pk in vivas.filter(orcamento__isnull=False).exclude(
        orcamento__status=Orcamento.Status.APROVADO,
    ).values_list("orcamento_id", flat=True):
        sincronizar_orcamento(pk)


# ----------------------------------------------------------------------
# OS AVISOS AO CLIENTE
# ----------------------------------------------------------------------
def _avisos(producao):
    avisos = dict(producao.avisos or {})
    avisos.setdefault("enviados", [])
    avisos.setdefault("pendentes", [])
    return avisos


def registrar_aviso(producao, chave):
    """Um fato novo para o cliente (uma vez só por fato)."""
    avisos = _avisos(producao)
    if avisos.get("silencio"):
        # a entrada de uma origem antiga: conta como avisado, sem e-mail
        if chave not in avisos["enviados"]:
            avisos["enviados"].append(chave)
    elif chave not in avisos["enviados"] and chave not in avisos["pendentes"]:
        avisos["pendentes"].append(chave)
    producao.avisos = avisos


def avisar(producao, *, forcar=False, hoje_=None):
    """Manda o e-mail dos fatos novos -- no máximo um por dia por origem.

    O primeiro fato do dia sai na hora; os outros do mesmo dia esperam e
    saem JUNTOS no próximo envio (o próximo fato num outro dia, ou a lista
    aberta noutro dia -- `avisar_pendentes`). O "pronta" nunca espera: é
    o aviso que o cliente mais quer.
    """
    avisos = _avisos(producao)
    pendentes = [c for c in avisos["pendentes"] if c not in avisos["enviados"]]
    if not pendentes:
        return False
    dia = (hoje_ or hoje()).isoformat()
    if not forcar and avisos.get("ultimo") == dia and "pronta" not in pendentes:
        return False
    avisos["enviados"] = avisos["enviados"] + pendentes
    avisos["pendentes"] = []
    avisos["ultimo"] = dia
    producao.avisos = avisos
    producao.save(update_fields=["avisos"])
    try:
        mensagem = montar_aviso(producao, pendentes)
        if mensagem is not None:
            from core.notificacoes import enviar_aviso_de_producao

            enviar_aviso_de_producao(
                mensagem, bloqueante=getattr(settings, "AVISOS_DA_PRODUCAO_NA_HORA", False),
            )
    except Exception:  # noqa: BLE001 -- o aviso nunca derruba a produção
        logger.exception("montagem: falhou o aviso da produção %s", producao.pk)
    return True


def avisar_pendentes():
    """Os avisos que ficaram para depois (o segundo fato do mesmo dia)."""
    from .models import ProducaoOrigem

    enviados = 0
    dia = hoje().isoformat()
    recentes = ProducaoOrigem.objects.exclude(situacao=ProducaoOrigem.Situacao.CANCELADA).filter(
        atualizado__gte=timezone.now() - timedelta(days=30),
    )
    for producao in recentes:
        avisos = _avisos(producao)
        if avisos["pendentes"] and avisos.get("ultimo") != dia:
            enviados += bool(avisar(producao))
    return enviados


def destinatario(producao):
    """O e-mail de quem acompanha: a conta do pedido, ou a do orçamento (ou o cadastro)."""
    if producao.pedido_id:
        cliente = producao.pedido.cliente
        conta = getattr(cliente, "user", None) if cliente else None
        return ((getattr(conta, "email", "") or "").strip(),
                (getattr(cliente, "nome_completo", "") or getattr(conta, "first_name", "") or "").split(" ")[0])
    orcamento = producao.orcamento
    email = ""
    if orcamento.conta_id and orcamento.conta and orcamento.conta.email:
        email = orcamento.conta.email
    email = email or orcamento.email_destinatario
    return (email or "").strip(), (orcamento.destinatario or "").split(" ")[0]


def titulo_da_origem(producao) -> str:
    if producao.pedido_id:
        return f"Pedido #{producao.pedido_id}"
    return f"Orçamento nº {producao.orcamento.numero_documento}"


def frase_do_aviso(producao, chave) -> str:
    if chave == "producao":
        return "Entrou em produção" if producao.pedido_id else "Sua compra entrou em produção"
    if chave == "pronta":
        if producao.pedido_id and producao.pedido.retirada:
            return "Tudo pronto: já pode retirar na fábrica"
        if producao.pedido_id:
            return "Tudo pronto e embalado para o envio"
        return "Tudo pronto para a entrega"
    nome = NOME_DA_ETAPA.get(chave, chave)
    return f"{nome}: concluída"


def montar_aviso(producao, chaves):
    """O e-mail (sem enviar): os fatos, a linha do tempo e a previsão."""
    email, nome = destinatario(producao)
    if not email:
        return None
    acompanhamento = acompanhamento_da_producao(producao)
    return {
        "para": email,
        "assunto": f"{titulo_da_origem(producao)}: {frase_do_aviso(producao, chaves[-1]).lower()} — Lazer & Sport",
        "nome": nome or "cliente",
        "titulo": titulo_da_origem(producao),
        "fatos": [frase_do_aviso(producao, chave) for chave in chaves],
        "grupos": acompanhamento.grupos,
        "previsao": acompanhamento.previsao,
    }


# ----------------------------------------------------------------------
# O QUE O CLIENTE VÊ (Meus pedidos, o acompanhamento do orçamento)
# ----------------------------------------------------------------------
@dataclass
class EtapaVista:
    chave: str
    nome: str
    icone: str
    estado: str  # feita | atual | futura
    nota: str = ""


@dataclass
class GrupoDeEtapas:
    """As etapas de UMA trilha da origem (máquinas, brinquedão, peças...)."""

    titulo: str
    etapas: list
    posicao: int | None = None


@dataclass
class AcompanhamentoDaProducao:
    situacao: str
    nota: str
    previsao: str
    #: um grupo por trilha (sem título quando a origem só tem uma)
    grupos: list
    na_fila: bool = False
    posicao: int | None = None
    pronta: bool = False

    @property
    def etapas(self):
        """Todas as etapas, em sequência (o e-mail e quem só quer a lista)."""
        return [etapa for grupo in self.grupos for etapa in grupo.etapas]


TITULO_DA_TRILHA = {
    "maquina": "Máquinas",
    "projeto": "Brinquedão / espaço",
    "kit": "Kit eletrônico",
    "peca": "Peças de reposição",
}


def _dm(dia) -> str:
    return dia.strftime("%d/%m") if dia else ""


def texto_da_previsao(de, ate) -> str:
    if not de and not ate:
        return ""
    if not de or not ate or de == ate:
        return f"previsão {_dm(ate or de)}"
    return f"previsão entre {_dm(de)} e {_dm(ate)}"


def _etapas_da_trilha(trilha, unidades):
    """As etapas de uma trilha: feita quando TODAS as máquinas dela a fizeram."""
    S = unidades[0].Situacao
    em_producao = any(u.situacao == S.PRODUCAO for u in unidades)
    etapas, atual_marcada = [], False
    for chave, nome, icone in etapas_da(trilha):
        if all(chave in (u.etapas_em or {}) for u in unidades):
            momento = max(_momento(u.etapas_em[chave]) for u in unidades)
            etapas.append(EtapaVista(chave, nome, icone, "feita", _dm(dia_local(momento)) if momento else ""))
            continue
        prevista = max((_data((u.previstas or {}).get(chave)) for u in unidades if (u.previstas or {}).get(chave)),
                       default=None)
        estado = "futura"
        if em_producao and not atual_marcada:
            estado, atual_marcada = "atual", True
        etapas.append(EtapaVista(chave, nome, icone, estado, f"prev. {_dm(prevista)}" if prevista else ""))
    return etapas


def acompanhamento_da_producao(producao, unidades=None) -> AcompanhamentoDaProducao:
    """A produção da origem, como o cliente lê: a fila, as etapas e a previsão.

    Uma linha de etapas por trilha: a máquina tem as 7 (corte de MDF ...
    embalagem), o brinquedão as dele, a peça separação e embalagem -- uma
    lista só misturaria "Fabricação" no meio das etapas da máquina.
    """
    from .models import ProducaoOrigem, UnidadeMontagem

    S = UnidadeMontagem.Situacao
    unidades = [u for u in (unidades if unidades is not None else producao.unidades.all())
                if u.situacao != S.CANCELADA]
    de = max((u.previsao_de for u in unidades if u.previsao_de), default=None)
    ate = max((u.previsao_ate for u in unidades if u.previsao_ate), default=None)
    # o prazo que a EQUIPE deu (e não a lista) é promessa: a previsão não
    # sai antes dele -- a mesma regra de `prazo_de_entrega`
    origem = producao.pedido if producao.pedido_id else producao.orcamento
    if origem is not None and not producao.prazo_automatico and origem.prazo_producao_dias:
        combinada = origem.previsao_producao
        if combinada and (ate is None or combinada > ate):
            ate = combinada
    previsao = texto_da_previsao(de, ate)
    trilhas = [t for t in ("maquina", "projeto", "kit", "peca") if any(u.trilha == t for u in unidades)]
    grupos = []
    for trilha in trilhas:
        da_trilha = [u for u in unidades if u.trilha == trilha]
        posicao = min((u.posicao for u in da_trilha if u.situacao == S.FILA and u.posicao), default=None)
        grupos.append(GrupoDeEtapas(
            TITULO_DA_TRILHA[trilha] if len(trilhas) > 1 else "", _etapas_da_trilha(trilha, da_trilha), posicao,
        ))
    na_fila = [u for u in unidades if u.situacao == S.FILA]
    em_producao = [u for u in unidades if u.situacao == S.PRODUCAO]
    posicoes = [(g.titulo, g.posicao) for g in grupos if g.posicao]
    posicao = posicoes[0][1] if posicoes else None
    P = ProducaoOrigem.Situacao
    if producao.situacao == P.CANCELADA:
        situacao, nota = "Cancelada", ""
    elif producao.situacao == P.ENTREGUE:
        situacao, nota = "Entregue", f"Pronta em {_dm(dia_local(producao.pronto_em))}"
    elif producao.situacao == P.PRONTA:
        situacao, nota = "Pronta", f"Pronta em {_dm(dia_local(producao.pronto_em))}"
    elif na_fila and not em_producao and not any(u.situacao == S.PRONTA for u in unidades):
        situacao = "Na fila de produção"
        if len(posicoes) > 1:
            nota = "Na fila de produção — " + " · ".join(
                f"{titulo.lower()}: posição {numero}" for titulo, numero in posicoes
            )
        elif posicoes:
            nota = f"Na fila de produção — posição {posicao}"
        else:
            nota = "Na fila de produção"
        if previsao:
            nota += f" — {previsao}"
    else:
        atual = next((e for g in grupos for e in g.etapas if e.estado == "atual"), None)
        situacao = "Em produção"
        nota = f"Em produção · {atual.nome}" if atual else "Em produção"
        if na_fila:
            nota += f" · {len(na_fila)} na fila"
        if previsao:
            nota += f" — {previsao}"
    return AcompanhamentoDaProducao(
        situacao=situacao, nota=nota, previsao=previsao, grupos=grupos,
        na_fila=bool(na_fila) and not em_producao, posicao=posicao,
        pronta=producao.situacao in (P.PRONTA, P.ENTREGUE),
    )


# ----------------------------------------------------------------------
# O PRAZO DE ENTREGA, NUM LUGAR SÓ
# ----------------------------------------------------------------------
@dataclass
class PrazoDeEntrega:
    """Quando fica pronto: em dias úteis a partir de hoje (antes da compra)
    ou em datas (depois). `fila`: a previsão inclui a espera por vaga."""

    dias_min: int | None
    dias_max: int | None
    data_de: date | None = None
    data_ate: date | None = None
    fila: bool = False
    texto: str = ""
    detalhe: str = ""


def _texto_dos_dias(de, ate) -> str:
    if de is None:
        return ""
    if ate is None or ate == de:
        return texto_dos_dias(de)
    return f"{de} a {texto_dos_dias(ate)}"


def _estado_das_linhas(config):
    return _guardado("linhas", lambda: _ler_estado_das_linhas(config))


def _ler_estado_das_linhas(config):
    from .models import UnidadeMontagem

    S = UnidadeMontagem.Situacao
    dia = hoje()
    maquinas = UnidadeMontagem.objects.filter(trilha="maquina", situacao__in=(S.FILA, S.PRODUCAO))
    em_montagem = maquinas.filter(situacao=S.PRODUCAO).count()
    na_fila = maquinas.filter(situacao=S.FILA).count()
    projetos = list(
        UnidadeMontagem.objects.filter(trilha="projeto", situacao__in=(S.FILA, S.PRODUCAO))
        .values_list("previsao_ate", flat=True)
    )
    vagas_projeto = sorted(max(p or dia, dia) for p in projetos)
    return em_montagem, na_fila, vagas_projeto


def previsao_antes_da_compra(linhas, config=None) -> PrazoDeEntrega:
    """O prazo que o cliente lê ANTES de comprar: a fila de agora + a montagem.

    Máquinas: com vaga para todas, só a montagem (4–5 dias úteis); sem
    vaga, a faixa da fila (15 a 30) + a montagem. Brinquedões: depois de
    TODOS os que já estão na linha deles (posição × 30). Peças: 3 dias.
    """
    config = config or configuracao()
    if not linhas:
        return PrazoDeEntrega(None, None)
    em_montagem, na_fila, vagas_projeto = _estado_das_linhas(config)
    dia = hoje()
    minimos, maximos, fila, partes = [], [], False, []
    maquinas = [l for l in linhas if l.trilha == "maquina"]
    if maquinas:
        dias = max(l.dias for l in maquinas)
        unidades = sum(l.quantidade for l in maquinas)
        livres = 0 if na_fila else max(config.capacidade_maquinas - em_montagem, 0)
        if unidades <= livres:
            minimos.append(dias)
            maximos.append(dias)
            partes.append(f"montagem: {texto_dos_dias(dias)}")
        else:
            fila = True
            minimos.append(config.fila_min_dias + dias)
            maximos.append(config.fila_max_dias + dias)
            partes.append(f"fila de produção: {config.fila_min_dias} a {config.fila_max_dias} dias úteis + montagem: {texto_dos_dias(dias)}")
    projetos = [l for l in linhas if l.trilha == "projeto"]
    if projetos:
        vagas = list(vagas_projeto)
        if len(vagas) >= config.capacidade_projetos:
            fila = True
        vagas += [dia] * max(config.capacidade_projetos - len(vagas), 0)
        fim = dia
        for linha in projetos:
            for _ in range(linha.quantidade):
                vagas.sort()
                comeco = vagas.pop(0)
                fim = somar_dias_uteis(comeco, linha.dias)
                vagas.append(fim)
        dias = dias_uteis_entre(dia, fim)
        minimos.append(dias)
        maximos.append(dias)
        partes.append(
            f"brinquedão: {texto_dos_dias(max(l.dias for l in projetos))} cada, um por vez"
            + (" (há outros na frente)" if fila else "")
        )
    pecas = [l for l in linhas if l.trilha in ("peca", "kit")]
    if pecas:
        minimos.append(config.dias_pecas)
        maximos.append(config.dias_pecas)
        partes.append(f"peças: {texto_dos_dias(config.dias_pecas)}")
    de, ate = max(minimos), max(maximos)
    texto = _texto_dos_dias(de, ate)
    return PrazoDeEntrega(
        de, ate, somar_dias_uteis(dia, de), somar_dias_uteis(dia, ate), fila,
        texto=texto, detalhe="; ".join(partes),
    )


def prazo_de_entrega(origem) -> PrazoDeEntrega:
    """O prazo de um pedido ou de um orçamento -- a resposta única (contrato incluído).

    Já na produção: as datas das máquinas (a última pronta). Ainda não:
    a previsão de agora (a fila + a montagem). O prazo que a EQUIPE deu
    (digitado, e não escrito pela lista) vale por cima, como piso.
    """
    from core.models import Pedido

    from .models import ProducaoOrigem

    producao = None
    try:
        producao = origem.producao
    except ProducaoOrigem.DoesNotExist:
        producao = None
    except AttributeError:
        producao = None
    if producao is not None and producao.situacao != ProducaoOrigem.Situacao.CANCELADA:
        unidades = _todas(producao)
        de = max((u.previsao_de for u in unidades if u.previsao_de), default=None)
        ate = max((u.previsao_ate for u in unidades if u.previsao_ate), default=None)
        inicio = origem.inicio_da_producao or hoje()
        fila = any(u.situacao == u.Situacao.FILA for u in unidades)
        dias_de = dias_uteis_entre(inicio, de) if de else None
        dias_ate = dias_uteis_entre(inicio, ate) if ate else None
        prazo = PrazoDeEntrega(dias_de, dias_ate, de, ate, fila, texto=_texto_dos_dias(dias_de, dias_ate),
                               detalhe=acompanhamento_da_producao(producao, unidades).nota)
    else:
        regras = Regras.agora()
        if isinstance(origem, Pedido):
            linhas = linhas_do_pedido(origem, regras)
        else:
            linhas = linhas_do_orcamento(origem, regras, dias_de_projeto_do_orcamento(origem))
        prazo = previsao_antes_da_compra(linhas, regras.config)
    digitado = origem.prazo_producao_dias
    automatico = producao is not None and producao.prazo_automatico
    if digitado is not None and not automatico and (prazo.dias_max is None or digitado > prazo.dias_max):
        inicio = origem.inicio_da_producao or hoje()
        prazo = PrazoDeEntrega(digitado, digitado, somar_dias_uteis(inicio, digitado),
                               somar_dias_uteis(inicio, digitado), False, texto=texto_dos_dias(digitado),
                               detalhe="prazo combinado com a equipe")
    return prazo


def prazo_do_produto(objeto, quantidade=1) -> PrazoDeEntrega:
    """A previsão da página do produto e do carrinho (um brinquedo, combo, promoção ou peça)."""
    from core.models import Brinquedos, Combos, PecasReposicao, Promocoes

    if objeto is None or not getattr(objeto, "pk", None):
        return PrazoDeEntrega(None, None)

    def calcular():
        regras = Regras.agora()
        linhas = []
        if isinstance(objeto, Brinquedos):
            linhas.append(_linha_do_brinquedo(regras, objeto, quantidade))
        elif isinstance(objeto, Combos):
            brinquedos = list(objeto.brinquedos.all())
            regras.carregar_categorias(brinquedos)
            linhas += [_linha_do_brinquedo(regras, b, quantidade) for b in brinquedos]
        elif isinstance(objeto, Promocoes):
            brinquedos = [b for b in [objeto.brinquedos, *objeto.brinquedos_extras.all()] if b is not None]
            regras.carregar_categorias(brinquedos)
            linhas += [_linha_do_brinquedo(regras, b, quantidade) for b in brinquedos]
        elif isinstance(objeto, PecasReposicao):
            linhas.append(_linha_da_peca(regras, objeto, quantidade))
        return previsao_antes_da_compra(linhas, regras.config)

    return _guardado(f"produto:{objeto._meta.model_name}:{objeto.pk}:{quantidade}", calcular)


def prazo_do_carrinho(carrinho) -> PrazoDeEntrega:
    """A previsão do carrinho inteiro (as máquinas juntas disputam as vagas)."""
    from core.models import Brinquedos, Combos, PecasReposicao, Promocoes

    # Sem guardar o resultado: o carrinho muda a cada toque, e a conta custa
    # uma consulta só (as categorias das máquinas dele, em lote) -- a mesma
    # com uma ou com sete máquinas (core/tests_telas_do_site).
    return _prazo_dos_itens(list(carrinho.itens.all()))


def _prazo_dos_itens(itens) -> PrazoDeEntrega:
    from core.models import Brinquedos, Combos, PecasReposicao, Promocoes

    regras = Regras.agora()
    regras.carregar_categorias([i.item for i in itens if isinstance(i.item, Brinquedos)])
    linhas = []
    for item in itens:
        objeto = item.item
        quantidade = max(int(item.quantidade or 1), 1)
        if isinstance(objeto, Brinquedos):
            linhas.append(_linha_do_brinquedo(regras, objeto, quantidade))
        elif isinstance(objeto, Combos):
            linhas += [_linha_do_brinquedo(regras, b, quantidade) for b in objeto.brinquedos.all()]
        elif isinstance(objeto, Promocoes):
            linhas += [_linha_do_brinquedo(regras, b, quantidade)
                       for b in [objeto.brinquedos, *objeto.brinquedos_extras.all()] if b is not None]
        elif isinstance(objeto, PecasReposicao):
            linhas.append(_linha_da_peca(regras, objeto, quantidade))
    return previsao_antes_da_compra(linhas, regras.config)


def _producao_ja_lida(origem):
    """A produção que a consulta já trouxe (select_related), sem consulta a mais."""
    from .models import ProducaoOrigem

    cache = getattr(origem, "_state", None)
    campos = getattr(cache, "fields_cache", {}) if cache is not None else {}
    if "producao" not in campos:
        return None
    producao = campos["producao"]
    if producao is None or producao.situacao == ProducaoOrigem.Situacao.CANCELADA:
        return None
    return producao


def producao_vista_do_pedido(pedido):
    """A fila e as etapas do pedido em Meus pedidos -- e a nota da fase "Produção".

    Lê só o que a página já trouxe (`select_related("producao")` com as
    unidades em prefetch). Acerta a nota da Produção no `pedido.andamento`
    (core.fases_pedido) enquanto o pedido está pago ou em preparação.
    """
    producao = _producao_ja_lida(pedido)
    if producao is None:
        return None
    vista = acompanhamento_da_producao(producao, list(producao.unidades.all()))
    andamento = getattr(pedido, "andamento", None)
    if andamento is not None and pedido.status in ("pago", "em_preparacao"):
        for fase in andamento.fases:
            if fase.chave == "producao":
                fase.nota = vista.nota
    return vista
