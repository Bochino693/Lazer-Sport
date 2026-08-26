"""Cadastro de cliente: uma regra só para o painel inteiro.

A mesma pessoa é cadastrada de dois lugares -- da aba Clientes, com calma,
e de dentro do orçamento, com o cliente esperando no telefone. Se cada
tela tivesse a sua validação, o cadastro rápido nasceria diferente do
completo e a lista viraria uma colcha de retalhos. Então as duas passam
por aqui.
"""

from __future__ import annotations

import re

from django.db.models import Q

from .models import Cliente, EnderecoCliente
from .utils import ErroDeFormulario, texto


def so_digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor or "")


def normalizar_tipo(valor: str) -> str:
    tipo = (valor or "").strip().lower()
    if tipo not in Cliente.Tipo.values:
        return Cliente.Tipo.PESSOA
    return tipo


def salvar_cliente(request, cliente: Cliente | None = None) -> Cliente:
    """Grava um cliente novo ou atualiza o que veio.

    O que é exigido: nome, e alguma forma de falar com a pessoa. Cadastro
    sem telefone nem e-mail é cadastro que ninguém consegue usar depois --
    e é o tipo de linha morta que enche a lista e some com a busca.
    """
    novo = cliente is None
    cliente = cliente or Cliente()

    nome = texto(
        request, "nome_cliente",
        obrigatorio=True, rotulo="o nome do cliente", limite=90,
    )

    telefone = texto(request, "telefone", limite=24)
    email = texto(request, "email", limite=150)

    if not telefone and not email:
        raise ErroDeFormulario(
            "Informe ao menos um contato: telefone/WhatsApp ou e-mail."
        )

    if telefone and len(so_digitos(telefone)) < 10:
        raise ErroDeFormulario(
            "Telefone incompleto: informe DDD e número, como (11) 99999-9999."
        )

    if email and "@" not in email:
        raise ErroDeFormulario("E-mail inválido.")

    # Nome repetido quase sempre é a mesma pessoa cadastrada duas vezes,
    # e cada duplicata parte o histórico dela em dois.
    repetido = Cliente.objects.filter(nome_cliente__iexact=nome)
    if not novo:
        repetido = repetido.exclude(pk=cliente.pk)
    if repetido.exists():
        raise ErroDeFormulario(
            f"Já existe um cliente chamado “{nome}”. Procure na lista antes "
            "de criar outro."
        )

    cliente.nome_cliente = nome
    cliente.telefone = telefone
    cliente.email = email
    cliente.tipo = normalizar_tipo(request.POST.get("tipo"))
    cliente.documento = texto(request, "documento", limite=20)
    cliente.observacoes = texto(request, "observacoes")

    cliente.parceiro = _buffet_escolhido(request, cliente)
    cliente.estabelecimento_id = _estabelecimento_escolhido(request)

    cliente.save()
    return cliente


def _buffet_escolhido(request, cliente: Cliente):
    """O buffet responsável, quando faz sentido.

    Buffet não pertence a buffet, e ninguém é o próprio parceiro: as duas
    situações criam um vínculo que nenhuma tela sabe desenhar.
    """
    bruto = (request.POST.get("parceiro") or "").strip()
    if not bruto.isdigit():
        return None

    if cliente.tipo == Cliente.Tipo.BUFFET:
        return None

    parceiro = Cliente.objects.filter(
        pk=int(bruto),
        tipo=Cliente.Tipo.BUFFET,
    ).first()

    if parceiro and cliente.pk and parceiro.pk == cliente.pk:
        return None

    return parceiro


def _estabelecimento_escolhido(request):
    bruto = (request.POST.get("estabelecimento") or "").strip()
    return int(bruto) if bruto.isdigit() else None


def salvar_endereco(request, cliente: Cliente) -> EnderecoCliente | None:
    """Guarda o endereço principal, quando a tela mandou algum campo.

    Endereço é opcional de propósito: orçamento de balcão fecha sem ele, e
    exigir CEP na pressa faz a pessoa inventar número para conseguir salvar.
    """
    campos = {
        "cep": texto(request, "cep", limite=18),
        "endereco": texto(request, "endereco", limite=120),
        "numero": texto(request, "numero", limite=5),
        "bairro": texto(request, "bairro", limite=50),
        "cidade": texto(request, "cidade", limite=25),
        "estado": texto(request, "estado", limite=20),
    }

    if not any(campos.values()):
        return None

    if not campos["endereco"] or not campos["cidade"]:
        raise ErroDeFormulario(
            "Para guardar o endereço, informe pelo menos a rua e a cidade."
        )

    endereco = cliente.enderecos.first() or EnderecoCliente(cliente=cliente)
    for campo, valor in campos.items():
        setattr(endereco, campo, valor)
    endereco.save()

    return endereco


def opcao_de_busca(cliente: Cliente) -> dict:
    """Formato que o campo de busca do painel entende."""
    detalhe = cliente.get_tipo_display()
    if cliente.parceiro_id and cliente.parceiro:
        detalhe += f" · {cliente.parceiro.nome_cliente}"
    elif cliente.telefone:
        detalhe += f" · {cliente.telefone}"

    return {
        "valor": str(cliente.id),
        "rotulo": cliente.nome_cliente,
        "detalhe": detalhe,
        "grupo": (
            "Parceiros (buffets)"
            if cliente.tipo == Cliente.Tipo.BUFFET
            else "Clientes"
        ),
        "whatsapp": cliente.telefone or "",
        "email": cliente.email or "",
    }


def buscar(consulta, termo: str):
    """Filtro de lista: nome, contato e documento, tudo em um campo só."""
    termo = (termo or "").strip()
    if not termo:
        return consulta

    filtro = (
        Q(nome_cliente__icontains=termo)
        | Q(telefone__icontains=termo)
        | Q(email__icontains=termo)
        | Q(documento__icontains=termo)
        | Q(parceiro__nome_cliente__icontains=termo)
    )

    # A busca por número casa com a cópia sem máscara: "11977776655",
    # "977776655" e "(11) 97777-6655" chegam ao mesmo cadastro.
    digitos = so_digitos(termo)
    if digitos:
        filtro |= Q(telefone_digitos__contains=digitos)

    return consulta.filter(filtro).distinct()
