# Air Game Kids Alienígenas — o objeto 3D

O `.glb` que a Arena 3D e a página do produto usam
(`core/static/site/arena/modelos/air-game-kids-alienigenas.glb`) e as fotos do
cadastro (`.../air-game-kids-alienigenas/*.webp`) saem daqui.

O Air Game Kids (a mesa de air hockey infantil de formato recortado do
catálogo, 0,90 × 0,86 × 1,50 m) com os adesivos dos alienígenas. **Tudo sai
da folha de adesivos da fábrica** (`folha-adesivos.webp`, a folha 26567-1,
guardada como veio): a arte de cada peça e o desenho dela. Nada da arte é
redesenhado, recolorido nem tirado: cada imagem vai inteira na sua face, e a
face tem a forma e a proporção da peça.

Conferido com a foto do Air Game Kids do catálogo (`/brinquedo/40/`): a forma
das laterais, os pés (os da própria lateral, sem tábua entre eles) e o tampo
entre elas batem com a folha. O que a mesa tem e a folha não desenha entrou:
a **fita de LED colorida na borda das laterais** (o contorno inteiro, menos o
pé que pisa no chão: uma faixa de 6 mm para fora da borda, na espessura da
lateral, com as cores correndo pelo contorno), a **régua das pontas preta**
(a de antes era azul), a **borda preta dos lados**, em cima do tampo,
encostada nas laterais (1,4 × 2,2 cm), e o **placar** branco no alto da
corcova, por dentro da lateral direita, com os dois pontos acesos. A face de
dentro das laterais fica pintada (a folha só traz o lado de fora).

Até a migração 0146 esta pasta era a `air-game-hockey-espacial` (o "Air Game
Hockey Espacial", com o Air Game Hockey de base e a mesa na altura de 1,00 m).
A folha é a do Air Game Kids: as proporções dela batem com as medidas dele, e
não com as do Air Game Hockey (2,10 × 1,10 m).

## As peças (a folha → adesivos/<peça>.png)

| Peça                 | Na folha             | Onde vai                                                             |
|----------------------|----------------------|----------------------------------------------------------------------|
| `tampo`              | Prancha tampo mesa   | o tampo, de cima: a cabeceira do "Jogador · 02" (a de trás) à esquerda da imagem, a do "Jogador · 01" (a da frente) à direita; cada "Jogador" se lê da sua cabeceira |
| `lateral-esquerda`   | Lateral esquerda     | a lateral comprida da esquerda, com o **contorno da folha** (a corcova em cima, os dois pés embaixo); de fora, a frente fica à direita |
| `lateral-direita`    | Lateral Direita      | a da direita, com o contorno dela; de fora, a frente fica à esquerda |
| `lateral-esquerda-2` | Lateral Esquerda 2   | a cabeceira de trás                                                  |
| `lateral-direita-2`  | Lateral Direita 2    | a cabeceira da frente                                                |

O `recortar_adesivos.py` acha cada peça na folha (o maior pedaço não branco
dentro da caixa aproximada do `recortes.json`, sem o nome escrito em cima; os
traços brancos finos da arte que encostam na borda não viram recorte), grava
a imagem recortada no limite da peça e, no `formas.json`, o tamanho em px e o
**contorno de verdade** das laterais (o polígono da máscara, 1 px para dentro
da arte, para o branco da folha não aparecer no 3D). O `montar.js` usa esse
contorno como o contorno da placa.

## As medidas: a folha é desenhada em escala

As peças da folha encaixam umas nas outras (as laterais são 33 px mais
compridas que o tampo, a cabeceira é 7 px mais larga que ele): é uma escala
só. O `montar.js` põe a mesa na altura do Air Game Kids, **0,90 m** com a fita
de LED (`ALT` = 0,894 m: o alto das laterais, na corcova do meio; ~3,04 mm por
px da folha), e o resto sai da folha: **1,51 m de comprimento** (o 1,50 m do
Air Game Kids, com a fita), o tampo de 1,40 m × 0,80 m e o campo a 0,75 m do
chão (as laterais sobem 7 a 15 cm acima dele). A largura: **0,86 m**, a do
catálogo, com as laterais de MDF grosso (~28 mm, com a borda arredondada; na
folha elas davam só 11 mm e a mesa ficava com 0,83 m, magra).
As cabeceiras ficam entre as laterais, na largura do tampo (as laterais passam
3 cm de cada ponta). Na folha, cada cabeceira vem com um retângulo **azul
liso** embaixo da arte: essa tábua **não existe na mesa**. O recorte a tira
(`"sem_faixa_lisa": true` no `recortes.json`; a altura tirada fica em
`faixa_lisa_px` no `formas.json`), a cabeceira é só a faixa da arte (~0,40 m)
logo abaixo do tampo, e embaixo dela a mesa é aberta entre os pés das
laterais. A altura do campo continua saindo da peça inteira da folha. Se a mesa de verdade for outra, é mudar `ALT` (a escala
sai dele) e as medidas no `core/arena.py` e no `core/cadastro_modelos.py`.

O resto da mesa não está na folha: a régua das pontas (preta, 2 cm, sobre a
beira de fora da moldura, sem cobrir o "Jogador") com a boca do gol, a borda
preta dos lados, a fita de LED, o placar, os dois rebatedores e o disco (do
tamanho da mesa infantil), a caixa de ar e o soprador embaixo do tampo.

~17 mil triângulos; ~2,1 MB depois do `gltfpack` (os cinco adesivos em JPEG, em
alta definição: abaixo).

**Os dois adesivos do Air Game Kids saem do MESMO `montar.js`** (o mesmo móvel,
a mesma medida: só a arte muda): `?arte=astronautas` usa as artes de
`../air-game-kids-astronautas/adesivos(-hd)/` (as duas laterais com a mesma
arte) e grava o `air-game-kids-astronautas.glb`.

## Em alta definição (LEIA-ME V10, seção 91)

O que as três máquinas de adesivo dividem está em `../comum3d.js`; o `.glb` sai
do `../gerar_glb.cjs` (com o three.js do site, `core/static/vendor/three`):

- **os adesivos em alta definição**: cada peça recortada da folha é ampliada 4x
  com nitidez pelo Real-ESRGAN (o modelo de arte desenhada,
  `../ampliar_adesivos.py`: `adesivos-hd/<peça>.webp`, guardadas no
  repositório) e vai para o `.glb` em JPEG de qualidade 0,9, em sRGB, com
  **2048 px no lado maior** nas peças grandes (as pequenas da testeira em 512 a
  1024). Nada da arte é redesenhado: é a mesma imagem, com as bordas nítidas;
- **os materiais da máquina de verdade** (PBR do glTF): o adesivo é vinil
  laminado brilhante (`KHR_materials_clearcoat`), o MDF preto acetinado, o metal
  cromado, e o que acende (o neon, o placar, os LEDs) com `emissiveStrength`;
- **as bordas arredondadas**: a chapa de MDF com o raio na quina (o adesivo do
  tamanho da face plana, a borda preta aparece em volta);
- **os nomes dos materiais e das malhas são os de antes** (o `gltfpack -kn -km`
  guarda os dois): quem importa o `.glb` no Blender acha cada peça pelo nome
  (`adesivo-<peça>`, `mdf-preto`, `neon-roxo`...).

    python3 ../ampliar_adesivos.py .        # adesivos-hd/ (precisa do modelo ONNX: veja o script)
    node ../gerar_glb.cjs <esta pasta>      # o .glb no static, as vistas v-*.jpg aqui

O `gerar_glb.cjs` não refaz as fotos do cadastro (as `.webp` da pasta do modelo
no static): elas são feitas à parte. `core/tests_glb_alta_definicao.py` confere
o tamanho (o do banco, a 2%), os 2048 px, o verniz, as luzes e os nomes.


## Trocar a folha (ou refazer)

    python3 recortar_adesivos.py --previa   # as caixas achadas e os contornos: previa-recortes.png
    python3 recortar_adesivos.py            # adesivos/<peça>.png e o formas.json
    python3 ../ampliar_adesivos.py .        # adesivos-hd/<peça>.webp (4x, nítido)
    node ../gerar_glb.cjs air-game-kids-alienigenas
    node ../gerar_glb.cjs air-game-kids-alienigenas --arte astronautas --saida air-game-kids-astronautas.glb
    python manage.py test core.tests_glb_alta_definicao core.tests_variantes_adesivo   # (na raiz)

Folha nova: salve-a como `folha-adesivos.webp` (ou mude `"folha"` no
`recortes.json`) e acerte as caixas aproximadas das peças. O `gerar_glb.cjs`
precisa do `playwright` e do `gltfpack` (`npm install playwright gltfpack`, ou o
`NODE_PATH` apontando para eles). As fotos do cadastro não saem mais daqui. O
`.glb` sem o `gltfpack`, as vistas e a prévia não vão para o repositório
(`.gitignore` desta pasta). O recorte só precisa do Pillow; o código que as
duas máquinas dividem está em `../adesivos_comum.py`.

## Ligar no site

`core/arena.py`, `MODELOS_3D` (id `air-game-kids-alienigenas`): o objeto se
liga à máquina pelo nome inteiro ("Air Game Kids Alienígenas", e ainda o de
antes, "Air Game Hockey Espacial"; o "Air Game Kids" e o "Air Game Hockey"
continuam sem ele), na seção "As máquinas que já fazíamos". O cadastro
(`core/cadastro_modelos.py`, `CADASTROS`) copia do Air Game Kids o preço, a
voltagem, a loja, a avaliação, as medidas, as categorias e as tags. No deploy:

* a `0145_variantes_de_adesivo` (que fica como estava) cadastra — num banco
  novo, pela chave antiga, que hoje é esta;
* a `0146_air_game_kids_alienigenas` passa o "Air Game Hockey Espacial" que a
  0145 cadastrou para o nome, a descrição e os campos do Air Game Kids, troca
  o nome nas descrições das fotos e liga o objeto 3D ao `.glb` novo (o
  `air-game-hockey-espacial.glb` não existe mais); no Render, as fotos que o
  cadastro subiu são refeitas com as daqui.

Se uma delas não conseguir (o Cloudinary fora do ar, por exemplo):
`python manage.py cadastrar_variantes_adesivo --so air-game-kids-alienigenas
--fotos`. Os testes: `core/tests_variantes_adesivo.py`.
