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

from django.core.cache import cache
from django.db.models import Avg, Q, Sum
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

    ativos = Brinquedos.objects.filter(ativo=True)
    media = ativos.aggregate(media=Avg("avaliacao"))["media"]
    return {
        "brinquedos": ativos.count(),
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
    em_producao = (
        OrdemProducao.objects
        .filter(status=OrdemProducao.Status.EM_PRODUCAO)
        .aggregate(total=Sum("quantidade"))["total"]
    ) or 0
    fabricados_no_mes = (
        OrdemProducao.objects
        .filter(status=OrdemProducao.Status.CONCLUIDA, concluida_em__gte=inicio_do_mes)
        .aggregate(total=Sum("quantidade"))["total"]
    ) or 0
    servicos_no_mes = OrdemServico.objects.filter(
        status=OrdemServico.Status.CONCLUIDA, concluida_em__gte=inicio_do_mes,
    ).count()
    servicos_agora = OrdemServico.objects.filter(
        status__in=(
            OrdemServico.Status.AGENDADA,
            OrdemServico.Status.EM_EXECUCAO,
            OrdemServico.Status.AGUARDANDO_PECA,
        ),
    ).count()
    return {
        "em_producao": em_producao,
        "fabricados_no_mes": fabricados_no_mes,
        "servicos_no_mes": servicos_no_mes,
        "servicos_agora": servicos_agora,
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
    """Os números do painel, guardados por um minuto."""
    dados = cache.get(CHAVE_CACHE)
    if dados is None:
        dados = calcular()
        cache.set(CHAVE_CACHE, dados, VALIDADE)
    return dados
