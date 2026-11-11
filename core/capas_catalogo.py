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
    "Basquete Street Quadrinhos": "a capa é a cena dos nossos 3D (core/cadastro_modelos.py)",
    "Brinquedão Modelo 4": "a capa é a imagem da fábrica (a perspectiva)",
    "Brinquedão Modelo 5": "a capa é a imagem da fábrica (o salão)",
}

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


def escolher(so=()):
    """Os itens de LISTA pedidos (`so`: ids ou nomes; vazio, todos)."""
    if not so:
        return list(LISTA)
    pedidos = {_normalizar(str(s)) for s in so}
    return [item for item in LISTA if str(item[1]) in pedidos or _normalizar(item[2]) in pedidos or item[0] in pedidos]


def achar(nome, Brinquedos):
    """O brinquedo do catálogo com este nome (o ativo primeiro)."""
    alvo = _normalizar(nome)
    achados = [b for b in Brinquedos.objects.order_by("-ativo", "id") if _normalizar(b.nome_brinquedo) == alvo]
    return achados[0] if achados else None


def _perfil(brinquedo, ImagemBrinquedo):
    return ImagemBrinquedo.objects.filter(brinquedo=brinquedo, tipo=PERFIL).order_by("ordem", "id").first()


def aplicar_um(item, Brinquedos, ImagemBrinquedo, simular=False):
    """Põe a capa em cena num produto. Devolve o que fez (uma frase)."""
    chave, _id, nome, public_id = item
    brinquedo = achar(nome, Brinquedos)
    if brinquedo is None:
        return f"{nome}: não está no catálogo."
    perfil = _perfil(brinquedo, ImagemBrinquedo)
    capa = (perfil.imagem.name if perfil and perfil.imagem else "") or (brinquedo.imagem_brinquedo.name or "")
    if perfil is not None and perfil.papel_na_capa == CENA:
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


def desfazer_um(item, Brinquedos, ImagemBrinquedo, simular=False):
    """Volta a capa de antes. Devolve o que fez (uma frase)."""
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


def rodar(Brinquedos, ImagemBrinquedo, so=(), simular=False, desfazer=False, avisar=print):
    """Aplica (ou desfaz) em cada item pedido; um erro num produto não para os outros. Devolve {nome: frase}."""
    feito = {}
    for item in escolher(so):
        try:
            frase = (desfazer_um if desfazer else aplicar_um)(item, Brinquedos, ImagemBrinquedo, simular=simular)
        except Exception as erro:  # a subida de um falhou: segue com os outros e avisa o comando
            frase = (f"{item[2]}: não foi feito agora ({erro!r}). "
                     f"Rode: python manage.py capas_em_cena --so {item[1]}")
        feito[item[2]] = frase
        avisar(frase)
    return feito


def subir_no_deploy(apps, schema_editor, avisar=print):
    """A migração (a 0156): só no Render (o Cloudinary só está lá); se algo falhar, o deploy segue."""
    from django.conf import settings

    if not getattr(settings, "IS_RENDER", False):
        return None
    try:
        return rodar(apps.get_model("core", "Brinquedos"), apps.get_model("core", "ImagemBrinquedo"), avisar=avisar)
    except Exception as erro:  # o deploy segue; o comando refaz depois
        avisar(f"As capas em cena do catálogo não subiram agora ({erro!r}). Rode: python manage.py capas_em_cena")
        return None
