/* ======================================================================
   ARENA 3D — a roda das máquinas da fábrica, cada uma feita das fotos dela.

   A CENA É A DE SEMPRE: as máquinas em estandes (pedestal com anel de
   luz), em roda e de frente para o centro, onde gira o alvo da marca;
   pilares de luz em volta, estrelas no céu e a câmera que voa até a
   máquina escolhida. As áreas da arena (jogos da Lazer & Sport, as
   máquinas que já fazíamos, trampolins e brinquedões) são trechos da
   roda, cada um com a sua cor no piso e a sua placa. A roda tem SEMPRE
   todas as máquinas: os botões de área -- e o próprio piso ou a placa da
   área, tocados no 3D -- levam a câmera até aquele trecho, que acende. O
   filtro de categoria é o único que tira máquinas da roda.

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
   com a foto inteira. Foto vazada (rede, grade) vira duas placas
   cruzadas, para continuar vazada.

   O QUE NÃO SAI DAS FOTOS: a máquina com objeto feito a partir dos
   arquivos da fábrica (.glb; core/arena.py, MODELOS_3D) aparece com ele,
   e a cama elástica é montada peça por peça (FORMAS, abaixo) -- da foto
   ela só tira as cores.

   A FICHA FICA FORA DO PALCO: ao lado no computador, embaixo no celular.

   O QUE ESTE ARQUIVO NÃO FAZ: baixar o three.js (~170 KB) antes de o
   palco chegar perto da tela, nem num aparelho sem WebGL -- ali a lista
   de máquinas é a página.
   ====================================================================== */

const raiz = document.querySelector("[data-arena3d]");
if (raiz) iniciar(raiz);

const PI = Math.PI;
const CORES = ["#e63946", "#2f8bff", "#ffd700", "#3fd0ff", "#8a5cff", "#ff7a00", "#1fbf5b", "#ff3df2"];
const COR_DA_ZONA = { jogos: "#e63946", maquinas: "#2f8bff", brinquedoes: "#22c55e", esportivos: "#ff9f1c" };
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
   FORMAS — o que a arena monta peça por peça, em 3D de verdade.
   Por enquanto a cama elástica: aro de aço, pernas em W, molas, lona,
   acolchoado, postes com espuma, rede com a entrada e a escadinha. O
   tamanho é o do cadastro; a foto só dá as cores (acolchoado e espumas).
   ====================================================================== */

/** As duas cores mais fortes da foto: [principal, segunda] (ou null). */
function coresDaFoto(tela) {
  const mini = document.createElement("canvas");
  mini.width = mini.height = 48;
  const g = mini.getContext("2d", { willReadFrequently: true });
  g.drawImage(tela, 0, 0, 48, 48);
  const p = g.getImageData(0, 0, 48, 48).data;
  // doze faixas de matiz; cinza, preto e branco não contam (são a lona,
  // a rede, o aço e o fundo -- não a cor do brinquedo)
  const faixas = Array.from({ length: 12 }, (_, k) => ({ k, peso: 0, r: 0, g: 0, b: 0 }));
  for (let i = 0; i < p.length; i += 4) {
    if (p[i + 3] < 128) continue;
    const r = p[i] / 255;
    const v = p[i + 1] / 255;
    const b = p[i + 2] / 255;
    const max = Math.max(r, v, b);
    const min = Math.min(r, v, b);
    const c = max - min;
    const l = (max + min) / 2;
    if (c < 0.22 || l < 0.16 || l > 0.88) continue;
    let h = max === r ? ((v - b) / c) % 6 : max === v ? (b - r) / c + 2 : (r - v) / c + 4;
    h = (h * 60 + 360) % 360;
    const faixa = faixas[Math.floor(h / 30) % 12];
    faixa.peso += c;
    faixa.r += p[i] * c;
    faixa.g += p[i + 1] * c;
    faixa.b += p[i + 2] * c;
  }
  const ordem = faixas.filter((f) => f.peso > 0).sort((a, b) => b.peso - a.peso);
  if (!ordem.length || ordem[0].peso < 3) return null;
  const hex = (f) => "#" + [f.r, f.g, f.b].map((x) => Math.round(x / f.peso).toString(16).padStart(2, "0")).join("");
  const primeira = ordem[0];
  const segunda = ordem.find((f) => Math.min(Math.abs(f.k - primeira.k), 12 - Math.abs(f.k - primeira.k)) >= 2 && f.peso > primeira.peso * 0.1);
  return [hex(primeira), segunda ? hex(segunda) : null];
}

/** A cama elástica, em metros, com o chão em y = 0 e a entrada na frente (+Z). */
function montarCamaElastica(T, { diametro, cores }) {
  const g = new T.Group();
  const R = diametro / 2;
  const hM = diametro >= 2.4 ? 0.82 : 0.62; // altura da lona
  const hN = diametro >= 2.4 ? 1.8 : 1.5; // altura da rede, acima da lona
  const topo = hM + hN;
  const V = (x, y, z) => new T.Vector3(x, y, z);
  const noAro = (a, raio, y) => V(Math.sin(a) * raio, y, Math.cos(a) * raio);
  const aco = new T.MeshStandardMaterial({ color: "#b9c2cf", roughness: 0.35, metalness: 0.8 });
  const acolchoado = new T.MeshStandardMaterial({ color: (cores && cores[0]) || "#1f6fff", roughness: 0.55, side: T.DoubleSide });
  const espuma = new T.MeshStandardMaterial({ color: (cores && (cores[1] || cores[0])) || "#e63946", roughness: 0.6 });
  const borracha = new T.MeshStandardMaterial({ color: "#14161b", roughness: 0.9 });
  const tubo = (curva, r, material, lados = 8, passos = 16) => {
    const m = new T.Mesh(new T.TubeGeometry(curva, passos, r, lados, false), material);
    g.add(m);
    return m;
  };
  const reta = (a, b, r, material) => tubo(new T.LineCurve3(a, b), r, material, 8, 1);
  const textura = (w, h, pintar) => {
    const c = document.createElement("canvas");
    c.width = w;
    c.height = h;
    pintar(c.getContext("2d"));
    const t = new T.CanvasTexture(c);
    t.colorSpace = T.SRGBColorSpace;
    return t;
  };

  // o aro de aço
  const aro = new T.Mesh(new T.TorusGeometry(R, 0.028, 8, 72), aco);
  aro.rotation.x = PI / 2;
  aro.position.y = hM - 0.04;
  g.add(aro);

  // pernas em W: dois tubos descem do aro abrindo e pisam num tubo no chão
  const pernas = diametro >= 3 ? 6 : 4;
  for (let i = 0; i < pernas; i++) {
    const a = (i / pernas) * PI * 2 + PI / pernas;
    const abre = 0.34 / R;
    const pe1 = noAro(a - abre, R + 0.06, 0.03);
    const pe2 = noAro(a + abre, R + 0.06, 0.03);
    reta(noAro(a - abre * 0.55, R, hM - 0.04), pe1, 0.024, aco);
    reta(noAro(a + abre * 0.55, R, hM - 0.04), pe2, 0.024, aco);
    reta(pe1, pe2, 0.026, aco);
    [pe1, pe2].forEach((ponto) => {
      const pe = new T.Mesh(new T.CylinderGeometry(0.045, 0.05, 0.04, 10), borracha);
      pe.position.set(ponto.x, 0.02, ponto.z);
      g.add(pe);
    });
  }

  // as molas, do aro até a lona (aparecem por baixo)
  const molas = Math.round((R * 2 * PI) / 0.11);
  const instancias = new T.InstancedMesh(new T.CylinderGeometry(0.009, 0.009, 0.17, 6), aco, molas);
  const matriz = new T.Matrix4();
  const giro = new T.Quaternion();
  for (let i = 0; i < molas; i++) {
    const a = (i / molas) * PI * 2;
    giro.setFromUnitVectors(V(0, 1, 0), V(Math.sin(a), 0, Math.cos(a)));
    matriz.compose(noAro(a, R - 0.11, hM - 0.035), giro, V(1, 1, 1));
    instancias.setMatrixAt(i, matriz);
  }
  g.add(instancias);

  // a lona de pular: preta, com as costuras em círculo
  const lona = new T.Mesh(
    new T.CircleGeometry(R - 0.2, 64),
    new T.MeshStandardMaterial({
      roughness: 0.85,
      side: T.DoubleSide,
      map: textura(256, 256, (c) => {
        c.fillStyle = "#17191f";
        c.fillRect(0, 0, 256, 256);
        c.strokeStyle = "rgba(255, 255, 255, .13)";
        c.lineWidth = 2;
        for (let r = 22; r < 128; r += 21) { c.beginPath(); c.arc(128, 128, r, 0, PI * 2); c.stroke(); }
      }),
    }),
  );
  lona.rotation.x = -PI / 2;
  lona.position.y = hM - 0.03;
  lona.userData.lona = true; // no passeio, quem pisa aqui quica
  g.add(lona);

  // o acolchoado sobre as molas
  const perfil = [[R - 0.27, -0.01], [R - 0.28, 0.03], [R - 0.25, 0.065], [R + 0.08, 0.065], [R + 0.11, 0.03], [R + 0.11, -0.06], [R + 0.07, -0.09]];
  const almofada = new T.Mesh(new T.LatheGeometry(perfil.map(([x, y]) => new T.Vector2(x, y)), 72), acolchoado);
  almofada.position.y = hM - 0.02;
  g.add(almofada);

  // a rede de proteção, aberta na frente (a entrada)
  const vao = Math.min(1.1, 0.62 / R);
  const rede = new T.Mesh(
    new T.CylinderGeometry(R - 0.04, R - 0.22, hN - 0.06, 72, 1, true, vao / 2, PI * 2 - vao),
    new T.MeshStandardMaterial({
      transparent: true,
      alphaTest: 0.3,
      side: T.DoubleSide,
      roughness: 0.9,
      map: (() => {
        const t = textura(64, 64, (c) => {
          c.clearRect(0, 0, 64, 64);
          c.strokeStyle = "rgba(24, 27, 35, .95)";
          c.lineWidth = 3;
          c.beginPath();
          for (let k = 0; k <= 64; k += 16) { c.moveTo(k, 0); c.lineTo(k, 64); c.moveTo(0, k); c.lineTo(64, k); }
          c.stroke();
        });
        t.wrapS = t.wrapT = T.RepeatWrapping;
        t.repeat.set(Math.round(((PI * 2 - vao) * R) / 0.4), Math.round(hN / 0.4));
        return t;
      })(),
    }),
  );
  rede.position.y = hM + (hN - 0.06) / 2;
  g.add(rede);
  // as bordas do zíper, de cada lado da entrada
  [vao / 2, -vao / 2].forEach((a) => reta(noAro(a, R - 0.22, hM + 0.02), noAro(a, R - 0.04, topo - 0.06), 0.016, espuma));

  // os postes da rede, curvos, com a espuma
  const postes = diametro >= 3 ? 8 : 6;
  for (let i = 0; i < postes; i++) {
    const a = (i / postes) * PI * 2 + PI / postes; // nenhum poste no meio da entrada
    const curva = new T.CatmullRomCurve3([noAro(a, R + 0.03, hM - 0.3), noAro(a, R + 0.09, hM + hN * 0.5), noAro(a, R - 0.02, topo)]);
    tubo(curva, 0.022, aco);
    tubo(new T.CatmullRomCurve3(Array.from({ length: 12 }, (_, k) => curva.getPoint(0.18 + (0.8 * k) / 11))), 0.05, espuma, 10);
    const tampa = new T.Mesh(new T.SphereGeometry(0.055, 12, 8), espuma);
    tampa.position.copy(curva.getPoint(1));
    g.add(tampa);
  }
  const aroDeCima = new T.Mesh(new T.TorusGeometry(R - 0.03, 0.026, 8, 72), espuma);
  aroDeCima.rotation.x = PI / 2;
  aroDeCima.position.y = topo - 0.03;
  g.add(aroDeCima);

  // a escadinha da entrada
  const z0 = R + 0.55;
  const z1 = R + 0.06;
  [-0.22, 0.22].forEach((x) => reta(V(x, 0.02, z0), V(x, hM - 0.06, z1), 0.02, aco));
  [0.36, 0.68].forEach((t) => {
    const degrau = new T.Mesh(new T.BoxGeometry(0.46, 0.035, 0.14), borracha);
    degrau.position.set(0, (hM - 0.06) * t, z0 + (z1 - z0) * t);
    g.add(degrau);
  });
  return g;
}

/** O desenho do cadastro (core/arena.py) -> a forma montada aqui. */
const FORMAS = { cama_elastica: montarCamaElastica };

/* ======================================================================
   O MOVIMENTO NOS OBJETOS DA FÁBRICA -- o que o espaço tem de jogo mexe:
   nas cestas, o SWISH (a bola sobe em arco, entra, a redinha balança e
   o "SWISH!" aparece); nos círculos de panna, o GOL FLASH redondo (a bola
   corre, os LEDs da borda giram, o alvo fica verde e, no gol, uma onda
   dourada corre o anel); e os TELÕES dos dois jogos, com o pôster e o
   placar do que acontece ali. Coordenadas no objeto (metros, frente em
   +z). Só anda com o espaço perto da câmera: de longe não se vê, e o
   celular agradece.
   ====================================================================== */
const ANIMACOES = {
  "espaco-esportivo-modelo-1": (arena, maquina) => {
    const T = arena.T;
    const g = new T.Group();
    maquina.corpo.add(g);
    const V = (x, y, z) => new T.Vector3(x, y, z);
    const tela = (w, h, pintar) => {
      const c = document.createElement("canvas");
      c.width = w;
      c.height = h;
      pintar(c.getContext("2d"));
      const t = new T.CanvasTexture(c);
      t.colorSpace = T.SRGBColorSpace;
      return t;
    };

    // --- SWISH: as cestas das enterradas e das quadras ---
    const tiros = [15.6, 13.6, 11.6, 9.6, 7.6].map((x) => ({ aro: V(x, 2.8, -10.88), de: V(x, 1.9, -8.3), chao: 0.98 }))
      .concat([
        { aro: V(-16.55, 2.4, -5), de: V(-13.6, 1.3, -4.4), chao: 0.18 },
        { aro: V(-9.45, 2.4, -5), de: V(-12.4, 1.3, -5.6), chao: 0.18 },
        { aro: V(-8.55, 2.4, -5), de: V(-5.7, 1.3, -4.5), chao: 0.18 },
        { aro: V(-2.45, 2.4, -5), de: V(-5.2, 1.3, -5.5), chao: 0.18 },
      ]);
    const texBola = tela(64, 32, (c) => {
      c.fillStyle = "#ff7a1a"; c.fillRect(0, 0, 64, 32);
      c.strokeStyle = "#3a1600"; c.lineWidth = 2;
      c.beginPath(); c.moveTo(0, 16); c.lineTo(64, 16); c.moveTo(16, 0); c.lineTo(16, 32); c.moveTo(48, 0); c.lineTo(48, 32); c.stroke();
    });
    const bola = new T.Mesh(new T.SphereGeometry(0.12, 16, 12), new T.MeshStandardMaterial({ map: texBola, roughness: 0.6 }));
    g.add(bola);
    const texRede = tela(64, 64, (c) => {
      c.strokeStyle = "rgba(255,255,255,.95)"; c.lineWidth = 3;
      for (let i = -64; i < 128; i += 12) { c.beginPath(); c.moveTo(i, 0); c.lineTo(i + 40, 64); c.moveTo(i + 40, 0); c.lineTo(i, 64); c.stroke(); }
    });
    texRede.wrapS = T.RepeatWrapping;
    texRede.repeat.set(3, 1);
    const matRede = new T.MeshBasicMaterial({ map: texRede, transparent: true, alphaTest: 0.3, side: T.DoubleSide, toneMapped: false });
    const geoRede = new T.CylinderGeometry(0.2, 0.12, 0.34, 18, 1, true);
    const redes = tiros.map((tiro) => {
      const rede = new T.Mesh(geoRede, matRede);
      rede.position.copy(tiro.aro).y -= 0.18;
      g.add(rede);
      return rede;
    });
    const swish = new T.Sprite(new T.SpriteMaterial({
      map: tela(512, 160, (c) => {
        c.font = "italic 900 112px Poppins, Manrope, sans-serif";
        c.textAlign = "center"; c.textBaseline = "middle";
        c.lineWidth = 16; c.strokeStyle = "#7a1d00"; c.strokeText("SWISH!", 256, 84);
        c.fillStyle = "#ffd84a"; c.fillText("SWISH!", 256, 84);
      }),
      transparent: true, depthWrite: false, toneMapped: false,
    }));
    swish.visible = false;
    g.add(swish);
    // o placar do Swish Arena (o mesmo do jogo: 45 s, os últimos 10 valem
    // três, quatro cestas seguidas e é EM CHAMAS, pontos em dobro)
    const placar = { pontos: 0, tempo: 45, seguidas: 0, cestas: 0, arremessos: 0, grito: 0, ganho: 0, fim: 0 };
    let tiro = tiros[0];
    let fase = "voo";
    let tempo = 0;
    let balanco = 0;
    let redeAtual = 0;
    let erra = false;
    let pedida = null; // a cesta que o passeio pediu (a enterrada de quem está lá)
    const fora = new T.Vector3();
    const proximo = () => {
      const i = pedida !== null ? pedida : Math.floor(Math.random() * tiros.length);
      erra = pedida === null && Math.random() < 0.22;
      pedida = null;
      tiro = tiros[i];
      redeAtual = i;
      fase = "voo";
      tempo = 0;
    };
    proximo();

    // --- GOL FLASH redondo: os dois círculos de panna ---
    const circulos = [V(-12.5, 0, 2.4), V(-6.5, 0, 2.4)];
    const porCirculo = 48;
    const leds = new T.InstancedMesh(new T.SphereGeometry(0.05, 8, 6), new T.MeshBasicMaterial({ toneMapped: false }), porCirculo * circulos.length);
    const ajuda = new T.Object3D();
    circulos.forEach((c, k) => {
      for (let i = 0; i < porCirculo; i++) {
        const a = (i / porCirculo) * PI * 2;
        ajuda.position.set(c.x + Math.cos(a) * 2.55, 0.68, c.z + Math.sin(a) * 2.55);
        ajuda.updateMatrix();
        leds.setMatrixAt(k * porCirculo + i, ajuda.matrix);
        leds.setColorAt(k * porCirculo + i, new T.Color("#1b2a5a"));
      }
    });
    g.add(leds);
    const cores = { apagado: new T.Color("#16224d"), cometa: new T.Color("#ff3d6e"), alvo: new T.Color("#38ff7a"), flash: new T.Color("#fff6b0"), flash2: new T.Color("#ffb703") };
    const jogos = circulos.map((c) => ({
      centro: c,
      bola: (() => {
        const b = new T.Mesh(new T.SphereGeometry(0.11, 14, 10), new T.MeshStandardMaterial({ color: "#ffffff", roughness: 0.4 }));
        b.position.set(c.x, 0.18, c.z);
        g.add(b);
        return b;
      })(),
      vel: V((Math.random() - 0.5) * 3, 0, (Math.random() - 0.5) * 3).setLength(2.4),
      alvo: Math.floor(Math.random() * porCirculo),
      idade: 0, // há quanto tempo o alvo está aceso (apaga sozinho, como no jogo)
      gol: 0,
      gols: 0,
      ganho: 0,
    }));
    let tempoGol = 45;
    let fimGol = 0;
    const cor = new T.Color();

    // --- OS TELÕES: o Swish Arena (em cima da parede das enterradas) e o
    // Gol Flash Arena (atrás dos dois círculos), com o pôster do jogo e o
    // placar do que acontece ali mesmo, no 3D ---
    const posters = {};
    const telas = [];
    const fonte = (peso, px) => `${peso} ${px}px Poppins, Manrope, system-ui, sans-serif`;
    const relogio = (s) => `0:${String(Math.max(0, Math.ceil(s))).padStart(2, "0")}`;
    const fundo = (ctx, img) => {
      ctx.fillStyle = "#070b1c";
      ctx.fillRect(0, 0, 512, 288);
      if (img && img.complete && img.naturalWidth) {
        const k = Math.max(512 / img.naturalWidth, 288 / img.naturalHeight);
        const w = img.naturalWidth * k;
        const h = img.naturalHeight * k;
        ctx.drawImage(img, (512 - w) / 2, (288 - h) / 2 - 14, w, h);
      }
    };
    const barra = (ctx, corDoJogo, itens) => {
      ctx.fillStyle = "rgba(3, 6, 18, .88)";
      ctx.fillRect(0, 224, 512, 64);
      ctx.fillStyle = corDoJogo;
      ctx.fillRect(0, 221, 512, 3);
      const passo = 512 / itens.length;
      ctx.textAlign = "center";
      ctx.textBaseline = "alphabetic";
      itens.forEach(([rotulo, valor], i) => {
        const x = passo * i + passo / 2;
        ctx.fillStyle = "rgba(255, 255, 255, .72)";
        ctx.font = fonte(800, 13);
        ctx.fillText(rotulo, x, 243);
        ctx.fillStyle = "#ffffff";
        ctx.font = fonte(900, 30);
        ctx.fillText(valor, x, 277);
      });
    };
    const grito = (ctx, texto, sub, corDoTexto, vida) => {
      if (vida <= 0) return;
      ctx.save();
      ctx.globalAlpha = Math.min(1, vida * 2.5);
      ctx.fillStyle = "rgba(3, 6, 18, .5)";
      ctx.fillRect(0, 0, 512, 221);
      ctx.translate(256, 104);
      const s = 0.8 + 0.2 * Math.min(1, (1.4 - vida) * 6);
      ctx.scale(s, s);
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.lineJoin = "round";
      ctx.font = fonte("italic 900", 86);
      ctx.lineWidth = 12;
      ctx.strokeStyle = "#120600";
      ctx.strokeText(texto, 0, 0);
      ctx.fillStyle = corDoTexto;
      ctx.fillText(texto, 0, 0);
      if (sub) {
        ctx.font = fonte(900, 30);
        ctx.lineWidth = 7;
        ctx.strokeText(sub, 0, 64);
        ctx.fillStyle = "#ffffff";
        ctx.fillText(sub, 0, 64);
      }
      ctx.restore();
    };
    const final = (ctx, titulo, linha) => {
      ctx.fillStyle = "rgba(3, 6, 18, .78)";
      ctx.fillRect(0, 0, 512, 221);
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillStyle = "#ffd84a";
      ctx.font = fonte(900, 40);
      ctx.fillText(titulo, 256, 90);
      ctx.fillStyle = "#ffffff";
      ctx.font = fonte(800, 26);
      ctx.fillText(linha, 256, 146);
    };
    const telao = (slug, x, y, z, largura, noChao, pintar) => {
      const c = document.createElement("canvas");
      c.width = 512;
      c.height = 288;
      const textura = new T.CanvasTexture(c);
      textura.colorSpace = T.SRGBColorSpace;
      textura.anisotropy = arena.anisotropia;
      const altura = (largura * 288) / 512;
      const suporte = new T.Group();
      suporte.position.set(x, y, z);
      // a moldura preta com as costas e, no chão, os dois pés
      arena.caixa(suporte, largura + 0.2, altura + 0.2, 0.1, arena.escuro(), 0, 0, -0.06);
      const baixo = y - altura / 2;
      if (noChao) [-1, 1].forEach((s) => arena.caixa(suporte, 0.1, baixo, 0.1, arena.escuro(), s * largura * 0.33, -altura / 2 - baixo / 2, -0.06));
      else arena.caixa(suporte, largura * 0.8, 0.12, 0.12, arena.escuro(), 0, -altura / 2 - 0.08, -0.06);
      const painel = new T.Mesh(new T.PlaneGeometry(largura, altura), new T.MeshBasicMaterial({ map: textura, toneMapped: false }));
      painel.position.z = 0.012;
      suporte.add(painel);
      g.add(suporte);
      const item = { slug, ctx: c.getContext("2d"), textura, suporte, pintar, ultimo: -1 };
      telas.push(item);
      return item;
    };
    const pintarTodas = () => telas.forEach((item) => { item.pintar(item.ctx); item.textura.needsUpdate = true; });

    telao("swish-arena", 11.6, 4.62, -11.02, 4, false, (ctx) => {
      fundo(ctx, posters["swish-arena"]);
      if (placar.fim > 0) final(ctx, "TEMPO ESGOTADO", `${placar.pontos} PONTOS · ${placar.cestas} CESTAS`);
      if (placar.seguidas >= 4 && placar.fim <= 0) {
        ctx.fillStyle = "#ff5a1f";
        ctx.fillRect(14, 14, 168, 34);
        ctx.fillStyle = "#ffffff";
        ctx.font = fonte("italic 900", 20);
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText("EM CHAMAS ×2", 98, 32);
      }
      grito(ctx, "SWISH!", `+${placar.ganho}`, "#ffd84a", placar.grito);
      barra(ctx, "#ff5a1f", [["PONTOS", String(placar.pontos)], ["CESTAS", `${placar.cestas}/${placar.arremessos}`], ["TEMPO", relogio(placar.tempo)]]);
    });
    const anelNaTela = (ctx, k, cx, cy, r) => {
      // o círculo de LED do 3D, visto de cima, com a bola
      const arr = leds.instanceColor.array;
      for (let i = 0; i < porCirculo; i++) {
        const a = (i / porCirculo) * PI * 2;
        const j = (k * porCirculo + i) * 3;
        cor.setRGB(arr[j], arr[j + 1], arr[j + 2], T.LinearSRGBColorSpace);
        ctx.fillStyle = cor.getStyle();
        ctx.beginPath();
        ctx.arc(cx + Math.cos(a) * r, cy + Math.sin(a) * r, 3.4, 0, PI * 2);
        ctx.fill();
      }
      const b = jogos[k].bola.position;
      ctx.fillStyle = "#ffffff";
      ctx.beginPath();
      ctx.arc(cx + ((b.x - circulos[k].x) / 2.55) * r, cy + ((b.z - circulos[k].z) / 2.55) * r, 4, 0, PI * 2);
      ctx.fill();
    };
    telao("gol-flash-arena", -9.5, 2.16, -0.55, 3.6, true, (ctx) => {
      fundo(ctx, posters["gol-flash-arena"]);
      ctx.fillStyle = "rgba(3, 6, 18, .7)";
      ctx.beginPath();
      ctx.arc(46, 46, 38, 0, PI * 2);
      ctx.arc(466, 46, 38, 0, PI * 2);
      ctx.fill();
      anelNaTela(ctx, 0, 46, 46, 30);
      anelNaTela(ctx, 1, 466, 46, 30);
      if (fimGol > 0) {
        const [a, b] = jogos.map((j) => j.gols);
        final(ctx, "TEMPO ESGOTADO", a === b ? `EMPATE · ${a} A ${b}` : `PLAYER ${a > b ? 1 : 2} VENCEU · ${Math.max(a, b)} GOLS`);
      }
      const quem = jogos[0].gol >= jogos[1].gol ? jogos[0] : jogos[1];
      grito(ctx, "GOOOL!", `+${quem.ganho}`, "#a6e22e", quem.gol);
      barra(ctx, "#a6e22e", [["P1 · GOL", String(jogos[0].gols)], ["TEMPO", relogio(tempoGol)], ["P2 · GOL", String(jogos[1].gols)]]);
    });
    (maquina.dados.jogos_no_espaco || []).forEach((j) => {
      if (!j.poster) return;
      const img = new Image();
      img.decoding = "async";
      img.addEventListener("load", pintarTodas);
      img.src = j.poster;
      posters[j.slug] = img;
    });
    pintarTodas(); // com menos movimento (nada anda), fica o pôster parado
    const onde = new T.Vector3();
    // o que mexe não é chão nem parede: fica fora dos raios (o toque na
    // máquina, o piso do passeio) -- e o "SWISH!" é um sprite, que nem pode
    g.traverse((o) => { o.raycast = () => {}; });

    const quadro = (dt, t, camera) => {
      // de longe não mexe (não se vê, e poupa o celular)
      maquina.grupo.getWorldPosition(onde);
      if (camera.position.distanceTo(onde) > 95) return;

      // swish: voo em arco até o aro; cesta (a queda pela redinha) ou aro
      // (a bola espirra para fora); uma pausa e o próximo arremesso
      tempo += dt;
      if (fase === "voo") {
        const k = Math.min(1, tempo / 1.1);
        bola.position.lerpVectors(tiro.de, tiro.aro, k);
        bola.position.y += Math.sin(k * PI) * 1.3 + 0.05;
        bola.rotation.x -= dt * 9;
        if (k >= 1) {
          tempo = 0;
          if (placar.fim <= 0) placar.arremessos++;
          if (erra) {
            fase = "fora";
            balanco = 0.3;
            placar.seguidas = 0;
            fora.subVectors(tiro.de, tiro.aro).setY(0).normalize().applyAxisAngle(V(0, 1, 0), (Math.random() - 0.5) * 1.4);
          } else {
            fase = "queda";
            balanco = 1;
            swish.visible = true;
            if (placar.fim <= 0) {
              placar.seguidas++;
              placar.cestas++;
              placar.ganho = (placar.tempo <= 10 ? 3 : 2) * (placar.seguidas > 4 ? 2 : 1);
              placar.pontos += placar.ganho;
              placar.grito = 1.4;
            }
          }
        }
      } else if (fase === "queda") {
        const k = Math.min(1, tempo / 0.5);
        bola.position.set(tiro.aro.x, tiro.aro.y - (tiro.aro.y - tiro.chao) * k * k, tiro.aro.z);
        if (k >= 1) { fase = "pausa"; tempo = 0; }
      } else if (fase === "fora") {
        const k = Math.min(1, tempo / 0.8);
        bola.position.copy(tiro.aro).addScaledVector(fora, k * 1.2);
        bola.position.y = tiro.aro.y + 0.05 + Math.sin(k * PI) * 0.4 - (tiro.aro.y - tiro.chao) * k * k;
        bola.rotation.z += dt * 8;
        if (k >= 1) { fase = "pausa"; tempo = 0; }
      } else if (tempo > 0.6) {
        proximo();
      }
      balanco = Math.max(0, balanco - dt * 1.6);
      redes.forEach((rede, i) => {
        rede.scale.set(1, i === redeAtual ? 1 + Math.sin(t * 24) * 0.18 * balanco : 1, 1);
      });
      if (swish.visible) {
        const vida = 1 - balanco;
        swish.position.set(tiro.aro.x, tiro.aro.y + 0.6 + vida * 0.5, tiro.aro.z + 0.2);
        const tamanho = 1.2 + Math.min(1, vida * 4) * 0.4;
        swish.scale.set(tamanho * 3.2, tamanho, 1);
        swish.material.opacity = Math.min(1, balanco * 1.6);
        if (balanco <= 0) swish.visible = false;
      }
      // a partida do placar: 45 s, o resultado na tela e outra partida
      placar.grito = Math.max(0, placar.grito - dt);
      if (placar.fim > 0) {
        placar.fim -= dt;
        if (placar.fim <= 0) Object.assign(placar, { pontos: 0, tempo: 45, seguidas: 0, cestas: 0, arremessos: 0 });
      } else {
        placar.tempo -= dt;
        if (placar.tempo <= 0) { placar.tempo = 0; placar.fim = 4; }
      }

      // gol flash: a bola corre e bate na borda; no alvo verde é gol
      if (fimGol > 0) {
        fimGol -= dt;
        if (fimGol <= 0) { tempoGol = 45; jogos.forEach((j) => { j.gols = 0; }); }
      } else {
        tempoGol -= dt;
        if (tempoGol <= 0) { tempoGol = 0; fimGol = 4; }
      }
      jogos.forEach((jogo, k) => {
        const b = jogo.bola.position;
        b.x += jogo.vel.x * dt;
        b.z += jogo.vel.z * dt;
        const dx = b.x - jogo.centro.x;
        const dz = b.z - jogo.centro.z;
        const d = Math.hypot(dx, dz);
        jogo.idade += dt;
        if (jogo.idade > 3.6) {
          // ninguém acertou: o alvo apaga e acende em outro lugar
          jogo.alvo = Math.floor(Math.random() * porCirculo);
          jogo.idade = 0;
        }
        if (d > 2.35) {
          // bateu na borda: volta para dentro, refletida, com um desvio
          const nx = dx / d;
          const nz = dz / d;
          const pv = jogo.vel.x * nx + jogo.vel.z * nz;
          jogo.vel.x -= 2 * pv * nx;
          jogo.vel.z -= 2 * pv * nz;
          jogo.vel.applyAxisAngle(V(0, 1, 0), (Math.random() - 0.5) * 0.6);
          b.x = jogo.centro.x + nx * 2.34;
          b.z = jogo.centro.z + nz * 2.34;
          const onde = Math.round(((Math.atan2(dz, dx) + PI * 2) % (PI * 2)) / (PI * 2) * porCirculo) % porCirculo;
          const perto = Math.min(Math.abs(onde - jogo.alvo), porCirculo - Math.abs(onde - jogo.alvo));
          if (perto <= 3) {
            jogo.gol = 1.4;
            if (fimGol <= 0) {
              // vale mais quanto mais rápido sai depois de o alvo acender
              jogo.ganho = 100 + Math.round(Math.max(0, 1 - jogo.idade / 3.6) * 100);
              jogo.gols++;
            }
            jogo.alvo = Math.floor(Math.random() * porCirculo);
            jogo.idade = 0;
          }
        }
        jogo.bola.rotation.x += dt * 6;
        jogo.gol = Math.max(0, jogo.gol - dt);
        const cabeca = (t * 22) % porCirculo;
        for (let i = 0; i < porCirculo; i++) {
          if (jogo.gol > 0) {
            // o gol: uma onda dourada correndo o anel (sem pisca-pisca)
            cor.copy(cores.flash2).lerp(cores.flash, 0.5 + 0.5 * Math.sin(t * 9 - i * 0.5));
          } else {
            const atras = (cabeca - i + porCirculo) % porCirculo;
            cor.copy(cores.apagado);
            if (atras < 6) cor.lerp(cores.cometa, 1 - atras / 6);
            const ate = Math.min(Math.abs(i - jogo.alvo), porCirculo - Math.abs(i - jogo.alvo));
            if (ate <= 3) cor.copy(cores.alvo).multiplyScalar(0.75 + 0.25 * Math.sin(t * 5));
          }
          leds.setColorAt(k * porCirculo + i, cor);
        }
      });
      leds.instanceColor.needsUpdate = true;

      // os telões: 12 quadros por segundo, e só de perto
      telas.forEach((item) => {
        if (t - item.ultimo < 1 / 12) return;
        if (camera.position.distanceTo(item.suporte.getWorldPosition(onde)) > 60) return;
        item.ultimo = t;
        item.pintar(item.ctx);
        item.textura.needsUpdate = true;
      });
    };
    // o passeio avisa: "swish:2" -- o próximo arremesso vai na cesta 2 (a
    // enterrada de quem está passando por lá)
    quadro.evento = (nome) => {
      const [tipo, valor] = nome.split(":");
      if (tipo === "swish") pedida = Number(valor);
    };
    return quadro;
  },
};

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
    // o objeto feito com os arquivos da fábrica (.glb) vence o das fotos;
    // e o que a arena sabe montar peça por peça (a cama elástica) também
    this.modelo = dados.modelo || "";
    this.forma = !this.modelo && FORMAS[dados.desenho] ? dados.desenho : "";
    // um espaço inteiro (o parque de trampolins com as quadras) não cabe na
    // roda: fica no seu próprio "reino", ao lado, ligado por uma passarela
    this.reino = Boolean(dados.reino && this.modelo);

    const medidas = this.modelo && (dados.medidas_modelo || []).length === 3 ? dados.medidas_modelo : dados.medidas;
    const [altura, largura, fundo] = (medidas || []).map(Number);
    const teto = this.modelo ? (dados.reino ? 60 : 14) : 4.5;
    this.altura = limitar(altura || 1.8, 0.6, this.modelo ? 6 : 4.5);
    this.largura = limitar(largura || 1, 0.4, teto);
    this.fundo = limitar(fundo || 1, 0.3, teto);
    // Grande (um brinquedão de 11 m) não gira no prato -- varreria os
    // vizinhos da roda --: nas vistas, quem dá a volta é a câmera. E fica
    // numa plataforma do seu formato, e não num pedestal redondo.
    this.grande = Math.max(this.largura, this.fundo) > 4.5;
    this.retangular = this.grande && Math.max(this.largura, this.fundo) > 1.6 * Math.min(this.largura, this.fundo);
    this.raioP = this.retangular ? this.fundo / 2 + 0.55 : Math.max(this.largura, this.fundo) * 0.62 + 0.45;
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
    if (this.retangular) {
      this.aro = arena.plataforma(grupo, this.largura + 0.9, this.fundo + 0.9, this.alturaP, this.cor);
    } else {
      arena.cilindro(grupo, this.raioP, this.alturaP, arena.pedestal(), 0, this.alturaP / 2, 0, 48);
      this.aro = arena.anel(grupo, this.raioP + 0.02, 0.045, arena.luz(this.cor, 2.2), 0, this.alturaP, 0);
      this.aro.rotation.x = PI / 2;
    }
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
    return Object.keys(this.fotos).length > 0 || Boolean(this.modelo || this.forma);
  }

  /** Tudo do estande responde ao toque como a máquina. */
  marcar() {
    this.grupo.traverse((obj) => { obj.userData.maquina = this; });
    this.arena.caixasSujas = true;
  }

  ajustarPivo() {
    this.pivo.position.y = this.H / 2;
    this.corpo.position.y = -this.H / 2;
  }

  /** Baixa e recorta as fotos no tamanho pedido (uma vez por tamanho). */
  pedir(tamanho) {
    if (this.modelo || this.forma) {
      // o objeto da fábrica (ou a forma montada aqui) vem inteiro, uma vez só
      if (this.pedido) return;
      this.pedido = Infinity;
      // o objeto da fábrica fura a fila: é o que mais se quer ver
      const tarefa = () => (this.modelo ? this.vestirModelo() : this.vestirForma());
      if (this.modelo) this.arena.fila.unshift(tarefa);
      else this.arena.fila.push(tarefa);
      return;
    }
    if (this.pedido >= tamanho || !this.temFoto) return;
    this.pedido = tamanho;
    this.arena.fila.push(() => this.carregar(tamanho));
  }

  /** A forma montada peça por peça, no tamanho do cadastro, com as cores da foto. */
  async vestirForma() {
    const T = this.arena.T;
    let cores = null;
    const url = this.fotos.perfil || Object.values(this.fotos)[0];
    if (url) {
      try {
        const recorte = recortar(await carregarImagem(fotoNaLargura(url, 320)), 320);
        if (recorte) cores = coresDaFoto(recorte.tela);
      } catch (erro) {
        // sem a foto, as cores da casa
      }
    }
    this.limpar();
    const objeto = FORMAS[this.forma](T, { diametro: limitar(Math.min(this.largura, this.fundo), 1.4, 4.6), cores });
    objeto.traverse((o) => {
      if (o.geometry) this.descartaveis.push(o.geometry);
      if (o.material) this.descartaveis.push(o.material, ...(o.material.map ? [o.material.map] : []));
    });
    this.corpo.add(objeto);
    const tamanho = new T.Box3().setFromObject(objeto).getSize(new T.Vector3());
    this.H = tamanho.y;
    this.W = tamanho.x;
    this.D = tamanho.z;
    this.montada = 1;
    this.sombra.scale.set(this.W * 0.6, this.D * 0.6, 1);
    this.ajustarPivo();
    this.marcar();
  }

  /** O objeto 3D feito com os arquivos da fábrica (.glb), no tamanho real. */
  async vestirModelo() {
    const T = this.arena.T;
    try {
      const objeto = await this.arena.carregarModelo(this.modelo);
      this.limpar();
      const caixa = new T.Box3().setFromObject(objeto);
      const tamanho = caixa.getSize(new T.Vector3());
      objeto.position.y -= caixa.min.y;
      this.corpo.add(objeto);
      this.H = tamanho.y;
      this.W = tamanho.x;
      this.D = tamanho.z;
      this.montada = 1;
      this.sombra.scale.set(this.W * 0.62, this.D * 0.7, 1);
      // o espaço tem o próprio piso: a sombra por cima dele só mancharia
      this.sombra.visible = !this.reino;
      this.arena.caixasSujas = true;
      const animacao = ANIMACOES[this.dados.modelo_id];
      if (animacao && !this.animar) this.animar = animacao(this.arena, this);
      this.ajustarPivo();
      this.marcar();
    } catch (erro) {
      // sem o objeto, a máquina volta para o volume feito das fotos
      console.error("Arena 3D: o objeto 3D não carregou", erro);
      this.modelo = "";
      this.pedido = 0;
      if (this.temFoto) this.pedir(this.arena.fotoLonge);
      else this.semFoto = true;
    }
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
    new Set(this.descartaveis).forEach((item) => item.dispose());
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
    if (this.grande) return; // o grande fica parado; a câmera é que anda
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
    this.fotoLonge = 384;
    this.fotoPerto = this.celular ? 768 : 1024;
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
    this.cena.background = new T.Color("#0a1238");
    this.cena.fog = new T.Fog("#141c4a", 30, 90);
    this.camera = new T.PerspectiveCamera(45, 1, 0.1, 400);
    this.camera.position.set(0, 12, 28);
    this.raycaster = new T.Raycaster();
    this.ponteiro = new T.Vector2();
    this.ajuda = new T.Vector3();

    this.montarLuzes();
    this.montarPiso();
    this.montarCentro();
    this.montarCeu();
    this.montarFesta();
    this.decoracao = new T.Group();
    this.cena.add(this.decoracao);

    // sem foto não há de onde montar o objeto: a máquina fica só na lista
    this.maquinas = (dados.maquinas || [])
      .map((d, i) => (Object.keys(fotosDe(d)).length || d.modelo || FORMAS[d.desenho] ? new Maquina(this, d, i) : null))
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

  /**
   * O pedestal e a plataforma: o tampo deles fica no mesmo plano do piso do
   * objeto (o EVA do Espaço, a base do brinquedão). Empurrado um tico para
   * trás na profundidade, o objeto sempre vence -- sem as duas cores
   * brigando ("piscando") quando a câmera anda.
   */
  pedestal() {
    return this.mat("pedestal", () => new this.T.MeshStandardMaterial({
      color: "#11182b", roughness: 0.55, metalness: 0.35, polygonOffset: true, polygonOffsetFactor: 2, polygonOffsetUnits: 4,
    }));
  }

  /** O que é pintado no chão (áreas, passarela, sombra): puxado para a frente. */
  noChao(material) {
    material.polygonOffset = true;
    material.polygonOffsetFactor = -2;
    material.polygonOffsetUnits = -4;
    return material;
  }

  borracha() {
    return this.mat("borracha", () => new this.T.MeshStandardMaterial({ color: "#05070c", roughness: 0.9 }));
  }

  /**
   * O objeto 3D de uma máquina (.glb). O GLTFLoader vem na primeira vez
   * que precisa, do mesmo endereço do three.js (sem ?v=): os dois falam
   * com a mesma cópia do motor.
   */
  async carregarModelo(url) {
    if (!this.carregadorGLB) {
      this.carregadorGLB = import(this.palco.dataset.gltf).then((modulo) => new modulo.GLTFLoader());
    }
    const gltf = await (await this.carregadorGLB).loadAsync(url);
    return gltf.scene;
  }

  /** A plataforma do brinquedão comprido: retângulo de cantos redondos, com a faixa de luz. */
  plataforma(grupo, w, d, altura, cor) {
    const T = this.T;
    const forma = (lw, ld, r) => {
      const s = new T.Shape();
      const x = -lw / 2;
      const y = -ld / 2;
      s.moveTo(x + r, y);
      s.lineTo(x + lw - r, y);
      s.quadraticCurveTo(x + lw, y, x + lw, y + r);
      s.lineTo(x + lw, y + ld - r);
      s.quadraticCurveTo(x + lw, y + ld, x + lw - r, y + ld);
      s.lineTo(x + r, y + ld);
      s.quadraticCurveTo(x, y + ld, x, y + ld - r);
      s.lineTo(x, y + r);
      s.quadraticCurveTo(x, y, x + r, y);
      return s;
    };
    const r = Math.min(0.8, d / 2 - 0.05);
    const base = new T.Mesh(new T.ExtrudeGeometry(forma(w, d, r), { depth: altura, bevelEnabled: false, curveSegments: 10 }), this.pedestal());
    base.rotation.x = -PI / 2; // a extrusão (Z) vira a altura (Y)
    grupo.add(base);
    const faixa = forma(w + 0.09, d + 0.09, r + 0.045);
    faixa.holes.push(forma(w - 0.01, d - 0.01, r - 0.005));
    const aro = new T.Mesh(new T.ExtrudeGeometry(faixa, { depth: 0.06, bevelEnabled: false, curveSegments: 10 }), this.luz(cor, 2.2));
    aro.rotation.x = -PI / 2;
    aro.position.y = altura - 0.04;
    grupo.add(aro);
    return aro;
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
      return this.noChao(new this.T.MeshBasicMaterial({ map: new this.T.CanvasTexture(tela), transparent: true, depthWrite: false }));
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
    // placa de texto vista de longe e deitada: o filtro mais forte que houver
    textura.anisotropy = this.renderer.capabilities.getMaxAnisotropy();
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

  esfera(pai, r, material, x = 0, y = 0, z = 0) {
    const m = new this.T.Mesh(this.geo("esfera", () => new this.T.SphereGeometry(1, 24, 16)), material);
    m.scale.setScalar(r);
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

  /**
   * A FESTA -- a arena como um parque de diversões à noite: o céu de fim de
   * tarde (roxo no horizonte, azul em cima), firme, sem nada piscando. As
   * bandeirinhas, as lâmpadas, os balões, o portal e as placas no ar vêm
   * com a roda (dependem do tamanho dela): `montarPilares` e `marcarArea`.
   */
  montarFesta() {
    const T = this.T;
    const c = document.createElement("canvas");
    c.width = 16;
    c.height = 256;
    const g = c.getContext("2d");
    const ceu = g.createLinearGradient(0, 0, 0, 256);
    ceu.addColorStop(0, "#050b26");
    ceu.addColorStop(0.45, "#13245e");
    ceu.addColorStop(0.62, "#3b2a78");
    ceu.addColorStop(0.7, "#7a3d86");
    ceu.addColorStop(1, "#141c4a");
    g.fillStyle = ceu;
    g.fillRect(0, 0, 16, 256);
    const textura = new T.CanvasTexture(c);
    textura.colorSpace = T.SRGBColorSpace;
    const cupula = new T.Mesh(new T.SphereGeometry(300, 32, 16), new T.MeshBasicMaterial({ map: textura, side: T.BackSide, fog: false, depthWrite: false, toneMapped: false }));
    cupula.renderOrder = -1;
    this.cena.add(cupula);

    this.baloes = [];
    this.placasNoAr = [];
  }

  /** Os balões e as placas no ar balançando devagar. */
  animarFesta(dt, t) {
    if (this.reduzido) return;
    this.baloes.forEach((b) => {
      b.position.y = b.userData.y + Math.sin(t * 1.3 + b.userData.fase) * 0.12;
      b.rotation.y = Math.sin(t * 0.6 + b.userData.fase) * 0.25;
    });
    this.placasNoAr.forEach((p) => { p.position.y = p.userData.y + Math.sin(t * 1.1 + p.userData.fase) * 0.18; });
  }

  /** Um cacho de balões coloridos com as fitas, num ponto do chão. */
  balões(x, z, quantos = 4, fase = 0) {
    const T = this.T;
    const cacho = new T.Group();
    cacho.position.set(x, 0, z);
    cacho.userData.y = 0;
    cacho.userData.fase = fase;
    const cores = ["#e63946", "#ffd700", "#2f8bff", "#22c55e", "#ff3df2", "#ff9f1c"];
    const geo = this.geo("balao", () => new T.SphereGeometry(1, 16, 12));
    const fitas = [];
    for (let k = 0; k < quantos; k++) {
      const a = (k / quantos) * PI * 2 + fase;
      const bx = Math.cos(a) * 0.32;
      const bz = Math.sin(a) * 0.32;
      const by = 2.5 + (k % 2) * 0.35;
      const cor = cores[(((k + Math.round(fase * 10)) % cores.length) + cores.length) % cores.length];
      const balao = new T.Mesh(geo, this.mat("balao" + cor, () => {
        const m = new T.MeshStandardMaterial({ color: cor, roughness: 0.25, metalness: 0.1, emissive: cor, emissiveIntensity: 0.25 });
        m.userData.compartilhado = true;
        return m;
      }));
      balao.scale.set(0.32, 0.4, 0.32);
      balao.position.set(bx, by, bz);
      balao.userData.compartilhado = true;
      cacho.add(balao);
      fitas.push(bx, by - 0.4, bz, 0, 0.05, 0);
    }
    const linha = new T.BufferGeometry();
    linha.setAttribute("position", new T.Float32BufferAttribute(fitas, 3));
    cacho.add(new T.LineSegments(linha, this.mat("fita", () => {
      const m = new T.LineBasicMaterial({ color: "#f4f6ff", transparent: true, opacity: 0.7 });
      m.userData.compartilhado = true;
      return m;
    })));
    this.baloes.push(cacho);
    return cacho;
  }

  /**
   * O portal: duas colunas listradas, o arco amarelo com lâmpadas e o
   * letreiro (dos dois lados). `angulo` diz para onde ele olha.
   */
  portal(x, z, angulo, texto, cor, largura = 6.4) {
    const T = this.T;
    const portal = new T.Group();
    portal.position.set(x, 0, z);
    portal.rotation.y = angulo;
    const alto = 5.4;
    const listras = this.mat("listras", () => {
      const c = document.createElement("canvas");
      c.width = 8;
      c.height = 64;
      const g = c.getContext("2d");
      for (let i = 0; i < 8; i++) { g.fillStyle = i % 2 ? "#ffffff" : "#e63946"; g.fillRect(0, i * 8, 8, 8); }
      const t = new T.CanvasTexture(c);
      t.colorSpace = T.SRGBColorSpace;
      t.wrapT = T.RepeatWrapping;
      t.repeat.set(1, 3);
      const m = new T.MeshStandardMaterial({ map: t, roughness: 0.4 });
      m.userData.compartilhado = true;
      return m;
    });
    [-largura / 2, largura / 2].forEach((lado) => {
      const coluna = this.cilindro(portal, 0.22, alto, listras, lado, alto / 2, 0, 20);
      coluna.userData.compartilhado = true;
      const topo = this.esfera(portal, 0.3, this.luz("#ffd700", 2.4), lado, alto + 0.15, 0);
      topo.userData.compartilhado = true;
    });
    const arco = new T.Mesh(new T.TorusGeometry(largura / 2, 0.16, 10, 40, PI), this.luz("#ffd700", 1.6));
    arco.position.y = alto;
    portal.add(arco);
    // as lâmpadas do arco
    const lampadas = new T.InstancedMesh(this.geo("lampada", () => new T.SphereGeometry(0.08, 8, 6)), this.mat("lampada", () => {
      const m = new T.MeshBasicMaterial({ color: "#fff2b0", toneMapped: false });
      m.userData.compartilhado = true;
      return m;
    }), 17);
    const ajuda = new T.Object3D();
    for (let i = 0; i < 17; i++) {
      const a = (i / 16) * PI;
      ajuda.position.set(Math.cos(a) * (largura / 2), alto + Math.sin(a) * (largura / 2) + 0.2, 0.12);
      ajuda.updateMatrix();
      lampadas.setMatrixAt(i, ajuda.matrix);
    }
    portal.add(lampadas);
    // o letreiro, legível dos dois lados
    const material = this.materialDeTexto([texto[0], texto[1]], cor, 1024, 256);
    material.side = T.FrontSide;
    [0, PI].forEach((giro) => {
      const placa = new T.Mesh(this.geo("plano", () => new T.PlaneGeometry(1, 1)), material);
      placa.scale.set(largura * 0.86, largura * 0.215, 1);
      placa.position.set(0, alto - 0.5, giro ? -0.05 : 0.05);
      placa.rotation.y = giro;
      portal.add(placa);
    });
    portal.add(this.balões(-largura / 2 - 0.6, 0.3, 4, 0.3), this.balões(largura / 2 + 0.6, 0.3, 4, 1.7));
    this.baloes.forEach((b) => { if (b.parent === portal) b.userData.y = 0; });
    return portal;
  }

  /** Uma placa no ar (sempre de frente para quem olha) que balança devagar. */
  placaNoAr(linhas, cor, x, y, z, largura = 5.6, zona = "") {
    const T = this.T;
    const material = this.materialDeTexto(linhas, cor, 1024, 256);
    const placa = new T.Sprite(new T.SpriteMaterial({ map: material.map, transparent: true, depthWrite: false, toneMapped: false }));
    material.dispose();
    placa.scale.set(largura, largura / 4, 1);
    placa.position.set(x, y, z);
    placa.userData.y = y;
    placa.userData.fase = x * 0.37 + z * 0.11;
    placa.userData.zona = zona;
    this.placasNoAr.push(placa);
    return placa;
  }

  /** Pilares de luz em volta da roda: a "arquibancada" da arena. */
  montarPilares(raio) {
    const T = this.T;
    if (this.pilares) {
      this.cena.remove(this.pilares);
      this.pilares.traverse((obj) => { if (obj.isInstancedMesh) obj.dispose(); });
    }
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

    // as bandeirinhas de festa, penduradas de pilar a pilar
    const porVao = 6;
    const bandeiras = new T.InstancedMesh(
      this.geo("bandeirinha", () => {
        const g = new T.BufferGeometry();
        g.setAttribute("position", new T.Float32BufferAttribute([-0.24, 0, 0, 0.24, 0, 0, 0, -0.46, 0], 3));
        g.computeVertexNormals();
        return g;
      }),
      this.mat("bandeiras", () => new T.MeshBasicMaterial({ side: T.DoubleSide, toneMapped: false })),
      n * porVao,
    );
    const cores = ["#e63946", "#ffd700", "#2f8bff", "#22c55e", "#ff3df2", "#ff9f1c"].map((c) => new T.Color(c));
    const ajuda = new T.Object3D();
    const fios = [];
    let k = 0;
    for (let i = 0; i < n; i++) {
      const a0 = (i / n) * PI * 2;
      const a1 = ((i + 1) / n) * PI * 2;
      const p0 = new T.Vector3(Math.cos(a0) * raio, 5.45, Math.sin(a0) * raio);
      const p1 = new T.Vector3(Math.cos(a1) * raio, 5.45, Math.sin(a1) * raio);
      const giro = -Math.atan2(p1.z - p0.z, p1.x - p0.x);
      const ponto = (t) => p0.clone().lerp(p1, t).setY(5.45 - Math.sin(t * PI) * 0.8);
      for (let j = 0; j < 8; j++) {
        const a = ponto(j / 8);
        const b = ponto((j + 1) / 8);
        fios.push(a.x, a.y, a.z, b.x, b.y, b.z);
      }
      for (let j = 0; j < porVao; j++) {
        ajuda.position.copy(ponto((j + 0.5) / porVao));
        ajuda.rotation.set(0, giro, 0);
        ajuda.updateMatrix();
        bandeiras.setMatrixAt(k, ajuda.matrix);
        bandeiras.setColorAt(k, cores[k % cores.length]);
        k++;
      }
    }
    grupo.add(bandeiras);
    const fio = new T.BufferGeometry();
    fio.setAttribute("position", new T.Float32BufferAttribute(fios, 3));
    grupo.add(new T.LineSegments(fio, new T.LineBasicMaterial({ color: "#f4f6ff", transparent: true, opacity: 0.55 })));

    // as lâmpadas de festa no aro de cima
    const quantas = Math.round((raio * PI * 2) / 0.9);
    const lampadas = new T.InstancedMesh(this.geo("lampada", () => new T.SphereGeometry(0.08, 8, 6)), this.mat("lampadaCor", () => new T.MeshBasicMaterial({ toneMapped: false })), quantas);
    const tons = ["#fff2b0", "#ffd166", "#ff9fb2", "#9fe1ff"].map((c) => new T.Color(c));
    for (let i = 0; i < quantas; i++) {
      const a = (i / quantas) * PI * 2;
      ajuda.position.set(Math.cos(a) * raio, 5.72, Math.sin(a) * raio);
      ajuda.rotation.set(0, 0, 0);
      ajuda.updateMatrix();
      lampadas.setMatrixAt(i, ajuda.matrix);
      lampadas.setColorAt(i, tons[i % tons.length]);
    }
    grupo.add(lampadas);
    this.lampadas = lampadas;
    this.tonsDasLampadas = tons;

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
      .filter((m) => !this.categoria || (m.dados.categorias || []).includes(this.categoria))
      .sort((a, b) => ordem(a.dados.grupo) - ordem(b.dados.grupo) || a.indice - b.indice);
  }

  limparDecoracao() {
    this.decoracao.children.slice().forEach((filho) => {
      this.decoracao.remove(filho);
      filho.traverse((obj) => {
        if (obj.isInstancedMesh) obj.dispose();
        // o que é compartilhado (balão, lâmpada, listras) fica para a próxima
        if (obj.userData.compartilhado || (obj.material && obj.material.userData.compartilhado)) return;
        if (obj.material && obj.material.map) obj.material.map.dispose();
        if (obj.material) obj.material.dispose();
        if (obj.geometry && ![...this.geometrias.values()].includes(obj.geometry)) obj.geometry.dispose();
      });
    });
    this.baloes = [];
    this.placasNoAr = [];
  }

  montar({ entrada = false } = {}) {
    // A roda tem TODAS as máquinas (só a categoria tira alguma): a visão é
    // ampla, e as áreas são lugares da roda aonde a câmera vai.
    this.lista = this.filtradas();
    // `this.roda` são todas as que estão à vista (a roda e os reinos)
    this.roda = this.lista;
    const roda = this.lista.filter((m) => !m.reino);
    const reinos = this.lista.filter((m) => m.reino);
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
    this.folga = folga;
    this.trechos = trechos;
    this.fundosDasAreas = {};
    trechos.forEach((trecho) => this.marcarArea(trecho, raio, folga));
    this.montarPilares(raio + folga + 4.5);
    this.montarReinos(reinos, raio + folga + 4.5);
    // o portal de entrada, do lado de onde a câmera chega
    const aPortal = 0.5;
    const rPortal = raio + folga + 4.5;
    this.decoracao.add(this.portal(Math.sin(aPortal) * rPortal, Math.cos(aPortal) * rPortal, aPortal, ["Bem-vindo à", "Arena Lazer & Sport"], "#ffd700", 6.8));
    this.caixasSujas = true;
    this.cena.fog.near = raio * 2.2;
    this.cena.fog.far = Math.max(raio * 5 + 30, this.longeDosReinos || 0);
    if (this.selecionada && !this.roda.includes(this.selecionada)) this.soltarSelecao({ voar: false });
    const zona = this.trechos.find((t) => t.id === this.zona);
    this.realcarArea(zona ? this.zona : "");
    if (zona && !entrada) this.camera3d.olharZona(zona);
    else this.camera3d.visaoGeral(entrada);
    this.roda.forEach((m) => m.pedir(this.fotoLonge));
    this.marcarLista();
  }

  /**
   * Os reinos: os espaços grandes demais para a roda (um parque de
   * trampolins com quadras, 39 m x 23 m) ficam atrás dela, lado a lado,
   * de frente para a roda, sobre o chão escuro, cada um ligado à roda por
   * uma passarela de luz e com a placa da área na entrada. A área deles
   * vira um "trecho" do tipo reino: o botão e a placa levam a câmera lá.
   */
  montarReinos(reinos, beira) {
    const T = this.T;
    this.longeDosReinos = 0;
    if (!reinos.length) return;
    const vao = 8;
    const larguras = reinos.map((m) => m.largura + 2);
    const total = larguras.reduce((a, b) => a + b, 0) + vao * (reinos.length - 1);
    const fundoMaior = Math.max(...reinos.map((m) => m.fundo));
    const zFrente = -(beira + 10);
    let x = -total / 2;
    const porArea = {};
    reinos.forEach((m, i) => {
      const cx = x + larguras[i] / 2;
      x += larguras[i] + vao;
      const cz = zFrente - m.fundo / 2 - 0.6;
      m.grupo.position.set(cx, 0, cz);
      m.grupo.rotation.y = 0; // de frente para a roda
      m.grupo.visible = true;
      const id = m.dados.grupo;
      const area = porArea[id] || (porArea[id] = { id, tipo: "reino", x0: Infinity, x1: -Infinity, z0: Infinity, z1: -Infinity });
      area.x0 = Math.min(area.x0, cx - m.largura / 2);
      area.x1 = Math.max(area.x1, cx + m.largura / 2);
      area.z0 = Math.min(area.z0, cz - m.fundo / 2);
      area.z1 = Math.max(area.z1, cz + m.fundo / 2);
      // a passarela de luz, da beira da roda até a entrada do reino
      const cor = COR_DA_ZONA[id] || "#ff9f1c";
      const fim = new T.Vector3(cx, 0, zFrente + 1);
      const inicio = fim.clone().setLength(beira - 1.5);
      const caminho = new T.Vector3().subVectors(fim, inicio);
      const suporte = new T.Group();
      suporte.position.copy(inicio).add(fim).multiplyScalar(0.5);
      suporte.position.y = 0.012;
      suporte.rotation.y = Math.atan2(caminho.x, caminho.z);
      const passarela = new T.Mesh(
        new T.PlaneGeometry(3.2, caminho.length()),
        this.noChao(new T.MeshBasicMaterial({ color: cor, transparent: true, opacity: 0.18, depthWrite: false, toneMapped: false })),
      );
      passarela.rotation.x = -PI / 2;
      passarela.userData.zona = id;
      suporte.add(passarela);
      [-1.7, 1.7].forEach((lado) => {
        const filete = new T.Mesh(this.geo("plano", () => new T.PlaneGeometry(1, 1)), this.noChao(new T.MeshBasicMaterial({ color: cor, toneMapped: false })));
        filete.scale.set(0.08, caminho.length(), 1);
        filete.rotation.x = -PI / 2;
        filete.position.set(lado, 0.004, 0);
        suporte.add(filete);
      });
      this.decoracao.add(suporte);
    });
    // o chão escuro sob os reinos e a placa da área na entrada
    Object.values(porArea).forEach((area) => {
      const cor = COR_DA_ZONA[area.id] || "#ff9f1c";
      const chao = new T.Mesh(
        new T.PlaneGeometry(area.x1 - area.x0 + 10, area.z1 - area.z0 + 10),
        // embaixo do piso da roda (onde os dois se cruzam, a roda vence)
        new T.MeshStandardMaterial({ color: "#081430", roughness: 0.9, polygonOffset: true, polygonOffsetFactor: 4, polygonOffsetUnits: 8 }),
      );
      chao.rotation.x = -PI / 2;
      chao.position.set((area.x0 + area.x1) / 2, -0.04, (area.z0 + area.z1) / 2);
      chao.userData.zona = area.id;
      this.decoracao.add(chao);
      const zona = this.zonas.find((z) => z.id === area.id);
      if (zona) {
        const placa = new T.Mesh(this.geo("plano", () => new T.PlaneGeometry(1, 1)), this.materialDeTexto([zona.kicker || "", zona.titulo], cor));
        placa.scale.set(7, 1.75, 1);
        placa.position.set((area.x0 + area.x1) / 2, 0.5, area.z1 + 3.2);
        placa.rotation.x = -1.05;
        placa.userData.zona = area.id;
        this.decoracao.add(placa);
        this.decoracao.add(this.portal((area.x0 + area.x1) / 2, area.z1 + 5.8, 0, [zona.kicker || "", zona.titulo], cor, 8));
      }
      this.trechos.push(area);
      this.longeDosReinos = Math.max(this.longeDosReinos, -area.z0 + 120);
    });
  }

  /** O trecho de uma área no piso da roda, na cor dela, com a placa. */
  marcarArea(trecho, raio, folga) {
    const T = this.T;
    const cor = COR_DA_ZONA[trecho.id] || "#2f8bff";
    const arco = (dentro, fora, opacidade) => {
      const malha = new T.Mesh(
        new T.RingGeometry(dentro, fora, 72, 1, trecho.a0 - PI / 2, trecho.a1 - trecho.a0),
        this.noChao(new T.MeshBasicMaterial({ color: cor, transparent: true, opacity: opacidade, depthWrite: false, toneMapped: false })),
      );
      malha.rotation.x = -PI / 2;
      malha.position.y = 0.015;
      malha.userData.zona = trecho.id;
      this.decoracao.add(malha);
      return malha;
    };
    this.fundosDasAreas[trecho.id] = arco(raio - folga - 0.9, raio + folga + 0.6, 0.14);
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
    placa.userData.zona = trecho.id;
    suporte.add(placa);
    this.decoracao.add(suporte);
    // um cacho de balões de cada lado da placa e o nome da área no ar
    const lado = largura / 2 + 0.7;
    [-1, 1].forEach((s) => {
      const bx = Math.sin(meio) * r + Math.cos(meio) * lado * s;
      const bz = Math.cos(meio) * r - Math.sin(meio) * lado * s;
      this.decoracao.add(this.balões(bx, bz, 3, meio + s));
    });
    const ra = raio + folga + 1.2;
    this.decoracao.add(this.placaNoAr([zona.kicker || "", zona.titulo], cor, Math.sin(meio) * ra, 7.6, Math.cos(meio) * ra, 6.4, trecho.id));
  }

  /** A área escolhida acende no piso; as outras apagam um pouco. */
  realcarArea(id) {
    Object.entries(this.fundosDasAreas || {}).forEach(([zona, malha]) => {
      malha.material.opacity = !id ? 0.14 : zona === id ? 0.34 : 0.06;
    });
  }

  /** A área sob o ponteiro (o piso colorido ou a placa dela), ou "". */
  zonaSob(x, y) {
    const r = this.canvas.getBoundingClientRect();
    this.ponteiro.set(((x - r.left) / r.width) * 2 - 1, -((y - r.top) / r.height) * 2 + 1);
    this.raycaster.setFromCamera(this.ponteiro, this.camera);
    const acerto = this.raycaster.intersectObjects(this.decoracao.children, true).find((a) => a.object.userData.zona);
    return acerto ? acerto.object.userData.zona : "";
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
    if (!this.roda.includes(maquina)) return;
    if (this.passeio) this.sairPasseio({ voar: false });
    if (this.selecionada && this.selecionada !== maquina) this.largar(this.selecionada);
    this.selecionada = maquina;
    this.roda.forEach((m) => { m.aro.material = this.luz(m.cor, m === maquina ? 5 : 2.2); });
    maquina.pedir(this.fotoPerto);
    this.vista("girar", { voar });
    const alvo = maquina.centro(this.ajuda);
    this.foco.position.set(alvo.x * 0.55, maquina.H + 6, alvo.z * 0.55);
    this.foco.target.position.set(alvo.x, 0, alvo.z);
    this.foco.intensity = 2.2;
    if (this.vistas) {
      this.vistas.hidden = false;
      const passeio = this.vistas.querySelector('[data-arena-vista="passeio"]');
      if (passeio) passeio.hidden = !(maquina.modelo || maquina.forma);
    }
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
    if (this.passeio) this.sairPasseio({ voar: false });
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
    if (nome === "passeio") {
      this.entrarPasseio();
      return;
    }
    this.ocioso = 0;
    this.vistaAtual = nome;
    m.girando = nome === "girar" && !m.grande;
    if (nome !== "girar" && !m.grande) m.giroAlvo = giroMaisPerto(m.prato.rotation.y, GIRO_DA_VISTA[nome]);
    m.tomboAlvo = nome === "baixo" && !m.grande ? TOMBO : 0;
    if (voar) this.camera3d.olharPara(m, nome);
    if (this.vistas) {
      this.vistas.querySelectorAll("[data-arena-vista]").forEach((botao) => {
        botao.setAttribute("aria-pressed", botao.dataset.arenaVista === nome ? "true" : "false");
      });
      // o botão dos lados mostra o lado de agora
      const lado = this.vistas.querySelector(`[data-arena-lados-menu] [data-arena-vista="${nome}"]`);
      this.vistas.querySelector("[data-arena-lados-nome]").textContent = lado ? lado.textContent : "Lados";
      this.vistas.querySelector("[data-arena-lados]").setAttribute("aria-pressed", lado ? "true" : "false");
      this.abrirLados(false);
    }
  }

  abrirLados(abrir) {
    const menu = this.vistas && this.vistas.querySelector("[data-arena-lados-menu]");
    if (!menu) return;
    menu.hidden = !abrir;
    this.vistas.querySelector("[data-arena-lados]").setAttribute("aria-expanded", abrir ? "true" : "false");
  }

  /** "Ver tudo": a arena inteira, de qualquer lugar (o botão, o mapa, Esc). */
  verTudo() {
    if (this.passeio) this.sairPasseio({ voar: false });
    if (this.tour) this.acao("tour", this.controles.querySelector('[data-arena-acao="tour"]'));
    this.escolherZona("");
  }

  /** O passeio por dentro do brinquedo escolhido (só nos objetos 3D de verdade). */
  /** O painel do passeio: pausar / continuar (no fim, "De novo") e sair. */
  ligarPainelDoPasseio(painel) {
    painel.querySelector("[data-passeio-sair]").addEventListener("click", () => this.sairPasseio());
    painel.querySelector("[data-passeio-pausa]").addEventListener("click", () => {
      if (this.passeio) this.passeio.alternarPausa();
    });
  }

  /** O painel acompanha o passeio: a etapa, a barra do quanto andou e o botão. */
  marcarPasseio({ etapa, fracao, pausado, fim }) {
    const painel = this.painelPasseio;
    if (!painel) return;
    painel.querySelector("[data-passeio-etapa]").textContent = pausado ? "Pausado" : etapa;
    painel.querySelector("[data-passeio-progresso]").style.transform = `scaleX(${limitar(fracao, 0, 1).toFixed(3)})`;
    const botao = painel.querySelector("[data-passeio-pausa]");
    const rotulo = fim ? "Passear de novo" : pausado ? "Continuar o passeio" : "Pausar o passeio";
    botao.setAttribute("aria-label", rotulo);
    botao.title = rotulo;
    botao.dataset.estado = fim ? "fim" : pausado ? "pausado" : "andando";
  }

  entrarPasseio() {
    const m = this.selecionada;
    if (!m || !(m.modelo || m.forma) || !m.montada) return;
    this.largar(m);
    m.prato.rotation.y = giroMaisPerto(m.prato.rotation.y, 0);
    this.tour = false;
    this.passeio = new Passeio(this, m);
    if (this.vistas) this.vistas.hidden = true;
    if (this.controles) this.controles.hidden = true;
    this.rotulo.hidden = true;
    if (this.painelPasseio) {
      this.painelPasseio.hidden = false;
      const dica = this.painelPasseio.querySelector("[data-passeio-dica]");
      if (dica) {
        dica.textContent = this.celular
          ? "O passeio anda sozinho · arraste para olhar em volta"
          : "O passeio anda sozinho · arraste para olhar em volta · espaço pausa · Esc sai";
      }
      this.passeio.desenharMapaBase(this.painelPasseio.querySelector("[data-passeio-mapa]"));
    }
    this.passeio.entrar();
    this.palco.classList.add("em-passeio");
    // no celular, o palco no meio da tela: a barra do site não cobre os botões
    this.palco.scrollIntoView({ behavior: this.reduzido ? "auto" : "smooth", block: "center" });
  }

  sairPasseio({ voar = true } = {}) {
    if (!this.passeio) return;
    this.passeio.sair();
    this.passeio = null;
    this.redimensionar();
    if (this.painelPasseio) this.painelPasseio.hidden = true;
    if (this.controles) this.controles.hidden = false;
    this.palco.classList.remove("em-passeio");
    if (this.selecionada) {
      if (this.vistas) this.vistas.hidden = false;
      if (voar) this.vista("frente");
    } else if (voar) this.camera3d.visaoGeral();
  }

  /**
   * As setas: o brinquedo que está daquele lado NA TELA (lado = 1, direita;
   * -1, esquerda), qualquer que seja o lado de onde a câmera olha. Sem
   * nenhum escolhido, começa pelo que está mais no meio da tela.
   */
  vizinha(lado) {
    const lista = this.lista.filter((m) => m.grupo.visible);
    const total = lista.length;
    if (!total) return;
    const T = this.T;
    const frente = this.camera.getWorldDirection(new T.Vector3()).setY(0).normalize();
    const direita = new T.Vector3(-frente.z, 0, frente.x);
    const atual = this.selecionada;
    if (!atual || !lista.includes(atual)) {
      const c = this.camera.position;
      const noMeio = (m) => {
        const d = this.ajuda.subVectors(m.grupo.position, c).setY(0);
        return d.dot(frente) / (d.length() || 1);
      };
      this.selecionar(lista.reduce((a, b) => (noMeio(b) > noMeio(a) ? b : a)));
      return;
    }
    const i = lista.indexOf(atual);
    const vizinhas = [lista[(i + 1) % total], lista[(i - 1 + total) % total]];
    const deLado = (m) => lado * this.ajuda.subVectors(m.grupo.position, atual.grupo.position).dot(direita);
    this.selecionar(deLado(vizinhas[0]) >= deLado(vizinhas[1]) ? vizinhas[0] : vizinhas[1]);
  }

  /**
   * Vai até uma área da arena -- a câmera passeia pela roda até o trecho
   * dela, que acende no piso. A roda continua inteira: as outras áreas
   * seguem ali do lado. "" volta para a arena inteira.
   */
  escolherZona(id) {
    this.zona = id;
    this.ocioso = 0;
    this.raiz.querySelectorAll("[data-arena-zona]").forEach((b) => {
      const ativo = b.dataset.arenaZona === id;
      b.classList.toggle("ativo", ativo);
      b.setAttribute("aria-pressed", ativo ? "true" : "false");
    });
    this.soltarSelecao({ voar: false });
    this.realcarArea(id);
    const trecho = (this.trechos || []).find((t) => t.id === id);
    if (trecho) this.camera3d.olharZona(trecho);
    else this.camera3d.visaoGeral();
  }

  filtrar(categoria) {
    this.categoria = categoria;
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
    // num espaço inteiro, os jogos da casa que rodam nele (Swish, Gol Flash)
    const jogos = f.querySelector("[data-ficha-jogos]");
    if (jogos) {
      const lista = b.jogos_no_espaco || [];
      jogos.hidden = !lista.length;
      const rotulo = document.createElement("span");
      rotulo.textContent = "Jogue a prévia:";
      jogos.replaceChildren(...(lista.length ? [rotulo] : []), ...lista.map((jogo) => {
        const link = document.createElement("a");
        link.href = `${jogar.dataset.base}${jogo.slug}/`;
        link.textContent = jogo.titulo;
        return link;
      }));
    }
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
      // sem tela cheia (o iPhone não deixa), o botão nem aparece
      if (!this.palco.requestFullscreen) this.controles.querySelector('[data-arena-acao="tela-cheia"]').hidden = true;
      this.controles.addEventListener("click", (evento) => {
        const botao = evento.target.closest("[data-arena-acao]");
        if (botao) this.acao(botao.dataset.arenaAcao, botao);
      });
    }
    if (this.vistas) {
      this.vistas.addEventListener("click", (evento) => {
        if (evento.target.closest("[data-arena-lados]")) {
          this.abrirLados(this.vistas.querySelector("[data-arena-lados-menu]").hidden);
          return;
        }
        const botao = evento.target.closest("[data-arena-vista]");
        if (botao) this.vista(botao.dataset.arenaVista);
      });
    }
    this.ligarMapa();
    this.painelPasseio = this.palco.querySelector("[data-arena-passeio]");
    if (this.painelPasseio) this.ligarPainelDoPasseio(this.painelPasseio);

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
          // fora da categoria de agora: volta para todas
          if (categoria) categoria.value = "";
          this.filtrar("");
        }
        this.selecionar(maquina);
        this.palco.scrollIntoView({ behavior: this.reduzido ? "auto" : "smooth", block: "center" });
      });
    });

    this.palco.addEventListener("keydown", (evento) => {
      if (this.passeio || evento.target.closest("select, input")) return;
      if (evento.key === "ArrowRight") { this.vizinha(1); evento.preventDefault(); }
      else if (evento.key === "ArrowLeft") { this.vizinha(-1); evento.preventDefault(); }
      else if (evento.key === "Escape") { this.verTudo(); evento.preventDefault(); }
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
    if (nome === "direita") this.vizinha(1);
    else if (nome === "esquerda") this.vizinha(-1);
    else if (nome === "visao") this.verTudo();
    else if (nome === "mapa") this.abrirMapa(this.mapa ? this.mapa.hidden : false);
    else if (nome === "tour") {
      this.tour = !this.tour;
      this.tourTempo = 0;
      botao.setAttribute("aria-pressed", this.tour ? "true" : "false");
      botao.querySelector("i").className = this.tour ? "fa-solid fa-pause" : "fa-solid fa-play";
      if (this.tour) this.vizinha(1);
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

    if (this.tour && !this.passeio) {
      this.tourTempo += dt;
      if (this.tourTempo > 6) {
        this.tourTempo = 0;
        this.vizinha(1);
      }
    }

    // O cenário fica firme: luzes, pilares, lâmpadas e estrelas paradas (cor
    // que corre pela tela parece defeito). Mexe só o que tem motivo: o alvo
    // da marca, os balões e os jogos.
    if (!this.reduzido) this.alvoMarca.rotation.y = t * 0.6;
    this.animarFesta(dt, t);

    this.roda.forEach((m) => {
      m.atualizar(dt, this.reduzido);
      if (m.animar && m.grupo.visible && !this.reduzido) m.animar(dt, t, this.camera);
    });
    if (this.passeio) {
      this.passeio.quadro(dt);
    } else {
      this.camera3d.atualizar(dt);
      this.liberarVista();
      this.posicionarRotulo(dt);
      this.atualizarMapa();
    }
    this.renderer.render(this.cena, this.camera);
  }

  /**
   * O alvo do centro não fica entre a câmera e a máquina escolhida: com a
   * câmera passando do meio da roda (máquina grande, roda pequena), ele some.
   */
  liberarVista() {
    const p = this.camera3d.alvo;
    if (Math.hypot(p.x, p.z) < 2) {
      // olhando para o centro (a arena inteira): o alvo é o destaque
      this.centroDaArena.visible = true;
      return;
    }
    const c = this.camera.position;
    const dx = p.x - c.x;
    const dz = p.z - c.z;
    const s = limitar(-(c.x * dx + c.z * dz) / (dx * dx + dz * dz || 1), 0, 1);
    this.centroDaArena.visible = Math.hypot(c.x, c.z) > 4 && Math.hypot(c.x + dx * s, c.z + dz * s) > 1.8;
  }

  /**
   * As caixas (no chão) de tudo o que está à vista, com a altura de cada
   * uma; refeitas só quando a roda muda ou um objeto chega.
   */
  medirCaixas() {
    const T = this.T;
    const caixa = new T.Box3();
    this.caixasSujas = false;
    this.caixas = this.roda.filter((m) => m.grupo.visible).map((m) => {
      const p = m.grupo.position;
      const topo = m.alturaP + Math.max(m.H, m.altura) + 0.1;
      if (!m.grande) {
        // a que gira no prato: a caixa do círculo dela
        const r = m.raioP;
        return { m, x0: p.x - r, x1: p.x + r, z0: p.z - r, z1: p.z + r, topo };
      }
      m.grupo.updateMatrixWorld(true);
      caixa.setFromObject(m.grupo);
      return { m, x0: caixa.min.x, x1: caixa.max.x, z0: caixa.min.z, z1: caixa.max.z, topo: Math.max(topo, caixa.max.y) };
    });
  }

  /**
   * A altura mais baixa em que a câmera pode ficar em (x, z): nunca abaixo
   * de um objeto. Perto da beira dele a altura cresce aos poucos (a câmera
   * sobe suave, sem pulo); a escolhida vista de baixo fica de fora.
   */
  alturaLivre(x, z) {
    if (this.caixasSujas || !this.caixas) this.medirCaixas();
    const BEIRA = 1.6;
    let minimo = 0.6;
    for (const c of this.caixas) {
      if (c.m === this.selecionada && this.vistaAtual === "baixo") continue;
      const d = Math.hypot(Math.max(c.x0 - x, 0, x - c.x1), Math.max(c.z0 - z, 0, z - c.z1));
      if (d >= BEIRA) continue;
      const k = 1 - d / BEIRA;
      minimo = Math.max(minimo, (c.topo + 0.7) * k * k * (3 - 2 * k));
    }
    return minimo;
  }

  ajustarPerto(perto) {
    const camera = this.camera;
    if (Math.abs(camera.near - perto) < 0.02) return;
    camera.near = perto;
    camera.updateProjectionMatrix();
  }

  /* ---------- o mapa: a arena vista de cima, como um mapa comum ---------- */
  ligarMapa() {
    this.mapa = this.palco.querySelector("[data-arena-mapa]");
    if (!this.mapa) return;
    this.telaDoMapa = this.mapa.querySelector("[data-arena-mapa-tela]");
    this.nomeNoMapa = this.mapa.querySelector("[data-arena-mapa-nome]");
    this.mapa.querySelector("[data-arena-mapa-fechar]").addEventListener("click", () => this.abrirMapa(false));
    const tela = this.telaDoMapa;
    let inicio = null;
    tela.addEventListener("pointerdown", (evento) => { inicio = { x: evento.clientX, y: evento.clientY }; });
    tela.addEventListener("pointerup", (evento) => {
      if (!inicio || Math.hypot(evento.clientX - inicio.x, evento.clientY - inicio.y) > 10) return;
      inicio = null;
      this.tocarNoMapa(evento.clientX, evento.clientY);
    });
    tela.addEventListener("pointermove", (evento) => {
      if (evento.pointerType !== "mouse") return;
      const m = this.pinoNoMapa(evento.clientX, evento.clientY);
      if (m !== this.sobreNoMapa) {
        this.sobreNoMapa = m;
        tela.style.cursor = m ? "pointer" : "default";
      }
    });
    tela.addEventListener("pointerleave", () => { this.sobreNoMapa = null; });
    // no computador, o mapa já fica no canto; no celular e no tablet abre no botão
    this.abrirMapa(window.matchMedia("(min-width: 961px)").matches);
  }

  abrirMapa(abrir) {
    if (!this.mapa) return;
    this.mapa.hidden = !abrir;
    const botao = this.controles && this.controles.querySelector('[data-arena-acao="mapa"]');
    if (botao) botao.setAttribute("aria-pressed", abrir ? "true" : "false");
    this.marcaDoMapa = "";
  }

  /**
   * Mundo (x, z) <-> mapa: a planta cabe inteira, com a entrada embaixo.
   * O caminho até os reinos (a passarela) fica curto no desenho -- como num
   * mapa de parque --, e a roda não vira um pontinho.
   */
  medidasDoMapa() {
    const tela = this.telaDoMapa;
    const w = tela.clientWidth;
    const h = tela.clientHeight;
    const R = (this.raio || 8) + (this.folga || 1) + 4.5;
    const reinos = (this.trechos || []).filter((t) => t.tipo === "reino");
    const frente = reinos.length ? Math.max(...reinos.map((t) => t.z1)) : -R;
    const vao = Math.max(0, -R - frente); // a passarela de verdade
    const curto = Math.min(vao, 3);
    // z do mundo -> z do desenho (e a volta), por trechos retos
    const zm = (z) => (z >= -R ? z : z >= frente ? -R - ((-R - z) * curto) / (vao || 1) : z + vao - curto);
    const zw = (z) => (z >= -R ? z : z >= -R - curto ? -R - ((-R - z) * vao) / (curto || 1) : z - vao + curto);
    let [x0, x1, z0, z1] = [-R - 1, R + 1, -R - 1, R + 1];
    reinos.forEach((t) => {
      x0 = Math.min(x0, t.x0 - 2);
      x1 = Math.max(x1, t.x1 + 2);
      z0 = Math.min(z0, zm(t.z0) - 2);
    });
    const grande = w >= 300;
    // de cada lado, o espaço dos nomes (no mapa grande)
    const folga = grande ? Math.min(118, w * 0.27) : 10;
    const s = Math.max(0.1, Math.min((w - folga * 2) / (x1 - x0), (h - 26) / (z1 - z0)));
    const ox = (w - (x1 - x0) * s) / 2 - x0 * s;
    const oy = (h - (z1 - z0) * s) / 2 - z0 * s;
    return { w, h, s, ox, oy, R, grande, folga, zm, zw, X: (x) => ox + x * s, Y: (z) => oy + zm(z) * s };
  }

  pinoNoMapa(cx, cy) {
    if (!this.medidaDoMapa) return null;
    const r = this.telaDoMapa.getBoundingClientRect();
    const { X, Y } = this.medidaDoMapa;
    let melhor = null;
    let perto = 18;
    this.roda.forEach((m) => {
      if (!m.grupo.visible) return;
      const d = Math.hypot(X(m.grupo.position.x) - (cx - r.left), Y(m.grupo.position.z) - (cy - r.top));
      if (d < perto) { perto = d; melhor = m; }
    });
    return melhor;
  }

  tocarNoMapa(cx, cy) {
    const m = this.pinoNoMapa(cx, cy);
    const pequeno = !window.matchMedia("(min-width: 961px)").matches;
    if (m) {
      this.selecionar(m);
      if (pequeno) this.abrirMapa(false); // no celular, o mapa sai da frente do brinquedo
      return;
    }
    // fora dos pinos: a área tocada (a faixa da roda ou o reino)
    const r = this.telaDoMapa.getBoundingClientRect();
    const { ox, oy, s, zw } = this.medidaDoMapa;
    const x = (cx - r.left - ox) / s;
    const z = zw((cy - r.top - oy) / s);
    const reino = (this.trechos || []).find((t) => t.tipo === "reino" && x >= t.x0 - 5 && x <= t.x1 + 5 && z >= t.z0 - 5 && z <= t.z1 + 5);
    if (reino) { this.escolherZona(reino.id); return; }
    const d = Math.hypot(x, z);
    if (d < (this.raio || 8) * 0.45) { this.verTudo(); return; }
    const a = (Math.atan2(x, z) + PI * 2) % (PI * 2);
    const trecho = (this.trechos || []).find((t) => t.tipo !== "reino" && a >= t.a0 && a <= t.a1);
    if (trecho && d < (this.raio || 8) + (this.folga || 1) + 5) this.escolherZona(trecho.id);
  }

  /** Redesenha o mapa só quando algo nele muda (a câmera, a escolha, o tamanho). */
  atualizarMapa() {
    if (!this.mapa || this.mapa.hidden || this.passeio) return;
    const tela = this.telaDoMapa;
    const c = this.camera.position;
    const d = this.camera.getWorldDirection(this.ajuda);
    const sel = this.selecionada;
    const marca = `${tela.clientWidth}x${tela.clientHeight}|${c.x.toFixed(1)},${c.z.toFixed(1)},${Math.atan2(d.x, d.z).toFixed(2)}|${sel ? sel.indice : ""}|${this.sobreNoMapa ? this.sobreNoMapa.indice : ""}|${this.zona}|${this.roda.length}`;
    if (marca === this.marcaDoMapa) return;
    this.marcaDoMapa = marca;
    this.desenharMapaDaArena();
  }

  desenharMapaDaArena() {
    const tela = this.telaDoMapa;
    const med = this.medidasDoMapa();
    this.medidaDoMapa = med;
    const { w, h, s, X, Y, R, grande } = med;
    if (!w || !h) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    if (tela.width !== Math.round(w * dpr) || tela.height !== Math.round(h * dpr)) {
      tela.width = Math.round(w * dpr);
      tela.height = Math.round(h * dpr);
    }
    const g = tela.getContext("2d");
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, h);
    const cx = X(0);
    const cy = Y(0);
    const raio = this.raio || 8;
    const folga = this.folga || 1;
    const fonte = (px, peso = 800) => `${peso} ${px}px Poppins, Manrope, system-ui, sans-serif`;

    // o piso da roda, a cerca de pilares e o alvo do meio
    g.fillStyle = "#10224f";
    g.beginPath(); g.arc(cx, cy, (raio + folga + 1.5) * s, 0, PI * 2); g.fill();
    g.strokeStyle = "rgba(63, 208, 255, .55)";
    g.lineWidth = 1.5;
    g.beginPath(); g.arc(cx, cy, R * s, 0, PI * 2); g.stroke();
    g.fillStyle = "#e63946";
    g.beginPath(); g.arc(cx, cy, Math.max(3, 1.2 * s), 0, PI * 2); g.fill();
    g.fillStyle = "#ffffff";
    g.beginPath(); g.arc(cx, cy, Math.max(1.5, 0.6 * s), 0, PI * 2); g.fill();

    // as áreas: a faixa colorida de cada uma na roda; o reino, ao lado
    (this.trechos || []).forEach((t) => {
      const cor = COR_DA_ZONA[t.id] || "#2f8bff";
      const ativa = this.zona === t.id;
      g.globalAlpha = ativa ? 0.62 : this.zona ? 0.2 : 0.38;
      g.fillStyle = cor;
      if (t.tipo === "reino") {
        // a passarela de luz e o espaço inteiro
        g.fillRect(X((t.x0 + t.x1) / 2) - 1.6 * s, Y(t.z1), 3.2 * s, Y(-R) - Y(t.z1));
        g.fillRect(X(t.x0), Y(t.z0), (t.x1 - t.x0) * s, Y(t.z1) - Y(t.z0));
        g.globalAlpha = 1;
        g.strokeStyle = cor;
        g.lineWidth = 1.5;
        g.strokeRect(X(t.x0), Y(t.z0), (t.x1 - t.x0) * s, Y(t.z1) - Y(t.z0));
        const zona = this.zonas.find((z) => z.id === t.id);
        if (zona && (t.x1 - t.x0) * s > 70) {
          g.fillStyle = "#ffffff";
          g.font = fonte(grande ? 12 : 9);
          g.textAlign = "center";
          g.textBaseline = "top";
          g.fillText(zona.titulo, X((t.x0 + t.x1) / 2), Y(t.z0) + 4);
        }
        return;
      }
      g.beginPath();
      g.arc(cx, cy, (raio + folga + 0.6) * s, PI / 2 - t.a0, PI / 2 - t.a1, true);
      g.arc(cx, cy, Math.max(0, raio - folga - 0.9) * s, PI / 2 - t.a1, PI / 2 - t.a0, false);
      g.closePath();
      g.fill();
    });
    g.globalAlpha = 1;

    // a entrada (o portal), embaixo
    const aP = 0.5;
    const ex = cx + Math.sin(aP) * R * s;
    const ey = cy + Math.cos(aP) * R * s;
    g.fillStyle = "#ffd700";
    g.beginPath(); g.arc(ex, ey, 4, 0, PI * 2); g.fill();
    g.font = fonte(grande ? 11 : 9, 900);
    g.textAlign = "center";
    g.textBaseline = "top";
    g.fillText("ENTRADA", Math.min(w - 30, ex), Math.min(h - 12, ey + 6));

    // os brinquedos: um pino na cor da área; o escolhido maior, com o nome
    const sel = this.selecionada;
    const sobre = this.sobreNoMapa;
    const nomes = [];
    this.roda.forEach((m) => {
      if (!m.grupo.visible) return;
      const px = X(m.grupo.position.x);
      const py = Y(m.grupo.position.z);
      const cor = COR_DA_ZONA[m.dados.grupo] || m.cor;
      const destaque = m === sel || m === sobre;
      if (m === sel) {
        g.fillStyle = "rgba(255, 255, 255, .25)";
        g.beginPath(); g.arc(px, py, 13, 0, PI * 2); g.fill();
      }
      g.fillStyle = cor;
      g.strokeStyle = "#ffffff";
      g.lineWidth = destaque ? 2.5 : 1.5;
      g.beginPath(); g.arc(px, py, destaque ? 8 : 5.5, 0, PI * 2); g.fill(); g.stroke();
      if (grande && !m.reino) nomes.push({ m, px, py, destaque });
    });

    // os nomes por fora da roda, na direção de cada brinquedo: de cada lado,
    // um embaixo do outro (sem encavalar), com um fio até o pino se precisou descer
    const ALTURA = 12;
    [1, -1].forEach((lado) => {
      const doLado = nomes
        .map((n) => {
          const a = Math.atan2(n.py - cy, n.px - cx);
          return { ...n, a, lx: cx + Math.cos(a) * (R * s + 8), ly: cy + Math.sin(a) * (R * s + 8) };
        })
        .filter((n) => (Math.cos(n.a) >= 0 ? 1 : -1) === lado)
        .sort((p, q) => p.ly - q.ly);
      for (let i = 1; i < doLado.length; i++) doLado[i].ly = Math.max(doLado[i].ly, doLado[i - 1].ly + ALTURA);
      // o que passou de baixo do mapa sobe de volta, empurrando os de cima
      for (let i = doLado.length - 1; i >= 0; i--) {
        const teto = i === doLado.length - 1 ? h - 8 : doLado[i + 1].ly - ALTURA;
        doLado[i].ly = Math.min(doLado[i].ly, teto);
      }
      doLado.forEach((n) => {
        const longe = Math.abs(n.ly - (cy + Math.sin(n.a) * (R * s + 8))) > 3;
        if (longe) {
          g.strokeStyle = "rgba(219, 231, 255, .35)";
          g.lineWidth = 1;
          g.beginPath();
          g.moveTo(n.px, n.py);
          g.lineTo(n.lx - lado * 2, n.ly);
          g.stroke();
        }
        g.font = fonte(10.5, n.destaque ? 900 : 700);
        const cabe = lado > 0 ? w - n.lx - 4 : n.lx - 4;
        let nome = n.m.dados.nome;
        while (nome.length > 3 && g.measureText(nome).width > cabe) nome = `${nome.slice(0, -2)}…`;
        g.textAlign = lado > 0 ? "left" : "right";
        g.textBaseline = "middle";
        g.fillStyle = n.destaque ? "#ffd84a" : "rgba(219, 231, 255, .92)";
        g.fillText(nome, n.lx, n.ly);
      });
    });

    // você está aqui: o ponto azul e o leque do que a câmera vê
    const c = this.camera.position;
    const d = this.camera.getWorldDirection(this.ajuda);
    const vx = limitar(X(c.x), 8, w - 8);
    const vy = limitar(Y(c.z), 8, h - 8);
    const ang = Math.atan2(d.z, d.x);
    const meia = Math.min(1.2, (this.camera.fov * PI) / 360 * Math.max(1, this.camera.aspect));
    const leque = g.createRadialGradient(vx, vy, 2, vx, vy, grande ? 70 : 46);
    leque.addColorStop(0, "rgba(63, 160, 255, .55)");
    leque.addColorStop(1, "rgba(63, 160, 255, 0)");
    g.fillStyle = leque;
    g.beginPath();
    g.moveTo(vx, vy);
    g.arc(vx, vy, grande ? 70 : 46, ang - meia, ang + meia);
    g.closePath();
    g.fill();
    g.fillStyle = "#2f8bff";
    g.strokeStyle = "#ffffff";
    g.lineWidth = 2.5;
    g.beginPath(); g.arc(vx, vy, 6.5, 0, PI * 2); g.fill(); g.stroke();

    // embaixo do mapa: o nome do brinquedo apontado (ou escolhido)
    if (this.nomeNoMapa) {
      const alvo = sobre || sel;
      const texto = alvo ? alvo.dados.nome : "Você está aqui · toque num brinquedo";
      if (this.nomeNoMapa.dataset.texto !== texto) {
        this.nomeNoMapa.dataset.texto = texto;
        this.nomeNoMapa.lastChild.textContent = ` ${texto}`;
      }
    }
  }

  /** O nome da máquina em cima dela: a do mouse, ou a escolhida. */
  posicionarRotulo(dt = 0.016) {
    const m = this.sobre || this.selecionada;
    if (!m || !m.grupo.visible) {
      this.rotulo.hidden = true;
      this.rotuloDe = null;
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
    const x = limitar(((v.x + 1) / 2) * w, 80, w - 80);
    const y = limitar(((1 - v.y) / 2) * h, 48, h - 70);
    // O nome desliza até o lugar, sem arredondar pixel a pixel: de longe,
    // com a câmera passeando devagar, o arredondamento fazia ele tremer.
    if (this.rotuloDe !== m) {
      this.rotuloDe = m;
      this.rotuloX = x;
      this.rotuloY = y;
    }
    const k = 1 - Math.exp(-dt * 12);
    this.rotuloX += (x - this.rotuloX) * k;
    this.rotuloY += (y - this.rotuloY) * k;
    this.rotulo.style.transform = `translate3d(${this.rotuloX.toFixed(2)}px, ${this.rotuloY.toFixed(2)}px, 0) translate(-50%, -100%)`;
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
   PASSEIO — um só fluxo por dentro do brinquedo, na altura de uma criança

   Só nos objetos 3D de verdade (o da fábrica e os montados peça por
   peça): por dentro de um volume feito de fotos não há o que ver.

   O passeio é UM caminho que passa por tudo o que o brinquedo tem --
   subir a escadinha, engatinhar na rede, passar pelo tubo, descer o
   tobogã, pular nas camas, cair na espuma --, com o corpo de quem passa
   por ali. Não se escolhe nada: entrou, ele anda sozinho. A pessoa pode
   olhar em volta (arrastar; o olhar volta sozinho para o caminho),
   pausar (o botão ou a barra de espaço) e sair (o botão ou Esc).
   ====================================================================== */
const OLHOS = 0.85; // altura dos olhos acima do piso: uma criança

/* Cada ponto do caminho é [x, y, z, modo, extras] no objeto (metros, frente
   em +z, y = a altura dos PÉS ali) e o modo é o jeito de chegar nele:
     ir          desliza da entrada até o começo
     andar       passo normal (a cabeça balança de leve)
     subir       escada e escadinha: devagar, olhando para cima
     rede        engatinhando na rede: balança para os lados
     tubo        agachado, dentro do tubo
     viga        andando na beirada, equilibrando
     pular       quicando na cama elástica
     enterrada   o pulo grande da enterrada, até a cesta
     escorregar  escorregador e tobogã: sentado, acelerando, deitando nas curvas
     cair        o pulo na piscina de espuma ou de bolinhas (afunda)
   Extras: pausa (segundos parado), olhar (o ponto que se olha na pausa),
   evento (avisa a animação do objeto: "swish:2" = o próximo arremesso vai
   na cesta 2, a da enterrada).
   O caminho é calculado uma vez (uma curva amostrada a cada 6 cm): andar
   nele não custa conta nenhuma por quadro. */

/* O brinquedão: o projeto é em milímetros, como o .3ds (x ao longo, y para
   a frente, z para cima); o objeto 3D é o mesmo desenho, centralizado. */
const BQ = (x, y, z) => [-x / 1000 - 5.8705, z / 1000, y / 1000 + 1.948];

/** O tobogã em espiral do brinquedão (o desenho do objeto), com os pés no fundo do tubo. */
function toboganDoBrinquedao() {
  const cx = -10590;
  const cy = -1500;
  const raio = 650;
  const a0 = (-50 * PI) / 180;
  const a1 = 2 * PI;
  const pontos = [];
  for (let i = 0; i <= 24; i++) {
    const t = i / 24;
    const a = a0 + (a1 - a0) * t;
    pontos.push([...BQ(cx + raio * Math.cos(a), cy + raio * Math.sin(a), 2404 - t * 1974 - 300), "escorregar"]);
  }
  pontos.push([...BQ(cx + raio, cy + 380, 95), "escorregar"], [...BQ(cx + raio, cy + 700, 90), "escorregar"]);
  return pontos;
}

/** O escorregador duplo ondulado (a pista da direita), com os pés na pista. */
function escorregadorDuplo() {
  const x = -9023.5 + 260;
  const pontos = [];
  for (let i = 0; i <= 18; i++) {
    const t = i / 18;
    const z = 1104 - 844 * t + 110 * Math.sin(t * PI * 3) * (1 - t) - (t > 0.85 ? (t - 0.85) * 600 : 0) - 20;
    pontos.push([...BQ(x, -2620 + 1750 * t, z), "escorregar"]);
  }
  return pontos;
}

/** A espiral do tobogã do circuito kids (o desenho do Espaço Esportivo). */
function toboganKids() {
  const pontos = [[16.2, 1.7, 7.35, "escorregar"], [17.2, 1.7, 7.9, "escorregar"]];
  for (let i = 0; i <= 24; i++) {
    const t = i / 24;
    const a = -PI / 2 + t * PI * 3;
    pontos.push([17.8 + 0.75 * Math.cos(a), 1.65 - t * 1.25, 9.4 + 0.75 * Math.sin(a), "escorregar"]);
  }
  return pontos;
}

/** O caminho de cada objeto (pelo id do modelo ou pela forma). */
const CAMINHOS = {
  // escadinha, a rede da torre das bolas, o andar de cima com a rede de
  // escalada, o tubo e o saco, o tobogã em espiral; por trás, o andar do
  // meio e o escorregador duplo; e o brinquedão inteiro visto da frente
  "brinquedao-modelo-2": () => [
    [...BQ(-3323, -1900, 0), "ir"],
    [...BQ(-3323, -2450, 0), "andar"],
    [...BQ(-3323, -2560, 135), "subir"],
    [...BQ(-3323, -2880, 643), "subir"],
    [...BQ(-3323, -3420, 1109), "subir"],
    [...BQ(-2450, -3300, 1833), "subir"],
    [...BQ(-1700, -2700, 1833), "rede", { pausa: 1.4, olhar: BQ(-1318, -3085, 2380) }],
    [...BQ(-2550, -3150, 1833), "rede"],
    [...BQ(-3300, -3150, 2074), "subir"],
    [...BQ(-3850, -3150, 2074), "andar"],
    [...BQ(-4200, -3150, 2480), "rede"],
    [...BQ(-5150, -3150, 2480), "rede"],
    [...BQ(-5500, -3350, 2074), "andar"],
    [...BQ(-6420, -3350, 2074), "andar"],
    [...BQ(-6460, -3150, 2084), "andar"],
    [...BQ(-7460, -3150, 2084), "tubo"],
    [...BQ(-7750, -2850, 2074), "andar"],
    [...BQ(-8300, -2850, 2074), "andar", { pausa: 0.8, olhar: BQ(-7990, -3150, 2450) }],
    [...BQ(-9300, -2900, 2074), "andar"],
    [...BQ(-10150, -2420, 2074), "andar", { pausa: 0.9, olhar: BQ(-10172, -1998, 2150) }],
    [...BQ(-10494, -2268, 2104), "andar"],
    ...toboganDoBrinquedao(),
    [...BQ(-9940, -450, 120), "cair"],
    [...BQ(-9940, 250, 0), "andar"],
    [...BQ(-11950, 100, 0), "andar"],
    [...BQ(-11950, -2000, 0), "andar"],
    [...BQ(-11300, -3950, 0), "andar"],
    [...BQ(-8763, -3950, 0), "andar"],
    [...BQ(-8763, -3550, 1104), "subir"],
    [...BQ(-8763, -2700, 1104), "andar", { pausa: 0.8, olhar: BQ(-8763, -870, 300) }],
    ...escorregadorDuplo(),
    [...BQ(-8763, -650, 120), "cair"],
    [...BQ(-8763, 250, 0), "andar"],
    [...BQ(-5500, 250, 0), "andar", { pausa: 1.6, olhar: BQ(-5500, -2200, 1700) }],
  ],
  // da entrada: o Gol Flash (telão e os dois círculos), as quadras, a
  // piscina de espuma grande, as camas (por cima do varredor), a enterrada
  // na cesta (o Swish arremessa nela), a beirada das piscinas do percurso,
  // o circuito kids com a rede e o tobogã, e o espaço inteiro no fim
  "espaco-esportivo-modelo-1": () => [
    [0, 0.05, 10.6, "ir"],
    [-9.5, 0.05, 7.2, "andar", { pausa: 2.5, olhar: [-9.5, 2.0, -0.55] }],
    [-12.5, 0.05, 5.6, "andar", { pausa: 2, olhar: [-12.5, 0.2, 2.4] }],
    [-6.5, 0.05, 5.6, "andar", { pausa: 2, olhar: [-6.5, 0.2, 2.4] }],
    [-1.2, 0.05, 2.0, "andar"],
    [-1.2, 0.05, -2.6, "andar", { pausa: 2, olhar: [-5.5, 2.0, -5] }],
    [-1.3, 0.05, -4.0, "andar"],
    [-0.45, 0.45, -4.0, "subir"],
    [0.35, 0.97, -4.0, "subir"],
    [3.6, 0.97, -5.15, "andar", { pausa: 0.8, olhar: [3.6, 0.9, -8.5] }],
    [3.6, 0.65, -8.2, "cair", { pausa: 1.6, olhar: [3.6, 2.4, -11.2] }],
    [3.6, 0.97, -5.4, "subir"],
    [3.6, 0.98, -2.7, "pular"],
    [1.6, 0.98, 0.3, "pular"],
    [3.6, 0.98, 2.3, "pular"],
    [5.6, 0.98, 0.3, "pular"],
    [7.6, 0.98, 2.3, "pular"],
    [9.6, 0.98, 0.3, "pular"],
    [7.6, 0.98, -1.7, "pular"],
    [9.6, 0.98, -3.7, "pular"],
    [11.6, 0.98, -5.7, "pular"],
    [11.6, 0.98, -7.7, "pular", { evento: "swish:2" }],
    [11.6, 0.97, -8.85, "andar"],
    [11.6, 1.9, -10.25, "enterrada", { pausa: 0.7, olhar: [11.6, 2.8, -10.88] }],
    [11.6, 0.97, -8.4, "cair"],
    [12.75, 0.97, -6.0, "andar"],
    [12.75, 0.97, -0.9, "viga"],
    [14.4, 0.97, -0.7, "viga"],
    [15.6, 0.7, 1.3, "cair", { pausa: 1.6, olhar: [15.1, 2.0, 0.1] }],
    [15.6, 0.97, 3.1, "subir"],
    [15.6, 0.05, 4.2, "cair"],
    [10.0, 0.05, 5.8, "andar"],
    [2.0, 0.05, 5.8, "andar"],
    [2.0, 0.65, 6.7, "subir"],
    [3.4, 0.65, 8.15, "andar"],
    [4.4, 0.65, 8.15, "andar"],
    [5.7, 0.65, 8.85, "andar"],
    [5.7, 1.8, 8.12, "rede"],
    [5.7, 1.85, 7.82, "subir"],
    [8.6, 1.85, 7.84, "andar"],
    [12.0, 1.85, 7.84, "andar"],
    [15.7, 1.85, 7.6, "andar", { pausa: 0.8, olhar: [17.8, 1.0, 9.4] }],
    ...toboganKids(),
    [17.8, 0.3, 10.45, "cair", { pausa: 1.6, olhar: [16.5, 0.6, 10.4] }],
    [17.3, 0.6, 10.95, "subir"],
    [16.8, 0.05, 11.3, "andar"],
    [8.0, 0.05, 11.1, "andar", { pausa: 2, olhar: [0, 1.5, 0] }],
  ],
  // a cama elástica: a medida sai do cadastro, como a forma dela
  cama_elastica: (m) => {
    const diametro = limitar(Math.min(m.largura, m.fundo), 1.4, 4.6);
    const R = diametro / 2;
    const h = (diametro >= 2.4 ? 0.82 : 0.62) - 0.02;
    return [
      [0, 0, R + 0.75, "andar"],
      [0, h * 0.36, R + 0.4, "subir"],
      [0, h, R - 0.25, "subir"],
      [0, h, 0, "pular", { pausa: 2.5 }],
      [-R * 0.45, h, -R * 0.3, "pular"],
      [R * 0.45, h, -R * 0.25, "pular"],
      [0, h, R * 0.1, "pular", { pausa: 2 }],
      [0, h, R - 0.3, "andar"],
      [0, h * 0.5, R + 0.35, "subir"],
      [0, 0, R + 1.2, "andar"],
    ];
  },
};

/** Um objeto sem caminho próprio: a volta em torno dele, parando em cada lado. */
function voltaEmVolta(m) {
  const a = (m.W || m.largura) / 2 + 0.9;
  const b = (m.D || m.fundo) / 2 + 0.9;
  const centro = [0, (m.H || m.altura) * 0.4, 0];
  const pontos = [];
  for (let i = 0; i <= 8; i++) {
    const t = (i / 8) * PI * 2;
    pontos.push([Math.sin(t) * a, 0, Math.cos(t) * b, "andar", i % 2 ? {} : { pausa: 1.2, olhar: centro }]);
  }
  return pontos;
}

/** O passo (m/s), a altura dos olhos, o quique e o nome de cada modo. */
const MODOS_DO_PASSEIO = {
  ir: { v: 6, olhos: OLHOS, nome: "Chegando" },
  andar: { v: 1.4, olhos: OLHOS, nome: "Passeando" },
  subir: { v: 0.55, olhos: OLHOS, olhar: 0.22, nome: "Subindo" },
  rede: { v: 0.6, olhos: 0.6, nome: "Na rede" },
  tubo: { v: 0.7, olhos: 0.45, nome: "No túnel" },
  viga: { v: 0.75, olhos: OLHOS, nome: "Na beirada" },
  pular: { v: 1.5, olhos: OLHOS, quique: 0.8, nome: "Pulando" },
  enterrada: { v: 1.2, olhos: OLHOS, quique: 1.2, nome: "Enterrada!" },
  escorregar: { v: 4.6, olhos: 0.55, nome: "Escorregando!" },
  cair: { v: 2.4, olhos: 0.45, olhar: -0.3, nome: "Tchibum!" },
};

class Passeio {
  constructor(arena, maquina) {
    const T = arena.T;
    this.arena = arena;
    this.maquina = maquina;
    this.pes = new T.Vector3();
    this.yaw = 0;
    this.pitch = -0.08;
    this.olhos = OLHOS;
    this.extra = { yaw: 0, pitch: 0, tempo: 0 }; // o olhar em volta (arrastando)
    this.pausado = false;
    this.fim = false;
    this.raio = new T.Raycaster();
    this.baixo = new T.Vector3(0, -1, 0);
    this.normal = new T.Vector3();
    this.origem = new T.Vector3();
    const caminho = CAMINHOS[maquina.dados.modelo_id] || CAMINHOS[maquina.forma] || voltaEmVolta;
    this.pontos = caminho(maquina);
    // num espaço grande (o parque de trampolins), o passo é mais largo
    this.ritmo = Math.max(maquina.largura, maquina.fundo) > 15 ? 1.3 : 1;
    this.aoApertar = (evento) => this.tecla(evento);
  }

  entrar() {
    const T = this.arena.T;
    const m = this.maquina;
    m.grupo.updateMatrixWorld(true);
    // começa na frente do brinquedo, olhando para dentro dele
    const D = m.D || m.fundo;
    this.pes.set(0, 0, D / 2 + 0.9).applyMatrix4(m.grupo.matrixWorld);
    this.pes.y = this.piso(this.pes.x, this.pes.z);
    const centro = new T.Vector3().setFromMatrixPosition(m.grupo.matrixWorld);
    this.yaw = Math.atan2(-(centro.x - this.pes.x), -(centro.z - this.pes.z));
    window.addEventListener("keydown", this.aoApertar);
    const camera = this.arena.camera;
    camera.rotation.order = "YXZ";
    camera.fov = 72;
    camera.near = 0.05; // de perto: grade, rede e degrau a um palmo dos olhos
    camera.updateProjectionMatrix();
    this.montarCaminho();
    this.quadro(0);
  }

  sair() {
    window.removeEventListener("keydown", this.aoApertar);
    // a órbita parte de onde o passeio parou: a saída é um voo, não um salto
    const camera = this.arena.camera;
    const c3 = this.arena.camera3d;
    const olhar = new this.arena.T.Vector3();
    camera.getWorldDirection(olhar);
    c3.alvo.copy(camera.position).addScaledVector(olhar, 2);
    c3.raio = 2;
    c3.phi = Math.acos(limitar(-olhar.y, -1, 1));
    c3.theta = Math.atan2(-olhar.x, -olhar.z);
    c3.thetaDesejado = c3.theta;
  }

  tecla(evento) {
    if (evento.key === "Escape") {
      evento.preventDefault();
      this.arena.sairPasseio();
    } else if (evento.key === " " && !evento.target.closest("input, textarea, select")) {
      evento.preventDefault();
      this.alternarPausa();
    }
  }

  /** Arrastar: olha em volta; o olhar volta sozinho para o caminho. */
  olhar(dx, dy) {
    this.extra.yaw -= dx * 0.005;
    this.extra.pitch = limitar(this.extra.pitch - dy * 0.004, -1, 1);
    this.extra.tempo = 1.6;
  }

  /** O piso mais alto embaixo de (x, z): onde os pés ficam na entrada. */
  piso(x, z) {
    let melhor = 0;
    for (const [ox, oz] of [[0, 0], [0.1, 0], [-0.1, 0], [0, 0.1], [0, -0.1]]) {
      this.origem.set(x + ox, this.pes.y + 1, z + oz);
      this.raio.set(this.origem, this.baixo);
      this.raio.far = 9;
      for (const acerto of this.raio.intersectObject(this.maquina.grupo, true)) {
        if (!acerto.face) continue;
        this.normal.copy(acerto.face.normal).transformDirection(acerto.object.matrixWorld);
        if (this.normal.y < 0.55) continue;
        melhor = Math.max(melhor, acerto.point.y);
        break;
      }
    }
    return melhor;
  }

  /**
   * O caminho: os pontos (no objeto) viram uma curva no mundo, amostrada a
   * cada 6 cm, com o modo de cada trecho e a pausa e o evento no fim dele.
   * Ele sai de onde a pessoa entrou.
   */
  montarCaminho() {
    const T = this.arena.T;
    const m = this.maquina;
    const noMundo = (p) => m.corpo.localToWorld(new T.Vector3(p[0], p[1], p[2]));
    const pontos = [{ w: this.pes.clone(), modo: "andar" }, ...this.pontos.map(([x, y, z, modo = "andar", extras = {}]) => ({
      w: noMundo([x, y, z]), modo, ...extras, olhar: extras.olhar ? noMundo(extras.olhar) : null,
    }))];
    const curva = new T.CatmullRomCurve3(pontos.map((p) => p.w), false, "centripetal");
    const n = pontos.length - 1;
    const amostras = [];
    let s = 0;
    for (let k = 0; k < n; k++) {
      const passos = Math.max(2, Math.ceil(pontos[k].w.distanceTo(pontos[k + 1].w) / 0.06));
      for (let j = k ? 1 : 0; j <= passos; j++) {
        const p = curva.getPoint((k + j / passos) / n);
        if (amostras.length) s += p.distanceTo(amostras[amostras.length - 1].p);
        amostras.push({ p, s, modo: pontos[k + 1].modo });
      }
      const fim = amostras[amostras.length - 1];
      const ponto = pontos[k + 1];
      if (ponto.pausa) Object.assign(fim, { pausa: ponto.pausa, olhar: ponto.olhar });
      if (ponto.evento) fim.evento = ponto.evento;
    }
    // o "ir" da entrada até o começo leva no máximo uns 2 segundos
    const ida = amostras.findIndex((a) => a.modo !== "ir");
    this.vIda = Math.max(MODOS_DO_PASSEIO.ir.v, (ida > 0 ? amostras[ida].s : 0) / 2);
    this.amostras = amostras;
    this.total = s;
    this.recomecar();
  }

  /** Do começo (o botão "De novo" no fim). */
  recomecar() {
    Object.assign(this, { s: 0, k: 0, v: 0, espera: 0, olharDaPausa: null, fase: 0, quique: 0, rolar: 0, fim: false, pausado: false, parte: -1, etapa: "" });
    this.extra.yaw = this.extra.pitch = 0;
    this.avisar();
  }

  alternarPausa() {
    if (this.fim) this.recomecar();
    else {
      this.pausado = !this.pausado;
      this.avisar();
    }
  }

  /** O painel: a etapa (Subindo, Na rede, Escorregando!...), o quanto andou, pausado ou no fim. */
  avisar() {
    const modo = this.amostras[Math.min(this.k + 1, this.amostras.length - 1)].modo;
    this.arena.marcarPasseio({
      etapa: this.fim ? "Fim do passeio" : (MODOS_DO_PASSEIO[modo] || MODOS_DO_PASSEIO.andar).nome,
      fracao: this.total ? this.s / this.total : 0,
      pausado: this.pausado,
      fim: this.fim,
    });
  }

  /** O ponto do caminho a `s` metros do começo (na amostra mais perto). */
  pontoNoCaminho(s) {
    const a = this.amostras;
    let lo = this.k;
    let hi = a.length - 1;
    if (s >= a[hi].s) return a[hi].p;
    while (hi - lo > 1) {
      const meio = (lo + hi) >> 1;
      if (a[meio].s <= s) lo = meio;
      else hi = meio;
    }
    return a[hi].p;
  }

  quadro(dt) {
    const a = this.amostras;
    const camera = this.arena.camera;
    const ultima = a.length - 1;
    let modo = a[Math.min(this.k + 1, ultima)].modo;
    const jeito = MODOS_DO_PASSEIO[modo] || MODOS_DO_PASSEIO.andar;
    if (this.pausado || this.fim) {
      this.v = 0;
    } else if (this.espera > 0) {
      this.espera -= dt;
      this.v = 0;
    } else {
      if (modo === "escorregar") this.v = Math.min(jeito.v, Math.max(this.v, 1.4) + dt * 3.4); // acelera na descida
      else if (modo === "ir") this.v = this.vIda;
      else this.v += (jeito.v * this.ritmo - this.v) * (1 - Math.exp(-dt * 5));
      this.s = Math.min(this.total, this.s + this.v * dt);
      while (this.k < ultima && a[this.k + 1].s <= this.s) {
        this.k++;
        const q = a[this.k];
        if (q.evento && this.maquina.animar && this.maquina.animar.evento) this.maquina.animar.evento(q.evento);
        if (q.pausa) {
          this.espera = q.pausa;
          this.olharDaPausa = q.olhar;
          this.s = q.s;
          break;
        }
      }
      if (this.s >= this.total && this.espera <= 0) {
        this.fim = true;
        this.avisar();
      }
    }
    const q0 = a[this.k];
    const q1 = a[Math.min(this.k + 1, ultima)];
    const f = q1.s > q0.s ? limitar((this.s - q0.s) / (q1.s - q0.s), 0, 1) : 0;
    this.pes.lerpVectors(q0.p, q1.p, f);
    modo = q1.modo;

    // para onde se olha: mais à frente no caminho, ou o que a pausa pede
    const parado = this.espera > 0 && this.olharDaPausa;
    const alvo = parado ? this.olharDaPausa : this.pontoNoCaminho(this.s + (modo === "escorregar" ? 1.1 : 1.6));
    const dx = alvo.x - this.pes.x;
    const dz = alvo.z - this.pes.z;
    const longe = Math.hypot(dx, dz);
    const k = 1 - Math.exp(-dt * (modo === "escorregar" ? 6 : 3.2));
    if (longe > 0.08 && !this.fim) {
      let delta = Math.atan2(-dx, -dz) - this.yaw;
      delta = Math.atan2(Math.sin(delta), Math.cos(delta));
      const antes = this.yaw;
      this.yaw += delta * k;
      // no tobogã, o corpo deita para dentro da curva
      if (modo === "escorregar") this.rolar += (limitar(((this.yaw - antes) / Math.max(dt, 0.001)) * 0.12, -0.32, 0.32) - this.rolar) * k;
    }
    if (modo !== "escorregar") this.rolar *= 1 - k;
    if (!this.fim) {
      const subida = parado ? alvo.y - (this.pes.y + this.olhos) : alvo.y - this.pes.y;
      const pitchAlvo = limitar(Math.atan2(subida, Math.max(longe, 0.3)) * (parado ? 1 : 0.7) + (parado ? 0 : jeito.olhar || 0), -1.1, 0.9);
      this.pitch += (pitchAlvo - this.pitch) * k;
    }

    // o corpo: o passo, o balanço da rede e da viga, o quique na cama
    const andando = this.v > 0.05;
    if (!this.pausado) this.fase += dt;
    this.quique += ((this.fim ? 0 : jeito.quique || 0) - this.quique) * (1 - Math.exp(-dt * 4));
    this.olhos += ((this.fim ? OLHOS : jeito.olhos) - this.olhos) * (1 - Math.exp(-dt * 5));
    let sobe = Math.abs(Math.sin(this.fase * 4.4)) * this.quique;
    let rolar = this.rolar;
    if (andando && (modo === "andar" || modo === "subir")) sobe += Math.abs(Math.sin(this.fase * 5.6)) * 0.03;
    if (!this.fim && (modo === "rede" || modo === "viga")) {
      sobe += Math.sin(this.fase * 3.6) * 0.04;
      rolar += Math.sin(this.fase * 2.1) * (modo === "rede" ? 0.08 : 0.05);
    }
    if (this.arena.reduzido) { sobe = 0; rolar = 0; }

    // o olhar em volta (arrastando) volta devagar para o caminho; parado, fica
    this.extra.tempo -= dt;
    if (this.extra.tempo <= 0 && !this.pausado && !this.fim) {
      const volta = 1 - Math.exp(-dt * 2.5);
      this.extra.yaw *= 1 - volta;
      this.extra.pitch *= 1 - volta;
    }
    camera.position.set(this.pes.x, this.pes.y + this.olhos + sobe, this.pes.z);
    camera.rotation.set(limitar(this.pitch + this.extra.pitch, -1.3, 1.3), this.yaw + this.extra.yaw, rolar, "YXZ");
    this.atualizarMapa();
    const parte = Math.round((this.s / this.total) * 100);
    const etapa = MODOS_DO_PASSEIO[modo] ? modo : "andar";
    if (parte !== this.parte || etapa !== this.etapa) {
      this.parte = parte;
      this.etapa = etapa;
      this.avisar();
    }
  }

  /** O mapa só se redesenha quando a pessoa se mexe (sem conta à toa). */
  atualizarMapa() {
    const marca = `${this.pes.x.toFixed(2)},${this.pes.z.toFixed(2)},${(this.yaw + this.extra.yaw).toFixed(2)}`;
    if (marca !== this.ultimaMarca) {
      this.ultimaMarca = marca;
      this.desenharMapa();
    }
  }

  /**
   * O mapa visto de cima: a câmera ortográfica fotografa o brinquedo uma
   * vez (com o pedestal), com o fundo do brinquedo para cima, como numa
   * planta. Depois, a cada quadro, só se desenha a bolinha e o leque.
   */
  desenharMapaBase(tela) {
    const a = this.arena;
    const T = a.T;
    const m = this.maquina;
    this.mapa = tela;
    const lado = Math.max(m.W || m.largura, m.D || m.fundo) + 2.4;
    this.ladoDoMapa = lado;
    const camera = new T.OrthographicCamera(-lado / 2, lado / 2, lado / 2, -lado / 2, 0.1, 200);
    const centro = new T.Vector3().setFromMatrixPosition(m.grupo.matrixWorld);
    camera.position.set(centro.x, 60, centro.z);
    camera.up.set(0, 0, -1).applyQuaternion(m.grupo.quaternion);
    camera.lookAt(centro);
    const n = 256;
    const alvo = new T.WebGLRenderTarget(n, n);
    alvo.texture.colorSpace = T.SRGBColorSpace;
    const neblina = a.cena.fog;
    const fundo = a.cena.background;
    a.cena.fog = null;
    a.cena.background = new T.Color("#0a1636");
    a.renderer.setRenderTarget(alvo);
    a.renderer.render(a.cena, camera);
    a.renderer.setRenderTarget(null);
    a.cena.fog = neblina;
    a.cena.background = fundo;
    const px = new Uint8Array(n * n * 4);
    a.renderer.readRenderTargetPixels(alvo, 0, 0, n, n, px);
    alvo.dispose();
    const base = document.createElement("canvas");
    base.width = base.height = n;
    const imagem = base.getContext("2d").createImageData(n, n);
    for (let y = 0; y < n; y++) imagem.data.set(px.subarray((n - 1 - y) * n * 4, (n - y) * n * 4), y * n * 4);
    base.getContext("2d").putImageData(imagem, 0, 0);
    this.mapaBase = base;
    this.desenharMapa();
  }

  desenharMapa() {
    if (!this.mapa || !this.mapaBase) return;
    const g = this.mapa.getContext("2d");
    const w = this.mapa.width;
    g.clearRect(0, 0, w, w);
    g.drawImage(this.mapaBase, 0, 0, w, w);
    // onde a pessoa está, no desenho (o fundo do brinquedo fica em cima)
    const local = this.maquina.grupo.worldToLocal(this.arena.ajuda.copy(this.pes));
    const x = (local.x / this.ladoDoMapa + 0.5) * w;
    const y = (local.z / this.ladoDoMapa + 0.5) * w;
    const giro = this.yaw + this.extra.yaw - this.maquina.grupo.rotation.y;
    g.save();
    g.translate(x, y);
    g.rotate(-giro);
    const leque = g.createRadialGradient(0, 0, 2, 0, 0, w * 0.16);
    leque.addColorStop(0, "rgba(255, 216, 74, .65)");
    leque.addColorStop(1, "rgba(255, 216, 74, 0)");
    g.fillStyle = leque;
    g.beginPath();
    g.moveTo(0, 0);
    g.arc(0, 0, w * 0.16, -PI / 2 - 0.55, -PI / 2 + 0.55);
    g.closePath();
    g.fill();
    g.restore();
    g.fillStyle = "#ffd84a";
    g.strokeStyle = "#071433";
    g.lineWidth = w * 0.012;
    g.beginPath();
    g.arc(x, y, w * 0.028, 0, PI * 2);
    g.fill();
    g.stroke();
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
    if (maquina.grande) {
      this.olharGrande(maquina, vista, centro);
      return;
    }
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

  /**
   * Uma área da roda: a câmera fica do lado do centro, de frente para o
   * trecho, longe o bastante para caber o trecho inteiro na tela.
   */
  olharZona(trecho) {
    const arena = this.arena;
    const camera = arena.camera;
    if (trecho.tipo === "reino") {
      // o reino inteiro, visto de cima e da frente (do lado da roda)
      const th = Math.tan((camera.fov * PI) / 360) * camera.aspect;
      const largura = trecho.x1 - trecho.x0 + 4;
      const fundo = trecho.z1 - trecho.z0;
      this.alvoDesejado.set((trecho.x0 + trecho.x1) / 2, 1.5, (trecho.z0 + trecho.z1) / 2);
      this.raioDesejado = Math.min(140, (largura / 2 / th) * 1.05 + fundo / 2);
      this.phiDesejado = 0.85;
      let delta = 0 - this.thetaDesejado;
      delta = Math.atan2(Math.sin(delta), Math.cos(delta));
      this.thetaDesejado += delta;
      return;
    }
    const raio = arena.raio || 8;
    const meio = (trecho.a0 + trecho.a1) / 2;
    const arco = Math.max(0.3, trecho.a1 - trecho.a0);
    const corda = 2 * raio * Math.sin(Math.min(PI, arco) / 2) + 2 * (arena.folga || 1.5);
    const th = Math.tan((camera.fov * PI) / 360) * camera.aspect;
    const r = arco > PI ? raio * 0.35 : raio * 0.9;
    this.alvoDesejado.set(Math.sin(meio) * r, 1.3, Math.cos(meio) * r);
    this.raioDesejado = Math.min(raio * 3.4 + 12, Math.max(7, (corda / 2 / th) * 1.08 + 1.5));
    this.phiDesejado = 0.98;
    let delta = Math.atan2(-Math.sin(meio), -Math.cos(meio)) - this.thetaDesejado;
    delta = Math.atan2(Math.sin(delta), Math.cos(delta));
    this.thetaDesejado += delta;
  }

  /**
   * O grande (um brinquedão de 11 m) fica parado: cada vista leva a câmera
   * para aquele lado dele, longe o bastante para caber inteiro na tela.
   */
  olharGrande(maquina, vista, centro) {
    const T = this.arena.T;
    const camera = this.arena.camera;
    const LADO = { direita: [1, 0], esquerda: [-1, 0], costas: [0, -1] };
    const [lx, lz] = LADO[vista] || [0, 1];
    const direcao = new T.Vector3(lx, 0, lz).applyQuaternion(maquina.grupo.quaternion);
    const tv = Math.tan((camera.fov * PI) / 360);
    const th = tv * camera.aspect;
    const W = maquina.W || maquina.largura;
    const D = maquina.D || maquina.fundo;
    const deLado = vista === "direita" || vista === "esquerda";
    const largo = deLado ? D : W;
    const fundo = deLado ? W : D;
    let raio = Math.max(largo / 2 / th, maquina.H / 2 / tv) * (largo > 15 ? 1.3 : 1.15) + fundo / 2;
    if (vista === "cima") raio = Math.max(W / 2 / th, D / 2 / tv) * 1.1 + maquina.H;
    this.raioDesejado = Math.min(30, raio);
    this.alvoDesejado.y = maquina.alturaP + maquina.H * (vista === "baixo" ? 0.6 : 0.45);
    this.phiDesejado = vista === "cima" ? 0.3 : vista === "baixo" ? 1.42 : 1.22;
    let delta = Math.atan2(direcao.x, direcao.z) - this.thetaDesejado;
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
        if (evento.pointerType === "mouse" && !arena.passeio) {
          arena.sobre = arena.escolher(evento.clientX, evento.clientY);
          canvas.classList.toggle("sobre-maquina", Boolean(arena.sobre) || Boolean(arena.zonaSob(evento.clientX, evento.clientY)));
        }
        return;
      }
      const dx = evento.clientX - anterior.x;
      const dy = evento.clientY - anterior.y;
      this.ponteiros.set(evento.pointerId, { x: evento.clientX, y: evento.clientY });
      arena.ocioso = 0;
      if (arena.passeio) {
        arena.passeio.olhar(dx, dy);
        return;
      }
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
        if (arena.passeio) return; // no passeio, tocar é só olhar
        const maquina = arena.escolher(evento.clientX, evento.clientY);
        if (maquina) arena.selecionar(maquina);
        else {
          const zona = arena.zonaSob(evento.clientX, evento.clientY);
          if (zona && zona !== arena.zona) arena.escolherZona(zona);
        }
      }
    };
    canvas.addEventListener("pointerup", soltar);
    canvas.addEventListener("pointercancel", soltar);

    canvas.addEventListener("wheel", (evento) => {
      evento.preventDefault();
      arena.ocioso = 0;
      if (arena.passeio) return; // o passeio anda sozinho
      this.raioDesejado *= Math.exp(evento.deltaY * 0.0012);
      this.limitar();
    }, { passive: false });
  }

  limitar() {
    this.phiDesejado = Math.min(1.45, Math.max(0.22, this.phiDesejado));
    const maximo = Math.max((this.arena.raio || 8) * 3.6 + 14, this.arena.longeDosReinos ? 140 : 0);
    this.raioDesejado = Math.min(maximo, Math.max(2.4, this.raioDesejado));
  }

  atualizar(dt) {
    const arena = this.arena;
    // ninguém mexendo há um tempo e nada escolhido: a câmera passeia sozinha
    if (!arena.reduzido && !arena.selecionada && arena.ocioso > 3.5 && this.ponteiros.size === 0) {
      this.thetaDesejado += dt * 0.1;
    }
    // o grande escolhido em "Girar": a câmera dá a volta nele
    const m = arena.selecionada;
    if (!arena.reduzido && m && m.grande && arena.vistaAtual === "girar" && this.ponteiros.size === 0) {
      this.thetaDesejado += dt * 0.16;
    }
    const k = 1 - Math.exp(-dt * (arena.reduzido ? 20 : 4.2));
    this.alvo.lerp(this.alvoDesejado, k);
    this.theta += (this.thetaDesejado - this.theta) * k;
    this.phi += (this.phiDesejado - this.phi) * k;
    this.raio += (this.raioDesejado - this.raio) * k;

    const s = Math.sin(this.phi);
    const p = arena.camera.position.set(
      this.alvo.x + this.raio * s * Math.sin(this.theta),
      this.alvo.y + this.raio * Math.cos(this.phi),
      this.alvo.z + this.raio * s * Math.cos(this.theta),
    );
    // nunca embaixo nem dentro de um objeto: chegando perto de um, a câmera
    // sobe por cima dele (e olha de cima), sem pulo
    p.y = Math.max(p.y, arena.alturaLivre(p.x, p.z));
    arena.camera.lookAt(this.alvo);
    // o plano de perto vai com a distância: de longe, a profundidade tem
    // precisão de sobra e nada "briga" (pisca) com o que está colado nele
    arena.ajustarPerto(limitar(p.distanceTo(this.alvo) * 0.012, 0.1, 0.6));
  }
}
