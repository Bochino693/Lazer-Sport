"""Meus pedidos, centralizado (LEIA-ME-V10, seção 146).

O dono: "melhore também as informações do lado do cliente (...) em meus
pedidos, para centralizar os dados dos orçamentos, O.S. e pedidos do site".

O que estes testes protegem:

  * a O.S. do orçamento da conta aparece no cartão dele (número, situação,
    agenda, o botão de abrir) -- mas só depois de enviada ao cliente, nunca
    a versão trocada, e nunca a de outra conta;
  * a O.S. esperando assinatura ganha "Assinar a O.S.": o link sai na hora
    para o dono da conta; outra conta, anônimo, GET e O.S. sem documento,
    já assinada ou cancelada ficam de fora;
  * a O.S. assinada mostra a cópia;
  * cada item do orçamento tem a foto do brinquedo (ou o ícone, sem foto);
  * "O que falta você fazer" junta responder, assinar o contrato, assinar a
    O.S., pagar e assinar o contrato do pedido do site, cada um com a
    âncora do cartão dele, e some quando não falta nada;
  * a página não fica mais lenta com mais orçamentos com O.S.
"""

from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from core.models import Brinquedos
from core.tests_codigo_do_orcamento import Base
from sistema_interno import central_do_cliente
from sistema_interno import documento_assinatura as svc_doc
from sistema_interno import documento_servico
from sistema_interno.models import DocumentoAssinatura, ItemOrcamento, ItemOrdemServico, Orcamento, OrdemServico

ASSINAR_OS = "/meus-pedidos/orcamento/ordem-de-servico/assinar/"


class BaseCentral(Base):
    def aprovado(self, conta=None, **campos):
        orcamento = self.orcamento(status=Orcamento.Status.APROVADO, respondido_em=timezone.now(), **campos)
        return self.ligar(orcamento, conta)

    def ordem(self, orcamento, enviada=True, **campos):
        padrao = {
            "orcamento": orcamento,
            "nome_cliente": "Buffet Inventado",
            "equipamento": "Air Game Kids",
            "status": OrdemServico.Status.AGENDADA,
            "agendada_para": timezone.now() + timedelta(days=3),
            "enviada_em": timezone.now() if enviada else None,
            "responsavel": self.equipe,
        }
        padrao.update(campos)
        ordem = OrdemServico.objects.create(**padrao)
        ItemOrdemServico.objects.create(
            ordem=ordem, tipo=ItemOrdemServico.Tipo.SERVICO,
            descricao="Instalação", quantidade=1, valor_unitario=Decimal("200.00"),
        )
        return ordem

    def assinar_documento(self, documento):
        svc_doc.assinar(
            documento, nome="Cliente Inventado", cpf_cnpj="52998224725",
            png=b"\x89PNG", ip="127.0.0.1", navegador="teste",
        )
        documento.save()
        return documento


class OrdemNoCartaoTests(BaseCentral):
    def test_a_ordem_enviada_aparece_no_cartao_do_orcamento(self):
        orcamento = self.aprovado()
        ordem = self.ordem(orcamento)
        resposta = self.client.get("/meus-pedidos/")
        self.assertContains(resposta, f'<span class="oc-ordem-numero">{ordem.numero_documento}</span>')
        self.assertContains(resposta, ordem.caminho_publico)
        self.assertContains(resposta, "agendada para")
        self.assertNotContains(resposta, "Assinar a O.S.")

    def test_a_ordem_que_nao_foi_enviada_nao_aparece(self):
        ordem = self.ordem(self.aprovado(), enviada=False)
        resposta = self.client.get("/meus-pedidos/")
        self.assertNotContains(resposta, "oc-ordem-numero")
        self.assertNotContains(resposta, ordem.token)

    def test_a_versao_trocada_nao_aparece(self):
        ordem = self.ordem(self.aprovado(), status=OrdemServico.Status.SUBSTITUIDA)
        self.assertNotContains(self.client.get("/meus-pedidos/"), ordem.token)

    def test_a_ordem_de_outra_conta_nao_aparece(self):
        ordem = self.ordem(self.aprovado(conta=self.outro))
        self.assertNotContains(self.client.get("/meus-pedidos/"), ordem.token)

    def test_a_ordem_sem_orcamento_da_conta_nao_aparece(self):
        # a O.S. avulsa (sem orçamento) não tem como ser ligada a uma conta
        self.aprovado()
        avulsa = self.ordem(None)
        self.assertNotContains(self.client.get("/meus-pedidos/"), avulsa.token)

    def test_a_cancelada_aparece_sem_pedir_assinatura(self):
        orcamento = self.aprovado()
        ordem = self.ordem(orcamento)
        documento_servico.gerar_da_ordem(ordem, self.equipe)
        OrdemServico.objects.filter(pk=ordem.pk).update(status=OrdemServico.Status.CANCELADA)
        resposta = self.client.get("/meus-pedidos/")
        self.assertContains(resposta, "oc-ordem-numero")
        self.assertNotContains(resposta, "Assinar a O.S.")
        self.assertFalse([p for p in resposta.context["o_que_falta"] if "O.S." in p["texto"]])

    def test_a_assinada_mostra_a_copia(self):
        orcamento = self.aprovado()
        ordem = self.ordem(orcamento)
        documento = self.assinar_documento(documento_servico.gerar_da_ordem(ordem, self.equipe))
        resposta = self.client.get("/meus-pedidos/")
        self.assertContains(resposta, "Ver a O.S. assinada")
        self.assertContains(resposta, f"/assinado/{documento.codigo_publico}/")
        self.assertNotContains(resposta, "Assinar a O.S.")

    def test_as_consultas_nao_crescem_com_as_ordens(self):
        def contar():
            with CaptureQueriesContext(connection) as capturadas:
                self.assertEqual(self.client.get("/meus-pedidos/").status_code, 200)
            return len(capturadas)

        brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Air Game Kids", descricao="x", avaliacao=Decimal("5.00"), voltz="220V",
            valor_brinquedo=Decimal("1000.00"), imagem_brinquedo="imagens_brinquedos/air.jpg",
        )

        def mais_um():
            orcamento = self.aprovado()
            ItemOrcamento.objects.filter(orcamento=orcamento).update(brinquedo=brinquedo)
            documento_servico.gerar_da_ordem(self.ordem(orcamento), self.equipe)

        mais_um()
        contar()
        poucos = contar()
        for _ in range(4):
            mais_um()
        self.assertEqual(contar(), poucos, "Meus pedidos consulta o banco uma vez por O.S. ou por item")


class AssinarOrdemTests(BaseCentral):
    def setUp(self):
        super().setUp()
        self.orc = self.aprovado()
        self.os = self.ordem(self.orc)

    def test_o_dono_ganha_o_link_e_vai_assinar(self):
        documento = documento_servico.gerar_da_ordem(self.os, self.equipe)
        pagina = self.client.get("/meus-pedidos/")
        self.assertContains(pagina, "Assinar a O.S.")
        resposta = self.client.post(ASSINAR_OS, {"codigo": self.orc.codigo})
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/assinar/", resposta["Location"])
        documento.refresh_from_db()
        self.assertEqual(documento.links_gerados, 1)
        self.assertEqual(self.client.get(resposta["Location"]).status_code, 200)

    def test_outra_conta_nao_ganha_link(self):
        documento = documento_servico.gerar_da_ordem(self.os, self.equipe)
        outro = Client()
        outro.force_login(self.outro)
        resposta = outro.post(ASSINAR_OS, {"codigo": self.orc.codigo})
        self.assertNotIn("/assinar/", resposta["Location"])
        documento.refresh_from_db()
        self.assertEqual(documento.links_gerados, 0)

    def test_anonimo_get_e_csrf_ficam_de_fora(self):
        documento_servico.gerar_da_ordem(self.os, self.equipe)
        self.assertEqual(self.client.get(ASSINAR_OS).status_code, 405)
        anonimo = Client().post(ASSINAR_OS, {"codigo": self.orc.codigo})
        self.assertIn("/login", anonimo["Location"])
        exigente = Client(enforce_csrf_checks=True)
        exigente.force_login(self.cliente)
        self.assertEqual(exigente.post(ASSINAR_OS, {"codigo": self.orc.codigo}).status_code, 403)

    def test_sem_documento_assinada_ou_cancelada_nao_gera_link(self):
        # sem documento: quem gera é a equipe
        resposta = self.client.post(ASSINAR_OS, {"codigo": self.orc.codigo})
        self.assertNotIn("/assinar/", resposta["Location"])
        self.assertEqual(DocumentoAssinatura.objects.filter(ordem_servico=self.os).count(), 0)
        # cancelada
        documento = documento_servico.gerar_da_ordem(self.os, self.equipe)
        OrdemServico.objects.filter(pk=self.os.pk).update(status=OrdemServico.Status.CANCELADA)
        self.assertNotIn("/assinar/", self.client.post(ASSINAR_OS, {"codigo": self.orc.codigo})["Location"])
        # assinada
        OrdemServico.objects.filter(pk=self.os.pk).update(status=OrdemServico.Status.AGENDADA)
        self.assinar_documento(documento)
        self.assertNotIn("/assinar/", self.client.post(ASSINAR_OS, {"codigo": self.orc.codigo})["Location"])
        documento.refresh_from_db()
        self.assertEqual(documento.links_gerados, 0)


class FotoDosItensTests(BaseCentral):
    def test_o_item_mostra_a_foto_do_brinquedo_ou_o_icone(self):
        orcamento = self.aprovado(itens=(("Air Game Kids", 1, "4800.00"), ("Frete combinado", 1, "100.00")))
        brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Air Game Kids", descricao="x", avaliacao=Decimal("5.00"), voltz="220V",
            valor_brinquedo=Decimal("1000.00"), imagem_brinquedo="imagens_brinquedos/air-game.jpg",
        )
        ItemOrcamento.objects.filter(orcamento=orcamento, descricao="Air Game Kids").update(brinquedo=brinquedo)
        resposta = self.client.get("/meus-pedidos/")
        itens = resposta.context["orcamentos"][0].itens
        fotos = {item.descricao: item.foto_url for item in itens}
        self.assertIn("air-game", fotos["Air Game Kids"])
        self.assertEqual(fotos["Frete combinado"], "")
        self.assertContains(resposta, 'class="oc-item-foto"', count=2)
        self.assertContains(resposta, '<i class="fa-solid fa-cube"></i>', count=1)


class OQueFaltaTests(BaseCentral):
    def test_junta_orcamento_ordem_e_pedido_com_a_ancora_de_cada_um(self):
        responder = self.ligar(self.orcamento())
        assinar = self.aprovado()
        documento_servico.gerar_da_ordem(self.ordem(assinar), self.equipe)
        resposta = self.client.get("/meus-pedidos/")
        falta = {(p["texto"].split(": ")[1], p["ancora"]) for p in resposta.context["o_que_falta"]}
        self.assertEqual(falta, {
            ("responder a proposta", f"orc-{responder.codigo}"),
            ("assinar o contrato", f"orc-{assinar.codigo}"),
            ("assinar a ordem de serviço", f"orc-{assinar.codigo}"),
        })
        self.assertContains(resposta, "O que falta você fazer")
        for passo in resposta.context["o_que_falta"]:
            self.assertContains(resposta, f'href="#{passo["ancora"]}"')
            self.assertContains(resposta, f'id="{passo["ancora"]}"')

    def test_os_pedidos_do_site_entram_com_pagar_e_assinar(self):
        pedidos = [
            SimpleNamespace(pk=7, status="aguardando_pagamento", contrato=None),
            SimpleNamespace(pk=8, status="pago", contrato={"situacao": "assinar"}),
            SimpleNamespace(pk=9, status="pago", contrato={"situacao": "assinado"}),
            SimpleNamespace(pk=10, status="pago", contrato=None),
        ]
        falta = central_do_cliente.o_que_falta(pedidos, [])
        self.assertEqual(
            [(p["texto"], p["ancora"]) for p in falta],
            [("Pedido #7: concluir o pagamento", "pedido-7"), ("Pedido #8: assinar o contrato", "pedido-8")],
        )

    def test_some_quando_nao_falta_nada(self):
        orcamento = self.aprovado()
        self.assinar_documento(svc_doc.gerar(orcamento, self.equipe))
        resposta = self.client.get("/meus-pedidos/")
        self.assertEqual(resposta.context["o_que_falta"], [])
        self.assertNotContains(resposta, "O que falta você fazer")

    def test_os_icones_estao_no_recorte_do_site(self):
        from pathlib import Path

        from django.conf import settings

        recorte = (Path(settings.BASE_DIR) / "core/static/vendor/fontawesome-site/icones.txt").read_text().split()
        for icone in ("fa-list-check", "fa-screwdriver-wrench", "fa-cube", "fa-chevron-right", "fa-signature", "fa-clock", "fa-file-lines"):
            self.assertIn(icone, recorte)
