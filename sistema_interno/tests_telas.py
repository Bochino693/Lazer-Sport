"""Varredura das telas do painel: todas abrem, e nenhuma vaza template.

POR QUE ESTE ARQUIVO. Duas falhas passaram batido por testes de regra de
negócio e só apareceram no navegador:

  * comentário `{# ... #}` escrito em várias linhas NÃO é comentário no
    Django -- o texto ia parar na tela do usuário, no meio do formulário;
  * link de menu para rota que a view devolve como desvio.

Ambas são baratas de pegar aqui: abre cada tela e confere o que saiu.
"""

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from .models import Cliente, ProdutoInterno


# Toda tela do painel, na ordem do menu. Tela nova entra aqui.
TELAS_DE_GESTOR = [
    "/",
    "/clientes/",
    "/orcamentos/",
    "/financeiro/",
    "/stock/",
    "/estoque/materiais/",
    "/estoque/movimentacoes/",
    "/estoque/dashboard/",
    "/producao/",
    "/producao/guias/",
    "/producao/produtos/",
    "/producao/ordens/",
    "/vendas/inner/",
    "/pedidos/inner/",
    "/manutencoes/inner/",
    "/minha-conta/",
]

# O que um colaborador de produção alcança sem cair em desvio. A raiz
# fica de fora de propósito: para quem monta, a casa é a produção, e a
# home manda para lá — comportamento coberto no teste logo abaixo.
TELAS_DE_COLABORADOR = [
    "/producao/",
    "/stock/",
    "/estoque/movimentacoes/",
    "/minha-conta/",
]


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class TelasDoPainelTests(TestCase):

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor",
            password="senha-segura",
            email="gestor@example.com",
        )

        # Dado suficiente para as telas saírem do estado vazio: é com
        # conteúdo que o template quebra, não sem ele.
        self.buffet = Cliente.objects.create(
            nome_cliente="Buffet Alegria",
            tipo=Cliente.Tipo.BUFFET,
            telefone="(11) 3333-4444",
        )
        Cliente.objects.create(
            nome_cliente="Marina Souza",
            telefone="(11) 99999-8888",
            parceiro=self.buffet,
        )
        ProdutoInterno.objects.create(
            nome="Cama elástica 3m",
            categoria=ProdutoInterno.Categoria.BRINQUEDO,
        )

    def abrir(self, rota):
        return self.client.get(rota, HTTP_HOST="interno.testserver")

    def test_gestor_abre_todas_as_telas(self):
        self.client.force_login(self.gestor)

        for rota in TELAS_DE_GESTOR:
            with self.subTest(rota=rota):
                resposta = self.abrir(rota)
                self.assertEqual(resposta.status_code, 200)

    def test_nenhuma_tela_vaza_marcacao_de_template(self):
        """`{#` na página é comentário multilinha virando texto visível."""
        self.client.force_login(self.gestor)

        for rota in TELAS_DE_GESTOR:
            with self.subTest(rota=rota):
                corpo = self.abrir(rota).content.decode()

                self.assertNotIn("{#", corpo)
                self.assertNotIn("{%", corpo)
                self.assertNotIn("{{", corpo)

    def test_colaborador_abre_o_que_e_dele(self):
        colaborador = User.objects.create_user(
            username="montador",
            password="senha-segura",
            is_staff=True,
        )
        self.client.force_login(colaborador)

        for rota in TELAS_DE_COLABORADOR:
            with self.subTest(rota=rota):
                resposta = self.abrir(rota)
                self.assertEqual(resposta.status_code, 200)

    def test_para_quem_monta_a_casa_e_a_producao(self):
        colaborador = User.objects.create_user(
            username="montador",
            password="senha-segura",
            is_staff=True,
        )
        self.client.force_login(colaborador)

        resposta = self.abrir("/")

        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/producao/", resposta["Location"])

    def test_colaborador_e_desviado_do_que_e_de_gestor(self):
        colaborador = User.objects.create_user(
            username="montador",
            password="senha-segura",
            is_staff=True,
        )
        self.client.force_login(colaborador)

        for rota in ["/clientes/", "/orcamentos/", "/financeiro/"]:
            with self.subTest(rota=rota):
                resposta = self.abrir(rota)
                self.assertEqual(resposta.status_code, 302)

    def test_visitante_vai_para_o_login_do_painel(self):
        resposta = self.abrir("/clientes/")

        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/login/inner/", resposta["Location"])

    def test_fora_do_subdominio_o_painel_nao_existe(self):
        """O mesmo caminho no site público não pode abrir a fábrica."""
        self.client.force_login(self.gestor)

        resposta = self.client.get("/clientes/", HTTP_HOST="testserver")

        self.assertNotEqual(resposta.status_code, 200)


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class AplicativoInstalavelTests(TestCase):
    """O painel precisa poder ser instalado no tablet da fábrica.

    Manifesto e service worker respondem na raiz do subdomínio: servidos
    de /static/ o aplicativo abriria dentro da pasta de estáticos e o
    service worker não controlaria o painel.
    """

    def abrir(self, rota):
        return self.client.get(rota, HTTP_HOST="interno.testserver")

    def test_manifesto_abre_sem_login(self):
        """O navegador busca o manifesto antes de qualquer sessão."""
        resposta = self.abrir("/manifest.webmanifest")

        self.assertEqual(resposta.status_code, 200)
        self.assertIn("manifest+json", resposta["Content-Type"])

    def test_manifesto_abre_o_painel_em_tela_cheia(self):
        dados = self.abrir("/manifest.webmanifest").json()

        self.assertEqual(dados["display"], "standalone")
        self.assertEqual(dados["start_url"], "/")
        self.assertEqual(dados["scope"], "/")
        self.assertTrue(dados["icons"])
        self.assertIn(
            "maskable",
            [icone["purpose"] for icone in dados["icons"]],
        )

    def test_service_worker_vem_da_raiz(self):
        resposta = self.abrir("/sw.js")

        self.assertEqual(resposta.status_code, 200)
        self.assertIn("javascript", resposta["Content-Type"])
        self.assertIn("fetch", resposta.content.decode())

    def test_service_worker_nao_guarda_resposta_em_cache(self):
        """Painel de operação com cache mostra número velho sem avisar."""
        corpo = self.abrir("/sw.js").content.decode()

        self.assertNotIn("caches.open", corpo)
        self.assertNotIn("cache.put", corpo)

    def test_pagina_do_painel_aponta_para_o_manifesto(self):
        gestor = User.objects.create_superuser(
            username="gestor",
            password="senha-segura",
            email="gestor@example.com",
        )
        self.client.force_login(gestor)

        corpo = self.abrir("/").content.decode()

        self.assertIn('rel="manifest" href="/manifest.webmanifest"', corpo)
        self.assertIn('name="apple-mobile-web-app-capable"', corpo)


class SemDependenciaDeCDNTests(TestCase):
    """O painel não pode depender de servidor de terceiro para funcionar.

    Bootstrap e ícones vinham de CDN. Quando o CDN não responde -- wi-fi
    ruim no galpão, DNS travado, operadora bloqueando --, o JavaScript do
    Bootstrap não carrega e TODOS os modais param: cadastrar cliente,
    montar orçamento, abrir etapa. A tela abre e não faz nada.

    Este teste lê os templates do painel: qualquer endereço externo novo
    reabre o mesmo buraco.
    """

    HOSPEDEIROS_PROIBIDOS = (
        "cdn.jsdelivr.net",
        "cdnjs.cloudflare.com",
        "unpkg.com",
        "stackpath.bootstrapcdn.com",
        "maxcdn.bootstrapcdn.com",
        "fonts.googleapis.com",
        "code.jquery.com",
    )

    def test_nenhum_template_do_painel_puxa_arquivo_de_fora(self):
        from pathlib import Path

        pasta = Path(__file__).resolve().parent / "templates"
        problemas = []

        for template in sorted(pasta.glob("*.html")):
            texto = template.read_text(encoding="utf-8")

            for numero, linha in enumerate(texto.splitlines(), 1):
                # O texto do comentário que explica a mudança cita o CDN
                # de propósito; o que não pode é src/href apontando pra lá.
                if "src=" not in linha and "href=" not in linha:
                    continue

                for hospedeiro in self.HOSPEDEIROS_PROIBIDOS:
                    if hospedeiro in linha:
                        problemas.append(f"{template.name}:{numero} → {hospedeiro}")

        self.assertEqual(
            problemas,
            [],
            "Arquivo externo no painel interno:\n" + "\n".join(problemas),
        )
