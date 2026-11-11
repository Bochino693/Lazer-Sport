"""O que falta preencher, a conferência do envio, e o rascunho criado.

O PEDIDO DO CLIENTE, NAS PALAVRAS DELE: "deve requisitar as informações
faltantes prevenindo erros e a uniformidade de informações nos
orçamentos." Então a importação não cria orçamento pela metade. A lista
de pendências abaixo é a MESMA que a tela mostra (o JavaScript repete as
regras para o botão acender na hora), e é ela que decide no servidor --
a tela é só sugestão, e um POST montado à mão passa por aqui igual.

O QUE É OBRIGATÓRIO, E POR QUÊ:
  * cliente identificado: cadastrado (e confirmado, quando o vínculo veio
    só pelo nome) ou cadastrado agora, com as regras do cadastro de
    clientes (`clientes.salvar_cliente`) -- cadastro feito pela
    importação não pode nascer mais frouxo que o feito à mão;
  * documento, quando houver, válido -- CPF/CNPJ errado vai para a nota;
  * WhatsApp ou e-mail no orçamento -- sem isso a proposta não tem por
    onde ser enviada;
  * cada item com produto do catálogo OU marcado, de propósito, como
    linha avulsa; quantidade inteira maior que zero; valor unitário;
  * validade a partir de hoje, forma de pagamento, frete (zero vale, se
    for escolhido) e forma de envio -- os campos de condição que o painel
    tem. O prazo de entrega não tem campo próprio no painel: entra nas
    observações, e por isso é recomendado, não obrigatório;
  * todo alerta vermelho resolvido: corrigido (a conta volta a bater) ou
    aceito com justificativa escrita, que vai para a atividade.
"""

from __future__ import annotations

import copy
import re
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.http import QueryDict
from django.utils import timezone

from ..models import (
    AtividadeOrcamento,
    AvaliacaoBlocoOrcamento,
    Cliente,
    ItemOrcamento,
    Orcamento,
)
from ..permissoes import origem_padrao_orcamento
from ..utils import ErroDeFormulario
from ..validacoes import documento_valido, telefone_valido, tipo_documento
from . import catalogo as cat
from . import deterministica as det
from .conferencia import NIVEL_VERMELHO, recalcular_alertas

LIMITE_DINHEIRO = Decimal("9999999999.99")
JUSTIFICATIVA_MINIMA = 10
JUSTIFICATIVA_MAXIMA = 160


# ======================================================================
# O ENVIO
# ======================================================================
def ler_envio(post) -> dict:
    """O formulário de conferência como dicionário de texto."""
    def campo(nome, limite=None):
        valor = (post.get(nome) or "").strip()
        return valor[:limite] if limite else valor

    # O uid do item volta para o HTML e para seletores do JavaScript: só o
    # formato que a própria tela gera ("i3" da leitura, "n2" acrescentado).
    ordem = []
    for uid in (post.get("itens_ordem") or "").split(","):
        uid = uid.strip()
        if re.fullmatch(r"[in]\d{1,4}", uid) and uid not in ordem:
            ordem.append(uid)
    itens = []
    for uid in ordem[:60]:
        prefixo = f"item-{uid}-"
        itens.append({
            "uid": uid,
            "descricao": campo(prefixo + "descricao", 400),
            "produto": campo(prefixo + "produto", 20),
            "avulsa": campo(prefixo + "avulsa") == "1",
            "conferido": campo(prefixo + "conferido") == "1",
            "quantidade": campo(prefixo + "quantidade", 30),
            "valor_unitario": campo(prefixo + "valor_unitario", 30),
        })
    justificativas = {}
    for chave in post.keys():
        if chave.startswith("aceite-") and post.get(chave) == "1":
            alerta = chave[len("aceite-"):]
            justificativas[alerta] = (post.get(f"justificativa-{alerta}") or "").strip()[:JUSTIFICATIVA_MAXIMA]
    # O total do Word diferente da soma tem duas saídas, e as duas são
    # escolha explícita: "manter a soma" é aceitar o alerta (com a
    # justificativa ao lado), "valor final" grava o total do Word.
    total_escolha = campo("total_escolha")
    if total_escolha == "soma":
        justificativas["soma_total"] = (post.get("justificativa-soma_total") or "").strip()[:JUSTIFICATIVA_MAXIMA]
    return {
        "cliente_modo": campo("cliente_modo") or "novo",
        "cliente_id": campo("cliente_id"),
        "cliente_confirmado": campo("cliente_confirmado") == "1",
        "nome": campo("nome", 200),
        "documento": campo("documento", 40),
        "tipo": campo("tipo", 20),
        "contato": campo("contato", 200),
        "telefone": campo("telefone", 40),
        "whatsapp": campo("whatsapp"),
        "email": campo("email", 300),
        "cep": campo("cep", 18),
        "endereco": campo("endereco", 200),
        "numero": campo("numero", 20),
        "bairro": campo("bairro", 80),
        "cidade": campo("cidade", 80),
        "estado": campo("estado", 30),
        "itens": itens,
        "frete": campo("frete", 30),
        "desconto": campo("desconto", 30),
        "validade": campo("validade", 20),
        "forma_pagamento": campo("forma_pagamento", 300),
        "forma_envio": campo("forma_envio", 300),
        "prazo": campo("prazo", 300),
        "observacoes": campo("observacoes", 4000),
        "total_escolha": total_escolha if total_escolha in ("soma", "valor_final") else "",
        "justificativas": justificativas,
    }


def envio_inicial(proposta) -> dict:
    """O formulário como a tela abre, a partir da proposta."""
    cliente = proposta["cliente"]
    vinculo = cliente["vinculo"]
    cadastro = vinculo.get("cadastro") or {}
    telefone = cliente["telefone"]["valor"]
    email = cliente["email"]["valor"]
    if vinculo["modo"] == "existente":
        # Sem telefone ou e-mail no Word, o contato do orçamento é o do
        # cadastro -- é o mesmo que o formulário normal faz ao escolher o
        # cliente na busca.
        if not telefone and cadastro.get("telefone"):
            telefone = det.formatar_telefone(cadastro["telefone"])
        if not email and cadastro.get("email"):
            email = cadastro["email"]
    whatsapp = ""
    if telefone and vinculo["modo"] == "existente" and cadastro.get("whatsapp") and (
        det.digitos_do_telefone(telefone) == det.digitos_do_telefone(cadastro.get("telefone", ""))
    ):
        whatsapp = "sim"
    return {
        "cliente_modo": vinculo["modo"],
        "cliente_id": str(vinculo["cliente_id"] or ""),
        "cliente_confirmado": False,
        "nome": cadastro.get("nome") or cliente["nome"]["valor"],
        "documento": cliente["documento"]["valor"],
        "tipo": cliente["tipo_sugerido"],
        "contato": cliente["contato"]["valor"],
        "telefone": telefone,
        "whatsapp": whatsapp,
        "email": email,
        "cep": cliente["cep"]["valor"],
        "endereco": cliente["logradouro"]["valor"] or cliente["endereco"]["valor"],
        "numero": cliente["numero"]["valor"],
        "bairro": cliente["bairro"]["valor"],
        "cidade": cliente["cidade"]["valor"],
        "estado": cliente["uf"]["valor"],
        "itens": [
            {
                "uid": item["uid"],
                "descricao": item["descricao"]["valor"],
                "produto": item["produto"]["escolhido"] or "",
                "avulsa": False,
                "conferido": False,
                "quantidade": item["quantidade"]["valor"],
                "valor_unitario": item["valor_unitario"]["valor"],
            }
            for item in proposta["itens"]
        ],
        "frete": proposta["valores"]["frete"]["valor"],
        "desconto": proposta["valores"]["desconto"]["valor"],
        "validade": proposta["condicoes"]["validade"]["valor"],
        "forma_pagamento": proposta["condicoes"]["forma_pagamento"]["valor"],
        "forma_envio": proposta["condicoes"]["forma_envio"]["valor"],
        "prazo": proposta["condicoes"]["prazo"]["valor"],
        "observacoes": proposta["condicoes"]["observacoes"]["valor"],
        # Nunca vem escolhido: entre a soma e o total do Word quem decide
        # é a pessoa (ver `recalcular_alertas`).
        "total_escolha": "",
        "justificativas": {},
    }


# ======================================================================
# A CONFERÊNCIA DO ENVIO
# ======================================================================
def _pendencia(lista, campo, rotulo, motivo, nivel="obrigatorio"):
    lista.append({"campo": campo, "rotulo": rotulo, "motivo": motivo, "nivel": nivel})


def _data(texto):
    try:
        return date.fromisoformat(texto)
    except (TypeError, ValueError):
        return None


def validar(proposta, envio, *, hoje=None) -> dict:
    """Pendências, alertas em aberto e os valores limpos -- tudo do servidor.

    Devolve {"pendencias", "recomendacoes", "alertas_abertos", "limpo",
    "pronto"}. `pronto` só é verdadeiro quando não falta nada obrigatório
    e nenhum alerta vermelho está em aberto.
    """
    hoje = hoje or timezone.localdate()
    pendencias: list[dict] = []
    recomendacoes: list[dict] = []
    limpo: dict = {}
    vinculo = proposta["cliente"]["vinculo"]

    # ------------------------------------------------------- cliente
    modo = envio["cliente_modo"] if envio["cliente_modo"] in ("existente", "novo") else "novo"
    limpo["modo"] = modo
    if modo == "existente":
        cliente = None
        if envio["cliente_id"].isdigit():
            cliente = Cliente.objects.filter(pk=int(envio["cliente_id"])).first()
        if cliente is None:
            _pendencia(pendencias, "cliente.vinculo", "Cliente",
                       "escolha o cliente cadastrado na busca (ou cadastre um novo)")
        elif (
            str(cliente.pk) == str(vinculo["cliente_id"] or "")
            and vinculo["confianca"] != "alta"
            and not envio["cliente_confirmado"]
        ):
            _pendencia(pendencias, "cliente.vinculo", "Cliente",
                       f"confirme que “{cliente.nome_cliente}” é o cliente do documento "
                       f"({vinculo['motivo'] or 'vínculo pelo nome'})")
        limpo["cliente"] = cliente
        limpo["nome"] = cliente.nome_cliente if cliente else ""
    else:
        limpo["cliente"] = None
        nome = det.espacos(envio["nome"])
        if not nome:
            _pendencia(pendencias, "cliente.nome", "Nome do cliente",
                       "o orçamento precisa dizer para quem é")
        elif len(nome) > 90:
            _pendencia(pendencias, "cliente.nome", "Nome do cliente",
                       "use no máximo 90 caracteres (é o limite do cadastro)")
        elif Cliente.objects.filter(nome_cliente__iexact=nome).exists():
            _pendencia(pendencias, "cliente.nome", "Nome do cliente",
                       f"já existe um cliente chamado “{nome}”: escolha-o em “Cliente cadastrado”")
        limpo["nome"] = nome
        if envio["tipo"] not in Cliente.Tipo.values:
            _pendencia(pendencias, "cliente.tipo", "Tipo de cadastro", "escolha o tipo do cliente")
        limpo["tipo"] = envio["tipo"]
        if not envio["documento"]:
            _pendencia(recomendacoes, "cliente.documento", "CPF/CNPJ",
                       "o documento importado não traz CPF/CNPJ; ele vai para a nota e o contrato", "recomendado")
        campos_endereco = ("cep", "endereco", "numero", "bairro", "cidade", "estado")
        if any(envio[c] for c in campos_endereco):
            if not (envio["endereco"] and envio["cidade"]):
                _pendencia(pendencias, "cliente.endereco", "Endereço",
                           "para guardar o endereço, informe pelo menos a rua e a cidade")
            limpo["endereco"] = {c: det.espacos(envio[c]) for c in campos_endereco}
        else:
            _pendencia(recomendacoes, "cliente.endereco", "Endereço",
                       "o endereço serve à entrega, à montagem e ao mapa do site", "recomendado")

    # O documento só é gravado no cadastro NOVO. Com o cliente já
    # cadastrado o cadastro não é tocado pela importação (quem muda
    # cadastro é a aba Clientes), então o CPF do Word ali só serviu para
    # achar a pessoa.
    documento = envio["documento"] if modo == "novo" else ""
    if documento:
        if not documento_valido(documento):
            _pendencia(pendencias, "cliente.documento", "CPF/CNPJ",
                       f"{tipo_documento(documento)} inválido: corrija pelo documento do cliente ou apague")
        elif modo == "novo" and Cliente.objects.filter(
            documento_chave=det.chave_documento(documento)
        ).exists():
            _pendencia(pendencias, "cliente.documento", "CPF/CNPJ",
                       "este CPF/CNPJ já está em outro cliente: escolha o cadastro existente")
    limpo["documento"] = det.formatar_documento(documento) if documento else ""

    telefone = envio["telefone"]
    limpo["telefone"] = ""
    limpo["whatsapp"] = False
    if telefone:
        if not telefone_valido(telefone):
            _pendencia(pendencias, "cliente.telefone", "Telefone/WhatsApp",
                       "telefone incompleto: informe DDD e número, como (11) 99999-9999")
        else:
            limpo["telefone"] = det.formatar_telefone(telefone)
            if envio["whatsapp"] not in ("sim", "nao"):
                _pendencia(pendencias, "cliente.whatsapp", "Este número tem WhatsApp?",
                           "confirme se o número tem WhatsApp (a proposta é enviada por ele)")
            limpo["whatsapp"] = envio["whatsapp"] == "sim"
    email = envio["email"].lower()
    limpo["email"] = ""
    if email:
        try:
            validate_email(email)
            limpo["email"] = email
        except ValidationError:
            _pendencia(pendencias, "cliente.email", "E-mail", "e-mail inválido")
        if modo == "novo" and Cliente.objects.filter(email__iexact=email).exists():
            _pendencia(pendencias, "cliente.email", "E-mail",
                       "este e-mail já está em outro cliente: escolha o cadastro existente")
    if not (limpo["whatsapp"] and limpo["telefone"]) and not limpo["email"]:
        _pendencia(pendencias, "cliente.contato_envio", "WhatsApp ou e-mail",
                   "informe um WhatsApp confirmado ou um e-mail: é por onde a proposta vai")
    contato = det.espacos(envio["contato"])
    if len(contato) > 120:
        _pendencia(pendencias, "cliente.contato", "Pessoa de contato", "use no máximo 120 caracteres")
    elif not contato:
        _pendencia(recomendacoes, "cliente.contato", "Pessoa de contato",
                   "quem atende do lado do cliente ajuda no envio e na cobrança", "recomendado")
    limpo["contato"] = contato

    # --------------------------------------------------------- itens
    por_uid = {item["uid"]: item for item in proposta["itens"]}
    itens_limpos = []
    valores_itens = {}
    if not envio["itens"]:
        _pendencia(pendencias, "itens", "Itens", "o orçamento precisa de pelo menos um item")
    for posicao, item in enumerate(envio["itens"], start=1):
        rotulo = f"Item {posicao}"
        chave = f"itens.{item['uid']}"
        original = por_uid.get(item["uid"])
        descricao = det.espacos(item["descricao"])
        if not descricao:
            _pendencia(pendencias, f"{chave}.descricao", rotulo, "escreva a descrição")
        elif len(descricao) > 180:
            _pendencia(pendencias, f"{chave}.descricao", rotulo,
                       "a descrição passa de 180 caracteres (o limite da linha da proposta)")
        produto = None
        if item["avulsa"]:
            pass
        elif not item["produto"]:
            _pendencia(pendencias, f"{chave}.produto", rotulo,
                       "escolha o produto do catálogo ou marque “linha avulsa”")
        else:
            produto = cat.produto_por_chave(item["produto"])
            if produto is None:
                _pendencia(pendencias, f"{chave}.produto", rotulo,
                           "o produto escolhido não existe mais no catálogo: escolha outro")
            elif (
                original
                and item["produto"] == original["produto"]["escolhido"]
                and original["produto"]["confianca"] != "alta"
                and not item["conferido"]
            ):
                _pendencia(pendencias, f"{chave}.conferido", rotulo,
                           f"confirme o produto sugerido (“{cat.nome_do_produto(produto)}”) ou escolha outro")
        quantidade, _, recusa = det.ler_quantidade(item["quantidade"]) if item["quantidade"] else (None, "", "")
        if quantidade is None:
            _pendencia(pendencias, f"{chave}.quantidade", rotulo,
                       recusa or "informe a quantidade (número inteiro maior que zero)")
        elif quantidade > 100000 or not item["quantidade"].strip().isdigit():
            if quantidade > 100000:
                _pendencia(pendencias, f"{chave}.quantidade", rotulo, "quantidade acima de 100.000")
            else:
                _pendencia(pendencias, f"{chave}.quantidade", rotulo,
                           "escreva só o número inteiro da quantidade")
        unitario = det.valor_do_campo(item["valor_unitario"])
        if unitario is None:
            _pendencia(pendencias, f"{chave}.valor_unitario", rotulo,
                       "informe o valor unitário (R$ 0,00 vale, se for cortesia)"
                       if not item["valor_unitario"] else "valor unitário ilegível: use o formato 1.234,56")
        elif unitario > LIMITE_DINHEIRO:
            _pendencia(pendencias, f"{chave}.valor_unitario", rotulo, "valor acima do limite")
        valores_itens[item["uid"]] = (quantidade, unitario)
        itens_limpos.append({
            "uid": item["uid"], "descricao": descricao[:180], "produto": produto,
            "chave_produto": item["produto"] if produto else "", "avulsa": item["avulsa"],
            "quantidade": quantidade, "valor_unitario": unitario,
            "original": original["original"] if original else "",
        })
    limpo["itens"] = itens_limpos

    # ------------------------------------------------------- valores
    total_word = det.valor_do_campo(proposta["valores"]["total"]["valor"])
    limpo["valor_final"] = (
        total_word if envio.get("total_escolha") == "valor_final" and total_word is not None else None
    )
    frete = det.valor_do_campo(envio["frete"])
    if not envio["frete"]:
        _pendencia(pendencias, "valores.frete", "Frete",
                   "informe o frete; se não houver, escolha “Sem frete (R$ 0,00)”")
    elif frete is None:
        _pendencia(pendencias, "valores.frete", "Frete", "valor do frete ilegível: use o formato 1.234,56")
    desconto = det.valor_do_campo(envio["desconto"]) if envio["desconto"] else Decimal("0.00")
    if envio["desconto"] and desconto is None:
        _pendencia(pendencias, "valores.desconto", "Desconto", "valor do desconto ilegível")
    com_valor_final = limpo["valor_final"] is not None
    if proposta["valores"]["desconto"].get("exigir") and not envio["desconto"] and not com_valor_final:
        _pendencia(pendencias, "valores.desconto", "Desconto",
                   "o documento dá desconto em porcentagem: confirme o valor em reais")
    limpo["frete"] = frete or Decimal("0.00")
    # Com o valor final combinado o desconto não entra na conta: o painel
    # grava zero e mostra ao cliente a diferença até o valor final.
    limpo["desconto"] = Decimal("0.00") if com_valor_final else (desconto or Decimal("0.00"))
    subtotal = sum(
        ((u * q).quantize(Decimal("0.01")) for q, u in valores_itens.values() if q is not None and u is not None),
        Decimal("0.00"),
    )
    if desconto and not com_valor_final and desconto > subtotal + limpo["frete"]:
        _pendencia(pendencias, "valores.desconto", "Desconto", "o desconto é maior que o total")

    # ------------------------------------------------------ condições
    validade = _data(envio["validade"])
    if not envio["validade"]:
        _pendencia(pendencias, "condicoes.validade", "Validade",
                   "escolha até quando a proposta vale (a sugestão do painel é de "
                   f"{Orcamento.DIAS_DE_VALIDADE_PADRAO} dias)")
    elif validade is None:
        _pendencia(pendencias, "condicoes.validade", "Validade", "data inválida")
    elif validade < hoje:
        _pendencia(pendencias, "condicoes.validade", "Validade",
                   "a validade não pode ser anterior a hoje: a proposta sairia vencida")
    limpo["validade"] = validade
    for nome, rotulo in (("forma_pagamento", "Forma de pagamento"), ("forma_envio", "Forma de envio")):
        texto = det.espacos(envio[nome])
        if not texto:
            _pendencia(pendencias, f"condicoes.{nome}", rotulo,
                       "escolha uma das opções ou escreva a condição combinada")
        elif len(texto) > 120:
            _pendencia(pendencias, f"condicoes.{nome}", rotulo,
                       "use no máximo 120 caracteres; o detalhe pode ir para as observações")
        limpo[nome] = texto
    limpo["prazo"] = det.espacos(envio["prazo"])
    if not limpo["prazo"]:
        _pendencia(recomendacoes, "condicoes.prazo", "Prazo de entrega",
                   "o painel não tem campo de prazo: ele vai para as observações", "recomendado")
    limpo["observacoes"] = (envio["observacoes"] or "").strip()

    # -------------------------------------------------------- alertas
    estado = copy.deepcopy(proposta)
    recalcular_alertas(estado, {"itens": valores_itens, "frete": frete, "desconto": desconto})
    abertos = []
    aceitos = []
    for alerta in estado["alertas"]:
        if alerta["nivel"] != NIVEL_VERMELHO:
            continue
        if _resolvido(alerta, envio, limpo, proposta):
            continue
        justificativa = envio["justificativas"].get(alerta["id"], "")
        if alerta["id"] in envio["justificativas"]:
            if len(justificativa) >= JUSTIFICATIVA_MINIMA:
                aceitos.append({"alerta": alerta, "justificativa": justificativa})
                continue
            _pendencia(pendencias, f"alerta.{alerta['id']}", alerta["titulo"],
                       f"escreva por que o alerta pode ser aceito (pelo menos {JUSTIFICATIVA_MINIMA} letras)")
        abertos.append(alerta)
    for alerta in abertos:
        if not any(p["campo"] == f"alerta.{alerta['id']}" for p in pendencias):
            _pendencia(pendencias, f"alerta.{alerta['id']}", alerta["titulo"],
                       "corrija o valor ou aceite o alerta com uma justificativa")
    limpo["aceitos"] = aceitos
    limpo["amarelos"] = [a for a in estado["alertas"] if a["nivel"] != NIVEL_VERMELHO]

    return {
        "pendencias": pendencias,
        "recomendacoes": recomendacoes,
        "alertas": estado["alertas"],
        "alertas_abertos": abertos,
        "contas": estado["contas"],
        "limpo": limpo,
        "pronto": not pendencias,
    }


def _resolvido(alerta, envio, limpo, proposta) -> bool:
    """O alerta vermelho deixou de valer com o que veio no formulário?

    Os de conta (linha, subtotal, total) são recalculados antes de chegar
    aqui: se ainda estão na lista, a conta ainda não bate. Divergência de
    campo editável se resolve quando a pessoa preenche o campo -- ele
    abre VAZIO de propósito, então qualquer valor ali foi escolha dela.
    """
    tipo = alerta["tipo"]
    if tipo == "soma_total" and envio.get("total_escolha") == "valor_final":
        return limpo.get("valor_final") is not None
    if tipo == "documento_invalido":
        return (
            envio["cliente_modo"] == "existente"
            or not envio["documento"]
            or documento_valido(envio["documento"])
        )
    if tipo == "cliente_conflito":
        vinculo = proposta["cliente"]["vinculo"]
        return (envio["cliente_modo"] != vinculo["modo"]) or (
            envio["cliente_id"] != str(vinculo["cliente_id"] or "")
        )
    if tipo == "divergencia" and not alerta.get("referencia"):
        campo = alerta["campo"]
        if campo.startswith("itens."):
            _, uid, nome = campo.split(".", 2)
            item = next((i for i in envio["itens"] if i["uid"] == uid), None)
            return item is None or bool(item.get(nome))
        nome = campo.split(".", 1)[1]
        mapa = {"documento": "documento", "telefone": "telefone", "email": "email",
                "frete": "frete", "desconto": "desconto", "validade": "validade"}
        return bool(envio.get(mapa.get(nome, nome)))
    if tipo == "divergencia" and alerta["campo"].startswith("itens."):
        # A referência (total da linha) de um item que a pessoa removeu
        # não tem mais o que conferir.
        uid = alerta["campo"].split(".")[1]
        return not any(i["uid"] == uid for i in envio["itens"])
    return False


# ======================================================================
# A TELA DEPOIS DE UM ENVIO RECUSADO
# ======================================================================
def aplicar_envio(proposta, envio) -> dict:
    """A proposta com os valores que a pessoa enviou, para redesenhar a tela."""
    estado = copy.deepcopy(proposta)
    por_uid = {item["uid"]: item for item in estado["itens"]}
    novos = []
    for posicao, item in enumerate(envio["itens"], start=1):
        base = por_uid.get(item["uid"])
        if base is None:
            base = item_em_branco(item["uid"], posicao)
        base["posicao"] = posicao
        novos.append(base)
    estado["itens"] = novos
    return estado


def item_em_branco(uid, posicao) -> dict:
    from .conferencia import _campo_vazio

    def campo(nome, tipo, rotulo, referencia=False):
        vazio = _campo_vazio(rotulo)
        vazio.update({"chave": f"itens.{uid}.{nome}", "tipo": tipo, "referencia": referencia})
        return vazio

    return {
        "uid": uid, "posicao": posicao, "linha_fonte": "", "contexto": "manual", "unidade": "",
        "descricao": campo("descricao", "texto", "descrição"),
        "quantidade": campo("quantidade", "quantidade", "quantidade"),
        "valor_unitario": campo("valor_unitario", "dinheiro", "valor unitário"),
        "total_linha": campo("total_linha", "dinheiro", "total da linha no documento", True),
        "produto": {"escolhido": None, "confianca": "baixa", "motivo": "linha acrescentada na conferência",
                    "pontos": 0, "candidatos": [], "por_ia": False, "opcao": None},
        "original": "",
    }


# ======================================================================
# O RASCUNHO
# ======================================================================
def _pedido_para_o_cadastro(request, dados: dict):
    """O cadastro de clientes lê `request.POST`; aqui ele lê os dados conferidos.

    Reaproveitar `salvar_cliente` em vez de gravar o Cliente direto é o
    que garante a mesma regra do cadastro à mão: nome repetido, CPF de
    outro cliente, e-mail de outro cliente, telefone incompleto.
    """
    falso = copy.copy(request)
    post = QueryDict(mutable=True)
    for chave, valor in dados.items():
        post[chave] = valor
    falso.POST = post
    return falso


@transaction.atomic
def criar_rascunho(request, proposta, validado, *, arquivo: str) -> Orcamento:
    """Cliente (quando novo), orçamento em RASCUNHO, itens, blocos e atividade.

    Nada é enviado ao cliente: o rascunho abre na tela normal de edição, e
    é de lá que a proposta segue o caminho de sempre.
    """
    from .. import clientes as svc_clientes

    if not validado["pronto"]:
        raise ErroDeFormulario("Ainda falta preencher: " + "; ".join(
            f"{p['rotulo']} ({p['motivo']})" for p in validado["pendencias"][:5]
        ))
    limpo = validado["limpo"]
    usuario = request.user

    cliente = limpo["cliente"]
    if limpo["modo"] == "novo":
        pedido = _pedido_para_o_cadastro(request, {
            "nome_cliente": limpo["nome"],
            "tipo": limpo["tipo"],
            "documento": limpo["documento"],
            "telefone": limpo["telefone"],
            "canal_telefone": (
                Cliente.CanalTelefone.WHATSAPP if limpo["whatsapp"] else Cliente.CanalTelefone.TELEFONE
            ) if limpo["telefone"] else Cliente.CanalTelefone.NAO_CONFIRMADO,
            "email": limpo["email"],
            "observacoes": f"Cadastrado pela importação do orçamento “{arquivo}”.",
        })
        cliente = svc_clientes.salvar_cliente(pedido)
        envio_endereco = limpo.get("endereco") or {}
        if envio_endereco:
            svc_clientes.salvar_endereco(_pedido_para_o_cadastro(request, envio_endereco), cliente)

    observacoes = limpo["observacoes"]
    if limpo["prazo"]:
        linha_prazo = f"Prazo de entrega: {limpo['prazo'].rstrip('.')}."
        observacoes = f"{linha_prazo}\n{observacoes}".strip() if observacoes else linha_prazo

    orcamento = Orcamento.objects.create(
        cliente=cliente,
        nome_cliente=(cliente.nome_cliente if cliente else limpo["nome"])[:120],
        contato=limpo["contato"][:120],
        whatsapp_cliente=limpo["telefone"] if limpo["whatsapp"] else "",
        email_cliente=limpo["email"],
        status=Orcamento.Status.RASCUNHO,
        origem=origem_padrao_orcamento(usuario),
        validade=limpo["validade"],
        frete=limpo["frete"],
        desconto=limpo["desconto"],
        valor_final=limpo.get("valor_final"),
        forma_pagamento=limpo["forma_pagamento"],
        forma_envio=limpo["forma_envio"],
        observacoes=observacoes,
        responsavel=usuario,
    )

    novos = []
    for item in limpo["itens"]:
        produto = item["produto"]
        chave = item["chave_produto"]
        novos.append(ItemOrcamento(
            orcamento=orcamento,
            descricao=item["descricao"],
            brinquedo=produto if chave.startswith("b:") else None,
            produto=produto if chave.startswith("p:") else None,
            peca=produto if chave.startswith("r:") else None,
            quantidade=item["quantidade"],
            valor_unitario=item["valor_unitario"],
        ))
    ItemOrcamento.objects.bulk_create(novos)

    # Como na criação pelo formulário: a proposta nasce com os dois blocos
    # pendentes de avaliação.
    AvaliacaoBlocoOrcamento.objects.bulk_create([
        AvaliacaoBlocoOrcamento(orcamento=orcamento, bloco=bloco,
                                status=AvaliacaoBlocoOrcamento.Status.PENDENTE)
        for bloco in AvaliacaoBlocoOrcamento.Bloco.values
    ])

    registrar_importacao(orcamento, usuario, limpo, arquivo=arquivo,
                         ia=proposta["ia"], amarelos=limpo["amarelos"])
    return orcamento


def registrar_importacao(orcamento, usuario, limpo, *, arquivo, ia, amarelos):
    """O rastro da importação: arquivo, quem, quando, e o que ficou de alerta.

    `resumo` tem 240 caracteres. Uma linha só não caberia as
    justificativas, então cada alerta aceito ganha a sua linha (com a
    justificativa escrita pela pessoa), as trocas de nome pelo catálogo
    ganham outra, e a linha principal -- a que o sino mostra -- é gravada
    por último. Quem e quando já são do próprio registro (autor e
    criação). Do arquivo, só o nome: ele não fica guardado.
    """
    do_pdf = (arquivo or "").lower().endswith(".pdf")
    fonte = "PDF" if do_pdf else "Word"
    for aceito in limpo["aceitos"]:
        AtividadeOrcamento.registrar(
            orcamento, usuario, AtividadeOrcamento.Tipo.CRIADO,
            resumo=(
                f"Importação do {fonte}: alerta aceito — {aceito['alerta']['titulo']}. "
                f"Justificativa: {aceito['justificativa']}"
            ),
        )
    trocas = [
        f"«{item['original'][:40]}» → {item['descricao'][:40]}"
        for item in limpo["itens"]
        if item["original"] and item["produto"] is not None
        and cat._normalizar(item["original"]) != cat._normalizar(item["descricao"])
    ]
    if trocas:
        AtividadeOrcamento.registrar(
            orcamento, usuario, AtividadeOrcamento.Tipo.CRIADO,
            resumo=f"Importação do {fonte}: nomes pelo catálogo — " + "; ".join(trocas),
        )
    if limpo.get("valor_final") is not None:
        soma = sum(
            ((i["valor_unitario"] * i["quantidade"]).quantize(Decimal("0.01")) for i in limpo["itens"]),
            Decimal("0.00"),
        ) + limpo["frete"]
        AtividadeOrcamento.registrar(
            orcamento, usuario, AtividadeOrcamento.Tipo.CRIADO,
            resumo=(
                f"Importação do {fonte}: valor final combinado R$ {det.moeda(limpo['valor_final'])}, "
                f"o total escrito no documento; a soma das linhas e do frete dá R$ {det.moeda(soma)}."
            ),
        )
    avulsas = sum(1 for item in limpo["itens"] if item["avulsa"])
    partes = [f"Importado do {fonte} «{arquivo[:60]}»"]
    partes.append("lido com IA" if ia.get("usada") else "lido só pelas tabelas (IA indisponível)")
    if limpo["aceitos"]:
        partes.append(f"{len(limpo['aceitos'])} alerta(s) aceito(s) com justificativa")
    if amarelos:
        partes.append(f"{len(amarelos)} aviso(s) conferido(s)")
    if avulsas:
        partes.append(f"{avulsas} linha(s) avulsa(s)")
    partes.append("rascunho, nada enviado ao cliente")
    AtividadeOrcamento.registrar(
        orcamento, usuario, AtividadeOrcamento.Tipo.CRIADO, resumo="; ".join(partes) + ".",
    )
