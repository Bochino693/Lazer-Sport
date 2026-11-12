"""A tela de Brinquedos do painel, refeita nas cores do sistema.

O que estes testes protegem:

  * a tela abre com o desenho novo (cartões, chips de filtro, o cadastro
    num <dialog>) e sem nenhum <select>: a categoria, a loja e a capa se
    escolhem em chips, que são links;
  * o JavaScript mora no bloco de scripts: dentro do conteúdo ele não rodava
    de novo quando um filtro trocava a lista sem recarregar a página, e
    "Editar" / "Excluir" paravam de responder depois do primeiro filtro;
  * os campos enviados (name=) e os ids do formulário são os de antes;
  * os filtros novos (na loja / fora, com capa / sem capa, o #número na
    busca) e a categoria inválida, que derrubava a tela com 500;
  * o cartão mostra o que importa: foto, nome, #número, voltagem, medidas
    (ou o aviso de que faltam), preço ou "Sob consulta", categorias e o
    "Ver no site" apontando para o site, e não para o painel;
  * salvar, editar e excluir continuam funcionando pela rota do painel, com
    os dois consertos da view: "18.000" no preço é dezoito mil, e
    "Não se aplica" (13 letras num campo de 10) grava a voltagem vazia.
"""

import json
import re
import tempfile
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from .models import Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, TagsBrinquedos

INTERNO = {"HTTP_HOST": "interno.testserver"}
AJAX = {**INTERNO, "HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
ROTA = "/site/brinquedos/"
RAIZ = Path(__file__).resolve().parent


def foto(nome="frente.png"):
    arquivo = BytesIO()
    Image.new("RGB", (4, 3), "red").save(arquivo, "PNG")
    return SimpleUploadedFile(nome, arquivo.getvalue(), content_type="image/png")


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.gestor = User.objects.create_superuser("catalogo", "catalogo@exemplo.com", "x")
        self.client.force_login(self.gestor)
        self.fliperamas = CategoriasBrinquedos.objects.create(
            nome_categoria="Fliperamas", imagem_categoria="categorias/fliperamas.png",
        )
        self.esportes = CategoriasBrinquedos.objects.create(
            nome_categoria="Esportes", imagem_categoria="categorias/esportes.png",
        )
        self.tag = TagsBrinquedos.objects.create(nome_tags="Mais vendido")
        self.air = Brinquedos.objects.create(
            nome_brinquedo="Air Game Hockey", descricao="Mesa de air game",
            avaliacao=Decimal("4.8"), voltz="220V", valor_brinquedo=Decimal("9800.00"),
            exibir_na_loja=True, imagem_brinquedo="brinquedos/air.png",
            altura_m=Decimal("1.00"), largura_m=Decimal("1.10"), profundidade_m=Decimal("2.10"),
        )
        self.air.categorias_brinquedos.set([self.fliperamas])
        self.casinha = Brinquedos.objects.create(
            nome_brinquedo="Casinha Cenográfica", descricao="Casinha de brincar",
            avaliacao=Decimal("5.0"), voltz="",
        )
        self.casinha.categorias_brinquedos.set([self.esportes])

    def tearDown(self):
        cache.clear()

    def abrir(self, **params):
        resposta = self.client.get(ROTA, params, **INTERNO)
        self.assertEqual(resposta.status_code, 200)
        return resposta

    @staticmethod
    def conteudo(resposta):
        """Só a tela (o miolo do painel), sem o menu e a barra de cima."""
        html = resposta.content.decode()
        inicio = html.index('<main class="ls-content">')
        return html[inicio:html.index("</main>", inicio)]

    def salvar(self, **campos):
        dados = {
            "action": "save", "nome_brinquedo": "Basquete Street", "descricao": "Cesta de rua",
            "avaliacao": "4,9", "voltz": "220V", **campos,
        }
        return self.client.post(ROTA, dados, **AJAX)


class TelaTests(Base):
    def test_a_tela_abre_com_o_desenho_novo(self):
        html = self.abrir().content.decode()
        for trecho in (
            'class="bq-tela"', 'class="bq-numeros"', 'class="bq-grade', 'data-bq-item',
            '<dialog id="toyDialog"', '<dialog id="deleteDialog"', '<dialog id="categoryDialog"',
            '<dialog id="tagDialog"', '<dialog id="lightbox"', "toysAdminData",
            "site/paginas/gestao-brinquedos_adm.css",
        ):
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, html)

    def test_o_script_da_tela_mora_no_bloco_de_scripts(self):
        html = self.abrir().content.decode()
        caixa = html.index('id="lsTelaScripts"')
        script = html.index("site/paginas/gestao-brinquedos_adm.js")
        self.assertGreater(script, caixa, "o script precisa estar no bloco de scripts")
        # e nada de JavaScript solto no conteúdo (só os dados, em JSON)
        miolo = self.conteudo(self.abrir())
        self.assertEqual(re.findall(r"<script(?![^>]*application/json)[^>]*>", miolo), [])

    def test_nenhum_select_na_tela(self):
        miolo = self.conteudo(self.abrir())
        self.assertNotIn("<select", miolo)
        # os filtros são chips (links), com a contagem de cada um
        self.assertIn("data-bq-filtro-categoria", miolo)
        self.assertIn("data-bq-filtro-loja", miolo)
        self.assertIn("data-bq-filtro-capa", miolo)

    def test_os_campos_do_formulario_sao_os_de_antes(self):
        html = self.abrir().content.decode()
        nomes = [
            "action", "id", "nome_brinquedo", "descricao", "valor_brinquedo", "avaliacao", "voltz",
            "altura_m", "largura_m", "profundidade_m", "exibir_na_loja", "categorias_brinquedos", "tags",
            "objeto_3d", "remover_objeto_3d", "confirmacao_exclusao", "nome_categoria",
            "imagem_categoria", "nome_tag",
        ]
        for tipo in ("perfil", "verso", "lado_direito", "lado_esquerdo"):
            nomes += [f"imagem_{tipo}", f"remover_imagem_{tipo}"]
        for nome in nomes:
            with self.subTest(name=nome):
                self.assertIn(f'name="{nome}"', html)
        ids = [
            "toyForm", "toyId", "toyTitle", "toyError", "toyErrorText", "closeToy", "cancelToy",
            "submitToy", "toyName", "toyDescription", "toyPrice", "toyRating", "toyVoltage",
            "toyHeight", "toyWidth", "toyDepth", "toyStore", "toyModel", "imgCounter", "imgCount",
            "categoryGrid", "tagGrid", "openCategory", "openTag", "newToy", "deleteForm", "deleteId",
            "deleteHidden", "deleteInput", "deletePhrase", "deleteSubmit", "cancelDelete",
            "categoryForm", "tagForm", "lightboxImg", "closeLightbox",
        ]
        for tipo in ("perfil", "verso", "lado_direito", "lado_esquerdo"):
            ids += [f"img-{tipo}", f"prev-{tipo}", f"flag-{tipo}"]
        for ident in ids:
            with self.subTest(id=ident):
                self.assertIn(f'id="{ident}"', html)
        for gancho in ('data-options-tools="categoryGrid"', 'data-options-tools="tagGrid"',
                       'data-slot="perfil"', 'data-objeto3d', 'data-edit="', 'data-delete="'):
            with self.subTest(gancho=gancho):
                self.assertIn(gancho, html)

    def test_preco_em_reais_inteiros_e_medidas_em_metros(self):
        html = self.abrir().content.decode()
        self.assertRegex(html, r'id="toyPrice"[^>]*data-mascara="moeda-valor"')
        self.assertEqual(html.count('data-mascara="medida"'), 3)

    def test_voltagem_e_categorias_sao_chips(self):
        html = self.abrir().content.decode()
        for valor in ("110V", "220V", "Bivolt", ""):
            with self.subTest(voltagem=valor):
                self.assertIn(f'type="radio" name="voltz" value="{valor}"', html)
        self.assertIn("Não se aplica", html)
        self.assertRegex(html, r'<label class="bq-opcao"><input name="categorias_brinquedos" type="checkbox"')
        self.assertRegex(html, r'<input id="toyStore" name="exibir_na_loja" type="checkbox">')

    def test_o_cartao_mostra_o_que_importa(self):
        miolo = self.conteudo(self.abrir())
        self.assertIn("Air Game Hockey", miolo)
        self.assertIn(f"#{self.air.pk}", miolo)
        self.assertIn("220V", miolo)
        self.assertIn("Altura 1 m × Largura 1,1 m × Profundidade 2,1 m", miolo)
        self.assertIn("R$ 9.800,00", miolo)
        self.assertIn("Fliperamas", miolo)
        self.assertIn("Na loja", miolo)
        # o sem preço e sem medida
        self.assertIn("Sob consulta", miolo)
        self.assertIn("Sem medidas — a proposta sai sem o tamanho", miolo)
        self.assertIn("Sem voltagem", miolo)
        self.assertIn("Só catálogo", miolo)

    def test_ver_no_site_aponta_para_o_site_e_nao_para_o_painel(self):
        resposta = self.abrir()
        enderecos = re.findall(r'<a class="bq-ver" href="([^"]+)"', resposta.content.decode())
        self.assertEqual(len(enderecos), 2)
        alvo = next(e for e in enderecos if e.endswith(f"/brinquedo/{self.air.pk}/"))
        self.assertTrue(alvo.startswith("http"))
        self.assertNotIn("interno.", alvo)
        self.assertEqual(alvo, resposta.context["site_publico"] + f"/brinquedo/{self.air.pk}/")

    def test_na_loja_sem_preco_avisa(self):
        self.casinha.exibir_na_loja = True
        self.casinha.save()
        self.assertIn("Na loja, sem preço", self.conteudo(self.abrir()))

    def test_os_numeros_do_topo(self):
        contexto = self.abrir().context
        self.assertEqual(contexto["total_brinquedos"], 2)
        self.assertEqual(contexto["total_loja"], 1)
        self.assertEqual(contexto["total_com_imagem"], 1)
        self.assertEqual(contexto["total_categorias"], 2)


class FiltrosTests(Base):
    def nomes(self, resposta):
        return [b.nome_brinquedo for b in resposta.context["brinquedos"]]

    def test_filtra_por_categoria(self):
        resposta = self.abrir(categoria=self.esportes.pk)
        self.assertEqual(self.nomes(resposta), ["Casinha Cenográfica"])
        ativo = [f for f in resposta.context["filtros_categoria"] if f["ativo"]]
        self.assertEqual([f["rotulo"] for f in ativo], ["Esportes"])

    def test_categoria_que_nao_e_numero_nao_derruba_a_tela(self):
        resposta = self.abrir(categoria="abc")
        self.assertEqual(len(self.nomes(resposta)), 2)
        self.assertEqual(resposta.context["categoria_ativa"], "todas")

    def test_filtra_na_loja_e_fora(self):
        self.assertEqual(self.nomes(self.abrir(loja="sim")), ["Air Game Hockey"])
        self.assertEqual(self.nomes(self.abrir(loja="nao")), ["Casinha Cenográfica"])

    def test_filtra_com_capa_e_sem(self):
        self.assertEqual(self.nomes(self.abrir(capa="com")), ["Air Game Hockey"])
        self.assertEqual(self.nomes(self.abrir(capa="sem")), ["Casinha Cenográfica"])

    def test_busca_pelo_nome_e_pelo_numero(self):
        self.assertEqual(self.nomes(self.abrir(q="casinha")), ["Casinha Cenográfica"])
        self.assertEqual(self.nomes(self.abrir(q=f"#{self.air.pk}")), ["Air Game Hockey"])

    def test_sem_filtro_a_busca_nao_leva_filtro_nenhum(self):
        """O primeiro desenho mandava "capa=<foto do último brinquedo>" na
        busca: o filtro e a foto do laço tinham o mesmo nome na view."""
        resposta = self.abrir()
        self.assertEqual(resposta.context["capa_ativa"], "todas")
        self.assertEqual(resposta.context["loja_ativa"], "todos")
        self.assertEqual(resposta.context["categoria_ativa"], "todas")
        busca = self.conteudo(resposta)
        busca = busca[busca.index('<form class="bq-busca"'):busca.index("</form>", busca.index('<form class="bq-busca"'))]
        self.assertNotIn('type="hidden"', busca)
        self.assertFalse(resposta.context["ha_filtro"])
        # e com o filtro de capa, ele vai junto
        self.assertIn('<input type="hidden" name="capa" value="sem">', self.conteudo(self.abrir(capa="sem")))

    def test_os_chips_guardam_os_outros_filtros(self):
        resposta = self.abrir(loja="sim", q="air")
        categorias = resposta.context["filtros_categoria"]
        fliper = next(f for f in categorias if f["rotulo"] == "Fliperamas")
        self.assertIn("loja=sim", fliper["url"])
        self.assertIn("q=air", fliper["url"])
        self.assertIn(f"categoria={self.fliperamas.pk}", fliper["url"])
        # "Todas" volta a todas as categorias sem perder a loja
        todas = categorias[0]
        self.assertEqual(todas["rotulo"], "Todas")
        self.assertNotIn("categoria=", todas["url"])
        self.assertIn("loja=sim", todas["url"])
        # a busca leva os filtros junto
        miolo = self.conteudo(resposta)
        self.assertIn('<input type="hidden" name="loja" value="sim">', miolo)
        self.assertTrue(resposta.context["ha_filtro"])
        self.assertIn("Limpar filtros", miolo)

    def test_contagens_dos_chips(self):
        contexto = self.abrir().context
        loja = {f["rotulo"]: f["total"] for f in contexto["filtros_loja"]}
        self.assertEqual(loja, {"Todos": 2, "Na loja": 1, "Fora da loja": 1})
        capa = {f["rotulo"]: f["total"] for f in contexto["filtros_capa"]}
        self.assertEqual(capa, {"Todas": 2, "Com capa": 1, "Sem capa": 1})
        cats = {f["rotulo"]: f["total"] for f in contexto["filtros_categoria"]}
        self.assertEqual(cats, {"Todas": 2, "Esportes": 1, "Fliperamas": 1})

    def test_a_paginacao_guarda_os_filtros(self):
        Brinquedos.objects.bulk_create([
            Brinquedos(nome_brinquedo=f"Brinquedo {n:02d}", descricao="x", avaliacao=5, voltz="220V")
            for n in range(20)
        ])
        resposta = self.abrir(loja="nao")
        self.assertGreater(resposta.context["page_obj"].paginator.num_pages, 1)
        self.assertIn("?loja=nao&amp;page=2", resposta.content.decode())


class SalvarEditarExcluirTests(Base):
    def setUp(self):
        super().setUp()
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        disco = FileSystemStorage(location=pasta.name)
        for campo in (Brinquedos._meta.get_field("imagem_brinquedo"), ImagemBrinquedo._meta.get_field("imagem")):
            troca = mock.patch.object(campo, "storage", disco)
            troca.start()
            self.addCleanup(troca.stop)

    def resposta_json(self, resposta, status=200):
        self.assertEqual(resposta.status_code, status, resposta.content[:300])
        return json.loads(resposta.content)

    def test_cadastrar_com_a_foto_de_frente(self):
        dados = self.resposta_json(self.salvar(
            imagem_perfil=foto(), imagem_verso=foto("verso.png"),
            valor_brinquedo="6990", altura_m="2,70", largura_m="1,00", profundidade_m="2,40",
            exibir_na_loja="on", categorias_brinquedos=[self.fliperamas.pk, self.esportes.pk],
            tags=[self.tag.pk],
        ))
        self.assertEqual(dados["status"], "sucesso")
        novo = Brinquedos.objects.get(pk=dados["id"])
        self.assertEqual(novo.nome_brinquedo, "Basquete Street")
        self.assertEqual(novo.valor_brinquedo, Decimal("6990.00"))
        self.assertEqual(novo.avaliacao, Decimal("4.90"))
        self.assertEqual(novo.voltz, "220V")
        self.assertEqual((novo.altura_m, novo.largura_m, novo.profundidade_m),
                         (Decimal("2.70"), Decimal("1.00"), Decimal("2.40")))
        self.assertTrue(novo.exibir_na_loja)
        self.assertEqual(set(novo.categorias_brinquedos.values_list("pk", flat=True)),
                         {self.fliperamas.pk, self.esportes.pk})
        self.assertEqual(list(novo.tags.values_list("pk", flat=True)), [self.tag.pk])
        self.assertTrue(novo.imagem_brinquedo)
        self.assertEqual(set(novo.imagens_brinquedo.values_list("tipo", flat=True)), {"perfil", "verso"})
        # e ele aparece na lista, com o cartão
        self.assertIn("Basquete Street", self.conteudo(self.abrir()))

    def test_sem_a_foto_de_frente_nao_salva(self):
        dados = self.resposta_json(self.salvar(), status=400)
        self.assertEqual(dados["status"], "erro")
        self.assertIn("PERFIL", dados["msg"])
        self.assertFalse(Brinquedos.objects.filter(nome_brinquedo="Basquete Street").exists())

    def test_editar_troca_os_dados_e_mantem_a_capa(self):
        dados = self.resposta_json(self.salvar(
            id=self.air.pk, nome_brinquedo="Air Game Hockey Pro", valor_brinquedo="12.500,00",
            categorias_brinquedos=[self.esportes.pk],
        ))
        self.assertEqual(dados["status"], "sucesso")
        self.air.refresh_from_db()
        self.assertEqual(self.air.nome_brinquedo, "Air Game Hockey Pro")
        self.assertEqual(self.air.valor_brinquedo, Decimal("12500.00"))
        self.assertEqual(self.air.imagem_brinquedo.name, "brinquedos/air.png")
        self.assertFalse(self.air.exibir_na_loja)  # a chave desligada desliga
        self.assertEqual(list(self.air.categorias_brinquedos.all()), [self.esportes])

    def test_preco_com_ponto_de_milhar_e_milhar(self):
        """"18.000" (Enter sem sair do campo) é dezoito mil, e não R$ 18,00."""
        self.resposta_json(self.salvar(id=self.air.pk, valor_brinquedo="18.000"))
        self.air.refresh_from_db()
        self.assertEqual(self.air.valor_brinquedo, Decimal("18000.00"))
        # sem o milhar, o ponto continua sendo decimal
        self.resposta_json(self.salvar(id=self.air.pk, valor_brinquedo="99.5"))
        self.air.refresh_from_db()
        self.assertEqual(self.air.valor_brinquedo, Decimal("99.50"))

    def test_medida_com_ponto_continua_em_metros(self):
        self.resposta_json(self.salvar(id=self.air.pk, altura_m="1.250"))
        self.air.refresh_from_db()
        self.assertEqual(self.air.altura_m, Decimal("1.25"))

    def test_preco_em_branco_e_sob_consulta(self):
        self.resposta_json(self.salvar(id=self.air.pk, valor_brinquedo=""))
        self.air.refresh_from_db()
        self.assertIsNone(self.air.valor_brinquedo)

    def test_nao_se_aplica_grava_a_voltagem_vazia(self):
        # o chip "Não se aplica" manda vazio
        self.resposta_json(self.salvar(id=self.air.pk, voltz=""))
        self.air.refresh_from_db()
        self.assertEqual(self.air.voltz, "")
        # e quem ainda mandar o texto antigo (13 letras, num campo de 10) também
        self.resposta_json(self.salvar(id=self.air.pk, voltz="Não se aplica"))
        self.air.refresh_from_db()
        self.assertEqual(self.air.voltz, "")

    def test_voltagem_maior_que_o_campo_e_recusada_com_aviso(self):
        dados = self.resposta_json(self.salvar(id=self.air.pk, voltz="110V / 220V auto"), status=400)
        self.assertIn("Voltagem", dados["msg"])
        self.air.refresh_from_db()
        self.assertEqual(self.air.voltz, "220V")

    def test_excluir_com_a_frase_de_confirmacao(self):
        frase_errada = self.client.post(ROTA, {
            "action": "delete", "id": self.casinha.pk, "confirmacao_exclusao": "CONFIRMAR EXCLUSÃO outro",
        }, **AJAX)
        self.assertEqual(frase_errada.status_code, 400)
        self.assertTrue(Brinquedos.objects.filter(pk=self.casinha.pk).exists())

        dados = self.resposta_json(self.client.post(ROTA, {
            "action": "delete", "id": self.casinha.pk,
            "confirmacao_exclusao": "CONFIRMAR EXCLUSÃO Casinha Cenográfica",
        }, **AJAX))
        self.assertEqual(dados["status"], "sucesso")
        self.assertFalse(Brinquedos.objects.filter(pk=self.casinha.pk).exists())

    def test_post_sem_javascript_continua_no_fluxo_antigo(self):
        resposta = self.client.post(ROTA, {
            "action": "save", "id": self.air.pk, "nome_brinquedo": "Air Game", "descricao": "x",
            "avaliacao": "5", "voltz": "220V",
        }, **INTERNO)
        self.assertEqual(resposta.status_code, 302)
        self.air.refresh_from_db()
        self.assertEqual(self.air.nome_brinquedo, "Air Game")


class IconesTests(TestCase):
    """Todo ícone da tela existe na fonte que o painel carrega."""

    def test_icones_da_tela_existem(self):
        css = (RAIZ.parent / "sistema_interno" / "static" / "interno" / "vendor"
               / "bootstrap-icons.min.css").read_text(encoding="utf-8")
        textos = [
            (RAIZ / "templates" / "gestao" / "brinquedos_adm.html").read_text(encoding="utf-8"),
            (RAIZ / "static" / "site" / "paginas" / "gestao-brinquedos_adm.js").read_text(encoding="utf-8"),
        ]
        usados = set()
        for texto in textos:
            usados |= set(re.findall(r"\bbi-([a-z0-9-]+)", texto))
        faltando = sorted(nome for nome in usados if f".bi-{nome}::before" not in css)
        self.assertEqual(faltando, [])
