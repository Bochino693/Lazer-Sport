"""O cliente da O.S.: quem é, se já está cadastrado, e o cadastro quando não está.

A LEITURA É A DO ORÇAMENTO (`importacao_word`): os rótulos ("Cliente:",
"CPF:", "Tel.:", "Endereço:") pela `deterministica`, e o texto sem rótulo
pela `identificar` -- que deixa de fora a fábrica (CNPJ, telefones, e-mail,
endereço da casa) e a equipe (o nome de quem atende, o celular de quem
assina). Aqui chegam só as linhas que não são da O.S.: defeito, técnico e
série já saíram (ver `campos.ler`).

O CASAMENTO COM O CADASTRO, na ordem do que menos erra -- a mesma do
orçamento (`catalogo.casar_cliente`): CPF/CNPJ, e-mail, telefone (os
dígitos, como quer que estejam escritos); o nome só sugere, e por isso
nunca liga sozinho. A diferença é a conta do banco: as três chaves fortes
vão numa consulta só (no orçamento são três), e o nome só é procurado
quando nenhuma delas achou.

O CADASTRO NOVO segue as regras da aba Clientes (`clientes.salvar_cliente`
e `salvar_endereco`): nome, um contato, CPF/CNPJ válido e de mais ninguém,
nome que ainda não existe. Cliente que já existia só ganha o que está VAZIO
no cadastro, e o endereço só se não tinha nenhum. O endereço gravado entra
no mapa pelo caminho de sempre do cadastro (a coordenada é procurada em
segundo plano, fora daqui).
"""

from __future__ import annotations

from django.db.models import Exists, OuterRef, Q

from ..importacao_word import catalogo as cat
from ..importacao_word import deterministica as det
from ..importacao_word import formulario, identificar
from ..validacoes import chave_documento, documento_valido
from .campos import chave as chave_rotulo


def ler(linhas: list[dict], *, hoje, contexto: dict) -> dict:
    """{"dados": o que o documento diz do cliente, "lido": a leitura inteira}."""
    empresa = contexto["empresa"]
    internos = contexto["internos"]
    fora = identificar.linhas_de_fora(linhas, empresa=empresa, internos=internos)
    trechos = identificar.lado_da_casa(linhas)
    fora = set(fora) | identificar.linhas_inteiras_da_casa(linhas, trechos)
    lido = det.ler(linhas, hoje=hoje, empresa=empresa, fora=fora, trechos_da_casa=trechos)
    achados = identificar.identificar(linhas, empresa=empresa, internos=internos, fora=fora,
                                      trechos_da_casa=trechos)
    identificar.completar(lido["campos"], achados, internos=internos, empresa=empresa,
                          contrato=bool(trechos))
    c = lido["campos"]

    def valor(nome):
        campo = c.get(nome) or {}
        bruto = campo.get("valor")
        return det.espacos(str(bruto)) if bruto not in (None, "") else ""

    nome = valor("cliente")
    estabelecimento = valor("estabelecimento")
    if estabelecimento and _mesmo(estabelecimento, nome):
        estabelecimento = ""
    documento = valor("documento")
    documento_invalido = ""
    if documento and not documento_valido(documento):
        documento_invalido, documento = det.formatar_documento(documento), ""
    telefone = valor("telefone")
    escrito = bool((c.get("telefone") or {}).get("whatsapp_escrito"))
    endereco = {
        "cep": det.formatar_cep(valor("cep")) if valor("cep") else "",
        "endereco": valor("logradouro")[:120],
        "numero": valor("numero")[:10],
        "complemento": valor("complemento")[:60],
        "bairro": valor("bairro")[:50],
        "cidade": valor("cidade")[:60],
        "estado": valor("uf").upper()[:2],
    }
    texto_endereco = valor("endereco") or _endereco_em_linha(endereco)
    return {
        "dados": {
            "nome": nome[:90],
            "nome_pelo_rotulo": bool(nome) and not (c.get("cliente") or {}).get("identificado"),
            "estabelecimento": estabelecimento[:150],
            "contato": valor("contato")[:120] if not _mesmo(valor("contato"), nome) else "",
            "documento": det.formatar_documento(documento) if documento else "",
            "documento_invalido": documento_invalido,
            "telefone": det.formatar_telefone(telefone) if telefone else "",
            "whatsapp": formulario.whatsapp_padrao(telefone, escrito=escrito) == "sim" if telefone else False,
            "email": valor("email").lower()[:150],
            "endereco": endereco,
            "endereco_texto": texto_endereco[:320],
        },
        "lido": lido,
    }


def _mesmo(a: str, b: str) -> bool:
    return bool(a) and bool(b) and cat._nome_para_comparar(a) == cat._nome_para_comparar(b)  # noqa: SLF001


def _endereco_em_linha(endereco: dict) -> str:
    rua = ", ".join(p for p in (endereco["endereco"], endereco["numero"], endereco["complemento"]) if p)
    cidade = "/".join(p for p in (endereco["cidade"], endereco["estado"]) if p)
    partes = [p for p in (rua, endereco["bairro"], cidade) if p]
    if endereco["cep"]:
        partes.append(f"CEP {endereco['cep']}")
    return " – ".join(partes)


def tem_endereco(endereco: dict) -> bool:
    """O bastante para o cadastro guardar: rua e cidade, ou o CEP (que completa)."""
    return bool((endereco.get("endereco") and endereco.get("cidade")) or endereco.get("cep"))


# ======================================================================
# O CADASTRO QUE JÁ EXISTE
# ======================================================================
def opcao(cliente) -> dict:
    detalhe = " · ".join(p for p in (cliente.nome_estabelecimento, cliente.telefone, cliente.email or "") if p)
    return {"id": cliente.pk, "nome": cliente.nome_cliente, "detalhe": detalhe[:120]}


def casar(dados: dict) -> dict:
    """O cliente do cadastro: {"cliente", "modo", "motivo", "candidatos", "conflito"}.

    modo: "existente" (CPF/CNPJ, e-mail ou telefone de um cadastro só),
    "duvida" (só o nome bate -- a pessoa confirma), "novo" (nada bate) ou
    "conflito" (dois dados apontam para cadastros diferentes).
    """
    from ..models import Cliente, EnderecoCliente

    chave = chave_documento(dados.get("documento", ""))
    email = (dados.get("email") or "").strip().lower()
    digitos = det.digitos_do_telefone(dados.get("telefone", ""))
    filtro = Q()
    usado = False
    if len(chave) in (11, 14):
        filtro |= Q(documento_chave=chave) | Q(cnpj_estabelecimento=chave)
        usado = True
    if email:
        filtro |= Q(email__iexact=email)
        usado = True
    if len(digitos) in (10, 11):
        filtro |= Q(telefone_digitos__in=[digitos, "55" + digitos])
        usado = True
    com_endereco = Exists(EnderecoCliente.objects.filter(cliente=OuterRef("pk")))
    fortes = list(Cliente.objects.filter(filtro).annotate(tem_endereco=com_endereco)[:10]) if usado else []

    def unico(lista):
        vistos = {c.pk: c for c in lista}
        return list(vistos.values())[0] if len(vistos) == 1 else None

    por_documento = unico([c for c in fortes if chave and chave in (c.documento_chave, c.cnpj_estabelecimento)])
    por_email = unico([c for c in fortes if email and (c.email or "").strip().lower() == email])
    por_telefone = unico([c for c in fortes if digitos and c.telefone_digitos in (digitos, "55" + digitos)])
    for escolhido, motivo in ((por_documento, "mesmo CPF/CNPJ do cadastro"), (por_email, "mesmo e-mail do cadastro"),
                              (por_telefone, "mesmo telefone do cadastro")):
        if escolhido is None:
            continue
        outros = [o for o in (por_documento, por_email, por_telefone) if o is not None and o.pk != escolhido.pk]
        if outros:
            return {
                "cliente": None, "modo": "conflito", "candidatos": [opcao(c) for c in [escolhido] + outros],
                "motivo": (
                    f"Os dados do documento apontam para dois cadastros: “{escolhido.nome_cliente}” e "
                    f"“{outros[0].nome_cliente}”. Escolha o certo."
                ),
            }
        return {"cliente": escolhido, "modo": "existente", "motivo": motivo, "candidatos": []}

    por_nome = _pelo_nome(dados)
    if por_nome:
        cidade = cat._normalizar(dados.get("endereco", {}).get("cidade", ""))  # noqa: SLF001
        mesma_cidade = [c for c, cidade_cadastro in por_nome if cidade and cidade_cadastro == cidade]
        lista = [c for c, _ in por_nome]
        if len(lista) == 1:
            motivo = ("mesmo nome e mesma cidade do cadastro: confirme se é o mesmo cliente" if mesma_cidade
                      else "mesmo nome de um cliente do cadastro: confirme se é a mesma pessoa")
        else:
            motivo = f"o nome bate com {len(lista)} clientes do cadastro: escolha o certo"
        ordem = mesma_cidade + [c for c in lista if c not in mesma_cidade]
        return {"cliente": None, "modo": "duvida", "motivo": motivo, "candidatos": [opcao(c) for c in ordem[:4]]}
    return {"cliente": None, "modo": "novo", "motivo": "nenhum cadastro com estes dados", "candidatos": []}


def _pelo_nome(dados: dict) -> list[tuple]:
    """Os cadastros com o mesmo nome (do cliente ou do estabelecimento), sem acento e sem "Ltda"."""
    from ..models import Cliente
    from ..views_gestao import BuscaItensOrcamentoView

    nomes = [n for n in (dados.get("nome", ""), dados.get("estabelecimento", "")) if cat._nome_para_comparar(n)]  # noqa: SLF001
    if not nomes:
        return []
    filtro = Q()
    for nome in nomes:
        palavra = max(cat._nome_para_comparar(nome).split(), key=len)  # noqa: SLF001
        padrao = BuscaItensOrcamentoView._padrao_sem_acento(palavra)  # noqa: SLF001
        filtro |= Q(nome_cliente__iregex=padrao) | Q(nome_estabelecimento__iregex=padrao)
    achados = []
    linhas = Cliente.objects.filter(filtro).values_list(
        "pk", "nome_cliente", "nome_estabelecimento", "telefone", "email", "enderecos__cidade",
    )[:80]
    vistos = set()
    for pk, nome_cliente, nome_estabelecimento, telefone, email, cidade in linhas:
        if pk in vistos:
            continue
        if any(cat._mesmo_nome(nome, cadastrado) for nome in nomes  # noqa: SLF001
               for cadastrado in (nome_cliente, nome_estabelecimento)):
            vistos.add(pk)
            achados.append((Cliente(pk=pk, nome_cliente=nome_cliente, nome_estabelecimento=nome_estabelecimento,
                                    telefone=telefone, email=email), cat._normalizar(cidade or "")))  # noqa: SLF001
    return achados


# ======================================================================
# CADASTRAR OU COMPLETAR
# ======================================================================
def pode_cadastrar(dados: dict) -> str:
    """"" quando o documento traz o bastante para um cadastro novo; senão, o motivo."""
    if not dados.get("nome"):
        return "o documento não diz o nome do cliente"
    if not (dados.get("telefone") or dados.get("email")):
        return "o documento traz o nome, mas nem telefone nem e-mail para o cadastro"
    return ""


def _limpo(dados: dict) -> dict:
    return {
        "nome": dados.get("nome", ""), "estabelecimento": dados.get("estabelecimento", ""),
        "documento": dados.get("documento", ""), "telefone": dados.get("telefone", ""),
        "whatsapp": bool(dados.get("whatsapp")), "email": dados.get("email", ""),
        "tipo": _tipo(dados),
    }


def _tipo(dados: dict) -> str:
    from ..importacao_word.conferencia import _tipo_sugerido

    return _tipo_sugerido(dados.get("estabelecimento") or dados.get("nome", ""), dados.get("documento", ""))[0]


def gravar(request, dados: dict, existente, *, arquivo: str) -> dict:
    """Cadastra (ou completa) o cliente. {"cliente", "novo", "completados"}.

    ErroDeFormulario do cadastro (nome repetido, e-mail de outro cliente)
    sobe para quem chamou: a O.S. fica esperando a pessoa decidir.
    """
    from .. import clientes as svc_clientes

    limpo = _limpo(dados)
    if existente is None:
        pedido = formulario._dados_do_cliente(None, limpo, completar=False)  # noqa: SLF001
        pedido["observacoes"] = f"Cadastrado pela leitura da O.S. no documento “{arquivo[:80]}”."
        cliente = svc_clientes.salvar_cliente(formulario._pedido_para_o_cadastro(request, pedido), None)  # noqa: SLF001
        completados = []
        precisa_endereco = True
    else:
        faltando = _o_que_completar(existente, limpo)
        precisa_endereco = not getattr(existente, "tem_endereco", True) and tem_endereco(dados.get("endereco", {}))
        if faltando:
            pedido = formulario._dados_do_cliente(existente, limpo, completar=True)  # noqa: SLF001
            # O telefone do cadastro não muda aqui: se ele ainda não tem o
            # WhatsApp confirmado, continua assim (é o "salvar mesmo sem
            # confirmar" do cadastro à mão), e o resto é completado.
            pedido["confirmar_telefone_sem_whatsapp"] = "1"
            cliente = svc_clientes.salvar_cliente(formulario._pedido_para_o_cadastro(request, pedido), existente)  # noqa: SLF001
        else:
            cliente = existente
        completados = list(faltando)
    endereco = dados.get("endereco") or {}
    if precisa_endereco and tem_endereco(endereco):
        from ..utils import ErroDeFormulario

        try:
            svc_clientes.salvar_endereco(
                formulario._pedido_para_o_cadastro(request, dict(endereco, pais="Brasil")), cliente,  # noqa: SLF001
            )
            if existente is not None:
                completados.append("endereço")
        except ErroDeFormulario:
            # Endereço pela metade (só o número, a rua sem cidade) não
            # segura a O.S.: o cadastro fica sem ele, e o aviso conta.
            completados.append("endereço incompleto: não entrou")
    return {"cliente": cliente, "novo": existente is None, "completados": completados}


def _o_que_completar(cliente, limpo: dict) -> list[str]:
    saida = []
    for campo, rotulo, valor in (
        ("documento", "CPF/CNPJ", limpo["documento"]), ("telefone", "telefone", limpo["telefone"]),
        ("email", "e-mail", limpo["email"]), ("nome_estabelecimento", "estabelecimento", limpo["estabelecimento"]),
    ):
        if valor and not (getattr(cliente, campo, "") or ""):
            saida.append(rotulo)
    return saida


def nome_de_tecnico(texto: str) -> str:
    """"João Silva - (11) 99999-8888" -> "João Silva"."""
    corte = len(texto or "")
    for achado in det.telefones(texto) + det.emails(texto) + det.documentos(texto):
        corte = min(corte, achado["inicio"])
    return det.espacos((texto or "")[:corte]).strip(" -–—,;/|()")


def casar_tecnico(texto: str, tecnicos: list[dict]) -> dict | None:
    """O técnico da equipe pelo nome: completo, usuário, primeiro + último, ou o primeiro nome só dele."""
    nome = cat._normalizar(nome_de_tecnico(texto))  # noqa: SLF001
    if not nome:
        return None
    partes = nome.split()
    for tecnico in tecnicos:
        completo = cat._normalizar(tecnico["nome"])  # noqa: SLF001
        if nome in (completo, cat._normalizar(tecnico["usuario"])):  # noqa: SLF001
            return tecnico
    if len(partes) >= 2:
        pares = [t for t in tecnicos if cat._normalizar(t["nome"]).split()[:1] == partes[:1]  # noqa: SLF001
                 and cat._normalizar(t["nome"]).split()[-1:] == partes[-1:]]  # noqa: SLF001
        if len(pares) == 1:
            return pares[0]
        return None
    primeiros = [t for t in tecnicos if cat._normalizar(t["nome"]).split()[:1] == partes]  # noqa: SLF001
    return primeiros[0] if len(primeiros) == 1 else None


__all__ = ["ler", "casar", "gravar", "pode_cadastrar", "tem_endereco", "casar_tecnico", "nome_de_tecnico",
           "opcao", "chave_rotulo"]
