/* ======================================================================
   "VER EM 3D" NA FICHA DO PROJETO (partials/ficha_galeria.html).

   O projeto que tem objeto 3D (feito no painel: pelas fotos do projeto,
   pelas fotos e medidas, ou por um arquivo 3D convertido) ganha o botão
   no canto do visor. No toque, as fotos dão lugar ao objeto girando --
   arrastar gira, pinça e rodinha aproximam, toque duplo volta --; no
   segundo toque, as fotos voltam.

   Nada pesa antes da hora: o three.js e o leitor do .glb só chegam no
   primeiro toque, e só se desenha com a ficha aberta, o 3D à mostra e algo
   mudando (girando sozinho ou pelo dedo).
   ====================================================================== */

const motores = new WeakMap(); // botão -> Promise<{ acordar }>
let modulos = null;

document.addEventListener("click", (evento) => {
  const botao = evento.target.closest("[data-ficha-3d]");
  if (!botao) return;
  evento.preventDefault();
  const visor = botao.closest(".ls-ficha-visor");
  const palco = visor && visor.querySelector("[data-ficha-3d-palco]");
  if (!palco) return;
  const ligar = palco.hidden;
  palco.hidden = !ligar;
  visor.classList.toggle("ls-ficha-visor--3d", ligar);
  botao.setAttribute("aria-pressed", ligar ? "true" : "false");
  const texto = botao.querySelector("[data-ficha-3d-texto]");
  if (texto) texto.textContent = ligar ? "Ver as fotos" : "Ver em 3D";
  const icone = botao.querySelector("i");
  if (icone) icone.className = ligar ? "fa-solid fa-images" : "fa-solid fa-cube";
  if (!ligar) return;
  if (!motores.has(botao)) {
    motores.set(botao, iniciar(botao, palco).catch((erro) => {
      console.error("Ficha 3D: não abriu", erro);
      const aviso = palco.querySelector("[data-ficha-3d-aviso]");
      aviso.hidden = false;
      aviso.textContent = "Não deu para abrir o 3D neste aparelho. As fotos continuam aqui.";
      return null;
    }));
  }
  motores.get(botao).then((motor) => motor && motor.acordar());
});

async function iniciar(botao, palco) {
  const tela = palco.querySelector("canvas");
  const aviso = palco.querySelector("[data-ficha-3d-aviso]");
  aviso.hidden = false;
  aviso.textContent = "Carregando o 3D…";
  if (!modulos) {
    modulos = Promise.all([import(botao.dataset.three), import(botao.dataset.gltf)]);
  }
  const [T, leitor] = await modulos;

  const renderer = new T.WebGLRenderer({ canvas: tela, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.toneMapping = T.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.outputColorSpace = T.SRGBColorSpace;
  renderer.setClearColor(0x000000, 0);

  const cena = new T.Scene();
  cena.add(new T.HemisphereLight("#ffffff", "#9aa8bd", 1.7));
  const sol = new T.DirectionalLight("#ffffff", 2.1);
  sol.position.set(4, 9, 7);
  cena.add(sol);
  const contra = new T.DirectionalLight("#cfe0ff", 0.9);
  contra.position.set(-6, 4, -8);
  cena.add(contra);

  const gltf = await new leitor.GLTFLoader().loadAsync(botao.getAttribute("data-ficha-3d"));
  const objeto = gltf.scene;
  const caixa = new T.Box3().setFromObject(objeto);
  const tamanho = caixa.getSize(new T.Vector3());
  objeto.position.x -= (caixa.min.x + caixa.max.x) / 2;
  objeto.position.z -= (caixa.min.z + caixa.max.z) / 2;
  objeto.position.y -= caixa.min.y;
  cena.add(objeto);

  // a sombra macia no chão: um disco com degradê, sem luz de sombra
  const pintura = document.createElement("canvas");
  pintura.width = pintura.height = 128;
  const g = pintura.getContext("2d");
  const degrade = g.createRadialGradient(64, 64, 4, 64, 64, 64);
  degrade.addColorStop(0, "rgba(10,30,60,.45)");
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

  const raio = Math.max(tamanho.length() / 2, 0.05);
  const alvo = new T.Vector3(0, tamanho.y / 2, 0);
  const camera = new T.PerspectiveCamera(32, 1, raio / 100, raio * 30);
  const INICIAL = { giro: 0.55, inclinacao: 0.22, perto: 1 };
  const vista = { ...INICIAL };
  const meta = { ...INICIAL };
  const distanciaBase = (raio / Math.sin((16 * Math.PI) / 180)) * 0.88;
  let sozinho = true;
  let parado = 0;
  let sujo = true;
  let rodando = false;
  let visivel = true;
  let anterior = 0;

  function medir() {
    const r = tela.getBoundingClientRect();
    if (!r.width || !r.height) return;
    renderer.setSize(r.width, r.height, false);
    camera.aspect = r.width / r.height;
    camera.updateProjectionMatrix();
    sujo = true;
  }

  function passo(agora) {
    const ficha = palco.closest(".ls-ficha");
    if (palco.hidden || (ficha && ficha.hidden) || !visivel || document.hidden) {
      rodando = false;
      return;
    }
    requestAnimationFrame(passo);
    const dt = Math.min(0.05, (agora - (anterior || agora)) / 1000);
    anterior = agora;
    if (!sozinho && (parado += dt) > 5) sozinho = true;
    if (sozinho) meta.giro += dt * 0.25;
    const k = 1 - Math.exp(-dt * 12);
    const antes = vista.giro + vista.inclinacao + vista.perto;
    vista.giro += (meta.giro - vista.giro) * k;
    vista.inclinacao += (meta.inclinacao - vista.inclinacao) * k;
    vista.perto += (meta.perto - vista.perto) * k;
    if (Math.abs(vista.giro + vista.inclinacao + vista.perto - antes) > 1e-5) sujo = true;
    if (!sujo) return;
    sujo = false;
    const d = distanciaBase * vista.perto * (camera.aspect < 1 ? 1.3 : 1);
    camera.position.set(
      alvo.x + Math.sin(vista.giro) * Math.cos(vista.inclinacao) * d,
      alvo.y + Math.sin(vista.inclinacao) * d,
      alvo.z + Math.cos(vista.giro) * Math.cos(vista.inclinacao) * d,
    );
    camera.lookAt(alvo);
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
  const limitar = (v, a, b) => Math.min(b, Math.max(a, v));
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
  const soltar = (e) => { dedos.delete(e.pointerId); pinca = 0; };
  tela.addEventListener("pointerup", soltar);
  tela.addEventListener("pointercancel", soltar);
  tela.addEventListener("wheel", (e) => {
    e.preventDefault();
    meta.perto = limitar(meta.perto * Math.exp(e.deltaY * 0.0012), 0.45, 2.2);
    mexeu();
  }, { passive: false });
  tela.addEventListener("dblclick", () => {
    Object.assign(meta, { giro: Math.round(meta.giro / (Math.PI * 2)) * Math.PI * 2 + INICIAL.giro, inclinacao: INICIAL.inclinacao, perto: 1 });
    mexeu();
  });

  new ResizeObserver(medir).observe(tela);
  new IntersectionObserver((entradas) => {
    visivel = entradas.some((x) => x.isIntersecting);
    if (visivel) acordar();
  }).observe(tela);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) acordar(); });

  aviso.hidden = true;
  return { acordar };
}
