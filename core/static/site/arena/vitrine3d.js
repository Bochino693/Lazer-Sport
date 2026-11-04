/* ======================================================================
   O 3D NA VITRINE "TODAS AS MÁQUINAS DA FÁBRICA"

   O cartão da máquina que tem objeto 3D mostra o objeto no lugar das
   fotos: sozinho, balança devagar mostrando a frente e os lados e,
   arrastando, a pessoa gira para onde quiser (no mouse, para os lados e para cima e para baixo; no dedo, para
   os lados -- de cima para baixo o dedo continua rolando a página). Dois
   toques voltam para a frente.

   Leve de propósito: cada cartão só monta o seu 3D quando chega perto da
   tela (o three.js e o leitor do .glb vêm uma vez só, na primeira vez), só
   desenha enquanto está visível e no máximo 30 quadros por segundo; até o
   objeto chegar, fica a foto. Sem JavaScript, fica a foto.
   ====================================================================== */

const grade = document.querySelector("[data-fotos-grade]");
const cartoes = grade ? Array.from(grade.querySelectorAll("[data-vitrine3d]")) : [];

if (cartoes.length) {
  let motor = null;
  const carregarMotor = () => {
    if (!motor) {
      motor = Promise.all([import(grade.dataset.three), import(grade.dataset.gltf)]).then(([T, leitor]) => ({
        T,
        carregador: new leitor.GLTFLoader(),
      }));
    }
    return motor;
  };

  const aoChegar = new IntersectionObserver((entradas) => {
    entradas.forEach((entrada) => {
      const cartao = entrada.target;
      if (entrada.isIntersecting && !cartao.dataset.montado) {
        cartao.dataset.montado = "1";
        montar(cartao).catch((erro) => console.error("Vitrine 3D: o objeto não carregou", erro));
      }
      if (cartao.visor) cartao.visor.visivel = entrada.isIntersecting;
    });
  }, { rootMargin: "250px 0px" });

  cartoes.forEach((cartao) => aoChegar.observe(cartao));

  async function montar(cartao) {
    const { T, carregador } = await carregarMotor();
    const gltf = await carregador.loadAsync(cartao.dataset.modelo);

    const tela = document.createElement("canvas");
    tela.className = "arena-foto-3d";
    tela.setAttribute("aria-label", "Objeto 3D: arraste para girar");
    cartao.append(tela);

    const renderer = new T.WebGLRenderer({ canvas: tela, antialias: true, alpha: true, powerPreference: "low-power" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
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

    const objeto = gltf.scene;
    const caixa = new T.Box3().setFromObject(objeto);
    const tamanho = caixa.getSize(new T.Vector3());
    objeto.position.x -= (caixa.min.x + caixa.max.x) / 2;
    objeto.position.z -= (caixa.min.z + caixa.max.z) / 2;
    objeto.position.y -= caixa.min.y;
    cena.add(objeto);

    const raio = tamanho.length() / 2;
    const alvo = new T.Vector3(0, tamanho.y * 0.48, 0);
    const camera = new T.PerspectiveCamera(30, 1, raio / 100, raio * 30);
    // a esfera em volta do objeto inteiro: nada sai do cartão ao girar
    const distancia = (raio / Math.sin(((camera.fov / 2) * Math.PI) / 180)) * 1.02;
    // o espaço grande (39 m) fica melhor visto de cima; a máquina, de frente
    const deitado = tamanho.x > tamanho.y * 3 || tamanho.z > tamanho.y * 3;
    const inicio = { giro: 0.6, inclinacao: deitado ? 0.62 : 0.2 };
    const vista = { ...inicio };
    const meta = { ...inicio };

    let sozinho = true;
    let parado = 0;
    const BALANCO = 0.85; // até ~50° para cada lado
    let centro = 0;
    let tempo = Math.asin(inicio.giro / BALANCO) / 0.45;
    let sujo = true;
    let anterior = 0;
    let acumulado = 0;
    const visor = { visivel: true };
    cartao.visor = visor;

    function medir() {
      const r = tela.getBoundingClientRect();
      if (!r.width || !r.height) return;
      renderer.setSize(r.width, r.height, false);
      camera.aspect = r.width / r.height;
      camera.updateProjectionMatrix();
      sujo = true;
    }

    function passo(agora) {
      requestAnimationFrame(passo);
      const dt = Math.min(0.1, (agora - (anterior || agora)) / 1000);
      anterior = agora;
      if (!visor.visivel || document.hidden) return;
      acumulado += dt;
      if (acumulado < 1 / 30) return; // 30 quadros bastam para girar liso
      const passoDt = acumulado;
      acumulado = 0;
      if (!sozinho && (parado += passoDt) > 4) {
        sozinho = true;
        // volta a balançar em volta da frente mais perto de onde a pessoa deixou
        centro = Math.round(meta.giro / (Math.PI * 2)) * Math.PI * 2;
        tempo = Math.asin(Math.max(-1, Math.min(1, (meta.giro - centro) / BALANCO))) / 0.45;
      }
      // sozinho, balança de um lado para o outro mostrando a frente (de
      // costas, a vitrine não mostra nada); arrastando, gira inteiro
      if (sozinho) {
        tempo += passoDt;
        meta.giro = centro + Math.sin(tempo * 0.45) * BALANCO;
      }
      const k = 1 - Math.exp(-passoDt * 10);
      const antes = vista.giro + vista.inclinacao;
      vista.giro += (meta.giro - vista.giro) * k;
      vista.inclinacao += (meta.inclinacao - vista.inclinacao) * k;
      if (Math.abs(vista.giro + vista.inclinacao - antes) > 1e-5) sujo = true;
      if (!sujo) return;
      sujo = false;
      camera.position.set(
        alvo.x + Math.sin(vista.giro) * Math.cos(vista.inclinacao) * distancia,
        alvo.y + Math.sin(vista.inclinacao) * distancia,
        alvo.z + Math.cos(vista.giro) * Math.cos(vista.inclinacao) * distancia,
      );
      camera.lookAt(alvo);
      renderer.render(cena, camera);
    }

    // arrastar gira; no dedo, só para os lados (o resto rola a página)
    let toque = null;
    tela.addEventListener("pointerdown", (e) => {
      toque = { x: e.clientX, y: e.clientY, mouse: e.pointerType === "mouse" };
      if (toque.mouse) tela.setPointerCapture(e.pointerId);
      sozinho = false;
      parado = 0;
    });
    tela.addEventListener("pointermove", (e) => {
      if (!toque) return;
      const largura = tela.clientWidth || 1;
      meta.giro -= ((e.clientX - toque.x) / largura) * Math.PI * 1.6;
      if (toque.mouse) {
        meta.inclinacao = Math.min(1.2, Math.max(-0.05, meta.inclinacao + ((e.clientY - toque.y) / largura) * Math.PI));
      }
      toque.x = e.clientX;
      toque.y = e.clientY;
      parado = 0;
    });
    const soltar = () => { toque = null; };
    tela.addEventListener("pointerup", soltar);
    tela.addEventListener("pointercancel", soltar);
    tela.addEventListener("dblclick", () => {
      meta.giro = Math.round(meta.giro / (Math.PI * 2)) * Math.PI * 2 + inicio.giro;
      meta.inclinacao = inicio.inclinacao;
      sozinho = false;
      parado = 0;
    });

    new ResizeObserver(medir).observe(tela);
    medir();
    requestAnimationFrame(passo);
    cartao.classList.add("arena-foto-midia--pronta");
  }
}
