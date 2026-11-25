"""A folha que resolve o aviso ali mesmo (LEIA-ME-V10, seção 116).

O PEDIDO: "melhore as notificações, deixe modais para solucionar problemas
pequenos e afins". O sino dizia "Cadastros de clientes incompletos (19) --
toque para corrigir", e o toque levava à tela de Clientes, onde a pessoa
ainda tinha de achar cada um dos dezenove. "Proposta aprovada -- combine
data e montagem" levava à lista de Orçamentos, sem dizer qual nem onde se
combina a data.

Aqui se monta, para cada aviso que tem conserto pequeno, o que a folha
mostra: a lista do que falta (a MESMA consulta que deu o número do sino,
ver `avisos.consulta_do_aviso`) e, em cada linha, só as ações que já
existem nas telas -- e só as que a função de quem abriu pode fazer.

NADA AQUI GRAVA. A folha lê daqui e grava pelos endereços de sempre:

    clientes          clientes_inner, action=completar   (só o que falta)
                      consultar_cep_inner                (o CEP preenche)
    propostas         orcamentos_inner, action=enviar    (WhatsApp)
                      lembrar_cliente                    (e-mail)
                      orcamentos_inner, action=status    (recusada/expirada)
    aprovadas         prazo_producao                     (o prazo de entrega)
                      documento_assinatura_inner         (gerar o contrato)
                      documento_assinatura_link          (o link no WhatsApp)
    pedidos           andamento_pedido                   (a folha de sempre)

Cada um desses confere a permissão dele, como sempre conferiu. As flags
que vão no JSON (`acoes`) só decidem que botão APARECE: são calculadas
com as mesmas regras, para a folha não oferecer o que o servidor recusa.

PRIVACIDADE. O cliente incompleto viaja com o nome e com o que falta. O
CPF/CNPJ só vai quando o número guardado é justamente o que está errado
(para a pessoa corrigir em cima dele); endereço e contato não vão, porque
quem está na lista é quem NÃO os tem.
"""

from __future__ import annotations

from urllib.parse import urlencode

from django.core.exceptions import PermissionDenied
from django.db.models import Exists, OuterRef, Prefetch
from django.http import Http404
from django.urls import reverse
from django.utils import timezone

from .avisos import RESOLVIVEIS, consulta_do_aviso, mapa_de_negociacoes
from .completude_clientes import faltas_do_cliente, filtro_incompletos
from .models import Cliente, EnderecoCliente, EstoqueMaterial, Orcamento
from .permissoes import capacidades

URLCONF = "sistema_interno.urls"

#: Quantas linhas a folha desenha. Passando disso, ela diz "mostrando 30
#: de 45" e a tela continua sendo o caminho do resto -- uma folha de
#: celular com cem formulários não é um conserto pequeno.
LIMITE = 30

#: O título da folha e para onde "Abrir a tela" leva, por aviso.
TITULOS = {
    "clientes_incompletos": ("Completar cadastros", "bi-person-exclamation"),
    "orcamentos_aprovados": ("Propostas aprovadas", "bi-patch-check"),
    "orcamentos_em_aberto": ("Propostas em aberto", "bi-file-earmark-text"),
    "orcamentos_vencendo": ("Propostas a vencer", "bi-hourglass-split"),
    "orcamentos_vencidos": ("Propostas vencidas", "bi-calendar-x"),
    "orcamentos_recusados": ("Propostas recusadas", "bi-emoji-frown"),
    "pedidos": ("Pedidos em aberto", "bi-box2-heart"),
    "estoque": ("Material para repor", "bi-box-seam"),
}

#: O que a folha diz embaixo do título, antes da lista.
INSTRUCOES = {
    "clientes_incompletos": (
        "Cada cliente pede só o que falta. Salve um por um: quem fica "
        "completo sai da lista na hora."
    ),
    "orcamentos_aprovados": (
        "Combine o prazo de entrega (ele vai para o contrato) e mande o "
        "contrato para o cliente assinar."
    ),
    "orcamentos_em_aberto": (
        "Reenvie pelo WhatsApp, lembre por e-mail ou registre a resposta "
        "que o cliente deu por telefone."
    ),
    "orcamentos_vencendo": (
        "Ainda dá tempo: lembre o cliente antes de a proposta vencer."
    ),
    "orcamentos_vencidos": (
        "Passou da validade. Marque como expirada, registre a recusa ou "
        "abra a proposta para fazer a versão nova com o preço de hoje."
    ),
    "orcamentos_recusados": (
        "O motivo de cada cliente, para a versão nova já nascer corrigida."
    ),
    "pedidos": (
        "Toque na situação do pedido para levá-lo ao próximo passo."
    ),
    "estoque": (
        "O que está no mínimo ou abaixo dele. A compra entra pela tela do "
        "estoque ou pela entrada de nota."
    ),
}


def _url(nome, *args, **query):
    endereco = reverse(nome, args=args, urlconf=URLCONF)
    if query:
        endereco += "?" + urlencode(query)
    return endereco


def _data(valor):
    if not valor:
        return ""
    if hasattr(valor, "tzinfo") and getattr(valor, "hour", None) is not None:
        valor = timezone.localtime(valor)
    return valor.strftime("%d/%m/%Y")


def _moeda(valor):
    from .views_gestao import moeda_br

    return f"R$ {moeda_br(valor)}"


def _plural(numero, um, varios):
    return f"{numero} {um if numero == 1 else varios}"


# ======================================================================
# A ENTRADA
# ======================================================================
def montar(user, chave, request=None):
    """O JSON da folha do aviso `chave`, para este usuário.

    Http404 para o aviso que não tem folha (ele continua levando para a
    tela); PermissionDenied para quem não recebe aquele aviso -- a mesma
    capacidade que decide o aviso decide a folha (`avisos.RESOLVIVEIS`).
    """
    capacidade = RESOLVIVEIS.get(chave)
    if capacidade is None:
        raise Http404("Este aviso não tem folha de conserto.")
    acesso = capacidades(user)
    if not acesso.get(capacidade):
        raise PermissionDenied("Este aviso não é da sua função.")

    titulo, icone = TITULOS[chave]
    if chave == "clientes_incompletos":
        corpo = _clientes()
    elif chave == "pedidos":
        corpo = _pedidos()
    elif chave == "estoque":
        corpo = _estoque()
    else:
        corpo = _propostas(user, acesso, chave, request)

    corpo.update({
        "status": "sucesso",
        "chave": chave,
        "titulo": titulo,
        "icone": icone,
        "instrucao": INSTRUCOES[chave],
        "limite": LIMITE,
    })
    corpo["mostrando"] = len(corpo["itens"])
    return corpo


# ======================================================================
# CLIENTES INCOMPLETOS
# ======================================================================
def _clientes():
    incompletos = (
        Cliente.objects.filter(ativo=True).filter(filtro_incompletos())
        .values("pk").distinct()
    )
    total = Cliente.objects.filter(pk__in=incompletos).count()

    # Quem tem proposta viva vem primeiro: é o cadastro que trava o
    # contrato, a entrega e a nota desta semana.
    com_proposta = Orcamento.objects.filter(
        cliente_id=OuterRef("pk"),
        status__in=(*Orcamento.EM_ABERTO, Orcamento.Status.APROVADO),
    )
    clientes = list(
        Cliente.objects.filter(pk__in=incompletos)
        .annotate(_com_proposta=Exists(com_proposta))
        .prefetch_related(
            Prefetch("enderecos", queryset=EnderecoCliente.objects.order_by("id")),
        )
        .order_by("-_com_proposta", "nome_cliente", "pk")[:LIMITE]
    )

    itens = []
    for cliente in clientes:
        faltas = faltas_do_cliente(cliente)
        documento_errado = "documento" in faltas and bool(cliente.documento)
        itens.append({
            "id": cliente.pk,
            "nome": cliente.nome_cliente,
            "tipo": cliente.get_tipo_display(),
            "com_proposta": bool(cliente._com_proposta),
            "faltas": faltas,
            # Só o número que está ERRADO viaja (para corrigir em cima dele).
            "documento": cliente.documento if documento_errado else "",
            "documento_invalido": documento_errado,
            "canal": cliente.canal_telefone,
            "ficha": _url("clientes_inner", q=cliente.nome_cliente, editar=cliente.pk),
        })

    return {
        "tipo": "clientes",
        "quantidade": total,
        "itens": itens,
        "tela": {
            "url": _url("clientes_inner", incompletos=1),
            "rotulo": "Abrir a tela de clientes",
        },
        "urls": {
            "salvar": _url("clientes_inner"),
            "cep": _url("consultar_cep_inner"),
        },
    }


# ======================================================================
# PROPOSTAS (em aberto, a vencer, vencidas, aprovadas, recusadas)
# ======================================================================
ORDEM = {
    "orcamentos_em_aberto": ("validade", "-criacao"),
    "orcamentos_vencendo": ("validade", "-criacao"),
    "orcamentos_vencidos": ("-validade", "-criacao"),
    "orcamentos_aprovados": ("-respondido_em",),
    "orcamentos_recusados": ("-respondido_em",),
}


def _uma_por_negociacao(consulta):
    """A versão mais nova de cada negociação, e o total de negociações.

    O sino conta NEGOCIAÇÕES (v1, v2 e v3 são uma só); a folha mostra uma
    linha por negociação, para a lista ter o tamanho do número.
    """
    ids = list(consulta.values_list("pk", flat=True))
    mapa = mapa_de_negociacoes(ids)
    escolhidos = {}
    for versao, negociacao in mapa.items():
        if versao > escolhidos.get(negociacao, 0):
            escolhidos[negociacao] = versao
    return set(escolhidos.values()), len(escolhidos)


def _texto_da_validade(orcamento):
    dias = orcamento.dias_para_vencer
    if dias is None:
        return "Sem validade"
    if dias < 0:
        return "Venceu há " + _plural(-dias, "dia", "dias")
    if dias == 0:
        return "Vence hoje"
    return "Vence em " + _plural(dias, "dia", "dias")


def _resumo_dos_itens(itens):
    linhas = [f"{item.quantidade}× {item.descricao}" for item in itens[:3]]
    if len(itens) > 3:
        linhas.append(f"e mais {len(itens) - 3}")
    return ", ".join(linhas)


def _propostas(user, acesso, chave, request):
    from core.email_utils import smtp_configurado

    consulta = consulta_do_aviso(user, chave)
    escolhidos, total = _uma_por_negociacao(consulta)

    orcamentos = list(
        Orcamento.objects.filter(pk__in=escolhidos)
        .select_related("cliente", "ordem_servico")
        .prefetch_related("itens")
        .order_by(*ORDEM[chave], "-pk")[:LIMITE]
    )

    editar = acesso["orcamentos_editar_comercial"]
    email_ligado = smtp_configurado() if editar else False
    aprovadas = chave == "orcamentos_aprovados"

    itens = []
    for orcamento in orcamentos:
        itens_da_proposta = list(orcamento.itens.all())
        viva = orcamento.status in Orcamento.EM_ABERTO
        whatsapp = "".join(c for c in (orcamento.whatsapp_destinatario or "") if c.isdigit())
        dias = orcamento.dias_para_vencer
        congelada = bool(
            getattr(orcamento, "ordem_servico", None) is not None
            or orcamento.motivo_situacao_travada
        )
        item = {
            "id": orcamento.pk,
            "versao": orcamento.versao,
            "cliente": orcamento.destinatario,
            "estado": orcamento.status,
            "situacao": orcamento.get_status_display(),
            "total": _moeda(orcamento.total),
            "itens": _resumo_dos_itens(itens_da_proposta),
            "validade": _data(orcamento.validade),
            "validade_texto": _texto_da_validade(orcamento) if viva else "",
            "vencida": orcamento.vencido,
            "enviada": (
                f"Enviada em {_data(orcamento.enviado_em)}"
                if orcamento.enviado_em else "Ainda não enviada"
            ),
            "abrir": _url("orcamentos_inner", q=orcamento.pk),
            "previa": _url("orcamento_previa_inner", orcamento.pk),
            # o passo seguinte da aprovação: o contrato para o cliente assinar
            "contrato_url": _url("documento_assinatura_inner", orcamento.pk) if editar else "",
            "acoes": {
                # Reenviar é o "Enviar → WhatsApp" da lista de Orçamentos,
                # com a mesma trava de `pode_enviar` (vencida não gera link).
                "whatsapp": bool(
                    editar and orcamento.pode_enviar and not orcamento.envio_para_consulta
                    and itens_da_proposta and len(whatsapp) >= 10
                ),
                "whatsapp_rotulo": (
                    "Enviar no WhatsApp"
                    if orcamento.status == Orcamento.Status.RASCUNHO
                    else "Reenviar no WhatsApp"
                ),
                # (o aviso de uma proposta já aprovada pede o passo seguinte,
                # o contrato, e não um reenvio: `envio_para_consulta`)
                "sem_whatsapp": bool(
                    editar and orcamento.pode_enviar and not orcamento.envio_para_consulta
                    and len(whatsapp) < 10
                ),
                # O lembrete por e-mail é o atalho da Home (LembrarClienteView).
                "email": bool(
                    editar and email_ligado
                    and orcamento.status == Orcamento.Status.AGUARDANDO_RESPOSTA
                    and (orcamento.email_destinatario or "").strip()
                    and dias is not None and dias >= 0
                ),
                # A situação, como o botão "Situação" da lista. A aprovação
                # que o cliente deu por telefone, WhatsApp ou no balcão é um
                # toque só (seção 121): "Cliente aprovou", ao lado da recusa.
                "aprovar": bool(editar and viva and not congelada and itens_da_proposta),
                "recusar": bool(editar and viva and not congelada),
                "expirar": bool(editar and viva and not congelada and orcamento.vencido),
            },
        }
        if orcamento.status == Orcamento.Status.RECUSADO:
            item["motivo"] = orcamento.motivo_recusa or ""
        if orcamento.respondido_em:
            quem = orcamento.respondido_por or "o cliente"
            verbo = "Aprovada" if orcamento.status == Orcamento.Status.APROVADO else "Respondida"
            if orcamento.status == Orcamento.Status.RECUSADO:
                verbo = "Recusada"
            item["resposta"] = f"{verbo} por {quem} em {_data(orcamento.respondido_em)}"
        if aprovadas:
            item.update(_aprovada(user, acesso, orcamento))
        itens.append(item)

    filtro = {
        "orcamentos_aprovados": {"filtro": "aprovados"},
        "orcamentos_recusados": {"filtro": "recusados"},
    }.get(chave, {})
    return {
        "tipo": "propostas",
        "quantidade": total,
        "itens": itens,
        "tela": {
            "url": _url("orcamentos_inner", **filtro),
            "rotulo": "Abrir a tela de orçamentos",
        },
        "urls": {
            "orcamentos": _url("orcamentos_inner"),
        },
    }


def _aprovada(user, acesso, orcamento):
    """O prazo de entrega e o contrato da proposta aprovada.

    O PRAZO é o de produção, em dias úteis, que o funil já grava
    (`views_funil.PrazoProducaoView`) e que a Cláusula 3ª do contrato lê
    (`contrato.prazo_de_entrega_do_orcamento`): combinar a data é escrever
    este número ANTES de gerar o contrato. O CONTRATO é o do cartão de
    assinatura (`views_documento_assinatura`).
    """
    from . import contrato
    from . import documento_assinatura as svc
    from .views_documento_assinatura import pode_documento
    from .views_funil import dados_do_prazo, pode_cuidar, prazo_editavel

    saida = {}
    if pode_cuidar(user, orcamento):
        prazo = dados_do_prazo(orcamento)
        prazo["editavel"] = prazo_editavel(orcamento)
        prazo["contrato"] = contrato.prazo_de_entrega_do_orcamento(orcamento)
        saida["prazo"] = prazo

    if pode_documento(user):
        documento = svc.documento_atual(orcamento)
        situacao = svc.situacao_do_cartao(orcamento, documento)
        papel = "contrato"
        if documento is not None and svc.e_servico(documento.conteudo or {}):
            # a ordem de serviço do orçamento de manutenção (seção 124)
            papel = "ordem de serviço"
        elif documento is not None and not svc.e_contrato(documento.conteudo or {}):
            papel = "termo de compra"
        saida["contrato"] = {
            "situacao": situacao,
            "papel": papel,
            "assinado_por": (
                documento.assinante_nome if documento is not None and documento.assinado else ""
            ),
            "observacoes": (
                [obs["texto"] for obs in contrato.observacoes(orcamento)]
                if documento is None else []
            ),
            "pagina": _url("documento_assinatura_inner", orcamento.pk),
            "gerar": _url("documento_assinatura_inner", orcamento.pk),
            "link": _url("documento_assinatura_link", orcamento.pk),
            "via": _url("documento_assinatura_via", orcamento.pk) if documento is not None else "",
        }
    return saida


# ======================================================================
# PEDIDOS DO SITE
# ======================================================================
def _pedidos():
    from core.models import Pedido

    from .views_funil import opcoes_de_andamento

    abertos = Pedido.objects.exclude(status__in=["finalizado", "cancelado"])
    total = abertos.count()
    pedidos = list(
        abertos.select_related("cliente__user")
        .prefetch_related("itens")
        .order_by("criacao", "id")[:LIMITE]
    )

    itens = []
    for pedido in pedidos:
        conta = getattr(pedido.cliente, "user", None) if pedido.cliente_id else None
        nome = ""
        if conta is not None:
            nome = conta.get_full_name() or conta.username
        produtos = list(pedido.itens.all())
        resumo = ", ".join(f"{p.quantidade}× {p.nome_item}" for p in produtos[:3])
        if len(produtos) > 3:
            resumo += f" e mais {len(produtos) - 3}"
        itens.append({
            "id": pedido.pk,
            "cliente": nome or "Cliente do site",
            "cidade": "/".join(p for p in (pedido.cidade or "", pedido.estado or "") if p),
            "itens": resumo,
            "total": _moeda(pedido.total_cobrado),
            "situacao": pedido.situacao_texto,
            "estado": pedido.status,
            "criado": _data(pedido.criacao),
            "entrega": pedido.get_tipo_envio_display() if pedido.tipo_envio else "",
            # O botão é o da tela de Pedidos: a folha do andamento
            # (producao-etiquetas.js) lê estes mesmos dados.
            "andamento": {
                "url": _url("andamento_pedido", pedido.pk),
                "opcoes": opcoes_de_andamento(pedido),
                "titulo": f"Andamento do pedido #{pedido.pk}",
                "transportadora": pedido.transportadora_envio or "",
                "codigo": pedido.codigo_rastreio or "",
                "link": pedido.link_rastreio or "",
            },
        })

    return {
        "tipo": "pedidos",
        "quantidade": total,
        "itens": itens,
        "tela": {"url": _url("pedidos_inner"), "rotulo": "Abrir a tela de pedidos"},
        "urls": {},
    }


# ======================================================================
# ESTOQUE NO MÍNIMO
# ======================================================================
def _estoque():
    criticos = EstoqueMaterial.objects.criticos()
    total = criticos.count()
    linhas = list(
        criticos.select_related("material", "fornecedor")
        .order_by("material__nome_material", "descricao_local")[:LIMITE]
    )
    itens = []
    for estoque in linhas:
        material = estoque.material
        # O código curto ("un", "m", "kg"): "3 de 12 un" cabe na linha.
        unidade = "m²" if material.unidade == "m2" else (material.unidade or "")
        itens.append({
            "id": estoque.pk,
            "material": material.nome_material,
            "codigo": material.codigo_interno or "",
            "local": estoque.descricao_local,
            "quantidade": estoque.quantidade,
            "minimo": estoque.estoque_minimo,
            "unidade": unidade,
            "fornecedor": estoque.fornecedor.nome if estoque.fornecedor_id and estoque.fornecedor else "",
            "zerado": estoque.quantidade <= 0,
        })
    return {
        "tipo": "estoque",
        "quantidade": total,
        "itens": itens,
        "tela": {"url": _url("estoque_inner"), "rotulo": "Abrir o estoque"},
        "urls": {},
    }
