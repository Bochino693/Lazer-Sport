"""As folhas de contato do antes e do depois das fotos do estúdio (só Pillow; qualquer Python).

    python3 ferramentas/fotos3d/folhas.py --antes HEAD~1 --saida /tmp/fotos3d/folhas

Para cada máquina de produtos.py: uma folha com as fotos do site como estão no disco (o
depois) e, com --antes <ref do git>, as mesmas fotos naquele commit, linha a linha (o antes
em cima, o depois embaixo). Confira com os olhos: a vida, a nitidez, o tamanho da máquina
entre os adesivos, nada cortado.
"""

from __future__ import annotations

import argparse
import io
import subprocess
import sys
from pathlib import Path

from PIL import Image

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

import acabamento  # noqa: E402
from produtos import PRODUTOS, RAIZ, arquivos_do_site  # noqa: E402


def _do_git(ref, caminho):
    saida = subprocess.run(["git", "-C", str(RAIZ), "show", f"{ref}:{caminho}"], capture_output=True)
    return Image.open(io.BytesIO(saida.stdout)) if saida.returncode == 0 and saida.stdout else None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--antes", help="o commit das fotos de antes (ex.: HEAD~1)")
    parser.add_argument("--saida", default=str(AQUI / "saida" / "folhas"))
    parser.add_argument("--largura", type=int, default=480)
    args = parser.parse_args(argv)
    for chave in PRODUTOS:
        arquivos = [(v, t, c) for p, v, t, c in arquivos_do_site() if p == chave]
        itens = []
        if args.antes:
            for variante, tomada, caminho in arquivos:
                antes = _do_git(args.antes, caminho)
                if antes is not None:
                    itens.append((antes, f"ANTES {variante}/{Path(caminho).name}"))
        for variante, tomada, caminho in arquivos:
            itens.append((RAIZ / caminho, f"{variante}/{Path(caminho).name}"))
        destino = Path(args.saida) / f"{chave}.jpg"
        acabamento.folha_de_contato(itens, destino, colunas=4, largura=args.largura,
                                    titulo=f"{PRODUTOS[chave]['nome']}: antes (em cima) e depois" if args.antes else None)
        print(destino)


if __name__ == "__main__":
    main()
