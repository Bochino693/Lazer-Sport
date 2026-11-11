/* ======================================================================
   AS CRIANÇAS DAS FOTOS DAS CATEGORIAS (ver cenas.js).

   São as mesmas crianças que brincam no Espaço Esportivo da Arena 3D
   (core/static/site/arena/arena3d.js, `montarCrianca`): a mesma malha
   única com esqueleto (quadril, tronco, cabeça, braços com cotovelo,
   pernas com joelho), as mesmas medidas (1,2 m) e as mesmas cores de pele,
   cabelo, camiseta e short. Aqui elas não andam: cada uma fica numa pose
   parada -- correndo, pulando, comemorando, jogando numa máquina --, como
   numa foto tirada no meio da brincadeira.
   ====================================================================== */

const PI = Math.PI;
const PELES = ["#f1c27d", "#e0ac69", "#c68642", "#8d5524"];
const CABELOS = ["#2b1b10", "#4a2c17", "#141414", "#8a4b23"];
const CAMISAS = ["#e63946", "#2f8bff", "#ffd700", "#22c55e", "#ff3df2", "#ff9f1c", "#ffffff"];
const SHORTS = ["#1d2b53", "#222222", "#3a4b6b", "#5b2a86"];

/** As poses (os ângulos das juntas, em radianos; braço e perna para a frente é negativo). */
const PARADA = {
  tronco: 0, cabeca: 0, giroCabeca: 0,
  bE: 0.05, bD: 0.05, bEz: -0.12, bDz: 0.12, cE: -0.2, cD: -0.2,
  pE: 0, pD: 0, pEz: 0, pDz: 0, jE: 0.04, jD: 0.04,
};
export const POSES = {
  parada: {},
  // correndo, no meio do passo
  correndo: { pE: 0.6, pD: -0.55, jE: 0.3, jD: 1.1, bE: -0.6, bD: 0.6, cE: -1.25, cD: -1.25, tronco: 0.18 },
  andando: { pE: 0.3, pD: -0.3, jE: 0.15, jD: 0.45, bE: -0.3, bD: 0.3, cE: -0.5, cD: -0.5 },
  // pulando com os braços para cima (no ar: o grupo sobe)
  pulando: { bE: -2.9, bD: -2.9, bEz: -0.35, bDz: 0.35, cE: -0.1, cD: -0.1, pE: -0.35, pD: -0.35, jE: 0.9, jD: 0.9, ar: 0.35 },
  // comemorando: os dois braços para o alto, de pé
  comemorando: { bE: -2.7, bD: -2.6, bEz: -0.5, bDz: 0.5, cE: -0.3, cD: -0.3, cabeca: -0.25 },
  // jogando numa máquina: as mãos para a frente, na altura do painel
  jogando: { bE: -1.2, bD: -1.25, bEz: -0.05, bDz: 0.05, cE: -0.4, cD: -0.35, tronco: 0.12, cabeca: 0.1 },
  // apontando (uma mão para o alto, chamando o amigo)
  apontando: { bD: -2.4, bDz: 0.3, cD: -0.1, bE: 0.1, giroCabeca: 0.5 },
};

/** Uma peça com a cor nos vértices; `osso`: a junta que a leva. */
function pecaColorida(T, geometria, cor, x, y, z, osso) {
  const g = geometria.index ? geometria.toNonIndexed() : geometria;
  if (g !== geometria) geometria.dispose();
  g.translate(x, y, z);
  const c = new T.Color(cor);
  const n = g.attributes.position.count;
  const cores = new Float32Array(n * 3);
  for (let i = 0; i < cores.length; i += 3) cores.set([c.r, c.g, c.b], i);
  g.setAttribute("color", new T.BufferAttribute(cores, 3));
  const indices = new Uint16Array(n * 4);
  const pesos = new Float32Array(n * 4);
  for (let i = 0; i < n; i++) {
    indices[i * 4] = osso;
    pesos[i * 4] = 1;
  }
  g.setAttribute("skinIndex", new T.BufferAttribute(indices, 4));
  g.setAttribute("skinWeight", new T.BufferAttribute(pesos, 4));
  return g;
}

function juntar(T, partes) {
  const nomes = Object.keys(partes[0].attributes).filter((nome) => nome !== "uv" && partes.every((p) => p.attributes[nome]));
  const total = partes.reduce((n, p) => n + p.attributes.position.count, 0);
  const g = new T.BufferGeometry();
  nomes.forEach((nome) => {
    const primeiro = partes[0].attributes[nome];
    const lista = new primeiro.array.constructor(total * primeiro.itemSize);
    let k = 0;
    partes.forEach((p) => {
      lista.set(p.attributes[nome].array, k);
      k += p.attributes[nome].array.length;
    });
    g.setAttribute(nome, new T.BufferAttribute(lista, primeiro.itemSize));
  });
  partes.forEach((p) => p.dispose());
  g.computeVertexNormals();
  return g;
}

/** Quanto o quadril desce com as pernas dobradas (os pés ficam no chão). */
function descida(p) {
  const perna = (a, j, z) => (0.26 * Math.cos(a) + 0.24 * Math.cos(a + j)) * Math.cos(z);
  return 0.5 - Math.max(perna(p.pE, p.jE, p.pEz), perna(p.pD, p.jD, p.pDz));
}

export function criarPessoas(T) {
  const material = new T.MeshStandardMaterial({ vertexColors: true, roughness: 0.75, metalness: 0 });

  /**
   * Uma criança de 1,2 m (`escala` muda a idade), de frente para +z, os pés no chão,
   * na pose pedida. `i` escolhe as cores.
   */
  function crianca(i, pose = "parada", escala = 1) {
    const osso = (pai, x, y) => {
      const b = new T.Bone();
      b.position.set(x, y, 0);
      if (pai) pai.add(b);
      return b;
    };
    const quadril = osso(null, 0, 0.6);
    const tronco = osso(quadril, 0, 0.06);
    const cabeca = osso(tronco, 0, 0.36);
    const bracoE = osso(tronco, -0.15, 0.31);
    const cotoveloE = osso(bracoE, 0, -0.2);
    const bracoD = osso(tronco, 0.15, 0.31);
    const cotoveloD = osso(bracoD, 0, -0.2);
    const pernaE = osso(quadril, -0.06, -0.05);
    const joelhoE = osso(pernaE, 0, -0.26);
    const pernaD = osso(quadril, 0.06, -0.05);
    const joelhoD = osso(pernaD, 0, -0.26);
    const ossos = [quadril, tronco, cabeca, bracoE, cotoveloE, bracoD, cotoveloD, pernaE, joelhoE, pernaD, joelhoD];
    const camisa = CAMISAS[(i * 5) % CAMISAS.length];
    const pele = PELES[i % PELES.length];
    const P = (geo, cor, x, y, z, junta) => pecaColorida(T, geo, cor, x, y, z, ossos.indexOf(junta));
    const cil = (r0, r1, h) => new T.CylinderGeometry(r0, r1, h, 10);
    const partes = [
      P(cil(0.115, 0.125, 0.15), SHORTS[(i * 3) % SHORTS.length], 0, 0.6, 0, quadril),
      P(cil(0.105, 0.12, 0.34), camisa, 0, 0.84, 0, tronco),
      P(new T.SphereGeometry(0.105, 14, 10), pele, 0, 1.1, 0, cabeca),
      P(new T.SphereGeometry(0.112, 14, 8, 0, PI * 2, 0, PI * 0.55), CABELOS[(i * 7) % CABELOS.length], 0, 1.115, -0.01, cabeca),
    ];
    [[-0.15, bracoE, cotoveloE], [0.15, bracoD, cotoveloD]].forEach(([x, ombro, cotovelo]) => {
      partes.push(
        P(cil(0.046, 0.042, 0.09), camisa, x, 0.925, 0, ombro),
        P(cil(0.034, 0.031, 0.2), pele, x, 0.87, 0, ombro),
        P(cil(0.031, 0.028, 0.2), pele, x, 0.67, 0, cotovelo),
        P(new T.SphereGeometry(0.036, 8, 6), pele, x, 0.565, 0, cotovelo),
      );
    });
    [[-0.06, pernaE, joelhoE], [0.06, pernaD, joelhoD]].forEach(([x, coxa, joelho]) => {
      partes.push(
        P(cil(0.05, 0.046, 0.26), pele, x, 0.42, 0, coxa),
        P(cil(0.046, 0.04, 0.24), pele, x, 0.17, 0, joelho),
        P(new T.BoxGeometry(0.09, 0.06, 0.15), "#f4f6ff", x, 0.035, 0.03, joelho),
      );
    });
    const corpo = new T.SkinnedMesh(juntar(T, partes), material);
    corpo.add(quadril);
    corpo.bind(new T.Skeleton(ossos));
    corpo.castShadow = true;
    corpo.receiveShadow = true;
    corpo.frustumCulled = false;
    // a pose
    const p = Object.assign({}, PARADA, POSES[pose] || {});
    tronco.rotation.x = p.tronco;
    cabeca.rotation.set(p.cabeca, p.giroCabeca, 0);
    bracoE.rotation.set(p.bE, 0, p.bEz);
    bracoD.rotation.set(p.bD, 0, p.bDz);
    cotoveloE.rotation.x = p.cE;
    cotoveloD.rotation.x = p.cD;
    pernaE.rotation.set(p.pE, 0, p.pEz);
    pernaD.rotation.set(p.pD, 0, p.pDz);
    joelhoE.rotation.x = p.jE;
    joelhoD.rotation.x = p.jD;
    quadril.position.y = 0.6 - descida(p);
    const grupo = new T.Group();
    grupo.add(corpo);
    grupo.position.y = (POSES[pose] || {}).ar || 0;
    grupo.scale.setScalar(escala);
    return grupo;
  }

  return { crianca };
}
