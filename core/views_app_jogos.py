"""O APP LAZER & SPORT GAMES: o manifesto (instalar na tela de início) e o service
worker que faz o launcher (/jogos/) abrir sem internet.

POR QUE UM SERVICE WORKER SÓ PARA /jogos/ (E NÃO O DO SITE, /app-sw.js).
O do site não guarda nada de propósito: na loja, página velha é preço velho
(ver core/views_app_avisos.py). Nos jogos é o contrário: quem abre o app no
ônibus, sem sinal, quer a biblioteca e os jogos que já jogou. Este cuida só do
que está abaixo de /jogos/ -- o escopo dele --, e a loja continua sempre fresca.

O QUE ELE GUARDA
  * as páginas do app (a biblioteca, as fichas, os reprodutores dos jogos já
    abertos): rede primeiro (o que é novo aparece), e sem rede, a guardada;
  * os arquivos do site (/static/: CSS, JS, o emulador, os núcleos dos consoles,
    as capas da casa) e as capas do Cloudinary: guardados na primeira vez;
  * o núcleo que vem do pacote oficial do EmulatorJS (jsDelivr).
O QUE ELE NÃO GUARDA: os arquivos dos jogos (as ROMs e os discos) -- esses o
jogo-guardado.js já guarda no aparelho, e duas cópias gastariam o espaço do
celular à toa --, e nada que não seja GET (partida, ranking, cadastro).
"""

import hashlib
import json

from django.http import HttpResponse
from django.urls import reverse
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

from sistema_interno.templatetags.interno_extras import estatico

#: O que o app precisa para abrir sem internet já na primeira visita.
CASCA = (
    "site/paginas/portal-jogos.css",
    "site/paginas/portal-jogos.js",
    "site/paginas/app-jogos.js",
    "site/paginas/jogo-emulador.css",
    "site/paginas/jogo-emulador.js",
    "site/paginas/jogo-guardado.js",
    "site/paginas/intro-jogos.css",
    "site/paginas/intro-jogos.js",
    "images/logoofi.png",
    "images/icone/icone-192.png",
    "images/icone/icone-512.png",
)

SERVICE_WORKER = r"""/* Lazer & Sport Games -- o app sem internet. Gerado por core/views_app_jogos.py */
var VERSAO = "__VERSAO__";
var CASCA = "ls-games-casca-" + VERSAO;
var ARQUIVOS = "ls-games-arquivos-v1";
var PAGINAS = "ls-games-paginas-v1";
var INICIO = "__INICIO__";
var LISTA_DA_CASCA = __LISTA__;
var MAX_ARQUIVOS = 600;

var SEM_REDE = '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">' +
  '<meta name="viewport" content="width=device-width, initial-scale=1"><title>Sem internet</title>' +
  '<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#04070f;color:#eef3ff;' +
  'font:16px system-ui,sans-serif;text-align:center;padding:24px}a{color:#fff;background:#ff3d57;padding:12px 22px;' +
  'border-radius:999px;text-decoration:none;font-weight:800;display:inline-block;margin-top:14px}</style></head>' +
  '<body><div><h1>Sem internet</h1><p>Esta página ainda não estava guardada no aparelho.<br>' +
  'Os jogos que você já abriu continuam na biblioteca.</p><a href="' + INICIO + '">Abrir a biblioteca</a></div></body></html>';

self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(CASCA).then(function (c) {
    // um arquivo que falhar não derruba o resto
    return Promise.all(LISTA_DA_CASCA.map(function (u) { return c.add(new Request(u, { credentials: "same-origin" })).catch(function () {}); }));
  }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (nomes) {
    return Promise.all(nomes.filter(function (n) { return n.indexOf("ls-games-casca-") === 0 && n !== CASCA; })
      .map(function (n) { return caches.delete(n); }));
  }).then(function () { return self.clients.claim(); }));
});

// a página avisa o que ela já baixou (o CSS do site, as capas): entra no cofre também
self.addEventListener("message", function (e) {
  var dados = e.data || {};
  if (dados.tipo !== "guardar" || !Array.isArray(dados.urls)) return;
  e.waitUntil(caches.open(ARQUIVOS).then(function (c) {
    return Promise.all(dados.urls.slice(0, 200).map(function (u) {
      var url;
      try { url = new URL(u, self.location.href); } catch (x) { return null; }
      if (!guardavel(url)) return null;
      return c.match(url.href).then(function (ja) { return ja || buscarParaGuardar(url).then(function (r) { if (r) return c.put(url.href, r); }); });
    }));
  }).catch(function () {}));
});

function guardavel(url) {
  if (url.origin === self.location.origin) return url.pathname.indexOf("/static/") === 0;
  if (url.hostname === "res.cloudinary.com") return url.pathname.indexOf("/image/upload/") !== -1;
  if (url.hostname === "cdn.jsdelivr.net") return url.pathname.indexOf("/npm/@emulatorjs/") === 0;
  if (url.hostname === "fonts.googleapis.com" || url.hostname === "fonts.gstatic.com") return true;
  return false;
}

// de outro domínio, pede com CORS: a resposta "opaca" ocuparia megabytes no cofre de cada uma
function buscarParaGuardar(url) {
  var mesma = url.origin === self.location.origin;
  return fetch(new Request(url.href, mesma ? { credentials: "same-origin" } : { mode: "cors", credentials: "omit" }))
    .then(function (r) { return r && r.ok ? r : null; }, function () { return null; });
}

var podando = false;
function podar(cache) {
  if (podando) return;
  podando = true;
  cache.keys().then(function (chaves) {
    var sobra = chaves.length - MAX_ARQUIVOS;
    return Promise.all(chaves.slice(0, Math.max(0, sobra)).map(function (k) { return cache.delete(k); }));
  }).then(function () { podando = false; }, function () { podando = false; });
}

function arquivo(req, url) {
  return caches.match(url.href).then(function (guardado) {
    if (guardado) return guardado;
    return buscarParaGuardar(url).then(function (r) {
      if (!r) return fetch(req);
      var copia = r.clone();
      caches.open(ARQUIVOS).then(function (c) { c.put(url.href, copia).then(function () { podar(c); }); });
      return r;
    });
  });
}

function pagina(req) {
  var chave = req.url.split("#")[0];
  var comTempo = new Promise(function (ok, falha) {
    var relogio = setTimeout(function () { falha(new Error("demorou")); }, 6000);
    fetch(req).then(function (r) { clearTimeout(relogio); ok(r); }, function (x) { clearTimeout(relogio); falha(x); });
  });
  return comTempo.then(function (r) {
    if (r && r.ok && r.type === "basic") {
      var copia = r.clone();
      caches.open(PAGINAS).then(function (c) { c.put(chave, copia); });
    }
    return r;
  }, function () {
    return caches.open(PAGINAS).then(function (c) {
      return c.match(chave).then(function (g) {
        return g || c.match(INICIO).then(function (i) {
          return i || caches.match(INICIO).then(function (j) {
            return j || new Response(SEM_REDE, { headers: { "Content-Type": "text/html; charset=utf-8" } });
          });
        });
      });
    });
  });
}

self.addEventListener("fetch", function (e) {
  var req = e.request;
  if (req.method !== "GET") return;
  var url;
  try { url = new URL(req.url); } catch (x) { return; }
  if (req.mode === "navigate") {
    if (url.origin === self.location.origin && url.pathname.indexOf("/jogos/") === 0) e.respondWith(pagina(req));
    return;
  }
  if (req.headers.get("range")) return; // pedaços de vídeo e afins: direto da rede
  if (guardavel(url)) e.respondWith(arquivo(req, url));
});
"""


def _versao():
    """Muda quando um arquivo da casca muda: o service worker novo entra no lugar."""
    impressao = "|".join(estatico(c) for c in CASCA)
    return hashlib.sha1(impressao.encode()).hexdigest()[:12]


@require_GET
@cache_control(no_cache=True, max_age=0)
def service_worker_dos_jogos(request):
    inicio = reverse("jogos")
    lista = [inicio] + [estatico(c) for c in CASCA]
    corpo = (SERVICE_WORKER.replace("__VERSAO__", _versao()).replace("__INICIO__", inicio)
             .replace("__LISTA__", json.dumps(lista)))
    resposta = HttpResponse(corpo, content_type="application/javascript; charset=utf-8")
    resposta["Service-Worker-Allowed"] = inicio
    return resposta


@require_GET
@cache_control(max_age=3600)
def manifesto_dos_jogos(request):
    inicio = reverse("jogos")
    manifesto = {
        "name": "Lazer & Sport Games",
        "short_name": "L&S Games",
        "description": "Os jogos da Lazer & Sport e os clássicos de console, grátis, no celular e no computador.",
        "id": inicio,
        "start_url": inicio + "?origem=app",
        "scope": inicio,
        "display": "fullscreen",
        "display_override": ["fullscreen", "standalone"],
        "orientation": "any",
        "background_color": "#04070f",
        "theme_color": "#04070f",
        "lang": "pt-BR",
        "categories": ["games", "entertainment"],
        "icons": [
            {"src": estatico("images/icone/icone-192.png"), "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
            {"src": estatico("images/icone/icone-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
        ],
    }
    return HttpResponse(json.dumps(manifesto, ensure_ascii=False), content_type="application/manifest+json; charset=utf-8")
