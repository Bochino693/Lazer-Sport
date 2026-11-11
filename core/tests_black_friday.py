"""Black Friday 2026: promoção com validade, condições, sem preço e a arte.

O que estes testes protegem:

  * a promoção some do site sozinha depois do último dia (`valida_ate`): da
    home, da loja, da API, da busca, do carrinho e da divulgação; a página
    dela continua no ar dizendo que terminou;
  * a promoção sem preço (brinde, "leve 4") mostra a condição e "Pedir
    orçamento" (WhatsApp) e não vai para o carrinho;
  * o preço "de" da arte vale no lugar da soma de tabela;
  * o painel salva validade, condições, preço "de" (22.990 é vinte e dois
    mil) e sem preço;
  * o cadastro da Black Friday (core/black_friday.py) cria os produtos que
    faltam e as 11 promoções, sem duplicar ao rodar de novo, e não cria as
    promoções depois da validade; a migração não faz nada fora do Render;
  * as imagens estão no repositório: 11 artes (sem as faixas desfocadas), 11
    cards quadrados e as fotos dos produtos novos.
"""

import datetime
import tempfile
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.storage import FileSystemStorage
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from . import black_friday
from .models import Brinquedos, CategoriasBrinquedos, ClientePerfil, ImagemBrinquedo, Promocoes

INTERNO = {"HTTP_HOST": "interno.testserver"}
HOJE = timezone.localdate()
ONTEM = HOJE - datetime.timedelta(days=1)
AMANHA = HOJE + datetime.timedelta(days=1)


def _brinquedo(nome, valor=None):
    return Brinquedos.objects.create(
        nome_brinquedo=nome, descricao=f"Descrição do {nome}", imagem_brinquedo=f"brinquedos/{nome}.jpg",
        avaliacao=Decimal("4.8"), valor_brinquedo=Decimal(valor) if valor else None, voltz="220V",
    )


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.air = _brinquedo("Air Game Kids", "9000")
        self.basquete = _brinquedo("Basquete Duplo", "18000")

    def tearDown(self):
        cache.clear()

    def promo(self, **campos):
        dados = {"descricao": "Black Friday: Air Game Kids", "brinquedos": self.air,
                 "preco_promocao": Decimal("4990"), "ativo": True, "valida_ate": AMANHA}
        dados.update(campos)
        return Promocoes.objects.create(**dados)


class ModeloTests(Base):
    def test_vigentes_respeita_o_ultimo_dia(self):
        hoje = self.promo(descricao="Hoje", valida_ate=HOJE)
        sem_data = self.promo(descricao="Sem data", valida_ate=None)
        self.promo(descricao="Ontem", valida_ate=ONTEM)
        self.promo(descricao="Desligada", ativo=False)

        self.assertEqual(set(Promocoes.objects.vigentes()), {hoje, sem_data})
        self.assertTrue(hoje.vigente)
        self.assertFalse(Promocoes.objects.get(descricao="Ontem").vigente)

    def test_preco_de_da_arte_e_as_condicoes(self):
        promocao = self.promo(preco_promocao=Decimal("19990"), preco_de=Decimal("22990"),
                              condicoes="Em até 10x sem juros\n\n - À vista no PIX ")
        self.assertEqual(promocao.preco_tabela, Decimal("22990"))
        self.assertEqual(promocao.desconto_percentual, 13)
        self.assertEqual(promocao.lista_condicoes, ["Em até 10x sem juros", "À vista no PIX"])


class SiteTests(Base):
    def test_home_mostra_so_as_vigentes(self):
        self.promo(descricao="Oferta que vale")
        self.promo(descricao="Oferta vencida", valida_ate=ONTEM)
        resposta = self.client.get("/")
        self.assertContains(resposta, "Oferta que vale")
        self.assertNotContains(resposta, "Oferta vencida")

    def test_sem_preco_mostra_a_condicao_e_nao_o_carrinho(self):
        promocao = self.promo(descricao="Leve 4", preco_promocao=None,
                              condicoes="Na compra de 3 cenográficos, leve 4!\nParcelamos em até 10x")
        home = self.client.get("/").content.decode()
        cartao = home.split(f"{reverse('promocao', args=[promocao.pk])}")[1].split("</article>")[0]
        self.assertIn("Na compra de 3 cenográficos, leve 4!", cartao)
        self.assertNotIn("adicionarAoCarrinho('promocao'", cartao)

        pagina = self.client.get(reverse("promocao", args=[promocao.pk]))
        self.assertContains(pagina, "Pedir orçamento")
        self.assertContains(pagina, "wa.me/")
        self.assertContains(pagina, "Parcelamos em até 10x")
        self.assertNotContains(pagina, "adicionarAoCarrinho('promocao'")

    def test_pagina_mostra_a_arte_a_validade_e_o_de(self):
        promocao = self.promo(preco_promocao=Decimal("19990"), preco_de=Decimal("22990"),
                              arte_promocao="promocoes/artes/arte.webp", condicoes="Em até 10x sem juros")
        pagina = self.client.get(reverse("promocao", args=[promocao.pk]))
        self.assertContains(pagina, 'class="promo-arte"')
        self.assertContains(pagina, f"Válida até {AMANHA:%d/%m/%Y}")
        self.assertContains(pagina, "22.990,00")
        self.assertContains(pagina, "19.990,00")
        self.assertContains(pagina, "Em até 10x sem juros")
        self.assertContains(pagina, "adicionarAoCarrinho('promocao'")

    def test_pagina_da_vencida_avisa_e_nao_vende(self):
        promocao = self.promo(valida_ate=ONTEM)
        pagina = self.client.get(reverse("promocao", args=[promocao.pk]))
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, "Esta promoção terminou")
        self.assertNotContains(pagina, "adicionarAoCarrinho('promocao'")

    def test_carrinho_recusa_vencida_e_sem_preco(self):
        usuario = User.objects.create_user("cliente", "c@exemplo.com", "x")
        perfil, _ = ClientePerfil.objects.get_or_create(user=usuario)
        perfil.nome_completo = "Cliente Teste"
        perfil.telefone = "11999998888"  # sem telefone, o site pede o telefone antes
        perfil.save()
        self.client.force_login(usuario)
        vencida = self.promo(descricao="Vencida", valida_ate=ONTEM)
        sem_preco = self.promo(descricao="Brinde", preco_promocao=None, condicoes="Ganhe um kit")
        valendo = self.promo(descricao="Valendo")
        url = lambda p: reverse("adicionar_ao_carrinho", args=["promocao", p.pk])  # noqa: E731
        self.assertEqual(self.client.post(url(vencida)).status_code, 404)
        self.assertEqual(self.client.post(url(sem_preco)).status_code, 404)
        self.assertEqual(self.client.post(url(valendo)).status_code, 200)

    def test_api_e_divulgacao(self):
        from sistema_interno.campanhas import ErroCampanha, conteudo_do_objeto
        from sistema_interno.models import CampanhaDivulgacao

        valendo = self.promo(descricao="Valendo", condicoes="Em até 10x sem juros")
        vencida = self.promo(descricao="Vencida", valida_ate=ONTEM)
        dados = self.client.get("/api/v1/promocoes/").json()
        nomes = [p.get("descricao") for p in dados.get("results", dados)]
        self.assertIn("Valendo", nomes)
        self.assertNotIn("Vencida", nomes)

        conteudo = conteudo_do_objeto(CampanhaDivulgacao.Tipo.PROMOCAO, valendo.pk)
        self.assertIn("Em até 10x sem juros.", conteudo.mensagem)
        self.assertIn(f"Válida até {AMANHA:%d/%m/%Y}", conteudo.mensagem)
        with self.assertRaises(ErroCampanha):
            conteudo_do_objeto(CampanhaDivulgacao.Tipo.PROMOCAO, vencida.pk)


class PainelTests(Base):
    def setUp(self):
        super().setUp()
        self.equipe = User.objects.create_superuser("criacao", "criacao@exemplo.com", "x")

    def painel(self, dados):
        self.client.force_login(self.equipe)
        return self.client.post("/site/promocoes/", dados, **INTERNO)

    def test_salva_validade_condicoes_e_preco_de(self):
        self.painel({
            "acao": "criar", "descricao": "Kit", "brinquedos": [str(self.air.pk), str(self.basquete.pk)],
            "preco_promocao": "19990.00", "preco_de": "22.990", "valida_ate": "2026-11-13",
            "condicoes": "Em até 10x sem juros\r\n\r\nÀ vista com 7%", "ativo": "on",
        })
        promocao = Promocoes.objects.get()
        self.assertEqual(promocao.preco_de, Decimal("22990.00"))
        self.assertEqual(promocao.valida_ate, datetime.date(2026, 11, 13))
        self.assertEqual(promocao.condicoes, "Em até 10x sem juros\nÀ vista com 7%")

    def test_sem_preco_precisa_de_condicao(self):
        base = {"acao": "criar", "descricao": "Brinde", "brinquedos": [str(self.air.pk)],
                "sem_preco": "on", "ativo": "on"}
        self.painel(base)
        self.assertFalse(Promocoes.objects.exists())
        self.painel({**base, "condicoes": "Ganhe um kit de mesinha kids"})
        promocao = Promocoes.objects.get()
        self.assertIsNone(promocao.preco_promocao)
        self.assertTrue(promocao.vigente)

    def test_tela_traz_os_campos_novos(self):
        self.promo(valida_ate=ONTEM)
        self.client.force_login(self.equipe)
        html = self.client.get("/site/promocoes/", **INTERNO).content.decode()
        for trecho in ('name="sem_preco"', 'name="preco_de"', 'name="valida_ate"', 'name="condicoes"',
                       'name="arte_promocao"', "Terminou em"):
            self.assertIn(trecho, html)


def _discos(pasta):
    storage = FileSystemStorage(location=pasta)
    campos = [
        (Brinquedos, "imagem_brinquedo"), (ImagemBrinquedo, "imagem"), (Promocoes, "imagem_promocao"),
        (Promocoes, "arte_promocao"), (CategoriasBrinquedos, "imagem_categoria"),
    ]
    return [mock.patch.object(m._meta.get_field(c), "storage", storage) for m, c in campos]


class CadastroTests(TestCase):
    def setUp(self):
        for nome in ("Air Game Kids", "Strike Kids", "Nervo Teste", "Boliche Virtual", "Air Game Home"):
            _brinquedo(nome)
        CategoriasBrinquedos.objects.create(nome_categoria="Competitivos", imagem_categoria="categorias/c.jpg")
        self.pasta = tempfile.TemporaryDirectory()
        self.patches = _discos(self.pasta.name)
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.pasta.cleanup()

    def rodar(self, **extra):
        avisos = []
        black_friday.rodar(Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, Promocoes,
                           hoje=datetime.date(2026, 11, 11), avisar=avisos.append, **extra)
        return avisos

    def test_cria_os_produtos_e_as_11_promocoes_sem_duplicar(self):
        self.rodar()
        for nome in ("Basquete Duplo", "Basquete Kids", "Air Rock", "Kid Play", "Cozinha Infantil",
                     "Oficina de Engenharia", "Salão de Beleza", "Brinquedão Modelo 5"):
            brinquedo = Brinquedos.objects.get(nome_brinquedo=nome)
            self.assertTrue(brinquedo.imagem_brinquedo, nome)
            self.assertFalse(brinquedo.exibir_na_loja)
        casinhas = CategoriasBrinquedos.objects.get(nome_categoria=black_friday.CATEGORIA_CASINHAS)
        self.assertEqual(casinhas.brinquedos.count() if hasattr(casinhas, "brinquedos") else
                         Brinquedos.objects.filter(categorias_brinquedos=casinhas).count(), 3)
        self.assertEqual(Promocoes.objects.count(), 11)
        self.assertTrue(all(p.imagem_promocao and p.arte_promocao for p in Promocoes.objects.all()))
        self.assertTrue(all(p.valida_ate == datetime.date(2026, 11, 13) for p in Promocoes.objects.all()))

        kit = Promocoes.objects.get(descricao__startswith="Kit Black Friday")
        self.assertEqual([b.nome_brinquedo for b in kit.todos_brinquedos],
                         ["Strike Kids", "Air Game Kids", "Basquete Kids"])
        self.assertEqual(kit.preco_de, Decimal("22990.00"))
        leve4 = Promocoes.objects.get(descricao__contains="leve 4")
        self.assertIsNone(leve4.preco_promocao)
        # a primeira da lista é a mais nova (o site mostra as mais novas antes)
        self.assertEqual(Promocoes.objects.order_by("-id").first().descricao, black_friday.PROMOCOES[0]["descricao"])

        arquivos = {p.imagem_promocao.name for p in Promocoes.objects.all()}
        self.rodar()
        self.assertEqual(Promocoes.objects.count(), 11)
        self.assertEqual(Brinquedos.objects.filter(nome_brinquedo="Basquete Duplo").count(), 1)
        self.assertEqual({p.imagem_promocao.name for p in Promocoes.objects.all()}, arquivos)

    def test_depois_da_validade_nao_cria_promocao(self):
        avisos = []
        black_friday.rodar(Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, Promocoes,
                           hoje=datetime.date(2026, 11, 14), avisar=avisos.append)
        self.assertFalse(Promocoes.objects.exists())
        self.assertTrue(Brinquedos.objects.filter(nome_brinquedo="Air Rock").exists())
        self.assertTrue(any("terminou" in a for a in avisos))

    def test_brinquedo_que_falta_deixa_a_promocao_para_depois(self):
        Brinquedos.objects.filter(nome_brinquedo="Nervo Teste").delete()
        avisos = self.rodar()
        self.assertFalse(Promocoes.objects.filter(descricao="Black Friday: Nervo Teste").exists())
        self.assertTrue(any("Nervo Teste" in a and "falta" in a for a in avisos))
        self.assertEqual(Promocoes.objects.count(), 9)  # a do Nervo Teste e o Kit Sucesso esperam

    @override_settings(IS_RENDER=False)
    def test_migracao_nao_faz_nada_fora_do_render(self):
        from django.apps import apps

        black_friday.subir_no_deploy(apps, None)
        self.assertFalse(Promocoes.objects.exists())


class ImagensTests(TestCase):
    def test_artes_cards_e_produtos_no_repositorio(self):
        pasta = black_friday.PASTA
        for n in range(1, 12):
            with Image.open(pasta / f"card-{n:02d}.webp") as card:
                self.assertEqual(card.width, card.height)
            with Image.open(pasta / f"arte-{n:02d}.webp") as arte:
                self.assertGreater(arte.height, arte.width * 0.9)
        for dados in black_friday.PRODUTOS:
            for arquivo in dados["fotos"]:
                self.assertTrue((pasta / arquivo).exists(), arquivo)
        for arquivo in Path(pasta).iterdir():
            self.assertLess(arquivo.stat().st_size, 400 * 1024, arquivo.name)

    def test_as_tres_artes_sem_as_faixas_desfocadas(self):
        # as artes 8, 9 e 10 vieram com faixas desfocadas em cima e embaixo: o cartaz é só o meio
        for n in (8, 9, 10):
            with Image.open(black_friday.PASTA / f"arte-{n:02d}.webp") as arte:
                cinza = arte.convert("L")
                for y0 in (0, arte.height - 24):
                    faixa = cinza.crop((0, y0, arte.width, y0 + 24))
                    pontos = list(faixa.getdata())
                    w = faixa.width
                    # média do salto entre vizinhos: a faixa desfocada dava 0,1 a 0,3; o cartaz, acima de 0,6
                    energia = sum(abs(pontos[i] - pontos[i + 1]) for i in range(len(pontos) - 1) if (i + 1) % w) / len(pontos)
                    self.assertGreater(energia, 0.45, f"arte {n}: a borda ({y0}) ainda parece desfocada")
