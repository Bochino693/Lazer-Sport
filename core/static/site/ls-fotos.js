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

   A FOTO ENCHE A CAIXA, BEM ENQUADRADA (sem as faixas desfocadas dos
   lados). Se o formato da foto não é o da caixa (mais de ~10% de
   diferença), o Cloudinary recorta a foto no formato exato da caixa pelo
   conteúdo (`c_fill,g_auto`: o brinquedo, o que chama a atenção, fica no
   centro do recorte) e ela preenche a caixa de ponta a ponta
   (`foto-enquadrada`). A foto do mesmo formato (as capas em cena) só
   preenche. Fora do Cloudinary, ou se o recorte não carregar, a foto
   original preenche a caixa ("cover") centrada um pouco acima do meio.
   Vale para todos os cartões e para a vitrine do quadro inicial.

   AS FOTOS QUE GIRAM (ls-giro.js, LEIA-ME 72) passam pelas mesmas regras:
   `window.LSFotos.preparar` e `vestirCaixa`.
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
    ".oferta-card-media",
  ].join(",");

  // a foto do cartão (a cópia de fundo, `aria-hidden`, não conta)
  const fotoDa = (caixa) => caixa.querySelector("img:not([aria-hidden='true'])") || caixa.querySelector("img");

  const SEM_TRANSPARENCIA = /\.(jpe?g|jfif)$/i;
  const MEMORIA = "ls-foto-cheia3:";
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
        // a cor média da borda da foto (as 4 beiradas): o fundo da caixa da foto inteira
        let r = 0, gg = 0, b = 0, n = 0;
        for (let x = 0; x < w; x += 1) for (const y of [0, h - 1]) { const i = (y * w + x) * 4; r += alfa[i]; gg += alfa[i + 1]; b += alfa[i + 2]; n += 1; }
        for (let y = 1; y < h - 1; y += 1) for (const x of [0, w - 1]) { const i = (y * w + x) * 4; r += alfa[i]; gg += alfa[i + 1]; b += alfa[i + 2]; n += 1; }
        const borda = n ? [r, gg, b].map((v) => Math.round(v / n)).join(",") : "";
        pronto({ cheia: pontos.every(([x, y]) => alfa[(y * w + x) * 4 + 3] > 245), proporcao: img.naturalWidth / img.naturalHeight, borda });
      } catch (erro) {
        pronto({ cheia: null, proporcao: img.naturalWidth / img.naturalHeight || 0 });
      }
    };
    img.onerror = () => pronto(null);
    img.src = miniatura(url);
  });

  // a foto de outro formato que o da caixa (mais de ~10%)
  const outroFormato = (caixa, proporcao) => {
    const w = caixa.clientWidth, h = caixa.clientHeight;
    return Boolean(proporcao && w && h) && Math.abs(Math.log(proporcao / (w / h))) > 0.1;
  };

  // O recorte da foto no formato da caixa, pelo conteúdo (Cloudinary
  // g_auto). Proporção e largura arredondadas: poucas versões de cada foto.
  const enquadrada = (url, caixa) => {
    const partes = url.match(/^(.*\/upload\/)(?:[a-z]_[^/]*\/)?(.*)$/);
    if (!url.includes("res.cloudinary.com") || !partes) return "";
    const w = caixa.clientWidth, h = caixa.clientHeight;
    if (!w || !h) return "";
    const proporcao = Math.min(3, Math.max(0.4, Math.round((w / h) * 10) / 10));
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const largura = Math.min(1600, Math.max(400, Math.ceil((w * dpr) / 200) * 200));
    return `${partes[1]}c_fill,g_auto,ar_${proporcao},w_${largura},q_auto,f_auto/${partes[2]}`;
  };

  const marcar = (caixa, cheia, proporcao, borda) => {
    if (!cheia) return;
    caixa.classList.add("foto-cheia");
    const foto = fotoDa(caixa);
    // A caixa que mostra a foto INTEIRA (a arte da promoção no quadro do topo da home:
    // o texto dela não pode ser cortado). Sem recorte: a foto inteira, e o que sobra da
    // caixa é a cor da própria borda da foto (a arte continua, sem faixa nem desfoque).
    if (caixa.hasAttribute("data-foto-inteira")) {
      caixa.classList.add("foto-inteira");
      if (borda) caixa.style.setProperty("--foto-borda", `rgb(${borda})`);
      return;
    }
    if (!outroFormato(caixa, proporcao || (foto.naturalWidth / foto.naturalHeight))) return;
    caixa.classList.add("foto-enquadrada");
    const original = foto.getAttribute("src") || "";
    const recorte = enquadrada(original, caixa);
    if (!recorte || recorte === original) return;
    // se o recorte não vier, volta a original (que já preenche a caixa)
    foto.addEventListener("error", () => {
      if (foto.getAttribute("src") === recorte) foto.setAttribute("src", original);
    }, { once: true });
    foto.removeAttribute("srcset");
    foto.removeAttribute("sizes");
    foto.setAttribute("src", recorte);
  };

  /**
   * A foto `url` pronta para a `caixa`, pelas mesmas regras do cartão (para
   * o ls-giro.js, que reveza as fotos do card): { src, cheia, enquadrada }.
   * `cheia`: a foto tem fundo (vai de ponta a ponta); `enquadrada`: é o
   * recorte no formato da caixa pelo conteúdo (o `src` já é o recorte).
   */
  const preparar = async (url, caixa) => {
    const caminho = url.split("?")[0].split("#")[0];
    let cheia = null;
    let proporcao = 0;
    const memoria = lembrado(url);
    if (memoria !== null) {
      const [c, p] = memoria.split(":");
      cheia = c === "1";
      proporcao = Number(p) || 0;
    } else {
      const sonda = await sondar(url);
      if (sonda) {
        cheia = SEM_TRANSPARENCIA.test(caminho) ? true : sonda.cheia;
        proporcao = sonda.proporcao || 0;
        if (cheia !== null) lembrar(url, `${cheia ? 1 : 0}:${proporcao.toFixed(3)}:${sonda.borda || ""}`);
      } else if (SEM_TRANSPARENCIA.test(caminho)) {
        cheia = true;
      }
    }
    if (cheia === null) cheia = caixa.classList.contains("foto-cheia");
    if (cheia && outroFormato(caixa, proporcao)) {
      const recorte = enquadrada(url, caixa);
      return { src: recorte || url, cheia: true, enquadrada: true };
    }
    return { src: url, cheia, enquadrada: false };
  };

  /** As classes da caixa para a foto que ela mostra (o que `marcar` faz no cartão). */
  const vestirCaixa = (caixa, pronta) => {
    caixa.classList.toggle("foto-cheia", Boolean(pronta.cheia));
    caixa.classList.toggle("foto-enquadrada", Boolean(pronta.cheia && pronta.enquadrada));
  };

  // para o ls-giro.js: as mesmas caixas, a mesma foto, as mesmas regras (sem duplicar)
  window.LSFotos = { CARTOES, fotoDa, preparar, vestirCaixa };

  const decidir = (caixa) => {
    if (decididos.has(caixa)) return;
    decididos.add(caixa);
    const foto = fotoDa(caixa);
    if (!foto) return;
    const url = foto.getAttribute("src") || "";
    if (!url || url.startsWith("data:") || /\.svg($|\?)/i.test(url)) return;
    const caminho = url.split("?")[0].split("#")[0];
    const memoria = lembrado(url);
    if (memoria !== null) {
      const [cheia, proporcao, borda] = memoria.split(":");
      marcar(caixa, cheia === "1", Number(proporcao) || 0, borda || "");
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
      lembrar(url, `${cheia ? 1 : 0}:${sonda.proporcao.toFixed(3)}:${sonda.borda || ""}`);
      marcar(caixa, cheia, sonda.proporcao, sonda.borda || "");
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
