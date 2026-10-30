"""Cadastra o Brinquedão Selva 11m no catálogo, com as fotos do projeto.

    python manage.py cadastrar_brinquedao_selva

O objeto 3D dele já vem no site (`core/arena.py`, MODELOS_3D) e se liga
pelo nome: este comando só cria o brinquedo, com as medidas da planta
(11 m × 2 m, altura 3,5 m) e as quatro imagens de `dados/brinquedao_selva/`
(frente, os dois lados e a planta vista de cima). As fotos sobem para o
Cloudinary como as enviadas pelo painel.

Rodar de novo não duplica: se o brinquedo já existe, só avisa. Com
`--fotos`, refaz a galeria dele com as imagens daqui.

Entra na categoria de brinquedões/playground que já existir no catálogo
(nenhuma é criada). Fica "sob consulta" (sem preço e fora da loja): o preço
e a vitrine são decisão de quem cuida do catálogo, no painel.
"""

from decimal import Decimal
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction

from core.arena import _normalizar
from core.models import Brinquedos, CategoriasBrinquedos, ImagemBrinquedo

PASTA = Path(__file__).resolve().parent / "dados" / "brinquedao_selva"
NOME = "Brinquedão Selva 11m"
DESCRICAO = (
    "Brinquedão temático de selva com 11 m de comprimento, 2 m de profundidade e 3,5 m de altura. "
    "Torre com piso de rede e bolas suspensas, três casinhas com arco (azul, laranja e amarela), "
    "andar superior com rede de escalada, rolo e tubo de passagem, painéis temáticos, escorregador "
    "duplo ondulado e tobogã em espiral. Estrutura em tubos com conexões e telas de proteção. "
    "Projeto ilustrativo: cores, painéis e itens podem ser ajustados conforme o espaço e a disponibilidade "
    "de materiais."
)
#: (arquivo, tipo na galeria, descrição da imagem)
FOTOS = (
    ("frente.webp", ImagemBrinquedo.TIPO_PERFIL, "Brinquedão Selva 11m visto de frente"),
    ("lado_esquerdo.webp", ImagemBrinquedo.TIPO_LADO_ESQUERDO, "Brinquedão Selva 11m visto pelo lado da torre das bolas"),
    ("lado_direito.webp", ImagemBrinquedo.TIPO_LADO_DIREITO, "Brinquedão Selva 11m visto pelo lado dos escorregadores"),
    ("planta.webp", None, "Planta do Brinquedão Selva vista de cima: 11 m por 2 m, altura de 3,5 m"),
)
#: Trechos de nome de categoria que servem para um brinquedão.
CATEGORIAS = ("brinquedao", "brinquedoes", "playground", "kid play", "kids play")


class Command(BaseCommand):
    help = "Cadastra o Brinquedão Selva 11m (fotos e medidas); o objeto 3D já está no site."

    def add_arguments(self, parser):
        parser.add_argument("--fotos", action="store_true", help="refaz a galeria de um cadastro que já existe")

    def handle(self, *args, fotos=False, **opcoes):
        brinquedo = Brinquedos.objects.filter(nome_brinquedo=NOME).first()
        if brinquedo and not fotos:
            self.stdout.write(f"O {NOME} já está cadastrado (id {brinquedo.pk}). Nada a fazer.")
            return

        with transaction.atomic():
            if not brinquedo:
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
                self.stdout.write(f"Criado: {NOME} (id {brinquedo.pk}).")
                if categorias:
                    self.stdout.write("Categorias: " + ", ".join(c.nome_categoria for c in categorias))
                else:
                    self.stdout.write("Nenhuma categoria de brinquedão encontrada: escolha uma no painel.")
            else:
                brinquedo.imagens_brinquedo.all().delete()

            for ordem, (arquivo, tipo, texto) in enumerate(FOTOS, start=1):
                with open(PASTA / arquivo, "rb") as origem:
                    imagem = ImagemBrinquedo(brinquedo=brinquedo, tipo=tipo, ordem=ordem, texto_alternativo=texto)
                    imagem.imagem.save(f"brinquedao-selva-{arquivo}", File(origem), save=True)
            with open(PASTA / FOTOS[0][0], "rb") as origem:
                brinquedo.imagem_brinquedo.save(f"brinquedao-selva-{FOTOS[0][0]}", File(origem), save=True)

        self.stdout.write(self.style.SUCCESS(
            f"Pronto: {len(FOTOS)} fotos na galeria. Na Arena 3D ele aparece com o objeto 3D do projeto."
        ))
