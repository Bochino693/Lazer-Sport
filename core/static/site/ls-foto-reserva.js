/* A RESERVA DAS FOTOS (LEIA-ME-V10, seção 128; ver core/fotos_reserva.py).
 *
 * Quando uma foto do Cloudinary não chega (a conta fora do ar devolve 401),
 * a foto não fica quebrada: se a cópia dela existe no próprio site (capa do
 * showroom, capa do objeto 3D, arte do kit, foto da categoria, arte da Black
 * Friday), entra a cópia; se não existe, entra um quadro "Foto em
 * atualização" no lugar do ícone quebrado. Enquanto o Cloudinary entrega,
 * este arquivo não faz nada: só age no erro de uma foto do Cloudinary.
 */
(function () {
  'use strict';
  if (window.__lsFotoReserva) return;
  window.__lsFotoReserva = true;

  var script = document.currentScript;
  var URL_DO_INDICE = (script && script.getAttribute('data-indice')) || '/static/site/fotos-reserva.json';
  var indice = null;
  var pedido = null;
  var fila = [];
  var foraDoAr = false;

  var VAZIA = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300" preserveAspectRatio="xMidYMid slice">' +
    '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">' +
    '<stop offset="0" stop-color="#16244a"/><stop offset="1" stop-color="#0b1330"/></linearGradient></defs>' +
    '<rect width="400" height="300" fill="url(#g)"/>' +
    '<g fill="none" stroke="#7f9cff" stroke-opacity=".55" stroke-width="6" stroke-linejoin="round">' +
    '<rect x="160" y="105" width="80" height="62" rx="10"/>' +
    '<path d="M168 159l20-22 16 15 12-11 16 18"/></g>' +
    '<circle cx="219" cy="122" r="7" fill="#7f9cff" fill-opacity=".55"/>' +
    '<text x="200" y="200" text-anchor="middle" font-family="system-ui,Segoe UI,Arial,sans-serif" ' +
    'font-size="17" font-weight="700" fill="#c9d6ff" fill-opacity=".8">Foto em atualização</text></svg>'
  );

  function eDoCloudinary(url) {
    return typeof url === 'string' && url.indexOf('res.cloudinary.com/') !== -1;
  }

  // ".../upload/c_limit,w_720,f_auto,q_auto/v1/imagens_brinquedos/galeria/cena-air-game-home-10bb33e058_ik4fg5"
  //   -> {pasta: "imagens_brinquedos/galeria", nome: "cena-air-game-home"}
  function nomeDaFoto(url) {
    var limpa = url.split('#')[0].split('?')[0];
    var depois = limpa.split('/upload/')[1] || limpa;
    var partes = depois.split('/').filter(function (p) {
      return p && !/^v\d+$/.test(p) && !/^[a-z]{1,3}_[^,\/]+(,[a-z]{1,3}_[^,\/]+)*$/.test(p);
    });
    var nome = (partes.pop() || '');
    try { nome = decodeURIComponent(nome); } catch (e) { /* segue como veio */ }
    nome = nome.toLowerCase().replace(/\.[a-z0-9]{2,5}$/, '')
      .replace(/_[a-z0-9]{6}$/, '')          // o sufixo que o Cloudinary sorteia
      .replace(/-[0-9a-f]{8,12}(?=-|$)/g, '') // a assinatura do arquivo
      .replace(/_/g, '-');
    return { pasta: partes.join('/').toLowerCase(), nome: nome };
  }

  function maisLonga(grupo, nome) {
    var melhor = '';
    if (!grupo) return '';
    Object.keys(grupo).forEach(function (chave) {
      if (chave.length > melhor.length && nome.indexOf(chave) !== -1) melhor = chave;
    });
    return melhor ? grupo[melhor] : '';
  }

  function copiaLocal(url) {
    if (!indice) return '';
    var foto = nomeDaFoto(url);
    if (foto.pasta.indexOf('categorias') !== -1) {
      return maisLonga(indice.categorias, foto.nome);
    }
    if (foto.nome.indexOf('black-friday') !== -1) {
      var arte = foto.nome.match(/(arte|card)-\d{2}/);
      if (arte && indice.black_friday && indice.black_friday[arte[0]]) return indice.black_friday[arte[0]];
    }
    return maisLonga(indice.produtos, foto.nome);
  }

  function semFontesAlternativas(img) {
    var pai = img.parentElement;
    if (pai && pai.tagName === 'PICTURE') {
      Array.prototype.slice.call(pai.querySelectorAll('source')).forEach(function (s) { s.remove(); });
    }
    img.removeAttribute('srcset');
    img.removeAttribute('sizes');
  }

  function trocar(img, urlQueFalhou) {
    var local = copiaLocal(urlQueFalhou);
    semFontesAlternativas(img);
    if (local) {
      img.setAttribute('data-ls-reserva', 'copia');
      img.classList.remove('ls-foto-reserva-vazia');
      img.src = local;
    } else {
      img.setAttribute('data-ls-reserva', 'vazia');
      img.classList.add('ls-foto-reserva-vazia');
      img.src = VAZIA;
    }
  }

  function carregarIndice() {
    if (pedido) return pedido;
    pedido = fetch(URL_DO_INDICE, { credentials: 'same-origin' })
      .then(function (r) { return r.ok ? r.json() : {}; })
      .catch(function () { return {}; })
      .then(function (dados) {
        indice = dados || {};
        var esperando = fila;
        fila = [];
        esperando.forEach(function (par) { trocar(par[0], par[1]); });
        trocarFundos();
      });
    return pedido;
  }

  function falhou(img) {
    var url = img.currentSrc || img.getAttribute('src') || '';
    if (!eDoCloudinary(url)) return;
    foraDoAr = true;
    if (indice) { trocar(img, url); return; }
    fila.push([img, url]);
    carregarIndice();
  }

  // Fundos em CSS escritos no próprio elemento (style="background-image:url(...cloudinary...)").
  function trocarFundos() {
    if (!foraDoAr || !indice) return;
    var comFundo = document.querySelectorAll('[style*="res.cloudinary.com"]');
    Array.prototype.forEach.call(comFundo, function (el) {
      var estilo = el.getAttribute('style') || '';
      var achado = estilo.match(/url\((['"]?)(https?:\/\/res\.cloudinary\.com\/[^'")]+)\1\)/);
      if (!achado) return;
      var local = copiaLocal(achado[2]);
      el.style.backgroundImage = local ? 'url("' + local + '")' : 'url("' + VAZIA + '")';
      el.setAttribute('data-ls-reserva', local ? 'copia' : 'vazia');
    });
  }

  // O erro de <img> não sobe na árvore: a escuta na captura pega todos,
  // inclusive as fotos que o carrossel dos cards troca depois.
  document.addEventListener('error', function (evento) {
    var alvo = evento.target;
    if (alvo && alvo.tagName === 'IMG') falhou(alvo);
  }, true);

  // As que já falharam antes deste arquivo chegar.
  function conferirAsQueJaFalharam() {
    Array.prototype.forEach.call(document.images, function (img) {
      var url = img.currentSrc || img.getAttribute('src') || '';
      if (eDoCloudinary(url) && img.complete && img.naturalWidth === 0) falhou(img);
    });
  }
  conferirAsQueJaFalharam();
  window.addEventListener('load', conferirAsQueJaFalharam);
})();
