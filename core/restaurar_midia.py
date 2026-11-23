"""AS FOTOS DE VOLTA: das cópias do repositório e da exportação do Cloudinary (seção 130).

O dono: "temos fotos por todo site, clientes e etc, vc deve pegar, são
imagens minhas" / "vc vai ter que pegar as imagens e depois salvar
novamente". Com o Cloudinary desativado, há dois caminhos para uma foto
voltar sem esperar a conta:

1. A CÓPIA DO REPOSITÓRIO (`restaurar_das_copias`, sozinho no Render a cada
   publicação, e `manage.py restaurar_midia`). Boa parte das fotos nasceu
   aqui e subiu depois. Só entra a cópia de que se tem CERTEZA:
     * EXATA PELO CONTEÚDO: o nome que as rotinas de publicação deram no
       Cloudinary carrega o SHA-1 do arquivo daqui
       ("cena-air-game-home-10bb33e058_ik4fg5"): o arquivo do repositório
       cujo SHA-1 começa assim É a foto -- byte a byte;
     * EXATA PELO NOME: core/static/site/reserva/ guarda as originais
       recuperadas com o nome que tinham no Cloudinary
       ("cabo-hdmi_ci5liw.png" é pecas_reposicao/cabo-hdmi_ci5liw);
     * A MESMA FOTO, NUMA VERSÃO MAIS NOVA (`exata=False`): o nome segue a
       regra de uma rotina de publicação com a chave EXATA de um arquivo
       daqui ("cena-<produto>-<assinatura antiga>" -> capas_catalogo/
       <produto>.webp; a vista do 3D "<pasta>-<vista>"; a capa
       "capa-<chave>-..."; o kit, a categoria e a Black Friday), e só no
       campo que aquela rotina preenche (a foto da categoria nunca vira foto
       de produto). Nada de "o nome contém": chave inteira ou nada;
     * O MESMO NOME NA PASTA media/ (`exata=False`): a mídia antiga que foi
       para o repositório, na mesma pasta e com o mesmo nome;
     * O RECORTE DA MESMA FOTO (`exata=False`): as peças de reposição
       recortadas por ferramentas/categorias/recortar.py, que registra de
       QUAL foto do Cloudinary cada recorte saiu (PECAS) -- só nas fotos de
       peça.
   A cópia que não é exata é servida com cache de um dia (não de um ano) e o
   espelho a troca pela original quando o Cloudinary voltar.

2. A EXPORTAÇÃO DO CLOUDINARY (`importar_arquivo`, a tela "Restaurar fotos"
   do painel e `manage.py restaurar_midia --zip`): o ZIP da Media Library
   (ou fotos soltas). Cada arquivo casa pelo public id -- a pasta e o nome
   sem a extensão -- com os campos que o usam; o ZIP é lido entrada por
   entrada, sem abrir tudo na memória.
"""

from __future__ import annotations

import ast
import hashlib
import logging
import posixpath
import re
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings

from .arquivos_no_banco import PREFIXO, e_do_banco, tipo_do_conteudo
from . import espelho_midia

log = logging.getLogger("lazer.midia")

BASE = Path(__file__).resolve().parent.parent
ESTATICO = Path(__file__).resolve().parent / "static"
SITE = ESTATICO / "site"
RESERVA = SITE / "reserva"
MEDIA = BASE / "media"
REPOSICAO = BASE / "ferramentas" / "categorias" / "reposicao"
RECORTAR = BASE / "ferramentas" / "categorias" / "recortar.py"

EXTENSOES_DE_FOTO = (".webp", ".png", ".jpg", ".jpeg", ".gif")
#: As extensões que o nome do Cloudinary pode trazer (o "raw" guarda a extensão).
EXTENSOES_CONHECIDAS = EXTENSOES_DE_FOTO + (".avif", ".glb", ".pdf", ".xml", ".docx", ".txt", ".bin", ".svg")

PRODUTO = frozenset({"core.ImagemBrinquedo.imagem", "core.Brinquedos.imagem_brinquedo"})
CATEGORIA = frozenset({"core.CategoriasBrinquedos.imagem_categoria"})
PECA = frozenset({"core.ImagemPeca.imagem", "core.ImagemPeca.imagem_original"})

_SUFIXO = re.compile(r"_[a-z0-9]{6}$")
_HEX = r"[0-9a-f]{8,12}"
_TOKEN = re.compile(r"(?:^|[-_])([0-9a-f]{8,12})(?=$|[-_])")

#: O ZIP da exportação: até 500 MB, e cada arquivo até o limite do espelho.
LIMITE_DO_ZIP = 500 * 1024 * 1024


# ======================================================================
# NOMES
# ======================================================================
def sem_extensao(nome: str) -> str:
    raiz, extensao = posixpath.splitext(str(nome or ""))
    return raiz if extensao.lower() in EXTENSOES_CONHECIDAS else str(nome or "")


def sem_sufixo(base: str) -> str:
    """Tira o sufixo que o Cloudinary sorteia ("_ik4fg5")."""
    return _SUFIXO.sub("", base)


def partes(nome):
    """(pasta, base sem extensão, base sem o sufixo do Cloudinary), em minúsculas."""
    nome = str(nome or "")
    if e_do_banco(nome):
        nome = nome[len(PREFIXO):]
    pasta, base = posixpath.split(sem_extensao(nome))
    base = base.lower()
    return pasta.lower(), base, sem_sufixo(base)


# ======================================================================
# O ÍNDICE DAS CÓPIAS DO REPOSITÓRIO
# ======================================================================
@dataclass
class Achado:
    caminho: Path
    regra: str
    exata: bool


@dataclass
class Indice:
    por_prefixo: dict = field(default_factory=dict)  # sha1[:8] -> [(sha1, caminho)]
    reserva: dict = field(default_factory=dict)  # base com sufixo -> caminho
    media: dict = field(default_factory=dict)  # (pasta, base) -> caminho
    regras: list = field(default_factory=list)  # (regex, caminho, campos, rótulo)
    recortes: dict = field(default_factory=dict)  # public id (minúsculo) -> caminho

    def achar(self, nome, rotulos) -> Achado | None:
        rotulos = set(rotulos)
        pasta, base, curta = partes(nome)
        if base in self.reserva:
            return Achado(self.reserva[base], "original com o nome do Cloudinary (site/reserva)", True)
        for token in _TOKEN.findall(curta):
            for sha, caminho in self.por_prefixo.get(token[:8], ()):
                if sha.startswith(token):
                    return Achado(caminho, "idêntica: a assinatura do nome é a do arquivo", True)
        if (pasta, curta) in self.media:
            return Achado(self.media[(pasta, curta)], "a mídia antiga do repositório, mesma pasta e nome", False)
        casadas = {}
        for regex, caminho, campos, rotulo in self.regras:
            if rotulos <= campos and regex.fullmatch(curta):
                casadas.setdefault(caminho, rotulo)
        if len(casadas) == 1:
            caminho, rotulo = next(iter(casadas.items()))
            return Achado(caminho, rotulo, False)
        if rotulos <= PECA:
            chave = f"{pasta}/{base}" if pasta else base
            recorte = self.recortes.get(chave) or self.recortes.get(re.sub(r"-sem-fundo(_[a-z0-9]{6})?$", "", chave))
            if recorte is not None:
                return Achado(recorte, "o recorte da mesma foto (ferramentas/categorias/reposicao)", False)
        return None


def _fotos(pasta: Path, recursivo=False):
    if not pasta.is_dir():
        return []
    iterador = pasta.rglob("*") if recursivo else pasta.iterdir()
    return sorted(p for p in iterador if p.is_file() and p.suffix.lower() in EXTENSOES_DE_FOTO)


def _recortes_das_pecas():
    """{public id da foto de origem: recorte} do PECAS de recortar.py (lido como texto, sem rodar)."""
    if not RECORTAR.is_file() or not REPOSICAO.is_dir():
        return {}
    try:
        arvore = ast.parse(RECORTAR.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return {}
    pecas = {}
    for no in arvore.body:
        alvo = getattr(no, "target", None) or (no.targets[0] if getattr(no, "targets", None) else None)
        if isinstance(alvo, ast.Name) and alvo.id == "PECAS":
            try:
                pecas = ast.literal_eval(no.value)
            except ValueError:
                pecas = {}
    saida = {}
    # a chave mais curta primeiro: "boneco-pebolim" (a foto inteira) antes do "-vermelho" (um boneco só)
    for chave in sorted(pecas, key=len):
        try:
            origem = str(pecas[chave][2]).lower()
        except (IndexError, TypeError):
            continue
        caminho = REPOSICAO / f"{chave}.webp"
        if caminho.is_file():
            saida.setdefault(origem, caminho)
    return saida


def montar_indice() -> Indice:
    indice = Indice()
    vistos = set()
    for caminho in _fotos(SITE, recursivo=True) + _fotos(MEDIA, recursivo=True) + _fotos(REPOSICAO):
        sha = hashlib.sha1(caminho.read_bytes()).hexdigest()
        if sha in vistos:
            continue
        vistos.add(sha)
        indice.por_prefixo.setdefault(sha[:8], []).append((sha, caminho))
    for caminho in _fotos(RESERVA, recursivo=True):
        indice.reserva[caminho.stem.lower()] = caminho
    for caminho in _fotos(MEDIA, recursivo=True):
        pasta = caminho.parent.relative_to(MEDIA).as_posix().lower()
        indice.media.setdefault((pasta, caminho.stem.lower()), caminho)

    def regra(padrao, caminho, campos, rotulo):
        indice.regras.append((re.compile(padrao), caminho, campos, rotulo))

    for caminho in _fotos(SITE / "capas_catalogo"):
        chave = re.escape(caminho.stem.lower())
        regra(rf"cena-{chave}-{_HEX}", caminho, PRODUTO, "a capa em cena do mesmo produto (versão do repositório)")
        regra(rf"estudio-catalogo-{chave}-{_HEX}", caminho, PRODUTO, "a foto de estúdio do mesmo produto")
    modelos = SITE / "arena" / "modelos"
    if modelos.is_dir():
        for pasta in sorted(p for p in modelos.iterdir() if p.is_dir()):
            chave = re.escape(pasta.name.lower())
            for caminho in _fotos(pasta):
                vista = re.escape(caminho.stem.lower())
                regra(rf"{chave}-{vista}(-v\d+)?", caminho, PRODUTO, "a mesma vista do 3D do produto")
                regra(rf"estudio-{chave}-{vista}-{_HEX}", caminho, PRODUTO, "a foto de estúdio da mesma vista")
                if caminho.stem == "capa":
                    regra(rf"capa-{chave}-{_HEX}", caminho, PRODUTO, "a capa quadrada do mesmo adesivo")
    for caminho in _fotos(SITE / "black_friday"):
        regra(rf"black-friday-2026-{re.escape(caminho.stem.lower())}-{_HEX}", caminho, PRODUTO,
              "a foto da Black Friday do mesmo produto")
    for caminho in _fotos(SITE / "kits"):
        regra(rf"{re.escape(caminho.stem.lower())}-{_HEX}", caminho, PRODUTO, "a capa do mesmo kit")
    for caminho in _fotos(SITE / "categorias"):
        chave = re.escape(caminho.stem.lower())
        regra(rf"(categoria-produto-)?{chave}-{_HEX}", caminho, CATEGORIA, "a foto da mesma categoria")
    indice.recortes = _recortes_das_pecas()
    return indice


# ======================================================================
# O RESULTADO
# ======================================================================
@dataclass
class Resultado:
    restaurados: list = field(default_factory=list)  # {nome, para, regra, exata, onde}
    faltando: list = field(default_factory=list)  # {nome, onde}
    nao_referenciados: list = field(default_factory=list)  # nomes do ZIP que nada usa
    ja: list = field(default_factory=list)  # já estavam no banco
    recusados: list = field(default_factory=list)  # {nome, motivo}

    def resumo(self):
        return {
            "restaurados": len(self.restaurados), "faltando": len(self.faltando),
            "nao_referenciados": len(self.nao_referenciados), "ja": len(self.ja), "recusados": len(self.recusados),
        }


def _onde(grupo):
    """[(modelo, campo, pk), ...] -- quem usa o arquivo."""
    return [(r.modelo._meta.label, r.campo, pk) for r in grupo for pk in r.pks]


def restaurar_das_copias(*, simular=False, avisar=None) -> Resultado:
    """As fotos que têm cópia certa no repositório voltam para o banco. Pode rodar de novo."""
    avisar = avisar or (lambda texto: None)
    resultado = Resultado()
    pendentes = espelho_midia.referencias(somente_publicos=True)
    if not pendentes:
        return resultado
    indice = montar_indice()
    for nome, grupo in pendentes.items():
        achado = indice.achar(nome, {r.rotulo for r in grupo})
        if achado is None:
            resultado.faltando.append({"nome": nome, "onde": _onde(grupo)})
            continue
        item = {"nome": nome, "de": str(achado.caminho.relative_to(BASE)), "regra": achado.regra,
                "exata": achado.exata, "onde": _onde(grupo)}
        if not simular:
            item["para"], _houve = espelho_midia.gravar_conteudo(
                nome, grupo, achado.caminho.read_bytes(), origem="copia_local", exata=achado.exata,
            )
        resultado.restaurados.append(item)
        avisar(f"Restaurada: {nome} <- {item['de']} ({achado.regra})")
    for item in resultado.faltando:
        avisar(f"Ainda falta: {item['nome']} ({', '.join(f'{m}.{c} #{pk}' for m, c, pk in item['onde'][:3])})")
    if resultado.restaurados and not simular:
        espelho_midia.limpar_caches()
    log.info("midia: restauração das cópias %s", resultado.resumo())
    return resultado


def relatorio():
    """Tudo o que ainda não está no banco: [{modelo, pk, campo, nome}], na ordem do modelo."""
    linhas = []
    for nome, grupo in espelho_midia.referencias().items():
        for modelo, campo, pk in _onde(grupo):
            linhas.append({"modelo": modelo, "pk": pk, "campo": campo, "nome": nome})
    return sorted(linhas, key=lambda l: (l["modelo"], l["campo"], str(l["pk"])))


# ======================================================================
# A EXPORTAÇÃO DO CLOUDINARY (ZIP ou arquivos soltos)
# ======================================================================
class Mapa:
    """Os nomes que os campos usam, para casar o que chega pelo public id."""

    def __init__(self):
        self.pendentes = espelho_midia.referencias()
        self.do_banco = espelho_midia.referencias(do_banco=True)
        self.por_id = {}
        self.por_base = {}
        for nome in list(self.pendentes) + list(self.do_banco):
            antigo = nome[len(PREFIXO):] if e_do_banco(nome) else nome
            chave = sem_extensao(antigo).lower()
            self.por_id.setdefault(chave, set()).add(nome)
            self.por_base.setdefault(chave.rsplit("/", 1)[-1], set()).add(nome)

    def casar(self, caminho):
        """Os nomes (dos campos) que o arquivo `caminho` do ZIP restaura."""
        caminho = str(caminho or "").replace("\\", "/").lstrip("./")
        chave = sem_extensao(caminho).lower()
        pedacos = [p for p in chave.split("/") if p]
        for inicio in range(len(pedacos)):
            achados = self.por_id.get("/".join(pedacos[inicio:]))
            if achados:
                return sorted(achados)
        if pedacos:
            achados = self.por_base.get(pedacos[-1])
            if achados and len({sem_extensao(n[len(PREFIXO):] if e_do_banco(n) else n).lower() for n in achados}) == 1:
                return sorted(achados)
        return []

    def esquecer(self, nome):
        self.pendentes.pop(nome, None)


def _aceita(dados, grupo):
    """O conteúdo serve para o campo? A foto tem de ser foto; o .glb, um .glb."""
    tipo = tipo_do_conteudo(dados)
    storage = grupo[0].storage
    if not getattr(storage, "guarda_publico", False):
        return True, tipo  # documento privado: o que o dono exportou da própria conta
    if getattr(storage, "legado", "image") == "raw":
        return tipo == "model/gltf-binary", tipo
    return tipo.startswith("image/") and tipo != "image/svg+xml", tipo


def importar_um(caminho, dados, mapa: Mapa, resultado: Resultado):
    """Um arquivo da exportação: guarda e reponta tudo o que usava aquele public id."""
    from .models import ArquivoNoBanco

    nomes = mapa.casar(caminho)
    if not nomes:
        resultado.nao_referenciados.append(caminho)
        return
    for nome in nomes:
        if e_do_banco(nome):
            grupo = mapa.do_banco[nome]
            exata = ArquivoNoBanco.objects.filter(nome=nome).values_list("exata", flat=True).first()
            if exata is not False:
                resultado.ja.append(nome)
                continue
            antigo = nome[len(PREFIXO):]
        else:
            grupo = mapa.pendentes.get(nome)
            if grupo is None:  # já restaurado por outro arquivo deste mesmo envio
                resultado.ja.append(nome)
                continue
            antigo = nome
        serve, tipo = _aceita(dados, grupo)
        if not serve:
            resultado.recusados.append({"nome": caminho, "motivo": f"o arquivo ({tipo}) não serve para {grupo[0].rotulo}"})
            continue
        para, houve = espelho_midia.gravar_conteudo(antigo, grupo, dados, origem="zip", exata=True)
        if houve == "ja":
            resultado.ja.append(nome)
        else:
            resultado.restaurados.append({"nome": antigo, "para": para, "de": caminho, "regra": "exportação do Cloudinary",
                                          "exata": True, "onde": _onde(grupo)})
        mapa.esquecer(nome)


def _entradas(arquivo_zip):
    for info in arquivo_zip.infolist():
        nome = info.filename.replace("\\", "/")
        base = nome.rsplit("/", 1)[-1]
        if info.is_dir() or not base or base.startswith(".") or "__MACOSX/" in nome:
            continue
        yield info


def importar_zip(caminho, *, inicio=0, prazo=None, mapa=None, resultado=None, limite=None):
    """Lê o ZIP a partir da entrada `inicio`; com `prazo` (segundos), para no meio e diz onde parou.

    Devolve (resultado, proximo, total): `proximo` é None quando acabou.
    """
    limite = limite or espelho_midia._limite()
    resultado = resultado or Resultado()
    mapa = mapa or Mapa()
    comeco = time.monotonic()
    with zipfile.ZipFile(caminho) as arquivo_zip:
        entradas = list(_entradas(arquivo_zip))
        total = len(entradas)
        for ordem in range(inicio, total):
            if prazo and ordem > inicio and time.monotonic() - comeco > prazo:
                if resultado.restaurados:
                    espelho_midia.limpar_caches()
                return resultado, ordem, total
            info = entradas[ordem]
            if info.file_size > limite:
                resultado.recusados.append({"nome": info.filename, "motivo": "grande demais"})
                continue
            with arquivo_zip.open(info) as entrada:
                dados = entrada.read(limite + 1)
            if len(dados) > limite:
                resultado.recusados.append({"nome": info.filename, "motivo": "grande demais"})
                continue
            importar_um(info.filename, dados, mapa, resultado)
    if resultado.restaurados:
        espelho_midia.limpar_caches()
    return resultado, None, total


def e_zip(caminho) -> bool:
    try:
        return zipfile.is_zipfile(caminho)
    except OSError:
        return False
