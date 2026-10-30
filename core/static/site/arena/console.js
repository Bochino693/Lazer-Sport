/* ======================================================================
   O CONSOLE DOS JOGOS — a máquina em foco no simulador (/jogos/<jogo>/).

   Cada jogo é um módulo (site/arena/jogos/<nome>.js) que só sabe jogar:
   desenhar, andar no tempo e responder ao toque. Tudo o que é igual em
   todos -- trocar de jogo, placar, recorde, som, contagem 3-2-1, tela
   cheia, os botões de comando embaixo da tela, pausa quando a aba some
   ou a máquina sai da tela -- mora aqui, uma vez só.

   CONTRATO DE UM JOGO (export default):

     {
       largura: 540, altura: 960,          // tela lógica, em pontos
       contagem: false,                     // opcional: sem o 3-2-1 do console
       artes: { bola: "boliche/bola.webp" }, // relativo ao arquivo do jogo
       criar(api) {                         // devolve a partida
         return {
           iniciar(),          // começa (ou recomeça) uma partida
           atualizar(dt),      // dt em segundos, já limitado a 1/20
           desenhar(ctx),      // contexto 2D em coordenadas lógicas
           apertar(x, y), mover(x, y), soltar(x, y),   // opcionais
           tecla(codigo, apertada),                     // opcional
           destruir(),                                  // opcional
         };
       },
     }

   O QUE O JOGO RECEBE (api):
     api.W, api.H            tamanho lógico
     api.variante            "dragon", "slam"... (o mesmo arquivo serve a família)
     api.img.<nome>          as artes, já carregadas (Image)
     api.som(nome)           clique, ponto, acerto, erro, quica, batida, strike,
                             tiro, vidro, soco, apito, moeda, fim, vitoria,
                             combo, whoosh, nota
     api.placar({pontos, tempo, info})   o painel de cima
     api.terminar({pontos, titulo, detalhe})   fim de partida
     api.contagem(depois)    o 3-2-1 do console no meio da partida (jogo
                             com `contagem: false` que escolhe algo antes
                             de começar: a contagem vem depois da escolha)
     api.efeitos.explosao(x, y, {cor, n, velocidade, tamanho, gravidade})
     api.efeitos.texto(texto, x, y, {cor, tamanho})
     api.tremer(forca)       sacode a tela
     api.vibrar(ms)          sacode o celular
     api.aleatorio(a, b), api.inteiro(a, b)
     api.texto(ctx, texto, x, y, {tamanho, cor, alinhar, peso, contorno, sombra, base})
     api.reduzido            a pessoa pediu menos movimento
   ====================================================================== */

const CHAVE_SOM = "ls-jogos-som";
const PREFIXO_RECORDE = "ls-jogo-recorde:";

function ler(chave) {
  try { return window.localStorage.getItem(chave); } catch (erro) { return null; }
}

function gravar(chave, valor) {
  try { window.localStorage.setItem(chave, valor); } catch (erro) { /* aba anônima */ }
}

/* ----------------------------------------------------------------------
   SOM SINTETIZADO

   Nenhum arquivo de áudio a baixar: cada efeito é uma receita de
   osciladores e ruído, tocada pelo WebAudio. O contexto só nasce depois
   de um toque da pessoa -- é a regra dos navegadores, e é também o certo.
   ---------------------------------------------------------------------- */
class Som {
  constructor() {
    this.ligado = ler(CHAVE_SOM) !== "0";
    this.ctx = null;
  }

  acordar() {
    if (this.ctx || !this.ligado) {
      if (this.ctx && this.ctx.state === "suspended") this.ctx.resume();
      return;
    }
    const Contexto = window.AudioContext || window.webkitAudioContext;
    if (!Contexto) return;
    this.ctx = new Contexto();
    this.mestre = this.ctx.createGain();
    this.mestre.gain.value = 0.55;
    this.mestre.connect(this.ctx.destination);
  }

  alternar() {
    this.ligado = !this.ligado;
    gravar(CHAVE_SOM, this.ligado ? "1" : "0");
    if (this.ligado) this.acordar();
    else if (this.ctx) this.ctx.suspend();
    return this.ligado;
  }

  tom(freq, dur, { tipo = "square", volume = 0.25, ate = null, atraso = 0 } = {}) {
    const c = this.ctx;
    const t = c.currentTime + atraso;
    const osc = c.createOscillator();
    const ganho = c.createGain();
    osc.type = tipo;
    osc.frequency.setValueAtTime(freq, t);
    if (ate) osc.frequency.exponentialRampToValueAtTime(Math.max(20, ate), t + dur);
    ganho.gain.setValueAtTime(volume, t);
    ganho.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    osc.connect(ganho).connect(this.mestre);
    osc.start(t);
    osc.stop(t + dur + 0.02);
  }

  ruido(dur, { volume = 0.3, filtro = 1200, atraso = 0, tipoFiltro = "lowpass" } = {}) {
    const c = this.ctx;
    const t = c.currentTime + atraso;
    const quadros = Math.max(1, Math.floor(c.sampleRate * dur));
    const buffer = c.createBuffer(1, quadros, c.sampleRate);
    const dados = buffer.getChannelData(0);
    for (let i = 0; i < quadros; i++) dados[i] = (Math.random() * 2 - 1) * (1 - i / quadros);
    const fonte = c.createBufferSource();
    fonte.buffer = buffer;
    const f = c.createBiquadFilter();
    f.type = tipoFiltro;
    f.frequency.value = filtro;
    const ganho = c.createGain();
    ganho.gain.setValueAtTime(volume, t);
    ganho.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    fonte.connect(f).connect(ganho).connect(this.mestre);
    fonte.start(t);
  }

  tocar(nome) {
    if (!this.ligado) return;
    this.acordar();
    if (!this.ctx) return;
    const receitas = {
      clique: () => this.tom(880, 0.06, { tipo: "triangle", volume: 0.18 }),
      ponto: () => { this.tom(660, 0.08, { volume: 0.16 }); this.tom(990, 0.12, { volume: 0.16, atraso: 0.07 }); },
      acerto: () => this.tom(520, 0.14, { tipo: "triangle", volume: 0.3, ate: 1040 }),
      erro: () => this.tom(220, 0.28, { tipo: "sawtooth", volume: 0.18, ate: 90 }),
      quica: () => this.tom(180, 0.09, { tipo: "sine", volume: 0.35, ate: 90 }),
      batida: () => { this.ruido(0.18, { volume: 0.45, filtro: 900 }); this.tom(120, 0.15, { tipo: "sine", volume: 0.3, ate: 60 }); },
      strike: () => {
        this.ruido(0.5, { volume: 0.5, filtro: 1600 });
        [523, 659, 784, 1046].forEach((f, i) => this.tom(f, 0.18, { volume: 0.14, atraso: 0.12 + i * 0.08 }));
      },
      tiro: () => { this.ruido(0.12, { volume: 0.4, filtro: 3000, tipoFiltro: "highpass" }); this.tom(900, 0.1, { tipo: "square", volume: 0.12, ate: 120 }); },
      vidro: () => { this.ruido(0.25, { volume: 0.32, filtro: 4000, tipoFiltro: "highpass" }); this.tom(2400, 0.2, { tipo: "triangle", volume: 0.08, ate: 1800 }); },
      soco: () => { this.ruido(0.2, { volume: 0.6, filtro: 600 }); this.tom(90, 0.25, { tipo: "sine", volume: 0.5, ate: 40 }); },
      apito: () => { this.tom(2100, 0.35, { tipo: "square", volume: 0.1 }); this.tom(2150, 0.35, { tipo: "square", volume: 0.06 }); },
      moeda: () => { this.tom(988, 0.07, { volume: 0.14 }); this.tom(1319, 0.25, { volume: 0.14, atraso: 0.07 }); },
      fim: () => [784, 659, 523, 392].forEach((f, i) => this.tom(f, 0.22, { volume: 0.14, atraso: i * 0.16 })),
      vitoria: () => [523, 659, 784, 1046, 784, 1046].forEach((f, i) => this.tom(f, 0.18, { volume: 0.14, atraso: i * 0.11 })),
      combo: () => [880, 1108, 1318].forEach((f, i) => this.tom(f, 0.1, { volume: 0.12, atraso: i * 0.05 })),
      whoosh: () => this.ruido(0.3, { volume: 0.25, filtro: 700, tipoFiltro: "bandpass" }),
      nota: () => this.tom(1200, 0.08, { tipo: "sine", volume: 0.22 }),
      contagem: () => this.tom(440, 0.12, { tipo: "square", volume: 0.14 }),
      vai: () => this.tom(880, 0.3, { tipo: "square", volume: 0.16 }),
    };
    (receitas[nome] || receitas.clique)();
  }
}

/* ----------------------------------------------------------------------
   EFEITOS COMPARTILHADOS — faíscas e textos que sobem
   ---------------------------------------------------------------------- */
class Efeitos {
  constructor(api) {
    this.api = api;
    this.particulas = [];
    this.textos = [];
  }

  limpar() {
    this.particulas.length = 0;
    this.textos.length = 0;
  }

  explosao(x, y, { cor = "#ffd700", n = 18, velocidade = 260, tamanho = 5, gravidade = 500, vida = 0.8 } = {}) {
    const cores = Array.isArray(cor) ? cor : [cor];
    const quantidade = this.api.reduzido ? Math.ceil(n / 3) : n;
    for (let i = 0; i < quantidade; i++) {
      const angulo = Math.random() * Math.PI * 2;
      const v = velocidade * (0.35 + Math.random() * 0.65);
      this.particulas.push({
        x, y,
        vx: Math.cos(angulo) * v,
        vy: Math.sin(angulo) * v - velocidade * 0.3,
        vida: vida * (0.6 + Math.random() * 0.4),
        total: vida,
        tamanho: tamanho * (0.6 + Math.random() * 0.8),
        cor: cores[i % cores.length],
        gravidade,
      });
    }
  }

  texto(texto, x, y, { cor = "#fff", tamanho = 42, vida = 1.1 } = {}) {
    this.textos.push({ texto, x, y, cor, tamanho, vida, total: vida });
  }

  atualizar(dt) {
    for (const p of this.particulas) {
      p.vida -= dt;
      p.vy += p.gravidade * dt;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
    }
    this.particulas = this.particulas.filter((p) => p.vida > 0);
    for (const t of this.textos) {
      t.vida -= dt;
      t.y -= 60 * dt;
    }
    this.textos = this.textos.filter((t) => t.vida > 0);
  }

  desenhar(ctx) {
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    for (const p of this.particulas) {
      ctx.globalAlpha = Math.max(0, p.vida / p.total);
      ctx.fillStyle = p.cor;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.tamanho, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
    for (const t of this.textos) {
      const progresso = 1 - t.vida / t.total;
      const escala = progresso < 0.15 ? 0.6 + progresso / 0.15 * 0.5 : 1.1 - Math.min(0.1, (progresso - 0.15));
      ctx.save();
      ctx.globalAlpha = Math.min(1, t.vida / (t.total * 0.35));
      this.api.texto(ctx, t.texto, t.x, t.y, {
        tamanho: t.tamanho * escala, cor: t.cor, contorno: "rgba(0,0,0,.65)", peso: 900,
      });
      ctx.restore();
    }
  }
}

/* ----------------------------------------------------------------------
   O CONSOLE
   ---------------------------------------------------------------------- */
class Console {
  constructor(raiz) {
    this.raiz = raiz;
    this.canvas = raiz.querySelector("[data-console-tela]");
    this.ctx = this.canvas.getContext("2d");
    this.transformarNativo = CanvasRenderingContext2D.prototype.setTransform.bind(this.ctx);
    this.quadro = raiz.querySelector("[data-console-quadro]");
    this.capa = raiz.querySelector("[data-console-capa]");
    this.fim = raiz.querySelector("[data-console-fim]");
    this.carregando = raiz.querySelector("[data-console-carregando]");
    this.botaoSom = raiz.querySelector("[data-console-som]");
    this.som = new Som();
    this.modulos = new Map();
    this.estado = "fechado";
    this.jogo = null;
    this.partida = null;
    this.tremor = 0;
    this.contagem = 0;
    this.quadroAnimacao = 0;
    this.reduzido = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    this.ligarEventos();
    this.mostrarSom();
  }

  /* ---------- eventos fixos ---------- */
  ligarEventos() {
    this.raiz.addEventListener("click", (evento) => {
      const alvo = evento.target.closest("[data-console-acao]");
      if (!alvo) return;
      const acao = alvo.dataset.consoleAcao;
      if (acao === "jogar") this.comecar();
      else if (acao === "reiniciar") this.reiniciar();
      else if (acao === "som") this.mostrarSom(this.som.alternar());
      else if (acao === "tela-cheia") this.telaCheia();
    });

    // Os botões embaixo da tela (as setas, o CHUTAR, o SOCAR) mandam a
    // mesma tecla que o teclado mandaria: apertar e soltar, para os jogos
    // que carregam força enquanto o botão está apertado.
    const presos = new Map();
    const largar = (evento) => {
      const codigo = presos.get(evento.pointerId);
      if (!codigo) return;
      presos.delete(evento.pointerId);
      this.teclaVirtual(codigo, false);
      const botao = this.raiz.querySelector(`[data-console-tecla="${codigo}"]`);
      if (botao) botao.classList.remove("apertado");
    };
    this.raiz.addEventListener("pointerdown", (evento) => {
      const botao = evento.target.closest("[data-console-tecla]");
      if (!botao) return;
      evento.preventDefault();
      try { botao.setPointerCapture(evento.pointerId); } catch (erro) { /* sem captura */ }
      presos.set(evento.pointerId, botao.dataset.consoleTecla);
      botao.classList.add("apertado");
      this.som.acordar();
      this.teclaVirtual(botao.dataset.consoleTecla, true);
    });
    this.raiz.addEventListener("pointerup", largar);
    this.raiz.addEventListener("pointercancel", largar);
    // Enter/espaço num botão focado pelo teclado: aperta e solta.
    this.raiz.addEventListener("keydown", (evento) => {
      const botao = evento.target.closest && evento.target.closest("[data-console-tecla]");
      if (!botao || (evento.key !== "Enter" && evento.key !== " ")) return;
      evento.preventDefault();
      evento.stopPropagation();
      this.teclaVirtual(botao.dataset.consoleTecla, true);
      window.setTimeout(() => this.teclaVirtual(botao.dataset.consoleTecla, false), 120);
    });

    const ponto = (evento) => {
      const r = this.canvas.getBoundingClientRect();
      return [
        (evento.clientX - r.left) * (this.jogo.largura / r.width),
        (evento.clientY - r.top) * (this.jogo.altura / r.height),
      ];
    };

    this.canvas.addEventListener("pointerdown", (evento) => {
      if (this.estado !== "jogando" || !this.partida) return;
      evento.preventDefault();
      try { this.canvas.setPointerCapture(evento.pointerId); } catch (erro) { /* sem captura */ }
      this.som.acordar();
      if (this.partida.apertar) this.partida.apertar(...ponto(evento), evento.pointerId);
    });
    this.canvas.addEventListener("pointermove", (evento) => {
      if (this.estado !== "jogando" || !this.partida || !this.partida.mover) return;
      this.partida.mover(...ponto(evento), evento.pointerId);
    });
    const soltar = (evento) => {
      if (this.estado !== "jogando" || !this.partida || !this.partida.soltar) return;
      this.partida.soltar(...ponto(evento), evento.pointerId);
    };
    this.canvas.addEventListener("pointerup", soltar);
    this.canvas.addEventListener("pointercancel", soltar);

    const teclas = (apertada) => (evento) => {
      if (this.estado === "fechado") return;
      if (evento.key === "Escape") return;
      // Quem está digitando ou navegando pelo seletor não joga sem querer.
      const alvo = evento.target;
      if (alvo && alvo !== document.body && alvo !== this.canvas && alvo.closest &&
          alvo.closest("input, textarea, select, a, button")) return;
      const codigo = evento.code || evento.key;
      if (this.estado !== "jogando") {
        if (apertada && (codigo === "Enter" || codigo === "Space")) {
          evento.preventDefault();
          this.comecar();
        }
        return;
      }
      if (["Space", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(codigo)) evento.preventDefault();
      if (this.partida && this.partida.tecla) this.partida.tecla(codigo, apertada);
    };
    window.addEventListener("keydown", teclas(true));
    window.addEventListener("keyup", teclas(false));

    // Pausa quando a aba some e quando a máquina sai da tela (quem rolou
    // a página para ler a ficha não perde a partida).
    this.visivel = true;
    const acertarPausa = () => {
      if (this.estado === "fechado") return;
      if (document.hidden || !this.visivel) this.pausar();
      else this.retomar();
    };
    document.addEventListener("visibilitychange", acertarPausa);
    if ("IntersectionObserver" in window) {
      new IntersectionObserver((entradas) => {
        this.visivel = entradas[0].isIntersecting;
        acertarPausa();
      }, { threshold: 0.25 }).observe(this.raiz);
    }

    window.addEventListener("resize", () => this.ajustarTela());
    document.addEventListener("fullscreenchange", () => window.setTimeout(() => this.ajustarTela(), 60));
  }

  teclaVirtual(codigo, apertada) {
    if (this.estado === "jogando") {
      if (this.partida && this.partida.tecla) this.partida.tecla(codigo, apertada);
    } else if (apertada && (this.estado === "capa" || this.estado === "fim")) {
      this.comecar();
    }
  }

  mostrarSom(ligado = this.som.ligado) {
    if (!this.botaoSom) return;
    this.botaoSom.setAttribute("aria-pressed", ligado ? "true" : "false");
    this.botaoSom.querySelector("i").className = ligado ? "fa-solid fa-volume-high" : "fa-solid fa-volume-xmark";
    this.botaoSom.setAttribute("aria-label", ligado ? "Desligar o som" : "Ligar o som");
  }

  /* ---------- abrir um jogo ---------- */
  async abrir(dados) {
    this.pararPartida();
    this.dados = dados;
    this.raiz.dispatchEvent(new CustomEvent("console:abrir", { detail: { slug: dados.slug } }));
    this.jogo = null;
    this.escalaMaxima = 2;
    this.raiz.style.setProperty("--cor-jogo", dados.cor || "#ffd700");
    this.raiz.querySelector("[data-console-titulo]").textContent = dados.titulo;
    this.raiz.querySelector("[data-console-maquina]").textContent = dados.maquina || "";
    const logo = this.raiz.querySelector("[data-console-logo]");
    logo.src = dados.miniatura || dados.capa;
    logo.alt = dados.titulo;
    this.capa.querySelector("[data-console-chamada]").textContent = dados.chamada || "";
    this.capa.querySelector("[data-console-comandos]").textContent = dados.comandos || "";
    this.capa.querySelector("[data-console-poster]").src = dados.poster || dados.capa;
    this.atualizarRecorde();

    const maquina = this.fim.querySelector("[data-console-maquina-link]");
    if (dados.maquinaUrl) {
      maquina.href = dados.maquinaUrl;
      maquina.removeAttribute("target");
      maquina.querySelector("span").textContent = "Ver a máquina " + (dados.maquinaNome || "");
    } else {
      const texto = `Olá! Joguei o ${dados.titulo} no site da Lazer & Sport e quero saber da máquina.`;
      maquina.href = `https://wa.me/${dados.whatsapp}?text=${encodeURIComponent(texto)}`;
      maquina.target = "_blank";
      maquina.rel = "noopener";
      maquina.querySelector("span").textContent = "Quero essa máquina";
    }

    this.placar({ pontos: 0, tempo: null, info: "" });
    this.capa.hidden = false;
    this.fim.hidden = true;
    this.estado = "capa";

    this.carregando.textContent = "Carregando o jogo…";
    this.carregando.hidden = false;
    try {
      const jogo = await this.carregar(dados.script);
      // Trocou de jogo enquanto este carregava: fica o último pedido.
      if (this.dados !== dados) return;
      this.jogo = jogo;
      this.criarPartida();
      this.carregando.hidden = true;
      this.ajustarTela();
      this.rodar();
    } catch (erro) {
      console.error("Console: jogo não carregou", erro);
      this.carregando.textContent = "Não foi possível carregar este jogo agora. Tente de novo em instantes.";
    }
  }

  async carregar(url) {
    if (!this.modulos.has(url)) {
      const promessa = import(url).then(async (modulo) => {
        const jogo = modulo.default;
        const imagens = {};
        await Promise.all(Object.entries(jogo.artes || {}).map(([nome, caminho]) => new Promise((resolver) => {
          const img = new Image();
          img.decoding = "async";
          img.onload = () => { imagens[nome] = img; resolver(); };
          img.onerror = () => { console.warn("Console: arte não carregou", caminho); resolver(); };
          img.src = new URL(caminho, new URL(url, window.location.href)).href;
        })));
        return { ...jogo, imagens };
      });
      // falhou (rede): esquece, para a próxima tentativa baixar de novo
      promessa.catch(() => this.modulos.delete(url));
      this.modulos.set(url, promessa);
    }
    return this.modulos.get(url);
  }

  criarPartida() {
    if (this.partida && this.partida.destruir) this.partida.destruir();
    const jogo = this.jogo;
    this.canvas.width = jogo.largura;
    this.canvas.height = jogo.altura;
    this.quadro.style.setProperty("--proporcao", `${jogo.largura} / ${jogo.altura}`);
    this.quadro.dataset.orientacao = jogo.largura > jogo.altura ? "paisagem" : "retrato";

    const api = this.criarApi(jogo);
    this.api = api;
    this.partida = jogo.criar(api);
    if (this.partida.iniciar) this.partida.iniciar();
  }

  criarApi(jogo) {
    const consoleJogo = this;
    const api = {
      W: jogo.largura,
      H: jogo.altura,
      variante: this.dados.variante || "",
      img: jogo.imagens,
      reduzido: this.reduzido,
      som: (nome) => this.som.tocar(nome),
      placar: (dados) => this.placar(dados),
      terminar: (resultado) => this.terminar(resultado),
      contagem: (depois) => this.contar(depois),
      tremer: (forca = 8) => { if (!this.reduzido) this.tremor = Math.max(this.tremor, forca); },
      vibrar: (ms = 30) => { try { if (navigator.vibrate) navigator.vibrate(ms); } catch (erro) { /* sem vibração */ } },
      aleatorio: (a, b) => a + Math.random() * (b - a),
      inteiro: (a, b) => Math.floor(a + Math.random() * (b - a + 1)),
      texto(ctx, texto, x, y, opcoes = {}) {
        const {
          tamanho = 32, cor = "#fff", alinhar = "center", peso = 800,
          contorno = null, sombra = null, base = "middle", fonte = "Poppins, Manrope, system-ui, sans-serif",
        } = opcoes;
        ctx.save();
        ctx.font = `${peso} ${Math.round(tamanho)}px ${fonte}`;
        ctx.textAlign = alinhar;
        ctx.textBaseline = base;
        if (sombra) {
          // O halo em três traços largos e transparentes, e não com
          // shadowBlur: o desfoque do canvas custa caro a cada quadro e
          // derrubava os jogos para 10 fps no celular.
          const alfa = ctx.globalAlpha;
          ctx.lineJoin = "round";
          ctx.strokeStyle = sombra;
          for (const [largura, forca] of [[0.62, 0.1], [0.4, 0.18], [0.22, 0.3]]) {
            ctx.globalAlpha = alfa * forca;
            ctx.lineWidth = tamanho * largura;
            ctx.strokeText(texto, x, y);
          }
          ctx.globalAlpha = alfa;
        }
        if (contorno) {
          ctx.lineJoin = "round";
          ctx.lineWidth = Math.max(2, tamanho * 0.14);
          ctx.strokeStyle = contorno;
          ctx.strokeText(texto, x, y);
        }
        ctx.fillStyle = cor;
        ctx.fillText(texto, x, y);
        ctx.restore();
      },
      get tempo() { return consoleJogo.relogio || 0; },
    };
    api.efeitos = new Efeitos(api);
    return api;
  }

  /* ---------- partida ---------- */
  /* A página pode segurar a partida: o visitante sem conta joga uma vez
     cada jogo (ranking.js cancela o evento e mostra o cadastro). */
  liberar() {
    return this.raiz.dispatchEvent(new CustomEvent("console:jogar", {
      cancelable: true,
      detail: { slug: this.dados && this.dados.slug },
    }));
  }

  comecar(liberado = false) {
    if (!this.jogo || this.estado === "jogando" || this.estado === "contagem") return;
    if (!liberado && !this.liberar()) return;
    this.som.acordar();
    this.som.tocar("moeda");
    this.capa.hidden = true;
    this.fim.hidden = true;
    this.api.efeitos.limpar();
    if (this.partida.iniciar) this.partida.iniciar();
    this.relogio = 0;
    // o jogo que tem a própria contagem (o Hit Music conta em cima da
    // introdução da música) dispensa o 3-2-1 do console
    this.semContagem = this.reduzido || this.jogo.contagem === false;
    this.contagem = this.semContagem ? 0.01 : 2.4;
    this.ultimaContagem = 4;
    this.depoisDaContagem = null;
    this.estado = "contagem";
    this.canvas.focus({ preventScroll: true });
  }

  /* A contagem pedida pelo jogo (api.contagem): a partida congela, a tela
     continua desenhada por baixo do número e, no "VAI!", o jogo segue. */
  contar(depois) {
    if (this.estado !== "jogando") return;
    this.semContagem = this.reduzido;
    this.contagem = this.reduzido ? 0.01 : 2.4;
    this.ultimaContagem = 4;
    this.depoisDaContagem = depois || null;
    this.estado = "contagem";
  }

  terminar({ pontos = 0, titulo = "Fim de jogo", detalhe = "" } = {}) {
    if (this.estado !== "jogando") return;
    this.estado = "fim";
    const recorde = Number(ler(PREFIXO_RECORDE + this.dados.slug) || 0);
    const novo = pontos > recorde;
    if (novo) gravar(PREFIXO_RECORDE + this.dados.slug, String(pontos));
    this.som.tocar(novo ? "vitoria" : "fim");
    this.fim.querySelector("[data-console-fim-titulo]").textContent = novo && pontos > 0 ? "Novo recorde!" : titulo;
    this.fim.querySelector("[data-console-fim-pontos]").textContent = pontos.toLocaleString("pt-BR");
    this.fim.querySelector("[data-console-fim-detalhe]").textContent = detalhe;
    this.fim.querySelector("[data-console-fim-recorde]").textContent =
      novo && pontos > 0 ? "Você bateu o seu recorde neste aparelho." : `Seu recorde: ${Math.max(recorde, pontos).toLocaleString("pt-BR")}`;
    this.fim.classList.toggle("console-fim--recorde", novo && pontos > 0);
    this.atualizarRecorde();
    this.raiz.dispatchEvent(new CustomEvent("console:fim", { detail: { slug: this.dados.slug, pontos } }));
    window.setTimeout(() => {
      if (this.estado !== "fim") return;
      this.fim.hidden = false;
      this.fim.querySelector("[data-console-acao='jogar']").focus({ preventScroll: true });
    }, 650);
  }

  atualizarRecorde() {
    const recorde = Number(ler(PREFIXO_RECORDE + (this.dados && this.dados.slug)) || 0);
    this.raiz.querySelector("[data-placar='recorde']").textContent = recorde.toLocaleString("pt-BR");
  }

  placar({ pontos, tempo, info } = {}) {
    if (pontos !== undefined) {
      this.raiz.querySelector("[data-placar='pontos']").textContent = Number(pontos || 0).toLocaleString("pt-BR");
    }
    if (tempo !== undefined) {
      const caixa = this.raiz.querySelector("[data-placar-caixa='tempo']");
      caixa.hidden = tempo === null;
      if (tempo !== null) {
        const s = Math.max(0, Math.ceil(tempo));
        caixa.querySelector("[data-placar='tempo']").textContent =
          s >= 60 ? `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}` : String(s);
        caixa.classList.toggle("console-placar-item--alerta", s <= 5 && s > 0);
      }
    }
    if (info !== undefined) {
      const caixa = this.raiz.querySelector("[data-placar-caixa='info']");
      caixa.hidden = !info;
      caixa.querySelector("[data-placar='info']").textContent = info || "";
    }
  }

  pausar() {
    this.pausado = true;
  }

  retomar() {
    this.pausado = false;
    this.ultimoQuadro = performance.now();
  }

  /* ---------- laço ---------- */
  rodar() {
    cancelAnimationFrame(this.quadroAnimacao);
    this.ultimoQuadro = performance.now();
    this.quadrosParados = 0;
    this.medicao = { soma: 0, n: 0 };
    const passo = (agora) => {
      if (this.estado === "fechado") return;
      this.quadroAnimacao = requestAnimationFrame(passo);
      const bruto = agora - this.ultimoQuadro;
      if (this.pausado) {
        this.ultimoQuadro = agora;
        return;
      }
      // Atrás da capa ou da tela de fim o jogo só enfeita o fundo: um
      // quadro em cada quatro basta, e a bateria do celular agradece.
      if (this.estado === "capa" || this.estado === "fim") {
        this.quadrosParados = (this.quadrosParados + 1) % 4;
        if (this.quadrosParados) return;
      }
      const dt = Math.min(0.05, bruto / 1000);
      this.ultimoQuadro = agora;
      this.passo(dt);
      if (this.estado === "jogando") this.medirDesempenho(bruto);
    };
    this.quadroAnimacao = requestAnimationFrame(passo);
  }

  /* A RESOLUÇÃO SE AJUSTA SOZINHA. Se o aparelho não dá conta de desenhar
     o jogo na densidade cheia da tela (média acima de ~45 ms por quadro,
     isto é, abaixo de ~22 quadros por segundo, ao longo de um segundo de
     partida), o canvas perde um degrau de pixels -- o jogo continua igual,
     só um pouco menos nítido -- até chegar na resolução lógica. */
  medirDesempenho(ms) {
    if (ms > 250) return; // a aba voltou de uma pausa: não conta
    const m = this.medicao;
    m.soma += ms;
    m.n += 1;
    if (m.n < 60) return;
    const media = m.soma / m.n;
    m.soma = 0;
    m.n = 0;
    if (media > 45 && (this.escala || 1) > 1) {
      this.escalaMaxima = Math.max(1, (this.escala || 1) - 0.35);
      this.ajustarTela();
    }
  }

  passo(dt) {
    const { ctx, partida, api } = this;
    if (!partida) return;

    if (this.estado === "contagem") {
      this.contagem -= dt;
      const numero = Math.ceil(this.contagem / 0.8);
      if (numero !== this.ultimaContagem && numero > 0 && !this.semContagem) {
        this.ultimaContagem = numero;
        this.som.tocar("contagem");
      }
      if (this.contagem <= 0) {
        this.estado = "jogando";
        if (!this.semContagem) {
          this.som.tocar("vai");
          api.efeitos.texto("VAI!", api.W / 2, api.H / 2, { cor: "#ffd700", tamanho: Math.min(api.W, api.H) * 0.2, vida: 0.8 });
        }
        const depois = this.depoisDaContagem;
        this.depoisDaContagem = null;
        if (depois) depois();
      }
    } else if (this.estado === "jogando") {
      this.relogio = (this.relogio || 0) + dt;
      partida.atualizar(dt);
    }
    api.efeitos.atualizar(dt);
    this.tremor = Math.max(0, this.tremor - dt * 40);

    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, api.W, api.H);
    if (this.tremor > 0) {
      ctx.translate((Math.random() - 0.5) * this.tremor, (Math.random() - 0.5) * this.tremor);
    }
    partida.desenhar(ctx);
    api.efeitos.desenhar(ctx);

    if (this.estado === "contagem" && this.contagem > 0) {
      const numero = Math.max(1, Math.ceil(this.contagem / 0.8));
      const fracao = (this.contagem % 0.8) / 0.8;
      ctx.save();
      ctx.fillStyle = "rgba(3, 8, 24, .45)";
      ctx.fillRect(0, 0, api.W, api.H);
      ctx.globalAlpha = Math.min(1, fracao * 2.2);
      api.texto(ctx, String(numero), api.W / 2, api.H / 2, {
        tamanho: Math.min(api.W, api.H) * (0.22 + (1 - fracao) * 0.06),
        cor: "#fff", contorno: getComputedStyle(this.raiz).getPropertyValue("--cor-jogo") || "#ffd700", peso: 900,
      });
      ctx.restore();
    }
  }

  ajustarTela() {
    if (!this.jogo) return;
    // A tela lógica é fixa; o que muda é o tamanho de cada ponto. Em tela
    // de alta densidade o canvas ganha mais pixels para não sair borrado.
    const r = this.canvas.getBoundingClientRect();
    if (!r.width) return;
    const densidade = Math.min(2, window.devicePixelRatio || 1);
    const escala = Math.min(this.escalaMaxima || 2, Math.max(1, (r.width * densidade) / this.jogo.largura));
    const largura = Math.round(this.jogo.largura * escala);
    const altura = Math.round(this.jogo.altura * escala);
    if (this.canvas.width !== largura) {
      this.canvas.width = largura;
      this.canvas.height = altura;
    }
    this.escala = escala;
    const ctx = this.ctx;
    const original = this.transformarNativo;
    // Todo `setTransform(1,0,0,1,0,0)` do console e dos jogos passa a
    // significar "coordenadas lógicas" -- o jogo nunca precisa saber da
    // densidade da tela.
    ctx.setTransform = (a, b, c, d, e, f) => original(a * escala, b * escala, c * escala, d * escala, e * escala, f * escala);
    ctx.resetTransform = () => original(escala, 0, 0, escala, 0, 0);
    ctx.imageSmoothingQuality = "high";
  }

  telaCheia() {
    const alvo = this.raiz.querySelector(".console-gabinete");
    if (document.fullscreenElement) document.exitFullscreen();
    else if (alvo.requestFullscreen) alvo.requestFullscreen().then(() => this.ajustarTela()).catch(() => {});
  }

  reiniciar() {
    if (!this.jogo || !this.liberar()) return;
    this.estado = "capa";
    this.comecar(true);
  }

  /** Para o jogo atual (troca de jogo): laço, partida e tela cheia. */
  pararPartida() {
    cancelAnimationFrame(this.quadroAnimacao);
    if (this.partida && this.partida.destruir) this.partida.destruir();
    this.partida = null;
    this.estado = "fechado";
    this.pausado = false;
  }
}

/* ----------------------------------------------------------------------
   LIGAÇÃO COM A PÁGINA DO SIMULADOR

   O seletor troca o jogo sem recarregar: o endereço vira /jogos/<jogo>/
   (voltar e avançar do navegador funcionam), e a ficha, os comandos e o
   título acompanham. O endereço de cada jogo é o link para mandar a
   alguém: a página já abre com ele em foco.
   ---------------------------------------------------------------------- */
const pagina = document.querySelector("[data-simulador]");
const raiz = pagina && pagina.querySelector("[data-console]");
const dadosDosJogos = document.getElementById("sim-jogos");

if (raiz && dadosDosJogos) {
  const consoleJogos = new Console(raiz);
  const jogos = JSON.parse(dadosDosJogos.textContent);
  const porSlug = Object.fromEntries(jogos.map((jogo) => [jogo.slug, jogo]));
  const whatsapp = pagina.dataset.whatsapp || "";
  const campo = (nome) => pagina.querySelector(`[data-sim-${nome}]`);
  const slugDoEndereco = () => {
    const achado = location.pathname.match(/\/jogos\/([\w-]+)\/?$/);
    return achado && porSlug[achado[1]] ? achado[1] : jogos[0].slug;
  };

  const criarBotao = (botao) => {
    const elemento = document.createElement("button");
    elemento.type = "button";
    elemento.className = "sim-botao" + (botao.grande ? " sim-botao--grande" : "");
    elemento.dataset.consoleTecla = botao.tecla;
    elemento.setAttribute("aria-label", botao.rotulo);
    const icone = document.createElement("i");
    icone.className = `fa-solid ${botao.icone}`;
    icone.setAttribute("aria-hidden", "true");
    elemento.append(icone);
    if (!botao.so_icone) {
      const texto = document.createElement("span");
      texto.textContent = botao.rotulo;
      elemento.append(" ", texto);
    }
    return elemento;
  };

  // A opção escolhida fica à vista no seletor, que rola sozinho (de lado
  // no celular, para baixo no computador) sem mexer na página.
  const mostrarOpcao = (opcao) => {
    const lista = opcao.closest("ul");
    if (!lista) return;
    if (lista.scrollWidth > lista.clientWidth) {
      lista.scrollTo({ left: opcao.offsetLeft - (lista.clientWidth - opcao.offsetWidth) / 2, behavior: "smooth" });
    } else if (lista.scrollHeight > lista.clientHeight) {
      lista.scrollTo({ top: opcao.offsetTop - (lista.clientHeight - opcao.offsetHeight) / 2, behavior: "smooth" });
    }
  };

  const mostrarFicha = (jogo) => {
    pagina.style.setProperty("--cor-jogo", jogo.cor);
    campo("h1").textContent = jogo.titulo;
    campo("trilha").textContent = jogo.titulo;
    campo("titulo").textContent = jogo.titulo;
    campo("maquina").textContent = jogo.maquina;
    campo("chamada").textContent = jogo.chamada;
    campo("descricao").textContent = jogo.descricao;
    campo("na-maquina").textContent = jogo.naMaquina;
    campo("passos").replaceChildren(...jogo.passos.map((passo) => {
      const item = document.createElement("li");
      item.textContent = passo;
      return item;
    }));
    campo("gesto").textContent = jogo.rotulo;
    campo("teclado").hidden = !jogo.teclado;
    campo("teclado-texto").textContent = jogo.teclado || "";
    campo("gesto-icone").className = `fa-solid ${jogo.icone}`;
    campo("botoes").replaceChildren(...jogo.botoes.map(criarBotao));
    campo("comandos").classList.toggle("sim-comandos--botoes", jogo.botoes.length > 0);

    const texto = `Olá! Joguei a prévia do ${jogo.titulo} no site da Lazer & Sport e quero saber da máquina.`;
    campo("whatsapp").href = `https://wa.me/${whatsapp}?text=${encodeURIComponent(texto)}`;
    const maquina = campo("maquina-link");
    maquina.hidden = !jogo.maquinaUrl;
    if (jogo.maquinaUrl) maquina.href = jogo.maquinaUrl;

    pagina.querySelectorAll("[data-sim-jogo]").forEach((opcao) => {
      if (opcao.dataset.simJogo === jogo.slug) {
        opcao.setAttribute("aria-current", "page");
        mostrarOpcao(opcao);
      } else {
        opcao.removeAttribute("aria-current");
      }
    });
    document.title = `${jogo.titulo}: jogue a prévia | Lazer & Sport Jogos`;
  };

  const escolher = (slug, { empurrar = true, focar = false } = {}) => {
    const jogo = porSlug[slug];
    if (!jogo) return;
    if (empurrar && location.pathname !== jogo.url) history.pushState({ slug }, "", jogo.url);
    mostrarFicha(jogo);
    consoleJogos.abrir({ ...jogo, whatsapp });
    // Escolheu no seletor: a máquina vem para a tela inteira, se não estiver.
    if (focar) {
      const caixa = raiz.getBoundingClientRect();
      if (caixa.top < 0 || caixa.bottom > window.innerHeight) raiz.scrollIntoView({ block: "start", behavior: "smooth" });
    }
  };

  // O dedo encostou ou o mouse passou por cima de um jogo do seletor: o
  // script e as artes dele já começam a vir, antes do clique.
  const preCarregar = (evento) => {
    const opcao = evento.target.closest && evento.target.closest("[data-sim-jogo]");
    const jogo = opcao && porSlug[opcao.dataset.simJogo];
    if (jogo) consoleJogos.carregar(jogo.script).catch(() => {});
  };
  pagina.addEventListener("pointerover", preCarregar);
  pagina.addEventListener("focusin", preCarregar);
  pagina.addEventListener("touchstart", preCarregar, { passive: true });

  pagina.addEventListener("click", (evento) => {
    const opcao = evento.target.closest("[data-sim-jogo]");
    if (!opcao || evento.button !== 0 || evento.metaKey || evento.ctrlKey || evento.shiftKey || evento.altKey) return;
    evento.preventDefault();
    escolher(opcao.dataset.simJogo, { focar: true });
  });

  window.addEventListener("popstate", () => escolher(slugDoEndereco(), { empurrar: false }));
  escolher(slugDoEndereco(), { empurrar: false });

  // Quem chegou pelo link de um jogo (/jogos/<jogo>/) já cai com a
  // máquina inteira na tela, logo abaixo do cabeçalho.
  const voltou = (() => {
    try { return performance.getEntriesByType("navigation")[0].type !== "navigate"; } catch (erro) { return false; }
  })();
  if (/\/jogos\/[\w-]+\/?$/.test(location.pathname) && window.scrollY < 40 && !location.hash && !voltou) {
    window.requestAnimationFrame(() => raiz.scrollIntoView({ block: "start" }));
  }
}
