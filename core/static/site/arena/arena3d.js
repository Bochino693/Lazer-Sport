/* ======================================================================
   ARENA 3D — os brinquedos da fábrica em estandes, para girar e aproximar.

   COMO A CENA É MONTADA. Cada brinquedo ganha um estande: um pedestal com
   anel de luz, o brinquedo modelado pelo TIPO dele (o servidor deduz o
   tipo pelo nome e pela categoria -- ver `core/arena.py`) no tamanho real
   do cadastro, e um totem atrás com a foto de verdade e o nome. Os
   estandes ficam em roda, de frente para o centro, onde gira o alvo da
   marca.

   POR QUE NÃO HÁ ARQUIVO 3D DE CADA BRINQUEDO. O catálogo não tem, e
   exigir um modelo por produto deixaria a arena vazia. Os desenhos daqui
   são feitos de peças simples (caixa, cilindro, toro), compartilham
   geometria e material, e cabem num celular comum.

   O QUE ESTE ARQUIVO NÃO FAZ: carregar o three.js antes da hora. O motor
   (~170 KB comprimido) só desce quando o palco chega perto da tela, e
   nunca num aparelho sem WebGL -- ali a página continua sendo a lista de
   brinquedos que o servidor já mandou.
   ====================================================================== */

const palco = document.querySelector("[data-arena]");
if (palco) iniciar(palco);

const CORES = ["#e63946", "#2f8bff", "#ffd700", "#3fd0ff", "#8a5cff", "#ff7a00", "#1fbf5b", "#ff3df2"];
const PI = Math.PI;

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

function semTresD(palco, motivo) {
  palco.classList.add("sem-3d");
  avisar(palco, "A vitrine 3D não abre neste aparelho", motivo + " Os brinquedos estão logo abaixo, em lista.", true);
}

async function iniciar(palco) {
  const fonte = document.getElementById("arena-dados");
  if (!fonte) return;
  if (!webglDisponivel()) {
    semTresD(palco, "Este navegador não tem aceleração 3D (WebGL).");
    return;
  }

  await quandoPerto(palco);

  let THREE;
  try {
    THREE = await import(palco.dataset.three);
  } catch (erro) {
    console.error("Arena 3D: o motor não carregou", erro);
    semTresD(palco, "Não foi possível carregar o motor 3D agora.");
    return;
  }

  try {
    const dados = JSON.parse(fonte.textContent);
    const arena = new Arena(THREE, palco, dados);
    arena.ligar();
    window.lsArena = arena; // para depuração no console do navegador
  } catch (erro) {
    console.error("Arena 3D: falhou ao montar a cena", erro);
    semTresD(palco, "Algo deu errado ao montar a cena.");
  }
}

/* ======================================================================
   A ARENA
   ====================================================================== */
class Arena {
  constructor(THREE, palco, dados) {
    this.T = THREE;
    this.palco = palco;
    // Na página de um produto o palco tem um brinquedo só, sem a roda.
    this.unico = palco.hasAttribute("data-unico");
    this.todos = dados.map((b, i) => ({ ...b, indiceOriginal: i, cor: CORES[i % CORES.length] }));
    this.visiveis = this.todos.slice();
    this.estandes = [];
    this.selecionado = -1;
    this.reduzido = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    this.celular = window.matchMedia && window.matchMedia("(max-width: 700px)").matches;
    this.limite = this.celular ? 10 : 16;
    this.pagina = 0;
    this.relogio = 0;
    this.ocioso = 0;
    this.tour = false;
    this.tourTempo = 0;
    this.geometrias = new Map();
    this.materiais = new Map();
    this.deslocamento = { x: 0, y: 0 };

    const T = THREE;
    this.canvas = document.createElement("canvas");
    this.canvas.setAttribute("aria-label", "Arena 3D com os brinquedos da Lazer & Sport. Arraste para girar e toque num brinquedo para ver a ficha.");
    this.canvas.setAttribute("role", "img");
    palco.prepend(this.canvas);

    const densidade = Math.min(window.devicePixelRatio || 1, this.celular ? 1.5 : 1.75);
    this.renderer = new T.WebGLRenderer({ canvas: this.canvas, antialias: densidade < 2, powerPreference: "high-performance" });
    this.renderer.setPixelRatio(densidade);
    this.renderer.toneMapping = T.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.15;
    this.renderer.outputColorSpace = T.SRGBColorSpace;

    this.cena = new T.Scene();
    this.cena.background = new T.Color("#040a1c");
    this.cena.fog = new T.Fog("#040a1c", 30, 90);

    this.camera = new T.PerspectiveCamera(45, 1, 0.1, 200);
    this.camera.position.set(0, 12, 28);

    this.raycaster = new T.Raycaster();
    this.ponteiro = new T.Vector2();

    this.montarLuzes();
    this.montarPiso();
    if (!this.unico) this.montarCentro();
    this.montarCeu();
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

  /* ---------- peças ---------- */
  caixa(pai, w, h, d, material, x = 0, y = 0, z = 0) {
    const g = this.geo("caixa", () => new this.T.BoxGeometry(1, 1, 1));
    const m = new this.T.Mesh(g, material);
    m.scale.set(w, h, d);
    m.position.set(x, y, z);
    pai.add(m);
    return m;
  }

  cilindro(pai, r, h, material, x = 0, y = 0, z = 0, lados = 24) {
    const g = this.geo("cil" + lados, () => new this.T.CylinderGeometry(1, 1, 1, lados));
    const m = new this.T.Mesh(g, material);
    m.scale.set(r, h, r);
    m.position.set(x, y, z);
    pai.add(m);
    return m;
  }

  esfera(pai, r, material, x = 0, y = 0, z = 0) {
    const g = this.geo("esfera", () => new this.T.SphereGeometry(1, 24, 16));
    const m = new this.T.Mesh(g, material);
    m.scale.setScalar(r);
    m.position.set(x, y, z);
    pai.add(m);
    return m;
  }

  anel(pai, r, espessura, material, x = 0, y = 0, z = 0) {
    // O toro é proporcional: guarda-se o de raio 1 e escala-se o resto.
    const proporcao = (espessura / r).toFixed(3);
    const g = this.geo("toro" + proporcao, () => new this.T.TorusGeometry(1, Number(proporcao), 12, 48));
    const m = new this.T.Mesh(g, material);
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

    // Grade radial, como piso de arena.
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

    // Anéis de neon e o nome da casa em volta do centro.
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

    g.save();
    g.translate(meio, meio);
    g.fillStyle = "rgba(255, 255, 255, .55)";
    g.font = `800 ${46 * k}px Poppins, Manrope, sans-serif`;
    g.textAlign = "center";
    g.textBaseline = "middle";
    const frase = "LAZER & SPORT  ·  ARENA 3D  ·  FÁBRICA DE BRINQUEDOS  ·  ";
    const letras = (frase + frase).split("");
    letras.forEach((letra, i) => {
      g.save();
      g.rotate((i / letras.length) * PI * 2);
      g.translate(0, -250 * k);
      g.fillText(letra, 0, 0);
      g.restore();
    });
    g.restore();

    const textura = new T.CanvasTexture(c);
    textura.colorSpace = T.SRGBColorSpace;
    textura.anisotropy = Math.min(8, this.renderer.capabilities.getMaxAnisotropy());

    // O piso tem tamanho fixo e é a escala que acompanha a roda montada.
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
    // O alvo da marca, com o dardo cravado, girando no meio da arena.
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
    this.alvoMarca = alvo;
  }

  montarCeu() {
    const T = this.T;
    // Estrelas e faíscas: pontos aditivos, uma chamada de desenho só.
    const quantidade = this.celular ? 260 : 520;
    const posicoes = new Float32Array(quantidade * 3);
    for (let i = 0; i < quantidade; i++) {
      const a = Math.random() * PI * 2;
      const r = 6 + Math.random() * 50;
      posicoes[i * 3] = Math.cos(a) * r;
      posicoes[i * 3 + 1] = 0.5 + Math.random() * 26;
      posicoes[i * 3 + 2] = Math.sin(a) * r;
    }
    const geometria = new T.BufferGeometry();
    geometria.setAttribute("position", new T.Float32BufferAttribute(posicoes, 3));
    const brilho = document.createElement("canvas");
    brilho.width = brilho.height = 64;
    const g = brilho.getContext("2d");
    const rad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    rad.addColorStop(0, "rgba(255,255,255,1)");
    rad.addColorStop(0.3, "rgba(160,210,255,.6)");
    rad.addColorStop(1, "rgba(160,210,255,0)");
    g.fillStyle = rad;
    g.fillRect(0, 0, 64, 64);
    this.estrelas = new T.Points(geometria, new T.PointsMaterial({
      size: 0.35, map: new T.CanvasTexture(brilho), transparent: true, depthWrite: false,
      blending: T.AdditiveBlending, color: "#bfe0ff",
    }));
    this.cena.add(this.estrelas);
  }

  /** Pilares de luz em volta da roda: a "arquibancada" da arena. */
  montarPilares(raio) {
    const T = this.T;
    if (this.pilares) this.cena.remove(this.pilares);
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
    this.cena.add(grupo);
    this.pilares = grupo;
    this.piso.scale.setScalar(Math.max(36, raio + 14));
  }

  /* ---------- montagem dos estandes ---------- */
  montar() {
    this.desmontar();

    if (this.unico) {
      const estande = this.criarEstande(this.visiveis[0]);
      this.cena.add(estande.grupo);
      this.estandes.push(estande);
      this.raio = 3;
      // Os pilares ficam longe: aqui a câmera chega perto do brinquedo.
      this.montarPilares(Math.max(estande.w, estande.d) + 12);
      this.cena.fog.near = 18;
      this.cena.fog.far = 60;
      this.selecionar(0);
      const c = this.camera3d;
      c.theta = c.thetaDesejado = 0.65;
      if (!this.reduzido) c.raio = c.raioDesejado * 1.6;
      return;
    }

    const inicio = this.pagina * this.limite;
    const lista = this.visiveis.slice(inicio, inicio + this.limite);
    // O raio da roda sai da soma das larguras: estande largo pede roda maior.
    const vagas = lista.map((b) => Math.max(b.medidas[1], b.medidas[2], 1.2) + 2.2);
    const circunferencia = vagas.reduce((a, b) => a + b, 0) || 1;
    const raio = Math.max(6.5, circunferencia / (PI * 2));
    this.raio = raio;

    let acumulado = 0;
    lista.forEach((brinquedo, i) => {
      const a = ((acumulado + vagas[i] / 2) / circunferencia) * PI * 2;
      acumulado += vagas[i];
      const estande = this.criarEstande(brinquedo);
      estande.grupo.position.set(Math.sin(a) * raio, 0, Math.cos(a) * raio);
      // De frente para o centro.
      estande.grupo.rotation.y = a + PI;
      this.cena.add(estande.grupo);
      this.estandes.push(estande);
    });

    this.montarPilares(raio + 6);
    this.cena.fog.near = raio * 2.2;
    this.cena.fog.far = raio * 5 + 30;
    this.camera3d.visaoGeral(true);
    this.marcarLista();
  }

  desmontar() {
    for (const estande of this.estandes) {
      this.cena.remove(estande.grupo);
      estande.descartaveis.forEach((d) => d.dispose && d.dispose());
      this.descartarComposicoes(estande);
    }
    this.estandes = [];
    this.selecionado = -1;
  }

  criarEstande(b) {
    const T = this.T;
    const grupo = new T.Group();
    const [h, w, d] = b.medidas;
    const descartaveis = [];

    // Pedestal com anel de luz.
    const raioP = Math.max(w, d) * 0.62 + 0.45;
    const alturaP = 0.3;
    this.cilindro(grupo, raioP, alturaP, this.escuro(), 0, alturaP / 2, 0, 48);
    const aro = this.anel(grupo, raioP + 0.02, 0.045, this.luz(b.cor, 2.2), 0, alturaP, 0);
    aro.rotation.x = PI / 2;
    // Sombra falsa: um disco escuro e difuso sob o brinquedo.
    const sombra = new T.Mesh(
      this.geo("sombra", () => new T.CircleGeometry(1, 32)),
      this.mat("sombra", () => new T.MeshBasicMaterial({ map: this.texturaSombra(), transparent: true, depthWrite: false })),
    );
    sombra.rotation.x = -PI / 2;
    sombra.scale.set(Math.max(w, 0.8) * 0.75, Math.max(d, 0.8) * 0.75, 1);
    sombra.position.y = alturaP + 0.005;
    grupo.add(sombra);

    // O brinquedo, num prato próprio para girar no pedestal.
    const prato = new T.Group();
    prato.position.y = alturaP;
    grupo.add(prato);
    const modelo = new T.Group();
    prato.add(modelo);

    const estande = {
      brinquedo: b, grupo, prato, modelo, aro, descartaveis, h, w, d,
      raioP, alturaP, animar: null, telas: null, faces: [],
    };

    // A roupa com que o brinquedo abre: a que o servidor escolheu pelo nome.
    const variantes = b.variantes || { adesivos: [], cores: [] };
    estande.opcao = variantes.adesivos.find((x) => x.id === variantes.adesivo) || variantes.adesivos[0] || null;
    estande.cor = (variantes.cores.find((c) => c.id === variantes.cor) || { hex: b.cor }).hex;
    estande.matCorpo = new T.MeshStandardMaterial({ color: estande.cor, roughness: 0.36, metalness: 0.18 });
    descartaveis.push(estande.matCorpo);

    // O totem atrás do brinquedo, com a foto e o nome.
    const totem = this.criarTotem(b, Math.max(1.6, w * 0.95), Math.max(2.4, h * 1.08), descartaveis);
    totem.position.set(0, 0, -(d / 2 + 0.55));
    grupo.add(totem);
    estande.totem = totem;

    const construir = MODELOS[b.desenho] || MODELOS.boliche;
    construir(this, estande, modelo);
    this.vestir(estande);

    // A foto entra quando chegar; até lá, totem com o nome e telas acesas.
    this.carregarFoto(b.capa).then((imagem) => {
      if (!imagem || !this.estandes.includes(estande)) return;
      this.pintarTotem(estande.totem, b, imagem);
      if (estande.telas && estande.telas.length) {
        const textura = new T.Texture(imagem);
        textura.colorSpace = T.SRGBColorSpace;
        textura.needsUpdate = true;
        const material = new T.MeshBasicMaterial({ map: textura, toneMapped: false });
        descartaveis.push(textura, material);
        estande.materialFoto = material;
        // A TV do boliche com tema pronto mostra o jogo, e não a foto.
        estande.telas.forEach((tela) => { if (!(tela === estande.tv && estande.telaFixa)) tela.material = material; });
      }
    });

    // Tudo do estande responde ao clique como o estande inteiro.
    grupo.traverse((obj) => { obj.userData.estande = estande; });
    return estande;
  }

  texturaSombra() {
    const c = document.createElement("canvas");
    c.width = c.height = 128;
    const g = c.getContext("2d");
    const r = g.createRadialGradient(64, 64, 0, 64, 64, 64);
    r.addColorStop(0, "rgba(0,0,0,.65)");
    r.addColorStop(1, "rgba(0,0,0,0)");
    g.fillStyle = r;
    g.fillRect(0, 0, 128, 128);
    return new this.T.CanvasTexture(c);
  }

  carregarFoto(url) {
    if (!url) return Promise.resolve(null);
    return new Promise((resolver) => {
      const img = new Image();
      // Sem isto o WebGL recusa a foto do Cloudinary (canvas "contaminado").
      img.crossOrigin = "anonymous";
      img.decoding = "async";
      img.onload = () => resolver(img);
      img.onerror = () => resolver(null);
      img.src = url;
    });
  }

  criarTotem(b, largura, altura, descartaveis) {
    const T = this.T;
    const totem = new T.Group();
    this.caixa(totem, largura + 0.12, altura + 0.12, 0.1, this.escuro(), 0, altura / 2 + 0.36, -0.03);
    this.caixa(totem, largura * 0.5, 0.36, 0.5, this.escuro(), 0, 0.18, 0);
    this.caixa(totem, largura + 0.14, 0.05, 0.12, this.luz(b.cor, 2.4), 0, altura + 0.45, -0.03);

    const canvas = document.createElement("canvas");
    canvas.width = this.celular ? 320 : 512;
    canvas.height = Math.round(canvas.width * (altura / largura));
    const textura = new T.CanvasTexture(canvas);
    textura.colorSpace = T.SRGBColorSpace;
    const material = new T.MeshBasicMaterial({ map: textura, toneMapped: false });
    const painel = new T.Mesh(this.geo("plano", () => new T.PlaneGeometry(1, 1)), material);
    painel.scale.set(largura, altura, 1);
    painel.position.set(0, altura / 2 + 0.36, 0.03);
    totem.add(painel);
    totem.userData.canvas = canvas;
    totem.userData.textura = textura;
    descartaveis.push(textura, material);
    this.pintarTotem(totem, b, null);
    return totem;
  }

  pintarTotem(totem, b, imagem) {
    const canvas = totem.userData.canvas;
    const g = canvas.getContext("2d");
    const W = canvas.width;
    const H = canvas.height;
    const k = W / 512;
    const fundo = g.createLinearGradient(0, 0, 0, H);
    fundo.addColorStop(0, "#ffffff");
    fundo.addColorStop(0.72, "#e8f0ff");
    fundo.addColorStop(1, "#c9daf8");
    g.fillStyle = fundo;
    g.fillRect(0, 0, W, H);

    const rodape = Math.min(170 * k, H * 0.26);
    if (imagem) {
      const area = { x: 24 * k, y: 24 * k, w: W - 48 * k, h: H - rodape - 40 * k };
      const escala = Math.min(area.w / imagem.width, area.h / imagem.height);
      const iw = imagem.width * escala;
      const ih = imagem.height * escala;
      g.drawImage(imagem, area.x + (area.w - iw) / 2, area.y + (area.h - ih) / 2, iw, ih);
    } else {
      g.fillStyle = "#c3d3ee";
      g.font = `900 ${120 * k}px Poppins, sans-serif`;
      g.textAlign = "center";
      g.textBaseline = "middle";
      g.fillText("L&S", W / 2, (H - rodape) / 2);
    }

    // Rodapé com o nome, na cor do estande.
    g.fillStyle = "#071433";
    g.fillRect(0, H - rodape, W, rodape);
    g.fillStyle = b.cor;
    g.fillRect(0, H - rodape, W, 10 * k);
    g.fillStyle = "#ffffff";
    g.textAlign = "center";
    g.textBaseline = "middle";
    let tamanho = 54 * k;
    g.font = `900 ${tamanho}px Poppins, Manrope, sans-serif`;
    while (g.measureText(b.nome).width > W - 40 * k && tamanho > 26 * k) {
      tamanho -= 2 * k;
      g.font = `900 ${tamanho}px Poppins, Manrope, sans-serif`;
    }
    g.fillText(b.nome, W / 2, H - rodape * 0.58, W - 30 * k);
    g.fillStyle = "#9fc1ff";
    g.font = `700 ${30 * k}px Manrope, Poppins, sans-serif`;
    g.fillText((b.categorias[0] || "Lazer & Sport").toUpperCase(), W / 2, H - rodape * 0.22, W - 30 * k);
    totem.userData.textura.needsUpdate = true;
  }

  /* ---------- cores e adesivos ---------- */

  /**
   * Um adesivo: retângulo w × h com o centro em `centro`, virado para
   * `normal`, e a borda direita do desenho apontando para `direita`. É a
   * mesma conta da maquete do Strike Kids (`gabinete_render.gd`), para os
   * adesivos caírem onde caem no gabinete de verdade.
   */
  placa(pai, w, h, centro, normal, direita, material) {
    const T = this.T;
    const n = new T.Vector3(...normal).normalize();
    const r = new T.Vector3(...direita).normalize();
    const u = new T.Vector3().crossVectors(n, r).normalize();
    const malha = new T.Mesh(this.geo("plano", () => new T.PlaneGeometry(1, 1)), material || this.escuro());
    malha.scale.set(w, h, 1);
    malha.quaternion.setFromRotationMatrix(new T.Matrix4().makeBasis(r, u, n));
    malha.position.set(...centro);
    pai.add(malha);
    return malha;
  }

  /** Uma face que veste o adesivo escolhido; até ele chegar, tem a cor do gabinete. */
  adesivo(estande, pai, id, tipo, w, h, centro, normal, direita, extras = {}) {
    const malha = this.placa(pai, w, h, centro, normal, direita, estande.matCorpo);
    estande.faces.push({ malha, id, tipo, w, h, ...extras });
    return malha;
  }

  texturaDe(url) {
    this.texturas = this.texturas || new Map();
    if (!this.texturas.has(url)) {
      const carregador = new this.T.TextureLoader();
      this.texturas.set(url, carregador.loadAsync(url).then((textura) => {
        textura.colorSpace = this.T.SRGBColorSpace;
        textura.anisotropy = Math.min(4, this.renderer.capabilities.getMaxAnisotropy());
        return textura;
      }).catch(() => null));
    }
    return this.texturas.get(url);
  }

  imagemDe(url) {
    this.imagens = this.imagens || new Map();
    if (!url) return Promise.resolve(null);
    if (!this.imagens.has(url)) {
      this.imagens.set(url, new Promise((resolver) => {
        const img = new Image();
        img.decoding = "async";
        img.onload = () => resolver(img);
        img.onerror = () => resolver(null);
        img.src = url;
      }));
    }
    return this.imagens.get(url);
  }

  materialDeAdesivo(textura, face) {
    // Furos vazados (tela, START, ficha) cortam a superfície: `alphaTest`
    // em vez de transparência evita a briga de ordem entre as camadas.
    return new this.T.MeshStandardMaterial({
      map: textura,
      alphaTest: 0.45,
      roughness: face.tipo === "piso" ? 0.55 : 0.32,
      metalness: 0.05,
      emissive: face.brilho || face.tipo === "letreiro" ? "#ffffff" : "#000000",
      emissiveMap: face.brilho || face.tipo === "letreiro" ? textura : null,
      emissiveIntensity: face.brilho || face.tipo === "letreiro" ? 0.38 : 0,
    });
  }

  descartarComposicoes(estande) {
    (estande.faces || []).forEach((face) => {
      if (face.composta) {
        face.composta.textura.dispose();
        face.composta.material.dispose();
        face.composta = null;
      }
    });
  }

  /** Veste o estande com o adesivo e a cor escolhidos. */
  async vestir(estande) {
    const T = this.T;
    const opcao = estande.opcao;
    estande.matCorpo.color.set(estande.cor);
    if (!opcao || !estande.faces.length) return;
    const vez = (estande.vez = (estande.vez || 0) + 1);

    if (opcao.tipo === "pronto") {
      estande.telaFixa = Boolean(opcao.tela);
      const tela = opcao.tela ? this.texturaDe(opcao.tela) : null;
      await Promise.all(estande.faces.map(async (face) => {
        const url = opcao.pasta + (ARQUIVO_DA_FACE[face.id] || face.id) + ".webp";
        const textura = await this.texturaDe(url);
        if (vez !== estande.vez || !textura) return;
        face.malha.material = this.mat(`adesivo:${url}`, () => this.materialDeAdesivo(textura, face));
      }));
      this.descartarComposicoes(estande);
      if (tela && estande.tv) {
        const textura = await tela;
        if (textura && vez === estande.vez) {
          estande.tv.material = this.mat(`tv:${opcao.tela}`, () => new T.MeshBasicMaterial({ map: textura, toneMapped: false }));
        }
      }
      return;
    }

    estande.telaFixa = false;
    if (estande.tv && estande.materialFoto) estande.tv.material = estande.materialFoto;
    const [arte, logo] = await Promise.all([this.imagemDe(opcao.arte), this.imagemDe(opcao.logo)]);
    if (vez !== estande.vez) return;
    const escolhido = this.estandes.indexOf(estande) === this.selecionado || this.unico;
    const resolucao = escolhido ? (this.celular ? 512 : 768) : (this.celular ? 256 : 320);
    estande.faces.forEach((face) => {
      const canvas = pintarAdesivo(face, { cor: estande.cor, arte, logo, resolucao });
      const textura = new T.CanvasTexture(canvas);
      textura.colorSpace = T.SRGBColorSpace;
      textura.anisotropy = Math.min(4, this.renderer.capabilities.getMaxAnisotropy());
      const material = this.materialDeAdesivo(textura, face);
      if (face.composta) {
        face.composta.textura.dispose();
        face.composta.material.dispose();
      }
      face.composta = { textura, material };
      face.malha.material = material;
    });
  }

  /** Troca a roupa do estande escolhido (pela ficha). */
  trocarRoupa(estande, { adesivo, cor }) {
    const variantes = estande.brinquedo.variantes;
    if (adesivo) estande.opcao = variantes.adesivos.find((x) => x.id === adesivo) || estande.opcao;
    if (cor) estande.cor = (variantes.cores.find((c) => c.id === cor) || { hex: estande.cor }).hex;
    estande.corId = cor || estande.corId;
    this.vestir(estande);
    this.mostrarRoupa(estande);
  }

  /** Os botões de cor e de adesivo na ficha. */
  mostrarRoupa(estande) {
    const caixa = this.ficha.querySelector("[data-ficha-roupa]");
    if (!caixa) return;
    const variantes = estande.brinquedo.variantes;
    if (!variantes || !variantes.adesivos.length) {
      caixa.hidden = true;
      return;
    }
    caixa.hidden = false;
    const cores = caixa.querySelector("[data-ficha-cores]");
    const adesivos = caixa.querySelector("[data-ficha-adesivos]");
    const pronto = estande.opcao && estande.opcao.tipo === "pronto";
    caixa.querySelector("[data-ficha-cores-grupo]").hidden = pronto;
    cores.innerHTML = "";
    variantes.cores.forEach((c) => {
      const botao = document.createElement("button");
      botao.type = "button";
      botao.className = "arena-cor";
      botao.style.setProperty("--cor", c.hex);
      botao.title = c.nome;
      botao.setAttribute("aria-label", "Gabinete " + c.nome);
      botao.setAttribute("aria-pressed", c.hex.toLowerCase() === String(estande.cor).toLowerCase() ? "true" : "false");
      botao.addEventListener("click", () => this.trocarRoupa(estande, { cor: c.id }));
      cores.append(botao);
    });
    adesivos.innerHTML = "";
    variantes.adesivos.forEach((opcao) => {
      const botao = document.createElement("button");
      botao.type = "button";
      botao.className = "arena-adesivo";
      botao.setAttribute("aria-pressed", estande.opcao && opcao.id === estande.opcao.id ? "true" : "false");
      const mini = document.createElement("img");
      mini.src = opcao.miniatura;
      mini.alt = "";
      mini.loading = "lazy";
      const nome = document.createElement("span");
      nome.textContent = opcao.nome;
      botao.append(mini, nome);
      botao.addEventListener("click", () => this.trocarRoupa(estande, { adesivo: opcao.id }));
      adesivos.append(botao);
    });
    const pedido = this.ficha.querySelector("[data-ficha-whatsapp-roupa]");
    if (pedido) {
      const cor = variantes.cores.find((c) => c.hex.toLowerCase() === String(estande.cor).toLowerCase());
      const detalhe = estande.opcao && estande.opcao.tipo === "pronto"
        ? `adesivagem ${estande.opcao.nome}`
        : `gabinete ${cor ? cor.nome.toLowerCase() : ""} com adesivo ${estande.opcao ? estande.opcao.nome : ""}`;
      const texto = `Olá! Vi o ${estande.brinquedo.nome} em 3D no site e quero assim: ${detalhe}.`;
      pedido.href = "https://wa.me/5511960563135?text=" + encodeURIComponent(texto);
    }
    const legenda = caixa.querySelector("[data-ficha-roupa-legenda]");
    if (legenda) {
      const cor = variantes.cores.find((c) => c.hex.toLowerCase() === String(estande.cor).toLowerCase());
      legenda.textContent = pronto
        ? `${estande.opcao.nome}: os 12 adesivos do gabinete de verdade.`
        : `${estande.opcao ? estande.opcao.nome : ""}${cor ? " · gabinete " + cor.nome.toLowerCase() : ""}`;
    }
  }

  /* ---------- seleção ---------- */
  selecionar(indice, { voar = true } = {}) {
    if (indice < 0 || indice >= this.estandes.length) return;
    this.selecionado = indice;
    const estande = this.estandes[indice];
    this.estandes.forEach((e, i) => {
      e.aro.material = this.luz(e.brinquedo.cor, i === indice ? 5 : 2.2);
    });
    if (voar) this.camera3d.olharPara(estande);
    const alvo = new this.T.Vector3();
    estande.grupo.getWorldPosition(alvo);
    this.foco.position.set(alvo.x * 0.55, estande.h + 6, alvo.z * 0.55);
    this.foco.target.position.copy(alvo);
    this.foco.intensity = 2.2;
    this.mostrarFicha(estande.brinquedo);
    this.mostrarRoupa(estande);
    // O escolhido ganha os adesivos em resolução maior (de perto aparece).
    if (estande.opcao && estande.opcao.tipo === "arte") this.vestir(estande);
    this.marcarLista();
  }

  soltarSelecao() {
    if (this.unico) {
      this.camera3d.olharPara(this.estandes[0]);
      return;
    }
    this.selecionado = -1;
    this.estandes.forEach((e) => { e.aro.material = this.luz(e.brinquedo.cor, 2.2); });
    this.foco.intensity = 0;
    this.ficha.hidden = true;
    this.camera3d.visaoGeral();
    this.marcarLista();
  }

  proximo(passo) {
    if (this.unico) return;
    const total = this.visiveis.length;
    if (!total) return;
    const atualGlobal = this.selecionado >= 0
      ? this.pagina * this.limite + this.selecionado
      : (passo > 0 ? this.pagina * this.limite - 1 : this.pagina * this.limite);
    this.irPara((atualGlobal + passo + total) % total);
  }

  /** Vai a um brinquedo pela posição na lista filtrada, trocando de "rodada" se preciso. */
  irPara(posicao) {
    const pagina = Math.floor(posicao / this.limite);
    if (pagina !== this.pagina) {
      this.pagina = pagina;
      this.montar();
    }
    this.selecionar(posicao % this.limite);
  }

  /* ---------- ficha ---------- */
  mostrarFicha(b) {
    const f = this.ficha;
    f.hidden = false;
    // A ficha da página do produto só tem a roupa: o resto já está na página.
    if (!f.querySelector("[data-ficha-nome]")) return;
    f.querySelector("[data-ficha-nome]").textContent = b.nome;
    f.querySelector("[data-ficha-categoria]").textContent = b.categorias.join(" · ") || "Brinquedo";
    f.querySelector("[data-ficha-desc]").textContent = b.descricao || "";
    const linhas = { medidas: b.medidas_texto, voltagem: b.voltagem, preco: b.preco };
    Object.entries(linhas).forEach(([nome, valor]) => {
      f.querySelector(`[data-ficha-linha="${nome}"]`).hidden = !valor;
      f.querySelector(`[data-ficha-${nome}]`).textContent = valor || "";
    });

    const foto = f.querySelector("[data-ficha-foto]");
    const lados = f.querySelector("[data-ficha-lados]");
    const NOMES = { perfil: "Frente", lado_direito: "Lado direito", verso: "Verso", lado_esquerdo: "Lado esquerdo" };
    lados.innerHTML = "";
    const trocar = (url, botao) => {
      foto.src = url;
      foto.alt = b.nome;
      lados.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", x === botao ? "true" : "false"));
    };
    if (b.fotos.length) trocar(b.fotos[0].url, null);
    if (b.fotos.length > 1) {
      b.fotos.forEach((item, i) => {
        const botao = document.createElement("button");
        botao.type = "button";
        botao.setAttribute("aria-label", NOMES[item.tipo] || "Foto");
        botao.setAttribute("aria-pressed", i === 0 ? "true" : "false");
        const mini = document.createElement("img");
        mini.src = item.url;
        mini.alt = "";
        mini.loading = "lazy";
        botao.append(mini);
        botao.addEventListener("click", () => trocar(item.url, botao));
        lados.append(botao);
      });
    }

    const detalhe = f.querySelector("[data-ficha-detalhe]");
    detalhe.hidden = !b.url;
    if (b.url) detalhe.href = b.url;
    const texto = `Olá! Vi o ${b.nome} na Arena 3D do site da Lazer & Sport e quero um orçamento.`;
    const whatsapp = f.querySelector("[data-ficha-whatsapp]");
    whatsapp.href = whatsapp.href.split("?")[0] + "?text=" + encodeURIComponent(texto);
    // A prévia do jogo desta máquina, no simulador.
    const jogar = f.querySelector("[data-ficha-jogar]");
    jogar.hidden = !b.jogo;
    if (b.jogo) jogar.href = `${jogar.dataset.base}${b.jogo}/`;
  }

  marcarLista() {
    const atual = this.selecionado >= 0 ? this.estandes[this.selecionado].brinquedo.indiceOriginal : -1;
    this.palco.parentElement.querySelectorAll("[data-arena-indice]").forEach((item) => {
      item.classList.toggle("ativo", Number(item.dataset.arenaIndice) === atual);
    });
  }

  filtrar(categoria) {
    this.visiveis = categoria ? this.todos.filter((b) => b.categorias.includes(categoria)) : this.todos.slice();
    this.pagina = 0;
    const visiveis = new Set(this.visiveis.map((b) => b.indiceOriginal));
    this.palco.parentElement.querySelectorAll("[data-arena-indice]").forEach((item) => {
      item.parentElement.hidden = !visiveis.has(Number(item.dataset.arenaIndice));
    });
    this.ficha.hidden = true;
    this.montar();
  }

  /* ---------- ligar à página ---------- */
  ligar() {
    const palco = this.palco;
    this.ficha = palco.querySelector("[data-arena-ficha]");
    this.aviso = palco.querySelector("[data-arena-aviso]");
    this.controles = palco.querySelector("[data-arena-controles]");
    this.filtros = palco.querySelector("[data-arena-filtros]");

    this.montar();
    this.redimensionar();
    new ResizeObserver(() => this.redimensionar()).observe(palco);

    this.camera3d.ligarEventos(this.canvas);

    if (this.controles) this.controles.hidden = false;
    if (this.filtros) this.filtros.hidden = this.filtros.querySelectorAll("button").length < 3;
    this.aviso.classList.add("sumiu");

    if (this.controles) {
      this.controles.addEventListener("click", (evento) => {
        const botao = evento.target.closest("[data-arena-acao]");
        if (botao) this.acao(botao.dataset.arenaAcao, botao);
      });
    }
    this.ficha.addEventListener("click", (evento) => {
      if (evento.target.closest("[data-arena-acao='fechar-ficha']")) this.soltarSelecao();
    });
    if (this.filtros) this.filtros.addEventListener("click", (evento) => {
      const botao = evento.target.closest("[data-arena-categoria]");
      if (!botao) return;
      this.filtros.querySelectorAll("button").forEach((b) => {
        const ativo = b === botao;
        b.classList.toggle("ativo", ativo);
        b.setAttribute("aria-pressed", ativo ? "true" : "false");
      });
      this.filtrar(botao.dataset.arenaCategoria);
    });

    // A lista abaixo do palco vira controle remoto da arena.
    palco.parentElement.querySelectorAll("[data-arena-indice]").forEach((item) => {
      item.addEventListener("click", (evento) => {
        if (evento.metaKey || evento.ctrlKey || evento.shiftKey) return;
        const original = Number(item.dataset.arenaIndice);
        const posicao = this.visiveis.findIndex((b) => b.indiceOriginal === original);
        if (posicao < 0) return;
        evento.preventDefault();
        this.irPara(posicao);
        palco.scrollIntoView({ behavior: this.reduzido ? "auto" : "smooth", block: "center" });
      });
    });

    palco.addEventListener("keydown", (evento) => {
      if (evento.key === "ArrowRight") { this.proximo(1); evento.preventDefault(); }
      else if (evento.key === "ArrowLeft") { this.proximo(-1); evento.preventDefault(); }
      else if (evento.key === "Escape" && this.selecionado >= 0) this.soltarSelecao();
    });
    this.canvas.tabIndex = 0;

    // Fora da tela ou com a aba escondida: não desenha nada.
    new IntersectionObserver((entradas) => {
      this.visivel = entradas.some((e) => e.isIntersecting);
      this.acordar();
    }).observe(palco);
    document.addEventListener("visibilitychange", () => this.acordar());

    this.visivel = true;
    this.acordar();
  }

  acao(nome, botao) {
    this.ocioso = 0;
    if (nome === "proximo") this.proximo(1);
    else if (nome === "anterior") this.proximo(-1);
    else if (nome === "visao") this.soltarSelecao();
    else if (nome === "tour") {
      this.tour = !this.tour;
      this.tourTempo = 0;
      botao.setAttribute("aria-pressed", this.tour ? "true" : "false");
      botao.querySelector("i").className = this.tour ? "fa-solid fa-pause" : "fa-solid fa-play";
      if (this.tour) this.proximo(1);
    } else if (nome === "tela-cheia") {
      if (document.fullscreenElement) document.exitFullscreen();
      else if (this.palco.requestFullscreen) this.palco.requestFullscreen().catch(() => {});
    }
  }

  redimensionar() {
    const r = this.palco.getBoundingClientRect();
    if (!r.width || !r.height) return;
    this.renderer.setSize(r.width, r.height, false);
    this.camera.aspect = r.width / r.height;
    // Tela em pé (celular) precisa de lente mais aberta para caber a roda.
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
      const dt = Math.min(0.05, (agora - this.relogioAnterior) / 1000);
      this.relogioAnterior = agora;
      this.quadro(dt);
    };
    requestAnimationFrame(passo);
  }

  quadro(dt) {
    // Com um jogo aberto por cima, a arena não desenha: o celular precisa
    // de todo o fôlego para o jogo, e a cena nem aparece atrás do console.
    this.relogio += dt;
    this.ocioso += dt;
    const t = this.relogio;

    if (this.tour) {
      this.tourTempo += dt;
      if (this.tourTempo > 6) {
        this.tourTempo = 0;
        this.proximo(1);
      }
    }

    if (!this.reduzido) {
      if (this.alvoMarca) this.alvoMarca.rotation.y = t * 0.6;
      this.estrelas.rotation.y = t * 0.012;
      this.luzesCor.forEach((l, i) => l.position.set(Math.sin(t * 0.4 + i * PI) * 7, 7, Math.cos(t * 0.4 + i * PI) * 7));
      if (this.pilares) {
        this.pilares.children.forEach((p) => {
          if (p.userData.fase !== undefined) p.scale.y = 5.5 * (0.75 + 0.25 * Math.sin(t * 2 + p.userData.fase * 0.7));
        });
      }
    }

    this.estandes.forEach((estande, i) => {
      // O escolhido gira devagar no pedestal, para mostrar todos os lados.
      if (i === this.selecionado && !this.reduzido) estande.prato.rotation.y += dt * 0.5;
      else estande.prato.rotation.y *= Math.max(0, 1 - dt * 3);
      if (estande.animar && !this.reduzido) estande.animar(t, dt);
    });

    this.camera3d.atualizar(dt);
    this.enquadrar(dt);
    this.renderer.render(this.cena, this.camera);
  }

  /**
   * Com a ficha aberta, o centro da imagem anda para o lado livre do palco:
   * à esquerda no computador (a ficha fica à direita), para cima no celular
   * (a ficha sobe da base). Sem isto o brinquedo escolhido ficava atrás dela.
   */
  enquadrar(dt) {
    let x = 0;
    let y = 0;
    if (this.ficha && !this.ficha.hidden) {
      const palco = this.palco.getBoundingClientRect();
      const ficha = this.ficha.getBoundingClientRect();
      if (ficha.width < palco.width * 0.7) x = ficha.width / 2;
      else y = Math.min(ficha.height, palco.height * 0.7) / 2;
    }
    const k = 1 - Math.exp(-dt * 5);
    this.deslocamento.x += (x - this.deslocamento.x) * k;
    this.deslocamento.y += (y - this.deslocamento.y) * k;
    const { width: w, height: h } = this.renderer.getSize(this.tamanho || (this.tamanho = new this.T.Vector2()));
    if (Math.abs(this.deslocamento.x) < 0.5 && Math.abs(this.deslocamento.y) < 0.5) {
      if (this.camera.view && this.camera.view.enabled) this.camera.clearViewOffset();
      return;
    }
    this.camera.setViewOffset(w, h, this.deslocamento.x, this.deslocamento.y, w, h);
  }

  /** Qual estande está sob o ponteiro (coordenadas de tela). */
  escolher(x, y) {
    const r = this.canvas.getBoundingClientRect();
    this.ponteiro.set(((x - r.left) / r.width) * 2 - 1, -((y - r.top) / r.height) * 2 + 1);
    this.raycaster.setFromCamera(this.ponteiro, this.camera);
    const acerto = this.raycaster.intersectObjects(this.estandes.map((e) => e.grupo), true)[0];
    return acerto ? this.estandes.indexOf(acerto.object.userData.estande) : -1;
  }
}

/* ======================================================================
   A CÂMERA — órbita própria, com voo suave até o brinquedo escolhido
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
    this.alvoDesejado.set(0, 1.2, 0);
    // Em pé, a roda inteira só cabe de mais longe.
    const folga = this.arena.camera.aspect < 0.8 ? 1.5 : 1;
    this.raioDesejado = (raioArena * 1.75 + 7) * folga;
    this.phiDesejado = 1.0;
    if (entrada && !this.arena.reduzido) {
      // Entrada de cinema: vem de longe e de cima.
      this.raio = this.raioDesejado * 1.8;
      this.phi = 0.55;
    }
  }

  olharPara(estande) {
    const posicao = new this.arena.T.Vector3();
    estande.grupo.getWorldPosition(posicao);
    this.alvoDesejado.set(posicao.x, estande.alturaP + estande.h * 0.5, posicao.z);
    const tamanho = Math.max(estande.h, estande.w, estande.d, 1.6);
    const folga = this.arena.camera.aspect < 0.8 ? 1.45 : 1;
    this.raioDesejado = this.arena.unico
      ? Math.max(3.2, tamanho * 1.5 + 1.1) * folga
      : Math.min(18, Math.max(4.2, tamanho * 2.1 + 2.2) * folga);
    this.phiDesejado = 1.2;
    // A câmera fica do lado do centro, de frente para o brinquedo.
    const thetaFrente = Math.atan2(-posicao.x, -posicao.z);
    let delta = thetaFrente - this.thetaDesejado;
    delta = Math.atan2(Math.sin(delta), Math.cos(delta));
    this.thetaDesejado += delta;
  }

  ligarEventos(canvas) {
    const arena = this.arena;
    let inicio = null;
    let distanciaPinca = 0;

    canvas.addEventListener("pointerdown", (evento) => {
      try { canvas.setPointerCapture(evento.pointerId); } catch (erro) { /* sem captura */ }
      this.ponteiros.set(evento.pointerId, { x: evento.clientX, y: evento.clientY });
      inicio = { x: evento.clientX, y: evento.clientY, t: performance.now() };
      arena.ocioso = 0;
      canvas.classList.add("arrastando");
      if (this.ponteiros.size === 2) {
        const [a, b] = [...this.ponteiros.values()];
        distanciaPinca = Math.hypot(a.x - b.x, a.y - b.y);
      }
    });

    canvas.addEventListener("pointermove", (evento) => {
      const anterior = this.ponteiros.get(evento.pointerId);
      if (!anterior) {
        // Só passando por cima: o cursor avisa que dá para clicar.
        if (evento.pointerType === "mouse") {
          canvas.classList.toggle("sobre-brinquedo", arena.escolher(evento.clientX, evento.clientY) >= 0);
        }
        return;
      }
      const dx = evento.clientX - anterior.x;
      const dy = evento.clientY - anterior.y;
      this.ponteiros.set(evento.pointerId, { x: evento.clientX, y: evento.clientY });
      arena.ocioso = 0;

      if (this.ponteiros.size === 2) {
        const [a, b] = [...this.ponteiros.values()];
        const distancia = Math.hypot(a.x - b.x, a.y - b.y);
        if (distanciaPinca > 0) this.raioDesejado *= distanciaPinca / Math.max(1, distancia);
        distanciaPinca = distancia;
        this.limitar();
        return;
      }
      this.thetaDesejado -= dx * 0.006;
      this.phiDesejado -= dy * 0.005;
      this.limitar();
    });

    const soltar = (evento) => {
      this.ponteiros.delete(evento.pointerId);
      canvas.classList.remove("arrastando");
      if (this.ponteiros.size < 2) distanciaPinca = 0;
      if (!inicio) return;
      const andou = Math.hypot(evento.clientX - inicio.x, evento.clientY - inicio.y);
      const rapido = performance.now() - inicio.t < 450;
      inicio = null;
      if (andou < 8 && rapido && evento.type === "pointerup") {
        const indice = arena.escolher(evento.clientX, evento.clientY);
        if (indice >= 0) arena.selecionar(indice);
      }
    };
    canvas.addEventListener("pointerup", soltar);
    canvas.addEventListener("pointercancel", soltar);

    canvas.addEventListener("wheel", (evento) => {
      evento.preventDefault();
      arena.ocioso = 0;
      this.raioDesejado *= Math.exp(evento.deltaY * 0.0012);
      this.limitar();
    }, { passive: false });
  }

  limitar() {
    this.phiDesejado = Math.min(1.42, Math.max(0.32, this.phiDesejado));
    const maximo = (this.arena.raio || 8) * 3.6 + 14;
    this.raioDesejado = Math.min(maximo, Math.max(2.6, this.raioDesejado));
  }

  atualizar(dt) {
    const arena = this.arena;
    // Ninguém mexendo há um tempo: a câmera passeia sozinha.
    if (!arena.reduzido && arena.ocioso > 3.5 && this.ponteiros.size === 0) {
      this.thetaDesejado += dt * (arena.selecionado >= 0 ? 0.08 : 0.1);
    }
    const k = 1 - Math.exp(-dt * (arena.reduzido ? 20 : 4.2));
    this.alvo.lerp(this.alvoDesejado, k);
    this.theta += (this.thetaDesejado - this.theta) * k;
    this.phi += (this.phiDesejado - this.phi) * k;
    this.raio += (this.raioDesejado - this.raio) * k;

    const s = Math.sin(this.phi);
    arena.camera.position.set(
      this.alvo.x + this.raio * s * Math.sin(this.theta),
      Math.max(0.6, this.alvo.y + this.raio * Math.cos(this.phi)),
      this.alvo.z + this.raio * s * Math.cos(this.theta),
    );
    arena.camera.lookAt(this.alvo);
  }
}

/* ======================================================================
   ADESIVOS — o mesmo gabinete em várias roupas

   Duas espécies de adesivo:

   PRONTO: os 12 adesivos de verdade do gabinete do Strike Kids, um
   arquivo por face, gerados pela ferramenta do próprio jogo. Os furos
   (tela, START, ficha, retorno das bolas) vêm vazados na imagem.

   ARTE: montado aqui, no canvas, com a arte do jogo da máquina sobre a
   cor escolhida -- é assim que o Dragon Bowling aparece rosa, vermelho,
   amarelo ou preto sem um arquivo para cada combinação.
   ====================================================================== */
const ARQUIVO_DA_FACE = {
  letreiro_frente: "01_letreiro_frente",
  letreiro_esq: "02_letreiro_lateral_esquerda",
  letreiro_dir: "02_letreiro_lateral_direita",
  letreiro_tras: "02_letreiro_traseira",
  torre_frente: "03_torre_frente",
  torre_esq: "04_torre_lateral_esquerda",
  torre_dir: "04_torre_lateral_direita",
  torre_tras: "05_torre_traseira",
  pista_esq: "06_pista_lateral_esquerda",
  pista_dir: "06_pista_lateral_direita",
  pista_frente: "07_pista_frente",
  piso: "08_pista_piso",
};

function rgb(hex) {
  const n = parseInt(String(hex).replace("#", ""), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function misturar(hex, alvo, t) {
  const a = rgb(hex);
  const b = rgb(alvo);
  return `rgb(${a.map((v, i) => Math.round(v + (b[i] - v) * t)).join(",")})`;
}

function claro(hex) {
  const [r, g, b] = rgb(hex);
  return (r * 299 + g * 587 + b * 114) / 1000 > 170;
}

/** Cabe a imagem inteira dentro da caixa, centrada. */
function encaixar(g, img, x, y, w, h, arredondar = 0) {
  if (!img) return;
  const escala = Math.min(w / img.width, h / img.height);
  const iw = img.width * escala;
  const ih = img.height * escala;
  const ix = x + (w - iw) / 2;
  const iy = y + (h - ih) / 2;
  g.save();
  if (arredondar) {
    g.beginPath();
    g.roundRect(ix, iy, iw, ih, arredondar);
    g.clip();
  }
  g.drawImage(img, ix, iy, iw, ih);
  g.restore();
  return { x: ix, y: iy, w: iw, h: ih };
}

function fundoDeAdesivo(g, W, H, cor, semente) {
  const fundo = g.createLinearGradient(0, 0, 0, H);
  fundo.addColorStop(0, misturar(cor, "#ffffff", 0.28));
  fundo.addColorStop(0.55, cor);
  fundo.addColorStop(1, misturar(cor, "#000000", 0.5));
  g.fillStyle = fundo;
  g.fillRect(0, 0, W, H);

  // Raios de sol saindo do alto, como nos adesivos da casa.
  g.save();
  g.translate(W / 2, H * 0.28);
  g.fillStyle = claro(cor) ? "rgba(0,0,0,.06)" : "rgba(255,255,255,.09)";
  for (let i = 0; i < 18; i++) {
    g.rotate((Math.PI * 2) / 18);
    g.beginPath();
    g.moveTo(0, 0);
    g.lineTo(Math.max(W, H) * 1.5, -Math.max(W, H) * 0.09);
    g.lineTo(Math.max(W, H) * 1.5, Math.max(W, H) * 0.09);
    g.closePath();
    g.fill();
  }
  g.restore();

  // Estrelinhas e confete, sempre no mesmo lugar para a mesma face.
  let s = semente;
  const aleatorio = () => ((s = (s * 9301 + 49297) % 233280) / 233280);
  for (let i = 0; i < 26; i++) {
    g.fillStyle = ["#ffd23f", "#ffffff", "#3fd0ff", "#ff3d71"][i % 4];
    g.globalAlpha = 0.45;
    const r = Math.max(W, H) * (0.004 + aleatorio() * 0.008);
    g.beginPath();
    g.arc(aleatorio() * W, aleatorio() * H, r, 0, Math.PI * 2);
    g.fill();
  }
  g.globalAlpha = 1;
}

function marcaDaCasa(g, W, H, y, tamanho) {
  g.save();
  g.font = `900 ${tamanho}px Poppins, Manrope, sans-serif`;
  g.textAlign = "center";
  g.textBaseline = "middle";
  const largura = g.measureText("LAZER & SPORT").width + tamanho * 1.4;
  g.fillStyle = "rgba(4, 10, 28, .78)";
  g.beginPath();
  g.roundRect(W / 2 - largura / 2, y - tamanho * 0.85, largura, tamanho * 1.7, tamanho * 0.85);
  g.fill();
  g.fillStyle = "#ffffff";
  g.fillText("LAZER & SPORT", W / 2, y + tamanho * 0.04);
  g.restore();
}

function pintarAdesivo(face, { cor, arte, logo, resolucao }) {
  const canvas = document.createElement("canvas");
  const proporcao = face.w / face.h;
  canvas.width = Math.round(proporcao >= 1 ? resolucao : resolucao * proporcao);
  canvas.height = Math.round(proporcao >= 1 ? resolucao / proporcao : resolucao);
  const g = canvas.getContext("2d");
  const W = canvas.width;
  const H = canvas.height;
  const menor = Math.min(W, H);
  const semente = face.id.length * 97 + Math.round(face.w * 100);

  if (face.tipo === "piso") {
    // Pista de madeira com as flechas de mira.
    const madeira = g.createLinearGradient(0, 0, W, 0);
    madeira.addColorStop(0, "#c98f55");
    madeira.addColorStop(0.5, "#e7b77b");
    madeira.addColorStop(1, "#c98f55");
    g.fillStyle = madeira;
    g.fillRect(0, 0, W, H);
    g.strokeStyle = "rgba(90, 50, 20, .25)";
    for (let x = 0; x < W; x += W / 14) {
      g.beginPath();
      g.moveTo(x, 0);
      g.lineTo(x, H);
      g.stroke();
    }
    g.fillStyle = cor;
    for (let i = 0; i < 7; i++) {
      const x = W * (0.16 + i * 0.113);
      const y = H * (0.36 + Math.abs(3 - i) * 0.025);
      g.beginPath();
      g.moveTo(x, y - W * 0.04);
      g.lineTo(x - W * 0.025, y + W * 0.02);
      g.lineTo(x + W * 0.025, y + W * 0.02);
      g.fill();
    }
    g.fillStyle = "#b3122a";
    g.fillRect(0, H * 0.94, W, H * 0.008);
    return canvas;
  }

  fundoDeAdesivo(g, W, H, cor, semente);

  if (face.tipo === "letreiro") {
    encaixar(g, logo, W * 0.06, H * 0.08, W * 0.88, H * 0.84, menor * 0.08);
  } else if (face.tipo === "torre_frente") {
    encaixar(g, logo, W * 0.12, H * 0.015, W * 0.76, H * 0.17, menor * 0.04);
    marcaDaCasa(g, W, H, H * 0.9, menor * 0.07);
    // A janela da TV: vazada, para a tela de trás aparecer.
    const j = face.janela;
    g.save();
    g.lineWidth = menor * 0.03;
    g.strokeStyle = "#ffd23f";
    g.strokeRect(j.x * W - g.lineWidth / 2, j.y * H - g.lineWidth / 2, j.w * W + g.lineWidth, j.h * H + g.lineWidth);
    g.globalCompositeOperation = "destination-out";
    g.fillRect(j.x * W, j.y * H, j.w * W, j.h * H);
    g.restore();
  } else if (face.tipo === "pista_frente") {
    g.save();
    g.fillStyle = "#ffffff";
    g.font = `900 ${H * 0.12}px Poppins, sans-serif`;
    g.textAlign = "center";
    g.fillText("ROLE A BOLA!", W / 2, H * 0.2);
    // START, ficha e o retorno das bolas, nos lugares da planta.
    g.fillStyle = "#e3192d";
    g.strokeStyle = "#ffffff";
    g.lineWidth = H * 0.02;
    g.beginPath();
    g.arc(W * (130 / 800), H * (1 - 330 / 520), H * 0.09, 0, Math.PI * 2);
    g.fill();
    g.stroke();
    g.fillStyle = "#0b1020";
    g.beginPath();
    g.roundRect(W * (615 / 800), H * (1 - 385 / 520), W * (110 / 800), H * (110 / 520), H * 0.02);
    g.fill();
    g.stroke();
    g.beginPath();
    g.roundRect(W * (250 / 800), H * (1 - 200 / 520), W * (300 / 800), H * (160 / 520), H * 0.03);
    g.fill();
    g.stroke();
    g.restore();
  } else {
    // Laterais, traseiras e frentes: a arte do jogo com a marca.
    if (W / H > 2.2) {
      encaixar(g, arte, W * 0.03, H * 0.08, W * 0.36, H * 0.84, menor * 0.06);
      encaixar(g, logo, W * 0.42, H * 0.1, W * 0.3, H * 0.62, menor * 0.08);
      marcaDaCasa(g, W, H, H * 0.86, menor * 0.08);
    } else if (H / W > 1.6) {
      encaixar(g, logo, W * 0.08, H * 0.04, W * 0.84, H * 0.2, menor * 0.06);
      encaixar(g, arte, W * 0.06, H * 0.27, W * 0.88, H * 0.58, menor * 0.05);
      marcaDaCasa(g, W, H, H * 0.93, menor * 0.075);
    } else {
      encaixar(g, arte || logo, W * 0.08, H * 0.08, W * 0.84, H * 0.7, menor * 0.06);
      marcaDaCasa(g, W, H, H * 0.9, menor * 0.07);
    }
  }

  // Borda fina, como o vinil laminado.
  g.strokeStyle = "rgba(255,255,255,.35)";
  g.lineWidth = Math.max(2, menor * 0.012);
  g.strokeRect(0, 0, W, H);
  return canvas;
}

/* ======================================================================
   O OBJETO 3D DE CADA MÁQUINA

   Só entra aqui máquina com planta de verdade. Hoje é o gabinete de
   boliche (Strike Kids e Dragon Bowling). As outras ficam com as fotos
   reais na vitrine da página até os planos de corte delas chegarem --
   gabinete inventado não vira 3D.
   ====================================================================== */
const MODELOS = {
  /**
   * O gabinete de boliche como a planta do Strike Kids o descreve (mm):
   * pista 2600 × 800 com laterais de 520 e piso a 450, torre de 600 de
   * fundo e 2000 de altura, letreiro 800 × 380 × 300 em cima e a TV de
   * 43" em pé atrás de uma janela de 535 × 950. As faces e a orientação
   * de cada adesivo são as da maquete do jogo (`gabinete_render.gd`).
   * Medidas diferentes no cadastro esticam o gabinete inteiro junto.
   */
  boliche(a, e, g) {
    const L = 0.8, PC = 2.6, PH = 0.52, PISO = 0.45, PL = 0.7, TP = 0.6, TH = 2.0, LH = 0.38, LP = 0.3;
    const TELA = [0.535, 0.95];
    const TELA_BASE = 0.76;
    const m = new a.T.Group();
    // Na maquete a origem é o canto da torre; aqui é o meio do gabinete.
    m.position.set(-L / 2 * (e.w / L), 0, -((PC - TP) / 2) * (e.d / (PC + TP)));
    m.scale.set(e.w / L, e.h / (TH + LH), e.d / (PC + TP));
    g.add(m);
    const escuro = a.escuro();
    const p = (w, h, centro, normal, direita) => a.placa(m, w, h, centro, normal, direita);
    const adesivo = (id, tipo, w, h, centro, normal, direita, extras) => a.adesivo(e, m, id, tipo, w, h, centro, normal, direita, extras);
    const e0 = 0.0015;

    // Torre: o corpo fica atrás da tela; a frente é o adesivo com os furos.
    a.caixa(m, L - 0.004, TH, TP - 0.03, escuro, L / 2, TH / 2, -(TP + 0.03) / 2);
    a.caixa(m, L - 0.004, PH, 0.03, escuro, L / 2, PH / 2, -0.015);
    const janela = {
      x: (1 - TELA[0] / L) / 2,
      y: 1 - (TELA_BASE + TELA[1] - PH) / (TH - PH),
      w: TELA[0] / L,
      h: TELA[1] / (TH - PH),
    };
    adesivo("torre_frente", "torre_frente", L, TH - PH, [L / 2, (PH + TH) / 2, e0], [0, 0, 1], [1, 0, 0], { janela });
    adesivo("torre_esq", "lateral", TP, TH, [-e0, TH / 2, -TP / 2], [-1, 0, 0], [0, 0, 1]);
    adesivo("torre_dir", "lateral", TP, TH, [L + e0, TH / 2, -TP / 2], [1, 0, 0], [0, 0, -1]);
    adesivo("torre_tras", "lateral", L, TH, [L / 2, TH / 2, -TP - e0], [0, 0, -1], [-1, 0, 0]);
    // A TV atrás da janela.
    const tv = p(TELA[0] + 0.02, TELA[1] + 0.02, [L / 2, TELA_BASE + TELA[1] / 2, -0.012], [0, 0, 1], [1, 0, 0]);
    tv.material = a.luz("#2f8bff", 1.2);
    e.tv = tv;

    // Letreiro luminoso em cima da torre.
    a.caixa(m, L - 0.004, LH, LP - 0.004, escuro, L / 2, TH + LH / 2, -LP / 2);
    adesivo("letreiro_frente", "letreiro", L, LH, [L / 2, TH + LH / 2, e0], [0, 0, 1], [1, 0, 0], { brilho: true });
    adesivo("letreiro_esq", "letreiro", LP, LH, [-e0, TH + LH / 2, -LP / 2], [-1, 0, 0], [0, 0, 1], { brilho: true });
    adesivo("letreiro_dir", "letreiro", LP, LH, [L + e0, TH + LH / 2, -LP / 2], [1, 0, 0], [0, 0, -1], { brilho: true });
    adesivo("letreiro_tras", "letreiro", L, LH, [L / 2, TH + LH / 2, -LP - e0], [0, 0, -1], [-1, 0, 0], { brilho: true });

    // Pista: o corpo para antes da frente, onde fica o nicho do retorno das bolas.
    const zf = PC - 0.26;
    a.caixa(m, L - 0.04, PISO - 0.01, zf - 0.01, escuro, L / 2, (PISO - 0.01) / 2, (zf + 0.01) / 2);
    a.caixa(m, L - 0.04, PH - 0.01, 0.24, escuro, L / 2, (PH - 0.01) / 2, PC - 0.13);
    adesivo("pista_esq", "lateral", PC, PH, [-e0, PH / 2, PC / 2], [-1, 0, 0], [0, 0, 1]);
    adesivo("pista_dir", "lateral", PC, PH, [L + e0, PH / 2, PC / 2], [1, 0, 0], [0, 0, -1]);
    adesivo("pista_frente", "pista_frente", L, PH, [L / 2, PH / 2, PC + e0], [0, 0, 1], [1, 0, 0]);
    adesivo("piso", "piso", PL, PC, [L / 2, PISO, PC / 2], [0, 1, 0], [1, 0, 0]);
    const friso = a.metal("#e8edf5");
    [0.009, L - 0.009].forEach((x) => {
      a.caixa(m, 0.018, PH - PISO, PC, escuro, x, (PH + PISO) / 2, PC / 2);
      a.caixa(m, 0.03, 0.02, PC + 0.01, friso, x, PH + 0.01, PC / 2);
    });
    a.caixa(m, L + 0.01, 0.02, 0.03, friso, L / 2, PH + 0.01, PC - 0.005);
    // Botão START na frente da pista.
    a.cilindro(m, 0.028, 0.03, a.luz("#ff2d3d", 1.6), 0.13, 0.33, PC + 0.012, 24).rotation.x = PI / 2;

    // Os dez pinos no fim da pista, perto da torre.
    const pino = a.geo("pino", () => {
      const pontos = [[0, 0], [0.05, 0], [0.06, 0.06], [0.055, 0.12], [0.03, 0.17], [0.024, 0.2], [0.035, 0.24], [0.02, 0.27], [0, 0.28]]
        .map(([x, y]) => new a.T.Vector2(x, y));
      return new a.T.LatheGeometry(pontos, 16);
    });
    const espaco = 0.12;
    for (let linha = 0; linha < 4; linha++) {
      for (let i = 0; i <= linha; i++) {
        const pinoMalha = new a.T.Mesh(pino, a.plastico("#ffffff"));
        pinoMalha.scale.setScalar(0.9);
        pinoMalha.position.set(L / 2 + (i - linha / 2) * espaco, PISO, 0.55 - linha * espaco * 0.9);
        m.add(pinoMalha);
      }
    }
    const bola = a.esfera(m, 0.075, a.plastico("#2f8bff"), L / 2, PISO + 0.075, PC - 0.4);
    e.animar = (t) => {
      const ciclo = (t * 0.3) % 1;
      bola.position.z = PC - 0.4 - ciclo * (PC - 1.0);
      bola.position.x = L / 2 + Math.sin(ciclo * PI) * 0.12;
      bola.rotation.x = -ciclo * 40;
    };
    e.telas = [tv];
  },

};
