/* ======================================================================
   OS CAMINHOS DO PASSEIO POR DENTRO (a Arena 3D, arena3d.js, anda por eles)

   Puro: só as contas, sem three.js nem página -- o arena3d.js usa, e o
   core/tests_js/passeio.mjs confere cada caminho com a geometria de verdade
   do .glb (os olhos nunca entram numa peça, e nada atravessa os túneis).

   Cada ponto do caminho é [x, y, z, modo, extras] no objeto (metros, frente
   em +z, y = a altura dos PÉS ali); `amostrarCaminho` faz deles a curva que
   a câmera segue, amostrada a cada 6 cm, já com a altura dos olhos de cada
   amostra (ela abaixa ANTES de entrar no túnel e só sobe depois de sair).
   ====================================================================== */

const PI = Math.PI;
const limitar = (valor, menor, maior) => Math.min(maior, Math.max(menor, valor));

export const OLHOS = 0.85; // altura dos olhos acima do piso: uma criança

/* Cada ponto do caminho é [x, y, z, modo, extras] no objeto (metros, frente
   em +z, y = a altura dos PÉS ali) e o modo é o jeito de chegar nele:
     ir          desliza da entrada até o começo
     andar       passo normal (a cabeça balança de leve)
     agachado    andar abaixado (teto baixo: o andar de cima do brinquedão)
     subir       escada e escadinha: devagar, olhando para cima
     rede        engatinhando na rede: balança para os lados
     tubo        agachado, dentro do tubo
     viga        andando na beirada, equilibrando
     pular       quicando na cama elástica
     enterrada   o pulo grande da enterrada, até a cesta
     escorregar  escorregador e tobogã: sentado, acelerando, deitando nas curvas
     cair        o pulo na piscina de espuma ou de bolinhas (afunda)
     tirolesa    pendurado no pegador da tirolesa, por cima da espuma
   Extras: pausa (segundos parado), olhar (o ponto que se olha na pausa),
   evento (avisa a animação do objeto: "swish:2" = o próximo arremesso vai
   na cesta 2, a da enterrada).
   O caminho é calculado uma vez (uma curva amostrada a cada 6 cm): andar
   nele não custa conta nenhuma por quadro. */

/* O brinquedão: o projeto é em milímetros, como o .3ds (x ao longo, y para
   a frente, z para cima); o objeto 3D é o mesmo desenho, centralizado. */
const BQ = (x, y, z) => [-x / 1000 - 5.8705, z / 1000, y / 1000 + 1.948];

/* OS OLHOS NO EIXO DO TOBOGÃ: em todo tobogã fechado, os "pés" ficam 45 cm
   abaixo do centro do tubo (os olhos do "escorregar" estão 45 cm acima
   deles) e a curva é a do montar.js do objeto, com os mesmos pontos. Antes
   os pés iam no fundo do tubo: a cabeça ficava a 5-9 cm do teto e, nas
   curvas, o plano de perto da câmera cortava a parede (o "ferro" e o buraco
   que se via dentro do túnel). */
const EIXO = 450;

/** O tobogã em espiral do brinquedão (o desenho do objeto: 48 passos, raio 65 cm, tubo de 33 cm). */
function toboganDoBrinquedao() {
  const cx = -10590;
  const cy = -1500;
  const raio = 650;
  const a0 = (-50 * PI) / 180;
  const a1 = 2 * PI;
  const pontos = [];
  let fim = null;
  for (let i = 0; i <= 48; i++) {
    const t = i / 48;
    const a = a0 + (a1 - a0) * t;
    fim = [cx + raio * Math.cos(a), cy + raio * Math.sin(a)];
    pontos.push([...BQ(fim[0], fim[1], 2404 - t * 1974 - EIXO), "escorregar"]);
  }
  pontos.push([...BQ(fim[0], fim[1] + 380, 395 - EIXO), "escorregar"], [...BQ(fim[0], fim[1] + 700, 385 - EIXO), "escorregar"]);
  return pontos;
}

/** O escorregador duplo ondulado (a pista da direita), com os pés na pista. */
function escorregadorDuplo() {
  const x = -9023.5 + 260;
  const pontos = [];
  for (let i = 0; i <= 18; i++) {
    const t = i / 18;
    const z = 1104 - 844 * t + 110 * Math.sin(t * PI * 3) * (1 - t) - (t > 0.85 ? (t - 0.85) * 600 : 0) - 20;
    pontos.push([...BQ(x, -2620 + 1750 * t, z), "escorregar"]);
  }
  return pontos;
}

/* O Brinquedão Ninja: o .3ds dele tem a frente em y baixo (x ao longo, y
   para o FUNDO, z para cima, em mm); o objeto 3D é o mesmo desenho, virado
   para a frente em +z e centralizado (ferramentas/modelos3d/brinquedao-ninja/). */
const NJ = (x, y, z) => [x / 1000 - 7.58, z / 1000, -y / 1000 + 2.8375];

/** O tobogã em espiral do ninja (o TOBOGA do montar.js: 60 passos), com os olhos no eixo do tubo. */
function toboganDoNinja() {
  const pontos = [[...NJ(9900, 3060, 2530 - EIXO), "escorregar"]];
  for (let i = 0; i <= 60; i++) {
    const t = i / 60;
    const a = (-540 * t * PI) / 180;
    pontos.push([...NJ(9030 + 400 * Math.cos(a), 2290 + 400 * Math.sin(a), 2525 - 1885 * t - EIXO), "escorregar"]);
  }
  pontos.push([...NJ(8700, 2600, 580 - EIXO), "escorregar"], [...NJ(8760, 2850, 530 - EIXO), "escorregar"]);
  return pontos;
}

/** A espiral do tobogã do circuito kids (o desenho do Espaço Esportivo: 36 passos), com os olhos no eixo do tubo. */
function toboganKids() {
  const eixo = EIXO / 1000;
  const pontos = [[16.2, 2.0 - eixo, 7.35, "escorregar"], [17.2, 2.0 - eixo, 7.9, "escorregar"]];
  for (let i = 0; i <= 36; i++) {
    const t = i / 36;
    const a = -PI / 2 + t * PI * 3;
    pontos.push([17.8 + 0.75 * Math.cos(a), 1.95 - t * 1.25 - eixo, 9.4 + 0.75 * Math.sin(a), "escorregar"]);
  }
  return pontos;
}

/** O caminho de cada objeto (pelo id do modelo). */
export const CAMINHOS = {
  // escadinha, a rede da torre das bolas, o andar de cima com a rede de
  // escalada, o tubo e o saco, o tobogã em espiral; por trás, o andar do
  // meio e o escorregador duplo; e o brinquedão inteiro visto da frente
  "brinquedao-modelo-2": () => [
    [...BQ(-3323, -1900, 0), "ir"],
    [...BQ(-3323, -2450, 0), "andar"],
    // os degraus: 0,64 m na frente e 1,11 m atrás. A frente do módulo tem a
    // barra a 1,10 m: passa por baixo dela com a cabeça baixa e só então sobe
    [...BQ(-3323, -2580, 100), "subir"],
    [...BQ(-3323, -2750, 220), "subir"],
    [...BQ(-3323, -2880, 643), "subir"],
    [...BQ(-3323, -3050, 643), "subir"],
    [...BQ(-3323, -3250, 1109), "subir"],
    [...BQ(-3323, -3420, 1109), "agachado"],
    // sai de baixo do andar de cima para a rede da torre: entre a beira do
    // piso de cima (2,03 m) e a beira da rede (1,83 m) há 20 cm -- a cabeça
    // passa no meio deles (rente) e só sobe depois
    [...BQ(-2950, -3420, 1109), "agachado"],
    [...BQ(-2960, -3420, 1358), "agachado", { rente: true }],
    [...BQ(-2700, -3420, 1358), "agachado", { rente: true }],
    [...BQ(-2600, -3380, 1833), "subir"],
    [...BQ(-2450, -3300, 1833), "subir"],
    [...BQ(-1700, -2700, 1833), "rede", { pausa: 1.4, olhar: BQ(-1318, -3085, 2380) }],
    [...BQ(-2550, -3150, 1833), "rede"],
    // da rede para a beira do andar de cima (sobe antes de passar por baixo dele)
    [...BQ(-2720, -3150, 2074), "subir"],
    // o andar de cima tem o teto baixo: anda-se abaixado
    [...BQ(-3300, -3150, 2074), "agachado"],
    // a rede de escalada (laranja, inclinada: baixa na frente, alta no fundo):
    // entra pela beira da frente, sobe por ela até o alto e desce do outro
    // lado. Antes o caminho ia de lado, a 2,49 m, e a cabeça batia nas barras
    // do teto (3,04 m) de cada coluna
    [...BQ(-3700, -2850, 2074), "agachado"],
    [...BQ(-4100, -2850, 2270), "rede"],
    [...BQ(-4550, -3250, 2580), "rede", { pausa: 0.8, olhar: BQ(-4550, -2000, 2300) }],
    [...BQ(-4950, -2850, 2270), "rede"],
    [...BQ(-5450, -3000, 2074), "agachado"],
    [...BQ(-5600, -3350, 2074), "agachado"],
    [...BQ(-6420, -3350, 2074), "agachado"],
    [...BQ(-6460, -3150, 2084), "agachado"],
    [...BQ(-7460, -3150, 2084), "tubo"],
    [...BQ(-7750, -2850, 2074), "agachado"],
    [...BQ(-8300, -2850, 2074), "agachado", { pausa: 0.8, olhar: BQ(-7990, -3150, 2450) }],
    [...BQ(-9300, -2900, 2074), "agachado"],
    [...BQ(-10150, -2600, 2074), "agachado"],
    // atrás da boca do tobogã, de frente para ela
    [...BQ(-10470, -2360, 2074), "agachado", { pausa: 0.9, olhar: BQ(-10172, -1998, 2250) }],
    [...BQ(-10264, -2075, 2104), "agachado"],
    ...toboganDoBrinquedao(),
    [...BQ(-9940, -450, 120), "cair"],
    [...BQ(-9940, 250, 0), "andar"],
    // a volta pela ponta do tobogã até a escada de marinheiro de trás
    [...BQ(-11950, 100, 0), "andar"],
    [...BQ(-11950, -2000, 0), "andar"],
    [...BQ(-11300, -3950, 0), "andar"],
    [...BQ(-9023, -3950, 0), "andar"],
    [...BQ(-9023, -3880, 560), "subir"],
    [...BQ(-9023, -3800, 1104), "subir"],
    [...BQ(-9023, -3450, 1104), "agachado"],
    [...BQ(-8763, -2700, 1104), "agachado", { pausa: 0.8, olhar: BQ(-8763, -870, 300) }],
    ...escorregadorDuplo(),
    [...BQ(-8763, -650, 120), "cair"],
    [...BQ(-8763, 250, 0), "andar"],
    [...BQ(-5500, 250, 0), "andar", { pausa: 1.6, olhar: BQ(-5500, -2200, 1700) }],
  ],
  // o canto em L e os degraus, o circuito do andar de cima (cilindros,
  // postes com pegas, o rolo vazado, a rede em V), o tobogã, a piscina de
  // bolinhas, as duas camas elásticas, a tirolesa e o pulo na espuma; e o
  // brinquedão inteiro visto da frente
  "brinquedao-ninja": () => [
    [...NJ(1750, 1300, 0), "ir"],
    // entra pelo lado direito do canto e sobe: degrau, triângulo azul, degrau, triângulo amarelo
    [...NJ(1750, 2700, 0), "andar"],
    // entra por baixo da barra do quadro (1,18 m, em x = 1480) e só então
    // sobe no degrau amarelo (0,65 m, de 1440 para dentro): a cabeça passa
    // baixa debaixo da barra
    [...NJ(1580, 2700, 0), "andar"],
    [...NJ(1430, 2700, 250), "subir"],
    [...NJ(1340, 2700, 420), "subir"],
    [...NJ(1260, 2700, 650), "subir"],
    [...NJ(1000, 2250, 1222), "subir"],
    [...NJ(785, 2300, 1742), "subir"],
    [...NJ(1020, 2720, 2260), "subir"],
    // o andar de cima tem o teto baixo: anda-se abaixado
    [...NJ(980, 3460, 2260), "agachado"],
    [...NJ(1400, 3480, 2260), "agachado", { pausa: 1, olhar: NJ(1690, 3480, 2800) }],
    // entre os cilindros pendurados (empurrando)
    [...NJ(1700, 3485, 2260), "agachado"],
    [...NJ(2200, 3560, 2260), "agachado"],
    [...NJ(2900, 3462, 2260), "agachado"],
    // os postes com as pegas
    [...NJ(3350, 3462, 2260), "agachado", { pausa: 0.9, olhar: NJ(3580, 3000, 2750) }],
    [...NJ(4400, 3462, 2260), "agachado"],
    // por dentro do rolo vazado
    [...NJ(4600, 3462, 2300), "tubo"],
    [...NJ(5440, 3462, 2300), "tubo"],
    [...NJ(5700, 3462, 2260), "agachado"],
    [...NJ(6250, 3462, 2290), "agachado"],
    // a passarela de rede em V, pela faixa verde do meio
    [...NJ(6500, 3462, 2290), "rede"],
    [...NJ(8200, 3462, 2290), "rede"],
    // o módulo vermelho, por trás do cilindro, até a boca do tobogã
    [...NJ(8550, 3400, 2260), "agachado"],
    [...NJ(8800, 3250, 2260), "agachado"],
    [...NJ(9600, 3250, 2260), "agachado"],
    // o capuz verde em cima da boca é meio tubo: dá a volta por trás dele e
    // entra pelo eixo (de lado, a cabeça atravessava a parede dele)
    [...NJ(9600, 3700, 2260), "agachado"],
    [...NJ(9980, 3760, 2260), "agachado"],
    [...NJ(10120, 3420, 2260), "agachado", { pausa: 0.8, olhar: NJ(9700, 2600, 2000) }],
    ...toboganDoNinja(),
    [...NJ(8950, 3150, 300), "cair", { pausa: 1.2, olhar: NJ(9300, 2300, 1400) }],
    // pela piscina de bolinhas até a saída da frente (por baixo do corrimão) e os degraus
    [...NJ(9650, 3250, 300), "andar"],
    [...NJ(9900, 2750, 300), "andar"],
    [...NJ(10200, 2250, 320), "andar"],
    [...NJ(10200, 2000, 330), "rastejar"],
    [...NJ(10180, 1870, 300), "subir"],
    [...NJ(10180, 1700, 150), "subir"],
    [...NJ(10180, 1400, 0), "andar"],
    // a primeira cama elástica: degraus, a entrada sob o corrimão e os pulos
    [...NJ(12240, 1350, 0), "andar"],
    [...NJ(12240, 1700, 150), "subir"],
    [...NJ(12240, 1880, 300), "subir"],
    [...NJ(12240, 2080, 330), "rastejar"],
    [...NJ(12160, 2300, 330), "andar"],
    [...NJ(11700, 2600, 330), "pular"],
    [...NJ(11000, 3300, 330), "pular"],
    [...NJ(11480, 2970, 330), "pular", { pausa: 1.6 }],
    [...NJ(10900, 2500, 330), "pular"],
    [...NJ(11900, 3400, 330), "pular"],
    [...NJ(12240, 2200, 330), "pular"],
    [...NJ(12240, 2000, 330), "rastejar"],
    [...NJ(12240, 1800, 300), "subir"],
    [...NJ(12240, 1650, 150), "subir"],
    [...NJ(12400, 1350, 0), "andar"],
    // a segunda cama
    [...NJ(14400, 1350, 0), "andar"],
    [...NJ(14400, 1700, 150), "subir"],
    [...NJ(14400, 1880, 300), "subir"],
    [...NJ(14400, 2080, 330), "rastejar"],
    [...NJ(14320, 2300, 330), "andar"],
    [...NJ(13800, 2700, 330), "pular"],
    [...NJ(13100, 3350, 330), "pular"],
    [...NJ(13600, 2970, 330), "pular", { pausa: 1.6 }],
    [...NJ(13000, 2450, 330), "pular"],
    [...NJ(14000, 3300, 330), "pular"],
    [...NJ(14400, 2200, 330), "pular"],
    [...NJ(14400, 2000, 330), "rastejar"],
    [...NJ(14400, 1800, 300), "subir"],
    [...NJ(14400, 1650, 150), "subir"],
    [...NJ(14300, 1300, 0), "andar"],
    // de volta pela frente até a saída da piscina de cubos: sobe no bloco rosa
    [...NJ(7860, 1300, 0), "andar"],
    [...NJ(7860, 2550, 0), "andar"],
    [...NJ(7860, 2700, 150), "subir"],
    [...NJ(7860, 2870, 300), "subir"],
    [...NJ(7700, 3300, 450), "subir"],
    [...NJ(7480, 3600, 450), "andar", { pausa: 1, olhar: NJ(6700, 3462, 1500) }],
    // a tirolesa por cima da espuma (por trás do poste da estrela) e o pulo nos cubos
    [...NJ(6950, 3700, 560), "tirolesa"],
    [...NJ(6600, 3570, 560), "tirolesa"],
    [...NJ(3500, 3462, 560), "tirolesa"],
    // (olha as cordas, e não ao longo da viga: de baixo ela fica escura)
    [...NJ(3250, 3462, 280), "cair", { pausa: 1.4, olhar: NJ(2240, 3100, 1300) }],
    // pela espuma de volta ao bloco, desce os degraus e olha o brinquedão inteiro
    [...NJ(5200, 3500, 300), "andar"],
    [...NJ(7100, 3700, 300), "andar"],
    [...NJ(7700, 3500, 450), "subir"],
    [...NJ(7860, 2870, 300), "subir"],
    [...NJ(7860, 2700, 150), "subir"],
    [...NJ(7600, 1200, 0), "andar"],
    [...NJ(7200, -2400, 0), "andar", { pausa: 1.8, olhar: NJ(7200, 3000, 1500) }],
  ],
  // da entrada: o Gol Flash (telão e os dois círculos), as quadras, a
  // piscina de espuma grande, as camas (por cima do varredor), a enterrada
  // na cesta (o Swish arremessa nela), a beirada das piscinas do percurso,
  // o circuito kids com a rede e o tobogã, e o espaço inteiro no fim
  "espaco-esportivo-modelo-1": () => [
    [0, 0.05, 10.4, "ir"],
    // o Gol Flash: cada círculo com a criança chutando, os LEDs e a tela
    [-12.5, 0.05, 6.6, "andar", { pausa: 2.5, olhar: [-12.5, 0.6, 1.4] }],
    [-6.5, 0.05, 6.6, "andar", { pausa: 2.5, olhar: [-6.5, 0.6, 1.4] }],
    [-1.2, 0.05, 2.0, "andar"],
    [-1.2, 0.05, -2.6, "andar", { pausa: 2, olhar: [-5.5, 2.0, -5] }],
    [-1.3, 0.05, -4.0, "andar"],
    [-0.45, 0.45, -4.0, "subir"],
    [0.35, 0.97, -4.0, "subir"],
    [3.6, 0.97, -5.15, "andar", { pausa: 0.8, olhar: [3.6, 0.9, -8.5] }],
    // na piscina de espuma: os olhos rentes aos cubos (dentro deles, a câmera via o avesso de cada um)
    [3.6, 0.86, -8.2, "cair", { pausa: 1.6, olhar: [3.6, 2.4, -11.2] }],
    [3.6, 0.97, -5.4, "subir"],
    [3.6, 0.98, -2.7, "pular"],
    [1.6, 0.98, 0.3, "pular"],
    [3.6, 0.98, 2.3, "pular"],
    [5.6, 0.98, 0.3, "pular"],
    [7.6, 0.98, 2.3, "pular"],
    [9.6, 0.98, 0.3, "pular"],
    [7.6, 0.98, -1.7, "pular"],
    // por cima dos braços do varredor (o poste do meio fica de lado)
    [9.6, 0.98, -1.7, "pular"],
    [9.6, 0.98, -3.7, "pular"],
    [11.6, 0.98, -5.7, "pular"],
    // as cestas do Swish: as crianças arremessando e as telas; a do meio é a sua
    [11.6, 0.98, -7.7, "pular", { pausa: 2.2, olhar: [11.6, 3.0, -11.0], evento: "swish:2" }],
    [11.6, 0.97, -8.85, "andar"],
    [11.6, 1.9, -10.25, "enterrada", { pausa: 0.7, olhar: [11.6, 2.8, -10.88] }],
    [11.6, 0.97, -8.4, "cair"],
    [12.75, 0.97, -6.0, "andar"],
    // na beirada entre as piscinas do percurso, e o pulo na espuma
    [12.75, 0.97, -0.9, "viga"],
    [13.6, 0.97, -0.7, "viga"],
    [13.6, 0.86, 1.3, "cair", { pausa: 1.6, olhar: [13.1, 2.0, 0.1] }],
    [13.6, 0.97, 3.15, "subir"],
    // pela beirada até a escada da frente, e desce degrau por degrau
    [12.9, 0.97, 3.15, "viga"],
    [11.65, 0.97, 3.15, "andar"],
    [11.65, 0.85, 3.45, "subir"],
    [11.65, 0.64, 3.75, "subir"],
    [11.65, 0.43, 4.05, "subir"],
    [11.65, 0.21, 4.35, "subir"],
    [11.65, 0.05, 4.85, "subir"],
    // entre o parque e o circuito kids, até a frente do circuito
    [10.0, 0.05, 5.8, "andar"],
    [0.4, 0.05, 5.8, "andar"],
    [-0.1, 0.05, 7.4, "andar"],
    [0.6, 0.05, 9.3, "andar"],
    [5.7, 0.05, 9.45, "andar"],
    // a rede amarela: sobe pela frente até o deck de cima
    [5.7, 0.65, 8.95, "subir"],
    [5.7, 1.8, 8.12, "rede"],
    [5.7, 1.85, 7.82, "subir"],
    [8.6, 1.85, 7.84, "agachado"],
    [12.0, 1.85, 7.84, "agachado"],
    [15.7, 1.85, 7.6, "agachado", { pausa: 0.8, olhar: [17.8, 1.0, 9.4] }],
    ...toboganKids(),
    // a saída do tubo aponta para -x: cai na frente dela (e não ao lado, rente à parede do tubo)
    [17.35, 0.3, 10.2, "cair", { pausa: 1.6, olhar: [16.5, 0.6, 10.4] }],
    [16.4, 0.62, 10.8, "subir"],
    [15.9, 0.05, 10.8, "andar"],
    [14.6, 0.05, 10.8, "andar", { pausa: 2, olhar: [0, 1.5, 0] }],
  ],
};

/* O trampolim de enterrada (num bloco próprio, fora do CAMINHOS: fácil de
   juntar com os caminhos dos outros objetos). O projeto é em milímetros,
   como o .3ds: x ao longo, com a parede da cesta em x = 0; y para o fundo,
   com a frente em y = 0; z para cima. O objeto 3D é o mesmo desenho,
   centralizado (o deslocamento sai do gerar.cjs de
   ferramentas/modelos3d/trampolim-enterrada/). */
const TE = (x, y, z) => [x / 1000 - 2.9962, z / 1000, -y / 1000 + 1.1475];
// o aro: no alto da parede inclinada, colado embaixo da moldura de cima (como no desenho da fábrica)
const ARO_DO_TRAMPOLIM = TE(566, 1130, 2695);
// sobe a escada da cabeceira (da frente para o fundo), pula pelas três camas
// em linha até a da cesta, enterra, volta pulando, desce a escada e olha o
// trampolim inteiro de fora
CAMINHOS["trampolim-enterrada"] = () => [
  [...TE(6350, -350, 0), "ir"],
  [...TE(5710, 650, 0), "andar"],
  // a escada fica na metade do fundo da cabeceira: três degraus de 27,75 cm
  // (22 cm de piso) e o bloco de cima, no fundo, a 1,11 m
  [...TE(5710, 1131, 278), "subir"],
  [...TE(5710, 1351, 555), "subir"],
  [...TE(5710, 1571, 833), "subir"],
  [...TE(5710, 1906, 1110), "subir", { pausa: 1.2, olhar: ARO_DO_TRAMPOLIM }],
  // a última cama, a do meio e a da cesta (a lona fica a 1,02 m)
  [...TE(4690, 1500, 1015), "pular"],
  [...TE(4690, 900, 1015), "pular"],
  [...TE(3210, 1130, 1015), "pular"],
  [...TE(3210, 700, 1015), "pular"],
  [...TE(3210, 1450, 1015), "pular"],
  [...TE(1650, 1130, 1015), "pular", { pausa: 1.6, olhar: ARO_DO_TRAMPOLIM }],
  // a enterrada: o pulo grande até o aro, e a queda de volta na cama
  [...TE(1080, 1130, 1895), "enterrada", { pausa: 0.8, olhar: ARO_DO_TRAMPOLIM }],
  [...TE(1800, 1130, 1015), "cair", { pausa: 1.2, olhar: TE(566, 1130, 2340) }],
  // de volta pelas camas até a escada, e desce degrau por degrau
  [...TE(3210, 1130, 1015), "pular"],
  [...TE(4690, 1500, 1015), "pular"],
  [...TE(5710, 1906, 1110), "subir"],
  [...TE(5710, 1571, 833), "subir"],
  [...TE(5710, 1351, 555), "subir"],
  [...TE(5710, 1131, 278), "subir"],
  [...TE(5710, 650, 0), "subir"],
  // e o trampolim inteiro, de fora, de 3/4
  [...TE(6600, -1600, 0), "andar"],
  [...TE(5600, -3300, 0), "andar", { pausa: 2, olhar: TE(2750, 1130, 1500) }],
];

/* O Brinquedão Modelo 4 (num bloco próprio, como o do trampolim). O projeto
   é em milímetros, como o .3ds: x ao longo, y para o FUNDO, z para cima; o
   objeto 3D é o mesmo desenho, virado para a frente em +z e centralizado (o
   deslocamento sai do gerar.cjs de ferramentas/modelos3d/brinquedao-modelo-4/).
   O andar de cima fica a 2,595 m (a faixa da rede em V, a 2,575 m). */
const M4 = (x, y, z) => [x / 1000 - 10.8075, z / 1000, -y / 1000 + 5.43];

/** O tobogã espiral do Modelo 4 (o TOBOGA do montar.js: de 15 em 15 graus), com os olhos no eixo do tubo. */
function toboganDoModelo4() {
  const pontos = [[...M4(19020, 4200, 2880 - EIXO), "escorregar"], [...M4(19020, 4110, 2880 - EIXO), "escorregar"]];
  for (let a = 180; a <= 880 + 0.01; a += 15) {
    const r = (a * PI) / 180;
    pontos.push([...M4(19590 + 570 * Math.cos(r), 3900 + 570 * Math.sin(r), 2880 - ((a - 180) / 700) * 2240 - EIXO), "escorregar"]);
  }
  pontos.push([...M4(18880, 3250, 560 - EIXO), "escorregar"]);
  return pontos;
}

// sobe a escada da ponta esquerda, atravessa o trecho de 12 m (rolos em pé,
// as redes em V, a pirâmide), a passagem pelos rolos magenta, o trecho de
// 9 m (o saco, os pares de rolos, o rolo amarelo, a rede), desce o tobogã até
// a piscina de bolinhas, sai pela escadinha verde e olha a Área Baby e o
// brinquedão inteiro
CAMINHOS["brinquedao-modelo-4"] = () => [
  [...M4(1550, 5200, 0), "ir"],
  [...M4(1550, 6350, 0), "andar"],
  // a escada: o piso de baixo, o piso pink do meio (1,59 m, a metade do
  // fundo) e o amarelo de cima (2,595 m, a metade da frente). Cada subida é
  // na metade de baixo, longe da diagonal; só passa a diagonal com os olhos
  // acima do piso da outra metade (antes, a cabeça entrava no piso pink)
  [...M4(1550, 6800, 240), "subir"],
  [...M4(1750, 6760, 240), "andar"],
  [...M4(1850, 6800, 1100), "subir"],
  [...M4(1350, 7250, 1590), "subir"],
  [...M4(1250, 7400, 2180), "subir"],
  [...M4(1850, 6950, 2595), "subir"],
  // o andar de cima tem o teto baixo: anda-se abaixado, pelo lado dos rolos em pé
  [...M4(2250, 6850, 2595), "agachado", { pausa: 0.9, olhar: M4(2500, 7100, 3050) }],
  // pela frente do rolo vermelho em pé (o caminho de antes passava por dentro dele)
  [...M4(2500, 6800, 2595), "agachado"],
  [...M4(2850, 6950, 2595), "agachado"],
  [...M4(2850, 7100, 2595), "agachado"],
  [...M4(3050, 7100, 2575), "rede"],
  [...M4(4850, 7100, 2575), "rede"],
  [...M4(5300, 7100, 2595), "agachado"],
  [...M4(6100, 6850, 2595), "agachado"],
  [...M4(6650, 6850, 2595), "agachado"],
  [...M4(6800, 7100, 2595), "agachado"],
  [...M4(6920, 7100, 2575), "rede"],
  [...M4(7750, 7100, 2575), "rede"],
  // por cima da pirâmide magenta
  [...M4(8050, 7100, 2595), "agachado"],
  [...M4(8300, 7100, 2880), "agachado"],
  [...M4(8600, 7100, 2595), "agachado"],
  [...M4(9900, 7100, 2595), "agachado"],
  [...M4(10050, 6800, 2595), "agachado"],
  [...M4(10500, 6850, 2595), "agachado"],
  [...M4(10650, 7100, 2595), "agachado"],
  [...M4(10780, 7100, 2575), "rede"],
  [...M4(11640, 7100, 2575), "rede"],
  // a passagem: por cima do rolo baixo, por baixo do alto, por cima do outro baixo
  [...M4(12170, 7100, 2595), "agachado", { pausa: 0.8, olhar: M4(12170, 5300, 2900) }],
  [...M4(12170, 6520, 2595), "agachado"],
  [...M4(12170, 6280, 2925), "subir"],
  [...M4(12170, 6020, 2595), "agachado"],
  [...M4(12170, 5760, 2595), "rastejar"],
  [...M4(12170, 5510, 2595), "agachado"],
  [...M4(12170, 5280, 2925), "subir"],
  [...M4(12170, 4950, 2595), "agachado"],
  // o saco azul e o par de rolos amarelos (passa-se pela fresta entre os dois)
  [...M4(11900, 4650, 2595), "agachado", { pausa: 0.8, olhar: M4(12170, 4405, 3100) }],
  [...M4(11900, 4150, 2595), "agachado"],
  [...M4(12450, 4130, 2595), "agachado"],
  [...M4(12900, 4405, 2595), "tubo"],
  [...M4(13130, 4405, 2595), "tubo"],
  [...M4(13360, 4405, 2595), "tubo"],
  // o rolo amarelo em pé, pela frente, e a rede em V
  [...M4(13800, 4100, 2595), "agachado"],
  [...M4(14450, 4100, 2595), "agachado"],
  [...M4(14660, 4405, 2575), "rede"],
  [...M4(16500, 4405, 2575), "rede"],
  // o outro par de rolos e o outro saco
  [...M4(16880, 4405, 2595), "tubo"],
  [...M4(17100, 4405, 2595), "tubo"],
  [...M4(17330, 4405, 2595), "tubo"],
  [...M4(17700, 4150, 2595), "agachado"],
  [...M4(18350, 4150, 2595), "agachado", { pausa: 0.7, olhar: M4(18050, 4405, 3100) }],
  // atrás da boca do tobogã, de frente para ela
  [...M4(18800, 4700, 2595), "agachado"],
  [...M4(19020, 4650, 2595), "agachado", { pausa: 0.9, olhar: M4(19020, 3900, 2400) }],
  ...toboganDoModelo4(),
  [...M4(19150, 3100, 280), "cair", { pausa: 1.2, olhar: M4(19590, 3900, 1700) }],
  // pela piscina até o arco azul, por cima da mureta e a escadinha verde
  [...M4(19800, 3150, 300), "andar"],
  [...M4(20105, 2900, 430), "subir"],
  [...M4(20105, 2720, 430), "subir"],
  [...M4(20105, 2530, 215), "subir"],
  [...M4(20105, 2250, 0), "andar"],
  // a Área Baby, de frente, e o brinquedão inteiro
  [...M4(15070, 2200, 0), "andar", { pausa: 1.4, olhar: M4(15070, 3500, 1200) }],
  [...M4(11500, -5500, 0), "andar", { pausa: 2, olhar: M4(11000, 5500, 1500) }],
];

/** Um objeto sem caminho próprio: a volta em torno dele, parando em cada lado. */
export function voltaEmVolta(m) {
  const a = (m.W || m.largura) / 2 + 0.9;
  const b = (m.D || m.fundo) / 2 + 0.9;
  const centro = [0, (m.H || m.altura) * 0.4, 0];
  const pontos = [];
  for (let i = 0; i <= 8; i++) {
    const t = (i / 8) * PI * 2;
    pontos.push([Math.sin(t) * a, 0, Math.cos(t) * b, "andar", i % 2 ? {} : { pausa: 1.2, olhar: centro }]);
  }
  return pontos;
}

/** O passo (m/s), a altura dos olhos, o quique e o nome de cada modo. */
export const MODOS_DO_PASSEIO = {
  ir: { v: 6, olhos: OLHOS, nome: "Chegando" },
  andar: { v: 1.4, olhos: OLHOS, nome: "Passeando" },
  agachado: { v: 0.9, olhos: 0.58, nome: "Andando abaixado" },
  subir: { v: 0.55, olhos: 0.65, olhar: 0.22, nome: "Subindo" },
  rede: { v: 0.6, olhos: 0.6, nome: "Na rede" },
  tubo: { v: 0.7, olhos: 0.45, nome: "No túnel" },
  rastejar: { v: 0.5, olhos: 0.32, nome: "Passando por baixo" },
  viga: { v: 0.75, olhos: OLHOS, nome: "Na beirada" },
  pular: { v: 1.5, olhos: OLHOS, quique: 0.8, nome: "Pulando" },
  enterrada: { v: 1.2, olhos: OLHOS, quique: 1.2, nome: "Enterrada!" },
  tirolesa: { v: 2.2, olhos: 0.75, nome: "Na tirolesa!" },
  escorregar: { v: 4.6, olhos: 0.45, nome: "Escorregando!" },
  cair: { v: 2.4, olhos: 0.45, olhar: -0.3, nome: "Tchibum!" },
};

/* O Brinquedão Modelo 3 (num bloco próprio, como o do trampolim). O projeto
   é em milímetros, como os .3ds: x ao longo da barra, y para o FUNDO (y = 0
   é a ponta da perna, onde fica a torre), z para cima. O objeto 3D é o mesmo
   desenho, virado para a frente em +z e centralizado (o deslocamento sai do
   gerar.cjs de ferramentas/modelos3d/brinquedao-modelo-3/). */
const M3 = (x, y, z) => [x / 1000 - 5, z / 1000, -y / 1000 + 2.6];

/** O tobogã em espiral do Modelo 3 (o TOBOGA do montar.js), com os olhos no meio do tubo. */
function toboganDoModelo3() {
  // OS OLHOS NO MEIO DO TUBO (raio de 25 cm): os "pés" 45 cm abaixo do
  // centro, e a curva é a mesma do montar.js (os mesmos 72 pontos): a câmera
  // fica a 25 cm da parede em toda a descida. Antes, com os olhos 9 cm abaixo
  // do teto, o plano de perto cortava a parede nas curvas.
  const pes = (x, y, z) => [...M3(x, y, z - 450), "escorregar"];
  const pontos = [pes(8650, 4720, 2165), pes(8850, 4720, 2163)];
  // 2,25 voltas de cima, no sentido do relógio, em volta da coluna do meio da
  // piscina (dentro da barra); os primeiros 2/3 de volta mais inclinados
  for (let i = 0; i <= 72; i++) {
    const u = (i / 72) * 2.25;
    const a = ((90 - u * 360) * PI) / 180;
    const z = u <= 0.67 ? 2160 - (680 * u) / 0.67 : 1480 - (930 * (u - 0.67)) / 1.58;
    pontos.push(pes(9000 + 520 * Math.cos(a), 4200 + 520 * Math.sin(a), z));
  }
  pontos.push(pes(9560, 3800, 510), pes(9600, 3580, 480));
  return pontos;
}

// entra pela torre da ponta da perna e sobe as plataformas em zigue-zague,
// atravessa a passarela de rede, o corredor de cunhas, o piso de rede com a
// bola-pêndulo, o balanço e os sacos de pancada; desce o tobogã em espiral
// dentro da piscina de bolinhas (na ponta direita da barra), sai pela
// escadinha da frente e olha o brinquedão inteiro
CAMINHOS["brinquedao-modelo-3"] = () => [
  [...M3(500, -1600, 0), "ir"],
  [...M3(500, -350, 0), "andar"],
  // a entrada embaixo da tela da frente (ela começa a 1 m): baixo até passar
  [...M3(600, -60, 0), "andar"],
  // as plataformas da torre: amarela (0,45 m), azul (0,9 m), azul (1,4 m) e a
  // amarela do 2º andar, alternando as metades da diagonal. Cada subida:
  // passa a diagonal ainda na altura do degrau de agora (os olhos ficam entre
  // o piso de cima e o de baixo) e só sobe longe da beira da outra plataforma
  [...M3(700, 250, 450), "subir"],
  [...M3(520, 480, 450), "subir"],
  [...M3(280, 720, 900), "subir"],
  [...M3(480, 520, 900), "subir"],
  [...M3(720, 280, 1400), "subir"],
  [...M3(500, 500, 1400), "subir"],
  [...M3(300, 750, 1900), "subir", { pausa: 1, olhar: M3(500, 200, 2900) }],
  // a passarela de rede, até o 1º módulo da barra
  [...M3(500, 1150, 1900), "rede"],
  [...M3(500, 3650, 1900), "rede", { pausa: 0.8, olhar: M3(4500, 3700, 2200) }],
  // o corredor de cunhas de espuma: sobe e desce cada uma
  [...M3(1500, 3700, 1900), "andar"],
  [...M3(2025, 3700, 1900), "andar"],
  ...[2230, 2640, 3050, 3460, 3870].flatMap((c) => [[...M3(c, 3700, 2200), "subir"], [...M3(c + 205, 3700, 1900), "andar"]]),
  // a passagem magenta e o piso de rede, por baixo da bola amarela pendurada
  [...M3(4500, 3700, 1940), "andar"],
  [...M3(4550, 4550, 1900), "rede"],
  [...M3(5100, 4420, 1900), "rede", { pausa: 1.2, olhar: M3(5500, 4700, 2650) }],
  [...M3(5500, 4300, 1900), "rede"],
  [...M3(6600, 4550, 1900), "rede"],
  // o balanço (as cordas vermelha e azul), visto do corredor dos sacos de
  // pancada, e o corredor entre as duas fileiras de sacos (sem passar pela
  // coluna do meio, onde o caminho de antes encostava)
  [...M3(6850, 4750, 1900), "andar", { pausa: 1, olhar: M3(7500, 3700, 2700) }],
  [...M3(7150, 4750, 1900), "agachado"],
  [...M3(7500, 4750, 1900), "agachado"],
  [...M3(7850, 4740, 1900), "agachado"],
  // o módulo amarelo de trás: entre os dois sacos azuis até a boca do tobogã
  [...M3(8400, 4700, 1900), "agachado"],
  [...M3(8480, 4720, 1900), "andar", { pausa: 0.9, olhar: M3(9300, 4500, 1700) }],
  ...toboganDoModelo3(),
  [...M3(9600, 3450, 300), "cair", { pausa: 1.2, olhar: M3(9000, 4200, 1300) }],
  // pela frente da piscina até a escadinha: por cima da mureta e os dois degraus
  [...M3(9550, 3380, 300), "andar"],
  [...M3(9550, 3260, 450), "subir"],
  [...M3(9550, 3110, 450), "subir"],
  [...M3(9550, 2940, 225), "subir"],
  [...M3(9550, 2600, 0), "andar"],
  // e o brinquedão inteiro, de frente
  [...M3(7000, -2400, 0), "andar"],
  [...M3(5000, -5200, 0), "andar", { pausa: 2, olhar: M3(5000, 3800, 1700) }],
];

/* ---------------------------------------------------------------- a curva
   A mesma Catmull-Rom centrípeta do three.js (CatmullRomCurve3, aberta):
   o passeio e o teste andam exatamente na mesma curva. */
function polinomio(x0, x1, x2, x3, dt0, dt1, dt2) {
  let t1 = (x1 - x0) / dt0 - (x2 - x0) / (dt0 + dt1) + (x2 - x1) / dt1;
  let t2 = (x2 - x1) / dt1 - (x3 - x1) / (dt1 + dt2) + (x3 - x2) / dt2;
  t1 *= dt1;
  t2 *= dt1;
  const c0 = x1;
  const c1 = t1;
  const c2 = -3 * x1 + 3 * x2 - 2 * t1 - t2;
  const c3 = 2 * x1 - 2 * x2 + t1 + t2;
  return (t) => c0 + c1 * t + c2 * t * t + c3 * t * t * t;
}

/** O ponto do trecho `k` (de pontos[k] a pontos[k + 1]) na fração `w` (0 a 1). */
function pontoDaCurva(pontos, k, w) {
  const l = pontos.length;
  const menos = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
  const mais = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
  const p0 = k > 0 ? pontos[k - 1] : mais(menos(pontos[0], pontos[1]), pontos[0]);
  const p1 = pontos[k];
  const p2 = pontos[k + 1];
  const p3 = k + 2 < l ? pontos[k + 2] : mais(menos(pontos[l - 1], pontos[l - 2]), pontos[l - 1]);
  const d2 = (a, b) => (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2;
  let dt0 = Math.pow(d2(p0, p1), 0.25);
  let dt1 = Math.pow(d2(p1, p2), 0.25);
  let dt2 = Math.pow(d2(p2, p3), 0.25);
  if (dt1 < 1e-4) dt1 = 1;
  if (dt0 < 1e-4) dt0 = dt1;
  if (dt2 < 1e-4) dt2 = dt1;
  return [0, 1, 2].map((e) => polinomio(p0[e], p1[e], p2[e], p3[e], dt0, dt1, dt2)(w));
}

/** Os modos em que o corpo sai do chão (a curva pode passar dos pontos na altura). */
const SOLTOS = ["escorregar", "pular", "enterrada", "cair"];
// os olhos abaixam ANTES de entrar num lugar baixo (o túnel, o tobogã) e só
// sobem depois de sair dele: a altura de cada amostra é a menor das que
// estão até ADIANTE metros à frente e ATRAS metros atrás, suavizada
const ADIANTE = 0.7;
const ATRAS = 0.45;
const SUAVE = 0.3;

/**
 * O caminho amostrado a cada 6 cm. `pontos`: [{ p: [x, y, z], modo, pausa,
 * olhar, evento }] (o primeiro é de onde se sai). Devolve as amostras
 * { p, s (metros desde o começo), modo, olhos (a altura dos olhos acima dos
 * pés), pausa, olhar, evento } e o total.
 */
export function amostrarCaminho(pontos) {
  const ps = pontos.map((q) => q.p);
  const n = pontos.length - 1;
  const amostras = [];
  let s = 0;
  for (let k = 0; k < n; k++) {
    const [a, b] = [ps[k], ps[k + 1]];
    const passos = Math.max(2, Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1], b[2] - a[2]) / 0.06));
    const y0 = Math.min(a[1], b[1]);
    const y1 = Math.max(a[1], b[1]);
    const solto = SOLTOS.includes(pontos[k + 1].modo);
    for (let j = k ? 1 : 0; j <= passos; j++) {
      const p = pontoDaCurva(ps, k, j / passos);
      // a curva suave não afunda no piso nem sobe além do degrau
      if (!solto) p[1] = limitar(p[1], y0, y1);
      const antes = amostras[amostras.length - 1];
      if (antes) s += Math.hypot(p[0] - antes.p[0], p[1] - antes.p[1], p[2] - antes.p[2]);
      amostras.push({ p, s, modo: pontos[k + 1].modo, ...(pontos[k + 1].rente ? { rente: true } : {}) });
    }
    const fim = amostras[amostras.length - 1];
    const ponto = pontos[k + 1];
    if (ponto.pausa) Object.assign(fim, { pausa: ponto.pausa, olhar: ponto.olhar || null });
    if (ponto.evento) fim.evento = ponto.evento;
  }
  // a altura dos olhos: a menor da janela (abaixa antes, sobe depois) e suavizada
  const alvo = amostras.map((q) => (MODOS_DO_PASSEIO[q.modo] || MODOS_DO_PASSEIO.andar).olhos);
  const menor = amostras.map((q, i) => {
    let m = alvo[i];
    for (let j = i; j < amostras.length && amostras[j].s - q.s <= ADIANTE; j++) m = Math.min(m, alvo[j]);
    for (let j = i; j >= 0 && q.s - amostras[j].s <= ATRAS; j--) m = Math.min(m, alvo[j]);
    return m;
  });
  amostras.forEach((q, i) => {
    let soma = 0;
    let peso = 0;
    for (let j = i; j < amostras.length && amostras[j].s - q.s <= SUAVE; j++) { soma += menor[j]; peso++; }
    for (let j = i - 1; j >= 0 && q.s - amostras[j].s <= SUAVE; j--) { soma += menor[j]; peso++; }
    // a média não sobe acima da janela: dentro do túnel fica o mais baixo
    q.olhos = Math.min(soma / peso, menor[i] + 0.02);
  });
  return { amostras, total: s };
}
