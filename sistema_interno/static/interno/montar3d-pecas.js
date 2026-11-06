/* ======================================================================
   AS PEÇAS NOVAS DO "MONTAR EM 3D" (o editor é o montar3d.js).

   Tiradas do que se vê nos playgrounds indoor, nos espaços esportivos kids
   e nas áreas ninja de verdade (só o padrão do ramo, nenhum desenho
   copiado):
     * estrutura: piso de EVA (xadrez de duas cores ou liso, como grama),
       painel com janela redonda, painel ábaco (as bolinhas nas varetas),
       teto em arco (o das torres do tema selva), fita de LED (o tema neon);
     * brincadeiras: tobogã espiral (tubo fechado ou calha aberta), túnel de
       rede, rolos (as colunas de espuma de passar no meio), colmeia (os
       hexágonos empilhados), bolas penduradas, piscina redonda, piscina de
       espuma, rampa e degraus de espuma, portal;
     * esporte e ninja: quadra com as linhas, trave de gol, tabela de
       basquete, parede de escalada com agarras, colchão, degraus ninja,
       trave de equilíbrio, argolas, barra de macaco, corda, parede curva.

   Cada desenho: um grupo com a base no chão (y = 0) e o meio em x = z = 0
   (o tobogã: o eixo da espiral; a boca fica do lado -x, de frente para a
   torre). `h` traz as ferramentas do editor (material, malha, tubo...).
   ====================================================================== */

export const GRUPOS = { estrutura: "Estrutura", brincar: "Brincadeiras", esporte: "Esporte e ninja" };

export const CATALOGO_EXTRA = {
  piso_eva: { nome: "Piso de EVA", grupo: "estrutura", d: { largura: 4, profundidade: 4 }, cor: "#22c55e", cor2: "#facc15" },
  janela: { nome: "Painel com janela", grupo: "estrutura", d: { largura: 1.05, altura: 0.9, espessura: 0.03 }, cor: "#f97316" },
  abaco: { nome: "Painel ábaco", grupo: "estrutura", d: { largura: 1.05, altura: 0.9 }, cor: "#8b5cf6" },
  teto_arco: { nome: "Teto em arco", grupo: "estrutura", d: { largura: 1.05, profundidade: 1.05, altura: 0.5 }, cor: "#6b4f3a" },
  led: { nome: "Fita de LED", grupo: "estrutura", d: { comprimento: 1.05 }, cor: "#3fd0ff" },

  toboga: { nome: "Tobogã espiral", grupo: "brincar", d: { altura: 2.5, raio: 1.0, voltas: 1.25, fechado: 1, espelhado: 0 }, cor: "#22c55e" },
  tunel_rede: { nome: "Túnel de rede", grupo: "brincar", d: { comprimento: 1.0, diametro: 0.62 }, cor: "#1f2937" },
  rolos: { nome: "Rolos", grupo: "brincar", d: { altura: 0.85, largura: 0.95, quantidade: 4 }, cor: "#ef4444" },
  colmeia: { nome: "Colmeia", grupo: "brincar", d: { largura: 0.9, altura: 2.6, profundidade: 0.8 }, cor: "#84cc16" },
  pendulos: { nome: "Bolas penduradas", grupo: "brincar", d: { largura: 0.95, altura: 0.95, quantidade: 3 }, cor: "#2563eb" },
  piscina_redonda: { nome: "Piscina redonda", grupo: "brincar", d: { diametro: 2.4, altura: 0.5 }, cor: "#6b4f3a" },
  espuma: { nome: "Piscina de espuma", grupo: "brincar", d: { largura: 3.0, profundidade: 4.0, altura: 0.9 }, cor: "#2563eb" },
  rampa: { nome: "Rampa de espuma", grupo: "brincar", d: { comprimento: 1.2, altura: 0.35, largura: 0.9 }, cor: "#facc15" },
  degraus_espuma: { nome: "Degraus de espuma", grupo: "brincar", d: { largura: 0.8, altura: 0.6, degraus: 3 }, cor: "#f97316" },
  arco: { nome: "Portal", grupo: "brincar", d: { largura: 1.4, altura: 2.0 }, cor: "#ec4899" },

  quadra: { nome: "Quadra", grupo: "esporte", d: { largura: 14, profundidade: 8 }, cor: "#1d4ed8" },
  gol: { nome: "Trave de gol", grupo: "esporte", d: { largura: 2.4, altura: 1.6 }, cor: "#ffffff" },
  tabela: { nome: "Tabela de basquete", grupo: "esporte", d: { altura: 2.6 }, cor: "#ef4444" },
  escalada: { nome: "Parede de escalada", grupo: "esporte", d: { largura: 3.0, altura: 3.5 }, cor: "#0ea5e9" },
  colchao: { nome: "Colchão", grupo: "esporte", d: { largura: 2.0, profundidade: 1.6, espessura: 0.25 }, cor: "#2563eb" },
  degraus: { nome: "Degraus ninja", grupo: "esporte", d: { comprimento: 3.2, largura: 1.2 }, cor: "#f97316" },
  trave: { nome: "Trave de equilíbrio", grupo: "esporte", d: { comprimento: 2.5, altura: 0.45 }, cor: "#facc15" },
  argolas: { nome: "Argolas", grupo: "esporte", d: { comprimento: 3.0, altura: 2.3, quantidade: 4 }, cor: "#1f2937" },
  macaco: { nome: "Barra de macaco", grupo: "esporte", d: { comprimento: 3.0, altura: 2.3, largura: 0.6 }, cor: "#1f2937" },
  corda: { nome: "Corda de subir", grupo: "esporte", d: { altura: 3.0 }, cor: "#1f2937" },
  parede_curva: { nome: "Parede curva", grupo: "esporte", d: { largura: 2.0, altura: 3.0 }, cor: "#facc15" },
};

/** As peças antigas, cada uma no seu grupo da biblioteca. */
export const GRUPO_DAS_ANTIGAS = {
  coluna: "estrutura", barra: "estrutura", plataforma: "estrutura", painel: "estrutura", rede: "estrutura",
  cerca: "estrutura", telhado: "estrutura", escorregador: "brincar", escada: "brincar", tunel: "brincar",
  cama: "brincar", piscina: "brincar",
};

/** As peças que aceitam a segunda cor (a diagonal das plataformas, o xadrez do EVA, a moldura da rede). */
export const COM_COR2 = new Set(["plataforma", "piso_eva", "rede"]);

export function desenhosExtra(T, h) {
  const { material, malha, caixa, tubo, redeMat, aleatorio, juntar } = h;
  const variar = (cor, passo) => {
    const c = new T.Color(cor);
    const hsl = c.getHSL({});
    if (hsl.s < 0.15) return "#" + new T.Color().setHSL((passo * 0.17) % 1, 0.75, 0.55).getHexString();
    return "#" + c.offsetHSL(passo * 0.17, 0, 0).getHexString();
  };
  const clarear = (cor, f) => "#" + new T.Color(cor).lerp(new T.Color("#ffffff"), f).getHexString();
  const escurecer = (cor, f) => "#" + new T.Color(cor).lerp(new T.Color("#000000"), f).getHexString();
  const cinza = () => material("#9ca3af", { metalness: 0.35, roughness: 0.4 });
  const VIVAS = ["#ef4444", "#facc15", "#2563eb", "#22c55e", "#ec4899", "#f97316"];
  const porCor = (lista, cores, mat) => cores.map((c, i) => (lista[i] && lista[i].length ? malha(juntar(lista[i]), mat(c)) : null)).filter(Boolean);

  /** Um prisma pela silhueta (x, y) no plano de pé, com a espessura no eixo z (centrada). */
  function silhueta(pontos, espessura, furos) {
    const forma = new T.Shape(pontos.map(([x, y]) => new T.Vector2(x, y)));
    (furos || []).forEach((f) => forma.holes.push(f));
    const g = new T.ExtrudeGeometry(forma, { depth: espessura, bevelEnabled: false, curveSegments: 28 });
    g.translate(0, 0, -espessura / 2);
    return g;
  }
  /** Um prisma deitado: a silhueta (x, z) no chão, com a altura `e` para cima. */
  function deitado(pontos, e) {
    const forma = new T.Shape(pontos.map(([x, z]) => new T.Vector2(x, -z)));
    const g = new T.ExtrudeGeometry(forma, { depth: e, bevelEnabled: false });
    g.rotateX(-Math.PI / 2);
    return g;
  }

  return {
    /* ------------------------------------------------------------ estrutura */
    piso_eva(d, cor, extra) {
      const L = d.largura, P = d.profundidade;
      const lado = L * P > 6 ? 1.0 : 0.5;
      const nx = Math.max(1, Math.round(L / lado)), nz = Math.max(1, Math.round(P / lado));
      const lx = L / nx, lz = P / nz;
      const outra = (extra && extra.cor2) || clarear(cor, 0.45);
      const grupos = [[], []];
      for (let i = 0; i < nx; i++) {
        for (let k = 0; k < nz; k++) {
          const g = caixa(lx - 0.006, 0.02, lz - 0.006);
          g.translate(-L / 2 + (i + 0.5) * lx, 0.01, -P / 2 + (k + 0.5) * lz);
          grupos[(i + k) % 2].push(g);
        }
      }
      return porCor(grupos, [cor, outra], (c) => material(c, { roughness: 0.85 }));
    },
    janela(d, cor) {
      const L = d.largura, A = d.altura, e = d.espessura;
      const r = Math.min(L, A) * 0.32, cy = A * 0.55;
      const furo = new T.Path();
      furo.absarc(0, cy, r, 0, Math.PI * 2, true);
      const painel = malha(silhueta([[-L / 2, 0], [L / 2, 0], [L / 2, A], [-L / 2, A]], e, [furo]), material(cor));
      const aro = malha(new T.TorusGeometry(r, Math.max(0.02, e * 0.9), 10, 40), material("#ffffff"));
      aro.position.set(0, cy, 0);
      return [painel, aro];
    },
    abaco(d, cor) {
      const L = d.largura, A = d.altura, grupo = [];
      const moldura = material(cor, { metalness: 0.15 });
      const w = L / 2 - 0.03;
      grupo.push(tubo(0.03, L, [-w, 0.04, 0], [w, 0.04, 0], moldura), tubo(0.03, L, [-w, A - 0.03, 0], [w, A - 0.03, 0], moldura),
        tubo(0.03, A, [-w, 0, 0], [-w, A, 0], moldura), tubo(0.03, A, [w, 0, 0], [w, A, 0], moldura));
      const varetas = Math.max(2, Math.round((A - 0.25) / 0.2));
      const sorte = aleatorio(Math.round(L * 997 + A * 131));
      const contas = VIVAS.map(() => []);
      for (let i = 0; i < varetas; i++) {
        const y = 0.15 + (i * (A - 0.3)) / Math.max(1, varetas - 1);
        grupo.push(tubo(0.008, L - 0.06, [-w, y, 0], [w, y, 0], cinza()));
        const n = Math.max(3, Math.round(L / 0.18));
        const desvio = (sorte() - 0.5) * L * 0.35;
        for (let j = 0; j < n; j++) {
          const g = new T.SphereGeometry(0.045, 10, 8);
          g.translate(Math.max(-w + 0.05, Math.min(w - 0.05, desvio + (j - n / 2) * 0.095)), y, 0);
          contas[(i + j) % contas.length].push(g);
        }
      }
      return grupo.concat(porCor(contas, VIVAS, (c) => material(c, { roughness: 0.3 })));
    },
    teto_arco(d, cor) {
      const L = d.largura, P = d.profundidade, A = d.altura, grupo = [];
      const mat = material(cor, { metalness: 0.2, roughness: 0.4 });
      for (const z of [-P / 2, 0, P / 2]) {
        const g = new T.TorusGeometry(L / 2, 0.035, 8, 36, Math.PI);
        g.scale(1, A / (L / 2), 1);
        g.translate(0, 0, z);
        grupo.push(malha(g, mat));
      }
      grupo.push(tubo(0.035, P, [0, A, -P / 2], [0, A, P / 2], mat));
      return grupo;
    },
    led(d, cor) {
      const g = caixa(d.comprimento, 0.035, 0.035);
      g.translate(0, 0.018, 0);
      const m = malha(g, material(cor, { emissive: cor, emissiveIntensity: 2.4, roughness: 0.3 }));
      m.castShadow = false;
      return [m];
    },

    /* ------------------------------------------------------------ brincadeiras */
    toboga(d, cor) {
      const H = d.altura, R = Math.max(0.6, d.raio), voltas = Math.max(0.5, d.voltas || 1.25);
      const fechado = !!Math.round(d.fechado || 0), lado = Math.round(d.espelhado || 0) ? -1 : 1;
      const rt = 0.38, folga = 0.35;
      const yTopo = H + (fechado ? rt * 0.9 : 0.06), yFim = fechado ? rt + 0.05 : 0.28;
      // a boca: na frente da torre (lado -x), no z da torre; depois a espiral em volta do eixo
      const pontos = [new T.Vector3(-R - folga, yTopo, lado * R), new T.Vector3(-R * 0.45, yTopo - 0.04, lado * R)];
      const passos = Math.max(24, Math.round(voltas * 40));
      const inicio = lado > 0 ? Math.PI / 2 : -Math.PI / 2;
      for (let i = 0; i <= passos; i++) {
        const t = i / passos;
        const ang = inicio - lado * t * voltas * Math.PI * 2;
        const queda = t < 0.04 ? 0.04 * t / 0.04 : 0.04 + (yTopo - 0.04 - yFim) * ((t - 0.04) / 0.96);
        pontos.push(new T.Vector3(R * Math.cos(ang), yTopo - Math.min(yTopo - yFim, queda), R * Math.sin(ang)));
      }
      // a saída: reto, na direção em que a espiral termina
      const fim = pontos[pontos.length - 1], antes = pontos[pontos.length - 2];
      const dir = fim.clone().sub(antes).setY(0).normalize();
      pontos.push(fim.clone().addScaledVector(dir, 0.45), fim.clone().addScaledVector(dir, 0.9));
      const caminho = new T.CatmullRomCurve3(pontos, false, "centripetal");
      const segs = Math.max(80, Math.round(voltas * 90));
      const grupo = [];
      const mat = material(cor, { side: T.DoubleSide, roughness: 0.25 });
      if (fechado) {
        grupo.push(malha(new T.TubeGeometry(caminho, segs, rt, 18, false), mat));
        const aro = malha(new T.TorusGeometry(rt, 0.035, 8, 28), material("#ffffff"));
        aro.position.copy(pontos[0]);
        aro.rotation.y = Math.PI / 2;
        grupo.push(aro);
      } else {
        // a calha: meio tubo aberto para cima
        const fatia = 14, pos = [], idx = [];
        const cima = new T.Vector3(0, 1, 0);
        for (let i = 0; i <= segs; i++) {
          const p = caminho.getPointAt(i / segs), t = caminho.getTangentAt(i / segs);
          const lateral = new T.Vector3().crossVectors(t, cima).normalize();
          const sobe = new T.Vector3().crossVectors(lateral, t).normalize();
          for (let j = 0; j <= fatia; j++) {
            const a = (j / fatia) * Math.PI;
            const v = p.clone().addScaledVector(lateral, Math.cos(a) * rt).addScaledVector(sobe, -Math.sin(a) * rt * 0.8);
            pos.push(v.x, v.y + rt * 0.55, v.z);
          }
        }
        for (let i = 0; i < segs; i++) {
          for (let j = 0; j < fatia; j++) {
            const a = i * (fatia + 1) + j, b = a + fatia + 1;
            idx.push(a, b, a + 1, b, b + 1, a + 1);
          }
        }
        const g = new T.BufferGeometry();
        g.setAttribute("position", new T.Float32BufferAttribute(pos, 3));
        g.setIndex(idx);
        g.computeVertexNormals();
        grupo.push(malha(g, mat));
      }
      grupo.push(tubo(0.08, yTopo + 0.15, [0, 0, 0], [0, yTopo + 0.15, 0], cinza()));
      return grupo;
    },
    tunel_rede(d, cor) {
      const r = d.diametro / 2, C = d.comprimento;
      const g = new T.CylinderGeometry(r, r, C, 28, 1, true);
      g.rotateZ(Math.PI / 2);
      g.translate(0, r, 0);
      const m = redeMat(Math.PI * d.diametro, C, cor);
      m.side = T.DoubleSide;
      const grupo = [malha(g, m)];
      const aro = material("#9ca3af", { metalness: 0.3 });
      const aneis = Math.max(2, Math.round(C / 0.5) + 1);
      for (let i = 0; i < aneis; i++) {
        const anel = malha(new T.TorusGeometry(r, 0.018, 8, 32), aro);
        anel.rotation.y = Math.PI / 2;
        anel.position.set(-C / 2 + (C * i) / (aneis - 1), r, 0);
        grupo.push(anel);
      }
      return grupo;
    },
    rolos(d, cor) {
      const L = d.largura, A = d.altura, n = Math.max(1, Math.round(d.quantidade || 4));
      const raio = Math.min(0.15, L / (n * 2.4));
      const grupo = [];
      for (let i = 0; i < n; i++) {
        const x = -L / 2 + (L * (i + 0.5)) / n;
        const g = new T.CylinderGeometry(raio, raio, A - 0.08, 20);
        g.translate(x, A / 2, 0);
        grupo.push(malha(g, material(variar(cor, i), { roughness: 0.55 })));
      }
      grupo.push(tubo(0.025, L, [-L / 2, A - 0.02, 0], [L / 2, A - 0.02, 0], cinza()));
      return grupo;
    },
    colmeia(d, cor) {
      const R = d.largura / 2, A = d.altura, P = d.profundidade;
      const apotema = R * Math.cos(Math.PI / 6);
      const n = Math.max(1, Math.floor(A / (2 * apotema)));
      const grupo = [];
      for (let i = 0; i < n; i++) {
        const g = new T.CylinderGeometry(R, R, P, 6, 1, true);
        g.rotateX(Math.PI / 2);
        g.rotateZ(Math.PI / 6);
        g.translate((i % 2 ? 0.12 : -0.12) * R, apotema + i * 2 * apotema, 0);
        grupo.push(malha(g, material(variar(cor, i * 2), { side: T.DoubleSide, roughness: 0.4 })));
        const borda = new T.TorusGeometry(R, 0.03, 6, 6);
        borda.rotateZ(Math.PI / 6 + Math.PI / 2);
        borda.translate((i % 2 ? 0.12 : -0.12) * R, apotema + i * 2 * apotema, P / 2);
        grupo.push(malha(borda, material(escurecer(variar(cor, i * 2), 0.25))));
      }
      return grupo;
    },
    pendulos(d, cor) {
      const L = d.largura, A = d.altura, n = Math.max(1, Math.round(d.quantidade || 3));
      const grupo = [tubo(0.025, L, [-L / 2, A, 0], [L / 2, A, 0], cinza())];
      const corda = material("#1f2937");
      for (let i = 0; i < n; i++) {
        const x = -L / 2 + (L * (i + 0.5)) / n;
        const y = Math.max(0.3, A * 0.45);
        grupo.push(tubo(0.008, A - y, [x, y, 0], [x, A, 0], corda));
        const bola = malha(new T.SphereGeometry(0.16, 18, 14), material(variar(cor, i), { roughness: 0.35 }));
        bola.position.set(x, y, 0);
        grupo.push(bola);
      }
      return grupo;
    },
    piscina_redonda(d, cor) {
      const R = d.diametro / 2, A = d.altura, e = 0.14;
      const parede = material(cor, { side: T.DoubleSide, roughness: 0.6 });
      const fora = new T.CylinderGeometry(R, R, A, 48, 1, true);
      fora.translate(0, A / 2, 0);
      const dentro = new T.CylinderGeometry(R - e, R - e, A, 48, 1, true);
      dentro.translate(0, A / 2, 0);
      const topo = new T.RingGeometry(R - e, R, 48);
      topo.rotateX(-Math.PI / 2);
      topo.translate(0, A, 0);
      const grupo = [malha(fora, parede), malha(dentro, parede), malha(topo, parede)];
      const sorte = aleatorio(Math.round(R * 1000 + A * 77));
      const quantas = Math.min(380, Math.round(Math.PI * (R - e) * (R - e) * 70));
      const bolas = [[], [], [], [], []], r = 0.04;
      for (let i = 0; i < quantas; i++) {
        const ang = sorte() * Math.PI * 2, dist = Math.sqrt(sorte()) * (R - e - r);
        const g = new T.SphereGeometry(r, 8, 6);
        g.translate(Math.cos(ang) * dist, r + sorte() * A * 0.55, Math.sin(ang) * dist);
        bolas[i % 5].push(g);
      }
      return grupo.concat(porCor(bolas, VIVAS.slice(0, 5), (c) => material(c, { roughness: 0.3 })));
    },
    espuma(d, cor) {
      const L = d.largura, P = d.profundidade, A = d.altura, e = 0.25;
      const grupo = [];
      const parede = material(cor, { roughness: 0.75 });
      for (const [l, p, x, z] of [[L, e, 0, P / 2 - e / 2], [L, e, 0, -P / 2 + e / 2], [e, P - 2 * e, L / 2 - e / 2, 0], [e, P - 2 * e, -L / 2 + e / 2, 0]]) {
        const b = malha(caixa(l, A, p), parede);
        b.position.set(x, A / 2, z);
        grupo.push(b);
      }
      const sorte = aleatorio(Math.round(L * 311 + P * 53 + A * 7));
      const cores = ["#ffffff", "#2563eb", "#facc15", "#ef4444"];
      const cubos = cores.map(() => []);
      const quantas = Math.min(320, Math.round((L - 2 * e) * (P - 2 * e) * 22));
      for (let i = 0; i < quantas; i++) {
        const g = new T.BoxGeometry(0.2, 0.2, 0.2);
        g.rotateX(sorte() * 3);
        g.rotateY(sorte() * 3);
        g.translate((sorte() - 0.5) * (L - 2 * e - 0.2), 0.1 + sorte() * A * 0.7, (sorte() - 0.5) * (P - 2 * e - 0.2));
        cubos[i % cores.length].push(g);
      }
      return grupo.concat(porCor(cubos, cores, (c) => material(c, { roughness: 0.9 })));
    },
    rampa(d, cor) {
      const C = d.comprimento, A = d.altura;
      return [malha(silhueta([[-C / 2, 0], [C / 2, 0], [C / 2, A]], d.largura), material(cor, { roughness: 0.8 }))];
    },
    degraus_espuma(d, cor) {
      const n = Math.max(1, Math.round(d.degraus)), s = 0.3, grupo = [];
      for (let k = 0; k < n; k++) {
        const a = (d.altura * (k + 1)) / n;
        const g = caixa(s, a, d.largura);
        g.translate(-n * s / 2 + (k + 0.5) * s, a / 2, 0);
        grupo.push(malha(g, material(k % 2 ? variar(cor, 1) : cor, { roughness: 0.8 })));
      }
      return grupo;
    },
    arco(d, cor) {
      const Ri = d.largura / 2, Ro = Ri + 0.25, hp = Math.max(0.3, d.altura - Ro);
      const pontos = [[-Ro, 0], [-Ri, 0], [-Ri, hp]];
      for (let i = 0; i <= 24; i++) { const a = Math.PI - (i / 24) * Math.PI; pontos.push([Math.cos(a) * Ri, hp + Math.sin(a) * Ri]); }
      pontos.push([Ri, 0], [Ro, 0], [Ro, hp]);
      for (let i = 0; i <= 24; i++) { const a = (i / 24) * Math.PI; pontos.push([Math.cos(a) * Ro, hp + Math.sin(a) * Ro]); }
      const portal = malha(silhueta(pontos, 0.25), material(cor, { roughness: 0.6 }));
      const bola = malha(new T.SphereGeometry(0.16, 18, 14), material(variar(cor, 3)));
      bola.position.set(0, hp + Ro + 0.14, 0);
      return [portal, bola];
    },

    /* ------------------------------------------------------------ esporte e ninja */
    quadra(d, cor) {
      const L = d.largura, P = d.profundidade;
      const piso = caixa(L, 0.02, P);
      piso.translate(0, 0.01, 0);
      const linhas = [];
      const linha = (l, p, x, z) => { const g = caixa(l, 0.004, p); g.translate(x, 0.022, z); linhas.push(g); };
      const f = 0.3, w = 0.06;
      linha(L - 2 * f, w, 0, -P / 2 + f); linha(L - 2 * f, w, 0, P / 2 - f);
      linha(w, P - 2 * f, -L / 2 + f, 0); linha(w, P - 2 * f, L / 2 - f, 0);
      linha(w, P - 2 * f, 0, 0);
      const area = Math.min(P * 0.45, 4), fundo = Math.min(L * 0.12, 1.6);
      for (const s of [-1, 1]) {
        linha(w, area, s * (L / 2 - f - fundo), 0);
        linha(fundo, w, s * (L / 2 - f - fundo / 2), -area / 2);
        linha(fundo, w, s * (L / 2 - f - fundo / 2), area / 2);
      }
      const roda = new T.RingGeometry(Math.min(1.2, P * 0.13), Math.min(1.2, P * 0.13) + w, 48);
      roda.rotateX(-Math.PI / 2);
      roda.translate(0, 0.023, 0);
      const branco = material("#ffffff", { roughness: 0.6 });
      return [malha(piso, material(cor, { roughness: 0.75 })), malha(juntar(linhas), branco), malha(roda, branco)];
    },
    gol(d, cor) {
      const L = d.largura, A = d.altura, P = 0.8, grupo = [];
      const mat = material(cor, { metalness: 0.2 });
      const zf = P / 2, zt = -P / 2, at = A * 0.75;
      grupo.push(tubo(0.04, A, [-L / 2, 0, zf], [-L / 2, A, zf], mat), tubo(0.04, A, [L / 2, 0, zf], [L / 2, A, zf], mat),
        tubo(0.04, L, [-L / 2, A, zf], [L / 2, A, zf], mat));
      const fino = material("#9ca3af", { metalness: 0.3 });
      for (const x of [-L / 2, L / 2]) {
        grupo.push(tubo(0.02, at, [x, 0, zt], [x, at, zt], fino), tubo(0.02, Math.hypot(P, A - at), [x, A, zf], [x, at, zt], fino),
          tubo(0.02, P, [x, 0.02, zf], [x, 0.02, zt], fino));
      }
      grupo.push(tubo(0.02, L, [-L / 2, at, zt], [L / 2, at, zt], fino));
      const fundo = new T.PlaneGeometry(L, at);
      fundo.translate(0, at / 2, zt);
      grupo.push(malha(fundo, redeMat(L, at, "#f8fafc")));
      const teto = new T.PlaneGeometry(L, Math.hypot(P, A - at));
      teto.rotateX(-Math.PI / 2 + Math.atan2(A - at, P));
      teto.translate(0, (A + at) / 2, 0);
      grupo.push(malha(teto, redeMat(L, P, "#f8fafc")));
      return grupo;
    },
    tabela(d, cor) {
      const A = d.altura, grupo = [];
      const base = malha(caixa(0.7, 0.18, 0.9), material("#1f2937"));
      base.position.set(0, 0.09, -0.55);
      grupo.push(base, tubo(0.06, A + 0.75, [0, 0, -0.55], [0, A + 0.75, -0.55], material("#4b5563", { metalness: 0.4 })),
        tubo(0.04, 0.33, [0, A + 0.3, -0.55], [0, A + 0.3, -0.22], material("#4b5563", { metalness: 0.4 })));
      const placa = malha(caixa(1.0, 0.7, 0.04), material("#f8fafc", { roughness: 0.3 }));
      placa.position.set(0, A + 0.3, -0.2);
      const quadro = malha(caixa(0.45, 0.32, 0.01), material(cor));
      quadro.position.set(0, A + 0.18, -0.175);
      const aro = malha(new T.TorusGeometry(0.2, 0.014, 8, 32), material("#f97316", { metalness: 0.4 }));
      aro.rotation.x = Math.PI / 2;
      aro.position.set(0, A, 0.03);
      const cesto = new T.CylinderGeometry(0.2, 0.13, 0.36, 18, 1, true);
      cesto.translate(0, A - 0.18, 0.03);
      const m = redeMat(1.2, 0.36, "#f8fafc");
      m.side = T.DoubleSide;
      grupo.push(placa, quadro, aro, malha(cesto, m));
      return grupo;
    },
    escalada(d, cor) {
      const L = d.largura, A = d.altura;
      const parede = malha(caixa(L, A, 0.15), material(cor, { roughness: 0.8 }));
      parede.position.set(0, A / 2, 0);
      const sorte = aleatorio(Math.round(L * 401 + A * 59));
      const agarras = VIVAS.map(() => []);
      const quantas = Math.min(160, Math.round(L * A * 4.5));
      for (let i = 0; i < quantas; i++) {
        const g = new T.DodecahedronGeometry(0.045 + sorte() * 0.04, 0);
        g.scale(1, 0.8, 0.55);
        g.translate((sorte() - 0.5) * (L - 0.2), 0.25 + sorte() * (A - 0.35), 0.09);
        agarras[i % agarras.length].push(g);
      }
      return [parede].concat(porCor(agarras, VIVAS, (c) => material(c, { roughness: 0.6 })));
    },
    colchao(d, cor) {
      const g = caixa(d.largura, d.espessura, d.profundidade);
      g.translate(0, d.espessura / 2, 0);
      const faixa = caixa(d.largura + 0.004, Math.min(0.05, d.espessura * 0.25), d.profundidade + 0.004);
      faixa.translate(0, d.espessura * 0.5, 0);
      return [malha(g, material(cor, { roughness: 0.85 })), malha(faixa, material(escurecer(cor, 0.35), { roughness: 0.85 }))];
    },
    degraus(d, cor) {
      const C = d.comprimento, W = d.largura, n = Math.max(3, Math.round(C / 0.65)), grupo = [];
      for (let i = 0; i < n; i++) {
        const x = -C / 2 + (C * (i + 0.5)) / n, lado = i % 2 ? 1 : -1, y = 0.45 + (i % 3) * 0.05;
        const z = lado * W / 4;
        grupo.push(tubo(0.035, y, [x, 0, z], [x, y, z], cinza()));
        const placa = malha(caixa(0.5, 0.06, 0.5), material(i % 2 ? variar(cor, 1) : cor, { roughness: 0.7 }));
        placa.position.set(x, y + 0.03, z);
        placa.rotation.x = -lado * T.MathUtils.degToRad(25);
        grupo.push(placa);
      }
      return grupo;
    },
    trave(d, cor) {
      const C = d.comprimento, A = d.altura;
      const viga = malha(caixa(C, 0.1, 0.1), material(cor, { roughness: 0.6 }));
      viga.position.set(0, A - 0.05, 0);
      const grupo = [viga];
      for (const x of [-C / 2 + 0.2, C / 2 - 0.2]) {
        grupo.push(tubo(0.03, Math.hypot(0.25, A - 0.1), [x, 0, -0.25], [x, A - 0.1, 0], cinza()), tubo(0.03, Math.hypot(0.25, A - 0.1), [x, 0, 0.25], [x, A - 0.1, 0], cinza()));
      }
      return grupo;
    },
    argolas(d, cor) {
      const C = d.comprimento, A = d.altura, n = Math.max(1, Math.round(d.quantidade || 4));
      const mat = material(cor, { metalness: 0.3 });
      const grupo = [tubo(0.05, C, [-C / 2, A, 0], [C / 2, A, 0], mat)];
      for (const x of [-C / 2, C / 2]) {
        grupo.push(tubo(0.05, Math.hypot(0.35, A), [x, 0, -0.35], [x, A, 0], mat), tubo(0.05, Math.hypot(0.35, A), [x, 0, 0.35], [x, A, 0], mat));
      }
      const corda = material("#c8a26b", { roughness: 0.9 });
      for (let i = 0; i < n; i++) {
        const x = -C / 2 + (C * (i + 0.5)) / n;
        grupo.push(tubo(0.01, 0.55, [x, A - 0.55, 0], [x, A, 0], corda));
        const anel = malha(new T.TorusGeometry(0.1, 0.02, 8, 24), material(variar("#ef4444", i), { roughness: 0.4 }));
        anel.position.set(x, A - 0.65, 0);
        grupo.push(anel);
      }
      return grupo;
    },
    macaco(d, cor) {
      const C = d.comprimento, A = d.altura, W = d.largura;
      const mat = material(cor, { metalness: 0.3 });
      const grupo = [];
      for (const z of [-W / 2, W / 2]) {
        grupo.push(tubo(0.04, C, [-C / 2, A, z], [C / 2, A, z], mat), tubo(0.045, A, [-C / 2, 0, z], [-C / 2, A, z], mat), tubo(0.045, A, [C / 2, 0, z], [C / 2, A, z], mat));
      }
      const degrau = material("#facc15", { metalness: 0.3 });
      const n = Math.max(2, Math.round(C / 0.33));
      for (let i = 0; i <= n; i++) {
        const x = -C / 2 + (C * i) / n;
        grupo.push(tubo(0.02, W, [x, A, -W / 2], [x, A, W / 2], degrau));
      }
      return grupo;
    },
    corda(d, cor) {
      const A = d.altura;
      const mat = material(cor, { metalness: 0.3 });
      const grupo = [tubo(0.05, A, [-0.6, 0, 0], [-0.6, A, 0], mat), tubo(0.05, A, [0.6, 0, 0], [0.6, A, 0], mat), tubo(0.05, 1.3, [-0.65, A, 0], [0.65, A, 0], mat)];
      const sisal = material("#c8a26b", { roughness: 0.95 });
      grupo.push(tubo(0.022, A - 0.3, [0, 0.3, 0], [0, A, 0], sisal));
      for (let y = 0.5; y < A - 0.2; y += 0.4) {
        const no = malha(new T.SphereGeometry(0.045, 10, 8), sisal);
        no.position.set(0, y, 0);
        grupo.push(no);
      }
      return grupo;
    },
    parede_curva(d, cor) {
      const L = d.largura, A = d.altura;
      const c = Math.min(A * 0.7, 2.2), pl = 0.8;
      const zf = (c + pl) / 2;
      // a silhueta de lado (z, y): a curva sobe da frente (+z) até ficar de pé no alto; atrás, a plataforma
      const pontos = [];
      for (let i = 0; i <= 20; i++) {
        const f = (i / 20) * Math.PI / 2;
        pontos.push([-(zf - c * Math.sin(f)), A - A * Math.cos(f)]);
      }
      pontos.push([-(zf - c - pl), A], [-(zf - c - pl), 0]);
      const g = new T.ExtrudeGeometry(new T.Shape(pontos.map(([u, y]) => new T.Vector2(u, y))), { depth: L, bevelEnabled: false });
      g.rotateY(Math.PI / 2);
      g.translate(-L / 2, 0, 0);
      const grupo = [malha(g, material(cor, { roughness: 0.55 }))];
      const zt = -(c + pl) / 2 + 0.05;
      const grade = material("#1f2937", { metalness: 0.3 });
      grupo.push(tubo(0.03, L, [-L / 2, A + 0.9, zt], [L / 2, A + 0.9, zt], grade), tubo(0.03, 0.9, [-L / 2, A, zt], [-L / 2, A + 0.9, zt], grade), tubo(0.03, 0.9, [L / 2, A, zt], [L / 2, A + 0.9, zt], grade));
      return grupo;
    },
  };
}
