"""Recorte automático das fotos de peça em fundo branco (LEIA-ME seção 102).

O dono: "o site deve estar tinindo ... as apresentações de produtos, os fundos".
As peças de reposição chegam do fornecedor em foto de catálogo: o produto num
fundo branco. No tema escuro do site isso vira um retângulo branco solto no
meio da galeria (e, nas fotos em pé, uma faixa branca com sobra escura dos
lados). Os brinquedos ganharam fundo de showroom; as peças ganham o recorte:
o fundo branco sai e a peça aparece inteira sobre o palco azul do site.

Só sai o branco que ENCOSTA NA BORDA da foto (preenchimento a partir das
bordas, comparando com o branco do fundo, não com o vizinho). O branco de
dentro da peça (a caixa do controle, um rolo de fio branco) não toca a borda
pelo fundo e fica. Foto que não é "produto no branco" (fundo de verdade, foto
de ambiente) devolve None e continua como está.

Sem numpy: só Pillow (o floodfill dele), com a foto reduzida a no máximo
LADO_MAXIMO px. Leva menos de um segundo por foto.
"""

import io

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

LADO_MAXIMO = 1200
LADO_MINIMO = 800           # foto menor que isto é ampliada 2x antes: a beira sai lisa no card
QUASE_BRANCO = 236          # cada canal >= isto conta como fundo branco na borda
BORDA_BRANCA_MINIMA = 0.80  # fração da borda que precisa ser branca
TOLERANCIA = 36             # soma das diferenças RGB aceita no preenchimento
SOMBRA_ALCANCE = 0.08       # até onde a sombra clara pode ir (fração do lado)
SOMBRA_LUZ_MINIMA = 150     # mais escuro que isto já é a peça
SOMBRA_SATURACAO = 14       # sombra é cinza neutro: o brilho rosado do disco é a peça
SOMBRA_ALFA_MAXIMO = 160    # a sombra nunca fica mais forte que isto
SOMBRA_ENCOSTA_NA_PECA = 0.5  # fração do encosto que precisa ser peça escura/colorida
SOMBRA_DEGRAU = 24          # o quanto a sombra pode escurecer de um px para o seguinte
FURO_DIFERENCA_MAXIMA = 3.0  # o vão tem a cor do fundo (a caixa branca difere 4 a 9)
FURO_TEXTURA_MAXIMA = 2.5    # e é liso como ele (o fio branco tem textura)
BRANCO_DO_FURO = 245       # branco puro (o do fundo) preso dentro da peça
FURO_MINIMO = 0.0004        # pedaço menor que isto é brilho, não furo
ANEL_ESCURO = 110           # luz abaixo disto é peça (o fio preto, o cabo)
ANEL_COLORIDO = 70          # saturação acima disto é peça (o fio amarelo, o azul)
ALCANCE_DO_ANEL = 0.05      # quanto olhar para fora da beira do furo (fração do lado)
CERCADO_DE_ESCURO = 0.80    # fração da beira que precisa achar peça
SOBRA = 0.04                # margem em volta da peça depois de aparar
COR_MARCA = (3, 251, 7)     # cor que nenhuma foto de peça tem


def _ja_tem_transparencia(im):
    """A foto já veio recortada (PNG sem fundo): a borda é transparente."""
    if im.mode != "RGBA":
        return False
    alfa = im.getchannel("A")
    w, h = im.size
    pontos = [(x, 0) for x in range(0, w, max(1, w // 40))] + [(0, y) for y in range(0, h, max(1, h // 40))]
    transparentes = sum(1 for p in pontos if alfa.getpixel(p) < 16)
    return transparentes >= len(pontos) * 0.6


def _borda(w, h):
    passo_x = max(1, w // 200)
    passo_y = max(1, h // 200)
    for x in range(0, w, passo_x):
        yield (x, 0)
        yield (x, h - 1)
    for y in range(0, h, passo_y):
        yield (0, y)
        yield (w - 1, y)


def _quase_branco(cor):
    return all(c >= QUASE_BRANCO for c in cor[:3])


def _aparar(im):
    caixa = im.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
    if not caixa:
        return None
    im = im.crop(caixa)
    sobra = int(max(im.size) * SOBRA)
    final = Image.new("RGBA", (im.width + 2 * sobra, im.height + 2 * sobra), (0, 0, 0, 0))
    final.alpha_composite(im, (sobra, sobra))
    return final


def _png(im):
    saida = io.BytesIO()
    im.save(saida, format="PNG", optimize=True)
    return saida.getvalue()


def recortar(conteudo):
    """bytes da foto -> bytes de um PNG sem fundo, ou None se a foto não é de fundo branco."""
    try:
        im = Image.open(io.BytesIO(conteudo))
        im = ImageOps.exif_transpose(im)
        im.load()
    except Exception:
        return None
    if im.mode in ("P", "LA", "PA") or (im.mode == "RGBA"):
        im = im.convert("RGBA")
    else:
        im = im.convert("RGB").convert("RGBA")
    im.thumbnail((LADO_MAXIMO, LADO_MAXIMO))
    w, h = im.size
    if w < 40 or h < 40:
        return None

    if _ja_tem_transparencia(im):
        aparada = _aparar(_ampliar_se_pequena(im))
        return _png(aparada) if aparada else None

    # Transparência parcial vira branco antes de medir o fundo.
    branco = Image.new("RGBA", im.size, (255, 255, 255, 255))
    branco.alpha_composite(im)
    rgb = branco.convert("RGB")

    borda = list(_borda(w, h))
    brancos = [p for p in borda if _quase_branco(rgb.getpixel(p))]
    if len(brancos) < len(borda) * BORDA_BRANCA_MINIMA:
        return None

    fundo = _fundo(rgb, brancos, TOLERANCIA)
    peca = ImageChops.invert(fundo)
    fracao = _fracao(peca)
    if fracao < 0.03 or fracao > 0.97:
        return None

    # O branco preso por dentro da peça (o miolo de um rolo de fio, o vão da
    # volta de um cabo) também é fundo, mas só quando é branco puro e quem o
    # cerca é peça escura ou colorida. Branco cercado de claro é a própria
    # peça (a caixa do controle, um rolo de fio branco) e fica.
    furos = _furos(rgb, fundo)
    if furos is not None:
        peca = ImageChops.subtract(peca, furos)

    # A sombra cinza-clara da foto de catálogo (embaixo do cabo, na beira do
    # rolo) vira sombra de verdade: preta e translúcida no palco azul.
    peca, sombra = _sombra(rgb, peca)

    # Tira 1 px de franja branca e suaviza a borda (antisserrilhado).
    alfa = peca.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.7))
    cor = rgb
    if sombra is not None:
        tem_sombra = sombra.point(lambda v: 255 if v else 0)
        alfa = ImageChops.lighter(alfa, sombra.filter(ImageFilter.GaussianBlur(0.6)))
        cor = Image.composite(Image.new("RGB", rgb.size, (0, 0, 0)), rgb, tem_sombra)
    recorte = cor.convert("RGBA")
    recorte.putalpha(alfa)
    aparada = _aparar(_ampliar_se_pequena(recorte))
    return _png(aparada) if aparada else None


def _ampliar_se_pequena(recorte):
    """A foto pequena (a "prévia" de 375 px que muita peça tem) sai 2x maior.

    O card mostra a peça maior que a foto e a beira recortada ficaria
    serrilhada. O recorte é feito ANTES, no tamanho da foto (ampliar antes
    deixaria toda beira "gradual" e a regra da sombra comeria peça). A cor
    da peça vaza um pouco para o fundo antes de ampliar, para a beira
    meio transparente não puxar o branco que havia ali.
    """
    w, h = recorte.size
    if max(w, h) >= LADO_MINIMO:
        return recorte
    alfa = recorte.getchannel("A")
    cor = recorte.convert("RGB")
    solida = alfa.point(lambda v: 255 if v > 8 else 0)
    cor = Image.composite(cor, cor.filter(ImageFilter.MinFilter(5)), solida)
    cor = cor.resize((w * 2, h * 2), Image.LANCZOS)
    alfa = alfa.resize((w * 2, h * 2), Image.BICUBIC)
    maior = cor.convert("RGBA")
    maior.putalpha(alfa)
    return maior


def _sombra(rgb, peca):
    """Descasca a sombra clara grudada no fundo: (peça sem a sombra, alfa da sombra ou None).

    Anda da beira do fundo para dentro, um px por vez, enquanto o pixel é
    cinza claro e vai ESCURECENDO AOS POUCOS (é assim que uma sombra chega na
    peça; a beira de uma peça clara, como o topo da maneta, pula de uma vez). Uma
    peça branca fica mais clara para dentro depois da linha da beira, e aí o
    descascar para: no máximo a beira vira um contorno escuro fino.
    """
    w, h = rgb.size
    luz = list(rgb.convert("L").getdata())
    sat = list(rgb.convert("HSV").getchannel("S").getdata())
    dentro = list(peca.getdata())
    estado = bytearray(w * h)  # 0 peça, 1 fundo, 2 sombra
    for i, v in enumerate(dentro):
        if not v:
            estado[i] = 1
    frente = set()
    for i in range(w * h):
        if estado[i]:
            continue
        x, y = i % w, i // w
        if (x > 0 and estado[i - 1]) or (x < w - 1 and estado[i + 1]) or \
                (y > 0 and estado[i - w]) or (y < h - 1 and estado[i + w]):
            frente.add(i)
    passos = max(4, int(max(w, h) * SOMBRA_ALCANCE))
    for _ in range(passos):
        descascados = []
        for i in frente:
            if luz[i] < SOMBRA_LUZ_MINIMA or sat[i] > SOMBRA_SATURACAO:
                continue
            x, y = i % w, i // w
            referencia = -1
            for j, ok in ((i - 1, x > 0), (i + 1, x < w - 1), (i - w, y > 0), (i + w, y < h - 1)):
                if ok and estado[j]:
                    referencia = max(referencia, luz[j])
            # Sombra escurece aos poucos (250, 246, 240, 234...); a beira de
            # uma peça pula de uma vez (255, 240, 170): aí não é sombra.
            if referencia >= 0 and referencia - SOMBRA_DEGRAU <= luz[i] <= referencia + 4:
                descascados.append(i)
        if not descascados:
            break
        nova = set()
        for i in descascados:
            estado[i] = 2
        for i in descascados:
            x, y = i % w, i // w
            for j, ok in ((i - 1, x > 0), (i + 1, x < w - 1), (i - w, y > 0), (i + w, y < h - 1)):
                if ok and not estado[j]:
                    nova.add(j)
        frente = nova
    if 2 not in estado:
        return peca, None

    # Sombra encosta na PEÇA (escura ou colorida). Se o pedaço descascado
    # encosta mais em claro, era a beira de uma peça branca: volta a ser peça.
    visto = bytearray(w * h)
    for inicio in range(w * h):
        if estado[inicio] != 2 or visto[inicio]:
            continue
        pilha, pedaco = [inicio], []
        visto[inicio] = 1
        encostos = solidos = 0
        while pilha:
            i = pilha.pop()
            pedaco.append(i)
            x, y = i % w, i // w
            for j, ok in ((i - 1, x > 0), (i + 1, x < w - 1), (i - w, y > 0), (i + w, y < h - 1)):
                if not ok:
                    continue
                if estado[j] == 2 and not visto[j]:
                    visto[j] = 1
                    pilha.append(j)
                elif estado[j] == 0:
                    encostos += 1
                    # peça: escura, colorida, ou uma beira que escurece de
                    # repente (a sombra chegando no cabo). A peça branca
                    # CLAREIA depois da beira: essa não conta.
                    if (luz[j] < SOMBRA_LUZ_MINIMA or sat[j] > SOMBRA_SATURACAO
                            or luz[j] < luz[i] - SOMBRA_DEGRAU):
                        solidos += 1
        if not encostos or solidos < encostos * SOMBRA_ENCOSTA_NA_PECA:
            for i in pedaco:
                estado[i] = 0
    if 2 not in estado:
        return peca, None
    peca_limpa = Image.frombytes("L", (w, h), bytes(255 if e == 0 else 0 for e in estado))
    sombra = Image.frombytes("L", (w, h), bytes(
        min(SOMBRA_ALFA_MAXIMO, int((255 - luz[i]) * 2.0)) if estado[i] == 2 else 0 for i in range(w * h)))
    return peca_limpa, sombra


def _furos(rgb, fundo):
    """Máscara L (255 = furo) dos brancos puros presos dentro da peça e cercados por ela."""
    w, h = rgb.size
    puro = rgb.convert("L").point(lambda v: 255 if v >= BRANCO_DO_FURO else 0)
    # Nos três canais (um amarelo claro não é branco).
    for canal in rgb.split():
        puro = ImageChops.multiply(puro, canal.point(lambda v: 255 if v >= BRANCO_DO_FURO else 0))
    candidatos = ImageChops.subtract(puro, fundo)
    if not candidatos.getbbox():
        return None
    marca = list(candidatos.getdata())
    # A cor do fundo de verdade (a média do branco que encosta na borda): o
    # furo tem ESSA cor, lisa; o branco da peça (a caixa do controle, o fio
    # branco) é parecido mas não é igual -- tem um tom e tem textura.
    cores = list(rgb.getdata())
    no_fundo = [cores[i] for i, v in enumerate(fundo.getdata()) if v]
    cor_do_fundo = [sum(c[k] for c in no_fundo) / len(no_fundo) for k in range(3)] if no_fundo else [255, 255, 255]
    # "Peça" em volta: escuro ou colorido. Cinza claro e branco não contam
    # (é assim que a caixa branca do controle e o rolo de fio branco ficam).
    escuro = rgb.convert("L").point(lambda v: 255 if v < ANEL_ESCURO else 0)
    colorido = rgb.convert("HSV").getchannel("S").point(lambda v: 255 if v > ANEL_COLORIDO else 0)
    solido = list(ImageChops.lighter(escuro, colorido).getdata())
    visto = bytearray(w * h)
    furo = bytearray(w * h)
    minimo = max(12, int(w * h * FURO_MINIMO))
    for inicio in range(w * h):
        if not marca[inicio] or visto[inicio]:
            continue
        pilha = [inicio]
        visto[inicio] = 1
        pedaco = []
        while pilha:
            i = pilha.pop()
            pedaco.append(i)
            x, y = i % w, i // w
            for j in ((i - 1) if x > 0 else -1, (i + 1) if x < w - 1 else -1,
                      (i - w) if y > 0 else -1, (i + w) if y < h - 1 else -1):
                if j >= 0 and marca[j] and not visto[j]:
                    visto[j] = 1
                    pilha.append(j)
        if len(pedaco) < minimo:
            continue
        if _igual_ao_fundo([cores[i] for i in pedaco], cor_do_fundo):
            for i in pedaco:
                furo[i] = 255
            continue
        # Quem cerca: de cada ponto da beira do pedaço, olha para fora até
        # ALCANCE px; se encontra peça (escuro ou colorido) é um furo da peça.
        # A beira do cabo costuma ter um brilho claro, por isso não basta o
        # vizinho colado.
        dentro = set(pedaco)
        alcance = max(6, int(max(w, h) * ALCANCE_DO_ANEL))
        olhadas = escuras = 0
        for i in pedaco:
            x, y = i % w, i // w
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                vizinho = (y + dy) * w + (x + dx)
                if not (0 <= x + dx < w and 0 <= y + dy < h) or vizinho in dentro:
                    continue
                olhadas += 1
                for passo in range(1, alcance + 1):
                    nx, ny = x + dx * passo, y + dy * passo
                    if not (0 <= nx < w and 0 <= ny < h):
                        break
                    if solido[ny * w + nx]:
                        escuras += 1
                        break
        if olhadas and escuras >= olhadas * CERCADO_DE_ESCURO:
            for i in pedaco:
                furo[i] = 255
    mascara = Image.frombytes("L", (w, h), bytes(furo))
    return mascara if mascara.getbbox() else None


def _igual_ao_fundo(cores, cor_do_fundo):
    """O pedaço é o fundo visto por um vão: a mesma cor do fundo e liso como ele.

    Medido nas fotos reais: o miolo dos rolos e o vão do cabo diferem do fundo
    em até ~2 pontos por canal, com variação ~1,5; a face branca da caixa do
    controle difere 4 a 9 pontos (é peça).
    """
    n = len(cores)
    media = [sum(c[k] for c in cores) / n for k in range(3)]
    if max(abs(media[k] - cor_do_fundo[k]) for k in range(3)) > FURO_DIFERENCA_MAXIMA:
        return False
    luz = [sum(c) / 3.0 for c in cores]
    m = sum(luz) / n
    return (sum((v - m) ** 2 for v in luz) / n) ** 0.5 <= FURO_TEXTURA_MAXIMA


def _fundo(rgb, sementes, tolerancia):
    """Máscara L (255 = fundo) do branco que encosta na borda."""
    pintada = rgb.copy()
    for p in sementes:
        if pintada.getpixel(p) == COR_MARCA:
            continue
        ImageDraw.floodfill(pintada, p, COR_MARCA, thresh=tolerancia)
    diferenca = ImageChops.difference(pintada, Image.new("RGB", rgb.size, COR_MARCA)).convert("L")
    return diferenca.point(lambda v: 0 if v > 0 else 255)


def _fracao(mascara):
    w, h = mascara.size
    return sum(mascara.histogram()[128:]) / float(w * h)


# ---------------------------------------------------------------------------
# A foto da peça no cadastro (ImagemPeca). Serve ao modelo de verdade e ao
# modelo histórico das migrações: só usa os campos `imagem`,
# `imagem_original` e `recorte_de` e grava com .update() (sem sinais).
#
#   imagem           o que o site mostra (o recorte em PNG, quando há)
#   imagem_original  a foto que a equipe subiu, guardada para desfazer
#   recorte_de       o nome do arquivo de `imagem` já conferido: se for igual
#                    ao atual, não confere de novo (com ou sem recorte)
# ---------------------------------------------------------------------------

MARCA_DO_RECORTE = "-sem-fundo"


def baixar(imagem, tempo=25):
    """Os bytes da foto: do Cloudinary no tamanho de trabalho e no formato dela; fora dele, o arquivo."""
    from urllib.request import Request, urlopen

    from .fotos import url_da_imagem

    url = url_da_imagem(imagem)
    if url and "res.cloudinary.com" in url and "/upload/" in url:
        antes, depois = url.split("/upload/", 1)
        pedido = Request(f"{antes}/upload/c_limit,w_{LADO_MAXIMO},h_{LADO_MAXIMO}/{depois}",
                         headers={"User-Agent": "lazer-sport-fotos/1.0"})
        with urlopen(pedido, timeout=tempo) as resposta:
            return resposta.read()
    with imagem.open("rb") as arquivo:
        return arquivo.read()


#: A coluna do arquivo (ImageField) guarda até 100 caracteres. O nome do
#: recorte cabe com folga: o Cloudinary ainda pode pôr um sufixo nele. (O
#: primeiro deploy caiu aqui: a foto dos bonecos de pebolim tinha um nome de
#: 85 caracteres e, com "-sem-fundo.png", passava de 100 -- no PostgreSQL
#: isso aborta a transação; o SQLite dos testes não confere o tamanho.)
LIMITE_DO_NOME = 100
BASE_MAXIMA = 48


def _nome_do_recorte(nome):
    import os

    base = os.path.splitext(os.path.basename(nome or "peca"))[0][:BASE_MAXIMA] or "peca"
    return f"pecas_reposicao/{base}{MARCA_DO_RECORTE}.png"


def precisa_conferir(foto):
    return bool(foto.imagem) and foto.imagem.name != (foto.recorte_de or "")


def processar(foto, avisar=None):
    """Confere uma foto de peça: "recortada", "sem_recorte" (fica como está) ou "ja_conferida".

    Erro de rede ou do Cloudinary sobe (quem chama decide: o sinal registra no
    log, a migração avisa e segue).
    """
    from django.core.files.base import ContentFile

    if not precisa_conferir(foto):
        return "ja_conferida"
    Modelo = type(foto)
    atual = foto.imagem.name
    png = recortar(baixar(foto.imagem))
    if png is None:
        Modelo.objects.filter(pk=foto.pk).update(recorte_de=atual)
        foto.recorte_de = atual
        if avisar:
            avisar(f"  foto {foto.pk}: não é de fundo branco, fica como está")
        return "sem_recorte"
    novo = foto.imagem.storage.save(_nome_do_recorte(atual), ContentFile(png))
    limite = getattr(Modelo._meta.get_field("imagem"), "max_length", None) or LIMITE_DO_NOME
    if len(novo) > limite or len(atual) > limite:
        raise ValueError(f"nome do arquivo com mais de {limite} caracteres: {novo!r}")
    Modelo.objects.filter(pk=foto.pk).update(imagem=novo, imagem_original=atual, recorte_de=novo)
    foto.imagem.name, foto.recorte_de = novo, novo
    foto.imagem_original.name = atual
    if avisar:
        avisar(f"  foto {foto.pk}: fundo branco tirado ({novo})")
    return "recortada"


def desfazer(foto):
    """A foto que a equipe subiu volta para o site. Devolve True se havia recorte."""
    if not foto.imagem_original:
        return False
    Modelo = type(foto)
    original = foto.imagem_original.name
    Modelo.objects.filter(pk=foto.pk).update(imagem=original, imagem_original=None, recorte_de=original)
    foto.imagem.name, foto.recorte_de = original, original
    foto.imagem_original.name = None
    return True


def processar_todas(ImagemPeca, avisar=print, so=None):
    """Confere as fotos ainda não conferidas. Uma foto que falha não para as outras."""
    resumo = {"recortada": 0, "sem_recorte": 0, "ja_conferida": 0, "falhou": 0}
    fotos = ImagemPeca.objects.exclude(imagem="").exclude(imagem__isnull=True).order_by("pk")
    if so:
        fotos = fotos.filter(peca_reposicao_id__in=so)
    from django.db import transaction

    for foto in list(fotos):
        try:
            # cada foto no seu ponto de salvamento: um erro de banco numa
            # foto (no PostgreSQL ele aborta a transação inteira da migração)
            # desfaz só ela, e as outras seguem
            with transaction.atomic():
                resumo[processar(foto, avisar=avisar)] += 1
        except Exception as erro:  # noqa: BLE001 -- uma foto ruim não para as outras
            resumo["falhou"] += 1
            if avisar:
                avisar(f"  foto {foto.pk}: não deu agora ({erro!r}); rode de novo depois")
    return resumo


def processar_em_segundo_plano(pk):
    """Depois de a equipe subir a foto no painel: recorta sem prender a tela."""
    import logging
    import threading

    from django.db import close_old_connections

    def _rodar():
        try:
            from .models import ImagemPeca

            foto = ImagemPeca.objects.filter(pk=pk).first()
            if foto is not None:
                processar(foto)
                _limpar_cache()
        except Exception:  # noqa: BLE001 -- a foto fica como subiu; o comando refaz
            logging.getLogger(__name__).exception("Recorte da foto de peça %s falhou.", pk)
        finally:
            close_old_connections()

    threading.Thread(target=_rodar, name=f"recorte-peca-{pk}", daemon=True).start()


def _limpar_cache():
    try:
        from .context_processors import limpar_cache_global
        limpar_cache_global()
    except Exception:  # noqa: BLE001
        pass
    try:
        from django.core.cache import cache
        cache.clear()
    except Exception:  # noqa: BLE001
        pass
