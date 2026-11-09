# Air Game Hockey Espacial — o objeto 3D

O `.glb` que a Arena 3D e a página do produto usam
(`core/static/site/arena/modelos/air-game-hockey-espacial.glb`) e as fotos do
cadastro (`.../air-game-hockey-espacial/*.webp`) saem daqui.

É a MESMA máquina do **Air Game Hockey** (a mesa de air hockey: 1,00 m de
altura, 1,10 m de largura e 2,10 m de comprimento), só com os adesivos novos,
do espaço: o logotipo HOCKEY KIDS, alienígenas astronautas jogando hóquei,
discos voadores, planetas, estrelas e o chão lunar laranja.

## De onde vem cada parte

- **A mesa** (`montar.js`), desenhada pelos moldes dos adesivos, nas medidas
  do Air Game Hockey: o tampo a 82 cm com a borda em volta (as réguas de 4 cm,
  mais largas nas cabeceiras, com a boca do gol no meio), os dois rebatedores e
  o disco; as duas laterais compridas com o contorno recortado (o alto sobe
  nas pontas até 1,00 m e afunda no meio, a 88,5 cm; embaixo, o vão de 47 cm
  entre os dois pés largos de 30 cm); as duas cabeceiras lisas, até o tampo;
  embaixo do tampo, a caixa de ar e o soprador, que aparecem pelo vão.
- **A arte**: cada adesivo é um arquivo de `adesivos/` (abaixo). O `montar.js`
  só cola cada imagem na sua face; a lateral recortada leva a imagem inteira e
  o contorno da peça corta o que sobra. No `.glb`, cada adesivo vai em JPEG,
  com no máximo 1024 px no lado maior (`RESOLUCAO` e `QUALIDADE_JPEG` no
  `montar.js`).

## As peças (adesivos/<peça>.png)

Cada imagem é a peça vista DE FORA, em pé, como na folha da gráfica. O
tamanho (mm), onde ela vai e o contorno estão no `pecas.json` (o `gerar.cjs`
grava, a partir do `montar.js`).

| Peça                 | mm          | Onde                                                                 |
|----------------------|-------------|----------------------------------------------------------------------|
| `tampo`              | 2100 × 1064 | o tampo inteiro, deitado: a cabeceira de trás (a da lateral esquerda 2) à esquerda da imagem, a da frente à direita; o alto da imagem é o lado direito da mesa. As réguas cobrem os 3,5 cm dos lados e os 8 cm das pontas |
| `lateral-esquerda`   | 2100 × 1000 | a lateral comprida da esquerda (recortada): a frente à direita da imagem |
| `lateral-direita`    | 2100 × 1000 | a da direita (recortada): a frente à esquerda da imagem              |
| `lateral-esquerda-2` | 1064 × 795  | a cabeceira de trás (a ponta curta à esquerda do tampo)              |
| `lateral-direita-2`  | 1064 × 795  | a cabeceira da frente (a ponta curta à direita do tampo)             |

**A arte que está aí é PROVISÓRIA** (`desenhar_provisorios.py`, só formas
simples e os textos do tema, sem personagem de ninguém): a folha de adesivos
da fábrica ainda não chegou.

## Quando a folha de adesivos chegar

1. Salve a imagem da folha nesta pasta como `folha-adesivos.jpg` (outro nome:
   mude `"folha"` no `recortes.json`; uma peça noutra imagem leva `"folha"`
   dentro dela).
2. No `recortes.json`, marque cada peça: a `caixa` `[x0, y0, x1, y1]` em px da
   folha (o canto de cima à esquerda e o de baixo à direita; abra a folha num
   editor de imagem e leia as coordenadas) e quanto `girar` (0, 90, 180 ou
   270, anti-horário) para ela ficar como na tabela acima. Peça sem caixa
   (`null`) fica com a arte que já está em `adesivos/`.
3. `python3 recortar_adesivos.py --previa` e confira as caixas em
   `previa-recortes.jpg`.
4. `python3 recortar_adesivos.py` grava `adesivos/<peça>.png` e avisa quando o
   recorte não tem a proporção da peça no 3D (confira a caixa e o giro; se a
   peça de verdade for de outro tamanho, acerte as medidas no `montar.js`).
5. Refaça o 3D e as fotos (abaixo, "Refazer") e olhe as vistas `v-*.jpg`.
6. `python manage.py test core.tests_variantes_adesivo` (o `.glb` tem de ficar
   abaixo de 800 KB: se passar, baixe a `RESOLUCAO` ou a `QUALIDADE_JPEG`).
7. Suba os arquivos novos (`adesivos/`, o `.glb` e os `.webp`) e, no servidor,
   `python manage.py cadastrar_variantes_adesivo --fotos`: a galeria do
   cadastro (no Cloudinary) passa a mostrar a arte nova.

## Refazer

    npm install three@0.169.0 playwright gltfpack
    python3 desenhar_provisorios.py                   # só sem a folha: a arte provisória
    python3 -m http.server 8790 --bind 127.0.0.1     # nesta pasta, com o node_modules
    node gerar.cjs glb fotos                          # vistas v-*.jpg, pecas.json, fotos e o .glb
    npx gltfpack -i air-game-hockey-espacial.glb -o ../../../core/static/site/arena/modelos/air-game-hockey-espacial.glb -kn -km -ke

Com a porta 8790 ocupada: `python3 -m http.server 8791 ...` e
`PORTA=8791 node gerar.cjs ...`. O `fotos` grava as `foto-*.jpg` (a vista
inteira, para conferir) e as `.webp` do cadastro já recortadas no objeto, em
16:10 (a frente de 3/4, os dois lados, a outra cabeceira e o tampo de cima),
direto na pasta do modelo no static. O `node_modules`, o `.glb` sem o
`gltfpack`, as vistas e a prévia dos recortes não vão para o repositório
(`.gitignore` desta pasta). O recorte e a arte provisória só precisam do Pillow;
o código que as duas máquinas dividem está em `../adesivos_comum.py`.

Medidas finais do objeto: 1,10 m × 1,00 m × 2,10 m (exatas); ~3,3 mil
triângulos; ~280 KB depois do `gltfpack` (as cinco imagens, ~215 KB).

## Ligar no site

`core/arena.py`, `MODELOS_3D`: o objeto se liga à máquina pelo nome inteiro
("Air Game Hockey Espacial": o "Air Game Hockey" de antes continua sem ele),
na seção "As máquinas que já fazíamos". O cadastro
(`core/cadastro_modelos.py`, `CADASTROS`) copia do Air Game Hockey o preço, a
voltagem, a loja, a avaliação, as medidas, as categorias e as tags; sai no
deploy pela migração `core/0145_variantes_de_adesivo`; se ela não conseguir,
`python manage.py cadastrar_variantes_adesivo`. Os testes:
`core/tests_variantes_adesivo.py`.
