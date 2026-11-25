"""O CONTRATO de compra e venda que o cliente assina no celular (LEIA-ME-V10, 107).

O PEDIDO DO DONO: "veja que no contrato final de assinatura, devem ter
essas cláusulas, fotos do item também e melhor aproveitamento das folhas
(...) ponha um contrato de assinatura bom e visível, como o de orçamento."

O texto legal é o do contrato que a empresa já usa -- o título, o quadro
"Quantidade | Equipamento", o preâmbulo com VENDEDOR e COMPRADOR, as onze
cláusulas e o fecho --, com os dados de cada venda nos lugares certos. Só
erros de digitação foram corrigidos; as cláusulas NÃO são reescritas aqui.

O QUE ESTE MÓDULO FAZ, E SÓ ISSO:

  * monta a parte do RETRATO que é o contrato (`partes_do_contrato`): o
    vendedor (de `DadosContrato`), o comprador, os itens com a FOTO de
    cada um, o valor por extenso, o prazo, as cláusulas JÁ ESCRITAS e o
    fecho com cidade e data. O texto vai inteiro para o retrato -- e para
    o hash: mudar uma vírgula aqui amanhã não muda o que alguém assinou;
    a folha lê o texto do retrato, nunca este arquivo;
  * escreve números e datas por extenso, em português;
  * diz o PRAZO DE ENTREGA do orçamento, num lugar só
    (`prazo_de_entrega_do_orcamento`);
  * diz o que falta para o contrato poder sair (`pendencias`).

A regra do documento (gerar, link de 24 horas, assinar, suspender) mora
em `documento_assinatura.py`, e a cara do papel nos templates
`documento_assinatura/contrato.html` e `site/paginas/assinatura.css`.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from decimal import Decimal

log = logging.getLogger(__name__)

#: O tipo que o retrato do contrato carrega (os termos antigos não têm).
TIPO = "contrato"

TITULO = "INSTRUMENTO PARTICULAR DE COMPRA E VENDA DE EQUIPAMENTO DE ENTRETENIMENTO"
TITULO_CURTO = "Contrato de compra e venda"

#: Último recurso da Cláusula 3ª: o contrato real da empresa diz 45 dias
#: úteis. Só vale quando o orçamento não diz prazo nenhum.
PRAZO_DE_ENTREGA_PADRAO = 45

#: A largura da foto do item no contrato: ~55 mm impressos a 400 dpi.
LARGURA_DA_FOTO = 900


# ======================================================================
# POR EXTENSO
# ======================================================================
_UNIDADES = (
    "zero", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito",
    "nove", "dez", "onze", "doze", "treze", "catorze", "quinze", "dezesseis",
    "dezessete", "dezoito", "dezenove",
)
_DEZENAS = (
    "", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta",
    "setenta", "oitenta", "noventa",
)
_CENTENAS = (
    "", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos",
    "seiscentos", "setecentos", "oitocentos", "novecentos",
)
_ESCALAS = (
    (10 ** 12, "trilhão", "trilhões"),
    (10 ** 9, "bilhão", "bilhões"),
    (10 ** 6, "milhão", "milhões"),
    (10 ** 3, "mil", "mil"),
    (1, "", ""),
)
_MESES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
    "agosto", "setembro", "outubro", "novembro", "dezembro",
)


def _ate_mil(n: int) -> str:
    """1..999 por extenso: "cem", "cento e um", "trezentos e quarenta e dois"."""
    if n == 100:
        return "cem"
    partes = []
    centena, resto = divmod(n, 100)
    if centena:
        partes.append(_CENTENAS[centena])
    if resto:
        if resto < 20:
            partes.append(_UNIDADES[resto])
        else:
            dezena, unidade = divmod(resto, 10)
            partes.append(_DEZENAS[dezena] + (f" e {_UNIDADES[unidade]}" if unidade else ""))
    return " e ".join(partes)


def numero_por_extenso(numero) -> str:
    """45 -> "quarenta e cinco"; 1500 -> "mil e quinhentos"; 2_000_000 -> "dois milhões".

    O "e" entre os grupos segue a regra de sempre: entra antes do último
    grupo quando ele é menor que cem ou uma centena redonda ("mil e
    quinhentos", "trinta e oito mil e cinco"); fora disso os grupos vão
    lado a lado ("mil quinhentos e vinte"). "Mil", e não "um mil".
    """
    numero = int(numero)
    if numero < 0:
        return "menos " + numero_por_extenso(-numero)
    if numero == 0:
        return "zero"
    grupos = []
    for escala, singular, plural in _ESCALAS:
        quantos, numero = divmod(numero, escala)
        if not quantos:
            continue
        if escala == 1:
            texto = _ate_mil(quantos)
        elif escala == 1000:
            texto = "mil" if quantos == 1 else f"{_ate_mil(quantos)} mil"
        else:
            texto = f"{numero_por_extenso(quantos)} {singular if quantos == 1 else plural}"
        grupos.append((quantos, texto))
    saida = grupos[0][1]
    for posicao, (quantos, texto) in enumerate(grupos[1:], start=1):
        ultimo = posicao == len(grupos) - 1
        saida += (" e " if ultimo and (quantos < 100 or quantos % 100 == 0) else " ") + texto
    return saida


def reais_por_extenso(valor) -> str:
    """38000 -> "trinta e oito mil reais"; 1.5 -> "um real e cinquenta centavos".

    "De reais" depois de milhão redondo ("um milhão de reais"), como se
    escreve em cheque e em contrato.
    """
    valor = Decimal(valor or 0).quantize(Decimal("0.01"))
    if valor < 0:
        return "menos " + reais_por_extenso(-valor)
    inteiro = int(valor)
    centavos = int((valor - inteiro) * 100)
    partes = []
    if inteiro:
        texto = numero_por_extenso(inteiro)
        if inteiro >= 10 ** 6 and inteiro % 10 ** 6 == 0:
            texto += " de"
        partes.append(texto + (" real" if inteiro == 1 else " reais"))
    if centavos:
        partes.append(numero_por_extenso(centavos) + (" centavo" if centavos == 1 else " centavos"))
    return " e ".join(partes) if partes else "zero real"


def data_por_extenso(data) -> str:
    """18/11/2026 -> "18 de novembro de 2026" (o dia 1 é "1º")."""
    dia = "1º" if data.day == 1 else str(data.day)
    return f"{dia} de {_MESES[data.month - 1]} de {data.year}"


# ======================================================================
# O PRAZO DE ENTREGA (Cláusula 3ª)
# ======================================================================
def prazo_de_entrega_do_orcamento(orcamento) -> int:
    """Em quantos dias úteis o equipamento é entregue: O LUGAR ÚNICO.

    A Cláusula 3ª lê o prazo daqui e de mais nenhum lugar. Hoje é o prazo
    de produção que a equipe escreve no orçamento
    (`Orcamento.prazo_producao_dias`, "15 dias úteis"); quando o orçamento
    não diz nada, vale o do contrato da empresa (`PRAZO_DE_ENTREGA_PADRAO`,
    45) -- só como último recurso, nunca escrito no texto da cláusula.

    Se a regra do prazo mudar (por tipo de item, por volume), é ESTA
    função que muda: a cláusula, a folha e os testes continuam iguais.
    """
    dias = getattr(orcamento, "prazo_producao_dias", None)
    if dias is None:
        # sem prazo digitado: o da lista de montagem (montagem + fila, seção 112),
        # pelo MAIOR número da faixa -- o contrato promete o que a fábrica cumpre
        try:
            from . import montagem

            prazo = montagem.prazo_de_entrega(orcamento)
            if prazo is not None and getattr(prazo, "dias_max", None):
                return max(int(prazo.dias_max), 0)
        except Exception:  # noqa: BLE001 -- sem a lista, o padrão do contrato
            pass
        return PRAZO_DE_ENTREGA_PADRAO
    return max(int(dias), 0)


def _prazo(orcamento) -> dict:
    dias = prazo_de_entrega_do_orcamento(orcamento)
    return {
        "dias": dias,
        # "45", "06": dois dígitos, como o contrato escreve a garantia.
        "numero": f"{dias:02d}",
        "extenso": numero_por_extenso(dias),
        "unidade": "dia útil" if dias == 1 else "dias úteis",
        "padrao": getattr(orcamento, "prazo_producao_dias", None) is None,
    }


# ======================================================================
# AS FOTOS DOS ITENS (Cláusula 1ª)
# ======================================================================
def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", (texto or "").lower())
    return " ".join("".join(c for c in texto if unicodedata.category(c) != "Mn").split())


def _adesivo_do_item(item):
    """O adesivo (a arte) da linha, quando o produto tem mais de um.

    A linha do orçamento não guarda o adesivo à parte: ele está no nome
    ("Air Game Kids Alienígenas"). Procura-se o nome de um adesivo do
    produto na descrição -- o mais comprido primeiro, para "Super Heróis
    Marvel" ganhar de "Super Heróis". Sem nenhum no nome, é o padrão.
    Produto de um adesivo só não tem adesivo para dizer: devolve None.
    """
    from core.models import VarianteAdesivo

    brinquedo = item.brinquedo
    variantes = list(
        VarianteAdesivo.objects.filter(brinquedo=brinquedo, ativo=True)
        .order_by("-padrao", "ordem", "id")
    )
    if len(variantes) < 2:
        return None, False

    def e_padrao(variante):
        return variante.padrao or variante.pk == brinquedo.adesivo_padrao_id

    descricao = _normalizar(item.descricao)
    for variante in sorted(
        (v for v in variantes if not e_padrao(v)), key=lambda v: -len(v.nome or ""),
    ):
        nome = _normalizar(variante.nome)
        if nome and nome in descricao:
            return variante, False
    padrao = next((v for v in variantes if e_padrao(v)), variantes[0])
    return padrao, True


def foto_e_adesivo(item) -> tuple[str, str]:
    """(endereço da foto, nome do adesivo) da linha -- ("", "") sem nada.

    A foto é a do catálogo: a frente do ADESIVO escolhido quando o produto
    tem vários (a mesma galeria da página do produto), senão a capa do
    brinquedo ou da peça (`ItemOrcamento.imagem`). Linha de produção ou
    escrita à mão não tem foto: a folha desenha um quadro discreto com o
    nome, nunca uma imagem quebrada. Nada aqui derruba o contrato -- foto
    que não abre vira "sem foto".
    """
    from core.fotos import reduzir_imagem, url_da_imagem

    adesivo = ""
    imagem = None
    try:
        if item.brinquedo_id and item.brinquedo:
            variante, e_padrao = _adesivo_do_item(item)
            if variante is not None:
                adesivo = variante.nome
                if not e_padrao:
                    from core.models import galeria_publica

                    galeria = galeria_publica(
                        list(item.brinquedo.imagens_brinquedo.all()), adesivo_id=variante.pk,
                    )
                    if galeria:
                        imagem = galeria[0].imagem
        if imagem is None:
            imagem = item.imagem
        url = url_da_imagem(imagem) if imagem else ""
        return (reduzir_imagem(url, LARGURA_DA_FOTO) if url else ""), adesivo
    except Exception:
        log.exception("Contrato do orçamento %s: a foto do item %s não abriu", item.orcamento_id, item.pk)
        return "", adesivo


# ======================================================================
# O TEXTO
# ======================================================================
def _clausula(numero, texto, **extra):
    return {"numero": numero, "rotulo": f"Cláusula {numero}ª.", "texto": texto, **extra}


def _paragrafo(rotulo, texto):
    return {"rotulo": rotulo, "texto": texto}


def _com_ponto(texto: str) -> str:
    texto = (texto or "").strip()
    return texto if not texto or texto[-1] in ".!?;" else texto + "."


def secoes(*, valor_total, valor_extenso, condicao, prazo) -> list[dict]:
    """As onze cláusulas, com os dados da venda -- o texto do contrato da empresa.

    Cada seção tem o título dela e as cláusulas, e cada cláusula o rótulo
    ("Cláusula 4ª."), o texto e, quando tem, os parágrafos. A 1ª leva as
    fotos (`fotos`) e a 2ª a condição de pagamento (`complemento`).
    """
    return [
        {
            "titulo": "DO OBJETO DO CONTRATO",
            "clausulas": [
                _clausula(
                    1,
                    "O presente instrumento tem como objeto equipamento de "
                    "entretenimento, conforme características da imagem abaixo, "
                    "sendo o VENDEDOR o único proprietário do referido "
                    "equipamento, vejamos:",
                    fotos=True,
                ),
                _clausula(
                    2,
                    "Pelo presente instrumento e na melhor forma do direito, o "
                    "VENDEDOR vende ao COMPRADOR o equipamento objeto deste "
                    "contrato, descrito na Cláusula 1ª, no valor total de "
                    f"R$ {valor_total} ({valor_extenso}), que deverá ser pago "
                    "da seguinte forma:",
                    complemento=(
                        "Condição de pagamento: Conforme negociação entre as "
                        "partes, o pagamento será realizado da seguinte forma: "
                        + _com_ponto(condicao)
                    ),
                ),
            ],
        },
        {
            "titulo": "DAS OBRIGAÇÕES E GARANTIAS",
            "clausulas": [
                _clausula(
                    3,
                    "O VENDEDOR obriga-se a entregar o equipamento descrito na "
                    + (
                        # 0 dia = pronta entrega: "no prazo de 00 (zero) dias úteis" não se escreve
                        "Cláusula 1ª imediatamente após a confirmação do pagamento (pronta entrega)."
                        if not prazo.get("dias")
                        else f"Cláusula 1ª no prazo de {prazo['numero']} ({prazo['extenso']}) "
                        f"{prazo['unidade']} após a confirmação do pagamento."
                    ),
                ),
                _clausula(
                    4,
                    "O VENDEDOR compromete-se a prestar todo o suporte referente "
                    "ao prazo de garantia de 06 (seis) meses de todos os produtos "
                    "descritos na Cláusula 1ª, desde que por defeito de fabricação.",
                    paragrafos=[
                        _paragrafo(
                            "Parágrafo primeiro.",
                            "Na hipótese de se fazer necessária a manutenção do "
                            "equipamento, este será avaliado por técnicos "
                            "devidamente cadastrados pela empresa e, caso seja "
                            "detectado defeito por mau uso, o VENDEDOR irá emitir "
                            "um orçamento para execução da manutenção do produto.",
                        ),
                        _paragrafo(
                            "Parágrafo segundo.",
                            "Fica resguardado ao COMPRADOR o direito de fazer "
                            "orçamento com um técnico de sua confiança para avaliar "
                            "o equipamento, de forma a garantir a isenção da "
                            "opinião do técnico advindo da empresa fornecedora, e, "
                            "nesta hipótese, o COMPRADOR se compromete a arcar com "
                            "os custos relacionados a essa prestação de serviços, "
                            "ficando a critério do VENDEDOR cobrir ou não o "
                            "orçamento apresentado.",
                        ),
                        _paragrafo(
                            "Parágrafo terceiro.",
                            "Caso seja executada a manutenção, conserto, montagem "
                            "ou qualquer espécie de manuseio do equipamento por "
                            "terceiros, sem que seja aprovado previamente pelo "
                            "VENDEDOR, haverá a perda imediata da garantia.",
                        ),
                    ],
                ),
                _clausula(
                    5,
                    "As despesas com frete do equipamento são por conta do COMPRADOR.",
                ),
            ],
        },
        {
            "titulo": "DA MULTA",
            "clausulas": [
                _clausula(
                    6,
                    "O presente contrato é celebrado de forma irrevogável e "
                    "irretratável, e, na hipótese de desistência ou rescisão, a "
                    "parte que der causa se responsabiliza pelo pagamento de multa "
                    "contratual no importe de 10% (dez por cento) do valor do "
                    "contrato atualizado, sem prejuízo de perdas e danos à parte "
                    "prejudicada. Resguardado o direito de desistência insculpido "
                    "no artigo 49 do CDC.",
                    paragrafos=[
                        _paragrafo(
                            "Parágrafo primeiro.",
                            "Havendo necessidade de qualquer das partes ingressar "
                            "em juízo a fim de fazer valer seus direitos, a parte "
                            "julgada culpada pagará à outra, além da multa, custas "
                            "processuais e honorários sucumbenciais, fixados em "
                            "20% (vinte por cento).",
                        ),
                    ],
                ),
            ],
        },
        {
            "titulo": "DA INADIMPLÊNCIA",
            "clausulas": [
                _clausula(
                    7,
                    "Em ocorrendo inadimplência do COMPRADOR, o VENDEDOR poderá "
                    "exigir o vencimento imediato das parcelas vincendas, sem "
                    "prejuízo da correção monetária, multa de 2% sobre o saldo "
                    "devedor remanescente e juros de 1% ao mês, até o efetivo "
                    "pagamento.",
                ),
                _clausula(
                    8,
                    "Poderá o VENDEDOR aceitar o pagamento das parcelas em atraso, "
                    "com ou sem a aplicação de multa, correção e juros, por mera "
                    "liberalidade, sem que isso configure novação, mantendo o "
                    "parcelamento outrora firmado.",
                ),
                _clausula(
                    9,
                    "Na hipótese do não cumprimento do prazo estipulado para a "
                    "entrega do equipamento pelo VENDEDOR, o COMPRADOR poderá "
                    "considerar rescindido o contrato e ser restituído dos valores "
                    "pagos, corrigidos e com juros de 1% (um por cento) ao mês, até "
                    "a efetiva entrega do equipamento, ou no máximo até o limite do "
                    "valor total do contrato.",
                ),
                _clausula(
                    10,
                    "As partes apenas poderão rescindir o presente instrumento de "
                    "pleno direito, independentemente de qualquer notificação, "
                    "interpelação judicial ou extrajudicial, se a outra parte "
                    "entrar em estado de insolvência ou se lhe for decretada a "
                    "falência por qualquer dívida que tenha contraído, ainda que "
                    "fora deste instrumento.",
                ),
            ],
        },
        {
            "titulo": "DO FORO",
            "clausulas": [
                _clausula(
                    11,
                    "Para dirimir quaisquer controvérsias oriundas do presente "
                    "instrumento, as partes elegem o foro da Comarca de São Paulo, "
                    "por mais privilegiado que outro seja.",
                ),
            ],
        },
    ]


def preambulo(vendedor: dict) -> dict:
    """A abertura (com o VENDEDOR por inteiro) e o fechamento do preâmbulo.

    Entre as duas vem o quadro do COMPRADOR (nome, CPF ou CNPJ, endereço
    completo, e-mail e telefone), como no contrato da empresa.
    """
    # O REPRESENTANTE AINDA EM BRANCO NÃO TRAVA O CONTRATO (o dono: "nem
    # precisa travar a assinatura"): sem o nome, "seu representante legal";
    # o RG e a residência entram só quando preenchidos.
    nome = vendedor.get("representante_nome") or ""
    representante = nome or "seu representante legal"
    if nome and vendedor.get("representante_rg"):
        representante += f", portador da cédula de identidade RG {vendedor['representante_rg']}"
    if nome and vendedor.get("representante_endereco"):
        representante += f", residente e domiciliado na {vendedor['representante_endereco']}"
    empresa = vendedor.get("nome_fantasia") or vendedor.get("razao_social") or "a empresa vendedora"
    partes = [empresa]
    if vendedor.get("razao_social") and vendedor.get("razao_social") != empresa:
        partes.append(f"razão social {vendedor['razao_social']}")
    if vendedor.get("cnpj"):
        partes.append(f"devidamente inscrita no CNPJ sob o n. {vendedor['cnpj']}")
    if vendedor.get("endereco_sede"):
        partes.append(f"com sede na {vendedor['endereco_sede']}")
    return {
        "abertura": (
            "Pelo presente INSTRUMENTO PARTICULAR DE COMPRA E VENDA, e na forma "
            "da Lei, comparecem aqui as partes: de um lado, na qualidade de "
            "fornecedor, doravante denominado simplesmente VENDEDOR: "
            + ", ".join(partes)
            + f", neste ato representada por {representante}; e, do outro lado, na "
            "qualidade de comprador, doravante denominado simplesmente COMPRADOR:"
        ),
        "fechamento": (
            "As partes acima identificadas têm, entre si, justo e acertado o "
            "presente instrumento de compra e venda de equipamento de "
            "entretenimento, que se regerá pelas cláusulas seguintes e pelas "
            "condições de preço, forma e termo de pagamento descritas no presente."
        ),
    }


FECHO = (
    "Por estarem assim justos e contratados, firmam o presente instrumento em "
    "duas vias de igual teor na presença de duas testemunhas."
)


# ======================================================================
# O QUE FALTA, E O RETRATO
# ======================================================================
def dados_do_vendedor(dados) -> dict:
    """Os dados do VENDEDOR copiados para o retrato (texto, sem espaço sobrando)."""
    campos = (
        "nome_fantasia", "razao_social", "cnpj", "endereco_sede", "cidade",
        "representante_nome", "representante_rg", "representante_endereco",
    )
    return {campo: " ".join((getattr(dados, campo, "") or "").split()) for campo in campos}


def pendencias(orcamento, dados=None) -> list[dict]:
    """O que IMPEDE o contrato de sair: nada.

    "A assinatura está travando... nem precisa travar a assinatura para os
    clientes." A forma de pagamento é lida do orçamento
    (`condicao_de_pagamento`) e o representante em branco vira "seu
    representante legal" (`preambulo`). O que convém completar aparece em
    `observacoes`, sem travar o botão.
    """
    return []


def observacoes(orcamento, dados=None) -> list[dict]:
    """O que convém saber antes de gerar (nada disso trava): [{"chave", "texto"}]."""
    from .models import DadosContrato

    dados = dados or DadosContrato.atual()
    saida = []
    condicao, origem = condicao_de_pagamento(orcamento)
    if origem != "escrita":
        saida.append({
            "chave": "forma",
            "texto": f"Condição de pagamento (Cláusula 2ª) {ORIGEM_DA_CONDICAO[origem]}: “{condicao}”.",
        })
    if dados.faltando:
        saida.append({
            "chave": "dados",
            "texto": (
                "Os dados do representante ainda estão em branco ("
                + ", ".join(dados.faltando)
                + "): o contrato sai com “seu representante legal”."
            ),
        })
    return saida


ORIGEM_DA_CONDICAO = {
    "escrita": "escrita no orçamento",
    "texto": "lida do texto do orçamento",
    "pagamento": "tirada do pagamento registrado",
    "padrao": "no padrão, porque o orçamento não diz",
}

#: O que indica um trecho que fala de PAGAMENTO no texto livre do orçamento.
#: "Entrada" e "na entrega" sozinhos são ambíguos ("entrada do salão"): só
#: contam com um número na mesma linha ("50% de entrada", "R$ 2.000 na entrega").
_PISTAS_DE_PAGAMENTO = re.compile(
    r"(?<!\w)(pix|boleto|cart[aã]o|cr[eé]dito|d[eé]bito|transfer[eê]ncia|dep[oó]sito|"
    r"parcelas?|parcelad[oa]|\d+\s*x|\d+\s*vezes|[aà] vista|quitad[oa]|pagamento|pagto|"
    r"\d+\s*%|r\$)(?!\w)",
    re.IGNORECASE,
)
_PISTAS_COM_NUMERO = re.compile(r"(?<!\w)(entrada|sinal|na entrega|na retirada|na instala[cç][aã]o)(?!\w)", re.IGNORECASE)
_ROTULO_DE_PAGAMENTO = re.compile(
    r"^\s*(forma|condi[cç][aãoõ]+(es)?)?\s*(de\s+)?(pagamento|pagto)\s*[:\-–]\s*",
    re.IGNORECASE,
)


def _condicao_no_texto(texto) -> str:
    """O trecho do texto livre que diz como se paga ("50% de entrada e 50% na entrega")."""
    for linha in re.split(r"[\r\n;]+|(?<=[.!?])\s+", texto or ""):
        linha = " ".join(linha.split()).strip(" -–•*")
        if len(linha) < 3:
            continue
        if not (_PISTAS_DE_PAGAMENTO.search(linha) or (_PISTAS_COM_NUMERO.search(linha) and re.search(r"\d", linha))):
            continue
        limpa = _ROTULO_DE_PAGAMENTO.sub("", linha).strip(" .:-–")
        if limpa:
            return limpa[:220]
    return ""


def condicao_de_pagamento(orcamento) -> tuple[str, str]:
    """A condição da Cláusula 2ª e de onde ela veio. NUNCA vazia.

    1. o que a equipe escreveu em "Forma de pagamento";
    2. o trecho de pagamento do texto do orçamento (observação do
       pagamento, observações, negociação) -- "50% de entrada e 50% na
       entrega", "Pix", "10x no cartão";
    3. o pagamento registrado: quitado ("à vista, quitado em 18/11/2026")
       ou com entrada (a entrada paga e o saldo até a entrega);
    4. o padrão: à vista, na confirmação do pedido.
    """
    from core.formatos import dinheiro

    escrita = " ".join((orcamento.forma_pagamento or "").split())
    if escrita:
        return escrita, "escrita"
    for campo in ("observacao_pagamento", "observacoes", "motivo_negociacao"):
        achada = _condicao_no_texto(getattr(orcamento, campo, ""))
        if achada:
            return achada, "texto"
    total = Decimal(orcamento.total or 0)
    pago = Decimal(getattr(orcamento, "valor_pago", None) or 0)
    quando = getattr(orcamento, "pago_em", None)
    em = f" em {quando:%d/%m/%Y}" if quando else ""
    if total > 0 and pago >= total:
        return f"à vista, em parcela única, quitado{em}", "pagamento"
    if pago > 0:
        return (
            f"entrada de {dinheiro(pago, prefixo='R$')} paga{em} e o saldo de {dinheiro(total - pago, prefixo='R$')} "
            "até a entrega do equipamento"
        ), "pagamento"
    return "à vista, na confirmação do pedido", "padrao"


def itens_do_contrato(orcamento) -> list[dict]:
    """As linhas do quadro e da Cláusula 1ª, com a foto e o adesivo de cada uma."""
    from core.formatos import dinheiro

    itens = []
    for item in orcamento.itens.all():
        foto, adesivo = foto_e_adesivo(item)
        itens.append({
            "descricao": item.descricao,
            "detalhes": list(item.ficha),
            "quantidade": item.quantidade,
            "valor_unitario": f"{Decimal(item.valor_unitario or 0).quantize(Decimal('0.01')):.2f}",
            "subtotal": f"{item.subtotal:.2f}",
            "valor_unitario_texto": dinheiro(item.valor_unitario),
            "foto": foto,
            "adesivo": adesivo,
            # O quadro só repete o adesivo quando o nome do item não o diz.
            "adesivo_no_nome": bool(adesivo) and _normalizar(adesivo) in _normalizar(item.descricao),
        })
    return itens


def partes_do_contrato(orcamento, dados, *, quando) -> dict:
    """O que o retrato do contrato acrescenta ao do documento.

    `quando` é o instante de gerar (a data do fecho). Tudo já escrito: o
    retrato é o papel, e a folha só o desenha.
    """
    from core.formatos import dinheiro

    vendedor = dados_do_vendedor(dados)
    total = orcamento.total
    condicao, _origem = condicao_de_pagamento(orcamento)
    prazo = _prazo(orcamento)
    return {
        "tipo": TIPO,
        "titulo": TITULO,
        "titulo_curto": TITULO_CURTO,
        "vendedor": vendedor,
        "preambulo": preambulo(vendedor),
        "prazo": prazo,
        "valor_total_texto": dinheiro(total),
        "valor_total_extenso": reais_por_extenso(total),
        "condicao_pagamento": condicao,
        "secoes": secoes(
            valor_total=dinheiro(total),
            valor_extenso=reais_por_extenso(total),
            condicao=condicao,
            prazo=prazo,
        ),
        "fecho": FECHO,
        "local_data": f"{vendedor['cidade']}, {data_por_extenso(quando.date())}",
    }


def e_contrato(conteudo) -> bool:
    """O retrato é deste contrato (e não do termo de compra de antes)?"""
    return (conteudo or {}).get("tipo") == TIPO
