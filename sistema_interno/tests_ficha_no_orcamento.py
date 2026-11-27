"""Com ou sem sistema de ficha no orçamento do painel e nos documentos (LEIA-ME-V10, seção 149).

O dono: "o acréscimo (...) é 999 reais e deve se chamar sistema de ficha".
Ao pôr a máquina na proposta, a equipe escolhe com ou sem; o preço COM vem
do servidor; a escolha aparece na linha do item e em todo documento, para a
fábrica saber montar.

O que estes testes protegem:

  * a busca de itens manda `ficha` (o acréscimo e o preço COM, calculados
    no servidor) só para a máquina que oferece: brinquedão, kit, máquina
    desligada pela Gestão e peça não levam; sem o acréscimo, ninguém leva;
  * salvar grava `com_moedeiro` e põe a marca no nome do item; tirar a
    escolha tira a marca; a escolha FORÇADA num brinquedão, num item sem
    máquina do catálogo ou com a opção desligada não é gravada;
  * reabrir o orçamento devolve a escolha; refazer (versão nova) a leva;
  * a proposta pública, o contrato (e o retrato dele), a lista de montagem,
    e as etiquetas dizem "com sistema de ficha" (a O.S. não nasce mais do
    orçamento e não leva máquina do catálogo: nada a marcar nela);
  * o retrato de um contrato já gerado não muda quando o item muda;
  * a migração é só de esquema; a lista de orçamentos não consulta o banco
    uma vez por item.
"""

import importlib
from decimal import Decimal

from django.db import connection, migrations
from django.test.utils import CaptureQueriesContext

from core.models import Brinquedos, CategoriasBrinquedos

from . import documento_assinatura as svc
from . import etiquetas_maquinas, moedeiro, montagem
from .models import DadosContrato, ItemOrcamento, Orcamento, UnidadeMontagem
from .tests_edicao_ate_assinar import AJAX, Base, item

MARCA = "com sistema de ficha"


def com_ficha(linha, valor=True):
    return {**linha, "com_ficha": valor}


class BaseFicha(Base):
    def setUp(self):
        super().setUp()
        self.assertEqual(DadosContrato.atual().acrescimo_moedeiro, Decimal("999.00"))
        self.brinquedao = Brinquedos.objects.create(
            nome_brinquedo="Brinquedão Sintético", descricao="x", valor_brinquedo=Decimal("85000"), avaliacao=5,
        )
        categoria = CategoriasBrinquedos.objects.create(nome_categoria="Brinquedão", imagem_categoria="c/b.png")
        self.brinquedao.categorias_brinquedos.add(categoria)
        montagem.configuracao().categorias_projeto.add(categoria)
        self.kit = Brinquedos.objects.create(
            nome_brinquedo="Kit Eletrônico Sintético", descricao="x", valor_brinquedo=Decimal("1200"),
            avaliacao=5, eh_kit=True,
        )
        from django.core.cache import cache

        cache.clear()

    def itens(self, orcamento):
        return list(ItemOrcamento.objects.filter(orcamento=orcamento).order_by("id"))

    def buscar(self, termo):
        self.client.force_login(self.vendedor)
        resposta = self.client.get("/orcamentos/itens/buscar/", {"q": termo}, **AJAX)
        self.assertEqual(resposta.status_code, 200)
        return {o["rotulo"]: o for o in resposta.json()["opcoes"]}


class BuscaDeItensTests(BaseFicha):
    def test_so_a_maquina_que_oferece_leva_a_ficha_com_o_preco_do_servidor(self):
        opcoes = self.buscar("Air Game")
        ficha = opcoes["Air Game Kids"]["ficha"]
        self.assertEqual((ficha["acrescimo"], ficha["preco_com"]), ("999,00", "2499,00"))
        self.assertEqual((ficha["rotulo_sem"], ficha["rotulo_com"]), ("Sem sistema de ficha", "Com sistema de ficha"))
        self.assertEqual(opcoes["Air Game Kids"]["preco"], "1500,00")       # o do cadastro é o SEM
        self.assertNotIn("ficha", self.buscar("Brinquedão")["Brinquedão Sintético"])
        self.assertNotIn("ficha", self.buscar("Kit Eletr")["Kit Eletrônico Sintético"])

    def test_a_palavra_da_gestao_e_o_acrescimo_vazio(self):
        Brinquedos.objects.filter(pk=self.agk.pk).update(moedeiro="nao")
        Brinquedos.objects.filter(pk=self.brinquedao.pk).update(moedeiro="sim")
        self.assertNotIn("ficha", self.buscar("Air Game")["Air Game Kids"])
        self.assertEqual(self.buscar("Brinquedão")["Brinquedão Sintético"]["ficha"]["preco_com"], "85999,00")
        DadosContrato.objects.update(acrescimo_moedeiro=None)
        moedeiro.esquecer()
        self.assertNotIn("ficha", self.buscar("Brinquedão")["Brinquedão Sintético"])


class SalvarTests(BaseFicha):
    def test_grava_a_escolha_e_poe_a_marca_no_nome(self):
        orcamento = self.aprovada(status=Orcamento.Status.RASCUNHO)
        resposta = self.salvar(orcamento, [
            com_ficha(item("Air Game Kids", 2, "2499,00", brinquedo=str(self.agk.pk))),
            item("Basquete Street", 1, "2000,00", brinquedo=str(self.basquete.pk)),
        ])
        self.assertEqual(resposta.status_code, 200, resposta.content)
        com, sem = self.itens(orcamento)
        self.assertEqual((com.descricao, com.com_moedeiro, com.valor_unitario),
                         ("Air Game Kids — com sistema de ficha", True, Decimal("2499.00")))
        self.assertEqual((sem.descricao, sem.com_moedeiro), ("Basquete Street", False))
        # a janela reabre com a escolha
        from .views_gestao import OrcamentosInnerView

        dados = OrcamentosInnerView.serializar(Orcamento.objects.get(pk=orcamento.pk))["itens"]
        self.assertEqual([i["com_ficha"] for i in dados], [True, False])
        self.assertEqual(dados[0]["opcao"]["ficha"]["preco_com"], "2499,00")

    def test_tirar_a_escolha_tira_a_marca_e_a_marca_nao_repete(self):
        orcamento = self.aprovada(status=Orcamento.Status.RASCUNHO)
        ja_marcado = item("Air Game Kids — com sistema de ficha", 1, "2499,00", brinquedo=str(self.agk.pk))
        self.salvar(orcamento, [com_ficha(ja_marcado)])
        self.assertEqual(self.itens(orcamento)[0].descricao, "Air Game Kids — com sistema de ficha")
        self.salvar(orcamento, [ja_marcado])                     # sem a escolha: a marca sai
        unico = self.itens(orcamento)[0]
        self.assertEqual((unico.descricao, unico.com_moedeiro), ("Air Game Kids", False))

    def test_a_escolha_forcada_em_quem_nao_oferece_nao_e_gravada(self):
        orcamento = self.aprovada(status=Orcamento.Status.RASCUNHO)
        Brinquedos.objects.filter(pk=self.basquete.pk).update(moedeiro="nao")
        resposta = self.salvar(orcamento, [
            com_ficha(item("Brinquedão Sintético", 1, "85999,00", brinquedo=str(self.brinquedao.pk))),
            com_ficha(item("Kit Eletrônico Sintético", 1, "1200,00", brinquedo=str(self.kit.pk))),
            com_ficha(item("Basquete Street", 1, "2000,00", brinquedo=str(self.basquete.pk))),
            com_ficha(item("Frete combinado", 1, "300,00")),
        ])
        self.assertEqual(resposta.status_code, 200, resposta.content)
        for gravado in self.itens(orcamento):
            self.assertFalse(gravado.com_moedeiro, gravado.descricao)
            self.assertNotIn(MARCA, gravado.descricao)

    def test_sem_o_acrescimo_ninguem_marca(self):
        DadosContrato.objects.update(acrescimo_moedeiro=None)
        moedeiro.esquecer()
        orcamento = self.aprovada(status=Orcamento.Status.RASCUNHO)
        self.salvar(orcamento, [com_ficha(item("Air Game Kids", 1, "1500,00", brinquedo=str(self.agk.pk)))])
        unico = self.itens(orcamento)[0]
        self.assertEqual((unico.descricao, unico.com_moedeiro), ("Air Game Kids", False))

    def test_refazer_leva_a_escolha_para_a_versao_nova(self):
        orcamento = self.aprovada(status=Orcamento.Status.AGUARDANDO_RESPOSTA)
        ItemOrcamento.objects.filter(orcamento=orcamento).update(
            com_moedeiro=True, descricao="Air Game Kids — com sistema de ficha", valor_unitario=Decimal("2499.00"),
        )
        self.client.force_login(self.vendedor)
        resposta = self.client.post("/orcamentos/", {"action": "refazer", "id": orcamento.pk, "motivo": "ajuste"}, **AJAX)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        nova = Orcamento.objects.get(orcamento_anterior=orcamento)
        unico = self.itens(nova)[0]
        self.assertEqual((unico.descricao, unico.com_moedeiro), ("Air Game Kids — com sistema de ficha", True))

    def test_a_lista_de_orcamentos_nao_consulta_por_item(self):
        self.client.force_login(self.vendedor)

        def contar():
            with CaptureQueriesContext(connection) as capturadas:
                self.assertEqual(self.client.get("/orcamentos/", HTTP_HOST="interno.testserver").status_code, 200)
            return len(capturadas)

        # em rascunho: a lista da aprovada tem outras contas (o contrato), que não são desta regra
        self.aprovada(status=Orcamento.Status.RASCUNHO)
        contar()
        poucas = contar()
        for _ in range(4):
            outro = self.aprovada(status=Orcamento.Status.RASCUNHO)
            ItemOrcamento.objects.create(orcamento=outro, descricao="Basquete Street", brinquedo=self.basquete,
                                         quantidade=1, valor_unitario=Decimal("2000"))
        contar()
        self.assertEqual(contar(), poucas, "a lista consulta o banco uma vez por item")

    def test_a_migracao_e_so_de_esquema(self):
        modulo = importlib.import_module("sistema_interno.migrations.0087_item_do_orcamento_com_sistema_de_ficha")
        self.assertTrue(all(isinstance(o, migrations.AddField) for o in modulo.Migration.operations))


class DocumentosTests(BaseFicha):
    def com_a_ficha(self):
        orcamento = self.aprovada()
        resposta = self.salvar(orcamento, [com_ficha(item("Air Game Kids", 1, "2499,00", brinquedo=str(self.agk.pk)))])
        self.assertEqual(resposta.status_code, 200, resposta.content)
        return Orcamento.objects.get(pk=orcamento.pk)

    def test_a_proposta_publica_diz_com_sistema_de_ficha(self):
        orcamento = self.com_a_ficha()
        resposta = self.client.get(orcamento.caminho_publico)
        self.assertContains(resposta, "Air Game Kids — com sistema de ficha")
        self.assertNotContains(resposta, "moedeiro")

    def test_o_contrato_e_o_retrato_dizem_e_o_retrato_nao_muda_depois(self):
        orcamento = self.com_a_ficha()
        documento = svc.gerar(orcamento, self.vendedor)
        descricoes = [i["descricao"] for i in documento.conteudo["itens"]]
        self.assertEqual(descricoes, ["Air Game Kids — com sistema de ficha"])
        token, _ = svc.emitir_link(documento)
        self.assertContains(self.client.get(f"/assinar/{token}/"), "com sistema de ficha")
        # o item muda no banco: o retrato já gerado continua como era
        antes = documento.hash_conteudo
        ItemOrcamento.objects.filter(orcamento=orcamento).update(descricao="Air Game Kids", com_moedeiro=False)
        documento.refresh_from_db()
        self.assertEqual(documento.hash_conteudo, antes)
        self.assertEqual(documento.conteudo["itens"][0]["descricao"], "Air Game Kids — com sistema de ficha")
        self.assertEqual(svc.hash_do_retrato(documento.conteudo), antes)

    def test_a_lista_de_montagem_e_a_etiqueta_dizem(self):
        orcamento = self.com_a_ficha()
        unidades = list(UnidadeMontagem.objects.filter(producao__orcamento=orcamento)
                        .exclude(situacao=UnidadeMontagem.Situacao.CANCELADA))
        self.assertEqual(len(unidades), 1)
        texto = f"{unidades[0].nome} {unidades[0].variante}"
        self.assertIn(MARCA, texto)
        maquinas = etiquetas_maquinas.ficha_do_orcamento(orcamento)["maquinas"]
        self.assertTrue(any(MARCA in str(vars(m)) for m in maquinas), [vars(m) for m in maquinas])

    def test_o_nome_antigo_nao_aparece_para_a_pessoa(self):
        self.assertEqual(moedeiro.NOME, "Sistema de ficha")
        orcamento = self.com_a_ficha()
        self.client.force_login(self.vendedor)
        html = self.client.get("/orcamentos/", HTTP_HOST="interno.testserver").content.decode().lower()
        self.assertIn("sem sistema de ficha", html)
        self.assertNotIn("moedeiro", html)
