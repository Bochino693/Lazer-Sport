/* ======================================================================
   ARENA 3D — a roda das máquinas da fábrica, cada uma feita das fotos dela.

   A CENA É A DE SEMPRE: as máquinas em estandes (pedestal com anel de
   luz), em roda e de frente para o centro, onde gira o alvo da marca;
   pilares de luz em volta, estrelas no céu e a câmera que voa até a
   máquina escolhida. As áreas da arena (jogos da Lazer & Sport, as
   máquinas que já fazíamos, trampolins e brinquedões) são trechos da
   roda, cada um com a sua cor no piso e a sua placa; os botões de área e
   o filtro de categoria refazem a roda só com aquelas máquinas.

   CADA MÁQUINA É UM OBJETO 3D FEITO DAS FOTOS DELA. O catálogo tem até
   quatro fotos (frente, lado direito, costas, lado esquerdo):

     1. RECORTE: a máquina sai do fundo da foto (PNG transparente vale
        como está; fundo liso é apagado a partir das bordas).
     2. VOLUME: em cada altura, a largura vem da silhueta da frente e a
        profundidade da silhueta do lado -- o casco que as duas fotos
        cruzadas desenham. Sem foto de lado, a profundidade é a do
        cadastro e a forma é a da frente.
     3. PELE: cada face veste a sua foto (a frente na frente, as costas
        atrás, cada lado no seu lado), esticada fatia a fatia até a beira
        do casco. Lado sem foto pega a cor da beira da frente; costas sem
        foto viram o painel traseiro do gabinete; embaixo fica a base.

   DÁ PARA VER DE TODOS OS LADOS: o prato do estande gira (Frente,
   Direita, Costas, Esquerda), a câmera sobe (Cima) e a máquina levanta e
   tomba para mostrar a base (Baixo). Arrastar gira a câmera em volta.

   Foto que não dá para recortar (fundo complicado) vira um painel em pé
   com a foto inteira. Foto vazada (a rede de uma cama elástica) vira duas
   placas cruzadas, para continuar vazada.

   A FICHA FICA FORA DO PALCO: ao lado no computador, embaixo no celular.

   O QUE ESTE ARQUIVO NÃO FAZ: baixar o three.js (~170 KB) antes de o
   palco chegar perto da tela, nem num aparelho sem WebGL -- ali a lista
   de máquinas é a página.
   ====================================================================== */

const raiz = document.querySelector("[data-arena3d]");
if (raiz) iniciar(raiz);

const PI = Math.PI;
const CORES = ["#e63946", "#2f8bff", "#ffd700", "#3fd0ff", "#8a5cff", "#ff7a00", "#1fbf5b", "#ff3df2"];
const COR_DA_ZONA = { jogos: "#e63946", maquinas: "#2f8bff", brinquedoes: "#22c55e" };
const LADOS = ["perfil", "lado_direito", "verso", "lado_esquerdo"];
const NOME_DO_LADO = { perfil: "Frente", lado_direito: "Lado direito", verso: "Costas", lado_esquerdo: "Lado esquerdo" };
const VISTA_DO_LADO = { perfil: "frente", lado_direito: "direita", verso: "costas", lado_esquerdo: "esquerda" };
// o giro do prato que põe cada lado da máquina de frente para o centro
const GIRO_DA_VISTA = { frente: 0, direita: -PI / 2, costas: PI, esquerda: PI / 2, cima: 0, baixo: 0 };
const TOMBO = -1.3; // "Baixo": a máquina tomba para a frente e mostra a base
const LINHAS = 40; // fatias do casco, de baixo para cima

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
 * para o painel em pé. `null` se a foto não pode ser lida (sem CORS).
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

    // Os vãos fechados também são fundo: os quadrados da rede de uma cama
    // elástica, o meio de um aro, o espaço entre as pernas com travessa.
    // Só manchas grandes e bem da cor do fundo -- um adesivo branco fica.
    const minimo = Math.max(30, n * 0.0015);
    const mancha = new Int32Array(n);
    for (let semente = 0; semente < n; semente++) {
      if (fundo[semente] || distancia(p, semente * 4, r0, g0, b0) >= 36) continue;
      let a = 0;
      let b = 0;
      mancha[b++] = semente;
      fundo[semente] = 2;
      while (a < b) {
        const i = mancha[a++];
        const x = i % w;
        const vizinhos = [x > 0 ? i - 1 : -1, x < w - 1 ? i + 1 : -1, i - w, i + w];
        for (const v of vizinhos) {
          if (v < 0 || v >= n || fundo[v] || distancia(p, v * 4, r0, g0, b0) >= 36) continue;
          fundo[v] = 2;
          mancha[b++] = v;
        }
      }
      // mancha pequena volta a ser máquina
      const valor = b >= minimo ? 1 : 3;
      for (let k = 0; k < b; k++) fundo[mancha[k]] = valor;
    }
    for (let i = 0; i < n; i++) if (fundo[i] === 3) fundo[i] = 0;
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
   DA FOTO AO VOLUME
   ====================================================================== */

/**
 * A silhueta da foto recortada, fatia a fatia de baixo para cima: onde a
 * máquina começa e termina em cada altura, de 0 a 1 na largura da foto.
 * `cheio` é quanto do retângulo a máquina ocupa (rede e grade dão pouco).
 */
function silhueta(tela) {
  const w = tela.width;
  const h = tela.height;
  const p = tela.getContext("2d", { willReadFrequently: true }).getImageData(0, 0, w, h).data;
  const esq = new Float32Array(LINHAS + 1);
  const dir = new Float32Array(LINHAS + 1);
  const achou = new Uint8Array(LINHAS + 1);
  const colunas = new Uint32Array(w);
  const meia = Math.max(1, h / LINHAS / 2);
  let cheios = 0;
  for (let i = 3; i < p.length; i += 4) if (p[i] > 127) cheios++;

  for (let k = 0; k <= LINHAS; k++) {
    const centro = (1 - k / LINHAS) * (h - 1);
    const y0 = Math.max(0, Math.floor(centro - meia));
    const y1 = Math.min(h - 1, Math.ceil(centro + meia));
    colunas.fill(0);
    let total = 0;
    for (let y = y0; y <= y1; y++) {
      let i = y * w * 4 + 3;
      for (let x = 0; x < w; x++, i += 4) {
        if (p[i] > 127) {
          colunas[x]++;
          total++;
        }
      }
    }
    if (!total) continue;
    // 2% de cada lado ficam de fora: um fio solto não alarga a máquina
    let soma = 0;
    let a = -1;
    let b = w - 1;
    for (let x = 0; x < w; x++) {
      soma += colunas[x];
      if (a < 0 && soma > total * 0.02) a = x;
      if (soma >= total * 0.98) {
        b = x;
        break;
      }
    }
    esq[k] = Math.max(0, a) / w;
    dir[k] = (b + 1) / w;
    achou[k] = 1;
  }

  [esq, dir].forEach((lista) => {
    // altura sem nada (um vão no meio): as fatias vizinhas cobrem
    for (let k = 0; k <= LINHAS; k++) {
      if (achou[k]) continue;
      let baixo = k - 1;
      while (baixo >= 0 && !achou[baixo]) baixo--;
      let cima = k + 1;
      while (cima <= LINHAS && !achou[cima]) cima++;
      if (baixo < 0 && cima > LINHAS) lista[k] = lista === esq ? 0 : 1;
      else if (baixo < 0) lista[k] = lista[cima];
      else if (cima > LINHAS) lista[k] = lista[baixo];
      else lista[k] = lista[baixo] + (lista[cima] - lista[baixo]) * ((k - baixo) / (cima - baixo));
    }
    // mediana de três: um degrau de um pixel não vira dente no casco
    const copia = Float32Array.from(lista);
    for (let k = 1; k < LINHAS; k++) {
      const [x, y, z] = [copia[k - 1], copia[k], copia[k + 1]];
      lista[k] = Math.max(Math.min(x, y), Math.min(Math.max(x, y), z));
    }
  });
  for (let k = 0; k <= LINHAS; k++) {
    if (dir[k] - esq[k] < 0.04) {
      const meio = (dir[k] + esq[k]) / 2;
      esq[k] = Math.max(0, meio - 0.02);
      dir[k] = Math.min(1, meio + 0.02);
    }
  }
  return { esq, dir, cheio: cheios / (w * h), aspecto: w / h };
}

/** A cor média da máquina na foto (o fundo transparente não conta). */
function corMedia(tela) {
  const mini = document.createElement("canvas");
  mini.width = mini.height = 16;
  const g = mini.getContext("2d", { willReadFrequently: true });
  g.drawImage(tela, 0, 0, 16, 16);
  const p = g.getImageData(0, 0, 16, 16).data;
  let r = 0;
  let v = 0;
  let b = 0;
  let peso = 0;
  for (let i = 0; i < p.length; i += 4) {
    r += p[i] * p[i + 3];
    v += p[i + 1] * p[i + 3];
    b += p[i + 2] * p[i + 3];
    peso += p[i + 3];
  }
  return peso ? [r / peso, v / peso, b / peso].map(Math.round) : [40, 52, 90];
}

/**
 * As costas de quem não tem foto de trás: o painel traseiro pintado, com o
 * contorno da frente espelhado (de costas, a máquina tem a mesma silhueta).
 */
function costasRecortadas(frente, cor) {
  const c = document.createElement("canvas");
  c.width = frente.width;
  c.height = frente.height;
  const g = c.getContext("2d");
  g.drawImage(pintarCostas(cor), 0, 0, c.width, c.height);
  g.globalCompositeOperation = "destination-in";
  g.translate(c.width, 0);
  g.scale(-1, 1);
  g.drawImage(frente, 0, 0);
  return c;
}

/** As costas de um gabinete sem foto de trás: porta de serviço, grade e a plaqueta. */
function pintarCostas(cor) {
  const c = document.createElement("canvas");
  c.width = 256;
  c.height = 512;
  const g = c.getContext("2d");
  const escuro = cor.map((v) => Math.round(v * 0.42 + 10));
  const grad = g.createLinearGradient(0, 0, 0, 512);
  grad.addColorStop(0, `rgb(${escuro.map((v) => Math.min(255, v + 22)).join(",")})`);
  grad.addColorStop(1, `rgb(${escuro.join(",")})`);
  g.fillStyle = grad;
  g.fillRect(0, 0, 256, 512);
  g.strokeStyle = "rgba(0, 0, 0, .4)";
  g.lineWidth = 4;
  g.strokeRect(36, 140, 184, 320);
  g.fillStyle = "rgba(0, 0, 0, .45)";
  for (let y = 360; y < 440; y += 13) g.fillRect(66, y, 124, 5);
  g.fillStyle = "rgba(255, 255, 255, .9)";
  g.fillRect(70, 52, 116, 36);
  g.fillStyle = "#071433";
  g.font = "900 15px Poppins, Manrope, sans-serif";
  g.textAlign = "center";
  g.textBaseline = "middle";
  g.fillText("LAZER & SPORT", 128, 71);
  return c;
}

/**
 * O casco: em cada fatia de altura, um retângulo -- de x0 a x1 (a
 * silhueta da frente) e de zb a zf (a silhueta do lado). As paredes ligam
 * uma fatia à de cima, e cada parede leva a coordenada da sua foto na
 * mesma altura: a foto encosta na beira do casco em toda a volta.
 *
 * `uv.<face>[k]` = [u na beira esquerda, u na beira direita] de quem olha
 * aquela face de fora. Grupos de material: 0 frente, 1 costas, 2 direita,
 * 3 esquerda, 4 topo, 5 base.
 */
function montarCasco(T, { y, x0, x1, zf, zb, uv }) {
  const posicoes = [];
  const coords = [];
  const cores = [];
  const geometria = new T.BufferGeometry();
  const L = y.length - 1;
  const alto = y[L] - y[0];
  let inicio = 0;
  const fechar = (material) => {
    const n = posicoes.length / 3;
    geometria.addGroup(inicio, n - inicio, material);
    inicio = n;
  };
  const ponto = (x, yy, z, u, v, luz) => {
    posicoes.push(x, yy, z);
    coords.push(u, v);
    // o pé da máquina um pouco mais escuro: parece apoiada, não flutuando
    const tom = luz * (0.72 + 0.28 * Math.min(1, (yy - y[0]) / Math.max(0.3, alto * 0.18)));
    cores.push(tom, tom, tom);
  };
  // A e B embaixo, C e D em cima; esquerda e direita de quem olha a face
  const quad = (A, B, C, D, luz) => {
    ponto(...A, luz); ponto(...B, luz); ponto(...D, luz);
    ponto(...A, luz); ponto(...D, luz); ponto(...C, luz);
  };
  const v = (k) => k / L;

  for (let k = 0; k < L; k++) {
    const [a0, b0] = uv.frente[k];
    const [a1, b1] = uv.frente[k + 1];
    quad([x0[k], y[k], zf[k], a0, v(k)], [x1[k], y[k], zf[k], b0, v(k)],
      [x0[k + 1], y[k + 1], zf[k + 1], a1, v(k + 1)], [x1[k + 1], y[k + 1], zf[k + 1], b1, v(k + 1)], 1);
  }
  fechar(0);
  // de costas, o +X fica à esquerda de quem olha
  for (let k = 0; k < L; k++) {
    const [a0, b0] = uv.costas[k];
    const [a1, b1] = uv.costas[k + 1];
    quad([x1[k], y[k], zb[k], a0, v(k)], [x0[k], y[k], zb[k], b0, v(k)],
      [x1[k + 1], y[k + 1], zb[k + 1], a1, v(k + 1)], [x0[k + 1], y[k + 1], zb[k + 1], b1, v(k + 1)], 0.8);
  }
  fechar(1);
  // do lado direito, a frente fica à esquerda de quem olha
  for (let k = 0; k < L; k++) {
    const [a0, b0] = uv.direita[k];
    const [a1, b1] = uv.direita[k + 1];
    quad([x1[k], y[k], zf[k], a0, v(k)], [x1[k], y[k], zb[k], b0, v(k)],
      [x1[k + 1], y[k + 1], zf[k + 1], a1, v(k + 1)], [x1[k + 1], y[k + 1], zb[k + 1], b1, v(k + 1)], 0.66);
  }
  fechar(2);
  // do lado esquerdo, a frente fica à direita
  for (let k = 0; k < L; k++) {
    const [a0, b0] = uv.esquerda[k];
    const [a1, b1] = uv.esquerda[k + 1];
    quad([x0[k], y[k], zb[k], a0, v(k)], [x0[k], y[k], zf[k], b0, v(k)],
      [x0[k + 1], y[k + 1], zb[k + 1], a1, v(k + 1)], [x0[k + 1], y[k + 1], zf[k + 1], b1, v(k + 1)], 0.66);
  }
  fechar(3);
  const [u0, u1, vt] = uv.topo;
  quad([x0[L], y[L], zf[L], u0, vt], [x1[L], y[L], zf[L], u1, vt], [x0[L], y[L], zb[L], u0, vt], [x1[L], y[L], zb[L], u1, vt], 1.15);
  fechar(4);
  quad([x0[0], y[0], zb[0], 0, 0], [x1[0], y[0], zb[0], 1, 0], [x0[0], y[0], zf[0], 0, 1], [x1[0], y[0], zf[0], 1, 1], 1.4);
  fechar(5);

  geometria.setAttribute("position", new T.Float32BufferAttribute(posicoes, 3));
  geometria.setAttribute("uv", new T.Float32BufferAttribute(coords, 2));
  geometria.setAttribute("color", new T.Float32BufferAttribute(cores, 3));
  geometria.computeBoundingSphere();
  return geometria;
}

/* ======================================================================
   UMA MÁQUINA — o estande e o objeto feito das fotos
   ====================================================================== */

/** As fotos de cada lado (lado -> URL); a capa vale como frente. */
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

    const [altura, largura, fundo] = (dados.medidas || []).map(Number);
    this.altura = limitar(altura || 1.8, 0.6, 4.5);
    this.largura = limitar(largura || 1, 0.4, 4.5);
    this.fundo = limitar(fundo || 1, 0.3, 4.5);
    this.raioP = Math.max(this.largura, this.fundo) * 0.62 + 0.45;
    this.alturaP = 0.3;
    // o objeto montado (até a foto chegar, o tamanho do cadastro)
    this.H = this.altura;
    this.D = this.fundo;
    this.pedido = 0;
    this.montada = 0;
    this.girando = false;
    this.giroAlvo = 0;
    this.tombo = 0;
    this.tomboAlvo = 0;
    this.descartaveis = [];

    const grupo = new T.Group();
    this.grupo = grupo;
    arena.cilindro(grupo, this.raioP, this.alturaP, arena.escuro(), 0, this.alturaP / 2, 0, 48);
    this.aro = arena.anel(grupo, this.raioP + 0.02, 0.045, arena.luz(this.cor, 2.2), 0, this.alturaP, 0);
    this.aro.rotation.x = PI / 2;
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

  get temFoto() {
    return Object.keys(this.fotos).length > 0;
  }

  /** Tudo do estande responde ao toque como a máquina. */
  marcar() {
    this.grupo.traverse((obj) => { obj.userData.maquina = this; });
  }

  ajustarPivo() {
    this.pivo.position.y = this.H / 2;
    this.corpo.position.y = -this.H / 2;
  }

  /** Baixa e recorta as fotos no tamanho pedido (uma vez por tamanho). */
  pedir(tamanho) {
    if (this.pedido >= tamanho || !this.temFoto) return;
    this.pedido = tamanho;
    this.arena.fila.push(() => this.carregar(tamanho));
  }

  async carregar(tamanho) {
    const lados = LADOS.filter((lado) => this.fotos[lado]);
    const prontas = await Promise.all(lados.map(async (lado) => {
      try {
        const img = await carregarImagem(fotoNaLargura(this.fotos[lado], tamanho));
        const recorte = recortar(img, tamanho);
        return recorte ? [lado, recorte] : null;
      } catch (erro) {
        return null;
      }
    }));
    const fotos = {};
    prontas.forEach((par) => { if (par) fotos[par[0]] = par[1]; });
    if (!fotos.perfil) {
      // sem a frente, a primeira foto que chegou faz o papel dela
      const outra = LADOS.find((lado) => fotos[lado]);
      if (!outra) {
        if (!this.montada) this.semFoto = true;
        return;
      }
      fotos.perfil = fotos[outra];
      delete fotos[outra];
    }
    if (tamanho < this.montada) return;
    this.montar(fotos);
    this.montada = tamanho;
  }

  limpar() {
    this.corpo.children.slice().forEach((filho) => this.corpo.remove(filho));
    this.descartaveis.forEach((item) => item.dispose());
    this.descartaveis = [];
  }

  textura(tela) {
    const T = this.arena.T;
    const textura = new T.CanvasTexture(tela);
    textura.colorSpace = T.SRGBColorSpace;
    textura.anisotropy = this.arena.anisotropia;
    this.descartaveis.push(textura);
    return textura;
  }

  material(opcoes) {
    const material = new this.arena.T.MeshBasicMaterial({ toneMapped: false, ...opcoes });
    this.descartaveis.push(material);
    return material;
  }

  montar(fotos) {
    this.limpar();
    const frente = fotos.perfil;
    if (!frente.recortada) this.montarPainel(frente);
    else {
      const forma = silhueta(frente.tela);
      if (forma.cheio < 0.4) this.montarVazado(frente, fotos);
      else this.montarCasco(frente, forma, fotos);
    }
    this.sombra.scale.set(Math.max(0.5, this.W) * 0.8, Math.max(0.5, this.D) * 0.8, 1);
    this.ajustarPivo();
    this.marcar();
  }

  /** Grande demais para o pedestal: encolhe por inteiro (nunca deforma). */
  caber(W, D) {
    const meiaDiagonal = Math.hypot(W, D) / 2;
    return Math.min(1, (this.raioP * 1.08) / meiaDiagonal);
  }

  montarCasco(frente, forma, fotos) {
    const T = this.arena.T;
    const lados = {};
    ["lado_direito", "lado_esquerdo", "verso"].forEach((lado) => {
      if (fotos[lado] && fotos[lado].recortada) lados[lado] = silhueta(fotos[lado].tela);
    });
    let H = this.altura;
    let W = limitar(H * forma.aspecto, 0.3, 5);
    // a profundidade é a das fotos de lado (na escala da altura) ou a do cadastro
    const deLado = [lados.lado_direito, lados.lado_esquerdo].filter(Boolean);
    let D = deLado.length ? deLado.reduce((soma, s) => soma + H * s.aspecto, 0) / deLado.length : this.fundo;
    D = limitar(D, 0.25, 5);
    const escala = this.caber(W, D);
    H *= escala;
    W *= escala;
    D *= escala;

    const y = [];
    const x0 = [];
    const x1 = [];
    const zf = [];
    const zb = [];
    const uv = { frente: [], costas: [], direita: [], esquerda: [] };
    const beira = 0.006; // um fio para dentro da beira da frente
    const ld = lados.lado_direito;
    const le = lados.lado_esquerdo;
    const lv = lados.verso;
    for (let k = 0; k <= LINHAS; k++) {
      y.push((H * k) / LINHAS);
      x0.push(-W / 2 + forma.esq[k] * W);
      x1.push(-W / 2 + forma.dir[k] * W);
      let f = 0;
      let b = 0;
      // foto do lado direito: a frente da máquina fica à esquerda da foto
      if (ld) { f += D / 2 - ld.esq[k] * D; b += D / 2 - ld.dir[k] * D; }
      if (le) { f += -D / 2 + le.dir[k] * D; b += -D / 2 + le.esq[k] * D; }
      if (deLado.length) { f /= deLado.length; b /= deLado.length; } else { f = D / 2; b = -D / 2; }
      if (f - b < 0.06) {
        const meio = (f + b) / 2;
        f = meio + 0.03;
        b = meio - 0.03;
      }
      zf.push(f);
      zb.push(b);
      uv.frente.push([forma.esq[k], forma.dir[k]]);
      uv.costas.push(lv ? [lv.esq[k], lv.dir[k]] : [0, 1]);
      uv.direita.push(ld ? [ld.esq[k], ld.dir[k]] : [forma.dir[k] - beira, forma.dir[k] - beira]);
      uv.esquerda.push(le ? [le.esq[k], le.dir[k]] : [forma.esq[k] + beira, forma.esq[k] + beira]);
    }
    uv.topo = [forma.esq[LINHAS], forma.dir[LINHAS], 0.985];

    // Cada face é a foto recortada: onde a foto é vazada (entre as pernas,
    // no vão de um aro) a face também é, e o que se vê lá dentro é o
    // avesso escuro das outras faces -- como o interior de um gabinete.
    const cor = corMedia(frente.tela);
    const texFrente = this.textura(frente.tela);
    const texturas = [
      texFrente,
      this.textura(lv ? fotos.verso.tela : costasRecortadas(frente.tela, cor)),
      ld ? this.textura(fotos.lado_direito.tela) : texFrente,
      le ? this.textura(fotos.lado_esquerdo.tela) : texFrente,
      texFrente,
    ];
    const unicos = new Map();
    const pele = (textura, lado) => {
      const chave = textura.uuid + lado;
      if (!unicos.has(chave)) {
        unicos.set(chave, this.material(lado === "fora"
          ? { map: textura, alphaTest: 0.5, vertexColors: true }
          : { map: textura, alphaTest: 0.5, color: "#2b3140", side: T.BackSide }));
      }
      return unicos.get(chave);
    };
    const geometria = montarCasco(T, { y, x0, x1, zf, zb, uv });
    this.descartaveis.push(geometria);
    this.corpo.add(new T.Mesh(geometria, [...texturas.map((t) => pele(t, "fora")), this.arena.matBase()]));
    this.corpo.add(new T.Mesh(geometria, [...texturas.map((t) => pele(t, "dentro")), this.arena.matBaseDentro()]));
    // os pés de borracha nos cantos da base (aparecem na vista de baixo)
    const pe = Math.min(0.09, (x1[0] - x0[0]) * 0.12, (zf[0] - zb[0]) * 0.12);
    [[x0[0], zf[0]], [x1[0], zf[0]], [x0[0], zb[0]], [x1[0], zb[0]]].forEach(([x, z]) => {
      this.arena.cilindro(this.corpo, pe, 0.05, this.arena.borracha(), x - Math.sign(x) * pe * 1.6, -0.025, z - Math.sign(z) * pe * 1.6, 12);
    });
    this.H = H;
    this.W = W;
    this.D = Math.max(...zf) - Math.min(...zb);
  }

  /** Foto de fundo complicado: um painel em pé com a foto inteira na frente. */
  montarPainel(frente) {
    const T = this.arena.T;
    const pe = 0.35;
    let H = limitar(this.altura, 1.3, 2.4);
    let W = limitar(H * frente.aspecto, 0.6, 3.2);
    const escala = this.caber(W, 0.3);
    H *= escala;
    W *= escala;
    const y = [];
    const lista = (valor) => Array.from({ length: LINHAS + 1 }, () => valor);
    for (let k = 0; k <= LINHAS; k++) y.push(pe + (H * k) / LINHAS);
    const cor = corMedia(frente.tela);
    const matFoto = this.material({ map: this.textura(frente.tela), vertexColors: true });
    const geometria = montarCasco(T, {
      y,
      x0: lista(-W / 2),
      x1: lista(W / 2),
      zf: lista(0.07),
      zb: lista(-0.07),
      uv: {
        frente: lista([0, 1]),
        costas: lista([0, 1]),
        direita: lista([0.995, 0.995]),
        esquerda: lista([0.005, 0.005]),
        topo: [0, 1, 0.99],
      },
    });
    this.descartaveis.push(geometria);
    const materiais = [matFoto, this.material({ map: this.textura(pintarCostas(cor)), vertexColors: true }), matFoto, matFoto, matFoto, this.arena.matBase()];
    this.corpo.add(new T.Mesh(geometria, materiais));
    this.arena.caixa(this.corpo, Math.min(0.5, W * 0.4), pe, 0.3, this.arena.escuro(), 0, pe / 2, 0);
    this.H = H + pe;
    this.W = W;
    this.D = 0.3;
  }

  /** Foto vazada (rede, grade): duas placas cruzadas, a frente e o lado. */
  montarVazado(frente, fotos) {
    const T = this.arena.T;
    const lado = [fotos.lado_direito, fotos.lado_esquerdo].find((f) => f && f.recortada);
    let H = this.altura;
    let W = limitar(H * frente.aspecto, 0.4, 5);
    let D = lado ? limitar(H * lado.aspecto, 0.3, 5) : limitar(this.fundo, 0.3, 5);
    const escala = this.caber(W, D);
    H *= escala;
    W *= escala;
    D *= escala;
    const plano = this.arena.geo("plano", () => new T.PlaneGeometry(1, 1));
    const placa = (foto, largura, giro) => {
      const malha = new T.Mesh(plano, this.material({ map: this.textura(foto.tela), alphaTest: 0.5, side: T.DoubleSide }));
      malha.scale.set(largura, H, 1);
      malha.position.y = H / 2;
      malha.rotation.y = giro;
      this.corpo.add(malha);
    };
    placa(frente, W, 0);
    placa(lado || frente, D, -PI / 2);
    this.H = H;
    this.W = W;
    this.D = D;
  }

  /** O centro do que a câmera deve olhar, já com o "levantar" da vista de baixo. */
  centro(alvo) {
    this.grupo.getWorldPosition(alvo);
    alvo.y = this.alturaP + this.pivo.position.y;
    return alvo;
  }

  atualizar(dt, reduzido) {
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
    this.limite = this.celular ? 10 : 16; // máquinas por "rodada" da roda
    this.fotoLonge = 384;
    this.fotoPerto = this.celular ? 768 : 1024;
    this.pagina = 0;
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
    this.canvas.setAttribute("aria-label", "Arena 3D com as máquinas da Lazer & Sport, montadas com as fotos reais. Arraste para girar e toque numa máquina para ver a ficha.");
    palco.prepend(this.canvas);

    const densidade = Math.min(window.devicePixelRatio || 1, this.celular ? 1.5 : 1.75);
    this.renderer = new T.WebGLRenderer({ canvas: this.canvas, antialias: densidade < 2, powerPreference: "high-performance" });
    this.renderer.setPixelRatio(densidade);
    this.renderer.toneMapping = T.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.15;
    this.renderer.outputColorSpace = T.SRGBColorSpace;
    this.anisotropia = Math.min(4, this.renderer.capabilities.getMaxAnisotropy());

    this.cena = new T.Scene();
    this.cena.background = new T.Color("#040a1c");
    this.cena.fog = new T.Fog("#040a1c", 30, 90);
    this.camera = new T.PerspectiveCamera(45, 1, 0.1, 220);
    this.camera.position.set(0, 12, 28);
    this.raycaster = new T.Raycaster();
    this.ponteiro = new T.Vector2();
    this.ajuda = new T.Vector3();

    this.montarLuzes();
    this.montarPiso();
    this.montarCentro();
    this.montarCeu();
    this.decoracao = new T.Group();
    this.cena.add(this.decoracao);

    // sem foto não há de onde montar o objeto: a máquina fica só na lista
    this.maquinas = (dados.maquinas || [])
      .map((d, i) => (Object.keys(fotosDe(d)).length ? new Maquina(this, d, i) : null))
      .filter(Boolean);
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

  borracha() {
    return this.mat("borracha", () => new this.T.MeshStandardMaterial({ color: "#05070c", roughness: 0.9 }));
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
      return new this.T.MeshBasicMaterial({ map: new this.T.CanvasTexture(tela), transparent: true, depthWrite: false });
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
    textura.anisotropy = this.anisotropia;
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

  montarCeu() {
    const T = this.T;
    // estrelas e faíscas: pontos aditivos, uma chamada de desenho só
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
    this.piso.scale.setScalar(Math.max(36, raio + 10));
  }

  /* ---------- a roda ---------- */
  filtradas() {
    const ordem = (id) => {
      const i = this.zonas.findIndex((z) => z.id === id);
      return i < 0 ? 99 : i;
    };
    return this.maquinas
      .filter((m) => (!this.zona || m.dados.grupo === this.zona)
        && (!this.categoria || (m.dados.categorias || []).includes(this.categoria)))
      .sort((a, b) => ordem(a.dados.grupo) - ordem(b.dados.grupo) || a.indice - b.indice);
  }

  limparDecoracao() {
    this.decoracao.children.slice().forEach((filho) => {
      this.decoracao.remove(filho);
      filho.traverse((obj) => {
        if (obj.material && obj.material.map) obj.material.map.dispose();
        if (obj.material) obj.material.dispose();
        if (obj.geometry && obj.geometry !== this.geometrias.get("plano")) obj.geometry.dispose();
      });
    });
  }

  montar({ entrada = false } = {}) {
    this.lista = this.filtradas();
    const paginas = Math.max(1, Math.ceil(this.lista.length / this.limite));
    this.pagina = Math.min(this.pagina, paginas - 1);
    const inicio = this.pagina * this.limite;
    const roda = this.lista.slice(inicio, inicio + this.limite);
    this.roda = roda;
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
    trechos.forEach((trecho) => this.marcarArea(trecho, raio, folga));
    this.montarPilares(raio + folga + 4.5);
    this.cena.fog.near = raio * 2.2;
    this.cena.fog.far = raio * 5 + 30;
    if (this.selecionada && !roda.includes(this.selecionada)) this.soltarSelecao({ voar: false });
    this.camera3d.visaoGeral(entrada);
    roda.forEach((m) => m.pedir(this.fotoLonge));
    this.marcarLista();
    this.mostrarRodada(paginas);
  }

  /** O trecho de uma área no piso da roda, na cor dela, com a placa. */
  marcarArea(trecho, raio, folga) {
    const T = this.T;
    const cor = COR_DA_ZONA[trecho.id] || "#2f8bff";
    const arco = (dentro, fora, opacidade) => {
      const malha = new T.Mesh(
        new T.RingGeometry(dentro, fora, 72, 1, trecho.a0 - PI / 2, trecho.a1 - trecho.a0),
        new T.MeshBasicMaterial({ color: cor, transparent: true, opacity: opacidade, depthWrite: false, toneMapped: false }),
      );
      malha.rotation.x = -PI / 2;
      malha.position.y = 0.015;
      this.decoracao.add(malha);
    };
    arco(raio - folga - 0.9, raio + folga + 0.6, 0.14);
    arco(raio - folga - 0.9, raio - folga - 0.8, 0.9);
    arco(raio + folga + 0.5, raio + folga + 0.6, 0.9);

    const zona = this.zonas.find((z) => z.id === trecho.id);
    if (!zona) return;
    const meio = (trecho.a0 + trecho.a1) / 2;
    const r = raio - folga - 2.1;
    const suporte = new T.Group();
    suporte.position.set(Math.sin(meio) * r, 0, Math.cos(meio) * r);
    suporte.rotation.y = meio + PI;
    const largura = Math.min(4.2, Math.max(2.6, (trecho.a1 - trecho.a0) * r * 0.8));
    const placa = new T.Mesh(this.geo("plano", () => new T.PlaneGeometry(1, 1)), this.materialDeTexto([zona.kicker || "", zona.titulo], cor));
    placa.scale.set(largura, largura / 4, 1);
    placa.position.y = 0.32;
    placa.rotation.x = -1.05;
    suporte.add(placa);
    this.decoracao.add(suporte);
  }

  mostrarRodada(paginas) {
    const rotulo = this.palco.querySelector("[data-arena-rodada]");
    if (!rotulo) return;
    rotulo.hidden = paginas < 2;
    rotulo.textContent = `${this.pagina + 1}/${paginas}`;
    rotulo.title = `Rodada ${this.pagina + 1} de ${paginas}: as setas passam para as outras máquinas`;
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
    const prontas = this.roda.filter((m) => m.montada || m.semFoto).length;
    if (prontas >= Math.min(this.roda.length, 3)) this.esconderAviso();
  }

  esconderAviso() {
    if (this.avisoSumiu) return;
    this.avisoSumiu = true;
    this.palco.querySelector("[data-arena-aviso]").classList.add("sumiu");
    const dica = this.palco.querySelector("[data-arena-dica]");
    if (dica) {
      dica.hidden = false;
      window.setTimeout(() => { dica.hidden = true; }, 6000);
    }
  }

  /* ---------- escolher uma máquina ---------- */
  selecionar(maquina, { voar = true } = {}) {
    if (!maquina) return;
    if (!this.roda.includes(maquina)) {
      // está em outra rodada da roda: vai até ela primeiro
      const posicao = this.lista.indexOf(maquina);
      if (posicao >= 0 && Math.floor(posicao / this.limite) !== this.pagina) this.irPara(posicao);
      return;
    }
    if (this.selecionada && this.selecionada !== maquina) this.largar(this.selecionada);
    this.selecionada = maquina;
    this.roda.forEach((m) => { m.aro.material = this.luz(m.cor, m === maquina ? 5 : 2.2); });
    maquina.pedir(this.fotoPerto);
    this.vista("girar", { voar });
    const alvo = maquina.centro(this.ajuda);
    this.foco.position.set(alvo.x * 0.55, maquina.H + 6, alvo.z * 0.55);
    this.foco.target.position.set(alvo.x, 0, alvo.z);
    this.foco.intensity = 2.2;
    if (this.vistas) this.vistas.hidden = false;
    this.mostrarFicha(maquina);
    this.marcarLista();
  }

  /** A máquina volta ao normal no estande: de frente, em pé. */
  largar(maquina) {
    maquina.girando = false;
    maquina.giroAlvo = giroMaisPerto(maquina.prato.rotation.y, 0);
    maquina.tomboAlvo = 0;
  }

  soltarSelecao({ voar = true } = {}) {
    if (this.selecionada) this.largar(this.selecionada);
    this.selecionada = null;
    this.roda.forEach((m) => { m.aro.material = this.luz(m.cor, 2.2); });
    this.foco.intensity = 0;
    if (this.vistas) this.vistas.hidden = true;
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
    this.ocioso = 0;
    this.vistaAtual = nome;
    m.girando = nome === "girar";
    if (nome !== "girar") m.giroAlvo = giroMaisPerto(m.prato.rotation.y, GIRO_DA_VISTA[nome]);
    m.tomboAlvo = nome === "baixo" ? TOMBO : 0;
    if (voar) this.camera3d.olharPara(m, nome);
    if (this.vistas) {
      this.vistas.querySelectorAll("[data-arena-vista]").forEach((botao) => {
        botao.setAttribute("aria-pressed", botao.dataset.arenaVista === nome ? "true" : "false");
      });
    }
  }

  proxima(passo) {
    const total = this.lista.length;
    if (!total) return;
    const atual = this.selecionada ? this.lista.indexOf(this.selecionada)
      : (passo > 0 ? this.pagina * this.limite - 1 : this.pagina * this.limite);
    this.irPara((atual + passo + total) % total);
  }

  /** Vai a uma máquina pela posição na lista filtrada, trocando de rodada se preciso. */
  irPara(posicao) {
    const pagina = Math.floor(posicao / this.limite);
    if (pagina !== this.pagina) {
      this.pagina = pagina;
      this.montar();
    }
    this.selecionar(this.lista[posicao]);
  }

  escolherZona(id) {
    this.zona = id;
    this.pagina = 0;
    this.raiz.querySelectorAll("[data-arena-zona]").forEach((b) => {
      const ativo = b.dataset.arenaZona === id;
      b.classList.toggle("ativo", ativo);
      b.setAttribute("aria-pressed", ativo ? "true" : "false");
    });
    this.soltarSelecao({ voar: false });
    this.montar();
  }

  filtrar(categoria) {
    this.categoria = categoria;
    this.pagina = 0;
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

    // as faixas de aviso da máquina (câmera, arma personalizada...)
    const moldura = f.querySelector("[data-ficha-moldura]");
    const modelo = f.querySelector("[data-faixas-modelo]");
    if (moldura && modelo) {
      moldura.querySelectorAll(":scope > .ls-faixas").forEach((velha) => velha.remove());
      const avisos = b.avisos || [];
      if (avisos.length) {
        const faixas = modelo.content.firstElementChild.cloneNode(true);
        faixas.querySelectorAll("[data-aviso]").forEach((faixa) => { if (!avisos.includes(faixa.dataset.aviso)) faixa.remove(); });
        faixas.setAttribute("aria-label", [...faixas.querySelectorAll(".ls-faixa-texto")].map((t) => t.textContent).join(" e "));
        moldura.append(faixas);
      }
    }

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
    if (!this.maquinas.length) avisar(this.palco, "Nenhuma máquina com foto ainda", "Assim que as fotos entrarem no catálogo, as máquinas aparecem aqui.");
    // foto que demora não segura o aviso para sempre
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
        const botao = evento.target.closest("[data-arena-vista]");
        if (botao) this.vista(botao.dataset.arenaVista);
      });
    }

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
          // fora do filtro de agora: volta para a arena inteira
          if (categoria) categoria.value = "";
          this.categoria = "";
          this.atualizarContagem();
          this.escolherZona("");
        }
        this.irPara(this.lista.indexOf(maquina));
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
    this.andarFila();

    if (this.tour) {
      this.tourTempo += dt;
      if (this.tourTempo > 6) {
        this.tourTempo = 0;
        this.proxima(1);
      }
    }

    if (!this.reduzido) {
      this.alvoMarca.rotation.y = t * 0.6;
      this.estrelas.rotation.y = t * 0.012;
      this.luzesCor.forEach((l, i) => l.position.set(Math.sin(t * 0.4 + i * PI) * 7, 7, Math.cos(t * 0.4 + i * PI) * 7));
      if (this.pilares) {
        this.pilares.children.forEach((p) => {
          if (p.userData.fase !== undefined) p.scale.y = 5.5 * (0.75 + 0.25 * Math.sin(t * 2 + p.userData.fase * 0.7));
        });
      }
    }

    this.roda.forEach((m) => m.atualizar(dt, this.reduzido));
    this.camera3d.atualizar(dt);
    this.liberarVista();
    this.posicionarRotulo();
    this.renderer.render(this.cena, this.camera);
  }

  /**
   * O alvo do centro não fica entre a câmera e a máquina escolhida: com a
   * câmera passando do meio da roda (máquina grande, roda pequena), ele some.
   */
  liberarVista() {
    const m = this.selecionada;
    if (!m) {
      this.centroDaArena.visible = true;
      return;
    }
    const c = this.camera.position;
    const p = m.grupo.position;
    const dx = p.x - c.x;
    const dz = p.z - c.z;
    const s = limitar(-(c.x * dx + c.z * dz) / (dx * dx + dz * dz || 1), 0, 1);
    this.centroDaArena.visible = Math.hypot(c.x, c.z) > 4 && Math.hypot(c.x + dx * s, c.z + dz * s) > 1.8;
  }

  /** O nome da máquina em cima dela: a do mouse, ou a escolhida. */
  posicionarRotulo() {
    const m = this.sobre || this.selecionada;
    if (!m || !m.grupo.visible) {
      this.rotulo.hidden = true;
      return;
    }
    const v = m.centro(this.ajuda);
    v.y += m.H / 2 + 0.35;
    v.project(this.camera);
    if (v.z > 1) {
      this.rotulo.hidden = true;
      return;
    }
    const w = this.palco.clientWidth;
    const h = this.palco.clientHeight;
    if (this.rotulo.textContent !== m.dados.nome) this.rotulo.textContent = m.dados.nome;
    this.rotulo.hidden = false;
    const x = limitar(Math.round(((v.x + 1) / 2) * w), 80, w - 80);
    const y = limitar(Math.round(((1 - v.y) / 2) * h), 48, h - 70);
    this.rotulo.style.transform = `translate(${x}px, ${y}px) translate(-50%, -100%)`;
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
    this.alvoDesejado.set(0, 1.2, 0);
    // em pé, a roda inteira só cabe de mais longe
    const folga = this.arena.camera.aspect < 0.8 ? 1.5 : 1;
    this.raioDesejado = (raioArena * 1.75 + 7) * folga;
    this.phiDesejado = 1.0;
    if (entrada && !this.arena.reduzido) {
      // entrada de cinema: vem de longe e de cima
      this.raio = this.raioDesejado * 1.8;
      this.phi = 0.55;
    }
  }

  olharPara(maquina, vista = "girar") {
    const centro = maquina.centro(new this.arena.T.Vector3());
    this.alvoDesejado.copy(centro);
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
        // só passando por cima: o cursor avisa que dá para tocar
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
    this.phiDesejado = Math.min(1.45, Math.max(0.22, this.phiDesejado));
    const maximo = (this.arena.raio || 8) * 3.6 + 14;
    this.raioDesejado = Math.min(maximo, Math.max(2.4, this.raioDesejado));
  }

  atualizar(dt) {
    const arena = this.arena;
    // ninguém mexendo há um tempo e nada escolhido: a câmera passeia sozinha
    if (!arena.reduzido && !arena.selecionada && arena.ocioso > 3.5 && this.ponteiros.size === 0) {
      this.thetaDesejado += dt * 0.1;
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
