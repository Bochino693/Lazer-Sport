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
    """Um ciclo do observador: primeiro lembrar, depois expirar.

    A ORDEM IMPORTA E É O PONTO DELA. Expirar antes de lembrar seria
    matar a proposta e só então avisar o cliente de que ela existia --
    o lembrete chegaria sobre um documento que a página pública já
    recusa. Lembrando primeiro, quem estava para decidir ainda tem os
    dias que restam.
    """
    # Importado aqui, e não no topo, porque o módulo do cliente carrega
    # template e SMTP: quem só quer expirar não paga por isso.
    from .notificacoes_cliente import lembrar_propostas_a_vencer

    return {
        "lembretes_ao_cliente": lembrar_propostas_a_vencer(),
        "orcamentos_expirados": expirar_orcamentos_vencidos(),
    }
