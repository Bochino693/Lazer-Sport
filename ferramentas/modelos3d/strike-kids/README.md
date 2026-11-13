# Strike Kids (o boliche kids) — o objeto 3D em alta definição

O `.glb` que a página do produto, a vitrine e a Arena 3D usam
(`core/static/site/arena/modelos/strike-kids.glb`) sai daqui (LEIA-ME V10,
seção 92). Até esta versão o Strike Kids era o `.glb` pronto que a fábrica
mandou (feito com o trimesh, sem código para refazer): chapas finas de 18 mm
sem borda, a testeira entrando no teto e nas laterais ("pontas sobrepostas"),
as bolas embaixo da pista e as artes em 630 px, apagadas.

## A máquina (como nas fotos do cliente)

- **Gabinete cheio e firme**: as laterais em MDF de **25 mm com a borda
  arredondada** (raio de 8 mm; o adesivo cobre a face plana, a borda preta
  aparece em volta), no contorno da arte: da coluna da tela, uma curva só até a
  pista, e o canto redondo da frente até o chão.
- **A coluna**: o painel da tela (a arte dos raios com as nuvens) inclinado como
  a frente das laterais (13,8°), com o **monitor em pé** (~32", 9:16): a moldura
  preta brilhante e a tela **acesa** com o jogo (o "ROLE A BOLA!" e os placares
  dos jogadores); a **caixinha branca da câmera** centrada em cima do monitor; o
  logotipo da Lazer & Sport embaixo (na arte).
- **A testeira em forma de nuvem** (0,70 × 0,49 m, MDF de 30 mm com a borda
  arredondada), presa na frente do alto da coluna por dois suportes em cima do
  teto: **nada se cruza** (a parte de trás dela fica 4 mm na frente da borda das
  laterais). O **neon flex vermelho** segue a linha que a própria arte marca (a
  ~4 cm da borda da nuvem, de um pé ao outro por cima).
- **A fita de LED de pontos coloridos** (um ponto a cada 33 mm, as cores do
  arco-íris correndo pela fita) por **toda a borda de cima das laterais**: do alto
  da frente, pela parte baixa, subindo pela frente da coluna até o alto das costas.
- **O neon flex vermelho** em volta do logotipo "Strike Kids" das duas laterais e
  o **azul** em volta do logotipo da frente: o contorno do desenho (os pinos e as
  letras) em cada arte (`contornos_neon.py`).
- **A pista** de madeira com as setas e o logotipo, **brilhante**, com o
  **recorte do bolsão** na frente, à direita: o bolsão (o piso, a divisória e o
  fundo) com as **duas bolas de borracha** de gomos (a vermelha e preta, a
  amarela com vermelho, azul e preto). Por dentro das laterais, acima da pista, a
  faixa do acabamento (o arco escuro com as lâmpadas amarelas perto do bolsão).
- **A frente** com o recorte do bolsão, o logotipo no neon azul, o **botão
  vermelho** (no círculo branco da arte) e a Lazer & Sport.
- **Acabamento**: os adesivos em vinil laminado brilhante (`KHR_materials_clearcoat`),
  o MDF preto acetinado, a lente e a moldura do monitor brilhantes; a tela, o
  neon e os LEDs acesos (`KHR_materials_emissive_strength`).

## As medidas

As do cadastro: **2,07 m de altura, 0,74 m de largura e 1,91 m de comprimento**,
a máquina inteira com o que sobressai (o neon das laterais, o tubo de 10 mm
encostado no adesivo, e o botão vermelho): o gabinete tem 0,72 × 1,894 m e as
laterais a proporção da arte delas (1,634 m de altura). A pista fica a 0,32 m, a
beira do bolsão a 0,11 m. `core/tests_glb_alta_definicao.py` confere o .glb com
o banco (2% no máximo). Se a medida de verdade da máquina for outra (o cliente
viu a pista "larga"), mude o cadastro e as três constantes do começo do
`montar.js` (`ALT`, `LARG`, `COMP`) e gere de novo.

## As peças e os nomes (para o Blender)

As malhas e os materiais têm o MESMO nome (o `gltfpack -kn -km` guarda os dois):

| nome | o que é |
|---|---|
| `estrutura_mdf` | as chapas pretas acetinadas (as laterais, a frente, a testeira, o painel, a laje da pista, o teto, as costas e os suportes) |
| `lateral_esquerda_arte`, `lateral_direita_arte` | os adesivos de fora das laterais |
| `acab_esq`, `acab_dir` | a faixa do acabamento por dentro das laterais |
| `pista` | o adesivo da pista (a madeira com as setas) |
| `painel_tela` | o adesivo do painel da coluna (com o buraco do monitor) |
| `testeira_arte` | o adesivo da testeira |
| `frente_arte` | o adesivo da frente |
| `monitor` | a tela acesa (o jogo, `emissiveTexture`) |
| `moldura_monitor`, `camera_sensor`, `lente` | a moldura do monitor, a caixinha da câmera e a lente |
| `bolsao`, `bola_0`, `bola_1` | o bolsão das bolas e as duas bolas |
| `botao_aro`, `botao_vermelho` | o botão da frente |
| `neon_vermelho`, `neon_azul` | o neon flex |
| `led_pontos`, `led_fita` | a fita de LED (os pontos acesos e a tira preta) |

Os nomes que começam com `monitor`, `pista`, `bola`, `bolsao` e `led` nunca se
tingem nas cores do site (`core/static/site/arena/cores3d.js`, `SEM_TINGIR`).

## Refazer

    python3 extrair_do_glb.py <strike_kids.glb da fábrica>   # adesivos/*.png e os contornos no formas.json (já feito)
    python3 ../ampliar_adesivos.py .                          # adesivos-hd/*.webp (4x, nítido; precisa do modelo ONNX)
    python3 contornos_neon.py --previa                        # o caminho do neon (formas.json; precisa do OpenCV)
    node ../gerar_glb.cjs strike-kids                         # o .glb no static (e as vistas v-*.jpg aqui)

O `gerar_glb.cjs` precisa do `playwright` e do `gltfpack` (`npm install
playwright gltfpack`, ou o `NODE_PATH` apontando para eles); o three.js é o do
site (`core/static/vendor/three`). ~31 mil triângulos, ~2,7 MB.
