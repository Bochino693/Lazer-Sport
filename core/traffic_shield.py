"""Proteção WSGI de custo constante contra saturação da instância.

Roda antes do Django: probes de WordPress/PHP e filtros legados não abrem
sessão, conexão com PostgreSQL, templates nem context processors. Também
limita a concorrência pública, reservando threads para o painel interno e
para o health check.
"""

from __future__ import annotations

import os
import re
import threading
import time
from collections import defaultdict, deque


_PROBE_RE = re.compile(
    r"(?:\.php(?:/|$)|/(?:wp-admin|wp-content|wp-includes|cgi-bin)(?:/|$)|"
    r"/(?:\.env|\.git|vendor/phpunit|xmlrpc\.php)(?:/|$))",
    re.IGNORECASE,
)
_BOT_MARKERS = (
    "bot", "crawler", "spider", "meta-externalagent", "facebookexternalhit",
    "bytespider", "semrush", "ahrefs", "mj12bot",
)
_PUBLIC_EXPENSIVE = ("/brinquedos/", "/loja/", "/produto-tag/")


def _integer(name: str, default: int, minimum: int) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


class TrafficShieldWSGI:
    """Rejeita lixo e impede tráfego público de tomar a instância inteira."""

    def __init__(self, application):
        self.application = application
        # Com WEB_THREADS=8, quatro requisições públicas podem consultar o
        # catálogo; as demais threads continuam disponíveis ao painel.
        self.public_slots = threading.BoundedSemaphore(
            _integer("PUBLIC_CONCURRENCY", 4, 1)
        )
        self.bot_limit = _integer("BOT_REQUESTS_PER_MINUTE", 24, 4)
        self._bot_hits = defaultdict(deque)
        self._bot_lock = threading.Lock()

    def __call__(self, environ, start_response):
        path = (environ.get("PATH_INFO") or "/")[:2048]
        query = (environ.get("QUERY_STRING") or "")[:8192]

        if _PROBE_RE.search(path):
            return self._plain(start_response, "404 Not Found", b"not found")

        # filter_cat pertence ao WordPress antigo. Redirecionar fazia o bot
        # seguir para /brinquedos/ e pagar a página pesada; 410 encerra a
        # cadeia e ensina o crawler a retirar a URL do índice.
        # Busca direta, limitada aos 8 KiB já cortados acima. Não usamos
        # parse_qs: uma query criada para conter milhares de campos não deve
        # gastar CPU nem conseguir levantar ValueError no próprio escudo.
        if re.search(r"(?:^|&)filter_cat(?:=|&|$)", query, re.IGNORECASE):
            return self._plain(
                start_response,
                "410 Gone",
                b"legacy filter removed",
                (("X-Robots-Tag", "noindex, nofollow"),),
            )

        host = (environ.get("HTTP_HOST") or "").split(":", 1)[0].lower()
        internal = host.startswith("interno.")
        user_agent = (environ.get("HTTP_USER_AGENT") or "").lower()

        if (not internal and path.startswith(_PUBLIC_EXPENSIVE)
                and any(marker in user_agent for marker in _BOT_MARKERS)
                and not self._bot_allowed(environ, user_agent)):
            return self._plain(
                start_response,
                "429 Too Many Requests",
                b"rate limited",
                (("Retry-After", "60"), ("X-Robots-Tag", "noindex")),
            )

        # O painel não disputa esta reserva com o catálogo público.
        acquired = internal or self.public_slots.acquire(blocking=False)
        if not acquired:
            return self._plain(
                start_response,
                "503 Service Unavailable",
                b"busy, retry shortly",
                (("Retry-After", "2"),),
            )
        try:
            return self.application(environ, start_response)
        finally:
            if not internal:
                self.public_slots.release()

    def _bot_allowed(self, environ, user_agent: str) -> bool:
        forwarded = (environ.get("HTTP_X_FORWARDED_FOR") or "").split(",", 1)[0].strip()
        address = forwarded or environ.get("REMOTE_ADDR") or "unknown"
        family = next((m for m in _BOT_MARKERS if m in user_agent), "bot")
        key = (address[:64], family)
        now = time.monotonic()
        cutoff = now - 60.0
        with self._bot_lock:
            hits = self._bot_hits[key]
            while hits and hits[0] < cutoff:
                hits.popleft()
            if len(hits) >= self.bot_limit:
                return False
            hits.append(now)
            # Impede IPs forjados de fazerem o próprio limitador crescer
            # sem limite. Perder histórico é seguro: no pior caso o bot
            # recebe uma janela nova.
            if len(self._bot_hits) > 2048:
                self._bot_hits.clear()
            return True

    @staticmethod
    def _plain(start_response, status, body, extra=()):
        headers = [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
        ]
        headers.extend(extra)
        start_response(status, headers)
        return [body]
