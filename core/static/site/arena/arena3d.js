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

  vidro() {
    return this.mat("vidro", () => new this.T.MeshStandardMaterial({
      color: "#a8d8ff", roughness: 0.05, metalness: 0.2, transparent: true, opacity: 0.16, depthWrite: false,
    }));
  }

  rede(cor = "#ffffff") {
    return this.mat("rede" + cor, () => new this.T.MeshBasicMaterial({ color: cor, wireframe: true, transparent: true, opacity: 0.55 }));
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

  /** Painel que recebe a foto do brinquedo quando ela chegar. */
  tela(pai, w, h, x = 0, y = 0, z = 0) {
    const g = this.geo("plano", () => new this.T.PlaneGeometry(1, 1));
    const m = new this.T.Mesh(g, this.luz("#2f8bff", 1.2));
    m.scale.set(w, h, 1);
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

    const construir = MODELOS[b.desenho] || MODELOS.fliperama;
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

    f.querySelector("[data-ficha-detalhe]").href = b.url;
    const texto = `Olá! Vi o ${b.nome} na Arena 3D do site da Lazer & Sport e quero um orçamento.`;
    const whatsapp = f.querySelector("[data-ficha-whatsapp]");
    whatsapp.href = whatsapp.href.split("?")[0] + "?text=" + encodeURIComponent(texto);
    const jogar = f.querySelector("[data-ficha-jogar]");
    jogar.hidden = !(b.jogo && document.querySelector(`[data-jogo="${b.jogo}"]`));
    jogar.dataset.slug = b.jogo || "";
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
      const jogar = evento.target.closest("[data-ficha-jogar]");
      if (jogar && jogar.dataset.slug) {
        window.dispatchEvent(new CustomEvent("ls-arena:jogar", { detail: { slug: jogar.dataset.slug } }));
      }
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
   OS DESENHOS — um por tipo de brinquedo
   Cada um recebe (arena, estande, grupo) e monta o brinquedo com a base
   em y = 0, a frente virada para +z, ocupando altura × largura × fundo.
   `estande.telas` recebem a foto do produto; `a.adesivo(...)` registra
   uma face que veste a cor e o adesivo escolhidos na ficha.
   ====================================================================== */
const E = 0.004; // o adesivo descola um fio da parede, para não piscar

function perfilGabinete(a, grupo, w, h, d, material) {
  // As duas laterais com o recorte clássico de fliperama.
  const T = a.T;
  const geometria = a.geo(`perfil:${h.toFixed(2)}:${d.toFixed(2)}`, () => {
    const forma = new T.Shape();
    const p = [[-0.5, 0], [0.5, 0], [0.5, 0.42], [0.36, 0.5], [0.22, 0.86], [0.38, 0.9], [0.38, 1], [-0.5, 1]];
    forma.moveTo(-p[0][0] * d, p[0][1] * h);
    p.slice(1).forEach(([z, y]) => forma.lineTo(-z * d, y * h));
    const g = new T.ExtrudeGeometry(forma, { depth: 0.05, bevelEnabled: false });
    g.rotateY(PI / 2);
    return g;
  });
  [-1, 1].forEach((lado) => {
    const m = new T.Mesh(geometria, material);
    m.position.x = lado > 0 ? w / 2 - 0.05 : -w / 2;
    grupo.add(m);
  });
}

/** Adesivos nas duas laterais de uma caixa centrada em (0, y, z). */
function lateraisAdesivadas(a, e, g, largura, altura, fundo, y, z, tipo = "lateral") {
  a.adesivo(e, g, "lado_esq", tipo, fundo, altura, [-largura / 2 - E, y, z], [-1, 0, 0], [0, 0, 1]);
  a.adesivo(e, g, "lado_dir", tipo, fundo, altura, [largura / 2 + E, y, z], [1, 0, 0], [0, 0, -1]);
}

const MODELOS = {
  fliperama(a, e, g) {
    const { w, h, d } = e;
    const cor = e.brinquedo.cor;
    perfilGabinete(a, g, w, h, d, e.matCorpo);
    const miolo = w - 0.1;
    a.caixa(g, miolo, h, d * 0.8, a.escuro(), 0, h / 2, -d * 0.1);
    a.caixa(g, miolo, 0.42 * h, d * 0.2, e.matCorpo, 0, 0.21 * h, 0.4 * d);
    a.caixa(g, miolo, 0.12 * h, 0.1, a.luz(cor, 2.6), 0, 0.95 * h, 0.36 * d);
    const tela = a.tela(g, miolo * 0.86, 0.3 * h, 0, 0.7 * h, 0.27 * d);
    tela.rotation.x = -0.18;
    const painel = a.caixa(g, miolo, 0.04, 0.22 * d, a.plastico("#1b2440"), 0, 0.47 * h, 0.42 * d);
    painel.rotation.x = 0.35;
    a.cilindro(g, 0.02, 0.12, a.metal(), -miolo * 0.25, 0.53 * h, 0.42 * d, 8);
    a.esfera(g, 0.045, a.plastico("#e63946"), -miolo * 0.25, 0.53 * h + 0.07, 0.42 * d);
    ["#ffd700", "#2f8bff", "#e63946", "#1fbf5b"].forEach((c, i) => {
      a.cilindro(g, 0.035, 0.03, a.luz(c, 1.6), miolo * (0.05 + i * 0.1), 0.505 * h, 0.43 * d - (i % 2) * 0.04, 16);
    });
    // Laterais, letreiro e a frente de baixo vestem o adesivo.
    lateraisAdesivadas(a, e, g, w, 0.8 * h, 0.7 * d, 0.43 * h, -0.15 * d);
    a.adesivo(e, g, "letreiro", "letreiro", miolo, 0.12 * h, [0, 0.95 * h, 0.36 * d + 0.05 + E], [0, 0, 1], [1, 0, 0]);
    a.adesivo(e, g, "frente", "frente", miolo, 0.4 * h, [0, 0.21 * h, 0.5 * d + E], [0, 0, 1], [1, 0, 0]);
    a.caixa(g, 0.24, 0.12, 0.02, a.luz("#ffb300", 1.2), 0, 0.12 * h, 0.5 * d + 0.012);
    e.telas = [tela];
  },

  tiro(a, e, g) {
    MODELOS.fliperama(a, e, g);
    const { w, h, d } = e;
    // Duas pistolas de luz no painel.
    [-1, 1].forEach((lado) => {
      const arma = a.caixa(g, 0.07, 0.1, 0.32, a.plastico(lado > 0 ? "#e63946" : "#2f8bff"), lado * w * 0.25, 0.58 * h, 0.48 * d);
      arma.rotation.x = -0.2;
      a.caixa(g, 0.05, 0.14, 0.06, a.escuro(), lado * w * 0.25, 0.53 * h, 0.4 * d);
    });
  },

  musica(a, e, g) {
    const { w, h, d } = e;
    const cor = e.brinquedo.cor;
    a.caixa(g, w, h * 0.42, d, e.matCorpo, 0, h * 0.21, 0);
    a.caixa(g, w * 0.92, h * 0.58, d * 0.35, a.plastico("#151a33"), 0, h * 0.71, -d * 0.3);
    // A tela redonda do Hit Music, com os oito botões em volta.
    const r = Math.min(w, h * 0.5) * 0.36;
    const tela = new a.T.Mesh(a.geo("disco", () => new a.T.CircleGeometry(1, 48)), a.luz("#ff3df2", 1.2));
    tela.scale.setScalar(r);
    tela.position.set(0, h * 0.72, -d * 0.12 + 0.01);
    g.add(tela);
    a.anel(g, r * 1.04, 0.025, a.luz("#ffffff", 3), 0, h * 0.72, -d * 0.11);
    for (let i = 0; i < 8; i++) {
      const ang = (i / 8) * PI * 2;
      a.cilindro(g, 0.06, 0.04, a.luz(CORES[i % CORES.length], 2.4), Math.cos(ang) * r * 1.25, h * 0.72 + Math.sin(ang) * r * 1.25, -d * 0.1, 16).rotation.x = PI / 2;
    }
    a.caixa(g, w, 0.06, 0.08, a.luz(cor, 2.4), 0, h * 0.42, d * 0.5);
    lateraisAdesivadas(a, e, g, w, h * 0.4, d * 0.96, h * 0.21, 0);
    a.adesivo(e, g, "frente", "frente", w * 0.96, h * 0.36, [0, h * 0.2, d / 2 + E], [0, 0, 1], [1, 0, 0]);
    e.telas = [tela];
  },

  simulador(a, e, g) {
    const { w, h, d } = e;
    const cor = e.brinquedo.cor;
    a.caixa(g, w, 0.18, d, a.escuro(), 0, 0.09, 0);
    a.caixa(g, w, 0.04, 0.05, a.luz(cor, 2.4), 0, 0.18, d / 2);
    // O piloto senta de costas para o público e olha a tela grande do fundo.
    a.caixa(g, w * 0.5, 0.12, d * 0.3, a.plastico("#1b1f2e"), 0, 0.45, d * 0.2);
    const encosto = a.caixa(g, w * 0.5, h * 0.42, 0.1, e.matCorpo, 0, 0.72, d * 0.36);
    encosto.rotation.x = 0.2;
    a.caixa(g, 0.12, 0.3, 0.12, a.metal(), 0, 0.3, d * 0.2);
    a.cilindro(g, 0.04, 0.5, a.metal(), 0, 0.55, -d * 0.08, 10).rotation.x = -0.5;
    const volante = a.anel(g, 0.17, 0.025, a.plastico("#222833"), 0, 0.78, -d * 0.16);
    volante.rotation.x = 0.6;
    a.caixa(g, w * 0.95, h * 0.55, 0.12, e.matCorpo, 0, h * 0.62, -d * 0.42);
    const tela = a.tela(g, w * 0.88, h * 0.46, 0, h * 0.62, -d * 0.42 + 0.065);
    a.adesivo(e, g, "traseira", "frente", w * 0.95, h * 0.55, [0, h * 0.62, -d * 0.42 - 0.06 - E], [0, 0, -1], [-1, 0, 0]);
    e.telas = [tela];
  },

  pinball(a, e, g) {
    const { w, h, d } = e;
    const cor = e.brinquedo.cor;
    [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(([x, z]) => a.caixa(g, 0.06, 0.62, 0.06, a.metal(), x * w * 0.42, 0.31, z * d * 0.42));
    const corpo = new a.T.Group();
    corpo.position.set(0, 0.74, 0);
    corpo.rotation.x = 0.1;
    g.add(corpo);
    a.caixa(corpo, w, 0.26, d * 0.9, e.matCorpo, 0, 0, 0);
    lateraisAdesivadas(a, e, corpo, w, 0.24, d * 0.88, 0, 0);
    const mesa = a.tela(corpo, w * 0.86, d * 0.82, 0, 0.135, 0);
    mesa.rotation.x = -PI / 2;
    a.caixa(corpo, w * 0.9, 0.01, d * 0.86, a.vidro(), 0, 0.15, 0);
    a.caixa(g, w, h * 0.42, 0.22, e.matCorpo, 0, h - h * 0.21, -d * 0.4);
    const placar = a.tela(g, w * 0.86, h * 0.3, 0, h - h * 0.21, -d * 0.4 + 0.115);
    a.adesivo(e, g, "traseira", "letreiro", w, h * 0.42, [0, h - h * 0.21, -d * 0.4 - 0.11 - E], [0, 0, -1], [-1, 0, 0]);
    a.caixa(g, w, 0.04, 0.24, a.luz(cor, 2.2), 0, h + 0.02, -d * 0.4);
    a.cilindro(g, 0.02, 0.12, a.metal(), w * 0.38, 0.7, d * 0.46, 8).rotation.x = PI / 2;
    e.telas = [mesa, placar];
  },

  basquete(a, e, g) {
    const { w, h, d } = e;
    const cor = e.brinquedo.cor;
    // Rampa inclinada com as bolas.
    const rampa = a.caixa(g, w, 0.08, d * 0.7, a.plastico("#c96a1a"), 0, 0.55, d * 0.1);
    rampa.rotation.x = -0.12;
    a.caixa(g, w, 0.5, d * 0.7, e.matCorpo, 0, 0.25, d * 0.12);
    lateraisAdesivadas(a, e, g, w, 0.46, d * 0.68, 0.25, d * 0.12);
    a.adesivo(e, g, "frente", "frente", w * 0.98, 0.44, [0, 0.23, d * 0.47 + E], [0, 0, 1], [1, 0, 0]);
    a.caixa(g, w, 0.05, 0.06, a.luz(cor, 2.6), 0, 0.5, d * 0.47);
    for (let i = 0; i < 5; i++) a.esfera(g, 0.12, a.plastico("#ff7a00"), -w * 0.3 + i * w * 0.15, 0.68, d * 0.38);
    // Redes laterais e tabela.
    const lateral = a.geo("redeLateral", () => new a.T.PlaneGeometry(1, 1, 8, 10));
    [-1, 1].forEach((lado) => {
      const r = new a.T.Mesh(lateral, a.rede("#cfe4ff"));
      r.scale.set(d * 0.75, h * 0.7, 1);
      r.rotation.y = PI / 2;
      r.position.set(lado * w / 2, h * 0.55, -d * 0.05);
      g.add(r);
    });
    a.caixa(g, w, 0.1, d * 0.75, e.matCorpo, 0, h - 0.05, -d * 0.05);
    a.caixa(g, w, h * 0.12, 0.08, a.luz(cor, 2.4), 0, h - h * 0.06, d * 0.33);
    a.adesivo(e, g, "letreiro", "letreiro", w * 0.98, h * 0.115, [0, h - h * 0.06, d * 0.33 + 0.04 + E], [0, 0, 1], [1, 0, 0]);
    a.caixa(g, w * 0.74, h * 0.29, 0.05, a.plastico("#ffffff"), 0, h * 0.72, -d * 0.43);
    const tabela = a.tela(g, w * 0.7, h * 0.26, 0, h * 0.72, -d * 0.4);
    const aro = a.anel(g, 0.23, 0.02, a.plastico("#ff5a1f"), 0, h * 0.6, -d * 0.4 + 0.3);
    aro.rotation.x = PI / 2;
    const redeAro = new a.T.Mesh(a.geo("redeAro", () => new a.T.CylinderGeometry(0.23, 0.15, 0.3, 12, 3, true)), a.rede());
    redeAro.position.set(0, h * 0.6 - 0.15, -d * 0.4 + 0.3);
    g.add(redeAro);
    const bola = a.esfera(g, 0.12, a.plastico("#ff7a00"), 0, h * 0.6, -d * 0.1);
    e.animar = (t) => {
      // Uma bola sobe em arco até o aro, sem parar.
      const ciclo = (t * 0.6) % 1;
      bola.position.set(Math.sin(t) * 0.05, 0.7 + Math.sin(ciclo * PI) * (h * 0.45), d * 0.35 - ciclo * (d * 0.45));
    };
    e.telas = [tabela];
  },

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

  pebolim(a, e, g) {
    const { w, h, d } = e;
    [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(([x, z]) => a.caixa(g, 0.08, h * 0.8, 0.08, a.plastico("#1b1f2e"), x * w * 0.4, h * 0.4, z * d * 0.4));
    a.caixa(g, w, 0.22, d, e.matCorpo, 0, h * 0.85, 0);
    lateraisAdesivadas(a, e, g, w, 0.2, d * 0.96, h * 0.85, 0);
    a.adesivo(e, g, "frente", "frente", w * 0.96, 0.2, [0, h * 0.85, d / 2 + E], [0, 0, 1], [1, 0, 0]);
    a.caixa(g, w * 0.86, 0.01, d * 0.9, a.plastico("#1f9d4a"), 0, h * 0.96 + 0.005, 0);
    for (let i = 0; i < 6; i++) {
      const z = -d * 0.38 + i * (d * 0.76 / 5);
      a.cilindro(g, 0.015, w * 1.25, a.metal(), 0, h * 1.02, z, 8).rotation.z = PI / 2;
      a.cilindro(g, 0.04, 0.08, a.plastico("#111111"), w * 0.64, h * 1.02, z, 12).rotation.z = PI / 2;
      for (let j = -1; j <= 1; j++) a.caixa(g, 0.06, 0.16, 0.05, a.plastico(i % 2 ? "#e63946" : "#2f8bff"), j * w * 0.22, h * 0.99, z);
    }
  },

  futebol(a, e, g) {
    const { w, h, d } = e;
    // Gol com os anéis de luz do Gol Flash Arena.
    a.caixa(g, w, 0.04, d, a.plastico("#1f9d4a"), 0, 0.02, 0);
    [-1, 1].forEach((lado) => a.cilindro(g, 0.05, h, a.plastico("#ffffff"), lado * w * 0.45, h / 2, -d * 0.35, 12));
    a.cilindro(g, 0.05, w * 0.9, a.plastico("#ffffff"), 0, h, -d * 0.35, 12).rotation.z = PI / 2;
    const fundoRede = new a.T.Mesh(a.geo("redeGol", () => new a.T.PlaneGeometry(1, 1, 12, 8)), a.rede());
    fundoRede.scale.set(w * 0.9, h, 1);
    fundoRede.position.set(0, h / 2, -d * 0.48);
    g.add(fundoRede);
    const aneis = ["#ffd700", "#2f8bff", "#1fbf5b", "#e63946", "#ff7a00"].map((c, i) => {
      const r = Math.min(w, h) * 0.12;
      return a.anel(g, r, 0.03, a.luz(c, 2), -w * 0.34 + i * (w * 0.68 / 4), h * (i % 2 ? 0.62 : 0.34), -d * 0.34);
    });
    // Placa de LED na frente do gol.
    a.caixa(g, w * 0.9, 0.26, 0.06, e.matCorpo, 0, 0.17, -d * 0.2);
    a.adesivo(e, g, "placa", "frente", w * 0.88, 0.24, [0, 0.17, -d * 0.2 + 0.03 + E], [0, 0, 1], [1, 0, 0]);
    a.esfera(g, 0.11, a.plastico("#f5f8ff"), 0, 0.13, d * 0.3);
    e.animar = (t) => {
      const aceso = Math.floor(t * 1.5) % aneis.length;
      aneis.forEach((anel, i) => anel.scale.setScalar(Math.min(w, h) * 0.12 * (i === aceso ? 1.25 : 1)));
    };
  },

  hockey(a, e, g) {
    const { w, h, d } = e;
    const cor = e.brinquedo.cor;
    a.caixa(g, w * 0.8, h * 0.7, d * 0.8, e.matCorpo, 0, h * 0.35, 0);
    lateraisAdesivadas(a, e, g, w * 0.8, h * 0.62, d * 0.78, h * 0.36, 0);
    a.adesivo(e, g, "frente", "frente", w * 0.78, h * 0.62, [0, h * 0.36, d * 0.4 + E], [0, 0, 1], [1, 0, 0]);
    a.caixa(g, w, 0.14, d, a.plastico(cor), 0, h * 0.75, 0);
    a.caixa(g, w * 0.88, 0.01, d * 0.92, a.plastico("#eaf2ff"), 0, h * 0.82 + 0.005, 0);
    a.caixa(g, w * 0.88, 0.006, 0.02, a.luz("#e63946", 2), 0, h * 0.83, 0);
    [-1, 1].forEach((lado) => {
      a.caixa(g, w * 0.3, 0.05, 0.04, a.escuro(), 0, h * 0.83, lado * d * 0.47);
      a.cilindro(g, 0.07, 0.06, a.plastico(lado > 0 ? "#2f8bff" : "#e63946"), lado * 0.1, h * 0.86, lado * d * 0.3, 20);
    });
    const disco = a.cilindro(g, 0.04, 0.015, a.plastico("#111111"), 0, h * 0.835, 0, 20);
    a.caixa(g, w * 0.6, h * 0.35, 0.1, a.escuro(), 0, h * 1.05, -d * 0.5);
    const placar = a.tela(g, w * 0.5, h * 0.25, 0, h * 1.05, -d * 0.44);
    e.animar = (t) => {
      disco.position.x = Math.sin(t * 2.1) * w * 0.3;
      disco.position.z = Math.sin(t * 1.3) * d * 0.35;
    };
    e.telas = [placar];
  },

  garra(a, e, g) {
    const { w, h, d } = e;
    a.caixa(g, w, h * 0.42, d, e.matCorpo, 0, h * 0.21, 0);
    lateraisAdesivadas(a, e, g, w, h * 0.38, d * 0.96, h * 0.22, 0);
    a.adesivo(e, g, "frente", "frente", w * 0.96, h * 0.24, [0, h * 0.3, d / 2 + E], [0, 0, 1], [1, 0, 0]);
    a.caixa(g, w * 0.3, h * 0.12, 0.04, a.escuro(), -w * 0.25, h * 0.1, d * 0.5);
    // Cabine de vidro com os quatro pilares.
    a.caixa(g, w * 0.96, h * 0.46, d * 0.96, a.vidro(), 0, h * 0.65, 0);
    [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(([x, z]) => a.caixa(g, 0.04, h * 0.46, 0.04, a.metal(), x * w * 0.48, h * 0.65, z * d * 0.48));
    a.caixa(g, w, h * 0.12, d, e.matCorpo, 0, h * 0.94, 0);
    const letreiro = a.tela(g, w * 0.9, h * 0.1, 0, h * 0.94, d * 0.5 + 0.005);
    // Pelúcias (bolinhas coloridas) no fundo da cabine.
    for (let i = 0; i < 14; i++) {
      a.esfera(g, 0.08, a.plastico(CORES[i % CORES.length]), (Math.random() - 0.5) * w * 0.7, h * 0.46 + Math.random() * 0.08, (Math.random() - 0.5) * d * 0.7);
    }
    const garra = new a.T.Group();
    a.cilindro(garra, 0.008, 0.5, a.metal(), 0, 0.25, 0, 6);
    a.cilindro(garra, 0.05, 0.06, a.metal("#c8d3e6"), 0, 0, 0, 12);
    [0, 1, 2].forEach((i) => {
      const dedo = a.caixa(garra, 0.015, 0.14, 0.015, a.metal("#c8d3e6"), Math.sin(i * 2.1) * 0.04, -0.07, Math.cos(i * 2.1) * 0.04);
      dedo.rotation.set(Math.cos(i * 2.1) * 0.4, 0, -Math.sin(i * 2.1) * 0.4);
    });
    garra.position.y = h * 0.82;
    g.add(garra);
    e.animar = (t) => {
      garra.position.x = Math.sin(t * 0.7) * w * 0.3;
      garra.position.z = Math.cos(t * 0.5) * d * 0.25;
      garra.position.y = h * 0.8 - Math.max(0, Math.sin(t * 0.9)) * h * 0.18;
    };
    e.telas = [letreiro];
  },

  boxe(a, e, g) {
    const { w, h, d } = e;
    a.caixa(g, w, 0.12, d, a.escuro(), 0, 0.06, 0);
    a.caixa(g, w * 0.7, h, d * 0.25, e.matCorpo, 0, h / 2, -d * 0.35);
    lateraisAdesivadas(a, e, g, w * 0.7, h * 0.96, d * 0.24, h / 2, -d * 0.35);
    a.adesivo(e, g, "frente", "frente", w * 0.68, h * 0.5, [0, h * 0.34, -d * 0.225 + E], [0, 0, 1], [1, 0, 0]);
    a.caixa(g, w * 0.62, h * 0.3, 0.02, a.escuro(), 0, h * 0.8, -d * 0.22);
    const tela = a.tela(g, w * 0.58, h * 0.26, 0, h * 0.8, -d * 0.205);
    // O braço com o saco de pancada.
    a.caixa(g, 0.08, 0.08, d * 0.45, a.metal(), 0, h * 0.62, -d * 0.05);
    const saco = new a.T.Mesh(a.geo("capsula", () => new a.T.CapsuleGeometry(1, 1.6, 6, 16)), a.plastico("#e63946"));
    saco.scale.setScalar(0.16);
    saco.position.set(0, h * 0.5, d * 0.18);
    g.add(saco);
    e.animar = (t) => { saco.rotation.x = Math.sin(t * 3) * 0.12; };
    e.telas = [tela];
  },

  cama_elastica(a, e, g) {
    const { w, h, d } = e;
    const r = Math.min(w, d) / 2;
    for (let i = 0; i < 6; i++) {
      const ang = (i / 6) * PI * 2;
      a.cilindro(g, 0.03, 0.55, a.metal(), Math.cos(ang) * r, 0.27, Math.sin(ang) * r, 8);
      a.cilindro(g, 0.025, h - 0.55, e.matCorpo, Math.cos(ang) * r, 0.55 + (h - 0.55) / 2, Math.sin(ang) * r, 8);
    }
    a.anel(g, r, 0.06, e.matCorpo, 0, 0.55, 0).rotation.x = PI / 2;
    const lona = new a.T.Mesh(a.geo("disco", () => new a.T.CircleGeometry(1, 48)), a.plastico("#141a2e"));
    lona.scale.setScalar(r * 0.94);
    lona.rotation.x = -PI / 2;
    lona.position.y = 0.53;
    g.add(lona);
    const rede = new a.T.Mesh(a.geo("redeCama", () => new a.T.CylinderGeometry(1, 1, 1, 24, 6, true)), a.rede("#9fd0ff"));
    rede.scale.set(r, h - 0.55, r);
    rede.position.y = 0.55 + (h - 0.55) / 2;
    g.add(rede);
    const bola = a.esfera(g, 0.14, a.plastico("#ffd700"), 0, 0.7, 0);
    e.animar = (t) => { bola.position.y = 0.7 + Math.abs(Math.sin(t * 2.4)) * (h * 0.4); };
  },

  escalada(a, e, g) {
    const { w, h, d } = e;
    const parede = a.caixa(g, w, h, 0.18, e.matCorpo, 0, h / 2, -d * 0.3);
    parede.rotation.x = 0.06;
    a.caixa(g, w * 1.05, 0.25, d, a.plastico("#e63946"), 0, 0.125, d * 0.05);
    const agarra = a.geo("agarra", () => new a.T.DodecahedronGeometry(1, 0));
    for (let i = 0; i < 30; i++) {
      const m = new a.T.Mesh(agarra, a.plastico(CORES[i % CORES.length]));
      m.scale.setScalar(0.05 + Math.random() * 0.05);
      const y = 0.4 + Math.random() * (h - 0.6);
      m.position.set((Math.random() - 0.5) * w * 0.9, y, -d * 0.3 + 0.1 - (y - h / 2) * 0.06);
      m.rotation.set(Math.random(), Math.random(), Math.random());
      g.add(m);
    }
    a.caixa(g, w, 0.16, 0.3, a.escuro(), 0, h + 0.05, -d * 0.3);
    a.caixa(g, w, 0.04, 0.04, a.luz(e.brinquedo.cor, 2.4), 0, h + 0.15, -d * 0.16);
  },

  carrossel(a, e, g) {
    const { w, h } = e;
    const r = w / 2;
    a.cilindro(g, r, 0.2, e.matCorpo, 0, 0.1, 0, 40);
    a.cilindro(g, 0.06, h * 0.8, a.metal("#ffd700"), 0, h * 0.4 + 0.2, 0, 12);
    const giro = new a.T.Group();
    g.add(giro);
    const teto = new a.T.Mesh(a.geo("cone", () => new a.T.ConeGeometry(1, 1, 16)), e.matCorpo);
    teto.scale.set(r * 1.05, h * 0.28, r * 1.05);
    teto.position.y = h * 0.86;
    giro.add(teto);
    a.anel(giro, r * 1.02, 0.04, a.luz("#ff3df2", 2.4), 0, h * 0.72, 0).rotation.x = PI / 2;
    for (let i = 0; i < 6; i++) {
      const ang = (i / 6) * PI * 2;
      const x = Math.cos(ang) * r * 0.72;
      const z = Math.sin(ang) * r * 0.72;
      a.cilindro(giro, 0.02, h * 0.55, a.metal("#ffd700"), x, h * 0.45, z, 8);
      a.esfera(giro, 1, a.plastico(CORES[i % CORES.length]), x, h * 0.35, z).scale.set(0.22, 0.14, 0.12);
    }
    e.animar = (t) => { giro.rotation.y = t * 0.6; };
  },

  touro(a, e, g) {
    const { w, d } = e;
    a.anel(g, Math.max(w, d) * 0.5, 0.18, e.matCorpo, 0, 0.18, 0).rotation.x = PI / 2;
    a.cilindro(g, 0.12, 0.6, a.metal(), 0, 0.3, 0, 12);
    const touro = new a.T.Group();
    touro.position.y = 0.75;
    g.add(touro);
    const corpo = new a.T.Mesh(a.geo("capsula", () => new a.T.CapsuleGeometry(1, 1.6, 6, 16)), a.plastico("#5a3215"));
    corpo.scale.setScalar(0.24);
    corpo.rotation.x = PI / 2;
    touro.add(corpo);
    a.esfera(touro, 0.2, a.plastico("#4a2810"), 0, 0.1, 0.42);
    [-1, 1].forEach((lado) => {
      const chifre = new a.T.Mesh(a.geo("cone", () => new a.T.ConeGeometry(1, 1, 16)), a.plastico("#f3e6c8"));
      chifre.scale.set(0.04, 0.2, 0.04);
      chifre.rotation.z = -lado * 1.1;
      chifre.position.set(lado * 0.2, 0.22, 0.44);
      touro.add(chifre);
    });
    e.animar = (t) => {
      touro.rotation.x = Math.sin(t * 3.1) * 0.18;
      touro.rotation.y = Math.sin(t * 1.2) * 0.5;
    };
  },

  playground(a, e, g) {
    const { w, h, d } = e;
    // Duas torres com telhado, passarela e escorregador.
    [[-1, e.matCorpo], [1, a.plastico("#2f8bff")]].forEach(([lado, material]) => {
      const x = lado * w * 0.28;
      a.caixa(g, w * 0.32, h * 0.55, d * 0.4, material, x, h * 0.275, -d * 0.1);
      const telhado = new a.T.Mesh(a.geo("piramide", () => new a.T.ConeGeometry(1, 1, 4)), a.plastico("#ffd700"));
      telhado.scale.set(w * 0.24, h * 0.3, d * 0.3);
      telhado.rotation.y = PI / 4;
      telhado.position.set(x, h * 0.7 + 0.05, -d * 0.1);
      g.add(telhado);
    });
    a.adesivo(e, g, "frente", "frente", w * 0.3, h * 0.4, [-w * 0.28, h * 0.3, -d * 0.1 + d * 0.2 + E], [0, 0, 1], [1, 0, 0]);
    a.caixa(g, w * 0.3, 0.08, d * 0.3, a.plastico("#1fbf5b"), 0, h * 0.5, -d * 0.1);
    const escorregador = a.caixa(g, w * 0.18, 0.05, d * 0.7, a.plastico("#ff7a00"), w * 0.28, h * 0.28, d * 0.3);
    escorregador.rotation.x = 0.62;
    const rede = new a.T.Mesh(a.geo("redePlay", () => new a.T.PlaneGeometry(1, 1, 6, 6)), a.rede("#ffd700"));
    rede.scale.set(w * 0.3, h * 0.25, 1);
    rede.position.set(0, h * 0.66, d * 0.05);
    g.add(rede);
    for (let i = 0; i < 18; i++) a.esfera(g, 0.07, a.plastico(CORES[i % CORES.length]), -w * 0.35 + Math.random() * w * 0.25, 0.07, d * 0.2 + Math.random() * d * 0.25);
  },

  montaria(a, e, g) {
    const { w, h, d } = e;
    const cor = e.brinquedo.cor;
    a.caixa(g, w, h * 0.16, d, a.plastico("#1b2440"), 0, h * 0.08, 0);
    lateraisAdesivadas(a, e, g, w, h * 0.14, d * 0.96, h * 0.08, 0);
    a.caixa(g, w + 0.02, 0.03, d + 0.02, a.luz(cor, 2.2), 0, h * 0.16, 0);
    const corpo = new a.T.Group();
    corpo.position.y = h * 0.16;
    g.add(corpo);
    const tronco = new a.T.Mesh(a.geo("capsula", () => new a.T.CapsuleGeometry(1, 1.6, 6, 16)), e.matCorpo);
    tronco.scale.set(w * 0.3, Math.min(d, 1.2) * 0.22, w * 0.3);
    tronco.rotation.x = PI / 2;
    tronco.position.y = h * 0.3;
    corpo.add(tronco);
    a.esfera(corpo, w * 0.28, e.matCorpo, 0, h * 0.55, d * 0.32);
    a.esfera(corpo, w * 0.07, a.plastico("#ffffff"), -w * 0.1, h * 0.6, d * 0.32 + w * 0.24);
    a.esfera(corpo, w * 0.07, a.plastico("#ffffff"), w * 0.1, h * 0.6, d * 0.32 + w * 0.24);
    a.caixa(corpo, w * 0.4, 0.06, d * 0.3, a.plastico("#1b1f2e"), 0, h * 0.45, -d * 0.05);
    const placa = a.tela(g, w * 0.8, h * 0.28, 0, h * 0.86, -d * 0.45);
    a.caixa(g, 0.05, h * 0.75, 0.05, a.metal(), 0, h * 0.4, -d * 0.48);
    e.animar = (t) => {
      corpo.rotation.x = Math.sin(t * 2.2) * 0.08;
      corpo.position.y = h * 0.16 + Math.abs(Math.sin(t * 2.2)) * 0.03;
    };
    e.telas = [placa];
  },
};
