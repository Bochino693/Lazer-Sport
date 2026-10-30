"""O Font Awesome do site, só com os ícones que o site usa.

POR QUE ESTE RECORTE EXISTE. O Font Awesome inteiro são quase 400 KB
(as três fontes mais o CSS) para desenhar algumas dezenas de ícones -- e
fonte de ícone segura o desenho da página no celular até chegar. Aqui
ficam só os ícones que aparecem nos modelos, nos scripts e no Python do
site público: as mesmas fontes oficiais, recortadas.

QUANDO RODAR. Sempre que um ícone novo entrar no site:

    pip install fonttools brotli
    python core/static/vendor/fontawesome-site/gerar.py

O teste `core/tests_assets.py` falha se um ícone usado pelo site não
estiver no recorte. O painel interno continua com o Font Awesome inteiro
(`vendor/fontawesome/`), que não é tocado.
"""

import hashlib
import re
from pathlib import Path

from fontTools import subset

AQUI = Path(__file__).resolve().parent
CORE = AQUI.parents[2]
ORIGEM = AQUI.parent / "fontawesome"

#: Onde o site público escreve nomes de ícone.
FONTES_DE_ICONES = (
    (CORE / "templates", ("*.html",)),
    (CORE / "static" / "site", ("*.js", "*.css")),
    (CORE, ("*.py",)),
    (CORE / "templatetags", ("*.py",)),
)

#: Classes do próprio Font Awesome que não são ícones.
NAO_SAO_ICONES = {
    "fa-solid", "fa-regular", "fa-brands", "fa-fw", "fa-spin", "fa-pulse", "fa-beat", "fa-fade",
    "fa-bounce", "fa-shake", "fa-flip", "fa-xs", "fa-sm", "fa-lg", "fa-xl", "fa-2xl", "fa-1x",
    "fa-2x", "fa-3x", "fa-4x", "fa-5x", "fa-6x", "fa-7x", "fa-8x", "fa-9x", "fa-10x", "fa-border",
    "fa-pull-left", "fa-pull-right", "fa-stack", "fa-stack-1x", "fa-stack-2x", "fa-inverse",
    "fa-rotate-90", "fa-rotate-180", "fa-rotate-270", "fa-flip-horizontal", "fa-flip-vertical",
    "fa-flip-both", "fa-ul", "fa-li", "fa-sr-only", "fa-classic", "fa-sharp",
}


def icones_usados():
    nomes = set()
    for pasta, padroes in FONTES_DE_ICONES:
        for padrao in padroes:
            arquivos = pasta.glob(padrao) if pasta == CORE else pasta.rglob(padrao)
            for arquivo in arquivos:
                if "vendor" in arquivo.parts:
                    continue
                nomes.update(re.findall(r"\bfa-[a-z0-9]+(?:-[a-z0-9]+)*", arquivo.read_text(encoding="utf-8", errors="ignore")))
    # os nomes dos arquivos de fonte (fa-solid-900...) também casam
    return {n for n in nomes - NAO_SAO_ICONES if not re.fullmatch(r"fa-(?:solid|regular|brands)-\d+", n)}


def recortar_css(css, usados):
    """Mantém as regras de base e só as regras de ícone que o site usa."""
    saida = []
    codigos = set()
    for regra in re.findall(r"[^{}]+\{[^{}]*\}", css):
        seletores, corpo = regra.split("{", 1)
        conteudo = re.search(r'content:\s*"\\([0-9a-f]+)"', corpo)
        icones = re.findall(r"\.(fa-[a-z0-9-]+):(?:before|after)", seletores)
        if conteudo and icones and all(re.fullmatch(r"\.fa-[a-z0-9-]+:(?:before|after)", s.strip()) for s in seletores.split(",")):
            vivos = [s.strip() for s in seletores.split(",") if s.strip()[1:].split(":")[0] in usados]
            if vivos:
                saida.append(",".join(vivos) + "{" + corpo)
                codigos.add(int(conteudo.group(1), 16))
            continue
        saida.append(regra)
    return "".join(saida), codigos


def main():
    usados = icones_usados()
    css = (ORIGEM / "css" / "all.min.css").read_text(encoding="utf-8")
    # o cabeçalho de licença fica
    licenca = re.match(r"/\*.*?\*/", css, re.S)
    corpo = css[licenca.end():] if licenca else css
    recortado, codigos = recortar_css(corpo, usados)
    faltando = sorted(n for n in usados if f".{n}:" not in recortado)

    (AQUI / "webfonts").mkdir(exist_ok=True)
    for nome in ("fa-solid-900", "fa-regular-400", "fa-brands-400"):
        opcoes = subset.Options()
        opcoes.flavor = "woff2"
        opcoes.layout_features = ["*"]
        opcoes.notdef_outline = True
        fonte = subset.load_font(str(ORIGEM / "webfonts" / f"{nome}.woff2"), opcoes)
        recorte = subset.Subsetter(opcoes)
        recorte.populate(unicodes=codigos)
        recorte.subset(fonte)
        subset.save_font(fonte, str(AQUI / "webfonts" / f"{nome}.woff2"), opcoes)

    # o CSS do recorte aponta para as fontes do recorte, e só para o woff2 --
    # COM A VERSÃO no endereço (o mesmo `?v=` do `{% estatico %}`, que é o
    # do preload no base.html). Sem ela, a fonte velha ficava no cache do
    # navegador (os arquivos de /vendor/ são servidos como imutáveis) e todo
    # ícone novo aparecia como um quadrado quebrado.
    recortado = recortado.replace("../webfonts/", "webfonts/")
    for nome in ("fa-solid-900", "fa-regular-400", "fa-brands-400"):
        versao = hashlib.sha256((AQUI / "webfonts" / f"{nome}.woff2").read_bytes()).hexdigest()[:10]
        recortado = recortado.replace(f"webfonts/{nome}.woff2)", f"webfonts/{nome}.woff2?v={versao})")
    (AQUI / "fontawesome-site.css").write_text(
        (licenca.group(0) if licenca else "")
        + "\n/* Recorte do site: gerado por gerar.py -- não edite à mão. */\n"
        + recortado,
        encoding="utf-8",
    )
    (AQUI / "icones.txt").write_text("\n".join(sorted(usados)) + "\n", encoding="utf-8")
    print(f"{len(usados)} ícones, {len(codigos)} desenhos; sem desenho no Font Awesome: {faltando or 'nenhum'}")


if __name__ == "__main__":
    main()
