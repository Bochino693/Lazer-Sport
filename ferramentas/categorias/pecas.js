/* ======================================================================
   OS ENFEITES DAS FOTOS DAS CATEGORIAS (ver cenas.js e gerar.cjs).

   Só o que não é máquina: a bola de basquete, a de futebol, os pinos e a
   bola de boliche (o que diz a categoria de longe) e a estrela dourada do
   palco dos Famosos. AS MÁQUINAS SÃO SEMPRE AS DE VERDADE: o .glb nosso ou
   a foto do catálogo, recortada (recortar.py) -- o gabinete, o pinball, o
   simulador, o pebolim, o carrossel e a mini roda desenhados aqui saíram,
   a pedido do cliente ("não quero nenhuma máquina fake").

   Cada peça: um grupo com a base no chão (y = 0) e o meio em x = z = 0.
   ======================================================================

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
  /** Caixa de cantos arredondados (sem quina viva). */
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

  return { mat, caixa, cilindro, esfera, textura, sombra, bolaBasquete, bolaFutebol, bolaBoliche, pino, estrela };
}
