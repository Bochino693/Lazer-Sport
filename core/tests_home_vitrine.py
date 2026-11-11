"""A home: a vitrine do quadro inicial com o 3D e as seções que só existem com conteúdo.

O que estes testes protegem:

  * seção vazia não vai para a página: sem promoção, sem combo, sem evento,
    sem projeto, sem peça, sem brinquedo, sem cliente no mapa... nem o
    título, nem a caixa "Nenhum ... disponível", nem o respiro
    (`.espacador`) que ficava sobrando entre as outras;
  * com conteúdo, cada seção volta -- e o que foi desligado no painel
    (promoção, combo) não conta como conteúdo;
  * o brinquedo com objeto 3D leva o .glb na vitrine (e a página leva o
    script do 3D e o three.js); o sem objeto, não; o objeto desligado no
    painel não volta pelo nome; sem cadastro, vale o objeto do site pelo nome;
  * a vitrine com o 3D vem do cache da home: a segunda visita não consulta
    o banco, e mexer no objeto 3D vale na visita seguinte;
  * a fábrica e os clientes ficam numa seção só (#contato), com UM mapa:
    sem cliente publicado, o mapa mostra só a fábrica (sem lista, sem
    filtro, sem a âncora "Mapa de Clientes"); com cliente, a lista sai no
    HTML para o Google ler e a âncora #clientes-section cai no mapa.
"""

from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from .cadastro_modelos import ligar_objeto_3d
from .models import (
    Brinquedos,
    BrinquedosProjeto,
    CategoriaPeca,
    CategoriasBrinquedos,
    Combos,
    Eventos,
    ObjetoTresD,
    PecasReposicao,
    Projetos,
    Promocoes,
)
from .views import modelo_3d_da_vitrine

GLB_STRIKE = "/static/site/arena/modelos/strike-kids.glb"
GLB_BRINQUEDAO = "/static/site/arena/modelos/brinquedao-modelo-2.glb"


def brinquedo(nome, **extra):
    """Um brinquedo ativo com foto (a vitrine do quadro só leva quem tem foto)."""
    dados = {
        "descricao": "Brinquedo de teste",
        "avaliacao": Decimal("4.50"),
        "voltz": "220V",
        "imagem_brinquedo": "imagens_brinquedos/foto.webp",
    }
    dados.update(extra)
    return Brinquedos.objects.create(nome_brinquedo=nome, **dados)


@override_settings(HOME_CACHE_TTL=600)
class HomeBase(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def home(self):
        resposta = self.client.get(reverse("home"))
        self.assertEqual(resposta.status_code, 200)
        return resposta


class SecoesVaziasTests(HomeBase):
    SECOES = (
        'id="brinquedos"',
        'id="categorias-section"',
        'id="promocoes-section"',
        'id="pecas-section"',
        'id="combos-section"',
        'id="eventos"',
        'id="projetos"',
        'id="clientes-section"',
    )
    CAIXAS_VAZIAS = (
        "Nenhum produto encontrado",
        "Nenhuma promoção disponível",
        "Nenhuma peça encontrada",
        "Nenhum combo disponível",
        "Nenhum evento cadastrado",
        "Não há projetos realizados",
        "Em breve, o mapa",
    )

    def test_sem_conteudo_nenhuma_secao_de_lista_aparece(self):
        resposta = self.home()
        for secao in self.SECOES:
            self.assertNotContains(resposta, secao, msg_prefix=secao)
        for caixa in self.CAIXAS_VAZIAS:
            self.assertNotContains(resposta, caixa, msg_prefix=caixa)
        # sem cliente, nada de clientes: nem lista, nem filtro, nem a camada
        # (o mapa continua, com a fábrica -- ver MapaUnicoTests)
        self.assertNotContains(resposta, 'class="ls-onde-lista')
        self.assertNotContains(resposta, 'id="filtro-cidade-cliente"')
        self.assertNotContains(resposta, 'data-onde-camada="clientes"')
        # sem a vitrine de brinquedos, nada aponta para ela
        self.assertNotContains(resposta, 'href="#brinquedos"')
        # o que não é lista continua: a arena, a manutenção e o contato
        self.assertContains(resposta, 'id="arena-home"')
        self.assertContains(resposta, 'id="manutencao"')
        self.assertContains(resposta, 'id="contato"')
        # e só sobram os respiros das duas seções que vieram antes de outra
        self.assertContains(resposta, 'class="espacador"', count=2)

    def test_promocao_e_combo_desligados_no_painel_nao_contam(self):
        alvo = brinquedo("Air Game Hockey", valor_brinquedo=Decimal("9800.00"), exibir_na_loja=True)
        Promocoes.objects.create(descricao="Air game em oferta", brinquedos=alvo, preco_promocao=Decimal("8800.00"), ativo=False)
        combo = Combos.objects.create(descricao="Combo antigo", valor_combo=Decimal("12000.00"), ativo=False)
        combo.brinquedos.add(alvo)
        resposta = self.home()
        self.assertNotContains(resposta, 'id="promocoes-section"')
        self.assertNotContains(resposta, 'id="combos-section"')
        self.assertNotContains(resposta, "Air game em oferta")
        # a faixa de recados não anuncia combo que não existe
        self.assertNotContains(resposta, "aproveite os combos")

    def test_com_conteudo_cada_secao_volta(self):
        categoria = CategoriasBrinquedos.objects.create(nome_categoria="Eletrônicos")
        alvo = brinquedo("Air Game Hockey", valor_brinquedo=Decimal("9800.00"), exibir_na_loja=True)
        alvo.categorias_brinquedos.add(categoria)
        Promocoes.objects.create(descricao="Air game em oferta", brinquedos=alvo, preco_promocao=Decimal("8800.00"))
        combo = Combos.objects.create(descricao="Combo quiosque", valor_combo=Decimal("12000.00"))
        combo.brinquedos.add(alvo)
        Eventos.objects.create(titulo="Festa no shopping", descricao="Montagem completa")
        projeto = BrinquedosProjeto.objects.create(nome_brinquedo_projeto="Arena temática", descricao="Sob medida")
        Projetos.objects.create(titulo="Arena do shopping", descricao="Do desenho à montagem", brinquedo_projetado=projeto)
        peca = PecasReposicao.objects.create(nome="Maneta do air game", descricao_peca="Original", preco_venda=Decimal("120.00"))
        peca.categoria_peca.add(CategoriaPeca.objects.create(nome_categoria_peca="Mesas"))

        resposta = self.home()
        for secao in self.SECOES[:-1]:  # o mapa depende de cliente publicado no painel
            self.assertContains(resposta, secao, msg_prefix=secao)
        for caixa in self.CAIXAS_VAZIAS:
            self.assertNotContains(resposta, caixa, msg_prefix=caixa)
        self.assertContains(resposta, 'href="#brinquedos"')
        self.assertContains(resposta, 'id="filtros-peca"')
        self.assertContains(resposta, "aproveite os combos")

    def test_filtro_de_pecas_so_com_categoria_que_tem_peca(self):
        PecasReposicao.objects.create(nome="Fonte 12V", descricao_peca="Original", preco_venda=Decimal("89.90"))
        CategoriaPeca.objects.create(nome_categoria_peca="Categoria vazia")
        resposta = self.home()
        self.assertContains(resposta, 'id="pecas-section"')
        # só "Peças em Destaque" sobraria: a barra de filtro não vem
        self.assertNotContains(resposta, 'id="filtros-peca"')
        self.assertNotContains(resposta, "Categoria vazia")

    def test_categoria_sem_brinquedo_nao_vira_chip_nem_cartao(self):
        CategoriasBrinquedos.objects.create(nome_categoria="Categoria Fantasma")
        resposta = self.home()
        # (a busca do topo, no base.html, sugere as categorias por conta própria)
        self.assertNotContains(resposta, 'class="ls-quadro-categoria"')
        self.assertNotContains(resposta, 'class="categoria-link"')
        self.assertNotContains(resposta, 'id="categorias-section"')


class VitrineComTresDTests(HomeBase):
    def test_brinquedo_com_objeto_3d_leva_o_glb_e_o_outro_nao(self):
        com_3d = brinquedo("Máquina Nova")
        ligar_objeto_3d("strike-kids", com_3d, ObjetoTresD)
        brinquedo("Air Game Hockey")

        resposta = self.home()
        self.assertContains(resposta, f'data-modelo3d="{GLB_STRIKE}', count=1)
        self.assertContains(resposta, 'data-modelo3d="', count=1)
        self.assertContains(resposta, 'class="ls-vitrine-chip3d"', count=1)
        self.assertContains(resposta, "ls-vitrine-mini--3d", count=1)
        # o script do 3D e o three.js (o mesmo endereço que o leitor importa)
        self.assertContains(resposta, "site/paginas/home-vitrine3d.js")
        self.assertContains(resposta, 'data-three="/static/vendor/three/three.module.min.js"')
        self.assertContains(resposta, 'data-gltf="/static/vendor/three/GLTFLoader.js"')

        vitrine = {item["nome"]: item["modelo_3d"] for item in resposta.context["vitrine_quadro"]}
        self.assertTrue(vitrine["Máquina Nova"].startswith(GLB_STRIKE))
        self.assertEqual(vitrine["Air Game Hockey"], "")

    def test_sem_objeto_3d_a_home_nao_leva_nada_do_3d(self):
        brinquedo("Air Game Hockey")
        resposta = self.home()
        self.assertNotContains(resposta, "data-modelo3d")
        self.assertNotContains(resposta, "home-vitrine3d.js")
        self.assertNotContains(resposta, "data-three=")
        self.assertNotContains(resposta, "ls-vitrine-chip3d")

    def test_objeto_desligado_no_painel_nao_volta_pelo_nome(self):
        # "Strike Kids" acharia o objeto do site pelo nome; desligado no
        # cadastro, tem de ficar sem 3D -- a mesma regra da página do brinquedo
        strike = brinquedo("Strike Kids")
        objeto = ligar_objeto_3d("strike-kids", strike, ObjetoTresD)
        objeto.ativo = False
        objeto.save()
        self.assertNotContains(self.home(), "data-modelo3d")

    def test_sem_cadastro_vale_o_objeto_do_site_pelo_nome(self):
        brinquedo("Brinquedão Modelo 2")
        self.assertContains(self.home(), f'data-modelo3d="{GLB_BRINQUEDAO}', count=1)

    def test_o_endereco_sai_sem_consultar_o_banco(self):
        com_3d = brinquedo("Máquina Nova")
        ligar_objeto_3d("strike-kids", com_3d, ObjetoTresD)
        sem_prefetch = Brinquedos.objects.get(pk=com_3d.pk)
        # sem o objeto trazido junto, não pergunta ao banco: fica sem 3D
        with self.assertNumQueries(0):
            self.assertEqual(modelo_3d_da_vitrine(sem_prefetch), "")
        trazido = Brinquedos.objects.prefetch_related("objeto_3d").get(pk=com_3d.pk)
        with self.assertNumQueries(0):
            self.assertTrue(modelo_3d_da_vitrine(trazido).startswith(GLB_STRIKE))


class CacheDaHomeComTresDTests(HomeBase):
    def test_segunda_visita_nao_consulta_o_banco(self):
        com_3d = brinquedo("Máquina Nova")
        ligar_objeto_3d("strike-kids", com_3d, ObjetoTresD)
        brinquedo("Air Game Hockey")
        self.home()

        with self.assertNumQueries(0):
            resposta = self.client.get(reverse("home"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, f'data-modelo3d="{GLB_STRIKE}', count=1)

    def test_desligar_o_objeto_3d_vale_na_visita_seguinte(self):
        com_3d = brinquedo("Máquina Nova")
        objeto = ligar_objeto_3d("strike-kids", com_3d, ObjetoTresD)
        self.assertContains(self.home(), "data-modelo3d", count=1)

        objeto.ativo = False
        objeto.save()  # o signal do ObjetoTresD apaga o cache da home

        self.assertNotContains(self.home(), "data-modelo3d")


class MapaUnicoTests(HomeBase):
    """A fábrica e os clientes numa seção só, com um mapa só.

    Eram duas seções seguidas, cada uma com o seu mapa (o do Google, só da
    fábrica, e o dos clientes). Agora é uma: o cartão da fábrica com os
    contatos e as rotas, as camadas e o filtro em cima do mapa, e a lista
    de clientes ao lado.
    """

    def publicar_cliente(self, nome, cidade, estado, lat, lng):
        from sistema_interno.models import Cliente, EnderecoCliente

        cliente = Cliente.objects.create(
            nome_cliente=f"Responsável {nome}",
            nome_estabelecimento=nome,
            telefone="(11) 90000-0000",
            publicar_no_mapa=True,
        )
        EnderecoCliente.objects.create(
            cliente=cliente, endereco="Rua A", cidade=cidade, estado=estado,
            latitude=lat, longitude=lng,
        )
        return cliente

    def test_sem_cliente_o_mapa_mostra_so_a_fabrica(self):
        resposta = self.home()
        html = resposta.content.decode()
        # um mapa só, o da casa (nada do mapa do Google embutido)
        self.assertContains(resposta, 'id="mapa-onde"', count=1)
        self.assertNotIn("output=embed", html)
        self.assertNotIn('id="mapa-clientes"', html)
        # os dados do mapa saem com a fábrica, e a camada dela aparece
        self.assertContains(resposta, 'id="dados-mapa-onde"', count=1)
        self.assertContains(resposta, '"tipo": "fabrica"')
        self.assertContains(resposta, 'data-onde-camada="fabrica"')
        # o cartão da fábrica: endereço, contatos e rotas
        self.assertContains(resposta, "Rua São Roque de Minas, 104")
        self.assertContains(resposta, 'href="https://wa.me/5511960563135"')
        self.assertContains(resposta, 'href="mailto:comercial@lazersport.com.br"')
        self.assertContains(resposta, "Rota no Google Maps")
        self.assertContains(resposta, "Abrir no Waze")
        # e a âncora "Mapa de Clientes" só existe com cliente
        self.assertNotContains(resposta, 'id="clientes-section"')

    def test_com_cliente_a_lista_e_a_ancora_aparecem_e_o_mapa_continua_um(self):
        self.publicar_cliente("Buffet Alegria", "Salvador", "BA", "-12.9777", "-38.5016")
        self.publicar_cliente("Rio Fun Park", "Rio de Janeiro", "RJ", "-22.9068", "-43.1729")

        resposta = self.home()
        self.assertContains(resposta, 'id="contato"', count=1)
        self.assertContains(resposta, 'id="clientes-section"', count=1)
        self.assertContains(resposta, 'id="mapa-onde"', count=1)
        self.assertNotContains(resposta, "output=embed")
        # a camada de clientes com a contagem, e o filtro por cidade
        self.assertContains(resposta, 'data-onde-camada="clientes"')
        self.assertContains(resposta, 'id="filtro-cidade-cliente"')
        # a lista que o Google lê, cada nome levando ao alfinete dele
        self.assertContains(resposta, 'data-onde-cliente="0"')
        self.assertContains(resposta, 'data-onde-cliente="1"')
        self.assertContains(resposta, "<strong>Lazer &amp; Sport</strong> em Salvador/BA")
        self.assertContains(resposta, "Buffet Alegria")
        # o alfinete leva a logo pequena da casa, não a de 1024 px
        self.assertContains(resposta, "images/logo-96.png")
        self.assertNotContains(resposta, '"logo": "/static/images/logoofi.png"')
        # o comportamento do mapa vem do arquivo próprio, carregado sob demanda
        self.assertContains(resposta, "site/paginas/home-mapa.js")


class CardInteiroAbreOItemTests(HomeBase):
    """Combos, promoções e cards da loja: tocar em qualquer lugar do card abre a página do item.

    O card leva `data-card-link` com o endereço da página (a mesma do
    "Detalhes"); o site/ls-card-clicavel.js, carregado em toda página, faz o
    resto e deixa os controles de dentro (o "Adicionar", a estrela) com o
    clique deles.
    """

    def _ofertas(self):
        alvo = brinquedo("Air Game Hockey", valor_brinquedo=Decimal("9800.00"), exibir_na_loja=True)
        promo = Promocoes.objects.create(descricao="Air game em oferta", brinquedos=alvo, preco_promocao=Decimal("8800.00"))
        combo = Combos.objects.create(descricao="Combo quiosque", valor_combo=Decimal("12000.00"))
        combo.brinquedos.add(alvo)
        return promo, combo

    def test_na_home_o_card_do_combo_e_da_promocao_abre_a_pagina_deles(self):
        promo, combo = self._ofertas()
        resposta = self.home()
        self.assertContains(resposta, f'data-card-link="{reverse("promocao", args=[promo.pk])}#promocao-pagina"')
        self.assertContains(resposta, f'data-card-link="{reverse("combo", args=[combo.pk])}#combo-pagina"')
        self.assertContains(resposta, "ls-card-clicavel.js")
        # o "Adicionar" continua sendo um botão (o clique dele não abre a página)
        self.assertContains(resposta, "adicionarAoCarrinho('combo', %d)" % combo.pk)
        # as páginas existem e abrem, como as de um produto
        self.assertEqual(self.client.get(reverse("promocao", args=[promo.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("combo", args=[combo.pk])).status_code, 200)

    def test_na_loja_todo_card_abre_o_item(self):
        promo, combo = self._ofertas()
        cache.clear()
        resposta = self.client.get(reverse("loja"))
        self.assertEqual(resposta.status_code, 200)
        html = resposta.content.decode()
        self.assertEqual(html.count("data-card-link="), html.count('class="loja-card"'))
        self.assertIn(f'data-card-link="{reverse("combo", args=[combo.pk])}', html)

    def test_o_script_deixa_os_controles_com_o_clique_deles(self):
        from django.contrib.staticfiles import finders

        with open(finders.find("site/ls-card-clicavel.js"), encoding="utf-8") as arquivo:
            script = arquivo.read()
        for controle in ("a,", "button", "input", "[data-card-ignorar]"):
            self.assertIn(controle, script)
        self.assertIn("auxclick", script)  # o botão do meio abre em outra aba
