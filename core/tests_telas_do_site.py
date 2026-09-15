"""As telas do site abrem com o desenho do site — e sem peso repetido.

DUAS GERAÇÕES DE TELA MORAVAM NO MESMO SITE. As novas (parceiros,
catálogo, peça) abriam com herói azul-marinho, onda de transição e
cartões escuros arredondados. As antigas -- brinquedos por
estabelecimento, eventos, projetos, peças de reposição -- abriam com um
título centralizado e cartões brancos quadrados, cada uma com o seu
próprio `<style>` dentro do HTML.

E não era só aparência:

  * **Eventos estava escrito em Bootstrap**, que este site não carrega.
    `row`, `col-md-6`, `card-body`, `text-primary`: nenhuma dessas
    classes existe aqui. A página abria sem grade nenhuma, em coluna
    única, e ninguém via um erro -- só uma tela feia.
  * **Os modais de fotos de Eventos não abriam.** O script que os abria
    mora em `home.js`, carregado só na página inicial. Clicar num evento
    não fazia nada.
  * **Quatro telas abriam um segundo `<main>`** dentro do que o
    `base.html` já abre. Para quem usa leitor de tela, "ir para o
    conteúdo principal" passava a ter dois destinos.
  * **Eventos e Projetos consultavam o banco uma vez por linha**, e a
    tela ia ficando mais lenta a cada evento cadastrado.
  * **Três telas carregavam cópias mortas** de `adicionarAoCarrinho`,
    `atualizarBadgeCarrinho` e `mostrarToast`: o `base.html` declara as
    três depois, no fim do documento, e no escopo global quem declara
    por último ganha.

O que se trava aqui é o resultado: casco comum, um `main` só, estilo em
arquivo com endereço cacheável, e consulta que não cresce com as linhas.
"""

import re
from pathlib import Path

from django.contrib.staticfiles import finders
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext, override_settings

RAIZ = Path(__file__).resolve().parent
TEMPLATES = RAIZ / "templates"

#: `{% estatico 'x' %}` e `{% static 'x' %}` — o site usa os dois.
REFERENCIA = re.compile(r"""\{%\s*(?:estatico|static)\s+(['"])([^'"]+)\1""")

#: Telas que PODEM continuar com o estilo dentro do HTML, e por quê.
#:
#: As de erro precisam desenhar-se quando o resto está quebrado: pedir um
#: arquivo a mais é justamente o que pode não chegar. As duas páginas
#: avulsas são abertas a partir de um link de campanha ou do retorno do
#: pagamento, fora do `base.html`, e valem mais como documento único.
ESTILO_INTERNO_PERMITIDO = {
    "404.html",
    "500.html",
    "campanha_publica.html",
    "payment_finally.html",
    "partials/auth_loading.html",
}


#: Comentário do Django e comentário de HTML. Eles são retirados antes
#: de qualquer varredura: as notas deste projeto citam a marcação que
#: explicam -- "antes eram 2 KB de `<style>` dentro do HTML" --, e uma
#: busca crua acusaria justamente a tela que foi corrigida.
COMENTARIOS = re.compile(r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}|<!--.*?-->", re.S)


def _sem_comentarios(texto):
    return COMENTARIOS.sub("", texto)


def _templates_do_site():
    for arquivo in sorted(TEMPLATES.rglob("*.html")):
        relativo = arquivo.relative_to(TEMPLATES).as_posix()
        if relativo.startswith(("emails/", "gestao/")):
            continue
        yield relativo, arquivo


@override_settings(ALLOWED_HOSTS=["www.lazersport.com.br", "testserver"])
class EstiloForaDoHtmlTests(TestCase):
    """Estilo dentro da página não tem endereço — e por isso não cacheia.

    O HTML de uma página nunca é guardado pelo navegador: ele pode mudar
    a cada visita. Um `<style>` lá dentro herda essa regra e desce de
    novo a cada abertura, por visitante e por robô de busca. Em arquivo,
    com a impressão digital do conteúdo no endereço, ele desce UMA vez e
    vale por um ano.
    """

    def test_nenhuma_tela_do_site_carrega_estilo_dentro_do_html(self):
        sobrando = []

        for relativo, arquivo in _templates_do_site():
            if relativo in ESTILO_INTERNO_PERMITIDO:
                continue
            texto = _sem_comentarios(arquivo.read_text(encoding="utf-8"))
            if re.search(r"<style[\s>]", texto):
                sobrando.append(relativo)

        self.assertEqual(
            sobrando, [],
            "Estas telas ainda trazem <style> dentro do HTML — mova para "
            "core/static/site/paginas/<nome>.css e chame com "
            "{% estatico %}:\n  " + "\n  ".join(sobrando),
        )

    def test_toda_folha_e_script_pedido_existe_de_verdade(self):
        """`{% estatico %}` não levantava erro para arquivo ausente.

        A varredura que já existia (`tests_assets`) só olhava
        `{% static %}`; o site usa `{% estatico %}` na maior parte das
        chamadas, e um caminho errado ali passava batido -- a página
        abria, respondia 200, e vinha sem estilo nenhum.
        """
        faltando = []

        for relativo, arquivo in _templates_do_site():
            texto = arquivo.read_text(encoding="utf-8")
            for _, caminho in REFERENCIA.findall(texto):
                if "{" in caminho or "%" in caminho:
                    continue
                if finders.find(caminho) is None:
                    faltando.append(f"{relativo} → {caminho}")

        self.assertEqual(
            faltando, [],
            "Arquivo pedido e inexistente (a página abre sem ele, em "
            "silêncio):\n  " + "\n  ".join(faltando),
        )


@override_settings(ALLOWED_HOSTS=["www.lazersport.com.br", "testserver"])
class UmConteudoPrincipalPorPaginaTests(TestCase):

    def test_nenhuma_tela_filha_abre_um_segundo_main(self):
        """O `base.html` já abre o conteúdo principal em volta do bloco."""
        duplicadas = []

        for relativo, arquivo in _templates_do_site():
            texto = _sem_comentarios(arquivo.read_text(encoding="utf-8"))
            if "{% extends" not in texto:
                continue
            if re.search(r"<main[\s>]", texto):
                duplicadas.append(relativo)

        self.assertEqual(
            duplicadas, [],
            "Segundo <main> dentro do <main> do base.html — o leitor de "
            "tela passa a ter dois 'conteúdo principal':\n  "
            + "\n  ".join(duplicadas),
        )


@override_settings(ALLOWED_HOSTS=["www.lazersport.com.br", "testserver"])
class CarrinhoESoUmCarrinhoTests(TestCase):
    """As funções do carrinho são do site, e de nenhuma tela em especial.

    Três telas traziam a própria cópia delas. Nenhuma rodava: o
    `base.html` declara as mesmas funções DEPOIS, no fim do documento, e
    no escopo global a última declaração vence. Eram setenta linhas de
    código morto por tela -- e código morto que parece vivo é o pior
    tipo, porque alguém corrige um defeito nele e não entende por que
    nada muda na tela.
    """

    DO_SITE = ("adicionarAoCarrinho", "atualizarBadgeCarrinho", "mostrarToast")

    def test_nenhuma_tela_filha_redeclara_as_funcoes_do_carrinho(self):
        repetidas = []

        for relativo, arquivo in _templates_do_site():
            if relativo == "base.html":
                continue
            texto = _sem_comentarios(arquivo.read_text(encoding="utf-8"))
            for nome in self.DO_SITE:
                # SÓ A DECLARAÇÃO DE TOPO, na coluna zero. Uma tela pode
                # ter o SEU próprio aviso dentro de um escopo fechado --
                # `brinquedo_info` faz isso de propósito, embrulhado numa
                # função anônima, e ali a cópia é local e legítima: ela
                # não substitui a do site, só vale dentro do embrulho.
                if re.search(r"^function\s+%s\s*\(" % nome, texto, re.M):
                    repetidas.append(f"{relativo} → {nome}")

        self.assertEqual(
            repetidas, [],
            "Função do carrinho redeclarada numa tela; o base.html declara "
            "depois e ganha, então esta cópia nunca roda:\n  "
            + "\n  ".join(repetidas),
        )


@override_settings(ALLOWED_HOSTS=["www.lazersport.com.br", "testserver"])
class TelasAntigasUsamOCascoDoSiteTests(TestCase):
    """As quatro telas que tinham ficado para trás abrem como o resto.

    Não se confere aqui "está bonito" -- isso é olho, e foi olhado. O que
    se trava é o que faz a tela ser a mesma coisa que as outras: o casco
    comum (`ls-pagina.css`), o herói, a onda e a grade. Trocar um deles
    por marcação avulsa é como a divergência começou da primeira vez.
    """

    HOST = {"HTTP_HOST": "www.lazersport.com.br"}

    def setUp(self):
        from decimal import Decimal

        from core.models import (
            Brinquedos,
            BrinquedosProjeto,
            Estabelecimentos,
            Eventos,
            Projetos,
        )

        self.estabelecimento = Estabelecimentos.objects.create(
            nome_estabelecimento="Shopping Aurora",
        )
        for nome, nota, valor in (
            ("Cama elástica 3m", "4.5", "1200.00"),
            ("Air game", "3.0", "300.00"),
            ("Piscina de bolinhas", "5.0", "800.00"),
        ):
            brinquedo = Brinquedos.objects.create(
                nome_brinquedo=nome,
                descricao="Brinquedo profissional para espaços kids.",
                avaliacao=Decimal(nota),
                valor_brinquedo=Decimal(valor),
                voltz="220v",
            )
            brinquedo.estabelecimentos.add(self.estabelecimento)

        evento = Eventos.objects.create(
            titulo="Festa de aniversário", descricao="Montagem completa no salão.",
        )
        evento.brinquedos.add(Brinquedos.objects.first())

        projetado = BrinquedosProjeto.objects.create(
            nome_brinquedo_projeto="Castelo sob medida", descricao="x",
        )
        Projetos.objects.create(
            titulo="Castelo do buffet", descricao="Feito sob medida.",
            brinquedo_projetado=projetado,
        )

    def html(self, rota):
        resposta = self.client.get(rota, **self.HOST)
        self.assertEqual(resposta.status_code, 200, rota)
        return resposta.content.decode()

    def test_as_quatro_telas_abrem_com_o_casco_comum(self):
        rotas = (
            f"/estabelecimentos/{self.estabelecimento.pk}/",
            "/eventos/",
            "/projetos/",
            "/pecas-reposicao/",
        )
        for rota in rotas:
            corpo = self.html(rota)
            self.assertIn("site/ls-pagina.css", corpo, rota)
            self.assertIn('class="ls-pagina-hero"', corpo, rota)
            self.assertIn("ls-pagina-onda", corpo, rota)
            # Um `<main>` só: o do base.html.
            self.assertEqual(corpo.count("<main"), 1, rota)

    def test_eventos_nao_depende_mais_de_bootstrap(self):
        """As classes do Bootstrap não existem neste site.

        Enquanto a tela foi escrita com elas, ela abria sem grade: os
        cartões empilhavam em coluna única, largura cheia, em qualquer
        tamanho de tela. O defeito não levantava erro nenhum.
        """
        corpo = self.html("/eventos/")
        for classe in ('class="row', "col-md-6", "card-body", "text-primary"):
            self.assertNotIn(classe, corpo, classe)
        self.assertIn('class="ls-grade', corpo)

    def test_a_janela_de_fotos_de_eventos_tem_quem_a_abra(self):
        """Era isto que faltava: o gatilho, a janela e NENHUM script.

        O código que abria o modal mora em `home.js`, carregado só na
        página inicial. Em /eventos/ o clique não fazia nada -- e não
        fazer nada, sem erro e sem aviso, passa por decisão de projeto.
        """
        corpo = self.html("/eventos/")
        self.assertIn("data-ls-galeria=", corpo)
        self.assertIn('class="ls-galeria"', corpo)
        self.assertIn("site/ls-galeria.js", corpo)
        self.assertIn("site/ls-galeria.css", corpo)

    def test_projetos_usa_a_mesma_janela_de_fotos(self):
        corpo = self.html("/projetos/")
        self.assertIn("data-ls-galeria=", corpo)
        self.assertIn("site/ls-galeria.js", corpo)

    def test_a_ordenacao_dos_brinquedos_e_feita_pelo_servidor(self):
        """O chip A–Z acendia sem nada estar ordenado.

        A ordenação era só do JavaScript, depois da página pronta. Sem
        ele -- ou antes de ele rodar -- a lista vinha na ordem de
        inserção com o chip dizendo que estava em ordem alfabética. E o
        parâmetro `?order=`, que o servidor sempre aceitou, nunca era
        usado pela tela: o link não existia.
        """
        rota = f"/estabelecimentos/{self.estabelecimento.pk}/"

        def nomes(consulta=""):
            return re.findall(r'data-nome="([^"]+)"', self.html(rota + consulta))

        self.assertEqual(
            nomes(), ["Air game", "Cama elástica 3m", "Piscina de bolinhas"],
        )
        self.assertEqual(
            nomes("?order=za"), ["Piscina de bolinhas", "Cama elástica 3m", "Air game"],
        )
        self.assertEqual(
            nomes("?order=custo"), ["Air game", "Piscina de bolinhas", "Cama elástica 3m"],
        )
        self.assertEqual(
            nomes("?order=avaliacao"),
            ["Piscina de bolinhas", "Cama elástica 3m", "Air game"],
        )
        # Parâmetro inventado não quebra a tela nem apaga todos os chips.
        self.assertEqual(nomes("?order=lixo"), nomes())

    def test_os_numeros_do_html_nao_saem_com_virgula(self):
        """O JavaScript lê estes atributos; a vírgula é de quem lê a tela.

        `4,5` é o certo para os olhos e é o que aparece escrito. Para o
        `parseFloat` que ordena a lista, não: com separador de milhar
        ligado, "1.200,00" viraria 1,2 e a ordenação por preço mentiria.
        """
        corpo = self.html(f"/estabelecimentos/{self.estabelecimento.pk}/")
        for atributo in re.findall(r'data-(?:avaliacao|custo|nota)="([^"]*)"', corpo):
            self.assertNotIn(",", atributo, corpo[:0] or atributo)


@override_settings(ALLOWED_HOSTS=["www.lazersport.com.br", "testserver"])
class ConsultaNaoCresceComAsLinhasTests(TestCase):
    """Uma consulta por conjunto, e não duas por evento.

    Eventos mostra, de cada evento, as fotos e os brinquedos usados. Sem
    `prefetch_related` isso era uma ida ao banco para as fotos e outra
    para os brinquedos EM CADA evento: com trinta eventos publicados,
    sessenta e uma consultas para desenhar uma página. Não dava erro --
    só ficava mais lenta a cada evento cadastrado, que é o jeito mais
    silencioso de uma tela apodrecer.
    """

    HOST = {"HTTP_HOST": "www.lazersport.com.br"}
    FOLGA = 2

    def criar(self, quantidade):
        from decimal import Decimal

        from core.models import Brinquedos, BrinquedosProjeto, Eventos, Projetos

        brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Air game", descricao="x",
            avaliacao=Decimal("4"), valor_brinquedo=Decimal("10"), voltz="220v",
        )
        for numero in range(quantidade):
            evento = Eventos.objects.create(titulo=f"Festa {numero}", descricao="x")
            evento.brinquedos.add(brinquedo)

            projetado = BrinquedosProjeto.objects.create(
                nome_brinquedo_projeto=f"Peça {numero}", descricao="x",
            )
            Projetos.objects.create(
                titulo=f"Projeto {numero}", descricao="x",
                brinquedo_projetado=projetado,
            )

    def consultas(self, rota):
        with CaptureQueriesContext(connection) as capturadas:
            resposta = self.client.get(rota, **self.HOST)
        self.assertEqual(resposta.status_code, 200, rota)
        return len(capturadas)

    def test_eventos_e_projetos_nao_consultam_por_linha(self):
        self.criar(2)
        # A primeira abertura aquece cache de sessão e de contexto; o que
        # se compara são duas aberturas já quentes, com tamanhos bem
        # diferentes de lista.
        self.consultas("/eventos/")
        self.consultas("/projetos/")

        poucos_eventos = self.consultas("/eventos/")
        poucos_projetos = self.consultas("/projetos/")

        self.criar(25)

        self.assertLessEqual(
            self.consultas("/eventos/"), poucos_eventos + self.FOLGA,
            "a tela de Eventos consulta o banco uma vez por evento",
        )
        self.assertLessEqual(
            self.consultas("/projetos/"), poucos_projetos + self.FOLGA,
            "a tela de Projetos consulta o banco uma vez por projeto",
        )


@override_settings(ALLOWED_HOSTS=["www.lazersport.com.br", "testserver"])
class AncoraQueLevaAAlgumLugarTests(TestCase):
    """Um `#` que não existe leva ao topo da página, calado.

    O site inteiro navega com âncora: `…/brinquedos/1/#bread` abre o
    produto já na altura certa, e é isso que faz a volta do catálogo não
    cair no cabeçalho. Quando o destino não existe -- porque o `id` foi
    renomeado num lado e não no outro --, o navegador não reclama: ele
    simplesmente abre no topo. O link continua funcionando o bastante
    para ninguém reportar, e mal o bastante para irritar todo dia.

    Eram cinco, e todos com essa cara: `#produto-box` (a lista de
    categorias e a de um parceiro), `#container` (a lista de peças),
    `#detalhe` e `#peca` (a lista de desejos), `#list` (as categorias na
    home) e `#pagamento` (meus pedidos).
    """

    #: `<use href="#simbolo">` aponta para um `<symbol>` do SVG, e não
    #: para um trecho da página. Não é âncora de navegação.
    ANCORA = re.compile(r'<a\s[^>]*href="[^"]*?#([A-Za-z][\w:.-]*)"')

    def test_todo_destino_de_ancora_existe_em_alguma_tela(self):
        identificadores = set()
        for _, arquivo in _templates_do_site():
            identificadores |= set(
                re.findall(r'id="([A-Za-z][\w:.-]*)"', arquivo.read_text(encoding="utf-8"))
            )

        # O `base.html` do painel interno também é destino de link do site.
        interno = RAIZ.parent / "sistema_interno" / "templates"
        if interno.is_dir():
            for arquivo in interno.rglob("*.html"):
                identificadores |= set(
                    re.findall(r'id="([A-Za-z][\w:.-]*)"', arquivo.read_text(encoding="utf-8"))
                )

        mortas = []
        for relativo, arquivo in _templates_do_site():
            texto = _sem_comentarios(arquivo.read_text(encoding="utf-8"))
            for ancora in self.ANCORA.findall(texto):
                if ancora not in identificadores:
                    mortas.append(f"{relativo} → #{ancora}")

        self.assertEqual(
            sorted(set(mortas)), [],
            "Âncora sem destino: o link abre no topo da página e ninguém "
            "vê erro nenhum.\n  " + "\n  ".join(sorted(set(mortas))),
        )


@override_settings(ALLOWED_HOSTS=["www.lazersport.com.br", "testserver"])
class UmTituloDePrimeiroNivelPorPaginaTests(TestCase):
    """A faixa da marca não é o título da página.

    "Fábrica de Brinquedos" era um `<h1>` dentro do `base.html`, ou seja,
    em TODAS as telas. Cada página ficava com dois títulos de primeiro
    nível -- o seu e aquele --, e o buscador lia a marca como o assunto
    de "Peças de reposição", de "Brinquedos em Shopping Aurora" e de
    qualquer outra. Para quem usa leitor de tela, a navegação por títulos
    abria com uma linha igual em toda página, que não diz onde se está.
    """

    HOST = {"HTTP_HOST": "www.lazersport.com.br"}

    def test_a_faixa_da_marca_nao_e_um_h1(self):
        base = _sem_comentarios((TEMPLATES / "base.html").read_text(encoding="utf-8"))
        marca = base[base.index('class="ls-faixa-marca"'):][:1400]
        self.assertNotIn("<h1", marca)
        self.assertIn("Fábrica de Brinquedos", marca)

    def test_as_telas_do_site_tem_um_h1_so(self):
        for rota in ("/", "/brinquedos/", "/pecas-reposicao/", "/eventos/", "/projetos/"):
            resposta = self.client.get(rota, **self.HOST)
            self.assertEqual(resposta.status_code, 200, rota)
            corpo = resposta.content.decode()
            self.assertEqual(
                len(re.findall(r"<h1[\s>]", corpo)), 1,
                f"{rota} tem mais de um título de primeiro nível",
            )
