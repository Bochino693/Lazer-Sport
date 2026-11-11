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
  * BRINQUEDÃO MODELO 5: o L pequeno de tubos cor de madeira (3,70 m × 1 m),
    das quatro imagens do projeto; a galeria leva as vistas do 3D e as
    imagens da fábrica (ver `ferramentas/modelos3d/brinquedao-modelo-5/`);
  * ESPAÇO ESPORTIVO MODELO 1: o trampo.3ds do parque de trampolins, as
    plantas do parque e das quadras e as imagens do espaço completo (ver
    `ferramentas/modelos3d/espaco-esportivo-modelo-1/`). As fotos dele são
    vistas do próprio objeto 3D, com o fundo claro do catálogo.
  * STRIKE KIDS (o boliche kids): o .glb da máquina com a adesivagem de
    verdade (laterais, testeira, tela, pista e frente), feito para a
    fábrica. É o PRIMEIRO objeto 3D ligado pelo cadastro (`ObjetoTresD`):
    se o brinquedo já está no catálogo (com as fotos reais), só ganha o
    objeto; se não está, entra com as fotos tiradas do próprio 3D.
  * AIR GAME KIDS ALIENÍGENAS e BASQUETE STREET QUADRINHOS: as máquinas de
    sempre (a `base`: o Air Game Kids e o Basquete Street) com os adesivos
    novos; o cadastro copia da base o preço, a voltagem, a loja, as
    medidas, as categorias e as tags (ver `ferramentas/modelos3d/<id>/`).
    O Air Game Kids Alienígenas se chamava "Air Game Hockey Espacial" (com
    o Air Game Hockey de base): a 0146 renomeia o que a 0145 cadastrou.

Quem cadastra:
  * as migrações de dados (`0113_brinquedao_modelo_2`,
    `0114_espaco_esportivo_modelo_1`, `0140_brinquedao_ninja`,
    `0142_brinquedao_modelo_4`, `0145_variantes_de_adesivo`,
    `0151_brinquedao_modelo_5`,
    `0146_air_game_kids_alienigenas`...), no deploy
    do Render (o migrate roda sozinho no Pre-Deploy Command): o brinquedo
    já entra no catálogo;
  * `python manage.py cadastrar_modelo_3d <id>` (ou
    `cadastrar_variantes_adesivo`, as duas variantes), se a migração não
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
            ("capa.webp", "perfil", "Brinquedão Modelo 2 montado num buffet infantil, com a criançada brincando em volta (projeto ilustrativo)"),
            ("frente.webp", None, "Brinquedão Modelo 2 visto de frente"),
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
            ("capa.webp", "perfil", "Brinquedão Ninja montado no galpão de um parque indoor, com a criançada em volta (projeto ilustrativo)"),
            ("frente.webp", None, "Brinquedão Ninja visto de frente: o andar de cima com os obstáculos, a piscina de cubos e o tobogã"),
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
            ("capa.webp", "perfil", "Espaço Esportivo Modelo 1 montado num galpão, visto do alto, com a criançada nas quadras e nas camas elásticas (projeto ilustrativo)"),
            ("frente.webp", None, "Espaço Esportivo Modelo 1 visto de frente: quadras, parque de trampolins e circuito kids"),
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
            ("capa.webp", "perfil", "Strike Kids numa game zone, com os pinos no chão e uma criança comemorando (ilustração)"),
            ("foto.webp", None, "Strike Kids, o boliche infantil, com a tela, a pista e a arte dos pinos"),
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
            ("capa.webp", "perfil", "Trampolim de Enterrada numa quadra, com crianças pulando nas camas (projeto ilustrativo)"),
            ("frente.webp", None, "Trampolim de Enterrada visto de frente: as três camas, a parede com a cesta e a escada"),
            ("lado_esquerdo.webp", "lado_esquerdo", "Trampolim de Enterrada visto pelo lado da cesta"),
            ("lado_direito.webp", "lado_direito", "Trampolim de Enterrada visto pelo lado da escada, com a pista até a cesta"),
            ("planta.webp", None, "Trampolim de Enterrada visto de cima: 6 m por 2 m"),
            ("espuma.webp", None, "A variante com a piscina de cubos de espuma no lugar da cama do meio"),
        ),
        "categorias": ("trampolim", "cama elastica", "camas elasticas"),
        "evitar": (),
    },
    # ---- Brinquedão Modelo 3 ----
    # O brinquedão em L feito com as três imagens do projeto (a frente, a
    # planta e a perspectiva; não há .3ds: ver
    # `ferramentas/modelos3d/brinquedao-modelo-3/`). As fotos são vistas do
    # próprio objeto 3D, com o fundo claro do catálogo; quando chegarem as do
    # projeto, troque os .webp da pasta e rode o comando com `--fotos`.
    # A migração que cadastra no deploy é a `0143_brinquedao_modelo_3`.
    "brinquedao-modelo-3": {
        "nome": "Brinquedão Modelo 3",
        "pasta": MODELOS / "brinquedao-modelo-3",
        "objeto_3d": "site/arena/modelos/brinquedao-modelo-3.glb",
        "descricao": (
            "Brinquedão Modelo 3, de dois andares em L: 10 m de comprimento, 5,20 m de fundo (a barra de 2 m "
            "encostada no fundo e a perna de 1 m que avança na frente) e 3,75 m de altura. Entrada pela torre da "
            "frente, com plataformas em zigue-zague e redes em onda, e passarela de rede até o andar de cima "
            "(a 1,90 m): corredor de cunhas de espuma, rolos, piso de rede, bola-pêndulo, sacos de pancada e "
            "balanço. Embaixo, três barraquinhas de faz-de-conta (máquina de prêmios, padaria e cozinha), um "
            "fliperama em cubo e uma mesa de fliperama. Na ponta direita, tobogã em espiral de tubo fechado até "
            "a piscina de bolinhas, com escadinha de espuma. Estrutura em tubos brancos com telas de proteção. "
            "Projeto ilustrativo: cores, painéis e itens podem ser ajustados conforme o espaço e a "
            "disponibilidade de materiais."
        ),
        "medidas": ("3.75", "10.00", "5.20"),
        "fotos": (
            ("capa.webp", "perfil", "Brinquedão Modelo 3 montado numa game zone, com a criançada brincando em volta (projeto ilustrativo)"),
            ("frente.webp", None, "Brinquedão Modelo 3 visto de frente: a torre, as barraquinhas, o andar de cima e o tobogã"),
            ("lado_esquerdo.webp", "lado_esquerdo", "Brinquedão Modelo 3 visto pelo lado da torre e da passarela de rede"),
            ("lado_direito.webp", "lado_direito", "Brinquedão Modelo 3 visto pelo lado do tobogã em espiral e da piscina de bolinhas"),
            ("planta.webp", None, "Planta do Brinquedão Modelo 3 vista de cima: o L de 10 m por 5,20 m"),
        ),
        "categorias": ("brinquedao", "brinquedoes", "playground", "kid play", "kids play"),
        "evitar": (),
    },
    # ---- Brinquedão Modelo 5 ----
    # O brinquedão pequeno de tubos cor de madeira em L, feito com as quatro
    # imagens do projeto (não há .3ds: ver `ferramentas/modelos3d/brinquedao-modelo-5/`).
    # A galeria leva as vistas do 3D (a frente, os dois lados e a perspectiva)
    # e as quatro imagens da fábrica (a perspectiva, que é a principal, a
    # planta e as duas do salão). A migração que cadastra no deploy é a
    # `0151_brinquedao_modelo_5`.
    "brinquedao-modelo-5": {
        "nome": "Brinquedão Modelo 5",
        "pasta": MODELOS / "brinquedao-modelo-5",
        "objeto_3d": "site/arena/modelos/brinquedao-modelo-5.glb",
        "descricao": (
            "Brinquedão Modelo 5, o playground de tubos redondos cor de madeira em L, para espaços menores: "
            "3,70 m de comprimento, 1 m de profundidade na barra (2,48 m com a perna e o escorregador) e 2 m de "
            "altura, com o piso de cima a 1 m.\n"
            "\n"
            "Sobe-se pelo 4º módulo: do piso azul do térreo para o degrau triangular e dele para o andar de cima "
            "(ou pela escada de tubos da ponta). Em cima, quatro módulos com piso de espuma: dois sacos de pancada "
            "(laranja e amarelo) para atravessar, a cunha azul para passar por cima e, na frente, as casinhas rosa "
            "e azul-clara com o telhado branco e a janela em arco, e o painel rosa com a fresta de janela alta. "
            "Embaixo, quatro rolos de espuma pendurados (rosa, amarelo, azul e laranja) para atravessar. A descida "
            "é pelo escorregador amarelo largo, de bordas arredondadas, que sai da perna da frente, sob o "
            "telhadinho de tubos.\n"
            "\n"
            "Estrutura em tubos redondos com cantos arredondados. Ideal para buffets infantis, brinquedotecas, "
            "restaurantes, condomínios e espaços kids. Projeto ilustrativo: cores, painéis e itens podem ser "
            "ajustados conforme o espaço e a disponibilidade de materiais."
        ),
        "medidas": ("2.00", "3.70", "1.00"),
        "fotos": (
            ("salao_frente.webp", "perfil", "O Brinquedão Modelo 5 montado num salão, visto de frente (projeto ilustrativo)"),
            ("perspectiva.webp", None, "Brinquedão Modelo 5 em perspectiva: as casinhas, os sacos, os rolos e o escorregador"),
            ("frente.webp", None, "Brinquedão Modelo 5 visto de frente, com 2 m de altura e o piso a 1 m"),
            ("lado_esquerdo.webp", "lado_esquerdo", "Brinquedão Modelo 5 visto pelo lado do escorregador"),
            ("lado_direito.webp", "lado_direito", "Brinquedão Modelo 5 visto pelo lado do degrau triangular de entrada"),
            ("perspectiva_3d.webp", None, "Brinquedão Modelo 5 em 3D, do mesmo ponto da perspectiva do projeto"),
            ("planta.webp", None, "Planta do Brinquedão Modelo 5 vista de cima: 3,70 m por 1 m, altura de 2 m"),
            ("salao_esquerda.webp", None, "O Brinquedão Modelo 5 montado num salão, visto pela esquerda (projeto ilustrativo)"),
        ),
        "categorias": ("brinquedao", "brinquedoes", "playground", "kid play", "kids play"),
        "evitar": (),
    },
    # ---- As máquinas de sempre com os adesivos novos ----
    # A MESMA máquina de um brinquedo do catálogo (a `base`, pelo nome
    # inteiro), só com outra adesivagem (ver `ferramentas/modelos3d/<id>/`). O
    # cadastro novo copia da base o preço, a voltagem, o "exibir na loja", a
    # avaliação, as medidas, as categorias e as tags; a descrição é a daqui
    # (fala da arte nova). Sem a base no catálogo, entra como os outros: as
    # medidas daqui (as do 3D, tiradas da folha de adesivos), as categorias
    # pelo nome, sem preço e fora da loja (confira no painel). As fotos são
    # vistas do próprio 3D, com a arte de verdade (a folha de adesivos da
    # fábrica). A migração que cadastra no deploy é a `0145_variantes_de_adesivo`;
    # `antes`: a chave e o nome de antes de uma variante renomeada (a
    # `0146_air_game_kids_alienigenas` passa o cadastro antigo para o novo).
    "air-game-kids-alienigenas": {
        # o Air Game Kids (a mesa infantil de formato recortado, 0,90 x 0,86 x
        # 1,50 m) com os adesivos dos alienígenas. Até a 0146 era o "Air Game
        # Hockey Espacial", com o Air Game Hockey de base: a folha de adesivos
        # é a do Air Game Kids (as proporções batem com as medidas dele)
        "nome": "Air Game Kids Alienígenas",
        "base": ("Air Game Kids",),
        "antes": {"air-game-hockey-espacial": "Air Game Hockey Espacial"},
        # o nome de antes também acha o brinquedo (um "Air Game Hockey Espacial
        # (mesa)" do painel, que a 0145 ligou, segue ligado e não ganha um irmão)
        "nomes": ("Air Game Kids Alienígenas", "Air Game Hockey Espacial"),
        "pasta": MODELOS / "air-game-kids-alienigenas",
        "objeto_3d": "site/arena/modelos/air-game-kids-alienigenas.glb",
        "descricao": (
            "O Air Game Kids Alienígenas é o Air Game Kids, a nossa mesa de air hockey infantil de formato "
            "recortado, com a adesivagem dos alienígenas: no centro do tampo, o logotipo HOCKEY KIDS com um "
            "alienígena verde, o campo branco com o chão lunar laranja e as crateras em volta, e o Jogador 01 e o "
            "Jogador 02 nas cabeceiras; nas laterais recortadas, os alienígenas astronautas jogando hóquei, o "
            "disco voador, planetas, estrelas e o HOCKEY KIDS; nas cabeceiras, o disco voador sobre o chão lunar.\n"
            "\n"
            "Dois jogadores disputam cada ponto rebatendo o disco que desliza sobre o colchão de ar, atacando e "
            "defendendo o próprio gol. Partidas rápidas, que estimulam reflexo, coordenação motora e concentração.\n"
            "\n"
            "Medidas aproximadas: 0,90 m de altura, 0,86 m de largura e 1,50 m de comprimento.\n"
            "\n"
            "Ideal para buffets infantis, brinquedotecas, parques, shoppings, hotéis, condomínios e áreas kids."
        ),
        # as do Air Game Kids do catálogo (o 3D, feito da folha na altura de 0,90 m,
        # tem 0,83 x 1,51 m: os 0,86 m contam a borda)
        "medidas": ("0.90", "0.86", "1.50"),
        "fotos": (
            ("capa.webp", "perfil", "Air Game Kids Alienígenas num buffet infantil, com crianças jogando (ilustração)"),
            ("frente.webp", None, "Air Game Kids Alienígenas: a mesa de air hockey com os alienígenas e o logotipo HOCKEY KIDS"),
            ("lado_esquerdo.webp", "lado_esquerdo", "Air Game Kids Alienígenas pelo lado esquerdo: os alienígenas astronautas no chão lunar"),
            ("lado_direito.webp", "lado_direito", "Air Game Kids Alienígenas pelo lado direito"),
            ("verso.webp", "verso", "Air Game Kids Alienígenas visto pela outra cabeceira"),
            ("tampo.webp", None, "O tampo do Air Game Kids Alienígenas visto de cima: o campo, o chão lunar e o HOCKEY KIDS"),
        ),
        "categorias": ("eletronic",),
        "evitar": (),
    },
    "basquete-street-quadrinhos": {
        # o gabinete do Basquete Home (a testeira em hexágono, o console com o
        # POW!, a lateral subindo atrás dele: LEIA-ME 61) com os adesivos em
        # quadrinhos. Até a seção 72 era o "Basquete Street Quadrinhos", com o
        # Basquete Street de base; a chave (os arquivos) ficou a mesma
        "nome": "Basquete Home Quadrinhos",
        "base": ("Basquete Home",),
        # o nome de antes também acha o brinquedo (a 0160 o renomeia: core.variantes.RENOMEADAS)
        "nomes": ("Basquete Home Quadrinhos", "Basquete Street Quadrinhos"),
        "pasta": MODELOS / "basquete-street-quadrinhos",
        "objeto_3d": "site/arena/modelos/basquete-street-quadrinhos.glb",
        "descricao": (
            "O Basquete Home Quadrinhos é o Basquete Home, o basquete de arcade do gabinete com a testeira em "
            "hexágono, com a adesivagem nova em estilo história em quadrinhos: fundo preto com formas arredondadas em amarelo, "
            "laranja, vermelho e rosa; nas laterais de fora, a bola de basquete grande e duas crianças jogando com "
            "o balão BASKETBALL; o \"BOOM!\" e a janela do placar no fundo da cesta, o \"POW!\" na frente e no teto "
            "interno, o \"WOW!\", o letreiro BASKETBALL na testeira e na frente, e a quadra de basquete com as "
            "linhas vermelhas no chão da pista.\n"
            "\n"
            "A rampa leva as bolas até o jogador, que arremessa na cesta para somar pontos antes de o tempo "
            "acabar.\n"
            "\n"
            "Ideal para residências, condomínios, salões de festas, buffets, escolas e áreas de lazer."
        ),
        "medidas": ("2.70", "1.00", "2.40"),
        "fotos": (
            ("capa.webp", "perfil", "Basquete Home Quadrinhos no showroom da Lazer & Sport"),
            ("frente.webp", None, "Basquete Home Quadrinhos: o console com o POW!, a pista e a testeira BASKETBALL"),
            ("lado_esquerdo.webp", "lado_esquerdo", "Basquete Home Quadrinhos pelo lado esquerdo: a bola grande e as crianças jogando"),
            ("lado_direito.webp", "lado_direito", "Basquete Home Quadrinhos pelo lado direito"),
            ("verso.webp", "verso", "Basquete Home Quadrinhos visto por trás"),
            ("jogador.webp", None, "Basquete Home Quadrinhos visto de quem joga: a cesta, o BOOM! e o console"),
        ),
        "categorias": ("eletronic",),
        "evitar": (),
    },
}

#: As máquinas que são outra adesivagem de um brinquedo do catálogo (têm `base`).
VARIANTES_DE_ADESIVO = tuple(chave for chave, dados in CADASTROS.items() if dados.get("base"))

#: As chaves de antes (o `antes` dos cadastros), que as migrações antigas ainda
#: usam: a 0145 cadastrava o "air-game-hockey-espacial", que virou o Air Game
#: Kids Alienígenas. Rodando hoje (num banco novo), a 0145 já cadastra o novo;
#: a 0146 renomeia o que ela cadastrou antes.
APELIDOS = {antiga: chave for chave, dados in CADASTROS.items() for antiga in dados.get("antes", {})}


def _chave(chave):
    """A chave de hoje (a de antes de uma variante renomeada vira a nova)."""
    return APELIDOS.get(chave, chave)


def achar_base(chave, Brinquedos):
    """O brinquedo do catálogo que é a MESMA máquina da variante `chave` (a `base`), ou None.

    Pelo nome inteiro, sem acento nem maiúscula: "BASQUETE HOME" é a base
    do Basquete Home Quadrinhos; o próprio Basquete Home Quadrinhos (ou
    outro "Basquete Home Kids") não é. O ativo vem antes do desativado.
    """
    nomes = {_normalizar(n) for n in CADASTROS[_chave(chave)].get("base", ())}
    if not nomes:
        return None
    return next(
        (b for b in Brinquedos.objects.order_by("-ativo", "id") if _normalizar(b.nome_brinquedo or "") in nomes),
        None,
    )


def _categorias_pelo_nome(dados, CategoriasBrinquedos):
    """As categorias que servem pelo nome (`categorias`, sem as de `evitar`); nenhuma é criada."""
    candidatas = [
        c for c in CategoriasBrinquedos.objects.all()
        if any(trecho in _normalizar(c.nome_categoria) for trecho in dados["categorias"])
    ]
    preferidas = [c for c in candidatas if not any(t in _normalizar(c.nome_categoria) for t in dados["evitar"])]
    return preferidas or candidatas


def _campos_da_base(base):
    """O que a variante copia da máquina de antes (a `base`): preço, avaliação, loja, voltagem e medidas."""
    campos = {
        "valor_brinquedo": base.valor_brinquedo,
        "avaliacao": base.avaliacao,
        "exibir_na_loja": base.exibir_na_loja,
        "voltz": base.voltz or "",
    }
    if None not in (base.altura_m, base.largura_m, base.profundidade_m):
        campos.update(altura_m=base.altura_m, largura_m=base.largura_m, profundidade_m=base.profundidade_m)
    return campos


def cadastrar(chave, Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, refazer_fotos=False, avisar=print):
    """Cria o brinquedo com as fotos. Devolve (brinquedo, criado).

    Recebe os modelos para servir às migrações (modelos históricos) e ao
    comando (os de verdade). A variante de adesivo (com `base`) copia da
    máquina de antes o que é da máquina: preço, voltagem, loja, avaliação,
    medidas, categorias e tags.
    """
    chave = _chave(chave)
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
            campos = {
                "nome_brinquedo": nome,
                "descricao": dados["descricao"],
                "valor_brinquedo": None,
                "avaliacao": Decimal("5.00"),
                "exibir_na_loja": False,
                "voltz": "",
                "altura_m": altura,
                "largura_m": largura,
                "profundidade_m": profundidade,
            }
            base = achar_base(chave, Brinquedos) if dados.get("base") else None
            if base is not None:
                campos.update(_campos_da_base(base))
            brinquedo = Brinquedos.objects.create(**campos)
            categorias = list(base.categorias_brinquedos.all()) if base is not None else []
            if not categorias:
                categorias = _categorias_pelo_nome(dados, CategoriasBrinquedos)
            brinquedo.categorias_brinquedos.set(categorias)
            avisar(f"Criado: {nome} (id {brinquedo.pk}).")
            if base is not None:
                brinquedo.tags.set(base.tags.all())
                avisar(f"Copiado de {base.nome_brinquedo} (id {base.pk}): preço, voltagem, loja, avaliação, medidas, "
                       "categorias e tags.")
            elif dados.get("base"):
                avisar(f"{dados['base'][0]} não está no catálogo: confira preço, voltagem e loja no painel.")
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
    dados = CADASTROS[_chave(chave)]
    trechos = [_normalizar(t) for t in dados.get("nomes", ()) or (dados["nome"],)]
    for brinquedo in Brinquedos.objects.filter(ativo=True).order_by("id"):
        nome = _normalizar(brinquedo.nome_brinquedo or "")
        if any(trecho in nome for trecho in trechos):
            return brinquedo
    return None


def ligar_objeto_3d(chave, brinquedo, ObjetoTresD):
    """Liga o objeto 3D do site ao brinquedo (cria ou atualiza; não duplica)."""
    from .objetos_3d import ler_glb_do_site

    chave = _chave(chave)
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
    chave = _chave(chave)

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
            # a capa de hoje é a primeira foto do cadastro (a cena da 0153; antes, foto.webp):
            # com a capa de antes, as fotos são refeitas
            capa = Path(dados["fotos"][0][0]).stem
            fotos_daqui = f"strike-kids-{capa}" in (brinquedo.imagem_brinquedo.name or "")
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
    chaves = tuple(_chave(chave) for chave in chaves)

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


def renomear_variante(chave_antiga, nome_antigo, Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, ObjetoTresD,
                      avisar=print):
    """Passa o cadastro de uma variante renomeada (`chave_antiga`, `nome_antigo`) para a de hoje.

    A da 0146: o "Air Game Hockey Espacial" que a 0145 cadastrou (copiando o
    Air Game Hockey) é o Air Game Kids Alienígenas. Só mexe no banco:
      * o brinquedo com o nome antigo (o nome inteiro, sem acento nem
        maiúscula) ganha o nome novo e a descrição daqui -- se nenhum outro já
        tem o nome novo (aí fica como está, com um aviso);
      * da base de hoje (`achar_base`), como no cadastro: preço, avaliação,
        loja, voltagem, medidas, categorias e tags. Sem a base no catálogo, as
        medidas daqui; o resto fica como está (confira no painel);
      * nas descrições das fotos, o nome novo no lugar do antigo;
      * o objeto 3D de antes (o `codigo` antigo ou o .glb antigo, que não
        existe mais) passa para o .glb e o código de hoje, com as cores e as
        medidas lidas do .glb novo.
    Devolve os brinquedos renomeados. Rodar de novo não faz nada.
    """
    from .objetos_3d import ler_glb_do_site

    chave = _chave(chave_antiga)
    dados = CADASTROS[chave]
    nome = dados["nome"]
    alvo = _normalizar(nome_antigo)
    antigos = [b for b in Brinquedos.objects.order_by("-ativo", "id") if _normalizar(b.nome_brinquedo or "") == alvo]
    base = achar_base(chave, Brinquedos) if antigos else None
    renomeados = []
    for brinquedo in antigos:
        if Brinquedos.objects.filter(nome_brinquedo=nome).exists():
            avisar(f"{brinquedo.nome_brinquedo} (id {brinquedo.pk}) ficou com o nome: já há um {nome} no catálogo "
                   "(confira no painel).")
            continue
        if base is not None:
            campos = _campos_da_base(base)
        else:
            altura, largura, profundidade = (Decimal(v) for v in dados["medidas"])
            campos = {"altura_m": altura, "largura_m": largura, "profundidade_m": profundidade}
        campos.update(nome_brinquedo=nome, descricao=dados["descricao"])
        for campo, valor in campos.items():
            setattr(brinquedo, campo, valor)
        brinquedo.save(update_fields=list(campos))
        if base is not None:
            categorias = list(base.categorias_brinquedos.all())
            if categorias:
                brinquedo.categorias_brinquedos.set(categorias)
            brinquedo.tags.set(base.tags.all())
        for imagem in ImagemBrinquedo.objects.filter(brinquedo=brinquedo):
            texto = imagem.texto_alternativo or ""
            if nome_antigo in texto:
                imagem.texto_alternativo = texto.replace(nome_antigo, nome)
                imagem.save(update_fields=["texto_alternativo"])
        renomeados.append(brinquedo)
        avisar(f"Renomeado: {nome_antigo} -> {nome} (id {brinquedo.pk}); " + (
            f"copiado de {base.nome_brinquedo} (id {base.pk}): preço, voltagem, loja, avaliação, medidas, "
            "categorias e tags." if base is not None
            else f"{dados['base'][0]} não está no catálogo: confira preço, voltagem e loja no painel."
        ))

    caminho = dados["objeto_3d"]
    antigo = f"site/arena/modelos/{chave_antiga}.glb"
    objetos = ObjetoTresD.objects.filter(codigo=chave_antiga) | ObjetoTresD.objects.filter(arquivo_estatico=antigo)
    objetos = list(objetos.distinct())
    lido = ler_glb_do_site(caminho) if objetos else None
    for objeto in objetos:
        objeto.codigo = chave
        if objeto.arquivo_estatico == antigo:  # um .glb enviado pelo painel (`arquivo`) fica, e vence
            objeto.arquivo_estatico = caminho
            objeto.cores, objeto.medidas = lido["cores"], lido["medidas"]
        objeto.save(update_fields=["codigo", "arquivo_estatico", "cores", "medidas"])
        avisar(f"Objeto 3D de {objeto.brinquedo.nome_brinquedo} (id {objeto.brinquedo_id}): {chave}, {caminho}.")
    return renomeados


def fotos_do_cadastro(brinquedo, chave):
    """As fotos do brinquedo são as que o cadastro `chave` subiu (não as de alguém, pelo painel)?"""
    return f"{chave}-" in (brinquedo.imagem_brinquedo.name or "")


def migracao_renomear_variante(chave_antiga, nome_antigo):
    """A migração que passa uma variante renomeada para a de hoje (a 0146).

    Em todo lugar (só o banco): `renomear_variante`. Depois, no Render, o
    renomeado que ainda tem as fotos que o cadastro subiu (vistas do 3D de
    antes) ganha as fotos de hoje, que sobem para o Cloudinary. Por fim, a
    `migracao_objetos_3d` da chave nova: cadastra onde a 0145 cadastraria
    (no Render, se a máquina não está no catálogo) e só liga o 3D nos outros
    lugares. Se a subida falhar, o deploy segue e o comando refaz.
    """
    chave = _chave(chave_antiga)
    ligar = migracao_objetos_3d(chave)

    def renomear_no_deploy(apps, schema_editor):
        from django.conf import settings

        Brinquedos = apps.get_model("core", "Brinquedos")
        CategoriasBrinquedos = apps.get_model("core", "CategoriasBrinquedos")
        ImagemBrinquedo = apps.get_model("core", "ImagemBrinquedo")
        with transaction.atomic():
            renomeados = renomear_variante(
                chave_antiga, nome_antigo, Brinquedos, CategoriasBrinquedos, ImagemBrinquedo,
                apps.get_model("core", "ObjetoTresD"), avisar=print,
            )
        if getattr(settings, "IS_RENDER", False):
            for brinquedo in renomeados:
                if not fotos_do_cadastro(brinquedo, chave_antiga):
                    continue
                try:
                    with transaction.atomic():
                        cadastrar(chave, Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, refazer_fotos=True)
                except Exception as erro:  # o deploy segue; o comando refaz depois
                    print(f"As fotos de {brinquedo.nome_brinquedo} não foram refeitas agora ({erro}). "
                          f"Rode: python manage.py cadastrar_variantes_adesivo --so {chave} --fotos")
        ligar(apps, schema_editor)

    return renomear_no_deploy
