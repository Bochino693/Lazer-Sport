"""A proposta muda no lugar ATÉ A ASSINATURA (LEIA-ME-V10, seção 123).

O dono: "minha usuária fechou um contrato de um jeito, porém teve que
inserir mais itens e deu divergências, o sistema deve permitir alterações
até a assinatura, se assinou não muda mais. mas enquanto isso podemos mudar
sem erros, tire as notificações de erros como um texto comum e trate tudo
como app, renderizando janelas, sendo claro".

O que estes testes seguram:

  * a APROVADA sem contrato assinado ganha itens na mesma janela: continua
    aprovada, sem versão nova, com o total novo e o histórico dizendo o que
    mudou;
  * o contrato que esperava a assinatura é REFEITO com os itens novos: o
    anterior vira substituído, o link velho é recusado (na abertura e no
    envio, com "Este link foi trocado"), a tela do documento e a régua
    mostram o novo, e a resposta traz a janela "Contrato refeito";
  * o pagamento é refeito contra o total novo: o pago que deixou de cobrir
    volta a parcial e a venda do 100% sai; o parcial que passou a cobrir
    vira pago e ganha a venda;
  * a lista de montagem acompanha: a máquina que continua fica com a vaga
    e as etapas; a nova entra; a que saiu é cancelada;
  * ASSINADO não muda mais: o servidor recusa com a janela "Contrato
    assinado" (quem e quando), e o pagamento continua funcionando;
  * a enviada e a em negociação também mudam no lugar (a janela oferece
    "Reenviar ao cliente"); recusada, expirada e substituída seguem com
    "Refazer proposta", que continua opcional na aprovada;
  * a concorrência ("Mudou em outro atendimento", com "Ver a versão
    atual") e os erros em JSON com `titulo`, `msg`, `campo` e `acao`;
  * a janela de erro do painel: `Painel.erro` desenha a janela de app, e
    nenhuma tela do painel tem caixa de alerta do Bootstrap.
"""

import json
import re
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from core.models import Brinquedos, Venda

from . import documento_assinatura as svc
from . import edicao_orcamento
from .etapas_do_pedido import etapas
from .models import (
    AtividadeOrcamento,
    Cliente,
    DocumentoAssinatura,
    ItemOrcamento,
    Orcamento,
    OrdemServico,
    UnidadeMontagem,
)
from .permissoes import atribuir_funcoes
from .tests_documento_assinatura import (
    AJAX,
    CPF_DO_CLIENTE,
    JSON,
    png_de_assinatura,
    preencher_dados_do_contrato,
)

RAIZ = Path(__file__).resolve().parent.parent
TEMPLATES_PAINEL = RAIZ / "sistema_interno" / "templates"
ESTATICOS_PAINEL = RAIZ / "sistema_interno" / "static" / "interno"


def item(descricao, quantidade=1, valor="1500,00", brinquedo=""):
    return {
        "descricao": descricao, "brinquedo": brinquedo, "produto": "", "peca": "",
        "quantidade": quantidade, "valor_unitario": valor,
    }


class Base(TestCase):

    def setUp(self):
        cache.clear()
        preencher_dados_do_contrato()
        self.vendedor = self.usuario("vendedora", "vendas")
        self.financeiro = self.usuario("financeira", "financeiro")
        self.gestao = self.usuario("gestora", "gestao")
        self.cadastro = Cliente.objects.create(
            nome_cliente="Buffet Alegria", documento=CPF_DO_CLIENTE, telefone="(11) 97777-6655",
        )
        self.agk = Brinquedos.objects.create(
            nome_brinquedo="Air Game Kids", descricao="x", valor_brinquedo=Decimal("1500"),
            avaliacao=5, altura_m=1.0, largura_m=1.0, profundidade_m=1.0,
        )
        self.basquete = Brinquedos.objects.create(
            nome_brinquedo="Basquete Street", descricao="x", valor_brinquedo=Decimal("2000"),
            avaliacao=5, altura_m=2.7, largura_m=1.0, profundidade_m=2.4,
        )

    @staticmethod
    def usuario(username, *funcoes):
        user = User.objects.create_user(username=username, password="senha-segura")
        atribuir_funcoes(user, funcoes)
        return user

    def aprovada(self, **campos):
        """A proposta do caso do dono: aprovada, com um Air Game Kids."""
        padrao = {
            "cliente": self.cadastro,
            "nome_cliente": "Buffet Alegria",
            "whatsapp_cliente": "(11) 97777-6655",
            "status": Orcamento.Status.APROVADO,
            "forma_pagamento": "Pix",
            "forma_envio": "Retirada na fábrica",
            "observacoes": "Garantia de 6 meses.",
            "responsavel": self.vendedor,
            "respondido_em": timezone.now() - timedelta(days=1),
            "enviado_em": timezone.now() - timedelta(days=2),
            "validade": timezone.localdate() + timedelta(days=3),
        }
        padrao.update(campos)
        with self.captureOnCommitCallbacks(execute=True):
            orcamento = Orcamento.objects.create(**padrao)
            ItemOrcamento.objects.create(
                orcamento=orcamento, descricao="Air Game Kids", brinquedo=self.agk,
                quantidade=1, valor_unitario=Decimal("1500.00"),
            )
            # o sinal da lista de montagem roda depois do commit
            orcamento.save()
        return Orcamento.objects.get(pk=orcamento.pk)

    def salvar(self, orcamento, itens, usuario=None, **campos):
        self.client.force_login(usuario or self.vendedor)
        orcamento.refresh_from_db()
        dados = {
            "action": "save",
            "id": orcamento.pk,
            "revisao": orcamento.atualizado.isoformat(),
            "cliente": orcamento.cliente_id or "",
            "nome_cliente": orcamento.nome_cliente,
            "contato": orcamento.contato,
            "whatsapp_cliente": orcamento.whatsapp_cliente,
            "email_cliente": orcamento.email_cliente,
            "validade": orcamento.validade.isoformat() if orcamento.validade else "",
            "forma_envio": orcamento.forma_envio,
            "observacoes": orcamento.observacoes,
            "desconto": "0,00",
            "frete": "0,00",
            "valor_final": "",
            "forma_pagamento": orcamento.forma_pagamento,
            "itens": json.dumps(itens),
        }
        dados.update(campos)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post("/orcamentos/", dados, **AJAX)

    def assinar(self, token):
        return self.client.post(
            f"/assinar/{token}/",
            {
                "nome": "Maria Alegria da Silva", "documento": CPF_DO_CLIENTE,
                "concordo": "1", "assinatura": png_de_assinatura(),
            },
            HTTP_USER_AGENT="Mozilla/5.0 (iPhone)", REMOTE_ADDR="200.150.10.20", **JSON,
        )

    def dois_itens(self, quantidade_agk=1):
        """O Air Game Kids de antes (escolhido do catálogo, como a janela manda) e mais um."""
        return [
            item("Air Game Kids", quantidade_agk, "1500,00", brinquedo=str(self.agk.pk)),
            item("Basquete Street", 1, "2000,00", brinquedo=str(self.basquete.pk)),
        ]


# ======================================================================
# 1. A APROVADA SEM ASSINATURA MUDA NO LUGAR
# ======================================================================
class AprovadaMudaNoLugarTests(Base):

    def test_ganha_itens_sem_versao_nova_e_continua_aprovada(self):
        orcamento = self.aprovada()
        resposta = self.salvar(orcamento, self.dois_itens())
        self.assertEqual(resposta.status_code, 200, resposta.content)
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, Orcamento.Status.APROVADO)
        self.assertEqual(orcamento.versao, 1)
        self.assertEqual(Orcamento.objects.count(), 1)
        self.assertEqual(orcamento.itens.count(), 2)
        self.assertEqual(orcamento.total, Decimal("3500.00"))
        # o histórico diz quem, o quê e o total de antes e de agora
        linha = AtividadeOrcamento.objects.filter(
            orcamento=orcamento, tipo=AtividadeOrcamento.Tipo.ALTERADO,
        ).latest("id")
        self.assertEqual(linha.autor, self.vendedor)
        self.assertIn("+ Basquete Street", linha.resumo)
        self.assertIn("R$ 1.500,00 → R$ 3.500,00", linha.resumo)
        self.assertIn("antes da assinatura", linha.resumo)

    def test_a_validade_vencida_da_aprovada_nao_atrapalha(self):
        orcamento = self.aprovada(validade=timezone.localdate() - timedelta(days=20))
        resposta = self.salvar(orcamento, self.dois_itens())
        self.assertEqual(resposta.status_code, 200, resposta.content)

    def test_a_janela_abre_editavel_e_avisa_o_que_anda_junto(self):
        orcamento = self.aprovada()
        svc.gerar(orcamento, self.vendedor)
        self.client.force_login(self.vendedor)
        from .views_gestao import OrcamentosInnerView

        dados = OrcamentosInnerView.serializar(Orcamento.objects.get(pk=orcamento.pk))
        self.assertTrue(dados["pode_editar"])
        self.assertIsNone(dados["trava"])
        self.assertIn("refaz o contrato", dados["aviso_edicao"])

    def test_refazer_continua_opcional(self):
        orcamento = self.aprovada()
        self.client.force_login(self.vendedor)
        lista = self.client.get("/orcamentos/", HTTP_HOST="interno.testserver").content.decode()
        self.assertIn(f'data-refazer="{orcamento.pk}"', lista)
        self.assertIn(f'data-editar="{orcamento.pk}"', lista)
        resposta = self.client.post("/orcamentos/", {"action": "refazer", "id": orcamento.pk}, **AJAX)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertEqual(Orcamento.objects.get(pk=resposta.json()["id"]).versao, 2)


# ======================================================================
# 2. O CONTRATO QUE ESPERAVA A ASSINATURA É REFEITO
# ======================================================================
class ContratoRefeitoTests(Base):

    def test_o_contrato_e_refeito_com_os_itens_novos_e_o_link_velho_morre(self):
        orcamento = self.aprovada()
        anterior = svc.gerar(orcamento, self.vendedor)
        token_velho, _ = svc.emitir_link(anterior)
        self.assertEqual(svc.ler_link(token_velho).situacao, "valido")

        resposta = self.salvar(orcamento, self.dois_itens())
        self.assertEqual(resposta.status_code, 200, resposta.content)
        corpo = resposta.json()
        self.assertTrue(corpo["contrato_refeito"])
        self.assertEqual(corpo["janela"]["titulo"], "Contrato refeito")
        self.assertEqual(corpo["janela"]["texto"], edicao_orcamento.TEXTO_CONTRATO_REFEITO)
        self.assertIn("deixaram de valer", corpo["msg"])
        self.assertEqual(corpo["janela"]["acao"]["url"], f"/orcamentos/{orcamento.pk}/documento/")

        anterior.refresh_from_db()
        self.assertEqual(anterior.situacao, DocumentoAssinatura.Situacao.SUBSTITUIDO)
        novo = svc.documento_atual(orcamento)
        self.assertNotEqual(novo.pk, anterior.pk)
        self.assertTrue(novo.aguardando)
        descricoes = [linha["descricao"] for linha in novo.conteudo["itens"]]
        self.assertIn("Basquete Street", descricoes)
        self.assertEqual(novo.conteudo["valores"]["total"], "3500.00")

        # o link velho: "trocado" na abertura e no envio, nada assinado
        self.assertEqual(svc.ler_link(token_velho).situacao, "substituido")
        pagina = self.client.get(f"/assinar/{token_velho}/")
        self.assertContains(pagina, "Este link foi trocado", status_code=410)
        self.assertContains(pagina, "contrato foi refeito", status_code=410)
        envio = self.assinar(token_velho)
        self.assertEqual(envio.status_code, 410)
        self.assertIn("contrato refeito", envio.json()["msg"])
        self.assertFalse(DocumentoAssinatura.objects.filter(situacao=DocumentoAssinatura.Situacao.ASSINADO).exists())

        # o link novo assina o contrato novo
        token_novo, _ = svc.emitir_link(novo)
        self.assertEqual(self.assinar(token_novo).status_code, 200)

    def test_o_historico_e_o_diario_contam_o_refeito(self):
        orcamento = self.aprovada()
        svc.gerar(orcamento, self.vendedor)
        self.salvar(orcamento, self.dois_itens())
        documento = svc.documento_atual(orcamento)
        self.assertTrue(AtividadeOrcamento.objects.filter(
            orcamento=orcamento, tipo=AtividadeOrcamento.Tipo.DOCUMENTO,
            resumo__startswith="Contrato refeito: o pedido mudou",
        ).exists())
        textos = [linha["texto"] for linha in svc.linhas_do_diario(documento)]
        self.assertTrue(any(t.startswith("Contrato refeito por") for t in textos), textos)

    def test_a_tela_do_documento_e_a_regua_mostram_o_novo_na_hora(self):
        orcamento = self.aprovada()
        anterior = svc.gerar(orcamento, self.vendedor)
        self.salvar(orcamento, self.dois_itens())
        novo = svc.documento_atual(orcamento)
        tela = self.client.get(f"/orcamentos/{orcamento.pk}/documento/", HTTP_HOST="interno.testserver")
        self.assertContains(tela, f'data-documento="{novo.pk}"')
        self.assertContains(tela, "Basquete Street")
        regua = etapas(Orcamento.objects.get(pk=orcamento.pk), self.vendedor)
        estados = {etapa.chave: etapa.estado for etapa in regua.lista}
        self.assertEqual(estados["aprovacao"], "feita")
        self.assertEqual(estados["termo"], "atual")
        # o cartão aberto em outra aba troca sozinho e diz por quê
        estado = self.client.get(
            f"/orcamentos/{orcamento.pk}/documento/estado/?documento={anterior.pk}&situacao=aguardando",
            **AJAX,
        ).json()
        self.assertTrue(estado["mudou"])
        self.assertIn("refeito", estado["msg"])

    def test_mudar_so_a_validade_nao_refaz_o_contrato(self):
        orcamento = self.aprovada()
        documento = svc.gerar(orcamento, self.vendedor)
        resposta = self.salvar(
            orcamento, [item("Air Game Kids", 1, "1500,00", brinquedo=str(self.agk.pk))],
            validade=(timezone.localdate() + timedelta(days=9)).isoformat(),
        )
        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertFalse(resposta.json()["contrato_refeito"])
        self.assertEqual(svc.documento_atual(orcamento).pk, documento.pk)

    def test_o_prazo_de_entrega_refaz_o_contrato_e_a_janela_nao_fica_velha(self):
        orcamento = self.aprovada()
        anterior = svc.gerar(orcamento, self.vendedor)
        self.client.force_login(self.vendedor)
        revisao = Orcamento.objects.get(pk=orcamento.pk).atualizado.isoformat()
        from django.urls import reverse

        url = reverse("prazo_producao", args=["orcamento", orcamento.pk], urlconf="sistema_interno.urls")
        corpo = self.client.post(url, {"prazo": "30"}, **AJAX).json()
        self.assertTrue(corpo["contrato_refeito"], corpo)
        self.assertEqual(corpo["revisao_anterior"], revisao)
        novo = svc.documento_atual(orcamento)
        self.assertNotEqual(novo.pk, anterior.pk)
        self.assertIn("30 (trinta) dias úteis", json.dumps(novo.conteudo, ensure_ascii=False))
        # a janela usa a revisão nova e salva sem "mudou em outro atendimento"
        resposta = self.salvar(orcamento, self.dois_itens(), revisao=corpo["revisao"])
        self.assertEqual(resposta.status_code, 200, resposta.content)

    def test_em_negociacao_o_contrato_suspenso_e_retirado(self):
        orcamento = self.aprovada()
        documento = svc.gerar(orcamento, self.vendedor)
        Orcamento.objects.filter(pk=orcamento.pk).update(status=Orcamento.Status.EM_NEGOCIACAO)
        resposta = self.salvar(orcamento, self.dois_itens())
        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertTrue(resposta.json()["contrato_retirado"])
        documento.refresh_from_db()
        self.assertEqual(documento.situacao, DocumentoAssinatura.Situacao.SUBSTITUIDO)
        # aprovada de novo, o cartão pede um contrato novo (nada dos itens velhos)
        Orcamento.objects.filter(pk=orcamento.pk).update(status=Orcamento.Status.APROVADO)
        self.assertIsNone(svc.documento_atual(orcamento))


# ======================================================================
# 3. O PAGAMENTO E A VENDA ACOMPANHAM O TOTAL NOVO
# ======================================================================
class PagamentoContraOTotalNovoTests(Base):

    def test_o_pago_que_deixa_de_cobrir_volta_a_parcial_e_a_venda_sai(self):
        orcamento = self.aprovada()
        orcamento.registrar_pagamento(Decimal("1500.00"))
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status_pagamento, Orcamento.StatusPagamento.PAGO)
        venda_id = orcamento.venda_id
        self.assertTrue(Venda.objects.filter(pk=venda_id).exists())

        resposta = self.salvar(orcamento, self.dois_itens())
        self.assertEqual(resposta.status_code, 200, resposta.content)
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status_pagamento, Orcamento.StatusPagamento.PARCIAL)
        self.assertEqual(orcamento.valor_pago, Decimal("1500.00"))
        self.assertEqual(orcamento.saldo_pagamento, Decimal("2000.00"))
        self.assertIsNone(orcamento.venda_id)
        self.assertFalse(Venda.objects.filter(pk=venda_id).exists())
        lista = " ".join(resposta.json()["janela"]["lista"])
        self.assertIn("voltou a parcial", lista)
        self.assertIn(f"venda #{venda_id} saiu", lista)

    def test_o_parcial_que_passa_a_cobrir_vira_pago_com_a_venda(self):
        orcamento = self.aprovada()
        with self.captureOnCommitCallbacks(execute=True):
            ItemOrcamento.objects.create(orcamento=orcamento, descricao="Basquete Street",
                                         quantidade=1, valor_unitario=Decimal("2000.00"))
        orcamento.registrar_pagamento(Decimal("1500.00"))
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status_pagamento, Orcamento.StatusPagamento.PARCIAL)

        resposta = self.salvar(orcamento, [item("Air Game Kids", 1, "1500,00", brinquedo=str(self.agk.pk))])
        self.assertEqual(resposta.status_code, 200, resposta.content)
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status_pagamento, Orcamento.StatusPagamento.PAGO)
        venda = Venda.objects.get(pk=orcamento.venda_id)
        self.assertEqual(venda.valor_pago, Decimal("1500.00"))
        self.assertIn("virou a venda", " ".join(resposta.json()["janela"]["lista"]))

    def test_sem_pagamento_nada_e_registrado(self):
        orcamento = self.aprovada()
        self.salvar(orcamento, self.dois_itens())
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status_pagamento, Orcamento.StatusPagamento.PENDENTE)
        self.assertEqual(Venda.objects.count(), 0)


# ======================================================================
# 4. A LISTA DE MONTAGEM ACOMPANHA OS ITENS
# ======================================================================
class ListaDeMontagemTests(Base):

    def vivas(self, orcamento):
        return list(
            UnidadeMontagem.objects.filter(producao__orcamento=orcamento)
            .exclude(situacao=UnidadeMontagem.Situacao.CANCELADA).order_by("id")
        )

    def test_a_maquina_que_continua_fica_e_as_novas_entram(self):
        orcamento = self.aprovada()
        antes = self.vivas(orcamento)
        self.assertEqual([u.nome for u in antes], ["Air Game Kids"])
        primeira = antes[0]
        UnidadeMontagem.objects.filter(pk=primeira.pk).update(
            situacao=UnidadeMontagem.Situacao.PRODUCAO, etapa="corte",
            etapas_em={"corte": timezone.now().isoformat()},
        )

        itens = [
            item("Air Game Kids", 2, "1500,00", brinquedo=str(self.agk.pk)),
            item("Basquete Street", 1, "2000,00", brinquedo=str(self.basquete.pk)),
        ]
        resposta = self.salvar(orcamento, itens)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        depois = self.vivas(orcamento)
        self.assertEqual(sorted(u.nome for u in depois), ["Air Game Kids", "Air Game Kids", "Basquete Street"])
        mantida = UnidadeMontagem.objects.get(pk=primeira.pk)
        self.assertNotEqual(mantida.situacao, UnidadeMontagem.Situacao.CANCELADA)
        self.assertIn("corte", mantida.etapas_em)
        self.assertEqual((mantida.numero, mantida.de), (1, 2))
        self.assertIsNotNone(mantida.item_orcamento_id)
        self.assertIn("Lista de montagem: 2 máquinas entraram", " ".join(resposta.json()["janela"]["lista"]))

        # tirar o Basquete: a unidade dele é cancelada (a vaga libera)
        resposta = self.salvar(orcamento, [item("Air Game Kids", 2, "1500,00", brinquedo=str(self.agk.pk))])
        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertEqual(sorted(u.nome for u in self.vivas(orcamento)), ["Air Game Kids", "Air Game Kids"])
        self.assertIn("1 saiu", " ".join(resposta.json()["janela"]["lista"]))

    def test_sem_mudar_os_itens_a_lista_nao_mexe(self):
        orcamento = self.aprovada()
        antes = [(u.pk, u.situacao) for u in self.vivas(orcamento)]
        self.salvar(orcamento, [item("Air Game Kids", 1, "1500,00", brinquedo=str(self.agk.pk))],
                    observacoes="Outra observação")
        self.assertEqual([(u.pk, u.situacao) for u in self.vivas(orcamento)], antes)


# ======================================================================
# 5. ASSINADO NÃO MUDA MAIS (e o pagamento continua)
# ======================================================================
class AssinadoNaoMudaTests(Base):

    def test_o_servidor_recusa_com_a_janela_de_quem_assinou(self):
        orcamento = self.aprovada()
        documento = svc.gerar(orcamento, self.vendedor)
        token, _ = svc.emitir_link(documento)
        self.assertEqual(self.assinar(token).status_code, 200)

        resposta = self.salvar(orcamento, self.dois_itens())
        self.assertEqual(resposta.status_code, 409)
        corpo = resposta.json()
        self.assertEqual(corpo["status"], "erro")
        self.assertEqual(corpo["titulo"], "Contrato assinado")
        self.assertEqual(corpo["trava"], "assinado")
        hoje = timezone.localtime().strftime("%d/%m")
        self.assertIn(f"Contrato assinado por Maria Alegria da Silva em {hoje}: este pedido não muda mais", corpo["msg"])
        self.assertIn("fale com a Gestão", corpo["msg"])
        self.assertEqual(corpo["acao"]["rotulo"], "Ver contrato")
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.itens.count(), 1)
        self.assertEqual(orcamento.total, Decimal("1500.00"))
        # nem pelo Financeiro (desconto, valor final)
        resposta = self.salvar(orcamento, self.dois_itens(), usuario=self.financeiro, desconto="100,00")
        self.assertEqual(resposta.status_code, 409)

        # a janela abre só para consulta, dizendo por quê
        from .views_gestao import OrcamentosInnerView

        dados = OrcamentosInnerView.serializar(Orcamento.objects.get(pk=orcamento.pk))
        self.assertFalse(dados["pode_editar"])
        self.assertEqual(dados["trava"]["chave"], "assinado")

        # o pagamento é o estágio seguinte: continua valendo
        self.client.force_login(self.financeiro)
        pago = self.client.post(
            "/orcamentos/", {"action": "pagamento", "id": orcamento.pk, "valor_pago": "1500,00"}, **AJAX,
        )
        self.assertEqual(pago.status_code, 200, pago.content)
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status_pagamento, Orcamento.StatusPagamento.PAGO)
        self.assertIsNotNone(orcamento.venda_id)

    def test_o_prazo_depois_de_assinado_nao_refaz_o_contrato(self):
        orcamento = self.aprovada()
        documento = svc.gerar(orcamento, self.vendedor)
        token, _ = svc.emitir_link(documento)
        self.assinar(token)
        self.client.force_login(self.vendedor)
        from django.urls import reverse

        url = reverse("prazo_producao", args=["orcamento", orcamento.pk], urlconf="sistema_interno.urls")
        corpo = self.client.post(url, {"prazo": "40"}, **AJAX).json()
        self.assertNotIn("contrato_refeito", corpo)
        documento.refresh_from_db()
        self.assertTrue(documento.assinado)


# ======================================================================
# 6. ENVIADA E EM NEGOCIAÇÃO; RECUSADA, EXPIRADA E SUBSTITUÍDA
# ======================================================================
class OutrasSituacoesTests(Base):

    def test_a_enviada_muda_no_lugar_e_oferece_o_reenvio(self):
        orcamento = self.aprovada(status=Orcamento.Status.AGUARDANDO_RESPOSTA, respondido_em=None)
        resposta = self.salvar(orcamento, self.dois_itens())
        self.assertEqual(resposta.status_code, 200, resposta.content)
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, Orcamento.Status.AGUARDANDO_RESPOSTA)
        self.assertEqual(orcamento.versao, 1)
        janela = resposta.json()["janela"]
        self.assertEqual(janela["titulo"], "Proposta atualizada")
        self.assertEqual(janela["acao"], {"rotulo": "Reenviar ao cliente", "chave": "reenviar", "id": orcamento.pk})
        self.assertIn("já enviada ao cliente", AtividadeOrcamento.objects.filter(
            orcamento=orcamento, tipo=AtividadeOrcamento.Tipo.ALTERADO).latest("id").resumo)

    def test_a_em_negociacao_continua_em_negociacao(self):
        orcamento = self.aprovada(status=Orcamento.Status.EM_NEGOCIACAO, respondido_em=None)
        resposta = self.salvar(orcamento, self.dois_itens())
        self.assertEqual(resposta.status_code, 200, resposta.content)
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, Orcamento.Status.EM_NEGOCIACAO)
        self.assertEqual(orcamento.itens.count(), 2)

    def test_o_rascunho_salvo_vai_para_aguardando_como_sempre(self):
        orcamento = self.aprovada(status=Orcamento.Status.RASCUNHO, enviado_em=None, respondido_em=None)
        self.assertEqual(self.salvar(orcamento, self.dois_itens()).status_code, 200)
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, Orcamento.Status.AGUARDANDO_RESPOSTA)

    def test_recusada_expirada_e_substituida_seguem_com_refazer(self):
        for status, titulo in (
            (Orcamento.Status.RECUSADO, "Proposta recusada"),
            (Orcamento.Status.EXPIRADO, "Proposta expirada"),
            (Orcamento.Status.SUBSTITUIDO, "Versão substituída"),
        ):
            with self.subTest(status=status):
                orcamento = self.aprovada(status=status, respondido_em=None)
                resposta = self.salvar(orcamento, self.dois_itens())
                self.assertEqual(resposta.status_code, 409)
                corpo = resposta.json()
                self.assertEqual(corpo["titulo"], titulo)
                if status != Orcamento.Status.SUBSTITUIDO:
                    self.assertEqual(corpo["acao"]["chave"], "refazer")
                self.assertEqual(Orcamento.objects.get(pk=orcamento.pk).itens.count(), 1)

    def test_a_que_liberou_os_continua_congelada(self):
        orcamento = self.aprovada()
        OrdemServico.objects.create(nome_cliente="Buffet Alegria", orcamento=orcamento)
        resposta = self.salvar(orcamento, self.dois_itens())
        self.assertEqual(resposta.status_code, 409)
        self.assertEqual(resposta.json()["titulo"], "Proposta com O.S.")
        self.assertEqual(resposta.json()["trava"], "os")

    def test_trava_e_pode_editar_formulario_sao_a_mesma_regra(self):
        for status in Orcamento.Status.values:
            orcamento = self.aprovada(status=status)
            with self.subTest(status=status):
                self.assertEqual(
                    edicao_orcamento.trava(orcamento) is None, orcamento.pode_editar_formulario,
                )
        assinada = self.aprovada()
        documento = svc.gerar(assinada, self.vendedor)
        DocumentoAssinatura.objects.filter(pk=documento.pk).update(
            situacao=DocumentoAssinatura.Situacao.ASSINADO, assinado_em=timezone.now(),
            assinante_nome="Fulano",
        )
        assinada = Orcamento.objects.get(pk=assinada.pk)
        self.assertFalse(assinada.pode_editar_formulario)
        self.assertIsNotNone(edicao_orcamento.trava(assinada))


# ======================================================================
# 7. CONCORRÊNCIA E OS ERROS COMO JANELA (titulo, msg, campo, acao)
# ======================================================================
class ErrosComoJanelaTests(Base):

    def test_mudou_em_outro_atendimento(self):
        orcamento = self.aprovada()
        revisao = orcamento.atualizado.isoformat()
        Orcamento.objects.filter(pk=orcamento.pk).update(observacoes="Mudado por colega", atualizado=timezone.now())
        resposta = self.salvar(orcamento, self.dois_itens(), revisao=revisao)
        self.assertEqual(resposta.status_code, 409)
        corpo = resposta.json()
        self.assertEqual(corpo["titulo"], "Mudou em outro atendimento")
        self.assertIn("mudou em outro atendimento", corpo["msg"])
        self.assertEqual(corpo["acao"]["rotulo"], "Ver a versão atual")
        self.assertEqual(corpo["acao"]["chave"], "versao_atual")
        self.assertEqual(Orcamento.objects.get(pk=orcamento.pk).observacoes, "Mudado por colega")

    def test_os_erros_de_campo_dizem_o_campo(self):
        orcamento = self.aprovada(status=Orcamento.Status.AGUARDANDO_RESPOSTA, respondido_em=None)
        casos = (
            ({"validade": (timezone.localdate() - timedelta(days=1)).isoformat()}, "validade", "Validade no passado"),
            ({"email_cliente": "sem-arroba"}, "email_cliente", "E-mail inválido"),
            ({"desconto": "99999999999,00"}, "desconto", None),
            ({"cliente": "", "nome_cliente": ""}, "nome_cliente", "Falta o cliente"),
        )
        for campos, campo, titulo in casos:
            with self.subTest(campo=campo):
                # o desconto é do bloco financeiro: a Gestão edita os dois
                resposta = self.salvar(orcamento, self.dois_itens(), usuario=self.gestao, **campos)
                self.assertEqual(resposta.status_code, 400, resposta.content)
                corpo = resposta.json()
                self.assertEqual(corpo["status"], "erro")
                self.assertTrue(corpo["msg"])
                self.assertEqual(corpo["campo"], campo)
                if titulo:
                    self.assertEqual(corpo["titulo"], titulo)
        resposta = self.salvar(orcamento, [item("", 1, "10,00")])
        self.assertEqual(resposta.json()["campo"], "item:1:descricao")
        resposta = self.salvar(orcamento, [item("Air Game Kids", 0, "10,00")])
        self.assertEqual(resposta.json()["campo"], "item:1:quantidade")
        resposta = self.salvar(
            orcamento, self.dois_itens(),
            validade=(timezone.localdate() - timedelta(days=1)).isoformat(),
        )
        self.assertEqual(resposta.json()["acao"]["chave"], "validade_padrao")

    def test_o_erro_por_formulario_comum_leva_o_titulo_para_o_toast(self):
        orcamento = self.aprovada(status=Orcamento.Status.RECUSADO, respondido_em=None)
        self.client.force_login(self.vendedor)
        resposta = self.client.post(
            "/orcamentos/", {"action": "save", "id": orcamento.pk}, HTTP_HOST="interno.testserver",
            follow=True,
        )
        recados = [(m.message, m.extra_tags) for m in resposta.context["messages"]]
        self.assertTrue(any("titulo:Proposta recusada" in tags for _, tags in recados), recados)


# ======================================================================
# 8. A JANELA DE ERRO NO PAINEL (o código das telas)
# ======================================================================
def sem_comentarios(texto):
    texto = re.sub(r"/\*.*?\*/", "", texto, flags=re.S)
    texto = re.sub(r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}", "", texto, flags=re.S)
    texto = re.sub(r"\{#.*?#\}", "", texto)
    return re.sub(r"<!--.*?-->", "", texto, flags=re.S)


class JanelaDeErroNoPainelTests(SimpleTestCase):

    def test_painel_erro_desenha_a_janela_de_app_e_guarda_a_fala(self):
        js = (ESTATICOS_PAINEL / "painel.js").read_text(encoding="utf-8")
        inicio = js.index("O ERRO É UMA JANELA DE APLICATIVO")
        trecho = js[inicio:js.index("Painel.detalhesDoErro = function")]
        self.assertIn("LSAviso.modal(", trecho)
        self.assertIn("visually-hidden", trecho)
        self.assertIn("aria-invalid", trecho)
        # o envio leva titulo, campo e acao do servidor até a janela
        self.assertIn("erro.titulo = json.titulo", js)
        self.assertIn("erro.campo = json.campo", js)
        self.assertIn("erro.acao = json.acao", js)

    def test_nenhuma_tela_do_painel_tem_caixa_de_alerta(self):
        achados = []
        for arquivo in sorted(TEMPLATES_PAINEL.rglob("*.html")):
            texto = sem_comentarios(arquivo.read_text(encoding="utf-8"))
            for numero, linha in enumerate(texto.splitlines(), 1):
                if re.search(r"\balert alert-|\balert-(danger|warning|success|info|light)\b", linha):
                    achados.append(f"{arquivo.relative_to(RAIZ)}:{numero}: {linha.strip()[:90]}")
        self.assertEqual(achados, [])

    def test_o_desenho_das_notas_so_usa_o_tema(self):
        css = re.sub(r"/\*.*?\*/", "", (ESTATICOS_PAINEL / "avisos-janela.css").read_text(encoding="utf-8"), flags=re.S)
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b", css), [])
        self.assertEqual(re.findall(r"rgba?\(\s*\d", css), [])
        self.assertNotRegex(css, r":\s*(?:white|black|red|green|blue|gray|grey)\b")
        base = (TEMPLATES_PAINEL / "base_inner.html").read_text(encoding="utf-8")
        self.assertIn("interno/avisos-janela.css", base)

    def test_a_janela_do_orcamento_tem_a_trava_e_nenhum_select_novo(self):
        html = (TEMPLATES_PAINEL / "orcamentos_inner.html").read_text(encoding="utf-8")
        self.assertIn('id="orcamentoTrava"', html)
        self.assertIn('id="orcamentoAvisoEdicao"', html)
        self.assertIn("versao_atual", html)
        self.assertIn("reenviar", html)
        # nenhum <select> novo: os que existem são os de antes (o da situação, só
        # leitura, os da avaliação dos blocos e os dos cadastros rápidos)
        self.assertEqual(html.count("<select"), 13)
