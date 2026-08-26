"""O que faz o painel virar aplicativo instalado no tablet.

POR QUE NÃO SÃO ARQUIVOS ESTÁTICOS. Os dois precisam responder na RAIZ do
subdomínio interno:

* o **manifesto** guarda `start_url` e `scope`, e o navegador resolve os
  dois em relação ao endereço dele -- servido de /static/ o aplicativo
  abriria dentro da pasta de estáticos;
* o **service worker** só controla o que está abaixo do caminho em que ele
  mesmo é servido. Em /static/interno/sw.js ele não controlaria nada, e o
  navegador não considera o painel instalável.

O service worker aqui é deliberadamente burro: ele repassa tudo para a
rede. Guardar resposta em cache num painel de operação daria tela velha
com número velho -- que é pior do que uma tela que não abre, porque o
usuário não percebe.
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

Repassa tudo para a rede, de propósito: painel de operação com resposta
guardada em cache mostra número velho sem avisar, e ninguém confere um
dado que a tela apresenta como atual.

Ele existe para o navegador considerar o painel instalável -- e para que
um dia, se for preciso, haja onde colocar uma fila de envio offline.
*/
self.addEventListener("install", function () {
  self.skipWaiting();
});

self.addEventListener("activate", function (evento) {
  evento.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", function (evento) {
  evento.respondWith(fetch(evento.request));
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
