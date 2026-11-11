"""O painel ao vivo da home: o que a fábrica está fazendo, em números.

O quadro inicial da home era fixo -- um título, três botões e três
números que nunca mudavam. Este módulo junta o que o sistema interno já
sabe e que o visitante PODE ver: quantos brinquedos estão na linha de
produção agora, quantos serviços técnicos fecharam no mês, quantos
clientes e cidades aparecem no mapa, o que entrou no catálogo.

SÓ TOTAIS, NUNCA REGISTROS. Nada de nome de cliente, valor de proposta,
endereço ou pessoa da equipe sai daqui. Os clientes e as cidades contam
apenas quem já aparece no mapa público da home (com a mesma regra de
publicação dela); a produção e os serviços entram como contagem.

CADA NÚMERO É OPCIONAL. Se uma consulta falhar -- tabela que ainda não
migrou, banco lento --, aquele número some do painel e os outros
continuam. A home não pode cair por causa de um contador.

E É BARATO: o resultado fica um minuto em cache, então mil visitantes na
mesma hora custam uma rodada de consultas por minuto, e não mil.
"""

from __future__ import annotations

import logging

from django.db.models import Avg, Count, Q, Sum
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)

CHAVE_CACHE = "painel-publico:v1"
VALIDADE = 60


def _seguro(nome, conta):
    """Roda uma conta; se ela falhar, o número só não aparece."""
    try:
        return conta()
    except Exception:  # pragma: no cover - depende do banco de produção
        logger.warning("Painel público: o número %s não pôde ser calculado.", nome, exc_info=True)
        return None


def _catalogo():
    from .models import Brinquedos, CategoriasBrinquedos, Eventos, PecasReposicao, Projetos

    # O total e a média numa ida ao banco só (eram duas).
    resumo = Brinquedos.objects.filter(ativo=True).aggregate(total=Count("id"), media=Avg("avaliacao"))
    media = resumo["media"]
    return {
        "brinquedos": resumo["total"],
        "categorias": CategoriasBrinquedos.objects.filter(ativo=True).count(),
        "pecas": PecasReposicao.da_vitrine().count(),
        "eventos": Eventos.objects.count(),
        "projetos": Projetos.objects.count(),
        "avaliacao": round(float(media), 1) if media else None,
    }


def _mapa():
    """Clientes e cidades do mapa público -- a mesma regra que a home usa."""
    from sistema_interno import clientes as clientes_svc
    from sistema_interno.models import EnderecoCliente

    publicados = clientes_svc.com_publicacao_mapa().filter(
        Q(publicar_no_mapa=True) | Q(_proposta_mapa=True)
    ).values("pk")
    enderecos = EnderecoCliente.objects.filter(
        cliente__ativo=True,
        cliente_id__in=publicados,
        latitude__isnull=False,
        longitude__isnull=False,
    )
    return {
        "clientes": enderecos.values("cliente_id").distinct().count(),
        "cidades": enderecos.exclude(cidade="").values("cidade").distinct().count(),
    }


def _fabrica():
    """A linha de produção e a equipe técnica, em contagem."""
    from sistema_interno.models import OrdemProducao, OrdemServico

    inicio_do_mes = timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # Uma consulta por tabela, com os filtros dentro da soma (eram quatro):
    # o painel é refeito a cada minuto enquanto houver alguém na home, e
    # cada ida ao Supabase é uma viagem pela rede.
    producao = OrdemProducao.objects.aggregate(
        em_producao=Sum("quantidade", filter=Q(status=OrdemProducao.Status.EM_PRODUCAO)),
        fabricados_no_mes=Sum(
            "quantidade",
            filter=Q(status=OrdemProducao.Status.CONCLUIDA, concluida_em__gte=inicio_do_mes),
        ),
    )
    servicos = OrdemServico.objects.aggregate(
        no_mes=Count(
            "id",
            filter=Q(status=OrdemServico.Status.CONCLUIDA, concluida_em__gte=inicio_do_mes),
        ),
        agora=Count(
            "id",
            filter=Q(status__in=(
                OrdemServico.Status.AGENDADA,
                OrdemServico.Status.EM_EXECUCAO,
                OrdemServico.Status.AGUARDANDO_PECA,
            )),
        ),
    )
    return {
        "em_producao": producao["em_producao"] or 0,
        "fabricados_no_mes": producao["fabricados_no_mes"] or 0,
        "servicos_no_mes": servicos["no_mes"] or 0,
        "servicos_agora": servicos["agora"] or 0,
    }


def _novidades():
    """O letreiro: o que entrou por último no que já é público."""
    from .models import Brinquedos, Eventos, Projetos

    itens = []
    for brinquedo in Brinquedos.objects.filter(ativo=True).only("id", "nome_brinquedo").order_by("-criacao", "-id")[:3]:
        itens.append({
            "tipo": "novo",
            "texto": f"Novo no catálogo: {brinquedo.nome_brinquedo}",
            "url": reverse("brinquedo_detalhe", args=[brinquedo.pk]) + "#bread",
        })
    evento = Eventos.objects.only("id", "titulo").order_by("-id").first()
    if evento:
        itens.append({
            "tipo": "evento",
            "texto": f"Evento realizado: {evento.titulo}",
            "url": reverse("eventos") + "#todos-eventos",
        })
    projeto = Projetos.objects.only("id", "titulo").order_by("-id").first()
    if projeto:
        itens.append({
            "tipo": "projeto",
            "texto": f"Projeto sob medida: {projeto.titulo}",
            "url": reverse("projetos") + "#todos-projetos",
        })
    return itens


def calcular():
    """Os números, sem cache. Use `numeros()` fora dos testes."""
    dados = {}
    for nome, conta in (("catalogo", _catalogo), ("mapa", _mapa), ("fabrica", _fabrica)):
        parte = _seguro(nome, conta)
        if parte:
            dados.update(parte)
    dados["novidades"] = _seguro("novidades", _novidades) or []
    dados["atualizado_em"] = timezone.now().isoformat()
    return dados


def numeros():
    """Os números do painel, guardados por um minuto.

    Vencido o minuto, em produção, os números de antes continuam servindo
    enquanto os novos são contados por trás (core/renovar.py): o painel é
    pedido a cada minuto por quem está na home, e eram dez consultas na
    conta de quem pedia naquele instante.
    """
    from .renovar import valor

    return valor(CHAVE_CACHE, calcular, VALIDADE)
