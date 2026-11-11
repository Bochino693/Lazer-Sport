# Basquete Street Quadrinhos — o objeto 3D

O `.glb` que a Arena 3D e a página do produto usam
(`core/static/site/arena/modelos/basquete-street-quadrinhos.glb`) e as fotos
do cadastro (`.../basquete-street-quadrinhos/*.webp`) saem daqui.

O basquete de arcade com os adesivos em quadrinhos, no tamanho do Basquete
Street do catálogo (2,70 × 1,00 × 2,40 m, o cadastro). **Tudo o que é adesivo
sai da folha da fábrica** (`folha-adesivos.webp`, a folha 26567-2, guardada
como veio): a arte de cada peça e o desenho dela. Nada da arte é redesenhado,
recolorido nem tirado: cada imagem vai inteira na sua face.

## O gabinete: o da folha, conferido com as máquinas de verdade

As peças da folha (as laterais de chapa com o contorno, a testeira em
hexágono, o fundo da cesta com o BOOM!, o teto interno, a prancha e a Frente
do console dobrada em três) são as do gabinete do **Basquete Home** do
catálogo, a mesma arte em quadrinhos em azul
(`ferramentas/categorias/maquinas/basquete-home.webp`; a página
`/brinquedo/3/`): a testeira em cima, a lateral subindo atrás do console, o
fundo com o BOOM! até a testeira e a quadra que sobe do console até o fundo.
Do **Basquete Street** (a foto do catálogo, `/brinquedo/8/`) vêm as peças de
máquina de ponto comercial que a folha não desenha: o moedeiro, o neon roxo
nas bordas, o placar, os pés e a estrutura de tubo preto atrás.

O que a cliente apontou na versão de antes, e como ficou:

- **a bola das laterais é vazada**: os gomos brancos da bola, na folha, são
  recortes que atravessam a chapa. O recorte acha esses brancos (`furos` no
  `recortes.json`: os pedaços quase brancos dentro de uma caixa em volta da
  bola; o balão BASKETBALL, embaixo, fica de fora) e grava os polígonos no
  `formas.json`; no 3D eles furam a chapa, o adesivo de fora e o L de dentro
  (onde a bola passa do alto do L, ele ganha o recorte na borda). Por eles se
  vê a pista; em cada furo, a rede de proteção (fio preto em quadrados de 7 cm);
- **a chapa que devolve a bola é a prancha**, inclinada (10°), do pé do fundo
  da cesta (logo abaixo do BOOM!) até o console; a bola desce e para na
  **chapa de parada**, logo atrás da tampa do console (a tampa fica a 13 cm da
  rampa: a bola, de 21 cm, não passa), ao alcance de quem joga; ali ficam
  quatro bolas, e duas descem a rampa. Os 19 cm da ponta da quadra passam
  embaixo da tampa (a folha é mais comprida que a rampa à vista);
- **sem "madeiras quadradas"**: sai a caixa preta entre o teto e a testeira
  (o fundo da cesta e o teto vão até a testeira) e saem os tacos pretos atrás
  das laterais; as costas são a estrutura de tubo preto (os dois montantes e
  as travessas) com a chapa recuada.

## As peças (a folha → adesivos/<peça>.png)

| Peça                          | Na folha                            | Onde vai                                             |
|-------------------------------|-------------------------------------|------------------------------------------------------|
| `lateral-externa-esquerda`    | Lateral Externa Esquerda            | o lado de fora, com o **contorno da folha** e a **bola vazada** (8 furos); a frente à direita |
| `lateral-externa-direita`     | Lateral externa direita             | o da direita, idem; a frente à esquerda                |
| `lateral-interna-esquerda`    | Lateral interna esquerda            | o lado de dentro da mesma chapa, em L (alto atrás, baixo na frente), visto da pista; vai até onde a chapa vai e leva os furos da bola |
| `lateral-interna-direita`     | Lateral Interna Direita             | a da direita                                           |
| `fundo-cesta`                 | Fundo cesta basquete                | o painel atrás da cesta, da rampa até o teto; na janela branca, o placar |
| `teto-interno`                | Teto Interno                        | o teto em cima da cesta, visto de baixo, encostado na testeira |
| `prancha`                     | Prancha                             | a rampa (a quadra; a cesta no alto da imagem)          |
| `frente`                      | Frente                              | o console, dobrado nas duas linhas da folha: o POW! de pé, o BASKETBALL inclinado e a tampa deitada (com o botão Start na marca tracejada) |
| `testeira-frente`             | Frente Testeira                     | a frente da testeira (o hexágono: o contorno da folha), acesa |
| `testeira-fundo`              | fundo testeira                      | o fundo da testeira                                    |
| `testeira-teto`               | teto testeira                       | o alto da testeira                                     |
| `testeira-superior-esquerda`  | Lateral esquerda superior testeira  | o chanfro da esquerda (desenhado torto na folha: o recorte endireita) |
| `testeira-superior-direita`   | Lateral Direita Superior testeira   | o chanfro da direita (idem)                            |
| `testeira-lateral-esquerda`   | Lateral Esquerda Testeira           | o lado reto da esquerda, embaixo do chanfro            |
| `testeira-lateral-direita`    | Lateral Direita testeira            | o da direita                                           |

O `recortar_adesivos.py` acha cada peça na folha (o maior pedaço não branco
dentro da caixa aproximada do `recortes.json`, sem o nome escrito em cima),
grava a imagem recortada no limite da peça e, no `formas.json`, o tamanho em
px, as dobras da Frente, o **contorno de verdade** das peças recortadas e os
**furos** da bola. As duas peças tortas da testeira são endireitadas pelo
menor retângulo girado delas.

**As três peças soltas ao lado da Lateral Externa Esquerda** (a tira de pé, a
faixa BASKETBALL inclinada e o retângulo do POW!) são as três faixas da
Frente desenhadas como a caixa aberta do console (a tampa, o chanfro e a
face de pé; na tira, o "Start" no lugar da marca do botão). Não são adesivos
à parte e não entram no 3D.

## As medidas: a folha é desenhada em escala

A testeira, a frente, a prancha, o fundo e o teto têm a mesma largura na
folha (182 px = 1,00 m), e a lateral de fora com a testeira e os pés dão
2,70 m. Daí:

- a testeira: 1,00 m × 0,27 m, 0,58 m de fundo, em cima da parte alta da lateral;
- a lateral de fora (a chapa): 2,28 m de comprido, do console até 12 cm das
  costas (a chapa continua, preta, até as costas), de 2,5 cm do chão (os pés
  niveladores) até 2,43 m;
- o L de dentro, na mesma escala, tem o comprimento da pista (da placa da
  frente do console até a chapa das costas); a parte baixa dele encontra a
  parte baixa da lateral de fora (0,96 m), o pé dele fica a 20 cm do chão e o
  alto, a 2,04 m;
- o teto interno encosta embaixo da testeira (2,41 m); o fundo da cesta vai
  dele até 0,77 m (a rampa cobre o pé dele, abaixo do BOOM!);
- a rampa: 0,84 m na chapa de parada, 1,20 m no fundo (10°);
- o console: a face de pé com o POW! (0,72 m), a inclinada com o BASKETBALL no
  chanfro da lateral de fora (60°) e a tampa deitada (0,23 m, a 0,99 m do chão);
  a boca das bolas, atrás da tampa, tem 27 cm até a diagonal da lateral;
- a cesta: o aro de 30 cm a 1,97 m, embaixo do placar.

Fora da folha, só o que a máquina tem: a cesta, o placar (o visor com os
dígitos na janela branca do fundo), a chapa de parada e as bolas, o botão
Start, a porta do moedeiro (na face de pé, à esquerda do POW!), o neon roxo
(o contorno de cima das laterais, da tampa até a testeira; a borda da tampa;
a luz do pé), a rede de proteção nos furos, a estrutura de tubo das costas e
os seis pés niveladores. Tudo dentro de 1,00 × 2,70 × 2,40 m.

~12 mil triângulos; ~740 KB depois do `gltfpack` (os 15 adesivos em JPEG,
ampliados com suavização: a folha tem ~400 px nas peças grandes; as chapas
com o contorno simplificado em 4 mm, embaixo do adesivo, que fica com o de
verdade).

## Trocar a folha (ou refazer)

    python3 recortar_adesivos.py --previa   # as caixas, os contornos (verde) e os furos (azul): previa-recortes.png
    python3 recortar_adesivos.py            # adesivos/<peça>.png e o formas.json
    npm install three@0.169.0 playwright gltfpack
    python3 -m http.server 8790 --bind 127.0.0.1     # nesta pasta, com o node_modules
    node gerar.cjs glb fotos                          # vistas v-*.jpg, pecas.json, fotos e o .glb
    npx gltfpack -i basquete-street-quadrinhos.glb -o ../../../core/static/site/arena/modelos/basquete-street-quadrinhos.glb -kn -km -ke
    python manage.py test core.tests_variantes_adesivo   # (na raiz) o .glb abaixo de 800 KB

Folha nova: salve-a como `folha-adesivos.webp` (ou mude `"folha"` no
`recortes.json`), acerte as caixas aproximadas e a caixa dos `furos` (em
frações da peça). Com a porta 8790 ocupada: `python3 -m http.server 8791 ...`
e `PORTA=8791 node gerar.cjs ...`. O `fotos` grava as `foto-*.jpg` (para
conferir) e as `.webp` do cadastro já recortadas no objeto, em 16:10 (a
frente de 3/4, os dois lados, as costas e a vista de quem joga), na pasta do
modelo no static. Depois de subir, no servidor: `python manage.py
cadastrar_variantes_adesivo --so basquete-street-quadrinhos --fotos`. O
`node_modules`, o `.glb` sem o `gltfpack`, as vistas e a prévia não vão para o
repositório (`.gitignore` desta pasta). O recorte só precisa do Pillow; o
código que as duas máquinas dividem está em `../adesivos_comum.py`.

## Ligar no site

`core/arena.py`, `MODELOS_3D`: o objeto se liga à máquina pelo nome inteiro
("Basquete Street Quadrinhos": o "Basquete Street" de antes continua sem ele),
na seção "As máquinas que já fazíamos"; o passeio é a volta em torno. O
cadastro (`core/cadastro_modelos.py`, `CADASTROS`) copia do Basquete Street o
preço, a voltagem, a loja, a avaliação, as medidas, as categorias e as tags;
sai no deploy pela migração `core/0145_variantes_de_adesivo` (a 0150 troca no
Render as fotos da arte provisória); se elas não conseguirem, `python
manage.py cadastrar_variantes_adesivo`. No "Monte seu espaço" ele entra com o
próprio .glb, na pegada de 1,00 × 2,40 m (e 1 m de frente para quem joga). Os
testes: `core/tests_variantes_adesivo.py`.
