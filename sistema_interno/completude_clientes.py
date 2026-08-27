"""Regras compartilhadas para identificar cadastros de cliente incompletos."""

from django.db.models import Q


def filtro_incompletos():
    """Campos mínimos para o cadastro servir ao comercial e à operação."""
    sem_contato = (
        (Q(telefone="") | Q(telefone__isnull=True))
        & (Q(email="") | Q(email__isnull=True))
    )
    sem_documento = Q(documento="") | Q(documento__isnull=True)
    sem_endereco = Q(enderecos__isnull=True)
    return sem_contato | sem_documento | sem_endereco


def pendencias_do_cliente(cliente):
    """Rótulos curtos para orientar a correção diretamente na lista."""
    pendencias = []
    if not (cliente.telefone or cliente.email):
        pendencias.append("contato")
    if not cliente.documento:
        pendencias.append("CPF/CNPJ")
    if not cliente.endereco_principal:
        pendencias.append("endereço")
    return pendencias
