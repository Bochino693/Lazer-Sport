"""Cadastro dos brinquedos que já chegam com o objeto 3D feito aqui.

  * BRINQUEDÃO MODELO 2: o .3ds da fábrica e as imagens do projeto
    (ver `ferramentas/modelos3d/brinquedao-modelo-2/`);
  * ESPAÇO ESPORTIVO MODELO 1: o trampo.3ds do parque de trampolins, as
    plantas do parque e das quadras e as imagens do espaço completo (ver
    `ferramentas/modelos3d/espaco-esportivo-modelo-1/`). As fotos dele são
    vistas do próprio objeto 3D, com o fundo claro do catálogo.

Quem cadastra:
  * as migrações de dados (`0113_brinquedao_modelo_2`,
    `0114_espaco_esportivo_modelo_1`), no deploy do Render (o migrate roda
    sozinho no Pre-Deploy Command): o brinquedo já entra no catálogo;
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
    "espaco-esportivo-modelo-1": {
        "nome": "Espaço Esportivo Modelo 1",
        "pasta": MODELOS / "espaco-esportivo-modelo-1",
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
