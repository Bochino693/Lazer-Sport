"""A conferência: ninguém é acreditado, nem a IA, nem as tabelas.

É AQUI QUE SE GARANTE "NUNCA FALHAR NOS VALORES". As duas leituras do
documento -- a das regras (`deterministica`) e a da IA (`ia`) -- chegam
aqui e passam pelas mesmas perguntas, sempre com Decimal:

  * O valor que a IA deu está ESCRITO na linha que ela citou? Não está:
    vira alerta e o valor não entra. (A IA não inventa um preço, porque
    um preço sem fonte simplesmente não chega ao formulário.)
  * Quantidade x unitário dá o total da linha que o documento escreveu?
  * A soma das linhas dá o subtotal? Soma + frete - desconto dá o total?
  * As tabelas e a IA leram o MESMO número? Leram números diferentes:
    alerta vermelho, o campo fica vazio com as duas leituras como opção,
    e a pessoa escolhe -- ninguém escolhe por ela.

O QUE SAI DAQUI é a proposta da tela de conferência: cada campo com o
valor como vai ficar, o texto como estava no Word, a fonte (id e trecho),
o selo de confiança, as opções e sugestões, e a lista de alertas. É um
dicionário de texto e números em texto, porque mora na sessão até a
pessoa confirmar.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings

from core.email_utils import cnpj_empresa

from ..models import Cliente, Orcamento
from ..validacoes import chave_documento, documento_valido, tipo_documento
from . import catalogo as cat
from . import deterministica as det
from .leitor import mapa_de_linhas

CENTAVO = Decimal("0.01")

NIVEL_VERMELHO = "vermelho"
NIVEL_AMARELO = "amarelo"

AVISO_PDF = (
    "Este PDF é uma imagem: o texto foi transcrito automaticamente, e cada valor foi "
    "conferido nessa transcrição e nas contas. Confira com o PDF aberto ao lado."
)


def identidade_da_empresa() -> dict:
    """O que é da Lazer & Sport no documento e não pode virar do cliente."""
    telefones = [
        getattr(settings, nome, "") for nome in
        ("EMPRESA_TELEFONE", "EMPRESA_WHATSAPP", "ORCAMENTO_TELEFONE", "ORCAMENTO_WHATSAPP")
    ]
    emails = [getattr(settings, nome, "") for nome in ("EMPRESA_EMAIL", "ORCAMENTO_EMAIL")]
    enderecos = []
    try:
        from core.models import EnderecoEmpresa

        for endereco in EnderecoEmpresa.objects.all()[:5]:
            if endereco.rua:
                enderecos.append(f"{endereco.rua}, {endereco.numero}".strip(", "))
            if getattr(endereco, "telefone", ""):
                telefones.append(endereco.telefone)
    except Exception:  # noqa: BLE001 -- banco sem a tabela não pode derrubar a leitura
        pass
    return {"documentos": [cnpj_empresa()], "telefones": telefones, "emails": emails,
            "enderecos": enderecos}


# ======================================================================
# COMPARAR TEXTO COM A FONTE
# ======================================================================
def _plano(texto: str) -> str:
    texto = unicodedata.normalize("NFC", str(texto or ""))
    texto = texto.replace(" ", " ").replace("–", "-").replace("—", "-")
    texto = re.sub(r"[‘’]", "'", texto)
    texto = re.sub(r"[“”]", '"', texto)
    return re.sub(r"\s+", " ", texto).strip().casefold()


def esta_escrito(valor: str, linha: str) -> bool:
    """O texto está na linha, tirando diferença de espaço, aspas e caixa?"""
    alvo = _plano(valor)
    return bool(alvo) and alvo in _plano(linha)


def _campo_vazio(rotulo="") -> dict:
    return {
        "valor": "", "exibir": "", "original": "", "fonte": None, "confianca": "vazio", "origem": "",
        "opcoes": [], "sugestao": None, "sugestoes": [], "nota": "", "normalizado": False,
        "exigir": False, "rotulo": rotulo,
    }


def _formatar(tipo: str, valor) -> str:
    """O valor no formato do campo do painel."""
    if valor is None or valor == "":
        return ""
    if tipo == "dinheiro":
        return det.moeda(valor)
    if tipo == "quantidade":
        return str(int(valor))
    if tipo == "documento":
        return det.formatar_documento(valor)
    if tipo == "telefone":
        return det.formatar_telefone(valor)
    if tipo == "email":
        return str(valor).strip().lower()
    if tipo == "data":
        return valor.isoformat() if isinstance(valor, date) else str(valor)
    return det.espacos(valor)


def _chave_de_comparacao(tipo: str, valor) -> str:
    if valor is None or valor == "":
        return ""
    if tipo == "dinheiro":
        return str(Decimal(valor).quantize(CENTAVO))
    if tipo == "documento":
        return chave_documento(str(valor))
    if tipo == "telefone":
        return det.digitos_do_telefone(str(valor))
    if tipo == "data":
        return valor.isoformat() if isinstance(valor, date) else str(valor)
    if tipo in ("email",):
        return str(valor).strip().lower()
    if tipo == "quantidade":
        return str(int(valor))
    return re.sub(r"\s+", " ", cat._normalizar(str(valor)))


def _exibir(tipo: str, valor) -> str:
    if tipo == "dinheiro":
        return f"R$ {det.moeda(valor)}" if valor not in (None, "") else ""
    if tipo == "data" and isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    return _formatar(tipo, valor)


# ======================================================================
# A LEITURA DA IA, CONFERIDA NA FONTE
# ======================================================================
class _Conferente:
    """Confere cada valor da IA contra a linha que ela citou."""

    def __init__(self, linhas, *, hoje, data_documento, empresa):
        self.linhas = mapa_de_linhas(linhas)
        self.hoje = hoje
        self.data_documento = data_documento
        self.empresa = empresa
        self.descartes: list[dict] = []

    def descartar(self, rotulo, texto, fonte_id, motivo):
        self.descartes.append({
            "rotulo": rotulo, "texto": texto, "fonte_id": fonte_id or "", "motivo": motivo,
        })

    def conferir(self, campo_ia, tipo: str, rotulo: str):
        """(valor lido, fonte, original) ou None.

        Um valor só passa se o id existe e se o que a IA escreveu está na
        linha citada. Para dinheiro a régua é o NÚMERO: a IA pode ter
        copiado "1234,56" de uma célula que diz "R$ 1.234,56" -- é o mesmo
        valor, e o que se confere é que a célula contém esse valor.
        """
        if not campo_ia:
            return None
        texto = (campo_ia.get("texto") or "").strip()
        if not texto:
            return None
        fonte = campo_ia.get("fonte") or {}
        fonte_id = (fonte.get("id") or "").strip().strip("[]")
        linha = self.linhas.get(fonte_id)
        if linha is None:
            self.descartar(rotulo, texto, fonte_id, "a IA não indicou de onde tirou o valor"
                           if not fonte_id else f"a linha {fonte_id} não existe no documento")
            return None
        fonte_ok = {"id": linha["id"], "texto": linha["texto"]}

        if tipo == "dinheiro":
            sem = det.sem_acento(texto)
            if det.FRETE_SEM_CUSTO.search(sem) and esta_escrito(texto, linha["texto"]):
                return Decimal("0.00"), fonte_ok, texto
            percentual = re.fullmatch(r"(\d{1,2}(?:[.,]\d{1,2})?)\s*%", texto)
            if percentual and esta_escrito(texto, linha["texto"]):
                return ("%", Decimal(percentual.group(1).replace(",", "."))), fonte_ok, texto
            achados = [a for a in det.valores_em_reais(texto, coluna_de_dinheiro=True) if a["valor"] is not None]
            recusados = [a for a in det.valores_em_reais(texto, coluna_de_dinheiro=True) if a["valor"] is None]
            if len(achados) != 1:
                motivo = recusados[0]["recusa"] if recusados else "não é um valor em reais"
                self.descartar(rotulo, texto, fonte_id, motivo)
                return None
            valor = achados[0]["valor"]
            na_linha = {a["valor"] for a in det.valores_em_reais(linha["texto"], coluna_de_dinheiro=True)}
            if valor not in na_linha:
                self.descartar(rotulo, texto, fonte_id,
                               f"R$ {det.moeda(valor)} não está escrito em {fonte_id}")
                return None
            return valor, fonte_ok, achados[0]["texto"]

        if not esta_escrito(texto, linha["texto"]):
            self.descartar(rotulo, texto, fonte_id, f"“{texto}” não está escrito em {fonte_id}")
            return None

        if tipo == "quantidade":
            quantidade, _, recusa = det.ler_quantidade(texto)
            if quantidade is None:
                self.descartar(rotulo, texto, fonte_id, recusa or "quantidade ilegível")
                return None
            return quantidade, fonte_ok, texto
        if tipo == "documento":
            chave = chave_documento(texto)
            if len(chave) not in (11, 14):
                self.descartar(rotulo, texto, fonte_id, "não é um CPF nem um CNPJ")
                return None
            if chave in {chave_documento(c) for c in self.empresa["documentos"]}:
                self.descartar(rotulo, texto, fonte_id, "é o CNPJ da própria Lazer & Sport")
                return None
            return chave, fonte_ok, texto
        if tipo == "telefone":
            digitos = det.digitos_do_telefone(texto)
            if not det.telefone_valido(digitos):
                self.descartar(rotulo, texto, fonte_id, "telefone incompleto")
                return None
            if digitos in {det.digitos_do_telefone(t) for t in self.empresa["telefones"] if t}:
                self.descartar(rotulo, texto, fonte_id, "é o telefone da própria Lazer & Sport")
                return None
            return digitos, fonte_ok, texto
        if tipo == "email":
            achados = det.emails(texto)
            if len(achados) != 1:
                self.descartar(rotulo, texto, fonte_id, "não é um e-mail")
                return None
            email = achados[0]["email"]
            if email in {e.lower() for e in self.empresa["emails"] if e}:
                self.descartar(rotulo, texto, fonte_id, "é o e-mail da própria Lazer & Sport")
                return None
            return email, fonte_ok, texto
        if tipo == "data":
            lido = det.ler_validade(texto, data_documento=self.data_documento, hoje=self.hoje)
            if not lido:
                self.descartar(rotulo, texto, fonte_id, "não dá para saber a data")
                return None
            return (lido["data"], lido["como"]), fonte_ok, texto
        return det.espacos(texto), fonte_ok, texto


def _do_deterministico(campo_det, tipo):
    if not campo_det or campo_det.get("valor") in (None, ""):
        return None
    valor = campo_det["valor"]
    if tipo == "data":
        valor = (valor, campo_det.get("motivo", ""))
    return valor, campo_det["fonte"], campo_det.get("original", "")


# ======================================================================
# FUNDIR AS DUAS LEITURAS
# ======================================================================
#: Onde a divergência é vermelha: número, documento e contato. Em texto
#: livre (nome, condição de pagamento) duas leituras diferentes quase
#: sempre são o mesmo dado escrito de dois jeitos -- vira opção, sem
#: bloquear.
TIPOS_EXATOS = ("dinheiro", "quantidade", "documento", "telefone", "email", "data")


def fundir(chave, rotulo, tipo, lido_det, lido_ia, *, ia_usada, alertas, referencia=False):
    """Um campo da proposta a partir das duas leituras (cada uma pode faltar)."""
    campo = _campo_vazio(rotulo)
    campo["chave"] = chave
    campo["tipo"] = tipo
    campo["referencia"] = referencia

    def valor_de(lido):
        valor = lido[0]
        if tipo == "data":
            return valor[0]
        return valor

    def preencher(lido, origem, confianca):
        valor = valor_de(lido)
        campo["valor"] = _formatar(tipo, valor)
        campo["exibir"] = _exibir(tipo, valor)
        campo["original"] = lido[2] or ""
        campo["fonte"] = lido[1]
        campo["origem"] = origem
        campo["confianca"] = confianca
        if tipo == "data" and lido[0][1]:
            campo["nota"] = lido[0][1]
        campo["normalizado"] = bool(
            campo["original"] and _plano(campo["original"]) != _plano(campo["exibir"])
        )

    if lido_det and lido_ia:
        if _chave_de_comparacao(tipo, valor_de(lido_det)) == _chave_de_comparacao(tipo, valor_de(lido_ia)):
            preencher(lido_det if tipo != "texto" else lido_ia, "ambas", "alta")
            return campo
        opcoes = []
        for lido, origem in ((lido_det, "tabelas"), (lido_ia, "ia")):
            valor = valor_de(lido)
            opcoes.append({
                "valor": _formatar(tipo, valor),
                "rotulo": _exibir(tipo, valor),
                "origem": origem,
                "fonte": lido[1],
                "original": lido[2],
            })
        if tipo in TIPOS_EXATOS:
            # As duas leituras discordam num número: ninguém escolhe pela
            # pessoa. O campo fica vazio, com as duas como botão.
            campo["opcoes"] = opcoes
            campo["confianca"] = "baixa"
            campo["origem"] = "divergente"
            campo["fonte"] = lido_det[1]
            campo["original"] = lido_det[2]
            alertas.append({
                "id": f"divergencia:{chave}",
                "nivel": NIVEL_VERMELHO,
                "tipo": "divergencia",
                "campo": chave,
                "referencia": referencia,
                "titulo": f"{rotulo}: as duas leituras discordam",
                "detalhe": (
                    f"Pelas tabelas: {opcoes[0]['rotulo']} ({lido_det[1]['id']}); pela IA: "
                    f"{opcoes[1]['rotulo']} ({lido_ia[1]['id']}). "
                    + ("Confira no documento e escreva qual vale." if referencia
                       else "Escolha a certa (ou corrija) no campo.")
                ),
                "fonte": lido_det[1],
            })
            return campo
        # Texto: a IA costuma pegar o nome inteiro ("Buffet Alegria Ltda"
        # onde o rótulo tinha "Buffet Alegria"). Vale a dela, com a outra
        # como opção.
        preencher(lido_ia, "ia", "media")
        campo["opcoes"] = opcoes
        return campo
    if lido_det:
        preencher(lido_det, "tabelas", "alta")
        if ia_usada:
            campo["nota"] = (campo["nota"] + " · " if campo["nota"] else "") + "a IA não citou este valor"
        return campo
    if lido_ia:
        preencher(lido_ia, "ia", "media")
        return campo
    return campo


def _linha_do_item(fonte_id: str) -> str:
    achado = re.match(r"^(.*T\d+L\d+)C\d+$", fonte_id or "")
    return achado.group(1) if achado else (fonte_id or "")


# ======================================================================
# A PROPOSTA
# ======================================================================
def montar_proposta(leitura: dict, *, hoje: date | None = None) -> dict:
    """A proposta da tela de conferência, a partir do que está na sessão.

    `leitura` = {"arquivo", "linhas", "ia": {"usada", "modelo", "aviso",
    "dados"}, "escolhas": {posição: "b:12"}}. Tudo é recalculado a cada
    abertura (e de novo no envio), com o catálogo e o cadastro de AGORA:
    o produto que alguém cadastrou enquanto a conferência estava aberta
    passa a ser encontrado.
    """
    from django.utils import timezone

    hoje = hoje or timezone.localdate()
    linhas = leitura["linhas"]
    empresa = identidade_da_empresa()
    lido = det.ler(linhas, hoje=hoje, empresa=empresa)
    campos_det = lido["campos"]
    ia_info = leitura.get("ia") or {}
    dados_ia = ia_info.get("dados") if ia_info.get("usada") else None
    ia_usada = dados_ia is not None

    alertas: list[dict] = []
    conferente = _Conferente(linhas, hoje=hoje, data_documento=lido["data_documento"], empresa=empresa)

    def pela_ia(caminho, tipo, rotulo):
        if not dados_ia:
            return None
        atual = dados_ia
        for parte in caminho.split("."):
            atual = (atual or {}).get(parte)
        return conferente.conferir(atual, tipo, rotulo)

    percentuais = {}

    def campo(chave, rotulo, tipo, chave_det, caminho_ia, *, referencia=False):
        lido_ia = pela_ia(caminho_ia, tipo, rotulo) if caminho_ia else None
        if lido_ia and isinstance(lido_ia[0], tuple) and lido_ia[0][0] == "%":
            # "10%" é desconto em porcentagem, e não um valor em reais: a
            # conta sobre o subtotal vira sugestão (ver _tratar_percentual).
            if chave == "valores.desconto":
                percentuais[chave] = (lido_ia[0][1], lido_ia[1], lido_ia[2])
            else:
                conferente.descartar(rotulo, lido_ia[2], lido_ia[1]["id"], "porcentagem não é valor em reais")
            lido_ia = None
        return fundir(
            chave, rotulo, tipo,
            _do_deterministico(campos_det.get(chave_det), tipo) if chave_det else None,
            lido_ia,
            ia_usada=ia_usada, alertas=alertas, referencia=referencia,
        )

    # --------------------------------------------------------- cliente
    cliente = {
        "nome": campo("cliente.nome", "Nome do cliente", "texto", "cliente", "cliente.nome"),
        "estabelecimento": campo("cliente.estabelecimento", "Estabelecimento", "texto",
                                 "estabelecimento", "cliente.estabelecimento"),
        "documento": campo("cliente.documento", "CPF/CNPJ", "documento", "documento", "cliente.documento"),
        "contato": campo("cliente.contato", "Pessoa de contato", "texto", "contato", "cliente.contato"),
        "telefone": campo("cliente.telefone", "Telefone/WhatsApp", "telefone", "telefone", "cliente.telefone"),
        "email": campo("cliente.email", "E-mail", "email", "email", "cliente.email"),
        "endereco": campo("cliente.endereco", "Endereço", "texto", "endereco", "cliente.endereco"),
        "cep": campo("cliente.cep", "CEP", "texto", "cep", "cliente.cep"),
        "logradouro": campo("cliente.logradouro", "Rua", "texto", "logradouro", "cliente.logradouro"),
        "numero": campo("cliente.numero", "Número", "texto", "numero", "cliente.numero"),
        "complemento": campo("cliente.complemento", "Complemento", "texto", "complemento",
                             "cliente.complemento"),
        "bairro": campo("cliente.bairro", "Bairro", "texto", "bairro", "cliente.bairro"),
        "cidade": campo("cliente.cidade", "Cidade", "texto", "cidade", "cliente.cidade"),
        "uf": campo("cliente.uf", "UF", "texto", "uf", "cliente.uf"),
    }
    if cliente["cep"]["valor"]:
        cliente["cep"]["valor"] = det.formatar_cep(cliente["cep"]["valor"])
    if cliente["uf"]["valor"]:
        cliente["uf"]["valor"] = cliente["uf"]["valor"].upper()[:2]
    # Endereço inteiro vindo só da IA (sem as partes): a mesma separação
    # da leitura por regra.
    if cliente["endereco"]["valor"] and not cliente["logradouro"]["valor"]:
        partes = det.ler_endereco(cliente["endereco"]["valor"])
        for nome_parte, chave in (("cep", "cep"), ("rua", "logradouro"), ("numero", "numero"),
                                  ("complemento", "complemento"), ("bairro", "bairro"),
                                  ("cidade", "cidade"), ("uf", "uf")):
            if partes[nome_parte] and not cliente[chave]["valor"]:
                cliente[chave].update({
                    "valor": partes[nome_parte], "exibir": partes[nome_parte],
                    "original": partes[nome_parte], "fonte": cliente["endereco"]["fonte"],
                    "confianca": cliente["endereco"]["confianca"], "origem": cliente["endereco"]["origem"],
                })
    # O documento disse "WhatsApp" ao lado do número?
    cliente["telefone"]["whatsapp_escrito"] = bool(
        (campos_det.get("telefone") or {}).get("whatsapp_escrito")
    )
    documento = cliente["documento"]
    if documento["valor"] and not documento_valido(documento["valor"]):
        documento["nota"] = f"{tipo_documento(documento['valor'])} inválido: os dígitos não conferem"
        alertas.append({
            "id": "documento_invalido", "nivel": NIVEL_VERMELHO, "tipo": "documento_invalido",
            "campo": "cliente.documento", "verificavel": True,
            "titulo": f"{tipo_documento(documento['valor'])} do cliente inválido",
            "detalhe": (
                f"“{documento['original'] or documento['valor']}” não passa na conta dos dígitos "
                "verificadores. Corrija pelo documento do cliente ou apague o campo."
            ),
            "fonte": documento["fonte"],
        })

    casamento = cat.casar_cliente(
        documento=documento["valor"] if documento_valido(documento["valor"]) else "",
        email=cliente["email"]["valor"],
        telefone=cliente["telefone"]["valor"],
        nome=cliente["nome"]["valor"],
    )
    for alerta in casamento["alertas"]:
        alertas.append({
            "id": "cliente_conflito", "nivel": NIVEL_VERMELHO, "tipo": "cliente_conflito",
            "campo": "cliente.vinculo", "titulo": "O cliente do documento bate com mais de um cadastro",
            "detalhe": alerta["detalhe"], "fonte": None,
        })
        break
    from .. import clientes as svc_clientes

    escolhido = casamento["cliente"]
    cliente["vinculo"] = {
        "modo": "existente" if escolhido else "novo",
        "cliente_id": escolhido.pk if escolhido else None,
        "confianca": casamento["confianca"] if escolhido else "baixa",
        "motivo": casamento["motivo"] or ("nenhum cadastro com estes dados: será cadastrado" if not escolhido else ""),
        "opcao": svc_clientes.opcao_de_busca(escolhido) if escolhido else None,
        "candidatos": [svc_clientes.opcao_de_busca(c) for c in casamento["candidatos"]],
        "cadastro": {
            "nome": escolhido.nome_cliente, "documento": escolhido.documento or "",
            "telefone": escolhido.telefone or "", "email": escolhido.email or "",
            "whatsapp": escolhido.canal_telefone == Cliente.CanalTelefone.WHATSAPP,
        } if escolhido else None,
    }
    cliente["tipo_sugerido"], cliente["tipo_motivo"] = _tipo_sugerido(
        cliente["nome"]["valor"], documento["valor"],
    )
    # O WhatsApp é fato do cadastro, não palpite: só vem marcado quando o
    # número do Word é o mesmo que o cadastro já confirmou como WhatsApp.
    cliente["whatsapp_confirmado"] = bool(
        escolhido and cliente["vinculo"]["cadastro"]["whatsapp"]
        and cliente["telefone"]["valor"]
        and det.digitos_do_telefone(cliente["telefone"]["valor"])
        == det.digitos_do_telefone(escolhido.telefone)
    )

    # ----------------------------------------------------------- itens
    catalogo = cat.carregar_catalogo()
    itens = _montar_itens(lido, dados_ia, conferente, alertas, ia_usada=ia_usada,
                          catalogo=catalogo, linhas=linhas, escolhas=leitura.get("escolhas") or {})

    # ---------------------------------------------------------- valores
    valores = {
        "subtotal": campo("valores.subtotal", "Subtotal do documento", "dinheiro", "subtotal", "subtotal", referencia=True),
        "frete": campo("valores.frete", "Frete", "dinheiro", "frete", "frete"),
        "desconto": campo("valores.desconto", "Desconto", "dinheiro", "desconto", "desconto"),
        "total": campo("valores.total", "Total do documento", "dinheiro", "total", "total_geral", referencia=True),
        "valor_final": campo("valores.valor_final", "Valor final negociado", "dinheiro", "valor_final",
                             "valor_negociado", referencia=True),
    }
    for chave_valor in ("subtotal", "total", "frete", "desconto", "valor_final"):
        conflitos = (campos_det.get(chave_valor) or {}).get("conflitos")
        if conflitos:
            alertas.append({
                "id": f"repetido:{chave_valor}", "nivel": NIVEL_VERMELHO, "tipo": "repetido",
                "campo": f"valores.{chave_valor}",
                "titulo": f"O documento traz dois valores para “{valores[chave_valor]['rotulo']}”",
                "detalhe": "Aparece " + " e também ".join(
                    f"R$ {det.moeda(c['valor'])} ({c['fonte']['id']})"
                    for c in [campos_det[chave_valor]] + conflitos
                ) + ". Confira no documento qual vale.",
                "fonte": campos_det[chave_valor]["fonte"],
            })

    _tratar_percentual(valores, campos_det, percentuais.get("valores.desconto"))
    frete = valores["frete"]
    if not frete["valor"] and not frete["opcoes"]:
        # A conta do próprio documento decide: se itens − desconto já dão o
        # total escrito, não há frete nessa conta -- é zero, e com a razão
        # à mostra. Sem total para conferir, a pessoa escolhe.
        total_doc = _decimal(valores["total"]["valor"])
        desconto_doc = _decimal(valores["desconto"]["valor"]) or Decimal("0.00")
        linhas_doc = [
            (int(i["quantidade"]["valor"]) if i["quantidade"]["valor"].isdigit() else None,
             _decimal(i["valor_unitario"]["valor"]))
            for i in itens
        ]
        conta_doc = contas(linhas_doc, Decimal("0.00"), desconto_doc)
        if itens and total_doc is not None and conta_doc["completos"] and conta_doc["total"] == total_doc:
            frete.update({
                "valor": "0,00", "exibir": "R$ 0,00", "confianca": "media", "origem": "tabelas",
                "fonte": valores["total"]["fonte"], "original": "",
                "nota": "o documento não cobra frete: itens − desconto já dão o total escrito",
            })
        else:
            frete["sugestoes"] = [{"valor": "0,00", "rotulo": "Sem frete (R$ 0,00)",
                                   "motivo": "o documento não fala de frete: confirme que não há"}]
            frete["nota"] = frete["nota"] or "o documento não traz frete; escolha de propósito, mesmo que seja zero"
    if campos_det.get("frete", {}).get("motivo") and frete["origem"] in ("tabelas", "ambas"):
        frete["nota"] = campos_det["frete"]["motivo"]

    # --------------------------------------------------------- condições
    condicoes = {
        "validade": campo("condicoes.validade", "Validade", "data", "validade", "validade"),
        "forma_pagamento": campo("condicoes.forma_pagamento", "Forma de pagamento", "texto",
                                 "forma_pagamento", "forma_pagamento"),
        "forma_envio": campo("condicoes.forma_envio", "Forma de envio", "texto", "forma_envio", "forma_envio"),
        "prazo": campo("condicoes.prazo", "Prazo de entrega", "texto", "prazo", "prazo_entrega"),
        "observacoes": campo("condicoes.observacoes", "Observações", "texto", "observacoes", "observacoes"),
    }
    _sugerir_validade(condicoes["validade"], hoje)
    existentes_pagamento = _mais_usados("forma_pagamento")
    existentes_envio = _mais_usados("forma_envio")
    for nome, existentes, normalizar in (
        ("forma_pagamento", existentes_pagamento, det.normalizar_pagamento),
        ("forma_envio", existentes_envio, det.normalizar_envio),
    ):
        alvo = condicoes[nome]
        if alvo["valor"]:
            normalizado = normalizar(alvo["valor"], existentes)
            if normalizado != alvo["valor"]:
                alvo["valor"] = normalizado
            alvo["exibir"] = alvo["valor"]
            alvo["normalizado"] = bool(alvo["original"] and alvo["original"].strip(" .") != alvo["valor"])
        for opcao in alvo["opcoes"]:
            opcao["valor"] = opcao["rotulo"] = normalizar(opcao["valor"], existentes)

    # --------------------------------------------- descartes e recusas
    for descarte in conferente.descartes:
        alertas.append({
            "id": f"sem_fonte:{len(alertas)}", "nivel": NIVEL_AMARELO, "tipo": "sem_fonte",
            "campo": "", "titulo": f"{descarte['rotulo']}: valor da IA descartado",
            "detalhe": f"A IA indicou “{descarte['texto']}”, mas {descarte['motivo']}. O valor não entrou.",
            "fonte": None,
        })
    for recusa in lido["recusas"]:
        alertas.append({
            "id": f"recusa:{len(alertas)}", "nivel": NIVEL_AMARELO, "tipo": "recusa",
            "campo": "", "titulo": "Valor do documento que não deu para ler",
            "detalhe": f"{recusa['motivo'][:1].upper()}{recusa['motivo'][1:]}. Preencha o campo à mão.",
            "fonte": recusa.get("fonte"),
        })
    for alerta in lido["alertas"]:
        alertas.append({
            "id": f"leitura:{len(alertas)}", "nivel": NIVEL_AMARELO, "tipo": alerta["tipo"],
            "campo": "", "titulo": "Confira no documento", "detalhe": alerta["detalhe"],
            "fonte": alerta.get("fonte"),
        })

    formato = leitura.get("formato") or "docx"
    proposta = {
        "arquivo": leitura.get("arquivo", ""),
        "formato": formato,
        "ia": {
            "usada": ia_usada,
            "modelo": ia_info.get("modelo", "") if ia_usada else "",
            "aviso": AVISO_PDF if formato == "pdf_ia" else "",
        },
        "cliente": cliente,
        "itens": itens,
        "valores": valores,
        "condicoes": condicoes,
        "opcoes": {
            "pagamento": _opcoes(existentes_pagamento, det.OPCOES_DE_PAGAMENTO),
            "envio": _opcoes(existentes_envio, det.OPCOES_DE_ENVIO),
        },
        "data_documento": lido["data_documento"].isoformat() if lido["data_documento"] else "",
    }
    _valores_nao_usados(proposta, linhas, alertas)
    if formato == "pdf_ia":
        _rebaixar_confianca_do_pdf(proposta)
    proposta["alertas"] = alertas
    recalcular_alertas(proposta)
    return proposta


def _rebaixar_confianca_do_pdf(proposta):
    """No PDF, "as duas leituras concordam" não é prova independente.

    A leitura por regra roda sobre a TRANSCRIÇÃO que a própria IA fez do
    PDF: se a IA leu um 8 onde estava um 3, as duas leem o mesmo 8. A
    concordância ainda pega o erro de cópia entre a transcrição e o
    esquema, e as contas continuam valendo -- mas nenhum valor de PDF
    passa de confiança média, e a pessoa confere com o PDF aberto.
    """
    def rebaixar(campo):
        if isinstance(campo, dict) and campo.get("confianca") == "alta":
            campo["confianca"] = "media"
            campo["nota"] = (campo.get("nota") + " · " if campo.get("nota") else "") + "transcrito do PDF"

    cliente = proposta["cliente"]
    for nome, campo in cliente.items():
        if nome != "vinculo" and isinstance(campo, dict) and "valor" in campo:
            rebaixar(campo)
    for item in proposta["itens"]:
        for nome in ("descricao", "quantidade", "valor_unitario", "total_linha"):
            rebaixar(item[nome])
    for grupo in ("valores", "condicoes"):
        for campo in proposta[grupo].values():
            rebaixar(campo)


def _tipo_sugerido(nome: str, documento: str):
    sem = det.sem_acento(nome or "")
    if "buffet" in sem:
        return Cliente.Tipo.BUFFET, "o nome tem “buffet”"
    if re.search(r"\b(escola|colegio|creche|educacao infantil)\b", sem):
        return Cliente.Tipo.ESCOLA, "o nome é de escola"
    if re.search(r"\bcondominio\b", sem):
        return Cliente.Tipo.CONDOMINIO, "o nome é de condomínio"
    if re.search(r"\b(prefeitura|secretaria|camara municipal|governo)\b", sem):
        return Cliente.Tipo.ORGAO, "o nome é de órgão público"
    chave = chave_documento(documento)
    if len(chave) == 14:
        return Cliente.Tipo.COMERCIAL, "o documento é um CNPJ"
    return Cliente.Tipo.RESIDENCIAL, "o documento é um CPF" if len(chave) == 11 else "padrão do cadastro"


def _mais_usados(campo: str, limite: int = 12) -> list[str]:
    """As formas já usadas nas propostas, das mais comuns às raras."""
    from django.db.models import Count

    return [
        linha[campo]
        for linha in Orcamento.objects.exclude(**{campo: ""})
        .values(campo).annotate(vezes=Count("id")).order_by("-vezes", campo)[:limite]
    ]


def _opcoes(existentes, padrao) -> list[str]:
    vistas, saida = set(), []
    for opcao in list(padrao) + list(existentes):
        chave = cat._normalizar(opcao)
        if opcao and chave not in vistas:
            vistas.add(chave)
            saida.append(opcao)
    return saida


def _sugerir_validade(validade: dict, hoje: date):
    """A validade do painel é sugestão a confirmar, nunca preenchida escondida."""
    padrao = hoje + timedelta(days=Orcamento.DIAS_DE_VALIDADE_PADRAO)
    sugestao_padrao = {
        "valor": padrao.isoformat(),
        "rotulo": f"{Orcamento.DIAS_DE_VALIDADE_PADRAO} dias (padrão do painel): {padrao:%d/%m/%Y}",
        "motivo": "o prazo com que toda proposta nova nasce no painel",
    }
    if validade["valor"]:
        escolhida = date.fromisoformat(validade["valor"])
        if escolhida < hoje:
            validade["nota"] = (
                f"a validade do documento ({escolhida:%d/%m/%Y}) já passou: a proposta sairia vencida"
            )
            validade["valor"] = ""
            validade["confianca"] = "baixa"
            validade["exigir"] = True
            validade["sugestoes"] = [sugestao_padrao]
            prazo = det._PRAZO_EM_DIAS.search(det.sem_acento(validade["original"] or ""))
            if prazo:
                dias = int(prazo.group(1))
                nova = det.somar_dias_uteis(hoje, dias) if prazo.group(2) else hoje + timedelta(days=dias)
                validade["sugestoes"].insert(0, {
                    "valor": nova.isoformat(),
                    "rotulo": f"o mesmo prazo do documento a partir de hoje: {nova:%d/%m/%Y}",
                    "motivo": validade["original"],
                })
        return
    if not validade["opcoes"]:
        validade["sugestoes"] = [sugestao_padrao]
        validade["nota"] = "o documento não traz validade"


def _tratar_percentual(valores, campos_det, percentual_ia):
    """Desconto escrito só em porcentagem: a conta vira sugestão, não valor.

    "10% de desconto" sem o valor em reais deixa o campo vazio e
    OBRIGATÓRIO: ignorar a frase faria o orçamento sair sem o desconto
    que o cliente leu no Word.
    """
    desconto = valores["desconto"]
    achado = None
    if campos_det.get("desconto_percentual"):
        campo_det = campos_det["desconto_percentual"]
        achado = (campo_det["valor"], campo_det["fonte"], campo_det["original"])
    elif percentual_ia:
        achado = percentual_ia
    if achado is None or desconto["valor"] or desconto["opcoes"]:
        return
    percentual, fonte, original = achado
    desconto["exigir"] = True
    desconto["fonte"] = fonte
    desconto["original"] = original
    desconto["percentual"] = str(percentual)
    desconto["nota"] = (
        f"o documento dá {original} de desconto, sem o valor em reais: confirme o valor "
        "(a sugestão é a conta sobre o subtotal dos itens)"
    )


def _montar_itens(lido, dados_ia, conferente, alertas, *, ia_usada, catalogo, linhas, escolhas):
    ordem = {linha["id"]: posicao for posicao, linha in enumerate(linhas)}
    itens_det = {
        item["linha_fonte"]: item for item in lido["itens"]
        if item["contexto"] == "tabela" or not ia_usada
    }
    usados = set()
    lista = []

    def lido_det(item, nome, tipo):
        campo_det = item.get(nome) if item else None
        if not campo_det or campo_det.get("valor") in (None, ""):
            return None
        return campo_det["valor"], campo_det["fonte"], campo_det.get("original", "")

    for posicao, item_ia in enumerate((dados_ia or {}).get("itens") or [], start=1):
        rotulo = f"Item {posicao}"
        descricao = conferente.conferir(item_ia.get("descricao"), "texto", f"{rotulo} (descrição)")
        if descricao is None:
            texto = ((item_ia.get("descricao") or {}).get("texto") or "").strip()
            if texto:
                alertas.append({
                    "id": f"item_descartado:{posicao}", "nivel": NIVEL_AMARELO, "tipo": "item_descartado",
                    "campo": "", "titulo": "Item da IA que não está no documento",
                    "detalhe": f"A IA listou “{texto}”, mas esse texto não está no documento. O item não entrou.",
                    "fonte": None,
                })
            continue
        linha_fonte = _linha_do_item(descricao[1]["id"])
        item_det = itens_det.get(linha_fonte)
        if item_det:
            usados.add(linha_fonte)
        lista.append({
            "ordem": ordem.get(descricao[1]["id"], 10**6),
            "linha_fonte": linha_fonte,
            "contexto": item_det["contexto"] if item_det else "ia",
            "descricao": (lido_det(item_det, "descricao", "texto"), descricao),
            "quantidade": (lido_det(item_det, "quantidade", "quantidade"),
                           conferente.conferir(item_ia.get("quantidade"), "quantidade", f"{rotulo} (quantidade)")),
            "valor_unitario": (lido_det(item_det, "valor_unitario", "dinheiro"),
                               conferente.conferir(item_ia.get("valor_unitario"), "dinheiro", f"{rotulo} (unitário)")),
            "total_linha": (lido_det(item_det, "total_linha", "dinheiro"),
                            conferente.conferir(item_ia.get("total_linha"), "dinheiro", f"{rotulo} (total)")),
            "unidade": item_det["unidade"] if item_det else "",
            "recusas": item_det["recusas"] if item_det else [],
        })
    for linha_fonte, item_det in itens_det.items():
        if linha_fonte in usados:
            continue
        lista.append({
            "ordem": ordem.get(item_det["descricao"]["fonte"]["id"], 10**6),
            "linha_fonte": linha_fonte,
            "contexto": item_det["contexto"],
            "descricao": (lido_det(item_det, "descricao", "texto"), None),
            "quantidade": (lido_det(item_det, "quantidade", "quantidade"), None),
            "valor_unitario": (lido_det(item_det, "valor_unitario", "dinheiro"), None),
            "total_linha": (lido_det(item_det, "total_linha", "dinheiro"), None),
            "unidade": item_det["unidade"],
            "recusas": item_det["recusas"],
            "so_tabelas": ia_usada,
        })
    lista.sort(key=lambda item: item["ordem"])

    itens = []
    for posicao, bruto in enumerate(lista, start=1):
        uid = f"i{posicao}"
        rotulo = f"Item {posicao}"
        chave = f"itens.{uid}"
        item = {"uid": uid, "posicao": posicao, "linha_fonte": bruto["linha_fonte"],
                "contexto": bruto["contexto"], "unidade": bruto["unidade"]}
        for nome, tipo, nome_rotulo, referencia in (
            ("descricao", "texto", "descrição", False),
            ("quantidade", "quantidade", "quantidade", False),
            ("valor_unitario", "dinheiro", "valor unitário", False),
            ("total_linha", "dinheiro", "total da linha no documento", True),
        ):
            de_tabela, de_ia = bruto[nome]
            item[nome] = fundir(
                f"{chave}.{nome}", f"{rotulo} — {nome_rotulo}", tipo, de_tabela, de_ia,
                ia_usada=ia_usada and not bruto.get("so_tabelas"), alertas=alertas,
                referencia=referencia,
            )
        for nome, motivo, celula in bruto["recusas"]:
            destino = item.get(nome)
            if destino is not None and not destino["valor"]:
                destino["nota"] = motivo
                destino["fonte"] = destino["fonte"] or {"id": celula["id"], "texto": celula["texto"]}
                destino["original"] = destino["original"] or celula["texto"]
                alertas.append({
                    "id": f"recusa:{uid}.{nome}", "nivel": NIVEL_AMARELO, "tipo": "recusa",
                    "campo": f"{chave}.{nome}", "titulo": f"{rotulo}: valor que não deu para ler",
                    "detalhe": f"{motivo[:1].upper()}{motivo[1:]} ({celula['id']}: “{celula['texto']}”).",
                    "fonte": {"id": celula["id"], "texto": celula["texto"]},
                })

        if bruto["contexto"] == "paragrafo":
            alertas.append({
                "id": f"paragrafo:{uid}", "nivel": NIVEL_AMARELO, "tipo": "paragrafo",
                "campo": f"{chave}.descricao", "titulo": f"{rotulo} lido de um parágrafo",
                "detalhe": "Sem tabela e sem IA, a linha foi lida pela posição dos valores. "
                           "Confira quantidade, unitário e total.",
                "fonte": item["descricao"]["fonte"],
            })
        if bruto.get("so_tabelas"):
            alertas.append({
                "id": f"so_tabelas:{uid}", "nivel": NIVEL_AMARELO, "tipo": "so_tabelas",
                "campo": f"{chave}.descricao", "titulo": f"{rotulo}: a IA não listou esta linha",
                "detalhe": "A linha está na tabela de itens do documento e entrou pela leitura da tabela. "
                           "Confira se é mesmo um item cobrado.",
                "fonte": item["descricao"]["fonte"],
            })

        _sugerir_valores_da_linha(item)

        original = item["descricao"]["original"] or item["descricao"]["valor"]
        casamento = cat.casar_item(original, catalogo)
        escolha_ia = escolhas.get(str(posicao)) or escolhas.get(posicao)
        if escolha_ia and casamento["confianca"] != "alta":
            if any(c["id"] == escolha_ia for c in casamento["candidatos"]):
                casamento["escolhido"] = escolha_ia
                casamento["confianca"] = "media"
                casamento["motivo"] = "a IA escolheu entre os candidatos parecidos; confirme"
                casamento["por_ia"] = True
        item["produto"] = {
            "escolhido": casamento["escolhido"] if casamento["confianca"] != "baixa" else None,
            "confianca": casamento["confianca"],
            "motivo": casamento["motivo"],
            "pontos": casamento["pontos"],
            "candidatos": casamento["candidatos"],
            "por_ia": casamento.get("por_ia", False),
            "opcao": cat.opcao_do_produto(casamento["escolhido"])
            if casamento["escolhido"] and casamento["confianca"] != "baixa" else None,
        }
        item["original"] = original
        if item["produto"]["opcao"]:
            # Uniformidade: a linha passa a ter o nome do catálogo, e o
            # texto do Word fica ao lado como referência.
            nome_catalogo = item["produto"]["opcao"]["rotulo"]
            item["descricao"]["valor"] = nome_catalogo
            item["descricao"]["exibir"] = nome_catalogo
            item["descricao"]["normalizado"] = _plano(nome_catalogo) != _plano(original)
        else:
            alertas.append({
                "id": f"produto:{uid}", "nivel": NIVEL_AMARELO, "tipo": "produto",
                "campo": f"{chave}.produto", "titulo": f"{rotulo}: produto não encontrado no catálogo",
                "detalhe": f"“{original}” não tem um produto parecido o bastante. Escolha na busca "
                           "ou marque como linha avulsa.",
                "fonte": item["descricao"]["fonte"],
            })
        itens.append(item)
    return itens


def _sugerir_valores_da_linha(item):
    """Quantidade e unitário que faltam viram SUGESTÃO, com a conta à mostra."""
    quantidade = item["quantidade"]
    unitario = item["valor_unitario"]
    total = item["total_linha"]
    valor_total = det.valor_do_campo(total["valor"])
    valor_unitario = det.valor_do_campo(unitario["valor"])
    if not quantidade["valor"] and not quantidade["opcoes"]:
        if valor_total is not None and valor_unitario:
            razao = valor_total / valor_unitario
            if razao == razao.to_integral_value() and razao > 0:
                quantidade["sugestoes"] = [{
                    "valor": str(int(razao)), "rotulo": str(int(razao)),
                    "motivo": f"total ÷ unitário = R$ {det.moeda(valor_total)} ÷ R$ {det.moeda(valor_unitario)}",
                }]
        elif valor_total is not None and not unitario["valor"]:
            quantidade["sugestoes"] = [{"valor": "1", "rotulo": "1",
                                        "motivo": "o documento traz só o valor da linha"}]
    valor_quantidade = int(quantidade["valor"]) if quantidade["valor"].isdigit() else None
    if not unitario["valor"] and not unitario["opcoes"] and valor_total is not None:
        base = valor_quantidade or (1 if not quantidade["valor"] else None)
        if base:
            unidade = (valor_total / base).quantize(CENTAVO)
            if unidade * base == valor_total:
                unitario["sugestoes"] = [{
                    "valor": det.moeda(unidade), "rotulo": f"R$ {det.moeda(unidade)}",
                    "motivo": f"total ÷ quantidade = R$ {det.moeda(valor_total)} ÷ {base}",
                }]


def _valores_nao_usados(proposta, linhas, alertas):
    """Todo valor em reais do documento precisa ter entrado em algum lugar.

    É a rede que pega o item que as duas leituras deixaram passar: um
    "R$ 350,00" escrito no documento e que não virou unitário, total,
    frete, desconto nem parte de uma condição de pagamento.
    """
    usados_por_linha: dict[str, set] = {}
    linhas_inteiras = set()

    def marcar(campo):
        if not campo or not campo.get("fonte"):
            return
        valor = det.valor_do_campo(campo.get("valor"))
        if valor is not None:
            usados_por_linha.setdefault(campo["fonte"]["id"], set()).add(valor)
        for opcao in campo.get("opcoes") or []:
            valor_opcao = det.valor_do_campo(opcao["valor"])
            if valor_opcao is not None and opcao.get("fonte"):
                usados_por_linha.setdefault(opcao["fonte"]["id"], set()).add(valor_opcao)

    for item in proposta["itens"]:
        for nome in ("valor_unitario", "total_linha"):
            marcar(item[nome])
            if item[nome]["fonte"] and item[nome].get("nota"):
                linhas_inteiras.add(item[nome]["fonte"]["id"])
    for campo in proposta["valores"].values():
        marcar(campo)
        if campo.get("percentual") and campo.get("fonte"):
            linhas_inteiras.add(campo["fonte"]["id"])
    for campo in list(proposta["condicoes"].values()) + [proposta["cliente"]["endereco"]]:
        if campo.get("fonte"):
            linhas_inteiras.add(campo["fonte"]["id"])

    soltos = []
    for linha in linhas:
        if linha["parte"] not in ("corpo", "caixa") or linha["id"] in linhas_inteiras:
            continue
        for achado in det.valores_em_reais(linha["texto"]):
            if achado["valor"] is None:
                continue
            if achado["valor"] in usados_por_linha.get(linha["id"], set()):
                continue
            soltos.append(f"R$ {det.moeda(achado['valor'])} em {linha['id']} (“{linha['texto'][:70]}”)")
    if soltos:
        alertas.append({
            "id": "valores_nao_usados", "nivel": NIVEL_AMARELO, "tipo": "valores_nao_usados",
            "campo": "", "titulo": "Valores do documento que não entraram em nenhum campo",
            "detalhe": "; ".join(soltos[:6]) + (f"; e mais {len(soltos) - 6}" if len(soltos) > 6 else "")
            + ". Confira se falta algum item.",
            "fonte": None,
        })


# ======================================================================
# AS CONTAS (na abertura e de novo no envio)
# ======================================================================
def _decimal(texto):
    return det.valor_do_campo(texto)


def contas(itens_valores, frete, desconto) -> dict:
    """Subtotal e total a partir do que está no formulário."""
    subtotal = Decimal("0.00")
    completos = True
    for quantidade, unitario in itens_valores:
        if quantidade is None or unitario is None:
            completos = False
            continue
        subtotal += (unitario * quantidade).quantize(CENTAVO)
    total = subtotal + (frete or Decimal("0.00")) - (desconto or Decimal("0.00"))
    return {"subtotal": subtotal.quantize(CENTAVO), "total": max(total, Decimal("0.00")).quantize(CENTAVO),
            "completos": completos}


def recalcular_alertas(proposta, valores_atuais=None):
    """Refaz os alertas de conta (linha, subtotal, total) com os valores do formulário.

    `valores_atuais` = {"itens": {uid: (quantidade, unitario)}, "frete",
    "desconto"} -- o que veio no envio. Sem ele, valem os valores da
    leitura. Os alertas de conta são VERIFICÁVEIS: se a pessoa corrigir o
    valor e a conta passar a bater, o alerta se resolve sozinho.
    """
    alertas = [a for a in proposta["alertas"] if a.get("tipo") not in ("linha", "soma_subtotal", "soma_total", "sem_total")]
    if valores_atuais is None:
        valores_atuais = {
            "itens": {
                item["uid"]: (
                    int(item["quantidade"]["valor"]) if item["quantidade"]["valor"].isdigit() else None,
                    _decimal(item["valor_unitario"]["valor"]),
                )
                for item in proposta["itens"]
            },
            "frete": _decimal(proposta["valores"]["frete"]["valor"]),
            "desconto": _decimal(proposta["valores"]["desconto"]["valor"]),
        }
    por_uid = {item["uid"]: item for item in proposta["itens"]}
    for uid, (quantidade, unitario) in valores_atuais["itens"].items():
        item = por_uid.get(uid)
        if not item:
            continue
        total_word = _decimal(item["total_linha"]["valor"])
        if total_word is None or quantidade is None or unitario is None:
            continue
        calculado = (unitario * quantidade).quantize(CENTAVO)
        if calculado != total_word:
            alertas.append({
                "id": f"linha:{uid}", "nivel": NIVEL_VERMELHO, "tipo": "linha", "verificavel": True,
                "campo": f"itens.{uid}.valor_unitario",
                "titulo": f"Item {item['posicao']}: a conta da linha não bate",
                "detalhe": (
                    f"{quantidade} × R$ {det.moeda(unitario)} = R$ {det.moeda(calculado)}, mas o documento "
                    f"diz R$ {det.moeda(total_word)} ({item['total_linha']['fonte']['id']}). "
                    "Corrija a quantidade ou o unitário, ou aceite escrevendo por quê."
                ),
                "fonte": item["total_linha"]["fonte"],
            })

    resultado = contas(valores_atuais["itens"].values(), valores_atuais["frete"], valores_atuais["desconto"])
    subtotal_word = _decimal(proposta["valores"]["subtotal"]["valor"])
    total_word = _decimal(proposta["valores"]["total"]["valor"])
    if subtotal_word is not None and resultado["subtotal"] != subtotal_word:
        alertas.append({
            "id": "soma_subtotal", "nivel": NIVEL_VERMELHO, "tipo": "soma_subtotal", "verificavel": True,
            "campo": "valores.subtotal", "titulo": "A soma das linhas não bate com o subtotal do documento",
            "detalhe": (
                f"Soma das linhas: R$ {det.moeda(resultado['subtotal'])}; subtotal no documento: "
                f"R$ {det.moeda(subtotal_word)} ({proposta['valores']['subtotal']['fonte']['id']})."
                + ("" if resultado["completos"] else " Há linhas sem quantidade ou unitário.")
            ),
            "fonte": proposta["valores"]["subtotal"]["fonte"],
        })
    if total_word is not None and resultado["total"] != total_word:
        alertas.append({
            "id": "soma_total", "nivel": NIVEL_VERMELHO, "tipo": "soma_total", "verificavel": True,
            "campo": "valores.total", "titulo": "O total calculado não bate com o total do documento",
            "detalhe": (
                f"Linhas R$ {det.moeda(resultado['subtotal'])} + frete "
                f"R$ {det.moeda(valores_atuais['frete'] or 0)} − desconto "
                f"R$ {det.moeda(valores_atuais['desconto'] or 0)} = R$ {det.moeda(resultado['total'])}; "
                f"o documento diz R$ {det.moeda(total_word)} ({proposta['valores']['total']['fonte']['id']})."
            ),
            "fonte": proposta["valores"]["total"]["fonte"],
        })
    if total_word is None and subtotal_word is None and proposta["itens"]:
        alertas.append({
            "id": "sem_total", "nivel": NIVEL_AMARELO, "tipo": "sem_total", "campo": "valores.total",
            "titulo": "O documento não traz total para conferir",
            "detalhe": "Sem total escrito, a conta não tem com o que ser comparada. Confira o total calculado.",
            "fonte": None,
        })
    # O VALOR FINAL COMBINADO. Dois casos, e só um deles é escolha óbvia:
    #  * o documento ESCREVE um valor negociado ("Valor final negociado:
    #    R$ 9.500,00") -- ele é o valor final, e a tela já o mostra
    #    escolhido (a pessoa pode trocar);
    #  * o documento diz um TOTAL que a conta das linhas não dá -- erro de
    #    digitação ou venda fechada por outro valor. Aí ninguém escolhe
    #    pela pessoa: a tela mostra os dois, nenhum marcado.
    valor_final_doc = _decimal((proposta["valores"].get("valor_final") or {}).get("valor"))
    if valor_final_doc is not None:
        campo_final = proposta["valores"]["valor_final"]
        proposta["valor_final"] = {
            "oferecido": True, "explicito": True,
            "valor": det.moeda(valor_final_doc),
            "soma": det.moeda(resultado["total"]),
            "fonte": campo_final["fonte"], "original": campo_final.get("original", ""),
        }
    else:
        proposta["valor_final"] = {
            "oferecido": total_word is not None and resultado["total"] != total_word,
            "explicito": False,
            "valor": det.moeda(total_word) if total_word is not None else "",
            "soma": det.moeda(resultado["total"]),
            "fonte": proposta["valores"]["total"]["fonte"],
            "original": proposta["valores"]["total"].get("original", ""),
        }
    desconto = proposta["valores"]["desconto"]
    if desconto.get("percentual"):
        base = resultado["subtotal"]
        conta = (base * Decimal(desconto["percentual"]) / 100).quantize(CENTAVO, rounding=ROUND_HALF_UP)
        desconto["sugestoes"] = [{
            "valor": det.moeda(conta), "rotulo": f"R$ {det.moeda(conta)}",
            "motivo": f"{desconto['original']} de R$ {det.moeda(base)} (subtotal dos itens)",
        }]
    proposta["alertas"] = alertas
    proposta["contas"] = {"subtotal": det.moeda(resultado["subtotal"]), "total": det.moeda(resultado["total"])}
    return proposta
