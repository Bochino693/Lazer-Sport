"""Observador leve de pendências urgentes com deduplicação de e-mail."""

import hashlib
import json
import logging
import signal
import threading

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone

from sistema_interno.avisos import coletar
from sistema_interno.automacoes import executar_automacoes_operacionais
from sistema_interno.campanhas import processar_emails_pendentes
from sistema_interno.models import EstadoNotificacao
from sistema_interno.notificacoes import enviar_pendencias_urgentes


log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Observa pendências urgentes e envia e-mail somente quando o estado muda."

    def add_arguments(self, parser):
        parser.add_argument("--uma-vez", action="store_true")
        parser.add_argument("--intervalo", type=int, default=60)

    def handle(self, *args, **options):
        parar = threading.Event()

        def encerrar(*_args):
            parar.set()

        signal.signal(signal.SIGTERM, encerrar)
        signal.signal(signal.SIGINT, encerrar)
        intervalo = max(30, int(options["intervalo"]))

        # O worker também bate no endereço público. Dois processos batendo
        # é redundância barata: se o web cair e voltar, ou se a thread
        # dele morrer por qualquer motivo, o worker continua segurando a
        # instância de pé. Ver `core/sempre_pronto.py`.
        from core import sempre_pronto

        sempre_pronto.ligar()

        self.stdout.write("Observador de pendências iniciado.")
        while not parar.is_set():
            try:
                self._executar_ciclo()
            except Exception:
                # Uma oscilação do banco ou SMTP não pode matar o processo
                # que deveria continuar observando o restante do dia.
                log.exception("Falha em um ciclo do observador de pendências.")
                close_old_connections()
            if options["uma_vez"]:
                break
            parar.wait(intervalo)
        self.stdout.write("Observador de pendências encerrado.")

    def _executar_ciclo(self):
        # Regras idempotentes entram antes dos avisos para que a equipe já
        # receba o estado correto no mesmo ciclo. Nenhuma etapa operacional
        # que dependa de confirmação humana é avançada automaticamente.
        resultados = executar_automacoes_operacionais()
        if any(resultados.values()):
            log.info("Automações operacionais executadas: %s", resultados)

        # A mesma sentinela leve processa a outbox comercial. O clique que
        # cria uma campanha nunca espera SMTP e uma oscilação do provedor
        # não derruba a central de avisos.
        try:
            processar_emails_pendentes(limite=20)
        except Exception:
            # A outbox e os avisos urgentes compartilham o processo, não o
            # destino: falha num e-mail comercial não pode atrasar pedido,
            # estoque ou cliente incompleto.
            log.exception("Falha ao processar a fila de campanhas.")
            close_old_connections()

        Usuario = get_user_model()
        usuarios = Usuario.objects.filter(is_active=True).filter(
            is_staff=True
        ) | Usuario.objects.filter(is_active=True, is_superuser=True)

        for usuario in usuarios.distinct().iterator():
            urgentes = [aviso for aviso in coletar(usuario) if aviso.urgente]
            payload = [
                {
                    "chave": aviso.chave,
                    "quantidade": aviso.quantidade,
                    "nivel": aviso.nivel,
                    "detalhe": aviso.detalhe,
                }
                for aviso in urgentes
            ]
            assinatura = hashlib.sha256(
                json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
            ).hexdigest() if payload else ""

            estado, _ = EstadoNotificacao.objects.get_or_create(
                usuario=usuario,
                chave="urgencias",
            )
            if estado.assinatura == assinatura:
                continue

            if not urgentes:
                estado.assinatura = ""
                estado.quantidade = 0
                estado.save(update_fields=["assinatura", "quantidade", "atualizado"])
                continue

            if enviar_pendencias_urgentes(usuario, urgentes):
                estado.assinatura = assinatura
                estado.quantidade = sum(aviso.quantidade for aviso in urgentes)
                estado.email_enviado_em = timezone.now()
                estado.save(update_fields=[
                    "assinatura", "quantidade", "email_enviado_em", "atualizado",
                ])

        close_old_connections()
