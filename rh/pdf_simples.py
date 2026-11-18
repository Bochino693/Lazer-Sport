"""Um PDF de texto de verdade, escrito à mão, para o termo assinado.

POR QUE ISTO EXISTE. As folhas do painel (proposta, O.S., termo de compra,
ficha do colaborador, espelho de ponto) saem pela impressão do navegador --
"Salvar em PDF" --, e o projeto não tem biblioteca de PDF. O termo de
exclusividade assinado é diferente: ele precisa virar um ARQUIVO guardado
na pasta do colaborador no instante da assinatura, sem ninguém clicar em
imprimir. Instalar weasyprint/reportlab para uma folha de texto seria muito
peso; o formato PDF de uma página de texto com uma imagem cabe aqui.

O QUE SABE FAZER: páginas A4, texto em Helvetica e Helvetica-Bold (as
fontes que todo leitor de PDF tem, sem embutir nada) com quebra de linha
pela largura real de cada letra, linhas, e uma imagem PNG (o traço da
assinatura) achatada sobre branco. O texto sai em WinAnsi (cp1252), que
tem todos os acentos do português; o que não couber nele vira "?".

O resultado é texto selecionável e pesquisável, de poucos KB, que o pypdf
lê de volta -- há teste que confere.
"""

from __future__ import annotations

import io
import zlib
from datetime import datetime

A4 = (595.28, 841.89)
MARGEM = 56

# Larguras (em milésimos do corpo) da Helvetica e da Helvetica-Bold, das
# métricas AFM padrão. Letra acentuada tem a largura da letra sem acento.
_ASCII = " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~"
_REGULAR = (
    278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
    556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
    1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
    667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
    333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
    556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584,
)
_NEGRITO = (
    278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278,
    556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 333, 333, 584, 584, 584, 611,
    975, 722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778,
    667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 333, 278, 333, 584, 556,
    333, 556, 611, 556, 611, 556, 333, 611, 611, 278, 278, 556, 278, 889, 611, 611,
    611, 611, 389, 556, 333, 611, 556, 778, 556, 556, 500, 389, 280, 389, 584,
)
LARGURAS = {
    "F1": dict(zip(_ASCII, _REGULAR)),
    "F2": dict(zip(_ASCII, _NEGRITO)),
}
_EXTRAS = {"—": 1000, "–": 556, "…": 1000, "“": 333, "”": 333, "‘": 222, "’": 222,
           "º": 365, "ª": 370, "§": 556, "°": 400, "·": 278, "•": 350}
_SEM_ACENTO = str.maketrans(
    "áàâãäéèêëíìîïóòôõöúùûüçñÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑ",
    "aaaaaeeeeiiiiooooouuuucnAAAAAEEEEIIIIOOOOOUUUUCN",
)


def largura(texto: str, fonte: str, corpo: float) -> float:
    tabela = LARGURAS[fonte]
    total = 0
    for letra in texto:
        if letra in tabela:
            total += tabela[letra]
        elif letra in _EXTRAS:
            total += _EXTRAS[letra]
        else:
            total += tabela.get(letra.translate(_SEM_ACENTO), 556)
    return total * corpo / 1000


def quebrar(texto: str, fonte: str, corpo: float, maximo: float) -> list[str]:
    linhas = []
    for paragrafo in (texto or "").split("\n"):
        atual = ""
        for palavra in paragrafo.split(" "):
            tentativa = f"{atual} {palavra}" if atual else palavra
            if largura(tentativa, fonte, corpo) <= maximo or not atual:
                atual = tentativa
            else:
                linhas.append(atual)
                atual = palavra
        linhas.append(atual)
    return linhas


def _texto_pdf(texto: str) -> bytes:
    bruto = texto.encode("cp1252", errors="replace")
    return bruto.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


class Documento:
    """Monta as páginas de cima para baixo, como uma folha sendo escrita."""

    def __init__(self, titulo="Documento", autor=""):
        self.titulo = titulo
        self.autor = autor
        self.paginas: list[list[bytes]] = []
        self.imagens: list[tuple[int, int, bytes]] = []
        self.largura_util = A4[0] - 2 * MARGEM
        self.nova_pagina()

    # ---------------- paginação ----------------
    def nova_pagina(self):
        self.paginas.append([])
        self.y = A4[1] - MARGEM

    def _cabe(self, altura):
        if self.y - altura < MARGEM:
            self.nova_pagina()

    def _op(self, comando: bytes):
        self.paginas[-1].append(comando)

    # ---------------- escrita ----------------
    def texto(self, texto, *, corpo=10.5, negrito=False, entrelinha=1.42, recuo=0, centro=False, cinza=False, depois=4):
        fonte = "F2" if negrito else "F1"
        maximo = self.largura_util - recuo
        for linha in quebrar(texto, fonte, corpo, maximo):
            self._cabe(corpo * entrelinha)
            self.y -= corpo * entrelinha
            x = MARGEM + recuo
            if centro:
                x = (A4[0] - largura(linha, fonte, corpo)) / 2
            cor = b"0.35 g " if cinza else b"0 g "
            self._op(
                cor + b"BT /" + fonte.encode() + b" " + f"{corpo:.2f}".encode() + b" Tf "
                + f"{x:.2f} {self.y:.2f}".encode() + b" Td (" + _texto_pdf(linha) + b") Tj ET"
            )
        self.y -= depois

    def espaco(self, pontos):
        self.y -= pontos

    def linha(self, x1=None, x2=None, espessura=0.6):
        x1 = MARGEM if x1 is None else x1
        x2 = A4[0] - MARGEM if x2 is None else x2
        self._cabe(6)
        self.y -= 4
        self._op(f"0.5 G {espessura:.2f} w {x1:.2f} {self.y:.2f} m {x2:.2f} {self.y:.2f} l S".encode())
        self.y -= 4

    def imagem_png(self, dados_png: bytes, largura_max=220, altura_max=90):
        """O traço da assinatura, achatado sobre branco (sem transparência)."""
        from PIL import Image

        with Image.open(io.BytesIO(dados_png)) as original:
            imagem = original.convert("RGBA")
        fundo = Image.new("RGB", imagem.size, (255, 255, 255))
        fundo.paste(imagem, mask=imagem.getchannel("A"))
        caixa = fundo.convert("L").point(lambda v: 255 if v < 245 else 0).getbbox()
        if caixa:
            fundo = fundo.crop(caixa)
        w, h = fundo.size
        escala = min(largura_max / w, altura_max / h, 1.0)
        exibido = (w * escala, h * escala)
        self._cabe(exibido[1] + 6)
        self.y -= exibido[1]
        indice = len(self.imagens)
        self.imagens.append((w, h, zlib.compress(fundo.tobytes(), 9)))
        self._op(
            f"q {exibido[0]:.2f} 0 0 {exibido[1]:.2f} {MARGEM:.2f} {self.y:.2f} cm /Im{indice} Do Q".encode()
        )
        self.y -= 4

    # ---------------- saída ----------------
    def gerar(self) -> bytes:
        objetos: list[bytes] = []

        def novo(conteudo: bytes) -> int:
            objetos.append(conteudo)
            return len(objetos)

        catalogo = novo(b"")  # preenchido no fim
        paginas_id = novo(b"")
        f1 = novo(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
        f2 = novo(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
        imagens_ids = []
        for w, h, comprimido in self.imagens:
            imagens_ids.append(novo(
                f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceRGB "
                f"/BitsPerComponent 8 /Filter /FlateDecode /Length {len(comprimido)} >>\nstream\n".encode()
                + comprimido + b"\nendstream"
            ))
        recursos = (
            f"<< /Font << /F1 {f1} 0 R /F2 {f2} 0 R >> /XObject << "
            + " ".join(f"/Im{i} {obj} 0 R" for i, obj in enumerate(imagens_ids))
            + " >> >>"
        ).encode()

        filhos = []
        total = len(self.paginas)
        for numero, comandos in enumerate(self.paginas, start=1):
            rodape = (
                b"0.45 g BT /F1 8 Tf " + f"{MARGEM:.2f} 28 Td".encode() + b" ("
                + _texto_pdf(f"{self.titulo} · página {numero} de {total}") + b") Tj ET"
            )
            fluxo = zlib.compress(b"\n".join(comandos + [rodape]), 9)
            conteudo = novo(
                f"<< /Length {len(fluxo)} /Filter /FlateDecode >>\nstream\n".encode() + fluxo + b"\nendstream"
            )
            filhos.append(novo(
                f"<< /Type /Page /Parent {paginas_id} 0 R /MediaBox [0 0 {A4[0]} {A4[1]}] "
                f"/Contents {conteudo} 0 R /Resources ".encode() + recursos + b" >>"
            ))
        objetos[paginas_id - 1] = (
            f"<< /Type /Pages /Kids [{' '.join(f'{p} 0 R' for p in filhos)}] /Count {len(filhos)} >>".encode()
        )
        objetos[catalogo - 1] = f"<< /Type /Catalog /Pages {paginas_id} 0 R >>".encode()
        agora = datetime.now().strftime("D:%Y%m%d%H%M%S")
        info = novo(
            b"<< /Title (" + _texto_pdf(self.titulo) + b") /Author (" + _texto_pdf(self.autor)
            + b") /Producer (Lazer & Sport - painel interno) /CreationDate (" + agora.encode() + b") >>"
        )

        saida = io.BytesIO()
        saida.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        posicoes = []
        for numero, corpo in enumerate(objetos, start=1):
            posicoes.append(saida.tell())
            saida.write(f"{numero} 0 obj\n".encode() + corpo + b"\nendobj\n")
        inicio_xref = saida.tell()
        saida.write(f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode())
        for posicao in posicoes:
            saida.write(f"{posicao:010d} 00000 n \n".encode())
        saida.write(
            f"trailer\n<< /Size {len(objetos) + 1} /Root {catalogo} 0 R /Info {info} 0 R >>\n"
            f"startxref\n{inicio_xref}\n%%EOF\n".encode()
        )
        return saida.getvalue()
