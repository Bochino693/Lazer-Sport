/* ======================================================================
   O 3D DOS ITENS NA PROPOSTA (orcamento_publico.html).

   Cada linha da proposta que tem objeto 3D ganha o "Ver em 3D": a janela
   abre o visor da página do brinquedo (site/arena/visor3d.js) -- girar com
   o dedo ou o mouse, aproximar, trocar as cores -- e as setas passam pelos
   outros itens em 3D da mesma proposta.

   Um visor por vez: ao trocar de item ou fechar a janela, o anterior
   devolve o WebGL e a memória (`soltar`). Nada do 3D chega antes do
   primeiro toque, e a proposta funciona igual sem ele.
   ====================================================================== */

const dialogo = document.getElementById("orc3d");
if (dialogo) ligar(dialogo);

function ligar(dialogo) {
  const botoes = [...document.querySelectorAll("[data-orc3d-abrir]")];
  const palco = dialogo.querySelector("[data-orc3d-palco]");
  const cores = dialogo.querySelector("[data-orc3d-cores]");
  const nome = dialogo.querySelector("#orc3dNome");
  const ficha = dialogo.querySelector("#orc3dFicha");
  const contador = dialogo.querySelector("[data-orc3d-contador]");
  let modulo = null; // o visor3d.js, importado no primeiro toque
  let motor = null; // a promessa do visor da vez
  let atual = -1;

  async function soltarAtual() {
    const anterior = motor;
    motor = null;
    if (anterior) {
      const m = await anterior;
      if (m) m.soltar();
    }
  }

  async function mostrar(indice) {
    if (!botoes.length) return;
    atual = (indice + botoes.length) % botoes.length;
    const botao = botoes[atual];
    nome.textContent = botao.dataset.nome || "";
    ficha.textContent = botao.dataset.ficha || "";
    ficha.hidden = !botao.dataset.ficha;
    if (contador) contador.textContent = `${atual + 1} de ${botoes.length}`;
    if (!dialogo.open) dialogo.showModal();
    soltarAtual(); // o anterior se solta sozinho quando terminar de carregar

    // o visor novo: o mesmo desenho do da página do brinquedo
    const visor = document.createElement("div");
    visor.className = "orc3d-visor";
    visor.dataset.modelo = botao.dataset.modelo;
    visor.dataset.three = dialogo.dataset.three;
    visor.dataset.gltf = dialogo.dataset.gltf;
    visor.dataset.cores3d = dialogo.dataset.cores3d;
    if (dialogo.dataset.realismo3d) visor.dataset.realismo3d = dialogo.dataset.realismo3d;
    // os adesivos do item (LEIA-ME 72): o controle "Adesivo: A · B" troca o 3D aqui mesmo
    if (botao.dataset.adesivos3d) {
      visor.dataset.adesivos3d = botao.dataset.adesivos3d;
      visor.dataset.adesivos3dModulo = dialogo.dataset.adesivos3dModulo;
    }
    const tela = document.createElement("canvas");
    tela.tabIndex = 0;
    tela.setAttribute("aria-label", `${botao.dataset.nome || "Item"} em 3D: arraste para girar, role ou pince para aproximar`);
    const aviso = document.createElement("p");
    aviso.className = "orc3d-aviso";
    visor.append(tela, aviso);
    palco.replaceChildren(visor);
    cores.replaceChildren();
    cores.hidden = true;

    modulo = modulo || import(dialogo.dataset.visor);
    const meu = modulo
      .then(({ iniciar }) => iniciar(visor, tela, aviso, cores))
      .catch((erro) => {
        console.error("Proposta em 3D: não abriu", erro);
        aviso.hidden = false;
        aviso.textContent = "Não deu para abrir o 3D neste aparelho. As fotos e os dados continuam na proposta.";
        return null;
      });
    motor = meu;
    const m = await meu;
    if (!m) return;
    if (motor !== meu || !dialogo.open) {
      m.soltar(); // trocou de item (ou fechou) enquanto carregava
      return;
    }
    m.acordar();
    tela.focus({ preventScroll: true });
  }

  botoes.forEach((botao, i) => botao.addEventListener("click", () => mostrar(i)));
  // a foto da linha com 3D também abre
  botoes.forEach((botao, i) => {
    const foto = botao.closest(".item")?.querySelector(".item-foto--3d");
    if (!foto) return;
    foto.setAttribute("role", "button");
    foto.tabIndex = 0;
    foto.setAttribute("aria-label", `Ver ${botao.dataset.nome || "o item"} em 3D`);
    foto.addEventListener("click", () => mostrar(i));
    foto.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        mostrar(i);
      }
    });
  });
  dialogo.querySelector("[data-orc3d-fechar]").addEventListener("click", () => dialogo.close());
  dialogo.querySelector("[data-orc3d-anterior]")?.addEventListener("click", () => mostrar(atual - 1));
  dialogo.querySelector("[data-orc3d-proximo]")?.addEventListener("click", () => mostrar(atual + 1));
  // tocar fora da janela (no fundo escuro) fecha
  dialogo.addEventListener("click", (e) => {
    if (e.target === dialogo) dialogo.close();
  });
  dialogo.addEventListener("keydown", (e) => {
    if (botoes.length < 2 || e.target.tagName === "CANVAS") return; // as setas giram o objeto no visor
    if (e.key === "PageDown") mostrar(atual + 1);
    if (e.key === "PageUp") mostrar(atual - 1);
  });
  dialogo.addEventListener("close", () => {
    soltarAtual();
    palco.replaceChildren();
    const botao = botoes[atual];
    if (botao) botao.focus({ preventScroll: true });
  });
}
