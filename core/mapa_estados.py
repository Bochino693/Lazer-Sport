"""Os estados do mapa da home, coloridos pelo nível de pedidos de brinquedos.

O QUE CONTA COMO PEDIDO, POR ESTADO (UF):
  * proposta APROVADA no painel (sistema_interno.Orcamento), no estado do
    cliente -- o primeiro endereço dele, o mesmo que vira o alfinete;
  * pedido da loja online pago ou adiante (pago, em preparação, saiu para
    entrega, finalizado), no estado de entrega do pedido;
  * cliente publicado no mapa sem nenhuma proposta aprovada registrada
    conta 1: ele comprou (é por isso que está no mapa), só que antes do
    painel existir. Assim todo estado com alfinete aparece colorido.

O SITE MOSTRA A FAIXA, NUNCA O NÚMERO. O número exato de pedidos por
estado é informação comercial; a página pública só recebe o nível (1 a 5)
e o rótulo da faixa ("3 a 5 pedidos"). A conta inteira roda ao montar o
cache da home, e não a cada visita.
"""

from __future__ import annotations

import unicodedata
from collections import Counter

#: As faixas da legenda, da mais clara à mais escura. O último limite é
#: aberto ("21 ou mais").
FAIXAS = ((1, 2), (3, 5), (6, 10), (11, 20), (21, None))

UFS = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas",
    "BA": "Bahia", "CE": "Ceará", "DF": "Distrito Federal",
    "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão",
    "MT": "Mato Grosso", "MS": "Mato Grosso do Sul", "MG": "Minas Gerais",
    "PA": "Pará", "PB": "Paraíba", "PR": "Paraná", "PE": "Pernambuco",
    "PI": "Piauí", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima",
    "SC": "Santa Catarina", "SP": "São Paulo", "SE": "Sergipe",
    "TO": "Tocantins",
}

STATUS_DA_LOJA_QUE_CONTAM = ("pago", "em_preparacao", "saiu_entrega", "finalizado")


def _sem_acento(texto: str) -> str:
    normal = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in normal if not unicodedata.combining(c)).casefold().strip()


_POR_NOME = {_sem_acento(nome): uf for uf, nome in UFS.items()}


def uf_de(valor) -> str:
    """'SP', 'sp', 'São Paulo', 'Sao Paulo ' -> 'SP'; o que não for estado -> ''."""
    texto = (valor or "").strip()
    if not texto:
        return ""
    if texto.upper() in UFS:
        return texto.upper()
    return _POR_NOME.get(_sem_acento(texto), "")


def nivel_de(quantidade: int) -> int:
    """0 sem pedido; 1 a len(FAIXAS) pela faixa."""
    if quantidade <= 0:
        return 0
    for indice, (_minimo, maximo) in enumerate(FAIXAS, start=1):
        if maximo is None or quantidade <= maximo:
            return indice
    return len(FAIXAS)


def rotulo_da_faixa(minimo: int, maximo) -> str:
    if maximo is None:
        return f"{minimo} ou mais pedidos"
    if minimo == maximo:
        return f"{minimo} pedido" + ("" if minimo == 1 else "s")
    return f"{minimo} a {maximo} pedidos"


def pedidos_por_estado(clientes_no_mapa=()) -> Counter:
    """Quantos pedidos de brinquedos cada estado (UF) já fez.

    `clientes_no_mapa`: pares (cliente_id, estado) dos clientes publicados
    no mapa -- os que ainda não têm proposta aprovada contam 1.
    """
    from django.db.models import OuterRef, Subquery

    from core.models import Pedido
    from sistema_interno.models import EnderecoCliente, Orcamento

    contagem: Counter = Counter()

    primeiro_endereco = (
        EnderecoCliente.objects
        .filter(cliente_id=OuterRef("cliente_id"))
        .order_by("id")
        .values("estado")[:1]
    )
    clientes_com_pedido = set()
    aprovadas = (
        Orcamento.objects
        .filter(status=Orcamento.Status.APROVADO, cliente__isnull=False)
        .annotate(_uf=Subquery(primeiro_endereco))
        .values_list("cliente_id", "_uf")
    )
    for cliente_id, estado in aprovadas:
        clientes_com_pedido.add(cliente_id)
        uf = uf_de(estado)
        if uf:
            contagem[uf] += 1

    da_loja = (
        Pedido.objects
        .filter(status__in=STATUS_DA_LOJA_QUE_CONTAM)
        .values_list("estado", flat=True)
    )
    for estado in da_loja:
        uf = uf_de(estado)
        if uf:
            contagem[uf] += 1

    for cliente_id, estado in clientes_no_mapa:
        if cliente_id in clientes_com_pedido:
            continue
        uf = uf_de(estado)
        if uf:
            contagem[uf] += 1

    return contagem


def dados_do_mapa(clientes_no_mapa=()) -> dict:
    """O que a página recebe: só o nível de cada estado e a legenda."""
    contagem = pedidos_por_estado(clientes_no_mapa)
    return {
        "niveis": {uf: nivel_de(n) for uf, n in sorted(contagem.items()) if n > 0},
        "nomes": UFS,
        "faixas": [
            {"nivel": i, "rotulo": rotulo_da_faixa(minimo, maximo)}
            for i, (minimo, maximo) in enumerate(FAIXAS, start=1)
        ],
    }
