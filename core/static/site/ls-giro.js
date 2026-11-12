/* ======================================================================
   AS FOTOS QUE GIRAM NOS CARDS: UMA POR ADESIVO (LEIA-ME, seção 72)

   O cliente: "o carrossel não deve ser por posição e sim por adesivos,
   entendeu? com uma transição suave e legal". O card do brinquedo com mais
   de um adesivo traz a lista (`data-fotos-card`, core/templatetags/giro.py:
   [{src, adesivo}], a capa quadrada de cada adesivo, o padrão primeiro) e
   aqui elas se revezam a cada ~3 s: a próxima entra por cima, deslizando um
   pouco de lado e com um zoom leve que assenta, enquanto a de antes recua
   para o outro lado; o nome do adesivo ("Adesivo: Alienígenas") troca junto,
   no canto do card. (A lista antiga, só de endereços, ainda funciona.)

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
  const TROCA = 950;        // ms da troca suave (a do CSS, .card-giro-camada)
  const NOME = 340;         // ms do nome do adesivo sumindo antes de trocar (o CSS, .card-giro-adesivo)
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

  // a próxima foto, pronta e já baixada (só com o card na tela). A foto de formato
  // muito diferente do card (a vista 16:10 no card quadrado) NÃO entra no giro: ela
  // apareceria inteira com faixas, menor que as outras -- o cliente: "não quero fotos
  // cortadas menores, deve seguir o mesmo padrão". Ela é pulada (e lembrada) e o giro
  // segue só com as fotos que enchem o card.
  const adiantar = (estado) => {
    if (estado.vindo) return;
    estado.vindo = (async () => {
      for (let passo = 1; passo < estado.lista.length; passo += 1) {
        const indice = (estado.indice + passo) % estado.lista.length;
        if (estado.puladas.has(indice)) continue;
        const pronta = await preparar(estado.lista[indice].src, estado.caixa).catch(() => null);
        if (!pronta) continue;
        if (pronta.inteira && !estado.caixa.hasAttribute("data-foto-inteira")) {
          estado.puladas.add(indice);
          continue;
        }
        if (await baixar(pronta.src)) return { ...pronta, indice };
      }
      return null;
    })().catch(() => null);
  };

  // a camada por cima: no lugar e do jeito da foto do card
  const camadaPara = (foto, src) => {
    const camada = document.createElement("img");
    camada.className = "card-giro-camada";
    // fora do "esqueleto" das imagens (ls-reveal.js): ele poria a camada à vista na hora, sem a troca
    camada.dataset.lsSkipSkeleton = "true";
    camada.alt = "";
    camada.setAttribute("aria-hidden", "true");
    camada.decoding = "async";
    const estilo = window.getComputedStyle(foto);
    for (const prop of ["objectFit", "objectPosition", "padding", "borderRadius", "boxSizing"]) {
      camada.style[prop] = estilo[prop];
    }
    // o filtro e o transform da foto do card ficam em variáveis: a troca anima por cima deles
    // (a próxima entra com um zoom leve e um desfoque que somem -- ls-tema.css)
    camada.style.setProperty("--giro-filtro", estilo.filter && estilo.filter !== "none" ? estilo.filter : "brightness(1)");
    camada.style.setProperty("--giro-transform", estilo.transform && estilo.transform !== "none" ? estilo.transform : "translateZ(0)");
    camada.style.left = `${foto.offsetLeft}px`;
    camada.style.top = `${foto.offsetTop}px`;
    camada.style.width = `${foto.offsetWidth}px`;
    camada.style.height = `${foto.offsetHeight}px`;
    camada.src = src;
    return camada;
  };

  // o nome do adesivo no canto do card: some, troca e volta junto com a foto
  const nomeDoAdesivo = (estado, indice) => {
    const etiqueta = estado.etiqueta;
    const nome = estado.lista[indice] && estado.lista[indice].adesivo;
    if (!etiqueta || !nome) return;
    etiqueta.classList.add("card-giro-adesivo--trocando");
    window.setTimeout(() => {
      etiqueta.querySelector("b").textContent = nome;
      etiqueta.classList.remove("card-giro-adesivo--trocando");
    }, NOME);
  };

  const trocar = async (estado) => {
    const pronta = await estado.vindo;
    estado.vindo = null;
    if (!pronta) { estado.proxima = Date.now() + INTERVALO; return; }
    const { caixa } = estado;
    const foto = fotoDa(caixa);
    if (!foto) return;
    // a caixa muda de jeito quando a próxima tem (ou não) fundo, ou quando uma fica
    // inteira (a de formato muito diferente, sem zoom) e a outra enche a caixa
    const mesmaCaixa = !fotos || pronta.cheia === null || (
      pronta.cheia === caixa.classList.contains("foto-cheia")
      && Boolean(pronta.inteira) === caixa.classList.contains("foto-inteira"));
    if (mesmaCaixa && foto.offsetWidth) {
      // a troca suave: a próxima por cima, aparecendo; depois ela vira a foto do card
      if (window.getComputedStyle(caixa).position === "static") caixa.style.position = "relative";
      const camada = camadaPara(foto, pronta.src);
      caixa.appendChild(camada);
      requestAnimationFrame(() => requestAnimationFrame(() => {
        camada.classList.add("card-giro-visivel");
        foto.classList.add("card-giro-saindo"); // a de antes recua para o outro lado
        nomeDoAdesivo(estado, pronta.indice);
      }));
      await new Promise((r) => window.setTimeout(r, TROCA + 40));
      foto.removeAttribute("srcset");
      foto.removeAttribute("sizes");
      foto.src = pronta.src;
      if (fotos && pronta.cheia !== null) fotos.vestirCaixa(caixa, pronta);
      await (foto.decode ? foto.decode().catch(() => {}) : Promise.resolve());
      // a foto do card volta ao lugar sem animar (a camada ainda cobre)
      foto.style.transition = "none";
      foto.classList.remove("card-giro-saindo");
      void foto.offsetWidth;
      foto.style.transition = "";
      camada.remove();
    } else {
      // de uma foto com fundo para uma recortada (ou o contrário): a caixa muda de jeito,
      // então a foto some rapidinho, troca e volta
      foto.classList.add("card-giro-sumindo");
      nomeDoAdesivo(estado, pronta.indice);
      await new Promise((r) => window.setTimeout(r, 380));
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
      // [{src, adesivo}] (um por adesivo); a lista antiga, só de endereços, também serve
      lista = lista.map((item) => (typeof item === "string" ? { src: item, adesivo: "" } : item)).filter((item) => item && item.src);
      const caixa = caixaDe(marca);
      if (!caixa || !fotoDa(caixa) || lista.length < 2 || estados.has(caixa)) return;
      const estado = {
        caixa, lista, indice: 0, visivel: !vigia, pausado: false, vindo: null, trocando: false, puladas: new Set(),
        // os cards não trocam todos juntos: cada um começa um pouco depois
        proxima: Date.now() + INTERVALO + (estados.size % 5) * 450,
        etiqueta: null,
      };
      // o nome do adesivo no canto do card ("Adesivo: Astronautas"), quando a lista é por adesivo
      if (lista[0].adesivo) {
        if (window.getComputedStyle(caixa).position === "static") caixa.style.position = "relative";
        const etiqueta = document.createElement("span");
        etiqueta.className = "card-giro-adesivo";
        etiqueta.setAttribute("aria-hidden", "true");
        etiqueta.append("Adesivo: ");
        const nome = document.createElement("b");
        nome.textContent = lista[0].adesivo;
        etiqueta.append(nome);
        caixa.appendChild(etiqueta);
        estado.etiqueta = etiqueta;
      }
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
