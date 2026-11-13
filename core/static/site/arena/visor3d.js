/* ======================================================================
   O VISOR 3D DA PÁGINA DO BRINQUEDO: o objeto 3D (.glb) do cadastro, para
   girar com o dedo ou o mouse, aproximar e trocar de cor -- além das fotos.

   Nada pesa antes da hora: o three.js, o leitor do .glb e as cores
   (cores3d.js) só chegam quando a pessoa toca em "Ver em 3D". E só se
   desenha quando algo muda (girando sozinho, arrastando, trocando de cor)
   e com o visor na tela.

   `iniciar` também serve a outras páginas (a proposta do orçamento abre o
   3D de cada item numa janela: site/paginas/orcamento-3d.js): devolve
   `acordar`, `soltar` (solta o WebGL e a memória ao fechar) e `trocar`.

   OS ADESIVOS (LEIA-ME 72): o produto com um 3D para cada adesivo traz a
   lista (`data-adesivos3d`: o id do JSON na página, ou o próprio JSON) e o
   controle "Adesivo: A · B" (site/arena/adesivos3d.js, `data-adesivos3d-
   modulo`) aparece sobre o 3D. Ele troca o .glb no mesmo lugar, com a
   câmera onde estava; o outro modelo só baixa quando é pedido. Os adesivos
   são a MESMA máquina: o enquadramento é o do primeiro 3D e fica (a troca
   nunca "encolhe" nem "cresce" a máquina na tela).

   A CARA DE FOTO DE CATÁLOGO (LEIA-ME V10, seção 91; site/arena/realismo3d.js):
   a luz de ambiente de estúdio (RoomEnvironment + PMREM), o tom neutro (a cor
   da arte como foi impressa), as texturas nítidas (anisotrópico), a sombra de
   contato no pé da máquina e a densidade de pixels que se ajusta (até 2; cai
   sozinha se os quadros ficam lentos). No aparelho fraco, as texturas descem
   para 1024 px.
   ====================================================================== */

const raiz = document.querySelector("[data-visor3d]");
if (raiz) ligar(raiz);

function ligar(visor) {
  const caixa = visor.closest(".produto-imagem-box") || visor.parentElement;
  const pagina = visor.closest(".produto-visual");
  const abrir = document.querySelectorAll("[data-visor3d-abrir]");
  const fechar = visor.querySelector("[data-visor3d-fechar]");
  const aviso = visor.querySelector("[data-visor3d-aviso]");
  const tela = visor.querySelector("[data-visor3d-tela]");
  const coresCaixa = document.querySelector("[data-visor3d-cores]");
  let motor = null;

  function mostrar(aberto) {
    visor.hidden = !aberto;
    caixa.classList.toggle("produto-imagem-box--3d", aberto);
    if (pagina) pagina.classList.toggle("produto-visual--3d", aberto);
    abrir.forEach((botao) => botao.setAttribute("aria-pressed", aberto ? "true" : "false"));
    if (coresCaixa) coresCaixa.hidden = !aberto || !coresCaixa.childElementCount;
    if (aberto) {
      if (!motor) {
        motor = iniciar(visor, tela, aviso, coresCaixa).catch((erro) => {
          console.error("Visor 3D: não abriu", erro);
          aviso.hidden = false;
          aviso.textContent = "Não deu para abrir o 3D neste aparelho. As fotos continuam aqui.";
          return null;
        });
      }
      motor.then((m) => m && m.acordar());
    }
  }

  abrir.forEach((botao) => botao.addEventListener("click", () => mostrar(visor.hidden)));
  fechar.addEventListener("click", () => mostrar(false));
  // escolher uma foto (miniatura ou setas) volta para as fotos
  document.querySelectorAll("[data-galeria-indice], [data-galeria-anterior], [data-galeria-proxima]").forEach((botao) => {
    botao.addEventListener("click", () => { if (!visor.hidden) mostrar(false); });
  });
  if (location.hash === "#ver-3d") mostrar(true);
}

export async function iniciar(visor, tela, aviso, coresCaixa) {
  // o controle dos adesivos de outro item (a janela da proposta reaproveita o visor)
  visor.querySelectorAll("[data-adesivos3d-controle]").forEach((velho) => velho.remove());
  aviso.hidden = false;
  aviso.textContent = "Carregando o 3D…";
  const realismoUrl = visor.dataset.realismo3d || new URL("realismo3d.js", import.meta.url).href;
  const [T, leitor, cores3d, R] = await Promise.all([
    import(visor.dataset.three),
    import(visor.dataset.gltf),
    import(visor.dataset.cores3d),
    import(realismoUrl),
  ]);

  const renderer = new T.WebGLRenderer({ canvas: tela, antialias: true, alpha: true, powerPreference: "high-performance" });
  const densidade = R.densidadeAdaptavel(renderer, 2);
  R.configurarRenderer(T, renderer, 1.0);
  renderer.setClearColor(0x000000, 0);
  const fraco = R.aparelhoFraco(renderer);

  const cena = new T.Scene();
  // a luz: a sala de estúdio (reflexos no verniz e no cromo) e um sol de frente, alto, para o brilho
  const luzAmbiente = R.ambiente(T, renderer, visor.dataset.three);
  const sol = new T.DirectionalLight("#fff6ea", 1.35);
  sol.position.set(3, 8, 6);
  cena.add(sol);
  const contra = new T.DirectionalLight("#9cc4ff", 0.6);
  contra.position.set(-6, 4, -8);
  cena.add(contra);

  const camera = new T.PerspectiveCamera(32, 1, 0.01, 100);
  const carregador = new leitor.GLTFLoader();
  let [gltf] = await Promise.all([carregador.loadAsync(visor.dataset.modelo), luzAmbiente.then((t) => {
    if (t) { cena.environment = t; cena.environmentIntensity = 1.0; }
  })]);
  let objeto = null;
  let raio = 1;
  const alvo = new T.Vector3();
  let sombra = null;
  let enquadrado = false;

  // a máquina em pé no chão, com o centro no meio da tela (a câmera mira o meio dela).
  // O enquadramento (o raio e o alvo) é o do PRIMEIRO 3D: o outro adesivo é a mesma
  // máquina e aparece do mesmo tamanho na tela.
  function vestir(novo) {
    objeto = novo.scene;
    R.prepararObjeto(T, objeto, renderer, { limite: fraco ? 1024 : 0 });
    const caixa = new T.Box3().setFromObject(objeto);
    const tamanho = caixa.getSize(new T.Vector3());
    objeto.position.x -= (caixa.min.x + caixa.max.x) / 2;
    objeto.position.z -= (caixa.min.z + caixa.max.z) / 2;
    objeto.position.y -= caixa.min.y;
    cena.add(objeto);
    if (!enquadrado) {
      enquadrado = true;
      raio = tamanho.length() / 2;
      alvo.set(0, tamanho.y / 2, 0);
      camera.near = raio / 100;
      camera.far = raio * 30;
      camera.updateProjectionMatrix();
    }
    if (sombra) {
      cena.remove(sombra);
      sombra.material.map.dispose();
      sombra.material.dispose();
      sombra.geometry.dispose();
    }
    sombra = R.sombraDeContato(T, tamanho.x, tamanho.z);
    cena.add(sombra);
    return tamanho;
  }
  vestir(gltf);

  // a câmera em volta: giro (de frente = 0), inclinação e distância
  const vista = { giro: 0.55, inclinacao: 0.22, perto: 1 };
  const meta = { ...vista };
  // a esfera em volta da caixa sobra nos cantos: um pouco mais perto que ela
  // a esfera em volta da caixa cabe na tela pelo lado mais apertado (no celular
  // em pé, a largura): uma máquina comprida não sai cortada dos lados
  function distanciaBase() {
    const meiaV = ((camera.fov / 2) * Math.PI) / 180;
    const meiaH = Math.atan(Math.tan(meiaV) * camera.aspect);
    return (raio / Math.sin(Math.min(meiaV, meiaH))) * 0.88;
  }
  let sozinho = true; // gira devagar até a pessoa mexer
  let parado = 0;
  let sujo = true;
  let rodando = false;
  let visivel = true;
  let anterior = 0;
  let solto = false;

  function posicionar() {
    const d = distanciaBase() * vista.perto;
    camera.position.set(
      alvo.x + Math.sin(vista.giro) * Math.cos(vista.inclinacao) * d,
      alvo.y + Math.sin(vista.inclinacao) * d,
      alvo.z + Math.cos(vista.giro) * Math.cos(vista.inclinacao) * d,
    );
    camera.lookAt(alvo);
  }

  function medir() {
    const r = tela.getBoundingClientRect();
    if (!r.width || !r.height) return;
    renderer.setSize(r.width, r.height, false);
    camera.aspect = r.width / r.height;
    camera.updateProjectionMatrix();
    sujo = true;
  }

  function passo(agora) {
    if (solto || visor.hidden || !visivel || document.hidden) {
      rodando = false;
      densidade.parou();
      return;
    }
    requestAnimationFrame(passo);
    const dt = Math.min(0.05, (agora - (anterior || agora)) / 1000);
    anterior = agora;
    if (!sozinho && (parado += dt) > 5) sozinho = true;
    if (sozinho) meta.giro += dt * 0.25;
    // vai macio até onde o dedo mandou
    const k = 1 - Math.exp(-dt * 12);
    const antes = vista.giro + vista.inclinacao + vista.perto;
    vista.giro += (meta.giro - vista.giro) * k;
    vista.inclinacao += (meta.inclinacao - vista.inclinacao) * k;
    vista.perto += (meta.perto - vista.perto) * k;
    if (Math.abs(vista.giro + vista.inclinacao + vista.perto - antes) > 1e-5) sujo = true;
    if (!sujo) {
      densidade.parou();
      return;
    }
    sujo = false;
    posicionar();
    renderer.render(cena, camera);
    // os quadros lentos (a placa não dá conta da densidade): desce a densidade e redesenha
    if (densidade.quadro(agora)) { medir(); sujo = true; }
  }

  function acordar() {
    if (solto) return;
    medir();
    if (rodando) return;
    rodando = true;
    anterior = 0;
    requestAnimationFrame(passo);
  }

  // ---- mexer: arrastar gira, pinça e rodinha aproximam, toque duplo volta ----
  const dedos = new Map();
  let pinca = 0;
  const mexeu = () => { sozinho = false; parado = 0; };
  tela.addEventListener("pointerdown", (e) => {
    tela.setPointerCapture(e.pointerId);
    dedos.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (dedos.size === 2) {
      const [a, b] = [...dedos.values()];
      pinca = Math.hypot(a.x - b.x, a.y - b.y);
    }
    mexeu();
  });
  tela.addEventListener("pointermove", (e) => {
    const antes = dedos.get(e.pointerId);
    if (!antes) return;
    const agora = { x: e.clientX, y: e.clientY };
    dedos.set(e.pointerId, agora);
    if (dedos.size === 1) {
      const largura = tela.clientWidth || 1;
      meta.giro -= ((agora.x - antes.x) / largura) * Math.PI * 1.6;
      meta.inclinacao = limitar(meta.inclinacao + ((agora.y - antes.y) / largura) * Math.PI, -0.05, 1.25);
    } else if (dedos.size === 2) {
      const [a, b] = [...dedos.values()];
      const d = Math.hypot(a.x - b.x, a.y - b.y);
      if (pinca) meta.perto = limitar(meta.perto * (pinca / d), 0.45, 2.2);
      pinca = d;
    }
    mexeu();
  });
  const soltar = (e) => {
    dedos.delete(e.pointerId);
    pinca = 0;
  };
  tela.addEventListener("pointerup", soltar);
  tela.addEventListener("pointercancel", soltar);
  tela.addEventListener("wheel", (e) => {
    e.preventDefault();
    meta.perto = limitar(meta.perto * Math.exp(e.deltaY * 0.0012), 0.45, 2.2);
    mexeu();
  }, { passive: false });
  tela.addEventListener("dblclick", () => {
    Object.assign(meta, { giro: Math.round(meta.giro / (Math.PI * 2)) * Math.PI * 2 + 0.55, inclinacao: 0.22, perto: 1 });
    mexeu();
  });
  tela.addEventListener("keydown", (e) => {
    const passos = { ArrowLeft: [0.3, 0], ArrowRight: [-0.3, 0], ArrowUp: [0, 0.15], ArrowDown: [0, -0.15] };
    const passoTecla = passos[e.key];
    if (!passoTecla) return;
    e.preventDefault();
    meta.giro += passoTecla[0];
    meta.inclinacao = limitar(meta.inclinacao + passoTecla[1], -0.05, 1.25);
    mexeu();
  });

  const observaTamanho = new ResizeObserver(medir);
  observaTamanho.observe(tela);
  const observaTela = new IntersectionObserver((entradas) => {
    visivel = entradas.some((x) => x.isIntersecting);
    if (visivel) acordar();
  });
  observaTela.observe(tela);
  const aoVoltar = () => { if (!document.hidden) acordar(); };
  document.addEventListener("visibilitychange", aoVoltar);

  // fechar de vez (a janela da proposta troca de item): o WebGL e a memória voltam
  function desligar() {
    if (solto) return;
    solto = true;
    observaTamanho.disconnect();
    observaTela.disconnect();
    document.removeEventListener("visibilitychange", aoVoltar);
    cena.traverse((o) => {
      if (o.geometry) o.geometry.dispose();
      for (const m of [].concat(o.material || [])) {
        for (const valor of Object.values(m)) if (valor && valor.isTexture) valor.dispose();
        m.dispose();
      }
    });
    renderer.dispose();
    renderer.forceContextLoss();
  }

  // ---- as cores ----
  function montarCores() {
  if (coresCaixa) { coresCaixa.replaceChildren(); coresCaixa.hidden = true; }
  const cores = cores3d.coresDoObjeto(gltf);
  if (coresCaixa && cores.length > 1) {
    // o rótulo com o ícone da paleta: "Cores do brinquedo"
    const rotulo = document.createElement("span");
    rotulo.className = "produto-cores-rotulo";
    const iconePaleta = document.createElement("i");
    iconePaleta.className = "fa-solid fa-palette";
    iconePaleta.setAttribute("aria-hidden", "true");
    rotulo.append(iconePaleta, document.createTextNode(" Cores"));
    // a cor da vez e a de antes: tocar de novo na cor escolhida volta para a anterior
    let atual = 0, anterior = 0;
    const escolher = async (i) => {
      if (i === atual) { if (i === 0) return; i = anterior === i ? 0 : anterior; }
      anterior = atual;
      atual = i;
      botoes.forEach((x, k) => x.setAttribute("aria-pressed", k === i ? "true" : "false"));
      await cores3d.aplicarCor(gltf, cores[i]);
      sujo = true;
    };
    const botoes = cores.map((cor, i) => {
      const botao = document.createElement("button");
      botao.type = "button";
      botao.className = "produto-cor3d";
      botao.setAttribute("aria-pressed", i === 0 ? "true" : "false");
      const amostra = cores3d.amostraDaCor(gltf, cor);
      if (amostra) botao.style.setProperty("--amostra", amostra);
      const bolinha = document.createElement("i");
      bolinha.setAttribute("aria-hidden", "true");
      botao.append(bolinha, document.createTextNode(cor.nome));
      botao.addEventListener("click", () => escolher(i));
      return botao;
    });
    coresCaixa.replaceChildren(rotulo, ...botoes);
    coresCaixa.hidden = visor.hidden;
  }
  }
  montarCores();

  // ---- trocar o .glb no mesmo visor (o adesivo): a câmera fica onde está ----
  let vezDaTroca = 0;
  async function trocar(url) {
    if (solto || !url) return;
    const vez = ++vezDaTroca;
    aviso.hidden = false;
    aviso.textContent = "Carregando o 3D…";
    const novo = await carregador.loadAsync(url);
    if (solto || vez !== vezDaTroca) {
      novo.scene.traverse((o) => { if (o.geometry) o.geometry.dispose(); });
      return;
    }
    const velho = objeto;
    cena.remove(velho);
    velho.traverse((o) => {
      if (o.geometry) o.geometry.dispose();
      for (const m of [].concat(o.material || [])) {
        for (const valor of Object.values(m)) if (valor && valor.isTexture) valor.dispose();
        m.dispose();
      }
    });
    gltf = novo;
    vestir(novo);
    visor.dataset.modelo = url;
    montarCores();
    aviso.hidden = true;
    sujo = true;
    acordar();
  }

  // ---- o controle dos adesivos sobre o 3D ----
  if (visor.dataset.adesivos3d && visor.dataset.adesivos3dModulo) {
    import(visor.dataset.adesivos3dModulo).then((modulo) => {
      const modelos = modulo.lerModelos(visor.dataset.adesivos3d);
      if (!modelos.length || solto) return;
      const atual = Math.max(0, modelos.findIndex((m) => m.url === visor.dataset.modelo));
      const campo = document.querySelector("[data-adesivo-escolhido]");
      if (window.getComputedStyle(visor).position === "static") visor.style.position = "relative";
      const controle = modulo.chipsDeAdesivo({
        modelos,
        atual,
        aoEscolher: async (modelo) => {
          await trocar(modelo.url);
          // o adesivo escolhido segue para o carrinho como observação
          if (campo) campo.value = modelo.nome;
          // a página do produto troca as fotos da galeria junto (brinquedo_info.html)
          document.dispatchEvent(new CustomEvent("ls:adesivo", {
            detail: { slug: modelo.slug, nome: modelo.nome, url: modelo.url, origem: "3d" },
          }));
        },
      });
      visor.appendChild(controle);
      // o seletor da galeria trocou o adesivo: o 3D troca junto (a câmera fica)
      const ouvir = (evento) => {
        if (solto) {
          document.removeEventListener("ls:adesivo", ouvir);
          return;
        }
        const detalhe = evento.detail || {};
        if (detalhe.origem === "3d") return;
        const indice = modelos.findIndex((m) => (detalhe.slug && m.slug === detalhe.slug) || (detalhe.url && m.url === detalhe.url));
        if (indice < 0) return;
        controle.marcar(indice);
        trocar(modelos[indice].url);
      };
      document.addEventListener("ls:adesivo", ouvir);
    }).catch((erro) => console.error("Visor 3D: o controle dos adesivos não carregou", erro));
  }

  aviso.hidden = true;
  visor.classList.add("produto-visor3d--pronto");
  return { acordar, soltar: desligar, trocar };
}

function limitar(valor, menor, maior) {
  return Math.min(maior, Math.max(menor, valor));
}
