"""As rotas do RH, no subdomínio do painel (interno.).

Entram na lista de `sistema_interno/urls.py` (e não por `include`): a
varredura de `sistema_interno/tests_urls.py` abre cada rota da lista pelo
nome, e assim as do RH entram nela sozinhas.
"""

from django.urls import path

from .views import (
    ColaboradoresView,
    ColaboradorEditarView,
    ColaboradorNovoView,
    DocumentoArquivoView,
    DocumentoEnviarView,
    DocumentoRemoverView,
    DocumentosView,
    FichaImprimirView,
    FichaView,
    InicioView,
)
from .views_ponto import (
    ComprovanteView,
    DecidirAjusteView,
    EspelhoImprimirView,
    EspelhoView,
    MarcarPontoView,
    MeuPontoView,
    PedirAjusteView,
    PontoEquipeView,
)
from .views_tarefas import SugerirView, TarefaEditarView, TarefaSituacaoView, TarefasView
from .views_termo import (
    MeuTermoView,
    TermoColaboradorView,
    TermoPublicoView,
    TermoTodosView,
    TermoViaView,
)

urlpatterns = [
    path("rh/", InicioView.as_view(), name="rh_inicio"),

    # ---------------- colaboradores e documentos ----------------
    path("rh/colaboradores/", ColaboradoresView.as_view(), name="rh_colaboradores"),
    path("rh/colaboradores/novo/", ColaboradorNovoView.as_view(), name="rh_colaborador_novo"),
    path("rh/colaboradores/<int:pk>/", FichaView.as_view(), name="rh_ficha"),
    path("rh/colaboradores/<int:pk>/editar/", ColaboradorEditarView.as_view(), name="rh_colaborador_editar"),
    path("rh/colaboradores/<int:pk>/imprimir/", FichaImprimirView.as_view(), name="rh_ficha_imprimir"),
    path("rh/colaboradores/<int:pk>/documentos/", DocumentoEnviarView.as_view(), name="rh_documento_enviar"),
    path("rh/documentos/", DocumentosView.as_view(), name="rh_documentos"),
    # O ÚNICO caminho até o arquivo: confere a permissão e anota quem abriu.
    path("rh/documentos/<int:pk>/arquivo/", DocumentoArquivoView.as_view(), name="rh_documento_arquivo"),
    path("rh/documentos/<int:pk>/remover/", DocumentoRemoverView.as_view(), name="rh_documento_remover"),

    # ---------------- ponto ----------------
    path("rh/ponto/", MeuPontoView.as_view(), name="rh_ponto"),
    path("rh/ponto/marcar/", MarcarPontoView.as_view(), name="rh_ponto_marcar"),
    path("rh/ponto/equipe/", PontoEquipeView.as_view(), name="rh_ponto_equipe"),
    path("rh/ponto/comprovante/<int:pk>/", ComprovanteView.as_view(), name="rh_comprovante"),
    path("rh/ponto/ajustes/", PedirAjusteView.as_view(), name="rh_ajuste_pedir"),
    path("rh/ponto/ajustes/<int:pk>/decidir/", DecidirAjusteView.as_view(), name="rh_ajuste_decidir"),
    path("rh/ponto/espelho/<int:pk>/", EspelhoView.as_view(), name="rh_espelho"),
    path("rh/ponto/espelho/<int:pk>/imprimir/", EspelhoImprimirView.as_view(), name="rh_espelho_imprimir"),

    # ---------------- tarefas ----------------
    path("rh/tarefas/", TarefasView.as_view(), name="rh_tarefas"),
    path("rh/tarefas/sugerir/", SugerirView.as_view(), name="rh_tarefa_sugerir"),
    path("rh/tarefas/<int:pk>/situacao/", TarefaSituacaoView.as_view(), name="rh_tarefa_situacao"),
    path("rh/tarefas/<int:pk>/", TarefaEditarView.as_view(), name="rh_tarefa_editar"),

    # ---------------- termo de exclusividade ----------------
    path("rh/termo/", MeuTermoView.as_view(), name="rh_meu_termo"),
    path("rh/termo/enviar-todos/", TermoTodosView.as_view(), name="rh_termo_todos"),
    path("rh/termo/<int:pk>/via/", TermoViaView.as_view(), name="rh_termo_via"),
    path("rh/colaboradores/<int:pk>/termo/", TermoColaboradorView.as_view(), name="rh_termo"),
    # Sem login: o link de 5 minutos, para assinar no celular.
    path("rh/termo/assinar/<str:token>/", TermoPublicoView.as_view(), name="rh_termo_publico"),
]
