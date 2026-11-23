"""A ordem de serviço assinada no celular -- manutenção e serviços (LEIA-ME-V10, 124).

O pedido do dono: "veja também referente aos orçamentos e os sem receber o
pagamento, também deve emitir contrato ou ordem de serviço, destinado a
manutenções e serviços, para padronizar."

O que estes testes protegem (dados SINTÉTICOS, nada de cliente real):

  * a O.S. SEM PAGAMENTO gera o documento; o papel diz "nenhum valor
    recebido" e não fala em "quitado"; o parcial diz a entrada e o saldo;
  * rascunho, cancelada, substituída e agenda vencida não geram;
  * o orçamento APROVADO SEM PAGAMENTO gera o contrato de venda, e todas as
    entradas (botão da lista, régua, folha dos avisos) levam a ele;
  * o orçamento de SERVIÇO gera a ordem de serviço (pela sugestão dos itens
    ou pelo chip), e "gerar de novo" não troca o papel;
  * quem pode, também por URL direta (o Financeiro vê o PDF, não gera);
  * a assinatura de ponta a ponta pela página pública: o link, a página no
    celular, o envio, o comprovante, a ciência registrada na O.S., o aviso;
  * o PDF (a via) com as cláusulas e a trilha;
  * assinada, trava: não gera de novo e os valores da O.S. não mudam (o
    andamento sim); cancelada, o link pendente fica suspenso;
  * a lista e a janela mostram o selo e o botão; os tetos de consultas.
"""

import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from core.models import PecasReposicao

from . import documento_assinatura as svc
from . import documento_servico as servico
from .models import (
    Cliente,
    DocumentoAssinatura,
    ItemOrcamento,
    ItemOrdemServico,
    Orcamento,
    OrdemServico,
)
from .permissoes import atribuir_funcoes
from .tests_documento_assinatura import (
    CPF_DO_CLIENTE,
    png_de_assinatura,
    preencher_dados_do_contrato,
)

INTERNO = {"HTTP_HOST": "interno.testserver"}
AJAX = {"HTTP_HOST": "interno.testserver", "HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
JSON = {"HTTP_ACCEPT": "application/json"}
CELULAR = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"


class BaseOS(TestCase):
    def setUp(self):
        cache.clear()
        preencher_dados_do_contrato()
        self.tecnico = self.usuario("tecnico-os", "producao")
        self.cliente_cadastro = Cliente.objects.create(
            nome_cliente="Parque Exemplo Diversões",
            documento=CPF_DO_CLIENTE,
            telefone="(11) 98888-7766",
        )
        self.ordem = self.criar_ordem()

    @staticmethod
    def usuario(username, *funcoes):
        user = User.objects.create_user(username=username, password="senha-segura")
        atribuir_funcoes(user, funcoes)
        return user

    def criar_ordem(self, *, status=OrdemServico.Status.AGENDADA, pago=Decimal("0.00"), itens=True, **campos):
        padrao = {
            "cliente": self.cliente_cadastro,
            "nome_cliente": "Parque Exemplo Diversões",
            "whatsapp_cliente": "(11) 98888-7766",
            "tipo": OrdemServico.Tipo.MANUTENCAO,
            "status": status,
            "equipamento": "Cama elástica 3,05 m",
            "numero_serie": "CE-TESTE-01",
            "defeito_relatado": "Lona rasgada na emenda e duas molas soltas.",
            "endereco_servico": "Rua Inventada, 100 – Bairro Teste – Cidade Teste/SP",
            "agendada_para": timezone.now() + timedelta(days=3),
            "frete": Decimal("80.00"),
            "desconto": Decimal("30.00"),
            "responsavel": self.tecnico,
            "tecnico": self.tecnico,
        }
        padrao.update(campos)
        ordem = OrdemServico.objects.create(**padrao)
        if itens:
            ItemOrdemServico.objects.create(
                ordem=ordem, tipo=ItemOrdemServico.Tipo.SERVICO,
                descricao="Troca da lona e regulagem", quantidade=1,
                valor_unitario=Decimal("350.00"),
            )
            ItemOrdemServico.objects.create(
                ordem=ordem, tipo=ItemOrdemServico.Tipo.PECA,
                descricao="Mola galvanizada", quantidade=4,
                valor_unitario=Decimal("25.00"),
            )
        if pago:
            ordem.registrar_pagamento(pago)
        return ordem

    def gerar(self, ordem=None, usuario=None):
        return servico.gerar_da_ordem(ordem or self.ordem, usuario or self.tecnico)

    def url(self, ordem=None, parte=""):
        return f"/ordens-servico/{(ordem or self.ordem).pk}/assinatura/{parte}"

    def link(self, documento):
        token, _ = svc.emitir_link(documento)
        return token

    def assinar(self, token, **troca):
        dados = {
            "nome": "Maria Exemplo da Silva",
            "documento": CPF_DO_CLIENTE,
            "concordo": "1",
            "assinatura": png_de_assinatura(),
        }
        dados.update(troca)
        return self.client.post(
            f"/assinar/{token}/", dados,
            HTTP_USER_AGENT=CELULAR, REMOTE_ADDR="200.150.10.20", **JSON,
        )


# ======================================================================
# A O.S. SEM PAGAMENTO GERA O DOCUMENTO
# ======================================================================
class GerarDaOrdemTests(BaseOS):

    def test_os_sem_pagamento_gera_pela_tela_e_o_papel_diz_que_nada_entrou(self):
        self.client.force_login(self.tecnico)
        pagina = self.client.get(self.url(), **INTERNO)
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, "Gerar a ordem de serviço para assinatura")
        self.assertContains(pagina, "Com ou sem pagamento")
        self.assertEqual(pagina["Cache-Control"], "no-store")

        resposta = self.client.post(self.url(), {"action": "gerar"}, **AJAX)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        corpo = resposta.json()
        self.assertEqual(corpo["status"], "sucesso")
        self.assertIn("Aguardando assinatura", corpo["html"])

        documento = DocumentoAssinatura.objects.get(ordem_servico=self.ordem)
        self.assertIsNone(documento.orcamento_id)
        conteudo = documento.conteudo
        self.assertEqual(conteudo["tipo"], "servico")
        self.assertEqual(conteudo["origem"], "ordem")
        self.assertEqual(conteudo["titulo"], servico.TITULO)
        self.assertEqual(conteudo["numero"], self.ordem.numero_documento)
        self.assertEqual(conteudo["modelo"], servico.VERSAO_DO_MODELO)
        # 350 + 4 x 25 + 80 de frete - 30 de desconto
        self.assertEqual(conteudo["valores"]["total"], "500.00")
        self.assertEqual(conteudo["valores"]["pago"], "0.00")
        self.assertEqual(conteudo["valores"]["saldo"], "500.00")
        self.assertEqual(conteudo["pagamento"]["codigo"], "pendente")
        self.assertFalse(conteudo["pagamento"]["quitado"])
        self.assertIn("Nenhum valor foi recebido até a emissão", conteudo["pagamento"]["texto"])
        self.assertEqual(conteudo["condicao_pagamento"], "à vista, na conclusão do serviço")
        self.assertEqual(conteudo["servico"]["equipamento"], "Cama elástica 3,05 m")
        self.assertEqual(conteudo["servico"]["numero_serie"], "CE-TESTE-01")
        self.assertEqual(conteudo["garantia"]["dias"], 90)
        texto = json.dumps(conteudo["secoes"], ensure_ascii=False)
        self.assertNotIn("quitado", texto)
        self.assertNotIn("entrada de", texto)
        self.assertIn("R$ 500,00 (quinhentos reais)", texto)
        self.assertIn("Situação do pagamento na emissão: Nenhum valor foi recebido", texto)
        # As onze cláusulas, numeradas na ordem.
        numeros = [c["numero"] for s in conteudo["secoes"] for c in s["clausulas"]]
        self.assertEqual(numeros, list(range(1, 12)))
        # O representante vem de DadosContrato (o sintético dos testes).
        self.assertEqual(conteudo["prestador"]["representante_nome"], "Fulano de Teste Ficticio")
        self.assertIn("CONTRATADA", conteudo["preambulo"]["abertura"])
        self.assertEqual(documento.hash_conteudo, svc.hash_do_retrato(conteudo))
        self.assertEqual(svc.linhas_do_diario(documento)[0]["texto"][:23], "Ordem de serviço gerada")

    def test_pagamento_parcial_e_pago_sao_escritos_do_jeito_certo(self):
        parcial = self.criar_ordem(pago=Decimal("200.00"), forma_pagamento="50% na aprovação e 50% na conclusão")
        conteudo = self.gerar(parcial).conteudo
        self.assertEqual(conteudo["pagamento"]["codigo"], "parcial")
        self.assertIn("Recebido até a emissão deste documento: R$ 200,00", conteudo["pagamento"]["texto"])
        self.assertIn("Saldo a pagar: R$ 300,00", conteudo["pagamento"]["texto"])
        self.assertEqual(conteudo["condicao_pagamento"], "50% na aprovação e 50% na conclusão")

        pago = self.criar_ordem(pago=Decimal("500.00"))
        conteudo = self.gerar(pago).conteudo
        self.assertEqual(conteudo["pagamento"]["codigo"], "pago")
        self.assertTrue(conteudo["pagamento"]["quitado"])

        sem_custo = self.criar_ordem(itens=False, frete=Decimal("0"), desconto=Decimal("0"))
        conteudo = self.gerar(sem_custo).conteudo
        self.assertEqual(conteudo["pagamento"]["codigo"], "sem_custo")
        setima = conteudo["secoes"][5]["clausulas"][0]
        self.assertIn("não têm custo", setima["texto"])

    def test_nao_gera_de_rascunho_cancelada_substituida_nem_agenda_vencida(self):
        self.client.force_login(self.tecnico)
        casos = {
            OrdemServico.Status.RASCUNHO: "rascunho",
            OrdemServico.Status.CANCELADA: "cancelada",
            OrdemServico.Status.SUBSTITUIDA: "substituída",
        }
        for status, palavra in casos.items():
            with self.subTest(status=status):
                ordem = self.criar_ordem(status=status)
                resposta = self.client.post(self.url(ordem), {"action": "gerar"}, **AJAX)
                self.assertEqual(resposta.status_code, 409)
                self.assertIn(palavra, resposta.json()["msg"].lower())
                self.assertFalse(DocumentoAssinatura.objects.filter(ordem_servico=ordem).exists())
        vencida = self.criar_ordem(agendada_para=timezone.now() - timedelta(days=2))
        resposta = self.client.post(self.url(vencida), {"action": "gerar"}, **AJAX)
        self.assertEqual(resposta.status_code, 409)
        self.assertIn("Reagende", resposta.json()["msg"])
        pagina = self.client.get(self.url(vencida), **INTERNO)
        self.assertContains(pagina, "A ordem de serviço não sai agora")

    def test_editar_a_os_depois_de_gerar_nao_muda_o_papel(self):
        documento = self.gerar()
        hash_antes = documento.hash_conteudo
        ItemOrdemServico.objects.filter(ordem=self.ordem).update(valor_unitario=Decimal("999.00"))
        documento.refresh_from_db()
        self.assertEqual(documento.hash_conteudo, hash_antes)
        self.assertEqual(documento.conteudo["valores"]["total"], "500.00")

    def test_gerar_de_novo_substitui_o_que_espera_e_mata_os_links(self):
        primeiro = self.gerar()
        token = self.link(primeiro)
        segundo = self.gerar()
        primeiro.refresh_from_db()
        self.assertEqual(primeiro.situacao, DocumentoAssinatura.Situacao.SUBSTITUIDO)
        self.assertEqual(svc.ler_link(token).situacao, "substituido")
        self.assertTrue(segundo.aguardando)


# ======================================================================
# O ORÇAMENTO: SEM PAGAMENTO, E O DE SERVIÇO
# ======================================================================
class OrcamentoSemPagamentoEDeServicoTests(BaseOS):
    def setUp(self):
        super().setUp()
        self.vendedor = self.usuario("vendedor-os", "vendas")

    def orcamento(self, *descricoes, **campos):
        padrao = {
            "nome_cliente": "Parque Exemplo Diversões",
            "cliente": self.cliente_cadastro,
            "whatsapp_cliente": "(11) 98888-7766",
            "status": Orcamento.Status.APROVADO,
            "respondido_em": timezone.now(),
            "responsavel": self.vendedor,
        }
        padrao.update(campos)
        orcamento = Orcamento.objects.create(**padrao)
        for descricao in descricoes or ("Cama elástica 3 m",):
            ItemOrcamento.objects.create(
                orcamento=orcamento, descricao=descricao, quantidade=1,
                valor_unitario=Decimal("400.00"),
            )
        return orcamento

    def test_aprovado_sem_pagamento_gera_o_contrato_e_as_entradas_levam_a_ele(self):
        from .etapas_do_pedido import etapas
        from .resolver_avisos import _aprovada
        from .permissoes import capacidades

        orcamento = self.orcamento()
        self.assertEqual(orcamento.status_pagamento, Orcamento.StatusPagamento.PENDENTE)
        self.client.force_login(self.vendedor)
        # 1. o botão da lista
        lista = self.client.get("/orcamentos/", **INTERNO).content.decode()
        self.assertIn(f"/orcamentos/{orcamento.pk}/documento/", lista)
        # 2. a régua da janela
        proximo = etapas(orcamento, self.vendedor).proximo
        self.assertEqual(proximo.acao, "Gerar o contrato")
        self.assertIn(f"/orcamentos/{orcamento.pk}/documento/", proximo.url)
        # 3. a folha dos avisos ("Cliente aprovou" -> "Gerar o contrato")
        bloco = _aprovada(self.vendedor, capacidades(self.vendedor), orcamento)["contrato"]
        self.assertEqual(bloco["situacao"], "gerar")
        # o chip sugerido é o da venda, e o gerar sai sem pagamento
        pagina = self.client.get(f"/orcamentos/{orcamento.pk}/documento/", **INTERNO).content.decode()
        self.assertIn('data-doc-modelo="compra_venda"\n                  aria-checked="true"', pagina)
        resposta = self.client.post(bloco["gerar"], {"action": "gerar"}, **AJAX)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        conteudo = DocumentoAssinatura.objects.get(orcamento=orcamento).conteudo
        self.assertEqual(conteudo["tipo"], "contrato")
        self.assertEqual(conteudo["pagamento"]["situacao"], "Pagamento pendente")
        texto = json.dumps(conteudo["secoes"], ensure_ascii=False)
        self.assertNotIn("entrada de", texto)
        self.assertNotIn("quitado", texto)
        self.assertIn("à vista, na confirmação do pedido", texto)

    def test_contrato_parcial_escreve_a_entrada_com_cifrao(self):
        orcamento = self.orcamento()
        orcamento.registrar_pagamento(Decimal("100.00"))
        conteudo = svc.gerar(orcamento, self.vendedor).conteudo
        self.assertIn("entrada de R$ 100,00 paga", conteudo["condicao_pagamento"])
        self.assertIn("saldo de R$ 300,00", conteudo["condicao_pagamento"])

    def test_orcamento_de_servico_sai_como_ordem_de_servico(self):
        orcamento = self.orcamento("Manutenção da cama elástica", "Troca de lona", "Deslocamento técnico")
        modelo, motivo = servico.sugestao_do_orcamento(orcamento)
        self.assertEqual(modelo, servico.MODELO_SERVICO)
        self.assertIn("manutenção e serviço", motivo)

        self.client.force_login(self.vendedor)
        pagina = self.client.get(f"/orcamentos/{orcamento.pk}/documento/", **INTERNO).content.decode()
        self.assertIn('data-doc-modelo="servico"\n                  aria-checked="true"', pagina)
        resposta = self.client.post(f"/orcamentos/{orcamento.pk}/documento/", {"action": "gerar"}, **AJAX)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        documento = DocumentoAssinatura.objects.get(orcamento=orcamento)
        conteudo = documento.conteudo
        self.assertEqual(conteudo["tipo"], "servico")
        self.assertEqual(conteudo["origem"], "orcamento")
        self.assertEqual(conteudo["orcamento"]["numero"], orcamento.numero_documento)
        self.assertEqual(conteudo["pagamento"]["codigo"], "pendente")
        self.assertEqual(
            [i["tipo"] for i in conteudo["itens"]],
            ["Serviço / mão de obra"] * 3,
        )
        # o histórico do orçamento diz o papel
        self.assertTrue(orcamento.atividades.filter(resumo__startswith="Ordem de serviço").exists())
        # "gerar de novo" (sem chip) não troca o papel
        novo = svc.gerar(orcamento, self.vendedor)
        self.assertEqual(novo.conteudo["tipo"], "servico")
        # o WhatsApp fala da ordem de serviço
        self.assertIn("assinar a ordem de serviço", svc.mensagem_whatsapp(novo, "https://x/assinar/t/"))
        # o contrato refeito pela edição da proposta (seção 123) também mantém
        refeito = svc.gerar(orcamento, self.vendedor, motivo="o pedido mudou")
        self.assertEqual(refeito.conteudo["tipo"], "servico")
        # assinada pelo link, o histórico do orçamento diz o papel
        resposta = self.assinar(self.link(refeito))
        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertTrue(
            orcamento.atividades.filter(resumo__startswith="Ordem de serviço assinada no celular").exists()
        )
        self.assertTrue(Orcamento.objects.get(pk=orcamento.pk).contrato_assinado)

    def test_o_chip_escolhe_o_papel_e_valor_estranho_e_recusado(self):
        orcamento = self.orcamento("Cama elástica 3 m")
        self.client.force_login(self.vendedor)
        resposta = self.client.post(
            f"/orcamentos/{orcamento.pk}/documento/", {"action": "gerar", "modelo": "servico"}, **AJAX,
        )
        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertEqual(DocumentoAssinatura.objects.get(orcamento=orcamento).conteudo["tipo"], "servico")
        resposta = self.client.post(
            f"/orcamentos/{orcamento.pk}/documento/", {"action": "gerar", "modelo": "aluguel"}, **AJAX,
        )
        self.assertEqual(resposta.status_code, 409)
        # nada mudou: o que esperava assinatura continua o mesmo
        self.assertEqual(
            DocumentoAssinatura.objects.filter(orcamento=orcamento, situacao="aguardando").count(), 1,
        )
        resposta = self.client.post(
            f"/orcamentos/{orcamento.pk}/documento/", {"action": "gerar", "modelo": "compra_venda"}, **AJAX,
        )
        self.assertEqual(resposta.status_code, 200)
        atual = svc.documento_atual(orcamento)
        self.assertEqual(atual.conteudo["tipo"], "contrato")

    def test_sugestao_pelos_itens(self):
        from core.models import Brinquedos

        manutencao = PecasReposicao.objects.create(
            nome="Kit de reparo de lona", uso=PecasReposicao.Uso.MANUTENCAO, preco_venda=Decimal("50"),
            descricao_peca="Kit sintético para teste",
        )
        so_pecas_de_manutencao = self.orcamento("Kit de reparo de lona")
        so_pecas_de_manutencao.itens.update(peca=manutencao)
        self.assertEqual(servico.sugestao_do_orcamento(so_pecas_de_manutencao)[0], "servico")
        # venda: um equipamento solto escrito à mão junto com "instalação"
        misto = self.orcamento("Pula-pula 3 m", "Instalação")
        self.assertEqual(servico.sugestao_do_orcamento(misto)[0], "compra_venda")
        brinquedo = Brinquedos.objects.first()
        if brinquedo is not None:
            catalogo = self.orcamento("Manutenção")
            catalogo.itens.update(brinquedo=brinquedo)
            self.assertEqual(servico.sugestao_do_orcamento(catalogo)[0], "compra_venda")


# ======================================================================
# QUEM PODE, TAMBÉM POR URL DIRETA
# ======================================================================
class PermissaoTests(BaseOS):

    def test_so_quem_edita_a_os_gera_e_acompanha(self):
        financeiro = self.usuario("financeiro-os", "financeiro")
        vendas = self.usuario("vendas-os", "vendas")
        gestao = self.usuario("gestao-os", "gestao")
        self.client.force_login(financeiro)
        for metodo, parte, dados in (
            ("get", "", None), ("post", "", {"action": "gerar"}),
            ("post", "link/", {}), ("get", "estado/", None),
        ):
            with self.subTest(parte=parte, metodo=metodo):
                resposta = getattr(self.client, metodo)(self.url(parte=parte), dados or {}, **AJAX)
                self.assertEqual(resposta.status_code, 403)
        self.assertFalse(DocumentoAssinatura.objects.exists())

        self.client.force_login(vendas)
        resposta = self.client.get(self.url(), **INTERNO)
        self.assertIn(resposta.status_code, (302, 403))
        self.assertFalse(DocumentoAssinatura.objects.exists())

        self.client.force_login(gestao)
        self.assertEqual(self.client.post(self.url(), {"action": "gerar"}, **AJAX).status_code, 200)

    def test_o_financeiro_abre_o_pdf_assinado(self):
        documento = self.gerar()
        self.assinar(self.link(documento))
        financeiro = self.usuario("financeiro-pdf", "financeiro")
        self.client.force_login(financeiro)
        via = self.client.get(self.url(parte="via/"), **INTERNO)
        self.assertEqual(via.status_code, 200)
        self.assertContains(via, "Documento assinado")
        lista = self.client.get("/ordens-servico/", **INTERNO).content.decode()
        self.assertIn("ls-doc-selo-os assinada", lista)
        self.assertIn(self.url(parte="via/"), lista)
        # o botão de gerar/acompanhar é de quem edita
        self.assertNotIn(f'href="{self.url()}"', lista)


# ======================================================================
# A ASSINATURA, DE PONTA A PONTA
# ======================================================================
class AssinaturaDePontaAPontaTests(BaseOS):

    def test_link_pagina_do_celular_assinatura_comprovante_e_ciencia(self):
        self.ordem.status = OrdemServico.Status.AGUARDANDO_RESPOSTA
        self.ordem.save(update_fields=["status"])
        self.client.force_login(self.tecnico)
        self.client.post(self.url(), {"action": "gerar"}, **AJAX)

        resposta = self.client.post(self.url(parte="link/"), {"canal": "whatsapp"}, **AJAX)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        corpo = resposta.json()
        self.assertIn("/assinar/", corpo["link"])
        self.assertIn("<svg", corpo["qr"])
        self.assertIn("ordem de serviço", corpo["mensagem"])
        self.assertIn(self.ordem.numero_documento, corpo["mensagem"])
        self.assertTrue(corpo["whatsapp"].startswith("https://wa.me/5511988887766?text="))
        token = corpo["link"].rsplit("/assinar/", 1)[1].strip("/")

        self.client.logout()
        pagina = self.client.get(f"/assinar/{token}/", HTTP_USER_AGENT=CELULAR)
        self.assertEqual(pagina.status_code, 200)
        html = pagina.content.decode()
        self.assertIn("<title>Assinar a ordem de serviço", html)
        self.assertIn("Li e concordo com o serviço, os valores e todas as cláusulas desta ordem de serviço.", html)
        self.assertIn(servico.TITULO, html)
        self.assertIn("Cama elástica 3,05 m", html)
        self.assertIn("Pagamento pendente", html)
        self.assertIn("<strong>CONTRATANTE</strong>", html)
        self.assertNotIn("contrato de compra e venda", html.lower())
        # o CPF do cadastro sai mascarado na página do link
        self.assertNotIn(CPF_DO_CLIENTE, html)

        resposta = self.assinar(token)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        destino = resposta.json()["destino"]
        documento = DocumentoAssinatura.objects.get(ordem_servico=self.ordem)
        self.assertTrue(documento.assinado)
        self.assertEqual(documento.assinante_nome, "Maria Exemplo da Silva")
        self.assertEqual(documento.hash_assinado, documento.hash_conteudo)
        self.assertEqual(documento.assinatura_ip, "200.150.10.20")

        comprovante = self.client.get(destino)
        self.assertContains(comprovante, "Pronto! Documento assinado.")
        self.assertContains(comprovante, "Registro da assinatura eletrônica")

        # assinar a ordem de serviço é a ciência da O.S.
        self.ordem.refresh_from_db()
        self.assertTrue(self.ordem.cliente_ciente)
        self.assertEqual(self.ordem.cliente_ciente_por, "Maria Exemplo da Silva")
        self.assertEqual(self.ordem.status, OrdemServico.Status.ABERTA)

        # o painel fica sabendo na sondagem
        self.client.force_login(self.tecnico)
        estado = self.client.get(self.url(parte="estado/"), {"documento": documento.pk, "situacao": "aguardando"}, **AJAX).json()
        self.assertTrue(estado["assinado"])
        self.assertIn("assinou a ordem de serviço", estado["msg"])
        self.assertIn("Ordem de serviço assinada", estado["html"])

        # o link usado vira o comprovante; assinar de novo não grava nada
        segunda = self.assinar(token, nome="Outra Pessoa Qualquer")
        self.assertEqual(segunda.status_code, 409)
        documento.refresh_from_db()
        self.assertEqual(documento.assinante_nome, "Maria Exemplo da Silva")

    def test_cpf_que_nao_confere_e_recusado(self):
        documento = self.gerar()
        resposta = self.assinar(self.link(documento), documento="111.444.777-35")
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.json()["campo"], "documento")
        documento.refresh_from_db()
        self.assertFalse(documento.assinado)

    def test_a_pagina_da_os_troca_a_ciencia_pela_assinatura(self):
        from django.urls import reverse

        self.ordem.marcar_enviada()

        publica = reverse("ordem_servico_publica", args=[self.ordem.token])
        self.assertContains(self.client.get(publica), "Confirmar ciência")
        documento = self.gerar()
        pagina = self.client.get(publica).content.decode()
        self.assertIn("Falta assinar a ordem de serviço", pagina)
        self.assertNotIn('name="nome"', pagina)
        self.assinar(self.link(documento))
        pagina = self.client.get(publica).content.decode()
        self.assertIn("Ordem de serviço assinada", pagina)
        documento.refresh_from_db()
        self.assertIn(f"/assinado/{documento.codigo_publico}/", pagina)


# ======================================================================
# O PDF (A VIA)
# ======================================================================
class ViaTests(BaseOS):

    def test_a_via_tem_o_papel_inteiro_e_a_trilha_depois_de_assinar(self):
        documento = self.gerar()
        self.client.force_login(self.tecnico)
        via = self.client.get(self.url(parte="via/"), **INTERNO)
        self.assertEqual(via.status_code, 200)
        html = via.content.decode()
        self.assertIn("Salvar em PDF", html)
        self.assertIn("Prévia do documento", html)
        self.assertIn(f"Ordem de serviço {self.ordem.numero_documento}", html)
        for titulo in ("DO OBJETO", "DA GARANTIA", "DO PREÇO E DO PAGAMENTO", "DOS DADOS PESSOAIS", "DO FORO"):
            self.assertIn(titulo, html)
        self.assertIn("Cláusula 11ª.", html)
        self.assertIn("counter(pages)", html)  # o "Página X de Y" de cada folha impressa
        # no painel o CPF sai inteiro
        self.assertIn(CPF_DO_CLIENTE, html)

        self.assinar(self.link(documento))
        via = self.client.get(self.url(parte="via/") + "?imprimir=1", **INTERNO).content.decode()
        self.assertIn("Registro da assinatura eletrônica", via)
        self.assertIn("Assinado eletronicamente em", via)
        self.assertIn('data-imprimir-ao-abrir="1"', via)


# ======================================================================
# ASSINADA, TRAVA -- COMO O CONTRATO DE VENDA
# ======================================================================
class TravaDepoisDeAssinarTests(BaseOS):

    def salvar(self, **troca):
        dados = {
            "action": "save", "id": self.ordem.pk,
            "cliente": self.cliente_cadastro.pk, "nome_cliente": self.ordem.nome_cliente,
            "whatsapp_cliente": self.ordem.whatsapp_cliente,
            "endereco_servico": self.ordem.endereco_servico,
            "equipamento": self.ordem.equipamento, "numero_serie": self.ordem.numero_serie,
            "defeito_relatado": self.ordem.defeito_relatado,
            "tipo": self.ordem.tipo, "status": "em_execucao", "prioridade": "normal",
            "diagnostico": "Molas trocadas; lona costurada.",
            "frete": "80,00", "desconto": "30,00",
            "itens": json.dumps([
                {"tipo": "servico", "descricao": "Troca da lona e regulagem", "quantidade": "1", "valor_unitario": "350,00"},
                {"tipo": "peca", "descricao": "Mola galvanizada", "quantidade": "4", "valor_unitario": "25,00"},
            ]),
        }
        dados.update(troca)
        return self.client.post("/ordens-servico/", dados, **AJAX)

    def test_assinada_nao_gera_de_novo_e_os_valores_nao_mudam(self):
        documento = self.gerar()
        self.assinar(self.link(documento))
        with self.assertRaises(Exception) as erro:
            self.gerar()
        self.assertIn("já tem a ordem de serviço assinada", str(erro.exception))

        self.client.force_login(self.tecnico)
        resposta = self.client.post(self.url(), {"action": "gerar"}, **AJAX)
        self.assertEqual(resposta.status_code, 409)

        # o andamento continua livre
        resposta = self.salvar()
        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.ordem.refresh_from_db()
        self.assertEqual(self.ordem.status, OrdemServico.Status.EM_EXECUCAO)
        self.assertEqual(self.ordem.diagnostico, "Molas trocadas; lona costurada.")
        self.assertEqual(self.ordem.itens.count(), 2)

        # o dinheiro assinado, não
        for troca in (
            {"frete": "120,00"},
            {"desconto": "0"},
            {"itens": json.dumps([{"tipo": "servico", "descricao": "Troca da lona e regulagem", "quantidade": "1", "valor_unitario": "900,00"}])},
        ):
            with self.subTest(troca=list(troca)):
                resposta = self.salvar(**troca)
                self.assertEqual(resposta.status_code, 409, resposta.content)
                corpo = resposta.json()
                self.assertEqual(corpo["titulo"], "Ordem de serviço assinada")
                self.assertIn("Refazer O.S.", corpo["msg"])
                self.assertEqual(corpo["acao"]["url"], self.url())
        self.ordem.refresh_from_db()
        self.assertEqual(self.ordem.total, Decimal("500.00"))

    def test_os_cancelada_suspende_o_documento_que_espera(self):
        documento = self.gerar()
        token = self.link(documento)
        self.ordem.status = OrdemServico.Status.CANCELADA
        self.ordem.save(update_fields=["status"])
        leitura = svc.ler_link(token)
        self.assertEqual(leitura.situacao, "suspenso")
        self.assertEqual(leitura.motivo, "ordem")
        pagina = self.client.get(f"/assinar/{token}/")
        self.assertEqual(pagina.status_code, 410)
        self.assertContains(pagina, "cancelada ou trocada", status_code=410)
        self.client.force_login(self.tecnico)
        self.assertEqual(self.client.post(self.url(parte="link/"), **AJAX).status_code, 409)
        self.assertIn("Ordem de serviço suspensa", self.client.get(self.url(), **INTERNO).content.decode())


# ======================================================================
# A LISTA E A JANELA DA O.S.
# ======================================================================
class ListaDaOSTests(BaseOS):

    def test_botao_e_selo_seguem_a_situacao(self):
        self.client.force_login(self.tecnico)
        lista = self.client.get("/ordens-servico/", **INTERNO).content.decode()
        self.assertIn(f'href="{self.url()}"', lista)
        self.assertIn('data-documento-assinatura="gerar"', lista)
        rascunho = self.criar_ordem(status=OrdemServico.Status.RASCUNHO)
        documento = self.gerar()
        lista = self.client.get("/ordens-servico/", **INTERNO).content.decode()
        self.assertIn('data-documento-assinatura="aguardando"', lista)
        self.assertIn("Assinatura pendente", lista)
        self.assertNotIn(f'href="{self.url(rascunho)}"', lista)
        self.assinar(self.link(documento))
        resposta = self.client.get("/ordens-servico/", **INTERNO)
        lista = resposta.content.decode()
        self.assertIn('data-documento-assinatura="assinado"', lista)
        self.assertIn("ls-doc-selo-os assinada", lista)
        dados = {o["id"]: o for o in resposta.context["ordens_dados"]}
        self.assertEqual(dados[self.ordem.pk]["documento"]["situacao"], "assinado")
        self.assertEqual(dados[self.ordem.pk]["documento"]["assinante"], "Maria Exemplo da Silva")
        self.assertIsNone(dados[rascunho.pk]["documento"])

    def test_a_lista_nao_le_o_documento_uma_vez_por_linha(self):
        self.client.force_login(self.tecnico)
        self.client.get("/ordens-servico/", **INTERNO)

        def contar():
            with CaptureQueriesContext(connection) as capturadas:
                self.assertEqual(self.client.get("/ordens-servico/", **INTERNO).status_code, 200)
            return len(capturadas.captured_queries)

        antes = contar()
        for _ in range(5):
            ordem = self.criar_ordem()
            self.gerar(ordem)
        depois = contar()
        self.assertLessEqual(depois, antes + 1, "a situação do documento veio linha a linha")


class TetoDeConsultasTests(BaseOS):
    """A tela do documento da O.S.: uma conta fixa, sem ler os itens de novo."""

    TETO_SEM_DOCUMENTO = 8
    TETO_COM_DOCUMENTO = 8
    TETO_DO_ESTADO = 8

    def medir(self, caminho):
        self.client.force_login(self.tecnico)
        self.client.get(caminho, **INTERNO)
        with CaptureQueriesContext(connection) as capturadas:
            resposta = self.client.get(caminho, **AJAX)
        self.assertEqual(resposta.status_code, 200)
        sqls = [q["sql"] for q in capturadas.captured_queries]
        itens = [q for q in sqls if "itemordemservico" in q.lower()]
        return len(sqls), itens, sqls

    def test_tela_sem_documento(self):
        total, itens, todas = self.medir(self.url())
        self.assertLessEqual(len(itens), 1, "\n".join(itens))
        self.assertLessEqual(total, self.TETO_SEM_DOCUMENTO, "\n".join(todas))

    def test_tela_com_documento_e_estado(self):
        self.gerar()
        total, itens, todas = self.medir(self.url())
        self.assertLessEqual(len(itens), 1, "\n".join(itens))
        self.assertLessEqual(total, self.TETO_COM_DOCUMENTO, "\n".join(todas))
        total, _, todas = self.medir(self.url(parte="estado/") + "?documento=0&situacao=x")
        self.assertLessEqual(total, self.TETO_DO_ESTADO, "\n".join(todas))

    def test_gerar_em_poucas_viagens(self):
        self.client.force_login(self.tecnico)
        self.client.get(self.url(), **INTERNO)
        with CaptureQueriesContext(connection) as capturadas:
            resposta = self.client.post(self.url(), {"action": "gerar"}, **AJAX)
        self.assertEqual(resposta.status_code, 200)
        self.assertLessEqual(len(capturadas.captured_queries), 18, "\n".join(q["sql"] for q in capturadas.captured_queries))
