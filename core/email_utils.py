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

from email.utils import formataddr, parseaddr

from django.conf import settings


NOME_EMPRESA_PADRAO = "Fábrica de brinquedos Lazer Sport"
CNPJ_EMPRESA_PADRAO = "54.486.908/0001-86"


def nome_empresa() -> str:
    """Nome jurídico/comercial exibido nos documentos do cliente."""
    return (
        getattr(settings, "EMPRESA_RAZAO_SOCIAL", "")
        or getattr(settings, "EMPRESA_NOME", "")
        or NOME_EMPRESA_PADRAO
    ).strip()


def cnpj_empresa() -> str:
    """CNPJ configurável, com o cadastro informado como padrão seguro."""
    return (
        getattr(settings, "EMPRESA_CNPJ", "")
        or CNPJ_EMPRESA_PADRAO
    ).strip()


def dados_bancarios_empresa() -> dict[str, str]:
    """Dados exibidos apenas nas áreas de pagamento dos documentos."""
    return {
        "pix_celular": (
            getattr(settings, "EMPRESA_PIX_CELULAR", "") or "11 96763-7589"
        ).strip(),
        "pix_cnpj": (
            getattr(settings, "EMPRESA_PIX_CNPJ", "") or cnpj_empresa()
        ).strip(),
        "santander_agencia": (
            getattr(settings, "EMPRESA_SANTANDER_AGENCIA", "") or "0563"
        ).strip(),
        "santander_conta": (
            getattr(settings, "EMPRESA_SANTANDER_CONTA", "") or "13.006139-1"
        ).strip(),
    }


def remetente() -> str:
    """Endereço que assina o envio, no formato 'Nome <e-mail>'."""
    configurado = (getattr(settings, "DEFAULT_FROM_EMAIL", "") or "").strip()
    nome, endereco = parseaddr(configurado)
    if not endereco:
        endereco = (getattr(settings, "EMAIL_HOST_USER", "") or "").strip()
    if not endereco:
        return configurado
    return formataddr((nome or "Lazer & Sport Brinquedos", endereco))


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

    comercial = getattr(settings, "ORCAMENTO_EMAIL", "")
    if _endereco_valido(comercial) and comercial.strip() not in candidatos:
        candidatos.append(comercial.strip())

    return candidatos


def backend_de_transporte() -> str:
    backend = getattr(settings, "EMAIL_BACKEND", "")
    if backend == "core.email_backend.EmailBackend":
        return getattr(settings, "EMAIL_TRANSPORT_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
    return backend


def smtp_configurado() -> bool:
    """Diz se dá para tentar enviar, sem esperar o timeout do SMTP.

    Backend que não é SMTP (console, arquivo, memória nos testes) sempre
    entrega: a checagem de credencial só faz sentido para o SMTP real.
    """
    backend = backend_de_transporte()
    if "smtp" not in backend:
        return True

    return bool(
        getattr(settings, "EMAIL_HOST_USER", "")
        and getattr(settings, "EMAIL_HOST_PASSWORD", "")
    )


def diagnostico_smtp() -> str:
    """Explicação curta e segura para a tela de envio.

    Não devolve host, usuário nem segredo. A equipe só precisa saber se o
    envio está disponível e, quando não está, qual grupo de configuração
    falta na hospedagem.
    """
    backend = backend_de_transporte()
    if "smtp" not in backend:
        return "Envio de e-mail disponível pelo backend configurado."
    faltam = []
    if not getattr(settings, "EMAIL_HOST_USER", ""):
        faltam.append("usuário")
    if not getattr(settings, "EMAIL_HOST_PASSWORD", ""):
        faltam.append("senha")
    if faltam:
        return "SMTP indisponível: falta " + " e ".join(faltam) + "."
    return "SMTP configurado e pronto para tentativa de envio."
