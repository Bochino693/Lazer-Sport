/* ======================================================================
   O MINI 3D das máquinas sem objeto 3D (.glb), para o "Monte seu projeto".

   Cada desenho do core/arena.py (fliperama, basquete, boliche, tiro,
   garra, hockey...) ganha a silhueta dele na MEDIDA DO CADASTRO, com a
   foto da máquina na frente (a capa do catálogo), para o cliente ver o
   lugar que ela ocupa e reconhecer qual é. Não é o objeto 3D de verdade
   -- esse é o .glb do cadastro, que vence sempre que existe.

   Cada desenho: um grupo com a base no chão (y = 0), o meio em x = z = 0,
   a largura no x, o fundo no z e a frente (o lado de quem joga) em +z.
   ====================================================================== */

const texturas = new Map();

/** A foto da máquina como textura (uma por endereço; carrega depois, sem travar). */
function foto(T, url) {
  if (!url) return null;
  if (!texturas.has(url)) {
    const t = new T.TextureLoader().load(url, (tex) => { tex.needsUpdate = true; if (foto.aoCarregar) foto.aoCarregar(); });
    t.colorSpace = T.SRGBColorSpace;
    t.anisotropy = 4;
    texturas.set(url, t);
  }
  return texturas.get(url);
}

export function criarMaquinas(T, aoCarregar) {
  foto.aoCarregar = aoCarregar;
  const mats = new Map();
  const mat = (cor, extra) => {
    const chave = cor + JSON.stringify(extra || {});
    if (!mats.has(chave)) mats.set(chave, new T.MeshStandardMaterial(Object.assign({ color: cor, roughness: 0.55, metalness: 0.08 }, extra || {})));
    return mats.get(chave);
  };
  const caixa = (g, l, a, p, m, x, y, z) => {
    const malha = new T.Mesh(new T.BoxGeometry(Math.max(l, 0.01), Math.max(a, 0.01), Math.max(p, 0.01)), m);
    malha.position.set(x || 0, (y || 0) + a / 2, z || 0);
    malha.castShadow = true;
    malha.receiveShadow = true;
    g.add(malha);
    return malha;
  };
  const cilindro = (g, r, a, m, x, y, z, seg = 20) => {
    const malha = new T.Mesh(new T.CylinderGeometry(r, r, a, seg), m);
    malha.position.set(x || 0, (y || 0) + a / 2, z || 0);
    malha.castShadow = true;
    g.add(malha);
    return malha;
  };
  /** A foto num painel: na frente da máquina, de pé ou deitada (com a borda escura). */
  const painelDeFoto = (g, url, l, a, x, y, z, deitado) => {
    const tex = foto(T, url);
    const m = tex ? new T.MeshStandardMaterial({ map: tex, roughness: 0.6, emissive: "#ffffff", emissiveMap: tex, emissiveIntensity: 0.25 })
      : mat("#1e293b", { emissive: "#3fd0ff", emissiveIntensity: 0.35 });
    const plano = new T.Mesh(new T.PlaneGeometry(l, a), m);
    if (deitado) { plano.rotation.x = -Math.PI / 2; plano.position.set(x, y, z); }
    else plano.position.set(x, y + a / 2, z);
    g.add(plano);
    return plano;
  };
  const corpoCor = (cor) => mat(cor || "#1f2937", { roughness: 0.45 });
  const metal = mat("#9ca3af", { metalness: 0.5, roughness: 0.35 });
  const preto = mat("#0f172a", { roughness: 0.4 });
  const luz = (cor) => mat(cor, { emissive: cor, emissiveIntensity: 0.9 });

  /* Os desenhos: (g, w, h, d, ficha) -- ficha: { capa, cor } */
  const D = {
    // o gabinete: corpo, tela inclinada com a foto, painel de comando e o letreiro
    fliperama(g, w, h, d, f) {
      caixa(g, w, h * 0.92, d * 0.9, corpoCor(f.cor), 0, 0, -d * 0.05);
      caixa(g, w * 1.02, h * 0.08, d * 0.5, luz(f.cor || "#3fd0ff"), 0, h * 0.92, -d * 0.2);
      caixa(g, w * 0.96, 0.08, d * 0.32, preto, 0, h * 0.46, d * 0.3);
      painelDeFoto(g, f.capa, w * 0.86, h * 0.42, 0, h * 0.5, d * 0.41);
    },
    tiro(g, w, h, d, f) {
      D.fliperama(g, w, h, d, f);
      // as armas no balcão
      for (const lado of [-1, 1]) caixa(g, 0.07, 0.07, 0.3, mat("#f97316"), lado * w * 0.25, h * 0.5, d * 0.38);
    },
    musica(g, w, h, d, f) {
      caixa(g, w, h, d * 0.35, corpoCor(f.cor), 0, 0, -d * 0.32);
      painelDeFoto(g, f.capa, w * 0.86, h * 0.45, 0, h * 0.42, -d * 0.14);
      // o tablado de dançar com as setas
      caixa(g, w, 0.12, d * 0.6, preto, 0, 0, d * 0.2);
      for (const [x, z, c] of [[-0.25, 0, "#ef4444"], [0.25, 0, "#2563eb"], [0, -0.22, "#22c55e"], [0, 0.22, "#facc15"]]) {
        caixa(g, w * 0.22, 0.02, d * 0.14, luz(c), x * w, 0.12, d * 0.2 + z * d * 0.6);
      }
    },
    // a pista que sobe até a tabela, com a rede em volta e a foto em cima
    basquete(g, w, h, d, f) {
      caixa(g, w, 0.9, d * 0.75, corpoCor(f.cor), 0, 0, d * 0.12);
      const rampa = caixa(g, w * 0.92, 0.04, d * 0.78, mat("#c2410c"), 0, 0.9, d * 0.1);
      rampa.rotation.x = -0.12;
      caixa(g, w, h * 0.55, 0.12, corpoCor(f.cor), 0, h * 0.45, -d / 2 + 0.06);
      painelDeFoto(g, f.capa, w * 0.7, h * 0.3, 0, h * 0.62, -d / 2 + 0.13);
      const aro = new T.Mesh(new T.TorusGeometry(Math.min(0.22, w * 0.2), 0.015, 8, 24), mat("#f97316"));
      aro.rotation.x = Math.PI / 2;
      aro.position.set(0, h * 0.58, -d / 2 + 0.35);
      g.add(aro);
    },
    // a pista comprida com a tela no fim
    boliche(g, w, h, d, f) {
      caixa(g, w, 0.75, d, corpoCor(f.cor), 0, 0, 0);
      caixa(g, w * 0.8, 0.02, d * 0.92, mat("#e5c38a", { roughness: 0.3 }), 0, 0.75, 0);
      caixa(g, w, h - 0.75, 0.25, corpoCor(f.cor), 0, 0.75, -d / 2 + 0.125);
      painelDeFoto(g, f.capa, w * 0.86, (h - 0.75) * 0.8, 0, 0.85, -d / 2 + 0.26);
      for (let i = 0; i < 4; i++) cilindro(g, 0.03, 0.14, mat("#ffffff"), (i - 1.5) * w * 0.15, 0.77, -d / 2 + 0.45);
    },
    futebol(g, w, h, d, f) {
      caixa(g, w, 0.05, d, mat("#16a34a"), 0, 0, 0);
      caixa(g, w, h, 0.15, preto, 0, 0, -d / 2 + 0.075);
      painelDeFoto(g, f.capa, w * 0.6, h * 0.45, 0, h * 0.3, -d / 2 + 0.16);
      for (const lado of [-1, 1]) caixa(g, 0.06, h * 0.7, 0.06, metal, lado * w * 0.45, 0, -d / 2 + 0.25);
    },
    garra(g, w, h, d, f) {
      caixa(g, w, h * 0.42, d, corpoCor(f.cor), 0, 0, 0);
      const vidro = new T.Mesh(new T.BoxGeometry(w * 0.94, h * 0.45, d * 0.94), mat("#bfdbfe", { transparent: true, opacity: 0.25, roughness: 0.05 }));
      vidro.position.set(0, h * 0.42 + h * 0.225, 0);
      g.add(vidro);
      caixa(g, w, h * 0.13, d, luz(f.cor || "#ec4899"), 0, h * 0.87, 0);
      painelDeFoto(g, f.capa, w * 0.8, h * 0.32, 0, h * 0.04, d / 2 + 0.005);
      for (let i = 0; i < 6; i++) {
        const b = new T.Mesh(new T.SphereGeometry(0.07, 10, 8), mat(["#ef4444", "#facc15", "#22c55e", "#3b82f6", "#ec4899", "#f97316"][i]));
        b.position.set((i % 3 - 1) * w * 0.25, h * 0.46, (Math.floor(i / 3) - 0.5) * d * 0.4);
        g.add(b);
      }
    },
    boxe(g, w, h, d, f) {
      caixa(g, w, h * 0.85, d * 0.45, corpoCor(f.cor), 0, 0, -d * 0.27);
      painelDeFoto(g, f.capa, w * 0.8, h * 0.35, 0, h * 0.45, -d * 0.04);
      const saco = new T.Mesh(new T.SphereGeometry(Math.min(0.2, w * 0.22), 16, 12), mat("#dc2626"));
      saco.position.set(0, h * 0.5, d * 0.2);
      saco.castShadow = true;
      g.add(saco);
      caixa(g, w * 0.3, 0.05, 0.4, metal, 0, h * 0.62, d * 0.05);
    },
    simulador(g, w, h, d, f) {
      caixa(g, w, 0.3, d, preto, 0, 0, 0);
      caixa(g, w * 0.6, 0.55, d * 0.35, corpoCor(f.cor), 0, 0.3, d * 0.22);
      caixa(g, w * 0.6, 0.6, 0.12, corpoCor(f.cor), 0, 0.55, d * 0.4);
      caixa(g, w, h - 0.3, d * 0.22, corpoCor(f.cor), 0, 0.3, -d / 2 + d * 0.11);
      painelDeFoto(g, f.capa, w * 0.86, (h - 0.3) * 0.5, 0, 0.3 + (h - 0.3) * 0.38, -d / 2 + d * 0.225);
      const volante = new T.Mesh(new T.TorusGeometry(0.16, 0.025, 8, 24), preto);
      volante.position.set(0, 0.95, -d * 0.12);
      volante.rotation.x = -0.6;
      g.add(volante);
    },
    pinball(g, w, h, d, f) {
      for (const [x, z] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) caixa(g, 0.05, 0.85, 0.05, metal, x * (w / 2 - 0.05), 0, z * (d / 2 - 0.05));
      const mesa = caixa(g, w, 0.18, d, corpoCor(f.cor), 0, 0.82, 0);
      mesa.rotation.x = 0.1;
      painelDeFoto(g, f.capa, w * 0.86, d * 0.86, 0, 1.02, 0, true).rotation.set(-Math.PI / 2 + 0.1, 0, 0);
      caixa(g, w, h - 0.9, 0.18, corpoCor(f.cor), 0, 0.9, -d / 2 + 0.09);
    },
    // as mesas: o tampo com a foto, por cima
    hockey(g, w, h, d, f) {
      caixa(g, w, h * 0.85, d, corpoCor(f.cor), 0, 0, 0);
      caixa(g, w * 0.94, 0.03, d * 0.96, mat("#e0f2fe", { roughness: 0.15 }), 0, h * 0.85, 0);
      painelDeFoto(g, f.capa, w * 0.9, h * 0.6, 0, h * 0.1, d / 2 + 0.005);
      for (const z of [-1, 1]) cilindro(g, 0.05, 0.05, mat("#ef4444"), 0, h * 0.88, z * d * 0.32);
    },
    pebolim(g, w, h, d, f) {
      for (const [x, z] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) caixa(g, 0.08, h * 0.65, 0.08, corpoCor(f.cor), x * (w / 2 - 0.08), 0, z * (d / 2 - 0.1));
      caixa(g, w, h * 0.3, d, corpoCor(f.cor), 0, h * 0.62, 0);
      caixa(g, w * 0.9, 0.02, d * 0.92, mat("#16a34a"), 0, h * 0.92, 0);
      for (let i = 0; i < 8; i++) {
        const v = new T.Mesh(new T.CylinderGeometry(0.012, 0.012, w * 1.3, 8), metal);
        v.rotation.z = Math.PI / 2;
        v.position.set(0, h * 0.9, -d / 2 + ((i + 0.5) / 8) * d);
        g.add(v);
      }
      painelDeFoto(g, f.capa, d * 0.7, h * 0.26, w / 2 + 0.005, h * 0.63, 0).rotation.y = Math.PI / 2;
    },
    carrossel(g, w, h, d, f) {
      const r = Math.min(w, d) / 2;
      cilindro(g, r, 0.3, corpoCor(f.cor), 0, 0, 0, 32);
      cilindro(g, 0.08, h - 0.6, metal, 0, 0.3, 0);
      const teto = new T.Mesh(new T.ConeGeometry(r * 1.02, 0.6, 32), luz(f.cor || "#f97316"));
      teto.position.set(0, h - 0.3, 0);
      g.add(teto);
      for (let i = 0; i < 6; i++) {
        const a = (i / 6) * Math.PI * 2;
        caixa(g, 0.3, 0.45, 0.5, mat(["#ef4444", "#facc15", "#22c55e", "#3b82f6", "#ec4899", "#a855f7"][i]), Math.cos(a) * r * 0.7, 0.4, Math.sin(a) * r * 0.7);
        cilindro(g, 0.02, h - 1.2, metal, Math.cos(a) * r * 0.7, 0.85, Math.sin(a) * r * 0.7, 8);
      }
    },
    touro(g, w, h, d, f) {
      const colchao = new T.Mesh(new T.CylinderGeometry(Math.min(w, d) / 2, Math.min(w, d) / 2, 0.35, 28), mat("#dc2626"));
      colchao.position.y = 0.175;
      g.add(colchao);
      cilindro(g, 0.12, 0.5, metal, 0, 0.35, 0);
      caixa(g, 0.4, 0.4, 0.95, mat("#7c2d12"), 0, 0.85, 0);
      caixa(g, 0.32, 0.32, 0.3, mat("#7c2d12"), 0, 1.0, 0.55);
    },
    montaria(g, w, h, d, f) {
      caixa(g, w, 0.25, d, corpoCor(f.cor), 0, 0, 0);
      const corpo = new T.Mesh(new T.CapsuleGeometry(Math.min(w, d) * 0.3, d * 0.35, 6, 12), mat(f.cor || "#ef4444"));
      corpo.rotation.x = Math.PI / 2;
      corpo.position.set(0, 0.25 + h * 0.35, 0);
      corpo.castShadow = true;
      g.add(corpo);
      painelDeFoto(g, f.capa, w * 0.8, h * 0.45, 0, 0.25 + h * 0.15, d / 2 + 0.005);
    },
    escalada(g, w, h, d, f) {
      caixa(g, w, h, 0.2, mat("#0ea5e9"), 0, 0, -d / 2 + 0.1);
      const sorte = (i) => ((Math.sin(i * 12.9898) * 43758.5453) % 1 + 1) % 1;
      for (let i = 0; i < 40; i++) {
        const agarra = new T.Mesh(new T.SphereGeometry(0.05, 6, 5), mat(["#facc15", "#ef4444", "#22c55e", "#f97316"][i % 4]));
        agarra.position.set((sorte(i) - 0.5) * w * 0.9, 0.3 + sorte(i + 99) * (h - 0.5), -d / 2 + 0.22);
        g.add(agarra);
      }
      caixa(g, w, 0.3, Math.max(0.3, d - 0.25), mat("#2563eb"), 0, 0, 0.12);
    },
    cama_elastica(g, w, h, d, f) {
      const a = Math.min(0.9, h);
      caixa(g, w, 0.12, d, mat(f.cor || "#2563eb"), 0, a - 0.12, 0);
      caixa(g, w * 0.8, 0.02, d * 0.8, preto, 0, a - 0.1, 0);
      for (const [x, z] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) caixa(g, 0.06, a - 0.12, 0.06, metal, x * (w / 2 - 0.1), 0, z * (d / 2 - 0.1));
      if (h > 1.5) {
        for (const [x, z] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) caixa(g, 0.04, h - a, 0.04, metal, x * (w / 2 - 0.05), a, z * (d / 2 - 0.05));
      }
    },
    // o brinquedo grande sem 3D: as torres coloridas na medida, com a foto na frente
    playground(g, w, h, d, f) {
      const cores = ["#2563eb", "#facc15", "#ef4444", "#22c55e"];
      const torres = Math.max(1, Math.round(w / 1.6));
      for (let i = 0; i < torres; i++) {
        const x = -w / 2 + (i + 0.5) * (w / torres);
        caixa(g, w / torres - 0.08, 0.06, d * 0.9, mat(cores[i % 4]), x, h * 0.4, 0);
        for (const [dx, dz] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) cilindro(g, 0.05, h * 0.92, mat(cores[(i + 1) % 4]), x + dx * (w / torres / 2 - 0.08), 0, dz * (d * 0.43), 12);
        const teto = new T.Mesh(new T.ConeGeometry(Math.min(w / torres, d) * 0.6, h * 0.18, 4), mat(cores[(i + 2) % 4], { flatShading: true }));
        teto.rotation.y = Math.PI / 4;
        teto.position.set(x, h * 0.92 + h * 0.09, 0);
        g.add(teto);
      }
      painelDeFoto(g, f.capa, Math.min(w * 0.6, 3), Math.min(h * 0.35, 1.4), 0, 0.15, d / 2 + 0.01);
    },
  };

  /**
   * O mini 3D da máquina: largura `w` (x), altura `h`, fundo `d` (z), frente em +z.
   * `ficha`: { desenho, capa, cor }.
   */
  return function desenhar(desenho, w, h, d, ficha) {
    const g = new T.Group();
    (D[desenho] || D.fliperama)(g, w, h, d, ficha || {});
    return g;
  };
}
