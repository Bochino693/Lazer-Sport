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

O móvel é o do Alienígenas: monte numa pasta de trabalho (`construir/`, fora
do repositório) com o `montar.js`, o `gerar.cjs`, o `formas.json` e o
`recortes.json` de `../air-game-kids-alienigenas/`; os `adesivos/*.png` daqui
(e o `lateral-esquerda.png` copiado também como `lateral-direita.png`); o
three.js de `core/static/vendor/three/` numa pasta `vendor/`, com o
`index.html` do Alienígenas apontando o importmap para ela; `NOME =
"air-game-kids-astronautas"` no `gerar.cjs` e `raiz.name` no `montar.js`.
Depois `python3 -m http.server 8790` nessa pasta, `node gerar.cjs glb` e o
`.glb` vai para `core/static/site/arena/modelos/`.

0,83 x 0,90 x 1,51 m (as do Alienígenas), ~6,7 mil triângulos, ~680 KB (sem
o `gltfpack`).

## No site

A 0166 (`core/variantes.py`, `unificar`) liga este .glb ao Air Game Kids
(`ObjetoTresD`, código `air-game-kids-astronautas`) quando ele não tem 3D. O
dos Alienígenas continua na ficha dele; os dois aparecem no produto, com o
controle "Adesivo: Astronautas · Alienígenas" em toda área 3D.
