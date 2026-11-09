# Basquete Street Quadrinhos — o objeto 3D

O `.glb` que a Arena 3D e a página do produto usam
(`core/static/site/arena/modelos/basquete-street-quadrinhos.glb`) e as fotos
do cadastro (`.../basquete-street-quadrinhos/*.webp`) saem daqui.

O basquete de arcade do Basquete Street com os adesivos em quadrinhos.
**Tudo sai da folha de adesivos da fábrica** (`folha-adesivos.webp`, a folha
26567-2, guardada como veio): a arte de cada peça e o desenho dela. Nada da
arte é redesenhado, recolorido nem tirado: cada imagem vai inteira na sua
face, e a face tem a forma e a proporção da peça.

## As peças (a folha → adesivos/<peça>.png)

| Peça                          | Na folha                            | Onde vai                                             |
|-------------------------------|-------------------------------------|------------------------------------------------------|
| `lateral-externa-esquerda`    | Lateral Externa Esquerda            | o lado de fora, com o **contorno da folha** (a parte alta atrás, a curva e a diagonal, a parte baixa e o chanfro do console na frente); a frente à direita |
| `lateral-externa-direita`     | Lateral externa direita             | o da direita, com o contorno dele; a frente à esquerda |
| `lateral-interna-esquerda`    | Lateral interna esquerda            | a parede de dentro da pista, em L (alta atrás, baixa na frente), vista da pista: a frente à esquerda |
| `lateral-interna-direita`     | Lateral Interna Direita             | a da direita: a frente à direita                       |
| `fundo-cesta`                 | Fundo cesta basquete                | o painel atrás da cesta, até o teto (o placar no alto) |
| `teto-interno`                | Teto Interno                        | o teto em cima da cesta, visto de baixo                |
| `prancha`                     | Prancha                             | o chão da pista (a quadra; a cesta no alto da imagem)  |
| `frente`                      | Frente                              | o console, dobrado nas duas linhas da folha: o POW! de pé, o BASKETBALL na face inclinada e a faixa de cima deitada |
| `testeira-frente`             | Frente Testeira                     | a frente da testeira (o hexágono: o contorno da folha) |
| `testeira-fundo`              | fundo testeira                      | o fundo da testeira                                    |
| `testeira-teto`               | teto testeira                       | o alto da testeira                                     |
| `testeira-superior-esquerda`  | Lateral esquerda superior testeira  | o chanfro da esquerda (desenhado torto na folha: o recorte endireita) |
| `testeira-superior-direita`   | Lateral Direita Superior testeira   | o chanfro da direita (idem)                            |
| `testeira-lateral-esquerda`   | Lateral Esquerda Testeira           | o lado reto da esquerda, embaixo do chanfro            |
| `testeira-lateral-direita`    | Lateral Direita testeira            | o da direita                                           |

O `recortar_adesivos.py` acha cada peça na folha (o maior pedaço não branco
dentro da caixa aproximada do `recortes.json`, sem o nome escrito em cima; os
traços brancos finos da arte que encostam na borda, como os das laterais de
dentro, não viram recorte), grava a imagem recortada no limite da peça e, no
`formas.json`, o tamanho em px, as dobras da Frente e o **contorno de
verdade** das peças recortadas (o polígono da máscara, 1 px para dentro da
arte). As duas peças tortas da testeira são endireitadas pelo menor
retângulo girado delas (`angulo` no `recortes.json` só diz o sentido). A
testeira é montada como na folha aberta: o teto preso na frente, os chanfros
saindo dos chanfros da frente (a ponta deles que encosta na frente vai na
frente; a arte do chanfro continua no lado reto embaixo).

**As três peças soltas ao lado da Lateral Externa Esquerda** (a tira de pé, a
faixa BASKETBALL inclinada e o retângulo do POW!) são as três faixas da
Frente, desenhadas de lado para mostrar como ela dobra no console (a mesma
arte: a tira de pé é a faixa de cima, com "Start" no lugar da marca do
botão). Não são adesivos à parte e não entram no 3D.

## As medidas: a folha é desenhada em escala

A testeira, a frente, a prancha, o fundo e o teto têm a mesma largura na
folha (182 px = 1,00 m), e a lateral de fora com a testeira dão 2,70 m (as
duas contas batem em 0,3%). Daí:

- a testeira: 1,00 m × 0,27 m, 0,59 m de fundo, em cima da parte alta da lateral;
- a lateral de fora: 2,31 m de comprido, do console até 9 cm do fundo;
- as paredes de dentro, na mesma escala, têm 2,40 m: a **profundidade da
  máquina é 2,40 m**; elas vão do fundo até a frente do console, a parte baixa
  delas encontra a parte baixa da lateral de fora (0,94 m) e o chão da pista
  fica a 17 cm; a parte alta delas (até 2,05 m, onde fica o teto interno) passa
  da diagonal da lateral de fora e aparece por fora em preto (é a parede da
  pista; a folha não traz rede de proteção); a quina reta da frente delas fica
  embaixo da face inclinada do console (o que passaria dela é cortado);
- o console: a face de pé com o POW! (0,72 m), a inclinada com o BASKETBALL no
  chanfro da lateral de fora (60°) e a de cima, deitada (0,23 m, a 0,97 m do chão).

Fora da folha, só o necessário: a cesta (o aro de 30 cm a 1,65 m, no fundo,
embaixo do placar), as bolas e as placas pretas (as costas, o teto, a caixa
de cima). Três faces da testeira ficam até 5% esticadas para fechar o
hexágono (as peças da folha diferem 1 a 2 px entre si).

~5,2 mil triângulos; ~610 KB depois do `gltfpack` (os 15 adesivos em JPEG,
ampliados com suavização: a folha tem ~400 px nas peças grandes).

## Trocar a folha (ou refazer)

    python3 recortar_adesivos.py --previa   # as caixas achadas e os contornos: previa-recortes.png
    python3 recortar_adesivos.py            # adesivos/<peça>.png e o formas.json
    npm install three@0.169.0 playwright gltfpack
    python3 -m http.server 8790 --bind 127.0.0.1     # nesta pasta, com o node_modules
    node gerar.cjs glb fotos                          # vistas v-*.jpg, pecas.json, fotos e o .glb
    npx gltfpack -i basquete-street-quadrinhos.glb -o ../../../core/static/site/arena/modelos/basquete-street-quadrinhos.glb -kn -km -ke
    python manage.py test core.tests_variantes_adesivo   # (na raiz) o .glb abaixo de 800 KB

Folha nova: salve-a como `folha-adesivos.webp` (ou mude `"folha"` no
`recortes.json`) e acerte as caixas aproximadas. Com a porta 8790 ocupada:
`python3 -m http.server 8791 ...` e `PORTA=8791 node gerar.cjs ...`. O
`fotos` grava as `foto-*.jpg` (para conferir) e as `.webp` do cadastro já
recortadas no objeto, em 16:10 (a frente de 3/4, os dois lados, as costas e a
vista de quem joga), na pasta do modelo no static. Depois de subir, no
servidor: `python manage.py cadastrar_variantes_adesivo --fotos`. O
`node_modules`, o `.glb` sem o `gltfpack`, as vistas e a prévia não vão para o
repositório (`.gitignore` desta pasta). O recorte só precisa do Pillow; o
código que as duas máquinas dividem está em `../adesivos_comum.py`.

## Ligar no site

`core/arena.py`, `MODELOS_3D`: o objeto se liga à máquina pelo nome inteiro
("Basquete Street Quadrinhos": o "Basquete Street" de antes continua sem ele),
na seção "As máquinas que já fazíamos"; o passeio é a volta em torno. O
cadastro (`core/cadastro_modelos.py`, `CADASTROS`) copia do Basquete Street o
preço, a voltagem, a loja, a avaliação, as medidas, as categorias e as tags;
sai no deploy pela migração `core/0145_variantes_de_adesivo`; se ela não
conseguir, `python manage.py cadastrar_variantes_adesivo`. Os testes:
`core/tests_variantes_adesivo.py`.
