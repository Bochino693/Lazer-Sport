/* ======================================================================
   MONTAR EM 3D, COMO NUM CAD (Objetos 3D > Montar; o servidor é
   sistema_interno/views_montar_3d.py).

   A planta em metros, com grade. As peças:
     * DESENHADAS na medida pedida (CATALOGO: coluna, barra, plataforma,
       painel, rede, escorregador, escada, túnel, cama elástica, piscina de
       bolinhas, cerca, telhado) -- o desenho é feito aqui, na hora;
     * GUARDADAS no laboratório (.glb), OBJETOS dos brinquedos e dos
       projetos (.glb), que entram de pé, no chão, na medida deles.

   Colocar: escolher a peça e clicar na planta (ela encaixa na grade e sobe
   em cima da peça que estiver embaixo: a plataforma vai no alto da coluna).
   Escolher: clicar na peça. Mover/girar: as alças na peça ou as setas do
   teclado, PgUp/PgDn sobe e desce, R gira 90°, Del apaga, Ctrl+D duplica,
   Ctrl+Z desfaz. A vista: arrastar o fundo gira, botão direito (ou dois
   dedos) arrasta, a rodinha (ou a pinça) aproxima; "Planta" é de cima.

   Guardar manda as peças (JSON) e o .glb da montagem inteira, exportado
   daqui mesmo (o que se vê é o que vai). "Usar em…" grava o .glb nos
   brinquedos e/ou no projeto; ".glb" baixa o arquivo.
   ====================================================================== */

const PASSO_PADRAO = 0.25;
/** As medidas das peças: as em metros (sem `tipo`), as contadas e as de ligar/desligar. */
const CHAVES = {
  altura: { rotulo: "Altura" }, largura: { rotulo: "Largura" }, profundidade: { rotulo: "Profundidade" },
  comprimento: { rotulo: "Comprimento" }, diametro: { rotulo: "Diâmetro" }, espessura: { rotulo: "Espessura" },
  raio: { rotulo: "Raio" },
  degraus: { rotulo: "Degraus", tipo: "inteiro" }, quantidade: { rotulo: "Quantidade", tipo: "inteiro" },
  voltas: { rotulo: "Voltas", tipo: "voltas" },
  fechado: { rotulo: "Tubo fechado", tipo: "sim" }, espelhado: { rotulo: "Espelhado", tipo: "sim" },
};
const emMetros = (k) => !(CHAVES[k] && CHAVES[k].tipo);
//: as cores da casa (as das paletas dos brinquedões)
const CORES = ["#2563eb", "#facc15", "#ef4444", "#22c55e", "#f97316", "#ec4899", "#8b5cf6", "#06b6d4",
  "#ffffff", "#9ca3af", "#1f2937", "#c8a26b"];
//: as cores raiz do projetista e da cor-tema
const RAIZES = ["#2563eb", "#0ea5e9", "#14b8a6", "#22c55e", "#84cc16", "#facc15", "#f97316", "#ef4444",
  "#ec4899", "#a855f7", "#7c3aed", "#6b4f3a", "#4b5563", "#0f766e", "#be123c", "#1e3a8a"];

// As peças antigas; as novas (montar3d-pecas.js) entram aqui quando o editor abre.
const CATALOGO = {
  coluna: { nome: "Coluna", d: { altura: 3.5, diametro: 0.12 }, cor: "#2563eb" },
  barra: { nome: "Barra", d: { comprimento: 1.5, diametro: 0.1 }, cor: "#facc15" },
  plataforma: { nome: "Plataforma", d: { largura: 1.5, profundidade: 1.5, espessura: 0.06 }, cor: "#f97316" },
  painel: { nome: "Painel", d: { largura: 1.5, altura: 1.0, espessura: 0.03 }, cor: "#ef4444" },
  rede: { nome: "Rede", d: { largura: 1.5, altura: 1.0 }, cor: "#1f2937" },
  escorregador: { nome: "Escorregador", d: { comprimento: 3.0, altura: 1.5, largura: 0.6, fechado: 0 }, cor: "#22c55e" },
  escada: { nome: "Escada", d: { altura: 1.5, largura: 0.6, degraus: 5 }, cor: "#facc15" },
  tunel: { nome: "Túnel", d: { comprimento: 1.5, diametro: 0.7 }, cor: "#ec4899" },
  cama: { nome: "Cama elástica", d: { largura: 3.0, profundidade: 3.0, altura: 0.9 }, cor: "#2563eb" },
  piscina: { nome: "Piscina de bolinhas", d: { largura: 2.0, profundidade: 2.0, altura: 0.5 }, cor: "#06b6d4" },
  cerca: { nome: "Cerca / tela", d: { comprimento: 2.0, altura: 1.0 }, cor: "#f97316" },
  telhado: { nome: "Telhado", d: { largura: 1.5, profundidade: 1.5, altura: 0.8 }, cor: "#ef4444" },
};

function metros(v) { return (Math.round(v * 100) / 100).toFixed(2).replace(".", ","); }
function rotuloDaPeca(tipo, d) {
  const c = CATALOGO[tipo];
  if (!c) return tipo;
  const chaves = Object.keys(c.d).filter((k) => emMetros(k) && k !== "espessura" && k !== "diametro");
  if (!chaves.length) return c.nome;
  return `${c.nome} ${chaves.map((k) => metros(d[k] ?? c.d[k])).join(" × ")} m`;
}
const semAcento = (s) => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

export async function iniciar(raiz) {
  let sujo = true; // desenhar de novo no próximo quadro
  const dados = JSON.parse(document.getElementById("montarDados").textContent || "{}");
  const pasta = raiz.dataset.three.slice(0, raiz.dataset.three.lastIndexOf("/") + 1);
  const [T, leitorMod, controlesMod, utilidades, pecasMod, gerador, cores3d] = await Promise.all([
    import(raiz.dataset.three), import(raiz.dataset.gltf), import(raiz.dataset.controles),
    import(pasta + "BufferGeometryUtils.js"), import(raiz.dataset.pecas), import(raiz.dataset.gerador), import(raiz.dataset.cores),
  ]);
  const celular = window.matchMedia("(max-width: 767.98px)");
  const $ = (id) => document.getElementById(id);
  const csrf = raiz.querySelector("[name=csrfmiddlewaretoken]").value;
  const tela = $("mtTela");
  const aviso = $("mtAviso");

  /* ---------------------------------------------------------------- a cena */
  const renderer = new T.WebGLRenderer({ canvas: tela, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = T.SRGBColorSpace;
  renderer.toneMapping = T.ACESFilmicToneMapping;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = T.PCFSoftShadowMap;
  const cena = new T.Scene();
  cena.background = new T.Color("#0b1322");
  cena.add(new T.HemisphereLight("#ffffff", "#5a6a85", 1.5));
  const sol = new T.DirectionalLight("#ffffff", 2.2);
  sol.position.set(8, 14, 10);
  sol.castShadow = true;
  sol.shadow.mapSize.set(2048, 2048);
  sol.shadow.bias = -0.0004;
  cena.add(sol, sol.target);

  const chao = new T.Mesh(new T.PlaneGeometry(200, 200), new T.ShadowMaterial({ opacity: 0.3 }));
  chao.rotation.x = -Math.PI / 2;
  chao.receiveShadow = true;
  cena.add(chao);
  const grade = new T.Group();
  const gradeFina = new T.GridHelper(40, 160, "#24324a", "#16213a");
  gradeFina.position.y = 0.001;
  const gradeMetro = new T.GridHelper(40, 40, "#3fd0ff", "#34507a");
  gradeMetro.position.y = 0.002;
  gradeMetro.material.opacity = 0.55;
  gradeMetro.material.transparent = true;
  grade.add(gradeFina, gradeMetro);
  cena.add(grade);

  const montagem = new T.Group();
  montagem.name = "montagem";
  cena.add(montagem);

  // as câmeras: a 3D (perspectiva, em volta) e a da planta (de cima, sem perspectiva)
  const camera3d = new T.PerspectiveCamera(40, 1, 0.05, 500);
  const cameraPlanta = new T.OrthographicCamera(-10, 10, 10, -10, 0.1, 500);
  let camera = camera3d;
  const vista = { alvo: new T.Vector3(0, 0.8, 0), giro: 0.75, inclinacao: 0.55, distancia: 14, zoomPlanta: 12 };
  let modoVista = "3d";

  const controles = new controlesMod.TransformControls(camera, tela);
  controles.setTranslationSnap(PASSO_PADRAO);
  controles.setRotationSnap(T.MathUtils.degToRad(15));
  controles.setSize(0.9);
  const ajudante = controles.getHelper ? controles.getHelper() : controles;
  cena.add(ajudante);
  let arrastandoAlca = false;
  controles.addEventListener("dragging-changed", (e) => {
    arrastandoAlca = e.value;
    if (!e.value) { prenderNoChao(selecionada); registrar(); mostrarPropriedades(); }
  });
  controles.addEventListener("objectChange", () => { if (selecionada) lerTransformacao(selecionada); sujo = true; });
  controles.addEventListener("change", () => { sujo = true; });

  const caixaSelecao = new T.BoxHelper(undefined, "#ffd23f");
  caixaSelecao.visible = false;
  cena.add(caixaSelecao);

  /* ---------------------------------------------------------------- materiais e desenhos */
  const materiais = new Map();
  function material(cor, extra) {
    const chave = cor + JSON.stringify(extra || {});
    if (!materiais.has(chave)) {
      materiais.set(chave, new T.MeshStandardMaterial(Object.assign({ color: cor, roughness: 0.5, metalness: 0.06 }, extra || {})));
    }
    return materiais.get(chave);
  }
  let texturaRede = null;
  function rede(largura, altura, cor) {
    if (!texturaRede) {
      const c = document.createElement("canvas");
      c.width = c.height = 64;
      const g = c.getContext("2d");
      g.strokeStyle = "#ffffff";
      g.lineWidth = 6;
      g.strokeRect(0, 0, 64, 64);
      texturaRede = new T.CanvasTexture(c);
      texturaRede.wrapS = texturaRede.wrapT = T.RepeatWrapping;
      texturaRede.colorSpace = T.SRGBColorSpace;
    }
    const tex = texturaRede.clone();
    tex.needsUpdate = true;
    tex.repeat.set(Math.max(1, largura / 0.1), Math.max(1, altura / 0.1));
    const m = new T.MeshStandardMaterial({ color: cor, map: tex, alphaTest: 0.5, transparent: false, side: T.DoubleSide, roughness: 0.8 });
    m.alphaMap = tex;
    return m;
  }
  const caixa = (l, a, p) => new T.BoxGeometry(Math.max(l, 0.005), Math.max(a, 0.005), Math.max(p, 0.005));
  const malha = (geo, mat) => { const m = new T.Mesh(geo, mat); m.castShadow = true; m.receiveShadow = true; return m; };
  function tubo(r, comprimento, de, para, mat) {
    const g = new T.CylinderGeometry(r, r, comprimento, 14);
    const m = malha(g, mat);
    const a = new T.Vector3(...de), b = new T.Vector3(...para);
    m.position.copy(a).add(b).multiplyScalar(0.5);
    m.quaternion.setFromUnitVectors(new T.Vector3(0, 1, 0), b.clone().sub(a).normalize());
    return m;
  }
  function aleatorio(semente) { let s = semente >>> 0 || 1; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296); }

  /* Cada desenho: um grupo com a base no chão (y = 0) e o meio em x = z = 0. */
  const DESENHOS = {
    coluna(d, cor) {
      const g = new T.CylinderGeometry(d.diametro / 2, d.diametro / 2, d.altura, 24);
      g.translate(0, d.altura / 2, 0);
      return [malha(g, material(cor, { metalness: 0.2, roughness: 0.4 }))];
    },
    barra(d, cor) {
      const r = d.diametro / 2;
      const g = new T.CylinderGeometry(r, r, d.comprimento, 20);
      g.rotateZ(Math.PI / 2);
      g.translate(0, r, 0);
      return [malha(g, material(cor, { metalness: 0.2, roughness: 0.4 }))];
    },
    plataforma(d, cor, extra) {
      if (extra && extra.cor2) {
        // o piso de duas cores, cortado na diagonal (o mais comum nos brinquedões)
        const L = d.largura / 2, P = d.profundidade / 2;
        const tri = (pts) => {
          const forma = new T.Shape(pts.map(([x, z]) => new T.Vector2(x, -z)));
          const g = new T.ExtrudeGeometry(forma, { depth: d.espessura, bevelEnabled: false });
          g.rotateX(-Math.PI / 2);
          return g;
        };
        return [malha(tri([[-L, -P], [L, -P], [-L, P]]), material(cor)), malha(tri([[L, -P], [L, P], [-L, P]]), material(extra.cor2))];
      }
      const g = caixa(d.largura, d.espessura, d.profundidade);
      g.translate(0, d.espessura / 2, 0);
      return [malha(g, material(cor))];
    },
    painel(d, cor) {
      const g = caixa(d.largura, d.altura, d.espessura);
      g.translate(0, d.altura / 2, 0);
      return [malha(g, material(cor))];
    },
    rede(d, cor, extra) {
      const plano = new T.PlaneGeometry(d.largura, d.altura);
      plano.translate(0, d.altura / 2, 0);
      const m = malha(plano, rede(d.largura, d.altura, cor));
      // a moldura: a segunda cor (a da estrutura, no projetista) ou o cinza do tubo
      const moldura = material((extra && extra.cor2) || "#9ca3af", { metalness: 0.3 });
      const w = d.largura / 2, h = d.altura;
      return [m, tubo(0.02, d.largura, [-w, 0, 0], [w, 0, 0], moldura), tubo(0.02, d.largura, [-w, h, 0], [w, h, 0], moldura),
        tubo(0.02, h, [-w, 0, 0], [-w, h, 0], moldura), tubo(0.02, h, [w, 0, 0], [w, h, 0], moldura)];
    },
    escorregador(d, cor) {
      const L = d.comprimento, H = d.altura, W = d.largura;
      const rampa = Math.hypot(L, H), angulo = -Math.atan2(H, L);
      const grupo = [];
      if (Math.round(d.fechado || 0)) {
        // o tobogã de tubo fechado, reto
        const r = Math.max(0.3, W * 0.6);
        const g = new T.CylinderGeometry(r, r, rampa, 24, 1, true);
        g.rotateZ(Math.PI / 2);
        const tuboFechado = malha(g, material(cor, { side: T.DoubleSide, roughness: 0.25 }));
        tuboFechado.position.set(0, H / 2 + r * 0.9, 0);
        tuboFechado.rotation.z = angulo;
        const aro = malha(new T.TorusGeometry(r, 0.035, 8, 28), material("#ffffff"));
        aro.rotation.y = Math.PI / 2;
        aro.position.set(-L / 2, H + r * 0.9, 0);
        return [tuboFechado, aro];
      }
      const base = malha(caixa(rampa, 0.04, W), material(cor, { roughness: 0.25 }));
      base.position.set(0, H / 2 + 0.03, 0);
      base.rotation.z = angulo;
      grupo.push(base);
      for (const lado of [-1, 1]) {
        const parede = malha(caixa(rampa, 0.26, 0.04), material(cor, { roughness: 0.3 }));
        parede.position.set(0, H / 2 + 0.16, lado * (W / 2 - 0.02));
        parede.rotation.z = angulo;
        grupo.push(parede);
      }
      return grupo;
    },
    escada(d, cor) {
      const H = d.altura, W = d.largura, n = Math.max(1, Math.round(d.degraus));
      const P = H * 0.75, grupo = [];
      const lateral = material(cor, { metalness: 0.2 });
      for (const lado of [-1, 1]) grupo.push(tubo(0.03, Math.hypot(P, H), [P / 2, 0, lado * W / 2], [-P / 2, H, lado * W / 2], lateral));
      for (let i = 0; i < n; i++) {
        const t = (i + 1) / n;
        const degrau = malha(caixa(Math.max(0.12, P / n), 0.04, W), material("#1f2937"));
        degrau.position.set(P / 2 - t * P, t * H - 0.02, 0);
        grupo.push(degrau);
      }
      return grupo;
    },
    tunel(d, cor) {
      const r = d.diametro / 2;
      const g = new T.CylinderGeometry(r, r, d.comprimento, 32, 1, true);
      g.rotateZ(Math.PI / 2);
      g.translate(0, r, 0);
      const m = malha(g, material(cor, { side: T.DoubleSide, roughness: 0.35 }));
      const aro = material("#ffffff");
      const grupo = [m];
      for (const lado of [-1, 1]) {
        const anel = malha(new T.TorusGeometry(r, 0.03, 8, 32), aro);
        anel.rotation.y = Math.PI / 2;
        anel.position.set(lado * d.comprimento / 2, r, 0);
        grupo.push(anel);
      }
      return grupo;
    },
    cama(d, cor) {
      const L = d.largura, P = d.profundidade, A = d.altura, borda = Math.min(0.35, Math.min(L, P) * 0.15);
      const grupo = [];
      const moldura = material(cor);
      for (const [l, p, x, z] of [[L, borda, 0, P / 2 - borda / 2], [L, borda, 0, -P / 2 + borda / 2], [borda, P - 2 * borda, L / 2 - borda / 2, 0], [borda, P - 2 * borda, -L / 2 + borda / 2, 0]]) {
        const b = malha(caixa(l, 0.12, p), moldura);
        b.position.set(x, A - 0.06, z);
        grupo.push(b);
      }
      const lona = malha(caixa(L - 2 * borda, 0.02, P - 2 * borda), material("#111827", { roughness: 0.9 }));
      lona.position.set(0, A - 0.08, 0);
      grupo.push(lona);
      const perna = material("#9ca3af", { metalness: 0.4 });
      for (const [x, z] of [[1, 1], [1, -1], [-1, 1], [-1, -1]]) grupo.push(tubo(0.04, A - 0.12, [x * (L / 2 - 0.1), 0, z * (P / 2 - 0.1)], [x * (L / 2 - 0.1), A - 0.12, z * (P / 2 - 0.1)], perna));
      return grupo;
    },
    piscina(d, cor) {
      const L = d.largura, P = d.profundidade, A = d.altura, e = 0.1;
      const grupo = [];
      const parede = material(cor);
      for (const [l, p, x, z] of [[L, e, 0, P / 2 - e / 2], [L, e, 0, -P / 2 + e / 2], [e, P - 2 * e, L / 2 - e / 2, 0], [e, P - 2 * e, -L / 2 + e / 2, 0]]) {
        const b = malha(caixa(l, A, p), parede);
        b.position.set(x, A / 2, z);
        grupo.push(b);
      }
      // as bolinhas: até 360, em 5 cores, numa malha por cor (leve de desenhar e de exportar)
      const sorte = aleatorio(Math.round(L * 1000 + P * 37 + A * 11));
      const quantas = Math.min(360, Math.round((L - 2 * e) * (P - 2 * e) * 70));
      const porCor = [[], [], [], [], []];
      const r = 0.04;
      for (let i = 0; i < quantas; i++) {
        const g = new T.SphereGeometry(r, 8, 6);
        g.translate((sorte() - 0.5) * (L - 2 * e - 2 * r), r + sorte() * A * 0.55, (sorte() - 0.5) * (P - 2 * e - 2 * r));
        porCor[i % 5].push(g);
      }
      ["#ef4444", "#facc15", "#2563eb", "#22c55e", "#ec4899"].forEach((c, i) => {
        if (porCor[i].length) grupo.push(malha(utilidades.mergeGeometries(porCor[i]), material(c, { roughness: 0.3 })));
      });
      return grupo;
    },
    cerca(d, cor) {
      const L = d.comprimento, A = d.altura, grupo = [];
      const postes = Math.max(2, Math.round(L / 1) + 1);
      const metal = material(cor, { metalness: 0.25 });
      for (let i = 0; i < postes; i++) {
        const x = -L / 2 + (L * i) / (postes - 1);
        grupo.push(tubo(0.025, A, [x, 0, 0], [x, A, 0], metal));
      }
      grupo.push(tubo(0.02, L, [-L / 2, A, 0], [L / 2, A, 0], metal), tubo(0.02, L, [-L / 2, 0.08, 0], [L / 2, 0.08, 0], metal));
      const tela = new T.PlaneGeometry(L, A - 0.08);
      tela.translate(0, 0.08 + (A - 0.08) / 2, 0);
      grupo.push(malha(tela, rede(L, A, "#1f2937")));
      return grupo;
    },
    telhado(d, cor) {
      const g = new T.ConeGeometry(Math.SQRT1_2, 1, 4, 1);
      g.rotateY(Math.PI / 4);
      g.scale(d.largura, d.altura, d.profundidade);
      g.translate(0, d.altura / 2, 0);
      return [malha(g, material(cor, { flatShading: true }))];
    },
  };
  // as peças novas (estrutura, brincadeiras, esporte e ninja)
  Object.assign(CATALOGO, pecasMod.CATALOGO_EXTRA);
  Object.entries(pecasMod.GRUPO_DAS_ANTIGAS).forEach(([tipo, grupo]) => { CATALOGO[tipo].grupo = grupo; });
  Object.assign(DESENHOS, pecasMod.desenhosExtra(T, {
    material, malha, caixa, tubo, redeMat: rede, aleatorio, juntar: (lista) => utilidades.mergeGeometries(lista),
  }));
  const COM_COR2 = pecasMod.COM_COR2;
  /** Solta da memória a geometria de uma peça desenhada (as dos .glb são do arquivo: ficam). */
  function descartar(objeto) {
    objeto.traverse((o) => { if (o.isMesh && o.geometry) o.geometry.dispose(); });
  }

  /* ---------------------------------------------------------------- as cores dos .glb (cor-tema) */
  const originaisGlb = new WeakMap();
  const guardaTemas = { userData: {} };
  const temasPorCor = new Map();
  function temaDaCor(hex) {
    if (!temasPorCor.has(hex)) temasPorCor.set(hex, cores3d.temaDeCores("raiz-" + hex, hex, gerador.familiasDaCor(hex)));
    return temasPorCor.get(hex);
  }
  function vestir(peca) {
    if (CATALOGO[peca.tipo]) return;
    cores3d.vestirObjeto(peca.obj, peca.tema ? temaDaCor(peca.tema) : null, originaisGlb, guardaTemas);
    sujo = true;
  }

  /* ---------------------------------------------------------------- os .glb (guardadas e objetos) */
  const biblioteca = dados.biblioteca || { modulos: [], objetos: [], projetos: [], mais_usadas: [] };
  const fontes = { modulo: biblioteca.modulos, objeto: biblioteca.objetos, projeto: biblioteca.projetos };
  const leitor = new leitorMod.GLTFLoader();
  const carregados = new Map();
  function carregarGlb(url) {
    if (!carregados.has(url)) carregados.set(url, leitor.loadAsync(url));
    return carregados.get(url);
  }
  function fonteDe(tipo, ref) { return (fontes[tipo] || []).find((x) => Number(x.id) === Number(ref)); }
  async function desenhoDeArquivo(peca) {
    const fonte = fonteDe(peca.tipo, peca.ref);
    if (!fonte) throw new Error("a peça não existe mais na biblioteca");
    const gltf = await carregarGlb(fonte.url);
    const copia = gltf.scene.clone(true);
    copia.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
    // de pé, no chão e no meio (como os visores do site)
    const caixaGlb = new T.Box3().setFromObject(copia);
    copia.position.x -= (caixaGlb.min.x + caixaGlb.max.x) / 2;
    copia.position.z -= (caixaGlb.min.z + caixaGlb.max.z) / 2;
    copia.position.y -= caixaGlb.min.y;
    return [copia];
  }

  /* ---------------------------------------------------------------- as peças */
  let pecas = [];
  // a peça de cada grupo 3D (fora do userData: o three.js copia o userData ao clonar e exportar)
  const pecaDoObjeto = new WeakMap();
  let selecionada = null;
  let proximoId = 1;
  const nomeDe = (p) => (CATALOGO[p.tipo] ? rotuloDaPeca(p.tipo, p.d) : (fonteDe(p.tipo, p.ref) || {}).nome || "Peça");

  async function montarPeca(dadosPeca) {
    const peca = {
      id: proximoId++, tipo: dadosPeca.tipo, ref: dadosPeca.ref ?? null,
      d: Object.assign({}, (CATALOGO[dadosPeca.tipo] || {}).d || {}, dadosPeca.d || {}),
      cor: dadosPeca.cor || (CATALOGO[dadosPeca.tipo] || {}).cor || "#2563eb",
      cor2: COM_COR2.has(dadosPeca.tipo) ? (dadosPeca.cor2 || null) : null,
      tema: CATALOGO[dadosPeca.tipo] ? null : (dadosPeca.tema || null),
      s: dadosPeca.s || 1,
      obj: new T.Group(),
    };
    pecaDoObjeto.set(peca.obj, peca);
    peca.obj.position.fromArray(dadosPeca.p || [0, 0, 0]);
    peca.obj.rotation.y = T.MathUtils.degToRad(dadosPeca.r || 0);
    await redesenhar(peca);
    montagem.add(peca.obj);
    pecas.push(peca);
    return peca;
  }
  async function redesenhar(peca) {
    if (CATALOGO[peca.tipo]) descartar(peca.obj);
    peca.obj.clear();
    const partes = CATALOGO[peca.tipo] ? DESENHOS[peca.tipo](peca.d, peca.cor, { cor2: peca.cor2 }) : await desenhoDeArquivo(peca);
    partes.forEach((p) => peca.obj.add(p));
    if (!CATALOGO[peca.tipo]) {
      peca.obj.scale.setScalar(peca.s || 1);
      if (peca.tema) vestir(peca);
    }
    sujo = true;
  }
  function paraJson(peca) {
    const j = { tipo: peca.tipo, p: peca.obj.position.toArray().map((v) => Math.round(v * 10000) / 10000),
      r: Math.round(T.MathUtils.radToDeg(peca.obj.rotation.y) * 1000) / 1000 };
    if (CATALOGO[peca.tipo]) {
      j.d = Object.assign({}, peca.d);
      j.cor = peca.cor;
      if (peca.cor2) j.cor2 = peca.cor2;
    } else {
      j.ref = peca.ref;
      if (peca.s !== 1) j.s = peca.s;
      if (peca.tema) j.tema = peca.tema;
    }
    return j;
  }
  function lerTransformacao(peca) {
    // o giro só em volta do eixo de pé (as peças não tombam)
    const y = peca.obj.rotation.y;
    peca.obj.rotation.set(0, y, 0);
  }
  function prenderNoChao(peca) {
    if (!peca) return;
    const b = new T.Box3().setFromObject(peca.obj);
    if (b.min.y < -0.001) peca.obj.position.y -= b.min.y;
    caixaSelecao.update();
  }

  /* ---------------------------------------------------------------- o histórico (desfazer/refazer) */
  const passado = [];
  const futuro = [];
  let estadoAtual = "[]";
  function registrar() {
    const novo = JSON.stringify(pecas.map(paraJson));
    if (novo === estadoAtual) return;
    passado.push(estadoAtual);
    if (passado.length > 80) passado.shift();
    futuro.length = 0;
    estadoAtual = novo;
    atualizarHistorico();
    atualizarResumo();
  }
  function atualizarHistorico() {
    $("mtDesfazer").disabled = !passado.length;
    $("mtRefazer").disabled = !futuro.length;
  }
  async function restaurar(json) {
    selecionar(null);
    pecas.forEach((p) => { if (CATALOGO[p.tipo]) descartar(p.obj); });
    montagem.clear();
    pecas = [];
    for (const p of JSON.parse(json)) {
      try { await montarPeca(p); } catch (erro) { console.warn("Montar 3D: peça sem arquivo", p, erro); }
    }
    estadoAtual = json;
    atualizarHistorico();
    atualizarResumo();
    sujo = true;
  }
  $("mtDesfazer").addEventListener("click", () => { if (passado.length) { futuro.push(estadoAtual); restaurar(passado.pop()); } });
  $("mtRefazer").addEventListener("click", () => { if (futuro.length) { passado.push(estadoAtual); restaurar(futuro.pop()); } });

  /* ---------------------------------------------------------------- escolher, apagar, duplicar */
  function selecionar(peca) {
    selecionada = peca;
    if (peca) {
      controles.attach(peca.obj);
      caixaSelecao.setFromObject(peca.obj);
      caixaSelecao.visible = true;
    } else {
      controles.detach();
      caixaSelecao.visible = false;
    }
    raiz.classList.toggle("tem-peca", !!peca);
    // no celular, a gaveta abre na peça escolhida (e fecha quando solta)
    if (celular.matches) {
      if (peca) abrirGaveta("propriedades");
      else if (raiz.dataset.gaveta === "propriedades") abrirGaveta("");
    }
    mostrarPropriedades();
    sujo = true;
  }
  function apagar(peca) {
    if (!peca) return;
    if (CATALOGO[peca.tipo]) descartar(peca.obj);
    montagem.remove(peca.obj);
    pecas = pecas.filter((p) => p !== peca);
    selecionar(null);
    registrar();
  }
  async function duplicar(peca) {
    if (!peca) return;
    const j = paraJson(peca);
    const passo = passoAtual() || 0.25;
    const largura = new T.Box3().setFromObject(peca.obj).getSize(new T.Vector3()).x;
    j.p[0] += Math.max(passo, Math.ceil(largura / (passo || 0.25)) * (passo || 0.25));
    const nova = await montarPeca(j);
    selecionar(nova);
    registrar();
  }

  /* ---------------------------------------------------------------- o painel da peça */
  const campos = $("mtCamposMedida");
  const cores = $("mtCores");
  /** Uma fileira de bolinhas de cor; `nenhuma` põe a primeira "sem cor". */
  function amostras(destino, lista, aoEscolher, nenhuma) {
    destino.innerHTML = "";
    const todas = nenhuma ? [""].concat(lista) : lista;
    todas.forEach((cor) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "mt-cor" + (cor ? "" : " mt-cor--nenhuma");
      if (cor) b.style.setProperty("--c", cor);
      b.dataset.cor = cor;
      b.title = cor || nenhuma;
      b.setAttribute("aria-label", cor ? "Cor " + cor : nenhuma);
      b.addEventListener("click", () => aoEscolher(cor));
      destino.appendChild(b);
    });
  }
  const marcarAmostra = (destino, cor) => destino.querySelectorAll(".mt-cor").forEach((b) => b.setAttribute("aria-pressed", b.dataset.cor === (cor || "") ? "true" : "false"));
  /** A cor da peça escolhida: a das peças desenhadas, ou o tema (as cores do desenho) do .glb. */
  async function pintarEscolhida(cor) {
    const p = selecionada;
    if (!p) return;
    if (CATALOGO[p.tipo]) { if (!cor) return; p.cor = cor; await redesenhar(p); } else { p.tema = cor || null; vestir(p); }
    registrar();
    mostrarPropriedades();
  }
  amostras(cores, CORES, pintarEscolhida);
  $("mtCorLivre").addEventListener("change", function () { pintarEscolhida(this.value); });
  $("mtCorOriginal").addEventListener("click", () => pintarEscolhida(null));
  amostras($("mtCores2"), CORES, async (cor) => {
    if (!selecionada || !COM_COR2.has(selecionada.tipo)) return;
    selecionada.cor2 = cor || null;
    await redesenhar(selecionada);
    registrar();
    mostrarPropriedades();
  }, "Uma cor só");
  function campoDeMedida(p, chave) {
    const meta = CHAVES[chave] || { rotulo: chave };
    const rotulo = document.createElement("label");
    const nome = document.createElement("span");
    const campo = document.createElement("input");
    const mudar = async (v) => {
      p.d[chave] = v;
      await redesenhar(p);
      caixaSelecao.setFromObject(p.obj);
      registrar();
      mostrarPropriedades();
    };
    if (meta.tipo === "sim") {
      rotulo.className = "mt-sim";
      campo.type = "checkbox";
      campo.checked = !!Math.round(p.d[chave] || 0);
      campo.addEventListener("change", () => mudar(campo.checked ? 1 : 0));
      nome.textContent = meta.rotulo;
      rotulo.append(campo, nome);
      return rotulo;
    }
    const inteiro = meta.tipo === "inteiro";
    nome.textContent = meta.rotulo + (meta.tipo ? "" : " (m)");
    campo.type = "number";
    campo.step = inteiro ? "1" : meta.tipo === "voltas" ? "0.25" : "0.05";
    campo.min = inteiro ? "1" : meta.tipo === "voltas" ? "0.25" : "0.01";
    campo.value = inteiro ? Math.round(p.d[chave]) : (Math.round(p.d[chave] * 1000) / 1000);
    campo.addEventListener("change", () => {
      const v = parseFloat(String(campo.value).replace(",", "."));
      if (v > 0) mudar(inteiro ? Math.round(v) : v);
    });
    rotulo.append(nome, campo);
    return rotulo;
  }
  function mostrarPropriedades() {
    const p = selecionada;
    $("mtNada").hidden = !!p;
    $("mtPeca").hidden = !p;
    if (!p) return;
    const desenhada = !!CATALOGO[p.tipo];
    $("mtPecaNome").textContent = nomeDe(p);
    const tamanho = new T.Box3().setFromObject(p.obj).getSize(new T.Vector3());
    $("mtPecaMedidas").textContent = `${metros(tamanho.x)} × ${metros(tamanho.z)} m, ${metros(tamanho.y)} m de altura`;
    campos.innerHTML = "";
    if (desenhada) Object.keys(CATALOGO[p.tipo].d).forEach((chave) => campos.appendChild(campoDeMedida(p, chave)));
    raiz.querySelectorAll("[data-pos]").forEach((campo) => { campo.value = Math.round(p.obj.position.getComponent(Number(campo.dataset.pos)) * 1000) / 1000; });
    $("mtGiro").value = Math.round(T.MathUtils.radToDeg(p.obj.rotation.y));
    $("mtEscalaCaixa").hidden = desenhada;
    $("mtEscala").value = p.s || 1;
    $("mtCorTitulo").textContent = desenhada ? "Cor" : "Cores do objeto";
    $("mtCorOriginal").hidden = desenhada;
    marcarAmostra(cores, desenhada ? p.cor : p.tema);
    $("mtCorLivre").value = (desenhada ? p.cor : p.tema) || "#2563eb";
    $("mtCor2Caixa").hidden = !COM_COR2.has(p.tipo);
    marcarAmostra($("mtCores2"), p.cor2);
  }
  $("mtSoltar").addEventListener("click", () => selecionar(null));
  raiz.querySelectorAll("[data-pos]").forEach((campo) => {
    campo.addEventListener("change", () => {
      if (!selecionada) return;
      const v = parseFloat(String(campo.value).replace(",", "."));
      if (Number.isNaN(v)) return;
      selecionada.obj.position.setComponent(Number(campo.dataset.pos), v);
      prenderNoChao(selecionada);
      caixaSelecao.setFromObject(selecionada.obj);
      registrar();
      sujo = true;
    });
  });
  $("mtGiro").addEventListener("change", () => {
    if (!selecionada) return;
    selecionada.obj.rotation.y = T.MathUtils.degToRad(parseFloat($("mtGiro").value) || 0);
    caixaSelecao.setFromObject(selecionada.obj);
    registrar();
    sujo = true;
  });
  raiz.querySelectorAll("[data-girar]").forEach((b) => b.addEventListener("click", () => girar(Number(b.dataset.girar))));
  function girar(graus) {
    if (!selecionada) return;
    selecionada.obj.rotation.y += T.MathUtils.degToRad(graus);
    caixaSelecao.setFromObject(selecionada.obj);
    registrar();
    mostrarPropriedades();
    sujo = true;
  }
  $("mtEscala").addEventListener("change", async () => {
    if (!selecionada || CATALOGO[selecionada.tipo]) return;
    selecionada.s = Math.max(0.05, parseFloat($("mtEscala").value) || 1);
    selecionada.obj.scale.setScalar(selecionada.s);
    caixaSelecao.setFromObject(selecionada.obj);
    registrar();
    mostrarPropriedades();
  });
  $("mtChao").addEventListener("click", () => {
    if (!selecionada) return;
    selecionada.obj.position.y = 0;
    caixaSelecao.setFromObject(selecionada.obj);
    registrar();
    mostrarPropriedades();
  });
  $("mtDuplicar").addEventListener("click", () => duplicar(selecionada));
  $("mtApagarPeca").addEventListener("click", () => apagar(selecionada));

  /* ---------------------------------------------------------------- a biblioteca */
  // miniaturas: cada peça desenhada uma vez, numa tela pequena, e guardada como imagem
  const miniRenderer = new T.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
  miniRenderer.setSize(120, 96);
  miniRenderer.outputColorSpace = T.SRGBColorSpace;
  miniRenderer.toneMapping = T.ACESFilmicToneMapping;
  const miniCena = new T.Scene();
  miniCena.add(new T.HemisphereLight("#ffffff", "#5a6a85", 1.8));
  const miniSol = new T.DirectionalLight("#ffffff", 2.2);
  miniSol.position.set(3, 6, 5);
  miniCena.add(miniSol);
  const miniCamera = new T.PerspectiveCamera(30, 120 / 96, 0.01, 200);
  function fotografar(objetos) {
    const g = new T.Group();
    objetos.forEach((o) => g.add(o));
    miniCena.add(g);
    const b = new T.Box3().setFromObject(g);
    const centro = b.getCenter(new T.Vector3());
    const raio = Math.max(b.getSize(new T.Vector3()).length() / 2, 0.05);
    const d = raio / Math.sin(T.MathUtils.degToRad(15)) * 0.95;
    miniCamera.position.set(centro.x + d * 0.6, centro.y + d * 0.45, centro.z + d * 0.66);
    miniCamera.lookAt(centro);
    miniRenderer.render(miniCena, miniCamera);
    const url = miniRenderer.domElement.toDataURL("image/png");
    miniCena.remove(g);
    return url;
  }
  function cartao(destino, { foto, nome, sub, aoEscolher, extra }) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "mt-item";
    const img = document.createElement("span");
    img.className = "mt-item-foto";
    if (foto) { const i = document.createElement("img"); i.src = foto; i.alt = ""; img.appendChild(i); } else { img.innerHTML = '<i class="bi bi-box"></i>'; }
    const t = document.createElement("span");
    t.className = "mt-item-texto";
    const n = document.createElement("strong");
    n.textContent = nome;
    t.appendChild(n);
    if (sub) { const s = document.createElement("small"); s.textContent = sub; t.appendChild(s); }
    if (extra) t.appendChild(extra);
    b.append(img, t);
    b.addEventListener("click", aoEscolher);
    destino.appendChild(b);
    return b;
  }
  // as miniaturas saem aos poucos (sem segurar a abertura do editor)
  const filaFotos = [];
  function fotoDepois(botao, desenhar) {
    filaFotos.push(() => {
      const partes = desenhar();
      const foto = fotografar(partes);
      partes.forEach(descartar);
      botao.querySelector(".mt-item-foto").innerHTML = `<img src="${foto}" alt="">`;
    });
  }
  function revelarFotos() {
    const ate = performance.now() + 12;
    while (filaFotos.length && performance.now() < ate) filaFotos.shift()();
    if (filaFotos.length) requestAnimationFrame(revelarFotos);
  }
  const subDoCatalogo = (c) => {
    const chaves = Object.keys(c.d).filter(emMetros);
    return chaves.length ? chaves.map((k) => metros(c.d[k])).join(" × ") + " m" : "";
  };
  const listaDesenhar = $("mtDesenhar");
  Object.entries(pecasMod.GRUPOS).forEach(([grupo, titulo]) => {
    const tipos = Object.keys(CATALOGO).filter((t) => CATALOGO[t].grupo === grupo);
    if (!tipos.length) return;
    const h = document.createElement("h6");
    h.className = "mt-grupo-titulo";
    h.dataset.grupo = grupo;
    h.innerHTML = `<i class="bi ${grupo === "estrutura" ? "bi-bricks" : grupo === "brincar" ? "bi-balloon-fill" : "bi-trophy-fill"}"></i> <span></span> <small>${tipos.length}</small>`;
    h.querySelector("span").textContent = titulo;
    const grade = document.createElement("div");
    grade.className = "mt-grade";
    grade.dataset.grupo = grupo;
    listaDesenhar.append(h, grade);
    tipos.forEach((tipo) => {
      const c = CATALOGO[tipo];
      const botao = cartao(grade, {
        foto: "", nome: c.nome, sub: subDoCatalogo(c),
        aoEscolher: () => comecarColocar({ tipo, d: Object.assign({}, c.d), cor: c.cor, cor2: c.cor2 }),
      });
      botao.dataset.busca = semAcento(c.nome + " " + tipo.replace(/_/g, " "));
      fotoDepois(botao, () => DESENHOS[tipo](c.d, c.cor, { cor2: c.cor2 }));
    });
  });
  $("mtBuscaPeca").addEventListener("input", function () {
    const termo = semAcento(this.value.trim());
    listaDesenhar.querySelectorAll(".mt-grade").forEach((grade) => {
      let algum = false;
      grade.querySelectorAll(".mt-item").forEach((b) => { b.hidden = !!termo && b.dataset.busca.indexOf(termo) < 0; algum = algum || !b.hidden; });
      grade.hidden = !algum;
      listaDesenhar.querySelector(`h6[data-grupo="${grade.dataset.grupo}"]`).hidden = !algum;
    });
    $("mtUsadas").hidden = !!termo || !(biblioteca.mais_usadas || []).length;
  });
  if ((biblioteca.mais_usadas || []).length) {
    $("mtUsadas").hidden = false;
    biblioteca.mais_usadas.forEach((u) => {
      if (!CATALOGO[u.tipo]) return;
      const d = Object.assign({}, CATALOGO[u.tipo].d, u.d);
      const botao = cartao($("mtUsadasGrade"), {
        foto: "",
        nome: rotuloDaPeca(u.tipo, d),
        sub: `usada ${u.vezes} vezes`,
        aoEscolher: () => comecarColocar({ tipo: u.tipo, d, cor: CATALOGO[u.tipo].cor }),
      });
      fotoDepois(botao, () => DESENHOS[u.tipo](d, CATALOGO[u.tipo].cor, {}));
    });
  }
  requestAnimationFrame(revelarFotos);
  function medidasDaFonte(f) { return f.medidas && f.medidas.length === 3 ? `${metros(f.medidas[1])} × ${metros(f.medidas[2])} × ${metros(f.medidas[0])} m` : ""; }
  function listarArquivos(destino, tipo, lista, vazio) {
    destino.innerHTML = "";
    if (!lista.length) { destino.innerHTML = `<p class="mt-dica">${vazio}</p>`; return; }
    lista.forEach((f) => {
      const botao = cartao(destino, {
        foto: "", nome: f.nome, sub: [f.categoria_nome, medidasDaFonte(f)].filter(Boolean).join(" · "),
        aoEscolher: () => comecarColocar({ tipo, ref: f.id }),
      });
      // a miniatura chega quando o .glb carrega (sem segurar a tela)
      carregarGlb(f.url).then((gltf) => {
        const foto = fotografar([gltf.scene.clone(true)]);
        botao.querySelector(".mt-item-foto").innerHTML = `<img src="${foto}" alt="">`;
      }).catch(() => {});
    });
  }
  listarArquivos($("mtGuardadas"), "modulo", biblioteca.modulos, "Nenhuma peça guardada ainda.");
  const listaObjetos = $("mtObjetos");
  listarArquivos(listaObjetos, "objeto", biblioteca.objetos, "Nenhum brinquedo com objeto 3D.");
  if (biblioteca.projetos.length) {
    const titulo = document.createElement("h6");
    titulo.innerHTML = '<i class="bi bi-easel2"></i> Projetos';
    listaObjetos.appendChild(titulo);
    const grade = document.createElement("div");
    grade.className = "mt-grade";
    listaObjetos.appendChild(grade);
    listarArquivos(grade, "projeto", biblioteca.projetos, "");
  }
  raiz.querySelectorAll(".mt-aba").forEach((aba) => {
    aba.addEventListener("click", () => {
      raiz.querySelectorAll(".mt-aba").forEach((a) => a.setAttribute("aria-selected", a === aba ? "true" : "false"));
      raiz.querySelectorAll("[data-painel]").forEach((p) => { p.hidden = p.dataset.painel !== aba.dataset.aba; });
    });
  });

  /* ---------------------------------------------------------------- colocar uma peça */
  let colocando = null; // { dados, fantasma }
  async function comecarColocar(dadosPeca) {
    cancelarColocar();
    selecionar(null);
    const fantasma = await montarPeca(Object.assign({ p: [0, 0, 0], r: 0 }, dadosPeca));
    // o fantasma não é peça ainda: sai da lista, fica meio transparente
    pecas = pecas.filter((p) => p !== fantasma);
    fantasma.obj.traverse((o) => {
      if (o.isMesh) {
        o.material = (Array.isArray(o.material) ? o.material : [o.material]).map((m) => { const c = m.clone(); c.transparent = true; c.opacity = 0.55; c.depthWrite = false; return c; });
        if (o.material.length === 1) o.material = o.material[0];
        o.castShadow = false;
      }
    });
    colocando = { dados: dadosPeca, fantasma };
    raiz.classList.add("colocando");
    const faixa = $("mtColocando");
    faixa.hidden = false;
    faixa.querySelector("span").textContent = nomeDe(fantasma);
    fantasma.obj.visible = false;
    // no celular a gaveta desce: a planta fica livre para o toque que põe a peça
    if (celular.matches) abrirGaveta("");
    tela.focus({ preventScroll: true });
  }
  function cancelarColocar() {
    if (!colocando) return;
    montagem.remove(colocando.fantasma.obj);
    if (CATALOGO[colocando.fantasma.tipo]) descartar(colocando.fantasma.obj);
    colocando = null;
    raiz.classList.remove("colocando");
    $("mtColocando").hidden = true;
    sujo = true;
  }
  $("mtCancelarColocar").addEventListener("click", cancelarColocar);

  const raio = new T.Raycaster();
  const ponteiro = new T.Vector2();
  function mirar(evento) {
    const r = tela.getBoundingClientRect();
    ponteiro.set(((evento.clientX - r.left) / r.width) * 2 - 1, -((evento.clientY - r.top) / r.height) * 2 + 1);
    raio.setFromCamera(ponteiro, camera);
  }
  function passoAtual() { return parseFloat($("mtPasso").value) || 0; }
  function encaixar(v) { const p = passoAtual(); return p ? Math.round(v / p) * p : v; }
  /** Onde a peça vai: o ponto no chão (na grade) ou em cima da peça que está embaixo. */
  function pontoDeApoio(ignorar) {
    const alvos = pecas.filter((p) => p !== ignorar).map((p) => p.obj);
    const acertos = raio.intersectObjects(alvos, true).filter((a) => a.face);
    const plano = new T.Plane(new T.Vector3(0, 1, 0), 0);
    const noChao = raio.ray.intersectPlane(plano, new T.Vector3());
    for (const a of acertos) {
      const normal = a.face.normal.clone().transformDirection(a.object.matrixWorld);
      if (normal.y > 0.6) return { x: encaixar(a.point.x), y: a.point.y, z: encaixar(a.point.z) };
    }
    if (!noChao) return null;
    return { x: encaixar(noChao.x), y: 0, z: encaixar(noChao.z) };
  }

  /* ---------------------------------------------------------------- a vista (girar, arrastar, aproximar) */
  function posicionarCamera() {
    if (modoVista === "planta") {
      const r = tela.getBoundingClientRect();
      const aspecto = (r.width || 1) / (r.height || 1);
      const z = vista.zoomPlanta;
      Object.assign(cameraPlanta, { left: -z * aspecto, right: z * aspecto, top: z, bottom: -z });
      cameraPlanta.position.set(vista.alvo.x, 60, vista.alvo.z);
      cameraPlanta.up.set(0, 0, -1);
      cameraPlanta.lookAt(vista.alvo.x, 0, vista.alvo.z);
      cameraPlanta.updateProjectionMatrix();
    } else {
      const d = vista.distancia;
      camera3d.position.set(
        vista.alvo.x + Math.sin(vista.giro) * Math.cos(vista.inclinacao) * d,
        vista.alvo.y + Math.sin(vista.inclinacao) * d,
        vista.alvo.z + Math.cos(vista.giro) * Math.cos(vista.inclinacao) * d,
      );
      camera3d.lookAt(vista.alvo);
    }
    sujo = true;
  }
  /* As vistas prontas: o 3D em volta, de frente, de lado e a planta. A troca é animada (sem pulo). */
  const VISTAS = { "3d": { giro: 0.75, inclinacao: 0.55 }, frente: { giro: 0, inclinacao: 0.1 }, lado: { giro: Math.PI / 2, inclinacao: 0.1 } };
  let animacao = null;
  function animarVista(para, ms = 420) {
    animacao = {
      de: { giro: vista.giro, inclinacao: vista.inclinacao, distancia: vista.distancia, zoomPlanta: vista.zoomPlanta, alvo: vista.alvo.clone() },
      para, t0: performance.now(), ms,
    };
    sujo = true;
  }
  function passoDaAnimacao() {
    if (!animacao) return;
    const { de, para, t0, ms } = animacao;
    const t = Math.min(1, (performance.now() - t0) / ms), e = 1 - Math.pow(1 - t, 3);
    if (para.giro !== undefined) {
      const delta = ((para.giro - de.giro + Math.PI * 3) % (Math.PI * 2)) - Math.PI; // pelo lado mais curto
      vista.giro = de.giro + delta * e;
    }
    for (const k of ["inclinacao", "distancia", "zoomPlanta"]) if (para[k] !== undefined) vista[k] = de[k] + (para[k] - de[k]) * e;
    if (para.alvo) vista.alvo.lerpVectors(de.alvo, para.alvo, e);
    posicionarCamera();
    if (t >= 1) animacao = null;
    sujo = true;
  }
  function marcarVista(nome) {
    raiz.querySelectorAll("[data-vista]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.vista === nome ? "true" : "false"));
  }
  function trocarVista(nova) {
    const planta = nova === "planta";
    modoVista = planta ? "planta" : "3d";
    camera = planta ? cameraPlanta : camera3d;
    controles.camera = camera;
    marcarVista(nova);
    if (!planta && VISTAS[nova]) {
      // a vista pronta já enquadra a montagem inteira, olhando daquele lado
      const para = Object.assign({}, VISTAS[nova]);
      const caixaToda = new T.Box3().setFromObject(montagem);
      if (!caixaToda.isEmpty()) {
        animacao = { para };
        para.alvo = caixaToda.getCenter(new T.Vector3());
        para.distancia = distanciaQueCabe(caixaToda, para.alvo);
      }
      animarVista(para);
    } else posicionarCamera();
  }
  raiz.querySelectorAll("[data-vista]").forEach((b) => b.addEventListener("click", () => trocarVista(b.dataset.vista)));
  raiz.querySelectorAll("[data-rodar]").forEach((b) => b.addEventListener("click", () => {
    if (modoVista === "planta") trocarVista("3d");
    animarVista({ giro: vista.giro + T.MathUtils.degToRad(Number(b.dataset.rodar)) }, 300);
    marcarVista("3d");
  }));
  raiz.querySelectorAll("[data-zoom]").forEach((b) => b.addEventListener("click", () => {
    const f = Number(b.dataset.zoom);
    if (modoVista === "planta") animarVista({ zoomPlanta: Math.min(80, Math.max(1, vista.zoomPlanta * f)) }, 250);
    else animarVista({ distancia: Math.min(150, Math.max(1.5, vista.distancia * f)) }, 250);
  }));
  /**
   * A distância em que os 8 cantos da montagem cabem na tela, olhando do giro e da inclinação
   * de agora (com folga para os botões da vista): projeta, corrige e repete.
   */
  function distanciaQueCabe(caixa, centro) {
    const cantos = [];
    for (const x of [caixa.min.x, caixa.max.x]) for (const y of [caixa.min.y, caixa.max.y]) for (const z of [caixa.min.z, caixa.max.z]) cantos.push(new T.Vector3(x, y, z));
    const cam = camera3d.clone();
    const ponto = new T.Vector3();
    let d = Math.max(4, caixa.getSize(new T.Vector3()).length());
    const giro = animacao && animacao.para.giro !== undefined ? animacao.para.giro : vista.giro;
    const inclinacao = animacao && animacao.para.inclinacao !== undefined ? animacao.para.inclinacao : vista.inclinacao;
    for (let volta = 0; volta < 4; volta++) {
      cam.position.set(centro.x + Math.sin(giro) * Math.cos(inclinacao) * d, centro.y + Math.sin(inclinacao) * d, centro.z + Math.cos(giro) * Math.cos(inclinacao) * d);
      cam.lookAt(centro);
      cam.updateMatrixWorld(true);
      let maior = 0;
      for (const c of cantos) {
        ponto.copy(c).project(cam);
        maior = Math.max(maior, Math.abs(ponto.x) / 0.86, Math.abs(ponto.y) / 0.8);
      }
      if (!(maior > 0)) break;
      d = Math.max(2.5, Math.min(300, d * maior));
    }
    return d;
  }
  function enquadrar(animado = true) {
    const b = new T.Box3().setFromObject(montagem);
    let para;
    if (b.isEmpty()) para = { alvo: new T.Vector3(0, 0.8, 0), distancia: 14, zoomPlanta: 8 };
    else {
      const centro = b.getCenter(new T.Vector3()), tamanho = b.getSize(new T.Vector3());
      const r = tela.getBoundingClientRect();
      const aspecto = Math.max(0.3, (r.width || 1) / (r.height || 1));
      para = {
        alvo: centro, distancia: distanciaQueCabe(b, centro),
        zoomPlanta: Math.max(3, Math.max(tamanho.z * 0.58, (tamanho.x * 0.58) / aspecto) + 0.6),
      };
    }
    if (animado) animarVista(para, 450);
    else { Object.assign(vista, { distancia: para.distancia, zoomPlanta: para.zoomPlanta }); vista.alvo.copy(para.alvo); posicionarCamera(); }
  }
  $("mtEnquadrar").addEventListener("click", () => enquadrar());
  // a dica dos gestos some depois do primeiro toque (ou sozinha)
  const gestos = $("mtGestos");
  let dicaSumiu = false;
  const sumirDica = () => { if (dicaSumiu) return; dicaSumiu = true; setTimeout(() => gestos.classList.add("some"), 1800); };
  setTimeout(sumirDica, 9000);
  raiz.querySelectorAll("[data-modo]").forEach((b) => b.addEventListener("click", () => {
    controles.setMode(b.dataset.modo === "girar" ? "rotate" : "translate");
    controles.showX = controles.showZ = b.dataset.modo !== "girar";
    controles.showY = true;
    raiz.querySelectorAll("[data-modo]").forEach((x) => x.setAttribute("aria-pressed", x === b ? "true" : "false"));
    sujo = true;
  }));
  $("mtPasso").addEventListener("change", () => { const p = passoAtual(); controles.setTranslationSnap(p || null); });

  const dedos = new Map();
  let gesto = null; // { tipo: "girar"|"arrastar", x, y, moveu }
  let pinca = 0;
  tela.addEventListener("contextmenu", (e) => e.preventDefault());
  tela.addEventListener("pointerdown", (e) => {
    tela.focus({ preventScroll: true });
    sumirDica();
    animacao = null;
    if (controles.axis !== null || arrastandoAlca) return; // a alça da peça cuida
    tela.setPointerCapture(e.pointerId);
    dedos.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (dedos.size === 2) {
      const [a, b] = [...dedos.values()];
      pinca = Math.hypot(a.x - b.x, a.y - b.y);
      gesto = { tipo: "pinca", x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, moveu: true };
      return;
    }
    const arrastar = e.button === 2 || e.button === 1 || e.shiftKey || modoVista === "planta";
    gesto = { tipo: arrastar ? "arrastar" : "girar", x: e.clientX, y: e.clientY, inicioX: e.clientX, inicioY: e.clientY, moveu: false };
  });
  tela.addEventListener("pointermove", (e) => {
    if (colocando && !gesto) {
      mirar(e);
      const ponto = pontoDeApoio(null);
      if (ponto) {
        colocando.fantasma.obj.position.set(ponto.x, ponto.y, ponto.z);
        colocando.fantasma.obj.visible = true;
        sujo = true;
      }
    }
    if (!dedos.has(e.pointerId) || !gesto) return;
    const antes = dedos.get(e.pointerId);
    dedos.set(e.pointerId, { x: e.clientX, y: e.clientY });
    const dx = e.clientX - antes.x, dy = e.clientY - antes.y;
    if (Math.hypot(e.clientX - (gesto.inicioX ?? e.clientX), e.clientY - (gesto.inicioY ?? e.clientY)) > 5) gesto.moveu = true;
    const r = tela.getBoundingClientRect();
    if (gesto.tipo === "pinca" && dedos.size === 2) {
      const [a, b] = [...dedos.values()];
      const d = Math.hypot(a.x - b.x, a.y - b.y);
      if (pinca) aproximar(pinca / d);
      pinca = d;
      arrastarVista(dx / 2, dy / 2, r);
    } else if (gesto.tipo === "girar" && modoVista === "3d") {
      if (gesto.moveu) marcarVista("3d");
      vista.giro -= (dx / r.width) * Math.PI * 1.6;
      vista.inclinacao = Math.min(1.5, Math.max(0.05, vista.inclinacao + (dy / r.height) * Math.PI));
      posicionarCamera();
    } else {
      arrastarVista(dx, dy, r);
    }
  });
  function arrastarVista(dx, dy, r) {
    if (modoVista === "planta") {
      const porPixel = (vista.zoomPlanta * 2) / r.height;
      vista.alvo.x -= dx * porPixel;
      vista.alvo.z -= dy * porPixel;
    } else {
      const porPixel = (vista.distancia * Math.tan(T.MathUtils.degToRad(20)) * 2) / r.height;
      const direita = new T.Vector3(Math.cos(vista.giro), 0, -Math.sin(vista.giro));
      const frente = new T.Vector3(-Math.sin(vista.giro), 0, -Math.cos(vista.giro));
      vista.alvo.addScaledVector(direita, -dx * porPixel).addScaledVector(frente, dy * porPixel);
    }
    posicionarCamera();
  }
  function aproximar(fator) {
    if (modoVista === "planta") vista.zoomPlanta = Math.min(80, Math.max(1, vista.zoomPlanta * fator));
    else vista.distancia = Math.min(150, Math.max(1.5, vista.distancia * fator));
    posicionarCamera();
  }
  tela.addEventListener("wheel", (e) => { e.preventDefault(); animacao = null; sumirDica(); aproximar(Math.exp(e.deltaY * 0.0012)); }, { passive: false });
  // nada de rolar a página nem dar zoom no navegador por cima do 3D (o app é a janela inteira)
  raiz.querySelector(".mt-tela").addEventListener("touchmove", (e) => { if (e.target === tela) e.preventDefault(); }, { passive: false });
  raiz.querySelector(".mt-tela").addEventListener("gesturestart", (e) => e.preventDefault());
  const soltar = async (e) => {
    const eraGesto = gesto;
    dedos.delete(e.pointerId);
    if (dedos.size < 2) pinca = 0;
    if (dedos.size) return;
    gesto = null;
    if (!eraGesto || eraGesto.moveu || e.type === "pointercancel" || e.button === 2) return;
    // um clique sem arrastar: põe a peça (colocando) ou escolhe a peça clicada
    mirar(e);
    if (colocando) {
      const ponto = pontoDeApoio(null);
      if (!ponto) return;
      const dadosPeca = Object.assign({}, colocando.dados, { p: [ponto.x, ponto.y, ponto.z], r: 0 });
      if (!e.shiftKey) cancelarColocar();
      const nova = await montarPeca(dadosPeca);
      selecionar(nova);
      registrar();
      return;
    }
    const acerto = raio.intersectObjects(pecas.map((p) => p.obj), true)[0];
    let alvo = acerto ? acerto.object : null;
    while (alvo && !pecaDoObjeto.has(alvo)) alvo = alvo.parent;
    selecionar(alvo ? pecaDoObjeto.get(alvo) : null);
  };
  tela.addEventListener("pointerup", soltar);
  tela.addEventListener("pointercancel", soltar);

  /* ---------------------------------------------------------------- o teclado */
  document.addEventListener("keydown", (e) => {
    if (!raiz.isConnected) return;
    const alvo = e.target;
    if (alvo && (alvo.tagName === "INPUT" || alvo.tagName === "SELECT" || alvo.tagName === "TEXTAREA")) return;
    if (document.querySelector(".modal.show")) return;
    const ctrl = e.ctrlKey || e.metaKey;
    if (e.key === "Escape") { cancelarColocar(); selecionar(null); return; }
    if (ctrl && e.key.toLowerCase() === "z") { e.preventDefault(); (e.shiftKey ? $("mtRefazer") : $("mtDesfazer")).click(); return; }
    if (ctrl && e.key.toLowerCase() === "y") { e.preventDefault(); $("mtRefazer").click(); return; }
    if (e.key === "f" || e.key === "F") { enquadrar(); return; }
    if (!selecionada) return;
    const passo = passoAtual() || 0.05;
    const mover = { ArrowLeft: [-passo, 0, 0], ArrowRight: [passo, 0, 0], ArrowUp: [0, 0, -passo], ArrowDown: [0, 0, passo], PageUp: [0, passo, 0], PageDown: [0, -passo, 0] }[e.key];
    if (mover) {
      e.preventDefault();
      selecionada.obj.position.add(new T.Vector3(...mover));
      prenderNoChao(selecionada);
      caixaSelecao.setFromObject(selecionada.obj);
      registrar();
      mostrarPropriedades();
      sujo = true;
    } else if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); apagar(selecionada); }
    else if (ctrl && e.key.toLowerCase() === "d") { e.preventDefault(); duplicar(selecionada); }
    else if (e.key === "r" || e.key === "R") { girar(e.shiftKey ? -90 : 90); }
    else if (e.key === "g" || e.key === "G") { raiz.querySelector('[data-modo="mover"]').click(); }
  });

  /* ---------------------------------------------------------------- as cotas e o resumo */
  const cotasCaixa = $("mtCotasCaixa");
  let mostrarCotas = true;
  const linhasCota = new T.LineSegments(new T.BufferGeometry(), new T.LineBasicMaterial({ color: "#ffd23f" }));
  linhasCota.renderOrder = 10;
  cena.add(linhasCota);
  const rotulosCota = ["largura", "profundidade", "altura"].map((nome) => {
    const r = document.createElement("span");
    r.className = "mt-cota mt-cota--" + nome;
    cotasCaixa.appendChild(r);
    return r;
  });
  $("mtCotas").addEventListener("click", () => {
    mostrarCotas = !mostrarCotas;
    $("mtCotas").setAttribute("aria-pressed", mostrarCotas ? "true" : "false");
    sujo = true;
  });
  let caixaTotal = new T.Box3();
  function medirTudo() {
    caixaTotal = new T.Box3();
    pecas.forEach((p) => caixaTotal.expandByObject(p.obj));
    return caixaTotal;
  }
  function atualizarResumo() {
    const b = medirTudo();
    if (!pecas.length || b.isEmpty()) { $("mtResumo").textContent = "Nenhuma peça ainda: escolha uma à esquerda ou chame o Projetista."; return; }
    const t = b.getSize(new T.Vector3());
    $("mtResumo").innerHTML = `<strong>${pecas.length} peça${pecas.length > 1 ? "s" : ""}</strong> · ${metros(t.x)} m de largura × ${metros(t.z)} m de profundidade × ${metros(t.y)} m de altura`;
    // a sombra cobre a montagem inteira
    const centro = b.getCenter(new T.Vector3()), raioSombra = Math.max(4, t.length() / 2 + 1);
    sol.position.set(centro.x + 8, centro.y + 14, centro.z + 10);
    sol.target.position.copy(centro);
    Object.assign(sol.shadow.camera, { left: -raioSombra, right: raioSombra, top: raioSombra, bottom: -raioSombra, near: 0.5, far: 60 });
    sol.shadow.camera.updateProjectionMatrix();
    sujo = true;
  }
  function desenharCotas() {
    const b = caixaTotal;
    const ativo = mostrarCotas && pecas.length && !b.isEmpty();
    linhasCota.visible = !!ativo;
    rotulosCota.forEach((r) => { r.hidden = !ativo; });
    if (!ativo) return;
    const { min, max } = b;
    const f = 0.35; // a folga da linha de cota
    const pts = [
      min.x, 0.01, max.z + f, max.x, 0.01, max.z + f,          // largura (na frente)
      max.x + f, 0.01, min.z, max.x + f, 0.01, max.z,          // profundidade (do lado)
      max.x + f, 0, max.z + f, max.x + f, max.y, max.z + f,    // altura (na quina)
    ];
    linhasCota.geometry.setAttribute("position", new T.Float32BufferAttribute(pts, 3));
    linhasCota.geometry.computeBoundingSphere();
    const r = tela.getBoundingClientRect();
    const meios = [
      [(min.x + max.x) / 2, 0.01, max.z + f, max.x - min.x],
      [max.x + f, 0.01, (min.z + max.z) / 2, max.z - min.z],
      [max.x + f, max.y / 2, max.z + f, max.y],
    ];
    meios.forEach(([x, y, z, valor], i) => {
      const p = new T.Vector3(x, y, z).project(camera);
      const rotulo = rotulosCota[i];
      if (p.z > 1 || (i === 2 && modoVista === "planta")) { rotulo.hidden = true; return; }
      rotulo.textContent = metros(valor) + " m";
      rotulo.style.transform = `translate(${((p.x + 1) / 2) * r.width}px, ${((1 - p.y) / 2) * r.height}px) translate(-50%, -50%)`;
    });
  }

  /* ---------------------------------------------------------------- desenhar só quando muda */
  function medir() {
    const r = tela.getBoundingClientRect();
    if (!r.width || !r.height) return;
    renderer.setSize(r.width, r.height, false);
    camera3d.aspect = r.width / r.height;
    camera3d.updateProjectionMatrix();
    posicionarCamera();
  }
  new ResizeObserver(medir).observe(tela);
  function quadro() {
    requestAnimationFrame(quadro);
    passoDaAnimacao();
    if (!sujo) return;
    sujo = false;
    if (selecionada && caixaSelecao.visible) caixaSelecao.setFromObject(selecionada.obj);
    if (arrastandoAlca) medirTudo();
    renderer.render(cena, camera);
    desenharCotas();
  }

  /* ---------------------------------------------------------------- exportar, guardar, usar */
  async function exportarGlb() {
    const { GLTFExporter } = await import(raiz.dataset.exportar);
    const saida = new T.Group();
    saida.name = $("mtNome").value.trim() || "Montagem";
    pecas.forEach((p) => {
      const copia = p.obj.clone(true);
      copia.name = nomeDe(p);
      saida.add(copia);
    });
    saida.updateMatrixWorld(true);
    const binario = await new GLTFExporter().parseAsync(saida, { binary: true, onlyVisible: true, maxTextureSize: 1024 });
    return new Blob([binario], { type: "model/gltf-binary" });
  }
  function medidasJson() {
    const t = medirTudo().getSize(new T.Vector3());
    return JSON.stringify([t.y, t.x, t.z].map((v) => Math.round(v * 100) / 100));
  }
  function enviar(url, dadosForm) {
    dadosForm.set("csrfmiddlewaretoken", csrf);
    return fetch(url, { method: "POST", body: dadosForm, headers: { "X-Requested-With": "XMLHttpRequest" }, credentials: "same-origin" })
      .then((r) => r.json().catch(() => null))
      .then((json) => {
        if (!json || json.status !== "sucesso") throw new Error((json && json.msg) || "Não deu agora. Tente de novo.");
        return json;
      });
  }
  let montagemId = dados.montagem ? dados.montagem.id : null;
  let projetoDaMontagem = dados.montagem ? dados.montagem.projeto : null;
  function ocupado(botao, texto) {
    const antes = botao.innerHTML;
    botao.disabled = true;
    botao.innerHTML = `<span class="spinner-border spinner-border-sm"></span> ${texto}`;
    return () => { botao.disabled = false; botao.innerHTML = antes; };
  }
  $("mtSalvar").addEventListener("click", async () => {
    const nome = $("mtNome").value.trim();
    if (!nome) { window.Painel && Painel.aviso("Dê um nome à montagem antes de guardar.", "erro"); $("mtNome").focus(); return; }
    if (!pecas.length) { window.Painel && Painel.aviso("Ponha pelo menos uma peça.", "erro"); return; }
    const pronto = ocupado($("mtSalvar"), "Guardando…");
    try {
      const f = new FormData();
      f.set("action", "salvar");
      if (montagemId) f.set("id", montagemId);
      if (projetoDaMontagem) f.set("projeto", projetoDaMontagem);
      f.set("nome", nome);
      f.set("pecas", JSON.stringify(pecas.map(paraJson)));
      f.set("medidas", medidasJson());
      f.set("arquivo", await exportarGlb(), "montagem.glb");
      const json = await enviar(raiz.dataset.acao, f);
      montagemId = json.id;
      history.replaceState(null, "", "?m=" + json.id);
      window.Painel && Painel.aviso(json.msg, "ok");
    } catch (erro) {
      window.Painel && Painel.aviso(erro.message, "erro");
    } finally { pronto(); }
  });
  $("mtBaixar").addEventListener("click", async () => {
    if (!pecas.length) return;
    const pronto = ocupado($("mtBaixar"), "");
    try {
      const blob = await exportarGlb();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = ($("mtNome").value.trim() || "montagem").replace(/[^\w\- ]+/g, "").replace(/\s+/g, "-").toLowerCase() + ".glb";
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 5000);
    } finally { pronto(); }
  });
  $("mtAbrir").addEventListener("change", function () {
    if (this.value === "nova") location.href = location.pathname;
    else if (this.value) location.href = "?m=" + this.value;
  });

  // "Usar em…": nos brinquedos e/ou no projeto
  const usarLista = $("usarBrinquedos");
  (dados.brinquedos || []).forEach((b) => {
    const l = document.createElement("label");
    l.className = "mt-usar-item";
    l.dataset.busca = b.nome.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
    l.innerHTML = `<input type="checkbox" value="${b.id}"><span></span>${b.tem_3d ? "<small>tem 3D: troca</small>" : ""}`;
    l.querySelector("span").textContent = b.nome;
    usarLista.appendChild(l);
  });
  (dados.projetos || []).forEach((p) => {
    const o = document.createElement("option");
    o.value = p.id;
    o.textContent = p.titulo;
    $("usarProjeto").appendChild(o);
  });
  $("usarBusca").addEventListener("input", function () {
    const termo = this.value.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
    usarLista.querySelectorAll("[data-busca]").forEach((l) => { l.hidden = !!termo && l.dataset.busca.indexOf(termo) < 0 && !l.querySelector("input").checked; });
  });
  $("mtUsar").addEventListener("click", () => {
    if (!pecas.length) { window.Painel && Painel.aviso("Ponha pelo menos uma peça.", "erro"); return; }
    Painel.erro("usarErro", "");
    if (projetoDaMontagem) $("usarProjeto").value = String(projetoDaMontagem);
    Painel.abrir("modalUsar");
  });
  $("usarGravar").addEventListener("click", async () => {
    const marcados = [...usarLista.querySelectorAll("input:checked")].map((c) => c.value);
    const projeto = $("usarProjeto").value;
    if (!marcados.length && !projeto) { Painel.erro("usarErro", "Escolha um ou mais brinquedos e/ou o projeto."); return; }
    const pronto = ocupado($("usarGravar"), "Gravando…");
    try {
      const f = new FormData();
      f.set("action", "gerado_salvar");
      f.set("arquivo", await exportarGlb(), "montagem.glb");
      marcados.forEach((id) => f.append("brinquedos", id));
      if (projeto) f.set("projeto", projeto);
      if ($("usarArena").checked) f.set("exibir_na_arena", "on");
      f.set("origem", "montagem");
      f.set("modo", "montagem");
      const json = await enviar(raiz.dataset.acaoObjetos, f);
      Painel.fechar("modalUsar");
      Painel.aviso(json.msg, "ok");
    } catch (erro) {
      Painel.erro("usarErro", erro.message);
    } finally { pronto(); }
  });

  /* ---------------------------------------------------------------- aprender de um arquivo da fábrica */
  let aprendida = null;
  $("mtAprender").addEventListener("click", async () => {
    const arquivo = $("mtAprenderArquivo").files[0];
    const destino = $("mtAprendidas");
    if (!arquivo) { destino.innerHTML = '<p class="mt-dica text-warning">Escolha o arquivo primeiro.</p>'; return; }
    const pronto = ocupado($("mtAprender"), "Lendo o arquivo…");
    destino.innerHTML = "";
    try {
      const f = new FormData();
      f.set("action", "aprender");
      f.set("arquivo3d", arquivo);
      const json = await enviar(raiz.dataset.acao, f);
      destino.innerHTML = `<p class="mt-dica"><strong>${json.msg}</strong></p>`;
      for (const p of json.pecas) {
        const bytes = Uint8Array.from(atob(p.glb), (c) => c.charCodeAt(0));
        const gltf = await leitor.parseAsync(bytes.buffer, "");
        const vezes = document.createElement("em");
        vezes.className = "mt-vezes";
        vezes.textContent = `×${p.vezes} no arquivo`;
        cartao(destino, {
          foto: fotografar([gltf.scene]), nome: p.nome, sub: p.medidas_texto, extra: vezes,
          aoEscolher: () => {
            aprendida = { bytes, nome: p.nome, categoria: p.categoria };
            $("guardarNome").value = p.nome;
            $("guardarCategoria").value = p.categoria;
            Painel.erro("guardarErro", "");
            Painel.abrir("modalGuardarPeca");
          },
        });
      }
    } catch (erro) {
      destino.innerHTML = "";
      const e = document.createElement("p");
      e.className = "mt-dica text-danger";
      e.textContent = erro.message;
      destino.appendChild(e);
    } finally { pronto(); }
  });
  $("guardarPeca").addEventListener("click", async () => {
    if (!aprendida) return;
    const pronto = ocupado($("guardarPeca"), "Guardando…");
    try {
      const f = new FormData();
      f.set("action", "modulo_salvar");
      f.set("nome", $("guardarNome").value.trim() || aprendida.nome);
      f.set("categoria", $("guardarCategoria").value);
      f.set("descricao", "Aprendida de um arquivo da fábrica (Montar em 3D).");
      f.set("arquivo", new Blob([aprendida.bytes], { type: "model/gltf-binary" }), "peca.glb");
      const json = await enviar(raiz.dataset.acaoObjetos, f);
      Painel.fechar("modalGuardarPeca");
      Painel.aviso(json.msg, "ok");
      if (json.id && json.url) {
        // já entra na biblioteca desta tela, pronta para pôr
        const nova = { id: json.id, nome: f.get("nome"), categoria_nome: $("guardarCategoria").selectedOptions[0].textContent, url: json.url, medidas: json.medidas || [] };
        biblioteca.modulos.push(nova);
        listarArquivos($("mtGuardadas"), "modulo", biblioteca.modulos, "");
      }
    } catch (erro) {
      Painel.erro("guardarErro", erro.message);
    } finally { pronto(); }
  });

  /* ---------------------------------------------------------------- o app: gaveta (celular) e tela cheia */
  function abrirGaveta(qual) {
    raiz.dataset.gaveta = qual || "";
    raiz.querySelectorAll(".mt-gaveta-abas [data-gaveta]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.gaveta === qual ? "true" : "false"));
    requestAnimationFrame(medir);
  }
  raiz.querySelectorAll(".mt-gaveta-abas [data-gaveta]").forEach((b) => b.addEventListener("click", () => {
    abrirGaveta(raiz.dataset.gaveta === b.dataset.gaveta ? "" : b.dataset.gaveta);
  }));
  raiz.querySelector("[data-gaveta-gerar]").addEventListener("click", () => abrirProjetista());
  const aoTrocarDeTamanho = () => abrirGaveta("");
  if (celular.addEventListener) celular.addEventListener("change", aoTrocarDeTamanho); else celular.addListener(aoTrocarDeTamanho);
  const botaoTelaCheia = $("mtTelaCheia");
  if (document.fullscreenEnabled && document.documentElement.requestFullscreen) {
    botaoTelaCheia.hidden = false;
    botaoTelaCheia.addEventListener("click", () => {
      if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
      else document.documentElement.requestFullscreen({ navigationUI: "hide" }).catch(() => {});
    });
    document.addEventListener("fullscreenchange", () => {
      if (!raiz.isConnected) return;
      botaoTelaCheia.querySelector("i").className = document.fullscreenElement ? "bi bi-fullscreen-exit" : "bi bi-arrows-fullscreen";
      botaoTelaCheia.title = document.fullscreenElement ? "Sair da tela cheia" : "Tela cheia";
    });
  }

  /* ---------------------------------------------------------------- cor-tema (a montagem inteira) */
  const projetista = {
    tipo: "brinquedao", estilo: "colorido", cor: "#2563eb", semente: 1,
    medidas: Object.assign({}, gerador.PROJETOS.brinquedao.medidas),
  };
  let corTema = projetista.cor;
  const temaPainel = $("mtTemaPainel");
  function amostraDoTema(hex) {
    const p = gerador.paletaDaCor(hex, projetista.estilo);
    $("mtTemaAmostra").style.background = `conic-gradient(${p.estrutura} 0 25%, ${p.acento} 0 50%, ${p.destaque} 0 75%, ${p.varias[0]} 0)`;
  }
  function escolherCorTema(cor) {
    corTema = cor;
    marcarAmostra($("mtTemaCores"), cor);
    $("mtTemaLivre").value = cor;
    amostraDoTema(cor);
  }
  amostras($("mtTemaCores"), RAIZES, escolherCorTema);
  $("mtTemaLivre").addEventListener("input", function () { corTema = this.value; marcarAmostra($("mtTemaCores"), this.value); amostraDoTema(this.value); });
  function fecharTema() { temaPainel.hidden = true; $("mtTema").setAttribute("aria-expanded", "false"); }
  $("mtTema").addEventListener("click", () => {
    const abrir = temaPainel.hidden;
    temaPainel.hidden = !abrir;
    $("mtTema").setAttribute("aria-expanded", abrir ? "true" : "false");
    if (abrir) { $("mtIdeia").hidden = true; escolherCorTema(corTema); }
  });
  /** Pinta a montagem inteira: cada peça desenhada pelo seu papel; os .glb pelas famílias de cor. Sem cor: as de fábrica. */
  async function pintarTudo(hex) {
    if (!pecas.length) { window.Painel && Painel.aviso("Ponha peças (ou chame o Projetista) antes de pintar.", "erro"); return; }
    const paleta = hex ? gerador.paletaDaCor(hex, projetista.estilo) : null;
    const contagem = {};
    for (const p of pecas) {
      if (CATALOGO[p.tipo]) {
        const i = (contagem[p.tipo] = (contagem[p.tipo] || 0) + 1) - 1;
        p.cor = paleta ? gerador.corDoPapel(paleta, p.tipo, i) : CATALOGO[p.tipo].cor;
        if (p.cor2) {
          const segunda = p.tipo === "piso_eva" ? paleta && paleta.chao2 : p.tipo === "rede" ? paleta && paleta.estrutura : paleta && gerador.corDoPapel(paleta, p.tipo, i + 3);
          p.cor2 = segunda || CATALOGO[p.tipo].cor2 || null;
        }
        await redesenhar(p);
      } else {
        p.tema = hex || null;
        vestir(p);
      }
    }
    if (selecionada) caixaSelecao.setFromObject(selecionada.obj);
    registrar();
    mostrarPropriedades();
  }
  $("mtTemaAplicar").addEventListener("click", async () => { await pintarTudo(corTema); fecharTema(); });
  $("mtTemaOriginal").addEventListener("click", async () => { await pintarTudo(null); fecharTema(); });

  /* ---------------------------------------------------------------- o projetista */
  const tiposGerar = $("gerarTipos");
  Object.entries(gerador.PROJETOS).forEach(([chave, p]) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "mt-gerar-tipo";
    b.setAttribute("role", "radio");
    b.dataset.tipo = chave;
    b.innerHTML = `<i class="bi ${p.icone}"></i><strong></strong><small></small>`;
    b.querySelector("strong").textContent = p.nome;
    b.querySelector("small").textContent = `${p.sub} · ${metros(p.medidas.largura)} × ${metros(p.medidas.profundidade)} m`;
    b.addEventListener("click", () => {
      projetista.tipo = chave;
      projetista.medidas = Object.assign({}, p.medidas);
      mostrarProjetista();
    });
    tiposGerar.appendChild(b);
  });
  const estilosGerar = $("gerarEstilos");
  Object.entries(gerador.ESTILOS).forEach(([chave, e]) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "mt-gerar-estilo";
    b.setAttribute("role", "radio");
    b.dataset.estilo = chave;
    b.innerHTML = `<span style="background:${e.amostra}"></span>`;
    b.append(e.nome);
    b.addEventListener("click", () => { projetista.estilo = chave; mostrarProjetista(); });
    estilosGerar.appendChild(b);
  });
  amostras($("gerarCores"), RAIZES, (cor) => { projetista.cor = cor; mostrarProjetista(); });
  $("gerarCorLivre").addEventListener("input", function () { projetista.cor = this.value; mostrarProjetista(); });
  const camposGerar = { largura: $("gerarLargura"), profundidade: $("gerarProfundidade"), altura: $("gerarAltura") };
  Object.entries(camposGerar).forEach(([chave, campo]) => campo.addEventListener("change", () => {
    const v = parseFloat(String(campo.value).replace(",", "."));
    if (v > 0) projetista.medidas[chave] = v;
  }));
  const aprendido = dados.aprendido || {};
  if (aprendido.modulo || aprendido.nivel) {
    const partes = [];
    if (aprendido.modulo) partes.push(`módulo de ${metros(aprendido.modulo)} m`);
    if (aprendido.nivel) partes.push(`pisos a cada ${metros(aprendido.nivel)} m`);
    $("gerarAprendeu").hidden = false;
    $("gerarAprendeu").innerHTML = '<i class="bi bi-mortarboard"></i> ';
    $("gerarAprendeu").append(`Aprendido das ${aprendido.vezes} montagens guardadas: ${partes.join(" e ")} (o brinquedão sai assim).`);
  }
  function mostrarProjetista() {
    tiposGerar.querySelectorAll("[data-tipo]").forEach((b) => b.setAttribute("aria-checked", b.dataset.tipo === projetista.tipo ? "true" : "false"));
    estilosGerar.querySelectorAll("[data-estilo]").forEach((b) => b.setAttribute("aria-checked", b.dataset.estilo === projetista.estilo ? "true" : "false"));
    Object.entries(camposGerar).forEach(([chave, campo]) => { campo.value = projetista.medidas[chave]; });
    marcarAmostra($("gerarCores"), projetista.cor);
    $("gerarCorLivre").value = projetista.cor;
    const p = gerador.paletaDaCor(projetista.cor, projetista.estilo);
    $("gerarPaleta").innerHTML = [p.estrutura, p.chao, ...p.varias, p.destaque, p.protecao].map((c) => `<span style="background:${c}" title="${c}"></span>`).join("");
    $("gerarAviso").hidden = !pecas.length;
  }
  function abrirProjetista() {
    mostrarProjetista();
    Painel.abrir("modalGerar");
  }
  $("mtGerar").addEventListener("click", abrirProjetista);
  let nomeDoProjetista = "";
  async function aplicarIdeia() {
    const ideia = gerador.gerar(projetista.tipo, projetista.medidas, projetista.cor, projetista.semente, { estilo: projetista.estilo, aprendido });
    cancelarColocar();
    selecionar(null);
    fecharTema();
    aviso.hidden = false;
    aviso.textContent = "O projetista está montando…";
    await new Promise((pronto) => requestAnimationFrame(() => setTimeout(pronto, 0)));
    pecas.forEach((p) => { if (CATALOGO[p.tipo]) descartar(p.obj); });
    montagem.clear();
    pecas = [];
    for (const p of ideia.pecas) await montarPeca(p);
    aviso.hidden = true;
    const nome = $("mtNome");
    if (!nome.value.trim() || nome.value === nomeDoProjetista) { nome.value = ideia.titulo; nomeDoProjetista = ideia.titulo; }
    registrar();
    if (modoVista === "planta") trocarVista("3d");
    enquadrar();
    escolherCorTema(projetista.cor);
    // o cartão da ideia: o que entrou e as regras que ele seguiu
    $("mtIdeiaTitulo").textContent = ideia.titulo;
    const resumo = $("mtIdeiaResumo"), regras = $("mtIdeiaRegras");
    resumo.innerHTML = "";
    regras.innerHTML = "";
    ideia.resumo.forEach((r) => { const li = document.createElement("li"); li.textContent = r; resumo.appendChild(li); });
    ideia.regras.forEach((r) => { const li = document.createElement("li"); li.textContent = r; regras.appendChild(li); });
    $("mtIdeia").hidden = false;
    if (celular.matches) abrirGaveta("");
    return ideia;
  }
  $("gerarIr").addEventListener("click", async () => {
    Object.entries(camposGerar).forEach(([chave, campo]) => {
      const v = parseFloat(String(campo.value).replace(",", "."));
      if (v > 0) projetista.medidas[chave] = v;
    });
    projetista.semente = 1;
    Painel.fechar("modalGerar");
    await aplicarIdeia();
  });
  $("mtIdeiaOutra").addEventListener("click", async () => { projetista.semente += 1; await aplicarIdeia(); });
  $("mtIdeiaAjustar").addEventListener("click", abrirProjetista);
  $("mtIdeiaFechar").addEventListener("click", () => { $("mtIdeia").hidden = true; });

  /* ---------------------------------------------------------------- começar */
  medir();
  if (dados.montagem && dados.montagem.pecas && dados.montagem.pecas.length) {
    aviso.textContent = "Abrindo a montagem…";
    await restaurar(JSON.stringify(dados.montagem.pecas));
    enquadrar(false);
  } else {
    posicionarCamera();
  }
  amostraDoTema(corTema);
  estadoAtual = JSON.stringify(pecas.map(paraJson));
  aviso.hidden = true;
  requestAnimationFrame(quadro);
  // para os testes e para quem quiser olhar no console
  window.LSMontar3D = {
    pecas: () => pecas.map(paraJson), colocar: (d) => montarPeca(d).then((p) => { registrar(); return p; }), exportarGlb,
    selecionar: (i) => selecionar(pecas[i] || null), tipos: () => Object.keys(CATALOGO),
    gerar: (cfg) => { Object.assign(projetista, cfg || {}); return aplicarIdeia(); }, pintar: pintarTudo, vista: trocarVista,
  };
}
