"""Cada item da nota ligado a um Material -- e os repetidos somados.

A ORDEM DA LIGAÇÃO, da mais segura para a mais fraca:

  1. PELO CÓDIGO DO FORNECEDOR. A nota anterior DESTE fornecedor (mesmo
     CNPJ) que trouxe o mesmo código, já conferida e lançada, diz qual é o
     material. É a memória do sistema: a segunda nota do mesmo fornecedor
     já chega ligada, sem ninguém escolher de novo.
  2. PELO NOME SEM ACENTO. "Parafuso chip 3,5 x 25" e "PARAF CHIP 3.5X25"
     não são o mesmo nome; "Fita crepe 48x50" e "FITA CREPE 48X50" são:
     caixa, acento, pontuação e o separador decimal não contam. Vale o
     nome do material e a descrição de nota anterior já ligada.
  3. PELA SEMELHANÇA, e só entre nomes COM OS MESMOS NÚMEROS: "3.5 X 25" e
     "3.5 X 40" são parafusos diferentes, por mais parecido que o resto
     seja. A tela mostra "parecido (87%)" para a pessoa confirmar.
  4. Nada disso: MATERIAL NOVO, que será criado no lançamento.

A SOMA DOS REPETIDOS. O mesmo produto aparece em várias linhas da nota
(pedidos juntados num faturamento só). Linhas com o mesmo código,
descrição e unidade -- ou ligadas com certeza (código ou nome) ao mesmo
material, na mesma unidade -- viram UMA linha na conferência, com as
quantidades e os valores somados. No lançamento soma-se de novo, pelo que a
pessoa deixou: duas linhas trocadas para o mesmo material e o mesmo local
viram uma entrada só no estoque.
"""

from __future__ import annotations

import difflib
import re
from collections import Counter, OrderedDict
from decimal import ROUND_HALF_UP, Decimal

from ..busca_local import sem_acento

#: Semelhança mínima (0 a 1) para propor um material "parecido".
SEMELHANCA_MINIMA = 0.8

#: Local de guarda quando o estoque ainda não tem nenhum.
LOCAL_PADRAO = "Almoxarifado"

#: A unidade da nota (uCom) -> a unidade do estoque, e quantas cabem em uma.
#: Cento, dúzia e milheiro têm tamanho certo: 5 CE de parafuso são 500
#: parafusos, e é assim que o estoque conta. Pacote, caixa e cartela não
#: têm tamanho escrito na nota -- entram como estão, e a tela avisa.
UNIDADES_DA_NOTA = {
    "un": ("UN", "UND", "UNID", "UNIDADE", "UNIDADES", "UNI", "UNT", "U", "UNIT"),
    "pc": ("PC", "PÇ", "PCA", "PÇA", "PECA", "PEÇA", "PCS", "PÇS", "PECAS", "PEÇAS"),
    "m": ("M", "MT", "MTS", "MTR", "METRO", "METROS", "ML"),
    "m2": ("M2", "M²", "MT2", "MQ", "M2."),
    "kg": ("KG", "KGS", "QUILO", "QUILOS", "KILO"),
    "l": ("L", "LT", "LTS", "LITRO", "LITROS"),
    "cx": ("CX", "CXA", "CAIXA", "CAIXAS"),
    "rl": ("RL", "RLS", "ROLO", "ROLOS", "BOB", "BOBINA"),
    "par": ("PAR", "PR", "PARES"),
}
MULTIPLOS = {
    "CE": (100, "cento"), "CT": (100, "cento"), "CENTO": (100, "cento"),
    "DZ": (12, "dúzia"), "DUZIA": (12, "dúzia"), "DÚZIA": (12, "dúzia"),
    "MIL": (1000, "milheiro"), "MI": (1000, "milheiro"), "MILHEIRO": (1000, "milheiro"),
}
PACOTES = {
    "PT": "pacote", "PCT": "pacote", "PACOTE": "pacote", "CA": "cartela", "CART": "cartela",
    "JG": "jogo", "JOGO": "jogo", "KIT": "kit", "FD": "fardo", "SC": "saco", "SACO": "saco",
    "GL": "galão", "GALAO": "galão", "LATA": "lata", "LT.": "lata", "TB": "tubo", "BD": "balde",
    "FR": "frasco", "BL": "bloco", "CJ": "conjunto", "CONJ": "conjunto",
}
_POR_SIGLA = {sigla: unidade for unidade, siglas in UNIDADES_DA_NOTA.items() for sigla in siglas}


def chave_de_nome(texto: str) -> str:
    """O nome reduzido ao que importa: letras e números, sem acento.

    "PARAF.NEW FIX CHIP 3,5 X 25" -> "paraf new fix chip 3.5 x 25".
    """
    limpo = sem_acento(texto or "")
    pedacos = re.findall(r"[a-z]+|\d+(?:[.,]\d+)?", limpo)
    return " ".join(pedaco.replace(",", ".") for pedaco in pedacos)


def numeros_do_nome(chave: str) -> tuple:
    return tuple(sorted(re.findall(r"\d+(?:\.\d+)?", chave)))


def semelhanca(a: str, b: str) -> float:
    """0 a 1 -- e 0 quando os números (medidas) não são os mesmos."""
    if not a or not b or numeros_do_nome(a) != numeros_do_nome(b):
        return 0.0
    por_letra = difflib.SequenceMatcher(None, a, b).ratio()
    palavras_a, palavras_b = set(a.split()), set(b.split())
    por_palavra = len(palavras_a & palavras_b) / len(palavras_a | palavras_b)
    return max(por_letra, por_palavra)


def unidade_do_estoque(sigla: str, quantidade: Decimal) -> tuple[str, int, str]:
    """(unidade do Material, quantidade inteira, aviso) para a linha da nota."""
    from ..models import Material

    original = (sigla or "").strip().upper()
    if original in MULTIPLOS:
        fator, nome = MULTIPLOS[original]
        total = quantidade * fator
        aviso = f"A nota conta em {nome} ({original}): entram {_inteiro(total)} unidades."
        return Material.Unidade.UNIDADE, _inteiro(total), aviso + _aviso_de_fracao(total)
    unidade = _POR_SIGLA.get(original)
    aviso = ""
    if unidade is None:
        unidade = Material.Unidade.UNIDADE
        if original in PACOTES:
            aviso = (
                f"A nota conta em {PACOTES[original]} ({original}). Se o estoque conta por "
                "peça, multiplique pela quantidade de cada um."
            )
        elif original:
            aviso = f"A unidade da nota ({original}) não existe no estoque: confira."
    return unidade, _inteiro(quantidade), aviso + _aviso_de_fracao(quantidade)


def _inteiro(quantidade: Decimal) -> int:
    return max(int(quantidade.to_integral_value(rounding=ROUND_HALF_UP)), 0)


def _aviso_de_fracao(quantidade: Decimal) -> str:
    if quantidade == quantidade.to_integral_value():
        return ""
    texto = format(quantidade.normalize(), "f").replace(".", ",")
    return f" A nota traz {texto}: o estoque conta inteiro, confira."


class Catalogo:
    """Os materiais e a memória das notas anteriores, carregados uma vez."""

    def __init__(self, fornecedor_cnpj: str = "", ignorar_nota=None):
        from ..models import ItemNotaEntrada, Material, NotaEntrada

        self.materiais = list(
            Material.objects.filter(ativo=True).prefetch_related("estoque").order_by("nome_material", "pk")
        )
        self.por_id = {material.pk: material for material in self.materiais}
        self.por_nome = {}
        # A semelhança só compara nomes com as MESMAS medidas: agrupados por
        # elas, cada item da nota olha só para os candidatos do seu grupo, e
        # uma nota de 500 linhas contra 2.000 materiais não vira 1 milhão de
        # comparações.
        self.por_medidas = {}
        for material in self.materiais:
            chave = chave_de_nome(material.nome_material)
            self.por_nome.setdefault(chave, material)
            self.por_medidas.setdefault(numeros_do_nome(chave), []).append((chave, material))

        anteriores = (
            ItemNotaEntrada.objects
            .filter(nota__situacao=NotaEntrada.Situacao.LANCADA, material__isnull=False, material__ativo=True)
            .order_by("-nota__lancada_em", "-pk")
            .values_list("nota__fornecedor_cnpj", "codigo", "descricao", "material_id")
        )
        if ignorar_nota is not None:
            anteriores = anteriores.exclude(nota=ignorar_nota)
        self.por_codigo = {}
        self.por_descricao = {}
        for cnpj, codigo, descricao, material_id in anteriores:
            material = self.por_id.get(material_id)
            if material is None:
                continue
            if fornecedor_cnpj and cnpj == fornecedor_cnpj and codigo:
                self.por_codigo.setdefault(codigo.strip().upper(), material)
            self.por_descricao.setdefault(chave_de_nome(descricao), material)

    def ligar(self, codigo: str, descricao: str):
        """(material ou None, como ligou, semelhança em %)."""
        from ..models import ItemNotaEntrada

        codigo = (codigo or "").strip().upper()
        if codigo and codigo in self.por_codigo:
            return self.por_codigo[codigo], ItemNotaEntrada.Ligacao.CODIGO, 100
        chave = chave_de_nome(descricao)
        if chave and chave in self.por_nome:
            return self.por_nome[chave], ItemNotaEntrada.Ligacao.NOME, 100
        if chave and chave in self.por_descricao:
            return self.por_descricao[chave], ItemNotaEntrada.Ligacao.NOME, 100
        melhor, nota_melhor = None, 0.0
        for chave_material, material in self.por_medidas.get(numeros_do_nome(chave), ()):
            valor = semelhanca(chave, chave_material)
            if valor > nota_melhor:
                melhor, nota_melhor = material, valor
        if melhor is not None and nota_melhor >= SEMELHANCA_MINIMA:
            return melhor, ItemNotaEntrada.Ligacao.PARECIDO, int(round(nota_melhor * 100))
        return None, ItemNotaEntrada.Ligacao.NOVO, 0


def locais_de_guarda() -> tuple[list[str], str]:
    """Os locais que o estoque já usa (para sugerir) e o mais comum."""
    from ..models import EstoqueMaterial

    contagem = Counter()
    nomes = {}
    for local in EstoqueMaterial.objects.values_list("descricao_local", flat=True):
        chave = (local or "").strip().casefold()
        if chave:
            contagem[chave] += 1
            nomes.setdefault(chave, local.strip())
    ordenados = [nomes[chave] for chave, _ in contagem.most_common()]
    return ordenados, (ordenados[0] if ordenados else LOCAL_PADRAO)


def local_do_material(material, padrao: str) -> str:
    """Onde o material já está guardado (o local com mais saldo) -- ou o padrão."""
    if material is None:
        return padrao
    locais = sorted(material.estoque.all(), key=lambda local: (-local.quantidade, local.pk))
    return locais[0].descricao_local if locais else padrao


def agrupar(itens_lidos, catalogo: Catalogo) -> list[dict]:
    """As linhas da conferência: ligadas, convertidas e com os repetidos somados."""
    from ..models import ItemNotaEntrada

    _, padrao = locais_de_guarda()
    grupos: "OrderedDict[tuple, dict]" = OrderedDict()
    for item in itens_lidos:
        material, ligacao, nota_semelhanca = catalogo.ligar(item.codigo, item.descricao)
        sigla = (item.unidade or "").strip().upper()
        certeza = ligacao in (ItemNotaEntrada.Ligacao.CODIGO, ItemNotaEntrada.Ligacao.NOME)
        if material is not None and certeza:
            chave = ("material", material.pk, sigla)
        else:
            chave = ("produto", (item.codigo or "").strip().upper(), chave_de_nome(item.descricao), sigla)
        grupo = grupos.get(chave)
        if grupo is None:
            grupos[chave] = {
                "linhas": [item.numero],
                "codigo": item.codigo,
                "descricao": item.descricao,
                "complemento": item.complemento,
                "ncm": item.ncm,
                "unidade_nota": sigla[:6],
                "quantidade_nota": item.quantidade,
                "valor_total": item.valor_total,
                "material": material,
                "ligacao": ligacao,
                "semelhanca": nota_semelhanca,
            }
            continue
        grupo["linhas"].append(item.numero)
        grupo["quantidade_nota"] += item.quantidade
        grupo["valor_total"] += item.valor_total
        if item.complemento and item.complemento not in grupo["complemento"]:
            grupo["complemento"] = f"{grupo['complemento']} · {item.complemento}".strip(" ·")[:250]

    linhas = []
    for ordem, grupo in enumerate(grupos.values(), start=1):
        unidade, quantidade, aviso = unidade_do_estoque(grupo["unidade_nota"], grupo["quantidade_nota"])
        material = grupo["material"]
        if material is not None:
            if material.unidade != unidade:
                # O material já existe: vale a unidade dele, e a quantidade
                # da nota fica para a pessoa conferir.
                aviso = (aviso + " " if aviso else "") + (
                    f"O material é contado em {material.get_unidade_display().lower()} e a nota em "
                    f"{grupo['unidade_nota'] or 'outra unidade'}: confira a quantidade."
                )
            unidade = material.unidade
        quantidade_nota = grupo["quantidade_nota"]
        valor_unitario = (grupo["valor_total"] / quantidade_nota) if quantidade_nota else Decimal("0")
        linhas.append({
            "ordem": ordem,
            "linhas_nota": ", ".join(str(n) for n in grupo["linhas"]),
            "codigo": (grupo["codigo"] or "")[:60],
            "descricao": (grupo["descricao"] or "")[:250] or "(sem descrição)",
            "complemento": grupo["complemento"][:250],
            "ncm": (grupo["ncm"] or "")[:8],
            "unidade_nota": grupo["unidade_nota"],
            "quantidade_nota": quantidade_nota.quantize(Decimal("0.0001")),
            "valor_unitario_nota": valor_unitario.quantize(Decimal("0.0001")),
            "valor_total": grupo["valor_total"].quantize(Decimal("0.01")),
            "material": material,
            "ligacao": grupo["ligacao"],
            "semelhanca": grupo["semelhanca"],
            "nome_material": nome_para_material(grupo["descricao"]),
            "unidade": unidade,
            "quantidade": quantidade,
            "local": local_do_material(material, padrao),
            "aviso": aviso.strip()[:200],
        })
    return linhas


def nome_para_material(descricao: str) -> str:
    """A descrição da nota como nome de material (até 90 caracteres)."""
    nome = re.sub(r"\s+", " ", descricao or "").strip()
    if len(nome) <= 90:
        return nome
    corte = nome[:90].rsplit(" ", 1)[0]
    return corte if len(corte) >= 40 else nome[:90]
