/* ======================================================================
   FOTO COM FUNDO OCUPA O CARTÃO INTEIRO

   Os cartões de produto mostram a foto inteira ("contain") num fundo
   claro de estúdio: perfeito para a foto recortada (PNG transparente), que
   parece estar de pé no cartão. Mas a foto tirada com fundo -- o showroom,
   a parede, o fundo branco do fotógrafo -- ficava com uma moldura em
   volta, as bordas do cartão sobrando dos lados.

   Aqui cada cartão descobre de que tipo é a sua foto:
     - JPG nunca tem transparência: tem fundo, vai para o cartão inteiro;
     - PNG e WebP podem ser recorte: uma cópia de 24 px da foto (no
       Cloudinary, ~1 KB) é desenhada num canvas e os cantos dizem se há
       transparência. Sem transparência nos cantos, a foto tem fundo.
   O cartão com fundo ganha a classe `foto-cheia` (ls-tema.css). Se a
   conferência não puder ser feita (rede, CORS), nada muda: fica como era.
   ====================================================================== */
(function () {
  "use strict";

  // as caixas de foto dos cartões de produto do site
  const CARTOES = [
    ".card-produto .img-area",
    ".pecas-card .img-area",
    ".catalogo-card-media",
    ".loja-card-img",
    ".arena-product-visual",
    ".arena-foto-midia",
    ".ls-result-media",
    ".desejo-foto",
    ".ls-vitrine-foto",
  ].join(",");

  const SEM_TRANSPARENCIA = /\.(jpe?g|jfif)$/i;
  const MEMORIA = "ls-foto-cheia:";
  const decididos = new WeakSet();

  const lembrar = (url, valor) => {
    try { window.sessionStorage.setItem(MEMORIA + url, valor ? "1" : "0"); } catch (erro) { /* aba anônima */ }
  };
  const lembrado = (url) => {
    try { return window.sessionStorage.getItem(MEMORIA + url); } catch (erro) { return null; }
  };

  // a cópia pequena da foto: no Cloudinary, 24 px em PNG (guarda o alfa)
  const miniatura = (url) => {
    const partes = url.match(/^(.*\/upload\/)(?:[a-z]_[^/]*\/)?(.*)$/);
    return url.includes("res.cloudinary.com") && partes ? `${partes[1]}c_scale,w_24,f_png/${partes[2]}` : url;
  };

  /** true = a foto tem fundo; false = é recorte; null = não deu para saber. */
  const sondar = (url) => new Promise((pronto) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.decoding = "async";
    img.onload = () => {
      try {
        const w = 24;
        const h = Math.max(1, Math.round((img.naturalHeight / img.naturalWidth) * w)) || 24;
        const tela = document.createElement("canvas");
        tela.width = w;
        tela.height = h;
        const g = tela.getContext("2d", { willReadFrequently: true });
        g.drawImage(img, 0, 0, w, h);
        const alfa = g.getImageData(0, 0, w, h).data;
        // os quatro cantos e o meio de cada lado
        const pontos = [[0, 0], [w - 1, 0], [0, h - 1], [w - 1, h - 1],
          [w >> 1, 0], [w >> 1, h - 1], [0, h >> 1], [w - 1, h >> 1]];
        pronto(pontos.every(([x, y]) => alfa[(y * w + x) * 4 + 3] > 245));
      } catch (erro) {
        pronto(null);
      }
    };
    img.onerror = () => pronto(null);
    img.src = miniatura(url);
  });

  // A cópia desfocada que preenche as sobras da vitrine do quadro inicial
  // (a foto fica inteira; o resto do quadro é ela mesma, sem foco).
  const desfocada = (url) => {
    const partes = url.match(/^(.*\/upload\/)(?:[a-z]_[^/]*\/)?(.*)$/);
    return url.includes("res.cloudinary.com") && partes ? `${partes[1]}c_scale,w_96,e_blur:400,q_auto,f_auto/${partes[2]}` : url;
  };

  const marcar = (caixa, cheia) => {
    if (!cheia) return;
    caixa.classList.add("foto-cheia");
    if (caixa.matches(".ls-vitrine-foto")) {
      const foto = caixa.querySelector("img");
      caixa.style.setProperty("--foto-fundo", `url("${desfocada(foto.getAttribute("src") || "")}")`);
    }
  };

  const decidir = (caixa) => {
    if (decididos.has(caixa)) return;
    decididos.add(caixa);
    const foto = caixa.querySelector("img");
    if (!foto) return;
    const url = foto.getAttribute("src") || "";
    if (!url || url.startsWith("data:") || /\.svg($|\?)/i.test(url)) return;
    const caminho = url.split("?")[0].split("#")[0];
    if (SEM_TRANSPARENCIA.test(caminho)) {
      marcar(caixa, true);
      return;
    }
    const memoria = lembrado(url);
    if (memoria !== null) {
      marcar(caixa, memoria === "1");
      return;
    }
    sondar(url).then((cheia) => {
      if (cheia === null) return;
      lembrar(url, cheia);
      marcar(caixa, cheia);
    });
  };

  // Só confere o cartão quando ele chega perto da tela (a sonda é pequena,
  // mas uma página de catálogo tem dezenas de cartões).
  const vigia = "IntersectionObserver" in window
    ? new IntersectionObserver((entradas) => {
      entradas.forEach((e) => {
        if (!e.isIntersecting) return;
        vigia.unobserve(e.target);
        decidir(e.target);
      });
    }, { rootMargin: "400px 0px" })
    : null;

  const procurar = (raiz) => {
    raiz.querySelectorAll(CARTOES).forEach((caixa) => {
      if (decididos.has(caixa)) return;
      if (vigia) vigia.observe(caixa);
      else decidir(caixa);
    });
  };

  const comecar = () => {
    procurar(document);
    // cartões que chegam depois (filtros, "ver mais", paginação sem recarregar)
    let agendado = 0;
    new MutationObserver(() => {
      if (agendado) return;
      agendado = window.setTimeout(() => { agendado = 0; procurar(document); }, 120);
    }).observe(document.body, { childList: true, subtree: true });
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", comecar);
  else comecar();
})();
