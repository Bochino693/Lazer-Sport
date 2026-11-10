/* ======================================================================
   AS PEÇAS DAS FOTOS DAS CATEGORIAS (ver cenas.js e gerar.cjs).

   As máquinas que ainda não têm objeto 3D (.glb) -- o gabinete de
   fliperama, o pinball, o simulador, o pebolim, o carrossel, a mini roda --
   e os enfeites que dizem a categoria de longe (a bola de basquete, a de
   futebol, os pinos e a bola de boliche). Feitas aqui, só para as fotos:
   silhuetas na medida das máquinas da fábrica, com as cores vivas do site
   e as telas desenhadas em canvas (sem texto e sem marca de ninguém: a
   foto não pode prometer um jogo licenciado nem repetir o nome do card).

   Cada peça: um grupo com a base no chão (y = 0), o meio em x = z = 0 e a
   frente (o lado de quem joga) em +z.
   ====================================================================== */

/* ---------------------------------------------------------------- canvas */

function canvas(l, a, desenhar) {
  const c = document.createElement("canvas");
  c.width = l;
  c.height = a;
  desenhar(c.getContext("2d"), l, a);
  return c;
}

function sorteio(semente) {
  let s = semente >>> 0 || 1;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

function estrelas(g, l, a, n, semente, cor = "#ffffff") {
  const r = sorteio(semente);
  g.fillStyle = cor;
  for (let i = 0; i < n; i++) {
    g.globalAlpha = 0.4 + r() * 0.6;
    g.beginPath();
    g.arc(r() * l, r() * a, 1 + r() * 2.2, 0, Math.PI * 2);
    g.fill();
  }
  g.globalAlpha = 1;
}

/** As telas dos jogos, desenhadas (sem texto): o que se vê de longe numa máquina ligada. */
export const ARTES = {
  // a corrida: o pôr do sol, as montanhas e a pista em perspectiva com o carro
  corrida: (g, l, a) => {
    const ceu = g.createLinearGradient(0, 0, 0, a * 0.55);
    ceu.addColorStop(0, "#1e1b4b");
    ceu.addColorStop(0.55, "#db2777");
    ceu.addColorStop(1, "#fb923c");
    g.fillStyle = ceu;
    g.fillRect(0, 0, l, a);
    g.fillStyle = "#fde047";
    g.beginPath();
    g.arc(l * 0.5, a * 0.5, a * 0.17, Math.PI, 0);
    g.fill();
    g.fillStyle = "#4c1d95";
    g.beginPath();
    g.moveTo(0, a * 0.55);
    for (let i = 0; i <= 8; i++) g.lineTo((l * i) / 8, a * (i % 2 ? 0.4 : 0.5));
    g.lineTo(l, a * 0.55);
    g.fill();
    g.fillStyle = "#14532d";
    g.fillRect(0, a * 0.55, l, a * 0.45);
    g.fillStyle = "#334155";
    g.beginPath();
    g.moveTo(l * 0.47, a * 0.55);
    g.lineTo(l * 0.53, a * 0.55);
    g.lineTo(l * 0.98, a);
    g.lineTo(l * 0.02, a);
    g.fill();
    for (const [x0, x1] of [[0.47, 0.02], [0.53, 0.98]]) {
      g.strokeStyle = "#f8fafc";
      g.lineWidth = l * 0.012;
      g.beginPath();
      g.moveTo(l * x0, a * 0.55);
      g.lineTo(l * x1, a);
      g.stroke();
    }
    g.strokeStyle = "#facc15";
    for (let i = 0; i < 5; i++) {
      const t0 = 0.58 + i * 0.09, t1 = t0 + 0.045;
      g.lineWidth = l * (0.004 + i * 0.004);
      g.beginPath();
      g.moveTo(l * 0.5, a * t0);
      g.lineTo(l * 0.5, a * t1);
      g.stroke();
    }
    // o carro, de costas
    const cx = l * 0.5, cy = a * 0.86, cl = l * 0.26;
    g.fillStyle = "#dc2626";
    g.beginPath();
    g.roundRect(cx - cl / 2, cy - a * 0.07, cl, a * 0.09, 12);
    g.fill();
    g.fillStyle = "#991b1b";
    g.beginPath();
    g.roundRect(cx - cl * 0.32, cy - a * 0.13, cl * 0.64, a * 0.07, 10);
    g.fill();
    g.fillStyle = "#0f172a";
    for (const s of [-1, 1]) g.fillRect(cx + s * cl * 0.36 - cl * 0.09, cy + a * 0.005, cl * 0.18, a * 0.05);
    g.fillStyle = "#fde047";
    for (const s of [-1, 1]) g.fillRect(cx + s * cl * 0.33 - cl * 0.06, cy - a * 0.045, cl * 0.12, a * 0.025);
  },
  // o espaço: estrelas, planetas e a nave atirando
  espaco: (g, l, a) => {
    const f = g.createRadialGradient(l * 0.5, a * 0.4, 10, l * 0.5, a * 0.5, l * 0.8);
    f.addColorStop(0, "#312e81");
    f.addColorStop(1, "#020617");
    g.fillStyle = f;
    g.fillRect(0, 0, l, a);
    estrelas(g, l, a, 140, 7);
    const planeta = (x, y, r, c1, c2) => {
      const p = g.createRadialGradient(x - r * 0.3, y - r * 0.3, r * 0.1, x, y, r);
      p.addColorStop(0, c1);
      p.addColorStop(1, c2);
      g.fillStyle = p;
      g.beginPath();
      g.arc(x, y, r, 0, Math.PI * 2);
      g.fill();
    };
    planeta(l * 0.78, a * 0.24, a * 0.13, "#fdba74", "#c2410c");
    g.strokeStyle = "#fde68a";
    g.lineWidth = a * 0.012;
    g.beginPath();
    g.ellipse(l * 0.78, a * 0.24, a * 0.22, a * 0.05, -0.3, 0, Math.PI * 2);
    g.stroke();
    planeta(l * 0.16, a * 0.7, a * 0.09, "#67e8f9", "#0e7490");
    // a nave
    g.fillStyle = "#e2e8f0";
    g.beginPath();
    g.moveTo(l * 0.5, a * 0.62);
    g.lineTo(l * 0.43, a * 0.84);
    g.lineTo(l * 0.57, a * 0.84);
    g.fill();
    g.fillStyle = "#38bdf8";
    g.beginPath();
    g.arc(l * 0.5, a * 0.74, a * 0.03, 0, Math.PI * 2);
    g.fill();
    g.strokeStyle = "#22d3ee";
    g.lineWidth = l * 0.012;
    for (const x of [0.47, 0.53]) {
      g.beginPath();
      g.moveTo(l * x, a * 0.6);
      g.lineTo(l * x, a * 0.3);
      g.stroke();
    }
    // os inimigos
    for (const [x, y, c] of [[0.3, 0.2, "#a3e635"], [0.45, 0.14, "#f472b6"], [0.6, 0.2, "#a3e635"]]) {
      g.fillStyle = c;
      g.beginPath();
      g.roundRect(l * x - a * 0.04, a * y - a * 0.025, a * 0.08, a * 0.05, 8);
      g.fill();
    }
  },
  // os blocos que caem: o fundo escuro e as peças em neon
  blocos: (g, l, a) => {
    g.fillStyle = "#0b1026";
    g.fillRect(0, 0, l, a);
    const t = Math.round(l / 10);
    const cores = ["#22d3ee", "#facc15", "#a855f7", "#22c55e", "#ef4444", "#f97316", "#3b82f6"];
    const r = sorteio(11);
    for (let y = a - t; y > a * 0.45; y -= t) {
      for (let x = 0; x < l; x += t) {
        if (r() < 0.18) continue;
        g.fillStyle = cores[Math.floor(r() * cores.length)];
        g.fillRect(x + 2, y + 2, t - 4, t - 4);
      }
    }
    g.fillStyle = "#a855f7";
    for (const [x, y] of [[4, 2], [5, 2], [6, 2], [5, 3]]) g.fillRect(x * t + 2, y * t + 2, t - 4, t - 4);
    g.strokeStyle = "rgba(148,163,184,.25)";
    g.lineWidth = 2;
    g.strokeRect(1, 1, l - 2, a - 2);
  },
  // o ritmo: os anéis de luz e as notas
  ritmo: (g, l, a) => {
    const f = g.createRadialGradient(l / 2, a / 2, 10, l / 2, a / 2, l * 0.7);
    f.addColorStop(0, "#4c1d95");
    f.addColorStop(1, "#0f0524");
    g.fillStyle = f;
    g.fillRect(0, 0, l, a);
    const cores = ["#f0abfc", "#22d3ee", "#facc15", "#4ade80"];
    for (let i = 0; i < 4; i++) {
      g.strokeStyle = cores[i];
      g.lineWidth = a * 0.025;
      g.shadowColor = cores[i];
      g.shadowBlur = 18;
      g.beginPath();
      g.arc(l / 2, a / 2, a * (0.12 + i * 0.1), 0, Math.PI * 2);
      g.stroke();
    }
    g.shadowBlur = 0;
    for (let i = 0; i < 8; i++) {
      const ang = (i / 8) * Math.PI * 2;
      g.fillStyle = cores[i % 4];
      g.beginPath();
      g.arc(l / 2 + Math.cos(ang) * a * 0.42, a / 2 + Math.sin(ang) * a * 0.42, a * 0.035, 0, Math.PI * 2);
      g.fill();
    }
  },
  // o campo de futebol visto do alto, com a bola
  futebol: (g, l, a) => {
    for (let i = 0; i < 8; i++) {
      g.fillStyle = i % 2 ? "#15803d" : "#16a34a";
      g.fillRect((l * i) / 8, 0, l / 8, a);
    }
    g.strokeStyle = "#f8fafc";
    g.lineWidth = a * 0.015;
    g.strokeRect(l * 0.05, a * 0.08, l * 0.9, a * 0.84);
    g.beginPath();
    g.moveTo(l / 2, a * 0.08);
    g.lineTo(l / 2, a * 0.92);
    g.stroke();
    g.beginPath();
    g.arc(l / 2, a / 2, a * 0.16, 0, Math.PI * 2);
    g.stroke();
    g.strokeRect(l * 0.05, a * 0.3, l * 0.1, a * 0.4);
    g.strokeRect(l * 0.85, a * 0.3, l * 0.1, a * 0.4);
    g.fillStyle = "#ffffff";
    g.beginPath();
    g.arc(l * 0.62, a * 0.42, a * 0.05, 0, Math.PI * 2);
    g.fill();
  },
  // a pista de boliche vista de quem joga
  boliche: (g, l, a) => {
    const f = g.createLinearGradient(0, 0, 0, a);
    f.addColorStop(0, "#1e3a8a");
    f.addColorStop(1, "#0f172a");
    g.fillStyle = f;
    g.fillRect(0, 0, l, a);
    g.fillStyle = "#f59e0b";
    g.beginPath();
    g.moveTo(l * 0.42, a * 0.3);
    g.lineTo(l * 0.58, a * 0.3);
    g.lineTo(l * 0.9, a);
    g.lineTo(l * 0.1, a);
    g.fill();
    g.fillStyle = "#fcd34d";
    for (let i = 0; i < 6; i++) {
      g.globalAlpha = 0.35;
      g.fillRect(l * (0.2 + i * 0.12), a * 0.62, l * 0.012, a * 0.38);
    }
    g.globalAlpha = 1;
    for (const [x, y] of [[0, 0], [-1, -1], [1, -1], [-2, -2], [0, -2], [2, -2]]) {
      g.fillStyle = "#ffffff";
      g.beginPath();
      g.ellipse(l * 0.5 + x * l * 0.022, a * 0.33 + y * a * 0.03, l * 0.012, a * 0.04, 0, 0, Math.PI * 2);
      g.fill();
      g.fillStyle = "#ef4444";
      g.fillRect(l * 0.5 + x * l * 0.022 - l * 0.011, a * 0.31 + y * a * 0.03, l * 0.022, a * 0.008);
    }
    g.fillStyle = "#7c3aed";
    g.beginPath();
    g.arc(l * 0.47, a * 0.8, a * 0.07, 0, Math.PI * 2);
    g.fill();
    estrelas(g, l, a * 0.25, 30, 3, "#facc15");
  },
  // o alvo do tiro: a mira e os alvos acesos
  tiro: (g, l, a) => {
    const f = g.createLinearGradient(0, 0, 0, a);
    f.addColorStop(0, "#111827");
    f.addColorStop(1, "#450a0a");
    g.fillStyle = f;
    g.fillRect(0, 0, l, a);
    for (const [x, y, r] of [[0.28, 0.4, 0.13], [0.7, 0.32, 0.1], [0.55, 0.7, 0.11]]) {
      for (let i = 4; i > 0; i--) {
        g.fillStyle = i % 2 ? "#ef4444" : "#f8fafc";
        g.beginPath();
        g.arc(l * x, a * y, a * r * (i / 4), 0, Math.PI * 2);
        g.fill();
      }
    }
    g.strokeStyle = "#22d3ee";
    g.lineWidth = a * 0.012;
    g.beginPath();
    g.arc(l * 0.55, a * 0.7, a * 0.17, 0, Math.PI * 2);
    g.moveTo(l * 0.55 - a * 0.24, a * 0.7);
    g.lineTo(l * 0.55 + a * 0.24, a * 0.7);
    g.moveTo(l * 0.55, a * 0.46);
    g.lineTo(l * 0.55, a * 0.94);
    g.stroke();
  },
};

/** O letreiro de cima (sem texto): a faixa acesa com o brilho e as estrelinhas. */
function arteLetreiro(cor1, cor2) {
  return (g, l, a) => {
    const f = g.createLinearGradient(0, 0, l, 0);
    f.addColorStop(0, cor1);
    f.addColorStop(0.5, cor2);
    f.addColorStop(1, cor1);
    g.fillStyle = f;
    g.fillRect(0, 0, l, a);
    const brilho = g.createRadialGradient(l / 2, a / 2, 4, l / 2, a / 2, l * 0.45);
    brilho.addColorStop(0, "rgba(255,255,255,.45)");
    brilho.addColorStop(1, "rgba(255,255,255,0)");
    g.fillStyle = brilho;
    g.fillRect(0, 0, l, a);
    estrelas(g, l, a, 26, 5, "#ffffff");
  };
}

/** A lateral do gabinete: as faixas em diagonal e as bolinhas (a adesivagem, sem desenho de ninguém). */
function arteLateral(cores) {
  return (g, l, a) => {
    g.fillStyle = cores[0];
    g.fillRect(0, 0, l, a);
    g.save();
    g.translate(l / 2, a / 2);
    g.rotate(-0.55);
    for (let i = -8; i < 8; i++) {
      g.fillStyle = cores[1 + (((i % (cores.length - 1)) + cores.length - 1) % (cores.length - 1))];
      g.fillRect(i * l * 0.16, -a, l * 0.07, a * 2);
    }
    g.restore();
    const r = sorteio(cores.join("").length);
    for (let i = 0; i < 24; i++) {
      g.fillStyle = "rgba(255,255,255,.55)";
      g.beginPath();
      g.arc(r() * l, r() * a, 3 + r() * 9, 0, Math.PI * 2);
      g.fill();
    }
  };
}

/* ---------------------------------------------------------------- as ferramentas */

export function criarPecas(T) {
  const mats = new Map();
  const mat = (cor, extra) => {
    const chave = cor + JSON.stringify(extra || {});
    if (!mats.has(chave)) mats.set(chave, new T.MeshStandardMaterial(Object.assign({ color: cor, roughness: 0.45, metalness: 0.05 }, extra || {})));
    return mats.get(chave);
  };
  const texturas = new Map();
  const textura = (chave, l, a, desenhar) => {
    if (!texturas.has(chave)) {
      const t = new T.CanvasTexture(canvas(l, a, desenhar));
      t.colorSpace = T.SRGBColorSpace;
      t.anisotropy = 8;
      texturas.set(chave, t);
    }
    return texturas.get(chave);
  };
  const tela = (arte) => {
    const t = textura("tela-" + arte, 512, 384, ARTES[arte] || ARTES.espaco);
    return new T.MeshStandardMaterial({ map: t, emissive: "#ffffff", emissiveMap: t, emissiveIntensity: 0.85, roughness: 0.25 });
  };
  const sombra = (m) => {
    m.traverse((o) => {
      if (o.isMesh) {
        o.castShadow = true;
        o.receiveShadow = true;
      }
    });
    return m;
  };
  const malha = (geo, m, x = 0, y = 0, z = 0) => {
    const o = new T.Mesh(geo, m);
    o.position.set(x, y, z);
    o.castShadow = true;
    o.receiveShadow = true;
    return o;
  };
  /** Caixa com a base em y (e não o meio). */
  const caixa = (g, l, a, p, m, x = 0, y = 0, z = 0, r = 0) => {
    const geo = r > 0 ? arredondada(l, a, p, r) : new T.BoxGeometry(l, a, p);
    const o = malha(geo, m, x, y + a / 2, z);
    g.add(o);
    return o;
  };
  /** Caixa de cantos arredondados (o gabinete de verdade não tem quina viva). */
  function arredondada(l, a, p, r) {
    // o chanfro cresce para fora do desenho: o desenho encolhe o tanto dele, e a peça fica na medida
    const chanfro = Math.min(r, p / 3);
    const lado = chanfro * 0.6;
    const s = new T.Shape();
    const L = l - 2 * lado, A = a - 2 * lado;
    const x0 = -L / 2, y0 = -A / 2;
    r = Math.max(0.001, Math.min(r - lado, L / 2 - 0.001, A / 2 - 0.001));
    s.moveTo(x0 + r, y0);
    s.lineTo(x0 + L - r, y0);
    s.quadraticCurveTo(x0 + L, y0, x0 + L, y0 + r);
    s.lineTo(x0 + L, y0 + A - r);
    s.quadraticCurveTo(x0 + L, y0 + A, x0 + L - r, y0 + A);
    s.lineTo(x0 + r, y0 + A);
    s.quadraticCurveTo(x0, y0 + A, x0, y0 + A - r);
    s.lineTo(x0, y0 + r);
    s.quadraticCurveTo(x0, y0, x0 + r, y0);
    const geo = new T.ExtrudeGeometry(s, { depth: p - 2 * chanfro, bevelEnabled: true, bevelSize: lado, bevelThickness: chanfro, bevelSegments: 4, curveSegments: 6 });
    geo.translate(0, 0, -(p - 2 * chanfro) / 2);
    return geo;
  }
  const cilindro = (g, r, a, m, x = 0, y = 0, z = 0, seg = 28, r2) => {
    const o = malha(new T.CylinderGeometry(r2 ?? r, r, a, seg), m, x, y + a / 2, z);
    g.add(o);
    return o;
  };
  const esfera = (g, r, m, x = 0, y = 0, z = 0) => {
    const o = malha(new T.SphereGeometry(r, 32, 20), m, x, y, z);
    g.add(o);
    return o;
  };
  /** Um plano com a tela, de frente para +z, inclinado para trás `incl` rad. */
  const plano = (g, l, a, m, x, y, z, incl = 0) => {
    const o = new T.Mesh(new T.PlaneGeometry(l, a), m);
    o.position.set(x, y, z);
    o.rotation.x = -incl;
    g.add(o);
    return o;
  };

  /* ------------------------------------------------------------ o gabinete de fliperama */
  /**
   * O gabinete em pé: o perfil clássico (base, o painel de comando que avança,
   * a tela inclinada e o letreiro aceso), as laterais adesivadas, a tela do jogo,
   * o manche e os botões. `kids`: mais baixo e mais redondo.
   */
  function gabinete({ cor = "#1d4ed8", cores = ["#1d4ed8", "#facc15", "#ef4444", "#22d3ee"], arte = "espaco", letreiro = ["#7c3aed", "#ec4899"], largura = 0.72, kids = false } = {}) {
    const g = new T.Group();
    const k = kids ? 0.8 : 1;
    // o perfil (z para a frente, y para cima), em metros
    const pts = [
      [-0.4, 0], [0.3, 0], [0.3, 0.78 * k], [0.44, 0.92 * k], [0.42, 0.99 * k], [0.21, 1.03 * k],
      [0.1, 1.55 * k], [0.23, 1.6 * k], [0.25, 1.86 * k], [-0.38, 1.86 * k], [-0.4, 1.7 * k],
    ];
    const perfil = new T.Shape(pts.map(([z, y]) => new T.Vector2(z, y)));
    const esp = 0.035;
    const lateral = textura("lat-" + cores.join() + k, 512, 1024, arteLateral(cores));
    lateral.repeat.set(1 / 0.85, 1 / (1.86 * k));
    lateral.offset.set(0.4 / 0.85, 0);
    const mLat = new T.MeshStandardMaterial({ map: lateral, roughness: 0.4 });
    for (const lado of [-1, 1]) {
      const geo = new T.ExtrudeGeometry(perfil, { depth: esp, bevelEnabled: true, bevelSize: 0.008, bevelThickness: 0.008, bevelSegments: 2 });
      const o = malha(geo, [mLat, mat(cores[1])]);
      o.rotation.y = -Math.PI / 2;
      o.position.x = lado > 0 ? largura / 2 + esp : -largura / 2;
      g.add(o);
    }
    // o corpo entre as laterais
    const corpo = new T.ExtrudeGeometry(perfil, { depth: largura - 0.004, bevelEnabled: false });
    const oc = malha(corpo, mat(cor, { roughness: 0.5 }));
    oc.rotation.y = -Math.PI / 2;
    oc.position.x = largura / 2 - 0.002;
    g.add(oc);
    // a moldura preta e a tela do jogo
    const [zt0, yt0] = [0.21, 1.03 * k], [zt1, yt1] = [0.1, 1.55 * k];
    const incl = Math.atan2(zt0 - zt1, yt1 - yt0);
    const altTela = Math.hypot(zt0 - zt1, yt1 - yt0);
    plano(g, largura * 0.98, altTela * 0.98, mat("#0b1020", { roughness: 0.2 }), 0, (yt0 + yt1) / 2, (zt0 + zt1) / 2 + 0.004, incl);
    plano(g, largura * 0.82, altTela * 0.78, tela(arte), 0, (yt0 + yt1) / 2 + 0.01, (zt0 + zt1) / 2 + 0.008, incl);
    // o letreiro aceso
    const tLet = textura("let-" + letreiro.join(), 512, 160, arteLetreiro(letreiro[0], letreiro[1]));
    const mLet = new T.MeshStandardMaterial({ map: tLet, emissive: "#ffffff", emissiveMap: tLet, emissiveIntensity: 0.55, roughness: 0.3 });
    const yl0 = 1.6 * k, yl1 = 1.84 * k;
    const inclLet = Math.atan2(0.25 - 0.23, yl1 - yl0);
    plano(g, largura * 0.96, (yl1 - yl0) * 0.92, mLet, 0, (yl0 + yl1) / 2, 0.245, -inclLet);
    // o painel de comando: o manche e os botões
    // (a tampa do painel sobe para trás: o manche e os botões acompanham)
    const painel = new T.Group();
    painel.position.set(0, 1.008 * k, 0.33);
    painel.rotation.x = Math.atan2(0.04 * k, 0.21);
    g.add(painel);
    for (const lado of [-1, 1]) {
      const x = lado * largura * 0.24;
      cilindro(painel, 0.012, 0.09, mat("#111827"), x - 0.06, 0, 0);
      esfera(painel, 0.032, mat("#ef4444", { roughness: 0.25 }), x - 0.06, 0.1, 0);
      const bot = ["#22c55e", "#facc15", "#3b82f6"];
      bot.forEach((c, i) => cilindro(painel, 0.022, 0.02, mat(c, { emissive: c, emissiveIntensity: 0.35 }), x + 0.03 + i * 0.05, 0, (i % 2) * 0.03 - 0.015, 20));
    }
    // a porta das fichas, com a luz
    caixa(g, 0.22, 0.24, 0.01, mat("#0f172a"), 0, 0.28 * k, 0.3);
    caixa(g, 0.05, 0.03, 0.012, mat("#f97316", { emissive: "#f97316", emissiveIntensity: 1 }), 0, 0.46 * k, 0.302);
    return sombra(g);
  }

  /* ------------------------------------------------------------ o pinball */
  function pinball({ cor = "#7c3aed", arte = "espaco", letreiro = ["#db2777", "#f59e0b"] } = {}) {
    const g = new T.Group();
    const L = 0.72, P = 1.3;
    for (const [x, z] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) cilindro(g, 0.03, 0.82, mat("#cbd5e1", { metalness: 0.7, roughness: 0.25 }), x * (L / 2 - 0.05), 0, z * (P / 2 - 0.08), 14);
    const corpo = new T.Group();
    corpo.position.set(0, 0.8, 0);
    corpo.rotation.x = 0.1;
    g.add(corpo);
    caixa(corpo, L, 0.22, P, mat(cor), 0, 0, 0, 0.03);
    // a mesa do jogo: o campo com os bumpers
    const mesa = textura("mesa-pinball", 384, 640, (c, l, a) => {
      const f = c.createLinearGradient(0, 0, 0, a);
      f.addColorStop(0, "#1e1b4b");
      f.addColorStop(1, "#7e22ce");
      c.fillStyle = f;
      c.fillRect(0, 0, l, a);
      estrelas(c, l, a, 60, 9);
      for (const [x, y, r, cc] of [[0.3, 0.28, 0.09, "#f43f5e"], [0.7, 0.28, 0.09, "#22d3ee"], [0.5, 0.42, 0.1, "#facc15"]]) {
        c.fillStyle = cc;
        c.beginPath();
        c.arc(l * x, a * y, l * r, 0, Math.PI * 2);
        c.fill();
        c.strokeStyle = "#fff";
        c.lineWidth = 6;
        c.stroke();
      }
      c.strokeStyle = "#f8fafc";
      c.lineWidth = 10;
      c.beginPath();
      c.moveTo(l * 0.18, a * 0.8);
      c.lineTo(l * 0.42, a * 0.9);
      c.moveTo(l * 0.82, a * 0.8);
      c.lineTo(l * 0.58, a * 0.9);
      c.stroke();
      c.fillStyle = "#cbd5e1";
      c.beginPath();
      c.arc(l * 0.5, a * 0.65, l * 0.04, 0, Math.PI * 2);
      c.fill();
    });
    const mMesa = new T.MeshStandardMaterial({ map: mesa, emissive: "#ffffff", emissiveMap: mesa, emissiveIntensity: 0.55, roughness: 0.2 });
    const tampo = new T.Mesh(new T.PlaneGeometry(L - 0.08, P - 0.08), mMesa);
    tampo.rotation.x = -Math.PI / 2;
    tampo.position.y = 0.221;
    corpo.add(tampo);
    // o vidro
    const vidro = new T.Mesh(new T.PlaneGeometry(L - 0.06, P - 0.06), new T.MeshStandardMaterial({ color: "#e0f2fe", transparent: true, opacity: 0.18, roughness: 0.02, metalness: 0.1 }));
    vidro.rotation.x = -Math.PI / 2;
    vidro.position.y = 0.235;
    corpo.add(vidro);
    // o backbox com a tela e o letreiro
    const back = new T.Group();
    back.position.set(0, 0.78, -P / 2 + 0.12);
    g.add(back);
    caixa(back, L, 0.75, 0.2, mat(cor), 0, 0.2, 0, 0.03);
    plano(back, L * 0.84, 0.48, tela(arte), 0, 0.62, 0.105);
    const tLet = textura("let-" + letreiro.join(), 512, 160, arteLetreiro(letreiro[0], letreiro[1]));
    plano(back, L * 0.9, 0.14, new T.MeshStandardMaterial({ map: tLet, emissive: "#fff", emissiveMap: tLet, emissiveIntensity: 0.55 }), 0, 0.88, 0.105);
    // os botões da frente
    for (const s of [-1, 1]) cilindro(g, 0.02, 0.02, mat("#facc15", { emissive: "#facc15", emissiveIntensity: 0.6 }), s * (L / 2 + 0.005), 0.92, P / 2 - 0.12).rotation.z = Math.PI / 2;
    return sombra(g);
  }

  /* ------------------------------------------------------------ o simulador de corrida */
  function simulador({ cor = "#dc2626", cor2 = "#111827", arte = "corrida", letreiro = ["#dc2626", "#f97316"] } = {}) {
    const g = new T.Group();
    // a base e o banco concha
    caixa(g, 0.95, 0.18, 1.85, mat(cor2), 0, 0, 0, 0.04);
    caixa(g, 0.62, 0.16, 0.95, mat(cor, { roughness: 0.35, metalness: 0.2 }), 0, 0.18, 0.25, 0.05);
    const banco = new T.Group();
    banco.position.set(0, 0.34, 0.45);
    g.add(banco);
    caixa(banco, 0.5, 0.12, 0.5, mat("#0f172a"), 0, 0, 0, 0.05);
    const encosto = caixa(banco, 0.46, 0.58, 0.1, mat("#0f172a"), 0, 0.05, 0.24, 0.045);
    encosto.rotation.x = -0.3;
    for (const s of [-1, 1]) caixa(banco, 0.05, 0.5, 0.12, mat(cor), s * 0.235, 0.1, 0.23, 0.02).rotation.x = -0.3;
    // a coluna do volante
    caixa(g, 0.26, 0.5, 0.2, mat(cor2), 0, 0.18, -0.1, 0.03);
    const volante = malha(new T.TorusGeometry(0.15, 0.022, 12, 36), mat("#111827"), 0, 0.82, 0.02);
    volante.rotation.x = -0.75;
    g.add(volante);
    // o gabinete da tela, de pé atrás
    const tv = new T.Group();
    tv.position.set(0, 0.18, -0.68);
    g.add(tv);
    caixa(tv, 0.95, 1.55, 0.42, mat(cor, { roughness: 0.35, metalness: 0.15 }), 0, 0, 0, 0.05);
    plano(tv, 0.88, 0.66, mat("#0b1020", { roughness: 0.2 }), 0, 0.98, 0.215, 0.12);
    plano(tv, 0.82, 0.6, tela(arte), 0, 0.98, 0.222, 0.12);
    const tLet = textura("let-" + letreiro.join(), 512, 160, arteLetreiro(letreiro[0], letreiro[1]));
    plano(tv, 0.9, 0.16, new T.MeshStandardMaterial({ map: tLet, emissive: "#fff", emissiveMap: tLet, emissiveIntensity: 0.55 }), 0, 1.43, 0.215);
    // as faixas de corrida nas laterais
    for (const s of [-1, 1]) caixa(g, 0.004, 0.05, 1.5, mat("#f8fafc"), s * 0.476, 0.07, 0);
    return sombra(g);
  }

  /* ------------------------------------------------------------ o pebolim */
  function pebolim({ cor = "#1e3a8a", time1 = "#ef4444", time2 = "#facc15" } = {}) {
    const g = new T.Group();
    const L = 0.78, P = 1.32, A = 0.92, E = 0.04, fundo = A - 0.26;
    for (const [x, z] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) caixa(g, 0.09, fundo, 0.09, mat(cor), x * (L / 2 - 0.08), 0, z * (P / 2 - 0.1), 0.01);
    // a caixa aberta: o fundo com o campo e as quatro paredes
    caixa(g, L, 0.05, P, mat(cor), 0, fundo, 0);
    for (const s of [-1, 1]) {
      caixa(g, E, A - fundo, P, mat(cor), s * (L / 2 - E / 2), fundo, 0, 0.012);
      caixa(g, L, A - fundo, E, mat(cor), 0, fundo, s * (P / 2 - E / 2), 0.012);
    }
    const campo = textura("campo-pebolim", 256, 420, (c, l, a) => {
      for (let i = 0; i < 6; i++) {
        c.fillStyle = i % 2 ? "#15803d" : "#16a34a";
        c.fillRect(0, (a * i) / 6, l, a / 6);
      }
      c.strokeStyle = "#fff";
      c.lineWidth = 5;
      c.strokeRect(8, 8, l - 16, a - 16);
      c.beginPath();
      c.moveTo(8, a / 2);
      c.lineTo(l - 8, a / 2);
      c.stroke();
      c.beginPath();
      c.arc(l / 2, a / 2, l * 0.18, 0, Math.PI * 2);
      c.stroke();
    });
    const f = new T.Mesh(new T.PlaneGeometry(L - 2 * E, P - 2 * E), new T.MeshStandardMaterial({ map: campo, roughness: 0.7 }));
    f.rotation.x = -Math.PI / 2;
    f.position.y = fundo + 0.051;
    f.receiveShadow = true;
    g.add(f);
    // as varetas atravessadas, com os bonequinhos pendurados até perto do campo
    const metal = mat("#e5e7eb", { metalness: 0.85, roughness: 0.2 });
    const yv = A - 0.06;
    const bonecos = [1, 2, 3, 5, 5, 3, 2, 1];
    for (let i = 0; i < 8; i++) {
      const z = -P / 2 + 0.12 + (i * (P - 0.24)) / 7;
      const v = malha(new T.CylinderGeometry(0.008, 0.008, L + 0.36, 10), metal, 0, yv, z);
      v.rotation.z = Math.PI / 2;
      g.add(v);
      const lado = i % 2 ? 1 : -1;
      const pega = malha(new T.CylinderGeometry(0.022, 0.022, 0.12, 14), mat("#111827"), lado * (L / 2 + 0.2), yv, z);
      pega.rotation.z = Math.PI / 2;
      g.add(pega);
      const time = [0, 1, 3, 5].includes(i) ? time1 : time2;
      const n = bonecos[i];
      for (let j = 0; j < n; j++) {
        const x = n === 1 ? 0 : -L * 0.3 + (j * L * 0.6) / (n - 1);
        caixa(g, 0.045, 0.13, 0.03, mat(time), x, yv - 0.11, z, 0.008);
        esfera(g, 0.022, mat("#fde68a"), x, yv + 0.035, z);
      }
    }
    esfera(g, 0.02, mat("#ffffff"), 0.06, fundo + 0.07, 0.04);
    return sombra(g);
  }

  /* ------------------------------------------------------------ a mesa de fliperama (de sentar) */
  function mesaArcade({ cor = "#0f766e", arte = "blocos" } = {}) {
    const g = new T.Group();
    caixa(g, 0.5, 0.62, 0.5, mat(cor), 0, 0, 0, 0.04);
    caixa(g, 0.82, 0.1, 0.72, mat(cor), 0, 0.62, 0, 0.04);
    const t = new T.Mesh(new T.PlaneGeometry(0.52, 0.4), tela(arte));
    t.rotation.x = -Math.PI / 2;
    t.position.y = 0.724;
    g.add(t);
    const vidro = new T.Mesh(new T.PlaneGeometry(0.78, 0.68), new T.MeshStandardMaterial({ color: "#e0f2fe", transparent: true, opacity: 0.16, roughness: 0.02 }));
    vidro.rotation.x = -Math.PI / 2;
    vidro.position.y = 0.73;
    g.add(vidro);
    for (const s of [-1, 1]) {
      cilindro(g, 0.01, 0.06, mat("#111827"), 0, 0.72, s * 0.31);
      esfera(g, 0.022, mat("#facc15"), 0, 0.79, s * 0.31);
    }
    return sombra(g);
  }

  /* ------------------------------------------------------------ o carrossel infantil */
  function carrossel({ cores = ["#f9a8d4", "#a7f3d0", "#fde68a", "#bfdbfe", "#fdba74", "#c4b5fd"], base = "#f472b6", teto = ["#fb7185", "#fff7ed"] } = {}) {
    const g = new T.Group();
    const R = 1.25;
    cilindro(g, R, 0.24, mat(base), 0, 0, 0, 48);
    cilindro(g, R * 0.97, 0.03, mat("#fff7ed"), 0, 0.24, 0, 48);
    cilindro(g, 0.1, 2.0, mat("#fde68a", { metalness: 0.4, roughness: 0.3 }), 0, 0.24, 0);
    // o teto listrado, com a borda de gomos
    const listras = textura("teto-" + teto.join(), 512, 64, (c, l, a) => {
      for (let i = 0; i < 16; i++) {
        c.fillStyle = teto[i % 2];
        c.fillRect((l * i) / 16, 0, l / 16, a);
      }
    });
    listras.wrapS = T.RepeatWrapping;
    const cone = malha(new T.ConeGeometry(R * 1.08, 0.75, 48, 1, true), new T.MeshStandardMaterial({ map: listras, side: T.DoubleSide, roughness: 0.5 }), 0, 2.48 + 0.375, 0);
    g.add(cone);
    for (let i = 0; i < 24; i++) {
      const ang = (i / 24) * Math.PI * 2;
      esfera(g, 0.11, mat(teto[i % 2]), Math.cos(ang) * R * 1.06, 2.44, Math.sin(ang) * R * 1.06).scale.set(1, 0.7, 0.5);
      esfera(g, 0.035, mat("#fef9c3", { emissive: "#fde047", emissiveIntensity: 1.2 }), Math.cos(ang + 0.13) * R * 1.07, 2.52, Math.sin(ang + 0.13) * R * 1.07);
    }
    esfera(g, 0.13, mat("#fde68a", { metalness: 0.5, roughness: 0.3 }), 0, 3.3, 0);
    // as xícaras de sorvete nos postes
    for (let i = 0; i < 6; i++) {
      const ang = (i / 6) * Math.PI * 2 + 0.3;
      const x = Math.cos(ang) * R * 0.68, z = Math.sin(ang) * R * 0.68;
      cilindro(g, 0.02, 2.2, mat("#fde68a", { metalness: 0.5, roughness: 0.3 }), x, 0.27, z, 10);
      const c = cores[i % cores.length];
      cilindro(g, 0.24, 0.32, mat(c), x, 0.42, z, 28, 0.32);
      cilindro(g, 0.3, 0.05, mat("#ffffff"), x, 0.74, z, 28);
      esfera(g, 0.14, mat(cores[(i + 2) % cores.length]), x, 0.83, z).scale.set(1, 0.8, 1);
    }
    return sombra(g);
  }

  /* ------------------------------------------------------------ a mini roda-gigante */
  function rodaGigante({ cores = ["#f9a8d4", "#a7f3d0", "#fde68a", "#bfdbfe", "#fdba74", "#c4b5fd", "#fca5a5", "#99f6e4"], estrutura = "#38bdf8" } = {}) {
    const g = new T.Group();
    const R = 1.05, eixo = 1.45;
    caixa(g, 1.6, 0.18, 1.0, mat("#f472b6"), 0, 0, 0, 0.05);
    const mEst = mat(estrutura, { roughness: 0.35, metalness: 0.25 });
    for (const s of [-1, 1]) {
      for (const lado of [-1, 1]) {
        const perna = malha(new T.CylinderGeometry(0.035, 0.045, eixo + 0.1, 12), mEst, lado * 0.42, 0.18 + eixo / 2 - 0.02, s * 0.28);
        perna.rotation.z = lado * -0.28;
        g.add(perna);
      }
    }
    const roda = new T.Group();
    roda.position.set(0, 0.18 + eixo, 0);
    g.add(roda);
    for (const s of [-1, 1]) {
      const aro = malha(new T.TorusGeometry(R, 0.03, 10, 64), mEst, 0, 0, s * 0.26);
      roda.add(aro);
      for (let i = 0; i < 8; i++) {
        const raio = malha(new T.CylinderGeometry(0.014, 0.014, R, 8), mat("#e0f2fe"), 0, 0, s * 0.26);
        raio.rotation.z = (i / 8) * Math.PI * 2;
        raio.translateY(R / 2);
        roda.add(raio);
      }
    }
    const cubo = malha(new T.CylinderGeometry(0.09, 0.09, 0.62, 20), mat("#fde68a", { metalness: 0.5 }), 0, 0, 0);
    cubo.rotation.x = Math.PI / 2;
    roda.add(cubo);
    for (let i = 0; i < 8; i++) {
      const ang = (i / 8) * Math.PI * 2;
      const x = Math.cos(ang) * R, y = Math.sin(ang) * R;
      const barra = malha(new T.CylinderGeometry(0.012, 0.012, 0.62, 8), mat("#e0f2fe"), x, y, 0);
      barra.rotation.x = Math.PI / 2;
      roda.add(barra);
      const c = cores[i % cores.length];
      const gondola = new T.Group();
      gondola.position.set(x, y - 0.24, 0);
      roda.add(gondola);
      cilindro(gondola, 0.15, 0.2, mat(c), 0, -0.04, 0, 24, 0.2);
      cilindro(gondola, 0.012, 0.22, mat("#e0f2fe"), 0, 0.1, 0, 8);
      const capota = malha(new T.SphereGeometry(0.17, 24, 10, 0, Math.PI * 2, 0, Math.PI / 2), mat(cores[(i + 3) % cores.length]), 0, 0.3, 0);
      gondola.add(capota);
      esfera(roda, 0.03, mat("#fef9c3", { emissive: "#fde047", emissiveIntensity: 1.3 }), Math.cos(ang + 0.39) * R, Math.sin(ang + 0.39) * R, 0.29);
    }
    return sombra(g);
  }

  /* ------------------------------------------------------------ o gol de LED (o Gol Flash) */
  function golLed({ cor = "#111827", aneis = ["#ef4444", "#22c55e", "#3b82f6", "#facc15", "#ec4899"] } = {}) {
    const g = new T.Group();
    const L = 2.4, A = 1.7;
    caixa(g, L + 0.2, 0.1, 1.6, mat("#16a34a", { roughness: 0.9 }), 0, 0, 0.1);
    caixa(g, L, A, 0.12, mat(cor), 0, 0.1, -0.6, 0.03);
    for (const s of [-1, 1]) caixa(g, 0.1, A + 0.1, 0.1, mat("#f8fafc"), s * (L / 2 + 0.05), 0.1, -0.5);
    caixa(g, L + 0.2, 0.1, 0.1, mat("#f8fafc"), 0, A + 0.1, -0.5);
    aneis.forEach((c, i) => {
      const x = -L / 2 + 0.32 + (i * (L - 0.64)) / (aneis.length - 1);
      const y = 0.1 + (i % 2 ? 0.55 : 1.15);
      const anel = malha(new T.TorusGeometry(0.2, 0.035, 12, 40), mat(c, { emissive: c, emissiveIntensity: 1.4 }), x, y, -0.53);
      g.add(anel);
    });
    return sombra(g);
  }

  /* ------------------------------------------------------------ as bolas, os pinos */
  function bolaBasquete(r = 0.12) {
    const t = textura("basquete", 512, 256, (c, l, a) => {
      c.fillStyle = "#ea580c";
      c.fillRect(0, 0, l, a);
      c.strokeStyle = "#1c1917";
      c.lineWidth = 7;
      c.beginPath();
      c.moveTo(0, a / 2);
      c.lineTo(l, a / 2);
      for (const x of [0.25, 0.75]) {
        c.moveTo(l * x, 0);
        c.lineTo(l * x, a);
      }
      c.stroke();
      c.beginPath();
      c.ellipse(l * 0.5, a / 2, l * 0.12, a * 0.5, 0, 0, Math.PI * 2);
      c.ellipse(0, a / 2, l * 0.12, a * 0.5, 0, 0, Math.PI * 2);
      c.ellipse(l, a / 2, l * 0.12, a * 0.5, 0, 0, Math.PI * 2);
      c.stroke();
    });
    const o = malha(new T.SphereGeometry(r, 48, 32), new T.MeshStandardMaterial({ map: t, roughness: 0.7 }), 0, r, 0);
    const g = new T.Group();
    g.add(o);
    return g;
  }
  function bolaFutebol(r = 0.11) {
    const t = textura("futebol", 512, 256, (c, l, a) => {
      c.fillStyle = "#f8fafc";
      c.fillRect(0, 0, l, a);
      c.fillStyle = "#111827";
      const r0 = sorteio(4);
      for (let y = 0; y < 4; y++) {
        for (let x = 0; x < 6; x++) {
          const cx = (l * (x + (y % 2) * 0.5)) / 6, cy = (a * (y + 0.5)) / 4;
          c.beginPath();
          for (let k = 0; k < 5; k++) {
            const ang = (k / 5) * Math.PI * 2 + r0() * 0.2;
            c.lineTo(cx + Math.cos(ang) * l * 0.035, cy + Math.sin(ang) * a * 0.07);
          }
          c.fill();
        }
      }
    });
    const o = malha(new T.SphereGeometry(r, 48, 32), new T.MeshStandardMaterial({ map: t, roughness: 0.5 }), 0, r, 0);
    const g = new T.Group();
    g.add(o);
    return g;
  }
  function bolaBoliche(cor = "#7c3aed", r = 0.11) {
    const g = new T.Group();
    const o = malha(new T.SphereGeometry(r, 48, 32), new T.MeshPhysicalMaterial({ color: cor, roughness: 0.12, metalness: 0.1, clearcoat: 1, clearcoatRoughness: 0.05 }), 0, r, 0);
    g.add(o);
    for (const [dx, dy] of [[-0.025, 0.05], [0.025, 0.05], [0, 0.0]]) {
      const furo = malha(new T.CircleGeometry(r * 0.12, 16), mat("#0b0b10"), dx, r + dy * 0.9, r * 0.98);
      furo.lookAt(dx * 3, r + dy * 3, r * 3);
      g.add(furo);
    }
    return g;
  }
  function pino(a = 0.38) {
    const k = a / 0.38;
    const perfil = [[0, 0], [0.028, 0], [0.04, 0.03], [0.055, 0.1], [0.058, 0.14], [0.05, 0.19], [0.032, 0.25], [0.026, 0.28], [0.03, 0.31], [0.034, 0.34], [0.03, 0.365], [0.018, 0.378], [0, 0.38]];
    const geo = new T.LatheGeometry(perfil.map(([x, y]) => new T.Vector2(x * k, y * k)), 32);
    const t = textura("pino", 64, 256, (c, l, aa) => {
      c.fillStyle = "#ffffff";
      c.fillRect(0, 0, l, aa);
      c.fillStyle = "#dc2626";
      c.fillRect(0, aa * 0.23, l, aa * 0.035);
      c.fillRect(0, aa * 0.29, l, aa * 0.035);
    });
    const g = new T.Group();
    g.add(malha(geo, new T.MeshPhysicalMaterial({ map: t, roughness: 0.18, clearcoat: 0.8 })));
    return g;
  }
  /** A estrela dourada (o enfeite dos famosos), de pé, virada para +z. */
  function estrela(r = 0.3, cor = "#fbbf24", esp = 0.06) {
    const s = new T.Shape();
    for (let i = 0; i < 10; i++) {
      const ang = Math.PI / 2 + (i / 10) * Math.PI * 2;
      const rr = i % 2 ? r * 0.45 : r;
      if (i === 0) s.moveTo(Math.cos(ang) * rr, Math.sin(ang) * rr);
      else s.lineTo(Math.cos(ang) * rr, Math.sin(ang) * rr);
    }
    const geo = new T.ExtrudeGeometry(s, { depth: esp, bevelEnabled: true, bevelSize: esp * 0.4, bevelThickness: esp * 0.4, bevelSegments: 3 });
    geo.translate(0, 0, -esp / 2);
    const g = new T.Group();
    g.add(malha(geo, mat(cor, { metalness: 0.7, roughness: 0.25, emissive: cor, emissiveIntensity: 0.12 })));
    return g;
  }

  return {
    mat, caixa, cilindro, esfera, textura, sombra,
    gabinete, pinball, simulador, pebolim, mesaArcade, carrossel, rodaGigante, golLed,
    bolaBasquete, bolaFutebol, bolaBoliche, pino, estrela,
  };
}
