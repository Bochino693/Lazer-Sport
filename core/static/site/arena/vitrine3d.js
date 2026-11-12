/* ======================================================================
   O 3D NA VITRINE "TODAS AS MÁQUINAS DA FÁBRICA"

   O cartão da máquina que tem objeto 3D mostra o objeto no lugar das
   fotos: sozinho, balança devagar mostrando a frente e os lados e,
   arrastando, a pessoa gira para onde quiser (no mouse, para os lados e para cima e para baixo; no dedo, para
   os lados -- de cima para baixo o dedo continua rolando a página). Dois
   toques voltam para a frente.

   ECONÔMICO DE PROPÓSITO (o catálogo mostra TODOS os objetos 3D):
   - UMA placa de vídeo só para a vitrine inteira: um WebGLRenderer, fora
     da página, desenha o cartão da vez e a imagem vai para o canvas 2D do
     cartão. Antes cada cartão abria o seu contexto WebGL (nove cartões,
     nove contextos -- mais o da arena; o navegador derruba os mais velhos
     depois de 16) e o seu laço de quadros;
   - o .glb de cada cartão só é baixado quando o cartão aparece na tela (até
     ele chegar, e sem JavaScript, fica a foto); o three.js e o leitor vêm
     uma vez só, na primeira vez;
   - UM laço de quadros para todos: ele só roda com algum cartão 3D à vista
     e a aba aberta, e para sozinho quando nenhum está; cada cartão é
     desenhado no máximo 30 vezes por segundo, e só quando algo muda.
   ====================================================================== */

const grade = document.querySelector("[data-fotos-grade]");
const cartoes = grade ? Array.from(grade.querySelectorAll("[data-vitrine3d]")) : [];

if (cartoes.length) {
  let motor = null;
  const visores = new Set(); // os cartões com o 3D montado
  let rodando = false;

  /** O three.js, o leitor e O renderer da vitrine (um só, fora da página). */
  const carregarMotor = () => {
    if (!motor) {
      motor = Promise.all([import(grade.dataset.three), import(grade.dataset.gltf)]).then(([T, leitor]) => {
        const renderer = new T.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "low-power" });
        renderer.toneMapping = T.ACESFilmicToneMapping;
        renderer.toneMappingExposure = 1.05;
        renderer.outputColorSpace = T.SRGBColorSpace;
        renderer.setClearColor(0x000000, 0);
        renderer.setPixelRatio(1); // a densidade vai no tamanho de cada cartão (abaixo)
        return { T, carregador: new leitor.GLTFLoader(), renderer, tamanho: [0, 0] };
      });
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
      if (cartao.visor) {
        cartao.visor.visivel = entrada.isIntersecting;
        cartao.visor.sujo = true;
      }
    });
    acordar();
  }, { rootMargin: "120px 0px" });

  cartoes.forEach((cartao) => aoChegar.observe(cartao));
  document.addEventListener("visibilitychange", acordar);

  /** O laço de quadros: um só, e só com algum cartão 3D à vista. */
  function acordar() {
    if (rodando || document.hidden || ![...visores].some((v) => v.visivel)) return;
    rodando = true;
    let anterior = performance.now();
    const passo = (agora) => {
      const dt = Math.min(0.1, (agora - anterior) / 1000);
      anterior = agora;
      const vistos = [...visores].filter((v) => v.visivel);
      if (document.hidden || !vistos.length) {
        rodando = false;
        return;
      }
      vistos.forEach((v) => v.passo(dt));
      requestAnimationFrame(passo);
    };
    requestAnimationFrame(passo);
  }

  async function montar(cartao) {
    const m = await carregarMotor();
    const { T, carregador, renderer } = m;
    const gltf = await carregador.loadAsync(cartao.dataset.modelo);

    const tela = document.createElement("canvas");
    tela.className = "arena-foto-3d";
    tela.setAttribute("aria-label", "Objeto 3D: arraste para girar");
    cartao.append(tela);
    const pincel = tela.getContext("2d");

    const cena = new T.Scene();
    cena.add(new T.HemisphereLight("#ffffff", "#9aa8bd", 1.6));
    const sol = new T.DirectionalLight("#ffffff", 2.2);
    sol.position.set(4, 9, 7);
    cena.add(sol);
    const contra = new T.DirectionalLight("#cfe0ff", 0.9);
    contra.position.set(-6, 4, -8);
    cena.add(contra);

    let objeto = gltf.scene;
    const caixa = new T.Box3().setFromObject(objeto);
    const tamanho = caixa.getSize(new T.Vector3());
    const centralizar = (o) => {
      const c = new T.Box3().setFromObject(o);
      o.position.x -= (c.min.x + c.max.x) / 2;
      o.position.z -= (c.min.z + c.max.z) / 2;
      o.position.y -= c.min.y;
    };
    centralizar(objeto);
    cena.add(objeto);
    // os sombreadores já agora (em paralelo, onde a placa deixa): o primeiro quadro não engasga
    try { renderer.compileAsync(cena, new T.PerspectiveCamera(), cena).catch(() => {}); } catch (erro) { /* compila no primeiro quadro */ }

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
    let acumulado = 0;
    const visor = { visivel: true, sujo: true, passo: null };
    cartao.visor = visor;

    function medir() {
      const r = tela.getBoundingClientRect();
      if (!r.width || !r.height) return;
      const densidade = Math.min(window.devicePixelRatio || 1, 1.5);
      tela.width = Math.round(r.width * densidade);
      tela.height = Math.round(r.height * densidade);
      camera.aspect = r.width / r.height;
      camera.updateProjectionMatrix();
      visor.sujo = true;
    }

    /** Desenha o cartão na placa da vitrine e copia a imagem para o canvas dele. */
    function desenhar() {
      const w = tela.width;
      const h = tela.height;
      if (!w || !h) return;
      // o renderer cresce até o maior cartão (e fica): sem refazer o buffer a cada cartão
      if (w > m.tamanho[0] || h > m.tamanho[1]) {
        m.tamanho = [Math.max(w, m.tamanho[0]), Math.max(h, m.tamanho[1])];
        renderer.setSize(m.tamanho[0], m.tamanho[1], false);
      }
      renderer.setViewport(0, 0, w, h);
      renderer.setScissor(0, 0, w, h);
      renderer.setScissorTest(true);
      renderer.render(cena, camera);
      renderer.setScissorTest(false);
      // o canto de baixo do buffer (o viewport do WebGL começa embaixo) vai para o cartão
      pincel.clearRect(0, 0, w, h);
      pincel.drawImage(renderer.domElement, 0, m.tamanho[1] - h, w, h, 0, 0, w, h);
    }

    visor.passo = (dt) => {
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
      if (Math.abs(vista.giro + vista.inclinacao - antes) > 1e-5) visor.sujo = true;
      if (!visor.sujo) return;
      visor.sujo = false;
      camera.position.set(
        alvo.x + Math.sin(vista.giro) * Math.cos(vista.inclinacao) * distancia,
        alvo.y + Math.sin(vista.inclinacao) * distancia,
        alvo.z + Math.cos(vista.giro) * Math.cos(vista.inclinacao) * distancia,
      );
      camera.lookAt(alvo);
      desenhar();
    };

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
    // à vista agora? (o cartão pode ter saído da tela enquanto o .glb chegava)
    const r = cartao.getBoundingClientRect();
    visor.visivel = r.bottom > -120 && r.top < window.innerHeight + 120;
    visores.add(visor);
    // o primeiro quadro já agora (o cartão sai da foto para o 3D sem esperar o laço)
    visor.passo(1);
    cartao.classList.add("arena-foto-midia--pronta");
    acordar();

    // OS ADESIVOS (LEIA-ME 72): o produto com outra arte troca o 3D ali mesmo, no cartão
    async function trocar(url) {
      const novo = await carregador.loadAsync(url);
      cena.remove(objeto);
      objeto.traverse((o) => {
        if (o.geometry) o.geometry.dispose();
        for (const mat of [].concat(o.material || [])) {
          for (const valor of Object.values(mat)) if (valor && valor.isTexture) valor.dispose();
          mat.dispose();
        }
      });
      objeto = novo.scene;
      centralizar(objeto);
      cena.add(objeto);
      cartao.dataset.modelo = url;
      visor.sujo = true;
      acordar();
    }
    const dados = cartao.querySelector('script[type="application/json"]');
    if (dados && grade.dataset.adesivos3d) {
      import(grade.dataset.adesivos3d).then((modulo) => {
        const modelos = modulo.lerModelos(dados.textContent);
        if (modelos.length < 2) return;
        const atual = Math.max(0, modelos.findIndex((mo) => mo.url === cartao.dataset.modelo));
        cartao.append(modulo.chipsDeAdesivo({ modelos, atual, aoEscolher: (modelo) => trocar(modelo.url) }));
      }).catch((erro) => console.error("Vitrine 3D: o controle dos adesivos não carregou", erro));
    }
  }
}
