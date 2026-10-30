/* ======================================================================
   ARENA 3D — as máquinas da fábrica, montadas com as fotos reais.

   CADA MÁQUINA VIRA UM OBJETO 3D FEITO DAS FOTOS DELA. O catálogo tem até
   quatro fotos por máquina (frente, lado direito, costas, lado esquerdo).
   Aqui, no navegador de quem visita:

     1. RECORTE: a máquina sai do fundo da foto. Foto já recortada (PNG
        transparente) vale como está; foto de fundo liso (o estúdio branco,
        a parede) tem o fundo apagado a partir das bordas, pela cor dele.
        Foto de fundo complicado (o salão, a loja) não dá para recortar
        sem estragar a máquina: ela entra num quadro em pé, inteira.
     2. OBJETO: o recorte fica em pé no tamanho de verdade (a altura do
        cadastro), com sombra no piso, e mostra o LADO CERTO conforme a
        pessoa gira: de frente a foto da frente, de lado a do lado, de
        trás a das costas. É assim que uma foto vira volume.

   AS ÁREAS FICAM DENTRO DO 3D: máquinas com jogos da Lazer & Sport, as que
   já fazíamos, trampolins e brinquedões -- cada uma com o seu tapete e a
   sua placa no piso da arena. Os botões de área levam a câmera até ela, e
   o filtro de categoria deixa na arena só as máquinas daquela categoria.

   A FICHA FICA FORA DO PALCO: ao lado no computador, embaixo no celular.
   O 3D nunca fica coberto.

   O QUE ESTE ARQUIVO NÃO FAZ: baixar o three.js antes da hora (~170 KB) ou
   num aparelho sem WebGL -- ali a lista de máquinas é a página.
   ====================================================================== */

const raiz = document.querySelector("[data-arena3d]");
if (raiz) iniciar(raiz);

const PI = Math.PI;
const COR_DA_ZONA = { jogos: "#e63946", maquinas: "#2f8bff", brinquedoes: "#22c55e" };
const NOME_DO_LADO = { perfil: "Frente", lado_direito: "Lado direito", verso: "Costas", lado_esquerdo: "Lado esquerdo" };
// a câmera de frente vê a frente; na direita de quem olha, o lado direito
const LADO_POR_QUADRANTE = ["perfil", "lado_direito", "verso", "lado_esquerdo"];
const VAGA = { largura: 3.4, fundo: 3.6 }; // o espaço de cada máquina no piso, em metros
const FOTO_LONGE = 360; // px: todas as máquinas na visão geral
const FOTO_PERTO = 900; // px: a máquina escolhida, de perto

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

/* ======================================================================
   RECORTE — a máquina sem o fundo da foto
   ====================================================================== */

/** A mesma foto do Cloudinary em outra largura (as outras URLs vêm como estão). */
function fotoNaLargura(url, largura) {
  if (!url.includes("res.cloudinary.com")) return url;
  if (/\/upload\/[^/]*\bw_\d+/.test(url)) return url.replace(/\bw_\d+/, `w_${largura}`);
  return url.replace("/upload/", `/upload/c_limit,w_${largura},f_auto,q_auto/`);
}

function carregarImagem(url) {
  return new Promise((resolver, falhar) => {
    const img = new Image();
    img.crossOrigin = "anonymous"; // a foto vira textura: precisa de CORS
    img.decoding = "async";
    img.onload = () => resolver(img);
    img.onerror = () => falhar(new Error("foto não carregou: " + url));
    img.src = url;
  });
}

const distancia = (p, i, r, g, b) => Math.abs(p[i] - r) + Math.abs(p[i + 1] - g) + Math.abs(p[i + 2] - b);

/**
 * Recorta a máquina da foto. Devolve { tela, aspecto, recortada } -- com
 * `recortada` falso quando o fundo não é liso: aí a tela é a foto inteira,
 * para o quadro em pé. `null` se a foto não pode ser lida (sem CORS).
 */
function recortar(img, maximo) {
  const escala = Math.min(1, maximo / Math.max(img.naturalWidth, img.naturalHeight));
  const w = Math.max(2, Math.round(img.naturalWidth * escala));
  const h = Math.max(2, Math.round(img.naturalHeight * escala));
  const tela = document.createElement("canvas");
  tela.width = w;
  tela.height = h;
  const g = tela.getContext("2d", { willReadFrequently: true });
  g.drawImage(img, 0, 0, w, h);
  let quadro;
  try {
    quadro = g.getImageData(0, 0, w, h);
  } catch (erro) {
    return null;
  }
  const p = quadro.data;
  const n = w * h;
  const fundo = new Uint8Array(n);

  const borda = [];
  for (let x = 0; x < w; x++) borda.push(x, (h - 1) * w + x);
  for (let y = 1; y < h - 1; y++) borda.push(y * w, y * w + w - 1);

  // 1) já recortada: a borda é transparente
  const transparentes = borda.filter((i) => p[i * 4 + 3] < 24).length;
  if (transparentes / borda.length > 0.6) {
    for (let i = 0; i < n; i++) fundo[i] = p[i * 4 + 3] < 24 ? 1 : 0;
  } else {
    // 2) fundo liso: a cor mais comum da borda (mediana de cada canal)
    const canal = (c) => {
      const valores = borda.map((i) => p[i * 4 + c]).sort((a, b) => a - b);
      return valores[valores.length >> 1];
    };
    const r0 = canal(0);
    const g0 = canal(1);
    const b0 = canal(2);
    const lisos = borda.filter((i) => distancia(p, i * 4, r0, g0, b0) < 48).length;
    if (lisos / borda.length < 0.62) return { tela, aspecto: w / h, recortada: false };

    // apaga a partir das bordas tudo o que é da cor do fundo e encosta nele
    const fila = new Int32Array(n);
    let inicio = 0;
    let fim = 0;
    for (const i of borda) {
      if (!fundo[i] && distancia(p, i * 4, r0, g0, b0) < 60) {
        fundo[i] = 1;
        fila[fim++] = i;
      }
    }
    while (inicio < fim) {
      const i = fila[inicio++];
      const x = i % w;
      const vizinhos = [x > 0 ? i - 1 : -1, x < w - 1 ? i + 1 : -1, i - w, i + w];
      for (const v of vizinhos) {
        if (v < 0 || v >= n || fundo[v]) continue;
        if (distancia(p, v * 4, r0, g0, b0) < 60 && distancia(p, v * 4, p[i * 4], p[i * 4 + 1], p[i * 4 + 2]) < 34) {
          fundo[v] = 1;
          fila[fim++] = v;
        }
      }
    }
  }

  // sobrou máquina de verdade? (nem quase nada, nem a foto inteira)
  let cheios = 0;
  let x0 = w;
  let y0 = h;
  let x1 = -1;
  let y1 = -1;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = y * w + x;
      if (fundo[i]) continue;
      cheios++;
      if (x < x0) x0 = x;
      if (x > x1) x1 = x;
      if (y < y0) y0 = y;
      if (y > y1) y1 = y;
    }
  }
  if (cheios / n < 0.05 || cheios / n > 0.97) return { tela, aspecto: w / h, recortada: false };

  // o fundo some; a beira da máquina fica meio transparente (sem serrilhado)
  for (let i = 0; i < n; i++) {
    if (fundo[i]) {
      p[i * 4 + 3] = 0;
      continue;
    }
    const x = i % w;
    const beira = (x > 0 && fundo[i - 1]) || (x < w - 1 && fundo[i + 1]) || (i >= w && fundo[i - w]) || (i + w < n && fundo[i + w]);
    if (beira) p[i * 4 + 3] = Math.min(p[i * 4 + 3], 140);
  }
  g.putImageData(quadro, 0, 0);

  const bw = x1 - x0 + 1;
  const bh = y1 - y0 + 1;
  const corte = document.createElement("canvas");
  corte.width = bw;
  corte.height = bh;
  corte.getContext("2d").drawImage(tela, x0, y0, bw, bh, 0, 0, bw, bh);
  return { tela: corte, aspecto: bw / bh, recortada: true };
}

/* ======================================================================
   UMA MÁQUINA — as fotos em pé, no tamanho de verdade
   ====================================================================== */
class Maquina {
  constructor(arena, dados) {
    const T = arena.T;
    this.arena = arena;
    this.dados = dados;
    this.cor = COR_DA_ZONA[dados.grupo] || "#2f8bff";
    this.fotos = {};
    (dados.fotos || []).forEach((f) => { if (f.url && !this.fotos[f.tipo]) this.fotos[f.tipo] = f.url; });
    if (!this.fotos.perfil && dados.capa) this.fotos.perfil = dados.capa;

    const [altura, largura, fundo] = (dados.medidas || []).map(Number);
    this.altura = Math.min(4.2, Math.max(0.8, altura || 1.8));
    this.largura = Math.min(VAGA.largura - 0.4, Math.max(0.5, largura || 1));
    this.fundo = Math.min(VAGA.fundo - 0.4, Math.max(0.5, fundo || 1));

    this.grupo = new T.Group();
    this.texturas = {}; // lado -> { textura, aspecto, recortada, tamanho }
    this.pedidos = {}; // lado -> tamanho já pedido
    this.lado = null;
    this.virada = 1; // a "virada" ao trocar de lado (escala X de 0 a 1)

    // sombra macia no piso e o disco com a cor da área
    this.sombra = new T.Mesh(arena.geoPiso, arena.matSombra);
    this.sombra.rotation.x = -PI / 2;
    this.sombra.position.y = 0.012;
    this.grupo.add(this.sombra);
    this.disco = new T.Mesh(arena.geoPiso, arena.matDisco(this.cor));
    this.disco.rotation.x = -PI / 2;
    this.disco.position.y = 0.008;
    this.disco.scale.set(Math.max(this.largura, 1.2) + 1.2, Math.max(this.fundo, 1.2) + 1.2, 1);
    this.grupo.add(this.disco);

    // a máquina: a foto recortada, sempre de frente para a câmera
    this.material = new T.MeshBasicMaterial({ transparent: true, alphaTest: 0.45, side: T.DoubleSide, toneMapped: false });
    this.painel = new T.Mesh(arena.geoPainel, this.material);
    this.painel.visible = false;
    this.painel.userData.maquina = this;
    this.grupo.add(this.painel);

    // a foto que não deu para recortar vai num quadro em pé
    this.quadro = new T.Mesh(arena.geoPainel, arena.matQuadro(this.cor));
    this.quadro.visible = false;
    this.quadro.userData.maquina = this;
    this.grupo.add(this.quadro);
  }

  get temFoto() {
    return Object.keys(this.fotos).length > 0;
  }

  /** O lado que a câmera vê agora, pelo ângulo em volta da máquina. */
  ladoVisto(camera) {
    const pos = this.grupo.position;
    const angulo = Math.atan2(camera.position.x - pos.x, camera.position.z - pos.z);
    const quadrante = (Math.round(angulo / (PI / 2)) + 4) % 4;
    const lado = LADO_POR_QUADRANTE[quadrante];
    return this.fotos[lado] ? lado : "perfil";
  }

  /** Baixa e recorta um lado no tamanho pedido (uma vez por tamanho). */
  pedir(lado, tamanho) {
    const url = this.fotos[lado];
    if (!url || (this.pedidos[lado] || 0) >= tamanho) return;
    this.pedidos[lado] = tamanho;
    this.arena.fila.push(async () => {
      try {
        const img = await carregarImagem(fotoNaLargura(url, tamanho));
        const resultado = recortar(img, tamanho);
        if (!resultado) throw new Error("foto sem CORS");
        const T = this.arena.T;
        const textura = new T.CanvasTexture(resultado.tela);
        textura.colorSpace = T.SRGBColorSpace;
        textura.anisotropy = 2;
        const antiga = this.texturas[lado];
        this.texturas[lado] = { textura, aspecto: resultado.aspecto, recortada: resultado.recortada, tamanho };
        if (this.lado === lado) this.vestir(lado);
        if (antiga) antiga.textura.dispose();
      } catch (erro) {
        if (lado === "perfil" && !this.texturas.perfil) this.semFoto = true;
      }
    });
  }

  vestir(lado) {
    const foto = this.texturas[lado];
    if (!foto) return;
    this.lado = lado;
    const malha = foto.recortada ? this.painel : this.quadro;
    const outra = foto.recortada ? this.quadro : this.painel;
    outra.visible = false;
    malha.material.map = foto.textura;
    malha.material.needsUpdate = true;
    if (foto.recortada) {
      // a altura é a do cadastro; a largura sai da proporção da foto
      this.larguraBase = Math.min(VAGA.largura - 0.2, this.altura * foto.aspecto);
      const h = this.larguraBase / foto.aspecto;
      malha.scale.set(this.larguraBase, h, 1);
      malha.position.y = h / 2;
    } else {
      // quadro em pé: a foto inteira, a 0,5 m do piso
      const h = Math.min(2.2, Math.max(1.4, this.altura));
      this.larguraBase = Math.min(VAGA.largura - 0.4, h * foto.aspecto);
      malha.scale.set(this.larguraBase, this.larguraBase / foto.aspecto, 1);
      malha.position.y = 0.5 + malha.scale.y / 2;
    }
    malha.visible = true;
    this.sombra.scale.set(this.larguraBase * 1.25, Math.max(this.fundo, 0.8) * 1.1, 1);
  }

  atualizar(camera, dt, perto) {
    // sempre de frente para quem olha; o lado certo vem pela foto
    const pos = this.grupo.position;
    const giro = Math.atan2(camera.position.x - pos.x, camera.position.z - pos.z);
    this.painel.rotation.y = giro;
    this.quadro.rotation.y = giro;

    const lado = this.ladoVisto(camera);
    this.pedir(lado, perto ? FOTO_PERTO : FOTO_LONGE);

    if (lado !== this.lado && this.texturas[lado]) {
      if (this.lado === null || this.arena.reduzido) {
        this.vestir(lado);
        this.virada = 1;
      } else if (this.virada > 0.15) {
        // troca de lado com uma "virada" rápida, como se a máquina girasse
        this.virada = Math.max(0.12, this.virada - dt * 9);
      } else {
        this.vestir(lado);
      }
    } else if (this.virada < 1) {
      this.virada = Math.min(1, this.virada + dt * 9);
    }
    const foto = this.texturas[this.lado];
    if (foto) {
      const malha = foto.recortada ? this.painel : this.quadro;
      malha.scale.x = this.larguraBase * this.virada;
      // a que fica entre a câmera e a máquina escolhida sai da frente
      malha.visible = !this.encoberta;
    }
  }

  mostrar(sim) {
    this.grupo.visible = sim;
  }
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
    this.relogio = 0;
    this.ocioso = 0;
    this.tour = false;
    this.tourTempo = 0;
    this.selecionada = null;
    this.zonaAtual = "";
    this.categoria = "";
    this.fila = [];
    this.trabalhando = 0;

    this.canvas = document.createElement("canvas");
    this.canvas.className = "arena3d-tela";
    this.canvas.setAttribute("role", "img");
    this.canvas.setAttribute("aria-label", "Arena 3D com as máquinas da Lazer & Sport, montadas com as fotos reais. Arraste para girar e toque numa máquina para ver a ficha.");
    palco.prepend(this.canvas);

    const densidade = Math.min(window.devicePixelRatio || 1, this.celular ? 1.5 : 1.75);
    this.renderer = new T.WebGLRenderer({ canvas: this.canvas, antialias: !this.celular, powerPreference: "high-performance" });
    this.renderer.setPixelRatio(densidade);
    this.renderer.outputColorSpace = T.SRGBColorSpace;

    this.cena = new T.Scene();
    this.cena.background = new T.Color("#040a1c");
    this.cena.fog = new T.Fog("#040a1c", 34, 110);
    this.camera = new T.PerspectiveCamera(42, 1, 0.1, 300);
    this.raycaster = new T.Raycaster();
    this.ponteiro = new T.Vector2();

    // peças compartilhadas
    this.geoPainel = new T.PlaneGeometry(1, 1);
    this.geoPiso = new T.PlaneGeometry(1, 1);
    this.matSombra = new T.MeshBasicMaterial({ map: this.texturaSombra(), transparent: true, depthWrite: false, opacity: 0.75 });
    this.discos = {};
    this.quadros = {};

    this.maquinas = (dados.maquinas || []).map((d) => new Maquina(this, d)).filter((m) => m.temFoto);
    this.maquinas.forEach((m) => this.cena.add(m.grupo));
    this.decoracao = new T.Group();
    this.cena.add(this.decoracao);
    this.montarPiso();
    this.camera3d = new Camera(this);
  }

  /* ---------- materiais ---------- */
  texturaSombra() {
    const tela = document.createElement("canvas");
    tela.width = tela.height = 128;
    const g = tela.getContext("2d");
    const grad = g.createRadialGradient(64, 64, 4, 64, 64, 62);
    grad.addColorStop(0, "rgba(0,0,0,.7)");
    grad.addColorStop(1, "rgba(0,0,0,0)");
    g.fillStyle = grad;
    g.fillRect(0, 0, 128, 128);
    return new this.T.CanvasTexture(tela);
  }

  matDisco(cor) {
    if (!this.discos[cor]) {
      const tela = document.createElement("canvas");
      tela.width = tela.height = 128;
      const g = tela.getContext("2d");
      const grad = g.createRadialGradient(64, 64, 20, 64, 64, 63);
      grad.addColorStop(0, "rgba(0,0,0,0)");
      grad.addColorStop(0.82, cor + "33");
      grad.addColorStop(0.9, cor + "cc");
      grad.addColorStop(1, cor + "00");
      g.fillStyle = grad;
      g.fillRect(0, 0, 128, 128);
      const textura = new this.T.CanvasTexture(tela);
      textura.colorSpace = this.T.SRGBColorSpace;
      this.discos[cor] = new this.T.MeshBasicMaterial({ map: textura, transparent: true, depthWrite: false });
    }
    return this.discos[cor];
  }

  matQuadro(cor) {
    // cada quadro tem a sua foto: material próprio, a moldura é a cor da área
    return new this.T.MeshBasicMaterial({ color: "#ffffff", side: this.T.DoubleSide, toneMapped: false, userData: { cor } });
  }

  texturaDeTexto(linhas, cor, largura = 1024, altura = 256) {
    const tela = document.createElement("canvas");
    tela.width = largura;
    tela.height = altura;
    const g = tela.getContext("2d");
    g.fillStyle = "rgba(5,11,31,.88)";
    const r = 40;
    g.beginPath();
    g.roundRect ? g.roundRect(8, 8, largura - 16, altura - 16, r) : g.rect(8, 8, largura - 16, altura - 16);
    g.fill();
    g.lineWidth = 8;
    g.strokeStyle = cor;
    g.stroke();
    g.textAlign = "center";
    g.textBaseline = "middle";
    g.fillStyle = cor;
    g.font = "800 46px Poppins, Manrope, sans-serif";
    g.fillText(linhas[0].toUpperCase(), largura / 2, altura * 0.32);
    g.fillStyle = "#ffffff";
    g.font = "900 72px Poppins, Manrope, sans-serif";
    g.fillText(linhas[1], largura / 2, altura * 0.66, largura - 60);
    const textura = new this.T.CanvasTexture(tela);
    textura.colorSpace = this.T.SRGBColorSpace;
    return textura;
  }

  montarPiso() {
    const T = this.T;
    const piso = new T.Mesh(new T.CircleGeometry(160, 64), new T.MeshBasicMaterial({ color: "#071230" }));
    piso.rotation.x = -PI / 2;
    this.cena.add(piso);
    const grade = new T.GridHelper(240, 80, "#1b3a7a", "#0f2452");
    grade.position.y = 0.004;
    grade.material.transparent = true;
    grade.material.opacity = 0.55;
    this.cena.add(grade);
  }

  /* ---------- montagem: as áreas, lado a lado ---------- */
  visiveis() {
    return this.maquinas.filter((m) => !this.categoria || (m.dados.categorias || []).includes(this.categoria));
  }

  montar() {
    const T = this.T;
    // limpa a decoração antiga (tapetes e placas)
    this.decoracao.children.slice().forEach((filho) => {
      this.decoracao.remove(filho);
      if (filho.material && filho.material.map) filho.material.map.dispose();
      if (filho.material) filho.material.dispose();
      if (filho.geometry && filho.geometry !== this.geoPiso && filho.geometry !== this.geoPainel) filho.geometry.dispose();
    });

    const visiveis = new Set(this.visiveis());
    this.maquinas.forEach((m) => m.mostrar(visiveis.has(m)));
    this.areas = [];

    // as áreas em fila, da esquerda para a direita, na ordem do servidor
    const zonas = this.zonas.map((z) => ({ ...z, maquinas: this.maquinas.filter((m) => m.dados.grupo === z.id && visiveis.has(m)) }))
      .filter((z) => z.maquinas.length);
    // Tela deitada: as áreas lado a lado. Tela em pé (celular): uma atrás
    // da outra, estreitas, e a câmera olha mais de cima -- cabem na tela.
    this.empilhar = this.camera.aspect < 0.9;
    const larguras = zonas.map((z) => this.empilhar
      ? Math.min(z.maquinas.length, 3)
      : Math.min(z.maquinas.length, Math.max(2, Math.ceil(Math.sqrt(z.maquinas.length * 1.6)))));
    const total = this.empilhar
      ? Math.max(...larguras, 1) * VAGA.largura
      : larguras.reduce((soma, colunas) => soma + colunas * VAGA.largura, 0) + Math.max(0, zonas.length - 1) * 4;
    let x = -total / 2;
    let z0 = 0;

    zonas.forEach((zona, k) => {
      const colunas = larguras[k];
      const linhas = Math.ceil(zona.maquinas.length / colunas);
      const largura = colunas * VAGA.largura;
      const fundo = linhas * VAGA.fundo;
      if (this.empilhar) x = -largura / 2;
      const cx = x + largura / 2;
      const cor = COR_DA_ZONA[zona.id] || "#2f8bff";

      zona.maquinas.forEach((m, i) => {
        const coluna = i % colunas;
        const linha = Math.floor(i / colunas);
        // a última linha incompleta fica centrada
        const naLinha = Math.min(colunas, zona.maquinas.length - linha * colunas);
        const desvio = (colunas - naLinha) * VAGA.largura / 2;
        m.grupo.position.set(x + desvio + (coluna + 0.5) * VAGA.largura, 0, z0 - (linha + 0.5) * VAGA.fundo);
      });

      // o tapete da área
      const tapete = new T.Mesh(this.geoPiso, new T.MeshBasicMaterial({ color: cor, transparent: true, opacity: 0.1, depthWrite: false }));
      tapete.rotation.x = -PI / 2;
      tapete.position.set(cx, 0.006, z0 - fundo / 2);
      tapete.scale.set(largura + 1, fundo + 1.2, 1);
      this.decoracao.add(tapete);
      const contorno = new T.LineSegments(
        new T.EdgesGeometry(new T.PlaneGeometry(largura + 1, fundo + 1.2)),
        new T.LineBasicMaterial({ color: cor, transparent: true, opacity: 0.85 }),
      );
      contorno.rotation.x = -PI / 2;
      contorno.position.set(cx, 0.01, z0 - fundo / 2);
      this.decoracao.add(contorno);

      // a placa da área, deitada na frente do tapete (lida de cima e de frente)
      const placa = new T.Mesh(this.geoPainel, new T.MeshBasicMaterial({
        map: this.texturaDeTexto([zona.kicker || "", zona.titulo], cor), transparent: true, depthWrite: false, toneMapped: false,
      }));
      const lp = Math.min(largura, 9);
      placa.scale.set(lp, lp / 4, 1);
      placa.rotation.x = -PI / 2.6;
      placa.position.set(cx, 0.35, z0 + 1.6);
      this.decoracao.add(placa);

      this.areas.push({ id: zona.id, centro: new T.Vector3(cx, 1, z0 - fundo / 2), largura, fundo });
      if (this.empilhar) z0 -= fundo + 4.5;
      else x += largura + 4;
    });

    this.ordem = this.areas.flatMap((a) => this.maquinas.filter((m) => m.dados.grupo === a.id && m.grupo.visible));
    this.limites = this.empilhar
      ? { largura: total, fundo: Math.max(VAGA.fundo, -z0 - 4.5) }
      : { largura: total, fundo: Math.max(VAGA.fundo, ...this.areas.map((a) => a.fundo)) };

    // as fotos de frente de todas, em tamanho pequeno
    this.ordem.forEach((m) => m.pedir("perfil", FOTO_LONGE));
  }

  /* ---------- fila de recortes: um por vez, sem travar a página ---------- */
  andarFila() {
    while (this.trabalhando < 2 && this.fila.length) {
      const tarefa = this.fila.shift();
      this.trabalhando++;
      tarefa().finally(() => {
        this.trabalhando--;
        this.mostrarProgresso();
      });
    }
  }

  mostrarProgresso() {
    const prontas = this.maquinas.filter((m) => m.texturas.perfil || m.semFoto).length;
    if (!this.avisoSumiu && prontas >= Math.min(this.maquinas.length, 3)) {
      this.avisoSumiu = true;
      this.palco.querySelector("[data-arena-aviso]").classList.add("sumiu");
      const dica = this.palco.querySelector("[data-arena-dica]");
      if (dica) {
        dica.hidden = false;
        window.setTimeout(() => { dica.hidden = true; }, 6000);
      }
    }
  }

  /* ---------- escolher uma máquina ---------- */
  selecionar(maquina, { voar = true } = {}) {
    if (!maquina) return;
    this.selecionada = maquina;
    if (voar) this.camera3d.olharPara(maquina);
    Object.keys(maquina.fotos).forEach((lado) => maquina.pedir(lado, FOTO_PERTO));
    this.mostrarFicha(maquina);
    this.marcarLista();
  }

  soltarSelecao() {
    this.selecionada = null;
    this.ficha.querySelector("[data-ficha-cheia]").hidden = true;
    this.ficha.querySelector("[data-ficha-vazia]").hidden = false;
    this.camera3d.visaoGeral();
    this.marcarLista();
  }

  proxima(passo) {
    const ordem = this.ordem || [];
    if (!ordem.length) return;
    const atual = this.selecionada ? ordem.indexOf(this.selecionada) : (passo > 0 ? -1 : 0);
    this.selecionar(ordem[(atual + passo + ordem.length) % ordem.length]);
  }

  irParaZona(id) {
    this.zonaAtual = id;
    const area = this.areas.find((a) => a.id === id);
    if (!area) {
      this.camera3d.visaoGeral();
      return;
    }
    this.camera3d.olharArea(area);
  }

  filtrar(categoria) {
    this.categoria = categoria;
    this.montar();
    if (this.selecionada && !this.selecionada.grupo.visible) this.soltarSelecao();
    this.camera3d.visaoGeral();
    this.atualizarContagem();
  }

  atualizarContagem() {
    const contagem = {};
    this.ordem.forEach((m) => { contagem[m.dados.grupo] = (contagem[m.dados.grupo] || 0) + 1; });
    this.raiz.querySelectorAll("[data-arena-zona]").forEach((botao) => {
      const id = botao.dataset.arenaZona;
      const total = id ? (contagem[id] || 0) : this.ordem.length;
      const b = botao.querySelector("b");
      if (b) b.textContent = String(total);
      botao.hidden = Boolean(id) && !total;
    });
  }

  /* ---------- ficha (fora do palco) ---------- */
  mostrarFicha(m) {
    const f = this.ficha;
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

    // as fotos de cada lado: tocar numa leva a câmera para aquele lado
    const foto = f.querySelector("[data-ficha-foto]");
    const lados = f.querySelector("[data-ficha-lados]");
    lados.replaceChildren();
    const ordem = LADO_POR_QUADRANTE.filter((lado) => m.fotos[lado]);
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
        this.camera3d.verLado(m, LADO_POR_QUADRANTE.indexOf(lado));
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
    this.controles = this.palco.querySelector("[data-arena-controles]");
    this.rotulo = document.createElement("div");
    this.rotulo.className = "arena3d-rotulo";
    this.rotulo.hidden = true;
    this.palco.append(this.rotulo);

    this.redimensionar();
    this.montar();
    this.atualizarContagem();
    new ResizeObserver(() => this.redimensionar()).observe(this.palco);
    this.camera3d.ligarEventos(this.canvas);
    this.camera3d.visaoGeral(true);
    if (this.controles) this.controles.hidden = false;

    this.controles.addEventListener("click", (evento) => {
      const botao = evento.target.closest("[data-arena-acao]");
      if (botao) this.acao(botao.dataset.arenaAcao, botao);
    });

    raiz.querySelector("[data-arena-zonas]").addEventListener("click", (evento) => {
      const botao = evento.target.closest("[data-arena-zona]");
      if (!botao) return;
      raiz.querySelectorAll("[data-arena-zona]").forEach((b) => {
        const ativo = b === botao;
        b.classList.toggle("ativo", ativo);
        b.setAttribute("aria-pressed", ativo ? "true" : "false");
      });
      this.ocioso = 0;
      this.irParaZona(botao.dataset.arenaZona);
    });

    const categoria = raiz.querySelector("[data-arena-categoria]");
    if (categoria) categoria.addEventListener("change", () => this.filtrar(categoria.value));

    // a lista vira o controle remoto da arena
    raiz.querySelectorAll("[data-arena-id]").forEach((link) => {
      link.addEventListener("click", (evento) => {
        if (evento.metaKey || evento.ctrlKey || evento.shiftKey) return;
        const maquina = this.maquinas.find((m) => String(m.dados.id) === link.dataset.arenaId && m.grupo.visible);
        if (!maquina) return;
        evento.preventDefault();
        this.selecionar(maquina);
        this.palco.scrollIntoView({ behavior: this.reduzido ? "auto" : "smooth", block: "center" });
      });
    });

    this.palco.addEventListener("keydown", (evento) => {
      if (evento.key === "ArrowRight") { this.proxima(1); evento.preventDefault(); }
      else if (evento.key === "ArrowLeft") { this.proxima(-1); evento.preventDefault(); }
      else if (evento.key === "Escape" && this.selecionada) this.soltarSelecao();
    });
    this.canvas.tabIndex = 0;

    // fora da tela ou com a aba escondida: não desenha nada
    new IntersectionObserver((entradas) => {
      this.visivel = entradas.some((e) => e.isIntersecting);
      this.acordar();
    }).observe(this.palco);
    document.addEventListener("visibilitychange", () => this.acordar());
    document.addEventListener("fullscreenchange", () => window.setTimeout(() => this.redimensionar(), 60));

    this.visivel = true;
    this.acordar();
  }

  acao(nome, botao) {
    this.ocioso = 0;
    if (nome === "proximo") this.proxima(1);
    else if (nome === "anterior") this.proxima(-1);
    else if (nome === "visao") this.soltarSelecao();
    else if (nome === "tour") {
      this.tour = !this.tour;
      this.tourTempo = 0;
      botao.setAttribute("aria-pressed", this.tour ? "true" : "false");
      botao.querySelector("i").className = this.tour ? "fa-solid fa-pause" : "fa-solid fa-play";
      if (this.tour) this.proxima(1);
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
    this.camera.fov = this.camera.aspect < 0.8 ? 56 : 42;
    this.camera.updateProjectionMatrix();
    if (this.areas && (this.camera.aspect < 0.9) !== this.empilhar) {
      this.montar();
      if (!this.selecionada) this.camera3d.visaoGeral();
    }
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
    this.andarFila();

    if (this.tour) {
      this.tourTempo += dt;
      if (this.tourTempo > 6) {
        this.tourTempo = 0;
        this.proxima(1);
      }
    }

    this.camera3d.atualizar(dt);
    const cam = this.camera.position;
    const sel = this.selecionada;
    const paraSel = this.paraSel || (this.paraSel = new this.T.Vector3());
    const paraM = this.paraM || (this.paraM = new this.T.Vector3());
    let distSel = 0;
    if (sel) {
      paraSel.subVectors(sel.grupo.position, cam);
      distSel = paraSel.length();
      paraSel.normalize();
    }
    for (const m of this.maquinas) {
      if (!m.grupo.visible) continue;
      const perto = m === sel || cam.distanceToSquared(m.grupo.position) < 81;
      // com uma máquina escolhida, a que estiver na frente dela, no caminho
      // do olhar, some -- nada tampa a escolhida
      m.encoberta = false;
      if (sel && m !== sel) {
        paraM.subVectors(m.grupo.position, cam);
        const d = paraM.length();
        if (d < distSel - 0.5 && paraM.normalize().dot(paraSel) > 0.82) m.encoberta = true;
      }
      m.atualizar(this.camera, dt, perto);
    }
    this.posicionarRotulo();
    this.renderer.render(this.cena, this.camera);
  }

  /** O nome da máquina em cima dela: a escolhida, ou a do mouse. */
  posicionarRotulo() {
    const m = this.sobre || this.selecionada;
    if (!m || !m.grupo.visible) {
      this.rotulo.hidden = true;
      return;
    }
    const v = this.vetor || (this.vetor = new this.T.Vector3());
    v.copy(m.grupo.position);
    v.y = (m.painel.visible ? m.painel.scale.y : m.altura) + 0.25;
    v.project(this.camera);
    if (v.z > 1) {
      this.rotulo.hidden = true;
      return;
    }
    const w = this.palco.clientWidth;
    const h = this.palco.clientHeight;
    if (this.rotulo.textContent !== m.dados.nome) this.rotulo.textContent = m.dados.nome;
    this.rotulo.hidden = false;
    this.rotulo.style.transform = `translate(${Math.round((v.x + 1) / 2 * w)}px, ${Math.round((1 - v.y) / 2 * h)}px) translate(-50%, -100%)`;
  }

  /** A máquina sob o ponteiro (coordenadas de tela). */
  escolher(x, y) {
    const r = this.canvas.getBoundingClientRect();
    this.ponteiro.set(((x - r.left) / r.width) * 2 - 1, -((y - r.top) / r.height) * 2 + 1);
    this.raycaster.setFromCamera(this.ponteiro, this.camera);
    const alvos = [];
    this.maquinas.forEach((m) => {
      if (!m.grupo.visible) return;
      if (m.painel.visible) alvos.push(m.painel);
      if (m.quadro.visible) alvos.push(m.quadro);
    });
    const acerto = this.raycaster.intersectObjects(alvos, false)[0];
    return acerto ? acerto.object.userData.maquina : null;
  }
}

/* ======================================================================
   A CÂMERA — órbita própria, com voo suave até a máquina escolhida
   ====================================================================== */
class Camera {
  constructor(arena) {
    this.arena = arena;
    this.alvo = new arena.T.Vector3(0, 1, -3);
    this.alvoDesejado = this.alvo.clone();
    this.theta = 0;
    this.phi = 1.0;
    this.raio = 40;
    this.thetaDesejado = 0;
    this.phiDesejado = 1.0;
    this.raioDesejado = 30;
    this.ponteiros = new Map();
  }

  /** A arena inteira na tela. */
  visaoGeral(entrada = false) {
    const limites = this.arena.limites || { largura: 10, fundo: 6 };
    // em pé, o centro do olhar vem um pouco para a frente: a área da frente
    // não fica atrás dos controles do pé do palco
    this.alvoDesejado.set(0, 1.2, -limites.fundo / 2 + (this.arena.empilhar ? 3 : 0));
    const camera = this.arena.camera;
    const aspecto = camera.aspect || 1.6;
    const fov = (camera.fov * PI) / 180;
    // distância para caber a largura (e o fundo) da arena
    const largura = limites.largura + 4;
    const pelaLargura = largura / 2 / Math.tan(fov / 2) / aspecto;
    const peloFundo = (limites.fundo + 4) / 2 / Math.tan(fov / 2);
    this.raioDesejado = Math.min(140, Math.max(9, pelaLargura, peloFundo) * 1.18);
    this.phiDesejado = this.arena.empilhar ? 0.62 : 0.95;
    let delta = 0 - this.thetaDesejado;
    delta = Math.atan2(Math.sin(delta), Math.cos(delta));
    this.thetaDesejado += delta;
    if (entrada && !this.arena.reduzido) {
      this.raio = this.raioDesejado * 1.6;
      this.phi = 0.6;
    }
  }

  olharArea(area) {
    const camera = this.arena.camera;
    const fov = (camera.fov * PI) / 180;
    const aspecto = camera.aspect || 1.6;
    this.alvoDesejado.set(area.centro.x, 1.2, area.centro.z);
    const pelaLargura = (area.largura + 3) / 2 / Math.tan(fov / 2) / aspecto;
    const peloFundo = (area.fundo + 3) / 2 / Math.tan(fov / 2);
    this.raioDesejado = Math.min(80, Math.max(7, pelaLargura, peloFundo));
    this.phiDesejado = 1.0;
    let delta = 0 - this.thetaDesejado;
    delta = Math.atan2(Math.sin(delta), Math.cos(delta));
    this.thetaDesejado += delta;
  }

  olharPara(maquina) {
    const p = maquina.grupo.position;
    this.alvoDesejado.set(p.x, maquina.altura * 0.5, p.z);
    const folga = this.arena.camera.aspect < 0.8 ? 1.45 : 1;
    this.raioDesejado = Math.min(16, Math.max(4.2, maquina.altura * 2.1 + 1.6) * folga);
    this.phiDesejado = 1.28;
    let delta = 0 - this.thetaDesejado;
    delta = Math.atan2(Math.sin(delta), Math.cos(delta));
    this.thetaDesejado += delta;
  }

  /** Gira até o lado pedido da máquina (0 frente, 1 direita, 2 costas, 3 esquerda). */
  verLado(maquina, quadrante) {
    if (this.arena.selecionada !== maquina) this.olharPara(maquina);
    const alvo = quadrante * (PI / 2);
    let delta = alvo - this.thetaDesejado;
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
        if (evento.pointerType === "mouse") {
          arena.sobre = arena.escolher(evento.clientX, evento.clientY);
          canvas.classList.toggle("sobre-maquina", Boolean(arena.sobre));
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

    canvas.addEventListener("pointerleave", () => { arena.sobre = null; });

    const soltar = (evento) => {
      this.ponteiros.delete(evento.pointerId);
      canvas.classList.remove("arrastando");
      if (this.ponteiros.size < 2) distanciaPinca = 0;
      if (!inicio) return;
      const andou = Math.hypot(evento.clientX - inicio.x, evento.clientY - inicio.y);
      const rapido = performance.now() - inicio.t < 450;
      inicio = null;
      if (andou < 8 && rapido && evento.type === "pointerup") {
        const maquina = arena.escolher(evento.clientX, evento.clientY);
        if (maquina) arena.selecionar(maquina);
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
    this.phiDesejado = Math.min(1.45, Math.max(0.35, this.phiDesejado));
    this.raioDesejado = Math.min(130, Math.max(2.8, this.raioDesejado));
  }

  atualizar(dt) {
    const arena = this.arena;
    // ninguém mexendo há um tempo, com uma máquina escolhida: a câmera dá
    // a volta nela devagar e as fotos de cada lado aparecem
    if (!arena.reduzido && arena.selecionada && arena.ocioso > 3.5 && this.ponteiros.size === 0) {
      this.thetaDesejado += dt * 0.35;
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
