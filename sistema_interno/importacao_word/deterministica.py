"""O que dá para ler por regra, sem IA -- e é por isso que se confia.

Esta camada roda SEMPRE. Com a IA ligada, ela é a régua que confere a IA;
sem a chave, ela é a leitura inteira. Duas regras valem para tudo aqui:

  1. Dinheiro é Decimal desde o primeiro caractere. Nada passa por float,
     e nada é arredondado: um valor com três casas ("12,345") não vira
     12,35 -- vira "não sei ler", e a pessoa decide.
  2. Na dúvida, não lê. "R$ 1,2 mil", "mil e duzentos" e "1,234" ficam de
     fora com o motivo, em vez de virarem um número que alguém vai
     confiar sem conferir.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from core.arena import _normalizar

from ..validacoes import (
    chave_documento,
    cnpj_valido,
    cpf_valido,
    somente_digitos,
    telefone_valido,
)

CENTAVO = Decimal("0.01")


# ======================================================================
# TEXTO
# ======================================================================
def sem_acento(texto: str) -> str:
    """Minúsculas e sem acento, MESMO TAMANHO do original.

    `_normalizar` (core/arena.py) é o certo para comparar nomes, mas ele
    funde pontuação e muda o comprimento do texto. Aqui a posição de cada
    letra precisa continuar a mesma, para que o rótulo achado no texto
    sem acento aponte o valor certo no texto original.
    """
    saida = []
    for caractere in str(texto or ""):
        base = unicodedata.normalize("NFD", caractere)[0].lower()
        saida.append(base if len(base) == 1 else caractere)
    return "".join(saida)


def espacos(texto: str) -> str:
    return re.sub(r"\s+", " ", str(texto or "")).strip()


# ======================================================================
# DINHEIRO
# ======================================================================
def ler_dinheiro(texto) -> Decimal | None:
    """Um valor escrito em reais -> Decimal com duas casas. Ou None.

    Aceita o que se escreve no Brasil e o que chega colado de sistema
    estrangeiro, desde que não haja dúvida:

        "R$ 1.234,56"  "1234,56"  "R$ 1.234"  "80"  "0,5"  "1,234.56"

    E recusa o que tem duas leituras possíveis ou nenhuma:

        "1,234"   (mil duzentos e trinta e quatro, ou um vírgula dois três quatro?)
        "12,345"  (três casas: arredondar seria inventar um centavo)
        "mil e duzentos"  (por extenso não é número para conta)

    "1.234" é milhar, sempre -- é assim que se lê em português, e é o
    erro clássico de quem converte com `Decimal("1.234")` e grava R$ 1,23.
    """
    if texto is None:
        return None
    bruto = str(texto).strip()
    bruto = re.sub(r"(?i)\bR\$|\bBRL\b|\breais\b|\breal\b", "", bruto)
    bruto = re.sub(r"[\s ]", "", bruto).lstrip("+")
    if not bruto:
        return None

    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+,\d{1,2}", bruto):
        numero = bruto.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d+,\d{1,2}", bruto):
        numero = bruto.replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", bruto):
        numero = bruto.replace(".", "")
    elif re.fullmatch(r"\d+", bruto):
        numero = bruto
    elif re.fullmatch(r"\d{1,3}(?:,\d{3})+\.\d{1,2}", bruto):
        numero = bruto.replace(",", "")
    elif re.fullmatch(r"\d+\.\d{1,2}", bruto):
        numero = bruto
    else:
        return None

    try:
        valor = Decimal(numero)
    except InvalidOperation:
        return None
    # Até duas casas por construção (as expressões acima não deixam passar
    # mais), então este quantize só completa zeros -- nunca arredonda.
    return valor.quantize(CENTAVO)


_CANDIDATO_DINHEIRO = re.compile(
    r"(?P<rs>R\$\s*)?(?P<num>\d[\d.,]*\d|\d)(?P<depois>\s*(?:%|mil\b|milh|bilh|k\b))?",
    re.IGNORECASE,
)


def valores_em_reais(texto: str, *, coluna_de_dinheiro: bool = False) -> list[dict]:
    """Cada valor em reais que aparece no texto, com a posição.

    Fora de uma coluna de dinheiro, só conta como valor o que TEM CARA de
    valor: "R$" na frente ou centavos com vírgula ("280,00"). Assim o
    "3" de "cama 3 m", o "2026" da data e os pedaços do CPF não viram
    dinheiro. Dentro da coluna "Valor unitário" de uma tabela, "280" é
    duzentos e oitenta reais.

    Percentual não é dinheiro, e valor abreviado ("1,2 mil", "5k") não é
    lido: vem marcado como recusado, para a conferência avisar.
    """
    achados = []
    for achado in _CANDIDATO_DINHEIRO.finditer(texto or ""):
        numero = achado.group("num")
        depois = (achado.group("depois") or "").strip().lower()
        antes = (texto[max(0, achado.start() - 1):achado.start()] or "")
        if antes and (antes.isalnum() or antes in "/-"):
            # Pedaço de outra coisa: "T1", "nº3", "11/2026", "123-45".
            continue
        com_rs = bool(achado.group("rs"))
        if depois.startswith("%"):
            continue
        tem_centavos = bool(re.search(r",\d{2}$", numero))
        if not (com_rs or tem_centavos or coluna_de_dinheiro):
            continue
        valor = ler_dinheiro(numero)
        recusa = ""
        if depois and not depois.startswith("%"):
            valor, recusa = None, "valor abreviado (mil, milhão, k): escreva o número inteiro"
        elif valor is None:
            recusa = "formato ambíguo: não dá para saber onde estão os centavos"
        achados.append({
            "valor": valor,
            "texto": achado.group(0).strip(),
            "inicio": achado.start(),
            "fim": achado.end(),
            "com_rs": com_rs,
            "recusa": recusa,
        })
    return achados


def primeiro_valor(texto: str, *, coluna_de_dinheiro: bool = False):
    for achado in valores_em_reais(texto, coluna_de_dinheiro=coluna_de_dinheiro):
        if achado["valor"] is not None:
            return achado
    return None


def moeda(valor) -> str:
    """Decimal -> "1.234,56" (o formato do campo de dinheiro do painel)."""
    if valor is None:
        return ""
    numero = Decimal(valor).quantize(CENTAVO)
    return f"{numero:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def valor_do_campo(texto) -> Decimal | None:
    """O que a pessoa digitou no campo de dinheiro da conferência."""
    texto = (texto or "").strip()
    if not texto:
        return None
    achado = primeiro_valor(texto, coluna_de_dinheiro=True)
    if not achado:
        return None
    # O campo inteiro tem de ser o número: "150,00 por km" não é 150.
    resto = (texto[:achado["inicio"]] + texto[achado["fim"]:]).strip()
    if resto and resto not in ("R$",):
        return None
    return achado["valor"]


# ======================================================================
# QUANTIDADE
# ======================================================================
UNIDADES = {
    "un": "un", "und": "un", "unid": "un", "unidade": "un", "unidades": "un",
    "pc": "pç", "pcs": "pç", "pç": "pç", "pçs": "pç", "peca": "pç", "pecas": "pç",
    "x": "un", "kit": "kit", "kits": "kit", "cx": "cx", "caixa": "cx", "caixas": "cx",
    "diaria": "diária", "diarias": "diária", "dia": "dia", "dias": "dia",
    "hora": "h", "horas": "h", "h": "h", "jogo": "jogo", "jogos": "jogo",
    "par": "par", "pares": "par", "conjunto": "cj", "conjuntos": "cj", "cj": "cj",
    "m": "m", "m2": "m²", "m²": "m²", "metro": "m", "metros": "m",
}


def ler_quantidade(texto) -> tuple[int | None, str, str]:
    """(quantidade inteira, unidade, motivo da recusa).

    A linha do orçamento guarda quantidade INTEIRA (ItemOrcamento usa
    PositiveIntegerField). "1,5 m²" não é arredondado para 2: volta como
    recusado, e a pessoa decide se cobra por unidade ou ajusta o preço.
    """
    bruto = espacos(texto)
    if not bruto:
        return None, "", ""
    sem = sem_acento(bruto)
    numeros = re.findall(r"\d+(?:[.,]\d+)*", sem)
    if not numeros:
        return None, "", "não há número na quantidade"
    if len(numeros) > 1:
        return None, "", f"duas quantidades no mesmo campo (“{bruto}”)"
    numero = numeros[0]
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", numero):
        inteiro = int(numero.replace(".", ""))
    elif re.fullmatch(r"\d+", numero):
        inteiro = int(numero)
    else:
        try:
            decimal = Decimal(numero.replace(".", "").replace(",", ".") if "," in numero else numero)
        except InvalidOperation:
            return None, "", f"quantidade ilegível (“{bruto}”)"
        if decimal != decimal.to_integral_value():
            return None, "", (
                f"quantidade fracionária (“{bruto}”): o orçamento só aceita "
                "quantidade inteira"
            )
        inteiro = int(decimal)
    if inteiro <= 0:
        return None, "", "quantidade zero"
    resto = re.sub(r"\d+(?:[.,]\d+)*", " ", sem)
    unidade = ""
    for palavra in re.findall(r"[a-z²0-9]+", resto):
        if palavra in UNIDADES:
            unidade = UNIDADES[palavra]
            break
    return inteiro, unidade, ""


# ======================================================================
# DOCUMENTO, TELEFONE, E-MAIL
# ======================================================================
_CPF = re.compile(r"(?<![\w./-])\d{3}\.\d{3}\.\d{3}-\d{2}(?![\w/-])")
_CNPJ = re.compile(
    r"(?<![\w./-])[0-9A-Z]{2}\.[0-9A-Z]{3}\.[0-9A-Z]{3}/[0-9A-Z]{4}-\d{2}(?![\w/-])"
)
_DOCUMENTO_CRU = re.compile(r"(?<![\w])(\d{11}|[0-9A-Z]{12}\d{2})(?![\w])")
_ROTULO_DOCUMENTO = re.compile(r"(?i)\b(cpf|cnpj|documento)\b")

_TELEFONE = re.compile(
    r"(?<![\d])(?:\+?\s?55[\s.-]?)?(?:\(\s?\d{2}\s?\)|\d{2})[\s.-]?9?\s?\d{4}[\s.-]?\d{4}(?![\d])"
)
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")


def formatar_documento(valor: str) -> str:
    """CPF e CNPJ como a máscara do painel escreve (painel.js, "documento")."""
    chave = chave_documento(valor)
    if len(chave) == 11 and chave.isdigit():
        return f"{chave[:3]}.{chave[3:6]}.{chave[6:9]}-{chave[9:]}"
    if len(chave) == 14:
        return f"{chave[:2]}.{chave[2:5]}.{chave[5:8]}/{chave[8:12]}-{chave[12:]}"
    return (valor or "").strip()


def documentos(texto: str) -> list[dict]:
    """CPF/CNPJ no texto, já conferidos pelos dígitos verificadores.

    Formatado ("123.456.789-09") vale em qualquer lugar. Só dígitos
    ("12345678909") só vale ao lado do rótulo CPF/CNPJ: onze dígitos
    soltos é, quase sempre, um celular com DDD.
    """
    achados = []
    ocupado = []
    for padrao, tipo in ((_CNPJ, "CNPJ"), (_CPF, "CPF")):
        for achado in padrao.finditer(texto or ""):
            chave = chave_documento(achado.group(0))
            valido = cnpj_valido(chave) if tipo == "CNPJ" else cpf_valido(chave)
            achados.append({
                "texto": achado.group(0), "chave": chave, "tipo": tipo,
                "valido": valido, "inicio": achado.start(), "fim": achado.end(),
            })
            ocupado.append((achado.start(), achado.end()))
    if _ROTULO_DOCUMENTO.search(texto or ""):
        for achado in _DOCUMENTO_CRU.finditer(texto or ""):
            if any(a <= achado.start() < b for a, b in ocupado):
                continue
            chave = chave_documento(achado.group(0))
            tipo = "CPF" if len(chave) == 11 else "CNPJ"
            valido = cpf_valido(chave) if tipo == "CPF" else cnpj_valido(chave)
            achados.append({
                "texto": achado.group(0), "chave": chave, "tipo": tipo,
                "valido": valido, "inicio": achado.start(), "fim": achado.end(),
            })
    return sorted(achados, key=lambda a: a["inicio"])


def digitos_do_telefone(valor: str) -> str:
    """Só os dígitos, sem o 55 do país: é a forma de comparar dois números."""
    numero = somente_digitos(valor)
    if numero.startswith("55") and len(numero) in (12, 13):
        numero = numero[2:]
    return numero


def formatar_telefone(valor: str) -> str:
    """"(11) 99999-9999", como a máscara de telefone do painel escreve.

    O 55 do país sai: todo cadastro do painel está sem ele, e o envio por
    WhatsApp o acrescenta sozinho. Dois jeitos de escrever o mesmo número
    fariam a busca por telefone deixar de achar o cliente.
    """
    numero = digitos_do_telefone(valor)
    if len(numero) == 11:
        return f"({numero[:2]}) {numero[2:7]}-{numero[7:]}"
    if len(numero) == 10:
        return f"({numero[:2]}) {numero[2:6]}-{numero[6:]}"
    return (valor or "").strip()


def telefones(texto: str) -> list[dict]:
    achados = []
    for achado in _TELEFONE.finditer(texto or ""):
        if not telefone_valido(achado.group(0)):
            continue
        achados.append({
            "texto": achado.group(0).strip(),
            "digitos": digitos_do_telefone(achado.group(0)),
            "inicio": achado.start(), "fim": achado.end(),
        })
    return achados


def emails(texto: str) -> list[dict]:
    return [
        {"texto": a.group(0), "email": a.group(0).lower(), "inicio": a.start(), "fim": a.end()}
        for a in _EMAIL.finditer(texto or "")
    ]


# ======================================================================
# DATAS E VALIDADE
# ======================================================================
MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}
_DATA_NUMERICA = re.compile(r"(?<!\d)(\d{1,2})[/.-](\d{1,2})[/.-](\d{4}|\d{2})(?!\d)")
_DATA_EXTENSO = re.compile(
    r"(?<!\d)(\d{1,2})\s+de\s+(" + "|".join(MESES) + r")\s+de\s+(\d{4})"
)
_PRAZO_EM_DIAS = re.compile(r"(?<!\d)(\d{1,3})\s*(?:\([^)]*\)\s*)?dias?(\s+uteis)?")


def datas(texto: str) -> list[dict]:
    achados = []
    sem = sem_acento(texto or "")
    for achado in _DATA_NUMERICA.finditer(sem):
        dia, mes, ano = (int(achado.group(i)) for i in (1, 2, 3))
        if ano < 100:
            ano += 2000
        try:
            achados.append({"data": date(ano, mes, dia), "texto": texto[achado.start():achado.end()],
                            "inicio": achado.start()})
        except ValueError:
            continue
    for achado in _DATA_EXTENSO.finditer(sem):
        try:
            achados.append({
                "data": date(int(achado.group(3)), MESES[achado.group(2)], int(achado.group(1))),
                "texto": texto[achado.start():achado.end()], "inicio": achado.start(),
            })
        except ValueError:
            continue
    return sorted(achados, key=lambda a: a["inicio"])


def somar_dias_uteis(inicio: date, dias: int) -> date:
    atual = inicio
    restantes = dias
    while restantes > 0:
        atual += timedelta(days=1)
        if atual.weekday() < 5:
            restantes -= 1
    return atual


def ler_validade(texto: str, *, data_documento: date | None, hoje: date) -> dict | None:
    """"15 dias", "até 30/11/2026", "30 de novembro de 2026" -> uma data.

    O prazo em dias conta da data do documento quando ela está escrita
    (é a leitura de quem emitiu: "vale 15 dias a partir de hoje", e o
    hoje dele era o dia do documento). Sem data no documento, conta de
    hoje -- e a tela diz qual das duas contas foi feita.
    """
    if not texto:
        return None
    achadas = datas(texto)
    if achadas:
        return {"data": achadas[0]["data"], "como": f"data escrita no documento ({achadas[0]['texto']})"}
    prazo = _PRAZO_EM_DIAS.search(sem_acento(texto))
    if not prazo:
        return None
    dias = int(prazo.group(1))
    if dias <= 0:
        return None
    base = data_documento or hoje
    origem = "da data do documento" if data_documento else "de hoje"
    if prazo.group(2):
        return {"data": somar_dias_uteis(base, dias),
                "como": f"{dias} dias úteis contados {origem} ({base:%d/%m/%Y})"}
    return {"data": base + timedelta(days=dias),
            "como": f"{dias} dias contados {origem} ({base:%d/%m/%Y})"}


# ======================================================================
# FORMA DE PAGAMENTO E DE ENVIO
# ======================================================================
TERMOS_DE_PAGAMENTO = (
    (r"\bpix\b", "Pix"),
    (r"\bboletos?(?: bancarios?)?\b", "boleto"),
    (r"\bcartao de credito\b", "cartão de crédito"),
    (r"\bcartao de debito\b", "cartão de débito"),
    (r"\bdinheiro\b|\bespecie\b", "dinheiro"),
    (r"\btransferencia(?: bancaria)?\b|\bted\b", "transferência bancária"),
    (r"\bdeposito(?: bancario)?\b", "depósito bancário"),
)

#: As formas que o painel sugere no campo, com a grafia da casa. Os dois
#: exemplos do próprio formulário de orçamento vêm primeiro.
OPCOES_DE_PAGAMENTO = (
    "Pix",
    "50% na entrada e 50% na entrega",
    "Boleto",
    "Cartão de crédito",
    "Cartão de débito",
    "Transferência bancária",
    "Dinheiro",
)
OPCOES_DE_ENVIO = (
    "Retirada pelo cliente",
    "Transportadora",
    "Entrega Lazer & Sport",
)


def normalizar_pagamento(texto: str, existentes=()) -> str:
    """A forma de pagamento escrita com a grafia que o painel já usa.

    Primeiro procura entre as formas já usadas nas propostas e as do
    painel (sem acento e sem caixa): achou, usa a grafia de lá. Não
    achou, corrige só a grafia dos termos conhecidos ("PIX" vira "Pix",
    "cartao de credito" vira "cartão de crédito") e mantém o resto como
    estava -- trocar "50% na entrada" por uma opção de lista apagaria a
    condição combinada.
    """
    bruto = espacos(texto).strip(" .;")
    if not bruto:
        return ""
    chave = _normalizar(bruto)
    for opcao in list(existentes) + list(OPCOES_DE_PAGAMENTO):
        if opcao and _normalizar(opcao) == chave:
            return opcao
    resultado = bruto
    sem = sem_acento(resultado)
    for padrao, grafia in TERMOS_DE_PAGAMENTO:
        partes = []
        ultimo = 0
        for achado in re.finditer(padrao, sem):
            partes.append(resultado[ultimo:achado.start()])
            partes.append(grafia)
            ultimo = achado.end()
        if partes:
            partes.append(resultado[ultimo:])
            resultado = "".join(partes)
            sem = sem_acento(resultado)
    return resultado[:1].upper() + resultado[1:]


def normalizar_envio(texto: str, existentes=()) -> str:
    bruto = espacos(texto).strip(" .;")
    if not bruto:
        return ""
    chave = _normalizar(bruto)
    for opcao in list(existentes) + list(OPCOES_DE_ENVIO):
        if opcao and _normalizar(opcao) == chave:
            return opcao
    sem = sem_acento(bruto)
    if re.fullmatch(r"(retirada|retirar)( pelo cliente| no local| na fabrica)?", sem):
        return "Retirada pelo cliente"
    if re.fullmatch(r"(via )?transportadora", sem):
        return "Transportadora"
    return bruto[:1].upper() + bruto[1:]


# ======================================================================
# RÓTULOS: "Frete: R$ 150,00", "CPF | 123.456.789-09"
# ======================================================================
ROTULOS = {
    "cliente": ("cliente", "nome do cliente", "razao social", "contratante", "nome",
                "destinatario", "sr", "sra", "sr a", "empresa", "proposta para", "para"),
    "contato": ("contato", "a c", "aos cuidados", "aos cuidados de", "responsavel",
                "att", "attn", "solicitante"),
    "documento": ("cpf", "cnpj", "cpf cnpj", "cnpj cpf", "documento", "cpf ou cnpj"),
    "telefone": ("telefone", "tel", "fone", "celular", "cel", "whatsapp", "whats",
                 "telefone whatsapp", "contato telefonico"),
    "email": ("e mail", "email"),
    "endereco": ("endereco", "end", "endereco de entrega", "local de entrega",
                 "local do evento", "local"),
    "cep": ("cep",),
    "bairro": ("bairro",),
    "cidade": ("cidade", "municipio", "cidade uf"),
    "uf": ("uf", "estado"),
    "validade": ("validade", "validade da proposta", "validade do orcamento",
                 "proposta valida ate", "valido ate", "valida ate", "proposta valida por",
                 "orcamento valido por", "orcamento valido ate"),
    "forma_pagamento": ("forma de pagamento", "formas de pagamento", "condicoes de pagamento",
                        "condicao de pagamento", "pagamento", "forma pagamento",
                        "condicoes", "condicoes comerciais"),
    "prazo": ("prazo de entrega", "prazo", "prazo de fabricacao", "prazo de producao",
              "previsao de entrega", "prazo de montagem", "prazo de execucao"),
    "forma_envio": ("forma de envio", "envio", "transporte", "modalidade de entrega",
                    "tipo de frete", "forma de entrega"),
    "frete": ("frete", "valor do frete", "taxa de entrega", "entrega", "frete e montagem"),
    "desconto": ("desconto", "desc", "descontos"),
    "subtotal": ("subtotal", "sub total", "total dos itens", "total dos produtos",
                 "valor dos itens", "total parcial", "soma dos itens"),
    "total": ("total", "total geral", "valor total", "total do orcamento",
              "total da proposta", "valor final", "total a pagar", "investimento",
              "investimento total", "valor total da proposta", "total final",
              "valor total negociado", "total negociado", "valor negociado", "valor fechado",
              "valor combinado", "valor final combinado", "valor final negociado"),
    "data": ("data", "data do orcamento", "data de emissao", "emissao", "emitido em"),
    "observacoes": ("observacoes", "observacao", "obs", "garantia", "condicoes gerais",
                    "informacoes adicionais"),
}
_ROTULO_POR_TEXTO = {
    rotulo: campo for campo, rotulos in ROTULOS.items() for rotulo in rotulos
}
#: Campos de dinheiro que um rótulo pode abrir no meio de uma linha corrida:
#: "Subtotal R$ 1.200,00 | Frete R$ 50,00 | Total R$ 1.250,00".
_ROTULO_DINHEIRO = re.compile(
    r"\b(sub\s*-?\s*total|total\s+geral|valor\s+total(?:\s+negociado)?|total\s+do\s+orcamento|"
    r"total\s+da\s+proposta|total\s+a\s+pagar|valor\s+final(?:\s+(?:combinado|negociado))?|"
    r"total\s+negociado|valor\s+(?:negociado|fechado|combinado)|total|frete|desconto)\b"
)
_CAMPO_DO_ROTULO_DINHEIRO = {
    "frete": "frete", "desconto": "desconto",
}


def campo_do_rotulo(rotulo: str) -> str:
    """"Valor total (R$)" e "Desconto (10%)" são os rótulos "valor total" e "desconto"."""
    sem_parenteses = re.sub(r"\([^)]*\)", " ", rotulo or "")
    return _ROTULO_POR_TEXTO.get(_normalizar(sem_parenteses), "")


def _par_rotulo_valor(texto: str):
    """"Rótulo: valor" -> (campo, valor, posição do valor). Ou None."""
    achado = re.match(r"^\s*([^:\n]{1,42}?)\s*[:：]\s*(.+)$", texto)
    if not achado:
        return None
    campo = campo_do_rotulo(achado.group(1))
    if not campo:
        return None
    return campo, achado.group(2).strip(), achado.start(2)


def _segmentos_de_dinheiro(texto: str):
    """Rótulos de dinheiro numa linha e o primeiro valor depois de cada um.

    O rótulo só vale no COMEÇO da linha ou depois de um separador ("|",
    ";", "•"). No meio de uma frase ele é outra coisa: "Cama elástica com
    frete incluso R$ 280,00" é um item, e ler o frete ali faria o frete
    custar o preço da cama.
    """
    sem = sem_acento(texto)
    rotulos = []
    for achado in _ROTULO_DINHEIRO.finditer(sem):
        antes = sem[:achado.start()].rstrip()
        if antes and antes[-1] not in "|;•·–-":
            continue
        rotulos.append(achado)
    segmentos = []
    for posicao, achado in enumerate(rotulos):
        fim = rotulos[posicao + 1].start() if posicao + 1 < len(rotulos) else len(texto)
        trecho = texto[achado.end():fim]
        palavra = re.sub(r"\s+", " ", achado.group(1))
        if palavra.startswith("sub"):
            campo = "subtotal"
        else:
            campo = _CAMPO_DO_ROTULO_DINHEIRO.get(palavra, "total")
        segmentos.append((campo, trecho, achado.end(), texto[achado.start():fim]))
    return segmentos


FRETE_SEM_CUSTO = re.compile(
    r"\b(gratis|gratuito|incluso|inclusos|incluido|incluida|cortesia|sem custo|"
    r"sem frete|isento|cif|por nossa conta)\b"
)
FRETE_DO_CLIENTE = re.compile(
    r"\b(por conta do cliente|por conta do comprador|fob|a cargo do cliente|"
    r"o cliente retira|retirada)\b"
)
FRETE_A_COMBINAR = re.compile(r"\b(a combinar|a calcular|a consultar|sob consulta|a definir)\b")


def _campo(valor, linha, *, texto_original, motivo="", extra=None):
    """A forma única de um valor achado: o quê, onde, e escrito como."""
    resultado = {
        "valor": valor,
        "original": texto_original,
        "fonte": {"id": linha["id"], "texto": linha["texto"]},
        "motivo": motivo,
    }
    if extra:
        resultado.update(extra)
    return resultado


# ======================================================================
# TABELAS DE ITENS
# ======================================================================
CABECALHOS = {
    "descricao": ("descricao", "descricao do item", "descricao dos itens", "produto",
                  "produtos", "servico", "servicos", "equipamento", "equipamentos",
                  "brinquedo", "brinquedos", "material", "especificacao", "discriminacao",
                  "itens", "item descricao", "descricao produto", "nome", "modelo"),
    "item": ("item", "n", "no", "num", "numero", "cod", "codigo", "ref", "referencia"),
    "quantidade": ("qtd", "qtde", "qt", "qde", "quant", "quantidade", "quantidades", "qtd."),
    "unidade": ("un", "und", "unid", "unidade", "medida"),
    "valor_unitario": ("valor unitario", "vlr unitario", "vl unitario", "unitario",
                       "preco unitario", "valor unit", "vlr unit", "v unit", "preco unit",
                       "valor", "preco", "valor un", "vlr un", "preco un", "unit",
                       "valor por unidade", "preco por unidade", "valor da diaria"),
    "total": ("total", "valor total", "vlr total", "vl total", "preco total", "subtotal",
              "total item", "total do item", "valor final", "total r"),
}
_CABECALHO_POR_TEXTO = {
    rotulo: campo for campo, rotulos in CABECALHOS.items() for rotulo in rotulos
}
LINHA_DE_RESUMO = re.compile(
    r"^(sub\s?total|total|valor total|total geral|frete|desconto|descontos|entrega|"
    r"taxa de entrega|soma|total a pagar|valor final|investimento)\b"
)


def _coluna_do_cabecalho(texto: str) -> str:
    chave = _normalizar(texto)
    chave = re.sub(r"\br s\b|\brs\b", "", chave).strip()
    if chave in _CABECALHO_POR_TEXTO:
        return _CABECALHO_POR_TEXTO[chave]
    # "Valor unitário (R$)", "Qtd. de diárias", "Total do item em R$".
    for rotulo, campo in sorted(_CABECALHO_POR_TEXTO.items(), key=lambda par: -len(par[0])):
        if len(rotulo) > 3 and (chave.startswith(rotulo + " ") or chave.endswith(" " + rotulo)):
            return campo
    return ""


def _mapear_cabecalho(celulas: dict[int, dict]) -> dict[str, int] | None:
    colunas: dict[str, int] = {}
    for coluna, celula in sorted(celulas.items()):
        campo = _coluna_do_cabecalho(celula["texto"])
        if campo and campo not in colunas:
            colunas[campo] = coluna
    # "Item" sozinho é a descrição; ao lado de "Descrição" é o número.
    if "descricao" not in colunas and "item" in colunas:
        colunas["descricao"] = colunas.pop("item")
    if "descricao" not in colunas:
        return None
    if not ({"valor_unitario", "total", "quantidade"} & colunas.keys()):
        return None
    # "Valor" sozinho com "Total" ao lado é o unitário; sem "Total", e com
    # quantidade, continua ambíguo e quem decide é a conta qtd x valor.
    return colunas


def tabelas_de_itens(linhas: list[dict]) -> tuple[list[dict], dict, list[dict]]:
    """Itens, linhas de resumo (subtotal, frete...) e alertas das tabelas.

    A tabela de itens é reconhecida pelo CABEÇALHO, não pela posição: a
    primeira linha (ou uma das três primeiras, porque modelo de orçamento
    costuma ter um título mesclado em cima) precisa ter uma coluna de
    descrição e pelo menos uma de quantidade ou valor. Tabela sem isso é
    diagramação -- dados do cliente, assinatura -- e fica para os rótulos.

    As linhas "Subtotal", "Frete", "Desconto" e "Total" que costumam
    fechar a tabela NÃO são itens: viram os valores de resumo, com a
    célula de onde saíram.
    """
    por_tabela: dict[str, dict[int, dict[int, dict]]] = {}
    for linha in linhas:
        if linha["tabela"] and linha["parte"] in ("corpo", "caixa"):
            por_tabela.setdefault(linha["tabela"], {}).setdefault(linha["linha"], {})[linha["coluna"]] = linha

    itens: list[dict] = []
    resumo: dict[str, dict] = {}
    alertas: list[dict] = []
    for id_tabela, linhas_tabela in por_tabela.items():
        numeros = sorted(linhas_tabela)
        colunas = None
        inicio = None
        for numero in numeros[:3]:
            colunas = _mapear_cabecalho(linhas_tabela[numero])
            if colunas:
                inicio = numero
                break
        if not colunas:
            continue

        colunas_de_dinheiro = {colunas.get("valor_unitario"), colunas.get("total")} - {None}
        for numero in numeros:
            if numero <= inicio:
                continue
            celulas = linhas_tabela[numero]
            id_linha = f"{id_tabela}L{numero}"
            celula_descricao = celulas.get(colunas["descricao"])
            texto_descricao = celula_descricao["texto"] if celula_descricao else ""
            # Linha de resumo: o rótulo pode estar na coluna da descrição
            # ou na primeira célula preenchida (a mesclada da esquerda).
            primeira = celulas[min(celulas)] if celulas else None
            rotulo = sem_acento(texto_descricao or (primeira["texto"] if primeira else ""))
            rotulo = rotulo.strip(" :.-")
            celula_qtd = celulas.get(colunas.get("quantidade"))
            com_quantidade = bool(celula_qtd and ler_quantidade(celula_qtd["texto"])[0])
            # "Entrega e montagem | 1 | R$ 300,00" é serviço cobrado na
            # linha, com quantidade: é item. "Frete | | R$ 150,00", sem
            # quantidade, é o resumo. "Total" é sempre resumo, mesmo com a
            # soma das quantidades ao lado.
            eh_resumo = LINHA_DE_RESUMO.match(rotulo) and (
                not com_quantidade
                or re.fullmatch(r"(sub\s?total|total( geral)?|valor total)\W*", rotulo)
            )
            if eh_resumo:
                dinheiro = None
                for coluna in sorted(celulas, reverse=True):
                    achado = primeiro_valor(celulas[coluna]["texto"], coluna_de_dinheiro=True)
                    if achado:
                        dinheiro = (achado, celulas[coluna])
                        break
                campo = _campo_do_resumo(rotulo)
                if campo == "frete" and dinheiro is None and FRETE_SEM_CUSTO.search(rotulo):
                    resumo.setdefault(campo, _campo(
                        Decimal("0.00"), primeira, texto_original=primeira["texto"],
                        motivo="frete sem custo escrito no documento",
                    ))
                elif dinheiro and campo not in resumo:
                    achado, celula = dinheiro
                    resumo[campo] = _campo(achado["valor"], celula, texto_original=achado["texto"])
                continue

            if not texto_descricao:
                # Linha sem descrição: espaço em branco da tabela, ou um
                # valor solto -- que a conferência aponta como não usado.
                continue

            item = {
                "linha_fonte": id_linha,
                "descricao": _campo(texto_descricao, celula_descricao, texto_original=texto_descricao),
                "quantidade": None,
                "valor_unitario": None,
                "total_linha": None,
                "unidade": "",
                "recusas": [],
                "contexto": "tabela",
            }
            celula_quantidade = celulas.get(colunas.get("quantidade"))
            if celula_quantidade:
                quantidade, unidade, recusa = ler_quantidade(celula_quantidade["texto"])
                if quantidade is not None:
                    item["quantidade"] = _campo(quantidade, celula_quantidade,
                                                texto_original=celula_quantidade["texto"])
                    item["unidade"] = unidade
                elif recusa:
                    item["recusas"].append(("quantidade", recusa, celula_quantidade))
            celula_unidade = celulas.get(colunas.get("unidade"))
            if celula_unidade and not item["unidade"]:
                item["unidade"] = UNIDADES.get(_normalizar(celula_unidade["texto"]), "")

            for campo in ("valor_unitario", "total"):
                celula = celulas.get(colunas.get(campo))
                if not celula:
                    continue
                achados = [a for a in valores_em_reais(celula["texto"], coluna_de_dinheiro=True)]
                validos = [a for a in achados if a["valor"] is not None]
                destino = "total_linha" if campo == "total" else campo
                if len(validos) == 1:
                    item[destino] = _campo(validos[0]["valor"], celula, texto_original=validos[0]["texto"])
                elif len(validos) > 1:
                    item["recusas"].append((destino, "mais de um valor na mesma célula", celula))
                elif achados:
                    item["recusas"].append((destino, achados[0]["recusa"], celula))
            itens.append(item)

        if not any(i["linha_fonte"].startswith(id_tabela + "L") for i in itens) and not colunas_de_dinheiro:
            alertas.append({
                "tipo": "tabela_sem_valores",
                "detalhe": f"A tabela {id_tabela} parece ser de itens, mas não tem coluna de valores.",
            })
    return itens, resumo, alertas


def _campo_do_resumo(rotulo: str) -> str:
    if re.match(r"sub\s?total|soma", rotulo):
        return "subtotal"
    if rotulo.startswith(("frete", "entrega", "taxa de entrega")):
        return "frete"
    if rotulo.startswith("desconto"):
        return "desconto"
    return "total"


# ======================================================================
# ITENS EM PARÁGRAFO (só quando a IA não está disponível)
# ======================================================================
_ITEM_EM_PARAGRAFO = re.compile(
    r"^\s*(?:[-•*·–]\s*|\d{1,2}[).]\s+)?"
    r"(?:(?P<qtd>\d{1,4})\s*(?:x|un\.?|unid\.?|unidades?|pcs?\.?|pecas?|diarias?)\s+(?:de\s+)?)?"
    r"(?P<desc>[^\d\s].*?)"
)


def itens_em_paragrafos(linhas: list[dict]) -> list[dict]:
    """Linhas de parágrafo com cara de item: descrição e um valor.

    É a leitura mais frágil de todas e fica marcada assim: só entra quando
    não há tabela de itens e a IA não está disponível, e cada item sai com
    confiança baixa para a pessoa conferir. Com dois valores na linha, o
    primeiro é o unitário e o segundo o total; com um só e "cada" ao
    lado, é o unitário; com um só, é o total da linha.
    """
    itens = []
    for linha in linhas:
        if linha["tabela"] or linha["parte"] not in ("corpo", "caixa"):
            continue
        texto = linha["texto"]
        sem = sem_acento(texto).strip(" -•*·–")
        if LINHA_DE_RESUMO.match(sem) or _par_rotulo_valor(texto):
            continue
        if re.search(r"\b(pagamento|parcela|entrada|sinal|validade|prazo|pix|boleto|cpf|cnpj)\b", sem):
            continue
        valores = [v for v in valores_em_reais(texto) if v["valor"] is not None]
        if not valores or len(valores) > 2:
            continue
        descricao_bruta = texto[:valores[0]["inicio"]]
        achado = _ITEM_EM_PARAGRAFO.match(sem_acento(descricao_bruta))
        if not achado or not achado.group("desc"):
            continue
        inicio_desc = achado.start("desc")
        descricao = descricao_bruta[inicio_desc:].strip(" -–—:.…=")
        descricao = re.sub(r"[.…_]{3,}$", "", descricao).strip(" -–—:")
        if len(_normalizar(descricao)) < 3:
            continue
        quantidade = int(achado.group("qtd")) if achado.group("qtd") else None
        unitario = total = None
        if len(valores) == 2:
            unitario, total = valores
        elif re.search(r"\b(cada|unitario|/\s*un|por unidade|a unidade)\b", sem):
            unitario = valores[0]
        else:
            total = valores[0]
        itens.append({
            "linha_fonte": linha["id"],
            "descricao": _campo(descricao, linha, texto_original=descricao),
            "quantidade": _campo(quantidade, linha, texto_original=str(quantidade)) if quantidade else None,
            "valor_unitario": _campo(unitario["valor"], linha, texto_original=unitario["texto"]) if unitario else None,
            "total_linha": _campo(total["valor"], linha, texto_original=total["texto"]) if total else None,
            "unidade": "",
            "recusas": [],
            "contexto": "paragrafo",
        })
    return itens


# ======================================================================
# A LEITURA INTEIRA
# ======================================================================
CAMPOS_DE_DINHEIRO = ("subtotal", "frete", "desconto", "total")
_DATA_DE_CARTA = re.compile(
    r"^[a-z .'-]{3,40},\s*(\d{1,2})\s+de\s+(" + "|".join(MESES) + r")\s+de\s+(\d{4})\.?$"
)


def ler(linhas: list[dict], *, hoje: date, empresa: dict) -> dict:
    """Tudo o que as regras conseguem tirar do documento.

    `empresa` traz CNPJ, telefones e e-mails da Lazer & Sport: o cabeçalho
    e o rodapé do orçamento estão cheios deles, e nenhum pode ser lido
    como se fosse do cliente.
    """
    campos: dict[str, dict] = {}
    recusas: list[dict] = []
    alertas: list[dict] = []
    # Dinheiro pode aparecer mais de uma vez ("Total" em cima e embaixo).
    # Todas as ocorrências são guardadas: se discordarem, a conferência
    # avisa, em vez de ficar com a primeira e calar a segunda.
    dinheiro: dict[str, list[dict]] = {campo: [] for campo in CAMPOS_DE_DINHEIRO}

    def guardar(nome, campo):
        if nome not in campos:
            campos[nome] = campo

    def fonte(linha):
        return {"id": linha["id"], "texto": linha["texto"]}

    corpo = [l for l in linhas if l["parte"] in ("corpo", "caixa")]

    # ------------------------------------------------ rótulo : valor
    pares = []
    for linha in corpo:
        par = _par_rotulo_valor(linha["texto"])
        if par:
            pares.append((par[0], par[1], linha))
    # Tabela de diagramação: "Cliente" | "Buffet Alegria" na mesma linha.
    por_linha_de_tabela: dict[tuple, list[dict]] = {}
    for linha in corpo:
        if linha["tabela"]:
            por_linha_de_tabela.setdefault((linha["tabela"], linha["linha"]), []).append(linha)
    for celulas in por_linha_de_tabela.values():
        celulas.sort(key=lambda c: c["coluna"])
        for posicao, celula in enumerate(celulas[:-1]):
            campo = campo_do_rotulo(celula["texto"].rstrip(" :"))
            if campo:
                vizinha = celulas[posicao + 1]
                if not campo_do_rotulo(vizinha["texto"].rstrip(" :")):
                    pares.append((campo, vizinha["texto"], vizinha))

    data_documento = None
    for campo, valor, linha in pares:
        if campo == "data":
            achadas = datas(valor)
            if achadas and data_documento is None:
                data_documento = achadas[0]["data"]
                guardar("data_documento", _campo(data_documento, linha, texto_original=achadas[0]["texto"]))
    if data_documento is None:
        # "São Paulo, 5 de novembro de 2026." -- a data de carta, sem rótulo.
        for linha in corpo:
            achado = _DATA_DE_CARTA.match(sem_acento(linha["texto"]))
            if achado:
                try:
                    data_documento = date(int(achado.group(3)), MESES[achado.group(2)], int(achado.group(1)))
                except ValueError:
                    continue
                guardar("data_documento", _campo(data_documento, linha, texto_original=linha["texto"]))
                break

    for campo, valor, linha in pares:
        sem = sem_acento(valor)
        if campo in ("cliente", "contato", "endereco", "bairro", "cidade", "uf"):
            limpo = valor.strip(" .;")
            # "Cliente: Buffet Alegria - CNPJ 12.345.678/0001-90": o nome
            # para antes do primeiro dado que tem campo próprio.
            corte = len(limpo)
            for achado in documentos(limpo) + telefones(limpo) + emails(limpo):
                corte = min(corte, achado["inicio"])
            rotulo_interno = re.search(
                r"(?i)\b(cpf|cnpj|tel|telefone|fone|celular|e-?mail|whatsapp)\b", limpo
            )
            if rotulo_interno:
                corte = min(corte, rotulo_interno.start())
            limpo = limpo[:corte].strip(" -–—,;/|")
            if limpo:
                guardar(campo, _campo(limpo, linha, texto_original=limpo))
        elif campo == "cep":
            achado = re.search(r"\d{5}-?\d{3}", valor)
            if achado:
                cep = somente_digitos(achado.group(0))
                guardar("cep", _campo(f"{cep[:5]}-{cep[5:]}", linha, texto_original=achado.group(0)))
        elif campo == "validade":
            lido = ler_validade(valor, data_documento=data_documento, hoje=hoje)
            if lido:
                guardar("validade", _campo(lido["data"], linha, texto_original=valor.strip(),
                                           motivo=lido["como"]))
            else:
                recusas.append({"campo": "validade",
                                "motivo": f"validade “{valor.strip()}” sem data nem prazo em dias",
                                "fonte": fonte(linha)})
        elif campo in ("forma_pagamento", "prazo", "forma_envio", "observacoes"):
            guardar(campo, _campo(valor.strip(" ."), linha, texto_original=valor.strip()))
        elif campo in CAMPOS_DE_DINHEIRO:
            valores = valores_em_reais(valor)
            valido = next((v for v in valores if v["valor"] is not None), None)
            if valido:
                dinheiro[campo].append(_campo(valido["valor"], linha, texto_original=valido["texto"]))
            elif valores:
                recusas.append({"campo": campo, "motivo": valores[0]["recusa"], "fonte": fonte(linha)})
            elif campo == "desconto":
                percentual = re.search(r"(\d{1,2}(?:[.,]\d{1,2})?)\s*%", valor)
                if percentual:
                    guardar("desconto_percentual", _campo(
                        Decimal(percentual.group(1).replace(",", ".")), linha,
                        texto_original=percentual.group(0),
                    ))
            elif campo == "frete":
                # "Frete: grátis", "Entrega: 15 dias", "Frete: por conta do cliente".
                if FRETE_SEM_CUSTO.search(sem):
                    dinheiro["frete"].append(_campo(
                        Decimal("0.00"), linha, texto_original=valor.strip(),
                        motivo="frete sem custo escrito no documento",
                    ))
                elif FRETE_DO_CLIENTE.search(sem):
                    dinheiro["frete"].append(_campo(
                        Decimal("0.00"), linha, texto_original=valor.strip(),
                        motivo="frete por conta do cliente: não entra no total",
                    ))
                    guardar("forma_envio", _campo("Frete por conta do cliente", linha,
                                                  texto_original=valor.strip()))
                elif FRETE_A_COMBINAR.search(sem):
                    recusas.append({"campo": "frete", "motivo": f"frete “{valor.strip()}”: sem valor",
                                    "fonte": fonte(linha)})
                elif _PRAZO_EM_DIAS.search(sem):
                    guardar("prazo", _campo(valor.strip(" ."), linha, texto_original=valor.strip()))

    # ------------------------------ dinheiro sem dois-pontos no rótulo
    # "TOTAL GERAL R$ 1.250,00" e "Subtotal R$ 1.200 | Frete R$ 50".
    ja_lidas = {(c["fonte"]["id"], campo) for campo, lista in dinheiro.items() for c in lista}
    for linha in corpo:
        if linha["tabela"]:
            continue  # tabela de itens tem leitura própria, logo abaixo
        for campo, trecho, _, pedaco in _segmentos_de_dinheiro(linha["texto"]):
            if (linha["id"], campo) in ja_lidas:
                continue
            valores = valores_em_reais(trecho)
            valido = next((v for v in valores if v["valor"] is not None), None)
            if valido:
                dinheiro[campo].append(_campo(valido["valor"], linha, texto_original=valido["texto"]))
            elif valores:
                recusas.append({"campo": campo, "motivo": valores[0]["recusa"], "fonte": fonte(linha)})
            elif campo == "desconto":
                percentual = re.search(r"(\d{1,2}(?:[.,]\d{1,2})?)\s*%", trecho)
                if percentual:
                    guardar("desconto_percentual", _campo(
                        Decimal(percentual.group(1).replace(",", ".")), linha,
                        texto_original=percentual.group(0),
                    ))
            elif campo == "frete" and FRETE_SEM_CUSTO.search(sem_acento(pedaco)):
                dinheiro["frete"].append(_campo(Decimal("0.00"), linha, texto_original=pedaco.strip(),
                                                motivo="frete sem custo escrito no documento"))

    # ---------------------------------------- documento, telefone, e-mail
    chaves_da_empresa = {chave_documento(c) for c in empresa.get("documentos", ()) if c}
    telefones_da_empresa = {digitos_do_telefone(t) for t in empresa.get("telefones", ()) if t}
    emails_da_empresa = {e.lower() for e in empresa.get("emails", ()) if e}

    documentos_achados, telefones_achados, emails_achados = [], [], []
    for linha in corpo:
        for achado in documentos(linha["texto"]):
            if achado["chave"] not in chaves_da_empresa:
                documentos_achados.append((achado, linha))
        for achado in telefones(linha["texto"]):
            if achado["digitos"] not in telefones_da_empresa:
                telefones_achados.append((achado, linha))
        for achado in emails(linha["texto"]):
            if achado["email"] not in emails_da_empresa:
                emails_achados.append((achado, linha))

    if documentos_achados:
        achado, linha = documentos_achados[0]
        guardar("documento", _campo(achado["chave"], linha, texto_original=achado["texto"],
                                    extra={"valido": achado["valido"], "tipo": achado["tipo"]}))
        outros = {a["chave"] for a, _ in documentos_achados[1:]} - {achado["chave"]}
        if outros:
            alertas.append({
                "tipo": "varios_documentos",
                "detalhe": "O documento traz mais de um CPF/CNPJ além do da empresa; "
                           "confira qual é o do cliente.",
                "fonte": fonte(linha),
            })
    if telefones_achados:
        achado, linha = telefones_achados[0]
        guardar("telefone", _campo(achado["digitos"], linha, texto_original=achado["texto"]))
    if emails_achados:
        achado, linha = emails_achados[0]
        guardar("email", _campo(achado["email"], linha, texto_original=achado["texto"]))

    # ------------------------------------------------------- itens
    itens, resumo, alertas_tabela = tabelas_de_itens(linhas)
    alertas.extend(alertas_tabela)

    # O que fecha a tabela de itens é a soma exata daqueles itens. Um
    # "Total" em parágrafo depois da tabela costuma ser o total COM frete.
    # Quando a tabela tem "Total" mas não tem "Subtotal", e o parágrafo
    # traz outro total, o da tabela é o subtotal dos itens.
    if "total" in resumo and "subtotal" not in resumo and dinheiro["total"]:
        if all(c["valor"] != resumo["total"]["valor"] for c in dinheiro["total"]):
            resumo["subtotal"] = resumo.pop("total")
    for campo in CAMPOS_DE_DINHEIRO:
        lista = ([resumo[campo]] if campo in resumo else []) + dinheiro[campo]
        if not lista:
            continue
        campos[campo] = lista[0]
        diferentes = []
        for ocorrencia in lista[1:]:
            if ocorrencia["valor"] != lista[0]["valor"] and ocorrencia not in diferentes:
                diferentes.append(ocorrencia)
        if diferentes:
            campos[campo] = dict(lista[0], conflitos=diferentes)

    if not itens:
        itens = itens_em_paragrafos(linhas)

    return {
        "campos": campos,
        "itens": itens,
        "recusas": recusas,
        "alertas": alertas,
        "data_documento": data_documento,
    }
