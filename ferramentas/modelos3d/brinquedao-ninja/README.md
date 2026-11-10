# Brinquedão Ninja — o objeto 3D

O `.glb` que a Arena 3D usa (`core/static/site/arena/modelos/brinquedao-ninja.glb`)
sai daqui. É UM objeto: o brinquedão de dois andares (10 m) e as duas camas
elásticas de 2 m × 2 m na ponta direita (o .3ds da fábrica traz os dois juntos).
Ele junta três fontes:

1. **O `.3ds` da fábrica** — só a estrutura: as colunas rosa e as barras
   laranja, as duas barras azuis de cima da rede em V e os corrimãos rosa
   das entradas da frente, em milímetros. O arquivo tem ~270 mil faces
   (cada tubo com 1.416); aqui ele vira uma lista leve (`estrutura.json`,
   feito pelo `extrair.py`) e cada peça é refeita no mesmo lugar e na mesma
   medida. Daqui saem as alturas: o andar de cima a 2,26 m, o corrimão de
   cima a 3,26 m, o quadro das camas e da piscina de bolinhas a 0,3 m.
2. **A imagem do projeto (vista de frente)** — as cores e as peças que o
   `.3ds` não tem: os cilindros pendurados, os postes com as pegas, o rolo
   vazado rosa, a passarela de rede em V verde-limão, os painéis com o X,
   as placas "ninja", o tobogã em espiral rosa e verde-limão, a piscina de
   cubos com as cordas, a viga azul com o pegador (a tirolesa), a estrela,
   os degraus verdes e as telas. O céu com nuvens do fundo é ilustrativo:
   no lugar dele vai a tela de proteção.
3. **A planta** (10 m + 4 m por 2 m, altura 3,10 m) — a ordem dos módulos,
   o canto em L com os dois triângulos (azul em baixo, amarelo em cima), a
   piscina de bolinhas, a lona rosa das camas com o círculo verde e os
   degraus que saem na frente.

A vista `v-projeto.jpg` é tirada do mesmo ponto de onde a fábrica fez a
imagem: a câmera foi achada pelas colunas do `.3ds` e onde elas caem na
imagem (erro de ~5 px), para comparar as duas lado a lado. A boca do
tobogã fica na metade direita do módulo vermelho, como na imagem (a planta
a desenha na esquerda, mas ali ela cairia atrás do painel com o X).

Medidas finais do objeto (com o tobogã e os degraus da frente): 14,3 m ×
2,42 m, altura 3,37 m (o corrimão de cima do `.3ds` fica a 3,3 m; a planta
diz 3,10 m, e o cadastro usa a da planta); ~36 mil triângulos; ~650 KB
depois do `gltfpack`.

## Refazer

    python3 extrair.py caminho/do/estrutura.3ds    # estrutura.json
    npm install three@0.169.0 playwright gltfpack
    python3 -m http.server 8790 --bind 127.0.0.1    # nesta pasta
    node gerar.cjs glb                              # vistas v-*.jpg e o .glb
    npx gltfpack -i brinquedao-ninja.glb -o ../../../core/static/site/arena/modelos/brinquedao-ninja.glb -kn -km -ke

O `.3ds` original (10,8 MB) não fica no repositório: o que se usa dele está
no `estrutura.json`.

## Ligar no site

`core/arena.py`, `MODELOS_3D`: o objeto se liga à máquina pelo nome
("Brinquedão Ninja") e aparece na Arena mesmo antes do cadastro, na roda
dos brinquedões. O cadastro com as duas fotos (a imagem do projeto e a
planta, em `static/site/arena/modelos/brinquedao-ninja/`) e o objeto 3D
ligado sai sozinho no deploy, pela migração `core/0140_brinquedao_ninja`;
se ela não conseguir, `python manage.py cadastrar_brinquedao_ninja`.

O passeio por dentro (`CAMINHOS["brinquedao-ninja"]` em
`core/static/site/arena/caminhos.js`) sobe os degraus do canto, atravessa o
andar de cima (cilindros, postes, o rolo por dentro, a rede em V), desce o
tobogã, sai da piscina de bolinhas, pula nas duas camas, vai de tirolesa
por cima da espuma e termina olhando o brinquedão inteiro. As medidas do
tobogã estão nos dois lugares (`TOBOGA` no `montar.js`, `toboganDoNinja` na
Arena), e `NJ` leva o `.3ds` ao objeto: se o objeto mudar de tamanho, o
centro que o `gerar.cjs` imprime vai nela.
