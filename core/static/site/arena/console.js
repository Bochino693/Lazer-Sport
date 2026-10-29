/* ======================================================================
   O CONSOLE DOS JOGOS — o gabinete de fliperama que abre por cima da página.

   Cada jogo é um módulo (site/arena/jogos/<nome>.js) que só sabe jogar:
   desenhar, andar no tempo e responder ao toque. Tudo o que é igual em
   todos -- abrir e fechar, placar, recorde, som, contagem 3-2-1, tela
   cheia, pausa quando a aba some -- mora aqui, uma vez só.

   CONTRATO DE UM JOGO (export default):

     {
       largura: 540, altura: 960,          // tela lógica, em pontos
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
  constructor(dialogo) {
    this.dialogo = dialogo;
    this.canvas = dialogo.querySelector("[data-console-tela]");
    this.ctx = this.canvas.getContext("2d");
    this.transformarNativo = CanvasRenderingContext2D.prototype.setTransform.bind(this.ctx);
    this.quadro = dialogo.querySelector("[data-console-quadro]");
    this.capa = dialogo.querySelector("[data-console-capa]");
    this.fim = dialogo.querySelector("[data-console-fim]");
    this.carregando = dialogo.querySelector("[data-console-carregando]");
    this.botaoSom = dialogo.querySelector("[data-console-som]");
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
    this.dialogo.addEventListener("click", (evento) => {
      const alvo = evento.target.closest("[data-console-acao]");
      if (!alvo) return;
      const acao = alvo.dataset.consoleAcao;
      if (acao === "fechar") this.fechar();
      else if (acao === "jogar") this.comecar();
      else if (acao === "som") this.mostrarSom(this.som.alternar());
      else if (acao === "tela-cheia") this.telaCheia();
    });

    this.dialogo.addEventListener("close", () => this.encerrar());
    this.dialogo.addEventListener("cancel", () => this.encerrar());

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
      const codigo = evento.code || evento.key;
      if (this.estado !== "jogando") {
        if (apertada && (codigo === "Enter" || codigo === "Space") && evento.target === document.body) {
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

    document.addEventListener("visibilitychange", () => {
      if (document.hidden && this.estado !== "fechado") this.pausar();
      else if (!document.hidden && this.estado !== "fechado") this.retomar();
    });

    window.addEventListener("resize", () => this.ajustarTela());
  }

  mostrarSom(ligado = this.som.ligado) {
    if (!this.botaoSom) return;
    this.botaoSom.setAttribute("aria-pressed", ligado ? "true" : "false");
    this.botaoSom.querySelector("i").className = ligado ? "fa-solid fa-volume-high" : "fa-solid fa-volume-xmark";
    this.botaoSom.setAttribute("aria-label", ligado ? "Desligar o som" : "Ligar o som");
  }

  /* ---------- abrir um jogo ---------- */
  async abrir(dados) {
    this.dados = dados;
    this.dialogo.style.setProperty("--cor-jogo", dados.cor || "#ffd700");
    this.dialogo.querySelector("[data-console-titulo]").textContent = dados.titulo;
    this.dialogo.querySelector("[data-console-maquina]").textContent = dados.maquina || "";
    const logo = this.dialogo.querySelector("[data-console-logo]");
    logo.src = dados.capa;
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

    if (!this.dialogo.open) {
      if (typeof this.dialogo.showModal === "function") this.dialogo.showModal();
      else this.dialogo.setAttribute("open", "");
    }
    document.documentElement.classList.add("ls-console-aberto");
    history.replaceState(null, "", "#jogar-" + dados.slug);

    this.carregando.hidden = false;
    try {
      this.jogo = await this.carregar(dados.script);
      this.criarPartida();
      this.carregando.hidden = true;
      this.ajustarTela();
      this.rodar();
      this.capa.querySelector("[data-console-acao='jogar']").focus();
    } catch (erro) {
      console.error("Console: jogo não carregou", erro);
      this.carregando.textContent = "Não foi possível carregar este jogo agora. Tente de novo em instantes.";
    }
  }

  async carregar(url) {
    if (!this.modulos.has(url)) {
      this.modulos.set(url, import(url).then(async (modulo) => {
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
      }));
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
  comecar() {
    if (!this.jogo || this.estado === "jogando" || this.estado === "contagem") return;
    this.som.acordar();
    this.som.tocar("moeda");
    this.capa.hidden = true;
    this.fim.hidden = true;
    this.api.efeitos.limpar();
    if (this.partida.iniciar) this.partida.iniciar();
    this.relogio = 0;
    this.contagem = this.reduzido ? 0.01 : 2.4;
    this.ultimaContagem = 4;
    this.estado = "contagem";
    this.canvas.focus({ preventScroll: true });
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
    window.setTimeout(() => {
      if (this.estado !== "fim") return;
      this.fim.hidden = false;
      this.fim.querySelector("[data-console-acao='jogar']").focus();
    }, 650);
  }

  atualizarRecorde() {
    const recorde = Number(ler(PREFIXO_RECORDE + (this.dados && this.dados.slug)) || 0);
    this.dialogo.querySelector("[data-placar='recorde']").textContent = recorde.toLocaleString("pt-BR");
  }

  placar({ pontos, tempo, info } = {}) {
    if (pontos !== undefined) {
      this.dialogo.querySelector("[data-placar='pontos']").textContent = Number(pontos || 0).toLocaleString("pt-BR");
    }
    if (tempo !== undefined) {
      const caixa = this.dialogo.querySelector("[data-placar-caixa='tempo']");
      caixa.hidden = tempo === null;
      if (tempo !== null) {
        const s = Math.max(0, Math.ceil(tempo));
        caixa.querySelector("[data-placar='tempo']").textContent =
          s >= 60 ? `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}` : String(s);
        caixa.classList.toggle("console-placar-item--alerta", s <= 5 && s > 0);
      }
    }
    if (info !== undefined) {
      const caixa = this.dialogo.querySelector("[data-placar-caixa='info']");
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
    const passo = (agora) => {
      if (this.estado === "fechado") return;
      this.quadroAnimacao = requestAnimationFrame(passo);
      const dt = Math.min(0.05, (agora - this.ultimoQuadro) / 1000);
      this.ultimoQuadro = agora;
      if (this.pausado) return;
      this.passo(dt);
    };
    this.quadroAnimacao = requestAnimationFrame(passo);
  }

  passo(dt) {
    const { ctx, partida, api } = this;
    if (!partida) return;

    if (this.estado === "contagem") {
      this.contagem -= dt;
      const numero = Math.ceil(this.contagem / 0.8);
      if (numero !== this.ultimaContagem && numero > 0) {
        this.ultimaContagem = numero;
        this.som.tocar("contagem");
      }
      if (this.contagem <= 0) {
        this.estado = "jogando";
        this.som.tocar("vai");
        if (!this.reduzido) api.efeitos.texto("VAI!", api.W / 2, api.H / 2, { cor: "#ffd700", tamanho: Math.min(api.W, api.H) * 0.2, vida: 0.8 });
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
        cor: "#fff", contorno: getComputedStyle(this.dialogo).getPropertyValue("--cor-jogo") || "#ffd700", peso: 900,
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
    const escala = Math.min(2, Math.max(1, (r.width * densidade) / this.jogo.largura));
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
    const alvo = this.dialogo.querySelector(".console-gabinete");
    if (document.fullscreenElement) document.exitFullscreen();
    else if (alvo.requestFullscreen) alvo.requestFullscreen().then(() => this.ajustarTela()).catch(() => {});
  }

  fechar() {
    if (this.dialogo.open && typeof this.dialogo.close === "function") this.dialogo.close();
    else this.encerrar();
  }

  encerrar() {
    if (this.estado === "fechado") return;
    this.estado = "fechado";
    cancelAnimationFrame(this.quadroAnimacao);
    if (this.partida && this.partida.destruir) this.partida.destruir();
    this.partida = null;
    this.dialogo.removeAttribute("open");
    document.documentElement.classList.remove("ls-console-aberto");
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    if (location.hash.startsWith("#jogar-") || /[?&]jogar=/.test(location.search)) {
      history.replaceState(null, "", location.pathname + "#jogos");
    }
    if (this.origem && document.contains(this.origem)) this.origem.focus({ preventScroll: true });
  }
}

/* ----------------------------------------------------------------------
   LIGAÇÃO COM A PÁGINA

   Qualquer botão com `data-jogo-abrir="<slug>"` abre o jogo, e o
   endereço `#jogar-<slug>` abre direto -- é o link para mandar a alguém.
   ---------------------------------------------------------------------- */
const dialogo = document.getElementById("arena-console");

if (dialogo) {
  const consoleJogos = new Console(dialogo);
  const catalogo = {};
  document.querySelectorAll("[data-jogo]").forEach((cartao) => {
    const d = cartao.dataset;
    catalogo[d.jogo] = {
      slug: d.jogo,
      titulo: d.jogoTitulo,
      maquina: d.jogoMaquina,
      chamada: d.jogoChamada,
      comandos: d.jogoComandos,
      capa: d.jogoCapa,
      poster: d.jogoPoster,
      cor: d.jogoCor,
      script: d.jogoScript,
      variante: d.jogoVariante,
      maquinaUrl: d.jogoMaquinaUrl,
      maquinaNome: d.jogoMaquinaNome,
      whatsapp: d.jogoWhatsapp,
    };
  });

  document.addEventListener("click", (evento) => {
    const botao = evento.target.closest("[data-jogo-abrir]");
    if (!botao) return;
    const dados = catalogo[botao.dataset.jogoAbrir];
    if (!dados) return;
    evento.preventDefault();
    consoleJogos.origem = botao;
    consoleJogos.abrir(dados);
  });

  // A arena 3D pede um jogo pelo nome quando a ficha de uma máquina tem
  // a miniatura dela.
  window.addEventListener("ls-arena:jogar", (evento) => {
    const dados = catalogo[evento.detail && evento.detail.slug];
    if (dados) consoleJogos.abrir(dados);
  });

  // `#jogar-<jogo>` (link para mandar a alguém) ou `?jogar=<jogo>` (os
  // cartões da home, que precisam do # para descer até a seção de jogos).
  const pedido = location.hash.match(/^#jogar-([\w-]+)/) || location.search.match(/[?&]jogar=([\w-]+)/);
  if (pedido && catalogo[pedido[1]]) consoleJogos.abrir(catalogo[pedido[1]]);
}
