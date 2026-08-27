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
from .permissoes import atribuir_funcoes


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
    "/site/brinquedos/",
    "/site/combos/",
    "/site/promocoes/",
    "/site/eventos/",
    "/site/projetos/",
    "/site/cupons/",
    "/site/pecas/",
    "/site/banners/",
    "/site/engajamento/",
    "/site/indicadores/",
    "/site/clientes-mapa/",
    "/site/contas-clientes/",
    "/equipe/",
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
        atribuir_funcoes(colaborador, ["producao"])
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
        atribuir_funcoes(colaborador, ["producao"])
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
        atribuir_funcoes(colaborador, ["producao"])
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


class JanelasDoPainelTests(TestCase):
    """A estrutura das janelas -- o que decide se dá para salvar.

    Duas falhas de tablet que teste de regra de negócio não pega:

      * "Salvar" e "Cancelar" atrás do teclado. `100dvh` não enxerga o
        teclado, então a janela continua com a altura inteira e o rodapé
        fica fora da área visível, sem rolagem que o alcance. Quem enxerga
        é o `visualViewport`, copiado para `--ls-vh`;
      * janela sem o contrato "cabeçalho fixo / corpo que rola / rodapé
        fixo". Metade dos templates não trazia a marca e dependia de o
        conteúdo ser curto o bastante.

    Estes testes olham o que é servido ao navegador: a folha de estilo e o
    painel.js. Não substituem abrir no aparelho, mas impedem a volta
    silenciosa do `100dvh` e do rodapé solto.
    """

    def ler(self, caminho):
        from pathlib import Path
        from django.conf import settings

        base = Path(settings.BASE_DIR) / "sistema_interno" / "static" / "interno"
        return (base / caminho).read_text(encoding="utf-8")

    def test_altura_das_janelas_vem_do_visualviewport(self):
        js = self.ler("painel.js")

        self.assertIn("visualViewport", js)
        self.assertIn("--ls-vh", js)

    def test_folha_de_estilo_nao_usa_mais_dvh_para_medir_janela(self):
        """`100dvh` é o que ignora o teclado. Só pode sobrar como reserva
        na declaração da própria variável."""
        import re

        # Comentário pode citar o problema pelo nome sem ser o problema.
        css = re.sub(r"/\*.*?\*/", "", self.ler("interno_modern.css"), flags=re.S)

        for linha in css.splitlines():
            if "100dvh" not in linha:
                continue
            self.assertIn(
                "--ls-vh:100dvh", linha.replace(" ", ""),
                f"100dvh fora da reserva da variável: {linha.strip()}",
            )

    def test_toda_janela_recebe_cabecalho_e_rodape_fixos(self):
        js = self.ler("painel.js")

        self.assertIn("modal-dialog-scrollable", js)
        self.assertIn("show.bs.modal", js)

    def test_dinheiro_se_digita_da_direita_para_a_esquerda(self):
        """0,01 -> 0,10 -> 1,00, como em qualquer maquininha."""
        js = self.ler("painel.js")

        # A máscara trabalha em centavos: o que garante a progressão é
        # completar até três dígitos antes de cortar as duas casas.
        self.assertIn('while (centavos.length < 3) centavos = "0" + centavos;', js)
        self.assertIn("medida:", js)
        self.assertIn("percentual:", js)

    def test_nada_fixo_fica_por_cima_da_janela_aberta(self):
        """As abas de baixo cobriam o rodapé da janela.

        Elas são `position:fixed` com z-index 1100; o modal do Bootstrap é
        1055. Num aparelho estreito o toque em "Salvar" caía na aba, não
        no botão -- não dava para salvar nem cancelar. Elas somem enquanto
        há janela aberta (e nem fazem falta: a página atrás está travada).

        A segunda metade do teste é a que protege o futuro: qualquer
        elemento fixo que nasça acima do modal precisa ser neutralizado do
        mesmo jeito, senão repete o bug em outro canto da tela.
        """
        import re

        css = re.sub(r"/\*.*?\*/", "", self.ler("interno_modern.css"), flags=re.S)
        sem_espaco = css.replace(" ", "").replace("\n", "")

        self.assertIn("body.modal-open.ls-abas{display:none!important}", sem_espaco)

        acima_do_modal = []
        for bloco in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
            seletor, corpo = bloco.group(1).strip(), bloco.group(2)
            if "position:fixed" not in corpo.replace(" ", ""):
                continue
            altura = re.search(r"z-index:\s*(\d+)", corpo)
            if altura and int(altura.group(1)) > 1055:
                acima_do_modal.append(seletor.split()[-1])

        # Hoje só as abas -- e elas já somem com a janela aberta.
        self.assertEqual(
            sorted(set(acima_do_modal)), [".ls-abas"],
            "elemento fixo acima do modal sem sumir com body.modal-open: "
            f"{sorted(set(acima_do_modal))}",
        )

    def test_campo_de_texto_cresce_com_o_que_se_escreve(self):
        js = self.ler("painel.js")

        self.assertIn("acomodarTextos", js)
        self.assertIn("shown.bs.modal", js)

    def test_exclusao_tem_confirmacao_reutilizavel_e_layout_responsivo(self):
        js = self.ler("painel.js")
        css = self.ler("interno_modern.css")

        self.assertIn("ligarExclusao", js)
        self.assertIn("toLocaleUpperCase", js)
        self.assertIn('name="confirmacao_exclusao"', js)
        self.assertIn(".ls-delete-modal", css)
        self.assertIn(".ls-commercial-table", css)
        self.assertIn("@media (max-width:900px)", css)
