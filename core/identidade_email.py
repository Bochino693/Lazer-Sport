"""Um endereço de e-mail identifica uma pessoa, independente do papel."""
from django.contrib.auth import get_user_model
from allauth.account.models import EmailAddress


def validar_email_unico(email, *, cliente_id=None, usuario_id=None):
    from sistema_interno.models import Cliente
    from sistema_interno.utils import ErroDeFormulario
    email = (email or "").strip().lower()
    if not email:
        return email
    consultas = (
        Cliente.objects.filter(email__iexact=email).exclude(pk=cliente_id),
        get_user_model().objects.filter(email__iexact=email).exclude(pk=usuario_id),
        EmailAddress.objects.filter(email__iexact=email).exclude(user_id=usuario_id),
    )
    if any(q.exists() for q in consultas):
        raise ErroDeFormulario(
            "Este e-mail já pertence a um cadastro. Abra o registro existente; "
            "não crie outra pessoa com o mesmo contato."
        )
    return email
