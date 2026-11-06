/* ======================================================================
   AS MEDIDAS ESCRITAS NAS FOTOS (Objetos 3D > Criar objeto 3D).

   As fotos de brinquedão quase sempre trazem as medidas escritas -- a
   planta do catálogo com "Comprimento 5,30 m", "Largura 2,65 m", "Altura
   4,35 m", a cota de lado, o "5,30 x 2,65 x 4,35 m" da legenda. Aqui o
   navegador LÊ a foto (OCR: o Tesseract, que roda no próprio navegador,
   sem mandar a foto a ninguém -- core/static/vendor/tesseract/), acha as
   medidas, e a janela preenche só o que está vazio. Só pergunta o que
   faltar.

   Também CONFERE a foto: pequena demais, escura, borrada ou com o fundo
   bagunçado (o recorte erra) -- cada problema vira um aviso na vista.

   Uso: LSMedidasNasFotos.ler(arquivoOuUrl) -> { texto, medidas, achados }
        LSMedidasNasFotos.interpretar(texto) -> { largura, profundidade, altura, achados }
        LSMedidasNasFotos.conferir(arquivoOuUrl) -> [avisos]
   A pasta do Tesseract vem do atributo data-ocr do elemento que chama.
   ====================================================================== */
(function () {
  "use strict";

  /* ---------------------------------------------------------------- ler o texto das medidas */
  var NUMERO = "(\\d{1,4}(?:[.,]\\d{1,3})?)";
  var UNIDADE = "(m(?:ts?|etros?)?|cm|mm)?";
  // "Comprimento: 5,30 m", "Larg. 2.65m", "ALTURA 4,35 MT", "Prof 3 m", "Ø 2,40"
  var ROTULADA = new RegExp("(comp(?:rimento)?|larg(?:ura)?|alt(?:ura)?|prof(?:undidade)?|di[aâ]m(?:etro)?|[øØ])\\.?\\s*(?:total)?\\s*[:=\\-]?\\s*" + NUMERO + "\\s*" + UNIDADE + "(?![\\w])", "gi");
  // "5,30 x 2,65 x 4,35 m" (comprimento x largura x altura) e "5 x 2 m"
  var TRIO = new RegExp(NUMERO + "\\s*" + UNIDADE + "\\s*[x×X\\*]\\s*" + NUMERO + "\\s*" + UNIDADE + "\\s*[x×X\\*]\\s*" + NUMERO + "\\s*" + UNIDADE, "g");
  var PAR = new RegExp(NUMERO + "\\s*" + UNIDADE + "\\s*[x×X\\*]\\s*" + NUMERO + "\\s*" + UNIDADE + "(?![\\d.,]*\\s*[x×X])", "g");

  function metros(numero, unidade) {
    var v = parseFloat(String(numero).replace(",", "."));
    if (!(v > 0)) return null;
    var u = String(unidade || "").toLowerCase();
    if (u === "cm") v /= 100;
    else if (u === "mm") v /= 1000;
    else if (!u) {
      // sem unidade: 265 é centímetro, 2650 é milímetro; 2,65 é metro
      if (v >= 1000) v /= 1000;
      else if (v > 40) v /= 100;
    }
    // um brinquedo vai de 20 cm a 40 m: fora disso é outra coisa (preço, ano, telefone)
    return v >= 0.2 && v <= 40 ? Math.round(v * 100) / 100 : null;
  }
  function limparTexto(texto) {
    return String(texto || "")
      // o OCR troca letras por números e vice-versa nas cotas
      .replace(/(\d)\s*[oO](?=\d)/g, "$10").replace(/(\d)\s*[lI|](?=\d)/g, "$11")
      .replace(/(\d[.,]\d?)[oO](?=\s*m|\b)/g, "$10")
      .replace(/(\d)\s+([.,])\s*(\d)/g, "$1$2$3").replace(/(\d)([.,])\s+(\d)/g, "$1$2$3")
      .replace(/m\s*t\s*s?\b/gi, "mt").replace(/[“”"']/g, " ");
  }
  /**
   * As medidas de um texto, já nos campos da janela: a LARGURA é a frente (o "comprimento"
   * dos catálogos), a PROFUNDIDADE é o fundo (a "largura" deles, quando vem junto com o
   * comprimento) e a ALTURA é a altura.
   */
  function interpretar(texto) {
    var t = limparTexto(texto);
    var achou = { comprimento: [], largura: [], altura: [], profundidade: [], diametro: [] };
    var achados = [];
    var m;
    ROTULADA.lastIndex = 0;
    while ((m = ROTULADA.exec(t))) {
      var r = m[1].toLowerCase();
      var chave = r[0] === "c" ? "comprimento" : r[0] === "l" ? "largura" : r[0] === "a" ? "altura" : r[0] === "p" ? "profundidade" : "diametro";
      var v = metros(m[2], m[3]);
      if (v) { achou[chave].push(v); achados.push({ rotulo: chave, valor: v, trecho: m[0].trim() }); }
    }
    // "5 x 2 x 3 m" só vale quando as cotas não vieram com nome (senão é outra peça da foto)
    var rotuladas = achados.length;
    var trio = null;
    TRIO.lastIndex = 0;
    if (rotuladas < 2 && (m = TRIO.exec(t))) {
      var u = m[6] || m[4] || m[2];
      var a = metros(m[1], m[2] || u), b = metros(m[3], m[4] || u), c = metros(m[5], u);
      if (a && b && c) { trio = [a, b, c]; achados.push({ rotulo: "c × l × a", valor: trio, trecho: m[0].trim() }); }
    }
    var par = null;
    if (!trio && !rotuladas) {
      PAR.lastIndex = 0;
      if ((m = PAR.exec(t))) {
        var u2 = m[4] || m[2];
        var p1 = metros(m[1], m[2] || u2), p2 = metros(m[3], u2);
        if (p1 && p2) { par = [p1, p2]; achados.push({ rotulo: "c × l", valor: par, trecho: m[0].trim() }); }
      }
    }
    // a maior de cada (a cota total ganha das cotas de pedaços)
    var maior = function (lista) { return lista.length ? Math.max.apply(null, lista) : null; };
    var saida = { largura: null, profundidade: null, altura: null, achados: achados };
    var comp = maior(achou.comprimento), larg = maior(achou.largura), diam = maior(achou.diametro);
    if (comp) { saida.largura = comp; saida.profundidade = larg || maior(achou.profundidade); }
    else { saida.largura = larg; saida.profundidade = maior(achou.profundidade); }
    saida.altura = maior(achou.altura);
    if (diam) { saida.largura = saida.largura || diam; saida.profundidade = saida.profundidade || diam; }
    if (trio) {
      saida.largura = saida.largura || trio[0];
      saida.profundidade = saida.profundidade || trio[1];
      saida.altura = saida.altura || trio[2];
    } else if (par) {
      saida.largura = saida.largura || Math.max(par[0], par[1]);
      saida.profundidade = saida.profundidade || Math.min(par[0], par[1]);
    }
    return saida;
  }

  /* ---------------------------------------------------------------- abrir a foto num canvas */
  function abrirImagem(fonte) {
    return new Promise(function (ok, falhou) {
      var img = new Image();
      var url = fonte;
      var temporario = false;
      if (typeof fonte !== "string") { url = URL.createObjectURL(fonte); temporario = true; }
      else img.crossOrigin = "anonymous"; // as fotos do projeto vêm do armazenamento (com CORS)
      img.onload = function () { if (temporario) URL.revokeObjectURL(url); ok(img); };
      img.onerror = function () { if (temporario) URL.revokeObjectURL(url); falhou(new Error("a foto não abriu")); };
      img.src = url;
    });
  }
  function desenhar(img, maximo, giro) {
    var escala = Math.min(1, maximo / Math.max(img.naturalWidth, img.naturalHeight));
    var w = Math.max(1, Math.round(img.naturalWidth * escala)), h = Math.max(1, Math.round(img.naturalHeight * escala));
    var tela = document.createElement("canvas");
    var deitada = giro === 90 || giro === 270;
    tela.width = deitada ? h : w;
    tela.height = deitada ? w : h;
    var g = tela.getContext("2d", { willReadFrequently: true });
    g.fillStyle = "#fff";
    g.fillRect(0, 0, tela.width, tela.height);
    g.translate(tela.width / 2, tela.height / 2);
    g.rotate((giro || 0) * Math.PI / 180);
    g.drawImage(img, -w / 2, -h / 2, w, h);
    return tela;
  }

  /* ---------------------------------------------------------------- o OCR (Tesseract, no navegador) */
  var pasta = "";
  function pastaDoTesseract() {
    if (pasta) return pasta;
    var el = document.querySelector("[data-ocr]");
    pasta = el ? el.getAttribute("data-ocr") : "";
    return pasta;
  }
  var carregando = null;
  function carregarTesseract() {
    if (window.Tesseract) return Promise.resolve(window.Tesseract);
    if (carregando) return carregando;
    carregando = new Promise(function (ok, falhou) {
      var s = document.createElement("script");
      s.src = pastaDoTesseract() + "tesseract.min.js";
      s.onload = function () { ok(window.Tesseract); };
      s.onerror = function () { carregando = null; falhou(new Error("o leitor de texto não carregou")); };
      document.head.appendChild(s);
    });
    return carregando;
  }
  var trabalhador = null;
  function oTrabalhador() {
    if (trabalhador) return trabalhador;
    trabalhador = carregarTesseract().then(function (T) {
      var p = pastaDoTesseract();
      return T.createWorker("eng", 1, {
        workerPath: p + "worker.min.js",
        corePath: p + "tesseract-core-simd-lstm.wasm.js",
        langPath: p.replace(/\/$/, ""),
        gzip: true,
        workerBlobURL: false,
      });
    }).then(function (w) {
      // só o que aparece em cotas: letras, números, vírgula, ponto, x, dois-pontos
      return w.setParameters({ preserve_interword_spaces: "1" }).then(function () { return w; });
    });
    trabalhador.catch(function () { trabalhador = null; });
    return trabalhador;
  }
  // uma foto por vez (o leitor é um só)
  var fila = Promise.resolve();
  function naFila(tarefa) {
    var vez = fila.then(tarefa, tarefa);
    fila = vez.catch(function () {});
    return vez;
  }
  function contar(m) { return (m.largura ? 1 : 0) + (m.profundidade ? 1 : 0) + (m.altura ? 1 : 0); }
  /**
   * Lê a foto: de pé; se achar menos de 3 medidas, também deitada para os dois lados (as
   * cotas de lado nas plantas vêm escritas na vertical).
   */
  function ler(fonte) {
    return naFila(function () {
      return Promise.all([abrirImagem(fonte), oTrabalhador()]).then(function (r) {
        var img = r[0], w = r[1];
        var textos = [];
        var tentativas = [0, 270, 90];
        var i = 0;
        function proxima() {
          if (i >= tentativas.length) return null;
          var giro = tentativas[i++];
          return w.recognize(desenhar(img, 2000, giro)).then(function (res) {
            textos.push(res.data.text || "");
            var juntas = interpretar(textos.join("\n"));
            return contar(juntas) >= 3 ? null : proxima();
          });
        }
        return Promise.resolve(proxima()).then(function () {
          var texto = textos.join("\n");
          var medidas = interpretar(texto);
          return { texto: texto, medidas: medidas, achados: medidas.achados };
        });
      });
    });
  }

  /* ---------------------------------------------------------------- conferir a foto */
  /**
   * O que pode atrapalhar o recorte e o contorno: foto pequena, escura, borrada ou com o
   * fundo bagunçado (a borda da foto é que diz se o fundo é liso).
   */
  function conferir(fonte) {
    return abrirImagem(fonte).then(function (img) {
      var avisos = [];
      var menor = Math.min(img.naturalWidth, img.naturalHeight);
      if (menor < 480) avisos.push("foto pequena (" + img.naturalWidth + " × " + img.naturalHeight + "): o contorno sai serrilhado; use uma de 1000 px ou mais");
      var tela = desenhar(img, 256, 0);
      var g = tela.getContext("2d", { willReadFrequently: true });
      var d = g.getImageData(0, 0, tela.width, tela.height).data;
      var W = tela.width, H = tela.height;
      var cinza = new Float32Array(W * H);
      var soma = 0;
      for (var k = 0, j = 0; k < d.length; k += 4, j++) { cinza[j] = 0.299 * d[k] + 0.587 * d[k + 1] + 0.114 * d[k + 2]; soma += cinza[j]; }
      var media = soma / (W * H);
      if (media < 55) avisos.push("foto escura: o recorte confunde o brinquedo com o fundo");
      // borrada: pouca variação nas bordas (laplaciano)
      var lap = 0, n = 0;
      for (var y = 1; y < H - 1; y++) {
        for (var x = 1; x < W - 1; x++) {
          var c = y * W + x;
          var v = 4 * cinza[c] - cinza[c - 1] - cinza[c + 1] - cinza[c - W] - cinza[c + W];
          lap += v * v; n++;
        }
      }
      if (n && lap / n < 40) avisos.push("foto borrada ou sem foco: o contorno sai mole");
      // o fundo: a borda da foto deve ser parecida (parede lisa, céu, fundo branco)
      var borda = [];
      for (var bx = 0; bx < W; bx++) { borda.push(cinza[bx], cinza[(H - 1) * W + bx]); }
      for (var by = 0; by < H; by++) { borda.push(cinza[by * W], cinza[by * W + W - 1]); }
      var mb = borda.reduce(function (a, b) { return a + b; }, 0) / borda.length;
      var desvio = Math.sqrt(borda.reduce(function (a, b) { return a + (b - mb) * (b - mb); }, 0) / borda.length);
      if (desvio > 48) avisos.push("o fundo não é liso: o recorte pode levar pedaços do fundo (desligue \"Recortar o fundo\" se a foto já vier recortada)");
      return avisos;
    });
  }

  window.LSMedidasNasFotos = { ler: ler, interpretar: interpretar, conferir: conferir };
})();
