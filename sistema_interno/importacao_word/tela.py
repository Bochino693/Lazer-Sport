"""O que a tela de conferência mostra primeiro: a decisão e os painéis.

O PEDIDO: "vc pôs uma tela de muita descida, ponha um modal moderno estilo
app para perguntar se quer ou não gerar o orçamento ou só o cliente, dê
ênfase pros campos que ainda faltam direcionando o usuário a ele ... quase
uma automação". Nada aqui decide regra -- as regras continuam em
formulario.validar. Aqui só se resume, para a tela:

  * `decisao`: o resumo do que foi lido (cliente, CPF/CNPJ, telefone,
    e-mail, cidade), com "falta" no que faltou e de onde veio o resto; o
    cliente já cadastrado e o orçamento repetido; e os dois caminhos, cada
    um dizendo se dá para "Criar agora" (nada obrigatório faltando, nenhum
    alerta vermelho) ou o que falta;
  * `paineis`: os quatro painéis da tela guiada (Cliente, Endereço, Itens,
    Valores e condições), com a linha de resumo ("Buffet X · CNPJ ✓ ·
    WhatsApp ✓") e se abre ou não: abre só o que tem falta, alerta
    vermelho ou leitura de confiança baixa.
"""

from __future__ import annotations

from . import deterministica as det

PAINEIS = ("cliente", "endereco", "itens", "valores")
_PARTES_DO_ENDERECO = ("cep", "logradouro", "numero", "complemento", "bairro", "cidade", "uf")
_DADOS_DO_CLIENTE = ("nome", "estabelecimento", "documento", "telefone", "email", "contato")


def painel_da_pendencia(campo: str) -> str:
    """Em que painel mora o campo da pendência ("cliente.endereco" -> "endereco")."""
    if campo.startswith("cliente.endereco"):
        return "endereco"
    if campo.startswith("cliente."):
        return "cliente"
    if campo.startswith("itens") or campo == "orcamento.repetido":
        return "itens"
    return "valores"


def _origem(campo: dict) -> str:
    """De onde veio o valor, em palavras da tela."""
    return {
        "texto": "lido do texto", "tabelas": "do documento", "ambas": "do documento",
        "ia": "do documento", "cep": "pela consulta do CEP", "catalogo": "do catálogo",
    }.get((campo or {}).get("origem", ""), "")


def _tipo_do_documento(documento: str) -> str:
    return "CNPJ" if len(det.somente_digitos(documento)) == 14 else "CPF"


def resumo_do_cliente(envio: dict) -> str:
    partes = [envio.get("nome") or "sem nome"]
    if envio.get("estabelecimento"):
        partes.append(envio["estabelecimento"])
    partes.append(f"{_tipo_do_documento(envio['documento'])} ✓" if envio.get("documento") else "sem CPF/CNPJ")
    if envio.get("telefone"):
        partes.append("WhatsApp ✓" if envio.get("whatsapp") == "sim" else "Telefone ✓")
    if envio.get("email"):
        partes.append("E-mail ✓")
    if not envio.get("telefone") and not envio.get("email"):
        partes.append("sem contato")
    return " · ".join(partes)


def resumo_do_endereco(envio: dict) -> str:
    if not (envio.get("endereco") or envio.get("cidade") or envio.get("cep")):
        return "Sem endereço (opcional; sem ele não há alfinete no mapa)"
    rua = ", ".join(p for p in (envio.get("endereco"), envio.get("numero")) if p)
    cidade = "/".join(p for p in (envio.get("cidade"), envio.get("estado")) if p)
    partes = [p for p in (rua, envio.get("bairro"), cidade) if p]
    if envio.get("cep"):
        partes.append("CEP ✓")
    if envio.get("publicar_no_mapa"):
        partes.append("no mapa ✓")
    return " · ".join(partes)


def resumo_dos_itens(envio: dict, contas: dict) -> str:
    quantos = len(envio.get("itens") or [])
    if not quantos:
        return "Nenhum item"
    return f"{quantos} {'item' if quantos == 1 else 'itens'} · R$ {contas.get('subtotal', '0,00')}"


def resumo_dos_valores(envio: dict, contas: dict) -> str:
    frete = f"Frete R$ {envio['frete']}" if envio.get("frete") else "Frete a preencher"
    partes = [frete, f"Total R$ {contas.get('total', '0,00')}"]
    if envio.get("forma_pagamento"):
        partes.append(envio["forma_pagamento"])
    return " · ".join(partes)


def paineis(proposta: dict, envio: dict, validado: dict, do_orcamento: dict) -> dict:
    """Cada painel: resumo, quantas faltas, e se abre.

    As faltas do cliente e do endereço vêm do caminho escolhido agora; as
    do orçamento, da conferência com o orçamento (a tela as tem prontas
    para quem ligar o orçamento). Confiança baixa (as leituras discordam)
    também abre: é campo para olhar.
    """
    faltas = {nome: 0 for nome in PAINEIS}
    for pendencia in validado["pendencias"]:
        painel = painel_da_pendencia(pendencia["campo"])
        if painel in ("cliente", "endereco"):
            faltas[painel] += 1
    for pendencia in do_orcamento["pendencias"]:
        painel = painel_da_pendencia(pendencia["campo"])
        if painel in ("itens", "valores"):
            faltas[painel] += 1
    cliente = proposta["cliente"]
    baixa = {
        "cliente": any(cliente[nome].get("confianca") == "baixa" for nome in _DADOS_DO_CLIENTE),
        "endereco": any(cliente[nome].get("confianca") == "baixa" for nome in _PARTES_DO_ENDERECO),
        "itens": any(
            item[nome].get("confianca") == "baixa"
            for item in proposta["itens"] for nome in ("quantidade", "valor_unitario")
        ),
        "valores": any(proposta["valores"][nome].get("confianca") == "baixa" for nome in ("frete", "desconto")),
    }
    contas = do_orcamento.get("contas") or {}
    resumos = {
        "cliente": resumo_do_cliente(envio),
        "endereco": resumo_do_endereco(envio),
        "itens": resumo_dos_itens(envio, contas),
        "valores": resumo_dos_valores(envio, contas),
    }
    return {
        nome: {"faltas": faltas[nome], "aberto": bool(faltas[nome] or baixa[nome]), "resumo": resumos[nome]}
        for nome in PAINEIS
    }


def _rotulos(pendencias: list[dict], limite: int = 4) -> list[str]:
    vistos = []
    for pendencia in pendencias:
        if pendencia["rotulo"] not in vistos:
            vistos.append(pendencia["rotulo"])
    return vistos[:limite]


def decisao(proposta: dict, envio: dict, *, do_cliente: dict, do_orcamento: dict,
            pergunta: dict | None, oferta: dict | None) -> dict:
    """O modal da decisão: o que foi lido, o que já existe, e os dois caminhos."""
    cliente = proposta["cliente"]
    existente = cliente["vinculo"]["cliente_id"] and envio["cliente_modo"] == "existente"

    def linha(chave, rotulo, valor, campo, obrigatorio=False):
        origem = _origem(campo)
        if valor and not origem and existente:
            origem = "do cadastro"
        return {"chave": chave, "rotulo": rotulo, "valor": valor, "origem": origem,
                "obrigatorio": obrigatorio, "falta": not valor}

    sem_contato = not envio["telefone"] and not envio["email"]
    cidade = "/".join(p for p in (envio["cidade"], envio["estado"]) if p)
    linhas = [
        linha("nome", "Cliente", envio["nome"], cliente["nome"], obrigatorio=True),
        linha("estabelecimento", "Estabelecimento", envio["estabelecimento"], cliente["estabelecimento"]),
        linha("documento", "CPF/CNPJ", envio["documento"], cliente["documento"]),
        linha("telefone", "WhatsApp" if envio["telefone"] and envio["whatsapp"] == "sim" else "Telefone",
              envio["telefone"], cliente["telefone"], obrigatorio=sem_contato),
        linha("email", "E-mail", envio["email"], cliente["email"], obrigatorio=sem_contato),
        linha("cidade", "Cidade/UF", cidade, cliente["cidade"]),
    ]
    tem_orcamento = bool(pergunta or oferta)
    return {
        "linhas": linhas,
        "ja_cadastrado": {
            "id": cliente["vinculo"]["cliente_id"],
            "nome": (cliente["vinculo"]["opcao"] or {}).get("rotulo", ""),
            "motivo": cliente["vinculo"]["motivo"],
        } if cliente["vinculo"]["cliente_id"] else None,
        "repetido": do_orcamento.get("repetido"),
        "orcamento": {
            "recomendado": tem_orcamento,
            "brinquedos": (pergunta or {}).get("brinquedos", []),
            "fora_do_catalogo": (pergunta or {}).get("fora_do_catalogo", 0),
            "itens": len(proposta["itens"]),
            "total": (oferta or {}).get("total") or (do_orcamento.get("contas") or {}).get("total", ""),
            "pronto": do_orcamento["pronto"],
            "faltam": _rotulos(do_orcamento["pendencias"]),
            "quantas_faltam": len(do_orcamento["pendencias"]),
        },
        "cliente": {
            "recomendado": not tem_orcamento,
            "pronto": do_cliente["pronto"],
            "faltam": _rotulos(do_cliente["pendencias"]),
            "quantas_faltam": len(do_cliente["pendencias"]),
        },
    }
