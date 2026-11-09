# Trampolim de Enterrada — o objeto 3D

O `.glb` que a Arena 3D usa (`core/static/site/arena/modelos/trampolim-enterrada.glb`),
a variante com a piscina de espuma (`trampolim-enterrada-espuma.glb`) e as fotos
do cadastro (`.../trampolim-enterrada/*.webp`) saem daqui.

## De onde vem cada parte

- **`trampolim.3ds` da fábrica** (1,1 MB, 832 objetos): só a estrutura de aço,
  em mm, com 5,50 m × 2,27 m × 2,98 m. O `extrair.py` guarda dele só as medidas
  (`estrutura.json`): as quatro colunas, o retângulo do quadro de tubos de cima
  (a 2,93 m), a base (1,0 m de altura, 2 m de fundo) com os três módulos das
  camas (1,85 m, 1,45 m e 1,45 m) e a linha da parede inclinada (do pé, na beira
  da primeira cama, até o alto da cabeceira). Parafusos, cantoneiras e a armação
  por dentro da base não entram: ficam cobertos pelo caixote e pelo estofado.
- **As imagens do projeto** (6 m × 2 m, altura 3,25 m; "projeto meramente
  ilustrativo"): o caixote cinza-escuro da base, as camas de lona grafite com a
  moldura e as divisórias amarelas, o estofado cinza da parede com a moldura
  amarela que desce até as camas, a cesta (aro laranja e rede branca), o quadro
  de cima amarelo com os cotovelos arredondados e a escada de espuma de três
  degraus com o tampo amarelo, no canto da frente da cabeceira oposta à cesta
  (no `.3ds` não há escada).
- **A variante** (`index.html?variante=espuma`): a cama do meio vira uma
  piscina de cubos de espuma, amarelos e cinza-escuros alternados.

O que ficou do `.3ds` e não das imagens: a altura (2,98 m no alto do quadro,
e não 3,25 m), a base a 1,0 m (as imagens sugerem uns 80 cm) e o fundo de
2,25 m com as colunas (a plataforma tem os 2 m). As colunas sobem até o meio
do cotovelo do canto, 2,6 cm para dentro de onde estão no `.3ds`.

Tudo junto: 6,01 m × 2,25 m, altura de 2,98 m; ~9,5 mil triângulos; ~135 KB
depois do `gltfpack` (a variante, ~170 KB). As camas levam a marca `lona`.

## Refazer

    python3 extrair.py caminho/do/trampolim.3ds      # estrutura.json
    npm install three@0.169.0 playwright gltfpack
    python3 -m http.server 8790 --bind 127.0.0.1     # nesta pasta, com o node_modules
    node gerar.cjs glb fotos                          # vistas v-*.jpg, fotos foto-*.jpg e o .glb
    node gerar.cjs glb fotos espuma                   # a variante
    npx gltfpack -i trampolim-enterrada.glb -o ../../../core/static/site/arena/modelos/trampolim-enterrada.glb -kn -km -ke
    npx gltfpack -i trampolim-enterrada-espuma.glb -o ../../../core/static/site/arena/modelos/trampolim-enterrada-espuma.glb -kn -km -ke

O `.3ds` original não fica no repositório: o que se usa dele está no
`estrutura.json`. As fotos `foto-*.jpg` (fundo claro, 1600 × 1000) viram os
`.webp` da pasta do modelo recortadas no objeto, em 16:10 (`foto-espuma-frente`
vira o `espuma.webp`). **São vistas do próprio 3D**, até chegarem as fotos do
projeto: aí é trocar os `.webp` e rodar `python manage.py cadastrar_trampolim_enterrada --fotos`.

## Ligar no site

`core/arena.py`, `MODELOS_3D`: liga pelo nome ("Trampolim de Enterrada"), na
área "Trampolins e brinquedões" (`grupo`; e em `REGRAS` o nome vira cama
elástica, e não basquete, por causa do "enterrada"). O passeio por dentro
(sobe a escada, pula nas três camas, enterra na cesta e volta) é o
`CAMINHOS["trampolim-enterrada"]` do `core/static/site/arena/arena3d.js`, com
os pontos em mm do `.3ds` (`TE` leva para o objeto centralizado; o
deslocamento sai do `gerar.cjs`). O cadastro com as fotos sai no deploy pela
migração `core/0139_trampolim_enterrada`; se ela não conseguir,
`python manage.py cadastrar_trampolim_enterrada`. A variante não se liga pelo
nome: para usá-la num cadastro, suba o `.glb` dela no painel (Objetos 3D).
