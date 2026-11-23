from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from core.arquivos_no_banco import midia_no_banco

handler404 = 'core.views.erro_404'
handler500 = 'core.views.erro_500'

urlpatterns = [
    path('system/', admin.site.urls),
    # MEDIA FORÇADO (produção)
    #path('media/<path:path>/', media_serve),

    path('accounts/', include('allauth.urls')),
    # A API precisa vir antes das rotas gerais. core.urls termina com um
    # catch-all que, se vier primeiro, transforma /api/v1/status/ e login
    # em redirecionamentos para a loja.
    path("api/v1/", include("core.api.urls")),
    # Os arquivos públicos guardados no banco (seção 130). Quem atende de
    # verdade é o MidiaNoBancoMiddleware, antes da sessão; a rota fica aqui
    # para o reverse() e para o caso de o middleware sair da lista.
    path("midia/banco/<path:caminho>", midia_no_banco, name="midia_no_banco"),
    path('', include('core.urls')),

]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
