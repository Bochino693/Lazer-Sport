"""As capas em cena dos produtos do catálogo (a seção 64 do LEIA-ME).

O cliente, sobre os cards com a foto da máquina no fundo branco (e o Pega
Toupeira cortado, com zoom): "você deve criar o fundo para todos que tem fundo
branco, tirando sempre o zoom e mostrando todo o brinquedo, com fundos
originais, com vida e com os estabelecimentos coerentes, não com cara muito de
IA, parecendo mais bonito e vivo, é para vender!!!". E: "faça padrão para todas
as imagens 2D" -- o padrão é o SHOWROOM DA LAZER & SPORT, o da foto de verdade
do Boliche Virtual no catálogo.

Para cada produto de LISTA (os do site no ar cuja capa é a máquina no fundo
branco ou transparente), a ferramenta (ferramentas/categorias: as cenas
"produto:<chave>") fez a foto da máquina no showroom, QUADRADA (1600 x 1600, o
formato do card) e com a máquina inteira: está em
core/static/site/capas_catalogo/<chave>.webp.

O CADASTRO DESSES PRODUTOS É DO PAINEL (as fotos são da equipe), então a troca
é reversível:
  * `aplicar`: a foto em cena sobe e vira a CAPA (a foto "perfil" da galeria,
    a primeira, e o `imagem_brinquedo`), marcada `papel_na_capa = "cena"`; a
    capa de antes continua na galeria, logo depois, sem tipo e marcada
    `papel_na_capa = "original"` (a galeria pública a mostra);
  * `desfazer`: a cena sai e a original volta a ser a capa;
  * só toca no produto cuja capa ainda é a foto da lista (o public id do
    Cloudinary em LISTA): se a equipe já trocou a foto no painel, não mexe. Um
    produto já em cena ganha a foto nova só se ela mudou (a assinatura no nome).
Recebe os modelos para servir à migração (modelos históricos) e ao comando.

    python manage.py capas_em_cena --simular
    python manage.py capas_em_cena [--so 13 "Pega Toupeira"]
    python manage.py capas_em_cena --desfazer [--so 13]

AS MÁQUINAS DA BLACK FRIDAY (VERMELHAS; a seção 78 do LEIA-ME). O cliente, com
o print do card do Basquete Kids: "veja que o fundo não ficou uniforme com o
que preciso, de paisagens e tal ... identifique as máquinas com o fundo
vermelho e ponha elas no padrão"; e, com o do Air Rock (a foto panorâmica
cortada no card quadrado): "valide para não ter fotos assim com zoom pois
estraga". Os produtos que a Black Friday criou (core/black_friday.py) tinham a
capa recortada do PRÓPRIO CARTAZ: a máquina no neon vermelho escuro ou a foto
panorâmica. Cada um ganha a foto da máquina inteira no showroom, quadrada,
como as de cima (a máquina tirada do fundo: ferramentas/categorias/
recortar_vermelho.py). A troca é a mesma, com UMA diferença: a capa de antes
(o recorte do cartaz) NÃO fica na galeria pública. Ela continua cadastrada
(nada é apagado: o --desfazer a põe de volta), mas sem tipo e sem papel, e a
galeria pública (`galeria_publica`: as fotos com tipo e a "original"), o card,
as fotos que giram (core/fotos_dos_cards.py), o quadro do topo
(`imagem_brinquedo`) e a API (a capa) não a mostram. Sem campo novo e sem
escolha nova no `papel_na_capa` (o modelo das fotos é de outro trabalho em
andamento): o --desfazer acha a foto de antes pelo nome do arquivo, que a
Black Friday deu (`black-friday-2026-produto-<chave>-<assinatura>`).
A categoria nova "Casinhas Cenográficas" (a foto era o recorte das três
casinhas no mesmo neon) ganha a foto de categoria num lugar de verdade, com as
crianças (a seção 64, item 3): a brinquedoteca, em
core/static/site/categorias/casinhas-cenograficas.webp.

    python manage.py capas_em_cena --vermelhas --simular
    python manage.py capas_em_cena --vermelhas            (os 7 produtos e a categoria)
    python manage.py capas_em_cena --so "Basquete Kids"
    python manage.py capas_em_cena --vermelhas --desfazer (o recorte do cartaz volta)
"""

import hashlib
import unicodedata
from pathlib import Path

from django.core.files import File
from django.db import transaction

PASTA = Path(__file__).resolve().parent / "static" / "site" / "capas_catalogo"

#: (a chave da foto, o id no site, o nome, o public id da capa de antes no Cloudinary)
LISTA = (
    ("air-game-premium", 1, "Air Game Premium", "imagens_brinquedos/Mesas_de_air_hockey_futuristas_com_LEDs_hr1x4m"),
    ("air-game-home", 2, "Air Game Home", "imagens_brinquedos/airhokey_lpyk86"),
    ("basquete-home", 3, "Basquete Home", "imagens_brinquedos/basquetehome_s1antg"),
    ("mundo-zumbi", 4, "Mundo Zumbi", "imagens_brinquedos/Mundo_Zumbi_cj4fhq"),
    ("porsche-simulador", 5, "Porsche Simulador", "imagens_brinquedos/Simulador_Porche_yrfemm"),
    ("simulador-mario-kart", 6, "Simulador Mario Kart", "imagens_brinquedos/Simulador_Mario_qqjqno"),
    ("pac-man", 7, "Pac Man", "imagens_brinquedos/Pac_Man_c3lp48"),
    ("basquete-street", 8, "Basquete Street", "imagens_brinquedos/Basquete_Street_kclh4g"),
    ("show-de-bola", 9, "Show de Bola", "imagens_brinquedos/Show_de_Bola_rto0vx"),
    ("homem-aranha-kids", 10, "Homem Aranha Kids", "imagens_brinquedos/Homem_Aranha_Kids_tj2kf5"),
    ("tomb-raider-kids", 11, "Tomb Raider Kids", "imagens_brinquedos/Tomb_Raider_Kids_fmvljf"),
    ("corrida-dos-minions", 12, "Corrida dos Minions", "imagens_brinquedos/Minions_egblw6"),
    ("pega-toupeira", 13, "Pega Toupeira", "imagens_brinquedos/pegatop_byx7nr"),
    ("matrix", 14, "Matrix", "imagens_brinquedos/Matrix_zze6sm"),
    ("multi-jogos-retro", 15, "Multi Jogos Retro", "imagens_brinquedos/Multi_Jogos_Retro_nmbwkp"),
    ("multi-jogos", 16, "Multi Jogos", "imagens_brinquedos/Multi_jogos_Mesa_foocks"),
    ("gabinete-games", 17, "Gabinete Games", "imagens_brinquedos/Gabinete_Games_pcz92j"),
    ("pinball-32", 18, "Pinball 32 Polegadas", "imagens_brinquedos/Pimbal_32_Polegadas_zymhyo"),
    ("pinball-40", 19, "Pinball 40 Polegadas", "imagens_brinquedos/Pimbal_40_polegadas_ezjlz8"),
    ("pebolim-eletronico", 20, "Pebolim Eletrônico", "imagens_brinquedos/pebolim-eletro_am7cub"),
    ("homem-aranha", 21, "Homem Aranha", "imagens_brinquedos/Homem_Aranha_Grande_l7xqsq"),
    ("sonic-dash", 22, "Sonic Dash", "imagens_brinquedos/Sonic_Grande_mvfjbo"),
    ("subway-surfers", 23, "Subway Surfers", "imagens_brinquedos/Subway_Surfers_hbuebk"),
    ("flappy-bird", 24, "Flappy Bird", "imagens_brinquedos/Flapyy_Bird_GRande_r13wlt"),
    ("speed-turbo", 25, "Speed Turbo", "imagens_brinquedos/Speed_Turbo_ojcxu0"),
    ("pantera-kids", 26, "Pantera Cor de Rosa Kids", "imagens_brinquedos/Pantera_Kids_rxjhod"),
    ("sonic-kids", 27, "Sonic Kids", "imagens_brinquedos/Sonic_Kids_pceewo"),
    ("minions-kids", 28, "Minions Kids", "imagens_brinquedos/Minions_Kids_wh35t1"),
    ("labamba", 29, "Labamba", "imagens_brinquedos/Labamba_idv3wd"),
    ("carrossel-sorvetinho", 30, "Carrossel Sorvetinho", "imagens_brinquedos/Carrosel_ra9ann"),
    ("mini-roda-sorvete", 31, "Mini Roda Sorvete", "imagens_brinquedos/Mini_Roda_Gigante_jxmj3r"),
    ("nervo-teste", 32, "Nervo Teste", "imagens_brinquedos/Nervo_Teste_pcgql3"),
    ("brinquedao-modelo-1", 33, "Brinquedão Modelo 1", "imagens_brinquedos/Imagem1-Photoroom_qfd8iy"),
    ("lazer-shot", 35, "Lazer Shot", "imagens_brinquedos/LAZER-SHOT_cautcu"),
    ("matrix-one-piece", 36, "Matrix One Piece", "imagens_brinquedos/matrix_oqoacy"),
    ("sonic-racing", 37, "Sonic Racing All-Stars", "imagens_brinquedos/SONIC_k6bpj7"),
    ("top-racer", 38, "Simulador de Corrida Top Racer",
     "imagens_brinquedos/ChatGPT_Image_24_de_jul._de_2026__15_31_31-removebg-preview_t3qcnh"),
    ("bob-esponja-kids", 39, "Bob Esponja Hammer Kids",
     "imagens_brinquedos/WhatsApp_Image_2026-07-24_at_16.01.53-removebg-preview_mdy0ek"),
    ("air-game-kids", 40, "Air Game Kids",
     "imagens_brinquedos/WhatsApp_Image_2026-07-24_at_16.10.57-removebg-preview_hcfnmt"),
)

#: Os que ficam de fora, e por quê (o LEIA-ME e os testes conferem).
FORA = {
    "Boliche Virtual": "a capa já é uma foto de verdade, no showroom (é a referência)",
    "Brinquedão Modelo 2": "a capa é a cena dos nossos 3D (core/cadastro_modelos.py)",
    "Brinquedão Modelo 3": "a capa é a cena dos nossos 3D (core/cadastro_modelos.py)",
    "Brinquedão Ninja": "a capa é a cena dos nossos 3D (core/cadastro_modelos.py)",
    "Espaço Esportivo Modelo 1": "a capa é a cena dos nossos 3D (core/cadastro_modelos.py)",
    "Trampolim de Enterrada": "a capa é a cena dos nossos 3D (core/cadastro_modelos.py)",
    "Strike Kids": "a capa é a cena dos nossos 3D (core/cadastro_modelos.py)",
    "Air Game Kids Alienígenas": "a capa é a cena dos nossos 3D (core/cadastro_modelos.py)",
    "Basquete Home Quadrinhos": "a capa é a cena dos nossos 3D (core/cadastro_modelos.py)",
    "Brinquedão Modelo 4": "a capa é a imagem da fábrica (a perspectiva)",
    "Brinquedão Modelo 5": "a capa é a imagem da fábrica (o salão)",
}

#: As máquinas da Black Friday (a seção 78): a capa era o recorte do cartaz, no fundo de neon vermelho
#: (Basquete Duplo, Basquete Kids e as três casinhas) ou a foto panorâmica que o card quadrado cortava
#: (Air Rock e Kid Play). (a chave da foto, o id no site, o nome, o começo do nome do arquivo da capa de
#: antes -- o que core/black_friday.py subiu: "black-friday-2026-produto-<chave>-<assinatura>")
VERMELHAS = (
    ("basquete-duplo", 58, "Basquete Duplo", "black-friday-2026-produto-basquete-duplo-"),
    ("basquete-kids", 59, "Basquete Kids", "black-friday-2026-produto-basquete-kids-"),
    ("air-rock", 60, "Air Rock", "black-friday-2026-produto-air-rock-"),
    ("kid-play", 61, "Kid Play", "black-friday-2026-produto-kid-play-"),
    ("cozinha-infantil", 62, "Cozinha Infantil", "black-friday-2026-produto-cozinha-infantil-"),
    ("oficina-de-engenharia", 63, "Oficina de Engenharia", "black-friday-2026-produto-oficina-de-engenharia-"),
    ("salao-de-beleza", 64, "Salão de Beleza", "black-friday-2026-produto-salao-de-beleza-"),
)
_CHAVES_VERMELHAS = {item[0] for item in VERMELHAS}

#: A categoria nova da Black Friday: o nome, a chave da foto (core/static/site/categorias/) e o começo do
#: nome do arquivo da foto de antes (o recorte das três casinhas no neon, que core/black_friday.py subiu).
CATEGORIA_CASINHAS = ("Casinhas Cenográficas", "casinhas-cenograficas", "categoria-produto-casinhas-cenograficas-")
#: A foto de antes da categoria, no repositório (o --desfazer a sobe de novo, com o nome de antes).
FOTO_DE_ANTES_DA_CATEGORIA = Path(__file__).resolve().parent / "static" / "site" / "black_friday" / "produto-casinhas-cenograficas.webp"

PERFIL = "perfil"
CENA = "cena"
ORIGINAL = "original"


def _normalizar(texto):
    texto = unicodedata.normalize("NFD", (texto or "").lower())
    return " ".join("".join(c for c in texto if unicodedata.category(c) != "Mn").split())


def arquivo(chave):
    return PASTA / f"{chave}.webp"


def assinatura(chave):
    return hashlib.sha1(arquivo(chave).read_bytes()).hexdigest()[:10]


def nome_no_cadastro(chave):
    """O nome do arquivo que sobe: a chave e a assinatura (a foto que mudou sobe de novo)."""
    return f"cena-{chave}-{assinatura(chave)}.webp"


def mesma_foto(nome, public_id):
    """O arquivo `nome` (do campo de imagem) é a foto `public_id` do Cloudinary?"""
    if not nome:
        return False
    sem_extensao = str(Path(nome).with_suffix("")) if Path(nome).suffix.lower() in (".jpg", ".jpeg", ".png", ".webp") else nome
    return sem_extensao == public_id or sem_extensao.endswith("/" + public_id) or sem_extensao.endswith(public_id)


def escolher(so=(), lista=None):
    """Os itens pedidos (`so`: ids, nomes ou chaves; vazio, todos de `lista`, que por padrão é LISTA).

    Com `so`, procura nas duas listas (LISTA e VERMELHAS), a não ser que `lista` diga qual.
    """
    if not so:
        return list(LISTA if lista is None else lista)
    pedidos = {_normalizar(str(s)) for s in so}
    onde = (LISTA + VERMELHAS) if lista is None else lista
    return [item for item in onde if str(item[1]) in pedidos or _normalizar(item[2]) in pedidos or item[0] in pedidos]


def vermelha(item):
    """O item é uma máquina da Black Friday (a capa de antes sai da galeria pública)?"""
    return item[0] in _CHAVES_VERMELHAS


def do_cartaz(nome, prefixo):
    """O arquivo `nome` é o recorte do cartaz da Black Friday (`prefixo`: o começo do nome dele)?"""
    return bool(nome) and Path(nome).name.startswith(prefixo)


def achar(nome, Brinquedos):
    """O brinquedo do catálogo com este nome (o ativo primeiro)."""
    alvo = _normalizar(nome)
    achados = [b for b in Brinquedos.objects.order_by("-ativo", "id") if _normalizar(b.nome_brinquedo) == alvo]
    return achados[0] if achados else None


def _perfil(brinquedo, ImagemBrinquedo):
    return ImagemBrinquedo.objects.filter(brinquedo=brinquedo, tipo=PERFIL).order_by("ordem", "id").first()


def aplicar_um(item, Brinquedos, ImagemBrinquedo, simular=False):
    """Põe a capa em cena num produto. Devolve o que fez (uma frase).

    Nas VERMELHAS, a capa de antes (o recorte do cartaz) fica cadastrada, mas fora da galeria pública.
    """
    if vermelha(item):
        return _aplicar_vermelha(item, Brinquedos, ImagemBrinquedo, simular=simular)
    chave, _id, nome, public_id = item
    brinquedo = achar(nome, Brinquedos)
    if brinquedo is None:
        return f"{nome}: não está no catálogo."
    perfil = _perfil(brinquedo, ImagemBrinquedo)
    capa = (perfil.imagem.name if perfil and perfil.imagem else "") or (brinquedo.imagem_brinquedo.name or "")
    if perfil is not None and perfil.papel_na_capa == CENA:
        return _renovar_cena(brinquedo, perfil, chave, nome, capa, simular)
    if not mesma_foto(capa, public_id):
        return f"{nome}: a capa foi trocada no painel ({capa or 'sem foto'}); fica como está."
    if simular:
        return f"{nome}: poria a capa em cena (a de antes fica na galeria)."
    novo = nome_no_cadastro(chave)
    with transaction.atomic():
        fotos = list(ImagemBrinquedo.objects.filter(brinquedo=brinquedo).order_by("ordem", "id"))
        for foto in fotos:
            foto.ordem = foto.ordem + 2
            foto.save(update_fields=["ordem"])
        if perfil is not None:
            perfil.tipo = None
            perfil.ordem = 2
            perfil.papel_na_capa = ORIGINAL
            perfil.save(update_fields=["tipo", "ordem", "papel_na_capa"])
        else:
            ImagemBrinquedo.objects.create(
                brinquedo=brinquedo, tipo=None, ordem=2, imagem=brinquedo.imagem_brinquedo.name,
                papel_na_capa=ORIGINAL, texto_alternativo=f"{brinquedo.nome_brinquedo}: a foto do produto"[:180],
            )
        cena = ImagemBrinquedo(
            brinquedo=brinquedo, tipo=PERFIL, ordem=1, papel_na_capa=CENA,
            texto_alternativo=f"{brinquedo.nome_brinquedo} no showroom da Lazer & Sport"[:180],
        )
        with open(arquivo(chave), "rb") as origem:
            cena.imagem.save(novo, File(origem), save=True)
        brinquedo.imagem_brinquedo = cena.imagem.name
        brinquedo.save(update_fields=["imagem_brinquedo"])
    return f"{nome}: a capa agora é a cena (a de antes continua na galeria)."


def _renovar_cena(brinquedo, perfil, chave, nome, capa, simular):
    """O produto já está com a capa em cena: sobe a foto de hoje só se ela mudou (a assinatura no nome)."""
    novo = nome_no_cadastro(chave)
    if Path(novo).stem in capa:
        return f"{nome}: já está com a capa em cena."
    if simular:
        return f"{nome}: trocaria a capa em cena pela de hoje."
    with transaction.atomic():
        with open(arquivo(chave), "rb") as origem:
            perfil.imagem.save(novo, File(origem), save=True)
        brinquedo.imagem_brinquedo = perfil.imagem.name
        brinquedo.save(update_fields=["imagem_brinquedo"])
    return f"{nome}: a capa em cena foi trocada pela de hoje."


def _cena_nova(brinquedo, chave, ImagemBrinquedo):
    """A foto em cena sobe e vira a capa (a "perfil", a primeira, e o `imagem_brinquedo`)."""
    cena = ImagemBrinquedo(
        brinquedo=brinquedo, tipo=PERFIL, ordem=1, papel_na_capa=CENA,
        texto_alternativo=f"{brinquedo.nome_brinquedo} no showroom da Lazer & Sport"[:180],
    )
    with open(arquivo(chave), "rb") as origem:
        cena.imagem.save(nome_no_cadastro(chave), File(origem), save=True)
    brinquedo.imagem_brinquedo = cena.imagem.name
    brinquedo.save(update_fields=["imagem_brinquedo"])
    return cena


def _aplicar_vermelha(item, Brinquedos, ImagemBrinquedo, simular=False):
    """A máquina da Black Friday: a cena vira a capa e o recorte do cartaz sai da galeria pública.

    O recorte do cartaz continua cadastrado (sem tipo e sem papel: a galeria pública só mostra as
    fotos com tipo e a "original"), no fim da galeria, para o --desfazer. Só mexe no produto cuja
    capa ainda é o recorte do cartaz (o começo do nome do arquivo): a capa trocada no painel fica.
    """
    chave, _id, nome, prefixo = item
    brinquedo = achar(nome, Brinquedos)
    if brinquedo is None:
        return f"{nome}: não está no catálogo."
    perfil = _perfil(brinquedo, ImagemBrinquedo)
    capa = (perfil.imagem.name if perfil and perfil.imagem else "") or (brinquedo.imagem_brinquedo.name or "")
    if perfil is not None and perfil.papel_na_capa == CENA:
        return _renovar_cena(brinquedo, perfil, chave, nome, capa, simular)
    if not do_cartaz(capa, prefixo):
        return f"{nome}: a capa foi trocada no painel ({capa or 'sem foto'}); fica como está."
    if simular:
        return f"{nome}: poria a capa em cena (o recorte do cartaz sai da galeria pública e fica guardado)."
    with transaction.atomic():
        fotos = list(ImagemBrinquedo.objects.filter(brinquedo=brinquedo).order_by("ordem", "id"))
        for foto in fotos:
            foto.ordem = foto.ordem + 1
            foto.save(update_fields=["ordem"])
        # o recorte do cartaz: no fim, sem tipo e sem papel (fora da galeria pública), guardado
        ultimo = max([foto.ordem for foto in fotos], default=1) + 1
        if perfil is not None:
            perfil.tipo = None
            perfil.ordem = ultimo
            perfil.papel_na_capa = ""
            perfil.save(update_fields=["tipo", "ordem", "papel_na_capa"])
        elif not any(foto.imagem.name == brinquedo.imagem_brinquedo.name for foto in fotos):
            ImagemBrinquedo.objects.create(
                brinquedo=brinquedo, tipo=None, ordem=ultimo, imagem=brinquedo.imagem_brinquedo.name,
                papel_na_capa="", texto_alternativo=f"{brinquedo.nome_brinquedo}: o recorte do cartaz"[:180],
            )
        _cena_nova(brinquedo, chave, ImagemBrinquedo)
    return f"{nome}: a capa agora é a cena no showroom (o recorte do cartaz saiu da galeria pública e fica guardado)."


def _desfazer_vermelha(item, Brinquedos, ImagemBrinquedo, simular=False):
    """Volta o recorte do cartaz como capa (a cena sai). Sem ele guardado, não mexe."""
    _chave, _id, nome, prefixo = item
    brinquedo = achar(nome, Brinquedos)
    if brinquedo is None:
        return f"{nome}: não está no catálogo."
    cenas = list(ImagemBrinquedo.objects.filter(brinquedo=brinquedo, papel_na_capa=CENA))
    antes = next(
        (foto for foto in ImagemBrinquedo.objects.filter(brinquedo=brinquedo, tipo__isnull=True).order_by("ordem", "id")
         if do_cartaz(foto.imagem.name, prefixo)),
        None,
    )
    if not cenas:
        return f"{nome}: não está com a capa em cena."
    if antes is None:
        # (o produto que já nasceu com a cena, numa Black Friday rodada depois desta versão)
        return f"{nome}: não há o recorte do cartaz guardado para voltar; fica com a capa em cena."
    if simular:
        return f"{nome}: voltaria o recorte do cartaz como capa."
    with transaction.atomic():
        for cena in cenas:
            cena.delete()
        outro_perfil = ImagemBrinquedo.objects.filter(brinquedo=brinquedo, tipo=PERFIL).exists()
        antes.tipo = None if outro_perfil else PERFIL
        antes.ordem = 1
        antes.save(update_fields=["tipo", "ordem"])
        brinquedo.imagem_brinquedo = antes.imagem.name
        brinquedo.save(update_fields=["imagem_brinquedo"])
    return f"{nome}: o recorte do cartaz voltou a ser a capa."


def _categoria(CategoriasBrinquedos):
    alvo = _normalizar(CATEGORIA_CASINHAS[0])
    return next((c for c in CategoriasBrinquedos.objects.order_by("id") if _normalizar(c.nome_categoria) == alvo), None)


def aplicar_categoria(CategoriasBrinquedos, simular=False):
    """A foto da categoria "Casinhas Cenográficas": as três casinhas na brinquedoteca, com as crianças.

    Só troca a foto de antes (o recorte do cartaz) ou uma versão anterior desta; a foto que a equipe
    pôs no painel fica. Rodar de novo não sobe de novo (a assinatura no nome).
    """
    from .categorias_capas import arquivo_da_capa, nome_no_cadastro as nome_da_categoria

    nome, chave, prefixo = CATEGORIA_CASINHAS
    categoria = _categoria(CategoriasBrinquedos)
    if categoria is None:
        return f"{nome} (categoria): não existe."
    atual = categoria.imagem_categoria.name or ""
    novo = nome_da_categoria(chave)
    if novo in atual:
        return f"{nome} (categoria): já está com a foto na brinquedoteca."
    if atual and not do_cartaz(atual, prefixo) and not Path(atual).name.startswith(f"{chave}-"):
        return f"{nome} (categoria): a foto foi trocada no painel ({atual}); fica como está."
    if simular:
        return f"{nome} (categoria): poria a foto na brinquedoteca (com as crianças)."
    with transaction.atomic(), open(arquivo_da_capa(chave), "rb") as origem:
        categoria.imagem_categoria.save(f"{novo}.webp", File(origem), save=False)
        categoria.save(update_fields=["imagem_categoria"])
    return f"{nome} (categoria): a foto agora é a das casinhas na brinquedoteca."


def desfazer_categoria(CategoriasBrinquedos, simular=False):
    """Volta a foto de antes da categoria (o recorte do cartaz, que está no repositório)."""
    nome, chave, prefixo = CATEGORIA_CASINHAS
    categoria = _categoria(CategoriasBrinquedos)
    if categoria is None:
        return f"{nome} (categoria): não existe."
    if not Path(categoria.imagem_categoria.name or "").name.startswith(f"{chave}-"):
        return f"{nome} (categoria): não está com a foto na brinquedoteca."
    if simular:
        return f"{nome} (categoria): voltaria a foto de antes (o recorte do cartaz)."
    assinatura_de_antes = hashlib.sha1(FOTO_DE_ANTES_DA_CATEGORIA.read_bytes()).hexdigest()[:8]
    with transaction.atomic(), open(FOTO_DE_ANTES_DA_CATEGORIA, "rb") as origem:
        categoria.imagem_categoria.save(f"{prefixo}{assinatura_de_antes}.webp", File(origem), save=False)
        categoria.save(update_fields=["imagem_categoria"])
    return f"{nome} (categoria): a foto de antes voltou."


def desfazer_um(item, Brinquedos, ImagemBrinquedo, simular=False):
    """Volta a capa de antes. Devolve o que fez (uma frase)."""
    if vermelha(item):
        return _desfazer_vermelha(item, Brinquedos, ImagemBrinquedo, simular=simular)
    _chave, _id, nome, _public_id = item
    brinquedo = achar(nome, Brinquedos)
    if brinquedo is None:
        return f"{nome}: não está no catálogo."
    cenas = list(ImagemBrinquedo.objects.filter(brinquedo=brinquedo, papel_na_capa=CENA))
    original = ImagemBrinquedo.objects.filter(brinquedo=brinquedo, papel_na_capa=ORIGINAL).order_by("ordem", "id").first()
    if not cenas and original is None:
        return f"{nome}: não está com a capa em cena."
    if simular:
        return f"{nome}: voltaria a capa de antes."
    with transaction.atomic():
        for cena in cenas:
            cena.delete()
        if original is not None:
            outro_perfil = ImagemBrinquedo.objects.filter(brinquedo=brinquedo, tipo=PERFIL).exists()
            original.tipo = None if outro_perfil else PERFIL
            original.papel_na_capa = ""
            original.ordem = 1
            original.save(update_fields=["tipo", "papel_na_capa", "ordem"])
            brinquedo.imagem_brinquedo = original.imagem.name
            brinquedo.save(update_fields=["imagem_brinquedo"])
    return f"{nome}: a capa de antes voltou."


def rodar(Brinquedos, ImagemBrinquedo, so=(), simular=False, desfazer=False, avisar=print, lista=None,
          CategoriasBrinquedos=None):
    """Aplica (ou desfaz) em cada item pedido; um erro num produto não para os outros. Devolve {nome: frase}.

    `lista`: LISTA (o padrão) ou VERMELHAS; com `CategoriasBrinquedos`, também a foto da categoria
    "Casinhas Cenográficas" (a das VERMELHAS).
    """
    feito = {}
    for item in escolher(so, lista):
        try:
            frase = (desfazer_um if desfazer else aplicar_um)(item, Brinquedos, ImagemBrinquedo, simular=simular)
        except Exception as erro:  # a subida de um falhou: segue com os outros e avisa o comando
            frase = (f"{item[2]}: não foi feito agora ({erro!r}). "
                     f"Rode: python manage.py capas_em_cena --so {item[1]}")
        feito[item[2]] = frase
        avisar(frase)
    if CategoriasBrinquedos is not None:
        try:
            frase = (desfazer_categoria if desfazer else aplicar_categoria)(CategoriasBrinquedos, simular=simular)
        except Exception as erro:  # a subida falhou: avisa o comando
            frase = (f"{CATEGORIA_CASINHAS[0]} (categoria): não foi feito agora ({erro!r}). "
                     "Rode: python manage.py capas_em_cena --vermelhas")
        feito[f"{CATEGORIA_CASINHAS[0]} (categoria)"] = frase
        avisar(frase)
    return feito


def subir_no_deploy(apps, schema_editor, avisar=print):
    """A migração (a 0157): só no Render (o Cloudinary só está lá); se algo falhar, o deploy segue."""
    from django.conf import settings

    if not getattr(settings, "IS_RENDER", False):
        return None
    try:
        return rodar(apps.get_model("core", "Brinquedos"), apps.get_model("core", "ImagemBrinquedo"), avisar=avisar)
    except Exception as erro:  # o deploy segue; o comando refaz depois
        avisar(f"As capas em cena do catálogo não subiram agora ({erro!r}). Rode: python manage.py capas_em_cena")
        return None


def vermelhas_no_deploy(apps, schema_editor, avisar=print):
    """A migração 0180: as máquinas da Black Friday no showroom e a foto da categoria das casinhas.

    Só no Render (o Cloudinary só está lá). Rodar de novo não muda nada; o que a equipe já trocou no
    painel fica; se uma subida falhar, o deploy segue e o aviso diz o comando.
    """
    from django.conf import settings

    if not getattr(settings, "IS_RENDER", False):
        return None
    try:
        feito = rodar(
            apps.get_model("core", "Brinquedos"), apps.get_model("core", "ImagemBrinquedo"), lista=VERMELHAS,
            CategoriasBrinquedos=apps.get_model("core", "CategoriasBrinquedos"), avisar=avisar,
        )
    except Exception as erro:  # o deploy segue; o comando refaz depois
        avisar(f"As máquinas da Black Friday não foram para o showroom agora ({erro!r}). "
               "Rode: python manage.py capas_em_cena --vermelhas")
        return None
    try:  # os cards (as fotos que giram) e a home guardados em cache passam a mostrar a cena
        from django.core.cache import cache

        cache.clear()
    except Exception:  # noqa: BLE001
        pass
    return feito
