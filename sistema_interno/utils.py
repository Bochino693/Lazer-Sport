"""Helpers de formulário do sistema interno."""

from decimal import Decimal, InvalidOperation

from django.utils import timezone


class ErroDeFormulario(Exception):
    """Falha previsível de validação: vira mensagem pro usuário, não 500."""


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
