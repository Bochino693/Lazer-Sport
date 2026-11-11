/* ======================================================================
   AS FOTOS QUE GIRAM NOS CARDS (LEIA-ME, seção 72)

   O cliente: "quando o brinquedo tiver mais que uma, no card de
   apresentação em home ou em brinquedos, deve ficar rodando as fotos". O
   card de todo brinquedo com mais de uma foto traz a lista delas
   (`data-fotos-card`, core/templatetags/giro.py: a capa primeiro e até
   quatro) e aqui elas se revezam a cada ~3 s, com uma troca suave (a
   próxima aparece por cima, aos poucos).

   Cada foto passa pelo MESMO tratamento da foto do card (ls-fotos.js,
   `window.LSFotos`): a que tem fundo enche a caixa, recortada pelo conteúdo
   no formato dela; a recortada (transparente) fica inteira. Só gira o card
   que está na tela e com a aba à vista; para no mouse em cima ou no foco do
   teclado; com "reduzir movimento", não gira. A próxima foto só é baixada
   pouco antes da troca e só com o card na tela (fora dela, nada de rede).
   ====================================================================== */
(function () {
  "use strict";

  const INTERVALO = 3200;   // ms entre uma troca e a próxima
  const ANTES = 1300;       // ms antes da troca em que a próxima começa a vir
  const TROCA = 620;        // ms da troca suave (a do CSS, .card-giro-camada)
  if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  const fotos = window.LSFotos || null;
  const estados = new Map(); // a caixa da foto -> o estado dela
  const vistos = new WeakSet();

  const caixaDe = (marca) => (fotos && marca.closest(fotos.CARTOES)) || marca.parentElement;
  const fotoDa = (caixa) => (fotos ? fotos.fotoDa(caixa) : caixa.querySelector("img"));

  const preparar = (url, caixa) => (fotos ? fotos.preparar(url, caixa) : Promise.resolve({ src: url, cheia: null }));

  const baixar = (src) => new Promise((pronto) => {
    const img = new Image();
    img.decoding = "async";
    img.onload = () => (img.decode ? img.decode().catch(() => {}) : Promise.resolve()).then(() => pronto(true));
    img.onerror = () => pronto(false);
    img.src = src;
  });

  // a próxima foto, pronta e já baixada (só com o card na tela)
  const adiantar = (estado) => {
    if (estado.vindo) return;
    const indice = (estado.indice + 1) % estado.lista.length;
    estado.vindo = preparar(estado.lista[indice], estado.caixa).then(async (pronta) => {
      const ok = await baixar(pronta.src);
      return ok ? { ...pronta, indice } : null;
    }).catch(() => null);
  };

  // a camada por cima: no lugar e do jeito da foto do card
  const camadaPara = (foto, src) => {
    const camada = document.createElement("img");
    camada.className = "card-giro-camada";
    camada.alt = "";
    camada.setAttribute("aria-hidden", "true");
    camada.decoding = "async";
    const estilo = window.getComputedStyle(foto);
    for (const prop of ["objectFit", "objectPosition", "padding", "borderRadius", "filter", "boxSizing", "transform"]) {
      camada.style[prop] = estilo[prop];
    }
    camada.style.left = `${foto.offsetLeft}px`;
    camada.style.top = `${foto.offsetTop}px`;
    camada.style.width = `${foto.offsetWidth}px`;
    camada.style.height = `${foto.offsetHeight}px`;
    camada.src = src;
    return camada;
  };

  const trocar = async (estado) => {
    const pronta = await estado.vindo;
    estado.vindo = null;
    if (!pronta) { estado.proxima = Date.now() + INTERVALO; return; }
    const { caixa } = estado;
    const foto = fotoDa(caixa);
    if (!foto) return;
    const mesmaCaixa = !fotos || pronta.cheia === null || pronta.cheia === caixa.classList.contains("foto-cheia");
    if (mesmaCaixa && foto.offsetWidth) {
      // a troca suave: a próxima por cima, aparecendo; depois ela vira a foto do card
      if (window.getComputedStyle(caixa).position === "static") caixa.style.position = "relative";
      const camada = camadaPara(foto, pronta.src);
      caixa.appendChild(camada);
      requestAnimationFrame(() => requestAnimationFrame(() => camada.classList.add("card-giro-visivel")));
      await new Promise((r) => window.setTimeout(r, TROCA + 40));
      foto.removeAttribute("srcset");
      foto.removeAttribute("sizes");
      foto.src = pronta.src;
      if (fotos && pronta.cheia !== null) fotos.vestirCaixa(caixa, pronta);
      await (foto.decode ? foto.decode().catch(() => {}) : Promise.resolve());
      camada.remove();
    } else {
      // de uma foto com fundo para uma recortada (ou o contrário): a caixa muda de jeito,
      // então a foto some rapidinho, troca e volta
      foto.classList.add("card-giro-sumindo");
      await new Promise((r) => window.setTimeout(r, 300));
      foto.removeAttribute("srcset");
      foto.removeAttribute("sizes");
      foto.src = pronta.src;
      fotos.vestirCaixa(caixa, pronta);
      await (foto.decode ? foto.decode().catch(() => {}) : Promise.resolve());
      foto.classList.remove("card-giro-sumindo");
    }
    estado.indice = pronta.indice;
    estado.proxima = Date.now() + INTERVALO;
  };

  const vigia = "IntersectionObserver" in window
    ? new IntersectionObserver((entradas) => {
      entradas.forEach((e) => {
        const estado = estados.get(e.target);
        if (!estado) return;
        estado.visivel = e.isIntersecting;
        if (estado.visivel && estado.proxima < Date.now()) estado.proxima = Date.now() + INTERVALO;
      });
    }, { threshold: 0.35 })
    : null;

  const procurar = (raiz) => {
    raiz.querySelectorAll("[data-fotos-card]").forEach((marca) => {
      if (vistos.has(marca)) return;
      vistos.add(marca);
      let lista = [];
      try { lista = JSON.parse(marca.dataset.fotosCard || "[]"); } catch (erro) { lista = []; }
      const caixa = caixaDe(marca);
      if (!caixa || !fotoDa(caixa) || lista.length < 2 || estados.has(caixa)) return;
      const estado = {
        caixa, lista, indice: 0, visivel: !vigia, pausado: false, vindo: null, trocando: false,
        // os cards não trocam todos juntos: cada um começa um pouco depois
        proxima: Date.now() + INTERVALO + (estados.size % 5) * 450,
      };
      estados.set(caixa, estado);
      const card = caixa.closest("a, [data-card-link], .card-produto, .catalogo-card, .loja-card, .ls-result") || caixa;
      card.addEventListener("mouseenter", () => { estado.pausado = true; });
      card.addEventListener("mouseleave", () => { estado.pausado = false; });
      card.addEventListener("focusin", () => { estado.pausado = true; });
      card.addEventListener("focusout", () => { estado.pausado = false; });
      if (vigia) vigia.observe(caixa);
    });
  };

  const relogio = () => {
    if (document.hidden) return;
    const agora = Date.now();
    estados.forEach((estado) => {
      if (!estado.visivel || estado.pausado || estado.trocando) return;
      if (agora >= estado.proxima - ANTES) adiantar(estado);
      if (agora >= estado.proxima) {
        estado.trocando = true;
        trocar(estado).finally(() => { estado.trocando = false; });
      }
    });
  };

  const comecar = () => {
    procurar(document);
    window.setInterval(relogio, 250);
    let agendado = 0;
    new MutationObserver(() => {
      if (agendado) return;
      agendado = window.setTimeout(() => { agendado = 0; procurar(document); }, 150);
    }).observe(document.body, { childList: true, subtree: true });
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", comecar);
  else comecar();
})();
