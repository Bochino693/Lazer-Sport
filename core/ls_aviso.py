"""Os recados do Django (`messages`) como avisos de aplicativo.

O PEDIDO: "este tipo de mensagem deve virar um modal moderno que aparece
estilo app para avisar" -- sobre a linha "A importação de “...docx” foi
descartada.", que aparecia como caixa do Bootstrap no alto da tela.

Os recados agora saem do servidor como DADOS (um cartão por recado, com
`data-*`), e o `ls-aviso.js` (core/static/site/, o mesmo no site e no
painel) os mostra como toast -- ou como folha, quando pedem atenção. Sem
JavaScript, os mesmos cartões ficam no alto do conteúdo, com a cara dos
toasts. Quem desenha é `partials/ls_avisos.html`, pela tag
`{% avisos_do_app %}` (core/templatetags/ls_aviso.py).

A VIEW ESCOLHE A APRESENTAÇÃO PELO `extra_tags`, em pedaços separados
por ";" (ou só espaço, para as marcas sem valor):

    modal                  folha (centro no PC, de baixo no celular), com
                           um botão: para o que precisa de atenção
    fixo                   o toast não some sozinho (o de erro já não some)
    titulo:<texto>         o título em negrito (sem ele, ver TITULOS)
    icone:<nome>           um dos ícones de ls-aviso.js (ICONES)
    acao:<url>|<rótulo>    o botão de ação do aviso ("Ver", "Importar outro")

    messages.info(request, "...", extra_tags="titulo:Importação descartada; icone:arquivo-x")
    messages.error(request, "...", extra_tags="modal; titulo:E-mail não configurado")

Para não escrever a sintaxe à mão, `avisar(request, texto, ...)` monta o
`extra_tags`. O que não é uma dessas marcas é ignorado (fica em
`message.tags`, como sempre).
"""

from __future__ import annotations

import re
import uuid

from django.contrib import messages

#: O nível do Django no nome que o JavaScript e o CSS usam.
NIVEIS = {
    messages.DEBUG: "info",
    messages.INFO: "info",
    messages.SUCCESS: "sucesso",
    messages.WARNING: "alerta",
    messages.ERROR: "erro",
}

#: Ícones que o ls-aviso.js desenha (o objeto ICONES de lá). Um nome fora
#: desta lista vira o ícone do nível.
ICONES = {
    "sucesso", "info", "alerta", "erro", "lixeira", "arquivo", "arquivo-x",
    "salvo", "pessoa", "carrinho", "email", "endereco",
}

#: O título de quem não deu um: o recado de sempre, reconhecido pelo verbo.
#: Um por linha, o primeiro que casar vale. O texto do recado continua
#: inteiro embaixo -- o título só diz, numa palavra, o que aconteceu.
TITULOS = (
    (re.compile(r"\bimporta[çc][ãa]o\b.*\bdescartad", re.I), "Importação descartada", "arquivo-x"),
    (re.compile(r"\b(exclu[íi]d[oa]s?|removid[oa]s?|apagad[oa]s?)\b", re.I), None, "lixeira"),
    (re.compile(r"\b(cancelad[oa]s?)\b", re.I), None, "sucesso"),
    (re.compile(r"\be-?mail\b.*\benviad[oa]\b", re.I), "E-mail enviado", "email"),
    (re.compile(r"\b(cadastrad[oa]s?|criad[oa]s?)\b", re.I), None, "sucesso"),
    (re.compile(r"\b(adicionad[oa]s?)\b.*\bcarrinho\b", re.I), "No carrinho", "carrinho"),
    (re.compile(r"\b(adicionad[oa]s?|inclu[íi]d[oa]s?)\b", re.I), None, "sucesso"),
    (re.compile(r"\b(salv[oa]s?|atualizad[oa]s?|ajustad[oa]s?|recolocad[oa]s?)\b", re.I), None, "salvo"),
)

#: O erro que é um campo a acertar ("Informe o título da promoção."): a
#: pessoa não errou nada, só falta um dado.
FALTA_DADO = re.compile(
    r"^(informe|escolha|digite|selecione|preencha|confira|descreva|cadastre|por favor)\b", re.I,
)

#: Sem título dado nem verbo conhecido: o do nível.
TITULO_DO_NIVEL = {
    "sucesso": "Pronto",
    "info": "Aviso",
    "alerta": "Atenção",
    "erro": "Não foi possível",
}

#: O "voltei para o painel" do endereço antigo (`?recuperado=pagina`).
RECUPERADO = {
    "nivel": "info",
    "titulo": "Endereço antigo",
    "texto": "O endereço acessado era antigo ou não existe mais. Você voltou com segurança para o painel.",
    "icone": "endereco",
}


def ler_marcas(extra_tags: str) -> dict:
    """O `extra_tags` (ver o topo) em dicionário: modal, fixo, titulo, icone, acao."""
    marcas = {"modal": False, "fixo": False, "titulo": "", "icone": "", "acao": None}
    for pedaco in (extra_tags or "").split(";"):
        pedaco = pedaco.strip()
        if not pedaco:
            continue
        chave, dois_pontos, valor = pedaco.partition(":")
        chave = chave.strip().lower()
        if dois_pontos and chave in {"titulo", "icone", "acao"}:
            valor = valor.strip()
            if chave == "acao":
                url, _, rotulo = valor.partition("|")
                if url.strip() and rotulo.strip():
                    marcas["acao"] = {"url": url.strip(), "rotulo": rotulo.strip()}
            elif chave == "icone":
                marcas["icone"] = valor if valor in ICONES else ""
            else:
                marcas["titulo"] = valor
            continue
        # Marcas sem valor podem vir juntas: "modal fixo".
        for palavra in pedaco.lower().split():
            if palavra in {"modal", "fixo"}:
                marcas[palavra] = True
    return marcas


def titulo_e_icone(texto: str, nivel: str) -> tuple[str, str]:
    """O título e o ícone de quem não deu: pelo verbo do recado, ou pelo nível.

    "Cliente “X” excluído." vira "Excluído", com a lixeira. O verbo só vale
    para recado de sucesso ou informação: "Esta manutenção não pode ser
    cancelada." é erro, e o título dele é o do erro.
    """
    if nivel in {"sucesso", "info"}:
        for padrao, titulo, icone in TITULOS:
            achado = padrao.search(texto)
            if achado:
                return titulo or achado.group(1).capitalize(), icone
    if nivel in {"erro", "alerta"} and FALTA_DADO.search(texto.strip()):
        return "Confira", "alerta"
    return TITULO_DO_NIVEL[nivel], nivel


def aviso_do_recado(recado) -> dict:
    """Um `Message` do Django no dicionário que o template e o JS leem."""
    nivel = NIVEIS.get(recado.level, "info")
    texto = str(recado.message)
    marcas = ler_marcas(recado.extra_tags or "")
    titulo_padrao, icone_padrao = titulo_e_icone(texto, nivel)
    return {
        "nivel": nivel,
        "titulo": marcas["titulo"] or titulo_padrao,
        "texto": texto,
        "icone": marcas["icone"] or icone_padrao,
        # O erro que precisa de atenção é folha; o resto é toast.
        "modal": marcas["modal"],
        "fixo": marcas["fixo"] or nivel == "erro",
        "acao": marcas["acao"],
    }


def avisos_da_pagina(recados, *, recuperado: bool = False) -> dict:
    """Tudo o que o `partials/ls_avisos.html` desenha.

    `chave` é única por resposta: o JS lembra (na aba) as que já mostrou, e
    a mesma página que volta do cache da navegação suave não repete o aviso.
    """
    avisos = [aviso_do_recado(recado) for recado in (recados or ())]
    if recuperado:
        avisos.insert(0, dict(RECUPERADO, modal=False, fixo=False, acao=None))
    return {"avisos": avisos, "chave": uuid.uuid4().hex[:16] if avisos else ""}


def avisar(request, texto, *, nivel=messages.INFO, titulo="", icone="", modal=False,
           fixo=False, acao=None):
    """`messages.add_message` com o `extra_tags` já escrito na convenção.

        avisar(request, "“X.docx” saiu da fila.", nivel=messages.SUCCESS,
               titulo="Importação descartada", icone="arquivo-x",
               acao=(reverse("importar_orcamento_word"), "Importar outro"))
    """
    marcas = []
    if modal:
        marcas.append("modal")
    if fixo:
        marcas.append("fixo")
    if titulo:
        marcas.append(f"titulo:{titulo}")
    if icone:
        marcas.append(f"icone:{icone}")
    if acao:
        url, rotulo = acao
        marcas.append(f"acao:{url}|{rotulo}")
    messages.add_message(request, nivel, texto, extra_tags="; ".join(marcas))
