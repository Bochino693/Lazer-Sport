"""Cadastro de cliente: uma regra só para o painel inteiro.

A mesma pessoa é cadastrada de dois lugares -- da aba Clientes, com calma,
e de dentro do orçamento, com o cliente esperando no telefone. Se cada
tela tivesse a sua validação, o cadastro rápido nasceria diferente do
completo e a lista viraria uma colcha de retalhos. Então as duas passam
por aqui.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Q, Exists, OuterRef

from core.models import Estabelecimentos
from core.utils import buscar_coordenadas_cep_rapido, buscar_dados_cep

from .models import Cliente, EnderecoCliente
from .utils import ErroDeFormulario, texto
from .validacoes import (
    chave_documento,
    documento_valido,
    somente_digitos,
    telefone_valido,
    tipo_documento,
)


def so_digitos(valor: str) -> str:
    return somente_digitos(valor)


def normalizar_tipo(valor: str) -> str:
    tipo = (valor or "").strip().lower()
    # Nomes antigos ainda chegam de aba aberta antes da mudança e de link
    # guardado no favorito. Traduzir é mais barato que perder o cadastro.
    tipo = {"pessoa": Cliente.Tipo.RESIDENCIAL, "empresa": Cliente.Tipo.COMERCIAL}.get(
        tipo, tipo
    )
    if tipo not in Cliente.Tipo.values:
        return Cliente.Tipo.RESIDENCIAL
    return tipo


def marcado(request, campo: str) -> bool:
    """Caixa marcada no formulário, aceitando as três formas que chegam."""
    return (request.POST.get(campo) or "").strip().lower() in ("1", "on", "true")


@transaction.atomic
def salvar_cliente(request, cliente: Cliente | None = None) -> Cliente:
    """Grava um cliente novo ou atualiza o que veio.

    O que é exigido: nome, e alguma forma de falar com a pessoa. Cadastro
    sem telefone nem e-mail é cadastro que ninguém consegue usar depois --
    e é o tipo de linha morta que enche a lista e some com a busca.
    """
    novo = cliente is None
    cliente = Cliente.objects.select_for_update().get(pk=cliente.pk) if cliente and cliente.pk else Cliente()

    nome = texto(
        request, "nome_cliente",
        obrigatorio=True, rotulo="o nome do cliente", limite=90,
    )

    telefone = texto(request, "telefone", limite=24)
    email = texto(request, "email", limite=150).strip().lower()

    if not telefone and not email:
        raise ErroDeFormulario(
            "Informe ao menos um contato: telefone/WhatsApp ou e-mail."
        )

    if telefone and not telefone_valido(telefone):
        raise ErroDeFormulario(
            "Telefone incompleto: informe DDD e número, como (11) 99999-9999."
        )

    if email:
        try:
            validate_email(email)
        except ValidationError as exc:
            raise ErroDeFormulario("E-mail inválido.") from exc

    documento = texto(request, "documento", limite=20)
    if documento and not documento_valido(documento):
        raise ErroDeFormulario(
            f"{tipo_documento(documento)} inválido: confira os caracteres e "
            "os dígitos verificadores."
        )

    chave = chave_documento(documento)
    if chave:
        mesmo_documento = Cliente.objects.filter(documento_chave=chave)
        if not novo:
            mesmo_documento = mesmo_documento.exclude(pk=cliente.pk)
        if mesmo_documento.exists():
            raise ErroDeFormulario(
                "Este CPF/CNPJ já está ligado a outro cliente. Abra o cadastro "
                "existente para não dividir o histórico."
            )

    canal_informado = "canal_telefone" in request.POST
    canal = (request.POST.get("canal_telefone") or "").strip()
    if canal not in Cliente.CanalTelefone.values:
        canal = (
            cliente.canal_telefone
            if cliente.pk and cliente.canal_telefone in Cliente.CanalTelefone.values
            # Aba antiga, aberta antes da atualização: o campo anterior se
            # chamava explicitamente "Telefone / WhatsApp". Preservar essa
            # leitura evita perder um cadastro no meio do atendimento.
            else Cliente.CanalTelefone.WHATSAPP
        )
    if not canal_informado and telefone:
        canal = Cliente.CanalTelefone.WHATSAPP
    if not telefone:
        canal = Cliente.CanalTelefone.NAO_CONFIRMADO
    elif (
        canal == Cliente.CanalTelefone.NAO_CONFIRMADO
        and not marcado(request, "confirmar_telefone_sem_whatsapp")
    ):
        raise ErroDeFormulario(
            "Confirme se este número tem WhatsApp. Se ainda não souber, marque "
            "“salvar mesmo sem confirmar”; o sistema não o usará como WhatsApp."
        )

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

    from core.identidade_email import validar_email_unico
    validar_email_unico(email, cliente_id=cliente.pk)
    if "nome_estabelecimento" in request.POST:
        cliente.nome_estabelecimento = texto(request, "nome_estabelecimento", limite=150)
    if "cnpj_estabelecimento" in request.POST:
        cnpj = somente_digitos(request.POST.get("cnpj_estabelecimento", ""))
        if cnpj and (len(cnpj) != 14 or not documento_valido(cnpj)):
            raise ErroDeFormulario("CNPJ do estabelecimento inválido.")
        if cnpj and Cliente.objects.filter(Q(cnpj_estabelecimento=cnpj) | Q(documento_chave=cnpj)).exclude(pk=cliente.pk).exists():
            raise ErroDeFormulario("Este estabelecimento já pertence a outro cadastro de cliente.")
        cliente.cnpj_estabelecimento = cnpj

    cliente.nome_cliente = nome
    cliente.telefone = telefone
    cliente.canal_telefone = canal
    cliente.email = email
    cliente.tipo = normalizar_tipo(request.POST.get("tipo"))
    cliente.documento = documento
    cliente.observacoes = texto(request, "observacoes")

    cliente.parceiro = _buffet_escolhido(request, cliente)
    # O vínculo antigo com core.Estabelecimentos é legado, não é o negócio do cliente.
    # Preservá-lo evita alterar os parceiros públicos já existentes.

    # ------------------------------------------------------------------
    # O que o site mostra deste cliente.
    #
    # Só é lido quando a tela mandou o campo: o cadastro rápido, feito de
    # dentro do orçamento, não tem essa parte do formulário, e ausência ali
    # não pode significar "despublique o cliente do mapa".
    # ------------------------------------------------------------------
    if "publicar_no_mapa" in request.POST:
        cliente.publicar_no_mapa = marcado(request, "publicar_no_mapa")
    if "site_cliente" in request.POST:
        cliente.site_cliente = texto(request, "site_cliente", limite=200)
    if "ativo" in request.POST:
        cliente.ativo = marcado(request, "ativo")

    logo = request.FILES.get("logo")
    if logo:
        from django import forms
        if logo.size > 5 * 1024 * 1024:
            raise ErroDeFormulario("A logo deve ter até 5 MB.")
        try:
            logo = forms.ImageField().clean(logo)
        except ValidationError as exc:
            raise ErroDeFormulario("A logo precisa ser uma imagem válida.") from exc
        cliente.logo = logo
    elif marcado(request, "remover_logo"):
        cliente.logo = None

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


def _estabelecimento_escolhido(request, cliente):
    bruto = (request.POST.get("estabelecimento") or "").strip()
    if not bruto.isdigit():
        return None
    estabelecimento_id = int(bruto)
    if not Estabelecimentos.objects.filter(pk=estabelecimento_id).exists():
        raise ErroDeFormulario(
            "Esse parceiro do site não existe mais. Atualize a tela e escolha outro."
        )
    ocupado = Cliente.objects.filter(estabelecimento_id=estabelecimento_id)
    if cliente.pk:
        ocupado = ocupado.exclude(pk=cliente.pk)
    if ocupado.exists():
        raise ErroDeFormulario(
            "Esse parceiro do site já está ligado a outro buffet interno."
        )
    return estabelecimento_id


def completar_cadastro(request, cliente: Cliente) -> Cliente:
    """Preenche SÓ o que estava faltando, sem tocar no resto.

    `salvar_cliente` lê o formulário inteiro: é o certo para a janela de
    edição, que mostra o cadastro todo. Aqui não serve. A janela de
    completar mostra apenas os campos vazios, então um `salvar_cliente`
    apagaria o telefone de quem só veio informar o CPF -- o campo não
    apareceu na tela, chegaria vazio, e vazio venceria o que estava
    guardado.

    Por isso cada campo aqui é opcional e só é gravado quando veio com
    conteúdo. As regras de validade são as mesmas da edição: um documento
    inválido não fica menos inválido por ter entrado por outra porta.
    """
    telefone = texto(request, "telefone", limite=24)
    email = texto(request, "email", limite=150).strip().lower()
    documento = texto(request, "documento", limite=20)

    if telefone:
        if not telefone_valido(telefone):
            raise ErroDeFormulario(
                "Telefone incompleto: informe DDD e número, como (11) 99999-9999."
            )
        cliente.telefone = telefone
        canal = (request.POST.get("canal_telefone") or "").strip()
        if canal in Cliente.CanalTelefone.values:
            cliente.canal_telefone = canal
        elif marcado(request, "canal_telefone_perguntado"):
            # A JANELA PERGUNTOU E A CAIXA VOLTOU DESMARCADA.
            #
            # Caixa desmarcada não viaja no POST, então sem este marcador
            # "sem resposta" e "não perguntamos" chegariam iguais -- e
            # "WhatsApp não confirmado" seria uma pendência que ninguém
            # conseguiria resolver, porque desmarcar não valia como
            # confirmação.
            cliente.canal_telefone = Cliente.CanalTelefone.WHATSAPP

    if email:
        try:
            validate_email(email)
        except ValidationError as exc:
            raise ErroDeFormulario("E-mail inválido.") from exc
        from core.identidade_email import validar_email_unico
        validar_email_unico(email, cliente_id=cliente.pk)
        cliente.email = email

    if documento:
        if not documento_valido(documento):
            raise ErroDeFormulario(
                f"{tipo_documento(documento)} inválido: confira os caracteres "
                "e os dígitos verificadores."
            )
        chave = chave_documento(documento)
        if chave and Cliente.objects.filter(
            documento_chave=chave
        ).exclude(pk=cliente.pk).exists():
            raise ErroDeFormulario(
                "Este CPF/CNPJ já está ligado a outro cliente. Abra o "
                "cadastro existente para não dividir o histórico."
            )
        cliente.documento = documento

    if not cliente.telefone and not cliente.email:
        raise ErroDeFormulario(
            "Informe ao menos um contato: telefone/WhatsApp ou e-mail."
        )

    cliente.save()
    return cliente


@transaction.atomic
def salvar_endereco(request, cliente: Cliente) -> EnderecoCliente | None:
    """Guarda o endereço do estabelecimento, quando a tela mandou algum campo.

    É UM ENDEREÇO SÓ, e é ele que serve para tudo: entrega, montagem e o
    alfinete no mapa do site. Ter um "endereço do mapa" separado era
    exatamente o que fazia a vitrine mostrar a rua antiga enquanto a
    proposta saía com a nova.

    Endereço é opcional de propósito: orçamento de balcão fecha sem ele, e
    exigir CEP na pressa faz a pessoa inventar número para conseguir salvar.
    """
    campos = {
        "cep": texto(request, "cep", limite=18),
        "endereco": texto(request, "endereco", limite=120),
        "numero": texto(request, "numero", limite=10),
        "complemento": texto(request, "complemento", limite=60),
        "bairro": texto(request, "bairro", limite=50),
        "cidade": texto(request, "cidade", limite=60),
        "estado": texto(request, "estado", limite=20),
        "pais": texto(request, "pais", limite=60) or "Brasil",
    }
    # "Brasil" é o padrão do campo; sozinho, não é sinal de que alguém
    # preencheu endereço nenhum.
    tem_algum = any(v for k, v in campos.items() if k != "pais")

    if not tem_algum:
        return None

    # O CEP digitado já resolve rua, bairro, cidade e UF no servidor. O
    # navegador usa a mesma consulta para preencher a tela imediatamente,
    # mas repetir a regra aqui é indispensável: um celular pode perder a
    # conexão depois de digitar o CEP e antes de enviar o formulário.
    # buscar_dados_cep tem cache por processo, portanto a segunda leitura
    # normalmente não abre outra conexão com o ViaCEP.
    if campos["cep"] and not all(
        campos[chave] for chave in ("endereco", "bairro", "cidade", "estado")
    ):
        dados_cep = buscar_dados_cep(campos["cep"])
        if dados_cep:
            campos["cep"] = dados_cep["cep"]
            campos["endereco"] = (campos["endereco"] or dados_cep["rua"])[:120]
            campos["bairro"] = (campos["bairro"] or dados_cep["bairro"])[:50]
            campos["cidade"] = (campos["cidade"] or dados_cep["cidade"])[:60]
            campos["estado"] = (campos["estado"] or dados_cep["estado"])[:20]

    if not campos["endereco"] or not campos["cidade"]:
        raise ErroDeFormulario(
            "Para guardar o endereço, informe pelo menos a rua e a cidade."
        )

    Cliente.objects.select_for_update().get(pk=cliente.pk)
    endereco = cliente.enderecos.order_by("id").first() or EnderecoCliente(cliente=cliente)
    endereco_anterior = (
        endereco.cep,
        endereco.endereco,
        endereco.numero,
        endereco.bairro,
        endereco.cidade,
        endereco.estado,
        endereco.pais,
    )
    for campo, valor in campos.items():
        setattr(endereco, campo, valor)

    latitude = (request.POST.get("latitude") or "").strip().replace(",", ".")
    longitude = (request.POST.get("longitude") or "").strip().replace(",", ".")
    recebeu_coordenadas = "latitude" in request.POST or "longitude" in request.POST
    if bool(latitude) != bool(longitude):
        raise ErroDeFormulario("Informe latitude e longitude juntas.")
    if latitude and longitude:
        try:
            latitude_decimal = Decimal(latitude)
            longitude_decimal = Decimal(longitude)
        except InvalidOperation as exc:
            raise ErroDeFormulario("As coordenadas do endereço são inválidas.") from exc
        if not latitude_decimal.is_finite() or not longitude_decimal.is_finite():
            raise ErroDeFormulario("As coordenadas do endereço são inválidas.")
        if not (-90 <= latitude_decimal <= 90 and -180 <= longitude_decimal <= 180):
            raise ErroDeFormulario("As coordenadas do endereço estão fora da faixa válida.")
        endereco.latitude = latitude_decimal
        endereco.longitude = longitude_decimal
        endereco.precisao = EnderecoCliente.Precisao.MANUAL
    elif recebeu_coordenadas or endereco_anterior != (
        campos["cep"], campos["endereco"], campos["numero"],
        campos["bairro"], campos["cidade"], campos["estado"], campos["pais"],
    ):
        # Um novo CEP sem coordenada não pode herdar o ponto do endereço
        # anterior. Ele permanece pendente até uma fonte rápida ou uma
        # pessoa informar o local correto.
        endereco.latitude = None
        endereco.longitude = None
        endereco.precisao = ""
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

    latitude, longitude = buscar_coordenadas_cep_rapido(limpo)
    dados["latitude"] = latitude
    dados["longitude"] = longitude
    return dados


def publicar_no_mapa(cliente: Cliente):
    """Põe no mapa do site o cliente de uma proposta aprovada.

    Antes esta função COPIAVA o cadastro para uma segunda tabela, a do
    site, e o trabalho todo era manter as duas cópias parecidas. Não há
    mais duas: publicar virou ligar uma chave no próprio cliente.

    Buffets ficam de fora. Eles já têm um paralelo próprio na área
    pública -- ``Cliente.estabelecimento`` aponta para o parceiro exibido
    em "Nossos Parceiros" --, e um alfinete de cliente para o mesmo buffet
    o mostraria duas vezes no site.

    Sem endereço utilizável não há o que desenhar, e marcar assim mesmo só
    encheria a lista de "no mapa" de cadastros que o mapa ignora.
    """
    if not cliente:
        return None

    endereco = cliente.endereco_principal
    if not endereco or not (endereco.cep or endereco.cidade):
        return None

    return endereco


def opcao_de_busca(cliente: Cliente) -> dict:
    """Formato que o campo de busca do painel entende."""
    detalhe = cliente.get_tipo_display()
    if cliente.parceiro_id and cliente.parceiro:
        detalhe += f" · {cliente.parceiro.nome_cliente}"
    elif cliente.telefone:
        detalhe += f" · {cliente.telefone}"
    if cliente.nome_estabelecimento:
        detalhe += f" · {cliente.nome_estabelecimento}"

    endereco = cliente.endereco_principal

    return {
        "valor": str(cliente.id),
        "rotulo": cliente.nome_cliente,
        "detalhe": detalhe,
        "grupo": (
            "Parceiros (buffets)"
            if cliente.tipo == Cliente.Tipo.BUFFET
            else "Clientes"
        ),
        "whatsapp": (
            cliente.telefone
            if cliente.canal_telefone == Cliente.CanalTelefone.WHATSAPP
            else ""
        ),
        "telefone": cliente.telefone or "",
        "canal_telefone": cliente.canal_telefone,
        "email": cliente.email or "",
        "documento": cliente.documento or "",
        "tipo": cliente.tipo,
        "endereco": (
            {
                "cep": endereco.cep or "",
                "rua": endereco.endereco or "",
                "numero": endereco.numero or "",
                "bairro": endereco.bairro or "",
                "cidade": endereco.cidade or "",
                "estado": endereco.estado or "",
                "latitude": str(endereco.latitude or ""),
                "longitude": str(endereco.longitude or ""),
            }
            if endereco else None
        ),
    }


def buscar(consulta, termo: str):
    """Filtro de lista: nome, contato e documento, tudo em um campo só."""
    termo = (termo or "").strip()
    if not termo:
        return consulta

    filtro = (
        Q(nome_cliente__icontains=termo)
        | Q(nome_estabelecimento__icontains=termo)
        | Q(cnpj_estabelecimento__icontains=termo)
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


def com_publicacao_mapa(consulta=None):
    from .models import Orcamento
    consulta = consulta if consulta is not None else Cliente.objects.all()
    return consulta.annotate(_proposta_mapa=Exists(Orcamento.objects.filter(
        cliente_id=OuterRef("pk"),
        status__in=("aguardando_resposta", "em_negociacao", "aprovado"),
    )))
