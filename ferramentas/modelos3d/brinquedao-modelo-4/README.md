# Brinquedão Modelo 4 — o objeto 3D

O `.glb` que a Arena 3D usa (`core/static/site/arena/modelos/brinquedao-modelo-4.glb`)
sai daqui. É o brinquedão de dois andares em "Z": um trecho de 12 m ao fundo e
outro de 9 m mais à frente e à direita, ligados por uma passagem no último
módulo do de 12 m; 1 m de fundo em cada trecho (2 m na piscina do tobogã).
Ele junta duas fontes:

1. **O `.3ds` da fábrica** (13 MB, ~295 mil triângulos, cada tubo com 408) —
   só a estrutura de tubos azuis (#0147a9), em milímetros, quase toda em duas
   cópias. O `extrair.py` (com o leitor do site, `core/conversor_3d.py`) junta
   as cópias e guarda uma lista leve (`estrutura.json`): 43 colunas e 153
   barras, o arco azul da entrada da piscina do tobogã e o disco solto que
   marca o rolo amarelo em pé. As sobras longe do brinquedo (um plano a 20 m,
   dois pontos a 28 m) saem. Daqui saem TODAS as medidas: o andar de cima a
   2,55 m, o corrimão de cima a 3,51 m, a escada da ponta esquerda (o piso de
   baixo a 0,2 m, o do meio a 1,59 m e os degraus de tubo a 0,98 m e 2,18 m),
   as barras de cima das quatro redes em V (3,27 m no trecho de 12 m, 3,31 m
   no de 9 m), os postes do par de rolos (13,13 m) e o quadro da piscina do
   tobogã (borda a 0,43 m, topo a 2,55 m). Nada da estrutura é inventado: o
   `montar.js` refaz cada tubo como um cilindro no mesmo lugar e medida.
2. **As imagens do projeto** — o render em perspectiva (o mais fiel das
   cores), a vista de frente (altura 3,45 m), a planta (12 m + 9 m, 3,60 m e
   2 m) e as duas vistas do salão. Delas vêm as cores e o que o `.3ds` não
   tem, cada coisa no módulo em que a planta a põe: os pisos (amarelos no
   trecho de 12 m e na passagem, pink no de 9 m, o de duas cores na diagonal
   da escada), os painéis "X" (círculo magenta e X amarelo) na frente dos
   módulos 1, 5 e 9 do trecho de 12 m e do 1º do de 9 m, os rolos vermelhos
   em pé, os pares de rolos amarelos deitados (passa-se pela fresta), o rolo
   amarelo em pé, as quatro redes amarelas em V, os sacos azuis, a pirâmide
   magenta, os três rolos magenta da passagem, o tobogã espiral amarelo e
   magenta (quase duas voltas em torno da coluna da quina, como na planta) com
   o painel magenta da boca, as duas piscinas de bolinhas (a grande, embaixo
   do trecho de 12 m, com os escorregadores ondulados; a do tobogã, com as
   bolinhas magenta e verde-limão em fileiras), a escadinha verde de dois
   degraus sob o arco azul, a Área Baby (cercadinho amarelo, blocos azuis,
   piso de EVA, bolinhas e a placa em nuvem azul "Área Baby") e as telas.

Ficam de fora o salão (mesas, pista quadriculada, paredes) e as máquinas de
jogos e o carrinho que aparecem embaixo e ao lado nas imagens: são do salão,
não do brinquedão. A placa das imagens diz "Aire Baby"; aqui ela diz "Área Baby".

As vistas `v-projeto.jpg` (do ponto do render da fábrica), `v-frente.jpg` (de
frente, sem perspectiva) e `v-cima.jpg` (a planta) servem para comparar lado a
lado com as imagens do projeto.

Medidas finais do objeto: 19,62 m × 5,98 m (com as piscinas, a Área Baby e a
escadinha; da frente do trecho de 9 m ao fundo do de 12 m são 3,7 m, os 3,60 m
da planta), altura 3,55 m (o corrimão
de cima do `.3ds`; a vista de frente diz 3,45 m); ~49 mil triângulos; ~780 KB
depois do `gltfpack`.

## Refazer

    /home/user/.venv-ls/bin/python extrair.py caminho/do/brinquedao.3ds   # estrutura.json
    npm install three@0.169.0 playwright gltfpack
    python3 -m http.server 8790 --bind 127.0.0.1    # nesta pasta
    node gerar.cjs glb                              # vistas v-*.jpg e o .glb
    npx gltfpack -i brinquedao-modelo-4.glb -o ../../../core/static/site/arena/modelos/brinquedao-modelo-4.glb -kn -km -ke

O `.3ds` original não fica no repositório: o que se usa dele está no
`estrutura.json`.

## Ligar no site

`core/arena.py`, `MODELOS_3D`: o objeto se liga à máquina pelo nome
("Brinquedão Modelo 4") e aparece na Arena mesmo antes do cadastro, na roda
dos brinquedões (e como modelo pronto de Brinquedão no "Monte seu projeto").
O cadastro (fora da loja) com as quatro imagens do projeto — o render em
perspectiva (a principal), a frente, a planta e o salão, em
`static/site/arena/modelos/brinquedao-modelo-4/` — e o objeto 3D ligado sai
sozinho no deploy, pela migração `core/0142_brinquedao_modelo_4`; se ela não
conseguir, `python manage.py cadastrar_brinquedao_modelo_4`.

O passeio por dentro (`CAMINHOS["brinquedao-modelo-4"]` em
`core/static/site/arena/arena3d.js`) sobe a escada da ponta esquerda,
atravessa o trecho de 12 m (rolos em pé, redes em V, por cima da pirâmide),
a passagem pelos rolos magenta, o trecho de 9 m (o saco, a fresta dos pares de
rolos, a rede), desce o tobogã até a piscina, sai pela escadinha verde e olha
a Área Baby e o brinquedão inteiro. As medidas do tobogã estão nos dois
lugares (`TOBOGA` no `montar.js`, `toboganDoModelo4` na Arena), e `M4` leva o
`.3ds` ao objeto: se o objeto mudar de tamanho, o centro que o `gerar.cjs`
imprime vai nela.
