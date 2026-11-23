"""A RESERVA DAS FOTOS: quando o Cloudinary não entrega, o site não mostra foto quebrada.

O QUE ACONTECEU (LEIA-ME-V10, seção 128). Em 23/11/2026 toda foto do
Cloudinary passou a voltar `401 cloud_name dgikjmki8 is disabled`: a conta
foi desativada do lado do Cloudinary, e o site inteiro (cards, página do
produto, categorias, logos dos clientes, peças) virou o ícone de imagem
quebrada com o texto alternativo por cima. Nada foi apagado -- quando a
conta volta, as fotos voltam sozinhas --, mas até lá o site não pode ficar
assim.

A RESERVA. Boa parte das fotos que o site mostra nasceu AQUI, no
repositório, e só depois subiu para o Cloudinary: as capas do showroom
(`site/capas_catalogo/<produto>.webp`), as capas dos objetos 3D
(`site/arena/modelos/<produto>/capa.webp`), as artes dos kits
(`site/kits/<kit>.webp`), as fotos das categorias
(`site/categorias/<categoria>.webp`) e as artes da Black Friday
(`site/black_friday/arte-NN.webp` / `card-NN.webp`). O nome que essas
fotos ganharam no Cloudinary carrega o nome do arquivo daqui
("cena-air-game-home-10bb33e058_ik4fg5" é a capa do Air Game Home), então
dá para achar a cópia local pelo nome.

`montar_indice()` lista essas cópias; o comando `fotos_reserva` grava a
lista em `site/fotos-reserva.json`, que o `ls-foto-reserva.js` lê só
quando uma foto do Cloudinary falha. A foto sem cópia local (logo de
cliente, foto de peça, combo) vira um quadro "Foto em atualização" no
lugar do ícone quebrado.
"""

import json
from pathlib import Path

PASTA_ESTATICA = Path(__file__).resolve().parent / "static"
ARQUIVO_INDICE = PASTA_ESTATICA / "site" / "fotos-reserva.json"
EXTENSOES = (".webp", ".jpg", ".jpeg", ".png")


def _url(caminho):
    return "/static/" + caminho.relative_to(PASTA_ESTATICA).as_posix()


def _arquivos(pasta):
    if not pasta.is_dir():
        return []
    return sorted(p for p in pasta.iterdir() if p.is_file() and p.suffix.lower() in EXTENSOES)


def montar_indice():
    """{grupo: {chave: url}}. A chave é o nome que o Cloudinary carrega."""
    site = PASTA_ESTATICA / "site"
    produtos = {}
    # capas do showroom por produto
    for arquivo in _arquivos(site / "capas_catalogo"):
        produtos[arquivo.stem] = _url(arquivo)
    # capas dos objetos 3D (também as dos adesivos: air-game-kids-alienigenas...)
    modelos = site / "arena" / "modelos"
    if modelos.is_dir():
        for pasta in sorted(p for p in modelos.iterdir() if p.is_dir()):
            capa = pasta / "capa.webp"
            if capa.is_file():
                produtos.setdefault(pasta.name, _url(capa))
    # artes dos kits
    for arquivo in _arquivos(site / "kits"):
        produtos[arquivo.stem] = _url(arquivo)
    categorias = {a.stem: _url(a) for a in _arquivos(site / "categorias")}
    black_friday = {a.stem: _url(a) for a in _arquivos(site / "black_friday")}
    return {
        "produtos": dict(sorted(produtos.items())),
        "categorias": categorias,
        "black_friday": black_friday,
    }


def texto_do_indice():
    return json.dumps(montar_indice(), ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def gravar_indice():
    ARQUIVO_INDICE.write_text(texto_do_indice(), encoding="utf-8")
    return ARQUIVO_INDICE
