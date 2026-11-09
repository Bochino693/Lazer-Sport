"""Cadastro dos brinquedos que já chegam com o objeto 3D feito aqui.

  * BRINQUEDÃO MODELO 2: o .3ds da fábrica e as imagens do projeto
    (ver `ferramentas/modelos3d/brinquedao-modelo-2/`);
  * BRINQUEDÃO NINJA: o brinquedão de dois andares com as duas camas
    elásticas, UM objeto só (o .3ds da fábrica traz os dois juntos); as
    fotos são a imagem do projeto e a planta (ver
    `ferramentas/modelos3d/brinquedao-ninja/`);
  * BRINQUEDÃO MODELO 4: dois trechos em "Z" (12 m + 9 m); a estrutura do
    .3ds da fábrica, o resto e as fotos das imagens do projeto (ver
    `ferramentas/modelos3d/brinquedao-modelo-4/`);
  * ESPAÇO ESPORTIVO MODELO 1: o trampo.3ds do parque de trampolins, as
    plantas do parque e das quadras e as imagens do espaço completo (ver
    `ferramentas/modelos3d/espaco-esportivo-modelo-1/`). As fotos dele são
    vistas do próprio objeto 3D, com o fundo claro do catálogo.
  * STRIKE KIDS (o boliche kids): o .glb da máquina com a adesivagem de
    verdade (laterais, testeira, tela, pista e frente), feito para a
    fábrica. É o PRIMEIRO objeto 3D ligado pelo cadastro (`ObjetoTresD`):
    se o brinquedo já está no catálogo (com as fotos reais), só ganha o
    objeto; se não está, entra com as fotos tiradas do próprio 3D.

Quem cadastra:
  * as migrações de dados (`0113_brinquedao_modelo_2`,
    `0114_espaco_esportivo_modelo_1`, `0140_brinquedao_ninja`,
    `0142_brinquedao_modelo_4`), no deploy
    do Render (o migrate roda sozinho no Pre-Deploy Command): o brinquedo
    já entra no catálogo;
  * `python manage.py cadastrar_modelo_3d <id>`, se a migração não
    conseguiu (sem Cloudinary naquela hora, por exemplo).

O objeto 3D se liga ao brinquedo pelo NOME (`core/arena.py`, MODELOS_3D).
As fotos 2D sobem para o Cloudinary como as enviadas pelo painel. Rodar
de novo não duplica.
"""

from decimal import Decimal
from pathlib import Path

from django.core.files import File
from django.db import transaction

from .arena import _normalizar

MODELOS = Path(__file__).resolve().parent / "static" / "site" / "arena" / "modelos"

#: O que cada cadastro leva. `fotos`: (arquivo, tipo na galeria, descrição); a
#: primeira é a foto principal. `categorias`: trechos de nome de categoria que
#: servem (nenhuma é criada); `evitar`, trechos que tiram a categoria.
CADASTROS = {
    "brinquedao-modelo-2": {
        "nome": "Brinquedão Modelo 2",
        "pasta": MODELOS / "brinquedao-modelo-2",
        "objeto_3d": "site/arena/modelos/brinquedao-modelo-2.glb",
        "descricao": (
            "Brinquedão temático de selva com 11 m de comprimento, 2 m de profundidade e 3,5 m de altura. "
            "Torre com piso de rede e bolas suspensas, três casinhas com arco (azul, laranja e amarela), "
            "andar superior com rede de escalada, rolo e tubo de passagem, painéis temáticos, escorregador "
            "duplo ondulado e tobogã em espiral. Estrutura em tubos com conexões e telas de proteção. "
            "Projeto ilustrativo: cores, painéis e itens podem ser ajustados conforme o espaço e a "
            "disponibilidade de materiais."
        ),
        "medidas": ("3.50", "11.00", "2.00"),
        "fotos": (
            ("frente.webp", "perfil", "Brinquedão Modelo 2 visto de frente"),
            ("lado_esquerdo.webp", "lado_esquerdo", "Brinquedão Modelo 2 visto pelo lado da torre das bolas"),
            ("lado_direito.webp", "lado_direito", "Brinquedão Modelo 2 visto pelo lado dos escorregadores"),
            ("planta.webp", None, "Planta do Brinquedão Modelo 2 vista de cima: 11 m por 2 m, altura de 3,5 m"),
        ),
        "categorias": ("brinquedao", "brinquedoes", "playground", "kid play", "kids play"),
        "evitar": (),
    },
    "brinquedao-ninja": {
        "nome": "Brinquedão Ninja",
        "pasta": MODELOS / "brinquedao-ninja",
        "objeto_3d": "site/arena/modelos/brinquedao-ninja.glb",
        "descricao": (
            "Brinquedão Ninja com 14 m de comprimento (10 m de brinquedão e 4 m de camas elásticas), 2 m de "
            "profundidade e 3,10 m de altura. Entrada pelo canto com degraus acolchoados; no andar de cima, o "
            "circuito ninja: cilindros pendurados, postes com pegas, rolo vazado, passarela de rede em V e "
            "painéis temáticos. Embaixo, piscina de cubos de espuma com cordas e tirolesa, módulo com piscina "
            "de bolinhas e tobogã em espiral, e duas camas elásticas de 2 m × 2 m com rede de proteção. "
            "Estrutura em tubos com conexões e telas de proteção. Projeto ilustrativo: cores, painéis e itens "
            "podem ser ajustados conforme o espaço e a disponibilidade de materiais."
        ),
        # as da planta (o .3ds chega a 3,3 m no corrimão de cima; o cadastro fica com o da fábrica)
        "medidas": ("3.10", "14.00", "2.00"),
        "fotos": (
            ("frente.webp", "perfil", "Brinquedão Ninja visto de frente: o andar de cima com os obstáculos, a piscina de cubos e o tobogã"),
            ("planta.webp", None, "Planta do Brinquedão Ninja vista de cima: 10 m + 4 m de camas elásticas, por 2 m, altura de 3,10 m"),
        ),
        "categorias": ("brinquedao", "brinquedoes", "playground", "kid play", "kids play"),
        "evitar": (),
    },
    # ---- Brinquedão Modelo 4 ----
    # O .3ds da fábrica (a estrutura de tubos azuis) e as imagens do projeto
    # (ver `ferramentas/modelos3d/brinquedao-modelo-4/`). As fotos são as
    # imagens do projeto mesmo: o render em perspectiva (a principal), a vista
    # de frente, a planta e o brinquedão montado num salão.
    "brinquedao-modelo-4": {
        "nome": "Brinquedão Modelo 4",
        "pasta": MODELOS / "brinquedao-modelo-4",
        "objeto_3d": "site/arena/modelos/brinquedao-modelo-4.glb",
        "descricao": (
            "Brinquedão de dois andares em Z, com 19,6 m de comprimento (um trecho de 12 m e outro de 9 m, "
            "ligados por uma passagem), 2 m de fundo em cada trecho e 3,55 m de altura. Sobe-se pela escada da "
            "ponta esquerda; no andar de cima, painéis X, rolos de espuma em pé e em pares deitados, quatro "
            "passarelas de rede amarela em V, sacos azuis pendurados e a pirâmide magenta. Embaixo, piscina de "
            "bolinhas com dois escorregadores ondulados, Área Baby com cercadinho, blocos de espuma e piso de "
            "EVA, e o tobogã espiral amarelo e magenta que desce até a piscina de bolinhas com a escadinha "
            "verde. Estrutura em tubos azuis com telas de proteção. Projeto ilustrativo: cores, painéis e itens "
            "podem ser ajustados conforme o espaço e a disponibilidade de materiais."
        ),
        # as do objeto (a planta: 12 m + 9 m, 3,60 m de fundo da estrutura, altura de 3,45 m)
        "medidas": ("3.55", "19.60", "6.00"),
        "fotos": (
            ("perspectiva.webp", "perfil", "Brinquedão Modelo 4 em perspectiva: o tobogã espiral, a Área Baby e os dois andares"),
            ("frente.webp", None, "Brinquedão Modelo 4 visto de frente, com 3,45 m de altura"),
            ("planta.webp", None, "Planta do Brinquedão Modelo 4 vista de cima: 12 m + 9 m, 2 m de fundo em cada trecho"),
            ("salao.webp", None, "O Brinquedão Modelo 4 montado num salão (projeto ilustrativo)"),
        ),
        "categorias": ("brinquedao", "brinquedoes", "playground", "kid play", "kids play"),
        "evitar": (),
    },
    "espaco-esportivo-modelo-1": {
        "nome": "Espaço Esportivo Modelo 1",
        "pasta": MODELOS / "espaco-esportivo-modelo-1",
        "objeto_3d": "site/arena/modelos/espaco-esportivo-modelo-1.glb",
        "descricao": (
            "Espaço esportivo completo numa área de 39 m × 23 m. Parque de trampolins de 18 m × 16,5 m "
            "(plataforma a 0,85 m e estrutura de 3,65 m): camas em blocos coloridos, seis piscinas de espuma "
            "com percurso suspenso, piscina de espuma grande com parede de escalada, cinco enterradas com "
            "cesta e o varredor. Ao lado, quadras de campo e de basquete enjauladas (altura de 2,9 m), dois "
            "círculos de 5 m do Gol Flash redondo e pista de 14 m; na frente, o circuito kids com tobogã e piscina de "
            "bolinhas, sobre piso de EVA. Projeto ilustrativo: a divisão e os itens se ajustam ao espaço."
        ),
        "medidas": ("3.65", "39.00", "23.00"),
        "fotos": (
            ("frente.webp", "perfil", "Espaço Esportivo Modelo 1 visto de frente: quadras, parque de trampolins e circuito kids"),
            ("lado_direito.webp", "lado_direito", "Espaço Esportivo Modelo 1 visto pelo lado do circuito kids"),
            ("lado_esquerdo.webp", "lado_esquerdo", "Espaço Esportivo Modelo 1 visto pelo lado das quadras"),
            ("planta.webp", None, "Espaço Esportivo Modelo 1 visto de cima"),
        ),
        "categorias": ("esportiv",),
        # "Espaço esportivo" é o certo; "kids" fica para os menores, se houver as duas
        "evitar": ("kids",),
    },
    "strike-kids": {
        "nome": "Strike Kids",
        # o brinquedo do catálogo que é esta máquina
        "nomes": ("strike kids",),
        "pasta": MODELOS / "strike-kids",
        "objeto_3d": "site/arena/modelos/strike-kids.glb",
        "descricao": (
            "Strike Kids, o boliche infantil da Lazer & Sport: pista de 1,4 m com bolsão para as bolas, "
            "tela vertical com o jogo Strike Kids, câmera que tira a foto do jogador para o ranking e 5 "
            "sensores de precisão que leem cada jogada. Testeira e laterais adesivadas com os pinos "
            "sorridentes e LEDs nas laterais. Medidas aproximadas: 2,07 m de altura, 0,74 m de largura e "
            "1,91 m de comprimento. Cores e adesivagem podem ser ajustadas no pedido."
        ),
        "medidas": ("2.07", "0.74", "1.91"),
        # as fotos, todas sem fundo e tiradas do .glb da própria máquina: a
        # principal de 3/4; os lados e as costas (os tipos que a Arena usa);
        # mais ângulos; e a adesivagem nas outras cores que o site oferece
        "fotos": (
            ("foto.webp", "perfil", "Strike Kids, o boliche infantil, com a tela, a pista e a arte dos pinos"),
            ("lado_direito.webp", "lado_direito", "Strike Kids pelo lado direito, com a arte dos pinos"),
            ("lado_esquerdo.webp", "lado_esquerdo", "Strike Kids pelo lado esquerdo, com a arte dos pinos"),
            ("verso.webp", "verso", "Strike Kids visto por trás"),
            ("frente.webp", None, "Strike Kids visto de frente: a pista, as bolas e a tela do jogo"),
            ("tres_quartos_esquerda.webp", None, "Strike Kids de 3/4, pelo lado esquerdo"),
            ("de_cima.webp", None, "Strike Kids visto de cima, com a pista inteira"),
            ("cor_azul.webp", None, "Strike Kids com a adesivagem em tons de azul"),
            ("cor_roxo.webp", None, "Strike Kids com a adesivagem em tons de roxo"),
            ("cor_rosa.webp", None, "Strike Kids com a adesivagem em tons de rosa"),
            ("cor_vermelho.webp", None, "Strike Kids com a adesivagem em tons de vermelho"),
            ("cor_laranja.webp", None, "Strike Kids com a adesivagem em tons de laranja"),
        ),
        "categorias": ("boliche", "jogos", "eletronic"),
        "evitar": (),
    },
    # ---- Trampolim de Enterrada ----
    # O .3ds da fábrica (a estrutura) e as imagens do projeto (ver
    # `ferramentas/modelos3d/trampolim-enterrada/`). As fotos ainda são vistas
    # do próprio objeto 3D, com o fundo claro do catálogo: quando chegarem as
    # do projeto, troque os .webp da pasta e rode o comando com `--fotos`.
    "trampolim-enterrada": {
        "nome": "Trampolim de Enterrada",
        "nomes": ("trampolim de enterrada", "trampolim enterrada"),
        "pasta": MODELOS / "trampolim-enterrada",
        "objeto_3d": "site/arena/modelos/trampolim-enterrada.glb",
        "descricao": (
            "Trampolim de enterrada com 6 m de comprimento, 2 m de profundidade e 3,25 m de altura. Pista de "
            "três camas elásticas em linha (uma de 2 m e duas de 1,5 m), com moldura e divisórias estofadas em "
            "amarelo, que termina na parede inclinada estofada com a cesta de basquete (aro e rede) para a "
            "enterrada. Base em caixote, estrutura de tubos com quatro colunas e quadro superior amarelo, e "
            "escada de espuma de três degraus. Variante com piscina de cubos de espuma no lugar da cama do meio. "
            "Projeto ilustrativo: cores e itens podem ser ajustados conforme o espaço e a disponibilidade de "
            "materiais."
        ),
        "medidas": ("3.25", "6.00", "2.00"),
        "fotos": (
            ("frente.webp", "perfil", "Trampolim de Enterrada visto de frente: as três camas, a parede com a cesta e a escada"),
            ("lado_esquerdo.webp", "lado_esquerdo", "Trampolim de Enterrada visto pelo lado da cesta"),
            ("lado_direito.webp", "lado_direito", "Trampolim de Enterrada visto pelo lado da escada, com a pista até a cesta"),
            ("planta.webp", None, "Trampolim de Enterrada visto de cima: 6 m por 2 m"),
            ("espuma.webp", None, "A variante com a piscina de cubos de espuma no lugar da cama do meio"),
        ),
        "categorias": ("trampolim", "cama elastica", "camas elasticas"),
        "evitar": (),
    },
}


def cadastrar(chave, Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, refazer_fotos=False, avisar=print):
    """Cria o brinquedo com as fotos. Devolve (brinquedo, criado).

    Recebe os modelos para servir às migrações (modelos históricos) e ao
    comando (os de verdade).
    """
    dados = CADASTROS[chave]
    nome = dados["nome"]
    brinquedo = Brinquedos.objects.filter(nome_brinquedo=nome).first()
    if brinquedo and not refazer_fotos:
        avisar(f"O {nome} já está cadastrado (id {brinquedo.pk}).")
        return brinquedo, False

    with transaction.atomic():
        criado = brinquedo is None
        if criado:
            altura, largura, profundidade = (Decimal(v) for v in dados["medidas"])
            brinquedo = Brinquedos.objects.create(
                nome_brinquedo=nome,
                descricao=dados["descricao"],
                valor_brinquedo=None,
                avaliacao=Decimal("5.00"),
                exibir_na_loja=False,
                voltz="",
                altura_m=altura,
                largura_m=largura,
                profundidade_m=profundidade,
            )
            candidatas = [
                c for c in CategoriasBrinquedos.objects.all()
                if any(trecho in _normalizar(c.nome_categoria) for trecho in dados["categorias"])
            ]
            preferidas = [c for c in candidatas if not any(t in _normalizar(c.nome_categoria) for t in dados["evitar"])]
            categorias = preferidas or candidatas
            brinquedo.categorias_brinquedos.set(categorias)
            avisar(f"Criado: {nome} (id {brinquedo.pk}).")
            avisar("Categorias: " + (", ".join(c.nome_categoria for c in categorias) or "nenhuma que sirva; escolha no painel"))
        else:
            brinquedo.imagens_brinquedo.all().delete()

        fotos = dados["fotos"]
        for ordem, (arquivo, tipo, texto) in enumerate(fotos, start=1):
            with open(dados["pasta"] / arquivo, "rb") as origem:
                imagem = ImagemBrinquedo(brinquedo=brinquedo, tipo=tipo, ordem=ordem, texto_alternativo=texto)
                imagem.imagem.save(f"{chave}-{arquivo}", File(origem), save=True)
        with open(dados["pasta"] / fotos[0][0], "rb") as origem:
            brinquedo.imagem_brinquedo.save(f"{chave}-{fotos[0][0]}", File(origem), save=True)
    avisar(f"{len(fotos)} fotos na galeria; na Arena 3D ele aparece com o objeto 3D do projeto.")
    return brinquedo, criado


def achar_no_catalogo(chave, Brinquedos):
    """O brinquedo ATIVO do catálogo que é esta máquina (pelo nome), ou None.

    Desativado não conta: ele não aparece no site, e contar com ele fazia o
    cadastro só ligar o 3D num brinquedo escondido em vez de criar o novo.
    """
    dados = CADASTROS[chave]
    trechos = [_normalizar(t) for t in dados.get("nomes", ()) or (dados["nome"],)]
    for brinquedo in Brinquedos.objects.filter(ativo=True).order_by("id"):
        nome = _normalizar(brinquedo.nome_brinquedo or "")
        if any(trecho in nome for trecho in trechos):
            return brinquedo
    return None


def ligar_objeto_3d(chave, brinquedo, ObjetoTresD):
    """Liga o objeto 3D do site ao brinquedo (cria ou atualiza; não duplica)."""
    from .objetos_3d import ler_glb_do_site

    caminho = CADASTROS[chave]["objeto_3d"]
    lido = ler_glb_do_site(caminho)
    objeto, _criado = ObjetoTresD.objects.update_or_create(
        brinquedo=brinquedo,
        defaults={
            "arquivo_estatico": caminho,
            "codigo": chave,
            "cores": lido["cores"],
            "medidas": lido["medidas"],
            "ativo": True,
            "exibir_na_arena": True,
        },
    )
    return objeto


def cadastrar_brinquedao_modelo_2(Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, refazer_fotos=False, avisar=print):
    """O cadastro do Brinquedão Modelo 2 (a migração 0113 chama por este nome)."""
    return cadastrar("brinquedao-modelo-2", Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, refazer_fotos, avisar)


def migracao(chave):
    """A função de uma migração de dados que cadastra o modelo `chave`.

    Só roda no Render (no computador e nos testes não há Cloudinary de
    verdade). Se algo falhar, avisa e não derruba o deploy: o comando
    `cadastrar_modelo_3d` refaz depois.
    """
    def cadastrar_no_deploy(apps, schema_editor):
        from django.conf import settings

        if not getattr(settings, "IS_RENDER", False):
            return
        try:
            with transaction.atomic():
                cadastrar(
                    chave,
                    apps.get_model("core", "Brinquedos"),
                    apps.get_model("core", "CategoriasBrinquedos"),
                    apps.get_model("core", "ImagemBrinquedo"),
                )
        except Exception as erro:  # o deploy segue; o comando refaz depois
            print(f"{CADASTROS[chave]['nome']} não foi cadastrado agora ({erro}). "
                  f"Rode: python manage.py cadastrar_modelo_3d {chave}")

    return cadastrar_no_deploy


def garantir_strike_kids(Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, ObjetoTresD, avisar=print):
    """Garante o Strike Kids no catálogo: ATIVO, com as fotos e o objeto 3D.

    Pode rodar quantas vezes for (no comando, ao subir o servidor, numa
    migração): quando já está tudo certo, só confere. Conta o que achou e
    o que fez, e deixa o erro subir -- quem chama decide se engole.

    * Um "Strike Kids" ativo cadastrado pelo site (as fotos são as daqui):
      fica com o nome "Strike Kids" e, se faltar foto, ganha as fotos.
    * Um ativo cadastrado no painel (as fotos são de alguém): fica como
      está, só ganha o 3D.
    * Nenhum ativo: o "Strike Kids" desativado volta (com as fotos daqui), ou
      um novo é cadastrado.
    """
    dados = CADASTROS["strike-kids"]
    parecidos = [
        b for b in Brinquedos.objects.order_by("id")
        if "strike kids" in _normalizar(b.nome_brinquedo or "")
    ]
    avisar("Strike Kids no banco: " + (", ".join(
        f"{b.nome_brinquedo} (id {b.pk}, {'ativo' if b.ativo else 'desativado'})" for b in parecidos
    ) or "nenhum"))
    brinquedo = next((b for b in parecidos if b.ativo), None)
    do_site = brinquedo is not None and "strike-kids-" in (brinquedo.imagem_brinquedo.name or "")
    if brinquedo is None:
        desativado = next((b for b in parecidos if b.nome_brinquedo == dados["nome"]), None)
        if desativado is not None:
            desativado.ativo = True
            desativado.save(update_fields=["ativo"])
            brinquedo, do_site = desativado, True
            avisar(f"Reativado: {brinquedo.nome_brinquedo} (id {brinquedo.pk}).")
    with transaction.atomic():
        if brinquedo is None:
            brinquedo, _criado = cadastrar("strike-kids", Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, avisar=avisar)
        elif do_site:
            if brinquedo.nome_brinquedo != dados["nome"]:
                brinquedo.nome_brinquedo = dados["nome"]
                brinquedo.descricao = dados["descricao"]
                brinquedo.save(update_fields=["nome_brinquedo", "descricao"])
            fotos_daqui = "strike-kids-foto" in (brinquedo.imagem_brinquedo.name or "")
            if not fotos_daqui or brinquedo.imagens_brinquedo.count() < len(dados["fotos"]):
                brinquedo, _ = cadastrar(
                    "strike-kids", Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, refazer_fotos=True, avisar=avisar,
                )
        ligar_objeto_3d("strike-kids", brinquedo, ObjetoTresD)
    avisar(f"Strike Kids pronto: {brinquedo.nome_brinquedo} (id {brinquedo.pk}), ativo, com "
           f"{brinquedo.imagens_brinquedo.count()} fotos e o objeto 3D.")
    return brinquedo


def strike_kids_no_catalogo(apps, schema_editor, avisar=print):
    """A migração do Strike Kids (a 0120 e a 0121): a garantia acima, no banco de verdade.

    Só no PostgreSQL (o banco do site, no Render ou no computador): o SQLite
    é o dos testes. Se falhar (a subida das fotos, por exemplo), o deploy
    segue -- e o servidor tenta de novo ao subir (gunicorn.conf.py).
    """
    from django.conf import settings

    real = getattr(settings, "IS_RENDER", False) or schema_editor.connection.vendor == "postgresql"
    if not real:
        return None
    try:
        return garantir_strike_kids(
            apps.get_model("core", "Brinquedos"),
            apps.get_model("core", "CategoriasBrinquedos"),
            apps.get_model("core", "ImagemBrinquedo"),
            apps.get_model("core", "ObjetoTresD"),
            avisar=avisar,
        )
    except Exception as erro:  # o deploy segue; o servidor tenta de novo ao subir
        avisar(f"O Strike Kids não foi cadastrado agora ({erro!r}). Rode: python manage.py cadastrar_modelo_3d strike-kids")
        return None


def migracao_objetos_3d(*chaves, cadastrar_no_banco_real=False):
    """A migração que liga os objetos 3D do site aos brinquedos `chaves`.

    A ligação roda em todo lugar (não mexe em arquivo nenhum). O cadastro
    do brinquedo, quando ele ainda não está no catálogo, só no Render (as
    fotos sobem para o Cloudinary); se falhar, o deploy segue e o comando
    `cadastrar_modelo_3d` refaz.
    """
    def ligar_no_deploy(apps, schema_editor):
        from django.conf import settings

        Brinquedos = apps.get_model("core", "Brinquedos")
        # o banco de verdade do site é o PostgreSQL (o Supabase), no Render
        # ou no computador; o SQLite é o dos testes e o de rascunho
        pode_cadastrar = getattr(settings, "IS_RENDER", False) or (
            cadastrar_no_banco_real and schema_editor.connection.vendor == "postgresql"
        )
        for chave in chaves:
            brinquedo = achar_no_catalogo(chave, Brinquedos)
            if brinquedo is None and pode_cadastrar:
                try:
                    with transaction.atomic():
                        brinquedo, _criado = cadastrar(
                            chave,
                            Brinquedos,
                            apps.get_model("core", "CategoriasBrinquedos"),
                            apps.get_model("core", "ImagemBrinquedo"),
                        )
                except Exception as erro:  # o deploy segue; o comando refaz depois
                    print(f"{CADASTROS[chave]['nome']} não foi cadastrado agora ({erro}). "
                          f"Rode: python manage.py cadastrar_modelo_3d {chave}")
                    continue
            if brinquedo is not None:
                ligar_objeto_3d(chave, brinquedo, apps.get_model("core", "ObjetoTresD"))

    return ligar_no_deploy
