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

    def test_service_worker_guarda_so_arquivos_estaticos(self):
        """Cache local poupa banda sem guardar orçamento ou estoque velho."""
        corpo = self.abrir("/sw.js").content.decode()

        self.assertIn('url.pathname.indexOf("/static/")', corpo)
        self.assertIn("caches.open(CACHE_ESTATICO)", corpo)
        self.assertIn("cache.put(pedido, copia)", corpo)
        self.assertNotIn("cache.put('/orcamentos/", corpo)

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


class CadastroRapidoCompletoTests(TestCase):
    """A janela de cadastro rápido não pode pedir menos que o documento usa.

    O QUE ORIGINOU ISTO. A mesma peça, cadastrada pelo orçamento,
    guardava as seis fotos do catálogo; cadastrada pela O.S., nenhuma --
    a janela da O.S. simplesmente não tinha os campos, embora as duas
    telas chamem o MESMO cadastro (`sistema_interno/pecas.py`). O
    documento impresso saía com uma linha de texto no lugar da foto, e
    qual dado sobrava dependia da porta de entrada.
    """

    #: Os nomes que `fotos_catalogo` lê do formulário. Posição nova no
    #: cadastro entra aqui, e as duas janelas passam a ser cobradas.
    FOTOS_DA_PECA = (
        "foto_frente", "foto_tras", "foto_lado_direito",
        "foto_lado_esquerdo", "foto_detalhe", "foto_outro",
    )
    FOTOS_DO_BRINQUEDO = (
        "foto_perfil", "foto_verso", "foto_lado_direito", "foto_lado_esquerdo",
    )

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor-cadastro", password="x", email="c@example.com",
        )
        self.client.force_login(self.gestor)

    def tela(self, caminho):
        return self.client.get(
            caminho, HTTP_HOST="interno.testserver",
        ).content.decode()

    def test_as_duas_janelas_de_peca_pedem_as_mesmas_fotos(self):
        orcamento = self.tela("/orcamentos/")
        ordem = self.tela("/ordens-servico/")

        for campo in self.FOTOS_DA_PECA:
            with self.subTest(campo=campo):
                self.assertIn(f'name="{campo}"', orcamento)
                self.assertIn(f'name="{campo}"', ordem)

    def test_a_janela_do_brinquedo_pede_a_ficha_que_a_proposta_imprime(self):
        html = self.tela("/orcamentos/")

        for campo in ("altura_m", "largura_m", "profundidade_m", "voltz",
                      "descricao", "categoria", "tags", "estabelecimentos"):
            with self.subTest(campo=campo):
                self.assertIn(f'name="{campo}"', html)
        for campo in self.FOTOS_DO_BRINQUEDO:
            with self.subTest(campo=campo):
                self.assertIn(f'name="{campo}"', html)


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

        # A REGRA NÃO É "NÃO EXISTIR", É "NÃO ROUBAR O TOQUE".
        #
        # O defeito que originou este teste era o toque em "Salvar" cair
        # na aba de baixo. O que faz um elemento ser perigoso acima do
        # modal não é estar lá -- é RECEBER TOQUE estando lá. Aviso de
        # reconexão, tarja de "salvando" e confirmação precisam ficar
        # visíveis justamente com a janela aberta, que é quando alguém
        # está gravando; nenhum deles pode interceptar um dedo.
        #
        # Então a lista fixa virou regra: acima do modal, ou some com
        # `body.modal-open`, ou declara `pointer-events:none`.
        proibidos = []
        for bloco in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
            seletor, corpo = bloco.group(1).strip(), bloco.group(2)
            compacto = corpo.replace(" ", "")
            if "position:fixed" not in compacto:
                continue
            altura = re.search(r"z-index:\s*(\d+)", corpo)
            if not altura or int(altura.group(1)) <= 1055:
                continue
            nome = seletor.split()[-1]
            # O aviso de reconexão é a única exceção, e é deliberada: ele
            # TEM um botão ("tentar de novo"), então não pode ser inerte,
            # e precisa continuar visível com a janela aberta -- que é
            # exatamente quando a conexão cair mais atrapalha. Ele nasce
            # centrado no alto, longe do rodapé onde ficam Salvar e
            # Cancelar, que era o toque roubado pelas abas.
            if nome == ".ls-nav-recovery":
                continue
            some_com_modal = f"body.modal-open{nome}{{display:none!important}}" in sem_espaco
            inerte = "pointer-events:none" in compacto
            if not (some_com_modal or inerte):
                proibidos.append(nome)

        self.assertEqual(
            sorted(set(proibidos)), [],
            "elemento fixo acima do modal que nem some com body.modal-open "
            f"nem é inerte ao toque: {sorted(set(proibidos))}",
        )

        # E as duas tarjas novas precisam continuar inertes: é o que as
        # deixa aparecer por cima da janela sem repetir o bug das abas.
        for tarja in (".ls-ocupado{", ".ls-tarja{"):
            corpo = sem_espaco[sem_espaco.index(tarja):]
            corpo = corpo[:corpo.index("}")]
            self.assertIn("pointer-events:none", corpo, tarja)

    def test_o_card_do_celular_usa_a_largura_inteira(self):
        """O conteúdo "caía para a esquerda" e sobrava faixa à direita.

        No celular a linha da tabela vira card: uma grade de duas colunas
        dentro de uma caixa. O botão de ações ficava `position:absolute`
        no canto de cima e o espaço dele era reservado no PADDING DO CARD
        -- 54 a 64 pixels à direita, valendo para a altura inteira. Um
        botão que ocupa uma linha tirava largura de todas: seis linhas de
        dado espremidas e encostadas à esquerda, com uma faixa morta
        descendo pela direita. Num aparelho de 390px é 15% da tela.

        A reserva agora é de quem divide a primeira linha com o botão, e
        não do card. Por isso o padding é simétrico: um número só, ou
        quatro iguais.
        """
        import re

        css = re.sub(r"/\*.*?\*/", "", self.ler("interno_modern.css"), flags=re.S)

        cards = re.findall(
            r"\.ls-(?:commercial-table|orcamentos-table|os-tabela)"
            r"\s+tbody\s+tr\{([^{}]*)\}",
            css,
        )
        self.assertTrue(cards, "nenhuma regra de card encontrada")

        for corpo in cards:
            padding = re.search(r"padding:([^;!]+)", corpo)
            if not padding:
                continue
            lados = padding.group(1).split()
            if len(lados) == 1:
                continue
            self.assertEqual(
                len(set(lados)), 1,
                "card com reserva lateral para o botão de ações: "
                f"padding:{padding.group(1).strip()}",
            )

    def test_a_nota_do_cabecalho_da_os_e_paragrafo_e_nao_caixa_flex(self):
        """Em flex, cada trecho de texto vira um item que quebra sozinho.

        A nota é um parágrafo com <strong> no meio. Declarada
        `inline-flex`, ela saía repartida em colunas verticais no celular,
        com o fim da frase cortado fora da tela -- e ainda empurrava o
        cabeçalho para além da largura da página, desalinhando tudo que
        vinha depois.
        """
        from pathlib import Path
        from django.conf import settings

        tela = (
            Path(settings.BASE_DIR) / "sistema_interno"
            / "templates" / "ordens_servico_inner.html"
        ).read_text(encoding="utf-8")

        regra = tela[tela.index(".ls-os-body .ls-page-hero-nota{"):]
        regra = regra[:regra.index("}")]

        self.assertIn("display:block", regra)
        self.assertNotIn("flex", regra)

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
