"""Os campos da O.S. no documento: rótulos, seções, itens, datas e valores.

O QUE A FICHA DE O.S. ESCREVE, E COMO. Quem preenche uma O.S. no Word, num
sistema antigo ou à mão e depois digita, escreve quase sempre do mesmo
jeito, e é isso que se lê aqui -- por regra, sem IA:

  * "Rótulo: valor" na linha ("Equipamento: Cama elástica 3 m"), e vários
    na mesma linha ("Equipamento: Cama elástica   Nº de série: CE-3091");
  * a ficha em tabela: "Equipamento | Cama elástica" (rótulo e valor lado a
    lado) ou a linha de títulos com os valores embaixo ("Equipamento | Nº de
    série | Técnico" e, na linha de baixo, cada valor na sua coluna);
  * a seção: o título sozinho ("DEFEITO RELATADO", "Serviço executado:") e
    o texto nos parágrafos de baixo, até o próximo título;
  * a tabela de peças e serviços (Descrição/Peça | Qtd | Valor | Total),
    lida pela mesma régua do orçamento (`deterministica.tabelas_de_itens`),
    com o tipo de cada linha pela coluna "Tipo", pelo título da seção
    ("PEÇAS UTILIZADAS") ou pelas palavras ("mão de obra", "deslocamento");
  * o valor solto com rótulo ("Mão de obra: R$ 150,00", "Deslocamento: R$
    80,00") vira linha de serviço ou de deslocamento;
  * o número da O.S. no título ("ORDEM DE SERVIÇO Nº 0457", "OS-00042/2026").

UM RÓTULO PODE QUERER DIZER DUAS COISAS, e quem decide é o valor: "Visita:
12/03/2026" é a data da visita, "Visita: R$ 80,00" é o deslocamento cobrado;
"Entrada: 10/03" é quando o equipamento entrou, "Entrada: R$ 200,00" é o
sinal pago. Valor que não serve para nenhum dos sentidos fica de fora -- e
a linha volta para a leitura do cliente, que pode precisar dela.

AS LINHAS LIDAS AQUI SAEM DA LEITURA DO CLIENTE. Defeito, técnico, série e
garantia não são do cliente: um nome no defeito ("o Sr. Pedro disse que...")
ou o celular do técnico não podem virar o cadastro. Por isso `ler` devolve,
além dos campos, as linhas que consumiu.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from core.arena import _normalizar

from ..importacao_word import deterministica as det

CENTAVO = Decimal("0.01")

# ======================================================================
# OS RÓTULOS
# ======================================================================
#: O tipo de valor que cada campo aceita. A ordem é a da preferência
#: quando o mesmo rótulo serve a mais de um campo: o valor que tem forma
#: (dinheiro, data, um dos nomes da lista) ganha do texto livre.
DINHEIRO, DATA, GARANTIA, HORA, MAPA, NUMERO, CURTO, LONGO = (
    "dinheiro", "data", "garantia", "hora", "mapa", "numero", "curto", "longo",
)
_PRIORIDADE_DO_TIPO = (DINHEIRO, DATA, GARANTIA, HORA, MAPA, NUMERO, CURTO, LONGO)

CAMPOS = {
    # campo: (tipo de valor, rótulos -- já sem acento, minúsculos)
    "numero_os": (NUMERO, (
        "os", "o s", "n os", "no os", "n o s", "no o s", "n da os", "no da os", "n da o s", "no da o s",
        "numero da os", "numero da o s", "numero os", "num os", "os n", "os no", "o s n", "o s no",
        "ordem de servico", "ordem de servico n", "ordem de servico no", "n da ordem de servico",
        "no da ordem de servico", "numero da ordem de servico", "numero da ordem", "n ordem",
    )),
    "equipamento": (CURTO, (
        "equipamento", "equipamentos", "brinquedo", "aparelho", "maquina", "produto", "objeto",
        "equipamento atendido", "item atendido", "descricao do equipamento", "equipamento brinquedo",
        "brinquedo equipamento", "nome do equipamento", "equipamento em manutencao",
    )),
    "modelo": (CURTO, ("modelo", "marca", "marca modelo", "modelo marca", "fabricante")),
    "numero_serie": (CURTO, (
        "n de serie", "no de serie", "numero de serie", "serie", "n serie", "no serie", "num serie",
        "numero serie", "n de serie patrimonio", "patrimonio", "n patrimonio", "no patrimonio",
        "numero do patrimonio", "codigo do equipamento", "identificacao", "identificacao do equipamento",
        "etiqueta", "s n", "serial",
    )),
    "defeito_relatado": (LONGO, (
        "defeito", "defeitos", "defeito relatado", "defeito reclamado", "defeito informado",
        "defeito apresentado", "problema", "problema relatado", "problema informado", "problema apresentado",
        "reclamacao", "reclamacao do cliente", "relato", "relato do cliente", "queixa", "solicitacao",
        "solicitacao do cliente", "servico solicitado", "servicos solicitados", "descricao do problema",
        "descricao do defeito", "motivo", "motivo do chamado", "motivo da visita", "motivo do atendimento",
        "servico a executar", "servicos a executar", "servico a realizar", "servicos a realizar",
        "servico a fazer", "a fazer", "o que o cliente relatou", "ocorrencia", "descricao da ocorrencia",
        "chamado", "descricao do chamado", "pedido do cliente",
        # "Serviço: troca da lona" sem valor e sem tipo: é o que se pede.
        "servico",
    )),
    "diagnostico": (LONGO, (
        "diagnostico", "diagnostico tecnico", "laudo", "laudo tecnico", "parecer", "parecer tecnico",
        "causa", "causa provavel", "defeito constatado", "constatado", "constatacao", "avaliacao tecnica",
        "analise tecnica", "analise", "vistoria", "resultado da vistoria",
    )),
    "servico_executado": (LONGO, (
        "servico executado", "servicos executados", "servico realizado", "servicos realizados",
        "trabalho realizado", "trabalho executado", "solucao", "solucao aplicada", "reparo realizado",
        "reparo executado", "o que foi feito", "providencias", "providencias tomadas",
        "procedimento realizado", "procedimentos realizados", "execucao", "atividades realizadas",
        "manutencao realizada", "servico prestado", "servicos prestados", "descricao do servico executado",
        "descricao dos servicos executados",
    )),
    "observacoes": (LONGO, (
        "observacoes", "observacao", "obs", "recomendacoes", "recomendacao", "orientacoes",
        "observacoes e recomendacoes", "informacoes adicionais", "observacoes gerais", "obs gerais",
        "notas", "nota",
    )),
    "tecnico": (CURTO, (
        "tecnico", "tecnicos", "tecnico responsavel", "responsavel tecnico", "executado por", "atendido por",
        "tecnico executor", "realizado por", "equipe tecnica", "montador", "instalador",
        "tecnico que atendeu", "nome do tecnico",
    )),
    "tipo": (MAPA, (
        "tipo", "tipo de servico", "tipo do servico", "tipo de atendimento", "natureza", "natureza do servico",
        "tipo da os", "tipo de os", "modalidade", "atendimento", "servico", "visita",
    )),
    "status": (MAPA, (
        "status", "situacao", "situacao da os", "status da os", "status do servico", "andamento",
        "situacao do servico", "estado do servico", "estado da os",
    )),
    "prioridade": (MAPA, ("prioridade", "urgencia", "nivel de urgencia", "grau de urgencia")),
    "status_pagamento": (MAPA, (
        "pagamento", "status do pagamento", "situacao do pagamento", "situacao financeira",
        "pagamento status",
    )),
    "data_documento": (DATA, (
        "data de abertura", "abertura", "aberta em", "aberto em", "data da os", "data de entrada",
        "entrada", "data do chamado", "data da solicitacao", "solicitado em", "data do pedido",
        "data de recebimento", "recebido em",
    )),
    "agendada_para": (DATA, (
        "agendado para", "agendada para", "agendamento", "data agendada", "data da visita", "visita",
        "data do atendimento", "atendimento", "data prevista", "previsao", "previsao de atendimento",
        "data marcada", "data e hora", "data hora", "data do servico", "data de execucao",
        "visita agendada", "visita tecnica",
    )),
    "hora": (HORA, ("horario", "hora", "hora da visita", "horario da visita", "hora agendada", "horario agendado")),
    "iniciada_em": (DATA, ("inicio", "data de inicio", "iniciado em", "iniciada em", "inicio do servico")),
    "concluida_em": (DATA, (
        "conclusao", "data de conclusao", "concluido em", "concluida em", "finalizado em", "finalizada em",
        "data de entrega", "entregue em", "entrega", "termino", "data de termino", "data de finalizacao",
        "encerrado em", "encerrada em", "data de saida", "saida",
    )),
    "garantia": (GARANTIA, (
        "garantia", "garantia ate", "prazo de garantia", "validade da garantia", "garantia do servico",
        "periodo de garantia", "garantia de", "garantia valida ate",
    )),
    "endereco_servico": (CURTO, (
        "local do servico", "endereco do servico", "local do atendimento", "endereco do atendimento",
        "local de atendimento", "local da instalacao", "endereco da instalacao", "local da visita",
        "local da manutencao", "local de instalacao", "endereco de instalacao", "local do equipamento",
        "endereco da visita", "local de execucao",
    )),
    "valor_pago": (DINHEIRO, (
        "valor pago", "pago", "total pago", "entrada", "sinal", "valor recebido", "recebido", "adiantamento",
        "valor ja pago",
    )),
    "item_servico": (DINHEIRO, (
        "mao de obra", "valor da mao de obra", "valor do servico", "valor dos servicos", "servico", "servicos",
        "taxa de servico", "valor da manutencao", "valor do conserto", "conserto", "reparo", "hora tecnica",
        "horas tecnicas", "visita tecnica", "valor da visita",
    )),
    "item_deslocamento": (DINHEIRO, (
        "deslocamento", "taxa de deslocamento", "taxa de visita", "visita", "km", "quilometragem", "transporte",
        "viagem", "despesas de viagem", "km rodado", "km rodados",
    )),
    "item_pecas": (DINHEIRO, (
        "pecas", "valor das pecas", "material", "materiais", "valor do material", "valor dos materiais",
        "pecas e materiais",
    )),
}

#: Títulos de seção que dizem o que é cada linha da tabela que vem embaixo.
SECOES_DE_ITENS = {
    "pecas": "peca", "pecas utilizadas": "peca", "pecas substituidas": "peca", "pecas trocadas": "peca",
    "materiais": "peca", "materiais utilizados": "peca", "pecas e materiais": "peca", "material utilizado": "peca",
    "material": "peca", "pecas aplicadas": "peca",
    "servicos": "servico", "mao de obra": "servico", "servicos executados": "servico",
    "servicos realizados": "servico",
    "deslocamento": "deslocamento", "despesas": "deslocamento",
}

_POR_CHAVE: dict[str, list[str]] = {}
for _campo_nome, (_tipo, _rotulos) in CAMPOS.items():
    for _rotulo in _rotulos:
        _POR_CHAVE.setdefault(_rotulo, []).append(_campo_nome)
for _chave in _POR_CHAVE:
    _POR_CHAVE[_chave].sort(key=lambda nome: _PRIORIDADE_DO_TIPO.index(CAMPOS[nome][0]))

#: Rótulos do cadastro e do orçamento que também cortam uma linha em pedaços
#: (e que esta leitura não consome: são do cliente ou das contas).
_ROTULOS_DE_FORA = {"cliente", "contato", "telefone", "e mail", "email", "cpf", "cnpj", "endereco"}


def chave(texto: str) -> str:
    """O rótulo como se compara: sem acento, sem pontuação, sem o "(R$)"."""
    sem_parenteses = re.sub(r"\([^)]*\)", " ", texto or "")
    sem_numero_na_frente = re.sub(r"^\s*(?:\d{1,2}|[ivx]{1,4})\s*[.)\-–—]\s+", "", sem_parenteses, flags=re.I)
    return _normalizar(sem_numero_na_frente)


def campos_do_rotulo(texto: str) -> list[str]:
    return list(_POR_CHAVE.get(chave(texto), ()))


def rotulo_conhecido(texto: str) -> bool:
    """É rótulo de alguma coisa -- da O.S., do cadastro ou das contas?"""
    limpo = (texto or "").strip().rstrip(" :：")
    if not limpo or len(limpo) > 48:
        return False
    if chave(limpo) in _POR_CHAVE or chave(limpo) in SECOES_DE_ITENS:
        return True
    return bool(det.campo_do_rotulo(limpo)) or chave(limpo) in _ROTULOS_DE_FORA


# ======================================================================
# O VALOR DE CADA TIPO
# ======================================================================
_VAZIOS = {
    "", "n a", "na", "nao se aplica", "nao informado", "nao informada", "sem", "nenhum", "nenhuma", "x",
    "nada", "nada consta", "sem observacoes", "sem observacao", "nenhuma observacao", "a definir",
}

MAPA_TIPO = (
    ("instalacao", r"\b(instalac\w*|montag\w*|implantac\w*)"),
    ("revisao", r"\b(revis\w*|preventiv\w*)"),
    ("visita", r"\b(visita\s+tecnica|vistoria|avaliac\w*|orcamento\s+no\s+local|levantamento)"),
    ("manutencao", r"\b(manutenc\w*|conserto|reparo|corretiv\w*|assistencia|garantia|defeito)"),
    ("outro", r"\b(outro|outros|diversos)\b"),
)
MAPA_STATUS = (
    ("aguardando_peca", r"\baguardando\s+(?:a\s+)?(?:peca|pecas|material|materiais)\b"),
    ("aguardando_resposta", r"\baguardando\s+(?:ciencia|aprovacao|cliente|resposta|autorizacao)\b"),
    ("em_execucao", r"\b(em\s+execucao|em\s+andamento|em\s+atendimento|em\s+manutencao|iniciad[ao]|executando)\b"),
    ("concluida", r"\b(conclu\w+|finalizad[ao]|entregue|encerrad[ao]|resolvid[ao]|pront[ao]|realizad[ao]|executad[ao])\b"),
    ("cancelada", r"\b(cancelad[ao])\b"),
    ("agendada", r"\b(agendad[ao])\b"),
    ("aberta", r"\b(abert[ao]|em\s+aberto|pendente|nov[ao])\b"),
)
MAPA_PRIORIDADE = (
    ("urgente", r"\b(urgente|urgencia|emergencia|critica|imediat\w*|maxima)\b"),
    ("alta", r"\b(alta|prioritari[ao])\b"),
    ("baixa", r"\b(baixa)\b"),
    ("normal", r"\b(normal|media|comum|padrao)\b"),
)
MAPA_PAGAMENTO = (
    ("parcial", r"\b(parcial\w*|sinal|metade)\b"),
    ("pendente", r"\b(pendente|a\s+receber|em\s+aberto|nao\s+pago|a\s+pagar|aguardando)\b"),
    ("pago", r"\b(pago|paga|quitad[ao]|recebid[ao]|pago\s+integralmente|liquidad[ao])\b"),
)
_MAPAS = {"tipo": MAPA_TIPO, "status": MAPA_STATUS, "prioridade": MAPA_PRIORIDADE,
          "status_pagamento": MAPA_PAGAMENTO}
_PALAVRAS_DE_TIPO = {
    "manutencao", "corretiva", "preventiva", "instalacao", "montagem", "revisao", "visita", "tecnica",
    "conserto", "reparo", "assistencia", "garantia", "vistoria", "avaliacao", "outro", "outros", "servico",
    "de", "em", "e", "a", "o", "no", "na", "local",
}


def mapear(campo: str, texto: str) -> str:
    sem = det.sem_acento(texto or "")
    for codigo, padrao in _MAPAS[campo]:
        if re.search(padrao, sem):
            return codigo
    return ""


_HORA = re.compile(r"(?<![\d/])([01]?\d|2[0-3])\s*(?::|h|hs|horas?)\s*([0-5]\d)?(?!\d)")
_DURACAO = re.compile(
    r"(?<!\d)(\d{1,4}|um|uma|dois|duas|tres|seis|doze|trinta|sessenta|noventa|cento\s+e\s+oitenta)"
    r"\s*(?:\([^)]*\)\s*)?(dias?|mes|meses|anos?)\b"
)
_EXTENSO = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "seis": 6, "doze": 12, "trinta": 30,
            "sessenta": 60, "noventa": 90, "cento e oitenta": 180}


def ler_hora(texto: str) -> str:
    achado = _HORA.search(det.sem_acento(texto or ""))
    if not achado:
        return ""
    return f"{int(achado.group(1)):02d}:{int(achado.group(2) or 0):02d}"


def ler_data(texto: str) -> dict | None:
    """A primeira data do texto ("12/03/2026 às 9h30", "12 de março de 2026")."""
    achadas = det.datas(texto or "")
    if not achadas:
        return None
    primeira = achadas[0]
    depois = (texto or "")[primeira["inicio"] + len(primeira["texto"]):][:24]
    hora = ler_hora(depois) if re.match(r"^\s*(?:,|-|–|às|as|a partir das|\bde\b)?\s*\d", det.sem_acento(depois)) else ""
    return {"data": primeira["data"].isoformat(), "hora": hora}


def ler_duracao(texto: str) -> dict | None:
    achado = _DURACAO.search(det.sem_acento(texto or ""))
    if not achado:
        return None
    numero = achado.group(1)
    quantidade = int(numero) if numero.isdigit() else _EXTENSO.get(re.sub(r"\s+", " ", numero), 0)
    if quantidade <= 0:
        return None
    unidade = achado.group(2)
    if unidade.startswith("dia"):
        return {"dias": quantidade}
    if unidade.startswith("ano"):
        return {"meses": quantidade * 12}
    return {"meses": quantidade}


def somar_meses(base: date, meses: int) -> date:
    ano = base.year + (base.month - 1 + meses) // 12
    mes = (base.month - 1 + meses) % 12 + 1
    for dia in (base.day, 30, 29, 28):
        try:
            return date(ano, mes, dia)
        except ValueError:
            continue
    return date(ano, mes, 28)


def _texto_limpo(valor: str) -> str:
    texto = det.espacos(valor).strip(" -–—:;|·•")
    return "" if _normalizar(texto) in _VAZIOS else texto


def interpretar(campo: str, valor: str, *, estrito: bool) -> object | None:
    """O valor que o campo aceita, ou None (e aí o rótulo não serve aqui).

    `estrito` vale para o rótulo que serve a mais de um campo ("Serviço",
    "Visita", "Entrada"): ali o dinheiro só conta com "R$" ou centavos,
    para "Serviço: 2 visitas" não virar dois reais.
    """
    tipo = CAMPOS[campo][0]
    texto = valor or ""
    # Valor com forma (lista, data, hora, número) é curto: "Tipo: Manutenção
    # corretiva". Um parágrafo inteiro embaixo de "Serviço" é o texto do
    # serviço, e não um tipo que por acaso tem a palavra "reparo".
    if tipo == MAPA and len(texto) > 60:
        return None
    if estrito and tipo in (DATA, HORA, NUMERO) and len(texto) > 48:
        return None
    if tipo == DINHEIRO:
        achado = det.primeiro_valor(texto, coluna_de_dinheiro=not estrito)
        if not achado:
            return None
        # O número tem de ser o valor da linha, e não um pedaço de frase:
        # "Peças: 2 molas e 1 lona" não é dinheiro.
        resto = det.sem_acento(texto[:achado["inicio"]] + " " + texto[achado["fim"]:])
        if re.search(r"[a-z]{4,}", re.sub(r"\b(reais|real|cada|total|valor|brl|r)\b", "", resto)):
            return None
        return achado["valor"]
    if tipo == DATA:
        return ler_data(texto)
    if tipo == HORA:
        return ler_hora(texto) or None
    if tipo == GARANTIA:
        data_escrita = ler_data(texto)
        if data_escrita:
            return {"data": data_escrita["data"]}
        duracao = ler_duracao(texto)
        if duracao:
            return duracao
        return {"sem": True} if re.search(r"\b(sem|nao ha|nao tem)\b", det.sem_acento(texto)) else None
    if tipo == MAPA:
        if campo == "tipo" and estrito:
            # "Serviço: Manutenção corretiva" é o tipo; "Serviço: Reparo da
            # costura" é o pedido -- o valor tem de ser só palavras de tipo.
            if any(palavra not in _PALAVRAS_DE_TIPO for palavra in _normalizar(texto).split()):
                return None
        return mapear(campo, texto) or None
    if tipo == NUMERO:
        achado = re.search(r"[A-Za-z]{0,4}[-–]?\d[\w./-]{0,24}", texto)
        if not achado or det.datas(achado.group(0)):
            return None
        return achado.group(0).strip(".-/")
    if tipo == LONGO:
        # O texto longo guarda as quebras: cada parágrafo do documento é
        # uma linha da O.S. (o defeito em dois parágrafos continua em dois).
        partes = [_texto_limpo(parte) for parte in texto.split("\n")]
        limpo = "\n".join(parte for parte in partes if parte)[:4000]
        return limpo or None
    limpo = _texto_limpo(texto)
    if not limpo:
        return None
    if tipo == CURTO and len(limpo) > 180:
        limpo = limpo[:180].rsplit(" ", 1)[0]
    return limpo


# ======================================================================
# AS LINHAS: "Rótulo: valor", vários por linha
# ======================================================================
_PALAVRA = re.compile(r"[^\s|;·•]+")


def pares_da_linha(texto: str) -> list[tuple[int, int, str]]:
    """Onde começa cada rótulo da linha e onde começa o valor dele.

    Cada dois-pontos é um candidato: o rótulo é o pedaço MAIS LONGO de
    palavras logo antes dele que é um rótulo conhecido. Dois-pontos de hora
    ("09:30") ou de link não têm rótulo antes e não cortam nada.
    Devolve [(início do rótulo, início do valor, texto do rótulo)].
    """
    achados = []
    anterior = 0
    for marca in re.finditer(r"[:：]", texto or ""):
        trecho = texto[anterior:marca.start()]
        palavras = list(_PALAVRA.finditer(trecho))
        for quantas in range(min(7, len(palavras)), 0, -1):
            inicio = palavras[-quantas].start()
            rotulo = trecho[inicio:]
            if rotulo_conhecido(rotulo):
                achados.append((anterior + inicio, marca.end(), rotulo.strip()))
                anterior = marca.end()
                break
    return achados


def separar_linhas(linhas: list[dict]) -> list[dict]:
    """A linha com vários rótulos vira uma linha por rótulo.

    "Cliente: Buffet X   Equipamento: Cama elástica" seria lido pelo
    cadastro como o cliente "Buffet X Equipamento: Cama elástica". Partida
    em duas, cada leitura vê o que é dela. O primeiro pedaço fica com o id
    da linha; os outros ganham "~2", "~3" (a fonte continua apontando a
    linha certa do documento). Célula de tabela fica como está.
    """
    saida = []
    for linha in linhas:
        if linha["tabela"]:
            saida.append(linha)
            continue
        pares = pares_da_linha(linha["texto"])
        cortes = [p[0] for p in pares if p[0] > 0]
        if not cortes:
            saida.append(linha)
            continue
        pedacos = []
        inicio = 0
        for corte in cortes:
            pedacos.append(linha["texto"][inicio:corte])
            inicio = corte
        pedacos.append(linha["texto"][inicio:])
        pedacos = [det.espacos(p).strip(" |;·•–—") for p in pedacos]
        pedacos = [p for p in pedacos if p]
        for numero, pedaco in enumerate(pedacos, start=1):
            saida.append(dict(linha, id=linha["id"] if numero == 1 else f"{linha['id']}~{numero}", texto=pedaco))
    return saida


# ======================================================================
# CABEÇALHO DA TABELA DE PEÇAS
# ======================================================================
_PECA_NO_CABECALHO = {"peca", "pecas", "peca servico", "pecas servicos", "pecas e servicos", "servico peca",
                      "peca material", "pecas materiais", "pecas e materiais", "mao de obra pecas",
                      "item peca", "discriminacao", "especificacao do item", "descricao da peca"}
_TIPO_NO_CABECALHO = {"tipo", "tipo do item", "categoria", "natureza"}


def preparar_tabelas(linhas: list[dict]) -> tuple[list[dict], dict]:
    """"Peça | Qtd | Valor" é tabela de itens: o cabeçalho ganha "Descrição".

    A régua das tabelas do orçamento reconhece Descrição/Produto/Serviço/
    Material, mas não "Peça". Trocar o texto da célula do cabeçalho (só
    dela, e só numa cópia das linhas) é o que deixa a mesma régua ler a
    tabela de peças da O.S. Devolve as linhas e, por tabela, a coluna do
    "Tipo" (quando há) -- {tabela: (linha do cabeçalho, coluna)}.
    """
    por_linha: dict[tuple, list[dict]] = {}
    for linha in linhas:
        if linha["tabela"]:
            por_linha.setdefault((linha["tabela"], linha["linha"]), []).append(linha)
    trocar: dict[str, str] = {}
    tipos: dict[str, tuple[int, int]] = {}
    vistas: set[str] = set()
    for (tabela, numero), celulas in sorted(por_linha.items(), key=lambda par: (par[0][0], par[0][1])):
        if tabela in vistas or numero > 3:
            continue
        colunas = {c["coluna"]: _coluna(c["texto"]) for c in celulas}
        tem_valores = {"quantidade", "valor_unitario", "total"} & set(colunas.values())
        if not tem_valores:
            continue
        if "descricao" not in colunas.values():
            pecas = [c for c in celulas if chave(c["texto"]) in _PECA_NO_CABECALHO]
            if not pecas:
                continue
            trocar[pecas[0]["id"]] = "Descrição"
        for celula in celulas:
            if chave(celula["texto"]) in _TIPO_NO_CABECALHO:
                tipos[tabela] = (numero, celula["coluna"])
        vistas.add(tabela)
    if not trocar:
        return linhas, tipos
    return [dict(l, texto=trocar[l["id"]]) if l["id"] in trocar else l for l in linhas], tipos


def _coluna(texto: str) -> str:
    return det._coluna_do_cabecalho(texto)  # noqa: SLF001 -- a régua do orçamento, de propósito


def preparar_texto_corrido(texto: str) -> str:
    """O texto do PDF ou do .txt antes de virar linhas.

    Duas coisas que a leitura das colunas não sabe:
      * "Equipamento        Cama elástica" (rótulo e valor em colunas, sem
        dois-pontos) vira "Equipamento: Cama elástica";
      * no cabeçalho da tabela de peças, "Peça" vira "Item" -- do mesmo
        tamanho, para as colunas continuarem no lugar --, que a régua do
        orçamento lê como a descrição.
    """
    saida = []
    for bruta in (texto or "").replace("\t", "    ").splitlines():
        pedacos = [(a.start(), a.end(), a.group(0)) for a in re.finditer(r"\S+(?: \S+)*", bruta)]
        if len(pedacos) >= 3:
            colunas = [_coluna(p[2]) for p in pedacos]
            if {"quantidade", "valor_unitario", "total"} & set(colunas) and "descricao" not in colunas:
                for inicio, fim, pedaco in pedacos:
                    if chave(pedaco) in _PECA_NO_CABECALHO:
                        largura = fim - inicio
                        bruta = bruta[:inicio] + "Item".ljust(largura) + bruta[fim:]
                        break
        elif len(pedacos) == 2 and not pedacos[0][2].rstrip().endswith(":"):
            rotulo = pedacos[0][2]
            if campos_do_rotulo(rotulo) and not det.campo_do_rotulo(rotulo):
                bruta = " " * pedacos[0][0] + f"{rotulo}: {pedacos[1][2]}"
        saida.append(bruta)
    return "\n".join(saida)


# ======================================================================
# A LEITURA
# ======================================================================
_ASSINATURA = re.compile(r"(?i)^(?:_{4,}|-{6,}|\.{6,}|assinatura\b|ass\.\s|atenciosamente\b|de acordo\b|"
                         r"visto\b|cliente\s*:?\s*_+|tecnico\s*:?\s*_+)")
_TITULO_DE_OS = re.compile(
    r"(?i)\b(?:ordem\s+de\s+servi[cç]o|relat[óo]rio\s+t[ée]cnico|laudo\s+t[ée]cnico|"
    r"relat[óo]rio\s+de\s+(?:visita|atendimento|manuten[cç][ãa]o|servi[cç]o)|pedido\s+de\s+servi[cç]o|"
    r"solicita[cç][ãa]o\s+de\s+servi[cç]o|chamado\s+t[ée]cnico)\b"
)
_NUMERO_NO_TITULO = (
    re.compile(r"(?i)\bordem\s+de\s+servi[cç]o\s*(?:n[º°o.]?|n[úu]mero|nro\.?)?\s*[:#]?\s*([A-Z]{0,4}-?\d[\w./-]{0,24})"),
    re.compile(r"\bO\.\s?S\.?\s*(?:[Nn][º°o.]?|[Nn][úu]mero)?\s*[:#]?\s*([A-Z]{0,4}-?\d[\w./-]{0,24})"),
    re.compile(r"\bOS\s*(?:[Nn][º°o.]?|[Nn][úu]mero)?\s*[:#-]?\s*(\d[\w./-]{0,24})"),
)
#: O número que o próprio painel imprime: "OS-00042/2026".
NUMERO_DO_PAINEL = re.compile(r"\bOS-(\d{5,})/(\d{4})\b")
_CHAMADO = re.compile(r"\bMAN[-\s]?(\d{1,7})\b")


def _numero_no_texto(texto: str) -> str:
    for padrao in _NUMERO_NO_TITULO:
        achado = padrao.search(texto or "")
        if achado:
            numero = achado.group(1).strip(".-/")
            if numero and not det.datas(numero) and not det.telefones(numero):
                return numero
    return ""


def _fim_da_secao(linha: dict) -> bool:
    texto = linha["texto"].strip()
    if _ASSINATURA.match(texto):
        return True
    if det._DATA_DE_CARTA.match(det.sem_acento(texto)):  # noqa: SLF001 -- "São Paulo, 10 de março de 2026"
        return True
    return False


def _cabeca(linha: dict) -> str | None:
    """A linha é só um título de seção ("DEFEITO RELATADO", "1. Serviço executado:")?"""
    texto = linha["texto"].strip()
    if len(texto) > 52:
        return None
    sem_dois_pontos = texto.rstrip(" :：")
    if not sem_dois_pontos:
        return None
    if chave(sem_dois_pontos) in _POR_CHAVE or chave(sem_dois_pontos) in SECOES_DE_ITENS:
        return sem_dois_pontos
    return None


#: O nome da linha que nasce de um valor com rótulo ("Mão de obra: R$ 150,00").
_DESCRICAO_DO_ROTULO = {
    "mao de obra": "Mão de obra", "valor da mao de obra": "Mão de obra", "hora tecnica": "Hora técnica",
    "horas tecnicas": "Horas técnicas", "visita tecnica": "Visita técnica", "valor da visita": "Visita técnica",
    "conserto": "Conserto", "valor do conserto": "Conserto", "reparo": "Reparo",
    "valor da manutencao": "Manutenção", "taxa de servico": "Taxa de serviço",
    "taxa de visita": "Taxa de visita", "taxa de deslocamento": "Deslocamento", "km": "Deslocamento (km)",
    "km rodado": "Deslocamento (km)", "km rodados": "Deslocamento (km)", "quilometragem": "Deslocamento (km)",
    "viagem": "Viagem", "despesas de viagem": "Despesas de viagem", "transporte": "Transporte",
    "visita": "Visita técnica",
}


class Leitura:
    """Junta o que foi achado: um valor por campo (o primeiro), e as fontes."""

    def __init__(self):
        self.valores: dict[str, object] = {}
        self.fontes: dict[str, str] = {}
        self.longos: dict[str, list[str]] = {}
        self.consumidas: set[str] = set()
        self.itens_rotulo: list[dict] = []
        self.secoes_tabela: dict[str, str] = {}
        #: "Cliente | Telefone" com os valores na linha de baixo: o cadastro
        #: só lê rótulo e valor lado a lado, então o par vira uma linha
        #: "Cliente: Fulano" para ele.
        self.linhas_extra: list[dict] = []

    def guardar(self, campo: str, valor, linha: dict, *, ids=()):
        tipo = CAMPOS[campo][0]
        self.consumidas.add(linha["id"])
        self.consumidas.update(ids)
        if campo.startswith("item_"):
            rotulo = chave(linha["texto"].split(":", 1)[0])
            descricao = _DESCRICAO_DO_ROTULO.get(rotulo) or {
                "item_servico": "Serviço",
                "item_deslocamento": "Deslocamento",
                "item_pecas": "Peças e materiais",
            }[campo]
            self.itens_rotulo.append({
                "tipo": {"item_servico": "servico", "item_deslocamento": "deslocamento",
                         "item_pecas": "peca"}[campo],
                "descricao": descricao, "quantidade": 1, "valor_unitario": valor, "total_linha": valor,
                "recusa": "", "fonte": linha["texto"][:120], "como": "rotulo",
            })
            return
        if tipo == LONGO:
            lista = self.longos.setdefault(campo, [])
            if valor not in lista:
                lista.append(valor)
            self.fontes.setdefault(campo, linha["texto"][:120])
            return
        if campo not in self.valores:
            self.valores[campo] = valor
            self.fontes[campo] = linha["texto"][:120]


def _aplicar(leitura: Leitura, rotulo: str, valor: str, linha: dict, *, ids=(), secao=False) -> bool:
    """Tenta cada campo do rótulo, na ordem; o primeiro que aceita o valor leva.

    `secao`: o valor veio dos parágrafos embaixo de um título. Aí o número
    da O.S. não vale (o título "ORDEM DE SERVIÇO" não tem número embaixo; o
    "45" da rua que vem depois não é ele), e valor com forma (data, lista,
    dinheiro) só vale numa linha só.
    """
    candidatos = campos_do_rotulo(rotulo)
    estrito = len(candidatos) > 1
    if secao:
        candidatos = [c for c in candidatos if CAMPOS[c][0] != NUMERO]
        if "\n" in valor:
            candidatos = [c for c in candidatos if CAMPOS[c][0] in (CURTO, LONGO)]
    for campo in candidatos:
        interpretado = interpretar(campo, valor, estrito=estrito)
        if interpretado is None:
            continue
        leitura.guardar(campo, interpretado, linha, ids=ids)
        return True
    return False


def ler(linhas: list[dict]) -> dict:
    """Os campos da O.S. e as linhas que eles usaram.

    `linhas` já passaram por `separar_linhas` e `preparar_tabelas`.
    """
    leitura = Leitura()
    blocos: list[tuple[str, object]] = []
    por_linha_tabela: dict[tuple, list[dict]] = {}
    for linha in linhas:
        if linha["tabela"]:
            chave_linha = (linha["tabela"], linha["linha"])
            if chave_linha not in por_linha_tabela:
                por_linha_tabela[chave_linha] = []
                blocos.append(("tabela", chave_linha))
            por_linha_tabela[chave_linha].append(linha)
        else:
            blocos.append(("linha", linha))

    # As tabelas de itens (Descrição/Peça | Qtd | Valor) não são ficha:
    # "Deslocamento | 1 | R$ 120,00" é uma linha de item, e não o rótulo
    # "Deslocamento" com o valor "1". Do cabeçalho para baixo, quem lê é a
    # régua das tabelas; em cima dele, só o título ("PEÇAS UTILIZADAS").
    cabecalho_de_itens = cabecalhos_de_itens(por_linha_tabela)

    titulos: list[str] = []
    posicao = 0
    while posicao < len(blocos):
        especie, conteudo = blocos[posicao]
        posicao += 1
        if especie == "tabela":
            tabela, numero = conteudo
            if tabela in cabecalho_de_itens:
                if numero < cabecalho_de_itens[tabela]:
                    celulas = por_linha_tabela[conteudo]
                    secao = SECOES_DE_ITENS.get(chave(celulas[0]["texto"].rstrip(" :"))) if len(celulas) == 1 else None
                    if secao:
                        leitura.secoes_tabela.setdefault(tabela, secao)
                        leitura.consumidas.add(celulas[0]["id"])
                continue
            _ler_linha_de_tabela(leitura, conteudo, por_linha_tabela)
            continue
        linha = conteudo
        texto = linha["texto"]
        if len(titulos) < 8 and linha["parte"] in ("cabecalho", "corpo", "caixa"):
            titulos.append(texto)
        numero = _numero_no_texto(texto) if _TITULO_DE_OS.search(texto) or re.search(r"\bO\.?\s?S\b", texto) else ""
        if numero and "numero_os" not in leitura.valores:
            leitura.valores["numero_os"] = numero
            leitura.fontes["numero_os"] = texto[:120]
            if not pares_da_linha(texto):
                leitura.consumidas.add(linha["id"])
                continue

        cabeca = _cabeca(linha)
        if cabeca is not None:
            # O título sozinho: o texto mora nos parágrafos de baixo, ou a
            # tabela de baixo é a das peças (ou dos serviços).
            secao = SECOES_DE_ITENS.get(chave(cabeca))
            if posicao < len(blocos) and blocos[posicao][0] == "tabela":
                if secao:
                    leitura.secoes_tabela.setdefault(blocos[posicao][1][0], secao)
                    leitura.consumidas.add(linha["id"])
                    continue
                # "DEFEITO RELATADO" com o texto numa caixa (tabela de uma
                # célula) embaixo: a célula é o valor.
                celulas = por_linha_tabela[blocos[posicao][1]]
                if len(celulas) == 1 and not rotulo_conhecido(celulas[0]["texto"]):
                    if _aplicar(leitura, cabeca, celulas[0]["texto"], linha, ids=(celulas[0]["id"],), secao=True):
                        posicao += 1
                        continue
            corpo, ids = [], []
            while posicao < len(blocos) and blocos[posicao][0] == "linha" and len(corpo) < 15:
                seguinte = blocos[posicao][1]
                if seguinte["parte"] != linha["parte"] or _cabeca(seguinte) is not None \
                        or pares_da_linha(seguinte["texto"]) or _fim_da_secao(seguinte):
                    break
                corpo.append(seguinte["texto"])
                ids.append(seguinte["id"])
                posicao += 1
            if corpo and _aplicar(leitura, cabeca, "\n".join(corpo), linha, ids=ids, secao=True):
                continue
            posicao -= len(corpo)
            if secao or campos_do_rotulo(cabeca) == ["numero_os"]:
                leitura.consumidas.add(linha["id"])
            continue

        pares = pares_da_linha(texto)
        if not pares or pares[0][0] > 0:
            continue
        inicio_rotulo, inicio_valor, rotulo = pares[0]
        valor = texto[inicio_valor:].strip()
        candidatos = campos_do_rotulo(rotulo)
        if not candidatos:
            continue
        ids = []
        if any(CAMPOS[c][0] == LONGO for c in candidatos):
            # "Defeito relatado: Não liga." e, na linha de baixo, "Cliente
            # informou que parou depois da chuva." -- o mesmo campo.
            continuacao = []
            while posicao < len(blocos) and blocos[posicao][0] == "linha" and len(continuacao) < 12:
                seguinte = blocos[posicao][1]
                if seguinte["parte"] != linha["parte"] or _cabeca(seguinte) is not None \
                        or pares_da_linha(seguinte["texto"]) or _fim_da_secao(seguinte) \
                        or _TITULO_DE_OS.search(seguinte["texto"]):
                    break
                continuacao.append(seguinte["texto"])
                ids.append(seguinte["id"])
                posicao += 1
            if continuacao:
                valor = "\n".join([valor] + continuacao) if valor else "\n".join(continuacao)
        if not _aplicar(leitura, rotulo, valor, linha, ids=ids):
            # Ninguém quis o valor: as linhas de continuação voltam a ser
            # do documento (podem ser do cliente).
            posicao -= len(ids)

    return _resultado(leitura, linhas, titulos)


def cabecalhos_de_itens(por_linha_tabela: dict) -> dict[str, int]:
    """{tabela: número da linha do cabeçalho} das tabelas de itens."""
    achados: dict[str, int] = {}
    for (tabela, numero), celulas in sorted(por_linha_tabela.items(), key=lambda par: (par[0][0], par[0][1])):
        if tabela in achados or numero > 3:
            continue
        mapa = {c["coluna"]: {"texto": c["texto"]} for c in celulas}
        if det._mapear_cabecalho(mapa):  # noqa: SLF001 -- a mesma régua das tabelas de itens
            achados[tabela] = numero
    return achados


def _ler_linha_de_tabela(leitura: Leitura, chave_linha, por_linha_tabela):
    celulas = sorted(por_linha_tabela[chave_linha], key=lambda c: c["coluna"])
    tabela, numero = chave_linha
    # 1) "Equipamento | Cama elástica": rótulo e valor lado a lado.
    usadas = set()
    for indice, celula in enumerate(celulas[:-1]):
        if celula["id"] in usadas:
            continue
        rotulo = celula["texto"].rstrip(" :：")
        vizinha = celulas[indice + 1]
        if campos_do_rotulo(rotulo) and not rotulo_conhecido(vizinha["texto"]):
            if _aplicar(leitura, rotulo, vizinha["texto"], celula, ids=(vizinha["id"],)):
                usadas.update((celula["id"], vizinha["id"]))
    # 2) "Equipamento: Cama elástica" dentro da célula.
    for celula in celulas:
        if celula["id"] in usadas:
            continue
        for inicio_rotulo, inicio_valor, rotulo in pares_da_linha(celula["texto"])[:1]:
            if inicio_rotulo == 0 and _aplicar(leitura, rotulo, celula["texto"][inicio_valor:], celula):
                usadas.add(celula["id"])
    # 3) A linha de títulos com os valores embaixo.
    if usadas or not celulas:
        return
    if not all(campos_do_rotulo(c["texto"].rstrip(" :：")) or det.campo_do_rotulo(c["texto"].rstrip(" :："))
               for c in celulas):
        return
    if not any(campos_do_rotulo(c["texto"].rstrip(" :：")) for c in celulas):
        return
    de_baixo = {c["coluna"]: c for c in por_linha_tabela.get((tabela, numero + 1), [])}
    for celula in celulas:
        valor = de_baixo.get(celula["coluna"])
        rotulo = celula["texto"].rstrip(" :：")
        if not valor or rotulo_conhecido(valor["texto"]):
            continue
        if campos_do_rotulo(rotulo):
            _aplicar(leitura, rotulo, valor["texto"], celula, ids=(valor["id"],))
        elif det.campo_do_rotulo(rotulo):
            leitura.consumidas.update((celula["id"], valor["id"]))
            leitura.linhas_extra.append(dict(valor, id=valor["id"] + "~v", texto=f"{rotulo}: {valor['texto']}",
                                             tabela="", linha=0, coluna=0))


def _resultado(leitura: Leitura, linhas: list[dict], titulos: list[str]) -> dict:
    valores = dict(leitura.valores)
    for campo, lista in leitura.longos.items():
        valores[campo] = "\n".join(lista)
    if valores.get("modelo") and valores.get("equipamento"):
        if _normalizar(valores["modelo"]) not in _normalizar(valores["equipamento"]):
            valores["equipamento"] = f"{valores['equipamento']} · {valores['modelo']}"[:180]
    texto_inteiro = "\n".join(l["texto"] for l in linhas)
    # O tipo pelo título ("RELATÓRIO DE VISITA TÉCNICA", "OS – INSTALAÇÃO").
    tipo_pelo_titulo = ""
    for titulo in titulos:
        if _TITULO_DE_OS.search(titulo) or titulo.isupper():
            tipo_pelo_titulo = mapear("tipo", titulo)
            if tipo_pelo_titulo and tipo_pelo_titulo != "outro":
                break
            tipo_pelo_titulo = ""
    # Prioridade escrita solta: "URGENTE" numa linha só.
    prioridade_solta = ""
    for linha in linhas:
        if _normalizar(linha["texto"]) in ("urgente", "urgencia", "prioridade urgente"):
            prioridade_solta = "urgente"
            leitura.consumidas.add(linha["id"])
            break
    # Garantia escrita em frase: "Garantia de 90 (noventa) dias para o serviço".
    garantia_em_frase = None
    if "garantia" not in valores:
        for linha in linhas:
            achado = re.search(r"\bgarantia\s+(?:de|por)\s+(.{1,40})", det.sem_acento(linha["texto"]))
            if achado:
                garantia_em_frase = ler_duracao(achado.group(1))
                if garantia_em_frase:
                    break
    chamado = _CHAMADO.search(texto_inteiro)
    proprio = NUMERO_DO_PAINEL.search(texto_inteiro)
    return {
        "valores": valores,
        "fontes": leitura.fontes,
        "consumidas": leitura.consumidas,
        "itens_rotulo": leitura.itens_rotulo,
        "secoes_tabela": leitura.secoes_tabela,
        "linhas_extra": leitura.linhas_extra,
        "tipo_pelo_titulo": tipo_pelo_titulo,
        "prioridade_solta": prioridade_solta,
        "garantia_em_frase": garantia_em_frase,
        "chamado": int(chamado.group(1)) if chamado else None,
        "numero_do_painel": (int(proprio.group(1)), int(proprio.group(2))) if proprio else None,
    }


# ======================================================================
# OS ITENS
# ======================================================================
_PALAVRAS_DE_SERVICO = re.compile(
    r"\b(mao\s+de\s+obra|servic\w*|conserto|reparo|troca|substituic\w*|instalac\w*|montag\w*|desmontag\w*|"
    r"ajuste|regulag\w*|limpeza|lubrificac\w*|revisao|manutenc\w*|solda\w*|costura|recolag\w*|colagem|"
    r"pintura|higienizac\w*|calibrac\w*|configurac\w*|diagnostico|teste|testes|retifica|rebobinament\w*|"
    r"recuperac\w*|aplicac\w*|hora\s+tecnica|horas\s+tecnicas|vistoria|reforma|alinhamento)\b"
)
_PALAVRAS_DE_DESLOCAMENTO = re.compile(
    r"\b(deslocamento|km|quilometr\w*|viagem|transporte|frete\s+tecnico|taxa\s+de\s+visita|visita\s+tecnica|"
    r"combustivel|pedagio|estadia|hospedagem)\b"
)


def tipo_do_item(descricao: str, *, coluna_tipo: str = "", secao: str = "") -> str:
    """Peça, serviço, deslocamento ou outro -- pela coluna, pela seção, pelas palavras."""
    if coluna_tipo:
        sem = det.sem_acento(coluna_tipo)
        if re.search(r"\b(peca|pecas|material|materiais|produto|pc)\b", sem):
            return "peca"
        if re.search(r"\b(servico|servicos|mao de obra|mo)\b", sem):
            return "servico"
        if re.search(r"\b(deslocamento|visita|viagem|km)\b", sem):
            return "deslocamento"
        if re.search(r"\b(outro|outros)\b", sem):
            return "outro"
    if secao:
        return secao
    sem = det.sem_acento(descricao)
    if _PALAVRAS_DE_DESLOCAMENTO.search(sem):
        return "deslocamento"
    if _PALAVRAS_DE_SERVICO.search(sem):
        return "servico"
    return "peca"


def itens_das_tabelas(itens_det: list[dict], linhas: list[dict], *, tipos: dict, secoes: dict) -> list[dict]:
    """Os itens das tabelas (a leitura do orçamento), com o tipo da O.S."""
    celulas = {(l["tabela"], l["linha"], l["coluna"]): l for l in linhas if l["tabela"]}
    saida = []
    for item in itens_det:
        if item.get("contexto") != "tabela":
            continue
        achado = re.match(r"^(.*T\d+)L(\d+)$", item["linha_fonte"])
        tabela, numero = (achado.group(1), int(achado.group(2))) if achado else ("", 0)
        coluna_tipo = ""
        if tabela in tipos:
            celula = celulas.get((tabela, numero, tipos[tabela][1]))
            coluna_tipo = celula["texto"] if celula else ""
        descricao = det.espacos((item["descricao"] or {}).get("valor") or "")
        if not descricao:
            continue
        saida.append(_item_lido(item, descricao, tipo_do_item(
            descricao, coluna_tipo=coluna_tipo, secao=secoes.get(tabela, ""),
        ), "tabela"))
    return saida


def itens_dos_paragrafos(itens_det: list[dict], consumidas: set) -> list[dict]:
    saida = []
    for item in itens_det:
        if item.get("contexto") != "paragrafo" or item["linha_fonte"] in consumidas:
            continue
        descricao = det.espacos((item["descricao"] or {}).get("valor") or "")
        if not descricao or chave(descricao) in _POR_CHAVE:
            continue
        saida.append(_item_lido(item, descricao, tipo_do_item(descricao), "paragrafo"))
    return saida


def _item_lido(item: dict, descricao: str, tipo: str, como: str) -> dict:
    """A linha lida, com o unitário tirado do total quando a conta é exata."""
    quantidade = (item.get("quantidade") or {}).get("valor")
    unitario = (item.get("valor_unitario") or {}).get("valor")
    total = (item.get("total_linha") or {}).get("valor")
    recusa = "; ".join(motivo for _, motivo, _ in item.get("recusas") or [])
    if quantidade is None and not recusa:
        quantidade = 1
    if unitario is None and total is not None and quantidade:
        conta = (Decimal(total) / Decimal(quantidade)).quantize(CENTAVO, rounding=ROUND_HALF_UP)
        if conta * quantidade == total:
            unitario = conta
    return {
        "tipo": tipo, "descricao": descricao[:200], "quantidade": quantidade, "valor_unitario": unitario,
        "total_linha": total, "recusa": recusa, "fonte": (item["descricao"] or {}).get("original", "")[:120],
        "como": como,
    }


def juntar_itens(das_tabelas: list[dict], dos_rotulos: list[dict], dos_paragrafos: list[dict]) -> list[dict]:
    """Tabela primeiro; o rótulo e o parágrafo só entram com o que a tabela não tem."""
    itens = list(das_tabelas)
    vistos = {_normalizar(i["descricao"]) for i in itens}
    for item in dos_rotulos + (dos_paragrafos if not das_tabelas else []):
        if _normalizar(item["descricao"]) in vistos:
            continue
        if item["tipo"] == "peca" and item["como"] == "rotulo" and any(i["tipo"] == "peca" for i in itens):
            # "Peças: R$ 300,00" é a soma das peças que a tabela já lista.
            continue
        vistos.add(_normalizar(item["descricao"]))
        itens.append(item)
    return itens[:80]


def desconto_percentual(itens: list[dict], percentual: Decimal) -> Decimal | None:
    soma = Decimal("0.00")
    for item in itens:
        if item["valor_unitario"] is None or not item["quantidade"]:
            return None
        soma += (Decimal(item["valor_unitario"]) * int(item["quantidade"])).quantize(CENTAVO)
    return (soma * Decimal(percentual) / Decimal(100)).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def garantia_ate(garantia: dict | None, base: date) -> date | None:
    if not garantia or garantia.get("sem"):
        return None
    if garantia.get("data"):
        return date.fromisoformat(garantia["data"])
    if garantia.get("dias"):
        return base + timedelta(days=int(garantia["dias"]))
    if garantia.get("meses"):
        return somar_meses(base, int(garantia["meses"]))
    return None
