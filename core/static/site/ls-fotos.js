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

   NUNCA CORTAR O BRINQUEDO (o Pega Toupeira saía cortado, com zoom: a foto
   em pé, com fundo, preenchia o cartão quadrado). Se o formato da foto não é
   o da caixa (mais de ~10% de diferença), ela fica INTEIRA ("contain") sobre
   ela mesma desfocada (`foto-encaixada`), como nas vitrines do quadro
   inicial; só a foto do mesmo formato (as capas em cena, quadradas) preenche
   a caixa de ponta a ponta.
   ====================================================================== */
(function () {
  "use strict";

  // as caixas de foto dos cartões de produto do site
  const CARTOES = [
    ".card-produto .img-area",
    ".pecas-card .img-area",
    ".pc-media",
    ".catalogo-card-media",
    ".loja-card-img",
    ".arena-product-visual",
    ".arena-foto-midia",
    ".ls-result-media",
    ".desejo-foto",
    ".ls-vitrine-foto",
  ].join(",");

  const SEM_TRANSPARENCIA = /\.(jpe?g|jfif)$/i;
  const MEMORIA = "ls-foto-cheia2:";
  const decididos = new WeakSet();

  const lembrar = (url, valor) => {
    try { window.sessionStorage.setItem(MEMORIA + url, valor); } catch (erro) { /* aba anônima */ }
  };
  const lembrado = (url) => {
    try { return window.sessionStorage.getItem(MEMORIA + url); } catch (erro) { return null; }
  };

  // a cópia pequena da foto: no Cloudinary, 24 px em PNG (guarda o alfa)
  const miniatura = (url) => {
    const partes = url.match(/^(.*\/upload\/)(?:[a-z]_[^/]*\/)?(.*)$/);
    return url.includes("res.cloudinary.com") && partes ? `${partes[1]}c_scale,w_24,f_png/${partes[2]}` : url;
  };

  /** { cheia: a foto tem fundo?, proporcao: largura / altura } ou null (não deu para saber). */
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
        pronto({ cheia: pontos.every(([x, y]) => alfa[(y * w + x) * 4 + 3] > 245), proporcao: img.naturalWidth / img.naturalHeight });
      } catch (erro) {
        pronto({ cheia: null, proporcao: img.naturalWidth / img.naturalHeight || 0 });
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

  // a foto de outro formato que o da caixa (mais de ~10%): inteira, sobre ela mesma desfocada
  const outroFormato = (caixa, proporcao) => {
    const w = caixa.clientWidth, h = caixa.clientHeight;
    return Boolean(proporcao && w && h) && Math.abs(Math.log(proporcao / (w / h))) > 0.1;
  };

  const marcar = (caixa, cheia, proporcao) => {
    if (!cheia) return;
    caixa.classList.add("foto-cheia");
    const foto = caixa.querySelector("img");
    const fundo = () => caixa.style.setProperty("--foto-fundo", `url("${desfocada(foto.getAttribute("src") || "")}")`);
    if (caixa.matches(".ls-vitrine-foto")) {
      fundo();
    } else if (outroFormato(caixa, proporcao || (foto.naturalWidth / foto.naturalHeight))) {
      caixa.classList.add("foto-encaixada");
      fundo();
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
    const memoria = lembrado(url);
    if (memoria !== null) {
      const [cheia, proporcao] = memoria.split(":");
      marcar(caixa, cheia === "1", Number(proporcao) || 0);
      return;
    }
    sondar(url).then((sonda) => {
      if (sonda === null) {
        // a sonda não carregou: o JPG tem fundo de todo jeito (o formato vem da própria foto)
        if (SEM_TRANSPARENCIA.test(caminho)) marcar(caixa, true, 0);
        return;
      }
      const cheia = SEM_TRANSPARENCIA.test(caminho) ? true : sonda.cheia;
      if (cheia === null) return;
      lembrar(url, `${cheia ? 1 : 0}:${sonda.proporcao.toFixed(3)}`);
      marcar(caixa, cheia, sonda.proporcao);
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
