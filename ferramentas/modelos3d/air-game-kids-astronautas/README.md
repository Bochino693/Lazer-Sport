# Air Game Kids (Astronautas) — o objeto 3D

O `.glb` dos astronautas que o Air Game Kids usa
(`core/static/site/arena/modelos/air-game-kids-astronautas.glb`), ao lado do
dos Alienígenas: o MESMO móvel (o produto é um só, com os dois adesivos —
LEIA-ME, seção 72). O cliente: "EU QUERO OS DOIS OBJETOS 3D, NO MESMO
BRINQUEDO".

## De onde vem cada adesivo

O Air Game Kids dos astronautas tem UMA foto no catálogo
(`foto-do-catalogo.png`, 433 x 577, de 3/4) e não tem a folha de adesivos da
fábrica. Então:

| Peça           | De onde |
|----------------|---------|
| as duas laterais | a lateral que a foto mostra, **desentortada pela perspectiva** (`desentortar.py`: o contorno da lateral da folha dos Alienígenas encaixado na silhueta da foto, 0,7 px de erro médio). A do outro lado é a mesma arte (as laterais da folha da fábrica são iguais): vista de fora, o espelho da primeira |
| as cabeceiras  | o azul do espaço da própria foto, os dois planetas dos cantos dela (o amarelo e o laranja) e o logotipo do produto (o círculo "Air Hockey Espacial Kids" da lateral) |
| o tampo        | o do Alienígenas (o campo, as linhas e os gols, que são da mesa), com o chão lunar laranja trocado pelos planetas da foto, o logotipo do produto no meio e sem as marquinhas "HOCKEY KIDS" das pontas |

Nenhum personagem novo: só pedaços da foto. Quando chegar a folha de
adesivos dos astronautas (como a 26567-1 dos Alienígenas) ou fotos do tampo,
do outro lado e das cabeceiras, refaça pelo caminho do Alienígenas
(`../air-game-kids-alienigenas/`) e o 3D fica igual à mesa de verdade.

## Refazer

    python3 desentortar.py      # lateral-desentortada.png (e previa-contorno.png)
    python3 texturas.py         # adesivos/*.png (e previa-pecas.png)
    python3 ../ampliar_adesivos.py . --reduzir 0.5   # adesivos-hd/ (4x a resolução de origem, nítido)
    node ../gerar_glb.cjs air-game-kids-alienigenas --arte astronautas --saida air-game-kids-astronautas.glb

O móvel é o do Alienígenas, o MESMO `montar.js` (`?arte=astronautas`: as artes
desta pasta, a mesma geometria e a mesma medida: LEIA-ME V10, seção 91). As
artes daqui já vinham ampliadas 2x com suavização: o `--reduzir 0.5` as volta
à resolução de origem antes do Real-ESRGAN. 0,90 × 0,86 × 1,51 m, ~17 mil
triângulos, ~1,9 MB.

## No site

A 0166 (`core/variantes.py`, `unificar`) liga este .glb ao Air Game Kids
(`ObjetoTresD`, código `air-game-kids-astronautas`) quando ele não tem 3D. O
dos Alienígenas continua na ficha dele; os dois aparecem no produto, com o
controle "Adesivo: Astronautas · Alienígenas" em toda área 3D.
