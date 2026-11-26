"""O contrato do pedido do site, assinado em Meus pedidos (LEIA-ME-V10, seção 145).

O dono: "se ele comprar pelo site, devemos também fazer o esquema de
assinaturas após tudo pago certinho, isso em meus pedidos". Decidido por
ele: o CPF/CNPJ é pedido ao assinar (vem preenchido se o checkout trouxe);
só as compras com máquina ou brinquedo pedem contrato; no cartão, o total
e o valor cobrado saem discriminados; o contrato nasce no toque do cliente
e a assinatura não trava nada.

Dados SINTÉTICOS. O que estes testes protegem:

  * quem pede contrato (máquina sim; só peças não) e quando (só pago);
  * o retrato: o comprador da conta, o CPF conferido, o endereço da
    entrega, o texto do modelo, o valor com o cartão discriminado;
  * Meus pedidos: o passo aparece, some no pedido de peças, e o pedido de
    OUTRA conta não é alcançado;
  * o fluxo: CPF inválido volta; válido gera e leva à página de assinar;
    assinar com outro CPF é recusado; assinado, Meus pedidos mostra a cópia;
    tocar duas vezes não cria dois; outro CPF substitui o que esperava;
  * a assinatura não muda o pedido nem a produção; cancelado, suspende;
  * o painel: o terceiro objeto na tela Assinaturas, a via só para quem
    vê os pedidos do site; o orçamento e a O.S. continuam como eram.
"""

from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from core.models import ItemPedido, PecasReposicao, Pedido

from . import documento_assinatura as svc
from . import documento_pedido as dp
from .models import DocumentoAssinatura, UnidadeMontagem
from .tests_documento_assinatura import CPF_DO_CLIENTE, OUTRO_CPF, png_de_assinatura, preencher_dados_do_contrato
from .tests_lista_montagem import INTERNO, QUARTA, Base, equipe, no_dia, no_relogio
from .utils import ErroDeFormulario

CELULAR = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"


class BasePedido(Base):
    def setUp(self):
        super().setUp()
        preencher_dados_do_contrato()
        with no_relogio(QUARTA), no_dia(QUARTA.date()):
            self.pedido_maquina = self.pedido()                                  # 1 Air Game Kids, pago
        Pedido.objects.filter(pk=self.pedido_maquina.pk).update(
            pago_em=timezone.now(), forma_pagamento="cartao", parcelas=6,
            total_final=Decimal("4990.00"), valor_cobrado=Decimal("5588.80"),
            tipo_envio="frete", rua="Rua Inventada", numero="100", bairro="Bairro Teste",
            cidade="Cidade Teste", estado="SP", cep="01000-000",
        )
        self.pedido_maquina.refresh_from_db()
        self.peca = PecasReposicao.objects.create(nome="Botão sintético", descricao_peca="x", preco_venda=Decimal("35.00"))
        with no_relogio(QUARTA), no_dia(QUARTA.date()):
            self.pedido_peca = self.pedido(itens=[(self.peca, 2, None)])
            self.pedido_aberto = self.pedido(status="aguardando_pagamento")
        self.client.force_login(self.dono)

    def assinar_url(self, pedido):
        return f"/meus-pedidos/{pedido.pk}/contrato/assinar/"

    def pedir(self, pedido, cpf=CPF_DO_CLIENTE, **extras):
        return self.client.post(self.assinar_url(pedido), {"cpf_cnpj": cpf}, **extras)

    def assinar(self, token, cpf=CPF_DO_CLIENTE):
        return self.client.post(
            f"/assinar/{token}/",
            {"nome": "Dona Montagem da Silva", "documento": cpf, "concordo": "1", "assinatura": png_de_assinatura()},
            HTTP_USER_AGENT=CELULAR, REMOTE_ADDR="200.150.10.20", HTTP_ACCEPT="application/json",
        )


class RegraDoContratoDoPedidoTests(BasePedido):
    def test_quem_pede_contrato_e_quando(self):
        self.assertTrue(dp.pede_contrato(self.pedido_maquina))
        self.assertFalse(dp.pede_contrato(self.pedido_peca))            # só peças: sem contrato
        self.assertEqual(dp.motivo_para_nao_assinar(self.pedido_maquina), "")
        self.assertIn("não precisa de contrato", dp.motivo_para_nao_assinar(self.pedido_peca))
        self.assertIn("pagamento for confirmado", dp.motivo_para_nao_assinar(self.pedido_aberto))
        with self.assertRaises(ErroDeFormulario):
            dp.gerar_do_pedido(self.pedido_aberto, CPF_DO_CLIENTE)
        with self.assertRaises(ErroDeFormulario):
            dp.gerar_do_pedido(self.pedido_peca, CPF_DO_CLIENTE)
        with self.assertRaises(ErroDeFormulario):
            dp.gerar_do_pedido(self.pedido_maquina, "111.111.111-11")
        self.assertFalse(DocumentoAssinatura.objects.exists())

    def test_o_retrato_do_pedido(self):
        documento = dp.gerar_do_pedido(self.pedido_maquina, CPF_DO_CLIENTE, self.dono)
        conteudo = documento.conteudo
        self.assertEqual((documento.pedido_id, documento.orcamento_id, documento.ordem_servico_id),
                         (self.pedido_maquina.pk, None, None))
        self.assertTrue(svc.e_contrato(conteudo))
        self.assertEqual(conteudo["origem"], "pedido")
        self.assertEqual(conteudo["orcamento"]["numero"], dp.numero_do_pedido(self.pedido_maquina))
        self.assertTrue(conteudo["orcamento"]["numero"].startswith("P"))
        cliente = conteudo["cliente"]
        self.assertEqual((cliente["nome"], cliente["documento"], cliente["telefone"]),
                         ("Dona Montagem", CPF_DO_CLIENTE, "(11) 98888-7777"))
        self.assertEqual(cliente["endereco"], "Rua Inventada, 100 – Bairro Teste – Cidade Teste/SP – CEP 01000-000")
        # o texto do modelo da empresa (seção 141)
        abertura = conteudo["preambulo"]["abertura"]
        self.assertIn("comparecem aqui, as partes, de um lado", abertura)
        self.assertIn("neste ato representado por", abertura)
        # o valor: o total do pedido, e o cartão discriminado
        self.assertEqual(conteudo["valor_total_texto"], "4.990,00")
        self.assertEqual((conteudo["valores"]["total"], conteudo["valores"]["acrescimo_cartao"], conteudo["valores"]["cobrado"]),
                         ("4990.00", "598.80", "5588.80"))
        condicao = conteudo["condicao_pagamento"]
        for pedaco in ("cartão de crédito", "em 6 parcelas", "R$ 4.990,00", "R$ 598,80 de acréscimo do cartão",
                       "valor cobrado de R$ 5.588,80", "quitado em"):
            self.assertIn(pedaco, condicao)
        self.assertEqual([(i["descricao"], i["quantidade"]) for i in conteudo["itens"]], [("Air Game Kids", 1)])
        self.assertEqual(documento.hash_conteudo, svc.hash_do_retrato(conteudo))

    def test_sem_acrescimo_o_cartao_nao_aparece(self):
        Pedido.objects.filter(pk=self.pedido_maquina.pk).update(forma_pagamento="pix", valor_cobrado=None, parcelas=1)
        self.pedido_maquina.refresh_from_db()
        condicao = dp.condicao_de_pagamento(self.pedido_maquina)
        self.assertIn("por Pix", condicao)
        self.assertNotIn("acréscimo", condicao)

    def test_o_cpf_do_checkout_vem_sugerido(self):
        self.assertEqual(dp.cpf_sugerido(self.pedido_maquina), "")
        carrinho = self.pedido_maquina.carrinho_origem
        carrinho.cpf_cnpj = "52998224725"
        carrinho.save()
        self.pedido_maquina.refresh_from_db()
        self.assertEqual(dp.cpf_sugerido(self.pedido_maquina), CPF_DO_CLIENTE)

    def test_tocar_duas_vezes_nao_cria_dois_e_outro_cpf_substitui(self):
        primeiro = dp.gerar_do_pedido(self.pedido_maquina, CPF_DO_CLIENTE)
        self.assertEqual(dp.gerar_do_pedido(self.pedido_maquina, "52998224725").pk, primeiro.pk)
        segundo = dp.gerar_do_pedido(self.pedido_maquina, OUTRO_CPF)
        primeiro.refresh_from_db()
        self.assertEqual(primeiro.situacao, DocumentoAssinatura.Situacao.SUBSTITUIDO)
        self.assertEqual(dp.documento_atual_do_pedido(self.pedido_maquina).pk, segundo.pk)


class MeusPedidosComContratoTests(BasePedido):
    def test_o_passo_aparece_so_onde_vale(self):
        resposta = self.client.get("/meus-pedidos/")
        self.assertEqual(resposta.status_code, 200)
        por_pedido = {p.pk: p.contrato for p in resposta.context["pedidos"]}
        self.assertEqual(por_pedido[self.pedido_maquina.pk]["situacao"], "assinar")
        self.assertIsNone(por_pedido[self.pedido_peca.pk])
        self.assertEqual(por_pedido[self.pedido_aberto.pk]["situacao"], "aguardando_pagamento")
        html = resposta.content.decode()
        self.assertIn(f'action="{self.assinar_url(self.pedido_maquina)}"', html)
        self.assertNotIn(self.assinar_url(self.pedido_peca), html)
        self.assertNotIn(self.assinar_url(self.pedido_aberto), html)
        self.assertIn("Falta assinar o contrato", html)
        self.assertIn("Sua produção segue normalmente", html)

    def test_cpf_invalido_volta_e_nada_e_gerado(self):
        resposta = self.pedir(self.pedido_maquina, "123")
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(f"/meus-pedidos/#pedido-{self.pedido_maquina.pk}", resposta["Location"])
        self.assertFalse(DocumentoAssinatura.objects.exists())
        # e os que não pedem contrato também não geram por POST direto
        self.pedir(self.pedido_peca)
        self.pedir(self.pedido_aberto)
        self.assertFalse(DocumentoAssinatura.objects.exists())

    def test_o_pedido_de_outra_conta_nao_e_alcancado(self):
        from django.contrib.auth.models import User

        outro = User.objects.create_user("outra-conta-site", "o@exemplo.test", "x")
        self.client.force_login(outro)
        resposta = self.pedir(self.pedido_maquina)
        self.assertEqual(resposta.status_code, 302)
        self.assertFalse(DocumentoAssinatura.objects.exists())
        self.client.logout()
        self.assertIn("login", self.pedir(self.pedido_maquina)["Location"])
        self.assertEqual(self.client.get(self.assinar_url(self.pedido_maquina)).status_code, 302)  # só POST (e login)

    def test_o_fluxo_inteiro_do_toque_a_copia_assinada(self):
        antes = Pedido.objects.values("status", "pago_em", "total_final", "valor_cobrado").get(pk=self.pedido_maquina.pk)
        unidades = list(UnidadeMontagem.objects.filter(producao__pedido=self.pedido_maquina).values_list("pk", "situacao", "etapa"))
        resposta = self.pedir(self.pedido_maquina)
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/assinar/", resposta["Location"])
        token = resposta["Location"].rstrip("/").split("/")[-1]
        documento = DocumentoAssinatura.objects.get()
        self.assertEqual(documento.links_gerados, 1)
        # a página de assinar: a mesma do orçamento, sem relógio, com o contrato do pedido
        pagina = self.client.get(resposta["Location"], HTTP_USER_AGENT=CELULAR)
        self.assertEqual(pagina.status_code, 200)
        html = pagina.content.decode()
        self.assertIn(dp.numero_do_pedido(self.pedido_maquina), html)
        self.assertIn("Air Game Kids", html)
        self.assertIn("Leia com calma", html)
        self.assertNotIn('class="relogio"', html)
        # outro CPF não assina; o conferido, sim
        self.assertEqual(self.assinar(token, OUTRO_CPF).status_code, 400)
        feito = self.assinar(token)
        self.assertEqual(feito.status_code, 200, feito.content)
        documento.refresh_from_db()
        self.assertTrue(documento.assinado)
        self.assertEqual(documento.assinante_nome, "Dona Montagem da Silva")
        # a assinatura não mexe no pedido nem na produção
        self.assertEqual(Pedido.objects.values("status", "pago_em", "total_final", "valor_cobrado").get(pk=self.pedido_maquina.pk), antes)
        self.assertEqual(list(UnidadeMontagem.objects.filter(producao__pedido=self.pedido_maquina).values_list("pk", "situacao", "etapa")), unidades)
        # Meus pedidos mostra a cópia, e tocar de novo leva a ela
        html = self.client.get("/meus-pedidos/").content.decode()
        self.assertIn("Contrato assinado", html)
        self.assertIn(f"/documento-assinado/{documento.codigo_publico}/" if "/documento-assinado/" in html else str(documento.codigo_publico), html)
        self.assertNotIn(f'action="{self.assinar_url(self.pedido_maquina)}"', html)
        de_novo = self.pedir(self.pedido_maquina)
        self.assertIn(str(documento.codigo_publico), de_novo["Location"])
        self.assertEqual(DocumentoAssinatura.objects.count(), 1)

    def test_cancelado_suspende_o_que_esperava(self):
        resposta = self.pedir(self.pedido_maquina)
        token = resposta["Location"].rstrip("/").split("/")[-1]
        Pedido.objects.filter(pk=self.pedido_maquina.pk).update(status="cancelado")
        documento = DocumentoAssinatura.objects.get()
        self.assertEqual(svc.motivo_da_suspensao(documento), "pedido")
        self.assertEqual(svc.ler_link(token).situacao, "suspenso")
        self.assertNotEqual(self.assinar(token).status_code, 200)
        self.assertNotIn(self.assinar_url(self.pedido_maquina), self.client.get("/meus-pedidos/").content.decode())

    def test_meus_pedidos_nao_ganha_consulta_por_pedido(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self.client.get("/meus-pedidos/")

        def consultas():
            with CaptureQueriesContext(connection) as contexto:
                self.assertEqual(self.client.get("/meus-pedidos/").status_code, 200)
            return [c["sql"] for c in contexto if "documentoassinatura" in c["sql"].lower()]

        self.assertEqual(len(consultas()), 1)
        with no_relogio(QUARTA), no_dia(QUARTA.date()):
            for _ in range(3):
                self.pedido()
        self.assertEqual(len(consultas()), 1)


class PainelComOContratoDoPedidoTests(BasePedido):
    def setUp(self):
        super().setUp()
        self.documento = dp.gerar_do_pedido(self.pedido_maquina, CPF_DO_CLIENTE, self.dono)
        self.financeiro = equipe("fin-pedido", "financeiro")
        self.gestao = equipe("gestao-pedido", "gestao")
        self.vendedor = equipe("vend-pedido", "vendas")
        self.producao_user = equipe("prod-pedido", "producao")

    def abrir(self, usuario, consulta=""):
        self.client.force_login(usuario)
        return self.client.get("/assinaturas/" + consulta, **INTERNO)

    def test_o_terceiro_objeto_na_tela_assinaturas(self):
        resposta = self.abrir(self.financeiro)
        self.assertEqual(resposta.status_code, 200)
        cartao = next(c for c in resposta.context["cartoes"] if c["documento"].pk == self.documento.pk)
        self.assertEqual(cartao["objeto"]["rotulo"], f"Pedido do site nº {self.pedido_maquina.pk}")
        self.assertEqual((cartao["situacao"], cartao["pode_qr"], cartao["cliente"], cartao["cliente_id"]),
                         ("aguardando", False, "Dona Montagem", None))
        html = resposta.content.decode()
        self.assertIn('data-as-objeto="pedidos"', html)
        self.assertIn("O cliente assina em Meus pedidos", html)
        self.assertNotIn("data-as-qr", html)
        filtrada = self.abrir(self.financeiro, "?objeto=pedidos")
        self.assertEqual([c["documento"].pk for c in filtrada.context["cartoes"]], [self.documento.pk])
        self.assertEqual({c["valor"]: c["quantos"] for c in filtrada.context["chips_objeto"]}["pedidos"], 1)
        # a busca pelo nome do comprador e pelo número do pedido
        self.assertEqual(len(self.abrir(self.financeiro, "?q=Dona+Montagem").context["cartoes"]), 1)
        self.assertEqual(len(self.abrir(self.financeiro, f"?q={self.pedido_maquina.pk}&objeto=pedidos").context["cartoes"]), 1)

    def test_quem_nao_ve_os_pedidos_do_site_nao_ve_o_contrato_deles(self):
        for usuario in (self.vendedor, self.producao_user):
            with self.subTest(usuario=usuario.username):
                resposta = self.abrir(usuario, "?objeto=pedidos")
                self.assertEqual([c for c in resposta.context["cartoes"] if c["documento"].pk == self.documento.pk], [])
                self.assertNotIn('data-as-objeto="pedidos"', resposta.content.decode())
                via = self.client.get(f"/pedidos/{self.pedido_maquina.pk}/contrato/via/", **INTERNO)
                self.assertNotEqual(via.status_code, 200)

    def test_a_via_abre_para_o_financeiro_e_a_gestao(self):
        for usuario in (self.financeiro, self.gestao):
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                via = self.client.get(f"/pedidos/{self.pedido_maquina.pk}/contrato/via/?documento={self.documento.pk}&imprimir=1", **INTERNO)
                self.assertEqual(via.status_code, 200)
                self.assertTrue(via.context["imprimir_ao_abrir"])
                self.assertEqual(via.context["voltar_url"], "/assinaturas/?objeto=pedidos")
                self.assertIn(CPF_DO_CLIENTE, via.content.decode())   # no painel o CPF sai inteiro
        self.assertEqual(self.client.get("/pedidos/999999/contrato/via/", **INTERNO).status_code, 404)

    def test_nenhum_botao_do_card_do_pedido_da_erro(self):
        import re

        html = self.abrir(self.financeiro, "?objeto=pedidos").content.decode()
        grade = html[html.index('class="ls-as-grade"'):]
        grade = grade[:grade.index("</section>")]
        for endereco in {e.replace("&amp;", "&") for e in re.findall(r'href="([^"]+)"', grade)}:
            with self.subTest(endereco=endereco):
                self.assertEqual(self.client.get(endereco, **INTERNO).status_code, 200)

    def test_o_aviso_da_assinatura_vai_para_quem_cuida_dos_pedidos(self):
        from unittest import mock

        from . import notificacoes

        with mock.patch.object(notificacoes, "_entregar") as entregar:
            notificacoes.avisar_documento_assinado(self.documento)
        pessoas, dados = entregar.call_args[0]
        self.assertEqual({p.username for p in pessoas}, {"fin-pedido", "gestao-pedido"})
        self.assertIn(f"Pedido do site #{self.pedido_maquina.pk}", dados["titulo"])
        self.assertNotIn("Dona Montagem", dados["titulo"] + dados["corpo"])

    def test_o_pedido_do_site_nao_entra_no_atalho_de_clientes(self):
        from . import views_assinaturas

        from .models import Cliente

        cliente = Cliente.objects.create(nome_cliente="Dona Montagem")
        self.assertEqual(views_assinaturas.contagem_por_cliente(self.gestao, [cliente.pk]), {})
        self.assertEqual(self.abrir(self.gestao, f"?cliente={cliente.pk}").context["cartoes"], [])
