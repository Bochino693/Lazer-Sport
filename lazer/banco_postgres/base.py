"""A conferência da conexão reaproveitada, sem uma viagem ao banco quando ela não ensina nada.

O QUE CUSTAVA. Com `CONN_HEALTH_CHECKS`, o Django faz um `SELECT 1` antes da
primeira consulta de TODA requisição que reaproveita a conexão. O banco
fica em outra região (LEIA-ME-V10, seções 63 e 120): cada viagem custa
~170 ms. Uma gravação do painel são três requisições quase juntas (a ação,
a lista e o sino), e as três pagavam a conferência -- meio segundo em cada
clique só para perguntar "você ainda está aí?" a uma conexão que tinha
respondido milissegundos antes.

POR QUE A CONFERÊNCIA EXISTE, E CONTINUA EXISTINDO. O pooler do Supabase
encerra conexão ociosa, e o Supabase pode reiniciar. Sem conferir, a
primeira consulta numa conexão morta estoura `OperationalError` e a tela
cai (no painel, vira a tela de "tente de novo"; no site, um 500). Isso não
pode voltar.

O QUE MUDA. Quando o servidor (ou o pooler) fecha a conexão, ele avisa
pelo próprio socket: chega um FIN (ou a mensagem FATAL de encerramento),
e o socket, que entre uma requisição e outra não devia ter nada para ler,
fica LEGÍVEL. Se o caminho de rede morre calado, o keepalive do TCP
(`keepalives_idle=30`, settings.py) faz o sistema operacional marcar o
erro no socket -- legível também. Perguntar isso ao sistema operacional
(`poll` com prazo zero) não sai da máquina: microssegundos, nenhuma viagem.
É a mesma conferência que o urllib3 faz antes de reaproveitar uma conexão
HTTP (`is_connection_dropped`).

Então: conexão usada há menos de `DB_CONEXAO_RECENTE_S` segundos, fora de
transação, com o socket quieto -> dispensa o `SELECT 1`. Qualquer outra
coisa (socket legível ou com erro, conexão parada há mais tempo que isso,
estado de transação estranho, qualquer exceção ao perguntar) -> a
conferência de sempre, com a viagem. A janela é curta de propósito: o que
o pooler encerra é conexão PARADA há minutos, e conexão parada há mais de
meio minuto paga a conferência como antes.

`DB_CONEXAO_RECENTE_S=0` volta ao comportamento antigo (toda requisição
confere). Só vale com `CONN_HEALTH_CHECKS` ligado -- sem ele o Django não
confere nada, e aqui também não.
"""

from __future__ import annotations

import select
import time

from django.conf import settings
from django.db.backends.postgresql import base as postgresql

#: libpq / psycopg: conexão parada, fora de qualquer transação.
_FORA_DE_TRANSACAO = 0


def segundos_de_confianca() -> float:
    """Quanto tempo depois do último uso a conexão quieta dispensa o SELECT 1."""
    try:
        return max(0.0, float(getattr(settings, "DB_CONEXAO_RECENTE_S", 0) or 0))
    except (TypeError, ValueError):
        return 0.0


def socket_quieto(conexao) -> bool:
    """True quando nada chegou pelo socket da conexão parada -- nem dado, nem fim, nem erro.

    Qualquer dúvida devolve False, e quem perguntou faz a conferência de verdade.
    """
    try:
        if getattr(conexao, "closed", 1):
            return False
        if int(conexao.info.transaction_status) != _FORA_DE_TRANSACAO:
            return False
        descritor = conexao.fileno()
        if hasattr(select, "poll"):
            vigia = select.poll()
            vigia.register(descritor, select.POLLIN | select.POLLPRI | select.POLLERR | select.POLLHUP)
            return not vigia.poll(0)
        legiveis, _, com_erro = select.select([descritor], [], [descritor], 0)
        return not legiveis and not com_erro
    except Exception:  # noqa: BLE001 -- na dúvida, confere com a viagem
        return False


class DatabaseWrapper(postgresql.DatabaseWrapper):
    #: Instante (relógio monotônico) do último cursor aberto nesta conexão.
    _ls_ultimo_uso = None

    def connect(self):
        self._ls_ultimo_uso = None
        super().connect()

    def create_cursor(self, name=None):
        cursor = super().create_cursor(name)
        # O começo da última consulta, não o fim: a conta da ociosidade sai
        # maior que a real (mais conferências, nunca menos).
        self._ls_ultimo_uso = time.monotonic()
        return cursor

    def conexao_recente_e_quieta(self) -> bool:
        janela = segundos_de_confianca()
        ultimo = self._ls_ultimo_uso
        if janela <= 0 or ultimo is None or time.monotonic() - ultimo >= janela:
            return False
        return socket_quieto(self.connection)

    def close_if_health_check_failed(self):
        if (
            self.connection is not None
            and self.health_check_enabled
            and not self.health_check_done
            and not getattr(self, "pool", None)
            and self.conexao_recente_e_quieta()
        ):
            self.health_check_done = True
            return
        super().close_if_health_check_failed()
