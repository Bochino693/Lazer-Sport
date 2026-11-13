"""O documento para assinatura do orçamento aprovado (LEIA-ME-V10, seção 81).

O pedido: "após o orçamento estar como pago (...) vc deve pôr uma opção de
gerar documento, no qual vc gera um documento de assinatura digital para o
cliente assinar no telefone dele em um link que vai ser gerado a cada 5
minutos, para o usuário assinar, com validações de tempo e tudo". E depois:
"após o orçamento atingir aprovado, que você deve gerar a assinatura, a
opção de pagamento deve ser o último estágio".

O que estes testes protegem:

  * só se gera com o orçamento APROVADO (pago ou não), e o retrato
    congela: editar o orçamento depois não muda o documento nem o hash
    dele; o termo não diz "pago" do que não está pago;
  * o pagamento registrado DEPOIS de gerar ou de assinar não suspende,
    não refaz e não troca o documento; recusar (ou expirar) o orçamento
    suspende o link; o termo antigo, que declara "quitado", ainda é
    suspenso se o pagamento for desfeito;
  * o link vale 5 minutos (o relógio do `TimestampSigner` é o que se
    adianta aqui -- não há freezegun no projeto) e é recusado depois, na
    abertura e no envio; o envio fora da janela não grava nada;
  * link fabricado, cortado ou de outro sal é inválido; o link não tem "_"
    nem "-" (o WhatsApp come o "_");
  * gerar de novo mata os links do documento anterior;
  * o CPF/CNPJ tem de conferir com o do cadastro; nome completo, "Li e
    concordo" e um traço de verdade no quadro;
  * assinado não se assina de novo; tudo o que a auditoria precisa fica
    gravado (PNG, nome, documento, hora, IP, navegador, hash);
  * o CSRF vale no formulário público e o freio por IP segura a martelada;
  * quem pode: o Comercial (a permissão de editar o orçamento); o
    Financeiro sozinho não; o Ambulante só nos dele;
  * o histórico do orçamento ganha a linha do "gerou" e a do "assinou",
    com a contagem dos links;
  * a via para "Salvar em PDF" abre, no painel e para o cliente.
"""

import base64
import io
import json
import re
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.core import signing
from django.core.cache import cache
from django.test import Client, TestCase
from django.utils import timezone

from . import documento_assinatura as svc
from .models import (
    AtividadeOrcamento,
    Cliente,
    DocumentoAssinatura,
    ItemOrcamento,
    Orcamento,
)
from .permissoes import atribuir_funcoes

INTERNO = {"HTTP_HOST": "interno.testserver"}
AJAX = {"HTTP_HOST": "interno.testserver", "HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
JSON = {"HTTP_ACCEPT": "application/json"}

CPF_DO_CLIENTE = "529.982.247-25"
OUTRO_CPF = "111.444.777-35"


def png_de_assinatura(largura=600, altura=200, com_traco=True):
    """Um PNG como o do quadro: fundo transparente e um traço escuro."""
    from PIL import Image, ImageDraw

    imagem = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
    if com_traco:
        desenho = ImageDraw.Draw(imagem)
        desenho.line([(40, 150), (160, 60), (260, 140), (420, 50), (560, 120)], fill=(11, 27, 77, 255), width=6)
    saida = io.BytesIO()
    imagem.save(saida, format="PNG")
    return "data:image/png;base64," + base64.b64encode(saida.getvalue()).decode("ascii")


class BaseDocumento(TestCase):
    def setUp(self):
        cache.clear()
        self.vendedor = self.usuario("vendedor", "vendas")
        self.cliente_cadastro = Cliente.objects.create(
            nome_cliente="Buffet Alegria",
            documento=CPF_DO_CLIENTE,
            telefone="(11) 97777-6655",
        )
        self.orcamento = self.criar_orcamento(cliente=self.cliente_cadastro)

    @staticmethod
    def usuario(username, *funcoes):
        user = User.objects.create_user(username=username, password="senha-segura")
        atribuir_funcoes(user, funcoes)
        return user

    def criar_orcamento(self, pago=True, **campos):
        padrao = {
            "nome_cliente": "Buffet Alegria",
            "whatsapp_cliente": "(11) 97777-6655",
            "status": Orcamento.Status.APROVADO,
            "forma_pagamento": "Pix",
            "forma_envio": "Entrega Lazer & Sport",
            "observacoes": "Produção em 20 dias úteis. Garantia de 1 ano.",
            "responsavel": self.vendedor,
        }
        padrao.update(campos)
        orcamento = Orcamento.objects.create(**padrao)
        ItemOrcamento.objects.create(
            orcamento=orcamento, descricao="Cama elástica 3 m",
            quantidade=2, valor_unitario=Decimal("1500.00"),
        )
        if pago:
            orcamento.registrar_pagamento(orcamento.total)
        return orcamento

    def gerar(self, orcamento=None, usuario=None):
        return svc.gerar(orcamento or self.orcamento, usuario or self.vendedor)

    def link(self, documento):
        token, _ = svc.emitir_link(documento)
        return token

    def dados_validos(self, **troca):
        dados = {
            "nome": "Maria Alegria da Silva",
            "documento": CPF_DO_CLIENTE,
            "concordo": "1",
            "assinatura": png_de_assinatura(),
        }
        dados.update(troca)
        return dados

    def assinar(self, token, client=None, **troca):
        return (client or self.client).post(
            f"/assinar/{token}/", self.dados_validos(**troca),
            HTTP_USER_AGENT="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
            REMOTE_ADDR="200.150.10.20",
            **JSON,
        )


# ======================================================================
# GERAR: só aprovado, retrato congelado, gerar de novo
# ======================================================================
class GerarDocumentoTests(BaseDocumento):

    def test_so_gera_com_o_orcamento_aprovado(self):
        self.client.force_login(self.vendedor)
        for status in (
            Orcamento.Status.RASCUNHO, Orcamento.Status.AGUARDANDO_RESPOSTA,
            Orcamento.Status.EM_NEGOCIACAO, Orcamento.Status.RECUSADO,
            Orcamento.Status.EXPIRADO, Orcamento.Status.SUBSTITUIDO,
        ):
            with self.subTest(status=status):
                fora = self.criar_orcamento(pago=False, status=status)
                resposta = self.client.post(f"/orcamentos/{fora.pk}/documento/", {"action": "gerar"}, **AJAX)
                self.assertEqual(resposta.status_code, 409)
                self.assertIn("aprovado", resposta.json()["msg"])
                self.assertIn(fora.get_status_display(), resposta.json()["msg"])
                self.assertFalse(DocumentoAssinatura.objects.filter(orcamento=fora).exists())
                with self.assertRaises(Exception):
                    svc.gerar(fora, self.vendedor)

        resposta = self.client.post(f"/orcamentos/{self.orcamento.pk}/documento/", {"action": "gerar"}, **AJAX)
        self.assertEqual(resposta.status_code, 200)
        corpo = resposta.json()
        self.assertEqual(corpo["status"], "sucesso")
        self.assertIn("Aguardando assinatura", corpo["html"])
        documento = DocumentoAssinatura.objects.get(orcamento=self.orcamento)
        self.assertEqual(documento.situacao, DocumentoAssinatura.Situacao.AGUARDANDO)
        self.assertEqual(documento.criado_por, self.vendedor)

    def test_aprovado_sem_pagamento_gera_e_o_termo_nao_diz_pago(self):
        """A assinatura vem ANTES do pagamento: aprovado basta."""
        pendente = self.criar_orcamento(pago=False, respondido_em=timezone.now())
        self.client.force_login(self.vendedor)
        pagina = self.client.get(f"/orcamentos/{pendente.pk}/documento/", **INTERNO)
        self.assertContains(pagina, "Gerar documento para assinatura")
        self.assertContains(pagina, "O orçamento está aprovado")

        resposta = self.client.post(f"/orcamentos/{pendente.pk}/documento/", {"action": "gerar"}, **AJAX)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        conteudo = DocumentoAssinatura.objects.get(orcamento=pendente).conteudo
        self.assertEqual(conteudo["titulo"], "Termo de compra")
        self.assertEqual(conteudo["modelo"], svc.VERSAO_DO_MODELO)
        self.assertEqual(conteudo["pagamento"]["situacao"], "Pagamento pendente")
        self.assertFalse(conteudo["pagamento"]["quitado"])
        self.assertEqual(conteudo["pagamento"]["forma"], "Pix")
        self.assertEqual(conteudo["valores"]["pago"], "0.00")
        self.assertEqual(conteudo["valores"]["saldo"], "3000.00")
        self.assertTrue(conteudo["orcamento"]["aprovado_em"])
        texto = " ".join(conteudo["declaracao"])
        self.assertIn("aprovado em", texto)
        self.assertIn("condições combinadas neste orçamento: Pix.", texto)
        self.assertIn("nenhum valor foi recebido", texto)
        for palavra in ("quitado", "foi feito", "pago:"):
            self.assertNotIn(palavra, texto)

        # A folha (a do cliente e a via) também não diz "Pago".
        documento = DocumentoAssinatura.objects.get(orcamento=pendente)
        folha = self.client.get(f"/assinar/{self.link(documento)}/").content.decode()
        self.assertIn("Aprovado · pagamento pendente", folha)
        self.assertIn("A pagar", folha)
        self.assertNotIn("✓ Pago", folha)
        self.assertIn("· aprovado</span>", folha)
        self.assertIn("Li e concordo com o termo de compra acima.", folha)

    def test_pagamento_parcial_entra_no_termo_como_o_que_ja_entrou(self):
        parcial = self.criar_orcamento(pago=False)
        parcial.registrar_pagamento(Decimal("1000.00"))
        conteudo = self.gerar(parcial).conteudo
        texto = " ".join(conteudo["declaracao"])
        self.assertIn("foram recebidos R$ 1.000,00; restam R$ 2.000,00", texto)
        self.assertNotIn("quitado", texto)
        self.assertEqual(conteudo["valores"]["pago"], "1000.00")
        self.assertEqual(conteudo["valores"]["saldo"], "2000.00")

    def test_o_retrato_congela_e_o_hash_e_o_do_json(self):
        documento = self.gerar()
        conteudo = documento.conteudo

        self.assertEqual(conteudo["titulo"], "Termo de compra")
        self.assertTrue(any("o valor total já foi recebido (R$ 3.000,00" in p for p in conteudo["declaracao"]))
        self.assertEqual(conteudo["orcamento"]["numero"], self.orcamento.numero_documento)
        self.assertEqual(conteudo["orcamento"]["versao"], 1)
        self.assertEqual(conteudo["cliente"]["nome"], "Buffet Alegria")
        self.assertEqual(conteudo["itens"][0]["descricao"], "Cama elástica 3 m")
        self.assertEqual(conteudo["itens"][0]["quantidade"], 2)
        self.assertEqual(conteudo["valores"]["total"], "3000.00")
        self.assertEqual(conteudo["valores"]["pago"], "3000.00")
        self.assertEqual(conteudo["pagamento"]["situacao"], "Pago")
        self.assertTrue(conteudo["pagamento"]["pago_em"])
        self.assertEqual(conteudo["condicoes"]["forma_envio"], "Entrega Lazer & Sport")
        self.assertIn("20 dias úteis", conteudo["condicoes"]["observacoes"])
        self.assertTrue(conteudo["empresa"]["nome"] and conteudo["empresa"]["cnpj"])
        self.assertTrue(any("R$ 3.000,00" in p for p in conteudo["declaracao"]))

        # O hash é o SHA-256 do JSON canônico -- inclusive depois de ir e
        # voltar do banco.
        documento.refresh_from_db()
        self.assertEqual(documento.hash_conteudo, svc.hash_do_retrato(documento.conteudo))
        self.assertEqual(len(documento.hash_conteudo), 64)

        # Editar o orçamento depois não muda o documento.
        hash_antes = documento.hash_conteudo
        item = self.orcamento.itens.get()
        item.descricao = "Outra coisa"
        item.valor_unitario = Decimal("1.00")
        item.save()
        self.orcamento.observacoes = "Mudou tudo"
        self.orcamento.save()
        documento.refresh_from_db()
        self.assertEqual(documento.conteudo["itens"][0]["descricao"], "Cama elástica 3 m")
        self.assertEqual(documento.hash_conteudo, hash_antes)
        self.assertEqual(svc.hash_do_retrato(documento.conteudo), hash_antes)

    def test_gerar_de_novo_substitui_e_mata_os_links_antigos(self):
        primeiro = self.gerar()
        token_velho = self.link(primeiro)
        self.assertEqual(svc.ler_link(token_velho).situacao, "valido")

        segundo = self.gerar()
        primeiro.refresh_from_db()
        self.assertEqual(primeiro.situacao, DocumentoAssinatura.Situacao.SUBSTITUIDO)
        self.assertEqual(segundo.situacao, DocumentoAssinatura.Situacao.AGUARDANDO)
        self.assertEqual(svc.documento_atual(self.orcamento), segundo)

        self.assertEqual(svc.ler_link(token_velho).situacao, "substituido")
        resposta = self.client.get(f"/assinar/{token_velho}/")
        self.assertEqual(resposta.status_code, 410)
        self.assertContains(resposta, "Este link foi trocado", status_code=410)
        # E o envio com o link velho não grava.
        resposta = self.assinar(token_velho)
        self.assertEqual(resposta.status_code, 410)
        self.assertFalse(DocumentoAssinatura.objects.filter(situacao="assinado").exists())

        self.assertEqual(svc.ler_link(self.link(segundo)).situacao, "valido")

    def test_um_hash_que_nao_bate_tambem_e_link_trocado(self):
        """O link carrega o começo do hash: o documento mudou, o link morre."""
        documento = self.gerar()
        token = self.link(documento)
        DocumentoAssinatura.objects.filter(pk=documento.pk).update(hash_conteudo="f" * 64)
        self.assertEqual(svc.ler_link(token).situacao, "substituido")

    def test_assinado_nao_gera_de_novo(self):
        documento = self.gerar()
        self.assertEqual(self.assinar(self.link(documento)).status_code, 200)
        with self.assertRaises(Exception):
            self.gerar()
        self.client.force_login(self.vendedor)
        resposta = self.client.post(f"/orcamentos/{self.orcamento.pk}/documento/", {"action": "gerar"}, **AJAX)
        self.assertEqual(resposta.status_code, 409)
        self.assertIn("já tem um documento assinado", resposta.json()["msg"])


# ======================================================================
# O LINK DE 5 MINUTOS
# ======================================================================
class LinkDeCincoMinutosTests(BaseDocumento):

    def test_vale_dentro_dos_5_minutos_e_expira_depois(self):
        documento = self.gerar()
        agora = 1_800_000_000
        with mock.patch("django.core.signing.time.time", return_value=agora):
            token = self.link(documento)

        for passados, esperado in ((0, "valido"), (60, "valido"), (299, "valido"), (300, "valido"),
                                   (301, "expirado"), (3600, "expirado")):
            with self.subTest(segundos=passados):
                with mock.patch("django.core.signing.time.time", return_value=agora + passados):
                    self.assertEqual(svc.ler_link(token).situacao, esperado)

        with mock.patch("django.core.signing.time.time", return_value=agora + 120):
            resposta = self.client.get(f"/assinar/{token}/")
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'data-restante="180"')

        with mock.patch("django.core.signing.time.time", return_value=agora + 301):
            resposta = self.client.get(f"/assinar/{token}/")
        self.assertEqual(resposta.status_code, 410)
        self.assertContains(resposta, "Este link expirou", status_code=410)
        self.assertContains(resposta, "Peça um novo ao atendente", status_code=410)
        self.assertNotContains(resposta, "Cama elástica", status_code=410)

    def test_o_envio_fora_da_janela_nao_grava_nada(self):
        documento = self.gerar()
        agora = 1_800_000_000
        with mock.patch("django.core.signing.time.time", return_value=agora):
            token = self.link(documento)
        with mock.patch("django.core.signing.time.time", return_value=agora + 301):
            resposta = self.assinar(token)
        self.assertEqual(resposta.status_code, 410)
        self.assertEqual(resposta.json()["situacao"], "expirado")
        self.assertIn("Nada foi salvo", resposta.json()["msg"])
        documento.refresh_from_db()
        self.assertEqual(documento.situacao, DocumentoAssinatura.Situacao.AGUARDANDO)
        self.assertFalse(documento.assinatura_png)
        self.assertEqual(documento.assinante_nome, "")

        # Dentro da janela, o mesmo envio grava.
        with mock.patch("django.core.signing.time.time", return_value=agora + 290):
            self.assertEqual(self.assinar(token).status_code, 200)

    def test_link_fabricado_cortado_ou_de_outro_sal_e_invalido(self):
        documento = self.gerar()
        token = self.link(documento)
        trocado = token[:-1] + ("A" if token[-1] != "A" else "B")
        outro_sal = signing.TimestampSigner(salt="outra-coisa").sign(svc._carga(documento))

        for ruim in (trocado, token[:-5], "1.abc.def.ghi", "nada", outro_sal, token + "x" * 300):
            with self.subTest(token=ruim[:30]):
                self.assertEqual(svc.ler_link(ruim).situacao, "invalido")
        resposta = self.client.get(f"/assinar/{trocado}/")
        self.assertEqual(resposta.status_code, 404)
        self.assertContains(resposta, "Link inválido", status_code=404)

    def test_o_link_so_tem_letras_numeros_e_ponto(self):
        """O "_" do base64 já derrubou o link da proposta no WhatsApp."""
        documento = self.gerar()
        for _ in range(30):
            self.assertRegex(self.link(documento), r"^[0-9A-Za-z.]+$")

    def test_o_painel_gera_o_link_e_conta(self):
        documento = self.gerar()
        self.client.force_login(self.vendedor)

        resposta = self.client.get(f"/orcamentos/{self.orcamento.pk}/documento/link/", **AJAX)
        self.assertEqual(resposta.status_code, 405)

        resposta = self.client.post(f"/orcamentos/{self.orcamento.pk}/documento/link/", **AJAX)
        self.assertEqual(resposta.status_code, 200)
        corpo = resposta.json()
        self.assertIn("/assinar/", corpo["link"])
        self.assertTrue(corpo["qr"].startswith("<svg"))
        self.assertEqual(corpo["validade"], 300)
        self.assertAlmostEqual(corpo["expira_em"] - corpo["agora"], 300_000, delta=2000)
        self.assertIn("wa.me/5511977776655", corpo["whatsapp"])
        self.assertIn("5 minutos", corpo["mensagem"])
        # O termo sai na aprovação: a conversa diz "aprovado", não "pago".
        self.assertIn(f"Seu pedido nº {self.orcamento.numero_documento} foi *aprovado*", corpo["mensagem"])
        self.assertIn("Assine aqui", corpo["mensagem"])
        self.assertNotIn("*pago*", corpo["mensagem"])
        self.assertEqual(corpo["numero"], 1)

        token = corpo["link"].rstrip("/").rsplit("/", 1)[1]
        self.assertEqual(svc.ler_link(token).situacao, "valido")

        self.client.post(f"/orcamentos/{self.orcamento.pk}/documento/link/", **AJAX)
        documento.refresh_from_db()
        self.assertEqual(documento.links_gerados, 2)
        self.assertIsNotNone(documento.ultimo_link_em)

    def test_sem_documento_ou_ja_assinado_nao_sai_link(self):
        self.client.force_login(self.vendedor)
        resposta = self.client.post(f"/orcamentos/{self.orcamento.pk}/documento/link/", **AJAX)
        self.assertEqual(resposta.status_code, 409)

        documento = self.gerar()
        self.assinar(self.link(documento))
        resposta = self.client.post(f"/orcamentos/{self.orcamento.pk}/documento/link/", **AJAX)
        self.assertEqual(resposta.status_code, 409)
        self.assertIn("assinado", resposta.json()["msg"])

    def test_o_pagamento_depois_de_gerar_nao_mexe_no_documento(self):
        """O pagamento é o estágio seguinte: nem suspende, nem "desatualiza"."""
        pendente = self.criar_orcamento(pago=False)
        documento = self.gerar(pendente)
        token = self.link(documento)
        hash_antes = documento.hash_conteudo

        for valor in ("1000.00", "3000.00", "0.00", "3000.00"):
            with self.subTest(valor=valor):
                pendente.registrar_pagamento(Decimal(valor))
                self.assertEqual(svc.ler_link(token).situacao, "valido")
                documento.refresh_from_db()
                self.assertEqual(documento.hash_conteudo, hash_antes)
                self.assertEqual(svc.situacao_do_cartao(pendente, documento), "aguardando")
                self.assertEqual(svc.documento_atual(pendente), documento)
        self.assertEqual(DocumentoAssinatura.objects.filter(orcamento=pendente).count(), 1)

        # E assina com o pagamento já quitado depois de gerar.
        self.assertEqual(self.assinar(token).status_code, 200)

    def test_o_pagamento_depois_de_assinar_nao_invalida_a_assinatura(self):
        pendente = self.criar_orcamento(pago=False)
        documento = self.gerar(pendente)
        token = self.link(documento)
        self.assertEqual(self.assinar(token).status_code, 200)
        documento.refresh_from_db()
        assinado = (documento.hash_conteudo, documento.hash_assinado, documento.assinado_em)

        pendente.registrar_pagamento(pendente.total)
        pendente.registrar_pagamento(Decimal("0.00"))  # e até um estorno

        documento.refresh_from_db()
        self.assertTrue(documento.assinado)
        self.assertEqual((documento.hash_conteudo, documento.hash_assinado, documento.assinado_em), assinado)
        self.assertEqual(svc.ler_link(token).situacao, "assinado")
        self.assertEqual(svc.situacao_do_cartao(pendente, documento), "assinado")
        self.assertEqual(Client().get(f"/assinado/{documento.codigo_publico}/").status_code, 200)

    def test_recusado_depois_de_gerar_suspende_o_link(self):
        documento = self.gerar()
        token = self.link(documento)
        self.orcamento.registrar_recusa("Desistiu", por="Cliente")

        leitura = svc.ler_link(token)
        self.assertEqual((leitura.situacao, leitura.motivo), ("suspenso", "aprovacao"))
        resposta = self.client.get(f"/assinar/{token}/")
        self.assertEqual(resposta.status_code, 410)
        self.assertContains(resposta, "não está mais aprovado", status_code=410)
        resposta = self.assinar(token)
        self.assertEqual(resposta.status_code, 410)
        self.assertIn("o pedido mudou", resposta.json()["msg"])
        documento.refresh_from_db()
        self.assertFalse(documento.assinado)

        self.client.force_login(self.vendedor)
        resposta = self.client.post(f"/orcamentos/{self.orcamento.pk}/documento/link/", **AJAX)
        self.assertEqual(resposta.status_code, 409)
        self.assertIn("não está mais aprovado", resposta.json()["msg"])
        pagina = self.client.get(f"/orcamentos/{self.orcamento.pk}/documento/", **INTERNO)
        self.assertContains(pagina, "Documento suspenso")
        self.assertContains(pagina, "recusado")
        # Nem gerar de novo: não há compra aprovada.
        resposta = self.client.post(f"/orcamentos/{self.orcamento.pk}/documento/", {"action": "gerar"}, **AJAX)
        self.assertEqual(resposta.status_code, 409)

    def test_o_termo_antigo_do_orcamento_pago_continua_valendo(self):
        """Os documentos gerados na regra antiga ("só com o orçamento pago").

        Continuam abrindo e assinando. A declaração deles diz "quitado":
        só ELES ainda ficam suspensos se o pagamento for desfeito.
        """
        documento = self.gerar()
        # O retrato como a regra antiga gravava: outro modelo, outro título,
        # sem as chaves novas.
        conteudo = dict(documento.conteudo, modelo=svc.MODELO_DO_RECIBO, titulo="Termo de compra e recibo")
        conteudo["pagamento"] = {k: v for k, v in conteudo["pagamento"].items() if k != "quitado"}
        conteudo["valores"] = {k: v for k, v in conteudo["valores"].items() if k != "saldo"}
        DocumentoAssinatura.objects.filter(pk=documento.pk).update(
            conteudo=conteudo, hash_conteudo=svc.hash_do_retrato(conteudo),
        )
        documento.refresh_from_db()
        token = self.link(documento)
        self.assertEqual(svc.ler_link(token).situacao, "valido")
        pagina = self.client.get(f"/assinar/{token}/")
        self.assertContains(pagina, "Termo de compra e recibo")
        self.assertContains(pagina, "· pago</span>")
        self.assertContains(pagina, "✓ Pago")

        self.orcamento.registrar_pagamento(Decimal("0.00"))
        leitura = svc.ler_link(token)
        self.assertEqual((leitura.situacao, leitura.motivo), ("suspenso", "pagamento"))
        self.assertContains(self.client.get(f"/assinar/{token}/"), "O pagamento deste pedido mudou", status_code=410)
        self.client.force_login(self.vendedor)
        self.assertContains(
            self.client.get(f"/orcamentos/{self.orcamento.pk}/documento/", **INTERNO),
            "do modelo antigo",
        )

        self.orcamento.registrar_pagamento(self.orcamento.total)
        self.assertEqual(svc.ler_link(token).situacao, "valido")
        self.assertEqual(self.assinar(token).status_code, 200)


# ======================================================================
# A PÁGINA DO CLIENTE E A ASSINATURA
# ======================================================================
class AssinaturaPublicaTests(BaseDocumento):

    def test_o_link_valido_mostra_o_documento_e_mais_nada(self):
        outro = self.criar_orcamento(nome_cliente="Concorrente Segredo")
        ItemOrcamento.objects.create(orcamento=outro, descricao="Item do outro", quantidade=1, valor_unitario=Decimal("9.00"))
        documento = self.gerar()

        resposta = self.client.get(f"/assinar/{self.link(documento)}/")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta["Cache-Control"], "no-store")
        self.assertIn("noindex", resposta["X-Robots-Tag"])
        self.assertContains(resposta, "Termo de compra")
        self.assertContains(resposta, "Cama elástica 3 m")
        self.assertContains(resposta, "R$ 3.000,00")
        self.assertContains(resposta, "csrfmiddlewaretoken")
        self.assertContains(resposta, 'id="quadroAssinatura"')
        self.assertContains(resposta, "Li e concordo")
        # O CPF do cadastro aparece mascarado: é o que o cliente digita.
        self.assertContains(resposta, "529.***.***-25")
        self.assertNotContains(resposta, CPF_DO_CLIENTE)
        self.assertNotContains(resposta, "Concorrente Segredo")
        self.assertNotContains(resposta, "Item do outro")
        self.assertNotContains(resposta, "interno.")

    def test_assinar_grava_tudo_o_que_a_auditoria_precisa(self):
        documento = self.gerar()
        token = self.link(documento)
        self.link(documento)  # um segundo link: a contagem vai ao histórico

        resposta = self.assinar(token)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        corpo = resposta.json()
        self.assertTrue(corpo["ok"])
        documento.refresh_from_db()
        self.assertIn(str(documento.codigo_publico), corpo["destino"])

        self.assertEqual(documento.situacao, DocumentoAssinatura.Situacao.ASSINADO)
        self.assertEqual(documento.assinante_nome, "Maria Alegria da Silva")
        self.assertEqual(documento.assinante_documento, "52998224725")
        self.assertEqual(documento.assinatura_ip, "200.150.10.20")
        self.assertIn("iPhone", documento.assinatura_navegador)
        self.assertEqual(documento.hash_assinado, documento.hash_conteudo)
        self.assertTrue(bytes(documento.assinatura_png).startswith(b"\x89PNG"))
        self.assertLessEqual(len(bytes(documento.assinatura_png)), svc.TAMANHO_MAXIMO_DA_ASSINATURA)
        self.assertAlmostEqual(documento.assinado_em, timezone.now(), delta=timedelta(seconds=30))

        # O link agora leva ao comprovante, mesmo vencido.
        resposta = self.client.get(f"/assinar/{token}/")
        self.assertRedirects(resposta, f"/assinado/{documento.codigo_publico}/", fetch_redirect_response=False)
        with mock.patch("django.core.signing.time.time", return_value=10**10):
            self.assertEqual(self.client.get(f"/assinar/{token}/").status_code, 302)

        comprovante = self.client.get(f"/assinado/{documento.codigo_publico}/")
        self.assertEqual(comprovante.status_code, 200)
        self.assertContains(comprovante, "Documento já assinado")
        self.assertContains(comprovante, "Maria Alegria da Silva")
        self.assertContains(comprovante, "Baixar PDF")
        self.assertContains(comprovante, "data:image/png;base64,")
        self.assertContains(comprovante, documento.hash_conteudo)
        self.assertContains(comprovante, "200.150.10.20")
        self.assertContains(self.client.get(f"/assinado/{documento.codigo_publico}/?pronto=1"), "Pronto! Documento assinado.")

    def test_nao_se_assina_duas_vezes(self):
        documento = self.gerar()
        token = self.link(documento)
        self.assertEqual(self.assinar(token).status_code, 200)

        resposta = self.assinar(token, nome="Outra Pessoa Qualquer", documento=OUTRO_CPF)
        self.assertEqual(resposta.status_code, 409)
        self.assertIn("já foi assinado", resposta.json()["msg"])
        self.assertIn(str(documento.codigo_publico), resposta.json()["destino"])
        documento.refresh_from_db()
        self.assertEqual(documento.assinante_nome, "Maria Alegria da Silva")

    def test_o_cpf_tem_de_conferir_com_o_do_cadastro(self):
        documento = self.gerar()
        token = self.link(documento)

        resposta = self.assinar(token, documento=OUTRO_CPF)
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.json()["campo"], "documento")
        self.assertIn("não confere com o do cadastro", resposta.json()["msg"])
        self.assertIn("529.***.***-25", resposta.json()["msg"])
        documento.refresh_from_db()
        self.assertFalse(documento.assinado)

        # Só com pontuação diferente, é o mesmo CPF.
        self.assertEqual(self.assinar(token, documento="52998224725").status_code, 200)

    def test_sem_cpf_no_cadastro_basta_um_documento_valido(self):
        sem_cpf = Cliente.objects.create(nome_cliente="Escola Feliz")
        orcamento = self.criar_orcamento(cliente=sem_cpf)
        documento = self.gerar(orcamento)
        self.assertEqual(self.assinar(self.link(documento), documento=OUTRO_CPF).status_code, 200)

    def test_cada_campo_recusado_volta_com_o_campo_marcado(self):
        documento = self.gerar()
        token = self.link(documento)
        casos = {
            "nome": {"nome": "Maria"},
            "documento": {"documento": "123.456.789-00"},
            "concordo": {"concordo": ""},
            "assinatura": {"assinatura": png_de_assinatura(com_traco=False)},
        }
        for campo, troca in casos.items():
            with self.subTest(campo=campo):
                resposta = self.assinar(token, **troca)
                self.assertEqual(resposta.status_code, 400)
                self.assertEqual(resposta.json()["campo"], campo)
        for ruim in ("", "data:image/jpeg;base64,AAAA", "data:image/png;base64,@@@@",
                     "data:image/png;base64," + base64.b64encode(b"nao e png").decode()):
            with self.subTest(assinatura=ruim[:25]):
                resposta = self.assinar(token, assinatura=ruim)
                self.assertEqual(resposta.status_code, 400)
                self.assertEqual(resposta.json()["campo"], "assinatura")
        documento.refresh_from_db()
        self.assertFalse(documento.assinado)

    def test_assinatura_grande_demais_e_recusada(self):
        documento = self.gerar()
        enorme = "data:image/png;base64," + "A" * (svc.TAMANHO_MAXIMO_DA_ASSINATURA * 2)
        resposta = self.assinar(self.link(documento), assinatura=enorme)
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("grande demais", resposta.json()["msg"])

    def test_sem_javascript_o_erro_volta_na_propria_pagina(self):
        documento = self.gerar()
        token = self.link(documento)
        resposta = self.client.post(f"/assinar/{token}/", self.dados_validos(nome="Maria"))
        self.assertEqual(resposta.status_code, 400)
        self.assertContains(resposta, "nome completo", status_code=400)
        self.assertContains(resposta, 'value="Maria"', status_code=400)

    def test_o_formulario_publico_exige_csrf(self):
        documento = self.gerar()
        token = self.link(documento)
        rigido = Client(enforce_csrf_checks=True)
        resposta = self.assinar(token, client=rigido)
        self.assertEqual(resposta.status_code, 403)
        documento.refresh_from_db()
        self.assertFalse(documento.assinado)

        # Com o token do formulário, passa.
        pagina = rigido.get(f"/assinar/{token}/")
        csrf = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', pagina.content.decode()).group(1)
        resposta = rigido.post(
            f"/assinar/{token}/", {**self.dados_validos(), "csrfmiddlewaretoken": csrf}, **JSON,
        )
        self.assertEqual(resposta.status_code, 200)

    def test_o_freio_segura_quem_martela_o_envio(self):
        documento = self.gerar()
        token = self.link(documento)
        for _ in range(svc.TENTATIVAS_POR_JANELA):
            self.assertEqual(self.assinar(token, nome="X").status_code, 400)
        resposta = self.assinar(token)
        self.assertEqual(resposta.status_code, 429)
        documento.refresh_from_db()
        self.assertFalse(documento.assinado)


# ======================================================================
# QUEM PODE
# ======================================================================
class PermissoesDoDocumentoTests(BaseDocumento):

    def test_comercial_abre_financeiro_sozinho_nao(self):
        self.client.force_login(self.vendedor)
        resposta = self.client.get(f"/orcamentos/{self.orcamento.pk}/documento/", **INTERNO)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta["Cache-Control"], "no-store")
        self.assertContains(resposta, "Gerar documento para assinatura")

        financeiro = self.usuario("financeiro", "financeiro")
        self.client.force_login(financeiro)
        for caminho in ("", "link/", "estado/", "via/"):
            with self.subTest(caminho=caminho):
                metodo = self.client.post if caminho == "link/" else self.client.get
                self.assertEqual(metodo(f"/orcamentos/{self.orcamento.pk}/documento/{caminho}", **INTERNO).status_code, 403)
        self.assertEqual(
            self.client.post(f"/orcamentos/{self.orcamento.pk}/documento/", {"action": "gerar"}, **AJAX).status_code,
            403,
        )
        self.assertFalse(DocumentoAssinatura.objects.exists())

    def test_ambulante_so_nos_orcamentos_dele(self):
        ambulante = self.usuario("ambulante", "ambulante")
        dele = self.criar_orcamento(responsavel=ambulante)
        self.client.force_login(ambulante)
        self.assertEqual(self.client.get(f"/orcamentos/{dele.pk}/documento/", **INTERNO).status_code, 200)
        self.assertEqual(self.client.get(f"/orcamentos/{self.orcamento.pk}/documento/", **INTERNO).status_code, 404)
        # Por fetch, o 404 do painel vira o 409 "registro não existe mais"
        # (o middleware de respostas do painel); link nenhum sai.
        resposta = self.client.post(f"/orcamentos/{self.orcamento.pk}/documento/link/", **AJAX)
        self.assertIn(resposta.status_code, (404, 409))
        self.assertNotIn("link", resposta.json())

    def test_sem_login_vai_para_o_login(self):
        resposta = self.client.get(f"/orcamentos/{self.orcamento.pk}/documento/", **INTERNO)
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("login", resposta["Location"])

    def test_o_botao_da_lista_aparece_no_orcamento_aprovado(self):
        aprovado_sem_pagar = self.criar_orcamento(pago=False)
        aguardando = self.criar_orcamento(pago=False, status=Orcamento.Status.AGUARDANDO_RESPOSTA)
        self.client.force_login(self.vendedor)
        html = self.client.get("/orcamentos/?filtro=todos", **INTERNO).content.decode()
        self.assertIn(f'href="/orcamentos/{self.orcamento.pk}/documento/"', html)
        # A assinatura vem antes do pagamento: aprovado basta.
        self.assertIn(f'href="/orcamentos/{aprovado_sem_pagar.pk}/documento/"', html)
        self.assertNotIn(f'href="/orcamentos/{aguardando.pk}/documento/"', html)
        self.assertIn("Gerar documento para assinatura", html)
        # E vem ANTES do botão do pagamento, na ordem dos estágios (quem vê
        # os dois é quem tem o comercial e o financeiro: a gestão).
        self.client.force_login(User.objects.create_superuser("gestao-doc", "g@example.com", "x"))
        completo = self.client.get("/orcamentos/?filtro=todos", **INTERNO).content.decode()
        self.assertLess(
            completo.index(f'href="/orcamentos/{aprovado_sem_pagar.pk}/documento/"'),
            completo.index(f'data-pagamento="{aprovado_sem_pagar.pk}"'),
        )
        self.assertIn('data-contrato="gerar"', completo)
        self.client.force_login(self.vendedor)

        documento = self.gerar()
        html = self.client.get("/orcamentos/", **INTERNO).content.decode()
        self.assertIn('data-documento-assinatura="aguardando"', html)
        self.assinar(self.link(documento))
        html = self.client.get("/orcamentos/", **INTERNO).content.decode()
        self.assertIn('data-documento-assinatura="assinado"', html)
        self.assertIn("Documento assinado", html)

        # E a janela do orçamento leva o atalho (a partir da aprovação).
        dados = json.loads(re.search(
            r'<script id="orcamentosDados" type="application/json">(.*?)</script>', html, re.S,
        ).group(1))
        por_id = {d["id"]: d for d in dados}
        self.assertEqual(por_id[self.orcamento.pk]["documento_assinatura"]["situacao"], "assinado")
        self.assertEqual(por_id[aprovado_sem_pagar.pk]["documento_assinatura"]["situacao"], "gerar")
        self.assertIsNone(por_id[aguardando.pk]["documento_assinatura"])

    def test_com_o_contrato_assinado_a_proposta_nao_ganha_outra_versao(self):
        """Refazer deixaria o termo assinado apontando para uma "substituída"."""
        pendente = self.criar_orcamento(pago=False)
        self.assertTrue(pendente.pode_refazer)
        self.assinar(self.link(self.gerar(pendente)))
        pendente = Orcamento.objects.get(pk=pendente.pk)
        self.assertTrue(pendente.contrato_assinado)
        self.assertFalse(pendente.pode_refazer)
        self.client.force_login(self.vendedor)
        resposta = self.client.post("/orcamentos/", {"action": "refazer", "id": pendente.pk}, **AJAX)
        self.assertGreaterEqual(resposta.status_code, 400)
        self.assertIn("já assinou o termo", resposta.json()["msg"])

    def test_financeiro_nao_ve_o_botao_da_lista(self):
        financeiro = self.usuario("financeiro2", "financeiro")
        self.client.force_login(financeiro)
        html = self.client.get("/orcamentos/", **INTERNO).content.decode()
        self.assertNotIn(f'href="/orcamentos/{self.orcamento.pk}/documento/"', html)
        self.assertNotIn("data-documento-assinatura=", html)


# ======================================================================
# HISTÓRICO, ESTADO E A VIA EM PDF
# ======================================================================
class HistoricoEViaTests(BaseDocumento):

    def test_o_historico_ganha_o_gerou_e_o_assinou_com_a_contagem(self):
        documento = self.gerar()
        gerou = AtividadeOrcamento.objects.get(orcamento=self.orcamento, tipo=AtividadeOrcamento.Tipo.DOCUMENTO)
        self.assertEqual(gerou.autor, self.vendedor)
        self.assertIn(documento.hash_conteudo[:12], gerou.resumo)

        self.link(documento)
        self.link(documento)
        token = self.link(documento)
        self.assinar(token)
        assinou = AtividadeOrcamento.objects.get(orcamento=self.orcamento, tipo=AtividadeOrcamento.Tipo.ASSINATURA)
        self.assertIsNone(assinou.autor)
        self.assertEqual(assinou.autor_nome, "Maria Alegria da Silva (cliente)")
        self.assertIn("3 links gerados", assinou.resumo)
        self.assertIn("529.***.***-25", assinou.resumo)
        # Renovar o link não vira uma linha por link: só conta.
        self.assertEqual(AtividadeOrcamento.objects.filter(orcamento=self.orcamento).count(), 2)

    def test_gerar_de_novo_conta_os_links_do_anterior(self):
        primeiro = self.gerar()
        self.link(primeiro)
        self.link(primeiro)
        self.gerar()
        refeito = AtividadeOrcamento.objects.filter(
            orcamento=self.orcamento, tipo=AtividadeOrcamento.Tipo.DOCUMENTO,
        ).order_by("-id").first()
        self.assertIn("Documento refeito", refeito.resumo)
        self.assertIn("2 links gerados", refeito.resumo)

    def test_o_sino_da_equipe_conta_a_assinatura(self):
        from .avisos import _atividades_orcamento

        documento = self.gerar()
        self.assinar(self.link(documento))
        colega = self.usuario("colega", "vendas")
        avisos = _atividades_orcamento(colega)
        self.assertEqual(len(avisos), 1)
        self.assertIn("assinou o documento do orçamento", avisos[0].detalhe)

    def test_o_estado_troca_o_cartao_quando_assina(self):
        documento = self.gerar()
        self.client.force_login(self.vendedor)
        url = f"/orcamentos/{self.orcamento.pk}/documento/estado/"

        corpo = self.client.get(url, {"documento": documento.pk, "situacao": "aguardando"}, **AJAX).json()
        self.assertFalse(corpo["mudou"])
        self.assertNotIn("html", corpo)

        self.assinar(self.link(documento), client=Client())
        corpo = self.client.get(url, {"documento": documento.pk, "situacao": "aguardando"}, **AJAX).json()
        self.assertTrue(corpo["mudou"])
        self.assertTrue(corpo["assinado"])
        self.assertIn("Assinado por Maria Alegria da Silva", corpo["html"])
        self.assertIn("Baixar PDF", corpo["html"])
        self.assertIn("Maria Alegria da Silva assinou", corpo["msg"])

    def test_a_via_do_painel_e_a_do_cliente_abrem_para_salvar_em_pdf(self):
        self.client.force_login(self.vendedor)
        # Sem documento, a via volta para o cartão.
        resposta = self.client.get(f"/orcamentos/{self.orcamento.pk}/documento/via/", **INTERNO)
        self.assertRedirects(resposta, f"/orcamentos/{self.orcamento.pk}/documento/", fetch_redirect_response=False)

        documento = self.gerar()
        previa = self.client.get(f"/orcamentos/{self.orcamento.pk}/documento/via/", **INTERNO)
        self.assertEqual(previa.status_code, 200)
        self.assertContains(previa, "Prévia do documento")
        self.assertContains(previa, "Salvar em PDF")
        self.assertContains(previa, CPF_DO_CLIENTE)  # no painel, o CPF inteiro

        self.assinar(self.link(documento), client=Client())
        via = self.client.get(f"/orcamentos/{self.orcamento.pk}/documento/via/?imprimir=1", **INTERNO)
        self.assertEqual(via.status_code, 200)
        self.assertContains(via, 'data-imprimir-ao-abrir="1"')
        self.assertContains(via, "Registro da assinatura eletrônica")
        documento.refresh_from_db()
        self.assertContains(via, documento.hash_conteudo)
        self.assertContains(via, "200.150.10.20")
        self.assertContains(via, "iPhone")
        self.assertContains(via, "data:image/png;base64,")
        self.assertContains(via, f"nº {self.orcamento.numero_documento}")

        # A cópia do cliente: só existe assinada, e com o CPF mascarado.
        copia = Client().get(f"/assinado/{documento.codigo_publico}/")
        self.assertEqual(copia.status_code, 200)
        self.assertNotContains(copia, CPF_DO_CLIENTE)
        outro = self.gerar(self.criar_orcamento())
        self.assertEqual(Client().get(f"/assinado/{outro.codigo_publico}/").status_code, 404)

    def test_o_cartao_assinado_mostra_quem_quando_e_o_pdf(self):
        documento = self.gerar()
        self.assinar(self.link(documento))
        self.client.force_login(self.vendedor)
        resposta = self.client.get(f"/orcamentos/{self.orcamento.pk}/documento/", **INTERNO)
        self.assertContains(resposta, "Assinado por Maria Alegria da Silva em")
        self.assertContains(resposta, "Baixar PDF")
        self.assertContains(resposta, f"/orcamentos/{self.orcamento.pk}/documento/via/?imprimir=1")
