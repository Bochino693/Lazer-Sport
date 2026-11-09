# Air Game Hockey Espacial — o objeto 3D

O `.glb` que a Arena 3D e a página do produto usam
(`core/static/site/arena/modelos/air-game-hockey-espacial.glb`) e as fotos do
cadastro (`.../air-game-hockey-espacial/*.webp`) saem daqui.

A mesa de air hockey com os adesivos do espaço. **Tudo sai da folha de
adesivos da fábrica** (`folha-adesivos.webp`, a folha 26567-1, guardada como
veio): a arte de cada peça e o desenho dela. Nada da arte é redesenhado,
recolorido nem tirado: cada imagem vai inteira na sua face, e a face tem a
forma e a proporção da peça.

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
só. O `montar.js` põe a mesa na altura de **1,00 m** (o alto das laterais, na
corcova do meio) e o resto sai da folha: **1,67 m de comprimento, 0,92 m de
largura**, o tampo de 1,57 m × 0,90 m e o campo a 0,83 m do chão (as laterais
sobem 8 a 17 cm acima dele). As cabeceiras ficam entre as laterais, na largura
do tampo (as laterais passam 4 cm de cada ponta).

**Atenção:** essas proporções não fecham com 2,10 m × 1,10 m × 1,00 m (a
medida do Air Game Hockey passada para o cadastro): o tampo da folha tem a
proporção 1,746 (2,10 × 1,10 dá 1,91), e na escala de 2,10 m a mesa teria
1,26 m de altura, com o campo a 1,07 m. As medidas da folha batem com as do
Air Game Kids do catálogo (0,90 × 0,86 × 1,50 m: o tampo de 1,50 × 0,86 m tem
a mesma proporção). Se a mesa de verdade for outra, é mudar `ALT` no
`montar.js` (a escala sai dele) e as medidas no `core/arena.py` e no
`core/cadastro_modelos.py`.

O resto da mesa não está na folha e é o mínimo para ela funcionar: a régua
das pontas (2,2 cm, sobre a beira de fora da moldura, sem cobrir o "Jogador")
com a boca do gol, os dois rebatedores e o disco, a caixa de ar e o soprador
embaixo do tampo.

~6,7 mil triângulos; ~565 KB depois do `gltfpack` (os cinco adesivos em JPEG,
~420 KB, ampliados com suavização a ~1024 px: a folha tem só ~500 px por peça).

## Trocar a folha (ou refazer)

    python3 recortar_adesivos.py --previa   # as caixas achadas e os contornos: previa-recortes.png
    python3 recortar_adesivos.py            # adesivos/<peça>.png e o formas.json
    npm install three@0.169.0 playwright gltfpack
    python3 -m http.server 8790 --bind 127.0.0.1     # nesta pasta, com o node_modules
    node gerar.cjs glb fotos                          # vistas v-*.jpg, pecas.json, fotos e o .glb
    npx gltfpack -i air-game-hockey-espacial.glb -o ../../../core/static/site/arena/modelos/air-game-hockey-espacial.glb -kn -km -ke
    python manage.py test core.tests_variantes_adesivo   # (na raiz) o .glb abaixo de 800 KB

Folha nova: salve-a como `folha-adesivos.webp` (ou mude `"folha"` no
`recortes.json`) e acerte as caixas aproximadas das peças. Com a porta 8790
ocupada: `python3 -m http.server 8791 ...` e `PORTA=8791 node gerar.cjs ...`.
O `fotos` grava as `foto-*.jpg` (a vista inteira, para conferir) e as `.webp`
do cadastro já recortadas no objeto, em 16:10 (a frente de 3/4, os dois lados,
a outra cabeceira e o tampo de cima), na pasta do modelo no static. Depois de
subir, no servidor: `python manage.py cadastrar_variantes_adesivo --fotos` (a
galeria do cadastro, no Cloudinary, com as fotos novas). O `node_modules`, o
`.glb` sem o `gltfpack`, as vistas e a prévia não vão para o repositório
(`.gitignore` desta pasta). O recorte só precisa do Pillow; o código que as
duas máquinas dividem está em `../adesivos_comum.py`.

## Ligar no site

`core/arena.py`, `MODELOS_3D`: o objeto se liga à máquina pelo nome inteiro
("Air Game Hockey Espacial": o "Air Game Hockey" de antes continua sem ele),
na seção "As máquinas que já fazíamos". O cadastro
(`core/cadastro_modelos.py`, `CADASTROS`) copia do Air Game Hockey o preço, a
voltagem, a loja, a avaliação, as medidas, as categorias e as tags; sai no
deploy pela migração `core/0145_variantes_de_adesivo`; se ela não conseguir,
`python manage.py cadastrar_variantes_adesivo`. Os testes:
`core/tests_variantes_adesivo.py`.
