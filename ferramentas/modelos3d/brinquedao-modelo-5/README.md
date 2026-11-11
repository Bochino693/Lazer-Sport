# Brinquedão Modelo 5 — o objeto 3D

O `.glb` que a Arena 3D usa (`core/static/site/arena/modelos/brinquedao-modelo-5.glb`)
e as fotos do 3D no cadastro (`.../brinquedao-modelo-5/frente.webp`,
`lado_esquerdo.webp`, `lado_direito.webp` e `perspectiva_3d.webp`) saem daqui.
É o brinquedão pequeno de tubos redondos cor de madeira, em L: a barra de
3,70 m × 1 m com quatro módulos, 2 m de altura, o piso a 1 m e, na ponta
esquerda, a perna com o escorregador saindo para a frente.

## De onde vem cada parte

Não há `.3ds` da fábrica: tudo sai das quatro imagens do projeto que o
cliente mandou, que também vão na galeria do produto (na pasta do modelo no
static): a planta cotada (`planta.webp`), a perspectiva sem fundo
(`perspectiva.webp`, a foto principal) e o brinquedão num salão, de frente e
pela esquerda (`salao_frente.webp`, `salao_esquerda.webp`). Os cavalinhos de
balanço e a mesinha do salão não são do produto e não entram.

1. **A planta** — 3,70 m × 1 m (por fora dos tubos), altura de 2 m. Os
   módulos medem 1 m, 1 m, 0,70 m e 1 m. Em cima, a grade de tubos: as
   pontas, as travessas entre os módulos e a dos sacos, no meio do 3º. O
   piso de cada módulo: azul (1º), amarelo com a faixa azul (2º: a cunha),
   amarelo com os dois sacos, o de trás amarelo e o da frente laranja (3º),
   e laranja com a linha da diagonal (4º). Na frente dos módulos 2 e 3, os
   quatro rolos (rosa, amarelo, azul e laranja, 14 cm). A perna do L: 0,62 m
   de largura, 0,86 m na frente da barra; o escorregador (0,48 m de largura
   por fora) vai da beira do piso até ~1,45 m na frente da barra.
2. **A perspectiva** — com a câmera dela calibrada (`calibrar.py`, abaixo)
   saem as medidas que a planta não dá:
   - o piso de cima a 1 m (os tubos de baixo dele a 1 m; a placa rente ao
     alto deles, a 1,04 m);
   - o telhado da perna: a frente dela é mais baixa (o tubo da frente a
     1,42 m) e os dois tubos inclinados sobem até o alto da barra; na frente
     da barra, entre eles, não há tubo em cima. Visto de lado, o módulo da
     esquerda tem a silhueta de casinha (a parede de trás de 2 m, o telhado
     inclinado na frente), mas é uma água só: não há cumeeira;
   - embaixo dos módulos 2 e 3 não há coluna entre eles: o piso de 1,70 m
     vai de uma coluna à outra e os rolos pendem na frente dele. A coluna ao
     lado da perna e a dos módulos 2/3 vão do piso para cima;
   - a faixa azul do 2º módulo é uma **cunha** de espuma (uma lombada de
     0,50 m de base e 0,38 m de altura, da frente até o fundo, com a
     cumeeira redonda no meio: a linha clara da planta), e não um
     escorregador: a cumeeira aparece pela janela rosa e pelo vão do 3º;
   - a "rampa" laranja do 4º módulo é um **degrau triangular**: a beira dela
     vai do fundo à esquerda até a frente à direita a 0,62 m o tempo todo
     (pela câmera calibrada, e na vista do salão é a "tábua" a ~0,6 m), e o
     terceiro canto também está a ~0,62 m. É a metade de trás e da direita
     do módulo; a outra metade (a da frente e da esquerda) é o piso de 1 m,
     outro triângulo laranja. É por isso que a planta mostra o módulo todo
     laranja com a linha da diagonal. Embaixo, o piso azul do térreo (num
     quadro de tubos a 0,1 m). Na ponta direita, os tubos a 0,1 m, 0,62 m e
     1 m fazem a escada de entrada;
   - os sacos: 0,22 m de diâmetro, de 1,24 m até ~1,85 m;
   - o escorregador: a beira das paredes sai rente ao piso e desce a ~32°;
     a saída quase plana a 0,17 m e as duas "orelhas" redondas (0,38 m)
     encostadas no chão; os dois tubos dos lados dele vão do piso até as
     colunas da frente da perna (a 0,47 m).
3. **As vistas do salão** — o mesmo, de frente: as duas casinhas (rosa no 2º
   módulo, azul-clara no 4º) com o telhado branco em V e a janela em arco
   branca com a cruz, o painel rosa estreito com a fresta alta (no 1º módulo,
   ao lado da perna), os rolos até 0,2 m do chão, o saco da frente e a beira
   do degrau triangular.

Medidas finais do objeto: 3,70 m × 2,48 m (a barra e a perna com o
escorregador), altura de 2 m (exatas: os tubos de fora ficam para dentro);
~28,4 mil triângulos; ~400 KB depois do `gltfpack`.

## A câmera da perspectiva (comparar lado a lado)

O `calibrar.py` (Python puro) acha a câmera da perspectiva da fábrica pelos
cantos da estrutura (o pixel de cada um e o ponto no `montar.js`): a DLT, e
a lente, a posição e os eixos dela, em `camera-perspectiva.json` (erro de
~2 px em média). O `gerar.cjs` desenha o objeto dessa câmera, no tamanho da
imagem (`v-projeto.png`): é só pôr ao lado da perspectiva (ou uma por cima
da outra) para conferir. Mudou um ponto? `python3 calibrar.py` de novo.

## Refazer

    npm install three@0.169.0 playwright gltfpack   # ou um link node_modules para um que já tenha
    python3 -m http.server 8790 --bind 127.0.0.1     # nesta pasta, com o node_modules
    node gerar.cjs glb fotos                          # vistas v-*, fotos e o .glb
    npx gltfpack -i brinquedao-modelo-5.glb -o ../../../core/static/site/arena/modelos/brinquedao-modelo-5.glb -kn -km -ke

Com a porta 8790 ocupada: `python3 -m http.server 8791 ...` e
`PORTA=8791 node gerar.cjs ...`. O Chromium sem placa de vídeo precisa do
SwiftShader (os argumentos já estão no `gerar.cjs`). O `fotos` grava as
`foto-*.jpg` (a vista inteira, para conferir) e as `.webp` do 3D, já
recortadas no objeto, em 16:10 (1600 × 1000), direto na pasta do modelo no
static. As quatro imagens da fábrica estão lá como vieram, só sem a faixa
branca de cima. O `node_modules`, o `.glb` sem o `gltfpack` e as vistas não
vão para o git (`.gitignore` desta pasta).

## Ligar no site

`core/arena.py`, `MODELOS_3D`: o objeto se liga à máquina pelo nome
("Brinquedão Modelo 5") e aparece na Arena mesmo antes do cadastro, na vaga
dos brinquedões da roda; no "Monte seu projeto" ele é um modelo pronto de
Brinquedão. O cadastro (`core/cadastro_modelos.py`, `CADASTROS`), fora da
loja, com as oito fotos (a perspectiva da fábrica de principal, as quatro
vistas do 3D, a planta e as duas do salão) e o objeto 3D ligado, sai sozinho
no deploy do Render, pela migração `core/0151_brinquedao_modelo_5`; se ela
não conseguir, `python manage.py cadastrar_brinquedao_modelo_5`.

O passeio por dentro (`CAMINHOS["brinquedao-modelo-5"]` em
`core/static/site/arena/caminhos.js`) chega pela ponta direita, sobe a
escada de tubos dela até o degrau triangular e dele para o piso de 1 m,
atravessa o 3º módulo abaixado entre os dois sacos, passa de gatinhas por
cima da cunha azul, desce o escorregador pela perna (os olhos 45 cm acima da
cama, no meio dela: a mesma curva do `ESC.eixo`) e, embaixo, olha os rolos e
o brinquedão inteiro. Os pontos são escritos nas coordenadas de trabalho do
`montar.js` (mm): `M5` leva ao objeto centralizado (o deslocamento que o
`gerar.cjs` imprime). O `core/tests_js/passeio.mjs` confere que os olhos
nunca chegam a menos de 10 cm de nada. Os testes:
`core/tests_brinquedao_modelo_5.py`.
