"""O que cada máquina fotografa no estúdio (as tomadas) e para onde vai cada foto do site.

Python puro (sem o Blender): os testes do site leem daqui os arquivos que o estúdio grava.

AS MEDIDAS são as do cadastro (Brinquedos.altura_m / largura_m / profundidade_m, postas pelas
migrações de dados) -- o estúdio põe o .glb nessa altura (a escala é uma só: a arte não
deforma) e confere a largura e a profundidade.

O ENQUADRAMENTO É UM SÓ POR MÁQUINA: cada tomada se calcula UMA vez, no primeiro adesivo
(o de referência, com 3D), e vale para todos os adesivos dela -- a mesma câmera, a mesma lente,
a mesma distância. O Basquete Home azul e o preto saem do mesmo tamanho na mesma foto.

Uma TOMADA:
  * giro: a máquina na mesa giratória, em graus (0: de frente para a câmera; positivo mostra
    o lado esquerdo da máquina, negativo o direito; 180: as costas);
  * camera: a altura da câmera (m), a de quem fotografa em pé (~1,6 m) ou mais alta;
  * saida: (largura, altura) da foto do site (o 4K de dentro tem a mesma proporção);
  * margem: a folga de cada lado no lado que limita (fração; a máquina inteira, nunca cortada);
  * luz: "estudio" (o padrão) ou "noite" (o estúdio apagado: os LEDs, o neon e a tela acesos);
  * detalhe: regex dos objetos/materiais que a câmera enquadra (o detalhe de perto: aí a
    máquina não aparece inteira, de propósito);
  * transparente: o recorte sem fundo (o "recorte para artes": só o painel o mostra);
  * so_mestre: só o mestre 4K (não vai para o site: para as artes e o Instagram).
Uma MÁQUINA ainda pode ter `luzes` ({luz: fator}: a mesa clara pede menos luz de cima),
`exposicao` (em pontos de exposição, somada à do modo de luz) e `fundo` (o fator do brilho
azul do fundo).
"""

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
MODELOS = "core/static/site/arena/modelos"
CAPAS = "core/static/site/capas_catalogo"

#: Os tamanhos de hoje no site.
CAPA = (1600, 1600)
VISTA = (1600, 1000)
QUADRADA = (1080, 1080)

PRODUTOS = {
    # ------------------------------------------------------------------
    # BASQUETE HOME: o azul (o padrão, ainda sem 3D: a foto da fábrica) e o Quadrinhos (preto)
    # ------------------------------------------------------------------
    "basquete-home": {
        "nome": "Basquete Home",
        # o cadastro (a 0166 copiou para o Basquete Home as do Quadrinhos, que vieram do Basquete
        # Street na 0145): 2,70 x 1,00 x 2,40 m. Uma estimativa antiga da cena dizia ~2,10 m de
        # altura: na dúvida, vale o banco (e o .glb tem 2,70 m)
        "medidas": (2.70, 1.00, 2.40),
        "frente": 0,
        # a máquina preta: o fotógrafo abre um pouco e clareia o fundo (a arte escura não some
        # nele, e a capa não fica escura demais: o card pede brilho médio acima de 70)
        "exposicao": 0.4,
        "fundo": 1.4,
        "variantes": (
            {"chave": "quadrinhos", "nome": "Quadrinhos", "glb": f"{MODELOS}/basquete-street-quadrinhos.glb",
             "pasta": f"{MODELOS}/basquete-street-quadrinhos",
             "artes": "ferramentas/modelos3d/basquete-street-quadrinhos/adesivos"},
            # o azul não tem 3D nem a folha de adesivos: a foto da fábrica entra no estúdio, no
            # MESMO quadro e no MESMO tamanho do Quadrinhos (estudio.cartao_da_foto)
            {"chave": "azul", "nome": "Azul", "foto": "ferramentas/categorias/maquinas-alta/basquete-home.webp",
             "fotos": {"capa": f"{CAPAS}/basquete-home.webp"}},
        ),
        "tomadas": {
            # a capa: de 3/4 pela direita e do alto (o ponto de vista da foto da fábrica do azul)
            "capa": {"giro": -30, "camera": 2.35, "saida": CAPA},
            "frente": {"giro": 33, "camera": 2.0, "saida": VISTA},
            "lado_esquerdo": {"giro": 74, "camera": 1.6, "saida": VISTA},
            # (de trás e pela direita: a mesma arte espelhada do lado esquerdo, de outro ponto)
            "lado_direito": {"giro": -104, "camera": 1.5, "saida": VISTA},
            "verso": {"giro": 148, "camera": 1.9, "saida": VISTA},
            # o detalhe: de quem joga, do alto -- a quadra, as bolas, a cesta, o BOOM! e o placar
            "jogador": {"giro": 0, "camera": 2.45, "saida": VISTA, "margem": 0.03,
                        "detalhe": r"prancha|aro|fundo-cesta|placar|bolas|rede|chapa-de-parada|botao|teto-interno"},
            # a capa com o estúdio apagado (o neon, o placar e a testeira acesos)
            "capa_noite": {"giro": -30, "camera": 2.35, "saida": CAPA, "luz": "noite", "so_mestre": True},
        },
    },
    # ------------------------------------------------------------------
    # AIR GAME KIDS: os Astronautas (o padrão) e os Alienígenas, o mesmo móvel
    # ------------------------------------------------------------------
    "air-game-kids": {
        "nome": "Air Game Kids",
        # o cadastro: 0,90 x 0,86 x 1,50 m (o 3D, desde a seção 92 com as laterais de MDF grosso: 0,86 x 1,51 m)
        "medidas": (0.90, 0.86, 1.50),
        # a lateral comprida com o placar (x+) de frente para a câmera
        "frente": -90,
        # o tampo branco, deitado, recebe mais luz que as laterais: menos luz de cima
        "luzes": {"teto": 0.35, "principal": 0.85},
        "variantes": (
            {"chave": "alienigenas", "nome": "Alienígenas", "glb": f"{MODELOS}/air-game-kids-alienigenas.glb",
             "pasta": f"{MODELOS}/air-game-kids-alienigenas",
             "artes": "ferramentas/modelos3d/air-game-kids-alienigenas/adesivos"},
            {"chave": "astronautas", "nome": "Astronautas", "glb": f"{MODELOS}/air-game-kids-astronautas.glb",
             "pasta": f"{MODELOS}/air-game-kids-astronautas",
             "artes": "ferramentas/modelos3d/air-game-kids-astronautas/adesivos",
             # a capa do produto (o card do catálogo) é a do adesivo padrão
             "extras": {"capa": (f"{CAPAS}/air-game-kids.webp",)}},
        ),
        "tomadas": {
            "capa": {"giro": -32, "camera": 1.55, "saida": CAPA},
            "frente": {"giro": 30, "camera": 1.7, "saida": VISTA},
            "lado_direito": {"giro": -8, "camera": 1.25, "saida": VISTA},
            # na altura das crianças
            "lado_esquerdo": {"giro": 150, "camera": 1.0, "saida": VISTA},
            "verso": {"giro": 72, "camera": 1.35, "saida": VISTA},
            # o tampo, do alto: o campo, os rebatedores e o logotipo (de pé: pelo lado de lá)
            "tampo": {"giro": 180, "camera": 3.1, "saida": VISTA, "margem": 0.05},
            "capa_noite": {"giro": -32, "camera": 1.55, "saida": CAPA, "luz": "noite", "so_mestre": True},
        },
    },
    # ------------------------------------------------------------------
    # STRIKE KIDS (o Boliche Kids)
    # ------------------------------------------------------------------
    "strike-kids": {
        "nome": "Strike Kids",
        # o cadastro (core/cadastro_modelos.py): 2,07 x 0,74 x 1,91 m
        "medidas": (2.07, 0.74, 1.91),
        "frente": 0,
        "variantes": (
            {"chave": "padrao", "nome": None, "glb": f"{MODELOS}/strike-kids.glb", "pasta": f"{MODELOS}/strike-kids",
             "artes": "ferramentas/modelos3d/strike-kids/adesivos"},
        ),
        "tomadas": {
            "capa": {"giro": -36, "camera": 1.6, "saida": CAPA},
            # a capa espelhada (pelo lado esquerdo) com o estúdio apagado: os LEDs, a tela e o neon acesos
            "tres_quartos_esquerda": {"giro": 36, "camera": 1.6, "saida": QUADRADA, "luz": "noite"},
            "frente": {"giro": 0, "camera": 1.55, "saida": QUADRADA},
            # os dois lados são a mesma arte espelhada: de pontos diferentes (o direito puxando para
            # a frente, o esquerdo para trás e mais baixo), senão um é o espelho do outro -- e o site
            # recusa a vista repetida (core.conferir_fotos)
            "lado_direito": {"giro": -66, "camera": 1.5, "saida": QUADRADA},
            "lado_esquerdo": {"giro": 112, "camera": 1.2, "saida": QUADRADA},
            "verso": {"giro": 146, "camera": 1.7, "saida": QUADRADA},
            # de frente e do alto: a pista inteira até a tela
            "de_cima": {"giro": -18, "camera": 3.7, "saida": QUADRADA},
            # o recorte sem fundo (para as artes; só o painel mostra)
            "foto": {"giro": -36, "camera": 1.6, "saida": QUADRADA, "transparente": True},
            # a própria capa com o estúdio apagado
            "capa_noite": {"giro": -36, "camera": 1.6, "saida": CAPA, "luz": "noite", "so_mestre": True},
        },
    },
}


def arquivos_do_site():
    """[(produto, variante, tomada, caminho no repositório)] de toda foto que o estúdio grava no site."""
    saida = []
    for chave, produto in PRODUTOS.items():
        for variante in produto["variantes"]:
            if "glb" in variante:
                for tomada, dados in produto["tomadas"].items():
                    if dados.get("so_mestre"):
                        continue
                    saida.append((chave, variante["chave"], tomada, f"{variante['pasta']}/{tomada}.webp"))
                for tomada, caminhos in variante.get("extras", {}).items():
                    for caminho in caminhos:
                        saida.append((chave, variante["chave"], tomada, caminho))
            else:
                for tomada, caminho in variante.get("fotos", {}).items():
                    saida.append((chave, variante["chave"], tomada, caminho))
    return saida
