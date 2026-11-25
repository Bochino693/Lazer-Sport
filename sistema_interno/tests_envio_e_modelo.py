"""O contrato igual ao modelo, o envio do pedido já aprovado e as fotos inteiras
(LEIA-ME-V10, seção 141). Dados SINTÉTICOS.

  A) a redação do preâmbulo é a do contrato modelo da empresa ("comparecem
     aqui, as partes, de um lado", "aqui doravante", "neste ato representado
     por", "RG:"), na O.S. com a concordância dela; o documento JÁ GERADO não
     muda (o retrato é congelado); a tela "Dados do contrato" tira o "RG:" e
     o ponto final que a pessoa digitar a mais;
  C) a foto do item aparece INTEIRA na proposta, no contrato e em Meus
     pedidos: `contain`, presa à moldura (a foto alta era cortada);
  D) a proposta já aprovada continua saindo -- para consulta: o envio não
     muda a situação nem a data do primeiro envio, a mensagem diz a situação
     real e não pede decisão; a página pública abre sem login e sem os
     botões de responder; recusada, vencida e substituída continuam sem envio.
"""

import re
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from . import documento_assinatura as svc
from . import documento_servico as servico
from .models import DadosContrato, ItemOrcamento, Orcamento
from .permissoes import atribuir_funcoes
from .tests_documento_assinatura import REPRESENTANTE_FICTICIO, BaseDocumento
from .tests_documento_os import BaseOS

RAIZ = Path(__file__).resolve().parent.parent
AJAX = {"HTTP_HOST": "interno.testserver", "HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
INTERNO = {"HTTP_HOST": "interno.testserver"}


# ======================================================================
# A) O TEXTO IGUAL AO MODELO
# ======================================================================
class PreambuloIgualAoModeloTests(BaseDocumento):
    def test_o_contrato_de_venda_palavra_por_palavra(self):
        abertura = self.gerar().conteudo["preambulo"]["abertura"]
        esperado = (
            "Pelo presente INSTRUMENTO PARTICULAR DE COMPRA E VENDA, e na forma da Lei, comparecem aqui, "
            "as partes, de um lado, na qualidade de fornecedor, aqui doravante denominado simplesmente "
            "VENDEDOR: Brinquedos Lazer & Sport, razão social Fábrica de Brinquedos Lazer & Sport Oficial – "
            "LTDA, devidamente inscrita no CNPJ sob o n. 54.486.908/0001-86, com sede na Rua São Roque de "
            "Minas, n. 104, Jardim Peri, São Paulo, Capital, neste ato representado por "
            f"{REPRESENTANTE_FICTICIO['representante_nome']}, portador da cédula de identidade RG: "
            f"{REPRESENTANTE_FICTICIO['representante_rg']}, residente e domiciliado na "
            f"{REPRESENTANTE_FICTICIO['representante_endereco']}; e, do outro lado, na qualidade de "
            "comprador, aqui doravante denominado simplesmente COMPRADOR:"
        )
        self.assertEqual(abertura, esperado)

    def test_o_documento_ja_gerado_nao_muda(self):
        """O retrato é congelado: mudar os dados (ou o texto) só vale para o próximo."""
        documento = self.gerar()
        antes = documento.conteudo["preambulo"]["abertura"]
        hash_antes = documento.hash_conteudo
        dados = DadosContrato.atual()
        dados.representante_nome = "Beltrana de Teste Ficticia"
        dados.save()
        documento.refresh_from_db()
        self.assertEqual(documento.conteudo["preambulo"]["abertura"], antes)
        self.assertEqual(documento.hash_conteudo, hash_antes)
        novo = svc.gerar(self.orcamento, self.vendedor, motivo="dados novos")
        self.assertIn("representado por Beltrana de Teste Ficticia", novo.conteudo["preambulo"]["abertura"])


class PreambuloDaOrdemDeServicoTests(BaseOS):
    def test_a_os_segue_o_modelo_com_a_concordancia_dela(self):
        abertura = servico.gerar_da_ordem(self.ordem, self.tecnico).conteudo["preambulo"]["abertura"]
        for pedaco in (
            "e na forma da Lei, comparecem aqui, as partes, de um lado, na qualidade de prestadora dos serviços, "
            "aqui doravante denominada simplesmente CONTRATADA: Brinquedos Lazer & Sport",
            f"neste ato representada por {REPRESENTANTE_FICTICIO['representante_nome']}, portador da cédula de "
            f"identidade RG: {REPRESENTANTE_FICTICIO['representante_rg']}, residente e domiciliado na",
            "; e, do outro lado, na qualidade de tomador dos serviços, aqui doravante denominado simplesmente CONTRATANTE:",
        ):
            self.assertIn(pedaco, abertura)
        self.assertNotIn("comparecem aqui as partes:", abertura)
        self.assertNotIn("identidade RG 0", abertura)


class DadosDoContratoNoFormatoDoModeloTests(TestCase):
    def setUp(self):
        self.gestora = User.objects.create_user("gestora-modelo", password="senha-de-teste")
        atribuir_funcoes(self.gestora, ("gestao",))
        self.client.force_login(self.gestora)

    def salvar(self, **troca):
        dados = {
            "action": "salvar", "nome_fantasia": "Brinquedos Lazer & Sport",
            "razao_social": "Fábrica de Brinquedos Lazer & Sport Oficial – LTDA", "cnpj": "54.486.908/0001-86",
            "endereco_sede": "Rua São Roque de Minas, n. 104, Jardim Peri, São Paulo, Capital", "cidade": "São Paulo",
            **REPRESENTANTE_FICTICIO,
        }
        dados.update(troca)
        return self.client.post("/orcamentos/dados-do-contrato/", dados, **AJAX)

    def test_tira_o_rg_e_o_ponto_que_vierem_a_mais(self):
        for digitado in ("RG: 11.222.333-4", "rg 11.222.333-4", "R.G. nº 11.222.333-4", "11.222.333-4"):
            with self.subTest(digitado=digitado):
                resposta = self.salvar(
                    representante_rg=digitado,
                    representante_endereco="Rua Inventada, n. 1, Bairro Ficticio, CEP: 00000-000, Cidade Teste. ",
                )
                self.assertEqual(resposta.status_code, 200, resposta.content)
                dados = DadosContrato.atual()
                self.assertEqual(dados.representante_rg, "11.222.333-4")
                self.assertEqual(
                    dados.representante_endereco, "Rua Inventada, n. 1, Bairro Ficticio, CEP: 00000-000, Cidade Teste",
                )

    def test_a_tela_diz_o_formato_de_cada_campo_e_mostra_o_texto_do_modelo(self):
        self.salvar()
        html = self.client.get("/orcamentos/dados-do-contrato/", **INTERNO).content.decode()
        for pedaco in (
            "neste ato representado por", "portador da cédula de identidade RG: <mark",
            "comparecem aqui, as partes, de um lado", "aqui doravante denominado simplesmente VENDEDOR",
            'placeholder="Rua …, n. …, bairro, CEP: …, cidade"', 'placeholder="00.000.000-0"',
            'id="dcAjudaRg"', 'id="dcAjudaEndereco"', 'id="dcAjudaNome"',
        ):
            self.assertIn(pedaco, html)
        self.assertNotIn("<select", html)


# ======================================================================
# C) A FOTO INTEIRA
# ======================================================================
class FotoDoItemInteiraTests(TestCase):
    """`contain` e presa à moldura: sem `cover`, sem a foto alta passando da moldura."""

    def regra(self, arquivo, seletor):
        css = (RAIZ / arquivo).read_text(encoding="utf-8")
        css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        achadas = re.findall(re.escape(seletor) + r"\s*\{([^}]*)\}", css)
        self.assertTrue(achadas, f"{seletor} não está em {arquivo}")
        return " ".join(achadas[0].split())

    def test_proposta_contrato_e_meus_pedidos(self):
        for arquivo, seletor in (
            ("core/static/site/paginas/orcamento_publico.css", ".item-foto img"),
            ("core/static/site/paginas/assinatura.css", ".ct-foto-quadro img"),
            ("core/static/site/paginas/meus_pedidos.css", ".pd-foto img"),
            ("core/static/site/paginas/meus_pedidos.css", ".pd-item-foto img"),
        ):
            with self.subTest(seletor=seletor):
                regra = self.regra(arquivo, seletor).replace(": ", ":")
                self.assertIn("object-fit:contain", regra)
                self.assertNotIn("cover", regra)
                # presa aos quatro lados da moldura: a altura vem da moldura, e não da foto
                self.assertIn("position:absolute", regra)
                self.assertIn("inset:0", regra)
                self.assertIn("width:100%", regra)
                self.assertIn("height:100%", regra)

    def test_a_moldura_tem_medida_fixa_e_segura_a_foto(self):
        for arquivo, seletor, medidas in (
            ("core/static/site/paginas/orcamento_publico.css", ".item-foto", ("width:76px", "height:76px", "overflow:hidden")),
            ("core/static/site/paginas/assinatura.css", ".ct-foto-quadro", ("position:relative", "aspect-ratio:4 / 3", "overflow:hidden")),
            ("core/static/site/paginas/meus_pedidos.css", ".pd-foto", ("position:relative", "width:56px", "height:56px")),
            ("core/static/site/paginas/meus_pedidos.css", ".pd-item-foto", ("position:relative", "width:72px", "height:72px")),
        ):
            with self.subTest(seletor=seletor):
                regra = self.regra(arquivo, seletor).replace(": ", ":")
                for medida in medidas:
                    self.assertIn(medida, regra)
        proposta = (RAIZ / "core/static/site/paginas/orcamento_publico.css").read_text(encoding="utf-8")
        self.assertIn(".item-foto{position:relative}", proposta)

    def test_nenhuma_foto_dos_documentos_usa_cover(self):
        for arquivo in ("core/static/site/paginas/orcamento_publico.css", "core/static/site/paginas/assinatura.css"):
            css = re.sub(r"/\*.*?\*/", "", (RAIZ / arquivo).read_text(encoding="utf-8"), flags=re.S)
            with self.subTest(arquivo=arquivo):
                self.assertNotRegex(css, r"object-fit:\s*cover")


# ======================================================================
# D) O PEDIDO JÁ APROVADO CONTINUA SAINDO, PARA CONSULTA
# ======================================================================
@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_HOST_USER="envio@exemplo.invalid", EMAIL_HOST_PASSWORD="senha-de-teste",
)
class EnvioDoPedidoAprovadoTests(TestCase):
    def setUp(self):
        self.vendedor = User.objects.create_user("vendedor-envio", password="senha-de-teste")
        atribuir_funcoes(self.vendedor, ("vendas",))
        self.client.force_login(self.vendedor)

    def proposta(self, status, pago=False, **campos):
        padrao = {
            "nome_cliente": "Buffet Alegria Sintético", "whatsapp_cliente": "(11) 97777-6655",
            "email_cliente": "cliente@exemplo.invalid", "status": status, "forma_pagamento": "Pix",
            "validade": timezone.localdate() + timedelta(days=5), "responsavel": self.vendedor,
        }
        padrao.update(campos)
        orcamento = Orcamento.objects.create(**padrao)
        ItemOrcamento.objects.create(
            orcamento=orcamento, descricao="Cama elástica 3 m", quantidade=1, valor_unitario=Decimal("1500.00"),
        )
        if pago:
            orcamento.registrar_pagamento(orcamento.total)
        return orcamento

    def enviar(self, orcamento, canal="preparar", **extras):
        return self.client.post(
            "/orcamentos/", {"action": "enviar", "id": orcamento.pk, "canal": canal, **extras}, **AJAX,
        )

    def aprovada(self, **campos):
        quando = timezone.now() - timedelta(days=2)
        return self.proposta(
            Orcamento.Status.APROVADO, enviado_em=quando - timedelta(days=1), respondido_em=quando,
            respondido_por="Maria Exemplo", **campos,
        )

    def test_quem_sai_e_quem_nao_sai_por_situacao(self):
        S = Orcamento.Status
        ontem = timezone.localdate() - timedelta(days=1)
        casos = (
            (self.proposta(S.RASCUNHO), True, False),
            (self.proposta(S.AGUARDANDO_RESPOSTA), True, False),
            (self.proposta(S.EM_NEGOCIACAO), True, False),
            (self.aprovada(), True, True),
            (self.aprovada(pago=True), True, True),
            (self.aprovada(validade=ontem), True, True),  # aprovada não "vence"
            (self.proposta(S.RECUSADO), False, False),
            (self.proposta(S.EXPIRADO), False, False),
            (self.proposta(S.SUBSTITUIDO), False, False),
            (self.proposta(S.AGUARDANDO_RESPOSTA, validade=ontem), False, False),
        )
        for orcamento, sai, consulta in casos:
            with self.subTest(status=orcamento.status, validade=str(orcamento.validade)):
                self.assertEqual(orcamento.pode_enviar, sai)
                self.assertEqual(orcamento.envio_para_consulta, consulta)
                self.assertEqual(self.enviar(orcamento).status_code, 200 if sai else 400)

    def test_o_reenvio_do_aprovado_nao_mexe_em_nada(self):
        orcamento = self.aprovada(pago=True)
        antes = Orcamento.objects.values(
            "status", "status_pagamento", "enviado_em", "respondido_em", "validade", "venda_id", "valor_pago",
        ).get(pk=orcamento.pk)
        for canal, extras in (("preparar", {}), ("link", {}), ("whatsapp", {"whatsapp": "(11) 97777-6655"}),
                              ("email", {"email": "cliente@exemplo.invalid"})):
            with self.subTest(canal=canal):
                resposta = self.enviar(orcamento, canal, **extras)
                self.assertEqual(resposta.status_code, 200, resposta.content)
                self.assertEqual(resposta.json()["status"], "sucesso")
        depois = Orcamento.objects.values(
            "status", "status_pagamento", "enviado_em", "respondido_em", "validade", "venda_id", "valor_pago",
        ).get(pk=orcamento.pk)
        self.assertEqual(depois, antes)

    def test_aprovado_sem_envio_anterior_nao_ganha_data_de_envio(self):
        """Aprovado por telefone, nunca enviado: o reenvio não inventa "enviada em"."""
        orcamento = self.proposta(Orcamento.Status.APROVADO, respondido_em=timezone.now())
        self.assertEqual(self.enviar(orcamento, "link").status_code, 200)
        orcamento.refresh_from_db()
        self.assertIsNone(orcamento.enviado_em)
        self.assertEqual(orcamento.status, Orcamento.Status.APROVADO)

    def test_a_mensagem_diz_a_situacao_e_nao_pede_decisao(self):
        orcamento = self.aprovada(pago=True)
        corpo = self.enviar(orcamento).json()
        self.assertTrue(corpo["consulta"])
        mensagem = corpo["mensagem"]
        dia = timezone.localtime(orcamento.respondido_em).strftime("%d/%m/%Y")
        self.assertIn(f"Segue o seu *pedido nº {orcamento.pk}* (aprovado em {dia}, pagamento registrado).", mensagem)
        self.assertIn("consultar e imprimir", mensagem)
        self.assertIn("não precisa de login", mensagem)
        self.assertIn(orcamento.caminho_publico, mensagem)
        for proibido in ("aprovar ou pedir ajustes", "Preparamos sua", "Válida até"):
            self.assertNotIn(proibido, mensagem)
        # a que ainda espera resposta continua com o convite de sempre
        esperando = self.enviar(self.proposta(Orcamento.Status.AGUARDANDO_RESPOSTA)).json()
        self.assertFalse(esperando["consulta"])
        self.assertIn("aprovar ou pedir ajustes", esperando["mensagem"])

    def test_o_email_do_aprovado_e_de_consulta(self):
        orcamento = self.aprovada()
        resposta = self.enviar(orcamento, "email", email="cliente@exemplo.invalid")
        self.assertEqual(resposta.status_code, 200, resposta.content)
        carta = mail.outbox[-1]
        self.assertEqual(carta.subject, f"Seu pedido Lazer & Sport #{orcamento.pk}")
        self.assertIn("consultar e imprimir", carta.body)
        self.assertNotIn("registrar sua aprovação", carta.body)
        html = carta.alternatives[0][0]
        self.assertIn("Abrir o pedido", html)
        self.assertNotIn("Abrir proposta e responder", html)
        self.assertNotIn("aprovar ou recusar", html)
        self.assertIn("para consultar e imprimir", html)

    def test_recusada_e_expirada_dizem_o_caminho(self):
        self.assertIn("recusou esta proposta", self.enviar(self.proposta(Orcamento.Status.RECUSADO)).json()["msg"])
        self.assertIn("Nova proposta", self.enviar(self.proposta(Orcamento.Status.EXPIRADO)).json()["msg"])
        self.assertIn("substituída", self.enviar(self.proposta(Orcamento.Status.SUBSTITUIDO)).json()["msg"])

    def test_a_lista_mostra_o_botao_no_aprovado_e_marca_a_consulta(self):
        aprovada = self.aprovada()
        recusada = self.proposta(Orcamento.Status.RECUSADO)
        html = self.client.get("/orcamentos/", **INTERNO).content.decode()
        self.assertRegex(html, rf'data-enviar="{aprovada.pk}"\s+data-consulta="1"')
        self.assertNotIn(f'data-enviar="{recusada.pk}"', html)

    def test_a_pagina_publica_abre_sem_login_so_para_consulta(self):
        orcamento = self.aprovada(pago=True)
        self.client.logout()
        resposta = self.client.get(orcamento.caminho_publico)
        self.assertEqual(resposta.status_code, 200)  # sem login, sem redirecionar
        self.assertFalse(resposta.context["pode_responder"])
        html = resposta.content.decode()
        self.assertIn("Proposta aprovada", html)
        self.assertIn("Pagamento registrado.", html)
        self.assertIn("Cama elástica 3 m", html)
        for proibido in ('name="decisao"', "consentimento_aceite", "Aprovar proposta"):
            self.assertNotIn(proibido, html)
        # um POST à mão não reabre a decisão
        self.client.post(orcamento.caminho_publico, {"decisao": "recusar", "nome": "Fulano", "motivo": "x"})
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, Orcamento.Status.APROVADO)

    def test_o_aviso_do_aprovado_nao_oferece_reenvio(self):
        """O aviso de um aprovado pede o passo seguinte (o contrato), e não um reenvio."""
        fonte = (RAIZ / "sistema_interno" / "resolver_avisos.py").read_text(encoding="utf-8")
        self.assertEqual(fonte.count("orcamento.pode_enviar and not orcamento.envio_para_consulta"), 2)
