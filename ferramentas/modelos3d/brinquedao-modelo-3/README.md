# Brinquedão Modelo 3 — o objeto 3D

O `.glb` que a Arena 3D usa (`core/static/site/arena/modelos/brinquedao-modelo-3.glb`)
e as fotos do cadastro (`.../brinquedao-modelo-3/*.webp`) saem daqui. É UM
objeto: o brinquedão de dois andares em L, com a torre de entrada, a
passarela, o tobogã em espiral e a piscina de bolinhas.

## De onde vem cada parte

Não há `.3ds` da fábrica: tudo sai das três imagens do projeto que o
cliente mandou (não ficam no repositório). As medidas são as delas, em
módulos de 1 m.

1. **A planta** — o L: a barra de 10 m × 2 m encostada no fundo (10 colunas
   × 2 fileiras de módulos) e a perna de 1 m de largura que sai da ponta
   esquerda e avança 3,20 m na frente (5,20 m de fundo no total). O piso de
   cada módulo do 2º andar: atrás, magenta/laranja na diagonal, as ondas em
   listras (2 a 4), a rede azul quadriculada com a bola (5 a 7), os sacos
   (8), laranja/amarelo na diagonal (9) e amarelo (10); na frente, a rede
   da passarela (1), magenta (2), o corredor de cunhas com a faixa magenta
   no meio (3 a 7), magenta (8), amarelo com os dois sacos azuis (9) e a
   boca do tobogã (10). Na perna, a passarela de rede quadriculada azul e
   amarela e a torre de 1 m × 1 m com o piso de duas cores na diagonal.
2. **A vista de frente** — as alturas: o piso do 2º andar a 1,90 m, 1,85 m
   de pé-direito em cima, 3,75 m no total. Embaixo, as três barraquinhas de
   faz-de-conta com o toldo listrado bordô (a lilás com a máquina de
   prêmios, a de tijolinho amarelo da padaria e a azul-clara com a cortina
   rosa e o fogão azul), o fliperama roxo em cubo e a mesa de fliperama
   preta. Em cima, as cunhas de espuma sobre a base azul sob o painel
   magenta, a bola amarela pendurada, os cinco sacos de pancada e o balanço,
   o saco azul do 9º; na ponta direita, o painel amarelo com a janela
   redonda e o tobogã em espiral de tubo fechado, em gomos azul, magenta,
   amarelo e laranja, até a piscina de bolinhas com a escadinha amarela.
3. **A perspectiva** — a torre com as plataformas em degraus (amarela, azul,
   azul, amarela), as redes em onda acima dela e a passarela a ~1,9 m.

Os personagens das imagens (figuras de jogo e de filme) não entram: a arte
do fliperama e das telas é genérica (estrelas, planeta, disco voador, um
quebra-blocos de pixels), desenhada em `canvas` no `montar.js`.

Como as imagens foram lidas onde elas não fecham sozinhas:

- **A piscina de bolinhas e o tobogã ficam DENTRO da barra**, nos últimos
  2 m dela (x de 8 a 10 m), nos 2 m de fundo inteiros: a piscina de 2 m ×
  2 m no chão e a espiral descendo dentro dela, em volta da coluna do meio
  (o poste do tobogã). Em cima, nesses 2 m, só o módulo amarelo de trás
  (8 a 9 m, com os dois sacos azuis) tem piso: a boca do tobogã sai da
  beira dele, para a direita; a frente dos módulos 9 e 10 e o fundo do 10º
  são o vão da espiral (sem piso e sem as travessas que a cruzariam, com
  tela em volta). O painel da janela redonda fica no alto da ponta direita.
  A escadinha amarela de 2 degraus fica colada na frente da piscina (x de
  9,3 a 9,8 m) e é a única coisa que sai da frente da barra (35 cm): vista
  de cima, o objeto é exatamente o L de 10 m × 5,20 m. (Na primeira versão
  a piscina ficava na frente da barra; a planta cotada a põe dentro.)
- **O tobogã** dá 2,25 voltas na espiral mais a boca (≈ 2,5 voltas de
  frente). Tubo de 50 cm, espiral de 52 cm de raio em volta da coluna. Os
  primeiros 2/3 de volta são mais inclinados: quando a espiral passa por
  baixo do piso amarelo, o tubo já desceu o bastante (sobram ~11 cm até o
  piso, ~6 cm até as travessas e ~3 cm entre uma volta e a outra).
- **A escada da torre**: quatro plataformas em triângulo, alternando as
  metades da diagonal (0,45 m, 0,9 m, 1,4 m e 1,9 m). As duas de baixo são
  blocos de espuma branca: de frente, são os degraus brancos da vista.
- **As redes em onda**: três faixas de rede (azul, amarela, azul) com as
  beiras em onda, encaixadas em zigue-zague e curvadas para dentro, na
  frente e nos lados da torre, do 2º andar até o alto.
- **As barraquinhas** têm 1,5 m cada (o tamanho delas na vista de frente):
  as colunas da frente passam diante delas e o toldo tem um vão em cada
  coluna.
- Embaixo, os fliperamas vão até ~7,4 m; no 8º módulo o chão fica livre.

Medidas finais do objeto: 10 m × 5,20 m, altura 3,75 m (exatas: as colunas
de fora ficam para dentro da tampa); ~37,2 mil triângulos; ~565 KB depois do
`gltfpack`.

## Refazer

    npm install three@0.169.0 playwright gltfpack
    python3 -m http.server 8790 --bind 127.0.0.1     # nesta pasta, com o node_modules
    node gerar.cjs glb fotos                          # vistas v-*.jpg, fotos e o .glb
    npx gltfpack -i brinquedao-modelo-3.glb -o ../../../core/static/site/arena/modelos/brinquedao-modelo-3.glb -kn -km -ke

Com a porta 8790 ocupada: `python3 -m http.server 8791 ...` e
`PORTA=8791 node gerar.cjs ...`. O `fotos` grava as `foto-*.jpg` (a vista
inteira, para conferir) e as `.webp` do cadastro já recortadas no objeto, em
16:10 (1600 × 1000), direto na pasta do modelo no static. **São vistas do
próprio 3D**, até chegarem as fotos do projeto: aí é trocar os `.webp` e
rodar `python manage.py cadastrar_brinquedao_modelo_3 --fotos`. O
`node_modules`, o `.glb` sem o `gltfpack` e as vistas não vão para o git
(`.gitignore` desta pasta).

## Ligar no site

`core/arena.py`, `MODELOS_3D`: o objeto se liga à máquina pelo nome
("Brinquedão Modelo 3") e aparece na Arena mesmo antes do cadastro, na roda
dos brinquedões; no "Monte seu projeto" ele é um modelo pronto de
Brinquedão. O cadastro (`core/cadastro_modelos.py`, `CADASTROS`) com as
quatro fotos e o objeto 3D ligado sai sozinho no deploy, pela migração
`core/0143_brinquedao_modelo_3`; se ela não conseguir,
`python manage.py cadastrar_brinquedao_modelo_3`.

O passeio por dentro (`CAMINHOS["brinquedao-modelo-3"]` em
`core/static/site/arena/caminhos.js`) entra pela torre e sobe as plataformas,
atravessa a passarela de rede, o corredor de cunhas, o piso de rede sob a
bola, o balanço e os sacos, passa entre os sacos azuis do módulo amarelo,
desce o tobogã por dentro até a piscina, sai pela escadinha da frente e
termina olhando o brinquedão inteiro. Os pontos são escritos nas
coordenadas de trabalho do `montar.js` (mm): `M3` leva ao objeto
centralizado (o deslocamento que o `gerar.cjs` imprime) e o tobogã está nos
dois lugares (`TOBOGA` no `montar.js`, `toboganDoModelo3` na Arena). Os
testes: `core/tests_brinquedao_modelo_3.py`.
