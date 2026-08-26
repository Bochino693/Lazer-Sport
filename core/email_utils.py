"""Como a Lazer & Sport se apresenta nos e-mails que envia.

Dois pontos que decidem se a mensagem chega e se a resposta volta:

* **De** -- quase todo provedor (Gmail, Zoho, Brevo) só aceita enviar com
  o endereço autenticado no SMTP. Trocar o "de" pelo e-mail pessoal do
  vendedor faz a mensagem ser recusada ou cair em spam. Por isso o "de"
  é sempre ``DEFAULT_FROM_EMAIL``, com o nome da empresa na frente.
* **Responder para** -- é aqui que entra o e-mail de quem atende. O
  cliente clica em "responder" e a mensagem vai para a pessoa certa, sem
  mexer na autenticação do envio.
"""

from __future__ import annotations

from django.conf import settings


def remetente() -> str:
    """Endereço que assina o envio, no formato 'Nome <e-mail>'."""
    return settings.DEFAULT_FROM_EMAIL


def _endereco_valido(valor: str) -> bool:
    valor = (valor or "").strip()
    return "@" in valor and " " not in valor


def responder_para(usuario=None) -> list[str]:
    """Para onde vai a resposta do cliente.

    Ordem: o e-mail de quem está enviando (o atendente logado), depois o
    ``EMAIL_RESPOSTA`` do ambiente. Sem nenhum dos dois, devolve lista
    vazia e o e-mail sai sem Reply-To -- a resposta cai na conta do SMTP.
    """
    candidatos = []

    email_usuario = getattr(usuario, "email", "") if usuario else ""
    if _endereco_valido(email_usuario):
        candidatos.append(email_usuario.strip())

    padrao = getattr(settings, "EMAIL_RESPOSTA", "")
    if _endereco_valido(padrao) and padrao.strip() not in candidatos:
        candidatos.append(padrao.strip())

    return candidatos


def smtp_configurado() -> bool:
    """Diz se dá para tentar enviar, sem esperar o timeout do SMTP.

    Backend que não é SMTP (console, arquivo, memória nos testes) sempre
    entrega: a checagem de credencial só faz sentido para o SMTP real.
    """
    backend = getattr(settings, "EMAIL_BACKEND", "")
    if "smtp" not in backend:
        return True

    return bool(
        getattr(settings, "EMAIL_HOST_USER", "")
        and getattr(settings, "EMAIL_HOST_PASSWORD", "")
    )
