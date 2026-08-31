"""O que faz o painel virar aplicativo instalado no tablet.

POR QUE NÃO SÃO ARQUIVOS ESTÁTICOS. Os dois precisam responder na RAIZ do
subdomínio interno:

* o **manifesto** guarda `start_url` e `scope`, e o navegador resolve os
  dois em relação ao endereço dele -- servido de /static/ o aplicativo
  abriria dentro da pasta de estáticos;
* o **service worker** só controla o que está abaixo do caminho em que ele
  mesmo é servido. Em /static/interno/sw.js ele não controlaria nada, e o
  navegador não considera o painel instalável.

O service worker nunca guarda páginas nem respostas operacionais. Somente
arquivos sob /static/ entram no cache local do aparelho; assim CSS, ícones e
JavaScript não gastam banda repetidamente, mas números e cadastros continuam
sempre vindo da rede.
"""

from django.http import HttpResponse, JsonResponse
from django.templatetags.static import static
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET


NOME = "Lazer & Sport · Gestão"


@require_GET
def manifesto(request):
    """Manifesto do aplicativo interno."""
    return JsonResponse(
        {
            "name": NOME,
            "short_name": "L&S Gestão",
            "description": (
                "Bancada de trabalho da Lazer & Sport: orçamentos, "
                "produção, estoque, clientes e manutenção."
            ),
            "lang": "pt-BR",
            "dir": "ltr",
            "start_url": "/",
            "scope": "/",
            # standalone: abre sem a barra do navegador. É o que faz o
            # tablet da fábrica parecer um aplicativo, e não um site.
            "display": "standalone",
            "orientation": "any",
            "background_color": "#13100B",
            "theme_color": "#13100B",
            "categories": ["business", "productivity"],
            "icons": [
                {
                    "src": static("interno/app-icone-192.png"),
                    "sizes": "192x192",
                    "type": "image/png",
                    "purpose": "any",
                },
                {
                    "src": static("interno/app-icone-512.png"),
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "any",
                },
                {
                    "src": static("interno/app-icone-mascara.png"),
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "maskable",
                },
            ],
            "shortcuts": [
                {
                    "name": "Novo orçamento",
                    "url": "/orcamentos/?novo=1",
                },
                {"name": "Clientes", "url": "/clientes/"},
                {"name": "Produção", "url": "/producao/"},
            ],
        },
        content_type="application/manifest+json",
    )


SERVICE_WORKER = """/* Service worker do painel interno.

Páginas e APIs são sempre da rede. Somente /static/ usa cache local: são
CSS, JavaScript, fontes e ícones versionados, nunca orçamento, estoque ou
cadastro. Isso poupa banda sem apresentar dado operacional antigo.
*/
var CACHE_ESTATICO = "ls-static-v2";

self.addEventListener("install", function () {
  self.skipWaiting();
});

self.addEventListener("activate", function (evento) {
  evento.waitUntil(
    caches.keys().then(function (chaves) {
      return Promise.all(chaves.map(function (chave) {
        if (chave.indexOf("ls-static-") === 0 && chave !== CACHE_ESTATICO) {
          return caches.delete(chave);
        }
      }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener("fetch", function (evento) {
  var pedido = evento.request;
  if (pedido.method !== "GET") return;

  var url = new URL(pedido.url);
  if (url.origin !== self.location.origin || url.pathname.indexOf("/static/") !== 0) {
    return;
  }

  function buscarEGuardar() {
    return fetch(pedido).then(function (resposta) {
      if (resposta.ok) {
        var copia = resposta.clone();
        caches.open(CACHE_ESTATICO).then(function (cache) {
          cache.put(pedido, copia);
        });
      }
      return resposta;
    });
  }

  evento.respondWith(
    caches.match(pedido).then(function (guardado) {
      if (!guardado) return buscarEGuardar();
      evento.waitUntil(buscarEGuardar().catch(function () {}));
      return guardado;
    })
  );
});

/* ----------------------------------------------------------------------
   AVISO NO CELULAR

   Quem está na estrada montando um brinquedo não tem o painel aberto.
   Para essa pessoa o aviso só existe se o telefone tocar -- e é o caso do
   orçamento que o cliente acabou de aprovar, que precisa virar agenda
   antes de a data ser vendida de novo.

   O corpo chega CIFRADO de ponta a ponta: o serviço do fabricante
   (Google no Android, Apple no iPhone) entrega, mas não lê.
   ---------------------------------------------------------------------- */
self.addEventListener("push", function (evento) {
  var dados = {};
  try { dados = evento.data ? evento.data.json() : {}; } catch (e) {}

  var titulo = dados.titulo || "Lazer & Sport · Gestão";
  var opcoes = {
    body: dados.corpo || "",
    icon: dados.icone || "/static/interno/app-icone-192.png",
    badge: "/static/interno/app-icone-192.png",
    data: { url: dados.url || "/" },
    /* A marca substitui o aviso anterior do MESMO assunto em vez de
       empilhar. Três notificações da proposta 412 na tela de bloqueio
       fazem a pessoa limpar todas sem ler nenhuma. */
    tag: dados.marca || "lazersport",
    renotify: !!dados.urgente,
    /* Vibra só o que é decisão do cliente. Uma vibração para cada coisa
       que acontece no dia treina a pessoa a ignorar todas. */
    vibrate: dados.urgente ? [80, 40, 80] : undefined,
  };

  evento.waitUntil(self.registration.showNotification(titulo, opcoes));
});

self.addEventListener("notificationclick", function (evento) {
  evento.notification.close();
  var destino = (evento.notification.data && evento.notification.data.url) || "/";

  /* Se o painel já está aberto em alguma aba, é ela que vai para o
     assunto -- abrir uma segunda aba do mesmo painel a cada aviso
     acabaria com dez abas iguais no fim do dia. */
  evento.waitUntil(
    self.clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then(function (abas) {
        for (var i = 0; i < abas.length; i += 1) {
          if ("focus" in abas[i]) {
            if ("navigate" in abas[i]) abas[i].navigate(destino);
            return abas[i].focus();
          }
        }
        return self.clients.openWindow(destino);
      })
  );
});
"""


@require_GET
@cache_control(max_age=0, no_cache=True)
def service_worker(request):
    """Servido da raiz: é o único lugar de onde ele controla o painel."""
    return HttpResponse(
        SERVICE_WORKER,
        content_type="application/javascript",
    )
