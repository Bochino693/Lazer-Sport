"""Regras compartilhadas para identificar cadastros de cliente incompletos."""

from django.db.models import Q

#: As três partes que tiram um cadastro da lista de incompletos, na ordem
#: em que a folha do sino pergunta (seção 116). Os nomes são os que viajam
#: no JSON e nos testes: `contato`, `documento`, `endereco`.
PARTES = ("contato", "documento", "endereco")


def partes_incompletas():
    """(sem contato, sem documento válido, sem endereço), como consulta.

    Separadas para a central de avisos contar cada parte numa consulta só
    ("falta CPF/CNPJ em 12, endereço em 5") com a MESMA regra do total.
    """
    sem_contato = (
        (Q(telefone="") | Q(telefone__isnull=True))
        & (Q(email="") | Q(email__isnull=True))
    )
    sem_documento_valido = (
        Q(documento="")
        | Q(documento__isnull=True)
        | Q(documento_valido=False)
    )
    sem_endereco = Q(enderecos__isnull=True)
    return sem_contato, sem_documento_valido, sem_endereco


def filtro_incompletos():
    """Campos mínimos para o cadastro servir ao comercial e à operação."""
    sem_contato, sem_documento_valido, sem_endereco = partes_incompletas()
    return sem_contato | sem_documento_valido | sem_endereco


def faltas_do_cliente(cliente):
    """O que tira ESTE cliente da lista de incompletos, pela regra da contagem.

    É `filtro_incompletos` escrito para um cadastro já carregado: a folha
    do sino mostra só estas partes, e um cliente sem nenhuma delas saiu do
    número -- ao contrário de `pendencias_do_cliente`, que também lembra o
    "WhatsApp não confirmado", que não conta como incompleto.
    """
    faltas = []
    if not (cliente.telefone or cliente.email):
        faltas.append("contato")
    if not cliente.documento or not cliente.documento_valido:
        faltas.append("documento")
    if not cliente.endereco_principal:
        faltas.append("endereco")
    return faltas


def pendencias_do_cliente(cliente):
    """Rótulos curtos para orientar a correção diretamente na lista."""
    pendencias = []
    if not (cliente.telefone or cliente.email):
        pendencias.append("contato")
    if not cliente.documento:
        pendencias.append("CPF/CNPJ")
    elif not cliente.documento_valido:
        pendencias.append("CPF/CNPJ inválido")
    if (
        cliente.telefone
        and cliente.canal_telefone == cliente.CanalTelefone.NAO_CONFIRMADO
    ):
        pendencias.append("WhatsApp não confirmado")
    if not cliente.endereco_principal:
        pendencias.append("endereço")
    return pendencias
