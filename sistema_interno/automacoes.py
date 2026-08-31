"""Automações operacionais seguras, pequenas e idempotentes."""

from django.utils import timezone

from .models import Orcamento


def expirar_orcamentos_vencidos(hoje=None):
    """Expira somente propostas já enviadas e sem resposta.

    Rascunhos podem estar incompletos e negociações podem ter prazo acertado
    fora do sistema; por isso esses dois estados nunca são alterados aqui.
    O update é idempotente: ciclos seguintes não reprocessam a mesma proposta.
    """
    hoje = hoje or timezone.localdate()
    return Orcamento.objects.filter(
        status=Orcamento.Status.AGUARDANDO_RESPOSTA,
        validade__lt=hoje,
    ).update(
        status=Orcamento.Status.EXPIRADO,
        atualizado=timezone.now(),
    )


def executar_automacoes_operacionais():
    return {
        "orcamentos_expirados": expirar_orcamentos_vencidos(),
    }
