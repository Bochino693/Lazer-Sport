"""A conferência das fotos de um adesivo (LEIA-ME 72): a quase igual e a sem fundo.

Duas regras do cliente para as fotos das posições de cada adesivo:

  * nada de duas fotos quase iguais no mesmo adesivo (a mesma sala, o mesmo
    ângulo): `parecidas` compara a "assinatura" das duas (um dHash de 16 x 16,
    256 bits, também contra a outra espelhada -- o lado esquerdo de uma
    máquina simétrica é o direito ao contrário). Usada no painel (a foto nova
    de uma posição), na ferramenta que sobe as posições tiradas do 3D
    (core.variantes.subir_posicoes) e no teste das vistas de cada adesivo;
  * nada de foto sem fundo no site: `sem_fundo` diz se a foto é um recorte
    (transparente, como as do remove.bg) ou de fundo branco (a de estúdio).
    Essas ficam guardadas como "recorte para artes" (só no painel).
"""

from PIL import Image

#: Quantos bits (de 256) separam, no máximo, duas fotos "quase iguais".
LIMITE = 32


def _abrir(origem):
    """A imagem (RGBA) de um caminho, de um arquivo enviado ou de um campo de imagem."""
    if hasattr(origem, "seek"):
        origem.seek(0)
    imagem = Image.open(origem)
    imagem.load()
    if hasattr(origem, "seek"):
        origem.seek(0)
    return imagem.convert("RGBA")


def _bits(cinza, lado):
    px = cinza.load()
    bits = 0
    for y in range(lado):
        for x in range(lado):
            bits = (bits << 1) | (px[x, y] > px[x + 1, y])
    return bits


def assinatura(origem, lado=16):
    """(a assinatura, a da foto espelhada): dois inteiros de lado x lado bits."""
    imagem = _abrir(origem)
    fundo = Image.new("RGBA", imagem.size, (255, 255, 255, 255))
    fundo.alpha_composite(imagem)
    cinza = fundo.convert("L").resize((lado + 1, lado), Image.LANCZOS)
    espelho = fundo.convert("L").transpose(Image.FLIP_LEFT_RIGHT).resize((lado + 1, lado), Image.LANCZOS)
    return _bits(cinza, lado), _bits(espelho, lado)


def distancia(a, b):
    """Os bits diferentes entre duas assinaturas (a menor: direta ou espelhada)."""
    return min(bin(a[0] ^ b[0]).count("1"), bin(a[0] ^ b[1]).count("1"))


def parecidas(a, b, limite=LIMITE):
    """As duas assinaturas são de fotos quase iguais?"""
    return distancia(a, b) <= limite


def repetidas(assinaturas, limite=LIMITE):
    """Os pares (i, j) quase iguais de uma lista de assinaturas."""
    return [
        (i, j)
        for i in range(len(assinaturas))
        for j in range(i + 1, len(assinaturas))
        if parecidas(assinaturas[i], assinaturas[j], limite)
    ]


def sem_fundo(origem):
    """A foto é um recorte (transparente) ou de fundo branco? Olha a moldura (6% de cada lado)."""
    imagem = _abrir(origem)
    imagem.thumbnail((200, 200))
    largura, altura = imagem.size
    if largura < 8 or altura < 8:
        return False
    borda = max(1, round(min(largura, altura) * 0.06))
    px = imagem.load()
    moldura = [
        px[x, y]
        for y in range(altura)
        for x in range(largura)
        if x < borda or y < borda or x >= largura - borda or y >= altura - borda
    ]
    transparentes = sum(1 for p in moldura if p[3] < 200)
    if transparentes > 0.10 * len(moldura):
        return True
    brancos = sum(1 for p in moldura if p[3] >= 200 and min(p[:3]) >= 236)
    return brancos > 0.60 * len(moldura)


# ----------------------------------------------------------------------
# A VARREDURA: as fotos sem fundo que ninguém marcou (LEIA-ME 72)
# ----------------------------------------------------------------------
# O cliente: "me diga sobre as imagens de fundo branco dos brinquedos, por que
# ainda aparecem? elas devem ficar de fora dos carrosseis e cards, ficando
# somente para outras finalidades." Toda foto ainda não conferida (`fundo`
# vazio) é olhada: a sem fundo vira "recorte para artes" (fica guardada, com a
# posição dela, e some do site); a capa (`imagem_brinquedo`) sem fundo dá
# lugar à primeira foto com fundo do adesivo padrão (a de antes fica em
# `capa_sem_fundo` e numa linha da galeria, como recorte). Nada é apagado; a
# capa em cena ("cena") e a de antes dela ("original") não são tocadas. As
# máquinas da Black Friday (core.variantes.BLACK_FRIDAY) ficam de fora por
# padrão: outra frente cuida das fotos delas (o comando lista; com
# --com-black-friday, marca também).

#: Os papéis que a varredura não confere: a capa em cena e as que já estão fora do site.
NAO_CONFERIR = ("cena", "original", "recorte")
FORA_DO_SITE = ("original", "recorte")
ORDEM = {"perfil": 0, "tres_quartos": 1, "lado_direito": 2, "lado_esquerdo": 3, "verso": 4, "de_cima": 5}


def miniatura(imagem, tempo=8):
    """A foto pequena para conferir (BytesIO): do Cloudinary, 240 px e no formato dela (sem o
    `f_auto`, que trocaria o PNG transparente por outro); fora dele, o próprio arquivo."""
    from io import BytesIO
    from urllib.request import Request, urlopen

    from .fotos import url_da_imagem

    url = url_da_imagem(imagem)
    if url and "res.cloudinary.com" in url and "/upload/" in url:
        antes, depois = url.split("/upload/", 1)
        pedido = Request(f"{antes}/upload/c_limit,w_240/{depois}", headers={"User-Agent": "lazer-sport-fotos/1.0"})
        with urlopen(pedido, timeout=tempo) as resposta:
            return BytesIO(resposta.read())
    with imagem.open("rb") as arquivo:
        return BytesIO(arquivo.read())


def foto_sem_fundo(imagem):
    """A foto guardada (um campo de imagem) não tem fundo? Erro de rede ou de arquivo sobe."""
    return sem_fundo(miniatura(imagem))


def _da_black_friday(brinquedo, Brinquedos):
    from . import variantes

    return variantes._da_black_friday(brinquedo, Brinquedos)


def _publicas(fotos, padrao_id):
    """As fotos com fundo e com posição do adesivo padrão, na ordem das posições."""
    lista = [
        f for f in fotos
        if f.tipo and f.imagem and f.imagem.name and f.papel_na_capa not in FORA_DO_SITE
        and f.variante_id in (None, padrao_id)
    ]
    return sorted(lista, key=lambda f: (ORDEM.get(f.tipo, 9), f.ordem, f.id))


def sem_foto_com_fundo(fotos, padrao_id):
    """O adesivo padrão não tem NENHUMA foto com fundo (o painel avisa "precisa de foto com fundo")?"""
    return not _publicas(fotos, padrao_id)


def ajustar_capa(brinquedo, Brinquedos, ImagemBrinquedo, conferir=foto_sem_fundo, simular=False, avisar=print,
                 fotos=None):
    """A capa sem fundo dá lugar à primeira foto com fundo do padrão. Devolve "trocada", "sem_foto" ou "".

    A capa de antes fica em `capa_sem_fundo` e, se ainda não estava na
    galeria, numa linha nova dela (o recorte para artes): nada se perde.
    """
    capa = brinquedo.imagem_brinquedo.name if brinquedo.imagem_brinquedo else ""
    if not capa or brinquedo.capa_sem_fundo:
        return ""
    if fotos is None:  # (o --simular passa as fotos com as marcas que faria, só na memória)
        fotos = list(ImagemBrinquedo.objects.filter(brinquedo=brinquedo))
    linha = next((f for f in fotos if f.imagem.name == capa), None)
    if linha is not None:
        branca = linha.papel_na_capa in FORA_DO_SITE
    else:
        try:
            branca = conferir(brinquedo.imagem_brinquedo)
        except Exception as erro:  # a rede: fica para a próxima
            avisar(f"{brinquedo.nome_brinquedo}: a capa não foi conferida agora ({erro!r}).")
            return ""
    if not branca:
        return ""
    publicas = _publicas(fotos, brinquedo.adesivo_padrao_id)
    if not publicas:
        return "sem_foto"
    if simular:
        avisar(f"{brinquedo.nome_brinquedo}: a capa sem fundo daria lugar a {publicas[0].imagem.name}.")
        return "trocada"
    if linha is None:
        ImagemBrinquedo.objects.create(
            brinquedo=brinquedo, variante_id=brinquedo.adesivo_padrao_id, tipo=None,
            ordem=max([f.ordem for f in fotos] or [0]) + 1, imagem=capa, papel_na_capa="recorte", fundo="sem",
            texto_alternativo=f"{brinquedo.nome_brinquedo}: a capa de antes, sem fundo (recorte para artes)"[:180],
        )
    Brinquedos.objects.filter(pk=brinquedo.pk).update(imagem_brinquedo=publicas[0].imagem.name, capa_sem_fundo=capa)
    brinquedo.imagem_brinquedo, brinquedo.capa_sem_fundo = publicas[0].imagem.name, capa
    avisar(f"{brinquedo.nome_brinquedo}: a capa sem fundo saiu do site; a capa agora é {publicas[0].imagem.name}.")
    return "trocada"


def marcar_sem_fundo(Brinquedos, ImagemBrinquedo, conferir=foto_sem_fundo, simular=False, avisar=print,
                     com_black_friday=False, prazo=None):
    """A varredura (a 0177 no Render e o comando `fotos_sem_fundo`). Pode rodar de novo.

    Confere só as fotos ainda não conferidas (`fundo` vazio), fora a capa em
    cena e as que já estão fora do site; a que falha (a rede) fica para a
    próxima, com aviso. `prazo`: segundos (a varredura para sem erro, e a
    próxima continua de onde ficou). Devolve o resumo: {"marcadas",
    "conferidas", "capas", "sem_foto_com_fundo", "falhas", "black_friday"}.
    """
    import time

    inicio = time.monotonic()
    resumo = {"marcadas": [], "conferidas": 0, "capas": [], "sem_foto_com_fundo": [], "falhas": [], "black_friday": []}
    for brinquedo in Brinquedos.objects.order_by("id"):
        if not com_black_friday and _da_black_friday(brinquedo, Brinquedos):
            resumo["black_friday"].append(brinquedo.nome_brinquedo)
            continue
        simuladas = set()  # (no --simular, as que seriam marcadas)
        fila = ImagemBrinquedo.objects.filter(brinquedo=brinquedo, fundo="").exclude(papel_na_capa__in=NAO_CONFERIR)
        for foto in fila.order_by("ordem", "id"):
            if not foto.imagem or not foto.imagem.name:
                continue
            if prazo is not None and time.monotonic() - inicio > prazo:
                avisar("A varredura parou no prazo; rode de novo para continuar: python manage.py fotos_sem_fundo")
                return resumo
            try:
                sem = conferir(foto.imagem)
            except Exception as erro:  # a rede, o arquivo: esta fica para a próxima
                resumo["falhas"].append(f"{brinquedo.nome_brinquedo}: {foto.imagem.name} ({erro!r})")
                avisar(f"{brinquedo.nome_brinquedo}: {foto.imagem.name} não foi conferida agora ({erro!r}).")
                continue
            resumo["conferidas"] += 1
            if sem:
                resumo["marcadas"].append(f"{brinquedo.nome_brinquedo}: {foto.imagem.name} ({foto.tipo or 'sem posição'})")
            if simular:
                if sem:
                    simuladas.add(foto.pk)
                continue
            mudar = {"fundo": "sem" if sem else "com"}
            if sem:
                mudar["papel_na_capa"] = "recorte"
            ImagemBrinquedo.objects.filter(pk=foto.pk).update(**mudar)
        fotos = list(ImagemBrinquedo.objects.filter(brinquedo=brinquedo))
        for foto in fotos:
            if foto.pk in simuladas:
                foto.papel_na_capa = "recorte"
        capa = ajustar_capa(brinquedo, Brinquedos, ImagemBrinquedo, conferir=conferir, simular=simular, avisar=avisar,
                            fotos=fotos if simular else None)
        if capa == "trocada":
            resumo["capas"].append(brinquedo.nome_brinquedo)
        if not simular:
            fotos = list(ImagemBrinquedo.objects.filter(brinquedo=brinquedo))
        if capa == "sem_foto" or (fotos and sem_foto_com_fundo(fotos, brinquedo.adesivo_padrao_id)):
            resumo["sem_foto_com_fundo"].append(brinquedo.nome_brinquedo)
    return resumo


def desmarcar_sem_fundo(Brinquedos, ImagemBrinquedo):
    """A volta da 0177: a capa de antes volta; as fotos marcadas pela conferência voltam a ser fotos."""
    for brinquedo in Brinquedos.objects.exclude(capa_sem_fundo=""):
        Brinquedos.objects.filter(pk=brinquedo.pk).update(imagem_brinquedo=brinquedo.capa_sem_fundo, capa_sem_fundo="")
    ImagemBrinquedo.objects.filter(fundo="sem", papel_na_capa="recorte").update(papel_na_capa="")
    ImagemBrinquedo.objects.exclude(fundo="").update(fundo="")
