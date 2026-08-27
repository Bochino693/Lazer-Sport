"""Helpers de formulário do sistema interno."""

from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit, urlunsplit

from django.utils import timezone


class ErroDeFormulario(Exception):
    """Falha previsível de validação: vira mensagem pro usuário, não 500."""


PALAVRA_CONFIRMACAO_EXCLUSAO = "CONFIRMAR"


def exigir_confirmacao_exclusao(request):
    """Exige a confirmação escrita das exclusões permanentes.

    A comparação ignora caixa e espaços nas pontas: ``confirmar``,
    ``Confirmar`` e ``CONFIRMAR`` expressam a mesma intenção. A validação
    mora no servidor porque esconder/desabilitar o botão no navegador não
    protege uma chamada POST feita à mão.
    """
    recebido = (request.POST.get("confirmacao_exclusao") or "").strip()
    if recebido.casefold() != PALAVRA_CONFIRMACAO_EXCLUSAO.casefold():
        raise ErroDeFormulario(
            f"Digite {PALAVRA_CONFIRMACAO_EXCLUSAO} para autorizar a exclusão."
        )


def pede_json(request):
    """O painel envia por fetch; um POST sem JavaScript segue o fluxo normal."""
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.POST.get("resposta") == "json"
    )


def texto(request, campo, obrigatorio=False, rotulo=None, limite=None):
    valor = (request.POST.get(campo) or "").strip()

    if obrigatorio and not valor:
        raise ErroDeFormulario(f"Informe {rotulo or campo}.")

    if limite and len(valor) > limite:
        raise ErroDeFormulario(
            f"{rotulo or campo}: use no máximo {limite} caracteres."
        )

    return valor


def decimal_br(valor, rotulo, obrigatorio=False, limite=None):
    """Aceita '1.234,56', '1234.56' e '1234' — é o que o teclado do
    celular e o copiar-colar da nota fiscal produzem na prática."""
    bruto = (valor or "").strip()

    if not bruto:
        if obrigatorio:
            raise ErroDeFormulario(f"Informe {rotulo}.")
        return None

    normalizado = (
        bruto
        .replace("R$", "")
        .replace(" ", "")
        .replace(" ", "")
    )

    if "," in normalizado:
        normalizado = normalizado.replace(".", "").replace(",", ".")
    elif normalizado.count(".") > 1:
        normalizado = normalizado.replace(".", "")

    try:
        numero = Decimal(normalizado)
    except (InvalidOperation, ValueError):
        raise ErroDeFormulario(f"{rotulo}: informe um número válido.")

    if numero < 0:
        raise ErroDeFormulario(f"{rotulo}: o valor não pode ser negativo.")

    if limite is not None and numero > limite:
        raise ErroDeFormulario(
            f"{rotulo}: o máximo permitido é {limite}."
        )

    return numero.quantize(Decimal("0.01"))


def inteiro(valor, rotulo, obrigatorio=False, minimo=0, maximo=None):
    bruto = (valor or "").strip()

    if not bruto:
        if obrigatorio:
            raise ErroDeFormulario(f"Informe {rotulo}.")
        return None

    try:
        numero = int(Decimal(bruto.replace(".", "").replace(",", ".")))
    except (InvalidOperation, ValueError):
        raise ErroDeFormulario(f"{rotulo}: informe um número inteiro.")

    if numero < minimo:
        raise ErroDeFormulario(f"{rotulo}: o mínimo é {minimo}.")

    if maximo is not None and numero > maximo:
        raise ErroDeFormulario(f"{rotulo}: o máximo é {maximo}.")

    return numero


def data(valor, rotulo):
    """Lê o valor de um <input type="date"> (sempre AAAA-MM-DD)."""
    bruto = (valor or "").strip()
    if not bruto:
        return None

    try:
        return timezone.datetime.strptime(bruto, "%Y-%m-%d").date()
    except ValueError:
        raise ErroDeFormulario(f"{rotulo}: informe uma data válida.")


def endereco_do_site(request=None):
    """Base http(s)://... do SITE PÚBLICO, visto de dentro do painel.

    O painel responde em interno.lazersport.com.br e a página do cliente
    mora no site principal. `request.build_absolute_uri` devolveria o
    endereço do subdomínio interno — um link que o cliente abre e leva na
    cara uma tela de login de equipe.

    Em produção a resposta é SITE_URL, que é o domínio publicado. Em
    desenvolvimento isso apontaria para o site no ar, o que atrapalha
    testar: ali o endereço é montado a partir do próprio host, só tirando
    o "interno." da frente, para continuar valendo em
    interno.localhost:8000 e em qualquer host alternativo.
    """
    from django.conf import settings

    if not settings.DEBUG:
        configurado = (getattr(settings, "SITE_URL", "") or "").strip()
        if configurado:
            if not configurado.startswith(("http://", "https://")):
                configurado = "https://" + configurado
            partes = urlsplit(configurado)
            host = partes.hostname or ""
            if host.startswith("interno."):
                host = host[len("interno."):]
            porta = f":{partes.port}" if partes.port else ""
            if host:
                return urlunsplit((
                    partes.scheme or "https",
                    host + porta,
                    partes.path.rstrip("/"),
                    "",
                    "",
                )).rstrip("/")

    if request is None:
        # Sem pedido não há host de onde partir. É o caso da própria página
        # do cliente, que precisa do endereço canônico para o cartão de
        # pré-visualização: quem chegou por lazersport.com.br e quem chegou
        # por www.lazersport.com.br têm de gerar o MESMO og:url, senão o
        # WhatsApp guarda dois cartões para a mesma proposta.
        return ""

    host = request.get_host()
    if host.startswith("interno."):
        host = host[len("interno."):]

    return f"{request.scheme}://{host}"
