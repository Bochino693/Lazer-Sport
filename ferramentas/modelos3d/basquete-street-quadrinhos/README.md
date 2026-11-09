# Basquete Street Quadrinhos — o objeto 3D

O `.glb` que a Arena 3D e a página do produto usam
(`core/static/site/arena/modelos/basquete-street-quadrinhos.glb`) e as fotos
do cadastro (`.../basquete-street-quadrinhos/*.webp`) saem daqui.

É a MESMA máquina do **Basquete Street** (o basquete de arcade: 2,70 m de
altura, 1,00 m de largura e 2,40 m de comprimento), só com os adesivos novos,
em quadrinhos: fundo preto com faixas arredondadas amarelas, laranja,
vermelhas e rosa, os balões "POW!", "BOOM!" e "WOW!", o letreiro BASKETBALL,
duas crianças jogando, a bola grande nas laterais de fora e a quadra com as
linhas vermelhas na prancha.

## De onde vem cada parte

- **A máquina** (`montar.js`), desenhada pelos moldes dos adesivos, nas
  medidas do Basquete Street. De trás para a frente (o jogador fica em +z):
  - a parte ALTA (70 cm de fundo, até 2,40 m): dentro, o fundo da cesta (o
    painel preto com o "BOOM!" e a janela do placar), a cesta (o aro de 30 cm
    a 1,95 m, com a rede) e o teto interno; em cima, a testeira (30 cm de
    altura, 43 cm de fundo) com o BASKETBALL aceso;
  - a quina de cima da parte alta desce em curva, na diagonal (~64°), até a
    parte BAIXA (~1/3 da altura), paralela à rampa, que vai até o console; em
    cima dela, o corrimão com a faixa BASKETBALL, o poste da frente e a rede
    de proteção até 2,00 m;
  - a prancha (a rampa preta com a quadra vermelha), de 1,01 m embaixo da
    cesta a 78 cm na frente, por onde as bolas voltam;
  - na frente, o console das bolas (25 cm de fundo, 90 cm de altura), com a
    bandeja e quatro bolas; duas bolas voltando pela rampa.
- **A arte**: cada adesivo é um arquivo de `adesivos/` (abaixo). O `montar.js`
  só cola cada imagem na sua face; as laterais recortadas levam a imagem
  inteira e o contorno da peça corta o que sobra. No `.glb`, cada adesivo vai
  em JPEG (`RESOLUCAO` e `QUALIDADE_JPEG` no `montar.js`: as 14 peças somam
  ~0,5 MB).

Onde a descrição dos moldes não fechava sozinha: a faixa BASKETBALL inclinada
vai no corrimão de cima da parte baixa; a faixa do poste, no poste da frente
que segura a rede; o retângulo pequeno com o "POW!", nos dois lados do
console. Se a folha mostrar outro jeito, mude o `montar.js` (`CONSOLE`,
`CORRIMAO`, `POSTE`, a diagonal `C1`/`C2`...).

## As peças (adesivos/<peça>.png)

Cada imagem é a peça vista DE FORA, em pé (as de dentro, vistas de dentro da
pista), como na folha da gráfica. O tamanho (mm), onde ela vai e o contorno
estão no `pecas.json` (o `gerar.cjs` grava, a partir do `montar.js`).

| Peça                       | mm          | Onde                                                                |
|----------------------------|-------------|---------------------------------------------------------------------|
| `lateral-externa-esquerda` | 2150 × 2400 | o lado de fora da esquerda, recortado: a parte alta à esquerda da imagem, a frente à direita (o console é à parte) |
| `lateral-externa-direita`  | 2150 × 2400 | o da direita: a parte alta à direita da imagem                      |
| `lateral-interna-esquerda` | 2131 × 1601 | o lado de dentro da esquerda, em L, da prancha para cima: a parte alta (até o teto) à direita da imagem |
| `lateral-interna-direita`  | 2131 × 1601 | o da direita: a parte alta à esquerda da imagem                     |
| `fundo-cesta`              | 960 × 1371  | o painel do fundo, da prancha até o teto (a cesta a ~43 cm do alto) |
| `teto-interno`             | 960 × 681   | o teto da parte alta, visto de baixo (a frente no alto da imagem)   |
| `testeira-frente`          | 1000 × 300  | a frente da testeira (o letreiro)                                   |
| `testeira-teto`            | 1000 × 430  | o alto da testeira (a frente embaixo da imagem)                     |
| `testeira-lado`            | 430 × 300   | os dois lados da testeira (a mesma peça)                            |
| `prancha`                  | 960 × 2143  | a rampa, vista de quem joga (a cesta no alto da imagem)             |
| `faixa-rampa`              | 474 × 90    | a faixa do corrimão, inclinada (os dois lados)                      |
| `poste`                    | 60 × 960    | a faixa do poste da frente, do corrimão para cima (os dois lados)   |
| `frente`                   | 1000 × 900  | a frente do console (o lado de quem joga)                           |
| `frente-lateral`           | 250 × 900   | os dois lados do console                                            |

**A arte que está aí é PROVISÓRIA** (`desenhar_provisorios.py`, só formas
simples e os textos do tema; as crianças são desenhos de pictograma, sem
personagem de ninguém): a folha de adesivos da fábrica ainda não chegou.

## Quando a folha de adesivos chegar

1. Salve a imagem da folha nesta pasta como `folha-adesivos.jpg` (outro nome:
   mude `"folha"` no `recortes.json`; uma peça noutra imagem leva `"folha"`
   dentro dela).
2. No `recortes.json`, marque cada peça: a `caixa` `[x0, y0, x1, y1]` em px da
   folha (o canto de cima à esquerda e o de baixo à direita; abra a folha num
   editor de imagem e leia as coordenadas) e quanto `girar` (0, 90, 180 ou
   270, anti-horário) para ela ficar como na tabela acima (`"espelhar": true`
   se a folha trouxer a peça espelhada). Peça sem caixa (`null`) fica com a
   arte que já está em `adesivos/`.
3. `python3 recortar_adesivos.py --previa` e confira as caixas em
   `previa-recortes.jpg`.
4. `python3 recortar_adesivos.py` grava `adesivos/<peça>.png` e avisa quando o
   recorte não tem a proporção da peça no 3D (confira a caixa e o giro; se a
   peça de verdade for de outro tamanho, acerte as medidas no `montar.js`).
5. Refaça o 3D e as fotos (abaixo, "Refazer") e olhe as vistas `v-*.jpg`
   (`v-jogador.jpg` e `v-cesta.jpg` mostram a pista por dentro).
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
    npx gltfpack -i basquete-street-quadrinhos.glb -o ../../../core/static/site/arena/modelos/basquete-street-quadrinhos.glb -kn -km -ke

Com a porta 8790 ocupada: `python3 -m http.server 8791 ...` e
`PORTA=8791 node gerar.cjs ...`. O `fotos` grava as `foto-*.jpg` (a vista
inteira, para conferir) e as `.webp` do cadastro já recortadas no objeto, em
16:10 (a frente de 3/4, os dois lados, as costas e a vista de quem joga),
direto na pasta do modelo no static. O `node_modules`, o `.glb` sem o
`gltfpack`, as vistas e a prévia dos recortes não vão para o repositório
(`.gitignore` desta pasta). O recorte e a arte provisória só precisam do Pillow;
o código que as duas máquinas dividem está em `../adesivos_comum.py`.

Medidas finais do objeto: 1,00 m × 2,70 m × 2,40 m (exatas); ~3,9 mil
triângulos; ~615 KB depois do `gltfpack`.

## Ligar no site

`core/arena.py`, `MODELOS_3D`: o objeto se liga à máquina pelo nome inteiro
("Basquete Street Quadrinhos": o "Basquete Street" de antes continua sem ele),
na seção "As máquinas que já fazíamos"; o passeio é a volta em torno (não há
`CAMINHOS` próprio: é uma máquina pequena). O cadastro
(`core/cadastro_modelos.py`, `CADASTROS`) copia do Basquete Street o preço, a
voltagem, a loja, a avaliação, as medidas, as categorias e as tags; sai no
deploy pela migração `core/0145_variantes_de_adesivo`; se ela não conseguir,
`python manage.py cadastrar_variantes_adesivo`. Os testes:
`core/tests_variantes_adesivo.py`.
