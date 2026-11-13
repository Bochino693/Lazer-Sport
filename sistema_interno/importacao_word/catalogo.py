"""Cada item com o produto certo do catálogo, e o cliente com o cadastro.

O ERRO QUE MAIS CUSTA AQUI NÃO É "NÃO ACHEI" -- é "achei o vizinho". O
catálogo tem "Brinquedão Modelo 2" e "Brinquedão Modelo 5", "Cama
elástica 3 m" e "Cama elástica 4 m": nomes que diferem num número. Uma
semelhança de texto qualquer daria 90% para os dois, e a proposta sairia
com o brinquedo errado e o preço do outro. Por isso:

  1. nome exato (sem acento e sem caixa, pelo `_normalizar` da Arena)
     vem primeiro, e é o único vínculo automático "alto" por nome;
  2. a semelhança por palavras vem depois, e os NÚMEROS pesam à parte:
     o número do modelo, a medida ("3 m"), as polegadas. Número que
     discorda derruba o candidato; número que falta pesa contra;
  3. abaixo do limite o item fica SEM VÍNCULO e a pessoa escolhe -- e
     no meio do caminho fica sugerido, mas pedindo confirmação.

A IA pode ajudar a escolher entre os candidatos (`ia.escolher_produtos`),
mas só responde um id da lista ou "nenhum", e a escolha dela nunca vira
confiança alta: ainda é a pessoa que confirma.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from django.db.models import Q

from core.arena import _normalizar
from core.models import Brinquedos, PecasReposicao

from ..models import Cliente, ProdutoInterno
from ..validacoes import chave_documento
from .deterministica import digitos_do_telefone, moeda, sem_acento, valores_em_reais

#: A partir daqui o vínculo é automático (e ainda assim mostrado).
LIMITE_ALTO = 0.93
#: Daqui até o alto, o produto vem sugerido e a pessoa confirma.
LIMITE_MEDIO = 0.62
#: Diferença mínima para o segundo colocado. Dois candidatos quase
#: empatados nunca são "certeza", por mais alto que seja o primeiro.
FOLGA = 0.08

PALAVRAS_VAZIAS = {
    "de", "da", "do", "das", "dos", "com", "para", "p", "c", "e", "a", "o", "as", "os",
    "em", "no", "na", "nos", "nas", "um", "uma", "sem", "por", "ao", "x", "tipo", "linha",
}
SINONIMOS = {
    "polegadas": "pol", "polegada": "pol", "pol": "pol",
    "metros": "m", "metro": "m", "mts": "m", "mt": "m", "m": "m",
    "centimetros": "cm", "cm": "cm", "milimetros": "mm", "mm": "mm",
    "mod": "modelo", "modelo": "modelo", "modelos": "modelo",
    "n": "numero", "nr": "numero", "nro": "numero", "numero": "numero", "no": "numero",
    "v": "versao", "versao": "versao", "ver": "versao",
    "lugares": "lugares", "lugar": "lugares", "jogadores": "jogadores",
    "kg": "kg", "litros": "l", "l": "l", "volts": "v", "w": "w", "watts": "w",
}
ROTULOS_DE_NUMERO = {"modelo", "numero", "versao", "serie", "tamanho", "tam"}
UNIDADES_DE_NUMERO = {"m", "cm", "mm", "pol", "lugares", "jogadores", "kg", "l", "w"}


# ======================================================================
# PALAVRAS E NÚMEROS
# ======================================================================
def palavras(texto: str) -> list[str]:
    """Palavras e números de um nome, já no singular e com sinônimos.

    "Cama Elástica 3,5m" -> ["cama", "elastica", "3.5", "m"]
    "TV 32\\" Modelo3"   -> ["tv", "32", "modelo", "3"]
    """
    base = sem_acento(texto or "")
    saida = []
    for pedaco in re.findall(r"\d+(?:[.,]\d+)?|[a-z]+", base):
        if pedaco[0].isdigit():
            if re.fullmatch(r"\d{1,3}\.\d{3}", pedaco):
                pedaco = pedaco.replace(".", "")
            pedaco = pedaco.replace(",", ".")
            if "." in pedaco:
                pedaco = pedaco.rstrip("0").rstrip(".")
            else:
                pedaco = str(int(pedaco))
            saida.append(pedaco)
            continue
        pedaco = SINONIMOS.get(pedaco, pedaco)
        if pedaco in PALAVRAS_VAZIAS:
            continue
        if len(pedaco) > 3 and pedaco.endswith("s") and not pedaco.endswith("ss"):
            pedaco = pedaco[:-1]
        saida.append(pedaco)
    return saida


def numeros(lista: list[str]) -> set[str]:
    """Os números que identificam: "modelo=3", "3m", "32pol", ou só "3"."""
    achados = set()
    for posicao, palavra in enumerate(lista):
        if not palavra[0].isdigit():
            continue
        anterior = lista[posicao - 1] if posicao else ""
        seguinte = lista[posicao + 1] if posicao + 1 < len(lista) else ""
        if anterior in ROTULOS_DE_NUMERO:
            achados.add(f"{anterior}={palavra}")
        elif seguinte in UNIDADES_DE_NUMERO:
            achados.add(f"{palavra}{seguinte}")
        else:
            achados.add(palavra)
    return achados


def _so_numero(caracteristica: str) -> str:
    return re.sub(r"^[a-z]+=|[a-z]+$", "", caracteristica)


def _palavra_parecida(palavra: str, outras: list[str]) -> float:
    if palavra in outras:
        return 1.0
    if palavra[0].isdigit() or len(palavra) < 4:
        return 0.0
    melhor = 0.0
    for outra in outras:
        if outra[0].isdigit() or len(outra) < 4:
            continue
        semelhanca = SequenceMatcher(None, palavra, outra).ratio()
        if semelhanca > melhor:
            melhor = semelhanca
    return 0.8 if melhor >= 0.84 else 0.0


def pontuar(texto_item: str, nome_catalogo: str) -> tuple[float, str]:
    """Quanto o item se parece com o produto: 0 a 1, e por quê."""
    if _normalizar(texto_item) == _normalizar(nome_catalogo):
        return 1.0, "nome igual ao do catálogo"

    do_item = palavras(texto_item)
    do_catalogo = palavras(nome_catalogo)
    if not do_item or not do_catalogo:
        return 0.0, ""
    palavras_catalogo = [p for p in do_catalogo if not p[0].isdigit()] or do_catalogo
    palavras_item = [p for p in do_item if not p[0].isdigit()] or do_item

    # Cobertura: quanto do NOME DO CATÁLOGO está escrito no item. É a
    # direção certa -- a linha do orçamento costuma ter mais coisa ("2
    # diárias, montagem inclusa"), e isso não a afasta do produto.
    cobertura = sum(_palavra_parecida(p, palavras_item) for p in palavras_catalogo) / len(palavras_catalogo)
    # E um pouco da direção contrária, para "Cama" não casar com
    # "Cama elástica profissional com rede" tão bem quanto com "Cama".
    retorno = sum(_palavra_parecida(p, palavras_catalogo) for p in palavras_item) / len(palavras_item)
    sequencia = SequenceMatcher(None, " ".join(do_item), " ".join(do_catalogo)).ratio()
    pontos = 0.6 * cobertura + 0.15 * retorno + 0.25 * sequencia

    numeros_item = numeros(do_item)
    numeros_catalogo = numeros(do_catalogo)
    motivo = "palavras parecidas"
    if numeros_catalogo:
        so_numeros_item = {_so_numero(n) for n in numeros_item}
        conflito = False
        faltando = 0
        for caracteristica in numeros_catalogo:
            if caracteristica in numeros_item:
                continue
            rotulo = caracteristica.split("=")[0] if "=" in caracteristica else ""
            unidade = re.sub(r"^[\d.]+", "", caracteristica) if "=" not in caracteristica else ""
            # O item diz OUTRO número para a mesma coisa: "modelo 3" contra
            # "modelo 5", "4 m" contra "3 m". Isso é outro produto.
            if rotulo and any(n.startswith(rotulo + "=") for n in numeros_item):
                conflito = True
            elif unidade and any(re.fullmatch(r"[\d.]+" + re.escape(unidade), n) for n in numeros_item):
                conflito = True
            elif _so_numero(caracteristica) in so_numeros_item:
                continue  # "modelo 3" no catálogo, "3" solto no item
            else:
                faltando += 1
        if conflito:
            pontos *= 0.25
            motivo = "o número (modelo ou medida) é outro"
        elif faltando:
            pontos *= 0.7 ** faltando
            motivo = "falta o número que o catálogo tem no nome"
        else:
            motivo = "palavras e números conferem"
    if retorno < 0.85 and pontos >= LIMITE_ALTO:
        # "Cama elástica 3 m com rede" cobre o nome do catálogo inteiro, mas
        # diz mais do que ele: pode ser o mesmo produto ou uma versão dele
        # que o catálogo não tem. Vínculo automático, não; sugestão, sim.
        pontos = LIMITE_ALTO - 0.01
        motivo = "o Word descreve mais do que o nome do catálogo; confirme"
    return round(min(pontos, 0.99), 3), motivo


# ======================================================================
# O CATÁLOGO
# ======================================================================
def carregar_catalogo() -> list[dict]:
    """As três origens de item, como a busca do orçamento oferece.

    Mesmos filtros de `BuscaItensOrcamentoView`: brinquedo e peça sem
    filtrar por `ativo` (ativo ali quer dizer "aparece no site"), e
    produto de produção só ativo.
    """
    produtos = []
    for pk, nome, valor in Brinquedos.objects.values_list("pk", "nome_brinquedo", "valor_brinquedo"):
        produtos.append({"id": f"b:{pk}", "nome": nome, "grupo": "Brinquedos", "preco": valor, "ordem": 0})
    for pk, nome, codigo, preco in ProdutoInterno.objects.filter(ativo=True).values_list(
        "pk", "nome", "codigo", "preco_venda",
    ):
        produtos.append({"id": f"p:{pk}", "nome": nome, "grupo": "Produção", "preco": preco,
                         "codigo": codigo or "", "ordem": 1})
    for pk, nome, preco, uso in PecasReposicao.objects.values_list("pk", "nome", "preco_venda", "uso"):
        produtos.append({
            "id": f"r:{pk}", "nome": nome, "preco": preco, "ordem": 2,
            "grupo": "Itens de manutenção" if uso == PecasReposicao.Uso.MANUTENCAO else "Peças de reposição",
        })
    for produto in produtos:
        produto["chave"] = _normalizar(produto["nome"])
    return produtos


#: No contrato de equipamento, a peça de reposição só ganha do brinquedo
#: com o nome praticamente igual; abaixo disso, ela pesa assim.
PESO_DA_PECA_NO_EQUIPAMENTO = 0.8
_GRUPOS_DE_PECA = ("Peças de reposição", "Itens de manutenção")


def casar_item(descricao: str, catalogo: list[dict], *, quantos: int = 4,
               preferir_brinquedos: bool = False) -> dict:
    """O melhor produto para a linha, a confiança, e os candidatos.

    `preferir_brinquedos`: a linha está numa tabela de "Equipamento" /
    "Brinquedo", ou o documento é um contrato de equipamento de
    entretenimento. Aí "Boliche kids" é o brinquedo (Strike Kids Boliche),
    e não a peça "Bola de Boliche Kids": a peça só ganha com o nome
    praticamente igual ao do catálogo.
    """
    texto = (descricao or "").strip()
    if not texto or not catalogo:
        return {"escolhido": None, "confianca": "baixa", "pontos": 0.0,
                "motivo": "catálogo vazio" if texto else "", "candidatos": []}

    chave = _normalizar(texto)
    exatos = [p for p in catalogo if p["chave"] == chave]
    codigos = [
        p for p in catalogo
        if p.get("codigo") and re.search(r"(?<![\w-])" + re.escape(p["codigo"].lower()) + r"(?![\w-])",
                                         texto.lower())
    ]
    pontuados = []
    for produto in catalogo:
        pontos, motivo = pontuar(texto, produto["nome"])
        if preferir_brinquedos and produto["grupo"] in _GRUPOS_DE_PECA and pontos < LIMITE_ALTO:
            pontos = round(pontos * PESO_DA_PECA_NO_EQUIPAMENTO, 3)
            motivo = "peça de reposição; o documento fala de equipamento"
        if pontos >= 0.3:
            pontuados.append((pontos, motivo, produto))
    pontuados.sort(key=lambda trio: (-trio[0], trio[2]["ordem"], trio[2]["nome"]))

    candidatos = []
    vistos = set()
    for pontos, motivo, produto in pontuados:
        if produto["id"] in vistos:
            continue
        vistos.add(produto["id"])
        candidatos.append(_candidato(produto, pontos, motivo))
        if len(candidatos) >= quantos:
            break

    def resultado(produto, confianca, pontos, motivo):
        if produto and all(c["id"] != produto["id"] for c in candidatos):
            candidatos.insert(0, _candidato(produto, pontos, motivo))
        return {"escolhido": produto["id"] if produto else None, "confianca": confianca,
                "pontos": pontos, "motivo": motivo, "candidatos": candidatos}

    if exatos:
        # O mesmo nome no catálogo do site e na produção é a regra (a
        # produção espelha o brinquedo). O catálogo do site vem primeiro,
        # como em `_gravar_itens`. Dois brinquedos com o mesmo nome, aí
        # sim, é dúvida de verdade.
        exatos.sort(key=lambda p: p["ordem"])
        mesmo_grupo = [p for p in exatos if p["ordem"] == exatos[0]["ordem"]]
        if len(mesmo_grupo) == 1:
            return resultado(exatos[0], "alta", 1.0, "nome igual ao do catálogo")
        return resultado(exatos[0], "media", 0.9, "há mais de um produto com este nome")
    if len(codigos) == 1:
        return resultado(codigos[0], "alta", 0.97, f"código {codigos[0]['codigo']} na descrição")

    if not pontuados:
        return resultado(None, "baixa", 0.0, "nada parecido no catálogo")
    melhor_pontos, melhor_motivo, melhor = pontuados[0]
    segundo = next(
        (p for p, _, prod in pontuados[1:] if prod["chave"] != melhor["chave"]), 0.0,
    )
    if melhor_pontos >= LIMITE_ALTO and melhor_pontos - segundo >= FOLGA:
        return resultado(melhor, "alta", melhor_pontos, melhor_motivo)
    if melhor_pontos >= LIMITE_MEDIO:
        motivo = melhor_motivo if melhor_pontos - segundo >= FOLGA else "dois produtos muito parecidos"
        return resultado(melhor, "media", melhor_pontos, motivo)
    return resultado(None, "baixa", melhor_pontos, "nenhum produto parecido o bastante")


def _candidato(produto, pontos, motivo):
    return {
        "id": produto["id"],
        "nome": produto["nome"],
        "grupo": produto["grupo"],
        "preco": moeda(produto["preco"]) if produto.get("preco") is not None else "",
        "pontos": pontos,
        "motivo": motivo,
    }


def opcao_do_produto(chave: str) -> dict | None:
    """O formato do campo de busca do orçamento, para um "b:12" / "p:3" / "r:5"."""
    from ..views_gestao import OrcamentosInnerView

    tipo, _, pk = (chave or "").partition(":")
    if not pk.isdigit():
        return None
    if tipo == "b":
        objeto = Brinquedos.objects.filter(pk=pk).first()
        return OrcamentosInnerView.opcao_brinquedo(objeto) if objeto else None
    if tipo == "p":
        objeto = ProdutoInterno.objects.filter(pk=pk, ativo=True).select_related("brinquedo").first()
        return OrcamentosInnerView.opcao_produto(objeto) if objeto else None
    if tipo == "r":
        objeto = PecasReposicao.objects.filter(pk=pk).prefetch_related("imagem_peca_reposicao").first()
        return OrcamentosInnerView.opcao_peca(objeto) if objeto else None
    return None


def produto_por_chave(chave: str):
    """O objeto do catálogo por trás de "b:12", ou None se não existe mais."""
    tipo, _, pk = (chave or "").partition(":")
    if not pk.isdigit():
        return None
    if tipo == "b":
        return Brinquedos.objects.filter(pk=pk).first()
    if tipo == "p":
        return ProdutoInterno.objects.filter(pk=pk, ativo=True).first()
    if tipo == "r":
        return PecasReposicao.objects.filter(pk=pk).first()
    return None


def nome_do_produto(objeto) -> str:
    return getattr(objeto, "nome_brinquedo", None) or getattr(objeto, "nome", "") or ""


def preco_do_produto(objeto):
    for campo in ("valor_brinquedo", "preco_venda"):
        valor = getattr(objeto, campo, None)
        if valor is not None:
            return valor
    return None


# ======================================================================
# O CLIENTE
# ======================================================================
_SUFIXOS_NO_NOME = {"ltda", "me", "eireli", "epp", "sa", "s a", "mei"}


def _nome_para_comparar(nome: str) -> str:
    """"Buffet Alegria Ltda" e "BUFFET ALEGRIA" são o mesmo nome para o cadastro."""
    partes = _normalizar(nome).split()
    while partes and partes[-1] in _SUFIXOS_NO_NOME:
        partes.pop()
    return " ".join(partes)


def _mesmo_nome(a: str, b: str) -> bool:
    a, b = _nome_para_comparar(a), _nome_para_comparar(b)
    if not a or not b:
        return False
    return a == b or (min(len(a), len(b)) >= 8 and SequenceMatcher(None, a, b).ratio() >= 0.92)


def casar_cliente(*, documento="", email="", telefone="", nome="", estabelecimento="", cidade="") -> dict:
    """O cliente do cadastro, na ordem do que menos erra.

    CPF/CNPJ é a pessoa; e-mail e telefone quase sempre são; nome é só um
    palpite (há três "Buffet Alegria" em São Paulo) e por isso nunca vira
    vínculo sem a pessoa confirmar. O nome conta o do cliente E o do
    estabelecimento, sem acento, sem "Ltda" e com um erro de digitação de
    folga; com dois cadastros de mesmo nome, a cidade do endereço desempata
    -- e sem ela a pessoa escolhe. Quando dois dados apontam para
    cadastros diferentes, isso vira alerta -- não escolha.
    """
    alertas = []
    por_documento = por_email = por_telefone = None
    candidatos: list[Cliente] = []

    chave = chave_documento(documento)
    if len(chave) in (11, 14):
        achados = list(Cliente.objects.filter(Q(documento_chave=chave) | Q(cnpj_estabelecimento=chave))[:5])
        if len(achados) == 1:
            por_documento = achados[0]
        candidatos += achados

    email = (email or "").strip().lower()
    if email:
        achados = list(Cliente.objects.filter(email__iexact=email)[:5])
        if len(achados) == 1:
            por_email = achados[0]
        candidatos += achados

    digitos = digitos_do_telefone(telefone)
    if len(digitos) in (10, 11):
        achados = list(Cliente.objects.filter(telefone_digitos__in=[digitos, "55" + digitos])[:5])
        if len(achados) == 1:
            por_telefone = achados[0]
        candidatos += achados

    por_nome = []
    for valor in (nome, estabelecimento):
        nome_normalizado = _nome_para_comparar(valor)
        if not nome_normalizado:
            continue
        from ..views_gestao import BuscaItensOrcamentoView

        # A palavra mais longa do nome, sem acento dos dois lados: "Condomínio"
        # no cadastro e "Condominio" no Word são o mesmo nome, e um
        # `icontains` simples não os juntaria.
        palavra = max(nome_normalizado.split(), key=len)
        padrao = BuscaItensOrcamentoView._padrao_sem_acento(palavra)
        for cliente in Cliente.objects.filter(
            Q(nome_cliente__iregex=padrao) | Q(nome_estabelecimento__iregex=padrao)
        ).prefetch_related("enderecos")[:60]:
            if any(_mesmo_nome(valor, cadastrado) for cadastrado in (cliente.nome_cliente, cliente.nome_estabelecimento)):
                if all(c.pk != cliente.pk for c in por_nome):
                    por_nome.append(cliente)
    cidade_normalizada = _normalizar(cidade)
    mesma_cidade = [
        c for c in por_nome
        if cidade_normalizada and c.endereco_principal and _normalizar(c.endereco_principal.cidade) == cidade_normalizada
    ]
    candidatos += por_nome

    escolhido, confianca, motivo = None, "baixa", ""
    if por_documento:
        escolhido, confianca, motivo = por_documento, "alta", "mesmo CPF/CNPJ do cadastro"
    elif por_email:
        escolhido, confianca, motivo = por_email, "alta", "mesmo e-mail do cadastro"
    elif por_telefone:
        escolhido, confianca, motivo = por_telefone, "alta", "mesmo telefone do cadastro"
    elif len(por_nome) == 1:
        escolhido, confianca = por_nome[0], "media"
        motivo = ("mesmo nome e mesma cidade; confirme se é o mesmo cliente" if mesma_cidade
                  else "mesmo nome; confirme se é a mesma pessoa")
    elif len(mesma_cidade) == 1:
        escolhido, confianca, motivo = mesma_cidade[0], "media", "mesmo nome e mesma cidade; confirme se é o mesmo cliente"
    elif len(por_nome) > 1:
        motivo = "há mais de um cliente com este nome; escolha o certo"

    if escolhido:
        for outro, dado in ((por_documento, "o CPF/CNPJ"), (por_email, "o e-mail"), (por_telefone, "o telefone")):
            if outro and outro.pk != escolhido.pk:
                alertas.append({
                    "tipo": "cliente_conflito",
                    "detalhe": (
                        f"{dado[0].upper() + dado[1:]} do Word aponta para “{outro.nome_cliente}”, e não "
                        f"para “{escolhido.nome_cliente}”. Confira qual é o cliente certo."
                    ),
                })
        if chave and escolhido.documento_chave and escolhido.documento_chave != chave and len(chave) in (11, 14):
            alertas.append({
                "tipo": "cliente_conflito",
                "detalhe": (
                    f"O cadastro de “{escolhido.nome_cliente}” tem outro CPF/CNPJ "
                    "que o do Word. Confira se é o mesmo cliente."
                ),
            })

    vistos, unicos = set(), []
    for cliente in ([escolhido] if escolhido else []) + candidatos:
        if cliente and cliente.pk not in vistos:
            vistos.add(cliente.pk)
            unicos.append(cliente)
    return {
        "cliente": escolhido,
        "confianca": confianca,
        "motivo": motivo,
        "candidatos": unicos[:5],
        "alertas": alertas,
    }


# ======================================================================
# BRINQUEDOS CITADOS NO TEXTO
# ======================================================================
#: "duas camas elásticas", "um Air Game Kids": a quantidade por extenso.
POR_EXTENSO = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6,
               "sete": 7, "oito": 8, "nove": 9, "dez": 10}
_QUANTIDADE_ANTES = re.compile(
    r"(?:(\d{1,3})\s*(?:\([^)]{0,12}\)\s*)?(?:x\s*|un\.?\s*|unidades?\s*|pcs?\.?\s*)?"
    r"|\b(" + "|".join(POR_EXTENSO) + r")\s+)(?:de\s+)?(?:[ao]s?\s+)?$"
)
_CADA = re.compile(r"\b(cada|unitario|unit\.?|/\s*un|por unidade|a unidade)\b")


def _palavras_com_lugar(texto: str) -> list[tuple[str, int, int]]:
    """As palavras de `palavras()`, com onde cada uma está no texto."""
    base = sem_acento(texto or "")
    saida = []
    for achado in re.finditer(r"\d+(?:[.,]\d+)?|[a-z]+", base):
        normalizada = palavras(achado.group(0))
        if normalizada:
            saida.append((normalizada[0], achado.start(), achado.end()))
    return saida


def _mesma_palavra(a: str, b: str) -> bool:
    if a == b:
        return True
    if a[0].isdigit() or b[0].isdigit() or len(a) < 4 or len(b) < 4:
        return False
    return SequenceMatcher(None, a, b).ratio() >= 0.84


def brinquedos_citados(linhas: list[dict], catalogo: list[dict], *, fora=frozenset()) -> list[dict]:
    """Os produtos do catálogo citados no texto corrido, como linhas de item.

    "Gostaria de alugar duas camas elásticas de 3 metros, um Air Game Kids
    e o Strike Kids" -> três itens, com a quantidade quando escrita (em
    número ou por extenso) e o valor quando há um na mesma frase. O nome
    tem de aparecer inteiro e na ordem (no plural, sem acento, com uma
    palavra pequena no meio); o número do produto ("3 m", "Modelo 5"),
    quando o texto o traz, tem de ser o mesmo. Peça de reposição não entra
    aqui: "mola" e "lona" aparecem em todo texto.

    Volta no formato dos itens da leitura por regra, com contexto
    "mencao": a conferência casa cada um com o catálogo como faz com a
    linha de uma tabela.
    """
    produtos = []
    for produto in catalogo:
        if produto["id"][0] not in ("b", "p"):
            continue
        nome = palavras(produto["nome"])
        if not nome or not any(not p[0].isdigit() and len(p) >= 3 for p in nome):
            continue
        produtos.append((produto, nome))
    itens = []
    for linha in linhas:
        if linha["id"] in fora or linha.get("tabela"):
            continue
        texto = linha["texto"]
        lugares = _palavras_com_lugar(texto)
        if not lugares:
            continue
        achados = []
        for produto, nome in produtos:
            palavras_texto = [p for p, _, _ in lugares]
            for inicio in range(len(lugares)):
                if not _mesma_palavra(palavras_texto[inicio], nome[0]):
                    continue
                posicao, casadas, numeros_faltando = inicio, 1, 0
                fim = inicio
                for parte in nome[1:]:
                    proxima = None
                    for salto in (1, 2):
                        candidata = posicao + salto
                        if candidata < len(lugares) and _mesma_palavra(palavras_texto[candidata], parte):
                            proxima = candidata
                            break
                    if proxima is None:
                        if parte[0].isdigit() or parte in UNIDADES_DE_NUMERO:
                            numeros_faltando += 1
                            continue
                        break
                    posicao = fim = proxima
                    casadas += 1
                else:
                    # Um número DIFERENTE logo depois do nome derruba ("Modelo 5" não é "Modelo 3").
                    seguinte = palavras_texto[fim + 1] if fim + 1 < len(palavras_texto) else ""
                    numeros_do_nome = {p for p in nome if p[0].isdigit()}
                    if seguinte[:1].isdigit() and numeros_do_nome and seguinte not in numeros_do_nome:
                        continue
                    achados.append({
                        "produto": produto, "inicio": lugares[inicio][1], "fim": lugares[fim][2],
                        "completo": numeros_faltando == 0, "tamanho": casadas,
                    })
        # Sobrepostos: fica o nome inteiro (com o número) e o mais longo.
        achados.sort(key=lambda a: (not a["completo"], -a["tamanho"], a["inicio"]))
        escolhidos = []
        for achado in achados:
            if any(not (achado["fim"] <= e["inicio"] or achado["inicio"] >= e["fim"]) for e in escolhidos):
                # O mesmo trecho com outro produto parecido (3 m e 4 m sem
                # número no texto): vira candidato do mesmo item.
                for e in escolhidos:
                    if e["inicio"] == achado["inicio"] and not e["completo"] and not achado["completo"]:
                        e.setdefault("parecidos", []).append(achado["produto"])
                continue
            escolhidos.append(achado)
        escolhidos.sort(key=lambda a: a["inicio"])
        for posicao, achado in enumerate(escolhidos):
            antes = sem_acento(texto[:achado["inicio"]])[-30:]
            quantidade = None
            achado_qtd = _QUANTIDADE_ANTES.search(antes)
            if achado_qtd:
                quantidade = int(achado_qtd.group(1)) if achado_qtd.group(1) else POR_EXTENSO[achado_qtd.group(2)]
            limite = escolhidos[posicao + 1]["inicio"] if posicao + 1 < len(escolhidos) else len(texto)
            depois = texto[achado["fim"]:limite]
            valores = [v for v in valores_em_reais(depois) if v["valor"] is not None]
            unitario = total = None
            if valores:
                if _CADA.search(sem_acento(depois)) or (quantidade or 1) == 1:
                    unitario = valores[0]
                else:
                    total = valores[0]
            original = texto[achado["inicio"]:achado["fim"]]
            produto = achado["produto"]
            fonte = {"id": linha["id"], "texto": linha["texto"]}

            def campo(valor, texto_original, motivo=""):
                return {"valor": valor, "original": texto_original, "fonte": fonte, "motivo": motivo}

            itens.append({
                "linha_fonte": linha["id"],
                # Nome inteiro achado: a linha leva o nome do catálogo, e o
                # texto do documento fica ao lado ("No documento").
                "descricao": campo(produto["nome"] if achado["completo"] else original, original),
                "quantidade": campo(quantidade, str(quantidade)) if quantidade else None,
                "valor_unitario": campo(unitario["valor"], unitario["texto"]) if unitario else None,
                "total_linha": campo(total["valor"], total["texto"]) if total else None,
                "unidade": "",
                "recusas": [],
                "contexto": "mencao",
                "produto_citado": produto["id"] if achado["completo"] else "",
            })
    return itens
