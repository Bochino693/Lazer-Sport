"""Um e-mail identifica uma pessoa DENTRO do cadastro dela -- e só dele.

CLIENTE E CONTA DE ACESSO SÃO OBJETOS DIFERENTES.

A regra anterior tratava os dois como a mesma pessoa: quem já tinha
login não podia ser cadastrado como cliente com o mesmo endereço, e o
contrário também. Na prática isso proibia o caso mais comum da casa --
o dono do buffet acompanha as propostas pelo site (conta) e é ele mesmo
quem recebe o orçamento (cliente). Repetir o endereço ali é o normal,
não a duplicidade, e nenhum caminho do sistema junta um cadastro ao
outro pelo e-mail: a trava só obrigava a inventar um segundo endereço
para a mesma pessoa.

O que continua valendo -- e é o que de fato dá problema:

  * dois CLIENTES com o mesmo contato são cadastro duplicado, e a
    proposta acaba indo para o registro errado;
  * duas CONTAS com o mesmo endereço deixam a recuperação de senha sem
    saber qual delas atender.

Os gatilhos do banco (migração 0045) guardam a mesma regra, por escopo:
aqui é a mensagem que a pessoa lê, lá é a garantia contra duas
gravações ao mesmo tempo.
"""
from django.contrib.auth import get_user_model
from allauth.account.models import EmailAddress


def _normalizar(email):
    return (email or "").strip().lower()


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


def validar_email_de_usuario(email, *, usuario_id=None):
    """Recusa o e-mail que já está em OUTRA conta de acesso.

    Os aliases do allauth entram na conta: são endereços da mesma
    pessoa, e é por qualquer um deles que ela entra no sistema.
    """
    from sistema_interno.utils import ErroDeFormulario

    email = _normalizar(email)
    if not email:
        return email

    consultas = (
        get_user_model().objects.filter(email__iexact=email).exclude(pk=usuario_id),
        EmailAddress.objects.filter(email__iexact=email).exclude(user_id=usuario_id),
    )
    if any(consulta.exists() for consulta in consultas):
        raise ErroDeFormulario(
            "Este e-mail já está em outra conta de acesso. Entre com ela ou "
            "use a recuperação de senha."
        )
    return email
