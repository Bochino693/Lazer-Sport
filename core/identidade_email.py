"""Um e-mail identifica uma pessoa DENTRO do cadastro dela -- e só dele.

CLIENTE E CONTA DE ACESSO SÃO OBJETOS DIFERENTES.

O mesmo endereço pode estar numa conta de acesso (login do site/painel) E
num cadastro comercial de cliente: o dono do buffet acompanha as propostas
pelo site (conta) e é ele mesmo quem recebe o orçamento (cliente). Nenhum
caminho do sistema junta um ao outro pelo e-mail.

O que nunca pode:

  * dois CLIENTES com o mesmo contato (cadastro duplicado: a proposta
    acaba indo para o registro errado);
  * duas CONTAS com o mesmo endereço -- principal ou endereço extra do
    allauth, sem diferença de maiúsculas, espaços ou variantes Unicode.
    Essa regra mora agora no app `contas` (contas/emails.py), com a
    guarda no pre_save e o índice único do banco; este módulo continua
    existindo para quem já o chamava, com a exceção que essas telas tratam
    (ErroDeFormulario).

Os gatilhos do banco (migração sistema_interno/0047) guardam a regra por
escopo; o índice da migração contas/0003, a das contas.
"""
from contas.emails import normalizar_email


def _normalizar(email):
    return normalizar_email(email)


def validar_email_de_cliente(email, *, cliente_id=None):
    """Recusa o e-mail que já está em OUTRO cadastro de cliente."""
    from sistema_interno.models import Cliente
    from sistema_interno.utils import ErroDeFormulario

    email = _normalizar(email)
    if not email:
        return email

    if Cliente.objects.filter(email__iexact=email).exclude(pk=cliente_id).exists():
        raise ErroDeFormulario(
            "Este e-mail já está em outro cadastro de cliente. Abra o "
            "registro existente em vez de criar a mesma pessoa duas vezes."
        )
    return email


def validar_email_de_usuario(email, *, usuario_id=None, pela_equipe=True):
    """Recusa o e-mail que já está em OUTRA conta de acesso (ErroDeFormulario).

    Os aliases do allauth entram na conta: são endereços da mesma pessoa, e
    é por qualquer um deles que ela entra no sistema. Quem chama daqui é o
    painel (a equipe), então os endereços da empresa são aceitos.
    """
    from django.contrib.auth import get_user_model
    from django.core.exceptions import ValidationError

    from contas.emails import mensagem_de, validar_email_de_conta
    from sistema_interno.utils import ErroDeFormulario

    email = _normalizar(email)
    if not email:
        return email
    usuario = get_user_model()(pk=usuario_id) if usuario_id else None
    try:
        return validar_email_de_conta(email, usuario=usuario, pela_equipe=pela_equipe)
    except ValidationError as exc:
        if getattr(exc, "code", "") == "em_uso":
            raise ErroDeFormulario(
                "Este e-mail já está em outra conta de acesso. Entre com ela ou "
                "use a recuperação de senha."
            ) from exc
        raise ErroDeFormulario(mensagem_de(exc)) from exc
