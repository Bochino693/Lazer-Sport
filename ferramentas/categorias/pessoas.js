/* ======================================================================
   AS CRIANÇAS DAS FOTOS DAS CATEGORIAS (ver cenas.js).

   O cliente: "nas categorias sim ponha as crianças" -- mas os bonecos de
   antes eram blocos. Estas têm proporção de criança (1,2 m, a cabeça grande,
   uns 1/5 da altura) e são REDONDAS: a cabeça e as mãos são esferas, os
   braços e as pernas são cápsulas, a camiseta e o short (ou a saia) são
   peças de torno com volume, a manga cobre o ombro, o tênis tem bico; a
   cabeça tem orelhas, olhos, nariz, a boca sorrindo e o CABELO (curto, de
   franja, rabo de cavalo, maria-chiquinha, cacheado, chanel). Cada uma é
   um esqueleto de juntas (quadril, tronco, pescoço, ombros, cotovelos,
   joelhos, tornozelos) parado numa pose natural do meio da brincadeira:
   correndo, andando, pulando, comemorando, jogando numa máquina, apontando,
   olhando. Os pés ficam no chão (a pose acerta a altura do quadril).
   As CAPAS dos produtos (as fotos individuais) não têm gente.
   ====================================================================== */

const PI = Math.PI;
const PELES = ["#f3c9a5", "#e0ac7e", "#c68a5b", "#9a6440", "#6e4428"];
const CABELOS = ["#2b1a10", "#4a2c17", "#121212", "#8a4b23", "#c8963e", "#5a3720"];
const CAMISAS = ["#ef4444", "#2563eb", "#facc15", "#16a34a", "#ec4899", "#f97316", "#8b5cf6", "#06b6d4", "#ffffff"];
const BAIXOS = ["#1e3a8a", "#1f2937", "#475569", "#7c3aed", "#0f766e", "#be185d"];
const TENIS = ["#f8fafc", "#ef4444", "#2563eb", "#111827", "#f59e0b"];
// cada uma: o penteado e se usa saia (as combinações se repetem com `i`)
const ESTILOS = [
  ["curto", false], ["rabo", true], ["franja", false], ["chiquinha", true],
  ["cacheado", false], ["chanel", true], ["curto", false], ["rabo", false],
];

/** As poses: os ângulos das juntas, em radianos (perna e braço para a FRENTE é negativo em x). */
const PARADA = {
  tronco: 0.02, cabeca: 0, giroCabeca: 0, inclinaCabeca: 0, giroTronco: 0,
  bE: 0.08, bD: 0.08, bEz: -0.14, bDz: 0.14, cE: -0.25, cD: -0.25,
  pE: 0, pD: 0, pEz: -0.04, pDz: 0.04, jE: 0.05, jD: 0.05, tE: -0.05, tD: -0.05,
};
export const POSES = {
  parada: {},
  // correndo, no meio da passada: um pé no chão, o outro lá atrás
  correndo: { pE: 0.55, pD: -0.75, jE: 1.25, jD: 0.35, tE: 0.3, tD: -0.1, bE: -0.85, bD: 0.75, cE: -1.35, cD: -1.1, tronco: 0.2, cabeca: -0.12 },
  andando: { pE: 0.28, pD: -0.32, jE: 0.35, jD: 0.12, bE: -0.32, bD: 0.3, cE: -0.45, cD: -0.35, tronco: 0.05 },
  // pulando com os braços para cima (no ar: o grupo sobe)
  pulando: { bE: -2.7, bD: -2.8, bEz: -0.35, bDz: 0.35, cE: -0.25, cD: -0.2, pE: -0.45, pD: -0.3, jE: 1.05, jD: 0.85, tE: 0.35, tD: 0.3, cabeca: -0.2, ar: 0.3 },
  // comemorando: os braços para o alto, em V
  comemorando: { bE: -2.55, bD: -2.5, bEz: -0.55, bDz: 0.55, cE: -0.35, cD: -0.3, cabeca: -0.18, inclinaCabeca: 0.1 },
  // jogando numa máquina: as mãos para a frente, na altura do painel
  jogando: { bE: -1.05, bD: -1.15, bEz: -0.12, bDz: 0.1, cE: -0.65, cD: -0.55, tronco: 0.16, cabeca: 0.18 },
  // apontando: o braço direito esticado para a frente e para cima, a cabeça virada
  apontando: { bD: -1.75, bDz: 0.2, cD: -0.08, bE: 0.12, cE: -0.35, giroCabeca: 0.35, cabeca: -0.08 },
  // olhando para a máquina, as mãos para trás, a cabeça um pouco de lado
  olhando: { bE: 0.35, bD: 0.38, bEz: -0.08, bDz: 0.08, cE: -0.9, cD: -0.9, cabeca: -0.06, inclinaCabeca: 0.12, pD: -0.08, jD: 0.12 },
};

export function criarPessoas(T) {
  const mats = new Map();
  const mat = (cor, aspereza = 0.8, extra = {}) => {
    const chave = cor + aspereza + JSON.stringify(extra);
    if (!mats.has(chave)) mats.set(chave, new T.MeshStandardMaterial(Object.assign({ color: cor, roughness: aspereza, metalness: 0 }, extra)));
    return mats.get(chave);
  };
  const malha = (geo, m, x = 0, y = 0, z = 0) => {
    const o = new T.Mesh(geo, m);
    o.position.set(x, y, z);
    o.castShadow = true;
    o.receiveShadow = true;
    return o;
  };
  const junta = (pai, x, y, z = 0) => {
    const j = new T.Group();
    j.position.set(x, y, z);
    pai.add(j);
    return j;
  };
  /** Uma cápsula de pé, do ponto da junta para baixo (`comprimento` total, com as pontas redondas). */
  const membro = (j, raio, comprimento, m, raio2) => {
    const c = malha(new T.CapsuleGeometry(raio, Math.max(0.001, comprimento - 2 * raio), 8, 16), m, 0, -comprimento / 2 + raio * 0.4, 0);
    if (raio2) c.scale.set(1, 1, raio2 / raio);
    j.add(c);
    return c;
  };
  /** Peça de torno (a camiseta, o short, a saia): `perfil` = [[raio, y], ...] de baixo para cima. */
  const torno = (perfil, m, achata = 0.78) => {
    const o = malha(new T.LatheGeometry(perfil.map(([r, y]) => new T.Vector2(r, y)), 32), m);
    o.scale.z = achata;
    return o;
  };

  function cabelo(cabeca, estilo, cor) {
    const m = mat(cor, 0.55, { envMapIntensity: 0.6 });
    // a calota em cima e atrás (o rosto fica de fora)
    const calota = malha(new T.SphereGeometry(0.121, 32, 20, 0, PI * 2, 0, PI * 0.47), m, 0, 0.012, -0.006);
    cabeca.add(calota);
    const nuca = malha(new T.SphereGeometry(0.119, 32, 20, PI, PI, PI * 0.3, PI * 0.42), m, 0, 0.0, -0.004);
    cabeca.add(nuca);
    if (estilo === "franja" || estilo === "chanel" || estilo === "chiquinha") {
      const franja = malha(new T.SphereGeometry(0.123, 24, 10, PI * 0.15, PI * 0.7, PI * 0.28, PI * 0.16), m, 0, 0.004, 0.004);
      cabeca.add(franja);
    }
    if (estilo === "curto" || estilo === "cacheado") {
      // o topete
      cabeca.add(malha(new T.SphereGeometry(0.06, 16, 10), m, 0.02, 0.09, 0.05));
    }
    if (estilo === "cacheado") {
      for (let k = 0; k < 16; k++) {
        const a = (k / 16) * PI * 2;
        const alto = k % 2 ? 0.07 : 0.035;
        cabeca.add(malha(new T.SphereGeometry(0.036, 12, 8), m, Math.cos(a) * 0.1, alto, Math.sin(a) * 0.1 - 0.01));
      }
    }
    if (estilo === "rabo") {
      cabeca.add(malha(new T.SphereGeometry(0.035, 12, 8), m, 0, 0.04, -0.125));
      const rabo = malha(new T.CapsuleGeometry(0.032, 0.12, 6, 12), m, 0, -0.04, -0.15);
      rabo.rotation.x = 0.35;
      cabeca.add(rabo);
    }
    if (estilo === "chiquinha") {
      for (const lado of [-1, 1]) {
        cabeca.add(malha(new T.SphereGeometry(0.03, 12, 8), m, lado * 0.115, 0.02, -0.03));
        const mecha = malha(new T.CapsuleGeometry(0.026, 0.09, 6, 12), m, lado * 0.135, -0.05, -0.035);
        mecha.rotation.z = lado * -0.25;
        cabeca.add(mecha);
      }
    }
    if (estilo === "chanel") {
      // o cabelo até o queixo, dos lados e atrás
      const lados = malha(new T.SphereGeometry(0.125, 32, 16, PI * 0.95, PI * 1.1, PI * 0.42, PI * 0.28), m, 0, 0.0, -0.002);
      cabeca.add(lados);
    }
  }

  function rosto(cabeca, pele) {
    const escuro = mat("#1c1917", 0.35);
    for (const lado of [-1, 1]) {
      // os olhos (com o brilho), a sobrancelha, a orelha e a bochecha
      cabeca.add(malha(new T.SphereGeometry(0.0145, 12, 10), escuro, lado * 0.038, 0.012, 0.098));
      cabeca.add(malha(new T.SphereGeometry(0.0045, 8, 6), mat("#ffffff", 0.2), lado * 0.034, 0.017, 0.111));
      const sobrancelha = malha(new T.CapsuleGeometry(0.004, 0.018, 4, 6), mat("#3b2416", 0.7), lado * 0.04, 0.042, 0.1);
      sobrancelha.rotation.z = PI / 2 + lado * 0.15;
      cabeca.add(sobrancelha);
      cabeca.add(malha(new T.SphereGeometry(0.026, 12, 10), mat(pele, 0.6), lado * 0.107, 0.0, -0.005));
      const bochecha = malha(new T.SphereGeometry(0.018, 10, 8), mat("#f19aa0", 0.8, { transparent: true, opacity: 0.45, depthWrite: false }), lado * 0.06, -0.022, 0.088);
      bochecha.scale.z = 0.4;
      bochecha.castShadow = false;
      cabeca.add(bochecha);
    }
    cabeca.add(malha(new T.SphereGeometry(0.014, 10, 8), mat(pele, 0.6), 0, -0.012, 0.11));
    // a boca sorrindo
    const boca = malha(new T.TorusGeometry(0.022, 0.0045, 6, 16, PI), mat("#9f1239", 0.5), 0, -0.04, 0.1);
    boca.rotation.z = PI;
    boca.rotation.x = -0.25;
    cabeca.add(boca);
  }

  /**
   * Uma criança de 1,2 m (`escala` muda a idade), de frente para +z, os pés no chão,
   * na pose pedida. `i` escolhe o penteado, as cores e a roupa.
   */
  function crianca(i, pose = "parada", escala = 1) {
    const [estilo, saia] = ESTILOS[i % ESTILOS.length];
    const pele = PELES[(i * 3) % PELES.length];
    const camisa = CAMISAS[(i * 5) % CAMISAS.length];
    const baixo = BAIXOS[(i * 7) % BAIXOS.length];
    const tenis = TENIS[(i * 3 + 1) % TENIS.length];
    const mPele = mat(pele, 0.55);
    const mCamisa = mat(camisa, 0.85);
    const mBaixo = mat(baixo, 0.85);

    const raiz = new T.Group();
    const quadril = junta(raiz, 0, 0.56);
    const tronco = junta(quadril, 0, 0.03);
    // a camiseta (com volume no peito e os ombros caídos) e o short ou a saia
    tronco.add(torno([[0.122, 0.0], [0.128, 0.08], [0.132, 0.18], [0.125, 0.25], [0.1, 0.3], [0.058, 0.325], [0.045, 0.33]], mCamisa));
    const gola = malha(new T.TorusGeometry(0.046, 0.008, 6, 20), mat(camisa === "#ffffff" ? "#cbd5e1" : "#ffffff", 0.8), 0, 0.325, 0);
    gola.rotation.x = PI / 2;
    gola.scale.y = 0.8;
    tronco.add(gola);
    if (saia) {
      quadril.add(torno([[0.19, -0.13], [0.16, -0.06], [0.128, 0.02], [0.124, 0.05]], mBaixo, 0.85));
    } else {
      quadril.add(torno([[0.135, -0.12], [0.132, -0.04], [0.125, 0.03], [0.123, 0.05]], mBaixo, 0.8));
    }
    const pescoco = junta(tronco, 0, 0.32);
    pescoco.add(malha(new T.CylinderGeometry(0.038, 0.042, 0.06, 16), mPele, 0, 0.02, 0));
    const cabeca = junta(pescoco, 0, 0.14);
    const cranio = malha(new T.SphereGeometry(0.11, 40, 30), mPele);
    cranio.scale.set(0.97, 1.02, 0.98);
    cabeca.add(cranio);
    rosto(cabeca, pele);
    cabelo(cabeca, estilo, CABELOS[(i * 5 + 2) % CABELOS.length]);

    // os braços: a manga no ombro, o braço, o antebraço e a mão
    const bracos = [-1, 1].map((lado) => {
      const ombro = junta(tronco, lado * 0.125, 0.27);
      const manga = malha(new T.CylinderGeometry(0.047, 0.05, 0.085, 20), mCamisa, 0, -0.035, 0);
      ombro.add(manga);
      ombro.add(malha(new T.SphereGeometry(0.047, 20, 12, 0, PI * 2, 0, PI / 2), mCamisa, 0, 0.007, 0));
      membro(ombro, 0.036, 0.19, mPele);
      const cotovelo = junta(ombro, 0, -0.18);
      cotovelo.add(malha(new T.SphereGeometry(0.034, 14, 10), mPele));
      membro(cotovelo, 0.032, 0.16, mPele);
      const mao = malha(new T.SphereGeometry(0.037, 16, 12), mPele, 0, -0.165, 0.004);
      mao.scale.set(0.85, 1.05, 0.7);
      cotovelo.add(mao);
      return { ombro, cotovelo };
    });
    // as pernas: a coxa, a canela, a meia e o tênis (de bico para a frente)
    const pernas = [-1, 1].map((lado) => {
      const coxa = junta(quadril, lado * 0.062, -0.02);
      membro(coxa, 0.05, 0.26, mPele);
      const joelho = junta(coxa, 0, -0.245);
      joelho.add(malha(new T.SphereGeometry(0.046, 14, 10), mPele));
      membro(joelho, 0.042, 0.24, mPele);
      joelho.add(malha(new T.CylinderGeometry(0.043, 0.041, 0.05, 16), mat("#f8fafc", 0.9), 0, -0.2, 0));
      const tornozelo = junta(joelho, 0, -0.235);
      const sapato = malha(new T.CapsuleGeometry(0.042, 0.07, 8, 16), mat(tenis, 0.6), 0, -0.022, 0.03);
      sapato.rotation.x = PI / 2;
      sapato.scale.set(1.05, 1, 0.72);
      tornozelo.add(sapato);
      const sola = malha(new T.BoxGeometry(0.085, 0.014, 0.15), mat("#e2e8f0", 0.9), 0, -0.048, 0.03);
      tornozelo.add(sola);
      return { coxa, joelho, tornozelo };
    });

    // a pose
    const p = Object.assign({}, PARADA, POSES[pose] || {});
    tronco.rotation.set(p.tronco, p.giroTronco, 0);
    cabeca.rotation.set(p.cabeca, p.giroCabeca, p.inclinaCabeca);
    bracos[0].ombro.rotation.set(p.bE, 0, p.bEz);
    bracos[1].ombro.rotation.set(p.bD, 0, p.bDz);
    bracos[0].cotovelo.rotation.x = p.cE;
    bracos[1].cotovelo.rotation.x = p.cD;
    pernas[0].coxa.rotation.set(p.pE, 0, p.pEz);
    pernas[1].coxa.rotation.set(p.pD, 0, p.pDz);
    pernas[0].joelho.rotation.x = p.jE;
    pernas[1].joelho.rotation.x = p.jD;
    pernas[0].tornozelo.rotation.x = p.tE;
    pernas[1].tornozelo.rotation.x = p.tD;
    // os pés no chão: o quadril desce até a sola mais baixa encostar em y = 0
    raiz.updateMatrixWorld(true);
    let maisBaixo = Infinity;
    for (const { tornozelo } of pernas) {
      tornozelo.children.forEach((o) => {
        const caixa = new T.Box3().setFromObject(o, true);
        maisBaixo = Math.min(maisBaixo, caixa.min.y);
      });
    }
    quadril.position.y -= maisBaixo;
    const grupo = new T.Group();
    grupo.add(raiz);
    grupo.position.y = (POSES[pose] || {}).ar || 0;
    grupo.scale.setScalar(escala);
    return grupo;
  }

  return { crianca };
}
