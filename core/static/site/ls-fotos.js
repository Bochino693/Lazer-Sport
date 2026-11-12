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

   NUNCA COM ZOOM. O cliente, com o print do card do Air Rock (a foto
   panorâmica, 2 x 1, recortada no quadrado: a máquina de perto, cortada):
   "valide para não ter fotos assim com zoom pois estraga" e, depois, "ainda
   com zoom". O recorte que enche a caixa só vale enquanto a diferença de
   formato é pequena (até 1,4 x). A foto MUITO mais larga ou mais alta que a
   caixa fica INTEIRA ("contain"): no máximo as beiradas são aparadas (~10%
   da foto, nunca a máquina), e o resto da caixa é a cor da beirada da
   própria foto (`foto-inteira`, como a arte do quadro do topo). A foto
   certa para o card é a quadrada (as capas em cena, 1600 x 1600).

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
  const MEMORIA = "ls-foto-cheia4:";
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
        const media = (lista) => {
          let rr = 0, g2 = 0, bb = 0;
          lista.forEach(([x, y]) => { const i = (y * w + x) * 4; rr += alfa[i]; g2 += alfa[i + 1]; bb += alfa[i + 2]; });
          return lista.length ? [rr, g2, bb].map((v) => Math.round(v / lista.length)).join(",") : "";
        };
        const linha = (y) => Array.from({ length: w }, (_, x) => [x, y]);
        const coluna = (x) => Array.from({ length: h }, (_, y) => [x, y]);
        // a borda inteira e cada beirada (em cima, embaixo, esquerda, direita), separadas
        // por ";": a foto inteira continua na cor da beirada do lado de cada faixa
        const borda = n ? [
          [r, gg, b].map((v) => Math.round(v / n)).join(","),
          media(linha(0)), media(linha(h - 1)), media(coluna(0)), media(coluna(w - 1)),
        ].join(";") : "";
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

  // a foto que o recorte deixaria com zoom (perderia mais de ~30% de um lado):
  // essa fica inteira, sem recorte
  const ZOOM_MAXIMO = Math.log(1.4);
  const zoomDemais = (caixa, proporcao) => {
    const w = caixa.clientWidth, h = caixa.clientHeight;
    return Boolean(proporcao && w && h) && Math.abs(Math.log(proporcao / (w / h))) > ZOOM_MAXIMO;
  };

  // a caixa que mostra a foto inteira: o resto dela é a cor da beirada da foto do
  // lado de cada faixa (a de cima em cima, a de baixo embaixo), e a foto parece continuar
  const pintarFundo = (caixa, borda, proporcao) => {
    if (!borda) return;
    const [toda, cima, baixo, esquerda, direita] = borda.split(";");
    caixa.style.setProperty("--foto-borda", `rgb(${toda})`);
    const w = caixa.clientWidth, h = caixa.clientHeight;
    const deitada = !(proporcao && w && h) || proporcao >= w / h;
    const [a, b2] = deitada ? [cima, baixo] : [esquerda, direita];
    if (a && b2) {
      caixa.style.setProperty("--foto-faixas",
        `linear-gradient(${deitada ? 180 : 90}deg, rgb(${a}) 0%, rgb(${a}) 34%, rgb(${b2}) 66%, rgb(${b2}) 100%)`);
    }
  };

  const deixarInteira = (caixa, borda, proporcao) => {
    caixa.classList.add("foto-inteira");
    caixa.classList.remove("foto-enquadrada");
    pintarFundo(caixa, borda, proporcao);
  };

  // A foto de formato muito diferente fica praticamente inteira: o recorte só
  // apara as beiradas (some no máximo ~10% da foto, pelo conteúdo) -- nunca a
  // máquina cortada ou de perto (o Air Rock panorâmico no card quadrado). O resto
  // da caixa são as faixas na cor da beirada da foto.
  const APARA_NO_MAXIMO = 1.12;
  const recorteLimitado = (url, caixa, proporcao) => {
    const partes = url.match(/^(.*\/upload\/)(?:[a-z]_[^/]*\/)?(.*)$/);
    if (!url.includes("res.cloudinary.com") || !partes || !proporcao) return "";
    const w = caixa.clientWidth, h = caixa.clientHeight;
    if (!w || !h) return "";
    const daCaixa = w / h;
    // o formato do recorte parte da FOTO (e não da caixa): no máximo ~10% a menos dela
    const alvo = proporcao > daCaixa
      ? Math.max(daCaixa, proporcao / APARA_NO_MAXIMO)
      : Math.min(daCaixa, proporcao * APARA_NO_MAXIMO);
    const formato = Math.min(3, Math.max(0.4, Math.round(alvo * 100) / 100));
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const largura = Math.min(1600, Math.max(400, Math.ceil((w * dpr) / 200) * 200));
    return { src: `${partes[1]}c_fill,g_auto,ar_${formato},w_${largura},q_auto,f_auto/${partes[2]}`, formato };
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
    const formato = proporcao || (foto.naturalWidth / foto.naturalHeight);
    if (caixa.hasAttribute("data-foto-inteira")) {
      deixarInteira(caixa, borda, formato);
      return;
    }
    if (zoomDemais(caixa, formato)) {
      const limitado = recorteLimitado(foto.getAttribute("src") || "", caixa, formato);
      deixarInteira(caixa, borda, limitado ? limitado.formato : formato);
      if (limitado) {
        const original = foto.getAttribute("src") || "";
        foto.addEventListener("error", () => {
          if (foto.getAttribute("src") === limitado.src) foto.setAttribute("src", original);
        }, { once: true });
        foto.removeAttribute("srcset");
        foto.removeAttribute("sizes");
        foto.setAttribute("src", limitado.src);
      }
      return;
    }
    if (!outroFormato(caixa, formato)) return;
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
   * recorte no formato da caixa pelo conteúdo (o `src` já é o recorte);
   * `inteira`: a foto de formato muito diferente, sem recorte (sem zoom),
   * com a cor da borda dela (`borda`) no resto da caixa.
   */
  const preparar = async (url, caixa) => {
    const caminho = url.split("?")[0].split("#")[0];
    let cheia = null;
    let proporcao = 0;
    let borda = "";
    const memoria = lembrado(url);
    if (memoria !== null) {
      const [c, p, b] = memoria.split(":");
      cheia = c === "1";
      proporcao = Number(p) || 0;
      borda = b || "";
    } else {
      const sonda = await sondar(url);
      if (sonda) {
        cheia = SEM_TRANSPARENCIA.test(caminho) ? true : sonda.cheia;
        proporcao = sonda.proporcao || 0;
        borda = sonda.borda || "";
        if (cheia !== null) lembrar(url, `${cheia ? 1 : 0}:${proporcao.toFixed(3)}:${sonda.borda || ""}`);
      } else if (SEM_TRANSPARENCIA.test(caminho)) {
        cheia = true;
      }
    }
    if (cheia === null) cheia = caixa.classList.contains("foto-cheia");
    if (cheia && caixa.hasAttribute("data-foto-inteira")) {
      return { src: url, cheia: true, enquadrada: false, inteira: true, borda, formato: proporcao };
    }
    if (cheia && zoomDemais(caixa, proporcao)) {
      const limitado = recorteLimitado(url, caixa, proporcao);
      return {
        src: limitado ? limitado.src : url, cheia: true, enquadrada: false, inteira: true, borda,
        formato: limitado ? limitado.formato : proporcao,
      };
    }
    if (cheia && outroFormato(caixa, proporcao)) {
      const recorte = enquadrada(url, caixa);
      return { src: recorte || url, cheia: true, enquadrada: true, inteira: false, borda };
    }
    return { src: url, cheia, enquadrada: false, inteira: false, borda };
  };

  /** As classes da caixa para a foto que ela mostra (o que `marcar` faz no cartão). */
  const vestirCaixa = (caixa, pronta) => {
    caixa.classList.toggle("foto-cheia", Boolean(pronta.cheia));
    caixa.classList.toggle("foto-enquadrada", Boolean(pronta.cheia && pronta.enquadrada));
    caixa.classList.toggle("foto-inteira", Boolean(pronta.cheia && pronta.inteira));
    if (pronta.inteira) pintarFundo(caixa, pronta.borda, pronta.formato);
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
