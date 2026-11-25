"""Apagar o cliente com tudo o que é dele (LEIA-ME-V10, seção 141).

O pedido do dono: o cadastro de um cliente "deve ser apagado inclusive, com
seus pedidos e também os outros objetos associados".

O que estes testes protegem (dados SINTÉTICOS, nada de cliente real):

  * a conta do que vai junto e do que fica, antes de confirmar;
  * a exclusão completa leva os orçamentos (todas as versões), o aceite,
    os documentos de assinatura, a venda, a produção da lista de montagem,
    o histórico, as O.S. (as do cliente e as nascidas dos orçamentos dele)
    e os endereços -- sem deixar linha solta;
  * NÃO leva o que não é só dele: outro cliente, o cliente atendido por
    ele, a movimentação de estoque (fica, sem o destinatário), a conta do
    site, a entrega de campanha;
  * só o superusuário: a Gestão e Vendas não recebem a conta nem apagam,
    também por POST direto; sem a palavra CONFIRMAR nada sai;
  * o rastro (`ExclusaoRegistrada`) diz o que foi junto;
  * a exclusão antiga (só o cadastro) continua como era.
"""

from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from . import documento_assinatura as svc
from . import documento_servico as servico
from . import exclusao_cliente
from .models import (
    AceiteOrcamento,
    AtividadeOrcamento,
    Cliente,
    DocumentoAssinatura,
    EnderecoCliente,
    EstoqueMaterial,
    ExclusaoRegistrada,
    ItemOrcamento,
    ItemOrdemServico,
    Material,
    MovimentoEstoque,
    Orcamento,
    OrdemServico,
    ProducaoOrigem,
    TipoMaterial,
)
from .permissoes import atribuir_funcoes
from .tests_documento_assinatura import CPF_DO_CLIENTE, png_de_assinatura, preencher_dados_do_contrato
from .utils import ErroDeFormulario

from core.models import Venda

AJAX = {"HTTP_HOST": "interno.testserver", "HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
INTERNO = {"HTTP_HOST": "interno.testserver"}
RAIZ = Path(__file__).resolve().parent


class BaseExclusao(TestCase):
    def setUp(self):
        preencher_dados_do_contrato()
        self.dono = User.objects.create_superuser("dono-excl", "d@exemplo.invalid", "senha-de-teste")
        self.gestao = self.usuario("gestao-excl", "gestao")
        self.vendedor = self.usuario("vendedor-excl", "vendas")
        self.tecnico = self.usuario("tecnico-excl", "producao")
        self.conta_do_site = User.objects.create_user("conta-site-excl", "c@exemplo.invalid", "senha-de-teste")

        # ---------------- o cliente que vai sair, com tudo
        self.cliente = Cliente.objects.create(
            nome_cliente="Cliente Sintético Completo", documento=CPF_DO_CLIENTE, telefone="(11) 97777-6655",
        )
        EnderecoCliente.objects.create(
            cliente=self.cliente, cep="13000-000", endereco="Rua das Palmeiras Fictícias", numero="123",
            bairro="Jardim Exemplo", cidade="Campinas", estado="SP",
        )
        # a proposta em duas versões; a v1 ficou SEM o vínculo (só a corrente a liga ao cliente)
        self.v1 = self.orcamento(None, status=Orcamento.Status.SUBSTITUIDO, pago=False)
        self.v2 = self.orcamento(self.cliente, orcamento_anterior=self.v1, conta=self.conta_do_site)
        self.aceite = AceiteOrcamento.objects.create(
            orcamento=self.v2, assinante_nome="Maria Exemplo", assinante_documento="52998224725",
            proposta_hash="x" * 64, ip_hash="y" * 64, navegador_hash="z" * 64,
        )
        self.documento = svc.gerar(self.v2, self.vendedor)
        svc.assinar(
            self.documento, nome="Maria Exemplo da Silva", cpf_cnpj=CPF_DO_CLIENTE,
            png=svc.png_da_assinatura(png_de_assinatura()), ip="200.150.10.20", navegador="x",
        )
        self.v2.refresh_from_db()
        self.venda_id = self.v2.venda_id
        self.producao = ProducaoOrigem.objects.create(orcamento=self.v2, chegada=timezone.now())
        # a O.S. do cliente e a O.S. que nasceu do orçamento (sem o vínculo do cliente)
        self.os_do_cliente = self.ordem(cliente=self.cliente)
        self.os_do_orcamento = self.ordem(cliente=None, orcamento=self.v2)
        self.documento_os = servico.gerar_da_ordem(self.os_do_cliente, self.tecnico)
        # o que NÃO é só dele
        self.atendido = Cliente.objects.create(nome_cliente="Atendido Sintético", parceiro=self.cliente)
        material = Material.objects.create(
            nome_material="Lona sintética de teste", tipo_material=TipoMaterial.objects.create(descricao="Lona"),
        )
        self.estoque = EstoqueMaterial.objects.create(
            material=material, descricao_local="Prateleira de teste", quantidade=7, preco_fornecedor=Decimal("10.00"),
        )
        self.movimento = MovimentoEstoque.objects.create(
            estoque=self.estoque, cliente=self.cliente, tipo=MovimentoEstoque.Tipo.SAIDA,
            quantidade=3, quantidade_resultante=7, motivo="Reposição",
        )

        # ---------------- o OUTRO cliente, que não pode ser tocado
        self.outro = Cliente.objects.create(nome_cliente="Outro Cliente Sintético", telefone="(11) 96666-0000")
        self.orcamento_do_outro = self.orcamento(self.outro)
        self.documento_do_outro = svc.gerar(self.orcamento_do_outro, self.vendedor)
        self.os_do_outro = self.ordem(cliente=self.outro)

    @staticmethod
    def usuario(username, *funcoes):
        user = User.objects.create_user(username=username, password="senha-de-teste")
        atribuir_funcoes(user, funcoes)
        return user

    def orcamento(self, cliente, pago=True, **campos):
        padrao = {
            "cliente": cliente,
            "nome_cliente": "Cliente Sintético",
            "whatsapp_cliente": "(11) 97777-6655",
            "status": Orcamento.Status.APROVADO,
            "forma_pagamento": "Pix",
            "forma_envio": "Entrega Lazer & Sport",
            "responsavel": self.vendedor,
        }
        padrao.update(campos)
        orcamento = Orcamento.objects.create(**padrao)
        ItemOrcamento.objects.create(
            orcamento=orcamento, descricao="Cama elástica 3 m", quantidade=1, valor_unitario=Decimal("1500.00"),
        )
        if pago:
            orcamento.registrar_pagamento(orcamento.total)
        return orcamento

    def ordem(self, **campos):
        ordem = OrdemServico.objects.create(
            nome_cliente="Cliente Sintético", whatsapp_cliente="(11) 98888-7766",
            tipo=OrdemServico.Tipo.MANUTENCAO, status=OrdemServico.Status.AGENDADA,
            equipamento="Cama elástica 3,05 m", defeito_relatado="Lona rasgada.",
            endereco_servico="Rua Inventada, 100", agendada_para=timezone.now() + timedelta(days=3),
            responsavel=self.tecnico, tecnico=self.tecnico, **campos,
        )
        ItemOrdemServico.objects.create(
            ordem=ordem, tipo=ItemOrdemServico.Tipo.SERVICO, descricao="Troca da lona",
            quantidade=1, valor_unitario=Decimal("350.00"),
        )
        return ordem

    def postar(self, usuario, **dados):
        self.client.force_login(usuario)
        return self.client.post("/clientes/", dados, **AJAX)

    def apagar_tudo(self, usuario=None, **troca):
        dados = {
            "action": "delete", "id": self.cliente.pk, "alcance": "tudo",
            "confirmacao_exclusao": "CONFIRMAR", "motivo_exclusao": "Cadastro de teste.",
        }
        dados.update(troca)
        return self.postar(usuario or self.dono, **dados)

    def assert_nada_saiu(self):
        self.assertTrue(Cliente.objects.filter(pk=self.cliente.pk).exists())
        self.assertEqual(Orcamento.objects.filter(pk__in=[self.v1.pk, self.v2.pk]).count(), 2)
        self.assertEqual(OrdemServico.objects.filter(pk__in=[self.os_do_cliente.pk, self.os_do_orcamento.pk]).count(), 2)
        self.assertTrue(DocumentoAssinatura.objects.filter(pk=self.documento.pk).exists())
        self.assertTrue(Venda.objects.filter(pk=self.venda_id).exists())
        self.assertFalse(ExclusaoRegistrada.objects.exists())


# ======================================================================
# A CONTA, ANTES DE CONFIRMAR
# ======================================================================
class LevantamentoTests(BaseExclusao):
    def test_a_conta_do_que_vai_junto_e_do_que_fica(self):
        conta = exclusao_cliente.levantar(self.cliente)
        self.assertEqual(conta.orcamentos, sorted([self.v1.pk, self.v2.pk]))  # a v1 entra pela corrente
        self.assertEqual(conta.ordens, sorted([self.os_do_cliente.pk, self.os_do_orcamento.pk]))
        self.assertEqual((conta.documentos, conta.documentos_assinados), (2, 1))
        self.assertEqual(conta.aceites, 1)
        self.assertEqual(conta.vendas, [self.venda_id])
        self.assertEqual(conta.producoes, 1)
        self.assertEqual(conta.enderecos, 1)
        self.assertEqual(conta.pagos, 1)
        self.assertEqual(
            (conta.movimentos_estoque, conta.clientes_atendidos, conta.contas_do_site), (1, 1, 1),
        )
        vai = {linha["chave"]: linha["quantos"] for linha in conta.vai_junto}
        self.assertEqual(
            vai, {"orcamentos": 2, "ordens": 2, "documentos": 2, "aceites": 1, "vendas": 1, "producoes": 1, "enderecos": 1},
        )
        self.assertEqual(
            {linha["chave"] for linha in conta.fica}, {"movimentos_estoque", "clientes_atendidos", "contas_do_site"},
        )

    def test_o_superusuario_recebe_a_conta_pela_tela(self):
        resposta = self.postar(self.dono, action="previa_exclusao", id=self.cliente.pk)
        self.assertEqual(resposta.status_code, 200)
        corpo = resposta.json()
        self.assertEqual(corpo["status"], "sucesso")
        self.assertTrue(corpo["tem_o_que_levar"])
        self.assertEqual(corpo["assinados"], 1)
        self.assertEqual(corpo["pagos"], 1)
        self.assertIn({"chave": "orcamentos", "quantos": 2, "rotulo": "orçamentos",
                       "nota": "todas as versões, com itens, envios e histórico"}, corpo["vai_junto"])
        self.assert_nada_saiu()  # contar não apaga

    def test_cliente_sem_nada_nao_tem_o_que_levar(self):
        limpo = Cliente.objects.create(nome_cliente="Cliente Limpo Sintético")
        corpo = self.postar(self.dono, action="previa_exclusao", id=limpo.pk).json()
        self.assertFalse(corpo["tem_o_que_levar"])
        self.assertEqual(corpo["vai_junto"], [])

    def test_quem_nao_e_superusuario_nao_recebe_a_conta(self):
        for usuario in (self.gestao, self.vendedor):
            with self.subTest(usuario=usuario.username):
                resposta = self.postar(usuario, action="previa_exclusao", id=self.cliente.pk)
                self.assertEqual(resposta.status_code, 403)
                self.assertNotIn("vai_junto", resposta.json())


# ======================================================================
# APAGAR COM TUDO
# ======================================================================
class ApagarComTudoTests(BaseExclusao):
    def test_leva_tudo_o_que_e_dele_e_nao_deixa_linha_solta(self):
        atividades = AtividadeOrcamento.objects.filter(orcamento__in=[self.v1, self.v2]).count()
        self.assertGreater(atividades, 0)
        resposta = self.apagar_tudo()
        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertEqual(resposta.json()["status"], "sucesso")
        self.assertIn("excluído com tudo o que era dele", resposta.json()["msg"])

        self.assertFalse(Cliente.objects.filter(pk=self.cliente.pk).exists())
        self.assertFalse(Orcamento.objects.filter(pk__in=[self.v1.pk, self.v2.pk]).exists())
        self.assertFalse(ItemOrcamento.objects.filter(orcamento_id__in=[self.v1.pk, self.v2.pk]).exists())
        self.assertFalse(AceiteOrcamento.objects.filter(pk=self.aceite.pk).exists())
        self.assertFalse(DocumentoAssinatura.objects.filter(pk__in=[self.documento.pk, self.documento_os.pk]).exists())
        self.assertFalse(Venda.objects.filter(pk=self.venda_id).exists())
        self.assertFalse(ProducaoOrigem.objects.filter(pk=self.producao.pk).exists())
        self.assertFalse(OrdemServico.objects.filter(pk__in=[self.os_do_cliente.pk, self.os_do_orcamento.pk]).exists())
        self.assertFalse(ItemOrdemServico.objects.filter(ordem_id__in=[self.os_do_cliente.pk, self.os_do_orcamento.pk]).exists())
        self.assertFalse(EnderecoCliente.objects.filter(cliente_id=self.cliente.pk).exists())
        # nenhuma linha de histórico solta (o SET_NULL deixaria "orçamento: nenhum")
        self.assertFalse(AtividadeOrcamento.objects.filter(orcamento__isnull=True).exists())
        self.assertFalse(DocumentoAssinatura.objects.filter(orcamento__isnull=True, ordem_servico__isnull=True).exists())

    def test_nao_leva_o_que_nao_e_so_dele(self):
        self.apagar_tudo()
        # o outro cliente, inteiro
        self.assertTrue(Cliente.objects.filter(pk=self.outro.pk).exists())
        self.assertTrue(Orcamento.objects.filter(pk=self.orcamento_do_outro.pk, cliente=self.outro).exists())
        self.assertTrue(DocumentoAssinatura.objects.filter(pk=self.documento_do_outro.pk).exists())
        self.assertTrue(OrdemServico.objects.filter(pk=self.os_do_outro.pk, cliente=self.outro).exists())
        self.assertTrue(Venda.objects.filter(pk=self.orcamento_do_outro.venda_id).exists())
        # o cliente atendido fica, sem o buffet
        self.atendido.refresh_from_db()
        self.assertIsNone(self.atendido.parceiro_id)
        # a conta do site fica
        self.assertTrue(User.objects.filter(pk=self.conta_do_site.pk).exists())
        # a equipe fica
        self.assertTrue(User.objects.filter(pk__in=[self.vendedor.pk, self.tecnico.pk]).count() == 2)

    def test_o_estoque_nao_volta_e_a_movimentacao_fica_com_o_nome_anotado(self):
        self.apagar_tudo()
        self.movimento.refresh_from_db()
        self.assertIsNone(self.movimento.cliente_id)
        self.assertIn("Destinatário removido: Cliente Sintético Completo", self.movimento.motivo)
        self.assertEqual((self.movimento.quantidade, self.movimento.quantidade_resultante), (3, 7))
        self.estoque.refresh_from_db()
        self.assertEqual(self.estoque.quantidade, 7)

    def test_o_rastro_diz_o_que_foi_junto(self):
        self.apagar_tudo()
        rastro = ExclusaoRegistrada.objects.get()
        self.assertEqual(rastro.tipo, "Cliente (com tudo)")
        self.assertEqual(rastro.identificacao, "Cliente Sintético Completo")
        self.assertEqual(rastro.autor, self.dono)
        self.assertEqual(rastro.motivo, "Cadastro de teste.")
        self.assertTrue(rastro.forcada)
        for pedaco in (
            f"#{self.v1.pk} (", f"#{self.v2.pk} (", "Orçamentos (2)", "Ordens de serviço (2)",
            self.os_do_cliente.numero_documento, "Documentos de assinatura: 2 (1 assinado(s))",
            "Assinados por: Maria Exemplo da Silva", f"Vendas removidas da receita: #{self.venda_id}",
            "Aceites eletrônicos: 1", "Produções na lista de montagem: 1", "Endereços: 1",
            "FICOU (não era só dele)", "1 movimentação de estoque", "1 cliente atendido por ele", "1 conta do site",
        ):
            self.assertIn(pedaco, rastro.resumo)

    def test_so_o_superusuario_tambem_por_post_direto(self):
        for usuario in (self.gestao, self.vendedor):
            with self.subTest(usuario=usuario.username):
                resposta = self.apagar_tudo(usuario)
                self.assertEqual(resposta.status_code, 403)
                self.assert_nada_saiu()

    def test_o_servico_nao_confia_na_tela(self):
        with self.assertRaises(ErroDeFormulario):
            exclusao_cliente.apagar_com_tudo(self.cliente, autor=self.gestao)
        self.assert_nada_saiu()

    def test_sem_a_palavra_confirmar_nada_sai(self):
        for palavra in ("", "sim", "CONFIRMA"):
            with self.subTest(palavra=palavra):
                resposta = self.apagar_tudo(confirmacao_exclusao=palavra)
                self.assertEqual(resposta.status_code, 400)
                self.assert_nada_saiu()

    def test_e_tudo_ou_nada(self):
        """Se algo falha no meio, a transação desfaz o que já tinha saído."""
        from unittest import mock

        with mock.patch.object(Cliente, "delete", side_effect=ErroDeFormulario("falha de teste")):
            resposta = self.apagar_tudo()
        self.assertEqual(resposta.status_code, 400)
        self.assert_nada_saiu()

    def test_a_exclusao_antiga_continua_so_o_cadastro(self):
        MovimentoEstoque.objects.filter(pk=self.movimento.pk).delete()  # a antiga leva a movimentação junto; fora deste teste
        resposta = self.postar(
            self.dono, action="delete", id=self.cliente.pk, confirmacao_exclusao="CONFIRMAR",
        )
        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertFalse(Cliente.objects.filter(pk=self.cliente.pk).exists())
        # os orçamentos e as O.S. ficam, sem cliente vinculado
        self.v2.refresh_from_db()
        self.assertIsNone(self.v2.cliente_id)
        self.assertTrue(OrdemServico.objects.filter(pk=self.os_do_cliente.pk, cliente__isnull=True).exists())
        self.assertTrue(DocumentoAssinatura.objects.filter(pk=self.documento.pk).exists())
        self.assertEqual(ExclusaoRegistrada.objects.get().tipo, "Cliente")

    def test_a_gestao_continua_sem_apagar_cliente_com_historico(self):
        resposta = self.postar(
            self.gestao, action="delete", id=self.cliente.pk, confirmacao_exclusao="CONFIRMAR",
        )
        self.assertEqual(resposta.status_code, 400)
        self.assert_nada_saiu()


# ======================================================================
# A JANELA
# ======================================================================
class JanelaDeExcluirTests(BaseExclusao):
    def test_so_o_superusuario_recebe_os_chips_do_alcance(self):
        self.client.force_login(self.dono)
        html = self.client.get("/clientes/", **INTERNO).content.decode()
        self.assertIn('id="excluirAlcance"', html)
        self.assertIn('name="alcance" value="cadastro" checked', html)
        self.assertIn('name="alcance" value="tudo"', html)
        self.assertIn("O cliente e tudo o que é dele", html)

        self.client.force_login(self.gestao)
        html = self.client.get("/clientes/", **INTERNO).content.decode()
        self.assertIn('id="modalExcluir"', html)  # a Gestão continua excluindo cadastro limpo
        self.assertNotIn('id="excluirAlcance"', html)
        self.assertNotIn('name="alcance" value=', html)

    def test_as_outras_telas_nao_ganham_os_chips(self):
        self.client.force_login(self.dono)
        html = self.client.get("/orcamentos/", **INTERNO).content.decode()
        self.assertNotIn('id="excluirAlcance"', html)

    def test_regras_da_casa(self):
        janela = (RAIZ / "templates" / "includes" / "modal_confirmar_exclusao.html").read_text(encoding="utf-8")
        tela = (RAIZ / "templates" / "clientes_inner.html").read_text(encoding="utf-8")
        self.assertNotIn("<select", janela)
        script = tela[tela.index("APAGAR O CLIENTE COM TUDO O QUE É DELE"):tela.index("?abrir=<id>")]
        for proibido in ("alert(", "confirm(", "innerHTML"):
            self.assertNotIn(proibido, script)
        import re

        css = (RAIZ / "static" / "interno" / "interno_modern.css").read_text(encoding="utf-8")
        secao = css[css.index("A JANELA DE EXCLUIR O CLIENTE COM TUDO O QUE É DELE"):]
        secao = re.sub(r"/\*.*?\*/", "", secao, flags=re.S)
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b", secao), [])
