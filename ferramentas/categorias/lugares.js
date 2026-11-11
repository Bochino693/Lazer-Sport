/* ======================================================================
   OS LUGARES DAS FOTOS DAS CATEGORIAS (ver cenas.js).

   O cliente pediu: "enriqueça mais as fotos das categorias, estão muito
   brancas, ponha em lugares, shoppings, parques, buffets entre outros."
   Cada foto agora tem os brinquedos DENTRO de um lugar de verdade, montado
   aqui em 3D (nada de foto baixada: o lugar é desenhado, e nenhuma loja,
   marca ou jogo de alguém aparece):

     buffet         o salão de festa infantil: piso claro, parede de bolinhas,
                    o arco de balões, o painel redondo com os cilindros, as
                    bandeirinhas e a mesa de doces;
     shopping       o corredor do shopping: piso brilhante, as vitrines acesas
                    (o "dentro" desfocado, sem nome de loja), o mezanino com o
                    guarda-corpo de vidro, as colunas e os vasos;
     gamezone       a game zone: o carpete escuro com os desenhos em neon, as
                    paredes com os tubos de luz e as outras máquinas ao fundo;
     galpao         o galpão do parque indoor: piso de concreto, a faixa
                    colorida na parede, a chapa metálica, os pilares, a treliça
                    e as luminárias do galpão;
     brinquedoteca  a brinquedoteca: o tapete de EVA em pastel, o arco-íris na
                    parede, a janela, as estantes com os brinquedos;
     praca          a praça: a grama, o piso de pedra, o céu, as árvores, os
                    bancos e os postes;
     salao          o salão de festas do condomínio: o piso de madeira, a
                    parede de vidro para o jardim e a piscina, o painel de
                    ripas, o sofá e os pendentes;
     quadra         a quadra da escola: o piso com as linhas, a arquibancada,
                    a tabela de basquete e as janelas altas;
     mural          o salão de festa infantil das imagens da fábrica (as capas
                    dos produtos): a parede com o mural pintado (o céu, as
                    nuvens, os morros, as árvores, os arbustos e a cerca), o
                    piso de madeira com o reflexo suave, o teto claro com os
                    spots, a parede do lado verde com a janela, a luz difusa e,
                    num canto, a mesinha branca com as cadeiras;
     loja           a loja de peças (o card "Peças e acessórios" da home): o
                    balcão de madeira, o painel perfurado com os ganchos, as
                    prateleiras com o estoque (as fotos das peças do
                    catálogo), a fita de LED quente e as luzinhas.

   Cada lugar se arma em volta da caixa dos brinquedos: o fundo atrás, a
   parede do lado oposto ao da câmera, o chão até a borda da foto. Devolve
   { grupo, fundo, neblina, luz }: o grupo vai para a cena e é desfocado
   pelo compor.py (os brinquedos ficam nítidos).
   ====================================================================== */

function sorteio(semente) {
  let s = semente >>> 0 || 1;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

export function criarLugares(T, P, extra = {}) {
  const GRAU = Math.PI / 180;
  const PI = Math.PI;
  // os materiais do lugar são só dele (a máscara dos brinquedos não pode pegar um material do lugar)
  const mats = new Map();
  const mat = (cor, extra) => {
    const chave = cor + JSON.stringify(extra || {});
    if (!mats.has(chave)) mats.set(chave, new T.MeshStandardMaterial(Object.assign({ color: cor, roughness: 0.6, metalness: 0.02 }, extra || {})));
    return mats.get(chave);
  };
  const luz = (cor, forca = 1.2) => mat(cor, { emissive: cor, emissiveIntensity: forca, roughness: 0.4 });
  const texturas = new Map();
  /** Textura de canvas que se repete (`l` x `a` px), uma por chave. */
  const tex = (chave, l, a, desenhar) => {
    if (!texturas.has(chave)) {
      const c = document.createElement("canvas");
      c.width = l;
      c.height = a;
      desenhar(c.getContext("2d"), l, a);
      const t = new T.CanvasTexture(c);
      t.colorSpace = T.SRGBColorSpace;
      t.wrapS = t.wrapT = T.RepeatWrapping;
      t.anisotropy = 16;
      texturas.set(chave, t);
    }
    return texturas.get(chave);
  };
  /** Material com a textura repetida a cada `passo` metros numa superfície `l` x `a`. */
  const matTex = (chave, l, a, passo, desenhar, extra = {}, px = 1024) => {
    const t = tex(chave, px, px, desenhar).clone();
    t.needsUpdate = true;
    t.repeat.set(l / passo, a / passo);
    return new T.MeshStandardMaterial(Object.assign({ map: t, roughness: 0.6 }, extra));
  };
  const malha = (geo, m, x = 0, y = 0, z = 0) => {
    const o = new T.Mesh(geo, m);
    o.position.set(x, y, z);
    return o;
  };
  const caixa = (g, l, a, p, m, x = 0, y = 0, z = 0, ry = 0) => {
    const o = malha(new T.BoxGeometry(l, a, p), m, x, y + a / 2, z);
    o.rotation.y = ry;
    g.add(o);
    return o;
  };
  const cil = (g, r, a, m, x = 0, y = 0, z = 0, seg = 24, r2) => {
    const o = malha(new T.CylinderGeometry(r2 ?? r, r, a, seg), m, x, y + a / 2, z);
    g.add(o);
    return o;
  };
  const esf = (g, r, m, x, y, z, seg = 20) => {
    const o = malha(new T.SphereGeometry(r, seg, Math.round(seg * 0.7)), m, x, y, z);
    g.add(o);
    return o;
  };
  /** Chão (plano deitado em y = -0,002, que recebe a sombra dos brinquedos). */
  const chao = (g, l, p, m, x = 0, z = 0, y = -0.002) => {
    const o = malha(new T.PlaneGeometry(l, p), m, x, y, z);
    o.rotation.x = -Math.PI / 2;
    o.receiveShadow = true;
    g.add(o);
    return o;
  };
  /** Parede de pé: `l` de largura, `a` de altura, a base em y, virada para `giro`. */
  const parede = (g, l, a, m, x, z, giro = 0, y = 0) => {
    const o = malha(new T.PlaneGeometry(l, a), m, x, y + a / 2, z);
    o.rotation.y = giro;
    g.add(o);
    return o;
  };

  /**
   * A sala em volta dos brinquedos: onde ficam o fundo e a parede do lado
   * (a do lado oposto ao da câmera). `atras` e `lado`: a folga até elas.
   */
  function medidas(caixaDos, giro, atras, lado) {
    const min = caixaDos.min, max = caixaDos.max;
    const centro = caixaDos.getCenter(new T.Vector3());
    const tam = caixaDos.getSize(new T.Vector3());
    const maior = Math.max(tam.x, tam.z);
    atras = atras ?? Math.max(1.4, maior * 0.22);
    lado = lado ?? Math.max(1.6, maior * 0.25);
    const zFundo = min.z - atras;
    const ladoEsq = giro >= 0; // a câmera vem da direita: a parede do lado é a da esquerda
    const xLado = ladoEsq ? min.x - lado : max.x + lado;
    return { min, max, centro, tam, maior, zFundo, xLado, ladoEsq, giroLado: ladoEsq ? Math.PI / 2 : -Math.PI / 2 };
  }

  /* ---------------------------------------------------------------- desenhos de canvas */
  const bolinhas = (fundo, cor, n = 7) => (c, l, a) => {
    c.fillStyle = fundo;
    c.fillRect(0, 0, l, a);
    c.fillStyle = cor;
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        c.beginPath();
        c.arc(((i + (j % 2) * 0.5) * l) / n, ((j + 0.5) * a) / n, l / n / 6, 0, Math.PI * 2);
        c.fill();
      }
    }
  };
  const ladrilhos = (fundo, junta, n = 2, ruido = 0) => (c, l, a) => {
    c.fillStyle = fundo;
    c.fillRect(0, 0, l, a);
    if (ruido) {
      const r = sorteio(7);
      for (let i = 0; i < 2500; i++) {
        c.fillStyle = `rgba(${r() < 0.5 ? "255,255,255" : "0,0,0"},${ruido * r()})`;
        c.fillRect(r() * l, r() * a, 2, 2);
      }
    }
    c.strokeStyle = junta;
    c.lineWidth = 3;
    for (let i = 0; i <= n; i++) {
      c.beginPath();
      c.moveTo((i * l) / n, 0);
      c.lineTo((i * l) / n, a);
      c.moveTo(0, (i * a) / n);
      c.lineTo(l, (i * a) / n);
      c.stroke();
    }
  };

  /** O piso de tacos de madeira, no tom (r, g, b) do meio. */
  const tacos = (r0, g0, b0) => (c, l, a) => {
    const r = sorteio(r0);
    for (let i = 0; i < 8; i++) for (let j = 0; j < 4; j++) {
      const v = 0.86 + r() * 0.26;
      c.fillStyle = `rgb(${Math.round(r0 * v)},${Math.round(g0 * v)},${Math.round(b0 * v)})`;
      c.fillRect(j * (l / 4) + (i % 2) * (l / 8), (i * a) / 8, l / 4, a / 8);
      c.fillRect(j * (l / 4) + (i % 2) * (l / 8) - l, (i * a) / 8, l / 4, a / 8);
    }
    c.strokeStyle = "rgba(60,35,15,.35)";
    c.lineWidth = 2;
    for (let i = 0; i <= 8; i++) {
      c.beginPath();
      c.moveTo(0, (i * a) / 8);
      c.lineTo(l, (i * a) / 8);
      c.stroke();
    }
  };

  /* ---------------------------------------------------------------- enfeites */
  const CORES_BALAO = ["#f472b6", "#facc15", "#38bdf8", "#a78bfa", "#fb7185", "#34d399", "#ffffff", "#f59e0b"];
  /** O arco de balões (a guirlanda) em volta de (x, y): de `a0` a `a1` graus, no plano x-y. */
  function arcoDeBaloes(g, x, y, z, raio, a0 = 0, a1 = 180, semente = 3) {
    const r = sorteio(semente);
    const n = Math.round(((a1 - a0) * GRAU * raio) / 0.22);
    for (let i = 0; i < n; i++) {
      const ang = (a0 + ((a1 - a0) * i) / (n - 1)) * GRAU;
      for (let k = 0; k < 2; k++) {
        const rr = raio + (r() - 0.5) * 0.45;
        const b = esf(g, 0.16 + r() * 0.16, mat(CORES_BALAO[Math.floor(r() * CORES_BALAO.length)], { roughness: 0.22, metalness: 0.05 }),
          x + Math.cos(ang) * rr, y + Math.sin(ang) * rr, z + (r() - 0.5) * 0.4 + k * 0.18);
        b.castShadow = true;
      }
    }
  }
  /** Um cacho de balões de pé (com a fitinha e o peso). */
  function cachoDeBaloes(g, x, z, altura = 2.0, semente = 1) {
    const r = sorteio(semente);
    for (let i = 0; i < 5; i++) {
      const bx = x + (r() - 0.5) * 0.6, bz = z + (r() - 0.5) * 0.6, by = altura + (r() - 0.5) * 0.5;
      const b = esf(g, 0.24, mat(CORES_BALAO[(i + semente) % CORES_BALAO.length], { roughness: 0.2 }), bx, by, bz);
      b.scale.set(1, 1.18, 1);
      b.castShadow = true;
      const fio = malha(new T.CylinderGeometry(0.004, 0.004, by - 0.25), mat("#e5e7eb"), (bx + x) / 2, (by - 0.25) / 2 + 0.05, (bz + z) / 2);
      fio.lookAt(bx, by, bz);
      fio.rotateX(Math.PI / 2);
      g.add(fio);
    }
    cil(g, 0.08, 0.1, mat("#fbbf24", { metalness: 0.6, roughness: 0.3 }), x, 0, z);
  }
  /** As bandeirinhas num fio, de (x0, y, z) a (x1, y, z). */
  function bandeirinhas(g, x0, x1, y, z, cores = ["#ef4444", "#facc15", "#22c55e", "#3b82f6", "#ec4899", "#f97316"]) {
    const n = Math.round(Math.abs(x1 - x0) / 0.45);
    const fio = malha(new T.CylinderGeometry(0.008, 0.008, Math.abs(x1 - x0)), mat("#f8fafc"), (x0 + x1) / 2, y, z);
    fio.rotation.z = Math.PI / 2;
    g.add(fio);
    const tri = new T.Shape([new T.Vector2(-0.16, 0), new T.Vector2(0.16, 0), new T.Vector2(0, -0.34)]);
    for (let i = 0; i < n; i++) {
      const xb = x0 + ((i + 0.5) * (x1 - x0)) / n;
      const b = malha(new T.ShapeGeometry(tri), mat(cores[i % cores.length], { side: T.DoubleSide }), xb, y - 0.01 - Math.sin((i / n) * Math.PI) * 0.25, z);
      g.add(b);
    }
  }
  /** Uma planta no vaso (o vaso e a copa em bolas de folhagem). */
  function planta(g, x, z, altura = 1.6, vaso = "#f8fafc", semente = 2) {
    const r = sorteio(semente);
    cil(g, 0.32, 0.55, mat(vaso, { roughness: 0.35 }), x, 0, z, 24, 0.38);
    cil(g, 0.035, altura - 0.5, mat("#5b4636"), x, 0.5, z, 8);
    for (let i = 0; i < 7; i++) {
      esf(g, 0.28 + r() * 0.18, mat(["#15803d", "#16a34a", "#22c55e", "#166534"][i % 4], { roughness: 0.8 }),
        x + (r() - 0.5) * 0.6, altura - 0.2 + (r() - 0.3) * 0.6, z + (r() - 0.5) * 0.6, 14);
    }
  }
  /** Uma árvore (o tronco e a copa em bolas). */
  function arvore(g, x, z, altura = 5, semente = 4) {
    const r = sorteio(semente);
    cil(g, 0.16, altura * 0.55, mat("#6b4f3a", { roughness: 0.9 }), x, 0, z, 10, 0.12);
    const copa = altura * 0.32;
    for (let i = 0; i < 9; i++) {
      esf(g, copa * (0.45 + r() * 0.3), mat(["#16a34a", "#15803d", "#22c55e", "#4d7c0f"][i % 4], { roughness: 0.85 }),
        x + (r() - 0.5) * copa * 1.4, altura * 0.62 + (r() - 0.2) * copa, z + (r() - 0.5) * copa * 1.4, 14);
    }
  }
  /** O banco de praça (as ripas de madeira nos pés de ferro). */
  function banco(g, x, z, ry = 0) {
    const b = new T.Group();
    for (let i = 0; i < 3; i++) caixa(b, 1.6, 0.04, 0.12, mat("#b45309", { roughness: 0.7 }), 0, 0.44, -0.15 + i * 0.15);
    for (let i = 0; i < 2; i++) {
      const enc = caixa(b, 1.6, 0.11, 0.035, mat("#b45309", { roughness: 0.7 }), 0, 0.62 + i * 0.16, -0.27);
      enc.rotation.x = -0.15;
    }
    for (const s of [-1, 1]) caixa(b, 0.06, 0.85, 0.5, mat("#1f2937", { metalness: 0.5 }), s * 0.7, 0, -0.08);
    b.position.set(x, 0, z);
    b.rotation.y = ry;
    g.add(b);
  }
  /** O poste com o globo aceso. */
  function poste(g, x, z, altura = 3.6) {
    cil(g, 0.06, altura, mat("#14532d", { metalness: 0.4, roughness: 0.4 }), x, 0, z, 10);
    esf(g, 0.22, luz("#fffbeb", 0.9), x, altura + 0.15, z);
  }
  /** Uma vitrine de loja: a moldura, o vidro com o "dentro" desfocado (sem nome) e a faixa da fachada. */
  function vitrine(g, l, a, x, z, ry, semente, faixa) {
    const v = new T.Group();
    const r = sorteio(semente);
    const dentro = tex("vitrine-" + semente, 512, 384, (c, w, h) => {
      const f = c.createLinearGradient(0, 0, 0, h);
      f.addColorStop(0, ["#f59e0b", "#ec4899", "#0ea5e9", "#8b5cf6", "#10b981"][((semente % 5) + 5) % 5]);
      f.addColorStop(1, ["#fde68a", "#fbcfe8", "#bae6fd", "#ddd6fe", "#bbf7d0"][((semente % 5) + 5) % 5]);
      c.fillStyle = f;
      c.fillRect(0, 0, w, h);
      c.filter = "blur(3px)";
      // as prateleiras com as caixas coloridas, dos dois lados
      for (const x0 of [0.04, 0.68]) {
        for (let k = 0; k < 3; k++) {
          const y = h * (0.3 + k * 0.22);
          c.fillStyle = "#ffffff";
          c.fillRect(w * x0, y, w * 0.28, 6);
          for (let i = 0; i < 5; i++) {
            c.fillStyle = ["#f472b6", "#60a5fa", "#fbbf24", "#34d399", "#a78bfa", "#f97316"][Math.floor(r() * 6)];
            c.fillRect(w * x0 + i * w * 0.055, y - 30 - r() * 14, w * 0.045, 30 + r() * 10);
          }
        }
      }
      // a porta aberta no meio, com o manequim
      c.fillStyle = "rgba(255,255,255,.55)";
      c.fillRect(w * 0.38, h * 0.22, w * 0.24, h * 0.78);
      c.fillStyle = ["#7c3aed", "#db2777", "#0891b2", "#ea580c", "#16a34a"][((semente % 5) + 5) % 5];
      c.beginPath();
      c.arc(w * 0.5, h * 0.42, 16, 0, Math.PI * 2);
      c.fill();
      c.fillRect(w * 0.5 - 22, h * 0.46, 44, h * 0.3);
      c.fillStyle = "rgba(255,255,255,.9)";
      for (let i = 0; i < 5; i++) {
        c.beginPath();
        c.arc((i + 0.5) * (w / 5), 18, 10, 0, Math.PI * 2);
        c.fill();
      }
      c.filter = "none";
    });
    const vidro = new T.MeshStandardMaterial({ map: dentro, emissive: "#ffffff", emissiveMap: dentro, emissiveIntensity: 0.35, roughness: 0.08, metalness: 0.1 });
    const p = malha(new T.PlaneGeometry(l - 0.5, a - 1.2), vidro, 0, (a - 1.2) / 2 + 0.05, 0.02);
    v.add(p);
    // a faixa da fachada (a cor da loja, sem nome) e as colunas da moldura
    caixa(v, l, 0.9, 0.18, mat(faixa, { roughness: 0.4 }), 0, a - 1.05, 0.05);
    caixa(v, l, 0.12, 0.2, mat("#e5e7eb", { roughness: 0.3 }), 0, a - 0.15, 0.05);
    for (const s of [-1, 1]) caixa(v, 0.25, a, 0.3, mat("#f1f5f9", { roughness: 0.3 }), s * (l / 2 - 0.12), 0, 0.05);
    v.position.set(x, 0, z);
    v.rotation.y = ry;
    g.add(v);
    return v;
  }

  /* ---------------------------------------------------------------- a vida */
  /** O confete parado no ar: os papeizinhos coloridos, fora do volume das máquinas. */
  function confete(g, caixaDos, n = 160, semente = 1, altura = 4.5) {
    const r = sorteio(semente);
    const min = caixaDos.min, max = caixaDos.max;
    const cores = ["#ef4444", "#facc15", "#22c55e", "#3b82f6", "#ec4899", "#f97316", "#a855f7", "#ffffff"];
    const geo = new T.PlaneGeometry(0.07, 0.11);
    let feitos = 0;
    for (let i = 0; feitos < n && i < n * 6; i++) {
      const x = min.x - 4 + r() * (max.x - min.x + 8), y = 0.4 + r() * altura, z = min.z - 3 + r() * (max.z - min.z + 6);
      // não cobre as máquinas: só atrás delas, acima delas ou dos lados
      const dentro = x > min.x - 0.2 && x < max.x + 0.2 && y < max.y + 0.5 && z > min.z - 0.3;
      if (dentro) continue;
      const o = malha(geo, mat(cores[i % cores.length], { side: T.DoubleSide, roughness: 0.5, emissive: cores[i % cores.length], emissiveIntensity: 0.15 }), x, y, z);
      o.rotation.set(r() * 6, r() * 6, r() * 6);
      g.add(o);
      feitos++;
    }
  }
  /** O cordão de lâmpadas (as luzinhas de festa) de (x0, z0) a (x1, z1), caindo no meio. */
  function luzinhas(g, x0, z0, x1, z1, y, cores = ["#fde68a", "#fbcfe8", "#bae6fd", "#bbf7d0"]) {
    const n = Math.max(6, Math.round(Math.hypot(x1 - x0, z1 - z0) / 0.45));
    for (let i = 0; i <= n; i++) {
      const t = i / n;
      const yy = y - Math.sin(t * Math.PI) * 0.6;
      esf(g, 0.06, luz(cores[i % cores.length], 2.6), x0 + (x1 - x0) * t, yy, z0 + (z1 - z0) * t, 10);
    }
  }
  /** A luminária pendente redonda (a de papel do buffet), acesa. */
  function pendente(g, x, y, z, cor = "#fff7ed", r = 0.32) {
    cil(g, 0.006, 3, mat("#e5e7eb"), x, y + r, z, 4);
    esf(g, r, luz(cor, 1.6), x, y, z, 24);
  }
  /** A mancha do sol que entra pela janela, no chão (um quadro de luz, macio nas bordas). */
  function solNoChao(g, x, z, l, p, ry = 0, forca = 0.5) {
    const t = tex("sol-no-chao", 256, 256, (c, w, h) => {
      const gr = c.createRadialGradient(w / 2, h / 2, 10, w / 2, h / 2, w * 0.55);
      gr.addColorStop(0, "rgba(255,244,214,1)");
      gr.addColorStop(0.6, "rgba(255,240,200,.75)");
      gr.addColorStop(1, "rgba(255,240,200,0)");
      c.fillStyle = gr;
      c.fillRect(0, 0, w, h);
    });
    const o = malha(new T.PlaneGeometry(l, p), new T.MeshBasicMaterial({ map: t, transparent: true, opacity: forca, depthWrite: false, blending: T.AdditiveBlending, toneMapped: false }), x, 0.006, z);
    o.rotation.x = -Math.PI / 2;
    o.rotation.z = ry;
    g.add(o);
  }
  /** O piso que reflete: fica um tanto transparente, e o espelho das máquinas aparece embaixo. */
  function refletir(g, piso, quanto, corDeBaixo, m) {
    piso.material.transparent = true;
    piso.material.opacity = 1 - quanto;
    const baixo = malha(new T.PlaneGeometry(300, 300), new T.MeshBasicMaterial({ color: corDeBaixo, fog: false }), m.centro.x, -12, m.centro.z);
    baixo.rotation.x = -Math.PI / 2;
    g.add(baixo);
  }
  /**
   * As máquinas do fundo: outros itens de verdade da mesma categoria (as fotos do
   * catálogo, `extra.maquina`), encostados no fundo e no lado, longe das da frente.
   */
  function maquinasAoFundo(g, lista, m, { folga = 0.9, distanciaDoFundo = 0.6 } = {}) {
    if (!lista || !lista.length || !extra.maquina) return;
    const r = sorteio(lista.length * 7);
    let k = 0;
    // no fundo: dos dois lados das máquinas da frente
    const xs = [];
    for (let d = 0; d < 8; d++) {
      xs.push(m.max.x + folga + d * 1.15, m.min.x - folga - d * 1.15);
    }
    for (const x of xs) {
      if (k >= lista.length) break;
      g.add(extra.maquina(lista[k++], { x, z: m.zFundo + distanciaDoFundo + r() * 0.3, r: (r() - 0.5) * 10 }));
    }
    // e encostadas na parede do lado, vindo para a frente
    const lado = m.ladoEsq ? 1 : -1;
    for (let z = m.zFundo + 1.6; k < lista.length && z < m.centro.z + 8; z += 1.3) {
      g.add(extra.maquina(lista[k++], { x: m.xLado + lado * 0.55, z, r: (r() - 0.5) * 10 }));
    }
  }
  /** As crianças do fundo (as da Arena 3D), andando e correndo, longe. */
  function criancasAoFundo(g, pontos) {
    if (!extra.crianca) return;
    pontos.forEach(([x, z, pose, r], i) => g.add(extra.crianca(10 + i, pose, { x, z, r })));
  }

  /* ================================================================ OS LUGARES */
  const LUGARES = {
    /* ------------------------------------------------------------ o buffet infantil */
    buffet(caixaDos, giro, op = {}) {
      const g = new T.Group();
      const m = medidas(caixaDos, giro, op.atras, op.lado);
      const H = Math.max(9, m.tam.y * 3.6);
      const piso = chao(g, 160, 160, matTex("piso-buffet", 160, 160, 1.6, tacos(205, 150, 98), { roughness: 0.3 }), m.centro.x, m.centro.z);
      refletir(g, piso, 0.12, "#7a5230", m);
      // a parede de bolinhas com o rodapé branco alto
      const corParede = op.parede || "#f9a8d4";
      for (const [l, x, z, ry] of [[160, m.centro.x, m.zFundo, 0], [160, m.xLado, m.centro.z, m.giroLado]]) {
        parede(g, l, H, matTex("parede-buffet-" + corParede, l, H, 1.2, bolinhas(corParede, "rgba(255,255,255,.55)", 5)), x, z, ry);
        const rod = parede(g, l, 1.15, mat("#ffffff", { roughness: 0.4 }), x, z, ry);
        rod.position.add(new T.Vector3(Math.sin(ry), 0, Math.cos(ry)).multiplyScalar(0.03));
        const friso = parede(g, l, 0.08, mat("#fbbf24", { roughness: 0.3 }), x, z, ry, 1.15);
        friso.position.add(new T.Vector3(Math.sin(ry), 0, Math.cos(ry)).multiplyScalar(0.035));
      }
      // o painel redondo da festa, com os três cilindros e o arco de balões em volta
      const lado = m.ladoEsq ? 1 : -1;
      const px = op.painelX ?? (m.ladoEsq ? m.max.x + 0.4 : m.min.x - 0.4) + lado * -0.2;
      const pz = m.zFundo + 0.08;
      const rp = Math.min(2.0, Math.max(0.85, m.tam.y * 0.55));
      if (op.painel !== false) {
        const painel = malha(new T.CylinderGeometry(rp, rp, 0.06, 64), mat("#a7f3d0", { roughness: 0.5 }), px, rp + 0.3, pz + 0.05);
        painel.rotation.x = Math.PI / 2;
        g.add(painel);
        arcoDeBaloes(g, px, rp + 0.3, pz + 0.35, rp + 0.15, -20, 200, 5);
        for (const [dx, a, c] of [[-0.75, 0.55, "#f9a8d4"], [0, 0.8, "#fde68a"], [0.75, 0.42, "#bae6fd"]]) {
          cil(g, 0.32, a, mat(c, { roughness: 0.45 }), px + dx, 0, pz + 0.7, 32).castShadow = true;
        }
      }
      // a mesa de doces: a toalha, o bolo de três andares e os docinhos
      // (encostada na parede do lado, perto do fundo: longe das máquinas, nunca na frente de uma)
      const mx = op.mesaX ?? m.xLado + lado * 0.6, mz = op.mesaZ ?? m.zFundo + 1.5;
      caixa(g, 0.9, 0.82, 2.0, mat("#ffffff", { roughness: 0.7 }), mx, 0, mz);
      caixa(g, 0.94, 0.06, 2.04, mat("#fbcfe8", { roughness: 0.6 }), mx, 0.76, mz);
      for (const [ra, a, y, c] of [[0.28, 0.2, 0.82, "#f9a8d4"], [0.21, 0.18, 1.02, "#ffffff"], [0.14, 0.16, 1.2, "#c4b5fd"]]) cil(g, ra, a, mat(c, { roughness: 0.5 }), mx, y, mz, 32);
      esf(g, 0.05, mat("#ef4444"), mx, 1.4, mz);
      const rr = sorteio(9);
      for (let i = 0; i < 14; i++) esf(g, 0.045, mat(["#7c2d12", "#fbbf24", "#f472b6", "#ffffff"][i % 4], { roughness: 0.4 }), mx + (rr() - 0.5) * 0.6, 0.86, mz + (i < 7 ? -0.65 : 0.65) + (rr() - 0.5) * 0.4, 10);
      // as bandeirinhas e os cachos de balões
      for (let i = 0; i < 3; i++) bandeirinhas(g, m.min.x - 6, m.max.x + 6, Math.min(H - 0.8, 6.8) - i * 0.55, m.zFundo + 0.4 + i * 0.9);
      cachoDeBaloes(g, m.xLado + lado * 0.6, m.zFundo + 0.7, Math.min(2.1, m.tam.y + 0.4), 2);
      cachoDeBaloes(g, op.cachoX ?? (m.ladoEsq ? m.max.x + 2.4 : m.min.x - 2.4), m.zFundo + 0.9, Math.min(1.9, m.tam.y + 0.3), 5);
      // a festa acesa: as luminárias de papel, as luzinhas e o confete no ar
      for (let i = -4; i <= 4; i++) pendente(g, m.centro.x + i * Math.max(1.6, m.tam.x / 6), Math.min(H - 1.6, 5.2) - (i % 2) * 0.4, m.zFundo + 1.6 + (i % 3) * 0.6, ["#fff7ed", "#fde68a", "#fbcfe8"][(i + 9) % 3]);
      luzinhas(g, m.min.x - 4, m.zFundo + 0.3, m.max.x + 4, m.zFundo + 0.3, Math.min(H - 0.4, 6.2));
      luzinhas(g, m.xLado + lado * 0.3, m.zFundo, m.xLado + lado * 0.3, m.centro.z + 8, Math.min(H - 0.6, 6.0));
      confete(g, caixaDos, 140, 3, Math.min(5, H - 1.5));
      maquinasAoFundo(g, op.fundo, m, { folga: 1.6, distanciaDoFundo: 1.4 });
      criancasAoFundo(g, [[m.xLado + lado * 2.4, m.zFundo + 1.6, "andando", 60 * lado], [m.max.x + 3.6, m.zFundo + 2.0, "comemorando", -30]]);
      const frente = (naTela) => {
        const f = new T.Group();
        const q = naTela(1.08, -1.04);
        if (q) cachoDeBaloes(f, q.x, q.z, 0.85, 11);
        return f;
      };
      return { grupo: g, frente, fundo: "#fde4ef", neblina: ["#fde4ef", m.maior * 5 + 20, m.maior * 10 + 80], luz: { ceu: "#fff7ed", chao: "#d4a373", hemi: 1.0, sol: 2.0, amb: 0.45, exposicao: 1.0 } };
    },

    /* ------------------------------------------------------------ o corredor do shopping */
    shopping(caixaDos, giro, op = {}) {
      const g = new T.Group();
      const m = medidas(caixaDos, giro, op.atras ?? Math.max(2.2, m0(caixaDos) * 0.3), op.lado ?? Math.max(3.5, m0(caixaDos) * 0.3));
      const piso = chao(g, 200, 200, matTex("piso-shopping", 200, 200, 2.4, (c, l, a) => {
        for (let i = 0; i < 2; i++) for (let j = 0; j < 2; j++) {
          c.fillStyle = (i + j) % 2 ? "#cbbfae" : "#a8998a";
          c.fillRect((i * l) / 2, (j * a) / 2, l / 2, a / 2);
        }
        c.strokeStyle = "#8b7d6e";
        c.lineWidth = 3;
        c.strokeRect(0, 0, l, a);
      }, { roughness: 0.12, metalness: 0.05, envMapIntensity: 1.5 }), m.centro.x, m.centro.z);
      refletir(g, piso, 0.26, "#6b5e52", m);
      // uma faixa escura no piso, de borda (o desenho do piso do corredor)
      const faixa = chao(g, 200, 0.5, mat("#9ca3af", { roughness: 0.12 }), m.centro.x, m.zFundo + 1.0, 0.0);
      faixa.position.y = -0.001;
      const cores = ["#f59e0b", "#0ea5e9", "#ec4899", "#10b981", "#8b5cf6", "#ef4444"];
      // as vitrines do térreo no fundo e no lado, o mezanino e as do andar de cima
      const larg = 5.2, alt = 3.6;
      for (let i = -6; i <= 6; i++) {
        const x = m.centro.x + i * larg;
        vitrine(g, larg, alt, x, m.zFundo, 0, 20 + i, cores[(i + 12) % cores.length]);
        vitrine(g, larg, alt - 0.6, x, m.zFundo - 2.2, 0, 40 + i, cores[(i + 15) % cores.length]).position.y = alt + 1.0;
      }
      for (let i = -4; i <= 6; i++) {
        const z = m.centro.z + i * larg;
        vitrine(g, larg, alt, m.xLado, z, m.giroLado, 60 + i, cores[(i + 9) % cores.length]);
      }
      // a laje do mezanino, o guarda-corpo de vidro e o corrimão
      caixa(g, 200, 0.5, 2.4, mat("#f8fafc", { roughness: 0.3 }), m.centro.x, alt + 0.5, m.zFundo - 1.1);
      const vidro = new T.MeshStandardMaterial({ color: "#bae6fd", transparent: true, opacity: 0.28, roughness: 0.05, depthWrite: false });
      parede(g, 200, 1.0, vidro, m.centro.x, m.zFundo + 0.05, 0, alt + 1.0);
      const corrimao = malha(new T.CylinderGeometry(0.04, 0.04, 200, 10), mat("#cbd5e1", { metalness: 0.8, roughness: 0.2 }), m.centro.x, alt + 2.0, m.zFundo + 0.05);
      corrimao.rotation.z = Math.PI / 2;
      g.add(corrimao);
      // as colunas redondas e as luzes de teto do mezanino
      for (let i = -3; i <= 3; i++) cil(g, 0.35, alt + 1.0, mat("#ffffff", { roughness: 0.25 }), m.centro.x + i * larg * 2 + larg / 2, 0, m.zFundo + 0.6, 32);
      for (let i = -12; i <= 12; i++) {
        const spot = malha(new T.CircleGeometry(0.16, 20), luz("#fffbeb", 2), m.centro.x + i * 1.8, alt + 0.49, m.zFundo + 0.4);
        spot.rotation.x = Math.PI / 2;
        g.add(spot);
      }
      // os vasos com as plantas e um banco
      const lado = m.ladoEsq ? 1 : -1;
      planta(g, m.min.x - 1.8, m.zFundo + 1.1, 2.0, "#f8fafc", 3);
      planta(g, m.max.x + 1.8, m.zFundo + 1.1, 1.8, "#f8fafc", 7);
      banco(g, m.xLado + lado * 0.8, m.centro.z + m.tam.z * 0.6 + 1.5, lado * Math.PI / 2);
      // as máquinas do fundo (da mesma categoria), o movimento do corredor e, se pedido, o confete
      maquinasAoFundo(g, op.fundo, m, { distanciaDoFundo: 0.9 });
      criancasAoFundo(g, [[m.min.x - 3.6, m.zFundo + 1.8, "andando", 90], [m.max.x + 4.2, m.zFundo + 2.4, "correndo", -80], [m.xLado + lado * 1.8, m.centro.z + 2, "andando", 150]]);
      if (op.confete) confete(g, caixaDos, 150, 5, 4.2);
      const frente = (naTela) => {
        const f = new T.Group();
        const p = naTela(1.06, -1.0);
        if (p) planta(f, p.x, p.z, 1.6, "#f8fafc", 13);
        return f;
      };
      return { grupo: g, frente, fundo: "#e2e8f0", neblina: ["#e2e8f0", m.maior * 5 + 24, m.maior * 10 + 90], luz: { ceu: "#ffffff", chao: "#a8998a", hemi: 1.05, sol: 2.1, amb: 0.55, exposicao: 1.0 } };
    },

    /* ------------------------------------------------------------ a game zone */
    gamezone(caixaDos, giro, op = {}) {
      const g = new T.Group();
      const m = medidas(caixaDos, giro, op.atras ?? 1.8, op.lado ?? 2.0);
      const H = 6.5;
      chao(g, 160, 160, matTex("carpete", 160, 160, 2.2, (c, l, a) => {
        c.fillStyle = "#1b1650";
        c.fillRect(0, 0, l, a);
        const r = sorteio(12);
        const cores = ["#22d3ee", "#f472b6", "#facc15", "#a3e635", "#a78bfa"];
        for (let i = 0; i < 46; i++) {
          c.strokeStyle = c.fillStyle = cores[i % cores.length];
          c.lineWidth = 7;
          const x = r() * l, y = r() * a, t = r() * 4;
          if (t < 1) {
            c.beginPath();
            c.arc(x, y, 12 + r() * 16, 0, Math.PI * 2);
            c.stroke();
          } else if (t < 2) {
            c.beginPath();
            c.moveTo(x, y);
            for (let k = 1; k < 5; k++) c.lineTo(x + k * 16, y + (k % 2 ? -14 : 14));
            c.stroke();
          } else if (t < 3) {
            c.beginPath();
            c.moveTo(x, y - 16);
            c.lineTo(x + 15, y + 12);
            c.lineTo(x - 15, y + 12);
            c.closePath();
            c.fill();
          } else {
            c.fillRect(x, y, 14, 14);
          }
        }
      }, { roughness: 1 }), m.centro.x, m.centro.z);
      // as paredes escuras com os tubos de neon
      for (const [l, x, z, ry] of [[160, m.centro.x, m.zFundo, 0], [160, m.xLado, m.centro.z, m.giroLado]]) {
        parede(g, l, H, mat("#2a2470", { roughness: 0.85 }), x, z, ry);
        const n = new T.Vector3(Math.sin(ry), 0, Math.cos(ry));
        for (const [y, c] of [[2.6, "#f472b6"], [2.85, "#22d3ee"], [0.25, "#a78bfa"]]) {
          const tubo = malha(new T.CylinderGeometry(0.035, 0.035, l, 10), luz(c, 2.4), x + n.x * 0.06, y, z + n.z * 0.06);
          tubo.rotation.z = Math.PI / 2;
          tubo.rotation.y = ry;
          g.add(tubo);
        }
      }
      // os desenhos de neon no fundo: o raio, os círculos e a estrela
      const nx = op.neonX ?? (m.ladoEsq ? m.max.x + 0.8 : m.min.x - 0.8);
      const raio = new T.Shape([[0, 0], [0.55, 0], [0.25, -0.75], [0.75, -0.75], [-0.2, -2.0], [0.1, -1.05], [-0.4, -1.05]].map(([x, y]) => new T.Vector2(x, y)));
      const oRaio = malha(new T.ShapeGeometry(raio), luz("#facc15", 2.2), nx, 4.6, m.zFundo + 0.05);
      g.add(oRaio);
      for (const [dx, y, r, c] of [[-2.4, 4.0, 0.55, "#22d3ee"], [-1.5, 4.5, 0.35, "#f472b6"], [2.2, 4.2, 0.5, "#a3e635"]]) {
        g.add(malha(new T.TorusGeometry(r, 0.05, 10, 40), luz(c, 2.4), nx + dx, y, m.zFundo + 0.06));
      }
      // os hexágonos de neon no alto do fundo (o desenho de game zone)
      const hexa = (r) => {
        const pts = [];
        for (let i = 0; i <= 6; i++) pts.push(new T.Vector3(Math.cos((i / 6) * Math.PI * 2) * r, Math.sin((i / 6) * Math.PI * 2) * r, 0));
        return new T.TubeGeometry(new T.CatmullRomCurve3(pts, false, "catmullrom", 0), 36, 0.035, 6, false);
      };
      const rh = sorteio(21);
      for (let i = 0; i < 26; i++) {
        const c = ["#22d3ee", "#f472b6", "#a3e635", "#facc15", "#a78bfa"][i % 5];
        const hx = m.centro.x - 13 + (i % 13) * 2.0 + (Math.floor(i / 13) % 2) * 1.0;
        const hy = 3.5 + Math.floor(i / 13) * 1.6 + rh() * 0.2;
        g.add(malha(hexa(0.5 + rh() * 0.25), luz(c, 2.2), hx, hy, m.zFundo + 0.08));
      }
      // as outras máquinas, encostadas no fundo e no lado (desfocadas na foto): itens de
      // verdade da mesma categoria, nunca um gabinete inventado
      maquinasAoFundo(g, op.fundo, m, { folga: 1.0, distanciaDoFundo: 0.5 });
      // os spots do teto e o movimento
      for (let i = -8; i <= 8; i++) {
        const spot = malha(new T.CircleGeometry(0.14, 18), luz("#fffbeb", 3), m.centro.x + i * 1.6, H - 0.05, m.zFundo + 1.2 + (i % 2) * 1.4);
        spot.rotation.x = Math.PI / 2;
        g.add(spot);
      }
      criancasAoFundo(g, [[m.max.x + 2.4, m.zFundo + 2.2, "andando", -60], [m.min.x - 2.8, m.zFundo + 2.6, "correndo", 70]]);
      if (op.confete) confete(g, caixaDos, 70, 8, 3.5);
      return {
        grupo: g, fundo: "#1b1650", neblina: ["#2a2068", m.maior * 2.5 + 8, m.maior * 6 + 30],
        luz: { ceu: "#c4b5fd", chao: "#2a1f6b", hemi: 1.0, sol: 2.6, amb: 0.35, exposicao: 1.05, cores: [["#f472b6", -1], ["#22d3ee", 1]] },
      };
    },

    /* ------------------------------------------------------------ o galpão do parque indoor */
    galpao(caixaDos, giro, op = {}) {
      const g = new T.Group();
      const m = medidas(caixaDos, giro, op.atras ?? 2.0, op.lado ?? 2.4);
      const H = Math.max(10, m.tam.y * 3.0);
      chao(g, 220, 220, matTex("concreto", 220, 220, 3, ladrilhos("#7f8a99", "#6b7584", 1, 0.06), { roughness: 0.5 }), m.centro.x, m.centro.z);
      // o piso emborrachado azul em volta dos brinquedos
      chao(g, m.tam.x + 7, m.tam.z + 7, matTex("borracha", m.tam.x + 7, m.tam.z + 7, 1.0, (c, l, a) => {
        c.fillStyle = "#2563eb";
        c.fillRect(0, 0, l, a);
        const r = sorteio(5);
        for (let i = 0; i < 2600; i++) {
          c.fillStyle = ["#93c5fd", "#facc15", "#1e40af"][i % 3];
          c.fillRect(r() * l, r() * a, 3, 3);
        }
      }, { roughness: 0.9 }), m.centro.x, m.centro.z, -0.001);
      // as paredes: a faixa colorida embaixo, a chapa metálica em cima, os pilares e a viga de treliça
      const chapa = (l) => matTex("chapa-" + l, l, H - 3, 0.9, (c, w, h) => {
        c.fillStyle = "#9fb3c8";
        c.fillRect(0, 0, w, h);
        for (let i = 0; i < 8; i++) {
          const gr = c.createLinearGradient((i * w) / 8, 0, ((i + 1) * w) / 8, 0);
          gr.addColorStop(0, "#b9cadb");
          gr.addColorStop(0.5, "#7f97b0");
          gr.addColorStop(1, "#adc0d3");
          c.fillStyle = gr;
          c.fillRect((i * w) / 8, 0, w / 8, h);
        }
      }, { roughness: 0.45, metalness: 0.3 });
      for (const [l, x, z, ry] of [[220, m.centro.x, m.zFundo, 0], [220, m.xLado, m.centro.z, m.giroLado]]) {
        const n = new T.Vector3(Math.sin(ry), 0, Math.cos(ry));
        parede(g, l, 3, mat("#0ea5e9", { roughness: 0.6 }), x, z, ry);
        const amarela = parede(g, l, 0.35, mat("#facc15", { roughness: 0.5 }), x, z, ry, 2.65);
        amarela.position.addScaledVector(n, 0.01);
        parede(g, l, H - 3, chapa(l), x, z, ry, 3);
        // as janelas altas (a luz do dia) numa faixa
        const janela = parede(g, l, 1.2, luz("#e0f2fe", 1.1), x, z, ry, H - 2.4);
        janela.position.addScaledVector(n, 0.02);
        // os pilares de aço e a viga de treliça
        for (let i = -12; i <= 12; i++) {
          const p = new T.Vector3(x, 0, z).addScaledVector(new T.Vector3(n.z, 0, -n.x), i * 6).addScaledVector(n, 0.2);
          caixa(g, 0.35, H, 0.35, mat("#334155", { metalness: 0.4, roughness: 0.5 }), p.x, 0, p.z);
        }
        const viga = new T.Vector3(x, 0, z).addScaledVector(n, 0.3);
        for (const y of [H - 0.6, H + 0.4]) {
          const banzo = malha(new T.BoxGeometry(l, 0.14, 0.14), mat("#475569", { metalness: 0.5 }), viga.x, y, viga.z);
          banzo.rotation.y = ry;
          g.add(banzo);
        }
        for (let i = -100; i <= 100; i += 1) {
          const d = malha(new T.BoxGeometry(0.07, 1.4, 0.07), mat("#475569", { metalness: 0.5 }), 0, H - 0.1, 0);
          const p = viga.clone().addScaledVector(new T.Vector3(n.z, 0, -n.x), i * 1.0);
          d.position.set(p.x, H - 0.1, p.z);
          d.rotation.y = ry;
          d.rotation.z = i % 2 ? 0.62 : -0.62;
          g.add(d);
        }
      }
      // as luminárias do galpão penduradas na frente do fundo
      for (let i = -6; i <= 6; i++) {
        const x = m.centro.x + i * 4.0;
        const z = m.zFundo + 3.5;
        cil(g, 0.01, 1.4, mat("#1f2937"), x, H - 1.6, z, 6);
        cil(g, 0.42, 0.35, mat("#475569", { metalness: 0.6, roughness: 0.3 }), x, H - 1.95, z, 24, 0.2);
        const lamp = malha(new T.CircleGeometry(0.4, 24), luz("#fffbeb", 3), x, H - 1.96, z);
        lamp.rotation.x = Math.PI / 2;
        g.add(lamp);
      }
      for (let i = -3; i <= 3; i += 2) solNoChao(g, m.centro.x + i * 4.2 + 1.5, m.max.z + 2.6, 2.4, 3.6, 0.35, 0.14);
      criancasAoFundo(g, [[m.max.x + 2.2, m.zFundo + 2.2, "correndo", -70], [m.min.x - 2.4, m.zFundo + 3.0, "andando", 80], [m.max.x + 4.2, m.centro.z + 2.0, "comemorando", -30]]);
      const frente = (naTela) => {
        const f = new T.Group();
        const p = naTela(-1.02, -0.98);
        if (p) {
          const cores = ["#f97316", "#facc15", "#22c55e", "#3b82f6"];
          [[0, 0, 0], [0.62, 0, 0.1], [0.3, 0.6, 0.05], [-0.5, 0, 0.5]].forEach(([dx, dy, dz], i) => caixa(f, 0.6, 0.6, 0.6, mat(cores[i], { roughness: 0.8 }), p.x + dx, dy, p.z + dz, i * 0.4));
        }
        return f;
      };
      return { grupo: g, frente, fundo: "#b8c6d6", neblina: ["#c7d3e0", m.maior * 4 + 20, m.maior * 9 + 90], luz: { ceu: "#f8fafc", chao: "#64748b", hemi: 1.05, sol: 2.2, amb: 0.5, exposicao: 1.0 } };
    },

    /* ------------------------------------------------------------ a brinquedoteca */
    brinquedoteca(caixaDos, giro, op = {}) {
      const g = new T.Group();
      const m = medidas(caixaDos, giro, op.atras ?? 1.2, op.lado ?? 1.4);
      const H = 5.5;
      chao(g, 120, 120, matTex("piso-brinquedoteca", 120, 120, 1.4, tacos(214, 168, 112), { roughness: 0.45 }), m.centro.x, m.centro.z);
      // as paredes: amarela com o arco-íris e as nuvens pintadas, e a do lado verde-água
      const pintura = matTex("parede-arco-iris", 14, H, 14, (c, l, a) => {
        c.fillStyle = "#fde68a";
        c.fillRect(0, 0, l, a);
        const cores = ["#ef4444", "#f97316", "#facc15", "#22c55e", "#3b82f6", "#8b5cf6"];
        cores.forEach((cor, i) => {
          c.strokeStyle = cor;
          c.lineWidth = 34;
          c.beginPath();
          c.arc(l * 0.5, a * 0.95, a * 0.6 - i * 34, Math.PI, 0);
          c.stroke();
        });
        c.fillStyle = "#ffffff";
        for (const [x, y, r] of [[0.12, 0.62, 44], [0.17, 0.58, 56], [0.23, 0.63, 40], [0.78, 0.6, 46], [0.84, 0.56, 58], [0.9, 0.61, 42]]) {
          c.beginPath();
          c.arc(l * x, a * y, r, 0, Math.PI * 2);
          c.fill();
        }
      }, { roughness: 0.9 }, 1024);
      pintura.map.repeat.set(1, 1);
      pintura.map.wrapS = pintura.map.wrapT = T.ClampToEdgeWrapping;
      parede(g, 120, H, mat("#fde68a", { roughness: 0.9 }), m.centro.x, m.zFundo - 0.01, 0);
      parede(g, 14, H, pintura, m.centro.x, m.zFundo, 0);
      parede(g, 120, H, mat("#5eead4", { roughness: 0.9 }), m.xLado, m.centro.z, m.giroLado);
      // o rodapé colorido
      parede(g, 120, 0.25, mat("#f9a8d4"), m.centro.x, m.zFundo + 0.01, 0);
      // a janela do lado, com a cortina
      const n = new T.Vector3(Math.sin(m.giroLado), 0, Math.cos(m.giroLado));
      const jz = m.centro.z - m.tam.z * 0.1;
      const jan = parede(g, 2.6, 1.8, luz("#e0f2fe", 1.0), m.xLado, jz, m.giroLado, 1.2);
      jan.position.addScaledVector(n, 0.02);
      for (const s of [-1, 1]) {
        const cort = caixa(g, 0.08, 2.4, 0.6, mat("#f9a8d4", { roughness: 0.9 }), m.xLado + n.x * 0.06, 0.9, jz + s * 1.55);
        if (!m.ladoEsq) cort.position.x = m.xLado + n.x * 0.06;
      }
      // as estantes de nichos com os brinquedos e os bichinhos
      const r = sorteio(8);
      const estante = (ex, ez, ry) => {
        const e = new T.Group();
        caixa(e, 2.4, 1.3, 0.4, mat("#ffffff", { roughness: 0.5 }), 0, 0, 0);
        for (let i = 0; i < 3; i++) for (let j = 0; j < 2; j++) {
          const cx = -0.8 + i * 0.8, cy = 0.12 + j * 0.6;
          caixa(e, 0.62, 0.42, 0.3, mat(["#f472b6", "#60a5fa", "#facc15", "#34d399", "#a78bfa", "#fb923c"][(i + j * 3) % 6], { roughness: 0.6 }), cx, cy, 0.08);
        }
        for (let i = 0; i < 3; i++) {
          const bx = -0.8 + i * 0.8;
          esf(e, 0.16, mat(["#fcd34d", "#f9a8d4", "#a5f3fc"][i], { roughness: 0.9 }), bx, 1.45, 0.02);
          esf(e, 0.12, mat(["#fcd34d", "#f9a8d4", "#a5f3fc"][i], { roughness: 0.9 }), bx, 1.68, 0.02);
        }
        e.position.set(ex, 0, ez);
        e.rotation.y = ry;
        g.add(e);
      };
      estante(m.ladoEsq ? m.max.x + 1.2 : m.min.x - 1.2, m.zFundo + 0.25, 0);
      estante(m.xLado + n.x * 0.25, m.centro.z + m.tam.z * 0.35, m.giroLado);
      // os pompons de papel pendurados
      for (let i = 0; i < 9; i++) {
        const x = m.min.x - 1 + r() * (m.tam.x + 2), z = m.zFundo + 0.8 + r() * 1.8, y = 3.4 + r() * 1.2;
        esf(g, 0.18 + r() * 0.12, mat(["#fbcfe8", "#bae6fd", "#fde68a", "#ddd6fe"][i % 4], { roughness: 0.9 }), x, y, z);
        cil(g, 0.005, H - y, mat("#e5e7eb"), x, y, z, 4);
      }
      return { grupo: g, fundo: "#fde68a", neblina: ["#fef3c7", 40, 120], luz: { ceu: "#fffbeb", chao: "#d6a870", hemi: 1.0, sol: 1.9, amb: 0.45, exposicao: 1.0 } };
    },

    /* ------------------------------------------------------------ a praça */
    praca(caixaDos, giro, op = {}) {
      const g = new T.Group();
      const m = medidas(caixaDos, giro, 3, 3);
      chao(g, 300, 300, matTex("grama", 300, 300, 2, (c, l, a) => {
        c.fillStyle = "#4ade80";
        c.fillRect(0, 0, l, a);
        const r = sorteio(3);
        for (let i = 0; i < 9000; i++) {
          c.fillStyle = ["#22c55e", "#16a34a", "#86efac", "#65a30d"][i % 4];
          c.fillRect(r() * l, r() * a, 2, 4);
        }
      }, { roughness: 0.95 }), m.centro.x, m.centro.z);
      // o piso de pedra da praça, redondo, embaixo dos brinquedos, e o caminho
      const raio = Math.max(m.tam.x, m.tam.z) * 0.62 + 1.6;
      const pedra = matTex("pedra", raio * 2, raio * 2, 1.0, ladrilhos("#d6b98f", "#a8875a", 3, 0.06), { roughness: 0.8 });
      const disco = malha(new T.CircleGeometry(raio, 64), pedra, m.centro.x, -0.001, m.centro.z);
      disco.rotation.x = -Math.PI / 2;
      disco.receiveShadow = true;
      g.add(disco);
      const borda = malha(new T.RingGeometry(raio, raio + 0.25, 64), mat("#9ca3af", { roughness: 0.7 }), m.centro.x, 0.0, m.centro.z);
      borda.rotation.x = -Math.PI / 2;
      g.add(borda);
      const caminho = chao(g, 2.4, 40, pedra, m.centro.x + raio * 0.5, m.centro.z - raio - 20, 0.0);
      caminho.rotation.z = 0.35;
      // o céu: o degradê e as nuvens
      const ceu = new T.Mesh(new T.SphereGeometry(220, 32, 16), new T.MeshBasicMaterial({
        side: T.BackSide, fog: false,
        map: tex("ceu", 512, 512, (c, l, a) => {
          const f = c.createLinearGradient(0, 0, 0, a);
          f.addColorStop(0, "#0284c7");
          f.addColorStop(0.42, "#38bdf8");
          f.addColorStop(0.5, "#bae6fd");
          f.addColorStop(1, "#bae6fd");
          c.fillStyle = f;
          c.fillRect(0, 0, l, a);
          c.filter = "blur(6px)";
          c.fillStyle = "rgba(255,255,255,.9)";
          const r = sorteio(6);
          for (let i = 0; i < 14; i++) {
            const x = r() * l, y = a * (0.25 + r() * 0.18);
            for (let k = 0; k < 4; k++) {
              c.beginPath();
              c.ellipse(x + k * 14, y + (k % 2) * 4, 22, 10, 0, 0, Math.PI * 2);
              c.fill();
            }
          }
          c.filter = "none";
        }),
      }));
      ceu.position.set(m.centro.x, 0, m.centro.z);
      g.add(ceu);
      // as árvores, os bancos, os postes e os canteiros em volta
      const r = sorteio(11);
      for (let i = 0; i < 16; i++) {
        const ang = Math.PI * (0.95 + r() * 1.1) + (m.ladoEsq ? 0 : 0.2);
        const dist = raio + 4 + r() * 12;
        arvore(g, m.centro.x + Math.cos(ang) * dist, m.centro.z + Math.sin(ang) * dist * 0.9, 4.5 + r() * 2.5, 20 + i);
      }
      for (let i = 0; i < 4; i++) {
        const ang = Math.PI * (1.05 + i * 0.28);
        const x = m.centro.x + Math.cos(ang) * (raio + 0.6), z = m.centro.z + Math.sin(ang) * (raio + 0.6);
        if (i % 2) banco(g, x, z, -ang - Math.PI / 2);
        else poste(g, x, z);
      }
      for (let i = 0; i < 3; i++) {
        const ang = Math.PI * (1.2 + i * 0.3);
        const x = m.centro.x + Math.cos(ang) * (raio + 2.2), z = m.centro.z + Math.sin(ang) * (raio + 2.2);
        cil(g, 0.9, 0.3, mat("#a8a29e"), x, 0, z, 24);
        for (let k = 0; k < 18; k++) esf(g, 0.12, mat(["#f43f5e", "#facc15", "#ffffff", "#c084fc"][k % 4]), x + (r() - 0.5) * 1.4, 0.38, z + (r() - 0.5) * 1.4, 8);
      }
      maquinasAoFundo(g, op.fundo, m, { folga: 1.6, distanciaDoFundo: 0.4 });
      cachoDeBaloes(g, m.centro.x - raio - 1.2, m.centro.z - 1.5, 2.4, 3);
      cachoDeBaloes(g, m.centro.x + raio + 0.8, m.centro.z - 2.5, 2.2, 6);
      criancasAoFundo(g, [[m.centro.x - raio - 2.4, m.centro.z - 3, "correndo", 70], [m.centro.x + raio + 2.6, m.centro.z - 4, "andando", -100], [m.centro.x + 1.5, m.centro.z - raio - 3, "comemorando", 10]]);
      const frente = (naTela) => {
        const f = new T.Group();
        const p = naTela(1.04, -0.98);
        if (p) {
          for (let k = 0; k < 7; k++) esf(f, 0.32 + (k % 3) * 0.08, mat(["#15803d", "#16a34a", "#22c55e"][k % 3], { roughness: 0.85 }), p.x + (k % 4) * 0.35 - 0.5, 0.3 + (k % 2) * 0.25, p.z + Math.floor(k / 4) * 0.4, 14);
          for (let k = 0; k < 14; k++) esf(f, 0.07, mat(["#f43f5e", "#facc15", "#ffffff", "#c084fc"][k % 4]), p.x + (k % 5) * 0.28 - 0.6, 0.62 + (k % 3) * 0.12, p.z + (k % 2) * 0.3, 8);
        }
        return f;
      };
      return { grupo: g, frente, fundo: "#7dd3fc", neblina: ["#cfe8fb", 60, 240], luz: { ceu: "#e0f2fe", chao: "#4ade80", hemi: 1.0, sol: 2.0, amb: 0.45, exposicao: 0.95 } };
    },

    /* ------------------------------------------------------------ o salão de festas do condomínio */
    salao(caixaDos, giro, op = {}) {
      const g = new T.Group();
      const m = medidas(caixaDos, giro, op.atras ?? 1.6, op.lado ?? 1.6);
      const H = 5.5;
      const piso = chao(g, 120, 120, matTex("tacos-salao", 120, 120, 1.6, tacos(170, 112, 68), { roughness: 0.3 }), m.centro.x, m.centro.z);
      refletir(g, piso, 0.16, "#5c3a1e", m);
      // o fundo de vidro: os caixilhos e, lá fora, o jardim e a piscina
      const fora = tex("jardim-piscina", 1024, 512, (c, l, a) => {
        const ceu = c.createLinearGradient(0, 0, 0, a * 0.45);
        ceu.addColorStop(0, "#7dd3fc");
        ceu.addColorStop(1, "#e0f2fe");
        c.fillStyle = ceu;
        c.fillRect(0, 0, l, a);
        c.filter = "blur(5px)";
        c.fillStyle = "#16a34a";
        for (let i = 0; i < 26; i++) {
          c.beginPath();
          c.arc((i / 26) * l + 10, a * 0.42 + Math.sin(i) * 14, 40 + (i % 3) * 14, 0, Math.PI * 2);
          c.fill();
        }
        c.fillStyle = "#86efac";
        c.fillRect(0, a * 0.5, l, a * 0.5);
        c.fillStyle = "#e7e5e4";
        c.fillRect(0, a * 0.6, l, a * 0.4);
        const agua = c.createLinearGradient(0, a * 0.66, 0, a);
        agua.addColorStop(0, "#22d3ee");
        agua.addColorStop(1, "#0284c7");
        c.fillStyle = agua;
        c.fillRect(l * 0.1, a * 0.68, l * 0.8, a * 0.26);
        c.filter = "none";
      });
      fora.wrapS = T.RepeatWrapping;
      fora.repeat.set(3, 1);
      parede(g, 60, H, new T.MeshBasicMaterial({ map: fora }), m.centro.x, m.zFundo - 0.3, 0);
      for (let i = -15; i <= 15; i++) caixa(g, 0.1, H, 0.12, mat("#1f2937", { metalness: 0.5 }), m.centro.x + i * 2.0, 0, m.zFundo);
      caixa(g, 60, 0.12, 0.14, mat("#1f2937", { metalness: 0.5 }), m.centro.x, 2.6, m.zFundo);
      caixa(g, 60, 0.6, 0.3, mat("#f5f5f4"), m.centro.x, H - 0.6, m.zFundo);
      // a parede do lado com o painel de ripas de madeira
      parede(g, 120, H, matTex("ripas", 120, H, 0.6, (c, l, a) => {
        c.fillStyle = "#7c4a24";
        c.fillRect(0, 0, l, a);
        for (let i = 0; i < 6; i++) {
          c.fillStyle = i % 2 ? "#a86a3a" : "#b5773f";
          c.fillRect((i * l) / 6 + 6, 0, l / 6 - 12, a);
        }
      }, { roughness: 0.6 }), m.xLado, m.centro.z, m.giroLado);
      // o sofá, a mesinha, a planta e os pendentes
      const n = new T.Vector3(Math.sin(m.giroLado), 0, Math.cos(m.giroLado));
      const sofa = new T.Group();
      caixa(sofa, 2.4, 0.42, 0.9, mat("#0f766e", { roughness: 0.9 }), 0, 0, 0);
      caixa(sofa, 2.4, 0.5, 0.22, mat("#0f766e", { roughness: 0.9 }), 0, 0.4, -0.34);
      for (const s of [-1, 1]) caixa(sofa, 0.22, 0.62, 0.9, mat("#115e59", { roughness: 0.9 }), s * 1.2, 0, 0);
      for (let i = 0; i < 3; i++) caixa(sofa, 0.5, 0.35, 0.12, mat(["#fde68a", "#fbcfe8", "#bae6fd"][i], { roughness: 0.9 }), -0.7 + i * 0.7, 0.5, -0.18);
      sofa.position.set(m.xLado + n.x * 0.6, 0, m.centro.z + m.tam.z * 0.1);
      sofa.rotation.y = m.giroLado;
      g.add(sofa);
      planta(g, m.ladoEsq ? m.max.x + 1.4 : m.min.x - 1.4, m.zFundo + 0.8, 1.9, "#d6d3d1", 9);
      for (let i = -3; i <= 3; i++) {
        const x = m.centro.x + i * 1.6, z = m.zFundo + 2.2;
        cil(g, 0.006, H - 2.6, mat("#111827"), x, 2.6, z, 4);
        const cupula = malha(new T.SphereGeometry(0.28, 20, 10, 0, Math.PI * 2, 0, Math.PI / 2), mat("#facc15", { metalness: 0.6, roughness: 0.3, side: T.DoubleSide }), x, 2.6, z);
        g.add(cupula);
        esf(g, 0.1, luz("#fffbeb", 2.5), x, 2.58, z);
      }
      for (let i = -3; i <= 3; i++) solNoChao(g, m.centro.x + i * 2.0 + 0.6, m.zFundo + 1.4, 1.5, 2.2, 0.25, 0.45);
      criancasAoFundo(g, [[m.max.x + 2.4, m.zFundo + 1.2, "andando", -70]]);
      const frente = (naTela) => {
        const f = new T.Group();
        const p = naTela(-1.04, -0.98);
        if (p) planta(f, p.x, p.z, 1.4, "#d6d3d1", 17);
        return f;
      };
      return { grupo: g, frente, fundo: "#f5efe6", neblina: ["#f5efe6", 26, 90], luz: { ceu: "#fffbeb", chao: "#b98455", hemi: 1.15, sol: 2.3, amb: 0.55, exposicao: 1.0 } };
    },

    /* ------------------------------------------------------------ a quadra da escola */
    quadra(caixaDos, giro, op = {}) {
      const g = new T.Group();
      const m = medidas(caixaDos, giro, op.atras ?? 2.4, op.lado ?? 2.4);
      const H = 9;
      // a quadra: o piso azul com as linhas, num entorno verde
      chao(g, 160, 160, mat("#15803d", { roughness: 0.7 }), m.centro.x, m.centro.z);
      const L = 22, P = 13;
      const quadra = chao(g, L, P, new T.MeshStandardMaterial({
        roughness: 0.45,
        map: tex("quadra", 1100, 650, (c, l, a) => {
          c.fillStyle = "#1d4ed8";
          c.fillRect(0, 0, l, a);
          c.fillStyle = "#f97316";
          c.fillRect(l * 0.02, a * 0.33, l * 0.13, a * 0.34);
          c.fillRect(l * 0.85, a * 0.33, l * 0.13, a * 0.34);
          c.strokeStyle = "#ffffff";
          c.lineWidth = 6;
          c.strokeRect(l * 0.02, a * 0.04, l * 0.96, a * 0.92);
          c.beginPath();
          c.moveTo(l / 2, a * 0.04);
          c.lineTo(l / 2, a * 0.96);
          c.stroke();
          c.beginPath();
          c.arc(l / 2, a / 2, a * 0.16, 0, Math.PI * 2);
          c.stroke();
          for (const [x, s] of [[0.02, 1], [0.98, -1]]) {
            c.beginPath();
            c.arc(l * x, a / 2, a * 0.38, -Math.PI / 2, Math.PI / 2, s < 0);
            c.stroke();
          }
          c.strokeStyle = "#facc15";
          c.strokeRect(l * 0.02, a * 0.33, l * 0.13, a * 0.34);
          c.strokeRect(l * 0.85, a * 0.33, l * 0.13, a * 0.34);
        }),
      }), m.centro.x, m.zFundo + P / 2 + 3.2, -0.001);
      quadra.receiveShadow = true;
      refletir(g, quadra, 0.14, "#1e3a8a", m);
      // o fundo: a arquibancada colorida, o muro e as janelas altas
      parede(g, 160, H, mat("#7dd3fc", { roughness: 0.9 }), m.centro.x, m.zFundo - 3.2, 0);
      const janelas = parede(g, 160, 1.6, luz("#f0f9ff", 0.9), m.centro.x, m.zFundo - 3.18, 0, H - 2.6);
      janelas.material = luz("#f0f9ff", 0.9);
      for (let i = 0; i < 5; i++) {
        caixa(g, 160, 0.45, 0.65, mat("#94a3b8", { roughness: 0.6 }), m.centro.x, i * 0.45, m.zFundo - 0.35 - i * 0.65);
        caixa(g, 160, 0.06, 0.4, mat(["#ef4444", "#facc15", "#3b82f6", "#22c55e", "#f97316"][i], { roughness: 0.5 }), m.centro.x, i * 0.45 + 0.45, m.zFundo - 0.3 - i * 0.65);
      }
      caixa(g, 160, 1.0, 0.1, mat("#1e3a8a", { roughness: 0.6 }), m.centro.x, 0, m.zFundo + 0.05);
      // a parede do lado, com a proteção azul e a tabela de basquete
      parede(g, 160, H, mat("#7dd3fc", { roughness: 0.9 }), m.xLado, m.centro.z, m.giroLado);
      parede(g, 160, 2.0, mat("#2563eb", { roughness: 0.8 }), m.xLado + Math.sin(m.giroLado) * 0.02, m.centro.z, m.giroLado);
      const n = new T.Vector3(Math.sin(m.giroLado), 0, Math.cos(m.giroLado));
      const tz = m.zFundo + P / 2 + 3.2;
      const tabela = caixa(g, 0.06, 1.05, 1.8, mat("#ffffff", { roughness: 0.3 }), m.xLado + n.x * 1.2, 2.75, tz);
      tabela.rotation.y = 0;
      caixa(g, 1.2, 0.08, 0.08, mat("#334155"), m.xLado + n.x * 0.6, 3.2, tz);
      const aro = malha(new T.TorusGeometry(0.23, 0.02, 10, 32), mat("#f97316"), m.xLado + n.x * 1.5, 3.05, tz);
      aro.rotation.x = Math.PI / 2;
      g.add(aro);
      // as faixas coloridas penduradas (sem nada escrito)
      for (let i = -4; i <= 4; i++) {
        caixa(g, 1.0, 2.2, 0.03, mat(["#ef4444", "#facc15", "#22c55e", "#3b82f6"][(i + 8) % 4], { roughness: 0.8 }), m.centro.x + i * 3.2, H - 4.4, m.zFundo - 3.1);
      }
      for (let i = -3; i <= 3; i++) solNoChao(g, m.centro.x + i * 3.2, m.zFundo + 3.6 + (i % 2) * 0.8, 1.6, 2.8, -0.3, 0.3);
      criancasAoFundo(g, [[m.max.x + 3.0, m.zFundo + 1.5, "correndo", -80], [m.min.x - 3.2, m.zFundo + 2.0, "comemorando", 40]]);
      const frente = (naTela) => {
        const f = new T.Group();
        const p = naTela(1.03, -0.97);
        if (p) for (let k = 0; k < 3; k++) cil(f, 0.16, 0.42, mat(k % 2 ? "#ffffff" : "#f97316", { roughness: 0.5 }), p.x + k * 0.5 - 0.5, 0, p.z + (k % 2) * 0.3, 20, 0.03);
        return f;
      };
      return { grupo: g, frente, fundo: "#7dd3fc", neblina: ["#bfe3fb", 40, 140], luz: { ceu: "#ffffff", chao: "#1d4ed8", hemi: 1.05, sol: 2.2, amb: 0.5, exposicao: 1.0 } };
    },

    /* ------------------------------------------------------------ o salão do mural (as capas) */
    // Como as imagens da fábrica (o Brinquedão Modelo 5 no salão): um lugar limpo e de verdade,
    // o produto sozinho no meio. As texturas são desenhadas aqui, em alta (o mural tem ~500 px
    // por metro; o piso, ~1000), sem foto nenhuma e sem marca.
    mural(caixaDos, giro, op = {}) {
      const g = new T.Group();
      const m = medidas(caixaDos, giro, op.atras ?? Math.max(1.0, m0(caixaDos) * 0.12), op.lado ?? Math.max(1.6, m0(caixaDos) * 0.18));
      // o pé-direito: o do salão (um tanto acima do produto) e sempre acima da câmera (a foto é de dentro)
      const H = op.teto ?? Math.max(3.2, m.tam.y + 0.95, (op.alturaDaCamera ?? 0) + 0.6);
      // o piso de madeira (as réguas desencontradas, o veio), com o brilho e o reflexo suaves
      const reguas = (c, l, a) => {
        const r = sorteio(41);
        const n = 11; // réguas de ~18 cm num quadro de 2 m
        const h = a / n;
        for (let i = 0; i < n; i++) {
          let x = -r() * l * 0.5;
          while (x < l) {
            const comp = l * (0.35 + r() * 0.4);
            const tom = 0.93 + r() * 0.12;
            c.fillStyle = `rgb(${Math.round(98 * tom)},${Math.round(58 * tom)},${Math.round(34 * tom)})`;
            c.fillRect(x, i * h, comp, h);
            for (let k = 0; k < 9; k++) {
              c.strokeStyle = `rgba(70,40,20,${0.05 + r() * 0.08})`;
              c.lineWidth = 1 + r() * 2;
              const yy = i * h + r() * h;
              c.beginPath();
              c.moveTo(x, yy);
              c.bezierCurveTo(x + comp * 0.3, yy + (r() - 0.5) * 6, x + comp * 0.7, yy + (r() - 0.5) * 6, x + comp, yy);
              c.stroke();
            }
            c.fillStyle = "rgba(40,22,10,0.55)";
            c.fillRect(x, i * h, 2, h);
            x += comp;
          }
          c.fillStyle = "rgba(40,22,10,0.45)";
          c.fillRect(0, i * h, l, 2);
        }
      };
      const piso = chao(g, 160, 160, matTex("piso-madeira", 160, 160, 2.0, reguas, { roughness: 0.38, envMapIntensity: 0.6 }, 2048), m.centro.x, m.centro.z);
      refletir(g, piso, 0.08, "#3a2212", m);
      // o mural da parede do fundo (um quadro de 12 m, repetido)
      const quadro = 12;
      const desenhoMural = (c, l, a) => {
        const r = sorteio(op.semente ?? 7);
        const px = l / quadro;
        const y = (metros) => a - metros * px;
        const ceu = c.createLinearGradient(0, 0, 0, a);
        ceu.addColorStop(0, "#47b6ea");
        ceu.addColorStop(0.55, "#93d6f4");
        ceu.addColorStop(1, "#d8f1fb");
        c.fillStyle = ceu;
        c.fillRect(0, 0, l, a);
        // as nuvens: bolas brancas juntas, com a sombra azulada embaixo
        const nuvem = (cx, cy, s) => {
          c.fillStyle = "rgba(160,200,225,0.55)";
          for (const [dx, dy, rr] of [[-1.1, 0.25, 0.55], [-0.4, 0.3, 0.7], [0.45, 0.3, 0.62], [1.1, 0.28, 0.48]]) {
            c.beginPath(); c.arc(cx + dx * s, cy + dy * s + s * 0.12, rr * s, 0, PI * 2); c.fill();
          }
          c.fillStyle = "#ffffff";
          for (const [dx, dy, rr] of [[-1.1, 0.2, 0.5], [-0.45, -0.15, 0.72], [0.35, -0.3, 0.8], [1.05, 0.12, 0.52], [0.0, 0.25, 0.6]]) {
            c.beginPath(); c.arc(cx + dx * s, cy + dy * s, rr * s, 0, PI * 2); c.fill();
          }
        };
        for (let k = 0; k < 5; k++) nuvem((k + 0.3 + r() * 0.5) * l / 5, y(3.6 + r() * 1.2), px * (0.32 + r() * 0.16));
        // os morros ao longe
        for (const [cor, base, alto] of [["#9fd8b0", 1.5, 1.0], ["#7cc68f", 1.3, 0.7]]) {
          c.fillStyle = cor;
          c.beginPath();
          c.moveTo(0, a);
          for (let x = 0; x <= l; x += l / 60) c.lineTo(x, y(base + alto * (0.5 + 0.5 * Math.sin((x / l) * PI * 4 + base * 3))));
          c.lineTo(l, a);
          c.fill();
        }
        // as árvores: o tronco (com os galhos) à mostra entre os arbustos e a copa, e a copa num cacho de
        // bolas sombreado (o verde escuro embaixo e atrás, o claro em cima, onde bate a luz)
        const arvore = (cx, alt, s) => {
          const base = y(1.0), topo = y(alt - 0.55 * s);
          c.fillStyle = "#6f4428";
          c.beginPath();
          c.moveTo(cx - 0.11 * px * s, base);
          c.quadraticCurveTo(cx - 0.05 * px * s, (base + topo) / 2, cx - 0.06 * px * s, topo);
          c.lineTo(cx + 0.06 * px * s, topo);
          c.quadraticCurveTo(cx + 0.05 * px * s, (base + topo) / 2, cx + 0.11 * px * s, base);
          c.fill();
          c.strokeStyle = "#6f4428";
          c.lineWidth = 0.04 * px * s;
          c.lineCap = "round";
          for (const lado of [-1, 1]) {
            c.beginPath();
            c.moveTo(cx, y(alt - 0.9 * s));
            c.quadraticCurveTo(cx + lado * 0.2 * px * s, y(alt - 0.75 * s), cx + lado * 0.32 * px * s, y(alt - 0.45 * s));
            c.stroke();
          }
          const rr = sorteio(Math.round(cx));
          const bolas = [];
          for (let k = 0; k < 16; k++) {
            const a = rr() * PI * 2, d = Math.sqrt(rr()) * 0.62;
            bolas.push([Math.cos(a) * d * 1.15, Math.sin(a) * d * 0.85, 0.3 + rr() * 0.18]);
          }
          const cy = y(alt);
          for (const [cor, dx, dy, f] of [["#2f7d32", 0.05, 0.06, 1.0], ["#4f9e34", 0.02, 0.02, 0.92], ["#76b843", -0.02, -0.03, 0.78], ["#a4d150", -0.06, -0.08, 0.5]]) {
            c.fillStyle = cor;
            for (const [bx, by, br] of bolas) {
              c.beginPath();
              c.arc(cx + (bx + dx) * px * s, cy - (by - dy) * px * s, br * f * px * s, 0, PI * 2);
              c.fill();
            }
          }
        };
        for (let k = 0; k < 4; k++) arvore((k + 0.15 + r() * 0.7) * l / 4, 3.0 + r() * 0.7, 1.0 + r() * 0.3);
        // os arbustos e a grama
        for (let x = -px * 0.3; x < l + px; x += px * (0.45 + r() * 0.3)) {
          const rr = px * (0.28 + r() * 0.18);
          c.fillStyle = r() > 0.5 ? "#4fae4a" : "#5fbd55";
          c.beginPath(); c.arc(x, y(1.05), rr, PI, 0); c.fill();
        }
        c.fillStyle = "#58b14e";
        c.fillRect(0, y(1.08), l, 1.08 * px);
        // a cerca de madeira amarela (as ripas com a ponta, as travessas)
        const ripa = 0.16 * px, vao = 0.06 * px;
        c.fillStyle = "#e7b53c";
        c.fillRect(0, y(0.82), l, 0.08 * px);
        c.fillRect(0, y(0.42), l, 0.08 * px);
        for (let x = 0; x < l; x += ripa + vao) {
          c.fillStyle = "#f6cf55";
          c.beginPath();
          c.moveTo(x, y(0.12));
          c.lineTo(x, y(1.02));
          c.lineTo(x + ripa / 2, y(1.12));
          c.lineTo(x + ripa, y(1.02));
          c.lineTo(x + ripa, y(0.12));
          c.fill();
          c.fillStyle = "rgba(160,110,20,0.35)";
          c.fillRect(x + ripa - 3, y(1.02), 3, 0.9 * px);
        }
        // o chão do mural (a grama até o rodapé)
        c.fillStyle = "#4ea347";
        c.fillRect(0, y(0.12), l, 0.12 * px);
      };
      const texMural = tex("mural-" + (op.semente ?? 7) + "-" + H.toFixed(1), 6144, Math.round((6144 * H) / quadro), desenhoMural);
      const larguraParede = 200;
      const tMural = texMural.clone();
      tMural.needsUpdate = true;
      tMural.repeat.set(larguraParede / quadro, 1);
      tMural.offset.x = (((m.centro.x - larguraParede / 2) / quadro) % 1 + 1) % 1;
      parede(g, larguraParede, H, new T.MeshStandardMaterial({ map: tMural, roughness: 0.85 }), m.centro.x, m.zFundo, 0);
      // o rodapé branco
      const rodape = parede(g, larguraParede, 0.1, mat("#f8fafc", { roughness: 0.4 }), m.centro.x, m.zFundo, 0);
      rodape.position.z += 0.012;
      // a parede do lado (verde, lisa) com a janela
      parede(g, larguraParede, H, mat(op.lateral || "#1f6b45", { roughness: 0.9 }), m.xLado, m.centro.z, m.giroLado);
      const lado = m.ladoEsq ? 1 : -1;
      const janela = new T.Group();
      caixa(janela, 0.08, 1.5, 2.2, mat("#f8fafc", { roughness: 0.35 }), 0, 0, 0);
      const desenhoJanela = (c, l, a) => {
        const d = c.createLinearGradient(0, 0, 0, a);
        d.addColorStop(0, "#9fd2f2");
        d.addColorStop(0.7, "#cfe8f7");
        d.addColorStop(1, "#b9dcc0");
        c.fillStyle = d;
        c.fillRect(0, 0, l, a);
        c.fillStyle = "#f8fafc";
        c.fillRect(l / 2 - 10, 0, 20, a);
        c.fillRect(0, a * 0.42 - 8, l, 16);
      };
      const tJanela = tex("janela", 1024, 680, desenhoJanela);
      const vidro = malha(new T.PlaneGeometry(2.0, 1.32), new T.MeshStandardMaterial({ map: tJanela, emissiveMap: tJanela, emissive: "#ffffff", emissiveIntensity: 0.45, roughness: 0.2 }), lado * 0.045, 0.75, 0);
      vidro.rotation.y = (lado * PI) / 2;
      janela.add(vidro);
      janela.position.set(m.xLado, 0.95, m.zFundo + Math.max(2.4, m.tam.z * 0.5 + 1.6));
      g.add(janela);
      // o teto claro, a sanca e os spots
      // (a luz que rebate no teto: mais clara em cima do produto e perto do mural, um degradê largo)
      const desenhoTeto = (c, l, a) => {
        const d = c.createRadialGradient(l / 2, a * 0.3, 0, l / 2, a * 0.3, l * 0.6);
        d.addColorStop(0, "#fbfbfa");
        d.addColorStop(1, "#d9d9d6");
        c.fillStyle = d;
        c.fillRect(0, 0, l, a);
      };
      const tTeto = tex("teto", 1024, 1024, desenhoTeto);
      const lado2 = Math.max(30, m.maior * 3);
      const teto = malha(new T.PlaneGeometry(lado2, lado2), new T.MeshStandardMaterial({ map: tTeto, emissiveMap: tTeto, emissive: "#ffffff", emissiveIntensity: 0.38, roughness: 0.9 }), m.centro.x, H, m.zFundo + lado2 / 2);
      teto.rotation.x = PI / 2;
      g.add(teto);
      // a sanca branca em cima do mural, com a fita de LED quente escondida
      caixa(g, larguraParede, 0.14, 0.22, mat("#ffffff", { roughness: 0.6 }), m.centro.x, H - 0.14, m.zFundo + 0.11);
      caixa(g, larguraParede, 0.025, 0.03, luz("#fff1d6", 2.2), m.centro.x, H - 0.16, m.zFundo + 0.23);
      // os spots embutidos, em fileiras do mural até a frente
      const passo = Math.max(1.8, m.maior / 6);
      for (let i = -8; i <= 8; i++) {
        for (let k = 0; k < 6; k++) {
          const spot = malha(new T.CircleGeometry(0.075, 24), luz("#fff7e6", 3.2), m.centro.x + i * passo, H - 0.005, m.zFundo + 1.0 + k * passo);
          spot.rotation.x = PI / 2;
          g.add(spot);
          const aro = malha(new T.RingGeometry(0.075, 0.095, 24), mat("#e5e7eb", { roughness: 0.4, metalness: 0.4 }), m.centro.x + i * passo, H - 0.004, m.zFundo + 1.0 + k * passo);
          aro.rotation.x = PI / 2;
          g.add(aro);
        }
      }
      // num canto, longe do produto: a mesinha branca e as cadeiras (como nas imagens da fábrica)
      if (op.mesa !== false) {
        const [mx, mz] = op.mesa || [m.ladoEsq ? m.max.x + 1.5 : m.min.x - 1.5, m.zFundo + 0.95];
        const branco = mat("#f8fafc", { roughness: 0.35 });
        const metal = mat("#d6d3d1", { roughness: 0.3, metalness: 0.6 });
        cil(g, 0.42, 0.025, branco, mx, 0.55, mz, 48);
        cil(g, 0.025, 0.55, metal, mx, 0, mz, 12);
        cil(g, 0.22, 0.02, metal, mx, 0, mz, 32);
        for (let k = 0; k < 4; k++) {
          const a = (k / 4) * PI * 2 + PI / 4;
          const cadeira = new T.Group();
          const assento = malha(new T.SphereGeometry(0.22, 32, 16, 0, PI * 2, PI * 0.55, PI * 0.45), branco, 0, 0.62, 0);
          assento.scale.set(1, 0.55, 1);
          cadeira.add(assento);
          const encosto = malha(new T.SphereGeometry(0.22, 32, 16, PI * 0.15, PI * 0.7, PI * 0.3, PI * 0.3), branco, 0, 0.5, 0);
          encosto.scale.set(1, 1.2, 1);
          cadeira.add(encosto);
          for (const [lx, lz] of [[-0.13, -0.13], [0.13, -0.13], [-0.13, 0.13], [0.13, 0.13]]) {
            const perna = malha(new T.CylinderGeometry(0.012, 0.012, 0.42, 8), mat("#c8a27a", { roughness: 0.5 }), lx * 0.8, 0.2, lz * 0.8);
            perna.rotation.set(lz * 0.6, 0, -lx * 0.6);
            cadeira.add(perna);
          }
          cadeira.position.set(mx + Math.cos(a) * 0.6, 0, mz + Math.sin(a) * 0.6);
          cadeira.rotation.y = -a - PI / 2;
          g.add(cadeira);
        }
      }
      return {
        grupo: g, fundo: "#f5f5f4", neblina: null,
        luz: { ceu: "#ffffff", chao: "#b98b62", hemi: op.hemi ?? 0.95, sol: op.sol ?? 1.7, amb: op.amb ?? 0.75, exposicao: op.exposicao ?? 1.0 },
      };
    },

    /* ------------------------------------------------------------ a loja de peças */
    // De perto, no balcão: as peças da frente são as `maquinas` da cena (nítidas);
    // aqui, o balcão embaixo delas, e atrás, desfocados, o painel perfurado com as
    // peças nos ganchos, as prateleiras com o estoque (as fotos das peças do
    // catálogo, `extra.peca`), a fita de LED quente e as luzinhas.
    loja(caixaDos, giro, op = {}) {
      const g = new T.Group();
      const c = caixaDos.getCenter(new T.Vector3());
      const topo = caixaDos.min.y;
      const zf = caixaDos.min.z - (op.atras ?? 0.75);
      const r = sorteio(17);
      const peca = (chave, x, y, z, opcoes = {}) => extra.peca && g.add(extra.peca(chave, Object.assign({ x, y, z, r: (r() - 0.5) * 8 }, opcoes)));
      // o chão, a parede atrás (escura: as peças e as luzes saltam) e o balcão de madeira
      chao(g, 40, 40, mat("#3f2a1c", { roughness: 0.5 }), c.x, c.z);
      parede(g, 30, 6, mat(op.parede || "#0f3d3e", { roughness: 0.85 }), c.x, zf - 0.03);
      const veio = (base) => (ctx, l, a) => {
        ctx.fillStyle = base;
        ctx.fillRect(0, 0, l, a);
        const rr = sorteio(31);
        for (let i = 0; i < 70; i++) {
          ctx.fillStyle = `rgba(${70 + rr() * 40},${42 + rr() * 25},${22 + rr() * 15},${0.1 + rr() * 0.16})`;
          ctx.fillRect(0, rr() * a, l, 1 + rr() * 4);
        }
      };
      const fundoBalcao = caixaDos.max.z + 0.3;
      caixa(g, 6, 0.045, fundoBalcao - zf + 0.2, matTex("tampo-loja", 6, 1, 0.9, veio("#9a6a40"), { roughness: 0.36, envMapIntensity: 0.6 }), c.x, topo - 0.045, (fundoBalcao + zf - 0.2) / 2);
      caixa(g, 6, topo - 0.045, 0.04, mat(op.balcao || "#ea580c", { roughness: 0.5 }), c.x, 0, fundoBalcao - 0.05);
      // o painel perfurado azul na parede, com as peças nos ganchos
      const furos = (ctx, l, a) => {
        ctx.fillStyle = "#0e7490";
        ctx.fillRect(0, 0, l, a);
        ctx.fillStyle = "#083344";
        for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) {
          ctx.beginPath();
          ctx.arc(((i + 0.5) * l) / 4, ((j + 0.5) * a) / 4, l / 30, 0, Math.PI * 2);
          ctx.fill();
        }
      };
      parede(g, 3.2, 1.2, matTex("painel-furos", 3.2, 1.2, 0.1, furos, { roughness: 0.8 }), c.x, zf, 0, topo);
      for (const [chave, x, y] of [
        ["cabo-hdmi", -1.0, 0.5], ["boneco-pebolim", -0.72, 0.48], ["cabo-hdmi", -0.44, 0.5], ["maneta-air-game", -0.2, 0.46],
        ["boneco-pebolim", 0.06, 0.48], ["cabo-hdmi", 0.34, 0.5], ["maneta-air-game", 0.58, 0.46], ["boneco-pebolim", 0.82, 0.48], ["cabo-hdmi", 1.1, 0.5],
      ]) {
        cil(g, 0.005, 0.08, mat("#e5e7eb", { metalness: 0.8, roughness: 0.3 }), c.x + x, topo + y, zf + 0.04, 6).rotation.x = Math.PI / 2;
        peca(chave, c.x + x, topo + y - 0.15, zf + 0.06, { semContato: true });
      }
      // a prateleira do estoque (as peças e as caixas lisas, sem marca), com a fita de LED quente
      const prateleira = 0.1;
      caixa(g, 3.2, 0.03, 0.3, matTex("prateleira", 3.2, 0.3, 0.9, veio("#b98552"), { roughness: 0.4 }), c.x, topo + prateleira - 0.03, zf + 0.15);
      caixa(g, 3.2, 0.012, 0.02, luz("#ffcf8a", 2.4), c.x, topo + 0.6, zf + 0.06);
      const cores = ["#c8a26b", "#ef4444", "#3b82f6", "#facc15", "#22c55e", "#d6b07a", "#ec4899"];
      let x = c.x - 1.5;
      let k = 0;
      while (x < c.x + 1.5) {
        const tipo = k % 5;
        if (tipo === 0 || tipo === 3) { peca("cabo-flexivel", x + 0.15, topo + prateleira, zf + 0.15, { escala: 0.75 }); x += 0.26; }
        else if (tipo === 1) { peca("mini-caixa-de-som", x + 0.05, topo + prateleira, zf + 0.18); peca("mini-caixa-de-som", x + 0.14, topo + prateleira, zf + 0.2); x += 0.22; }
        else {
          for (let n = 0; n < 2; n++) {
            const la = 0.09 + r() * 0.07;
            caixa(g, 0.1 + r() * 0.04, la, 0.12, mat(cores[(k * 2 + n) % cores.length], { roughness: 0.7 }), x + 0.06 + n * 0.13, topo + prateleira, zf + 0.15, (r() - 0.5) * 0.3);
          }
          x += 0.28;
        }
        k++;
      }
      // os pendentes quentes, as luzinhas e, no balcão, as caixas lisas e o vasinho
      for (const px of [-0.42, 0.42]) {
        cil(g, 0.004, 1.2, mat("#1f2937"), c.x + px, topo + 0.62, c.z - 0.42, 4);
        cil(g, 0.08, 0.07, mat("#1f2937", { roughness: 0.4, metalness: 0.5 }), c.x + px, topo + 0.55, c.z - 0.42, 24, 0.025);
        esf(g, 0.035, luz("#ffe2b0", 3.2), c.x + px, topo + 0.55, c.z - 0.42, 14);
      }
      for (let i = 0; i <= 30; i++) {
        const t = i / 30;
        esf(g, 0.014, luz(["#ffd59a", "#fde68a", "#fbcfe8", "#fed7aa"][i % 4], 3.4), c.x - 1.5 + 3.0 * t, topo + 0.56 - Math.sin(t * Math.PI * 4) ** 2 * 0.05, zf + 0.09, 10);
      }
      caixa(g, 0.2, 0.11, 0.15, mat("#c8a26b", { roughness: 0.75 }), c.x - 0.52, topo, c.z - 0.2, 0.2);
      caixa(g, 0.16, 0.09, 0.12, mat("#d6b07a", { roughness: 0.75 }), c.x - 0.51, topo + 0.11, c.z - 0.21, 0.1);
      cil(g, 0.05, 0.09, mat("#f8fafc", { roughness: 0.35 }), c.x + 0.5, topo, c.z - 0.24, 20, 0.06);
      for (let i = 0; i < 7; i++) esf(g, 0.035 + r() * 0.02, mat(["#15803d", "#16a34a", "#22c55e"][i % 3], { roughness: 0.8 }), c.x + 0.5 + (r() - 0.5) * 0.1, topo + 0.13 + r() * 0.08, c.z - 0.24 + (r() - 0.5) * 0.08, 12);
      return {
        grupo: g, fundo: "#0f3d3e", neblina: null,
        luz: { ceu: "#ffdcae", chao: "#5b3a22", hemi: 0.8, sol: 1.6, amb: 0.45, exposicao: 0.97 },
      };
    },
  };

  function m0(caixaDos) {
    const t = caixaDos.getSize(new T.Vector3());
    return Math.max(t.x, t.z);
  }

  return LUGARES;
}
