/* ======================================================================
   ARENA 3D — um parque à noite, com a roda dos brinquedos em 3D de verdade.

   A CENA: os brinquedos em estandes (pedestal com anel de luz), em roda e
   de frente para o centro, onde gira o alvo da marca sobre o símbolo da
   Lazer & Sport pintado no chão. As áreas da arena (jogos da Lazer &
   Sport, as máquinas que já fazíamos, trampolins e brinquedões) são
   trechos da roda, cada um com a sua cor no piso e a sua placa; os
   espaços grandes demais para a roda (o Espaço Esportivo) ficam no seu
   "reino", ao lado. Os botões de área -- e o próprio piso ou a placa da
   área, tocados no 3D -- levam a câmera até aquele trecho, que acende. O
   filtro de categoria é o único que tira máquinas da roda.

   SÓ ENTRA NA RODA QUEM TEM OBJETO 3D DE VERDADE: o .glb do cadastro
   (ObjetoTresD) ou o feito com os arquivos da fábrica (core/arena.py,
   MODELOS_3D). O volume que se levantava das fotos (recorte + casco) não
   era a máquina de verdade e saiu; quem não tem .glb segue na galeria de
   fotos da página. Ver `na_roda_3d`.

   EM VOLTA, O PARQUE (`montarParque`): a calçada com os pilares de luz e
   as bandeirinhas, o gramado com árvores, postes, bancos e canteiros, os
   caminhos que ligam as áreas, a mureta com a entrada e os carrinhos de
   pipoca e algodão-doce. E o CÉU de festa (`montarCeu`): o crepúsculo de
   anil a magenta, as estrelas, a silhueta do parque lá longe, os
   holofotes, uns fogos discretos e o confete no ar. Tudo leve: poucas
   chamadas de desenho (instâncias e peças juntadas), nenhuma luz nova de
   verdade e, com "menos movimento" no aparelho, o céu fica parado.

   DÁ PARA VER DE TODOS OS LADOS: o prato do estande gira (Frente,
   Direita, Costas, Esquerda), a câmera sobe (Cima) e a máquina levanta e
   tomba para mostrar a base (Baixo). Arrastar gira a câmera em volta. E o
   PASSEIO anda por dentro do objeto, na altura de uma criança.

   A FICHA FICA FORA DO PALCO: ao lado no computador, embaixo no celular.

   O QUE ESTE ARQUIVO NÃO FAZ: baixar o three.js (~170 KB) antes de o
   palco chegar perto da tela, nem num aparelho sem WebGL -- ali a lista
   de máquinas é a página.
   ====================================================================== */

const raiz = document.querySelector("[data-arena3d]");
if (raiz) iniciar(raiz);

const PI = Math.PI;
const CORES = ["#e63946", "#2f8bff", "#ffd700", "#3fd0ff", "#8a5cff", "#ff7a00", "#1fbf5b", "#ff3df2"];
const COR_DA_ZONA = { jogos: "#e63946", maquinas: "#2f8bff", brinquedoes: "#22c55e", esportivos: "#ff9f1c" };
const LADOS = ["perfil", "lado_direito", "verso", "lado_esquerdo"];
const NOME_DO_LADO = { perfil: "Frente", lado_direito: "Lado direito", verso: "Costas", lado_esquerdo: "Lado esquerdo" };
const VISTA_DO_LADO = { perfil: "frente", lado_direito: "direita", verso: "costas", lado_esquerdo: "esquerda" };
// o giro do prato que põe cada lado da máquina de frente para o centro
const GIRO_DA_VISTA = { frente: 0, direita: -PI / 2, costas: PI, esquerda: PI / 2, cima: 0, baixo: 0 };
// o lado da entrada (o portal), na roda: o nome do símbolo do chão olha para ele
const A_ENTRADA = 0.5;
// o horizonte do céu de festa: a neblina e o chão de longe têm esta cor
const HORIZONTE = "#3a1d6b";
const TOMBO = -1.3; // "Baixo": a máquina tomba para a frente e mostra a base

const limitar = (valor, menor, maior) => Math.min(maior, Math.max(menor, valor));
// o mesmo ângulo, na volta mais perto de onde o prato está
const giroMaisPerto = (atual, alvo) => alvo + Math.round((atual - alvo) / (2 * PI)) * 2 * PI;

function webglDisponivel() {
  try {
    const teste = document.createElement("canvas");
    return !!(window.WebGLRenderingContext && (teste.getContext("webgl2") || teste.getContext("webgl")));
  } catch (erro) {
    return false;
  }
}

function quandoPerto(elemento) {
  return new Promise((resolver) => {
    if (!("IntersectionObserver" in window)) return resolver();
    const observador = new IntersectionObserver((entradas) => {
      if (entradas.some((e) => e.isIntersecting)) {
        observador.disconnect();
        resolver();
      }
    }, { rootMargin: "400px 0px" });
    observador.observe(elemento);
  });
}

function avisar(palco, titulo, texto, erro = false) {
  const aviso = palco.querySelector("[data-arena-aviso]");
  if (!aviso) return;
  aviso.classList.toggle("erro", erro);
  aviso.classList.remove("sumiu");
  aviso.querySelector("[data-arena-aviso-titulo]").textContent = titulo;
  aviso.querySelector("[data-arena-aviso-texto]").textContent = texto;
}

function semTresD(raiz, motivo) {
  const palco = raiz.querySelector("[data-arena-palco]");
  raiz.classList.add("sem-3d");
  avisar(palco, "A arena 3D não abre neste aparelho", motivo + " As máquinas estão na lista logo abaixo.", true);
  const lista = raiz.querySelector("[data-arena-lista]");
  if (lista) lista.open = true;
}

async function iniciar(raiz) {
  const fonte = document.getElementById("arena-dados");
  const palco = raiz.querySelector("[data-arena-palco]");
  if (!fonte || !palco) return;
  if (!webglDisponivel()) {
    semTresD(raiz, "Este navegador não tem aceleração 3D (WebGL).");
    return;
  }

  await quandoPerto(palco);

  let THREE;
  try {
    THREE = await import(palco.dataset.three);
  } catch (erro) {
    console.error("Arena 3D: o motor não carregou", erro);
    semTresD(raiz, "Não foi possível carregar o motor 3D agora.");
    return;
  }

  try {
    const arena = new Arena(THREE, raiz, palco, JSON.parse(fonte.textContent));
    arena.ligar();
    window.lsArena = arena; // para depuração no console do navegador
  } catch (erro) {
    console.error("Arena 3D: falhou ao montar a cena", erro);
    semTresD(raiz, "Algo deu errado ao montar a cena.");
  }
}

/* As crianças que brincam no espaço: UMA malha por criança, com esqueleto
   (quadril, tronco, cabeça, braços com cotovelo, pernas com joelho) -- uma
   chamada de desenho só, e o corpo dobra de verdade para arremessar, chutar,
   pular e escalar. As cores ficam nos vértices (short, camiseta, pele,
   cabelo, tênis), num material só para todas. */
const PELES = ["#f1c27d", "#e0ac69", "#c68642", "#8d5524"];
const CABELOS = ["#2b1b10", "#4a2c17", "#141414", "#8a4b23"];
const CAMISAS = ["#e63946", "#2f8bff", "#ffd700", "#22c55e", "#ff3df2", "#ff9f1c", "#ffffff"];
const SHORTS = ["#1d2b53", "#222222", "#3a4b6b", "#5b2a86"];

/** Uma peça com a cor nos vértices (para juntar com as outras); `osso`: a junta que a leva. */
function pecaColorida(T, geometria, cor, x = 0, y = 0, z = 0, osso = -1) {
  const g = geometria.index ? geometria.toNonIndexed() : geometria;
  if (g !== geometria) geometria.dispose();
  g.translate(x, y, z);
  const c = new T.Color(cor);
  const n = g.attributes.position.count;
  const cores = new Float32Array(n * 3);
  for (let i = 0; i < cores.length; i += 3) cores.set([c.r, c.g, c.b], i);
  g.setAttribute("color", new T.BufferAttribute(cores, 3));
  if (osso >= 0) {
    const indices = new Uint16Array(n * 4);
    const pesos = new Float32Array(n * 4);
    for (let i = 0; i < n; i++) { indices[i * 4] = osso; pesos[i * 4] = 1; }
    g.setAttribute("skinIndex", new T.BufferAttribute(indices, 4));
    g.setAttribute("skinWeight", new T.BufferAttribute(pesos, 4));
  }
  return g;
}

/** Junta as peças numa geometria só (os atributos que todas têm; o uv, só se pedido). */
function juntarPecas(T, partes, comUv = false) {
  const nomes = Object.keys(partes[0].attributes).filter((nome) => (comUv || nome !== "uv") && partes.every((p) => p.attributes[nome]));
  const total = partes.reduce((n, p) => n + p.attributes.position.count, 0);
  const g = new T.BufferGeometry();
  nomes.forEach((nome) => {
    const primeiro = partes[0].attributes[nome];
    const lista = new primeiro.array.constructor(total * primeiro.itemSize);
    let k = 0;
    partes.forEach((p) => { lista.set(p.attributes[nome].array, k); k += p.attributes[nome].array.length; });
    g.setAttribute(nome, new T.BufferAttribute(lista, primeiro.itemSize));
  });
  partes.forEach((p) => p.dispose());
  return g;
}

/** Uma criança de 1,2 m, de frente para +z, com os pés na origem (no `grupo`). */
function montarCrianca(T, material, i) {
  const pele = PELES[i % PELES.length];
  const camisa = CAMISAS[(i * 5) % CAMISAS.length];
  const osso = (pai, x, y) => {
    const b = new T.Bone();
    b.position.set(x, y, 0);
    if (pai) pai.add(b);
    return b;
  };
  // o esqueleto parado (cada junta onde ela fica no corpo de pé)
  const quadril = osso(null, 0, 0.6);
  const tronco = osso(quadril, 0, 0.06); // 0,66
  const cabeca = osso(tronco, 0, 0.36); // 1,02
  const bracoE = osso(tronco, -0.15, 0.31); // o ombro, a 0,97
  const cotoveloE = osso(bracoE, 0, -0.2);
  const bracoD = osso(tronco, 0.15, 0.31);
  const cotoveloD = osso(bracoD, 0, -0.2);
  const pernaE = osso(quadril, -0.06, -0.05); // o quadril, a 0,55
  const joelhoE = osso(pernaE, 0, -0.26);
  const pernaD = osso(quadril, 0.06, -0.05);
  const joelhoD = osso(pernaD, 0, -0.26);
  const ossos = [quadril, tronco, cabeca, bracoE, cotoveloE, bracoD, cotoveloD, pernaE, joelhoE, pernaD, joelhoD];
  const P = (geo, cor, x, y, z, junta) => pecaColorida(T, geo, cor, x, y, z, ossos.indexOf(junta));
  const cilindro = (r0, r1, h) => new T.CylinderGeometry(r0, r1, h, 8);
  const partes = [
    P(cilindro(0.115, 0.125, 0.15), SHORTS[(i * 3) % SHORTS.length], 0, 0.6, 0, quadril),
    P(cilindro(0.105, 0.12, 0.34), camisa, 0, 0.84, 0, tronco),
    P(new T.SphereGeometry(0.105, 12, 10), pele, 0, 1.1, 0, cabeca),
    P(new T.SphereGeometry(0.112, 12, 8, 0, PI * 2, 0, PI * 0.55), CABELOS[(i * 7) % CABELOS.length], 0, 1.115, -0.01, cabeca),
  ];
  [[-0.15, bracoE, cotoveloE], [0.15, bracoD, cotoveloD]].forEach(([x, ombro, cotovelo]) => {
    partes.push(
      P(cilindro(0.046, 0.042, 0.09), camisa, x, 0.925, 0, ombro), // a manga
      P(cilindro(0.034, 0.031, 0.2), pele, x, 0.87, 0, ombro),
      P(cilindro(0.031, 0.028, 0.2), pele, x, 0.67, 0, cotovelo),
      P(new T.SphereGeometry(0.036, 8, 6), pele, x, 0.565, 0, cotovelo),
    );
  });
  [[-0.06, pernaE, joelhoE], [0.06, pernaD, joelhoD]].forEach(([x, coxa, joelho]) => {
    partes.push(
      P(cilindro(0.05, 0.046, 0.26), pele, x, 0.42, 0, coxa),
      P(cilindro(0.046, 0.04, 0.24), pele, x, 0.17, 0, joelho),
      P(new T.BoxGeometry(0.09, 0.06, 0.15), "#f4f6ff", x, 0.035, 0.03, joelho),
    );
  });
  const corpo = new T.SkinnedMesh(juntarPecas(T, partes), material);
  corpo.add(quadril);
  corpo.bind(new T.Skeleton(ossos));
  // a esfera do corte da câmera cobre os braços para cima e o pulo grupado
  corpo.boundingSphere = new T.Sphere(new T.Vector3(0, 0.7, 0), 1.15);
  const grupo = new T.Group();
  grupo.add(corpo);
  return {
    grupo, corpo, tronco, cabeca, bracoE, bracoD, cotoveloE, cotoveloD, pernaE, pernaD, joelhoE, joelhoD,
    pose: { ...POSE_PARADA },
  };
}

/* O CORPO EM MOVIMENTO. Cada criança pede uma pose (os ângulos de cada
   junta, em radianos) e o corpo vai até ela com uma mola curta: sem pulo
   de um movimento para o outro. Braço e perna para a frente é negativo;
   joelho e cotovelo dobram para o lado de sempre. Os pés ficam no chão
   sozinhos: o quadril desce o tanto que as pernas dobram (`descida`). */
const POSE_PARADA = {
  tronco: 0, cabeca: 0, giroCabeca: 0,
  bE: 0.05, bD: 0.05, bEz: -0.12, bDz: 0.12, cE: -0.2, cD: -0.2,
  pE: 0, pD: 0, pEz: 0, pDz: 0, jE: 0.04, jD: 0.04,
};
const JUNTAS = Object.keys(POSE_PARADA);

function posar(k, alvo, dt, rapidez = 14) {
  const f = dt > 0 ? 1 - Math.exp(-dt * rapidez) : 1;
  const p = k.pose;
  for (const j of JUNTAS) p[j] += ((alvo[j] ?? POSE_PARADA[j]) - p[j]) * f;
  k.tronco.rotation.x = p.tronco;
  k.cabeca.rotation.set(p.cabeca, p.giroCabeca, 0);
  k.bracoE.rotation.set(p.bE, 0, p.bEz);
  k.bracoD.rotation.set(p.bD, 0, p.bDz);
  k.cotoveloE.rotation.x = p.cE;
  k.cotoveloD.rotation.x = p.cD;
  k.pernaE.rotation.set(p.pE, 0, p.pEz);
  k.pernaD.rotation.set(p.pD, 0, p.pDz);
  k.joelhoE.rotation.x = p.jE;
  k.joelhoD.rotation.x = p.jD;
}

/** Quanto o quadril desce com as pernas dobradas (pisa a perna mais esticada). */
function descida(p) {
  const perna = (a, j, z) => (0.26 * Math.cos(a) + 0.24 * Math.cos(a + j)) * Math.cos(z);
  return 0.5 - Math.max(perna(p.pE, p.jE, p.pEz), perna(p.pD, p.jD, p.pDz));
}

/** O meio das duas mãos, no corpo da criança: [altura, para a frente] (para a bola ir nas mãos). */
function maos(p) {
  const t = p.tronco;
  const y = 0.66 + 0.31 * Math.cos(t) - descida(p);
  const z = 0.31 * Math.sin(t);
  const meio = (b, c) => {
    const a = t + b;
    return [-0.2 * Math.cos(a) - 0.2 * Math.cos(a + c), -0.2 * Math.sin(a) - 0.2 * Math.sin(a + c)];
  };
  const [ey, ez] = meio(p.bE, p.cE);
  const [dy, dz] = meio(p.bD, p.cD);
  return [y + (ey + dy) / 2, z + (ez + dz) / 2];
}

/** Um ponto do corpo da criança (lado, altura, frente) no espaço do objeto. */
function noCorpo(k, x, y, z, saida) {
  const g = k.grupo;
  const s = Math.sin(g.rotation.y);
  const c = Math.cos(g.rotation.y);
  return saida.set(g.position.x + x * c + z * s, g.position.y + y, g.position.z - x * s + z * c);
}

/** Corrida (ou caminhada, mais lenta): pernas e braços alternados, `f` é a fase do passo. */
function passada(f, forca = 1, ré = false) {
  const s = Math.sin(f) * (ré ? -1 : 1);
  return {
    pE: 0.62 * s * forca, pD: -0.62 * s * forca,
    jE: 0.25 + 1.0 * Math.max(0, s) * forca, jD: 0.25 + 1.0 * Math.max(0, -s) * forca,
    bE: -0.55 * s * forca, bD: 0.55 * s * forca, cE: -1.25, cD: -1.25,
    tronco: ré ? -0.05 : 0.18 * forca,
  };
}

const suave = (x) => {
  const t = limitar(x, 0, 1);
  return t * t * (3 - 2 * t);
};

/* ======================================================================
   O MOVIMENTO NOS OBJETOS DA FÁBRICA -- o que o espaço tem de jogo mexe,
   com crianças jogando:
   - SWISH: a tabela de cada uma das cinco cestas das enterradas é uma
     tela com o Swish Arena DE VERDADE rodando (o jogo do simulador). Em
     quatro, uma criança arremessa -- e o arremesso vale no jogo da tabela:
     a bola sobe em arco, entra (a redinha balança) ou bate no aro, cai na
     cama inclinada e rola de volta para ela. A do meio fica livre: é a da
     enterrada do passeio.
   - GOL FLASH redondo, como a máquina de verdade: 7 LEDs na parede de
     dentro de cada círculo, de 1 a 3 acesos por vez (amarelo, vermelho,
     verde, azul), cada um apaga sozinho se ninguém acerta. A criança vira
     para um aceso e chuta: no aceso é GOOOL (o LED brilha e outro acende);
     no apagado, o LED pisca vermelho. Uma tela atrás de cada círculo, com
     os 7 anéis do jogo, os gols e o tempo.
   - CRIANÇAS BRINCANDO, com o corpo inteiro (joelho, cotovelo, pulo de
     verdade, com subida e descida): o arremesso agacha, estica e salta; o
     chute tem corrida, a perna vai para trás e vem com tudo, e o gol é
     comemorado (o erro, mão na cabeça); nas camas elásticas, pulos com
     truque (estrela, grupado, carpado, giro, tesoura), a lona afundando a
     cada volta; uma criança escala a parede e se joga na espuma; outra
     dribla na quadra de basquete e arremessa.
   Coordenadas no objeto (metros, frente em +z). Só anda com o espaço
   perto da câmera: de longe não se vê, e o celular agradece. Com "menos
   movimento" no aparelho, as crianças ficam paradas na vista da arena --
   mas no passeio, que a pessoa pediu, elas brincam.
   ====================================================================== */
const ANIMACOES = {
  "espaco-esportivo-modelo-1": (arena, maquina) => {
    const T = arena.T;
    const g = new T.Group();
    maquina.corpo.add(g);
    const V = (x, y, z) => new T.Vector3(x, y, z);
    const textura = (w, h, pintar) => {
      const c = document.createElement("canvas");
      c.width = w;
      c.height = h;
      pintar(c.getContext("2d"));
      const t = new T.CanvasTexture(c);
      t.colorSpace = T.SRGBColorSpace;
      return t;
    };
    const pele = new T.MeshStandardMaterial({ vertexColors: true, roughness: 0.65 });
    let nCrianca = 0;
    const crianca = () => montarCrianca(T, pele, nCrianca++);
    const texBola = (fundo, linhas) => textura(64, 32, (c) => {
      c.fillStyle = fundo; c.fillRect(0, 0, 64, 32);
      c.strokeStyle = linhas; c.lineWidth = 2;
      c.beginPath(); c.moveTo(0, 16); c.lineTo(64, 16); c.moveTo(16, 0); c.lineTo(16, 32); c.moveTo(48, 0); c.lineTo(48, 32); c.stroke();
    });
    const geoBola = new T.SphereGeometry(0.12, 16, 12);
    const matBasquete = new T.MeshStandardMaterial({ map: texBola("#ff7a1a", "#3a1600"), roughness: 0.6 });
    const matFutebol = new T.MeshStandardMaterial({ map: texBola("#f4f6fa", "#1b1d22"), roughness: 0.45 });

    /* --- as telas: o pôster do jogo de fundo e o placar por cima --- */
    const posters = {};
    const telas = [];
    const fonte = (peso, px) => `${peso} ${px}px Poppins, Manrope, system-ui, sans-serif`;
    const relogio = (s) => `0:${String(Math.max(0, Math.ceil(s))).padStart(2, "0")}`;
    const LW = 320;
    const LH = 180;
    const fundo = (ctx, img, escurecer = 0.35) => {
      ctx.fillStyle = "#070b1c";
      ctx.fillRect(0, 0, LW, LH);
      if (img && img.complete && img.naturalWidth) {
        const k = Math.max(LW / img.naturalWidth, LH / img.naturalHeight);
        ctx.drawImage(img, (LW - img.naturalWidth * k) / 2, (LH - img.naturalHeight * k) / 2 - 10, img.naturalWidth * k, img.naturalHeight * k);
      }
      ctx.fillStyle = `rgba(3, 6, 18, ${escurecer})`;
      ctx.fillRect(0, 0, LW, LH);
    };
    const barra = (ctx, corDoJogo, itens) => {
      ctx.fillStyle = "rgba(3, 6, 18, .9)";
      ctx.fillRect(0, 136, LW, 44);
      ctx.fillStyle = corDoJogo;
      ctx.fillRect(0, 134, LW, 3);
      const passo = LW / itens.length;
      ctx.textAlign = "center";
      ctx.textBaseline = "alphabetic";
      itens.forEach(([rotulo, valor], i) => {
        const x = passo * i + passo / 2;
        ctx.fillStyle = "rgba(255, 255, 255, .7)";
        ctx.font = fonte(800, 10);
        ctx.fillText(rotulo, x, 150);
        ctx.fillStyle = "#ffffff";
        ctx.font = fonte(900, 21);
        ctx.fillText(valor, x, 174);
      });
    };
    const grito = (ctx, texto, sub, cor, vida) => {
      if (vida <= 0) return;
      ctx.save();
      ctx.globalAlpha = Math.min(1, vida * 2.5);
      ctx.fillStyle = "rgba(3, 6, 18, .5)";
      ctx.fillRect(0, 0, LW, 134);
      ctx.translate(LW / 2, 62);
      const s = 0.8 + 0.2 * Math.min(1, (1.4 - vida) * 6);
      ctx.scale(s, s);
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.lineJoin = "round";
      ctx.font = fonte("italic 900", 52);
      ctx.lineWidth = 9;
      ctx.strokeStyle = "#120600";
      ctx.strokeText(texto, 0, 0);
      ctx.fillStyle = cor;
      ctx.fillText(texto, 0, 0);
      if (sub) {
        ctx.font = fonte(900, 20);
        ctx.lineWidth = 5;
        ctx.strokeText(sub, 0, 42);
        ctx.fillStyle = "#ffffff";
        ctx.fillText(sub, 0, 42);
      }
      ctx.restore();
    };
    const final = (ctx, titulo, linha) => {
      ctx.fillStyle = "rgba(3, 6, 18, .78)";
      ctx.fillRect(0, 0, LW, 134);
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillStyle = "#ffd84a";
      ctx.font = fonte(900, 24);
      ctx.fillText(titulo, LW / 2, 52);
      ctx.fillStyle = "#ffffff";
      ctx.font = fonte(800, 16);
      ctx.fillText(linha, LW / 2, 88);
    };
    /** Uma tela de 16:9 virada para +z, com a moldura; `pes`: até o chão ou um suporte curto. */
    const tela = (x, y, z, largura, pes, pintar) => {
      const c = document.createElement("canvas");
      c.width = LW;
      c.height = LH;
      const tex = new T.CanvasTexture(c);
      tex.colorSpace = T.SRGBColorSpace;
      tex.anisotropy = arena.anisotropia;
      const altura = (largura * LH) / LW;
      const suporte = new T.Group();
      suporte.position.set(x, y, z);
      arena.caixa(suporte, largura + 0.12, altura + 0.12, 0.08, arena.escuro(), 0, 0, -0.05);
      const baixo = y - altura / 2;
      if (pes === "chao") [-1, 1].forEach((s) => arena.caixa(suporte, 0.07, baixo, 0.07, arena.escuro(), s * largura * 0.33, -altura / 2 - baixo / 2, -0.05));
      else arena.caixa(suporte, largura * 0.5, pes, 0.1, arena.escuro(), 0, -altura / 2 - pes / 2, -0.06);
      const painel = new T.Mesh(new T.PlaneGeometry(largura, altura), new T.MeshBasicMaterial({ map: tex, toneMapped: false }));
      painel.position.z = 0.01;
      suporte.add(painel);
      g.add(suporte);
      const item = { ctx: c.getContext("2d"), tex, suporte, pintar, ultimo: -1 };
      telas.push(item);
      return item;
    };

    /* --- SWISH: as cinco cestas das enterradas --- */
    const LIVRE = 2; // a cesta do meio é a da enterrada do passeio
    const camaY = (z) => 0.982 + limitar((-9.0 - z) / 2.2, 0, 1) * 1.6; // a cama inclinada até a parede
    const texRede = textura(64, 64, (c) => {
      c.strokeStyle = "rgba(255,255,255,.95)"; c.lineWidth = 3;
      for (let i = -64; i < 128; i += 12) { c.beginPath(); c.moveTo(i, 0); c.lineTo(i + 40, 64); c.moveTo(i + 40, 0); c.lineTo(i, 64); c.stroke(); }
    });
    texRede.wrapS = T.RepeatWrapping;
    texRede.repeat.set(3, 1);
    const matRede = new T.MeshBasicMaterial({ map: texRede, transparent: true, alphaTest: 0.3, side: T.DoubleSide, toneMapped: false });
    const geoRede = new T.CylinderGeometry(0.2, 0.12, 0.34, 18, 1, true);
    const geoTabela = new T.PlaneGeometry(1.2, 0.675);
    const matTabelaEspera = new T.MeshBasicMaterial({ color: "#0b1030", toneMapped: false });
    const cestas = [15.6, 13.6, 11.6, 9.6, 7.6].map((x, i) => {
      const cesta = {
        i, x,
        aro: V(x, 2.8, -10.88),
        fase: "segura", tempo: -i * 0.7, balanco: 0, erra: false, de: V(), fora: V(),
        salto: 9, saltou: false, reacao: 0, acertou: false,
      };
      // a tabela da cesta é uma tela: o Swish Arena de verdade (o mesmo
      // jogo do simulador) roda nela -- até ele chegar, o pôster
      cesta.tabela = new T.Mesh(geoTabela, matTabelaEspera);
      cesta.tabela.position.set(x, 3.05, -11.09);
      g.add(cesta.tabela);
      cesta.rede = new T.Mesh(geoRede, matRede);
      cesta.rede.position.set(x, 2.62, -10.88);
      g.add(cesta.rede);
      if (i !== LIVRE) {
        cesta.crianca = crianca();
        cesta.crianca.grupo.position.set(x, 0.97, -8.75);
        cesta.crianca.grupo.rotation.y = PI; // de frente para a cesta
        g.add(cesta.crianca.grupo);
        cesta.bola = new T.Mesh(geoBola, matBasquete);
        g.add(cesta.bola);
      }
      return cesta;
    });
    const swish = new T.Sprite(new T.SpriteMaterial({
      map: textura(512, 160, (c) => {
        c.font = "italic 900 112px Poppins, Manrope, sans-serif";
        c.textAlign = "center"; c.textBaseline = "middle";
        c.lineWidth = 16; c.strokeStyle = "#7a1d00"; c.strokeText("SWISH!", 256, 84);
        c.fillStyle = "#ffd84a"; c.fillText("SWISH!", 256, 84);
      }),
      transparent: true, depthWrite: false, toneMapped: false,
    }));
    swish.visible = false;
    g.add(swish);
    let swishDe = null;
    let swishVida = 0;

    /* O SWISH ARENA DE VERDADE nas tabelas: o mesmo jogo do simulador
       (basquete.js, variante swish), dois rodando -- um nas cestas 1, 3 e
       5, outro nas 2 e 4 --, e as crianças arremessando nele: cada
       arremesso no 3D é um arremesso no jogo da tabela. Carrega só quando
       o espaço chega perto da câmera; de longe, o jogo fica parado. */
    const infoSwish = (maquina.dados.jogos_no_espaco || []).find((j) => j.slug === "swish-arena" && j.script);
    const jogosSwish = [];
    let pediuSwish = false;
    const textoDoJogo = (ctx, texto, x, y, opcoes = {}) => {
      const {
        tamanho = 32, cor = "#fff", alinhar = "center", peso = 800,
        contorno = null, sombra = null, base = "middle", fonte: familia = "Poppins, Manrope, system-ui, sans-serif",
      } = opcoes;
      ctx.save();
      ctx.font = `${peso} ${Math.round(tamanho)}px ${familia}`;
      ctx.textAlign = alinhar;
      ctx.textBaseline = base;
      ctx.lineJoin = "round";
      if (sombra) {
        const alfa = ctx.globalAlpha;
        ctx.strokeStyle = sombra;
        for (const [largura, forca] of [[0.62, 0.1], [0.4, 0.18], [0.22, 0.3]]) {
          ctx.globalAlpha = alfa * forca;
          ctx.lineWidth = tamanho * largura;
          ctx.strokeText(texto, x, y);
        }
        ctx.globalAlpha = alfa;
      }
      if (contorno) {
        ctx.lineWidth = Math.max(2, tamanho * 0.14);
        ctx.strokeStyle = contorno;
        ctx.strokeText(texto, x, y);
      }
      ctx.fillStyle = cor;
      ctx.fillText(texto, x, y);
      ctx.restore();
    };
    const carregarSwish = async () => {
      pediuSwish = true;
      try {
        const jogo = (await import(infoSwish.script)).default;
        const base = new URL(infoSwish.script, window.location.href);
        const imagens = {};
        await Promise.all(Object.entries(jogo.artes || {}).map(([nome, caminho]) => new Promise((pronto) => {
          const img = new Image();
          img.decoding = "async";
          img.onload = () => { imagens[nome] = img; pronto(); };
          img.onerror = () => pronto();
          img.src = new URL(caminho, base).href;
        })));
        for (let n = 0; n < 2; n++) {
          const c = document.createElement("canvas");
          c.width = 480;
          c.height = 270;
          const item = { ctx: c.getContext("2d"), ultimo: -1, parado: 1 + n, fim: 0 };
          item.partida = jogo.criar({
            W: c.width, H: c.height, variante: infoSwish.variante || "swish", img: imagens, reduzido: arena.reduzido,
            som() {}, placar() {}, vibrar() {},
            terminar: () => { item.fim = 4; }, // o fim da partida fica na tela e outra começa
            texto: textoDoJogo,
          });
          item.partida.iniciar();
          item.tex = new T.CanvasTexture(c);
          item.tex.colorSpace = T.SRGBColorSpace;
          item.tex.anisotropy = arena.anisotropia;
          item.mat = new T.MeshBasicMaterial({ map: item.tex, toneMapped: false });
          jogosSwish.push(item);
        }
        cestas.forEach((c, i) => {
          c.jogo = jogosSwish[i % 2];
          c.tabela.material = c.jogo.mat;
          if (i === 1 || i === 2) c.jogo.tabela = c.tabela; // a cesta do meio de cada jogo diz se ele está à vista
        });
      } catch (erro) {
        console.error("Arena 3D: o Swish das tabelas não carregou", erro);
      }
    };
    /** Um arremesso no jogo da tabela (certeiro, ou torto quando a criança erra). */
    const arremessarNoJogo = (item, erra) => {
      const p = item && item.partida;
      if (!p || item.fim > 0 || !p.mao || !p.podeArremessar() || p.mao.chega < 0.6) return;
      const potencia = erra ? 1 + (Math.random() < 0.5 ? -0.38 : 0.42) : 1 + (Math.random() - 0.5) * 0.1;
      const angulo = erra ? (Math.random() - 0.5) * 0.6 : (Math.random() - 0.5) * 0.05;
      p.arremessar(p.mao, potencia, angulo);
      item.parado = 0;
    };
    /** A tela está na frente da câmera (e perto)? Senão, pintar é à toa. */
    const praTela = new T.Vector3();
    const aVista = (malha) => {
      malha.getWorldPosition(praTela);
      const camera = arena.camera;
      if (camera.position.distanceTo(praTela) > 45) return false;
      camera.getWorldDirection(olharAux);
      return praTela.sub(camera.position).dot(olharAux) > 0;
    };
    const olharAux = new T.Vector3();
    const andarSwish = (dt, t, camera, perto) => {
      jogosSwish.forEach((item) => {
        if (!perto) return; // de longe, o jogo espera
        const p = item.partida;
        if (item.fim > 0) {
          item.fim -= dt;
          if (item.fim <= 0) p.iniciar();
        } else {
          p.atualizar(Math.min(dt, 0.05));
          // sem arremesso por um tempo (a cesta livre), a tabela joga sozinha
          item.parado += dt;
          if (item.parado > 2.4) arremessarNoJogo(item, Math.random() < 0.25);
        }
        if (t - item.ultimo < 1 / 10 || !aVista(item.tabela) || !arena.podePintar()) return;
        item.ultimo = t;
        item.ctx.setTransform(1, 0, 0, 1, 0, 0);
        item.ctx.clearRect(0, 0, 480, 270);
        p.desenhar(item.ctx);
        item.tex.needsUpdate = true;
      });
    };

    /** A bola nas mãos da criança (segurando, mirando, pegando de volta). */
    const bolaNasMaos = (k, saida) => {
      const [y, z] = maos(k.pose);
      return noCorpo(k, 0, y + 0.03, z + 0.13, saida);
    };
    /** A altura do salto (subida e descida), `s` segundos depois de sair do chão. */
    const alturaDoSalto = (s, duracao, altura) => (s >= 0 && s < duracao ? altura * 4 * (s / duracao) * (1 - s / duracao) : 0);
    /** O arremesso, `f` segundos depois de começar: agacha, estica e salta (a bola sai no alto). */
    const poseDoArremesso = (f) => (f < 0.35
      ? { bE: -0.7, bD: -0.7, bEz: 0.3, bDz: -0.3, cE: -1.7, cD: -1.7, tronco: 0.3, cabeca: -0.35, pE: -0.75, pD: -0.75, jE: 1.35, jD: 1.35 }
      : { bE: -2.75, bD: -2.75, bEz: 0.2, bDz: -0.2, cE: -0.65, cD: -0.65, cabeca: -0.45, tronco: -0.05 });
    /** Depois de arremessar: o braço acompanha a bola e desce; acertou, comemora; errou, mão na cabeça. */
    const poseDepois = (tempo, reacao, acertou) => {
      if (reacao > 0) {
        return acertou
          ? { bD: -2.95, cD: -1.3, bDz: 0.05, bE: -0.35, cE: -0.9, cabeca: -0.2 }
          : { bE: -2.45, bD: -2.45, bEz: -0.5, bDz: 0.5, cE: -2.35, cD: -2.35, cabeca: 0.25 };
      }
      return tempo < 0.5 ? { bE: -2.6, bD: -2.6, cE: -0.15, cD: -0.15, cabeca: -0.45 } : { bE: -0.35, bD: -0.35, cE: -0.5, cD: -0.5, cabeca: -0.3 };
    };
    /** O pouso: os joelhos amortecem logo que o pé volta à cama. */
    const amortecer = (alvo, s, duracao) => {
      const f = (s - duracao) / 0.22;
      if (f < 0 || f > 1) return alvo;
      const peso = Math.sin(f * PI);
      return { ...alvo, pE: -0.45 * peso, pD: -0.45 * peso, jE: 0.85 * peso, jD: 0.85 * peso, tronco: (alvo.tronco || 0) + 0.15 * peso };
    };

    const andarCesta = (c, dt, t) => {
      c.balanco = Math.max(0, c.balanco - dt * 1.6);
      c.rede.scale.y = 1 + Math.sin(t * 24) * 0.18 * c.balanco;
      if (!c.crianca) return;
      const k = c.crianca;
      const b = c.bola.position;
      c.tempo += dt;
      c.salto += dt;
      c.reacao = Math.max(0, c.reacao - dt);
      let alvo;
      let quique = 0; // parada na cama, a criança quica de leve
      if (c.fase === "segura") {
        if (c.tempo < 0.6) {
          // mira, com a bola no peito
          alvo = { bE: -0.9, bD: -0.9, bEz: 0.3, bDz: -0.3, cE: -1.5, cD: -1.5, cabeca: -0.2, pE: -0.15, pD: -0.15, jE: 0.3, jD: 0.3 };
          quique = Math.abs(Math.sin(Math.max(0, c.tempo) * 8)) * 0.035;
        } else {
          const f = c.tempo - 0.6;
          alvo = poseDoArremesso(f);
          if (f >= 0.35 && !c.saltou) { c.saltou = true; c.salto = 0; }
          if (f >= 0.62) {
            // solta no alto do salto: o mesmo arremesso no jogo da tabela
            c.fase = "voo";
            c.tempo = 0;
            c.de.copy(b);
            c.erra = Math.random() < 0.22;
            arremessarNoJogo(c.jogo, c.erra);
          }
        }
      } else if (c.fase === "voo") {
        const f = Math.min(1, c.tempo / 0.9);
        b.lerpVectors(c.de, c.aro, f);
        b.y += Math.sin(f * PI) * 0.75 + 0.06;
        c.bola.rotation.x -= dt * 9;
        alvo = poseDepois(c.tempo, 0, false);
        if (f >= 1) {
          c.tempo = 0;
          c.reacao = 0.95;
          c.acertou = !c.erra;
          if (c.erra) {
            c.fase = "fora";
            c.balanco = 0.3;
            c.fora.set((Math.random() - 0.5) * 0.6, 0, 0.35);
          } else {
            c.fase = "queda";
            c.balanco = 1;
            swishDe = c;
            swishVida = 1;
            swish.visible = true;
          }
        }
      } else if (c.fase === "queda" || c.fase === "fora") {
        // pela redinha, ou espirrando do aro, até a cama inclinada
        const dur = c.fase === "queda" ? 0.3 : 0.55;
        const f = Math.min(1, c.tempo / dur);
        const zFim = c.fase === "queda" ? -10.88 : -10.88 + c.fora.z;
        b.set(c.x + c.fora.x * f * (c.fase === "fora" ? 1 : 0), 0, c.aro.z + (zFim - c.aro.z) * f);
        b.y = c.aro.y + (c.fase === "fora" ? Math.sin(f * PI) * 0.35 : 0) - (c.aro.y - camaY(b.z) - 0.12) * f * f;
        alvo = poseDepois(1, c.reacao, c.acertou);
        if (f >= 1) { c.fase = "rola"; c.tempo = 0; c.de.copy(b); }
      } else if (c.fase === "rola") {
        // a bola desce rolando a cama até a criança, que comemora (ou lamenta) e espera
        const f = Math.min(1, c.tempo / 1.0);
        const z = c.de.z + (-9.1 - c.de.z) * (1 - (1 - f) * (1 - f));
        b.set(c.de.x + (c.x - c.de.x) * f, camaY(z) + 0.12, z);
        c.bola.rotation.x += dt * 10;
        alvo = c.reacao > 0 ? poseDepois(1, c.reacao, c.acertou) : { pE: -0.1, pD: -0.1, jE: 0.22, jD: 0.22, bE: 0.1, bD: 0.1, cabeca: -0.1 };
        if (c.reacao > 0 && c.acertou) quique = Math.abs(Math.sin(c.reacao * 10)) * 0.12; // pulinho de alegria
        else if (c.reacao <= 0) quique = Math.abs(Math.sin(t * 7 + c.i)) * 0.05;
        if (f >= 1) { c.fase = "pega"; c.tempo = 0; c.de.copy(b); }
      } else {
        // pega: abaixa e estica os braços até a bola
        alvo = { bE: -1.1, bD: -1.1, bEz: 0.25, bDz: -0.25, cE: -0.45, cD: -0.45, tronco: 0.4, cabeca: -0.1, pE: -0.55, pD: -0.55, jE: 1.0, jD: 1.0 };
        if (c.tempo >= 0.45) { c.fase = "segura"; c.tempo = 0; c.saltou = false; }
      }
      posar(k, amortecer(alvo, c.salto, 0.55), dt);
      k.grupo.position.y = 0.97 + alturaDoSalto(c.salto, 0.55, 0.3) + quique - descida(k.pose);
      if (c.fase === "segura") bolaNasMaos(k, b);
      else if (c.fase === "pega") b.lerp(bolaNasMaos(k, naMao), Math.min(1, c.tempo / 0.45));
    };
    const naMao = new T.Vector3();

    /* --- GOL FLASH: os dois círculos, 7 LEDs cada --- */
    const CORES_LED = ["#ffe600", "#ff2626", "#22ff4a", "#3d8bff"].map((c) => new T.Color(c));
    const LEDS = 7;
    const apagado = new T.Color("#262a33");
    const lenteApagada = new T.Color("#171a21");
    const branco = new T.Color("#ffffff");
    const vermelho = new T.Color("#ff2626");
    const aros = new T.InstancedMesh(new T.TorusGeometry(0.12, 0.03, 8, 28), new T.MeshBasicMaterial({ toneMapped: false }), LEDS * 2);
    const lentes = new T.InstancedMesh(new T.CircleGeometry(0.095, 24), new T.MeshBasicMaterial({ toneMapped: false }), LEDS * 2);
    const ajuda = new T.Object3D();
    const circulos = [-12.5, -6.5].map((x, k) => {
      const centro = V(x, 0, 2.4);
      const leds = [];
      for (let i = 0; i < LEDS; i++) {
        const a = ((i + 0.5) / LEDS) * PI * 2;
        const p = V(x + Math.sin(a) * 2.47, 0.42, 2.4 + Math.cos(a) * 2.47);
        ajuda.position.copy(p);
        ajuda.lookAt(centro.x, 0.42, centro.z); // de frente para o meio
        ajuda.updateMatrix();
        aros.setMatrixAt(k * LEDS + i, ajuda.matrix);
        lentes.setMatrixAt(k * LEDS + i, ajuda.matrix);
        leds.push({ p, dir: V(Math.sin(a), 0, Math.cos(a)), aceso: null, vida: 0, gol: 0, erro: 0 });
      }
      const jogo = {
        k, centro, leds,
        crianca: crianca(),
        bola: new T.Mesh(geoBola, matFutebol),
        fase: "mira", tempo: -k * 0.8, alvo: k * 3, escolheu: false, de: V(), ate: V(), inicio: V(),
        voo: -1, volta: -1, chutou: false, reacao: 0, acertou: false,
        gols: 0, pontos: 0, ganho: 0, grito: 0, acender: 0.3,
      };
      jogo.crianca.grupo.position.set(x, 0.07, 2.4 - 1.05);
      g.add(jogo.crianca.grupo, jogo.bola);
      jogo.tela = tela(x, 1.62, -0.78, 1.7, "chao", (ctx) => {
        fundo(ctx, posters["gol-flash-arena"], 0.55);
        // os 7 anéis do jogo, como a parede do círculo agora
        for (let i = 0; i < LEDS; i++) {
          const led = leds[i];
          const cx = 34 + i * 42;
          const cy = 62;
          let cor = led.aceso ? `#${led.aceso.getHexString()}` : "#2b303b";
          if (led.gol > 0) cor = "#ffffff";
          if (led.erro > 0 && Math.sin(led.erro * 25) > 0) cor = "#ff2626";
          ctx.lineWidth = 6;
          ctx.strokeStyle = cor;
          ctx.beginPath();
          ctx.arc(cx, cy, 15, 0, PI * 2);
          ctx.stroke();
          ctx.fillStyle = "rgba(255, 255, 255, .8)";
          ctx.font = fonte(900, 11);
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText("ABCDEFG"[i], cx, cy + 28);
        }
        if (fimGol > 0) final(ctx, "TEMPO ESGOTADO", `PLAYER ${k + 1} FINALIZOU COM ${jogo.gols} GOLS`);
        grito(ctx, "GOOOL!", `+${jogo.ganho}`, "#a6e22e", jogo.grito);
        barra(ctx, "#a6e22e", [["GOL", String(jogo.gols)], ["TEMPO", relogio(tempoGol)], ["PONTOS", String(jogo.pontos)]]);
      });
      return jogo;
    });
    g.add(aros, lentes);
    let tempoGol = 45;
    let fimGol = 0;
    const cor = new T.Color();
    const acesos = (j) => j.leds.filter((l) => l.aceso);
    const quantosAcesos = (j) => { let n = 0; for (const l of j.leds) if (l.aceso) n++; return n; };

    const bolaParada = new T.Vector3();
    const ondeIr = new T.Vector3();
    /** Escolhe o próximo alvo: um aceso (às vezes erra o tempo e chuta num apagado). */
    const escolherAlvo = (j) => {
      const ok = acesos(j);
      j.alvo = ok.length && Math.random() < 0.78 ? j.leds.indexOf(ok[Math.floor(Math.random() * ok.length)]) : Math.floor(Math.random() * LEDS);
    };
    /* O CHUTE: a criança espera atrás da bola (no meio do círculo), de
       frente para o LED escolhido; corre, a perna vai para trás e vem com
       tudo; a bola voa até a parede. GOOOL: braços para cima e pulos; no
       apagado, mão na cabeça. E volta de costas para a marca do próximo. */
    const andarCirculo = (j, dt, t) => {
      const kid = j.crianca;
      const b = j.bola.position;
      // os alvos: de 1 a 3 acesos, cada um com vida curta (como no jogo)
      j.leds.forEach((l) => {
        l.gol = Math.max(0, l.gol - dt);
        l.erro = Math.max(0, l.erro - dt);
        if (l.aceso) {
          l.vida -= dt;
          if (l.vida <= 0) l.aceso = null;
        }
      });
      j.acender -= dt;
      if (j.acender <= 0 && quantosAcesos(j) < 1 + (Math.floor(t / 7 + j.k) % 3)) {
        const livres = j.leds.filter((l) => !l.aceso && l.gol <= 0);
        const l = livres[Math.floor(Math.random() * livres.length)];
        if (l) { l.aceso = CORES_LED[Math.floor(Math.random() * CORES_LED.length)]; l.vida = 3.6 - (1 - tempoGol / 45) * 1.3; }
        j.acender = 0.5;
      }
      j.grito = Math.max(0, j.grito - dt);
      j.reacao = Math.max(0, j.reacao - dt);
      j.tempo += dt;
      bolaParada.set(j.centro.x, 0.19, j.centro.z);

      // a bola: voando até a parede, e depois voltando para o meio
      if (j.voo >= 0) {
        j.voo += dt;
        const f = Math.min(1, j.voo / 0.32);
        b.lerpVectors(j.de, j.ate, f);
        j.bola.rotation.x += dt * 20;
        if (f >= 1) {
          // bateu na parede: no LED aceso é gol
          const alvo = j.leds[j.alvo];
          j.acertou = Boolean(alvo.aceso) && fimGol <= 0;
          if (j.acertou) {
            j.ganho = 100 + Math.round(Math.max(0, alvo.vida / 3.6) * 100);
            j.pontos += j.ganho;
            j.gols++;
            j.grito = 1.4;
            alvo.gol = 0.9;
            alvo.aceso = null;
            j.acender = 0.08; // o grupo se completa logo depois
          } else if (!alvo.aceso) {
            alvo.erro = 0.5;
          }
          j.reacao = 1.1;
          j.voo = -1;
          j.volta = 0;
          j.de.copy(b);
        }
      } else if (j.volta >= 0) {
        j.volta += dt;
        const f = Math.min(1, j.volta / 1.1);
        b.lerpVectors(j.de, bolaParada, 1 - (1 - f) * (1 - f));
        j.bola.rotation.x -= dt * 8 * (1 - f);
        if (f >= 1) j.volta = -1;
      } else if (!j.chutou) {
        b.copy(bolaParada);
      }

      // a criança
      const d = j.leds[j.alvo].dir;
      let delta = Math.atan2(d.x, d.z) - kid.grupo.rotation.y;
      delta = Math.atan2(Math.sin(delta), Math.cos(delta));
      kid.grupo.rotation.y += delta * (1 - Math.exp(-dt * 7));
      const marca = (distancia, saida) => saida.set(j.centro.x - d.x * distancia, 0.07, j.centro.z - d.z * distancia);
      let alvo;
      let quique = 0;
      let rapidez = 14;
      if (j.fase === "mira") {
        if (!j.escolheu && j.tempo >= 0) { escolherAlvo(j); j.escolheu = true; }
        // pronta, atrás da bola: joelhos dobrados, braços abertos, quicando
        alvo = { pE: -0.3, pD: -0.3, jE: 0.6, jD: 0.6, tronco: 0.3, bE: -0.3, bD: -0.3, bEz: -0.55, bDz: 0.55, cE: -0.9, cD: -0.9, cabeca: -0.25 };
        quique = Math.abs(Math.sin(j.tempo * 9)) * 0.03;
        kid.grupo.position.lerp(marca(1.05, ondeIr), 1 - Math.exp(-dt * 6));
        if (j.tempo > 0.55) { j.fase = "corre"; j.tempo = 0; j.inicio.copy(kid.grupo.position); }
      } else if (j.fase === "corre") {
        // três passos até a bola; no último, a perna do chute vai para trás
        const f = Math.min(1, j.tempo / 0.5);
        kid.grupo.position.lerpVectors(j.inicio, marca(0.34, ondeIr), f * (0.6 + 0.4 * f));
        const passo = j.tempo * PI * 2 * 3;
        alvo = passada(passo, 1);
        if (f > 0.68) Object.assign(alvo, { pD: 0.95, jD: 1.65, pE: -0.25, jE: 0.4, bEz: -0.7, bE: -0.5, bD: 0.5 });
        quique = Math.abs(Math.sin(passo)) * 0.06;
        if (f >= 1) { j.fase = "chuta"; j.tempo = 0; j.chutou = false; }
      } else if (j.fase === "chuta") {
        // a perna vem com tudo, bate na bola e segue alto; o braço de fora equilibra
        rapidez = 30;
        alvo = { pD: j.tempo < 0.07 ? -0.4 : -1.3, jD: j.tempo < 0.07 ? 0.7 : 0.05, pE: -0.1, jE: 0.35, tronco: -0.15, bE: -0.5, bEz: -1.05, cE: -0.3, bD: 0.6, bDz: 0.5, cabeca: -0.3 };
        if (j.tempo >= 0.07 && !j.chutou) {
          j.chutou = true;
          j.voo = 0;
          j.de.copy(b);
          j.ate.copy(j.leds[j.alvo].p).setY(0.19).addScaledVector(j.leds[j.alvo].dir, -0.14);
        }
        if (j.tempo > 0.5) { j.fase = "reage"; j.tempo = 0; }
      } else if (j.fase === "reage") {
        // GOOOL: braços para cima e pulos; no apagado, mão na cabeça
        if (j.acertou) {
          alvo = { bE: -2.9, bD: -2.9, bEz: -0.35, bDz: 0.35, cE: -0.25, cD: -0.25, cabeca: -0.3 };
          quique = Math.abs(Math.sin(j.tempo * 7.5)) * 0.24;
        } else {
          alvo = { bE: -2.45, bD: -2.45, bEz: -0.5, bDz: 0.5, cE: -2.35, cD: -2.35, cabeca: 0.3, tronco: 0.1 };
        }
        if (j.reacao <= 0 && j.voo < 0) { j.fase = "volta"; j.tempo = 0; escolherAlvo(j); j.inicio.copy(kid.grupo.position); }
      } else {
        // de costas, trotando até a marca do próximo chute
        const f = Math.min(1, j.tempo / 0.9);
        kid.grupo.position.lerpVectors(j.inicio, marca(1.05, ondeIr), suave(f));
        alvo = passada(j.tempo * PI * 2 * 2.2, 0.7, true);
        quique = Math.abs(Math.sin(j.tempo * PI * 2 * 2.2)) * 0.035;
        if (f >= 1) { j.fase = "mira"; j.tempo = 0; j.chutou = false; }
      }
      posar(kid, alvo, dt, rapidez);
      kid.grupo.position.y = 0.07 + quique - descida(kid.pose);
      // a cor de cada LED
      j.leds.forEach((l, i) => {
        if (l.gol > 0) cor.copy(l.aceso || branco).lerp(branco, 0.5 + 0.5 * Math.sin(t * 12));
        else if (l.erro > 0) cor.copy(Math.sin(l.erro * 25) > 0 ? vermelho : apagado);
        else if (l.aceso) cor.copy(l.aceso);
        else cor.copy(apagado);
        aros.setColorAt(j.k * LEDS + i, cor);
        if (!l.aceso && l.gol <= 0 && l.erro <= 0) cor.copy(lenteApagada);
        else cor.lerp(branco, 0.35);
        lentes.setColorAt(j.k * LEDS + i, cor);
      });
    };

    /* --- crianças pulando nas camas elásticas: cada pulo com um truque --- */
    // o pulo no alto (os braços e as pernas de cada um, no meio do ar)
    const TRUQUES = {
      reto: { bE: -2.8, bD: -2.8, bEz: -0.15, bDz: 0.15, cE: -0.1, cD: -0.1, cabeca: -0.15 },
      estrela: { bE: -1.7, bD: -1.7, bEz: -1.25, bDz: 1.25, cE: -0.05, cD: -0.05, pEz: -0.5, pDz: 0.5 },
      grupado: { pE: -1.75, pD: -1.75, jE: 2.3, jD: 2.3, bE: -0.9, bD: -0.9, cE: -0.75, cD: -0.75, tronco: 0.45, cabeca: 0.2 },
      carpado: { pE: -1.45, pD: -1.45, jE: 0, jD: 0, bE: -1.45, bD: -1.45, cE: 0, cD: 0, tronco: 0.55 },
      giro: { bE: -0.55, bD: -0.55, bEz: 0.55, bDz: -0.55, cE: -2.2, cD: -2.2, cabeca: -0.1 },
      tesoura: { pE: -0.95, pD: 0.55, jE: 0.1, jD: 0.65, bE: 0.5, bD: -2.5, cE: -0.4, cD: -0.2 },
    };
    const NO_AR = { bE: -1.1, bD: -1.1, cE: -0.25, cD: -0.25, jE: 0.05, jD: 0.05 };
    const CONTATO = 0.24; // a lona afundando e devolvendo
    const NO_AR_DURA = 0.84;
    const misturar = (a, b, peso) => {
      const saida = {};
      for (const j of JUNTAS) saida[j] = (a[j] ?? POSE_PARADA[j]) * (1 - peso) + (b[j] ?? POSE_PARADA[j]) * peso;
      return saida;
    };
    // em cada cama, longe do caminho do passeio (que também pula por elas)
    const pulando = [
      [15.6, -5.7, ["reto", "estrela", "reto", "grupado"]],
      [13.6, -7.7, ["reto", "giro", "reto", "carpado"]],
      [5.6, -2.7, ["estrela", "reto", "tesoura", "reto"]],
      [5.65, 4.3, ["reto", "grupado", "estrela"]],
      [9.69, 4.3, ["reto", "reto", "giro"]],
      [17.6, -7.7, ["carpado", "reto", "estrela", "reto"]],
      [7.6, -5.7, ["tesoura", "reto", "grupado", "reto"]],
    ].map(([x, z, truques], i) => {
      const k = crianca();
      k.grupo.position.set(x, 0.982, z);
      k.grupo.rotation.y = i * 2.1;
      g.add(k.grupo);
      return { k, truques, t: i * 0.37, giro0: i * 2.1, altura: 0.62 + (i % 3) * 0.08 };
    });
    const andarPulando = (c, dt) => {
      const k = c.k;
      c.t += dt;
      const ciclo = CONTATO + NO_AR_DURA;
      const n = Math.floor(c.t / ciclo);
      const local = c.t - n * ciclo;
      const truque = c.truques[n % c.truques.length];
      if (local < CONTATO) {
        // na lona: ela afunda, os joelhos dobram e os braços vão para trás
        const s = Math.sin((local / CONTATO) * PI);
        posar(k, { pE: -0.45 * s, pD: -0.45 * s, jE: 0.9 * s, jD: 0.9 * s, bE: 0.55 * s, bD: 0.55 * s, cE: -0.3, cD: -0.3, tronco: 0.25 * s }, dt, 24);
        k.grupo.position.y = 0.982 - 0.12 * s - descida(k.pose);
        k.grupo.rotation.y = c.giro0;
      } else {
        // no ar: sobe, faz o truque no alto e volta esticado para a lona
        const s = (local - CONTATO) / NO_AR_DURA;
        posar(k, misturar(NO_AR, TRUQUES[truque], Math.pow(Math.sin(s * PI), 0.7)), dt, 22);
        k.grupo.position.y = 0.982 + c.altura * 4 * s * (1 - s);
        k.grupo.rotation.y = c.giro0 + (truque === "giro" ? PI * 2 * suave(s * 1.15) : 0);
      }
    };

    /* --- a parede de escalada: sobe agarra por agarra e se joga de costas na espuma --- */
    const PAREDE = -11.115;
    const escalando = { k: crianca(), t: 0 };
    escalando.k.grupo.position.set(5.1, 0.95, PAREDE + 0.24);
    escalando.k.grupo.rotation.y = PI; // de frente para a parede
    g.add(escalando.k.grupo);
    const LANCES = 7;
    const andarEscalada = (e, dt) => {
      const k = e.k;
      const grupo = k.grupo;
      e.t += dt;
      const local = e.t % 10.4;
      let alvo;
      let y = 0.95;
      let z = PAREDE + 0.24;
      let deitar = 0;
      const subida = LANCES * 0.62;
      if (local < subida) {
        // um braço sobe até a próxima agarra e a perna do outro lado pisa mais alto
        const n = Math.floor(local / 0.62);
        const f = (local - n * 0.62) / 0.62;
        const sobe = Math.sin(f * PI);
        y = 0.95 + 0.21 * (n + suave(f));
        const direita = n % 2 === 0;
        const alcanca = -2.35 - 0.6 * suave(f);
        const puxa = -2.95 + 0.6 * suave(f);
        alvo = {
          bE: direita ? puxa : alcanca, bD: direita ? alcanca : puxa, bEz: -0.35, bDz: 0.35, cE: -0.5, cD: -0.5,
          pE: direita ? -1.0 * sobe - 0.2 : -0.25, jE: direita ? 1.7 * sobe + 0.3 : 0.35,
          pD: direita ? -0.25 : -1.0 * sobe - 0.2, jD: direita ? 0.35 : 1.7 * sobe + 0.3,
          tronco: 0.12, cabeca: -0.45,
        };
      } else if (local < subida + 0.7) {
        // lá no alto: olha para trás e acena
        y = 0.95 + 0.21 * LANCES;
        alvo = { bE: -2.95, bEz: -0.3, cE: -0.5, bD: -2.1, bDz: 1.0, cD: -0.6 - 0.4 * Math.sin(local * 14), giroCabeca: 1.0, pE: -0.25, jE: 0.35, pD: -0.2, jD: 0.3 };
      } else if (local < subida + 1.6) {
        // se joga de costas, de braços abertos
        const s = (local - subida - 0.7) / 0.9;
        const alto = 0.95 + 0.21 * LANCES;
        y = alto + (0.62 - alto) * s * s + 0.3 * Math.sin(s * PI);
        z = PAREDE + 0.24 + 1.1 * s;
        deitar = 1.3 * suave(s * 1.3);
        alvo = { bE: -2.6, bD: -2.6, bEz: -0.6, bDz: 0.6, cE: -0.2, cD: -0.2, pE: -0.7, pD: -0.7, jE: 0.4, jD: 0.4, cabeca: 0.3 };
      } else if (local < subida + 3.0) {
        // afundada na espuma, nadando nos cubos
        const s = local - subida - 1.6;
        y = 0.62 - 0.04 * Math.sin(s * 5);
        z = PAREDE + 1.34;
        deitar = 1.3;
        alvo = { bE: -2.2 + 0.5 * Math.sin(s * 6), bD: -2.2 - 0.5 * Math.sin(s * 6), bEz: -0.8, bDz: 0.8, pE: -0.6, pD: -0.6, jE: 0.6, jD: 0.6 };
      } else if (local < subida + 3.8) {
        // levanta
        const s = (local - subida - 3.0) / 0.8;
        y = 0.62 + 0.1 * s;
        z = PAREDE + 1.34;
        deitar = 1.3 * (1 - suave(s));
        alvo = { pE: -0.9 * (1 - s), pD: -0.9 * (1 - s), jE: 1.4 * (1 - s), jD: 1.4 * (1 - s), bE: -0.8, bD: -0.8, tronco: 0.4 * (1 - s) };
      } else {
        // e volta para a parede pela espuma, com o joelho alto
        const s = Math.min(1, (local - subida - 3.8) / (10.4 - subida - 3.8));
        y = 0.72 + 0.23 * suave(s);
        z = PAREDE + 1.34 - 1.1 * suave(s);
        alvo = passada(local * 7, 0.8);
        alvo.jE += 0.4;
        alvo.jD += 0.4;
      }
      posar(k, alvo, dt, 12);
      grupo.position.set(5.1, y - (deitar ? 0 : descida(k.pose) * 0.5), z);
      grupo.rotation.set(deitar, PI, 0);
    };

    /* --- a quadra de basquete: dribla até a cesta, arremessa e volta driblando --- */
    const ARO_DA_QUADRA = V(-2.45, 2.4, -5);
    const QUADRA_LONGE = V(-6.3, 0.06, -4.55);
    const QUADRA_PERTO = V(-3.95, 0.06, -5.0);
    const quadra = {
      k: crianca(), bola: new T.Mesh(geoBola, matBasquete),
      fase: "vai", tempo: 0, de: V(), salto: 9, saltou: false, reacao: 0, acertou: false, erra: false,
    };
    quadra.k.grupo.position.copy(QUADRA_LONGE);
    g.add(quadra.k.grupo, quadra.bola);
    const ladoDaBola = new T.Vector3();
    /** O drible: a bola desce do lado da mão, bate no chão e volta para a mão. */
    const driblar = (q, tempo, alvo) => {
      const u = (tempo % 0.44) / 0.44;
      noCorpo(q.k, 0.23, 0, 0.3, ladoDaBola);
      q.bola.position.set(ladoDaBola.x, 0.06 + 0.12 + 0.6 * Math.abs(Math.cos(u * PI)), ladoDaBola.z);
      q.bola.rotation.x += 0.08;
      alvo.bD = -0.55 + 0.3 * Math.sin(u * PI * 2);
      alvo.bDz = 0.25;
      alvo.cD = -0.75;
      return alvo;
    };
    const andarQuadra = (q, dt) => {
      const k = q.k;
      const b = q.bola.position;
      q.tempo += dt;
      q.salto += dt;
      q.reacao = Math.max(0, q.reacao - dt);
      const olharPara = (destino) => {
        let delta = Math.atan2(destino.x - k.grupo.position.x, destino.z - k.grupo.position.z) - k.grupo.rotation.y;
        delta = Math.atan2(Math.sin(delta), Math.cos(delta));
        k.grupo.rotation.y += delta * (1 - Math.exp(-dt * 6));
      };
      let alvo;
      let quique = 0;
      if (q.fase === "vai" || q.fase === "sai") {
        // driblando: até perto da cesta, ou de volta para o meio da quadra
        const vai = q.fase === "vai";
        const f = Math.min(1, q.tempo / 1.8);
        k.grupo.position.lerpVectors(vai ? QUADRA_LONGE : QUADRA_PERTO, vai ? QUADRA_PERTO : QUADRA_LONGE, suave(f));
        if (vai || f < 0.85) olharPara(vai ? ARO_DA_QUADRA : QUADRA_LONGE);
        alvo = driblar(q, q.tempo, passada(q.tempo * PI * 2 * 1.9, 0.75));
        quique = Math.abs(Math.sin(q.tempo * PI * 2 * 1.9)) * 0.03;
        if (f >= 1) { q.fase = vai ? "arremessa" : "vira"; q.tempo = 0; q.saltou = false; }
      } else if (q.fase === "vira") {
        // no meio da quadra, vira para a cesta driblando parado
        olharPara(ARO_DA_QUADRA);
        alvo = driblar(q, q.tempo, { pE: -0.2, pD: -0.2, jE: 0.4, jD: 0.4, tronco: 0.15 });
        if (q.tempo > 0.9) { q.fase = "vai"; q.tempo = 0; }
      } else if (q.fase === "arremessa") {
        olharPara(ARO_DA_QUADRA);
        alvo = poseDoArremesso(q.tempo);
        if (q.tempo >= 0.35 && !q.saltou) { q.saltou = true; q.salto = 0; }
        bolaNasMaos(k, b);
        if (q.tempo >= 0.62) { q.fase = "voo"; q.tempo = 0; q.de.copy(b); q.erra = Math.random() < 0.3; }
      } else if (q.fase === "voo") {
        const f = Math.min(1, q.tempo / 0.95);
        b.lerpVectors(q.de, ARO_DA_QUADRA, f);
        b.y += Math.sin(f * PI) * 0.9 + 0.08;
        q.bola.rotation.z -= dt * 9;
        alvo = poseDepois(q.tempo, 0, false);
        if (f >= 1) { q.fase = "quica"; q.tempo = 0; q.reacao = 1.0; q.acertou = !q.erra; q.de.copy(b); }
      } else if (q.fase === "quica") {
        // pela rede (ou espirrando do aro), quica duas vezes e volta para a mão
        const f = Math.min(1, q.tempo / 1.3);
        noCorpo(k, 0, 0.9, 0.35, ladoDaBola);
        b.lerpVectors(q.de, ladoDaBola, f);
        const queda = Math.max(0, 1 - f * 1.6);
        b.y = 0.18 + (q.de.y - 0.18) * queda * queda + Math.abs(Math.sin(f * PI * 2)) * 0.5 * (1 - f) + (ladoDaBola.y - 0.18) * suave((f - 0.8) / 0.2);
        alvo = q.tempo < 0.25 ? poseDepois(0.6, 0, false) : poseDepois(1, q.reacao, q.acertou);
        if (q.reacao > 0 && q.acertou) quique = Math.abs(Math.sin(q.reacao * 10)) * 0.14;
        if (f >= 1) { q.fase = "sai"; q.tempo = 0; }
      }
      posar(k, amortecer(alvo, q.salto, 0.55), dt);
      k.grupo.position.y = 0.06 + alturaDoSalto(q.salto, 0.55, 0.32) + quique - descida(k.pose);
    };

    (maquina.dados.jogos_no_espaco || []).forEach((j) => {
      if (!j.poster) return;
      const img = new Image();
      img.decoding = "async";
      img.addEventListener("load", () => {
        telas.forEach((item) => { item.pintar(item.ctx); item.tex.needsUpdate = true; });
        if (j.slug === "swish-arena") {
          const tex = new T.Texture(img);
          tex.colorSpace = T.SRGBColorSpace;
          tex.needsUpdate = true;
          matTabelaEspera.map = tex;
          matTabelaEspera.color.set("#ffffff");
          matTabelaEspera.needsUpdate = true;
        }
      });
      img.src = j.poster;
      posters[j.slug] = img;
    });
    /** As crianças brincando (um passo de `dt` segundos). */
    const brincar = (dt, t) => {
      cestas.forEach((c) => andarCesta(c, dt, t));
      circulos.forEach((j) => andarCirculo(j, dt, t));
      pulando.forEach((c) => andarPulando(c, dt));
      andarEscalada(escalando, dt);
      andarQuadra(quadra, dt);
    };
    // as primeiras cores e telas, e as crianças já no meio da brincadeira
    // (com menos movimento, ficam assim, paradas, até o passeio)
    for (let n = 0; n < 30; n++) brincar(0.05, n * 0.05);
    aros.instanceColor.needsUpdate = true;
    lentes.instanceColor.needsUpdate = true;
    telas.forEach((item) => { item.pintar(item.ctx); item.tex.needsUpdate = true; });
    // o que mexe não é chão nem parede: fica fora dos raios (o toque na
    // máquina, o piso do passeio) -- e o "SWISH!" é um sprite, que nem pode
    g.traverse((o) => { o.raycast = () => {}; });

    const onde = new T.Vector3();
    const olhar = new T.Vector3();
    let vez = 0;
    const quadro = (dt, t, camera) => {
      // de longe não mexe (não se vê, e poupa o celular)
      maquina.grupo.getWorldPosition(onde);
      if (camera.position.distanceTo(onde) > 95) return;
      if (infoSwish && !pediuSwish) carregarSwish();
      brincar(dt, t);
      andarSwish(dt, t, camera, camera.position.distanceTo(cestas[2].tabela.getWorldPosition(olhar)) < 45);
      if (swish.visible) {
        swishVida = Math.max(0, swishVida - dt * 0.8);
        const a = swishDe.aro;
        swish.position.set(a.x, a.y + 0.35 + (1 - swishVida) * 0.35, a.z + 0.3);
        const tamanho = 0.55 + Math.min(1, (1 - swishVida) * 4) * 0.15;
        swish.scale.set(tamanho * 3.2, tamanho, 1);
        swish.material.opacity = Math.min(1, swishVida * 1.6);
        if (swishVida <= 0) swish.visible = false;
      }
      if (fimGol > 0) {
        fimGol -= dt;
        if (fimGol <= 0) { tempoGol = 45; circulos.forEach((j) => { j.gols = 0; j.pontos = 0; }); }
      } else {
        tempoGol -= dt;
        if (tempoGol <= 0) { tempoGol = 0; fimGol = 4; }
      }
      aros.instanceColor.needsUpdate = true;
      lentes.instanceColor.needsUpdate = true;
      // as telas: no máximo duas por quadro, 8 vezes por segundo cada,
      // só as de perto e de frente para a câmera
      camera.getWorldDirection(olhar);
      for (let n = 0; n < telas.length; n++) {
        const item = telas[(vez + n) % telas.length];
        if (t - item.ultimo < 1 / 8 || !aVista(item.suporte)) continue;
        if (!arena.podePintar()) break;
        item.ultimo = t;
        item.pintar(item.ctx);
        item.tex.needsUpdate = true;
        break;
      }
      vez = (vez + 1) % telas.length;
    };
    // o passeio avisa: "swish:2" -- a enterrada de quem passa pela cesta 2
    quadro.evento = (nome) => {
      const [tipo, valor] = nome.split(":");
      const c = cestas[Number(valor)];
      if (tipo === "swish" && c) {
        arremessarNoJogo(c.jogo, false); // a enterrada conta no jogo da tabela
        c.balanco = 1;
      }
    };
    return quadro;
  },
};

/* ======================================================================
   UMA MÁQUINA — o estande e o objeto 3D (.glb) dela
   ====================================================================== */

/** As fotos de cada lado (lado -> URL), para a ficha; a capa vale como frente. */
function fotosDe(dados) {
  const fotos = {};
  (dados.fotos || []).forEach((f) => {
    if (f.url && LADOS.includes(f.tipo) && !fotos[f.tipo]) fotos[f.tipo] = f.url;
  });
  if (!fotos.perfil && dados.capa) fotos.perfil = dados.capa;
  return fotos;
}

class Maquina {
  constructor(arena, dados, indice) {
    const T = arena.T;
    this.arena = arena;
    this.dados = dados;
    this.indice = indice;
    this.cor = COR_DA_ZONA[dados.grupo] || CORES[indice % CORES.length];
    this.fotos = fotosDe(dados);
    // só entra na roda quem tem o objeto 3D de verdade (core/arena.py, na_roda_3d)
    this.modelo = dados.modelo || "";
    // um espaço inteiro (o parque de trampolins com as quadras) não cabe na
    // roda: fica no seu próprio "reino", ao lado, ligado por uma passarela
    this.reino = Boolean(dados.reino);

    // o tamanho de verdade do objeto (o do código ou o lido do .glb) reserva
    // o lugar dele na roda antes de o arquivo chegar
    const medidas = (dados.medidas_modelo || []).length === 3 ? dados.medidas_modelo : dados.medidas;
    const [altura, largura, fundo] = (medidas || []).map(Number);
    const teto = dados.reino ? 60 : 14;
    this.altura = limitar(altura || 1.8, 0.6, 6);
    this.largura = limitar(largura || 1, 0.4, teto);
    this.fundo = limitar(fundo || 1, 0.3, teto);
    // Grande (um brinquedão de 11 m) não gira no prato -- varreria os
    // vizinhos da roda --: nas vistas, quem dá a volta é a câmera. E fica
    // numa plataforma do seu formato, e não num pedestal redondo.
    this.grande = Math.max(this.largura, this.fundo) > 4.5;
    this.retangular = this.grande && Math.max(this.largura, this.fundo) > 1.6 * Math.min(this.largura, this.fundo);
    this.raioP = this.retangular ? this.fundo / 2 + 0.55 : Math.max(this.largura, this.fundo) * 0.62 + 0.45;
    this.alturaP = 0.3;
    // o objeto montado (até o arquivo chegar, o tamanho reservado)
    this.H = this.altura;
    this.D = this.fundo;
    this.pedido = false;
    this.montada = 0;
    this.girando = false;
    this.giroAlvo = 0;
    this.tombo = 0;
    this.tomboAlvo = 0;

    const grupo = new T.Group();
    this.grupo = grupo;
    if (this.retangular) {
      this.aro = arena.plataforma(grupo, this.largura + 0.9, this.fundo + 0.9, this.alturaP, this.cor);
    } else {
      arena.cilindro(grupo, this.raioP, this.alturaP, arena.pedestal(), 0, this.alturaP / 2, 0, 48);
      this.aro = arena.anel(grupo, this.raioP + 0.02, 0.045, arena.luz(this.cor, 2.2), 0, this.alturaP, 0);
      this.aro.rotation.x = PI / 2;
    }
    this.sombra = new T.Mesh(arena.geo("disco", () => new T.CircleGeometry(1, 32)), arena.matSombra());
    this.sombra.rotation.x = -PI / 2;
    this.sombra.position.y = this.alturaP + 0.006;
    this.sombra.scale.set(this.largura * 0.75, this.fundo * 0.75, 1);
    grupo.add(this.sombra);

    // prato (gira) > pivô (tomba, no meio da máquina) > corpo (o objeto)
    this.prato = new T.Group();
    this.prato.position.y = this.alturaP;
    grupo.add(this.prato);
    this.pivo = new T.Group();
    this.prato.add(this.pivo);
    this.corpo = new T.Group();
    this.pivo.add(this.corpo);
    this.ajustarPivo();

    // a placa com o nome, no pé do pedestal, virada para o centro
    const placa = new T.Mesh(arena.geo("plano", () => new T.PlaneGeometry(1, 1)), arena.materialDeTexto([dados.nome], this.cor, 640, 128));
    placa.scale.set(Math.min(2.4, this.raioP * 1.7), Math.min(2.4, this.raioP * 1.7) / 5, 1);
    placa.position.set(0, 0.22, this.raioP + 0.5);
    placa.rotation.x = -1.1;
    grupo.add(placa);

    grupo.visible = false;
    this.marcar();
    arena.cena.add(grupo);
  }

  /** Tudo do estande responde ao toque como a máquina. */
  marcar() {
    this.grupo.traverse((obj) => { obj.userData.maquina = this; });
    this.arena.caixasSujas = true;
  }

  ajustarPivo() {
    this.pivo.position.y = this.H / 2;
    this.corpo.position.y = -this.H / 2;
  }

  /** Pede o objeto 3D (uma vez só): ele fura a fila, é o que mais se quer ver. */
  pedir() {
    if (this.pedido) return;
    this.pedido = true;
    this.arena.fila.unshift(() => this.vestirModelo());
  }

  /** O objeto 3D feito com os arquivos da fábrica (.glb), no tamanho real. */
  async vestirModelo() {
    const T = this.arena.T;
    try {
      const gltf = await this.arena.carregarModelo(this.modelo);
      const objeto = gltf.scene;
      // o arquivo inteiro fica guardado: as cores trocam os materiais dele
      this.gltf = gltf;
      const caixa = new T.Box3().setFromObject(objeto);
      const tamanho = caixa.getSize(new T.Vector3());
      objeto.position.y -= caixa.min.y;
      this.corpo.add(objeto);
      this.H = tamanho.y;
      this.W = tamanho.x;
      this.D = tamanho.z;
      this.montada = 1;
      this.sombra.scale.set(this.W * 0.62, this.D * 0.7, 1);
      // o espaço tem o próprio piso: a sombra por cima dele só mancharia
      this.sombra.visible = !this.reino;
      this.arena.caixasSujas = true;
      const animacao = ANIMACOES[this.dados.modelo_id];
      if (animacao && !this.animar) this.animar = animacao(this.arena, this);
      this.ajustarPivo();
      this.marcar();
      // escolhida antes de o objeto chegar: as cores aparecem agora na ficha
      if (this.arena.selecionada === this) this.arena.mostrarCores(this);
    } catch (erro) {
      // sem o objeto não há o que mostrar: a máquina sai da roda (fica na
      // lista e na galeria de fotos) e a roda se fecha sem o buraco
      console.error("Arena 3D: o objeto 3D não carregou", erro);
      this.arena.tirarDaRoda(this);
    }
  }

  /** O centro do que a câmera deve olhar, já com o "levantar" da vista de baixo. */
  centro(alvo) {
    this.grupo.getWorldPosition(alvo);
    alvo.y = this.alturaP + this.pivo.position.y;
    return alvo;
  }

  atualizar(dt, reduzido) {
    if (this.grande) return; // o grande fica parado; a câmera é que anda
    const k = 1 - Math.exp(-dt * (reduzido ? 30 : 5));
    if (this.girando && !reduzido) this.prato.rotation.y += dt * 0.5;
    else this.prato.rotation.y += (this.giroAlvo - this.prato.rotation.y) * k;
    this.tombo += (this.tomboAlvo - this.tombo) * k;
    this.pivo.rotation.x = this.tombo;
    // tombada, a máquina levanta o bastante para não entrar no pedestal
    const t = Math.abs(this.tombo);
    const meia = (this.H / 2) * Math.cos(t) + (this.D / 2) * Math.sin(t);
    this.pivo.position.y = this.H / 2 + Math.max(0, meia - this.H / 2) + 0.25 * (t / Math.abs(TOMBO));
    this.corpo.position.y = -this.H / 2;
  }
}

/* ======================================================================
   O SÍMBOLO E O PARQUE — os desenhos que não dependem da cena
   ====================================================================== */

/** Números "sorteados" sempre iguais (o parque fica igual a cada montagem da roda). */
function sorteador(semente) {
  let s = semente >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Um texto ao longo de um arco, com o pé das letras para fora e o topo
 * para o meio, lido da esquerda para a direita por quem está do lado de
 * fora daquele arco (`centro` é o ângulo do meio do texto, no canvas).
 */
function textoNoArco(g, texto, centro, raio, peso, tamanho, cor, espaco = 0.05) {
  g.font = `${peso} ${tamanho}px Poppins, Manrope, sans-serif`;
  const letras = [...texto];
  const larguras = letras.map((letra) => g.measureText(letra).width + tamanho * espaco);
  let a = centro + larguras.reduce((soma, l) => soma + l, 0) / raio / 2;
  g.fillStyle = cor;
  g.textAlign = "center";
  g.textBaseline = "middle";
  letras.forEach((letra, i) => {
    const meio = a - larguras[i] / raio / 2;
    a -= larguras[i] / raio;
    g.save();
    g.translate(Math.cos(meio) * raio, Math.sin(meio) * raio);
    g.rotate(meio - PI / 2);
    g.fillText(letra, 0, 0);
    g.restore();
  });
}

/** O símbolo da Lazer & Sport (o do logo), num canvas de `n` px: alvo, dardo e o nome em volta. */
function pintarSimbolo(g, n) {
  g.clearRect(0, 0, n, n);
  g.save();
  g.translate(n / 2, n / 2);
  g.scale(n / 1024, n / 1024); // desenhado em 1024 px
  const disco = (r, cor) => { g.fillStyle = cor; g.beginPath(); g.arc(0, 0, r, 0, PI * 2); g.fill(); };
  const anel = (r, cor, largura) => { g.strokeStyle = cor; g.lineWidth = largura; g.beginPath(); g.arc(0, 0, r, 0, PI * 2); g.stroke(); };
  // a borda azul-noite com o neon amarelo
  disco(512, "#0b1440");
  g.save();
  g.shadowColor = "#ffd700";
  g.shadowBlur = 20;
  anel(493, "#ffd700", 9);
  g.restore();
  // a faixa branca do nome, como o selo do logo, com os fios vermelhos
  disco(476, "#fbfbff");
  anel(464, "#e63946", 6);
  // o alvo, vermelho e branco, com o contorno escuro e o brilho do volume
  disco(330, "#141a3a");
  [[322, "#e63946"], [266, "#ffffff"], [210, "#e63946"], [154, "#ffffff"], [98, "#e63946"]].forEach(([r, cor]) => disco(r, cor));
  const luz = g.createRadialGradient(-120, -130, 10, -70, -70, 340);
  luz.addColorStop(0, "rgba(255, 255, 255, .3)");
  luz.addColorStop(1, "rgba(255, 255, 255, 0)");
  g.fillStyle = luz;
  g.beginPath(); g.arc(0, 0, 322, 0, PI * 2); g.fill();
  // os nomes na faixa: "Lazer & Sport" embaixo (a entrada), o resto em cima
  textoNoArco(g, "Lazer & Sport", PI / 2, 396, 800, 104, "#141a3a", 0.03);
  textoNoArco(g, "BRINQUEDOS • CENOGRAFIA • PARQUES", -PI / 2, 402, 800, 46, "#e63946", 0.08);
  // estrelinhas no vão da esquerda
  [[-0.17, 404, 22], [0, 400, 30], [0.17, 404, 22]].forEach(([da, r, t]) => {
    const a = PI + da;
    g.save();
    g.translate(Math.cos(a) * r, Math.sin(a) * r);
    g.rotate(a);
    g.fillStyle = "#ffc400";
    g.beginPath();
    for (let i = 0; i < 10; i++) {
      const ri = i % 2 ? t * 0.45 : t;
      g.lineTo(Math.cos((i / 10) * PI * 2 - PI / 2) * ri, Math.sin((i / 10) * PI * 2 - PI / 2) * ri);
    }
    g.fill();
    g.restore();
  });
  // o dardo azul, cravado no meio, saindo pelo vão da direita
  g.save();
  g.rotate(-0.02);
  g.lineJoin = "round";
  g.fillStyle = "#3d4660";
  g.beginPath(); g.moveTo(0, 0); g.lineTo(70, -12); g.lineTo(70, 12); g.closePath(); g.fill();
  g.fillStyle = "#2f8bff";
  g.beginPath(); g.arc(78, 0, 22, 0, PI * 2); g.fill();
  g.fillStyle = "#f4f6ff";
  g.strokeStyle = "#141a3a";
  g.lineWidth = 7;
  g.beginPath();
  if (g.roundRect) g.roundRect(96, -15, 300, 30, 15); else g.rect(96, -15, 300, 30);
  g.fill();
  g.stroke();
  [[-1, "#3fd0ff"], [1, "#2f8bff"]].forEach(([lado, cor]) => {
    g.fillStyle = cor;
    g.beginPath();
    g.moveTo(350, lado * 10);
    g.lineTo(455, lado * 74);
    g.lineTo(478, lado * 50);
    g.lineTo(420, lado * 8);
    g.closePath();
    g.fill();
    g.stroke();
  });
  g.restore();
  g.restore();
}

/**
 * Um carrinho de festa (pipoca ou algodão-doce), em peças com a cor nos
 * vértices, de frente para +z e com as rodas no chão: o toldo listrado, a
 * vitrine acesa e as rodas. Devolve a geometria (para juntar com as outras).
 */
function montarCarrinho(T, tipo) {
  const pipoca = tipo === "pipoca";
  const corpo = pipoca ? "#e63946" : "#ff5fc8";
  const pecas = [];
  [-0.62, 0.62].forEach((x) => {
    const roda = new T.CylinderGeometry(0.28, 0.28, 0.07, 14);
    roda.rotateZ(PI / 2);
    pecas.push(pecaColorida(T, roda, "#232838", x, 0.28, 0));
    const cubo = new T.CylinderGeometry(0.07, 0.07, 0.09, 8);
    cubo.rotateZ(PI / 2);
    pecas.push(pecaColorida(T, cubo, "#ffd700", x, 0.28, 0));
  });
  pecas.push(
    pecaColorida(T, new T.BoxGeometry(1.25, 0.72, 0.75), corpo, 0, 0.78, 0),
    pecaColorida(T, new T.BoxGeometry(1.27, 0.1, 0.77), "#ffffff", 0, 1.0, 0),
    pecaColorida(T, new T.BoxGeometry(1.15, 0.06, 0.7), corpo, 0, 1.72, 0),
    pecaColorida(T, new T.CylinderGeometry(0.03, 0.03, 0.5, 6), "#e9e9f2", 0, 1.98, 0),
  );
  const alca = new T.CylinderGeometry(0.025, 0.025, 0.9, 6);
  alca.rotateZ(PI / 2);
  pecas.push(pecaColorida(T, alca, "#e9e9f2", 0, 1.1, -0.55));
  if (pipoca) {
    // a vitrine cheia de pipoca, acesa
    pecas.push(pecaColorida(T, new T.BoxGeometry(1.05, 0.55, 0.6), "#fff0a6", 0, 1.42, 0));
  } else {
    // as nuvens de algodão-doce no palito
    [[-0.3, "#ffb3e6"], [0.05, "#9fe1ff"], [0.35, "#ffd1f0"]].forEach(([x, cor], i) => {
      pecas.push(pecaColorida(T, new T.CylinderGeometry(0.012, 0.012, 0.35, 4), "#f4f6ff", x, 1.3, 0.05 * i));
      pecas.push(pecaColorida(T, new T.IcosahedronGeometry(0.2, 1), cor, x, 1.55, 0.05 * i));
    });
  }
  // o toldo listrado: um cone de 8 gomos, cada gomo de uma cor
  const toldo = new T.ConeGeometry(0.95, 0.45, 8, 1, true).toNonIndexed();
  const listra = [new T.Color(corpo), new T.Color("#ffffff")];
  const cores = new Float32Array(toldo.attributes.position.count * 3);
  for (let v = 0; v < toldo.attributes.position.count; v++) {
    const c = listra[Math.floor(v / 6) % 2];
    cores.set([c.r, c.g, c.b], v * 3);
  }
  toldo.setAttribute("color", new T.BufferAttribute(cores, 3));
  toldo.translate(0, 2.42, 0);
  pecas.push(toldo);
  return juntarPecas(T, pecas);
}

/* ======================================================================
   A ARENA
   ====================================================================== */
class Arena {
  constructor(THREE, raiz, palco, dados) {
    const T = THREE;
    this.T = T;
    this.raiz = raiz;
    this.palco = palco;
    this.zonas = dados.zonas || [];
    this.reduzido = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    this.celular = window.matchMedia && window.matchMedia("(max-width: 700px)").matches;
    this.zona = "";
    this.categoria = "";
    this.roda = [];
    this.lista = [];
    this.selecionada = null;
    this.relogio = 0;
    this.ocioso = 0;
    this.tour = false;
    this.tourTempo = 0;
    this.fila = [];
    this.trabalhando = 0;
    this.geometrias = new Map();
    this.materiais = new Map();

    this.canvas = document.createElement("canvas");
    this.canvas.className = "arena3d-tela";
    this.canvas.setAttribute("role", "img");
    this.canvas.setAttribute("aria-label", "Arena 3D da Lazer & Sport: um parque com os brinquedos da fábrica em 3D. Arraste para girar e toque num brinquedo para ver a ficha.");
    palco.prepend(this.canvas);

    const densidade = Math.min(window.devicePixelRatio || 1, this.celular ? 1.5 : 1.75);
    this.densidadeMaxima = densidade;
    this.densidadeMinima = Math.min(densidade, this.celular ? 0.75 : 1);
    this.renderer = new T.WebGLRenderer({ canvas: this.canvas, antialias: densidade < 2, powerPreference: "high-performance" });
    this.renderer.setPixelRatio(densidade);
    this.renderer.toneMapping = T.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.15;
    this.renderer.outputColorSpace = T.SRGBColorSpace;
    this.anisotropia = Math.min(4, this.renderer.capabilities.getMaxAnisotropy());

    this.cena = new T.Scene();
    // o fundo e a neblina na cor do horizonte do céu (montarCeu): o chão
    // de longe some nele sem emenda
    this.cena.background = new T.Color(HORIZONTE);
    this.cena.fog = new T.Fog(HORIZONTE, 30, 90);
    this.camera = new T.PerspectiveCamera(45, 1, 0.1, 400);
    this.camera.position.set(0, 12, 28);
    this.raycaster = new T.Raycaster();
    this.ponteiro = new T.Vector2();
    this.ajuda = new T.Vector3();

    this.montarLuzes();
    this.montarPiso();
    this.montarCentro();
    this.montarCeu();
    this.montarFesta();
    this.decoracao = new T.Group();
    this.cena.add(this.decoracao);

    // só quem tem o objeto 3D (o servidor já manda só esses)
    this.maquinas = (dados.maquinas || []).filter((d) => d.modelo).map((d, i) => new Maquina(this, d, i));
    this.camera3d = new Camera(this);
  }

  /* ---------- materiais e geometrias compartilhados ---------- */
  mat(chave, criar) {
    if (!this.materiais.has(chave)) this.materiais.set(chave, criar());
    return this.materiais.get(chave);
  }

  geo(chave, criar) {
    if (!this.geometrias.has(chave)) this.geometrias.set(chave, criar());
    return this.geometrias.get(chave);
  }

  plastico(cor) {
    return this.mat("plastico" + cor, () => new this.T.MeshStandardMaterial({ color: cor, roughness: 0.42, metalness: 0.08 }));
  }

  metal(cor = "#9aa7bd") {
    return this.mat("metal" + cor, () => new this.T.MeshStandardMaterial({ color: cor, roughness: 0.28, metalness: 0.85 }));
  }

  luz(cor, intensidade = 2.2) {
    return this.mat("luz" + cor + intensidade, () => new this.T.MeshStandardMaterial({
      color: "#05070d", emissive: cor, emissiveIntensity: intensidade, roughness: 0.6,
    }));
  }

  escuro() {
    return this.mat("escuro", () => new this.T.MeshStandardMaterial({ color: "#11182b", roughness: 0.55, metalness: 0.35 }));
  }

  /**
   * O pedestal e a plataforma: o tampo deles fica no mesmo plano do piso do
   * objeto (o EVA do Espaço, a base do brinquedão). Empurrado um tico para
   * trás na profundidade, o objeto sempre vence -- sem as duas cores
   * brigando ("piscando") quando a câmera anda.
   */
  pedestal() {
    return this.mat("pedestal", () => new this.T.MeshStandardMaterial({
      color: "#11182b", roughness: 0.55, metalness: 0.35, polygonOffset: true, polygonOffsetFactor: 2, polygonOffsetUnits: 4,
    }));
  }

  /** O que é pintado no chão (áreas, passarela, sombra): puxado para a frente. */
  noChao(material) {
    material.polygonOffset = true;
    material.polygonOffsetFactor = -2;
    material.polygonOffsetUnits = -4;
    return material;
  }

  borracha() {
    return this.mat("borracha", () => new this.T.MeshStandardMaterial({ color: "#05070c", roughness: 0.9 }));
  }

  /**
   * O objeto 3D de uma máquina (.glb). O GLTFLoader vem na primeira vez
   * que precisa, do mesmo endereço do three.js (sem ?v=): os dois falam
   * com a mesma cópia do motor.
   */
  async carregarModelo(url) {
    if (!this.carregadorGLB) {
      this.carregadorGLB = import(this.palco.dataset.gltf).then((modulo) => new modulo.GLTFLoader());
    }
    return (await this.carregadorGLB).loadAsync(url);
  }

  /** O módulo das cores dos objetos 3D (cores3d.js), na primeira vez que precisa. */
  modulosDeCor() {
    if (!this.cores3d) this.cores3d = import(this.palco.dataset.cores3d);
    return this.cores3d;
  }

  /**
   * As cores do objeto 3D na ficha: as variações que o arquivo traz ou os
   * tons da adesivagem. Tocar numa veste a máquina naquela cor.
   */
  async mostrarCores(m) {
    const caixa = this.ficha && this.ficha.querySelector("[data-ficha-cores]");
    if (!caixa) return;
    // a ficha pode pedir de novo antes de a primeira chegar: vale a última
    const vez = (this.vezDasCores = (this.vezDasCores || 0) + 1);
    caixa.hidden = true;
    caixa.replaceChildren();
    if (!m.gltf || !this.palco.dataset.cores3d) return;
    let modulo;
    try {
      modulo = await this.modulosDeCor();
    } catch (erro) {
      return;
    }
    if (vez !== this.vezDasCores || this.selecionada !== m) return;
    const cores = modulo.coresDoObjeto(m.gltf);
    if (cores.length < 2) return;
    // o rótulo com o ícone da paleta: "Cores do brinquedo"
    const rotulo = document.createElement("span");
    rotulo.className = "arena3d-cores-rotulo";
    const iconePaleta = document.createElement("i");
    iconePaleta.className = "fa-solid fa-palette";
    iconePaleta.setAttribute("aria-hidden", "true");
    rotulo.append(iconePaleta, document.createTextNode(" Cores"));
    const botoes = cores.map((cor, i) => {
      const botao = document.createElement("button");
      botao.type = "button";
      botao.className = "arena3d-cor";
      botao.setAttribute("aria-pressed", i === (m.corEscolhida || 0) ? "true" : "false");
      const amostra = modulo.amostraDaCor(m.gltf, cor);
      if (amostra) botao.style.setProperty("--amostra", amostra);
      const bolinha = document.createElement("i");
      bolinha.setAttribute("aria-hidden", "true");
      botao.append(bolinha, document.createTextNode(cor.nome));
      botao.addEventListener("click", async () => {
        // tocar de novo na cor escolhida volta para a anterior (ou para a original)
        let k = i;
        const atual = m.corEscolhida || 0;
        if (k === atual) { if (k === 0) return; k = (m.corAnterior || 0) === k ? 0 : (m.corAnterior || 0); }
        m.corAnterior = atual;
        m.corEscolhida = k;
        botoes.forEach((x, j) => x.setAttribute("aria-pressed", j === k ? "true" : "false"));
        await modulo.aplicarCor(m.gltf, cores[k]);
      });
      return botao;
    });
    caixa.replaceChildren(rotulo, ...botoes);
    caixa.hidden = false;
  }

  /** A plataforma do brinquedão comprido: retângulo de cantos redondos, com a faixa de luz. */
  plataforma(grupo, w, d, altura, cor) {
    const T = this.T;
    const forma = (lw, ld, r) => {
      const s = new T.Shape();
      const x = -lw / 2;
      const y = -ld / 2;
      s.moveTo(x + r, y);
      s.lineTo(x + lw - r, y);
      s.quadraticCurveTo(x + lw, y, x + lw, y + r);
      s.lineTo(x + lw, y + ld - r);
      s.quadraticCurveTo(x + lw, y + ld, x + lw - r, y + ld);
      s.lineTo(x + r, y + ld);
      s.quadraticCurveTo(x, y + ld, x, y + ld - r);
      s.lineTo(x, y + r);
      s.quadraticCurveTo(x, y, x + r, y);
      return s;
    };
    const r = Math.min(0.8, d / 2 - 0.05);
    const base = new T.Mesh(new T.ExtrudeGeometry(forma(w, d, r), { depth: altura, bevelEnabled: false, curveSegments: 10 }), this.pedestal());
    base.rotation.x = -PI / 2; // a extrusão (Z) vira a altura (Y)
    grupo.add(base);
    const faixa = forma(w + 0.09, d + 0.09, r + 0.045);
    faixa.holes.push(forma(w - 0.01, d - 0.01, r - 0.005));
    const aro = new T.Mesh(new T.ExtrudeGeometry(faixa, { depth: 0.06, bevelEnabled: false, curveSegments: 10 }), this.luz(cor, 2.2));
    aro.rotation.x = -PI / 2;
    aro.position.y = altura - 0.04;
    grupo.add(aro);
    return aro;
  }

  /** A base de baixo das máquinas: chapa escura, como a de um gabinete. */
  matBase() {
    return this.mat("base", () => new this.T.MeshBasicMaterial({ color: "#1a2233", vertexColors: true, toneMapped: false }));
  }

  matBaseDentro() {
    return this.mat("baseDentro", () => new this.T.MeshBasicMaterial({ color: "#10141d", side: this.T.BackSide, toneMapped: false }));
  }

  matSombra() {
    return this.mat("sombra", () => {
      const tela = document.createElement("canvas");
      tela.width = tela.height = 128;
      const g = tela.getContext("2d");
      const grad = g.createRadialGradient(64, 64, 0, 64, 64, 64);
      grad.addColorStop(0, "rgba(0,0,0,.65)");
      grad.addColorStop(1, "rgba(0,0,0,0)");
      g.fillStyle = grad;
      g.fillRect(0, 0, 128, 128);
      return this.noChao(new this.T.MeshBasicMaterial({ map: new this.T.CanvasTexture(tela), transparent: true, depthWrite: false }));
    });
  }

  /** Uma placa de texto (o nome da máquina, a área): fundo escuro e borda na cor. */
  materialDeTexto(linhas, cor, largura = 1024, altura = 256) {
    const tela = document.createElement("canvas");
    tela.width = largura;
    tela.height = altura;
    const g = tela.getContext("2d");
    const raio = altura * 0.3;
    g.fillStyle = "rgba(5, 11, 31, .9)";
    g.beginPath();
    if (g.roundRect) g.roundRect(6, 6, largura - 12, altura - 12, raio);
    else g.rect(6, 6, largura - 12, altura - 12);
    g.fill();
    g.lineWidth = altura * 0.045;
    g.strokeStyle = cor;
    g.stroke();
    g.textAlign = "center";
    g.textBaseline = "middle";
    const caber = (texto, peso, tamanho) => {
      let t = tamanho;
      g.font = `${peso} ${t}px Poppins, Manrope, sans-serif`;
      while (g.measureText(texto).width > largura - altura * 0.5 && t > tamanho * 0.5) {
        t -= 2;
        g.font = `${peso} ${t}px Poppins, Manrope, sans-serif`;
      }
    };
    if (linhas.length > 1 && linhas[0]) {
      g.fillStyle = cor;
      caber(linhas[0].toUpperCase(), 800, altura * 0.18);
      g.fillText(linhas[0].toUpperCase(), largura / 2, altura * 0.32);
      g.fillStyle = "#ffffff";
      caber(linhas[1], 900, altura * 0.28);
      g.fillText(linhas[1], largura / 2, altura * 0.66);
    } else {
      const texto = linhas[linhas.length - 1];
      g.fillStyle = "#ffffff";
      caber(texto, 900, altura * 0.42);
      g.fillText(texto, largura / 2, altura * 0.53);
    }
    const textura = new this.T.CanvasTexture(tela);
    textura.colorSpace = this.T.SRGBColorSpace;
    // placa de texto vista de longe e deitada: o filtro mais forte que houver
    textura.anisotropy = this.renderer.capabilities.getMaxAnisotropy();
    return new this.T.MeshBasicMaterial({ map: textura, transparent: true, depthWrite: false, toneMapped: false });
  }

  /* ---------- peças ---------- */
  caixa(pai, w, h, d, material, x = 0, y = 0, z = 0) {
    const m = new this.T.Mesh(this.geo("caixa", () => new this.T.BoxGeometry(1, 1, 1)), material);
    m.scale.set(w, h, d);
    m.position.set(x, y, z);
    pai.add(m);
    return m;
  }

  cilindro(pai, r, h, material, x = 0, y = 0, z = 0, lados = 24) {
    const m = new this.T.Mesh(this.geo("cil" + lados, () => new this.T.CylinderGeometry(1, 1, 1, lados)), material);
    m.scale.set(r, h, r);
    m.position.set(x, y, z);
    pai.add(m);
    return m;
  }

  esfera(pai, r, material, x = 0, y = 0, z = 0) {
    const m = new this.T.Mesh(this.geo("esfera", () => new this.T.SphereGeometry(1, 24, 16)), material);
    m.scale.setScalar(r);
    m.position.set(x, y, z);
    pai.add(m);
    return m;
  }

  anel(pai, r, espessura, material, x = 0, y = 0, z = 0) {
    // o toro é proporcional: guarda-se o de raio 1 e escala-se o resto
    const proporcao = (espessura / r).toFixed(3);
    const m = new this.T.Mesh(this.geo("toro" + proporcao, () => new this.T.TorusGeometry(1, Number(proporcao), 12, 48)), material);
    m.scale.setScalar(r);
    m.position.set(x, y, z);
    pai.add(m);
    return m;
  }

  /* ---------- luz, piso, centro, céu ---------- */
  montarLuzes() {
    const T = this.T;
    this.cena.add(new T.HemisphereLight("#b9d4ff", "#0a1430", 1.25));
    const sol = new T.DirectionalLight("#ffffff", 2.1);
    sol.position.set(8, 20, 12);
    this.cena.add(sol);
    const contra = new T.DirectionalLight("#7aa8ff", 0.9);
    contra.position.set(-10, 8, -14);
    this.cena.add(contra);

    this.luzesCor = [];
    ["#e63946", "#2f8bff"].forEach((cor, i) => {
      const l = new T.PointLight(cor, 3.2, 40, 0);
      l.position.set(i ? -6 : 6, 7, 0);
      this.cena.add(l);
      this.luzesCor.push(l);
    });

    this.foco = new T.SpotLight("#fff4d6", 0, 30, PI / 7, 0.5, 0);
    this.foco.position.set(0, 12, 0);
    this.cena.add(this.foco);
    this.cena.add(this.foco.target);
  }

  montarPiso() {
    const T = this.T;
    const tamanho = this.celular ? 1024 : 2048;
    const c = document.createElement("canvas");
    c.width = c.height = tamanho;
    const g = c.getContext("2d");
    const meio = tamanho / 2;
    const k = tamanho / 2048;
    const fundo = g.createRadialGradient(meio, meio, 0, meio, meio, meio);
    fundo.addColorStop(0, "#14306e");
    fundo.addColorStop(0.45, "#0a1a42");
    fundo.addColorStop(1, "#040a1c");
    g.fillStyle = fundo;
    g.fillRect(0, 0, tamanho, tamanho);

    // grade radial, como piso de arena
    g.strokeStyle = "rgba(90, 160, 255, .16)";
    g.lineWidth = 2 * k;
    for (let i = 0; i < 48; i++) {
      const a = (i / 48) * PI * 2;
      g.beginPath();
      g.moveTo(meio + Math.cos(a) * 140 * k, meio + Math.sin(a) * 140 * k);
      g.lineTo(meio + Math.cos(a) * meio, meio + Math.sin(a) * meio);
      g.stroke();
    }
    for (let r = 140 * k; r < meio; r += 64 * k) {
      g.beginPath();
      g.arc(meio, meio, r, 0, PI * 2);
      g.stroke();
    }

    // anéis de neon e o nome da casa em volta do centro
    const neon = (raio, cor, largura) => {
      g.save();
      g.shadowColor = cor;
      g.shadowBlur = 30 * k;
      g.strokeStyle = cor;
      g.lineWidth = largura * k;
      g.beginPath();
      g.arc(meio, meio, raio * k, 0, PI * 2);
      g.stroke();
      g.restore();
    };
    neon(200, "#3fd0ff", 6);
    neon(300, "#e63946", 5);
    neon(860, "#2f8bff", 8);

    // O nome da casa em volta do centro, para ser LIDO por quem olha de fora
    // da roda (a vista de sempre): o pé das letras para fora, o topo para o
    // meio, e a frase correndo da esquerda para a direita de quem está ali.
    // Cada letra ocupa a largura dela (um "I" não fica com o espaço de um
    // "W"), e a frase fecha a volta certinha.
    const texto = "LAZER & SPORT  •  ARENA 3D  •  FÁBRICA DE BRINQUEDOS  •  ";
    const raioTexto = 250 * k;
    let alturaLetra = 46 * k;
    g.font = `800 ${alturaLetra}px Poppins, Manrope, sans-serif`;
    const espaco = 0.06; // o respiro entre as letras, em fração da altura
    const larguraDe = (letra) => g.measureText(letra).width + alturaLetra * espaco;
    let volta = [...texto].reduce((soma, letra) => soma + larguraDe(letra), 0);
    // a altura de letra que faz a frase dar a volta inteira
    alturaLetra *= (PI * 2 * raioTexto) / volta;
    g.font = `800 ${alturaLetra}px Poppins, Manrope, sans-serif`;
    volta = [...texto].reduce((soma, letra) => soma + larguraDe(letra), 0);
    g.save();
    g.translate(meio, meio);
    g.textAlign = "center";
    g.textBaseline = "middle";
    g.shadowColor = "rgba(63, 208, 255, .55)";
    g.shadowBlur = 12 * k;
    g.fillStyle = "rgba(255, 255, 255, .78)";
    let andado = 0;
    const comeco = PI / 2; // a primeira letra embaixo, de frente para a entrada
    [...texto].forEach((letra) => {
      const largura = larguraDe(letra);
      const a = comeco - ((andado + largura / 2) / volta) * PI * 2;
      andado += largura;
      if (letra === " ") return;
      g.save();
      g.translate(Math.cos(a) * raioTexto, Math.sin(a) * raioTexto);
      g.rotate(a - PI / 2);
      g.fillText(letra, 0, 0);
      g.restore();
    });
    g.restore();

    const textura = new T.CanvasTexture(c);
    textura.colorSpace = T.SRGBColorSpace;
    textura.anisotropy = Math.min(8, this.renderer.capabilities.getMaxAnisotropy());
    // o piso tem tamanho fixo e é a escala que acompanha a roda montada
    const piso = new T.Mesh(
      new T.CircleGeometry(1, 96),
      new T.MeshStandardMaterial({
        map: textura, emissiveMap: textura, emissive: "#ffffff", emissiveIntensity: 0.35,
        roughness: 0.32, metalness: 0.35,
      }),
    );
    piso.rotation.x = -PI / 2;
    piso.scale.setScalar(36);
    this.cena.add(piso);
    this.piso = piso;
  }

  montarCentro() {
    // o alvo da marca, com o dardo cravado, girando no meio da arena
    const T = this.T;
    const centro = new T.Group();
    this.cilindro(centro, 0.9, 0.5, this.escuro(), 0, 0.25, 0, 40);
    this.anel(centro, 0.92, 0.04, this.luz("#3fd0ff", 3), 0, 0.5, 0).rotation.x = PI / 2;
    this.cilindro(centro, 0.08, 1.4, this.metal(), 0, 1.2, 0, 12);

    const alvo = new T.Group();
    alvo.position.y = 2.75;
    const camadas = [["#e63946", 1.2], ["#ffffff", 0.96], ["#e63946", 0.72], ["#ffffff", 0.48], ["#e63946", 0.24]];
    camadas.forEach(([cor, r], i) => {
      const disco = this.cilindro(alvo, r, 0.18 + i * 0.03, this.plastico(cor), 0, 0, 0, 48);
      disco.rotation.x = PI / 2;
    });
    const dardo = new T.Group();
    this.cilindro(dardo, 0.05, 0.9, this.plastico("#f5f8ff"), 0, 0, 0.55, 12).rotation.x = PI / 2;
    const ponta = new T.Mesh(this.geo("cone", () => new T.ConeGeometry(1, 1, 16)), this.metal("#c8d3e6"));
    ponta.scale.set(0.05, 0.25, 0.05);
    ponta.rotation.x = -PI / 2;
    ponta.position.z = 0.02;
    dardo.add(ponta);
    [0, 1, 2].forEach((i) => {
      const angulo = (i / 3) * PI * 2;
      const aleta = this.caixa(dardo, 0.02, 0.28, 0.3, this.plastico("#3fd0ff"), Math.sin(angulo) * 0.12, Math.cos(angulo) * 0.12, 1.0);
      aleta.rotation.z = -angulo;
    });
    dardo.rotation.set(-0.35, 0.4, 0);
    dardo.position.set(0.12, 0.1, 0.1);
    alvo.add(dardo);
    centro.add(alvo);
    this.cena.add(centro);
    this.centroDaArena = centro;
    this.alvoMarca = alvo;
  }

  /**
   * O CÉU DE FESTA, todo num grupo que acompanha a câmera (o céu fica
   * sempre "no infinito", e nunca sai do alcance dela):
   *   - a cúpula: o crepúsculo de anil (em cima) a roxo e magenta, com o
   *     brilho rosado do parque logo acima do horizonte -- um shader de
   *     poucas contas, sem textura nenhuma; embaixo do horizonte, a cor da
   *     neblina, para o chão sumir nele sem emenda;
   *   - as estrelas, pontos fixos na cúpula (uma chamada de desenho);
   *   - a silhueta do parque lá longe: roda-gigante, montanha-russa e tendas
   *     com as luzinhas (um canvas de 1024 x 128, repetido em volta).
   * E, no mundo, os holofotes do parque varrendo o céu, uns fogos
   * discretos de vez em quando e o confete caindo devagar no ar da arena.
   * Com "menos movimento", holofotes e confete ficam parados e não há fogos.
   */
  montarCeu() {
    const T = this.T;
    const ceu = new T.Group();
    this.ceu = ceu;
    this.cena.add(ceu);
    const cupula = new T.Mesh(new T.SphereGeometry(300, 32, 20), new T.ShaderMaterial({
      uniforms: {
        alto: { value: new T.Color("#060a2c") },
        meio: { value: new T.Color("#26176a") },
        baixo: { value: new T.Color("#7a2c8c") },
        brilho: { value: new T.Color("#ff5f8f") },
        chao: { value: new T.Color(HORIZONTE) },
      },
      vertexShader: "varying vec3 vDir; void main() { vDir = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
      fragmentShader: `
        uniform vec3 alto, meio, baixo, brilho, chao;
        varying vec3 vDir;
        void main() {
          float h = vDir.y;
          vec3 c = mix(baixo, meio, smoothstep(0.0, 0.2, h));
          c = mix(c, alto, smoothstep(0.16, 0.72, h));
          // o brilho do parque no horizonte, mais forte para uns lados (as luzes da cidade)
          float lado = 0.75 + 0.25 * sin(atan(vDir.z, vDir.x) * 3.0);
          c += brilho * (0.5 * lado) * exp(-max(h, 0.0) * 13.0);
          c = mix(chao, c, smoothstep(-0.03, 0.015, h));
          gl_FragColor = vec4(c, 1.0);
          #include <colorspace_fragment>
        }`,
      side: T.BackSide, depthWrite: false,
    }));
    cupula.renderOrder = -3;
    ceu.add(cupula);

    // as estrelas: na cúpula, mais densas no alto, cada uma com o seu brilho
    const brilho = this.texturaDeBrilho();
    const quantas = this.celular ? 220 : 420;
    const pos = new Float32Array(quantas * 3);
    const cores = new Float32Array(quantas * 3);
    for (let i = 0; i < quantas; i++) {
      const y = 0.12 + 0.88 * Math.sqrt(Math.random());
      const a = Math.random() * PI * 2;
      const r = Math.sqrt(1 - y * y);
      pos.set([Math.cos(a) * r * 280, y * 280, Math.sin(a) * r * 280], i * 3);
      const k = 0.45 + Math.random() * 0.55;
      cores.set(Math.random() < 0.15 ? [k, k * 0.8, k * 0.95] : [k * 0.85, k * 0.92, k], i * 3);
    }
    const geoEstrelas = new T.BufferGeometry();
    geoEstrelas.setAttribute("position", new T.BufferAttribute(pos, 3));
    geoEstrelas.setAttribute("color", new T.BufferAttribute(cores, 3));
    const estrelas = new T.Points(geoEstrelas, new T.PointsMaterial({
      size: 2.6, sizeAttenuation: false, map: brilho, vertexColors: true, transparent: true,
      depthWrite: false, blending: T.AdditiveBlending, fog: false, toneMapped: false,
    }));
    estrelas.renderOrder = -2;
    ceu.add(estrelas);

    // a silhueta do parque no horizonte
    const silhueta = new T.Mesh(
      new T.CylinderGeometry(220, 220, 46, 64, 1, true),
      new T.MeshBasicMaterial({ map: this.texturaDaSilhueta(), transparent: true, side: T.BackSide, depthWrite: false, fog: false, toneMapped: false }),
    );
    silhueta.position.y = 46 / 2 - 9; // o pé um pouco abaixo do horizonte
    silhueta.renderOrder = -1;
    ceu.add(silhueta);

    this.montarHolofotes();
    this.montarFogos();
    this.montarConfete();
  }

  /** O brilho redondo (estrelas, postes, fogos): um canvas de 64 px, feito uma vez. */
  texturaDeBrilho() {
    if (this.brilhoRedondo) return this.brilhoRedondo;
    const c = document.createElement("canvas");
    c.width = c.height = 64;
    const g = c.getContext("2d");
    const rad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    rad.addColorStop(0, "rgba(255,255,255,1)");
    rad.addColorStop(0.25, "rgba(255,255,255,.55)");
    rad.addColorStop(1, "rgba(255,255,255,0)");
    g.fillStyle = rad;
    g.fillRect(0, 0, 64, 64);
    this.brilhoRedondo = new this.T.CanvasTexture(c);
    return this.brilhoRedondo;
  }

  /** A silhueta: roda-gigante, montanha-russa, tendas e árvores, com as luzinhas acesas. */
  texturaDaSilhueta() {
    const T = this.T;
    const W = 1024;
    const H = 128;
    const c = document.createElement("canvas");
    c.width = W;
    c.height = H;
    const g = c.getContext("2d");
    const pe = H - 6;
    const cor = "#170d3f";
    g.fillStyle = cor;
    g.strokeStyle = cor;
    const luzes = [];
    // árvores e morrinhos ao longo de tudo
    for (let x = 0; x < W; x += 9) {
      const h = 10 + 7 * Math.sin(x * 0.031) + 5 * Math.sin(x * 0.11 + 1.3);
      g.beginPath();
      g.arc(x, pe - h * 0.5, 7 + (x % 5), 0, PI * 2);
      g.fill();
    }
    g.fillRect(0, pe - 6, W, 6 + 6);
    // a roda-gigante
    const rodaGigante = (cx, r) => {
      const cy = pe - r - 8;
      g.lineWidth = 2.2;
      g.beginPath(); g.arc(cx, cy, r, 0, PI * 2); g.stroke();
      g.lineWidth = 1.2;
      for (let i = 0; i < 12; i++) {
        const a = (i / 12) * PI * 2;
        g.beginPath(); g.moveTo(cx, cy); g.lineTo(cx + Math.cos(a) * r, cy + Math.sin(a) * r); g.stroke();
        g.fillRect(cx + Math.cos(a) * r - 3, cy + Math.sin(a) * r, 6, 6);
        luzes.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r, i % 3]);
      }
      g.lineWidth = 3;
      g.beginPath(); g.moveTo(cx - r * 0.5, pe); g.lineTo(cx, cy); g.lineTo(cx + r * 0.5, pe); g.stroke();
    };
    // a montanha-russa: o trilho ondulado nos pilares
    const montanhaRussa = (x0, x1, alto) => {
      g.lineWidth = 2.5;
      g.beginPath();
      for (let x = x0; x <= x1; x += 4) {
        const t = (x - x0) / (x1 - x0);
        const y = pe - 10 - alto * (0.55 + 0.45 * Math.sin(t * PI * 3.2 + 0.6)) * Math.sin(t * PI);
        if (x === x0) g.moveTo(x, y); else g.lineTo(x, y);
        if ((x - x0) % 16 === 0) { g.fillRect(x - 1, y, 2, pe - y); if ((x - x0) % 32 === 0) luzes.push([x, y - 2, 1]); }
      }
      g.stroke();
    };
    // a tenda listrada do circo, com a bandeirinha
    const tenda = (cx, w, h) => {
      g.beginPath();
      g.moveTo(cx - w / 2, pe);
      g.lineTo(cx - w / 2, pe - h * 0.45);
      g.quadraticCurveTo(cx - w * 0.2, pe - h * 0.6, cx, pe - h);
      g.quadraticCurveTo(cx + w * 0.2, pe - h * 0.6, cx + w / 2, pe - h * 0.45);
      g.lineTo(cx + w / 2, pe);
      g.fill();
      g.fillRect(cx - 1, pe - h - 12, 2, 12);
      g.beginPath(); g.moveTo(cx + 1, pe - h - 12); g.lineTo(cx + 11, pe - h - 9); g.lineTo(cx + 1, pe - h - 6); g.fill();
      luzes.push([cx, pe - h, 2], [cx - w / 2, pe - h * 0.45, 0], [cx + w / 2, pe - h * 0.45, 0]);
    };
    // a torre de queda livre
    const torre = (cx, h) => {
      g.fillRect(cx - 3, pe - h, 6, h);
      g.fillRect(cx - 9, pe - h * 0.55, 18, 6);
      luzes.push([cx, pe - h, 1], [cx, pe - h * 0.5, 2]);
    };
    rodaGigante(150, 46);
    montanhaRussa(250, 470, 52);
    tenda(560, 90, 54);
    torre(660, 96);
    tenda(760, 60, 38);
    rodaGigante(880, 34);
    montanhaRussa(930, 1010, 30);
    // as luzinhas acesas (amarelas, rosas e azuis), com um halo
    const tons = ["#ffd84a", "#ff6fd8", "#7fd8ff"];
    luzes.forEach(([x, y, k]) => {
      g.fillStyle = tons[k];
      g.shadowColor = tons[k];
      g.shadowBlur = 6;
      g.beginPath(); g.arc(x, y, 1.8, 0, PI * 2); g.fill();
    });
    g.shadowBlur = 0;
    const textura = new T.CanvasTexture(c);
    textura.colorSpace = T.SRGBColorSpace;
    textura.wrapS = T.RepeatWrapping;
    textura.repeat.set(3, 1);
    return textura;
  }

  /**
   * Os holofotes: fachos de luz saindo de trás do parque e varrendo o céu
   * devagar. Uma instância por facho (uma chamada de desenho), num shader
   * que apaga o facho para cima e nas beiradas -- parece luz, não cone.
   */
  montarHolofotes() {
    const T = this.T;
    const altura = 90;
    const geo = new T.CylinderGeometry(5.5, 0.35, altura, 20, 1, true);
    geo.translate(0, altura / 2, 0);
    const material = new T.ShaderMaterial({
      uniforms: { altura: { value: altura } },
      vertexShader: `
        uniform float altura;
        varying float vSubida;
        varying float vBorda;
        varying vec3 vCor;
        void main() {
          vec4 p = vec4(position, 1.0);
          mat3 giro = mat3(1.0);
          vCor = vec3(1.0);
          #ifdef USE_INSTANCING
            p = instanceMatrix * p;
            giro = mat3(instanceMatrix);
          #endif
          #ifdef USE_INSTANCING_COLOR
            vCor = instanceColor;
          #endif
          vec4 mv = modelViewMatrix * p;
          vec3 n = normalize(normalMatrix * giro * normal);
          vBorda = abs(dot(n, normalize(-mv.xyz)));
          vSubida = position.y / altura;
          gl_Position = projectionMatrix * mv;
        }`,
      fragmentShader: `
        varying float vSubida;
        varying float vBorda;
        varying vec3 vCor;
        void main() {
          float a = pow(1.0 - vSubida, 1.7) * pow(vBorda, 2.2) * 0.22;
          gl_FragColor = vec4(vCor * a, 1.0);
        }`,
      transparent: true, depthWrite: false, blending: T.AdditiveBlending, side: T.DoubleSide,
    });
    const tons = ["#ff5fd2", "#7fd8ff", "#ffd84a", "#ffffff", "#ff5fd2", "#7fd8ff"];
    const n = this.celular ? 4 : 6;
    const fachos = new T.InstancedMesh(geo, material, n);
    fachos.frustumCulled = false;
    fachos.renderOrder = 2;
    this.fachos = { malha: fachos, lista: [] };
    for (let i = 0; i < n; i++) {
      const a = (i / n) * PI * 2 + 0.35;
      this.fachos.lista.push({ x: Math.sin(a) * 62, z: Math.cos(a) * 62, fase: i * 1.7, giro: a });
      fachos.setColorAt(i, new T.Color(tons[i]));
    }
    this.cena.add(fachos);
    this.animarHolofotes(0);
  }

  animarHolofotes(t) {
    const ajuda = this.ajudaObjeto || (this.ajudaObjeto = new this.T.Object3D());
    const { malha, lista } = this.fachos;
    lista.forEach((f, i) => {
      ajuda.position.set(f.x, -1, f.z);
      // inclinado para dentro do parque, balançando devagar de um lado para o outro
      ajuda.rotation.set(0, 0, 0);
      ajuda.rotateY(f.giro + Math.sin(t * 0.23 + f.fase) * 0.55);
      ajuda.rotateX(-0.42 + Math.sin(t * 0.17 + f.fase * 1.3) * 0.12);
      ajuda.updateMatrix();
      malha.setMatrixAt(i, ajuda.matrix);
    });
    malha.instanceMatrix.needsUpdate = true;
  }

  /**
   * Os fogos: de vez em quando, um estouro pequeno lá longe, sobre o parque
   * (uns 60 pontos que se abrem, caem um pouco e apagam). Um conjunto de
   * pontos só, para todos; as contas são poucas e só com os fogos no ar.
   */
  montarFogos() {
    const T = this.T;
    const POR_ESTOURO = 56;
    const ESTOUROS = 3;
    const total = POR_ESTOURO * ESTOUROS;
    const geo = new T.BufferGeometry();
    geo.setAttribute("position", new T.BufferAttribute(new Float32Array(total * 3), 3));
    geo.setAttribute("color", new T.BufferAttribute(new Float32Array(total * 3), 3));
    const pontos = new T.Points(geo, new T.PointsMaterial({
      size: 2.4, map: this.texturaDeBrilho(), vertexColors: true, transparent: true, depthWrite: false,
      blending: T.AdditiveBlending, fog: false, toneMapped: false,
    }));
    pontos.frustumCulled = false;
    this.cena.add(pontos);
    const direcoes = [];
    for (let i = 0; i < POR_ESTOURO; i++) {
      const y = 1 - (2 * (i + 0.5)) / POR_ESTOURO;
      const r = Math.sqrt(1 - y * y);
      const a = i * 2.39996;
      direcoes.push([Math.cos(a) * r, y, Math.sin(a) * r]);
    }
    this.fogos = {
      pontos, direcoes, POR_ESTOURO,
      estouros: Array.from({ length: ESTOUROS }, () => ({ vida: 99, centro: new T.Vector3(), cor: new T.Color(), forca: 1 })),
      proximo: 2.5,
    };
    pontos.visible = false;
  }

  animarFogos(dt) {
    const f = this.fogos;
    f.proximo -= dt;
    if (f.proximo <= 0) {
      const livre = f.estouros.find((e) => e.vida > 2.2);
      if (livre) {
        const a = Math.random() * PI * 2;
        const r = 80 + Math.random() * 50;
        livre.centro.set(Math.sin(a) * r, 38 + Math.random() * 26, Math.cos(a) * r);
        livre.cor.set(["#ffd84a", "#ff3df2", "#3fd0ff", "#e63946", "#7dff9a"][Math.floor(Math.random() * 5)]);
        livre.forca = 9 + Math.random() * 5;
        livre.vida = 0;
      }
      f.proximo = 2.2 + Math.random() * 3.5;
    }
    const pos = f.pontos.geometry.attributes.position;
    const cor = f.pontos.geometry.attributes.color;
    let algum = false;
    f.estouros.forEach((e, k) => {
      e.vida += dt;
      const vivo = e.vida < 2.2;
      algum = algum || vivo;
      const abre = (1 - Math.exp(-e.vida * 2.6)) * e.forca / 2.6;
      const cai = 1.6 * e.vida * e.vida;
      const apaga = vivo ? Math.pow(1 - e.vida / 2.2, 1.6) : 0;
      for (let i = 0; i < f.POR_ESTOURO; i++) {
        const [dx, dy, dz] = f.direcoes[i];
        const j = k * f.POR_ESTOURO + i;
        pos.setXYZ(j, e.centro.x + dx * abre, e.centro.y + dy * abre - cai, e.centro.z + dz * abre);
        const pisca = 0.75 + 0.25 * Math.sin(e.vida * 30 + i);
        cor.setXYZ(j, e.cor.r * apaga * pisca, e.cor.g * apaga * pisca, e.cor.b * apaga * pisca);
      }
    });
    f.pontos.visible = algum;
    if (algum) {
      pos.needsUpdate = true;
      cor.needsUpdate = true;
    }
  }

  /** O confete: papeizinhos coloridos caindo devagar no ar da arena, balançando. */
  montarConfete() {
    const T = this.T;
    const quantos = this.celular ? 90 : 170;
    const pos = new Float32Array(quantos * 3);
    const cores = new Float32Array(quantos * 3);
    const tons = ["#e63946", "#ffd700", "#2f8bff", "#22c55e", "#ff3df2", "#ff9f1c", "#ffffff"].map((c) => new T.Color(c));
    const dados = [];
    for (let i = 0; i < quantos; i++) {
      const a = Math.random() * PI * 2;
      const r = Math.sqrt(Math.random());
      dados.push({ a, r, y: Math.random(), fase: Math.random() * PI * 2, v: 0.6 + Math.random() * 0.6 });
      const t = tons[i % tons.length];
      cores.set([t.r, t.g, t.b], i * 3);
    }
    const geo = new T.BufferGeometry();
    geo.setAttribute("position", new T.BufferAttribute(pos, 3));
    geo.setAttribute("color", new T.BufferAttribute(cores, 3));
    // um papelzinho retangular (o ponto sempre de frente: o retângulo dá o jeito de papel)
    const c = document.createElement("canvas");
    c.width = c.height = 16;
    const g = c.getContext("2d");
    g.fillStyle = "#ffffff";
    g.fillRect(4, 1, 8, 14);
    const pontos = new T.Points(geo, new T.PointsMaterial({
      size: 0.16, map: new T.CanvasTexture(c), vertexColors: true, alphaTest: 0.5, toneMapped: false,
    }));
    pontos.frustumCulled = false;
    this.cena.add(pontos);
    this.confete = { pontos, dados };
    this.animarConfete(0, 0);
  }

  animarConfete(dt, t) {
    const { pontos, dados } = this.confete;
    const raio = (this.raio || 8) + (this.folga || 1.5) + 3;
    const pos = pontos.geometry.attributes.position;
    dados.forEach((d, i) => {
      d.y -= (dt * d.v * 0.045);
      if (d.y < 0) d.y += 1;
      const balanco = Math.sin(t * 1.3 + d.fase) * 0.5;
      pos.setXYZ(i, Math.sin(d.a) * d.r * raio + balanco, 0.4 + d.y * 13, Math.cos(d.a) * d.r * raio + Math.cos(t * 1.1 + d.fase) * 0.4);
    });
    pos.needsUpdate = true;
  }

  /** O que é do céu (e não do chão): fica fora da planta do passeio. */
  festaNoCeu() {
    return [this.ceu, this.fachos && this.fachos.malha, this.fogos && this.fogos.pontos, this.confete && this.confete.pontos].filter(Boolean);
  }

  /** O céu a cada quadro: acompanha a câmera; holofotes, fogos e confete andam (sem "menos movimento"). */
  animarCeu(dt, t) {
    this.ceu.position.copy(this.camera.position);
    if (this.reduzido) return;
    this.animarHolofotes(t);
    this.animarFogos(dt);
    this.animarConfete(dt, t);
  }

  /**
   * A FESTA: as bandeirinhas, as lâmpadas, os balões, o portal e as placas
   * no ar vêm com a roda (dependem do tamanho dela): `montarPilares`,
   * `marcarArea` e `montarParque`.
   */
  montarFesta() {
    this.baloes = [];
    this.placasNoAr = [];
  }

  /** Os balões e as placas no ar balançando devagar. */
  animarFesta(dt, t) {
    if (this.reduzido) return;
    this.baloes.forEach((b) => {
      b.position.y = b.userData.y + Math.sin(t * 1.3 + b.userData.fase) * 0.12;
      b.rotation.y = Math.sin(t * 0.6 + b.userData.fase) * 0.25;
    });
    this.placasNoAr.forEach((p) => { p.position.y = p.userData.y + Math.sin(t * 1.1 + p.userData.fase) * 0.18; });
  }

  /**
   * A placa no ar do lado de cá da roda (entre a câmera e o meio) some: ela
   * taparia a roda e o símbolo do chão. As do outro lado ficam, de frente.
   */
  clarearPlacas() {
    const c = this.camera.position;
    const longe = Math.hypot(c.x, c.z);
    this.placasNoAr.forEach((p) => {
      const perto = Math.hypot(p.position.x - c.x, p.position.z - c.z);
      const r = Math.hypot(p.position.x, p.position.z) || 1;
      // o cosseno entre a placa e a câmera, vistos do meio da roda
      const doLado = longe > 1 ? (p.position.x * c.x + p.position.z * c.z) / (r * longe) : -1;
      p.material.opacity = Math.min(limitar((perto - 8) / 6, 0, 1), 1 - limitar((doLado - 0.3) / 0.35, 0, 1));
      p.visible = p.material.opacity > 0.02;
    });
  }

  /** Um cacho de balões coloridos com as fitas, num ponto do chão. */
  balões(x, z, quantos = 4, fase = 0) {
    const T = this.T;
    const cacho = new T.Group();
    cacho.position.set(x, 0, z);
    cacho.userData.y = 0;
    cacho.userData.fase = fase;
    const cores = ["#e63946", "#ffd700", "#2f8bff", "#22c55e", "#ff3df2", "#ff9f1c"];
    const geo = this.geo("balao", () => new T.SphereGeometry(1, 16, 12));
    const fitas = [];
    for (let k = 0; k < quantos; k++) {
      const a = (k / quantos) * PI * 2 + fase;
      const bx = Math.cos(a) * 0.32;
      const bz = Math.sin(a) * 0.32;
      const by = 2.5 + (k % 2) * 0.35;
      const cor = cores[(((k + Math.round(fase * 10)) % cores.length) + cores.length) % cores.length];
      const balao = new T.Mesh(geo, this.mat("balao" + cor, () => {
        const m = new T.MeshStandardMaterial({ color: cor, roughness: 0.25, metalness: 0.1, emissive: cor, emissiveIntensity: 0.25 });
        m.userData.compartilhado = true;
        return m;
      }));
      balao.scale.set(0.32, 0.4, 0.32);
      balao.position.set(bx, by, bz);
      balao.userData.compartilhado = true;
      cacho.add(balao);
      fitas.push(bx, by - 0.4, bz, 0, 0.05, 0);
    }
    const linha = new T.BufferGeometry();
    linha.setAttribute("position", new T.Float32BufferAttribute(fitas, 3));
    cacho.add(new T.LineSegments(linha, this.mat("fita", () => {
      const m = new T.LineBasicMaterial({ color: "#f4f6ff", transparent: true, opacity: 0.7 });
      m.userData.compartilhado = true;
      return m;
    })));
    this.baloes.push(cacho);
    return cacho;
  }

  /**
   * O portal: duas colunas listradas, o arco amarelo com lâmpadas e o
   * letreiro (dos dois lados). `angulo` diz para onde ele olha.
   */
  portal(x, z, angulo, texto, cor, largura = 6.4) {
    const T = this.T;
    const portal = new T.Group();
    portal.position.set(x, 0, z);
    portal.rotation.y = angulo;
    const alto = 5.4;
    const listras = this.mat("listras", () => {
      const c = document.createElement("canvas");
      c.width = 8;
      c.height = 64;
      const g = c.getContext("2d");
      for (let i = 0; i < 8; i++) { g.fillStyle = i % 2 ? "#ffffff" : "#e63946"; g.fillRect(0, i * 8, 8, 8); }
      const t = new T.CanvasTexture(c);
      t.colorSpace = T.SRGBColorSpace;
      t.wrapT = T.RepeatWrapping;
      t.repeat.set(1, 3);
      const m = new T.MeshStandardMaterial({ map: t, roughness: 0.4 });
      m.userData.compartilhado = true;
      return m;
    });
    [-largura / 2, largura / 2].forEach((lado) => {
      const coluna = this.cilindro(portal, 0.22, alto, listras, lado, alto / 2, 0, 20);
      coluna.userData.compartilhado = true;
      const topo = this.esfera(portal, 0.3, this.luz("#ffd700", 2.4), lado, alto + 0.15, 0);
      topo.userData.compartilhado = true;
    });
    const arco = new T.Mesh(new T.TorusGeometry(largura / 2, 0.16, 10, 40, PI), this.luz("#ffd700", 1.6));
    arco.position.y = alto;
    portal.add(arco);
    // as lâmpadas do arco
    const lampadas = new T.InstancedMesh(this.geo("lampada", () => new T.SphereGeometry(0.08, 8, 6)), this.mat("lampada", () => {
      const m = new T.MeshBasicMaterial({ color: "#fff2b0", toneMapped: false });
      m.userData.compartilhado = true;
      return m;
    }), 17);
    const ajuda = new T.Object3D();
    for (let i = 0; i < 17; i++) {
      const a = (i / 16) * PI;
      ajuda.position.set(Math.cos(a) * (largura / 2), alto + Math.sin(a) * (largura / 2) + 0.2, 0.12);
      ajuda.updateMatrix();
      lampadas.setMatrixAt(i, ajuda.matrix);
    }
    portal.add(lampadas);
    // o letreiro, legível dos dois lados
    const material = this.materialDeTexto([texto[0], texto[1]], cor, 1024, 256);
    material.side = T.FrontSide;
    [0, PI].forEach((giro) => {
      const placa = new T.Mesh(this.geo("plano", () => new T.PlaneGeometry(1, 1)), material);
      placa.scale.set(largura * 0.86, largura * 0.215, 1);
      placa.position.set(0, alto - 0.5, giro ? -0.05 : 0.05);
      placa.rotation.y = giro;
      portal.add(placa);
    });
    portal.add(this.balões(-largura / 2 - 0.6, 0.3, 4, 0.3), this.balões(largura / 2 + 0.6, 0.3, 4, 1.7));
    this.baloes.forEach((b) => { if (b.parent === portal) b.userData.y = 0; });
    return portal;
  }

  /** Uma placa no ar (sempre de frente para quem olha) que balança devagar. */
  placaNoAr(linhas, cor, x, y, z, largura = 5.6, zona = "") {
    const T = this.T;
    const material = this.materialDeTexto(linhas, cor, 1024, 256);
    const placa = new T.Sprite(new T.SpriteMaterial({ map: material.map, transparent: true, depthWrite: false, toneMapped: false }));
    material.dispose();
    placa.scale.set(largura, largura / 4, 1);
    placa.position.set(x, y, z);
    placa.userData.y = y;
    placa.userData.fase = x * 0.37 + z * 0.11;
    placa.userData.zona = zona;
    this.placasNoAr.push(placa);
    return placa;
  }

  /** Pilares de luz em volta da roda: a "arquibancada" da arena. */
  montarPilares(raio) {
    const T = this.T;
    if (this.pilares) {
      this.cena.remove(this.pilares);
      this.pilares.traverse((obj) => { if (obj.isInstancedMesh) obj.dispose(); });
    }
    const grupo = new T.Group();
    const n = 28;
    for (let i = 0; i < n; i++) {
      const a = (i / n) * PI * 2;
      const cor = i % 2 ? "#2f8bff" : "#e63946";
      const p = this.caixa(grupo, 0.12, 5.5, 0.12, this.luz(cor, 2.4), Math.cos(a) * raio, 2.75, Math.sin(a) * raio);
      p.userData.fase = i;
    }
    const halo = this.anel(grupo, raio, 0.06, this.luz("#3fd0ff", 2.6), 0, 5.6, 0);
    halo.rotation.x = PI / 2;

    // as bandeirinhas de festa, penduradas de pilar a pilar
    const porVao = 6;
    const bandeiras = new T.InstancedMesh(
      this.geo("bandeirinha", () => {
        const g = new T.BufferGeometry();
        g.setAttribute("position", new T.Float32BufferAttribute([-0.24, 0, 0, 0.24, 0, 0, 0, -0.46, 0], 3));
        g.computeVertexNormals();
        return g;
      }),
      this.mat("bandeiras", () => new T.MeshBasicMaterial({ side: T.DoubleSide, toneMapped: false })),
      n * porVao,
    );
    const cores = ["#e63946", "#ffd700", "#2f8bff", "#22c55e", "#ff3df2", "#ff9f1c"].map((c) => new T.Color(c));
    const ajuda = new T.Object3D();
    const fios = [];
    let k = 0;
    for (let i = 0; i < n; i++) {
      const a0 = (i / n) * PI * 2;
      const a1 = ((i + 1) / n) * PI * 2;
      const p0 = new T.Vector3(Math.cos(a0) * raio, 5.45, Math.sin(a0) * raio);
      const p1 = new T.Vector3(Math.cos(a1) * raio, 5.45, Math.sin(a1) * raio);
      const giro = -Math.atan2(p1.z - p0.z, p1.x - p0.x);
      const ponto = (t) => p0.clone().lerp(p1, t).setY(5.45 - Math.sin(t * PI) * 0.8);
      for (let j = 0; j < 8; j++) {
        const a = ponto(j / 8);
        const b = ponto((j + 1) / 8);
        fios.push(a.x, a.y, a.z, b.x, b.y, b.z);
      }
      for (let j = 0; j < porVao; j++) {
        ajuda.position.copy(ponto((j + 0.5) / porVao));
        ajuda.rotation.set(0, giro, 0);
        ajuda.updateMatrix();
        bandeiras.setMatrixAt(k, ajuda.matrix);
        bandeiras.setColorAt(k, cores[k % cores.length]);
        k++;
      }
    }
    grupo.add(bandeiras);
    const fio = new T.BufferGeometry();
    fio.setAttribute("position", new T.Float32BufferAttribute(fios, 3));
    grupo.add(new T.LineSegments(fio, new T.LineBasicMaterial({ color: "#f4f6ff", transparent: true, opacity: 0.55 })));

    // as lâmpadas de festa no aro de cima
    const quantas = Math.round((raio * PI * 2) / 0.9);
    const lampadas = new T.InstancedMesh(this.geo("lampada", () => new T.SphereGeometry(0.08, 8, 6)), this.mat("lampadaCor", () => new T.MeshBasicMaterial({ toneMapped: false })), quantas);
    const tons = ["#fff2b0", "#ffd166", "#ff9fb2", "#9fe1ff"].map((c) => new T.Color(c));
    for (let i = 0; i < quantas; i++) {
      const a = (i / quantas) * PI * 2;
      ajuda.position.set(Math.cos(a) * raio, 5.72, Math.sin(a) * raio);
      ajuda.rotation.set(0, 0, 0);
      ajuda.updateMatrix();
      lampadas.setMatrixAt(i, ajuda.matrix);
      lampadas.setColorAt(i, tons[i % tons.length]);
    }
    grupo.add(lampadas);
    this.lampadas = lampadas;
    this.tonsDasLampadas = tons;

    this.cena.add(grupo);
    this.pilares = grupo;
    this.piso.scale.setScalar(Math.max(36, raio + 10));
    this.recortarPiso(raio - 1.2);
  }

  /**
   * O piso da roda vai só até a calçada dos pilares: dali para fora é o
   * parque (desenhar o piso embaixo da grama era pintar a tela duas vezes).
   * O desenho dele (os anéis, o nome da casa) fica onde estava.
   */
  recortarPiso(raio) {
    const T = this.T;
    const k = Math.min(1, raio / this.piso.scale.x);
    const g = new T.CircleGeometry(k, 96);
    const uv = g.attributes.uv;
    const pos = g.attributes.position;
    for (let i = 0; i < uv.count; i++) uv.setXY(i, 0.5 + pos.getX(i) / 2, 0.5 + pos.getY(i) / 2);
    this.piso.geometry.dispose();
    this.piso.geometry = g;
  }

  /* ---------- o símbolo no chão e o parque em volta ---------- */

  /**
   * O SÍMBOLO DA LAZER & SPORT PINTADO NO CHÃO, no meio da roda, como o
   * piso de um parque: o alvo vermelho e branco com o dardo azul (o do
   * logo), e o nome numa faixa branca em volta -- "Lazer & Sport" embaixo,
   * de frente para a ENTRADA, e "Brinquedos • Cenografia • Parques" em
   * cima. O alvo de verdade gira em pé no meio dele.
   *
   * É uma malha própria, com um canvas só dela (1024 px; 768 no celular):
   * desenhado no piso inteiro (72 m num canvas), o nome sairia borrado.
   * As letras se leem de fora da roda, sem espelhar: o pé para fora e o
   * topo para o meio (a mesma regra do nome da casa no piso).
   */
  montarSimbolo(raio, folga) {
    const T = this.T;
    // cabe por dentro das placas das áreas, que ficam deitadas no chão
    const R = limitar(raio - folga - 2.2, 2.3, 7);
    const material = this.mat("simbolo", () => {
      const n = this.celular ? 768 : 1024;
      const c = document.createElement("canvas");
      c.width = c.height = n;
      const textura = new T.CanvasTexture(c);
      textura.colorSpace = T.SRGBColorSpace;
      textura.anisotropy = this.renderer.capabilities.getMaxAnisotropy();
      const pintar = () => {
        pintarSimbolo(c.getContext("2d"), n);
        textura.needsUpdate = true;
      };
      pintar();
      // a fonte da marca (Poppins 800) pode chegar depois: aí repinta
      if (document.fonts && document.fonts.load) document.fonts.load("800 64px Poppins").then(pintar, () => {});
      // sem conta de luz: as cores da marca como são (e a tela pintada uma vez só)
      const m = this.noChao(new T.MeshBasicMaterial({ map: textura, color: "#f2f2f7" }));
      m.userData.compartilhado = true;
      return m;
    });
    const simbolo = new T.Mesh(this.geo("discoSimbolo", () => new T.CircleGeometry(1, 96)), material);
    simbolo.scale.setScalar(R);
    // o pé do nome para o lado da entrada (o canvas de baixo vai para +z, girado até ela)
    simbolo.rotation.set(-PI / 2, 0, A_ENTRADA);
    simbolo.position.y = 0.012;
    simbolo.userData.compartilhado = true;
    simbolo.raycast = () => {};
    this.decoracao.add(simbolo);
    this.raioDoSimbolo = R;
  }

  /**
   * O PARQUE EM VOLTA DA RODA, por anéis a partir da cerca de pilares
   * (`beira`): a calçada de pedra (com os pilares, as bandeirinhas e o
   * portal), o gramado com árvores, postes, bancos e canteiros, os caminhos
   * que saem da entrada e de cada área, com o varal de luzes, e a mureta
   * colorida em volta. Os carrinhos de pipoca e de algodão-doce ficam na
   * entrada. A praça na frente de cada reino (o Espaço Esportivo) e a
   * passarela até ele ficam livres.
   *
   * Leve de propósito: cada tipo de coisa é UMA chamada de desenho
   * (instâncias, ou peças juntadas numa geometria com as cores nos
   * vértices); as luzes são material que brilha e um brilho em ponto, sem
   * nenhuma luz de verdade a mais. Nada passa de 3,4 m: a câmera, ao
   * entrar no parque, sobe por cima (`alturaLivre`).
   */
  montarParque(beira) {
    const T = this.T;
    const antes = this.decoracao.children.length;
    const sorte = sorteador(7);
    const calcadaDentro = beira - 1.4;
    const gramaDentro = beira + 2.2;
    const gramaFora = beira + 12;
    this.parque = { dentro: gramaDentro, fora: gramaFora + 0.6, portao: gramaFora + 0.3 };
    // as praças dos reinos (e o caminho até cada uma): nada do parque ali
    const pracas = (this.trechos || []).filter((t) => t.tipo === "reino").flatMap((t) => {
      const meio = (t.x0 + t.x1) / 2;
      return [
        { x0: t.x0 - 3, x1: t.x1 + 3, z0: t.z0 - 3, z1: t.z1 + 8.5 },
        { x0: meio - 5.5, x1: meio + 5.5, z0: t.z1, z1: -(beira - 3) },
      ];
    });
    const livre = (x, z, margem = 0) => !pracas.some((p) => x > p.x0 - margem && x < p.x1 + margem && z > p.z0 - margem && z < p.z1 + margem);
    const noAnel = (a, r) => [Math.sin(a) * r, Math.cos(a) * r];
    const portao = noAnel(A_ENTRADA, gramaFora + 0.3);
    /** Os trechos de um anel, em volta: [[a0, a1, livre], ...] (livre = fora das praças). */
    const trechosDoAnel = (r0, r1) => {
      const passos = 240;
      const ok = [];
      for (let i = 0; i < passos; i++) {
        const a = ((i + 0.5) / passos) * PI * 2;
        ok.push([r0, (r0 + r1) / 2, r1].every((r) => livre(...noAnel(a, r), 0.3)));
      }
      if (ok.every(Boolean) || !ok.some(Boolean)) return [[0, PI * 2, ok[0]]];
      const saida = [];
      const comeco = ok.findIndex((v, i) => v !== ok[(i + passos - 1) % passos]);
      let inicio = comeco;
      for (let k = 1; k <= passos; k++) {
        const i = (comeco + k) % passos;
        if (ok[i] !== ok[(i + passos - 1) % passos] || k === passos) {
          saida.push([(inicio / passos) * PI * 2, ((comeco + k) / passos) * PI * 2, ok[inicio % passos]]);
          inicio = comeco + k;
        }
      }
      return saida;
    };
    /** Um pedaço de anel deitado no chão, com o uv do mundo (as emendas somem). */
    const anelNoChao = (r0, r1, a0, a1, escala) => {
      const g = new T.RingGeometry(r0, r1, Math.max(8, Math.round(((a1 - a0) / (PI * 2)) * 160)), 1, a0 - PI / 2, a1 - a0);
      g.rotateX(-PI / 2);
      return uvDoMundo(g, escala);
    };
    const uvDoMundo = (g, escala) => {
      const pos = g.attributes.position;
      const uv = new Float32Array(pos.count * 2);
      for (let i = 0; i < pos.count; i++) { uv[i * 2] = pos.getX(i) / escala; uv[i * 2 + 1] = pos.getZ(i) / escala; }
      g.setAttribute("uv", new T.BufferAttribute(uv, 2));
      return g.index ? g.toNonIndexed() : g;
    };

    // os caminhos: o da entrada e um na direção de cada área da roda
    const caminhos = [A_ENTRADA];
    (this.trechos || []).filter((t) => t.tipo !== "reino").forEach((t) => {
      const meio = (t.a0 + t.a1) / 2;
      const longe = (a) => Math.abs(Math.atan2(Math.sin(meio - a), Math.cos(meio - a))) > 0.42;
      if (caminhos.every(longe) && livre(...noAnel(meio, gramaFora), 1)) caminhos.push(meio);
    });
    const LARGURA = 2.4;
    const noCaminho = (x, z, folgaExtra) => caminhos.some((a) => {
      const ao = x * Math.sin(a) + z * Math.cos(a); // ao longo do caminho
      const lado = x * Math.cos(a) - z * Math.sin(a);
      return ao > gramaDentro - 1 && Math.abs(lado) < LARGURA / 2 + folgaExtra;
    });

    // --- a calçada (o anel dos pilares) e os caminhos: pedra, uma geometria só
    const pedras = [anelNoChao(calcadaDentro, gramaDentro + 0.05, 0, PI * 2, 1.6)];
    caminhos.forEach((a) => {
      const comprimento = gramaFora - gramaDentro + 1.2;
      const g = new T.PlaneGeometry(LARGURA, comprimento);
      g.rotateX(-PI / 2);
      g.rotateY(a);
      const meio = gramaDentro + comprimento / 2 - 0.6;
      g.translate(Math.sin(a) * meio, 0.003, Math.cos(a) * meio);
      pedras.push(uvDoMundo(g, 1.6));
    });

    // --- o gramado, fora das praças dos reinos (três faixas, para a borda seguir a
    // praça), e a praça calçada na frente de cada reino
    const faixas = [gramaDentro, gramaDentro + (gramaFora - gramaDentro) / 3, gramaDentro + (2 * (gramaFora - gramaDentro)) / 3, gramaFora];
    const gramas = [];
    for (let k = 0; k < 3; k++) {
      trechosDoAnel(faixas[k], faixas[k + 1]).forEach(([a0, a1, ehGrama]) => {
        (ehGrama ? gramas : pedras).push(anelNoChao(faixas[k], faixas[k + 1], a0, a1, ehGrama ? 2.4 : 1.6));
      });
    }
    if (gramas.length) {
      const grama = new T.Mesh(juntarPecas(T, gramas, true), this.mat("grama", () => this.materialDoParque("grama")));
      grama.position.y = 0.003;
      this.decoracao.add(grama);
    }
    const calcada = new T.Mesh(juntarPecas(T, pedras, true), this.mat("calcada", () => this.materialDoParque("pedra")));
    calcada.position.y = 0.006;
    this.decoracao.add(calcada);
    // e o chão de fora do parque, escurecendo até a cor do horizonte (sem
    // borda nenhuma: o chão de longe vira o céu de baixo)
    const chaoDeFora = new T.RingGeometry(gramaFora - 0.1, 170, 96, 4);
    chaoDeFora.rotateX(-PI / 2);
    const tonsDoChao = [[0, "#0e1838"], [0.25, "#16153f"], [0.55, "#26174f"], [1, HORIZONTE]].map(([k, c]) => [k, new T.Color(c)]);
    const posChao = chaoDeFora.attributes.position;
    const coresDoChao = new Float32Array(posChao.count * 3);
    const tom = new T.Color();
    for (let i = 0; i < posChao.count; i++) {
      const k = (Math.hypot(posChao.getX(i), posChao.getZ(i)) - gramaFora) / (170 - gramaFora);
      const j = Math.max(1, tonsDoChao.findIndex(([limite]) => limite >= k));
      const [k0, c0] = tonsDoChao[j - 1];
      const [k1, c1] = tonsDoChao[j];
      tom.copy(c0).lerp(c1, limitar((k - k0) / (k1 - k0 || 1), 0, 1));
      coresDoChao.set([tom.r, tom.g, tom.b], i * 3);
    }
    chaoDeFora.setAttribute("color", new T.BufferAttribute(coresDoChao, 3));
    const terreno = new T.Mesh(chaoDeFora, this.mat("terreno", () => this.materialDoParque("terreno")));
    terreno.position.y = -0.002;
    this.decoracao.add(terreno);
    // e as luzinhas da cidade lá longe, no chão da noite (pontos de 1 a 2 px)
    const luzesLonge = [];
    const coresLonge = [];
    const tonsLonge = ["#ffd98a", "#ff8fd8", "#8fdcff", "#fff2c4"].map((c) => new T.Color(c));
    for (let i = 0; i < (this.celular ? 160 : 300); i++) {
      const a = sorte() * PI * 2;
      const r = 75 + sorte() * 90;
      const [x, z] = noAnel(a, r);
      if (!livre(x, z, 4)) continue;
      luzesLonge.push(x, 0.3, z);
      const c = tonsLonge[i % tonsLonge.length];
      const k = 0.5 + sorte() * 0.5;
      coresLonge.push(c.r * k, c.g * k, c.b * k);
    }
    const geoLonge = new T.BufferGeometry();
    geoLonge.setAttribute("position", new T.Float32BufferAttribute(luzesLonge, 3));
    geoLonge.setAttribute("color", new T.Float32BufferAttribute(coresLonge, 3));
    this.decoracao.add(new T.Points(geoLonge, this.mat("luzesLonge", () => {
      const m = new T.PointsMaterial({
        size: 3.4, sizeAttenuation: false, vertexColors: true, map: this.texturaDeBrilho(), transparent: true,
        depthWrite: false, blending: T.AdditiveBlending, fog: false, toneMapped: false,
      });
      m.userData.compartilhado = true;
      return m;
    })));

    // --- o que fica em pé no gramado: lugares sorteados, longe dos caminhos e das praças
    const lugares = [];
    // os carrinhos da entrada (mais abaixo) já têm o lugar deles
    const rCarrinho = gramaDentro + 2.6;
    const lugarDoCarrinho = (lado) => [
      Math.sin(A_ENTRADA) * rCarrinho + Math.cos(A_ENTRADA) * lado * (LARGURA / 2 + 1.5),
      Math.cos(A_ENTRADA) * rCarrinho - Math.sin(A_ENTRADA) * lado * (LARGURA / 2 + 1.5),
    ];
    [-1, 1].forEach((lado) => lugares.push([...lugarDoCarrinho(lado), 1.2]));
    const cabe = (x, z, raioDaCoisa) => livre(x, z, raioDaCoisa + 0.5) && !noCaminho(x, z, raioDaCoisa + 0.5)
      && lugares.every((p) => Math.hypot(p[0] - x, p[1] - z) > p[2] + raioDaCoisa + 0.4);
    const sortearLugar = (r0, r1, raioDaCoisa) => {
      for (let tentativa = 0; tentativa < 40; tentativa++) {
        const a = sorte() * PI * 2;
        const r = r0 + sorte() * (r1 - r0);
        const [x, z] = noAnel(a, r);
        if (cabe(x, z, raioDaCoisa)) {
          lugares.push([x, z, raioDaCoisa]);
          return [x, z];
        }
      }
      return null;
    };

    // os postes, dos dois lados de cada caminho, com o varal de luzes entre eles
    const postes = [];
    caminhos.forEach((a) => {
      [-1, 1].forEach((lado) => {
        const fila = [];
        for (let r = gramaDentro + 1.6; r < gramaFora - 0.5; r += 3.4) {
          const x = Math.sin(a) * r + Math.cos(a) * lado * (LARGURA / 2 + 0.45);
          const z = Math.cos(a) * r - Math.sin(a) * lado * (LARGURA / 2 + 0.45);
          if (!livre(x, z, 0.6)) continue;
          fila.push([x, z]);
          lugares.push([x, z, 0.3]);
        }
        postes.push(fila);
      });
    });
    const ALTURA_DO_POSTE = 3.1;
    const todosOsPostes = postes.flat();
    const ajuda = new T.Object3D();
    const instancias = (geometria, material, lista, colocar) => {
      if (!lista.length) return null;
      const malha = new T.InstancedMesh(geometria, material, lista.length);
      lista.forEach((item, i) => {
        ajuda.position.set(0, 0, 0);
        ajuda.rotation.set(0, 0, 0);
        ajuda.scale.set(1, 1, 1);
        colocar(item, i);
        ajuda.updateMatrix();
        malha.setMatrixAt(i, ajuda.matrix);
      });
      this.decoracao.add(malha);
      return malha;
    };
    instancias(this.geo("poste", () => juntarPecas(T, [
      pecaColorida(T, new T.CylinderGeometry(0.13, 0.16, 0.28, 10), "#1f2742", 0, 0.14, 0),
      pecaColorida(T, new T.CylinderGeometry(0.045, 0.06, ALTURA_DO_POSTE - 0.3, 8), "#2a3352", 0, ALTURA_DO_POSTE / 2, 0),
      pecaColorida(T, new T.CylinderGeometry(0.17, 0.11, 0.1, 10), "#ffd700", 0, ALTURA_DO_POSTE - 0.12, 0),
      pecaColorida(T, new T.ConeGeometry(0.2, 0.16, 10), "#ffd700", 0, ALTURA_DO_POSTE + 0.36, 0),
    ])), this.mat("parquePecas", () => this.materialDoParque("pecas")), todosOsPostes, ([x, z]) => ajuda.position.set(x, 0, z));
    instancias(this.geo("globoDoPoste", () => new T.SphereGeometry(0.19, 14, 10)), this.mat("globo", () => {
      const m = new T.MeshBasicMaterial({ color: "#fff1c4", toneMapped: false });
      m.userData.compartilhado = true;
      return m;
    }), todosOsPostes, ([x, z]) => ajuda.position.set(x, ALTURA_DO_POSTE + 0.1, z));

    // o varal de luzes: de poste em poste, com a barriguinha do fio
    const fios = [];
    const lampadas = [];
    postes.forEach((fila) => {
      for (let i = 0; i + 1 < fila.length; i++) {
        const [x0, z0] = fila[i];
        const [x1, z1] = fila[i + 1];
        const ponto = (t) => [x0 + (x1 - x0) * t, ALTURA_DO_POSTE - 0.15 - Math.sin(t * PI) * 0.55, z0 + (z1 - z0) * t];
        for (let j = 0; j < 6; j++) fios.push(...ponto(j / 6), ...ponto((j + 1) / 6));
        for (let j = 1; j < 6; j++) lampadas.push(ponto(j / 6));
      }
    });
    if (fios.length) {
      const geo = new T.BufferGeometry();
      geo.setAttribute("position", new T.Float32BufferAttribute(fios, 3));
      this.decoracao.add(new T.LineSegments(geo, new T.LineBasicMaterial({ color: "#f4f6ff", transparent: true, opacity: 0.45 })));
    }

    // a mureta colorida em volta do parque (pedaços de 1 m, nas cores da marca), com a entrada aberta
    const pedacos = [];
    const rMureta = gramaFora + 0.3;
    const passosMureta = Math.round((rMureta * PI * 2) / 1.05);
    for (let i = 0; i < passosMureta; i++) {
      const a = ((i + 0.5) / passosMureta) * PI * 2;
      const [x, z] = noAnel(a, rMureta);
      if (!livre(x, z, 0.8) || noCaminho(x, z, 0.4) || Math.hypot(x - portao[0], z - portao[1]) < 4.3) continue;
      pedacos.push([x, z, a, i]);
    }
    const corDaMureta = ["#e63946", "#ffffff", "#ffd700", "#2f8bff"].map((c) => new T.Color(c));
    const mureta = instancias(this.geo("mureta", () => new T.BoxGeometry(0.96, 0.5, 0.26)), this.mat("muretaMaterial", () => {
      const m = new T.MeshStandardMaterial({ roughness: 0.55, emissive: "#ffffff", emissiveIntensity: 0.12 });
      m.userData.compartilhado = true;
      return m;
    }), pedacos, ([x, z, a]) => { ajuda.position.set(x, 0.25, z); ajuda.rotation.y = a + PI / 2; });
    if (mureta) pedacos.forEach((p, i) => mureta.setColorAt(i, corDaMureta[p[3] % corDaMureta.length]));
    // uma bolinha de luz em cima da mureta, de tanto em tanto
    pedacos.forEach(([x, z], i) => { if (i % 4 === 0) lampadas.push([x, 0.58, z]); });

    // as lâmpadas do varal e da mureta, nas cores da festa
    const tons = ["#fff2b0", "#ffd166", "#ff9fb2", "#9fe1ff", "#c7ffb0"].map((c) => new T.Color(c));
    const materialDaLuz = this.mat("luzDoParque", () => {
      const m = new T.MeshBasicMaterial({ toneMapped: false });
      m.userData.compartilhado = true;
      return m;
    });
    const bolinhas = instancias(this.geo("lampada", () => new T.SphereGeometry(0.08, 8, 6)), materialDaLuz, lampadas, ([x, y, z]) => ajuda.position.set(x, y, z));
    if (bolinhas) lampadas.forEach((_, i) => bolinhas.setColorAt(i, tons[i % tons.length]));

    // as árvores: redondas e pinheirinhos, baixas (a copa até 2,9 m)
    const arvores = { redonda: [], pinheiro: [] };
    const quantas = this.celular ? 26 : 46;
    for (let i = 0; i < quantas; i++) {
      const lugar = sortearLugar(gramaDentro + 1.4, gramaFora - 1.2, 1.0);
      if (lugar) arvores[i % 3 ? "redonda" : "pinheiro"].push([...lugar, sorte()]);
    }
    // e o bosque lá fora, depois da mureta: árvores grandes que somem na
    // neblina e enchem o chão até o horizonte (sem elas, ele ficava vazio)
    const bosque = { redonda: [], pinheiro: [] };
    const rBosque0 = gramaFora + 6;
    const rBosque1 = gramaFora + 46;
    this.parque.bosque = rBosque1;
    for (let i = 0; i < 130; i++) {
      const a = sorte() * PI * 2;
      const r = rBosque0 + Math.pow(sorte(), 0.8) * (rBosque1 - rBosque0);
      const [x, z] = noAnel(a, r);
      // a praça do reino e a vista do portão ficam livres
      if (!livre(x, z, 6) || Math.abs(Math.atan2(Math.sin(a - A_ENTRADA), Math.cos(a - A_ENTRADA))) < 0.22) continue;
      bosque[i % 3 ? "redonda" : "pinheiro"].push([x, z, sorte()]);
    }
    const grandeDoBosque = ([x, z, s]) => {
      ajuda.position.set(x, 0, z);
      ajuda.rotation.y = s * PI * 2;
      ajuda.scale.setScalar(1.9 + s * 1.3);
    };

    const materialDasPecas = this.mat("parquePecas", () => this.materialDoParque("pecas"));
    const tamanhoDaArvore = ([x, z, s]) => {
      ajuda.position.set(x, 0, z);
      ajuda.rotation.y = s * PI * 2;
      ajuda.scale.setScalar(0.85 + s * 0.35);
    };
    instancias(this.geo("arvoreRedonda", () => juntarPecas(T, [
      pecaColorida(T, new T.CylinderGeometry(0.09, 0.13, 1.1, 7), "#6b4a2f", 0, 0.55, 0),
      pecaColorida(T, new T.IcosahedronGeometry(0.85, 0), "#22a35a", 0, 1.7, 0),
      pecaColorida(T, new T.IcosahedronGeometry(0.55, 0), "#35c46c", 0.32, 2.1, 0.12),
      pecaColorida(T, new T.IcosahedronGeometry(0.45, 0), "#1c8c4c", -0.38, 1.95, -0.1),
    ])), materialDasPecas, [...arvores.redonda, ...bosque.redonda.map((b) => [...b, true])], (item) => (item[3] ? grandeDoBosque(item) : tamanhoDaArvore(item)));
    instancias(this.geo("pinheiro", () => juntarPecas(T, [
      pecaColorida(T, new T.CylinderGeometry(0.07, 0.1, 0.7, 7), "#6b4a2f", 0, 0.35, 0),
      pecaColorida(T, new T.ConeGeometry(0.8, 1.3, 7), "#1b7f4f", 0, 1.2, 0),
      pecaColorida(T, new T.ConeGeometry(0.6, 1.05, 7), "#22985c", 0, 1.85, 0),
      pecaColorida(T, new T.ConeGeometry(0.4, 0.85, 7), "#2bb26b", 0, 2.42, 0),
    ])), materialDasPecas, [...arvores.pinheiro, ...bosque.pinheiro.map((b) => [...b, true])], (item) => (item[3] ? grandeDoBosque(item) : tamanhoDaArvore(item)));

    // os bancos, na beira dos caminhos, de frente para eles
    const bancos = [];
    // (no caminho da entrada ficam os carrinhos)
    caminhos.slice(1).forEach((a) => {
      [-1, 1].forEach((lado) => {
        const r = gramaDentro + 3.3 + (lado > 0 ? 3.4 : 0);
        const x = Math.sin(a) * r + Math.cos(a) * lado * (LARGURA / 2 + 0.75);
        const z = Math.cos(a) * r - Math.sin(a) * lado * (LARGURA / 2 + 0.75);
        if (livre(x, z, 0.8)) bancos.push([x, z, a + (lado > 0 ? -PI / 2 : PI / 2)]);
      });
    });
    instancias(this.geo("banco", () => juntarPecas(T, [
      pecaColorida(T, new T.BoxGeometry(1.4, 0.06, 0.42), "#c9783a", 0, 0.46, 0),
      pecaColorida(T, new T.BoxGeometry(1.4, 0.3, 0.05), "#c9783a", 0, 0.74, -0.2),
      pecaColorida(T, new T.BoxGeometry(0.07, 0.46, 0.4), "#2a3352", -0.6, 0.23, 0),
      pecaColorida(T, new T.BoxGeometry(0.07, 0.46, 0.4), "#2a3352", 0.6, 0.23, 0),
    ])), materialDasPecas, bancos, ([x, z, giro]) => { ajuda.position.set(x, 0, z); ajuda.rotation.y = giro; });

    // os canteiros: a terra com a beirada e as flores (pontinhos de cor que brilham de leve)
    const canteiros = [];
    for (let i = 0; i < (this.celular ? 6 : 10); i++) {
      const lugar = sortearLugar(gramaDentro + 1, gramaFora - 1, 0.9);
      if (lugar) canteiros.push(lugar);
    }
    if (canteiros.length) {
      const pecas = [];
      canteiros.forEach(([x, z]) => {
        const beira = new T.CylinderGeometry(0.9, 0.95, 0.14, 18);
        pecas.push(pecaColorida(T, beira, "#e9e2cf", x, 0.07, z));
        pecas.push(pecaColorida(T, new T.CylinderGeometry(0.8, 0.8, 0.15, 18), "#3a2618", x, 0.08, z));
      });
      this.decoracao.add(new T.Mesh(juntarPecas(T, pecas), materialDasPecas));
      const flores = [];
      canteiros.forEach(([x, z]) => {
        for (let k = 0; k < 14; k++) {
          const a = sorte() * PI * 2;
          const r = Math.sqrt(sorte()) * 0.7;
          flores.push([x + Math.cos(a) * r, 0.2 + sorte() * 0.12, z + Math.sin(a) * r]);
        }
      });
      const coresDasFlores = ["#ff3df2", "#ffd700", "#e63946", "#ffffff", "#3fd0ff", "#ff9f1c"].map((c) => new T.Color(c));
      const malha = instancias(this.geo("flor", () => new T.IcosahedronGeometry(0.075, 0)), materialDaLuz, flores, ([x, y, z]) => ajuda.position.set(x, y, z));
      if (malha) flores.forEach((_, i) => malha.setColorAt(i, coresDasFlores[i % coresDasFlores.length]));
    }

    // os carrinhos de pipoca e de algodão-doce, na entrada, de frente para o caminho
    const carrinhos = [];
    [[-1, "pipoca"], [1, "algodao"]].forEach(([lado, tipo]) => {
      const a = A_ENTRADA;
      const [x, z] = lugarDoCarrinho(lado);
      if (!livre(x, z, 1)) return;
      const g = montarCarrinho(T, tipo);
      g.rotateY(a + (lado > 0 ? -PI / 2 : PI / 2));
      g.translate(x, 0, z);
      carrinhos.push(g);
      // a lampadinha do toldo e o letreiro
      const placa = new T.Mesh(this.geo("plano", () => new T.PlaneGeometry(1, 1)), this.materialDeTexto([tipo === "pipoca" ? "Pipoca" : "Algodão-doce"], tipo === "pipoca" ? "#ffd700" : "#ff3df2", 640, 128));
      placa.scale.set(1.5, 0.3, 1);
      placa.position.set(x, 2.55, z);
      placa.rotation.y = a + (lado > 0 ? -PI / 2 : PI / 2);
      this.decoracao.add(placa);
      // e um cacho de balões ao lado do de algodão-doce
      if (tipo === "algodao") this.decoracao.add(this.balões(x + Math.cos(a) * 0.9, z - Math.sin(a) * 0.9, 6, 0.8));
    });
    if (carrinhos.length) this.decoracao.add(new T.Mesh(juntarPecas(T, carrinhos), materialDasPecas));

    // os brilhos de todas as luzes do parque: um ponto de luz em cada globo (sem luz de verdade)
    const brilhos = todosOsPostes.map(([x, z]) => [x, ALTURA_DO_POSTE + 0.1, z]);
    if (brilhos.length) {
      const geo = new T.BufferGeometry();
      geo.setAttribute("position", new T.Float32BufferAttribute(brilhos.flat(), 3));
      const pontos = new T.Points(geo, this.mat("brilhoDoPoste", () => {
        const m = new T.PointsMaterial({
          size: 2.4, map: this.texturaDeBrilho(), color: "#ffc978", transparent: true, depthWrite: false,
          blending: T.AdditiveBlending, fog: false, toneMapped: false,
        });
        m.userData.compartilhado = true;
        return m;
      }));
      this.decoracao.add(pontos);
    }
    // o parque não se toca: o toque e o mouse (as placas das áreas) passam direto por ele
    this.decoracao.children.slice(antes).forEach((o) => o.traverse((x) => { x.raycast = () => {}; }));
  }

  /** Os materiais do parque (pedra, grama, as peças com cor nos vértices), feitos uma vez. */
  materialDoParque(tipo) {
    const T = this.T;
    let m;
    if (tipo === "pecas") {
      // Lambert com as faces chapadas: o jeito low-poly, e a conta de luz mais barata
      m = new T.MeshLambertMaterial({ vertexColors: true, flatShading: true, emissive: "#1d1640" });
    } else if (tipo === "terreno") {
      // o chão de fora do parque: liso, some na neblina do horizonte
      m = new T.MeshBasicMaterial({ vertexColors: true });
      m.polygonOffset = true;
      m.polygonOffsetFactor = 1;
      m.polygonOffsetUnits = 2;
    } else {
      const c = document.createElement("canvas");
      c.width = c.height = 128;
      const g = c.getContext("2d");
      if (tipo === "pedra") {
        // as pedras da calçada: blocos claros e quentes, com o rejunte escuro
        g.fillStyle = "#5b4d6e";
        g.fillRect(0, 0, 128, 128);
        const tons = ["#c9b8d6", "#bba8c9", "#d6c6df", "#b39fc4"];
        for (let y = 0; y < 4; y++) {
          for (let x = 0; x < 4; x++) {
            g.fillStyle = tons[(x * 3 + y * 5) % tons.length];
            const desloca = (y % 2) * 16;
            g.fillRect(((x * 32 + desloca) % 128) + 2, y * 32 + 2, 28, 28);
            if (x * 32 + desloca + 30 > 128) g.fillRect(-2, y * 32 + 2, (x * 32 + desloca + 30) % 128, 28);
          }
        }
      } else {
        // a grama: verde com tufinhos mais claros e mais escuros
        g.fillStyle = "#1f7a43";
        g.fillRect(0, 0, 128, 128);
        const sorte = sorteador(3);
        for (let i = 0; i < 420; i++) {
          g.fillStyle = sorte() < 0.5 ? "rgba(86, 196, 112, .45)" : "rgba(12, 70, 38, .5)";
          g.fillRect(sorte() * 128, sorte() * 128, 2, 2 + sorte() * 3);
        }
      }
      const textura = new T.CanvasTexture(c);
      textura.colorSpace = T.SRGBColorSpace;
      textura.wrapS = textura.wrapT = T.RepeatWrapping;
      textura.anisotropy = Math.min(4, this.renderer.capabilities.getMaxAnisotropy());
      // o chão grande do parque sem conta de luz (é muita tela): a cor da noite já vem no tom
      m = new T.MeshBasicMaterial({ map: textura, color: tipo === "pedra" ? "#a99cc4" : "#8fb59c" });
      m.polygonOffset = true;
      m.polygonOffsetFactor = tipo === "pedra" ? -2 : -1;
      m.polygonOffsetUnits = tipo === "pedra" ? -4 : -2;
    }
    m.userData.compartilhado = true;
    return m;
  }

  /* ---------- a roda ---------- */
  filtradas() {
    const ordem = (id) => {
      const i = this.zonas.findIndex((z) => z.id === id);
      return i < 0 ? 99 : i;
    };
    return this.maquinas
      .filter((m) => !this.categoria || (m.dados.categorias || []).includes(this.categoria))
      .sort((a, b) => ordem(a.dados.grupo) - ordem(b.dados.grupo) || a.indice - b.indice);
  }

  limparDecoracao() {
    this.decoracao.children.slice().forEach((filho) => {
      this.decoracao.remove(filho);
      filho.traverse((obj) => {
        if (obj.isInstancedMesh) obj.dispose();
        // o que é compartilhado (balão, lâmpada, listras) fica para a próxima
        if (obj.userData.compartilhado || (obj.material && obj.material.userData.compartilhado)) return;
        if (obj.material && obj.material.map) obj.material.map.dispose();
        if (obj.material) obj.material.dispose();
        if (obj.geometry && ![...this.geometrias.values()].includes(obj.geometry)) obj.geometry.dispose();
      });
    });
    this.baloes = [];
    this.placasNoAr = [];
  }

  montar({ entrada = false } = {}) {
    // A roda tem TODAS as máquinas (só a categoria tira alguma): a visão é
    // ampla, e as áreas são lugares da roda aonde a câmera vai.
    this.lista = this.filtradas();
    // `this.roda` são todas as que estão à vista (a roda e os reinos)
    this.roda = this.lista;
    const roda = this.lista.filter((m) => !m.reino);
    const reinos = this.lista.filter((m) => m.reino);
    this.maquinas.forEach((m) => { m.grupo.visible = false; });
    this.limparDecoracao();

    // o raio da roda sai da soma das vagas: estande largo pede roda maior;
    // entre uma área e outra, um corredor
    const vagas = roda.map((m) => Math.max(m.largura, m.fundo, 1.2) + 2.2);
    const corredor = 2.6;
    const trocas = roda.map((m, i) => (i > 0 && m.dados.grupo !== roda[i - 1].dados.grupo ? corredor : 0));
    const fecha = roda.length > 1 && roda[0].dados.grupo !== roda[roda.length - 1].dados.grupo ? corredor : 0;
    const circunferencia = vagas.reduce((a, b) => a + b, 0) + trocas.reduce((a, b) => a + b, 0) + fecha || 1;
    const raio = Math.max(6.5, circunferencia / (PI * 2));
    this.raio = raio;

    const trechos = [];
    let andado = fecha / 2;
    roda.forEach((m, i) => {
      andado += trocas[i];
      const a0 = (andado / circunferencia) * PI * 2;
      const a = ((andado + vagas[i] / 2) / circunferencia) * PI * 2;
      andado += vagas[i];
      const a1 = (andado / circunferencia) * PI * 2;
      m.grupo.position.set(Math.sin(a) * raio, 0, Math.cos(a) * raio);
      m.grupo.rotation.y = a + PI; // de frente para o centro
      m.grupo.visible = true;
      const ultimo = trechos[trechos.length - 1];
      if (ultimo && ultimo.id === m.dados.grupo) ultimo.a1 = a1;
      else trechos.push({ id: m.dados.grupo, a0, a1 });
    });

    const folga = roda.length ? Math.max(...roda.map((m) => m.raioP)) : 1;
    this.folga = folga;
    this.trechos = trechos;
    this.fundosDasAreas = {};
    trechos.forEach((trecho) => this.marcarArea(trecho, raio, folga));
    this.montarPilares(raio + folga + 4.5);
    this.montarReinos(reinos, raio + folga + 4.5);
    // o símbolo da marca pintado no meio da roda, e o parque em volta; o
    // portal de entrada é o portão do parque, do lado de onde a câmera chega
    // (atrás dela, na vista de sempre: emoldura a chegada sem tapar a roda)
    this.montarSimbolo(raio, folga);
    this.montarParque(raio + folga + 4.5);
    const rPortal = this.parque.portao;
    this.decoracao.add(this.portal(Math.sin(A_ENTRADA) * rPortal, Math.cos(A_ENTRADA) * rPortal, A_ENTRADA, ["Bem-vindo à", "Arena Lazer & Sport"], "#ffd700", 6.8));
    this.caixasSujas = true;
    this.cena.fog.near = raio * 2.2;
    this.cena.fog.far = Math.max(raio * 5 + 30, this.longeDosReinos || 0);
    if (this.selecionada && !this.roda.includes(this.selecionada)) this.soltarSelecao({ voar: false });
    const zona = this.trechos.find((t) => t.id === this.zona);
    this.realcarArea(zona ? this.zona : "");
    if (zona && !entrada) this.camera3d.olharZona(zona);
    else this.camera3d.visaoGeral(entrada);
    this.roda.forEach((m) => m.pedir());
    this.marcarLista();
  }

  /** O objeto 3D não chegou: a máquina sai da roda, que se fecha sem o buraco. */
  tirarDaRoda(m) {
    if (!this.maquinas.includes(m)) return;
    if (this.selecionada === m) this.soltarSelecao({ voar: false });
    this.maquinas = this.maquinas.filter((x) => x !== m);
    this.cena.remove(m.grupo);
    this.montar();
    this.atualizarContagem();
    this.mostrarProgresso();
  }

  /**
   * Os reinos: os espaços grandes demais para a roda (um parque de
   * trampolins com quadras, 39 m x 23 m) ficam atrás dela, lado a lado,
   * de frente para a roda, sobre o chão escuro, cada um ligado à roda por
   * uma passarela de luz e com a placa da área na entrada. A área deles
   * vira um "trecho" do tipo reino: o botão e a placa levam a câmera lá.
   */
  montarReinos(reinos, beira) {
    const T = this.T;
    this.longeDosReinos = 0;
    if (!reinos.length) return;
    const vao = 8;
    const larguras = reinos.map((m) => m.largura + 2);
    const total = larguras.reduce((a, b) => a + b, 0) + vao * (reinos.length - 1);
    const fundoMaior = Math.max(...reinos.map((m) => m.fundo));
    const zFrente = -(beira + 10);
    let x = -total / 2;
    const porArea = {};
    reinos.forEach((m, i) => {
      const cx = x + larguras[i] / 2;
      x += larguras[i] + vao;
      const cz = zFrente - m.fundo / 2 - 0.6;
      m.grupo.position.set(cx, 0, cz);
      m.grupo.rotation.y = 0; // de frente para a roda
      m.grupo.visible = true;
      const id = m.dados.grupo;
      const area = porArea[id] || (porArea[id] = { id, tipo: "reino", x0: Infinity, x1: -Infinity, z0: Infinity, z1: -Infinity });
      area.x0 = Math.min(area.x0, cx - m.largura / 2);
      area.x1 = Math.max(area.x1, cx + m.largura / 2);
      area.z0 = Math.min(area.z0, cz - m.fundo / 2);
      area.z1 = Math.max(area.z1, cz + m.fundo / 2);
      // a passarela de luz, da beira da roda até a entrada do reino
      const cor = COR_DA_ZONA[id] || "#ff9f1c";
      const fim = new T.Vector3(cx, 0, zFrente + 1);
      const inicio = fim.clone().setLength(beira - 1.5);
      const caminho = new T.Vector3().subVectors(fim, inicio);
      const suporte = new T.Group();
      suporte.position.copy(inicio).add(fim).multiplyScalar(0.5);
      suporte.position.y = 0.012;
      suporte.rotation.y = Math.atan2(caminho.x, caminho.z);
      const passarela = new T.Mesh(
        new T.PlaneGeometry(3.2, caminho.length()),
        this.noChao(new T.MeshBasicMaterial({ color: cor, transparent: true, opacity: 0.18, depthWrite: false, toneMapped: false })),
      );
      passarela.rotation.x = -PI / 2;
      passarela.userData.zona = id;
      passarela.userData.piso = true;
      suporte.add(passarela);
      [-1.7, 1.7].forEach((lado) => {
        const filete = new T.Mesh(this.geo("plano", () => new T.PlaneGeometry(1, 1)), this.noChao(new T.MeshBasicMaterial({ color: cor, toneMapped: false })));
        filete.scale.set(0.08, caminho.length(), 1);
        filete.rotation.x = -PI / 2;
        filete.position.set(lado, 0.004, 0);
        suporte.add(filete);
      });
      this.decoracao.add(suporte);
    });
    // o chão escuro sob os reinos e a placa da área na entrada
    Object.values(porArea).forEach((area) => {
      const cor = COR_DA_ZONA[area.id] || "#ff9f1c";
      const chao = new T.Mesh(
        new T.PlaneGeometry(area.x1 - area.x0 + 10, area.z1 - area.z0 + 10),
        // embaixo do piso da roda (onde os dois se cruzam, a roda vence)
        new T.MeshStandardMaterial({ color: "#081430", roughness: 0.9, polygonOffset: true, polygonOffsetFactor: 4, polygonOffsetUnits: 8 }),
      );
      chao.rotation.x = -PI / 2;
      chao.position.set((area.x0 + area.x1) / 2, -0.04, (area.z0 + area.z1) / 2);
      chao.userData.zona = area.id;
      chao.userData.piso = true;
      this.decoracao.add(chao);
      const zona = this.zonas.find((z) => z.id === area.id);
      if (zona) {
        const placa = new T.Mesh(this.geo("plano", () => new T.PlaneGeometry(1, 1)), this.materialDeTexto([zona.kicker || "", zona.titulo], cor));
        placa.scale.set(7, 1.75, 1);
        placa.position.set((area.x0 + area.x1) / 2, 0.5, area.z1 + 3.2);
        placa.rotation.x = -1.05;
        placa.userData.zona = area.id;
        this.decoracao.add(placa);
        this.decoracao.add(this.portal((area.x0 + area.x1) / 2, area.z1 + 5.8, 0, [zona.kicker || "", zona.titulo], cor, 8));
      }
      this.trechos.push(area);
      this.longeDosReinos = Math.max(this.longeDosReinos, -area.z0 + 120);
    });
  }

  /** O trecho de uma área no piso da roda, na cor dela, com a placa. */
  marcarArea(trecho, raio, folga) {
    const T = this.T;
    const cor = COR_DA_ZONA[trecho.id] || "#2f8bff";
    const arco = (dentro, fora, opacidade) => {
      const malha = new T.Mesh(
        new T.RingGeometry(dentro, fora, 72, 1, trecho.a0 - PI / 2, trecho.a1 - trecho.a0),
        this.noChao(new T.MeshBasicMaterial({ color: cor, transparent: true, opacity: opacidade, depthWrite: false, toneMapped: false })),
      );
      malha.rotation.x = -PI / 2;
      malha.position.y = 0.015;
      malha.userData.zona = trecho.id;
      malha.userData.piso = true;
      this.decoracao.add(malha);
      return malha;
    };
    this.fundosDasAreas[trecho.id] = arco(raio - folga - 0.9, raio + folga + 0.6, 0.14);
    arco(raio - folga - 0.9, raio - folga - 0.8, 0.9);
    arco(raio + folga + 0.5, raio + folga + 0.6, 0.9);

    const zona = this.zonas.find((z) => z.id === trecho.id);
    if (!zona) return;
    const meio = (trecho.a0 + trecho.a1) / 2;
    // perto dos estandes: o meio da roda fica para o símbolo da marca no chão
    const r = raio - folga - 1.6;
    const suporte = new T.Group();
    suporte.position.set(Math.sin(meio) * r, 0, Math.cos(meio) * r);
    suporte.rotation.y = meio + PI;
    const largura = Math.min(4.2, Math.max(2.6, (trecho.a1 - trecho.a0) * r * 0.8));
    const placa = new T.Mesh(this.geo("plano", () => new T.PlaneGeometry(1, 1)), this.materialDeTexto([zona.kicker || "", zona.titulo], cor));
    placa.scale.set(largura, largura / 4, 1);
    placa.position.y = 0.32;
    placa.rotation.x = -1.05;
    placa.userData.zona = trecho.id;
    suporte.add(placa);
    this.decoracao.add(suporte);
    // um cacho de balões no corredor que abre a área (por fora dos estandes,
    // sem tapar o símbolo do meio) e o nome da área no ar
    const rb = raio + folga + 0.8;
    this.decoracao.add(this.balões(Math.sin(trecho.a0) * rb, Math.cos(trecho.a0) * rb, 4, trecho.a0));
    const ra = raio + folga + 1.2;
    this.decoracao.add(this.placaNoAr([zona.kicker || "", zona.titulo], cor, Math.sin(meio) * ra, 7.6, Math.cos(meio) * ra, 6.4, trecho.id));
  }

  /** A área escolhida acende no piso; as outras apagam um pouco. */
  realcarArea(id) {
    Object.entries(this.fundosDasAreas || {}).forEach(([zona, malha]) => {
      malha.material.opacity = !id ? 0.14 : zona === id ? 0.34 : 0.06;
    });
  }

  /** A área sob o ponteiro (a placa ou o letreiro dela -- o chão não), ou "". */
  zonaSob(x, y) {
    const r = this.canvas.getBoundingClientRect();
    this.ponteiro.set(((x - r.left) / r.width) * 2 - 1, -((y - r.top) / r.height) * 2 + 1);
    this.raycaster.setFromCamera(this.ponteiro, this.camera);
    const acerto = this.raycaster.intersectObjects(this.decoracao.children, true).find((a) => a.object.userData.zona && !a.object.userData.piso);
    return acerto ? acerto.object.userData.zona : "";
  }

  /** O ponto do chão (y = 0) sob a tela, ou null (olhando para o céu). */
  pontoNoChao(x, y) {
    const r = this.canvas.getBoundingClientRect();
    this.ponteiro.set(((x - r.left) / r.width) * 2 - 1, -((y - r.top) / r.height) * 2 + 1);
    this.raycaster.setFromCamera(this.ponteiro, this.camera);
    const raio = this.raycaster.ray;
    if (raio.direction.y > -0.02) return null;
    const t = -raio.origin.y / raio.direction.y;
    return t < 300 ? raio.origin.clone().addScaledVector(raio.direction, t) : null;
  }

  /**
   * Um toque no 3D: na máquina, escolhe a máquina; na placa de uma área, vai
   * até a área; no chão vazio, solta a máquina escolhida.
   */
  tocar(x, y) {
    const maquina = this.escolher(x, y);
    if (maquina) {
      this.selecionar(maquina);
      return;
    }
    const zona = this.zonaSob(x, y);
    if (zona && zona !== this.zona) this.escolherZona(zona);
    else if (this.selecionada) this.fecharSelecao();
  }

  /** A pessoa mexeu na câmera: ela fica livre (o grande para de dar a volta, o tour para). */
  soltarCamera() {
    if (this.tour) this.acao("tour", this.controles.querySelector('[data-arena-acao="tour"]'));
    if (this.vistaAtual === "livre") return;
    this.vistaAtual = "livre";
    if (this.vistas) {
      this.vistas.querySelectorAll("[data-arena-vista]").forEach((b) => b.setAttribute("aria-pressed", "false"));
      this.vistas.querySelector("[data-arena-lados-nome]").textContent = "Lados";
      this.vistas.querySelector("[data-arena-lados]").setAttribute("aria-pressed", "false");
    }
  }

  /** Solta a máquina escolhida e recua um pouco: a arena em volta aparece. */
  fecharSelecao() {
    if (!this.selecionada) return;
    this.soltarSelecao({ voar: false });
    const c = this.camera3d;
    c.raioDesejado = Math.max(c.raioDesejado, Math.min(c.raio * 1.8 + 4, 32));
    c.phiDesejado = Math.min(c.phiDesejado, 1.05);
    c.limitar();
  }

  /* ---------- fila de fotos: duas máquinas por vez, sem travar a página ---------- */
  andarFila() {
    while (this.trabalhando < 2 && this.fila.length) {
      const tarefa = this.fila.shift();
      this.trabalhando++;
      tarefa().catch((erro) => console.error("Arena 3D: máquina não montou", erro)).finally(() => {
        this.trabalhando--;
        this.mostrarProgresso();
      });
    }
  }

  mostrarProgresso() {
    const prontas = this.roda.filter((m) => m.montada).length;
    if (prontas >= Math.min(this.roda.length, 3)) this.esconderAviso();
  }

  esconderAviso() {
    if (this.avisoSumiu) return;
    this.avisoSumiu = true;
    this.palco.querySelector("[data-arena-aviso]").classList.add("sumiu");
    const dica = this.palco.querySelector("[data-arena-dica]");
    if (dica) {
      dica.lastChild.textContent = this.celular
        ? " 1 dedo gira · 2 dedos andam e aproximam · toque duplo vai até lá"
        : " Arraste para girar · botão direito anda · roda aproxima · duplo clique vai até lá";
      dica.hidden = false;
      window.setTimeout(() => { dica.hidden = true; }, 9000);
    }
  }

  /* ---------- escolher uma máquina ---------- */
  selecionar(maquina, { voar = true } = {}) {
    if (!maquina) return;
    if (!this.roda.includes(maquina)) return;
    if (this.passeio) this.sairPasseio({ voar: false });
    if (this.selecionada && this.selecionada !== maquina) this.largar(this.selecionada);
    this.selecionada = maquina;
    this.roda.forEach((m) => { m.aro.material = this.luz(m.cor, m === maquina ? 5 : 2.2); });
    this.vista("girar", { voar });
    const alvo = maquina.centro(this.ajuda);
    this.foco.position.set(alvo.x * 0.55, maquina.H + 6, alvo.z * 0.55);
    this.foco.target.position.set(alvo.x, 0, alvo.z);
    this.foco.intensity = 2.2;
    if (this.vistas) {
      this.vistas.hidden = false;
      const passeio = this.vistas.querySelector('[data-arena-vista="passeio"]');
      if (passeio) passeio.hidden = false;
    }
    this.mostrarFicha(maquina);
    this.corpo.classList.add("tem-ficha");
    this.marcarLista();
  }

  /** A máquina volta ao normal no estande: de frente, em pé. */
  largar(maquina) {
    maquina.girando = false;
    maquina.giroAlvo = giroMaisPerto(maquina.prato.rotation.y, 0);
    maquina.tomboAlvo = 0;
  }

  soltarSelecao({ voar = true } = {}) {
    if (this.passeio) this.sairPasseio({ voar: false });
    if (this.selecionada) this.largar(this.selecionada);
    this.selecionada = null;
    this.roda.forEach((m) => { m.aro.material = this.luz(m.cor, 2.2); });
    this.foco.intensity = 0;
    if (this.vistas) this.vistas.hidden = true;
    if (this.corpo) this.corpo.classList.remove("tem-ficha");
    if (this.ficha) {
      this.ficha.querySelector("[data-ficha-cheia]").hidden = true;
      this.ficha.querySelector("[data-ficha-vazia]").hidden = false;
    }
    if (voar) this.camera3d.visaoGeral();
    this.marcarLista();
  }

  /**
   * Ver a máquina escolhida de um lado: o prato gira até aquele lado ficar
   * de frente para a câmera; "cima" sobe a câmera; "baixo" tomba a máquina
   * para a base aparecer; "girar" deixa o prato rodando.
   */
  vista(nome, { voar = true } = {}) {
    const m = this.selecionada;
    if (!m) return;
    if (nome === "passeio") {
      this.entrarPasseio();
      return;
    }
    this.ocioso = 0;
    this.vistaAtual = nome;
    m.girando = nome === "girar" && !m.grande;
    if (nome !== "girar" && !m.grande) m.giroAlvo = giroMaisPerto(m.prato.rotation.y, GIRO_DA_VISTA[nome]);
    m.tomboAlvo = nome === "baixo" && !m.grande ? TOMBO : 0;
    if (voar) this.camera3d.olharPara(m, nome);
    if (this.vistas) {
      this.vistas.querySelectorAll("[data-arena-vista]").forEach((botao) => {
        botao.setAttribute("aria-pressed", botao.dataset.arenaVista === nome ? "true" : "false");
      });
      // o botão dos lados mostra o lado de agora
      const lado = this.vistas.querySelector(`[data-arena-lados-menu] [data-arena-vista="${nome}"]`);
      this.vistas.querySelector("[data-arena-lados-nome]").textContent = lado ? lado.textContent : "Lados";
      this.vistas.querySelector("[data-arena-lados]").setAttribute("aria-pressed", lado ? "true" : "false");
      this.abrirLados(false);
    }
  }

  abrirLados(abrir) {
    const menu = this.vistas && this.vistas.querySelector("[data-arena-lados-menu]");
    if (!menu) return;
    menu.hidden = !abrir;
    this.vistas.querySelector("[data-arena-lados]").setAttribute("aria-expanded", abrir ? "true" : "false");
  }

  /** "Ver tudo": a arena inteira, de qualquer lugar (o botão, o mapa, Esc). */
  verTudo() {
    if (this.passeio) this.sairPasseio({ voar: false });
    if (this.tour) this.acao("tour", this.controles.querySelector('[data-arena-acao="tour"]'));
    this.escolherZona("");
  }

  /** O painel do passeio: pausar / continuar (no fim, "De novo") e sair. */
  ligarPainelDoPasseio(painel) {
    painel.querySelector("[data-passeio-sair]").addEventListener("click", () => this.sairPasseio());
    painel.querySelector("[data-passeio-pausa]").addEventListener("click", () => {
      if (this.passeio) this.passeio.alternarPausa();
    });
  }

  /** O painel acompanha o passeio: a etapa, a barra do quanto andou e o botão. */
  marcarPasseio({ etapa, fracao, pausado, fim }) {
    const painel = this.painelPasseio;
    if (!painel) return;
    painel.querySelector("[data-passeio-etapa]").textContent = pausado ? "Pausado" : etapa;
    painel.querySelector("[data-passeio-progresso]").style.transform = `scaleX(${limitar(fracao, 0, 1).toFixed(3)})`;
    const botao = painel.querySelector("[data-passeio-pausa]");
    const rotulo = fim ? "Passear de novo" : pausado ? "Continuar o passeio" : "Pausar o passeio";
    botao.setAttribute("aria-label", rotulo);
    botao.title = rotulo;
    botao.dataset.estado = fim ? "fim" : pausado ? "pausado" : "andando";
  }

  entrarPasseio() {
    const m = this.selecionada;
    if (!m || !m.montada) return;
    this.largar(m);
    m.prato.rotation.y = giroMaisPerto(m.prato.rotation.y, 0);
    this.tour = false;
    this.passeio = new Passeio(this, m);
    if (this.vistas) this.vistas.hidden = true;
    if (this.controles) this.controles.hidden = true;
    this.rotulo.hidden = true;
    if (this.painelPasseio) {
      this.painelPasseio.hidden = false;
      const dica = this.painelPasseio.querySelector("[data-passeio-dica]");
      if (dica) {
        dica.textContent = this.celular
          ? "O passeio anda sozinho · arraste para olhar em volta"
          : "O passeio anda sozinho · arraste para olhar em volta · espaço pausa · Esc sai";
      }
      this.passeio.desenharMapaBase(this.painelPasseio.querySelector("[data-passeio-mapa]"));
    }
    this.passeio.entrar();
    this.palco.classList.add("em-passeio");
    // no celular, o palco no meio da tela: a barra do site não cobre os botões
    if (!this.expandida) this.palco.scrollIntoView({ behavior: this.reduzido ? "auto" : "smooth", block: "center" });
  }

  sairPasseio({ voar = true } = {}) {
    if (!this.passeio) return;
    this.passeio.sair();
    this.passeio = null;
    this.redimensionar();
    if (this.painelPasseio) this.painelPasseio.hidden = true;
    if (this.controles) this.controles.hidden = false;
    this.palco.classList.remove("em-passeio");
    if (this.selecionada) {
      if (this.vistas) this.vistas.hidden = false;
      if (voar) this.vista("frente");
    } else if (voar) this.camera3d.visaoGeral();
  }

  /**
   * As setas: o brinquedo que está daquele lado NA TELA (lado = 1, direita;
   * -1, esquerda), qualquer que seja o lado de onde a câmera olha. Sem
   * nenhum escolhido, começa pelo que está mais no meio da tela.
   */
  vizinha(lado) {
    const lista = this.lista.filter((m) => m.grupo.visible);
    const total = lista.length;
    if (!total) return;
    const T = this.T;
    const frente = this.camera.getWorldDirection(new T.Vector3()).setY(0).normalize();
    const direita = new T.Vector3(-frente.z, 0, frente.x);
    const atual = this.selecionada;
    if (!atual || !lista.includes(atual)) {
      const c = this.camera.position;
      const noMeio = (m) => {
        const d = this.ajuda.subVectors(m.grupo.position, c).setY(0);
        return d.dot(frente) / (d.length() || 1);
      };
      this.selecionar(lista.reduce((a, b) => (noMeio(b) > noMeio(a) ? b : a)));
      return;
    }
    const i = lista.indexOf(atual);
    const vizinhas = [lista[(i + 1) % total], lista[(i - 1 + total) % total]];
    const deLado = (m) => lado * this.ajuda.subVectors(m.grupo.position, atual.grupo.position).dot(direita);
    this.selecionar(deLado(vizinhas[0]) >= deLado(vizinhas[1]) ? vizinhas[0] : vizinhas[1]);
  }

  /**
   * Vai até uma área da arena -- a câmera passeia pela roda até o trecho
   * dela, que acende no piso. A roda continua inteira: as outras áreas
   * seguem ali do lado. "" volta para a arena inteira.
   */
  escolherZona(id) {
    this.zona = id;
    this.ocioso = 0;
    this.raiz.querySelectorAll("[data-arena-zona]").forEach((b) => {
      const ativo = b.dataset.arenaZona === id;
      b.classList.toggle("ativo", ativo);
      b.setAttribute("aria-pressed", ativo ? "true" : "false");
    });
    this.soltarSelecao({ voar: false });
    this.realcarArea(id);
    const trecho = (this.trechos || []).find((t) => t.id === id);
    if (trecho) this.camera3d.olharZona(trecho);
    else this.camera3d.visaoGeral();
  }

  filtrar(categoria) {
    this.categoria = categoria;
    this.soltarSelecao({ voar: false });
    this.montar();
    this.atualizarContagem();
  }

  atualizarContagem() {
    const contagem = {};
    let todas = 0;
    this.maquinas.forEach((m) => {
      if (this.categoria && !(m.dados.categorias || []).includes(this.categoria)) return;
      contagem[m.dados.grupo] = (contagem[m.dados.grupo] || 0) + 1;
      todas++;
    });
    this.raiz.querySelectorAll("[data-arena-zona]").forEach((botao) => {
      const id = botao.dataset.arenaZona;
      const total = id ? (contagem[id] || 0) : todas;
      const b = botao.querySelector("b");
      if (b) b.textContent = String(total);
      botao.hidden = Boolean(id) && !total;
    });
  }

  /* ---------- ficha (fora do palco) ---------- */
  mostrarFicha(m) {
    const f = this.ficha;
    if (!f) return;
    const b = m.dados;
    f.querySelector("[data-ficha-vazia]").hidden = true;
    f.querySelector("[data-ficha-cheia]").hidden = false;
    const zona = this.zonas.find((z) => z.id === b.grupo);
    const rotuloZona = f.querySelector("[data-ficha-zona]");
    rotuloZona.textContent = zona ? zona.titulo : "";
    rotuloZona.style.setProperty("--cor-zona", m.cor);
    f.querySelector("[data-ficha-nome]").textContent = b.nome;
    f.querySelector("[data-ficha-categoria]").textContent = (b.categorias || []).join(" · ") || "Brinquedo";
    const linhas = { medidas: b.medidas_texto, voltagem: b.voltagem, preco: b.preco };
    Object.entries(linhas).forEach(([nome, valor]) => {
      f.querySelector(`[data-ficha-linha="${nome}"]`).hidden = !valor;
      f.querySelector(`[data-ficha-${nome}]`).textContent = valor || "";
    });

    // a foto de cada lado: tocar numa gira a máquina para aquele lado
    const foto = f.querySelector("[data-ficha-foto]");
    const lados = f.querySelector("[data-ficha-lados]");
    lados.replaceChildren();
    const ordem = LADOS.filter((lado) => m.fotos[lado]);
    const trocar = (lado, botao) => {
      foto.src = m.fotos[lado];
      foto.alt = `${b.nome} — ${NOME_DO_LADO[lado]}`;
      lados.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", x === botao ? "true" : "false"));
    };
    ordem.forEach((lado, i) => {
      const botao = document.createElement("button");
      botao.type = "button";
      botao.textContent = NOME_DO_LADO[lado];
      botao.setAttribute("aria-pressed", i === 0 ? "true" : "false");
      botao.addEventListener("click", () => {
        trocar(lado, botao);
        this.vista(VISTA_DO_LADO[lado]);
      });
      lados.append(botao);
    });
    lados.hidden = ordem.length < 2;
    if (ordem.length) trocar(ordem[0], lados.querySelector("button"));


    const detalhe = f.querySelector("[data-ficha-detalhe]");
    detalhe.hidden = !b.url;
    if (b.url) detalhe.href = b.url;
    const texto = `Olá! Vi o ${b.nome} na Arena 3D do site da Lazer & Sport e quero um orçamento.`;
    const whatsapp = f.querySelector("[data-ficha-whatsapp]");
    whatsapp.href = whatsapp.href.split("?")[0] + "?text=" + encodeURIComponent(texto);
    // só as máquinas que SÃO um jogo da casa têm a prévia
    const jogar = f.querySelector("[data-ficha-jogar]");
    jogar.hidden = !b.jogo;
    if (b.jogo) jogar.href = `${jogar.dataset.base}${b.jogo}/`;
    // as cores do objeto 3D (quando a máquina tem um)
    this.mostrarCores(m);
    // num espaço inteiro, os jogos da casa que rodam nele (Swish, Gol Flash)
    const jogos = f.querySelector("[data-ficha-jogos]");
    if (jogos) {
      const lista = b.jogos_no_espaco || [];
      jogos.hidden = !lista.length;
      const rotulo = document.createElement("span");
      rotulo.textContent = "Jogue a prévia:";
      jogos.replaceChildren(...(lista.length ? [rotulo] : []), ...lista.map((jogo) => {
        const link = document.createElement("a");
        link.href = `${jogar.dataset.base}${jogo.slug}/`;
        link.textContent = jogo.titulo;
        return link;
      }));
    }
  }

  marcarLista() {
    const atual = this.selecionada ? String(this.selecionada.dados.id) : "";
    this.raiz.querySelectorAll("[data-arena-id]").forEach((link) => {
      link.classList.toggle("ativo", link.dataset.arenaId === atual);
    });
  }

  /* ---------- ligar à página ---------- */
  ligar() {
    const raiz = this.raiz;
    this.ficha = raiz.querySelector("[data-arena-ficha]");
    this.corpo = this.palco.closest(".arena3d-corpo") || this.palco.parentElement;
    this.controles = this.palco.querySelector("[data-arena-controles]");
    this.vistas = this.palco.querySelector("[data-arena-vistas]");
    this.rotulo = document.createElement("div");
    this.rotulo.className = "arena3d-rotulo";
    this.rotulo.hidden = true;
    this.palco.append(this.rotulo);

    this.redimensionar();
    this.montar({ entrada: true });
    this.atualizarContagem();
    new ResizeObserver(() => this.redimensionar()).observe(this.palco);
    this.camera3d.ligarEventos(this.canvas);
    if (!this.maquinas.length) avisar(this.palco, "Nenhum brinquedo em 3D ainda", "Assim que um brinquedo ganhar o objeto 3D, ele aparece aqui.");
    // objeto que demora não segura o aviso para sempre
    window.setTimeout(() => { if (this.maquinas.length) this.esconderAviso(); }, 9000);

    if (this.controles) {
      this.controles.hidden = false;
      this.controles.addEventListener("click", (evento) => {
        const botao = evento.target.closest("[data-arena-acao]");
        if (botao) this.acao(botao.dataset.arenaAcao, botao);
      });
    }
    if (this.vistas) {
      this.vistas.addEventListener("click", (evento) => {
        if (evento.target.closest("[data-arena-fechar]")) {
          this.fecharSelecao();
          return;
        }
        if (evento.target.closest("[data-arena-lados]")) {
          this.abrirLados(this.vistas.querySelector("[data-arena-lados-menu]").hidden);
          return;
        }
        const botao = evento.target.closest("[data-arena-vista]");
        if (botao) this.vista(botao.dataset.arenaVista);
      });
    }
    this.ligarMapa();
    this.painelPasseio = this.palco.querySelector("[data-arena-passeio]");
    if (this.painelPasseio) this.ligarPainelDoPasseio(this.painelPasseio);

    const zonas = raiz.querySelector("[data-arena-zonas]");
    if (zonas) {
      zonas.addEventListener("click", (evento) => {
        const botao = evento.target.closest("[data-arena-zona]");
        if (!botao) return;
        this.ocioso = 0;
        this.escolherZona(botao.dataset.arenaZona);
      });
    }
    const categoria = raiz.querySelector("[data-arena-categoria]");
    if (categoria) categoria.addEventListener("change", () => this.filtrar(categoria.value));

    // a lista vira o controle remoto da arena
    raiz.querySelectorAll("[data-arena-id]").forEach((link) => {
      link.addEventListener("click", (evento) => {
        if (evento.metaKey || evento.ctrlKey || evento.shiftKey) return;
        const maquina = this.maquinas.find((m) => String(m.dados.id) === link.dataset.arenaId);
        if (!maquina) return;
        evento.preventDefault();
        if (!this.lista.includes(maquina)) {
          // fora da categoria de agora: volta para todas
          if (categoria) categoria.value = "";
          this.filtrar("");
        }
        this.selecionar(maquina);
        if (!this.expandida) this.palco.scrollIntoView({ behavior: this.reduzido ? "auto" : "smooth", block: "center" });
      });
    });

    this.palco.addEventListener("keydown", (evento) => {
      if (this.passeio || evento.target.closest("select, input")) return;
      if (evento.key === "ArrowRight") { this.vizinha(1); evento.preventDefault(); }
      else if (evento.key === "ArrowLeft") { this.vizinha(-1); evento.preventDefault(); }
      else if (evento.key === "Escape") {
        // Esc solta a máquina; sem nenhuma, sai da tela cheia ou volta para a arena inteira
        if (this.selecionada) this.fecharSelecao();
        else if (this.expandida) this.telaCheia(false);
        else this.verTudo();
        evento.preventDefault();
      }
    });
    this.canvas.tabIndex = 0;

    // fora da tela ou com a aba escondida: não desenha nada
    new IntersectionObserver((entradas) => {
      this.visivel = this.expandida || entradas.some((e) => e.isIntersecting);
      this.acordar();
    }).observe(this.palco);
    document.addEventListener("visibilitychange", () => this.acordar());
    // a tela cheia do navegador abriu ou fechou: a da arena segue como está
    ["fullscreenchange", "webkitfullscreenchange"].forEach((nome) => document.addEventListener(nome, () => window.setTimeout(() => this.redimensionar(), 60)));

    this.visivel = true;
    this.acordar();
  }

  acao(nome, botao) {
    this.ocioso = 0;
    if (nome === "direita") this.vizinha(1);
    else if (nome === "esquerda") this.vizinha(-1);
    else if (nome === "visao") this.verTudo();
    else if (nome === "mapa") this.abrirMapa(this.mapa ? this.mapa.hidden : false);
    else if (nome === "tour") {
      this.tour = !this.tour;
      this.tourTempo = 0;
      botao.setAttribute("aria-pressed", this.tour ? "true" : "false");
      botao.querySelector("i").className = this.tour ? "fa-solid fa-pause" : "fa-solid fa-play";
      if (this.tour) this.vizinha(1);
    } else if (nome === "tela-cheia") {
      this.telaCheia(!this.expandida);
    }
  }

  /**
   * A TELA CHEIA: a arena (o 3D e a ficha) cobre a tela por conta própria e,
   * onde o navegador deixa, entra também na tela cheia dele. Se o navegador
   * fechar a dele (Esc, girar o celular, o iPhone que nem tem), a arena
   * continua cheia: sai só pelo botão "Sair" (ou Esc sem máquina escolhida).
   */
  telaCheia(ligar) {
    this.expandida = ligar;
    // a seção da arena tem a animação de entrada (transform): dentro dela, o
    // "fixed" não cobre a tela. Cheia, a arena vai para o nível da página;
    // ao sair, volta para o lugar dela.
    if (ligar && !this.lugarDoCorpo) {
      this.lugarDoCorpo = document.createComment("arena 3d");
      this.corpo.before(this.lugarDoCorpo);
      document.body.append(this.corpo);
    } else if (!ligar && this.lugarDoCorpo) {
      this.lugarDoCorpo.replaceWith(this.corpo);
      this.lugarDoCorpo = null;
    }
    this.corpo.classList.toggle("arena3d--cheia", ligar);
    document.documentElement.classList.toggle("arena-tela-cheia", ligar);
    const botao = this.controles.querySelector('[data-arena-acao="tela-cheia"]');
    botao.setAttribute("aria-pressed", ligar ? "true" : "false");
    botao.setAttribute("aria-label", ligar ? "Sair da tela cheia" : "Tela cheia");
    botao.querySelector("i").className = ligar ? "fa-solid fa-xmark" : "fa-solid fa-up-right-and-down-left-from-center";
    botao.querySelector("[data-tela-cheia-rotulo]").textContent = ligar ? "Sair" : "";
    const dele = document.fullscreenElement || document.webkitFullscreenElement;
    if (ligar && !dele) {
      const pedir = this.corpo.requestFullscreen || this.corpo.webkitRequestFullscreen;
      try {
        const pedido = pedir && pedir.call(this.corpo, { navigationUI: "hide" });
        if (pedido && pedido.catch) pedido.catch(() => {});
      } catch (erro) { /* sem a do navegador: a da arena basta */ }
    } else if (!ligar && dele) {
      const sair = document.exitFullscreen || document.webkitExitFullscreen;
      try {
        const pedido = sair && sair.call(document);
        if (pedido && pedido.catch) pedido.catch(() => {});
      } catch (erro) { /* já saiu */ }
    }
    this.visivel = true;
    this.acordar();
    window.setTimeout(() => this.redimensionar(), 60);
  }

  redimensionar() {
    const r = this.palco.getBoundingClientRect();
    if (!r.width || !r.height) return;
    this.renderer.setSize(r.width, r.height, false);
    this.camera.aspect = r.width / r.height;
    // tela em pé (celular) precisa de lente mais aberta para caber a roda
    this.camera.fov = this.camera.aspect < 0.8 ? 58 : 45;
    this.camera.updateProjectionMatrix();
  }

  acordar() {
    const deveRodar = this.visivel && !document.hidden;
    if (!deveRodar || this.rodando) return;
    this.rodando = true;
    this.relogioAnterior = performance.now();
    const passo = (agora) => {
      if (!this.visivel || document.hidden) {
        this.rodando = false;
        return;
      }
      requestAnimationFrame(passo);
      this.medirQuadro(agora - this.relogioAnterior);
      const dt = Math.min(0.05, (agora - this.relogioAnterior) / 1000);
      this.relogioAnterior = agora;
      this.quadro(dt);
    };
    requestAnimationFrame(passo);
  }

  /**
   * A resolução acompanha o aparelho: com os quadros lentos (abaixo de ~45
   * por segundo), a densidade de pixels desce um degrau; com folga por um
   * tempo, volta a subir. No celular mais fraco a imagem fica um pouco mais
   * macia, mas tudo anda liso.
   */
  medirQuadro(ms) {
    if (ms > 250) return; // a aba voltando: não conta
    this.somaDosQuadros = (this.somaDosQuadros || 0) + ms;
    this.quadrosMedidos = (this.quadrosMedidos || 0) + 1;
    if (this.somaDosQuadros < 2000) return;
    const media = this.somaDosQuadros / this.quadrosMedidos;
    this.somaDosQuadros = 0;
    this.quadrosMedidos = 0;
    const atual = this.renderer.getPixelRatio();
    let nova = atual;
    if (media > 22) {
      nova = Math.max(this.densidadeMinima, atual - 0.25);
      this.folga = 0;
    } else if (media < 15 && atual < this.densidadeMaxima) {
      this.folga = (this.folga || 0) + 1;
      if (this.folga >= 3) {
        nova = Math.min(this.densidadeMaxima, atual + 0.25);
        this.folga = 0;
      }
    } else {
      this.folga = 0;
    }
    if (nova !== atual) {
      this.renderer.setPixelRatio(nova);
      this.redimensionar();
    }
  }

  /** As telas (jogos, placares) pintam uma por quadro: nenhum quadro pesa mais que os outros. */
  podePintar() {
    if (this.pinturasNoQuadro >= 1) return false;
    this.pinturasNoQuadro++;
    return true;
  }

  quadro(dt) {
    this.pinturasNoQuadro = 0;
    this.relogio += dt;
    this.ocioso += dt;
    const t = this.relogio;
    this.andarFila();

    if (this.tour && !this.passeio) {
      this.tourTempo += dt;
      if (this.tourTempo > 6) {
        this.tourTempo = 0;
        this.vizinha(1);
      }
    }

    // O cenário fica firme: luzes, pilares, lâmpadas e estrelas paradas (cor
    // que corre pela tela parece defeito). Mexe só o que tem motivo: o alvo
    // da marca, os balões, os jogos e, devagar, a festa no céu (holofotes,
    // fogos e confete).
    if (!this.reduzido) this.alvoMarca.rotation.y = t * 0.6;
    this.animarFesta(dt, t);

    // as crianças brincando: com "menos movimento" ficam paradas na arena,
    // mas no passeio (que a pessoa pediu, e que anda sozinho) elas brincam
    this.roda.forEach((m) => {
      m.atualizar(dt, this.reduzido);
      const brinca = !this.reduzido || (this.passeio && this.passeio.maquina === m);
      if (m.animar && m.grupo.visible && brinca) m.animar(dt, t, this.camera);
    });
    if (this.passeio) {
      this.passeio.quadro(dt);
    } else {
      this.camera3d.atualizar(dt);
      this.liberarVista();
      this.posicionarRotulo();
      this.atualizarMapa();
    }
    this.animarCeu(dt, t);
    this.clarearPlacas();
    this.renderer.render(this.cena, this.camera);
  }

  /**
   * O alvo do centro não fica entre a câmera e a máquina escolhida: com a
   * câmera passando do meio da roda (máquina grande, roda pequena), ele some.
   */
  liberarVista() {
    const p = this.camera3d.alvo;
    if (Math.hypot(p.x, p.z) < 2) {
      // olhando para o centro (a arena inteira): o alvo é o destaque
      this.centroDaArena.visible = true;
      return;
    }
    const c = this.camera.position;
    const dx = p.x - c.x;
    const dz = p.z - c.z;
    const s = limitar(-(c.x * dx + c.z * dz) / (dx * dx + dz * dz || 1), 0, 1);
    this.centroDaArena.visible = Math.hypot(c.x, c.z) > 4 && Math.hypot(c.x + dx * s, c.z + dz * s) > 1.8;
  }

  /**
   * As caixas (no chão) de tudo o que está à vista, com a altura de cada
   * uma; refeitas só quando a roda muda ou um objeto chega.
   */
  medirCaixas() {
    const T = this.T;
    const caixa = new T.Box3();
    this.caixasSujas = false;
    this.caixas = this.roda.filter((m) => m.grupo.visible).map((m) => {
      const p = m.grupo.position;
      const topo = m.alturaP + Math.max(m.H, m.altura) + 0.1;
      if (!m.grande) {
        // a que gira no prato: a caixa do círculo dela
        const r = m.raioP;
        return { m, x0: p.x - r, x1: p.x + r, z0: p.z - r, z1: p.z + r, topo };
      }
      m.grupo.updateMatrixWorld(true);
      caixa.setFromObject(m.grupo);
      return { m, x0: caixa.min.x, x1: caixa.max.x, z0: caixa.min.z, z1: caixa.max.z, topo: Math.max(topo, caixa.max.y) };
    });
  }

  /**
   * A altura mais baixa em que a câmera pode ficar em (x, z): nunca abaixo
   * de um objeto. Perto da beira dele a altura cresce aos poucos (a câmera
   * sobe suave, sem pulo); a escolhida vista de baixo fica de fora.
   */
  alturaLivre(x, z) {
    if (this.caixasSujas || !this.caixas) this.medirCaixas();
    const BEIRA = 1.6;
    let minimo = 0.6;
    for (const c of this.caixas) {
      if (c.m === this.selecionada && this.vistaAtual === "baixo") continue;
      const d = Math.hypot(Math.max(c.x0 - x, 0, x - c.x1), Math.max(c.z0 - z, 0, z - c.z1));
      if (d >= BEIRA) continue;
      const k = 1 - d / BEIRA;
      minimo = Math.max(minimo, (c.topo + 0.7) * k * k * (3 - 2 * k));
    }
    // no parque em volta (árvores e postes de até 3,5 m) e no bosque lá fora
    // (árvores de até 9 m), a câmera passa por cima das copas
    const p = this.parque;
    if (p) {
      const r = Math.hypot(x, z);
      const subir = (r0, r1, altura) => {
        const longe = Math.max(r0 - r, 0, r - r1);
        if (longe >= 1.6) return;
        const k = 1 - longe / 1.6;
        minimo = Math.max(minimo, altura * k * k * (3 - 2 * k));
      };
      subir(p.dentro - 0.5, p.fora + 0.5, 4.6);
      subir(p.fora + 4, p.bosque + 1, 10);
    }
    return minimo;
  }

  ajustarPerto(perto) {
    const camera = this.camera;
    if (Math.abs(camera.near - perto) < 0.02) return;
    camera.near = perto;
    camera.updateProjectionMatrix();
  }

  /* ---------- o mapa: a arena vista de cima, como um mapa comum ---------- */
  ligarMapa() {
    this.mapa = this.palco.querySelector("[data-arena-mapa]");
    if (!this.mapa) return;
    this.telaDoMapa = this.mapa.querySelector("[data-arena-mapa-tela]");
    this.nomeNoMapa = this.mapa.querySelector("[data-arena-mapa-nome]");
    this.mapa.querySelector("[data-arena-mapa-fechar]").addEventListener("click", () => this.abrirMapa(false));
    const tela = this.telaDoMapa;
    let inicio = null;
    tela.addEventListener("pointerdown", (evento) => { inicio = { x: evento.clientX, y: evento.clientY }; });
    tela.addEventListener("pointerup", (evento) => {
      if (!inicio || Math.hypot(evento.clientX - inicio.x, evento.clientY - inicio.y) > 10) return;
      inicio = null;
      this.tocarNoMapa(evento.clientX, evento.clientY);
    });
    tela.addEventListener("pointermove", (evento) => {
      if (evento.pointerType !== "mouse") return;
      const m = this.pinoNoMapa(evento.clientX, evento.clientY);
      if (m !== this.sobreNoMapa) {
        this.sobreNoMapa = m;
        tela.style.cursor = m ? "pointer" : "default";
      }
    });
    tela.addEventListener("pointerleave", () => { this.sobreNoMapa = null; });
    // no computador, o mapa já fica no canto; no celular e no tablet abre no botão
    this.abrirMapa(window.matchMedia("(min-width: 961px)").matches);
  }

  abrirMapa(abrir) {
    if (!this.mapa) return;
    this.mapa.hidden = !abrir;
    const botao = this.controles && this.controles.querySelector('[data-arena-acao="mapa"]');
    if (botao) botao.setAttribute("aria-pressed", abrir ? "true" : "false");
    this.marcaDoMapa = "";
  }

  /**
   * Mundo (x, z) <-> mapa: a planta cabe inteira, com a entrada embaixo.
   * O caminho até os reinos (a passarela) fica curto no desenho -- como num
   * mapa de parque --, e a roda não vira um pontinho.
   */
  medidasDoMapa() {
    const tela = this.telaDoMapa;
    const w = tela.clientWidth;
    const h = tela.clientHeight;
    const R = (this.raio || 8) + (this.folga || 1) + 4.5;
    const reinos = (this.trechos || []).filter((t) => t.tipo === "reino");
    const frente = reinos.length ? Math.max(...reinos.map((t) => t.z1)) : -R;
    const vao = Math.max(0, -R - frente); // a passarela de verdade
    const curto = Math.min(vao, 3);
    // z do mundo -> z do desenho (e a volta), por trechos retos
    const zm = (z) => (z >= -R ? z : z >= frente ? -R - ((-R - z) * curto) / (vao || 1) : z + vao - curto);
    const zw = (z) => (z >= -R ? z : z >= -R - curto ? -R - ((-R - z) * vao) / (curto || 1) : z - vao + curto);
    let [x0, x1, z0, z1] = [-R - 1, R + 1, -R - 1, R + 1];
    reinos.forEach((t) => {
      x0 = Math.min(x0, t.x0 - 2);
      x1 = Math.max(x1, t.x1 + 2);
      z0 = Math.min(z0, zm(t.z0) - 2);
    });
    const grande = w >= 300;
    // de cada lado, o espaço dos nomes (no mapa grande)
    const folga = grande ? Math.min(118, w * 0.27) : 10;
    const s = Math.max(0.1, Math.min((w - folga * 2) / (x1 - x0), (h - 26) / (z1 - z0)));
    const ox = (w - (x1 - x0) * s) / 2 - x0 * s;
    const oy = (h - (z1 - z0) * s) / 2 - z0 * s;
    return { w, h, s, ox, oy, R, grande, folga, zm, zw, X: (x) => ox + x * s, Y: (z) => oy + zm(z) * s };
  }

  pinoNoMapa(cx, cy) {
    if (!this.medidaDoMapa) return null;
    const r = this.telaDoMapa.getBoundingClientRect();
    const { X, Y } = this.medidaDoMapa;
    let melhor = null;
    let perto = 18;
    this.roda.forEach((m) => {
      if (!m.grupo.visible) return;
      const d = Math.hypot(X(m.grupo.position.x) - (cx - r.left), Y(m.grupo.position.z) - (cy - r.top));
      if (d < perto) { perto = d; melhor = m; }
    });
    return melhor;
  }

  tocarNoMapa(cx, cy) {
    const m = this.pinoNoMapa(cx, cy);
    const pequeno = !window.matchMedia("(min-width: 961px)").matches;
    if (m) {
      this.selecionar(m);
      if (pequeno) this.abrirMapa(false); // no celular, o mapa sai da frente do brinquedo
      return;
    }
    // fora dos pinos: a área tocada (a faixa da roda ou o reino)
    const r = this.telaDoMapa.getBoundingClientRect();
    const { ox, oy, s, zw } = this.medidaDoMapa;
    const x = (cx - r.left - ox) / s;
    const z = zw((cy - r.top - oy) / s);
    const reino = (this.trechos || []).find((t) => t.tipo === "reino" && x >= t.x0 - 5 && x <= t.x1 + 5 && z >= t.z0 - 5 && z <= t.z1 + 5);
    if (reino) { this.escolherZona(reino.id); return; }
    const d = Math.hypot(x, z);
    if (d < (this.raio || 8) * 0.45) { this.verTudo(); return; }
    const a = (Math.atan2(x, z) + PI * 2) % (PI * 2);
    const trecho = (this.trechos || []).find((t) => t.tipo !== "reino" && a >= t.a0 && a <= t.a1);
    if (trecho && d < (this.raio || 8) + (this.folga || 1) + 5) this.escolherZona(trecho.id);
  }

  /** Redesenha o mapa só quando algo nele muda (a câmera, a escolha, o tamanho). */
  atualizarMapa() {
    if (!this.mapa || this.mapa.hidden || this.passeio) return;
    if (this.relogio - (this.mapaConferido || 0) < 0.1) return;
    this.mapaConferido = this.relogio;
    const tela = this.telaDoMapa;
    const c = this.camera.position;
    const d = this.camera.getWorldDirection(this.ajuda);
    const sel = this.selecionada;
    const marca = `${tela.clientWidth}x${tela.clientHeight}|${c.x.toFixed(1)},${c.z.toFixed(1)},${Math.atan2(d.x, d.z).toFixed(2)}|${sel ? sel.indice : ""}|${this.sobreNoMapa ? this.sobreNoMapa.indice : ""}|${this.zona}|${this.roda.length}`;
    if (marca === this.marcaDoMapa) return;
    this.marcaDoMapa = marca;
    this.desenharMapaDaArena();
  }

  desenharMapaDaArena() {
    const tela = this.telaDoMapa;
    const med = this.medidasDoMapa();
    this.medidaDoMapa = med;
    const { w, h, s, X, Y, R, grande } = med;
    if (!w || !h) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    if (tela.width !== Math.round(w * dpr) || tela.height !== Math.round(h * dpr)) {
      tela.width = Math.round(w * dpr);
      tela.height = Math.round(h * dpr);
    }
    const g = tela.getContext("2d");
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, h);
    const cx = X(0);
    const cy = Y(0);
    const raio = this.raio || 8;
    const folga = this.folga || 1;
    const fonte = (px, peso = 800) => `${peso} ${px}px Poppins, Manrope, system-ui, sans-serif`;

    // o piso da roda, a cerca de pilares e o alvo do meio
    g.fillStyle = "#10224f";
    g.beginPath(); g.arc(cx, cy, (raio + folga + 1.5) * s, 0, PI * 2); g.fill();
    g.strokeStyle = "rgba(63, 208, 255, .55)";
    g.lineWidth = 1.5;
    g.beginPath(); g.arc(cx, cy, R * s, 0, PI * 2); g.stroke();
    // o símbolo da marca pintado no chão: a faixa branca e o alvo
    const simbolo = Math.max(4, (this.raioDoSimbolo || 1.5) * s);
    [[1, "#fbfbff"], [0.68, "#e63946"], [0.52, "#ffffff"], [0.36, "#e63946"], [0.2, "#ffffff"]].forEach(([k, cor]) => {
      g.fillStyle = cor;
      g.beginPath(); g.arc(cx, cy, simbolo * k, 0, PI * 2); g.fill();
    });

    // as áreas: a faixa colorida de cada uma na roda; o reino, ao lado
    (this.trechos || []).forEach((t) => {
      const cor = COR_DA_ZONA[t.id] || "#2f8bff";
      const ativa = this.zona === t.id;
      g.globalAlpha = ativa ? 0.62 : this.zona ? 0.2 : 0.38;
      g.fillStyle = cor;
      if (t.tipo === "reino") {
        // a passarela de luz e o espaço inteiro
        g.fillRect(X((t.x0 + t.x1) / 2) - 1.6 * s, Y(t.z1), 3.2 * s, Y(-R) - Y(t.z1));
        g.fillRect(X(t.x0), Y(t.z0), (t.x1 - t.x0) * s, Y(t.z1) - Y(t.z0));
        g.globalAlpha = 1;
        g.strokeStyle = cor;
        g.lineWidth = 1.5;
        g.strokeRect(X(t.x0), Y(t.z0), (t.x1 - t.x0) * s, Y(t.z1) - Y(t.z0));
        const zona = this.zonas.find((z) => z.id === t.id);
        if (zona && (t.x1 - t.x0) * s > 70) {
          g.fillStyle = "#ffffff";
          g.font = fonte(grande ? 12 : 9);
          g.textAlign = "center";
          g.textBaseline = "top";
          g.fillText(zona.titulo, X((t.x0 + t.x1) / 2), Y(t.z0) + 4);
        }
        return;
      }
      g.beginPath();
      g.arc(cx, cy, (raio + folga + 0.6) * s, PI / 2 - t.a0, PI / 2 - t.a1, true);
      g.arc(cx, cy, Math.max(0, raio - folga - 0.9) * s, PI / 2 - t.a1, PI / 2 - t.a0, false);
      g.closePath();
      g.fill();
    });
    g.globalAlpha = 1;

    // a entrada (o portal), embaixo
    const aP = A_ENTRADA;
    const ex = cx + Math.sin(aP) * R * s;
    const ey = cy + Math.cos(aP) * R * s;
    // o caminho da entrada, da roda até o portão do parque (na borda do mapa)
    g.strokeStyle = "rgba(201, 184, 214, .55)";
    g.lineWidth = Math.max(2, 2.4 * s);
    g.beginPath();
    g.moveTo(ex, ey);
    g.lineTo(limitar(cx + Math.sin(aP) * (R + 12) * s, 4, w - 4), limitar(cy + Math.cos(aP) * (R + 12) * s, 4, h - 4));
    g.stroke();
    g.fillStyle = "#ffd700";
    g.beginPath(); g.arc(ex, ey, 4, 0, PI * 2); g.fill();
    g.font = fonte(grande ? 11 : 9, 900);
    g.textAlign = "center";
    g.textBaseline = "top";
    g.fillText("ENTRADA", Math.min(w - 30, ex), Math.min(h - 12, ey + 6));

    // os brinquedos: um pino na cor da área; o escolhido maior, com o nome
    const sel = this.selecionada;
    const sobre = this.sobreNoMapa;
    const nomes = [];
    this.roda.forEach((m) => {
      if (!m.grupo.visible) return;
      const px = X(m.grupo.position.x);
      const py = Y(m.grupo.position.z);
      const cor = COR_DA_ZONA[m.dados.grupo] || m.cor;
      const destaque = m === sel || m === sobre;
      if (m === sel) {
        g.fillStyle = "rgba(255, 255, 255, .25)";
        g.beginPath(); g.arc(px, py, 13, 0, PI * 2); g.fill();
      }
      g.fillStyle = cor;
      g.strokeStyle = "#ffffff";
      g.lineWidth = destaque ? 2.5 : 1.5;
      g.beginPath(); g.arc(px, py, destaque ? 8 : 5.5, 0, PI * 2); g.fill(); g.stroke();
      if (grande && !m.reino) nomes.push({ m, px, py, destaque });
    });

    // os nomes por fora da roda, na direção de cada brinquedo: de cada lado,
    // um embaixo do outro (sem encavalar), com um fio até o pino se precisou descer
    const ALTURA = 12;
    [1, -1].forEach((lado) => {
      const doLado = nomes
        .map((n) => {
          const a = Math.atan2(n.py - cy, n.px - cx);
          return { ...n, a, lx: cx + Math.cos(a) * (R * s + 8), ly: cy + Math.sin(a) * (R * s + 8) };
        })
        .filter((n) => (Math.cos(n.a) >= 0 ? 1 : -1) === lado)
        .sort((p, q) => p.ly - q.ly);
      for (let i = 1; i < doLado.length; i++) doLado[i].ly = Math.max(doLado[i].ly, doLado[i - 1].ly + ALTURA);
      // o que passou de baixo do mapa sobe de volta, empurrando os de cima
      for (let i = doLado.length - 1; i >= 0; i--) {
        const teto = i === doLado.length - 1 ? h - 8 : doLado[i + 1].ly - ALTURA;
        doLado[i].ly = Math.min(doLado[i].ly, teto);
      }
      doLado.forEach((n) => {
        const longe = Math.abs(n.ly - (cy + Math.sin(n.a) * (R * s + 8))) > 3;
        if (longe) {
          g.strokeStyle = "rgba(219, 231, 255, .35)";
          g.lineWidth = 1;
          g.beginPath();
          g.moveTo(n.px, n.py);
          g.lineTo(n.lx - lado * 2, n.ly);
          g.stroke();
        }
        g.font = fonte(10.5, n.destaque ? 900 : 700);
        const cabe = lado > 0 ? w - n.lx - 4 : n.lx - 4;
        let nome = n.m.dados.nome;
        while (nome.length > 3 && g.measureText(nome).width > cabe) nome = `${nome.slice(0, -2)}…`;
        g.textAlign = lado > 0 ? "left" : "right";
        g.textBaseline = "middle";
        g.fillStyle = n.destaque ? "#ffd84a" : "rgba(219, 231, 255, .92)";
        g.fillText(nome, n.lx, n.ly);
      });
    });

    // você está aqui: o ponto azul e o leque do que a câmera vê
    const c = this.camera.position;
    const d = this.camera.getWorldDirection(this.ajuda);
    const vx = limitar(X(c.x), 8, w - 8);
    const vy = limitar(Y(c.z), 8, h - 8);
    const ang = Math.atan2(d.z, d.x);
    const meia = Math.min(1.2, (this.camera.fov * PI) / 360 * Math.max(1, this.camera.aspect));
    const leque = g.createRadialGradient(vx, vy, 2, vx, vy, grande ? 70 : 46);
    leque.addColorStop(0, "rgba(63, 160, 255, .55)");
    leque.addColorStop(1, "rgba(63, 160, 255, 0)");
    g.fillStyle = leque;
    g.beginPath();
    g.moveTo(vx, vy);
    g.arc(vx, vy, grande ? 70 : 46, ang - meia, ang + meia);
    g.closePath();
    g.fill();
    g.fillStyle = "#2f8bff";
    g.strokeStyle = "#ffffff";
    g.lineWidth = 2.5;
    g.beginPath(); g.arc(vx, vy, 6.5, 0, PI * 2); g.fill(); g.stroke();

    // embaixo do mapa: o nome do brinquedo apontado (ou escolhido)
    if (this.nomeNoMapa) {
      const alvo = sobre || sel;
      const texto = alvo ? alvo.dados.nome : "Você está aqui · toque num brinquedo";
      if (this.nomeNoMapa.dataset.texto !== texto) {
        this.nomeNoMapa.dataset.texto = texto;
        this.nomeNoMapa.lastChild.textContent = ` ${texto}`;
      }
    }
  }

  /** O nome da máquina em cima dela: a do mouse, ou a escolhida. */
  posicionarRotulo() {
    // o nome do escolhido fica PARADO embaixo do palco: preso ao objeto, ele
    // ia junto com a câmera girando e tremia; o da máquina sob o mouse
    // acompanha o ponteiro, como uma dica
    const sobre = this.sobre && this.sobre !== this.selecionada ? this.sobre : null;
    const m = sobre || this.selecionada;
    if (!m || !m.grupo.visible) {
      this.rotulo.hidden = true;
      return;
    }
    if (this.rotulo.textContent !== m.dados.nome) this.rotulo.textContent = m.dados.nome;
    this.rotulo.hidden = false;
    this.rotulo.classList.toggle("arena3d-rotulo--fixo", !sobre);
    let posicao = "";
    if (sobre) {
      const w = this.palco.clientWidth;
      const h = this.palco.clientHeight;
      const x = Math.round(limitar(this.mouseX || 0, 80, w - 80));
      const y = Math.round(limitar((this.mouseY || 0) - 18, 40, h - 70));
      posicao = `translate3d(${x}px, ${y}px, 0) translate(-50%, -100%)`;
    }
    if (this.rotulo.style.transform !== posicao) this.rotulo.style.transform = posicao;
  }

  /** A máquina sob o ponteiro (coordenadas de tela). */
  escolher(x, y) {
    const r = this.canvas.getBoundingClientRect();
    this.ponteiro.set(((x - r.left) / r.width) * 2 - 1, -((y - r.top) / r.height) * 2 + 1);
    this.raycaster.setFromCamera(this.ponteiro, this.camera);
    const acerto = this.raycaster.intersectObjects(this.roda.map((m) => m.grupo), true)[0];
    return acerto ? acerto.object.userData.maquina || null : null;
  }
}

/* ======================================================================
   PASSEIO — um só fluxo por dentro do brinquedo, na altura de uma criança

   Em todo objeto 3D da roda: o caminho é desenho do objeto (CAMINHOS);
   quem não tem um dá a volta em torno dele, parando em cada lado.

   O passeio é UM caminho que passa por tudo o que o brinquedo tem --
   subir a escadinha, engatinhar na rede, passar pelo tubo, descer o
   tobogã, pular nas camas, cair na espuma --, com o corpo de quem passa
   por ali. Não se escolhe nada: entrou, ele anda sozinho. A pessoa pode
   olhar em volta (arrastar; o olhar volta sozinho para o caminho),
   pausar (o botão ou a barra de espaço) e sair (o botão ou Esc).
   ====================================================================== */
const OLHOS = 0.85; // altura dos olhos acima do piso: uma criança

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

/** O tobogã em espiral do brinquedão (o desenho do objeto), com os pés no fundo do tubo. */
function toboganDoBrinquedao() {
  const cx = -10590;
  const cy = -1500;
  const raio = 650;
  const a0 = (-50 * PI) / 180;
  const a1 = 2 * PI;
  const pontos = [];
  for (let i = 0; i <= 24; i++) {
    const t = i / 24;
    const a = a0 + (a1 - a0) * t;
    pontos.push([...BQ(cx + raio * Math.cos(a), cy + raio * Math.sin(a), 2404 - t * 1974 - 300), "escorregar"]);
  }
  pontos.push([...BQ(cx + raio, cy + 380, 95), "escorregar"], [...BQ(cx + raio, cy + 700, 90), "escorregar"]);
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

/** O tobogã em espiral do ninja (o TOBOGA do montar.js), com os pés no fundo do tubo. */
function toboganDoNinja() {
  const pontos = [[...NJ(9900, 3060, 2295), "escorregar"]];
  for (let i = 0; i <= 24; i++) {
    const t = i / 24;
    const a = (-540 * t * PI) / 180;
    pontos.push([...NJ(9030 + 400 * Math.cos(a), 2290 + 400 * Math.sin(a), 2525 - 1885 * t - 235), "escorregar"]);
  }
  pontos.push([...NJ(8700, 2600, 345), "escorregar"], [...NJ(8760, 2850, 295), "escorregar"]);
  return pontos;
}

/** A espiral do tobogã do circuito kids (o desenho do Espaço Esportivo). */
function toboganKids() {
  const pontos = [[16.2, 1.7, 7.35, "escorregar"], [17.2, 1.7, 7.9, "escorregar"]];
  for (let i = 0; i <= 24; i++) {
    const t = i / 24;
    const a = -PI / 2 + t * PI * 3;
    pontos.push([17.8 + 0.75 * Math.cos(a), 1.65 - t * 1.25, 9.4 + 0.75 * Math.sin(a), "escorregar"]);
  }
  return pontos;
}

/** O caminho de cada objeto (pelo id do modelo). */
const CAMINHOS = {
  // escadinha, a rede da torre das bolas, o andar de cima com a rede de
  // escalada, o tubo e o saco, o tobogã em espiral; por trás, o andar do
  // meio e o escorregador duplo; e o brinquedão inteiro visto da frente
  "brinquedao-modelo-2": () => [
    [...BQ(-3323, -1900, 0), "ir"],
    [...BQ(-3323, -2450, 0), "andar"],
    // os degraus: 0,64 m na frente e 1,11 m atrás
    [...BQ(-3323, -2700, 643), "subir"],
    [...BQ(-3323, -3050, 643), "subir"],
    [...BQ(-3323, -3250, 1109), "subir"],
    [...BQ(-3323, -3420, 1109), "agachado"],
    // sai de baixo do andar de cima antes de subir para a rede da torre
    [...BQ(-2860, -3420, 1109), "agachado"],
    [...BQ(-2450, -3300, 1833), "subir"],
    [...BQ(-1700, -2700, 1833), "rede", { pausa: 1.4, olhar: BQ(-1318, -3085, 2380) }],
    [...BQ(-2550, -3150, 1833), "rede"],
    // da rede para a beira do andar de cima (sobe antes de passar por baixo dele)
    [...BQ(-2720, -3150, 2074), "subir"],
    // o andar de cima tem o teto baixo: anda-se abaixado
    [...BQ(-3300, -3150, 2074), "agachado"],
    [...BQ(-3870, -3150, 2074), "agachado"],
    // a rede de escalada: sobe pela beira dela e engatinha por cima
    [...BQ(-3950, -3150, 2490), "subir"],
    [...BQ(-5300, -3150, 2490), "rede"],
    [...BQ(-5420, -3250, 2074), "subir"],
    [...BQ(-5600, -3350, 2074), "agachado"],
    [...BQ(-6420, -3350, 2074), "agachado"],
    [...BQ(-6460, -3150, 2084), "agachado"],
    [...BQ(-7460, -3150, 2084), "tubo"],
    [...BQ(-7750, -2850, 2074), "agachado"],
    [...BQ(-8300, -2850, 2074), "agachado", { pausa: 0.8, olhar: BQ(-7990, -3150, 2450) }],
    [...BQ(-9300, -2900, 2074), "agachado"],
    [...BQ(-10150, -2600, 2074), "agachado"],
    // atrás da boca do tobogã, de frente para ela
    [...BQ(-10530, -2360, 2074), "agachado", { pausa: 0.9, olhar: BQ(-10172, -1998, 2250) }],
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
    [...NJ(1320, 2700, 0), "andar"],
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
    [...NJ(9950, 3300, 2260), "agachado", { pausa: 0.8, olhar: NJ(9700, 2600, 2000) }],
    ...toboganDoNinja(),
    [...NJ(8950, 3150, 300), "cair", { pausa: 1.2, olhar: NJ(9300, 2300, 1400) }],
    // pela piscina de bolinhas até a saída da frente (por baixo do corrimão) e os degraus
    [...NJ(9650, 3250, 300), "andar"],
    [...NJ(9900, 2750, 300), "andar"],
    [...NJ(10200, 2250, 320), "andar"],
    [...NJ(10200, 2000, 340), "tubo"],
    [...NJ(10180, 1870, 300), "subir"],
    [...NJ(10180, 1700, 150), "subir"],
    [...NJ(10180, 1400, 0), "andar"],
    // a primeira cama elástica: degraus, a entrada sob o corrimão e os pulos
    [...NJ(12240, 1350, 0), "andar"],
    [...NJ(12240, 1700, 150), "subir"],
    [...NJ(12240, 1880, 300), "subir"],
    [...NJ(12240, 2080, 330), "tubo"],
    [...NJ(11700, 2600, 330), "pular"],
    [...NJ(11000, 3300, 330), "pular"],
    [...NJ(11480, 2970, 330), "pular", { pausa: 1.6 }],
    [...NJ(10900, 2500, 330), "pular"],
    [...NJ(11900, 3400, 330), "pular"],
    [...NJ(12240, 2200, 330), "pular"],
    [...NJ(12240, 2000, 330), "tubo"],
    [...NJ(12240, 1800, 300), "subir"],
    [...NJ(12240, 1650, 150), "subir"],
    [...NJ(12400, 1350, 0), "andar"],
    // a segunda cama
    [...NJ(14400, 1350, 0), "andar"],
    [...NJ(14400, 1700, 150), "subir"],
    [...NJ(14400, 1880, 300), "subir"],
    [...NJ(14400, 2080, 330), "tubo"],
    [...NJ(13800, 2700, 330), "pular"],
    [...NJ(13100, 3350, 330), "pular"],
    [...NJ(13600, 2970, 330), "pular", { pausa: 1.6 }],
    [...NJ(13000, 2450, 330), "pular"],
    [...NJ(14000, 3300, 330), "pular"],
    [...NJ(14400, 2200, 330), "pular"],
    [...NJ(14400, 2000, 330), "tubo"],
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
    [...NJ(6600, 3462, 560), "tirolesa"],
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
    [3.6, 0.65, -8.2, "cair", { pausa: 1.6, olhar: [3.6, 2.4, -11.2] }],
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
    [13.6, 0.7, 1.3, "cair", { pausa: 1.6, olhar: [13.1, 2.0, 0.1] }],
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
    [17.8, 0.3, 10.45, "cair", { pausa: 1.6, olhar: [16.5, 0.6, 10.4] }],
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

/** O tobogã espiral do Modelo 4 (o TOBOGA do montar.js), com os pés no fundo do tubo. */
function toboganDoModelo4() {
  const pontos = [[...M4(19020, 4200, 2610), "escorregar"]];
  for (let i = 0; i <= 28; i++) {
    const t = i / 28;
    const a = ((180 + 700 * t) * PI) / 180;
    pontos.push([...M4(19590 + 570 * Math.cos(a), 3900 + 570 * Math.sin(a), 2880 - 2240 * t - 270), "escorregar"]);
  }
  pontos.push([...M4(18880, 3250, 290), "escorregar"]);
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
  // a escada: o piso de baixo, o degrau de 0,98 m, o piso pink do meio, o degrau de 2,18 m e o amarelo de cima
  [...M4(1550, 6800, 240), "subir"],
  [...M4(1300, 7000, 240), "andar"],
  [...M4(1200, 7250, 980), "subir"],
  [...M4(1350, 7400, 1630), "subir"],
  [...M4(1700, 7450, 2180), "subir"],
  [...M4(1850, 6950, 2595), "subir"],
  // o andar de cima tem o teto baixo: anda-se abaixado, pelo lado dos rolos em pé
  [...M4(2250, 6850, 2595), "agachado", { pausa: 0.9, olhar: M4(2500, 7100, 3050) }],
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
  [...M4(9950, 7100, 2595), "agachado"],
  [...M4(10050, 6850, 2595), "agachado"],
  [...M4(10500, 6850, 2595), "agachado"],
  [...M4(10650, 7100, 2595), "agachado"],
  [...M4(10780, 7100, 2575), "rede"],
  [...M4(11640, 7100, 2575), "rede"],
  // a passagem: por cima do rolo baixo, por baixo do alto, por cima do outro baixo
  [...M4(12170, 7100, 2595), "agachado", { pausa: 0.8, olhar: M4(12170, 5300, 2900) }],
  [...M4(12170, 6520, 2595), "agachado"],
  [...M4(12170, 6280, 2925), "subir"],
  [...M4(12170, 6020, 2595), "agachado"],
  [...M4(12170, 5760, 2595), "tubo"],
  [...M4(12170, 5510, 2595), "agachado"],
  [...M4(12170, 5280, 2925), "subir"],
  [...M4(12170, 4950, 2595), "agachado"],
  // o saco azul e o par de rolos amarelos (passa-se pela fresta entre os dois)
  [...M4(11950, 4650, 2595), "agachado", { pausa: 0.8, olhar: M4(12170, 4405, 3100) }],
  [...M4(12450, 4150, 2595), "agachado"],
  [...M4(12900, 4405, 2595), "tubo"],
  [...M4(13130, 4405, 2700), "tubo"],
  [...M4(13360, 4405, 2595), "tubo"],
  // o rolo amarelo em pé, pela frente, e a rede em V
  [...M4(13800, 4100, 2595), "agachado"],
  [...M4(14450, 4100, 2595), "agachado"],
  [...M4(14660, 4405, 2575), "rede"],
  [...M4(16500, 4405, 2575), "rede"],
  // o outro par de rolos e o outro saco
  [...M4(16880, 4405, 2595), "tubo"],
  [...M4(17100, 4405, 2700), "tubo"],
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
function voltaEmVolta(m) {
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
const MODOS_DO_PASSEIO = {
  ir: { v: 6, olhos: OLHOS, nome: "Chegando" },
  andar: { v: 1.4, olhos: OLHOS, nome: "Passeando" },
  agachado: { v: 0.9, olhos: 0.58, nome: "Andando abaixado" },
  subir: { v: 0.55, olhos: 0.65, olhar: 0.22, nome: "Subindo" },
  rede: { v: 0.6, olhos: 0.6, nome: "Na rede" },
  tubo: { v: 0.7, olhos: 0.45, nome: "No túnel" },
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
  // os "pés" ficam 29 cm abaixo do centro do tubo (raio de 26 cm): com os
  // olhos 45 cm acima deles, a cabeça fica 10 cm abaixo do teto do tubo e o
  // plano de perto da câmera não corta a parede
  const pes = (x, y, z) => [...M3(x, y, z - 290), "escorregar"];
  const pontos = [pes(9480, 3520, 2170), pes(9510, 3200, 2165), pes(9630, 2820, 2145)];
  // 2,25 voltas de cima, no sentido do relógio, de 2,12 m a 0,65 m (o centro do tubo)
  for (let i = 0; i <= 27; i++) {
    const t = i / 27;
    const a = -t * 2.25 * 2 * PI;
    pontos.push(pes(9250 + 460 * Math.cos(a), 2380 + 460 * Math.sin(a), 2120 - 1470 * t));
  }
  pontos.push(pes(8800, 1960, 610), pes(8430, 2030, 570));
  return pontos;
}

// entra pela torre da ponta da perna e sobe as plataformas em zigue-zague,
// atravessa a passarela de rede, o corredor de cunhas, o piso de rede com a
// bola-pêndulo, o balanço e os sacos de pancada; desce o tobogã em espiral
// até a piscina de bolinhas, sai pela escadinha e olha o brinquedão inteiro
CAMINHOS["brinquedao-modelo-3"] = () => [
  [...M3(500, -1600, 0), "ir"],
  [...M3(500, -350, 0), "andar"],
  // as plataformas da torre: amarela (0,45 m), azul (0,9 m), azul (1,4 m) e a
  // amarela do 2º andar, alternando as metades da diagonal; cada subida
  // acontece depois de passar para a outra metade (é lá que há altura livre)
  [...M3(600, 120, 450), "subir"],
  [...M3(560, 470, 450), "subir"],
  [...M3(380, 620, 900), "subir"],
  [...M3(470, 560, 900), "subir"],
  [...M3(650, 380, 1400), "subir"],
  [...M3(560, 450, 1400), "subir"],
  [...M3(350, 700, 1900), "subir", { pausa: 1, olhar: M3(500, 200, 2900) }],
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
  // o balanço (as cordas vermelha e azul) e os sacos de pancada, passando entre eles
  [...M3(6880, 4350, 1900), "andar"],
  [...M3(7200, 3700, 1900), "andar", { pausa: 1, olhar: M3(7500, 3700, 2700) }],
  [...M3(7300, 4250, 1900), "agachado"],
  [...M3(7300, 4700, 1900), "agachado"],
  [...M3(7600, 4770, 1900), "agachado"],
  [...M3(7850, 4700, 1900), "agachado"],
  // os últimos módulos de trás e a boca do tobogã, no 10º da frente
  [...M3(8500, 4700, 1900), "andar"],
  [...M3(9400, 4700, 1900), "andar"],
  [...M3(9480, 4000, 1900), "andar"],
  [...M3(9480, 3760, 1900), "andar", { pausa: 0.9, olhar: M3(9550, 2900, 1900) }],
  ...toboganDoModelo3(),
  [...M3(8250, 2050, 300), "cair", { pausa: 1.2, olhar: M3(9250, 2380, 1500) }],
  // pela piscina até a frente, por cima da mureta e pela escadinha
  [...M3(8500, 1500, 300), "andar"],
  [...M3(8500, 1260, 450), "subir"],
  [...M3(8500, 1100, 450), "subir"],
  [...M3(8500, 900, 225), "subir"],
  [...M3(8500, 500, 0), "andar"],
  // e o brinquedão inteiro, de frente
  [...M3(6000, -2600, 0), "andar"],
  [...M3(5000, -5200, 0), "andar", { pausa: 2, olhar: M3(5000, 3800, 1700) }],
];

class Passeio {
  constructor(arena, maquina) {
    const T = arena.T;
    this.arena = arena;
    this.maquina = maquina;
    this.pes = new T.Vector3();
    this.yaw = 0;
    this.pitch = -0.08;
    this.olhos = OLHOS;
    this.extra = { yaw: 0, pitch: 0, tempo: 0 }; // o olhar em volta (arrastando)
    this.pausado = false;
    this.fim = false;
    this.raio = new T.Raycaster();
    this.baixo = new T.Vector3(0, -1, 0);
    this.normal = new T.Vector3();
    this.origem = new T.Vector3();
    const caminho = CAMINHOS[maquina.dados.modelo_id] || voltaEmVolta;
    this.pontos = caminho(maquina);
    // num espaço grande (o parque de trampolins), o passo é mais largo
    this.ritmo = Math.max(maquina.largura, maquina.fundo) > 15 ? 1.3 : 1;
    this.aoApertar = (evento) => this.tecla(evento);
  }

  entrar() {
    const T = this.arena.T;
    const m = this.maquina;
    m.grupo.updateMatrixWorld(true);
    // começa na frente do brinquedo, olhando para dentro dele
    const D = m.D || m.fundo;
    this.pes.set(0, 0, D / 2 + 0.9).applyMatrix4(m.grupo.matrixWorld);
    this.pes.y = this.piso(this.pes.x, this.pes.z);
    const centro = new T.Vector3().setFromMatrixPosition(m.grupo.matrixWorld);
    this.yaw = Math.atan2(-(centro.x - this.pes.x), -(centro.z - this.pes.z));
    window.addEventListener("keydown", this.aoApertar);
    const camera = this.arena.camera;
    camera.rotation.order = "YXZ";
    camera.fov = 72;
    camera.near = 0.05; // de perto: grade, rede e degrau a um palmo dos olhos
    camera.updateProjectionMatrix();
    this.montarCaminho();
    this.quadro(0);
  }

  sair() {
    window.removeEventListener("keydown", this.aoApertar);
    // a órbita parte de onde o passeio parou: a saída é um voo, não um salto
    const camera = this.arena.camera;
    const c3 = this.arena.camera3d;
    const olhar = new this.arena.T.Vector3();
    camera.getWorldDirection(olhar);
    c3.alvo.copy(camera.position).addScaledVector(olhar, 2);
    c3.raio = 2;
    c3.phi = Math.acos(limitar(-olhar.y, -1, 1));
    c3.theta = Math.atan2(-olhar.x, -olhar.z);
    c3.thetaDesejado = c3.theta;
  }

  tecla(evento) {
    if (evento.key === "Escape") {
      evento.preventDefault();
      this.arena.sairPasseio();
    } else if (evento.key === " " && !evento.target.closest("input, textarea, select")) {
      evento.preventDefault();
      this.alternarPausa();
    }
  }

  /** Arrastar: olha em volta; o olhar volta sozinho para o caminho. */
  olhar(dx, dy) {
    this.extra.yaw -= dx * 0.005;
    this.extra.pitch = limitar(this.extra.pitch - dy * 0.004, -1, 1);
    this.extra.tempo = 1.6;
  }

  /** O piso mais alto embaixo de (x, z): onde os pés ficam na entrada. */
  piso(x, z) {
    let melhor = 0;
    for (const [ox, oz] of [[0, 0], [0.1, 0], [-0.1, 0], [0, 0.1], [0, -0.1]]) {
      this.origem.set(x + ox, this.pes.y + 1, z + oz);
      this.raio.set(this.origem, this.baixo);
      this.raio.far = 9;
      for (const acerto of this.raio.intersectObject(this.maquina.grupo, true)) {
        if (!acerto.face) continue;
        this.normal.copy(acerto.face.normal).transformDirection(acerto.object.matrixWorld);
        if (this.normal.y < 0.55) continue;
        melhor = Math.max(melhor, acerto.point.y);
        break;
      }
    }
    return melhor;
  }

  /**
   * O caminho: os pontos (no objeto) viram uma curva no mundo, amostrada a
   * cada 6 cm, com o modo de cada trecho e a pausa e o evento no fim dele.
   * Ele sai de onde a pessoa entrou.
   */
  montarCaminho() {
    const T = this.arena.T;
    const m = this.maquina;
    const noMundo = (p) => m.corpo.localToWorld(new T.Vector3(p[0], p[1], p[2]));
    const pontos = [{ w: this.pes.clone(), modo: "andar" }, ...this.pontos.map(([x, y, z, modo = "andar", extras = {}]) => ({
      w: noMundo([x, y, z]), modo, ...extras, olhar: extras.olhar ? noMundo(extras.olhar) : null,
    }))];
    const curva = new T.CatmullRomCurve3(pontos.map((p) => p.w), false, "centripetal");
    const n = pontos.length - 1;
    const amostras = [];
    let s = 0;
    for (let k = 0; k < n; k++) {
      const passos = Math.max(2, Math.ceil(pontos[k].w.distanceTo(pontos[k + 1].w) / 0.06));
      const y0 = Math.min(pontos[k].w.y, pontos[k + 1].w.y);
      const y1 = Math.max(pontos[k].w.y, pontos[k + 1].w.y);
      const solto = ["escorregar", "pular", "enterrada", "cair"].includes(pontos[k + 1].modo);
      for (let j = k ? 1 : 0; j <= passos; j++) {
        const p = curva.getPoint((k + j / passos) / n);
        // a curva suave não afunda no piso nem sobe além do degrau
        if (!solto) p.y = limitar(p.y, y0, y1);
        if (amostras.length) s += p.distanceTo(amostras[amostras.length - 1].p);
        amostras.push({ p, s, modo: pontos[k + 1].modo });
      }
      const fim = amostras[amostras.length - 1];
      const ponto = pontos[k + 1];
      if (ponto.pausa) Object.assign(fim, { pausa: ponto.pausa, olhar: ponto.olhar });
      if (ponto.evento) fim.evento = ponto.evento;
    }
    // o "ir" da entrada até o começo leva no máximo uns 2 segundos
    const ida = amostras.findIndex((a) => a.modo !== "ir");
    this.vIda = Math.max(MODOS_DO_PASSEIO.ir.v, (ida > 0 ? amostras[ida].s : 0) / 2);
    this.amostras = amostras;
    this.total = s;
    this.recomecar();
  }

  /** Do começo (o botão "De novo" no fim). */
  recomecar() {
    Object.assign(this, { s: 0, k: 0, v: 0, espera: 0, olharDaPausa: null, fase: 0, quique: 0, rolar: 0, fim: false, pausado: false, parte: -1, etapa: "" });
    this.extra.yaw = this.extra.pitch = 0;
    this.avisar();
  }

  alternarPausa() {
    if (this.fim) this.recomecar();
    else {
      this.pausado = !this.pausado;
      this.avisar();
    }
  }

  /** O painel: a etapa (Subindo, Na rede, Escorregando!...), o quanto andou, pausado ou no fim. */
  avisar() {
    const modo = this.amostras[Math.min(this.k + 1, this.amostras.length - 1)].modo;
    this.arena.marcarPasseio({
      etapa: this.fim ? "Fim do passeio" : (MODOS_DO_PASSEIO[modo] || MODOS_DO_PASSEIO.andar).nome,
      fracao: this.total ? this.s / this.total : 0,
      pausado: this.pausado,
      fim: this.fim,
    });
  }

  /** O ponto do caminho a `s` metros do começo (na amostra mais perto). */
  pontoNoCaminho(s) {
    const a = this.amostras;
    let lo = this.k;
    let hi = a.length - 1;
    if (s >= a[hi].s) return a[hi].p;
    while (hi - lo > 1) {
      const meio = (lo + hi) >> 1;
      if (a[meio].s <= s) lo = meio;
      else hi = meio;
    }
    return a[hi].p;
  }

  quadro(dt) {
    const a = this.amostras;
    const camera = this.arena.camera;
    const ultima = a.length - 1;
    let modo = a[Math.min(this.k + 1, ultima)].modo;
    const jeito = MODOS_DO_PASSEIO[modo] || MODOS_DO_PASSEIO.andar;
    if (this.pausado || this.fim) {
      this.v = 0;
    } else if (this.espera > 0) {
      this.espera -= dt;
      this.v = 0;
    } else {
      if (modo === "escorregar") this.v = Math.min(jeito.v, Math.max(this.v, 1.4) + dt * 3.4); // acelera na descida
      else if (modo === "ir") this.v = this.vIda;
      else this.v += (jeito.v * this.ritmo - this.v) * (1 - Math.exp(-dt * 5));
      this.s = Math.min(this.total, this.s + this.v * dt);
      while (this.k < ultima && a[this.k + 1].s <= this.s) {
        this.k++;
        const q = a[this.k];
        if (q.evento && this.maquina.animar && this.maquina.animar.evento) this.maquina.animar.evento(q.evento);
        if (q.pausa) {
          this.espera = q.pausa;
          this.olharDaPausa = q.olhar;
          this.s = q.s;
          break;
        }
      }
      if (this.s >= this.total && this.espera <= 0) {
        this.fim = true;
        this.avisar();
      }
    }
    const q0 = a[this.k];
    const q1 = a[Math.min(this.k + 1, ultima)];
    const f = q1.s > q0.s ? limitar((this.s - q0.s) / (q1.s - q0.s), 0, 1) : 0;
    this.pes.lerpVectors(q0.p, q1.p, f);
    modo = q1.modo;

    // para onde se olha: mais à frente no caminho, ou o que a pausa pede
    const parado = this.espera > 0 && this.olharDaPausa;
    const alvo = parado ? this.olharDaPausa : this.pontoNoCaminho(this.s + (modo === "escorregar" ? 1.1 : 1.6));
    const dx = alvo.x - this.pes.x;
    const dz = alvo.z - this.pes.z;
    const longe = Math.hypot(dx, dz);
    const k = 1 - Math.exp(-dt * (modo === "escorregar" ? 6 : 3.2));
    if (longe > 0.08 && !this.fim) {
      let delta = Math.atan2(-dx, -dz) - this.yaw;
      delta = Math.atan2(Math.sin(delta), Math.cos(delta));
      const antes = this.yaw;
      this.yaw += delta * k;
      // no tobogã, o corpo deita para dentro da curva
      if (modo === "escorregar") this.rolar += (limitar(((this.yaw - antes) / Math.max(dt, 0.001)) * 0.12, -0.32, 0.32) - this.rolar) * k;
    }
    if (modo !== "escorregar") this.rolar *= 1 - k;
    if (!this.fim) {
      const subida = parado ? alvo.y - (this.pes.y + this.olhos) : alvo.y - this.pes.y;
      const pitchAlvo = limitar(Math.atan2(subida, Math.max(longe, 0.3)) * (parado ? 1 : 0.7) + (parado ? 0 : jeito.olhar || 0), -1.1, 0.9);
      this.pitch += (pitchAlvo - this.pitch) * k;
    }

    // o corpo: o passo, o balanço da rede e da viga, o quique na cama
    const andando = this.v > 0.05;
    if (!this.pausado) this.fase += dt;
    this.quique += ((this.fim ? 0 : jeito.quique || 0) - this.quique) * (1 - Math.exp(-dt * 4));
    this.olhos += ((this.fim ? OLHOS : jeito.olhos) - this.olhos) * (1 - Math.exp(-dt * 5));
    let sobe = Math.abs(Math.sin(this.fase * 4.4)) * this.quique;
    let rolar = this.rolar;
    if (andando && (modo === "andar" || modo === "subir")) sobe += Math.abs(Math.sin(this.fase * 5.6)) * 0.03;
    if (!this.fim && (modo === "rede" || modo === "viga" || modo === "tirolesa")) {
      sobe += Math.sin(this.fase * 3.6) * 0.04;
      rolar += Math.sin(this.fase * 2.1) * (modo === "rede" ? 0.08 : 0.05);
    }
    if (this.arena.reduzido) { sobe = 0; rolar = 0; }

    // o olhar em volta (arrastando) volta devagar para o caminho; parado, fica
    this.extra.tempo -= dt;
    if (this.extra.tempo <= 0 && !this.pausado && !this.fim) {
      const volta = 1 - Math.exp(-dt * 2.5);
      this.extra.yaw *= 1 - volta;
      this.extra.pitch *= 1 - volta;
    }
    camera.position.set(this.pes.x, this.pes.y + this.olhos + sobe, this.pes.z);
    camera.rotation.set(limitar(this.pitch + this.extra.pitch, -1.3, 1.3), this.yaw + this.extra.yaw, rolar, "YXZ");
    this.atualizarMapa();
    const parte = Math.round((this.s / this.total) * 100);
    const etapa = MODOS_DO_PASSEIO[modo] ? modo : "andar";
    if (parte !== this.parte || etapa !== this.etapa) {
      this.parte = parte;
      this.etapa = etapa;
      this.avisar();
    }
  }

  /** O mapa só se redesenha quando a pessoa se mexe (sem conta à toa), até 15 vezes por segundo. */
  atualizarMapa() {
    const agora = performance.now();
    if (agora - (this.mapaPintado || 0) < 66) return;
    const marca = `${this.pes.x.toFixed(2)},${this.pes.z.toFixed(2)},${(this.yaw + this.extra.yaw).toFixed(2)}`;
    if (marca !== this.ultimaMarca) {
      this.ultimaMarca = marca;
      this.mapaPintado = agora;
      this.desenharMapa();
    }
  }

  /**
   * O mapa visto de cima: a câmera ortográfica fotografa o brinquedo uma
   * vez (com o pedestal), com o fundo do brinquedo para cima, como numa
   * planta. Depois, a cada quadro, só se desenha a bolinha e o leque.
   */
  desenharMapaBase(tela) {
    const a = this.arena;
    const T = a.T;
    const m = this.maquina;
    this.mapa = tela;
    const lado = Math.max(m.W || m.largura, m.D || m.fundo) + 2.4;
    this.ladoDoMapa = lado;
    const camera = new T.OrthographicCamera(-lado / 2, lado / 2, lado / 2, -lado / 2, 0.1, 200);
    const centro = new T.Vector3().setFromMatrixPosition(m.grupo.matrixWorld);
    camera.position.set(centro.x, 60, centro.z);
    camera.up.set(0, 0, -1).applyQuaternion(m.grupo.quaternion);
    camera.lookAt(centro);
    const n = 256;
    const alvo = new T.WebGLRenderTarget(n, n);
    alvo.texture.colorSpace = T.SRGBColorSpace;
    const neblina = a.cena.fog;
    const fundo = a.cena.background;
    a.cena.fog = null;
    // a planta tem o fundo da noite do céu, sem o céu (os fachos e os fogos não entram)
    a.cena.background = new T.Color("#0d0b33");
    const festa = a.festaNoCeu();
    festa.forEach((o) => { o.userData.visivel = o.visible; o.visible = false; });
    a.renderer.setRenderTarget(alvo);
    a.renderer.render(a.cena, camera);
    a.renderer.setRenderTarget(null);
    festa.forEach((o) => { o.visible = o.userData.visivel; });
    a.cena.fog = neblina;
    a.cena.background = fundo;
    const px = new Uint8Array(n * n * 4);
    a.renderer.readRenderTargetPixels(alvo, 0, 0, n, n, px);
    alvo.dispose();
    const base = document.createElement("canvas");
    base.width = base.height = n;
    const imagem = base.getContext("2d").createImageData(n, n);
    for (let y = 0; y < n; y++) imagem.data.set(px.subarray((n - 1 - y) * n * 4, (n - y) * n * 4), y * n * 4);
    base.getContext("2d").putImageData(imagem, 0, 0);
    this.mapaBase = base;
    this.desenharMapa();
  }

  desenharMapa() {
    if (!this.mapa || !this.mapaBase) return;
    const g = this.mapa.getContext("2d");
    const w = this.mapa.width;
    g.clearRect(0, 0, w, w);
    g.drawImage(this.mapaBase, 0, 0, w, w);
    // onde a pessoa está, no desenho (o fundo do brinquedo fica em cima)
    const local = this.maquina.grupo.worldToLocal(this.arena.ajuda.copy(this.pes));
    const x = (local.x / this.ladoDoMapa + 0.5) * w;
    const y = (local.z / this.ladoDoMapa + 0.5) * w;
    const giro = this.yaw + this.extra.yaw - this.maquina.grupo.rotation.y;
    g.save();
    g.translate(x, y);
    g.rotate(-giro);
    const leque = g.createRadialGradient(0, 0, 2, 0, 0, w * 0.16);
    leque.addColorStop(0, "rgba(255, 216, 74, .65)");
    leque.addColorStop(1, "rgba(255, 216, 74, 0)");
    g.fillStyle = leque;
    g.beginPath();
    g.moveTo(0, 0);
    g.arc(0, 0, w * 0.16, -PI / 2 - 0.55, -PI / 2 + 0.55);
    g.closePath();
    g.fill();
    g.restore();
    g.fillStyle = "#ffd84a";
    g.strokeStyle = "#071433";
    g.lineWidth = w * 0.012;
    g.beginPath();
    g.arc(x, y, w * 0.028, 0, PI * 2);
    g.fill();
    g.stroke();
  }
}

/* ======================================================================
   A CÂMERA — órbita própria, com voo suave até a máquina escolhida
   ====================================================================== */
class Camera {
  constructor(arena) {
    this.arena = arena;
    this.alvo = new arena.T.Vector3(0, 1, 0);
    this.alvoDesejado = this.alvo.clone();
    this.theta = 0.5;
    this.phi = 0.95;
    this.raio = 40;
    this.thetaDesejado = this.theta;
    this.phiDesejado = this.phi;
    this.raioDesejado = 26;
    this.ponteiros = new Map();
  }

  visaoGeral(entrada = false) {
    const raioArena = this.arena.raio || 8;
    // A roda inteira e, em cima, o céu de festa atrás do parque: a câmera
    // um pouco mais baixa e mais longe, olhando um tico acima do chão. Em
    // pé (celular), a roda só cabe de mais longe.
    const emPe = this.arena.camera.aspect < 0.8;
    this.alvoDesejado.set(0, emPe ? 2.6 : 3.2, 0);
    this.raioDesejado = (raioArena * 1.75 + 7) * (emPe ? 1.5 : 1.15);
    this.phiDesejado = emPe ? 1.12 : 1.22;
    if (entrada && !this.arena.reduzido) {
      // entrada de cinema: vem de longe e de cima
      this.raio = this.raioDesejado * 1.8;
      this.phi = 0.55;
    }
  }

  olharPara(maquina, vista = "girar") {
    const centro = maquina.centro(new this.arena.T.Vector3());
    this.alvoDesejado.copy(centro);
    if (maquina.grande) {
      this.olharGrande(maquina, vista, centro);
      return;
    }
    const tamanho = Math.max(maquina.H, maquina.W || 0, maquina.D, 1.6);
    const folga = this.arena.camera.aspect < 0.8 ? 1.5 : 1;
    this.raioDesejado = Math.min(16, Math.max(3.2, tamanho * 1.7 + 0.8) * folga);
    this.phiDesejado = vista === "cima" ? 0.3 : vista === "baixo" ? 1.3 : 1.2;
    if (vista === "baixo") {
      // tombada, a máquina sobe: o centro do olhar sobe junto
      const t = Math.abs(TOMBO);
      const meia = (maquina.H / 2) * Math.cos(t) + (maquina.D / 2) * Math.sin(t);
      this.alvoDesejado.y = maquina.alturaP + maquina.H / 2 + Math.max(0, meia - maquina.H / 2) + 0.25;
    }
    // a câmera fica do lado do centro, de frente para o estande
    const thetaFrente = Math.atan2(-centro.x, -centro.z);
    let delta = thetaFrente - this.thetaDesejado;
    delta = Math.atan2(Math.sin(delta), Math.cos(delta));
    this.thetaDesejado += delta;
  }

  /**
   * Uma área da roda: a câmera fica do lado do centro, de frente para o
   * trecho, longe o bastante para caber o trecho inteiro na tela.
   */
  olharZona(trecho) {
    const arena = this.arena;
    const camera = arena.camera;
    if (trecho.tipo === "reino") {
      // o reino inteiro, visto de cima e da frente (do lado da roda)
      const th = Math.tan((camera.fov * PI) / 360) * camera.aspect;
      const largura = trecho.x1 - trecho.x0 + 4;
      const fundo = trecho.z1 - trecho.z0;
      this.alvoDesejado.set((trecho.x0 + trecho.x1) / 2, 1.5, (trecho.z0 + trecho.z1) / 2);
      this.raioDesejado = Math.min(140, (largura / 2 / th) * 1.05 + fundo / 2);
      this.phiDesejado = 0.85;
      let delta = 0 - this.thetaDesejado;
      delta = Math.atan2(Math.sin(delta), Math.cos(delta));
      this.thetaDesejado += delta;
      return;
    }
    const raio = arena.raio || 8;
    const meio = (trecho.a0 + trecho.a1) / 2;
    const arco = Math.max(0.3, trecho.a1 - trecho.a0);
    const corda = 2 * raio * Math.sin(Math.min(PI, arco) / 2) + 2 * (arena.folga || 1.5);
    const th = Math.tan((camera.fov * PI) / 360) * camera.aspect;
    const r = arco > PI ? raio * 0.35 : raio * 0.9;
    this.alvoDesejado.set(Math.sin(meio) * r, 1.3, Math.cos(meio) * r);
    this.raioDesejado = Math.min(raio * 3.4 + 12, Math.max(7, (corda / 2 / th) * 1.08 + 1.5));
    this.phiDesejado = 0.98;
    let delta = Math.atan2(-Math.sin(meio), -Math.cos(meio)) - this.thetaDesejado;
    delta = Math.atan2(Math.sin(delta), Math.cos(delta));
    this.thetaDesejado += delta;
  }

  /**
   * O grande (um brinquedão de 11 m) fica parado: cada vista leva a câmera
   * para aquele lado dele, longe o bastante para caber inteiro na tela.
   */
  olharGrande(maquina, vista, centro) {
    const T = this.arena.T;
    const camera = this.arena.camera;
    const LADO = { direita: [1, 0], esquerda: [-1, 0], costas: [0, -1] };
    const [lx, lz] = LADO[vista] || [0, 1];
    const direcao = new T.Vector3(lx, 0, lz).applyQuaternion(maquina.grupo.quaternion);
    const tv = Math.tan((camera.fov * PI) / 360);
    const th = tv * camera.aspect;
    const W = maquina.W || maquina.largura;
    const D = maquina.D || maquina.fundo;
    const deLado = vista === "direita" || vista === "esquerda";
    const largo = deLado ? D : W;
    const fundo = deLado ? W : D;
    let raio = Math.max(largo / 2 / th, maquina.H / 2 / tv) * (largo > 15 ? 1.3 : 1.15) + fundo / 2;
    if (vista === "cima") raio = Math.max(W / 2 / th, D / 2 / tv) * 1.1 + maquina.H;
    this.raioDesejado = Math.min(30, raio);
    this.alvoDesejado.y = maquina.alturaP + maquina.H * (vista === "baixo" ? 0.6 : 0.45);
    this.phiDesejado = vista === "cima" ? 0.3 : vista === "baixo" ? 1.42 : 1.22;
    let delta = Math.atan2(direcao.x, direcao.z) - this.thetaDesejado;
    delta = Math.atan2(Math.sin(delta), Math.cos(delta));
    this.thetaDesejado += delta;
  }

  /**
   * Os gestos, como num mapa: um dedo (ou o botão esquerdo) gira; dois dedos
   * (ou o botão direito, ou Shift + arrastar) andam pela arena e a pinça
   * aproxima; a roda aproxima na direção do mouse; toque duplo (duplo
   * clique) vai até o ponto; tocar no chão vazio solta a máquina escolhida.
   * Qualquer movimento da pessoa solta a câmera da máquina: ela anda livre.
   */
  ligarEventos(canvas) {
    const arena = this.arena;
    let inicio = null;
    let distanciaPinca = 0;
    let meio = null;
    let modo = "girar";
    let ultimoToque = null;

    canvas.addEventListener("contextmenu", (evento) => evento.preventDefault());

    canvas.addEventListener("pointerdown", (evento) => {
      try { canvas.setPointerCapture(evento.pointerId); } catch (erro) { /* sem captura */ }
      this.ponteiros.set(evento.pointerId, { x: evento.clientX, y: evento.clientY });
      inicio = { x: evento.clientX, y: evento.clientY, t: performance.now() };
      modo = evento.pointerType === "mouse" && (evento.button !== 0 || evento.shiftKey || evento.ctrlKey) ? "andar" : "girar";
      arena.ocioso = 0;
      canvas.classList.add("arrastando");
      if (this.ponteiros.size === 2) {
        const [a, b] = [...this.ponteiros.values()];
        distanciaPinca = Math.hypot(a.x - b.x, a.y - b.y);
        meio = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
      }
    });

    canvas.addEventListener("pointermove", (evento) => {
      const anterior = this.ponteiros.get(evento.pointerId);
      if (!anterior) {
        // só passando por cima: o cursor avisa que dá para tocar
        if (evento.pointerType === "mouse" && !arena.passeio) {
          const r = arena.palco.getBoundingClientRect();
          arena.mouseX = evento.clientX - r.left;
          arena.mouseY = evento.clientY - r.top;
          arena.sobre = arena.escolher(evento.clientX, evento.clientY);
          canvas.classList.toggle("sobre-maquina", Boolean(arena.sobre) || Boolean(arena.zonaSob(evento.clientX, evento.clientY)));
        }
        return;
      }
      const dx = evento.clientX - anterior.x;
      const dy = evento.clientY - anterior.y;
      this.ponteiros.set(evento.pointerId, { x: evento.clientX, y: evento.clientY });
      arena.ocioso = 0;
      if (arena.passeio) {
        arena.passeio.olhar(dx, dy);
        return;
      }
      if (this.ponteiros.size === 2) {
        // dois dedos: o meio deles anda pela arena; a pinça aproxima
        const [a, b] = [...this.ponteiros.values()];
        const agora = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
        if (meio) this.andarNaTela(agora.x - meio.x, agora.y - meio.y);
        meio = agora;
        const distancia = Math.hypot(a.x - b.x, a.y - b.y);
        if (distanciaPinca > 0) this.aproximar(distanciaPinca / Math.max(1, distancia), agora.x, agora.y);
        distanciaPinca = distancia;
        return;
      }
      if (modo === "andar") {
        this.andarNaTela(dx, dy);
        return;
      }
      if (Math.abs(dx) + Math.abs(dy) > 0) arena.soltarCamera();
      this.thetaDesejado -= dx * 0.006;
      this.phiDesejado -= dy * 0.005;
      this.limitar();
    });

    canvas.addEventListener("pointerleave", () => { arena.sobre = null; });

    const soltar = (evento) => {
      this.ponteiros.delete(evento.pointerId);
      canvas.classList.remove("arrastando");
      if (this.ponteiros.size < 2) { distanciaPinca = 0; meio = null; }
      if (!inicio) return;
      const andou = Math.hypot(evento.clientX - inicio.x, evento.clientY - inicio.y);
      const rapido = performance.now() - inicio.t < 450;
      inicio = null;
      if (andou >= 8 || !rapido || evento.type !== "pointerup" || modo !== "girar") return;
      if (arena.passeio) return; // no passeio, tocar é só olhar
      // toque duplo: vai até o ponto tocado (no mouse, o dblclick cuida)
      const agora = performance.now();
      const duplo = evento.pointerType !== "mouse" && ultimoToque && agora - ultimoToque.t < 330 && Math.hypot(evento.clientX - ultimoToque.x, evento.clientY - ultimoToque.y) < 30;
      ultimoToque = duplo ? null : { x: evento.clientX, y: evento.clientY, t: agora };
      if (duplo) {
        this.irAoPonto(evento.clientX, evento.clientY);
        return;
      }
      arena.tocar(evento.clientX, evento.clientY);
    };
    canvas.addEventListener("pointerup", soltar);
    canvas.addEventListener("pointercancel", soltar);
    canvas.addEventListener("dblclick", (evento) => {
      if (!arena.passeio) this.irAoPonto(evento.clientX, evento.clientY);
    });

    canvas.addEventListener("wheel", (evento) => {
      evento.preventDefault();
      arena.ocioso = 0;
      if (arena.passeio) return; // o passeio anda sozinho
      this.aproximar(Math.exp(evento.deltaY * 0.0012), evento.clientX, evento.clientY);
    }, { passive: false });
  }

  /** Arrastar a arena pela tela (como um mapa): o ponto do chão vai com o dedo. */
  andarNaTela(dx, dy) {
    const arena = this.arena;
    const altura = arena.canvas.clientHeight || 600;
    const porPixel = (2 * this.raio * Math.tan((arena.camera.fov * PI) / 360)) / altura;
    const fundo = porPixel / Math.max(0.45, Math.cos(this.phi)); // o chão deitado, visto de lado
    const s = Math.sin(this.theta);
    const c = Math.cos(this.theta);
    // a direita (c, -s) e a frente (-s, -c) da câmera, no chão
    const x = -c * dx * porPixel - s * dy * fundo;
    const z = s * dx * porPixel - c * dy * fundo;
    this.alvo.x += x;
    this.alvo.z += z;
    this.alvoDesejado.x = this.alvo.x;
    this.alvoDesejado.z = this.alvo.z;
    this.alvoDesejado.y = this.alvo.y = Math.min(this.alvo.y, 1.6);
    arena.soltarCamera();
    this.limitar();
  }

  /** Aproxima (fator < 1) ou afasta, na direção do ponto da tela. */
  aproximar(fator, x, y) {
    const antes = this.raioDesejado;
    this.raioDesejado *= fator;
    this.limitar();
    const real = this.raioDesejado / antes;
    const p = this.arena.pontoNoChao(x, y);
    if (p && real < 1) {
      // o ponto sob o mouse fica sob o mouse: o alvo anda na direção dele
      const k = 1 - real;
      this.alvoDesejado.x += (p.x - this.alvoDesejado.x) * k;
      this.alvoDesejado.z += (p.z - this.alvoDesejado.z) * k;
      if (Math.hypot(p.x - this.alvo.x, p.z - this.alvo.z) > 1.5) this.arena.soltarCamera();
      this.limitar();
    }
  }

  /**
   * Toque duplo: voa até o ponto. Numa máquina, escolhe a máquina; num
   * espaço grande (o parque inteiro), vai até aquele canto dele.
   */
  irAoPonto(x, y) {
    const arena = this.arena;
    const maquina = arena.escolher(x, y);
    if (maquina && !maquina.grande) {
      arena.selecionar(maquina);
      return;
    }
    const p = arena.pontoNoChao(x, y);
    if (!p) return;
    if (maquina && maquina !== arena.selecionada) arena.selecionar(maquina, { voar: false });
    arena.soltarCamera();
    this.alvoDesejado.set(p.x, 1.2, p.z);
    this.raioDesejado = Math.min(this.raioDesejado, 14);
    this.limitar();
  }

  limitar() {
    this.phiDesejado = Math.min(1.45, Math.max(0.22, this.phiDesejado));
    const maximo = Math.max((this.arena.raio || 8) * 3.6 + 14, this.arena.longeDosReinos ? 140 : 0);
    this.raioDesejado = Math.min(maximo, Math.max(2.4, this.raioDesejado));
    // andando pela arena, o alvo não sai dela (a roda e os reinos)
    const borda = (this.arena.raio || 8) + (this.arena.folga || 1) + 12;
    const reinos = (this.arena.trechos || []).filter((t) => t.tipo === "reino");
    const fundo = Math.min(-borda, ...reinos.map((t) => t.z0 - 4));
    const lado = Math.max(borda, ...reinos.map((t) => Math.max(-t.x0, t.x1) + 4));
    for (const alvo of [this.alvo, this.alvoDesejado]) {
      alvo.x = limitar(alvo.x, -lado, lado);
      alvo.z = limitar(alvo.z, fundo, borda);
    }
  }

  atualizar(dt) {
    const arena = this.arena;
    // ninguém mexendo há um tempo, nada escolhido e a câmera no meio da
    // arena: ela passeia sozinha (andando livre, fica onde a pessoa deixou)
    if (!arena.reduzido && !arena.selecionada && arena.ocioso > 3.5 && this.ponteiros.size === 0 && Math.hypot(this.alvo.x, this.alvo.z) < 3) {
      this.thetaDesejado += dt * 0.1;
    }
    // o grande escolhido em "Girar": a câmera dá a volta nele
    const m = arena.selecionada;
    if (!arena.reduzido && m && m.grande && arena.vistaAtual === "girar" && this.ponteiros.size === 0) {
      this.thetaDesejado += dt * 0.16;
    }
    const k = 1 - Math.exp(-dt * (arena.reduzido ? 20 : 4.2));
    this.alvo.lerp(this.alvoDesejado, k);
    this.theta += (this.thetaDesejado - this.theta) * k;
    this.phi += (this.phiDesejado - this.phi) * k;
    this.raio += (this.raioDesejado - this.raio) * k;

    const s = Math.sin(this.phi);
    const p = arena.camera.position.set(
      this.alvo.x + this.raio * s * Math.sin(this.theta),
      this.alvo.y + this.raio * Math.cos(this.phi),
      this.alvo.z + this.raio * s * Math.cos(this.theta),
    );
    // nunca embaixo nem dentro de um objeto: chegando perto de um, a câmera
    // sobe por cima dele (e olha de cima), sem pulo
    p.y = Math.max(p.y, arena.alturaLivre(p.x, p.z));
    arena.camera.lookAt(this.alvo);
    // o plano de perto vai com a distância: de longe, a profundidade tem
    // precisão de sobra e nada "briga" (pisca) com o que está colado nele
    arena.ajustarPerto(limitar(p.distanceTo(this.alvo) * 0.012, 0.1, 0.6));
  }
}
