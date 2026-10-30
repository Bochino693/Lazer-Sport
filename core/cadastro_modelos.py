"""Cadastro dos brinquedos que já chegam com o objeto 3D feito aqui.

Por enquanto um: o BRINQUEDÃO MODELO 2, feito com o .3ds da fábrica e as
imagens do projeto (ver `ferramentas/modelos3d/brinquedao-modelo-2/`).

Quem cadastra:
  * a migração `0113_brinquedao_modelo_2`, no deploy do Render (o migrate
    roda sozinho no Pre-Deploy Command): o brinquedo já entra no catálogo;
  * `python manage.py cadastrar_brinquedao_modelo_2`, se a migração não
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

PASTA = Path(__file__).resolve().parent / "static" / "site" / "arena" / "modelos" / "brinquedao-modelo-2"
NOME = "Brinquedão Modelo 2"
DESCRICAO = (
    "Brinquedão temático de selva com 11 m de comprimento, 2 m de profundidade e 3,5 m de altura. "
    "Torre com piso de rede e bolas suspensas, três casinhas com arco (azul, laranja e amarela), "
    "andar superior com rede de escalada, rolo e tubo de passagem, painéis temáticos, escorregador "
    "duplo ondulado e tobogã em espiral. Estrutura em tubos com conexões e telas de proteção. "
    "Projeto ilustrativo: cores, painéis e itens podem ser ajustados conforme o espaço e a "
    "disponibilidade de materiais."
)
#: (arquivo, tipo na galeria, descrição da imagem). A primeira é a foto principal.
FOTOS = (
    ("frente.webp", "perfil", "Brinquedão Modelo 2 visto de frente"),
    ("lado_esquerdo.webp", "lado_esquerdo", "Brinquedão Modelo 2 visto pelo lado da torre das bolas"),
    ("lado_direito.webp", "lado_direito", "Brinquedão Modelo 2 visto pelo lado dos escorregadores"),
    ("planta.webp", None, "Planta do Brinquedão Modelo 2 vista de cima: 11 m por 2 m, altura de 3,5 m"),
)
#: Trechos de nome de categoria que servem para um brinquedão (nenhuma é criada).
CATEGORIAS = ("brinquedao", "brinquedoes", "playground", "kid play", "kids play")


def cadastrar_brinquedao_modelo_2(Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, refazer_fotos=False, avisar=print):
    """Cria o brinquedo com as fotos. Devolve (brinquedo, criado).

    Recebe os modelos para servir à migração (modelos históricos) e ao
    comando (os de verdade).
    """
    brinquedo = Brinquedos.objects.filter(nome_brinquedo=NOME).first()
    if brinquedo and not refazer_fotos:
        avisar(f"O {NOME} já está cadastrado (id {brinquedo.pk}).")
        return brinquedo, False

    with transaction.atomic():
        criado = brinquedo is None
        if criado:
            brinquedo = Brinquedos.objects.create(
                nome_brinquedo=NOME,
                descricao=DESCRICAO,
                valor_brinquedo=None,
                avaliacao=Decimal("5.00"),
                exibir_na_loja=False,
                voltz="",
                altura_m=Decimal("3.50"),
                largura_m=Decimal("11.00"),
                profundidade_m=Decimal("2.00"),
            )
            categorias = [
                c for c in CategoriasBrinquedos.objects.all()
                if any(trecho in _normalizar(c.nome_categoria) for trecho in CATEGORIAS)
            ]
            brinquedo.categorias_brinquedos.set(categorias)
            avisar(f"Criado: {NOME} (id {brinquedo.pk}).")
            avisar("Categorias: " + (", ".join(c.nome_categoria for c in categorias) or "nenhuma de brinquedão; escolha no painel"))
        else:
            brinquedo.imagens_brinquedo.all().delete()

        for ordem, (arquivo, tipo, texto) in enumerate(FOTOS, start=1):
            with open(PASTA / arquivo, "rb") as origem:
                imagem = ImagemBrinquedo(brinquedo=brinquedo, tipo=tipo, ordem=ordem, texto_alternativo=texto)
                imagem.imagem.save(f"brinquedao-modelo-2-{arquivo}", File(origem), save=True)
        with open(PASTA / FOTOS[0][0], "rb") as origem:
            brinquedo.imagem_brinquedo.save(f"brinquedao-modelo-2-{FOTOS[0][0]}", File(origem), save=True)
    avisar(f"{len(FOTOS)} fotos na galeria; na Arena 3D ele aparece com o objeto 3D do projeto.")
    return brinquedo, criado
