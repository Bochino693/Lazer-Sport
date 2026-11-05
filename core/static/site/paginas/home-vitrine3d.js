/* ======================================================================
   O 3D NA VITRINE DO QUADRO INICIAL

   O brinquedo da vitrine que tem objeto 3D (`data-modelo3d`, o .glb)
   troca a foto pelo objeto girando: 1,5 s depois de entrar na vez, o 3D
   aparece por cima da foto (um desvanecer) e balança devagar mostrando a
   frente e os lados; com o mouse, dá para arrastar e girar. Quando a vez
   passa, volta a foto. Assim o 3D aparece "de vez em quando" sem ocupar
   uma seção só para ele.

   O QUE NÃO PODE PESAR, E COMO NÃO PESA
   - UM visor só para a vitrine inteira: um <canvas> e um WebGLRenderer,
     criados na primeira vez em que um 3D vai aparecer e reaproveitados
     depois -- o canvas muda de slide, e na cena só se troca o objeto. Os
     .glb lidos ficam guardados (um por endereço): a segunda volta da
     vitrine não baixa nem lê nada de novo.
   - Nada do 3D é baixado antes da hora: o three.js, o leitor e o .glb só
     são pedidos com a página já carregada, com a vitrine na tela e quando
     um brinquedo com 3D está na vez ou é o próximo da fila.
   - Só desenha com o 3D à mostra, a vitrine na tela (IntersectionObserver)
     e a aba aberta; no máximo 30 quadros por segundo. Fora disso não há
     nenhum requestAnimationFrame rodando.
   - Fica a foto (e nada é baixado) com "menos movimento" ligado, com
     economia de dados ou rede 2G, com menos de 4 GB de memória
     (`navigator.deviceMemory`), sem WebGL ou com WebGL por software (o
     `failIfMajorPerformanceCaveat`: o desenho cairia no processador) e em
     tela de celular (menos de 768 px). No celular o cartão tem uns 360 px:
     o 3D acrescenta pouco à foto e custaria ~1 MB de download (o three.js
     e o .glb), quase sempre no plano de dados, mais a bateria de desenhar
     no meio da rolagem -- a página do brinquedo continua com o "Ver em 3D".
   - Se algo falha (rede, .glb quebrado, o WebGL perdido), a vitrine segue
     com as fotos, sem erro na tela.
   ====================================================================== */

const vitrine = document.querySelector("[data-vitrine][data-three]");
const palco = vitrine && vitrine.querySelector("[data-vitrine-palco]");
const slides = palco ? Array.from(palco.querySelectorAll("[data-slide]")) : [];

const ESPERA_MS = 1500; // a foto aparece primeiro; o 3D entra depois disto
const BALANCO = 0.85; // até ~50° para cada lado da frente
const RITMO = 0.4; // a velocidade do balanço
const QUADRO = 1 / 30; // 30 quadros por segundo bastam para girar liso
// Sem placa de vídeo para o 3D não é defeito, é o aparelho: fica a foto, calado.
const SEM_PLACA = new Error("sem WebGL 2 na placa de vídeo");

if (slides.some((s) => s.dataset.modelo3d) && aparelhoAguenta()) ligar();

function aparelhoAguenta() {
  const consulta = (q) => window.matchMedia && window.matchMedia(q).matches;
  if (consulta("(prefers-reduced-motion: reduce)")) return false;
  if (consulta("(max-width: 767px)")) return false;
  const rede = navigator.connection;
  if (rede && (rede.saveData || /2g$/.test(rede.effectiveType || ""))) return false;
  if (navigator.deviceMemory && navigator.deviceMemory < 4) return false;
  return "WebGL2RenderingContext" in window && "IntersectionObserver" in window;
}

function ligar() {
  // A folha só mostra o selo "3D" e alonga a vez do brinquedo com esta
  // classe: onde o 3D não vai aparecer, nada promete que vai.
  vitrine.classList.add("ls-vitrine--com-3d");

  let ativo = slides.find((s) => s.classList.contains("ativo")) || slides[0];
  let mostrando = null; // o slide com o 3D à mostra
  let espera = 0;
  let naTela = false;
  let paginaPronta = document.readyState === "complete";
  let desistiu = false;
  let motor = null; // Promise do visor (three.js, leitor, renderer, cena)
  let visor = null; // o visor pronto
  const modelos = new Map(); // endereço do .glb -> Promise do objeto lido

  function desistir(erro) {
    if (desistiu) return;
    desistiu = true;
    if (erro && erro !== SEM_PLACA) console.warn("Vitrine 3D: segue com as fotos.", erro);
    window.clearTimeout(espera);
    if (visor) visor.parar();
    slides.forEach((s) => s.classList.remove("ls-vitrine-slide--3d"));
    vitrine.classList.remove("ls-vitrine--com-3d");
  }

  // O contexto WebGL do visor. Pedido com `failIfMajorPerformanceCaveat`:
  // sem WebGL 2, ou só com o desenho por software, vem null -- e fica a foto.
  function pedirContexto(tela) {
    return tela.getContext("webgl2", {
      alpha: true,
      antialias: true,
      depth: true,
      stencil: false,
      premultipliedAlpha: true,
      powerPreference: "low-power",
      failIfMajorPerformanceCaveat: true,
    });
  }

  // Logo depois de a página carregar, com o navegador folgado: este
  // aparelho desenha 3D na placa de vídeo? Se não, o selo "3D" e a vez
  // mais longa saem já -- e não quando o primeiro 3D fosse aparecer. O
  // contexto de teste é devolvido na hora: o do visor só nasce quando ele
  // for preciso.
  function sondarPlaca() {
    if (desistiu || motor) return;
    const gl = pedirContexto(document.createElement("canvas"));
    if (!gl) {
      desistir(SEM_PLACA);
      return;
    }
    const perder = gl.getExtension("WEBGL_lose_context");
    if (perder) perder.loseContext();
  }

  function carregarMotor() {
    if (!motor) {
      motor = Promise.resolve()
        .then(() => {
          // antes de baixar 700 KB de three.js, a placa de vídeo responde
          const tela = document.createElement("canvas");
          const gl = pedirContexto(tela);
          if (!gl) throw SEM_PLACA;
          return Promise.all([import(vitrine.dataset.three), import(vitrine.dataset.gltf)])
            .then(([T, leitor]) => montarVisor(T, leitor, tela, gl));
        })
        .then((pronto) => {
          visor = pronto;
          return pronto;
        });
      motor.catch(desistir);
    }
    return motor;
  }

  function carregarModelo(url) {
    if (!modelos.has(url)) {
      const pedido = carregarMotor().then((v) => v.ler(url));
      // um .glb que não abre não derruba os outros: só este fica com a foto
      pedido.catch((erro) => {
        if (!desistiu) console.warn("Vitrine 3D: o objeto não carregou.", url, erro);
      });
      modelos.set(url, pedido);
    }
    return modelos.get(url);
  }

  async function aparecer(slide) {
    const modelo = await carregarModelo(slide.dataset.modelo3d);
    if (desistiu || slide !== ativo) return;
    visor.mostrar(modelo, slide.querySelector(".ls-vitrine-foto"));
    mostrando = slide;
    // o primeiro quadro já está desenhado: o desvanecer não mostra vazio
    slide.classList.add("ls-vitrine-slide--3d");
    atualizar();
  }

  function agendar() {
    window.clearTimeout(espera);
    if (desistiu || !paginaPronta || !naTela) return;
    // o próximo da fila já vem descendo, para entrar sem espera na vez dele
    const proximo = slides[(slides.indexOf(ativo) + 1) % slides.length];
    if (proximo !== ativo && proximo.dataset.modelo3d) carregarModelo(proximo.dataset.modelo3d).catch(() => {});
    if (!ativo.dataset.modelo3d || mostrando === ativo) return;
    const slide = ativo;
    carregarModelo(slide.dataset.modelo3d).catch(() => {});
    espera = window.setTimeout(() => {
      aparecer(slide).catch(() => { /* este fica com a foto */ });
    }, ESPERA_MS);
  }

  function atualizar() {
    if (visor) visor.rodar(Boolean(mostrando) && naTela && !document.hidden);
  }

  vitrine.addEventListener("vitrine:troca", (evento) => {
    const novo = evento.detail && evento.detail.slide;
    if (!novo || novo === ativo) return;
    window.clearTimeout(espera);
    if (mostrando) {
      // a foto volta enquanto o slide sai; o visor para no último quadro
      mostrando.classList.remove("ls-vitrine-slide--3d");
      mostrando = null;
      atualizar();
    }
    ativo = novo;
    agendar();
  });

  new IntersectionObserver((entradas) => {
    naTela = entradas.some((e) => e.isIntersecting);
    atualizar();
    if (naTela) agendar();
    else window.clearTimeout(espera);
  }, { threshold: 0.2 }).observe(palco);

  document.addEventListener("visibilitychange", atualizar);

  const quandoFolgado = (fazer) => ("requestIdleCallback" in window
    ? window.requestIdleCallback(fazer, { timeout: 1500 })
    : window.setTimeout(fazer, 300));

  if (paginaPronta) {
    quandoFolgado(sondarPlaca);
  } else {
    // a foto do primeiro brinquedo é o que a página mostra primeiro: nada
    // do 3D disputa a rede com ela
    window.addEventListener("load", () => {
      paginaPronta = true;
      quandoFolgado(sondarPlaca);
      agendar();
    }, { once: true });
  }

  /* ---------------------------------------------------------------
     O VISOR: um renderer, uma cena, uma câmera; o objeto é que muda
     --------------------------------------------------------------- */
  function montarVisor(T, leitor, tela, gl) {
    tela.className = "ls-vitrine-3d";
    tela.setAttribute("aria-hidden", "true");

    const renderer = new T.WebGLRenderer({ canvas: tela, context: gl, antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    renderer.toneMapping = T.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    renderer.outputColorSpace = T.SRGBColorSpace;
    renderer.setClearColor(0x000000, 0);

    // a mesma luz da Arena e da página do brinquedo (vitrine3d.js, visor3d.js)
    const cena = new T.Scene();
    cena.add(new T.HemisphereLight("#ffffff", "#9aa8bd", 1.6));
    const sol = new T.DirectionalLight("#ffffff", 2.2);
    sol.position.set(4, 9, 7);
    cena.add(sol);
    const contra = new T.DirectionalLight("#cfe0ff", 0.9);
    contra.position.set(-6, 4, -8);
    cena.add(contra);

    const camera = new T.PerspectiveCamera(30, 1, 0.01, 100);
    const carregador = new leitor.GLTFLoader();

    let atual = null; // o objeto em cena, com o enquadramento dele
    const vista = { giro: 0, inclinacao: 0 };
    const meta = { giro: 0, inclinacao: 0 };
    let sozinho = true;
    let parado = 0;
    let centro = 0;
    let tempo = 0;
    let rodando = false;
    let anterior = 0;
    let acumulado = 0;
    let largura = 0;
    let altura = 0;

    function enquadrar() {
      if (!atual || !largura || !altura) return;
      camera.aspect = largura / altura;
      // a esfera em volta do objeto inteiro cabe na tela, no lado mais
      // apertado: girando, nada sai do cartão
      const vertical = (camera.fov * Math.PI) / 180;
      const horizontal = 2 * Math.atan(Math.tan(vertical / 2) * camera.aspect);
      atual.distancia = atual.raio / Math.sin(Math.min(vertical, horizontal) / 2);
      camera.near = atual.raio / 100;
      camera.far = atual.raio * 30;
      camera.updateProjectionMatrix();
    }

    function medir() {
      const caixa = tela.getBoundingClientRect();
      if (!caixa.width || !caixa.height) return;
      largura = caixa.width;
      altura = caixa.height;
      renderer.setSize(largura, altura, false);
      enquadrar();
      desenhar();
    }

    function desenhar() {
      if (!atual || !atual.distancia) return;
      const { alvo, distancia } = atual;
      camera.position.set(
        alvo.x + Math.sin(vista.giro) * Math.cos(vista.inclinacao) * distancia,
        alvo.y + Math.sin(vista.inclinacao) * distancia,
        alvo.z + Math.cos(vista.giro) * Math.cos(vista.inclinacao) * distancia,
      );
      camera.lookAt(alvo);
      renderer.render(cena, camera);
    }

    function passo(agora) {
      if (!rodando) return;
      window.requestAnimationFrame(passo);
      acumulado += Math.min(0.1, (agora - (anterior || agora)) / 1000);
      anterior = agora;
      if (acumulado < QUADRO) return;
      const dt = acumulado;
      acumulado = 0;
      if (!sozinho && (parado += dt) > 3) {
        // volta a balançar em volta da frente mais perto de onde a pessoa deixou
        sozinho = true;
        centro = Math.round(meta.giro / (Math.PI * 2)) * Math.PI * 2;
        tempo = Math.asin(Math.max(-1, Math.min(1, (meta.giro - centro) / BALANCO))) / RITMO;
      }
      // sozinho, balança mostrando a frente (de costas, a máquina não diz
      // nada); arrastando, gira inteiro
      if (sozinho) {
        tempo += dt;
        meta.giro = centro + Math.sin(tempo * RITMO) * BALANCO;
        meta.inclinacao = atual ? atual.inicio.inclinacao : 0.2;
      }
      const k = 1 - Math.exp(-dt * 8);
      vista.giro += (meta.giro - vista.giro) * k;
      vista.inclinacao += (meta.inclinacao - vista.inclinacao) * k;
      desenhar();
    }

    // arrastar com o mouse gira; no dedo, o deslizar continua trocando de
    // brinquedo (e o de cima para baixo, rolando a página)
    let arraste = null;
    let arrastou = false;
    tela.addEventListener("pointerdown", (e) => {
      if (e.pointerType !== "mouse" || e.button !== 0) return;
      // o palco trocaria de brinquedo com o arraste (home-quadro.js)
      e.stopPropagation();
      e.preventDefault();
      arraste = { x: e.clientX, y: e.clientY };
      arrastou = false;
      tela.setPointerCapture(e.pointerId);
      sozinho = false;
      parado = 0;
    });
    tela.addEventListener("pointermove", (e) => {
      if (!arraste) return;
      const dx = e.clientX - arraste.x;
      const dy = e.clientY - arraste.y;
      if (Math.abs(dx) + Math.abs(dy) > 3) arrastou = true;
      const base = tela.clientWidth || 1;
      meta.giro -= (dx / base) * Math.PI * 1.6;
      meta.inclinacao = Math.min(1.1, Math.max(-0.05, meta.inclinacao + (dy / base) * Math.PI));
      arraste = { x: e.clientX, y: e.clientY };
      parado = 0;
    });
    const soltar = (e) => {
      if (!arraste) return;
      e.stopPropagation();
      arraste = null;
    };
    tela.addEventListener("pointerup", soltar);
    tela.addEventListener("pointercancel", soltar);
    // o canvas mora dentro do link da foto: girar não é clicar
    tela.addEventListener("click", (e) => {
      if (!arrastou) return;
      e.preventDefault();
      e.stopPropagation();
      arrastou = false;
    });

    tela.addEventListener("webglcontextlost", (e) => {
      e.preventDefault();
      desistir(new Error("o WebGL foi perdido"));
    });

    new ResizeObserver(medir).observe(tela);

    return {
      /** Lê o .glb e prepara o enquadramento (sem pôr na cena). */
      ler(url) {
        return carregador.loadAsync(url).then((gltf) => {
          const objeto = gltf.scene;
          const caixa = new T.Box3().setFromObject(objeto);
          const tamanho = caixa.getSize(new T.Vector3());
          // a máquina em pé no chão, com o centro no meio
          objeto.position.x -= (caixa.min.x + caixa.max.x) / 2;
          objeto.position.z -= (caixa.min.z + caixa.max.z) / 2;
          objeto.position.y -= caixa.min.y;
          // o espaço grande fica melhor visto de cima; a máquina, de frente
          const deitado = tamanho.x > tamanho.y * 3 || tamanho.z > tamanho.y * 3;
          return {
            objeto,
            raio: tamanho.length() / 2,
            alvo: new T.Vector3(0, tamanho.y * 0.48, 0),
            inicio: { giro: 0.6, inclinacao: deitado ? 0.62 : 0.2 },
            distancia: 0,
          };
        });
      },

      /** Põe o objeto em cena e o visor dentro da foto deste slide. */
      mostrar(modelo, foto) {
        if (atual !== modelo) {
          if (atual) cena.remove(atual.objeto);
          cena.add(modelo.objeto);
          atual = modelo;
        }
        // cada vez que entra, começa do mesmo jeito: de três quartos
        vista.giro = meta.giro = modelo.inicio.giro;
        vista.inclinacao = meta.inclinacao = modelo.inicio.inclinacao;
        centro = 0;
        tempo = Math.asin(modelo.inicio.giro / BALANCO) / RITMO;
        sozinho = true;
        if (tela.parentElement !== foto) {
          foto.append(tela);
          // arrastar o 3D não pode virar "arrastar o link" do navegador
          foto.setAttribute("draggable", "false");
        }
        medir();
      },

      rodar(sim) {
        if (sim && !rodando) {
          rodando = true;
          anterior = 0;
          acumulado = 0;
          window.requestAnimationFrame(passo);
        } else if (!sim) {
          rodando = false;
        }
      },

      parar() {
        rodando = false;
        tela.remove();
      },
    };
  }
}
