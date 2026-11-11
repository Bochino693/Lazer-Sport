"""A placa iluminada do showroom da Lazer & Sport (o lugar `showroom` do lugares.js).

No showroom de verdade (a foto do Boliche Virtual no catálogo), o logo é uma placa
na parede preta: o alvo com o dardo em cima e, embaixo, o contorno branco aceso com
"Lazer & Sport" em branco e "Brinquedos · Cenografia · Parques" em vermelho. Este
script faz essa placa a partir do logo oficial do repositório
(core/static/images/logoofi.png): no painel de baixo, o branco do fundo some (a
parede preta aparece), o escuro (as letras e o contorno) vira branco aceso e o
vermelho fica vermelho; o alvo fica como é. Grava showroom/placa-lazer-sport.png.

    python ferramentas/categorias/placa.py
"""

from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parent.parent.parent
LOGO = RAIZ / "core" / "static" / "images" / "logoofi.png"
SAIDA = Path(__file__).resolve().parent / "showroom" / "placa-lazer-sport.png"


def placa():
    logo = Image.open(LOGO).convert("RGBA")
    w, h = logo.size
    # onde começa o painel do nome (a primeira linha, de baixo para cima, sem o branco do painel)
    corte = int(h * 0.555)
    saida = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    saida.paste(logo.crop((0, 0, w, corte)), (0, 0))
    painel = logo.crop((0, corte, w, h))
    pixels = []
    for r, g, b, a in painel.getdata():
        if a < 40:
            pixels.append((0, 0, 0, 0))
        elif r > 150 and g < 110 and b < 120:
            pixels.append((235, 40, 52, a))  # o vermelho fica vermelho
        elif min(r, g, b) > 200:
            pixels.append((0, 0, 0, 0))  # o branco do painel some
        else:
            luz = 255 - min(r, g, b)  # o escuro (as letras, o contorno) vira branco aceso
            pixels.append((255, 255, 255, min(a, int(80 + luz * 0.7))))
    painel.putdata(pixels)
    saida.paste(painel, (0, corte), painel)
    SAIDA.parent.mkdir(exist_ok=True)
    saida.save(SAIDA)
    return SAIDA


if __name__ == "__main__":
    print(placa())
