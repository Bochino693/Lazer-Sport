"""O service worker que faz a notificação aparecer no celular do cliente.

POR QUE ELE É UMA VIEW, E NÃO UM ARQUIVO EM /static/.

Um service worker só controla o que está ABAIXO do caminho em que ele
mesmo é servido. Publicado em `/static/site/app-sw.js`, ele controlaria
`/static/site/...` -- ou seja, nada do que interessa -- e o navegador
recusaria a inscrição de push para o site inteiro. Servido na raiz, ele
cobre a loja toda.

O QUE ELE FAZ, E SÓ ISSO:

  * `push`   -- desenha a notificação que chegou;
  * `notificationclick` -- abre a página que o aviso aponta, reusando a
    aba do site se ela já estiver aberta;
  * `install`/`activate` -- assume o controle na hora, sem esperar a
    próxima visita.

O QUE ELE NÃO FAZ: cache. Guardar página aqui significaria um cliente
vendo preço velho depois de a promoção acabar, e isso é pior que uma
visita mais lenta. O painel interno tem o seu, com a mesma escolha e
pelos mesmos motivos (ver `sistema_interno/views_app.py`).
"""

from django.http import HttpResponse
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET


SERVICE_WORKER = """/* Lazer & Sport -- avisos do aplicativo. Gerado por core/views_app_avisos.py */
self.addEventListener("install", function (evento) {
  self.skipWaiting();
});

self.addEventListener("activate", function (evento) {
  evento.waitUntil(self.clients.claim());
});

self.addEventListener("push", function (evento) {
  var dados = {};
  try {
    dados = evento.data ? evento.data.json() : {};
  } catch (erro) {
    dados = {};
  }

  var titulo = dados.titulo || "Lazer & Sport";
  var opcoes = {
    body: dados.mensagem || "",
    icon: "/static/images/logoofi.png",
    badge: "/static/images/logoofi.png",
    /* Uma tag por aviso: dois disparos diferentes aparecem como duas
       notificações, e o mesmo aviso reenviado substitui o anterior em vez
       de empilhar. */
    tag: "ls-aviso-" + (dados.aviso || "geral"),
    data: { url: dados.url || "/" },
    vibrate: [90, 40, 90]
  };

  evento.waitUntil(self.registration.showNotification(titulo, opcoes));
});

self.addEventListener("notificationclick", function (evento) {
  evento.notification.close();
  var destino = (evento.notification.data && evento.notification.data.url) || "/";

  evento.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true })
      .then(function (abas) {
        /* Se a loja já está aberta, é nela que a pessoa continua: abrir
           uma segunda aba do mesmo site é o jeito mais rápido de fazer
           alguém perder o carrinho que estava montando. */
        for (var i = 0; i < abas.length; i += 1) {
          if (abas[i].url.indexOf(self.location.origin) === 0 && "focus" in abas[i]) {
            abas[i].navigate(destino);
            return abas[i].focus();
          }
        }
        return self.clients.openWindow(destino);
      })
  );
});
"""


@require_GET
@cache_control(max_age=0, no_cache=True, no_store=True, must_revalidate=True)
def service_worker_do_site(request):
    """Entrega o script sempre fresco.

    Service worker cacheado é service worker que não se atualiza: o
    navegador continuaria rodando a versão antiga por horas depois de uma
    correção, e a notificação sairia errada sem ninguém entender por quê.
    """
    resposta = HttpResponse(SERVICE_WORKER, content_type="application/javascript")
    # Diz ao navegador que este script pode controlar a raiz do site,
    # mesmo servido por uma view.
    resposta["Service-Worker-Allowed"] = "/"
    return resposta
