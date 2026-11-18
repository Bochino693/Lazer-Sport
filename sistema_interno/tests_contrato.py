"""O CONTRATO de compra e venda que o cliente assina no celular (LEIA-ME-V10, 107).

O dono: "no contrato final de assinatura, devem ter essas cláusulas, fotos
do item também e melhor aproveitamento das folhas (...) ponha um contrato
de assinatura bom e visível, como o de orçamento."

O que estes testes protegem (TUDO com dados inventados):

  * números, dinheiro e datas por extenso, em português;
  * o prazo da Cláusula 3ª vem de UM lugar só
    (`contrato.prazo_de_entrega_do_orcamento`), com 45 dias úteis só como
    último recurso;
  * o contrato não sai sem os dados do vendedor (o representante, que não
    mora no código) nem sem a forma de pagamento -- no serviço, no POST do
    painel e no cartão, que diz o que falta;
  * a tela "Dados do contrato": só a Gestão, salva, confere o CNPJ, avisa
    o que falta; sem <select>, sem cor escrita à mão no CSS;
  * o retrato: título, quadro, preâmbulo com VENDEDOR e COMPRADOR, as onze
    cláusulas com o texto da empresa, a foto de cada item (a do adesivo
    escolhido), o valor por extenso, a condição de pagamento, o prazo, o
    fecho com cidade e data -- e tudo congelado no hash;
  * a página do cliente e a via impressa (o "Salvar em PDF"): o contrato
    inteiro, as fotos sem imagem quebrada, o "Li e concordo" depois dele,
    as assinaturas (vendedor, comprador e duas testemunhas), a trilha da
    assinatura e o rodapé "Página X de Y" com o código do contrato;
  * os termos de antes do contrato continuam com a folha deles.
"""

import json
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from core.models import Brinquedos, ImagemBrinquedo, VarianteAdesivo

from . import contrato
from . import documento_assinatura as svc
from .models import DadosContrato, DocumentoAssinatura, EnderecoCliente, ItemOrcamento, Orcamento
from .permissoes import atribuir_funcoes
from .templatetags.contrato_extras import destaque_contrato, texto_de_rodape
from .tests_documento_assinatura import (
    AJAX,
    CPF_DO_CLIENTE,
    INTERNO,
    JSON,
    REPRESENTANTE_FICTICIO,
    BaseDocumento,
    conteudo_do_termo_antigo,
    png_de_assinatura,
)
from .utils import ErroDeFormulario

ROTULO = re.compile(r"Cláusula (\d+)ª\.")
INTERNO_DIR = Path(__file__).resolve().parent


def brinquedo(nome, imagem="", **campos):
    return Brinquedos.objects.create(
        nome_brinquedo=nome, imagem_brinquedo=imagem, descricao=f"{nome} de teste",
        valor_brinquedo=Decimal("100.00"), avaliacao=Decimal("5.00"), voltz="110", **campos,
    )


# ======================================================================
# POR EXTENSO
# ======================================================================
class ExtensoTests(SimpleTestCase):

    def test_numeros(self):
        casos = {
            0: "zero", 1: "um", 2: "dois", 10: "dez", 14: "catorze", 16: "dezesseis",
            21: "vinte e um", 45: "quarenta e cinco", 100: "cem", 101: "cento e um",
            110: "cento e dez", 999: "novecentos e noventa e nove", 1000: "mil",
            1001: "mil e um", 1100: "mil e cem", 1500: "mil e quinhentos",
            1520: "mil quinhentos e vinte", 2000: "dois mil", 38000: "trinta e oito mil",
            70500: "setenta mil e quinhentos", 100000: "cem mil",
            1_000_000: "um milhão", 1_000_001: "um milhão e um",
            1_500_000: "um milhão e quinhentos mil", 2_000_000: "dois milhões",
            1_234_567: "um milhão duzentos e trinta e quatro mil quinhentos e sessenta e sete",
        }
        for numero, texto in casos.items():
            with self.subTest(numero=numero):
                self.assertEqual(contrato.numero_por_extenso(numero), texto)

    def test_reais(self):
        casos = {
            "38000": "trinta e oito mil reais",
            "1": "um real",
            "0.50": "cinquenta centavos",
            "1.01": "um real e um centavo",
            "70500.50": "setenta mil e quinhentos reais e cinquenta centavos",
            "1000000": "um milhão de reais",
            "2500000": "dois milhões e quinhentos mil reais",
            "1000000.10": "um milhão de reais e dez centavos",
            "0": "zero real",
        }
        for valor, texto in casos.items():
            with self.subTest(valor=valor):
                self.assertEqual(contrato.reais_por_extenso(Decimal(valor)), texto)

    def test_datas(self):
        self.assertEqual(contrato.data_por_extenso(date(2026, 11, 18)), "18 de novembro de 2026")
        self.assertEqual(contrato.data_por_extenso(date(2026, 12, 1)), "1º de dezembro de 2026")
        self.assertEqual(contrato.data_por_extenso(date(2027, 3, 9)), "9 de março de 2027")


class FiltrosDaFolhaTests(SimpleTestCase):

    def test_o_destaque_escapa_antes_de_pintar(self):
        self.assertEqual(
            destaque_contrato("<b>o VENDEDOR & o COMPRADOR</b>"),
            "&lt;b&gt;o <strong>VENDEDOR</strong> &amp; o <strong>COMPRADOR</strong>&lt;/b&gt;",
        )

    def test_o_rodape_da_impressao_so_leva_texto_seguro(self):
        self.assertEqual(
            texto_de_rodape('Contrato nº 0012/2026 · LS-7K3QX9"}body{x:url(a)}\\'),
            "Contrato nº 0012/2026 · LS-7K3QX9bodyx:urla",
        )


# ======================================================================
# O PRAZO (Cláusula 3ª): UM LUGAR SÓ
# ======================================================================
class PrazoDeEntregaTests(SimpleTestCase):

    def test_o_prazo_do_orcamento_e_45_so_como_ultimo_recurso(self):
        self.assertEqual(contrato.prazo_de_entrega_do_orcamento(Orcamento(prazo_producao_dias=30)), 30)
        self.assertEqual(contrato.prazo_de_entrega_do_orcamento(Orcamento(prazo_producao_dias=None)), 45)
        self.assertEqual(contrato.prazo_de_entrega_do_orcamento(Orcamento(prazo_producao_dias=0)), 0)

    def test_a_clausula_le_o_prazo_da_funcao(self):
        def terceira(dias):
            prazo = contrato._prazo(Orcamento(prazo_producao_dias=dias))
            secoes = contrato.secoes(valor_total="1,00", valor_extenso="um real", condicao="Pix", prazo=prazo)
            return secoes[1]["clausulas"][0]["texto"]

        self.assertIn("no prazo de 45 (quarenta e cinco) dias úteis após a confirmação do pagamento.", terceira(None))
        self.assertIn("no prazo de 30 (trinta) dias úteis após", terceira(30))
        self.assertIn("no prazo de 01 (um) dia útil após", terceira(1))


# ======================================================================
# OS DADOS DO VENDEDOR: SEM ELES, NÃO SAI
# ======================================================================
class DadosDoContratoVaziosTests(TestCase):
    """O banco recém-migrado: a empresa preenchida, o representante vazio."""

    def test_a_migracao_cria_a_linha_so_com_os_dados_da_empresa(self):
        self.assertEqual(DadosContrato.objects.count(), 1)
        dados = DadosContrato.atual()
        self.assertEqual(dados.nome_fantasia, "Brinquedos Lazer & Sport")
        self.assertEqual(dados.razao_social, "Fábrica de Brinquedos Lazer & Sport Oficial – LTDA")
        self.assertEqual(dados.cnpj, "54.486.908/0001-86")
        self.assertIn("Rua São Roque de Minas, n. 104", dados.endereco_sede)
        self.assertEqual(dados.cidade, "São Paulo")
        # Os PESSOAIS não moram no código nem na migração.
        self.assertEqual((dados.representante_nome, dados.representante_rg, dados.representante_endereco), ("", "", ""))
        self.assertEqual(
            dados.faltando,
            ["nome do representante", "RG do representante", "endereço do representante"],
        )
        for arquivo in ("0070_dados_do_contrato.py", "0071_dados_do_contrato_iniciais.py"):
            texto = (INTERNO_DIR / "migrations" / arquivo).read_text(encoding="utf-8")
            self.assertNotIn("representante_nome=", texto)
            self.assertNotIn("representante_rg=", texto)


class BloqueioTests(BaseDocumento):

    def setUp(self):
        super().setUp()
        dados = DadosContrato.atual()
        dados.representante_nome = dados.representante_rg = dados.representante_endereco = ""
        dados.save()
        self.gestor = self.usuario("gestora", "gestao")

    def test_sem_o_representante_o_contrato_nao_sai(self):
        with self.assertRaises(ErroDeFormulario) as recusa:
            svc.gerar(self.orcamento, self.vendedor)
        self.assertIn("nome do representante, RG do representante, endereço do representante", str(recusa.exception))
        self.assertIn("Dados do contrato", str(recusa.exception))

        self.client.force_login(self.vendedor)
        resposta = self.client.post(f"/orcamentos/{self.orcamento.pk}/documento/", {"action": "gerar"}, **AJAX)
        self.assertEqual(resposta.status_code, 409)
        self.assertIn("O contrato ainda não pode ser enviado para assinatura", resposta.json()["msg"])
        self.assertFalse(DocumentoAssinatura.objects.exists())

    def test_o_cartao_avisa_e_trava_o_gerar(self):
        self.client.force_login(self.vendedor)
        pagina = self.client.get(f"/orcamentos/{self.orcamento.pk}/documento/", **INTERNO).content.decode()
        self.assertIn('data-pendencia="dados"', pagina)
        self.assertIn("Faltam os dados do vendedor no contrato", pagina)
        self.assertIn("Peça à Gestão para preencher.", pagina)
        self.assertNotIn('data-doc-acao="gerar"', pagina)
        self.assertIn('aria-disabled="true"', pagina)

        # A Gestão ganha o caminho para preencher.
        self.client.force_login(self.gestor)
        pagina = self.client.get(f"/orcamentos/{self.orcamento.pk}/documento/", **INTERNO).content.decode()
        self.assertIn('href="/orcamentos/dados-do-contrato/"', pagina)
        self.assertIn("Preencher os dados do contrato", pagina)

    def test_sem_forma_de_pagamento_tambem_nao_sai(self):
        from .tests_documento_assinatura import preencher_dados_do_contrato

        preencher_dados_do_contrato()
        sem_forma = self.criar_orcamento(forma_pagamento="")
        with self.assertRaises(ErroDeFormulario) as recusa:
            svc.gerar(sem_forma, self.vendedor)
        self.assertIn("Cláusula 2ª", str(recusa.exception))
        self.client.force_login(self.vendedor)
        pagina = self.client.get(f"/orcamentos/{sem_forma.pk}/documento/", **INTERNO).content.decode()
        self.assertIn('data-pendencia="forma"', pagina)
        self.assertNotIn('data-pendencia="dados"', pagina)
        # Preenchido o que faltava, o botão volta.
        pagina = self.client.get(f"/orcamentos/{self.orcamento.pk}/documento/", **INTERNO).content.decode()
        self.assertIn('data-doc-acao="gerar"', pagina)
        self.assertNotIn("data-pendencia", pagina)

    def test_o_documento_ja_gerado_nao_depende_dos_dados_de_hoje(self):
        """Gerado com os dados, o contrato é o retrato: esvaziar depois não o trava."""
        from .tests_documento_assinatura import preencher_dados_do_contrato

        preencher_dados_do_contrato()
        documento = svc.gerar(self.orcamento, self.vendedor)
        dados = DadosContrato.atual()
        dados.representante_nome = ""
        dados.save()
        self.assertEqual(self.assinar(self.link(documento)).status_code, 200)


class TelaDosDadosTests(TestCase):
    URL = "/orcamentos/dados-do-contrato/"

    def setUp(self):
        self.gestor = User.objects.create_user("gestora-dados", password="x")
        atribuir_funcoes(self.gestor, ["gestao"])
        self.vendas = User.objects.create_user("vendas-dados", password="x")
        atribuir_funcoes(self.vendas, ["vendas"])

    def salvar(self, **troca):
        dados = {
            "action": "salvar",
            "nome_fantasia": "Brinquedos Lazer & Sport",
            "razao_social": "Fábrica de Brinquedos Lazer & Sport Oficial – LTDA",
            "cnpj": "54486908000186",
            "endereco_sede": "Rua São Roque de Minas, n. 104, Jardim Peri, São Paulo, Capital",
            "cidade": "São Paulo",
            **REPRESENTANTE_FICTICIO,
        }
        dados.update(troca)
        return self.client.post(self.URL, dados, **AJAX)

    def test_so_a_gestao_abre_e_salva(self):
        self.client.force_login(self.vendas)
        self.assertEqual(self.client.get(self.URL, **INTERNO).status_code, 302)
        resposta = self.salvar()
        self.assertNotEqual(resposta.status_code, 200)
        self.assertEqual(DadosContrato.atual().representante_nome, "")

        self.client.force_login(self.gestor)
        pagina = self.client.get(self.URL, **INTERNO)
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, "O contrato ainda não sai para assinatura.")
        self.assertContains(pagina, "Falta preencher: nome do representante, RG do representante, endereço do representante.")
        # O menu leva à tela; o preâmbulo aparece como sai no contrato.
        self.assertContains(pagina, 'href="/orcamentos/dados-do-contrato/"')
        self.assertContains(pagina, 'data-dc-previa="representante_nome"')
        self.assertContains(pagina, "neste ato representada por")

    def test_salvar_confere_o_cnpj_e_diz_o_que_falta(self):
        self.client.force_login(self.gestor)
        resposta = self.salvar()
        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertEqual(resposta.json()["faltando"], [])
        dados = DadosContrato.atual()
        self.assertEqual(dados.cnpj, "54.486.908/0001-86")
        self.assertEqual(dados.representante_nome, REPRESENTANTE_FICTICIO["representante_nome"])
        self.assertEqual(dados.atualizado_por, self.gestor)
        self.assertContains(self.client.get(self.URL, **INTERNO), "Tudo pronto.")

        resposta = self.salvar(cnpj="11.111.111/1111-11")
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("CNPJ inválido", resposta.json()["msg"])
        resposta = self.salvar(nome_fantasia="  ")
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(DadosContrato.atual().nome_fantasia, "Brinquedos Lazer & Sport")

        resposta = self.salvar(representante_rg="")
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("Ainda falta: RG do representante", resposta.json()["msg"])

    def test_as_regras_do_painel(self):
        html = (INTERNO_DIR / "templates" / "dados_contrato_inner.html").read_text(encoding="utf-8")
        self.assertNotIn("<select", html)
        for linha in html.splitlines():
            if "{#" in linha:
                self.assertIn("#}", linha, "{# #} é de uma linha só")
        css = (INTERNO_DIR / "static" / "interno" / "dados-contrato.css").read_text(encoding="utf-8")
        self.assertFalse(re.findall(r"#[0-9a-fA-F]{3,8}\b", css), "CSS do painel só com as variáveis do tema")
        self.assertNotRegex(css, r"background:\s*(white|#fff|gr[ae]y)")
        js = (INTERNO_DIR / "static" / "interno" / "dados-contrato.js").read_text(encoding="utf-8")
        self.assertNotIn("alert(", js)
        self.assertNotIn("confirm(", js)


# ======================================================================
# O CONTRATO
# ======================================================================
class ContratoTests(BaseDocumento):

    def setUp(self):
        super().setUp()
        EnderecoCliente.objects.create(
            cliente=self.cliente_cadastro, endereco="Rua das Palmeiras Fictícias", numero="123",
            complemento="Galpão 2", bairro="Jardim Exemplo", cidade="Campinas", estado="SP", cep="13000-000",
        )
        self.cliente_cadastro.email = "contato@exemplo.com.br"
        self.cliente_cadastro.save()

    def com_itens(self, *itens, **campos):
        orcamento = Orcamento.objects.create(
            cliente=self.cliente_cadastro, nome_cliente="Buffet Alegria",
            whatsapp_cliente="(11) 97777-6655", status=Orcamento.Status.APROVADO,
            forma_pagamento=campos.pop("forma_pagamento", "50% de entrada via Pix e 50% na entrega"),
            responsavel=self.vendedor, **campos,
        )
        for item in itens:
            ItemOrcamento.objects.create(orcamento=orcamento, **item)
        return orcamento

    def secoes(self, conteudo):
        return [c for secao in conteudo["secoes"] for c in secao["clausulas"]]

    # --------------------------------------------------------- o retrato
    def test_um_item_com_foto(self):
        cama = brinquedo("Cama elástica", "imagens_brinquedos/cama-elastica.jpg")
        orcamento = self.com_itens({"brinquedo": cama, "descricao": "Cama elástica 3 m", "quantidade": 1, "valor_unitario": Decimal("3000.00")})
        conteudo = svc.gerar(orcamento, self.vendedor).conteudo

        self.assertEqual(conteudo["titulo"], contrato.TITULO)
        [item] = conteudo["itens"]
        self.assertIn("cama-elastica", item["foto"])
        self.assertIn("w_900", item["foto"])
        self.assertEqual(item["adesivo"], "")
        clausulas = self.secoes(conteudo)
        self.assertEqual([c["numero"] for c in clausulas], list(range(1, 12)))
        self.assertTrue(clausulas[0]["fotos"])

        documento = DocumentoAssinatura.objects.get(orcamento=orcamento)
        pagina = self.client.get(f"/assinar/{self.link(documento)}/").content.decode()
        self.assertIn('data-quantidade="1"', pagina)
        self.assertIn(f'src="{item["foto"]}"', pagina)
        self.assertIn("data-ct-foto", pagina)
        self.assertIn("Quantidade: 1", pagina)

    def test_varios_itens_com_e_sem_foto_nunca_imagem_quebrada(self):
        cama = brinquedo("Cama elástica", "imagens_brinquedos/cama-elastica.jpg")
        sem_capa = brinquedo("Pula-pula sem foto")
        orcamento = self.com_itens(
            {"brinquedo": cama, "descricao": "Cama elástica 3 m", "quantidade": 2, "valor_unitario": Decimal("3000.00")},
            {"brinquedo": sem_capa, "descricao": "Pula-pula sem foto", "quantidade": 1, "valor_unitario": Decimal("1500.00")},
            {"descricao": "Painel de LED com a marca", "quantidade": 1, "valor_unitario": Decimal("2450.00")},
        )
        conteudo = svc.gerar(orcamento, self.vendedor).conteudo
        fotos = [item["foto"] for item in conteudo["itens"]]
        self.assertTrue(fotos[0])
        self.assertEqual(fotos[1:], ["", ""])

        documento = DocumentoAssinatura.objects.get(orcamento=orcamento)
        pagina = self.client.get(f"/assinar/{self.link(documento)}/").content.decode()
        self.assertIn('data-quantidade="3"', pagina)
        self.assertEqual(pagina.count("data-ct-foto"), 1)
        self.assertNotIn('src=""', pagina)
        self.assertEqual(pagina.count('ct-foto-quadro sem-foto'), 2)
        # O quadro discreto diz o nome; o quadro do contrato tem as três linhas.
        self.assertIn("Painel de LED com a marca", pagina)
        self.assertEqual(pagina.count('class="ct-qtd"'), 3)
        # A foto que não abrir vira o quadro com o nome (assinatura.js).
        js = (Path(__file__).resolve().parents[1] / "core" / "static" / "site" / "paginas" / "assinatura.js").read_text(encoding="utf-8")
        self.assertIn("img[data-ct-foto]", js)

    def test_o_adesivo_escolhido_traz_a_foto_dele(self):
        kids = brinquedo("Air Game Kids", "imagens_brinquedos/air-game-kids-capa.jpg")
        VarianteAdesivo.objects.filter(pk=kids.adesivo_padrao_id).update(nome="Astronautas", slug="astronautas")
        alien = VarianteAdesivo.objects.create(brinquedo=kids, nome="Alienígenas", slug="alienigenas", ordem=2)
        ImagemBrinquedo.objects.create(
            brinquedo=kids, variante=alien, tipo="tres_quartos", ordem=1,
            imagem="imagens_brinquedos/galeria/air-game-kids-alienigenas-frente.jpg",
        )
        orcamento = self.com_itens(
            {"brinquedo": kids, "descricao": "Air Game Kids Alienígenas", "quantidade": 1, "valor_unitario": Decimal("18500.00")},
            {"brinquedo": kids, "descricao": "Air Game Kids", "quantidade": 2, "valor_unitario": Decimal("18500.00")},
        )
        alienigenas, padrao = svc.gerar(orcamento, self.vendedor).conteudo["itens"]
        self.assertEqual(alienigenas["adesivo"], "Alienígenas")
        self.assertIn("alienigenas-frente", alienigenas["foto"])
        self.assertTrue(alienigenas["adesivo_no_nome"])
        self.assertEqual(padrao["adesivo"], "Astronautas")
        self.assertIn("air-game-kids-capa", padrao["foto"])
        self.assertFalse(padrao["adesivo_no_nome"])

        pagina = self.client.get(f"/assinar/{self.link(DocumentoAssinatura.objects.get(orcamento=orcamento))}/").content.decode()
        self.assertIn("Adesivo: Alienígenas", pagina)
        self.assertIn("Adesivo: Astronautas", pagina)
        # O quadro repete o adesivo só quando o nome não o diz.
        self.assertIn("<small>· adesivo Astronautas</small>", pagina)
        self.assertNotIn("<small>· adesivo Alienígenas</small>", pagina)

    def test_preambulo_com_vendedor_e_comprador(self):
        conteudo = self.gerar().conteudo
        abertura = conteudo["preambulo"]["abertura"]
        for pedaco in (
            "Pelo presente INSTRUMENTO PARTICULAR DE COMPRA E VENDA, e na forma da Lei",
            "VENDEDOR: Brinquedos Lazer & Sport, razão social Fábrica de Brinquedos Lazer & Sport Oficial – LTDA",
            "inscrita no CNPJ sob o n. 54.486.908/0001-86",
            "com sede na Rua São Roque de Minas, n. 104, Jardim Peri, São Paulo, Capital",
            f"neste ato representada por {REPRESENTANTE_FICTICIO['representante_nome']}",
            f"RG {REPRESENTANTE_FICTICIO['representante_rg']}",
            f"residente e domiciliado na {REPRESENTANTE_FICTICIO['representante_endereco']};",
            "doravante denominado simplesmente COMPRADOR:",
        ):
            self.assertIn(pedaco, abertura)
        self.assertTrue(conteudo["preambulo"]["fechamento"].startswith("As partes acima identificadas têm, entre si"))
        cliente = conteudo["cliente"]
        self.assertEqual(cliente["documento"], CPF_DO_CLIENTE)
        self.assertEqual(cliente["endereco"], "Rua das Palmeiras Fictícias, 123, Galpão 2 – Jardim Exemplo – Campinas/SP – CEP 13000-000")
        self.assertEqual(cliente["email"], "contato@exemplo.com.br")
        self.assertEqual(cliente["telefone"], "(11) 97777-6655")

        documento = DocumentoAssinatura.objects.get(orcamento=self.orcamento)
        pagina = self.client.get(f"/assinar/{self.link(documento)}/").content.decode()
        for rotulo in ("CPF ou CNPJ", "Endereço completo", "E-mail", "Telefone", "Representante"):
            self.assertIn(f"<dt>{rotulo}</dt>", pagina)
        self.assertIn("<strong>VENDEDOR</strong>", pagina)
        self.assertIn("529.***.***-25", pagina)
        self.assertNotIn(CPF_DO_CLIENTE, pagina)

    def test_as_onze_clausulas_sao_as_do_contrato_da_empresa(self):
        conteudo = self.gerar().conteudo
        self.assertEqual(
            [secao["titulo"] for secao in conteudo["secoes"]],
            ["DO OBJETO DO CONTRATO", "DAS OBRIGAÇÕES E GARANTIAS", "DA MULTA", "DA INADIMPLÊNCIA", "DO FORO"],
        )
        clausulas = {c["numero"]: c for c in self.secoes(conteudo)}
        self.assertEqual(sorted(clausulas), list(range(1, 12)))
        self.assertEqual(len(clausulas[4]["paragrafos"]), 3)
        self.assertEqual(len(clausulas[6]["paragrafos"]), 1)
        texto = json.dumps(conteudo["secoes"], ensure_ascii=False)
        for pedaco in (
            "conforme características da imagem abaixo, sendo o VENDEDOR o único proprietário do referido equipamento, vejamos:",
            "prazo de garantia de 06 (seis) meses",
            "haverá a perda imediata da garantia.",
            "As despesas com frete do equipamento são por conta do COMPRADOR.",
            "multa contratual no importe de 10% (dez por cento) do valor do contrato atualizado",
            "Resguardado o direito de desistência insculpido no artigo 49 do CDC.",
            "honorários sucumbenciais, fixados em 20% (vinte por cento).",
            "multa de 2% sobre o saldo devedor remanescente e juros de 1% ao mês",
            "sem que isso configure novação, mantendo o parcelamento outrora firmado.",
            "ou no máximo até o limite do valor total do contrato.",
            "ainda que fora deste instrumento.",
            "as partes elegem o foro da Comarca de São Paulo, por mais privilegiado que outro seja.",
        ):
            self.assertIn(pedaco, texto)
        self.assertEqual(
            conteudo["fecho"],
            "Por estarem assim justos e contratados, firmam o presente instrumento em duas vias de igual teor na presença de duas testemunhas.",
        )

    def test_clausula_segunda_valor_por_extenso_e_condicao_de_pagamento(self):
        orcamento = self.com_itens(
            {"descricao": "Boliche", "quantidade": 1, "valor_unitario": Decimal("70500.50")},
            forma_pagamento="Entrada de R$ 20.000,00 via Pix e o restante em 6 boletos",
        )
        segunda = self.secoes(svc.gerar(orcamento, self.vendedor).conteudo)[1]
        self.assertIn(
            "no valor total de R$ 70.500,50 (setenta mil e quinhentos reais e cinquenta centavos), que deverá ser pago da seguinte forma:",
            segunda["texto"],
        )
        self.assertEqual(
            segunda["complemento"],
            "Condição de pagamento: Conforme negociação entre as partes, o pagamento será realizado "
            "da seguinte forma: Entrada de R$ 20.000,00 via Pix e o restante em 6 boletos.",
        )

    def test_o_valor_final_combinado_e_o_valor_do_contrato(self):
        orcamento = self.com_itens(
            {"descricao": "Air Game Kids", "quantidade": 2, "valor_unitario": Decimal("20000.00")},
            valor_final=Decimal("38000.00"),
        )
        conteudo = svc.gerar(orcamento, self.vendedor).conteudo
        self.assertEqual(conteudo["valor_total_texto"], "38.000,00")
        self.assertIn("R$ 38.000,00 (trinta e oito mil reais)", self.secoes(conteudo)[1]["texto"])

    def test_clausula_terceira_le_o_prazo_do_orcamento(self):
        com_prazo = self.com_itens({"descricao": "Brinquedão", "quantidade": 1, "valor_unitario": Decimal("90000")}, prazo_producao_dias=30)
        terceira = self.secoes(svc.gerar(com_prazo, self.vendedor).conteudo)[2]
        self.assertIn("no prazo de 30 (trinta) dias úteis após a confirmação do pagamento.", terceira["texto"])
        # sem prazo digitado: o da lista de montagem (montagem + fila, LEIA-ME 112), o maior da faixa
        from . import montagem

        dias = montagem.prazo_de_entrega(self.orcamento).dias_max
        sem_prazo = self.secoes(self.gerar().conteudo)[2]
        self.assertIn(f"no prazo de {dias:02d} (", sem_prazo["texto"])

    def test_fecho_com_a_cidade_e_a_data_por_extenso(self):
        from .tests_documento_assinatura import preencher_dados_do_contrato

        preencher_dados_do_contrato(cidade="Campinas")
        conteudo = self.gerar().conteudo
        self.assertEqual(conteudo["local_data"], f"Campinas, {contrato.data_por_extenso(timezone.localdate())}")

    # ------------------------------------------------------- as telas
    def test_a_pagina_do_cliente_mostra_o_contrato_inteiro_e_assina_no_fim(self):
        documento = self.gerar()
        pagina = self.client.get(f"/assinar/{self.link(documento)}/").content.decode()
        self.assertEqual(sorted({int(n) for n in ROTULO.findall(pagina)}), list(range(1, 12)))
        self.assertIn("Ir direto para a assinatura", pagina)
        self.assertLess(pagina.index('class="ct-final'), pagina.index('id="formAssinatura"'))
        self.assertLess(pagina.index('id="formAssinatura"'), pagina.index("Li e concordo com todas as cláusulas"))
        for parte in ("VENDEDOR <small>(Proprietário)</small>", "<strong>COMPRADOR</strong>", "TESTEMUNHA 1", "TESTEMUNHA 2"):
            self.assertIn(parte, pagina)
        self.assertIn(contrato.data_por_extenso(timezone.localdate()), pagina)
        self.assertNotIn("alert(", pagina)
        self.assertNotIn("confirm(", pagina)
        # Os ícones da página pública: nenhum Font Awesome fora do recorte.
        self.assertNotRegex(pagina, r"\bfa-[a-z]")

    def test_a_via_impressa_o_pdf_tem_as_11_clausulas_as_fotos_e_as_paginas(self):
        cama = brinquedo("Cama elástica", "imagens_brinquedos/cama-elastica.jpg")
        kids = brinquedo("Air Game Kids", "imagens_brinquedos/air-game-kids-capa.jpg")
        orcamento = self.com_itens(
            {"brinquedo": cama, "descricao": "Cama elástica 3 m", "quantidade": 2, "valor_unitario": Decimal("3000.00")},
            {"brinquedo": kids, "descricao": "Air Game Kids", "quantidade": 1, "valor_unitario": Decimal("18500.00")},
        )
        documento = svc.gerar(orcamento, self.vendedor)
        self.assertEqual(self.assinar(self.link(documento), documento=CPF_DO_CLIENTE).status_code, 200)
        documento.refresh_from_db()

        self.client.force_login(self.vendedor)
        via = self.client.get(f"/orcamentos/{orcamento.pk}/documento/via/?imprimir=1", **INTERNO).content.decode()
        self.assertEqual(len(ROTULO.findall(via)), 11)
        for item in documento.conteudo["itens"]:
            self.assertIn(f'src="{item["foto"]}"', via)
        self.assertEqual(via.count("data-ct-foto"), 2)
        # O rodapé de cada folha: o código do contrato e "Página X de Y".
        self.assertIn('counter(page) " de " counter(pages)', via)
        codigo = f"Contrato nº {orcamento.numero_documento} · {orcamento.codigo} · integridade {documento.hash_conteudo[:10]}"
        self.assertIn(f'@bottom-left{{content:"{codigo}"', via)
        # As assinaturas: a do celular entra no lugar do COMPRADOR.
        bloco = via[via.index('class="ct-final'):via.index('class="ct-auditoria"')]
        self.assertIn("data:image/png;base64,", bloco[bloco.index("ct-assina-comprador"):])
        self.assertIn("Assinado eletronicamente em", bloco)
        self.assertEqual(bloco.count("ct-assina-linha"), 4)
        # A trilha da auditoria, discreta, depois das assinaturas.
        self.assertIn("Registro da assinatura eletrônica", via)
        self.assertIn(documento.hash_conteudo, via)
        self.assertIn("200.150.10.20", via)
        self.assertIn(CPF_DO_CLIENTE, via)  # no painel, inteiro

        # A cópia do cliente: a mesma folha, com o CPF mascarado.
        copia = self.client.get(f"/assinado/{documento.codigo_publico}/").content.decode()
        self.assertEqual(len(ROTULO.findall(copia)), 11)
        self.assertIn("counter(pages)", copia)
        self.assertNotIn(CPF_DO_CLIENTE, copia)

    def test_a_impressao_da_folha_a4(self):
        css = (Path(__file__).resolve().parents[1] / "core" / "static" / "site" / "paginas" / "assinatura.css").read_text(encoding="utf-8")
        self.assertIn("@page{size:A4;margin:16mm 17mm 18mm}", css)
        impressao = css[css.index("o contrato, em A4"):]
        for regra in (
            ".contrato{padding:0;font-size:10.2pt",
            "text-align:justify",
            ".ct-secao-titulo{margin:0 0 1.8mm;font-size:8.4pt;gap:2.2mm;break-after:avoid",
            ".ct-foto{border-radius:2mm;break-inside:avoid",
            ".ct-final{margin-top:4.5mm;padding-top:2.8mm;border-top-width:.6mm;break-inside:avoid",
            ".ct-partes{grid-template-columns:1fr 1fr",
        ):
            self.assertIn(regra, impressao)

    def test_whatsapp_e_historico_falam_em_contrato(self):
        documento = self.gerar()
        self.assertIn("Agora é só assinar o contrato de compra e venda", svc.mensagem_whatsapp(documento, "https://x/assinar/1/"))
        self.assertTrue(
            self.orcamento.atividades.filter(resumo__startswith="Contrato de compra e venda · integridade").exists()
        )

    def test_o_resumo_do_painel_diz_o_prazo_e_o_vendedor(self):
        self.client.force_login(self.vendedor)
        antes = self.client.get(f"/orcamentos/{self.orcamento.pk}/documento/", **INTERNO).content.decode()
        self.assertIn("Entrega (Cláusula 3ª)", antes)
        from . import montagem

        self.assertIn(f"{montagem.prazo_de_entrega(self.orcamento).dias_max} dias úteis", antes)
        self.gerar()
        depois = self.client.get(f"/orcamentos/{self.orcamento.pk}/documento/", **INTERNO).content.decode()
        self.assertIn(REPRESENTANTE_FICTICIO["representante_nome"], depois)

    # ------------------------------------------- os termos de antes
    def test_o_termo_de_compra_2026_11b_continua_com_a_folha_dele(self):
        documento = self.gerar()
        conteudo = conteudo_do_termo_antigo(documento, svc.MODELO_DO_TERMO)
        DocumentoAssinatura.objects.filter(pk=documento.pk).update(
            conteudo=conteudo, hash_conteudo=svc.hash_do_retrato(conteudo),
        )
        documento.refresh_from_db()
        self.assertFalse(svc.e_contrato(documento.conteudo))
        pagina = self.client.get(f"/assinar/{self.link(documento)}/").content.decode()
        self.assertIn("Termo de compra", pagina)
        self.assertIn("Declaração", pagina)
        self.assertIn("Li e concordo com o termo de compra acima.", pagina)
        self.assertNotIn("Cláusula 1ª", pagina)
        self.assertIn("Agora é só assinar o termo de compra", svc.mensagem_whatsapp(documento, "https://x/"))
        self.assertEqual(self.assinar(self.link(documento)).status_code, 200)
        documento.refresh_from_db()
        self.assertTrue(documento.assinado)
        self.assertTrue(self.orcamento.atividades.filter(resumo__startswith="Termo de compra assinado").exists())


class PrazoZeroTests(SimpleTestCase):
    """0 dia não vira "00 (zero) dias úteis": é pronta entrega."""

    def test_clausula_terceira_com_prazo_zero(self):
        prazo = contrato._prazo(Orcamento(prazo_producao_dias=0))
        secoes = contrato.secoes(valor_total="1,00", valor_extenso="um real", condicao="Pix", prazo=prazo)
        texto = " ".join(c["texto"] for s in secoes for c in s["clausulas"])
        self.assertIn("imediatamente após a confirmação do pagamento (pronta entrega)", texto)
        self.assertNotIn("(zero) dias", texto)
