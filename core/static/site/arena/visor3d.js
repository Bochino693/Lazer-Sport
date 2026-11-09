/* ======================================================================
   O VISOR 3D DA PÁGINA DO BRINQUEDO: o objeto 3D (.glb) do cadastro, para
   girar com o dedo ou o mouse, aproximar e trocar de cor -- além das fotos.

   Nada pesa antes da hora: o three.js, o leitor do .glb e as cores
   (cores3d.js) só chegam quando a pessoa toca em "Ver em 3D". E só se
   desenha quando algo muda (girando sozinho, arrastando, trocando de cor)
   e com o visor na tela.
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

async function iniciar(visor, tela, aviso, coresCaixa) {
  aviso.hidden = false;
  aviso.textContent = "Carregando o 3D…";
  const [T, leitor, cores3d] = await Promise.all([
    import(visor.dataset.three),
    import(visor.dataset.gltf),
    import(visor.dataset.cores3d),
  ]);

  const renderer = new T.WebGLRenderer({ canvas: tela, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.toneMapping = T.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.outputColorSpace = T.SRGBColorSpace;
  renderer.setClearColor(0x000000, 0);

  const cena = new T.Scene();
  cena.add(new T.HemisphereLight("#ffffff", "#9aa8bd", 1.6));
  const sol = new T.DirectionalLight("#ffffff", 2.2);
  sol.position.set(4, 9, 7);
  cena.add(sol);
  const contra = new T.DirectionalLight("#cfe0ff", 0.9);
  contra.position.set(-6, 4, -8);
  cena.add(contra);

  const camera = new T.PerspectiveCamera(32, 1, 0.01, 100);
  const gltf = await new leitor.GLTFLoader().loadAsync(visor.dataset.modelo);
  const objeto = gltf.scene;
  const caixa = new T.Box3().setFromObject(objeto);
  const tamanho = caixa.getSize(new T.Vector3());
  // a máquina em pé no chão, com o centro no meio da tela
  objeto.position.x -= (caixa.min.x + caixa.max.x) / 2;
  objeto.position.z -= (caixa.min.z + caixa.max.z) / 2;
  objeto.position.y -= caixa.min.y;
  cena.add(objeto);
  const raio = tamanho.length() / 2;
  const alvo = new T.Vector3(0, tamanho.y / 2, 0);
  camera.near = raio / 100;
  camera.far = raio * 30;

  // a sombra macia embaixo (um disco com degradê: leve e sem luz de sombra)
  const pintura = document.createElement("canvas");
  pintura.width = pintura.height = 128;
  const g = pintura.getContext("2d");
  const degrade = g.createRadialGradient(64, 64, 4, 64, 64, 64);
  degrade.addColorStop(0, "rgba(10,30,60,.42)");
  degrade.addColorStop(1, "rgba(10,30,60,0)");
  g.fillStyle = degrade;
  g.fillRect(0, 0, 128, 128);
  const sombra = new T.Mesh(
    new T.PlaneGeometry(1, 1),
    new T.MeshBasicMaterial({ map: new T.CanvasTexture(pintura), transparent: true, depthWrite: false }),
  );
  sombra.rotation.x = -Math.PI / 2;
  sombra.position.y = 0.002;
  sombra.scale.set(tamanho.x * 1.5, tamanho.z * 1.5, 1);
  cena.add(sombra);

  // a câmera em volta: giro (de frente = 0), inclinação e distância
  const vista = { giro: 0.55, inclinacao: 0.22, perto: 1 };
  const meta = { ...vista };
  // a esfera em volta da caixa sobra nos cantos: um pouco mais perto que ela
  const distanciaBase = (raio / Math.sin(((camera.fov / 2) * Math.PI) / 180)) * 0.88;
  let sozinho = true; // gira devagar até a pessoa mexer
  let parado = 0;
  let sujo = true;
  let rodando = false;
  let visivel = true;
  let anterior = 0;

  function posicionar() {
    const d = distanciaBase * vista.perto * (camera.aspect < 1 ? 1.25 : 1);
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
    if (visor.hidden || !visivel || document.hidden) {
      rodando = false;
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
    if (!sujo) return;
    sujo = false;
    posicionar();
    renderer.render(cena, camera);
  }

  function acordar() {
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

  new ResizeObserver(medir).observe(tela);
  new IntersectionObserver((entradas) => {
    visivel = entradas.some((x) => x.isIntersecting);
    if (visivel) acordar();
  }).observe(tela);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) acordar(); });

  // ---- as cores ----
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

  aviso.hidden = true;
  visor.classList.add("produto-visor3d--pronto");
  return { acordar };
}

function limitar(valor, menor, maior) {
  return Math.min(maior, Math.max(menor, valor));
}
