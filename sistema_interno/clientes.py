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

from core.models import Clientes as ClienteMapa
from core.utils import buscar_dados_cep

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
    cliente.estabelecimento_id = (
        _estabelecimento_escolhido(request)
        if cliente.tipo == Cliente.Tipo.BUFFET else None
    )
    if "cliente_mapa" in request.POST:
        cliente.cliente_mapa_id = _cliente_mapa_escolhido(request, cliente)

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


def _cliente_mapa_escolhido(request, cliente: Cliente):
    if cliente.tipo == Cliente.Tipo.BUFFET:
        return None

    bruto = (request.POST.get("cliente_mapa") or "").strip()
    if not bruto.isdigit():
        return None

    mapa = ClienteMapa.objects.filter(pk=int(bruto)).first()
    if not mapa:
        return None

    ocupado = Cliente.objects.filter(cliente_mapa=mapa)
    if cliente.pk:
        ocupado = ocupado.exclude(pk=cliente.pk)
    if ocupado.exists():
        raise ErroDeFormulario(
            "Esse cliente do mapa já está ligado a outro cadastro interno."
        )
    return mapa.pk


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

    # O CEP digitado já resolve rua, bairro, cidade e UF no servidor. O
    # navegador usa a mesma consulta para preencher a tela imediatamente,
    # mas repetir a regra aqui é indispensável: um celular pode perder a
    # conexão depois de digitar o CEP e antes de enviar o formulário.
    # buscar_dados_cep tem cache por processo, portanto a segunda leitura
    # normalmente não abre outra conexão com o ViaCEP.
    if campos["cep"] and not all(
        campos[chave] for chave in ("endereco", "cidade", "estado")
    ):
        dados_cep = buscar_dados_cep(campos["cep"])
        if dados_cep:
            campos["cep"] = dados_cep["cep"]
            campos["endereco"] = (campos["endereco"] or dados_cep["rua"])[:120]
            campos["bairro"] = (campos["bairro"] or dados_cep["bairro"])[:50]
            campos["cidade"] = (campos["cidade"] or dados_cep["cidade"])[:25]
            campos["estado"] = (campos["estado"] or dados_cep["estado"])[:20]

    if not campos["endereco"] or not campos["cidade"]:
        raise ErroDeFormulario(
            "Para guardar o endereço, informe pelo menos a rua e a cidade."
        )

    endereco = cliente.enderecos.first() or EnderecoCliente(cliente=cliente)
    for campo, valor in campos.items():
        setattr(endereco, campo, valor)
    endereco.save()

    return endereco


def consultar_cep(cep: str) -> dict:
    """Valida e consulta um CEP para os modais do painel."""
    limpo = so_digitos(cep)
    if len(limpo) != 8:
        raise ErroDeFormulario("Informe um CEP com 8 números.")

    dados = buscar_dados_cep(limpo)
    if not dados:
        raise ErroDeFormulario(
            "Não encontrei esse CEP agora. Confira os números ou preencha o endereço manualmente."
        )

    return dados


def sincronizar_cliente_no_mapa(cliente: Cliente):
    """Publica no mapa o cliente de uma proposta aprovada.

    Buffets já possuem um paralelo próprio: ``Cliente.estabelecimento``
    aponta para o parceiro exibido na área pública. Criar também um pino de
    cliente para o mesmo buffet duplicaria a empresa no site.

    A relação OneToOne torna a operação idempotente: aprovar de novo ou
    editar o orçamento atualiza o mesmo pino, nunca cria cópias.
    """
    if not cliente or cliente.eh_buffet:
        return None

    endereco = cliente.endereco_principal
    if not endereco or not (endereco.cep or endereco.cidade):
        return None

    mapa = cliente.cliente_mapa or ClienteMapa()
    endereco_anterior = (
        mapa.cep,
        mapa.rua,
        mapa.numero,
        mapa.bairro,
        mapa.cidade,
        mapa.estado,
    )
    endereco_novo = (
        endereco.cep or None,
        endereco.endereco or None,
        endereco.numero or None,
        endereco.bairro or None,
        endereco.cidade or None,
        (endereco.estado or "")[:2].upper() or None,
    )

    mapa.descricao_cliente = cliente.nome_cliente
    (
        mapa.cep,
        mapa.rua,
        mapa.numero,
        mapa.bairro,
        mapa.cidade,
        mapa.estado,
    ) = endereco_novo
    mapa.pais = "Brasil"
    mapa.ativo = True
    mapa.exibir_no_mapa = True

    # Endereço alterado precisa de um novo ponto. Se o endereço interno já
    # tiver coordenadas confiáveis, elas são reaproveitadas e nenhuma
    # consulta de geocodificação é feita.
    if endereco_anterior != endereco_novo:
        mapa.latitude = endereco.latitude
        mapa.longitude = endereco.longitude
        mapa.precisao_local = "manual" if endereco.latitude and endereco.longitude else ""

    mapa.save()

    if cliente.cliente_mapa_id != mapa.pk:
        cliente.cliente_mapa = mapa
        cliente.save(update_fields=["cliente_mapa", "telefone_digitos", "atualizado"])

    return mapa


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
