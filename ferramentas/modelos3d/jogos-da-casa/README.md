# Lazer Shot e Boliche Virtual — os objetos 3D

Os `.glb` que a Arena 3D, a vitrine "Todas as máquinas" e a página do
brinquedo usam (`core/static/site/arena/modelos/lazer-shot.glb` e
`boliche-virtual.glb`) saem daqui. Não há projeto da fábrica dos gabinetes
(o .3ds ou as medidas de corte): eles são montados peça por peça em
three.js (`montar.js`) e vestidos com a ARTE REAL dos jogos:

* **Lazer Shot:** o letreiro e a mira do jogo, o pôster "Torne-se o melhor
  atirador" nas laterais e, na TV em pé, uma partida de verdade (o cenário
  do mar). A pistola personalizada fica no apoio e a câmera da foto do
  jogador em cima do letreiro (as duas faixas da página do brinquedo).
  Medidas: 2,32 m × 1,10 m × 0,95 m.
* **Boliche Virtual** (a máquina do Dragon Bowling): a pista com os trilhos
  de LED (a fita da placa `leds_boliche`), as bolas com START e CRÉDITO na
  frente e a torre com a TV em pé (a partida do Dragon Bowling, no
  strike) e o letreiro do dragão. Medidas do Dragon Bowling Rosa do
  catálogo: 2,38 m × 0,84 m × 3,21 m.

As texturas compostas (laterais, frente, letreiros) estão em `arte/`; elas
foram montadas com as artes de `bochino693/lazer-shot` e
`bochino693/dragonbowling1-android7.1`. As peças que não são adesivo
(`tela_video`, `led_*`, `metal_*`, `bola_*`, `pista`, `bolsao`) ficam como
estão quando o site troca a cor da máquina (`cores3d.js`).

Com fotos e medidas dos gabinetes de verdade, é só ajustar o perfil e as
caixas em `montar.js` e gerar de novo.

## Refazer

    npm install three@0.169.0 gltfpack
    python3 -m http.server 8790 --bind 127.0.0.1   # nesta pasta
    node gerar.cjs lazer-shot glb                  # vistas v-*.jpg e o .glb
    npx gltfpack -i lazer-shot.glb -o lazer-shot-q.glb -kn -km
    python3 -I rejpeg.py lazer-shot-q.glb ../../../core/static/site/arena/modelos/lazer-shot.glb 82 1024
    # e o mesmo com boliche-virtual (qualidade 80, lado 900)

As fotos do catálogo (`modelos/<máquina>/frente.webp`...) são as vistas
`v-*-dir34`, `lado_direito`, `lado_esquerdo` e `verso`, em WebP.
