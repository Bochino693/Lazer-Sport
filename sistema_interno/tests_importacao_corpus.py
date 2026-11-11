"""O corpus de orçamentos de verdade: cada informação no campo certo.

O PEDIDO: "quero tudo funcionando perfeitamente e bem, colocando tudo
corretamente nos campos". Os testes de tests_importacao_word.py provam
cada regra com XML mínimo; estes provam o resultado com documentos como a
equipe recebe -- salvos pelo Word (python-docx) e pelo LibreOffice (o
PDF), com cabeçalho, rodapé da empresa, tabela, texto corrido e ficha de
cadastro. Ver tests_importacao_corpus/gerar_corpus.py.

O valor esperado de cada campo está em tests_importacao_corpus/
esperado.json, escrito à mão. Tudo aqui roda SEM a chave da IA, como em
produção hoje: é a leitura por regra que tem de acertar.

Dois níveis:
  1. a leitura: o que a tela de conferência abre em cada campo;
  2. a gravação: o que fica no banco (Cliente, EnderecoCliente,
     Orcamento, ItemOrcamento) depois de "Criar", passando pela tela.
"""

from __future__ import annotations

import json
import os
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from core.models import Brinquedos

from .importacao_word import conferencia, formulario, leitor
from .models import Cliente, ItemOrcamento, Orcamento
from .permissoes import atribuir_funcoes

PASTA = Path(__file__).resolve().parent / "tests_importacao_corpus"
ESPERADO = json.loads((PASTA / "esperado.json").read_text(encoding="utf-8"))
DOCUMENTOS = sorted(nome for nome in ESPERADO if not nome.startswith("_"))
HOJE = date(2026, 11, 11)
HOST = {"HTTP_HOST": "interno.testserver"}

CATALOGO = (
    ("Cama elástica 3 m", "2800.00"),
    ("Cama elástica 4 m", "3500.00"),
    ("Pula-pula", "1234.00"),
    ("Air Game Kids", "18000.00"),
    ("Piscina de bolinhas", "450.00"),
    ("Brinquedão Modelo 3", "9000.00"),
    ("Brinquedão Modelo 5", "12000.00"),
)


def esperado_de(nome):
    dados = ESPERADO[nome]
    return ESPERADO[dados["igual_a"]] if "igual_a" in dados else dados


def linhas_do_arquivo(nome):
    conteudo = (PASTA / nome).read_bytes()
    if nome.endswith(".pdf"):
        return leitor.ler_pdf_local(conteudo, nome)
    return leitor.ler_docx(conteudo, nome)


def criar_base():
    produtos = {
        nome: Brinquedos.objects.create(
            nome_brinquedo=nome, descricao=nome, valor_brinquedo=Decimal(valor),
            avaliacao=Decimal("5.00"), voltz="220",
        )
        for nome, valor in CATALOGO
    }
    # O Buffet Alegria já é cliente (só o e-mail): o orçamento 01 tem de
    # LIGAR a ele e completar o cadastro, e não criar outro.
    Cliente.objects.create(nome_cliente="Buffet Alegria", email="contato@buffetalegria.com.br")
    return produtos


def campos_da_tela(proposta, envio):
    """O que a tela de conferência mostra, no formato do esperado.json."""
    nome_do_produto = {}
    for item in proposta["itens"]:
        opcao = item["produto"]["opcao"]
        nome_do_produto[item["uid"]] = opcao["rotulo"] if opcao else None
    valor_final = ""
    if envio["total_escolha"] == "valor_final":
        valor_final = proposta["valor_final"]["valor"]
    return {
        "modo": envio["modo"],
        "cliente_existente": envio["cliente_modo"] == "existente",
        "cliente": {
            "nome": envio["nome"], "estabelecimento": envio["estabelecimento"],
            "documento": envio["documento"], "telefone": envio["telefone"],
            "whatsapp": envio["whatsapp"], "email": envio["email"], "contato": envio["contato"],
        },
        "endereco": {
            "cep": envio["cep"], "rua": envio["endereco"], "numero": envio["numero"],
            "complemento": envio["complemento"], "bairro": envio["bairro"],
            "cidade": envio["cidade"], "uf": envio["estado"],
        },
        "itens": [
            {
                "descricao": item["descricao"],
                "original": next(i["original"] for i in proposta["itens"] if i["uid"] == item["uid"]),
                "produto": nome_do_produto[item["uid"]],
                "quantidade": item["quantidade"],
                "valor_unitario": item["valor_unitario"],
            }
            for item in envio["itens"]
        ],
        "frete": envio["frete"], "desconto": envio["desconto"], "valor_final": valor_final,
        "validade": envio["validade"],
        "forma_pagamento": envio["forma_pagamento"], "forma_envio": envio["forma_envio"],
        "prazo": envio["prazo"], "observacoes": envio["observacoes"],
    }


class _SemChave(TestCase):

    def setUp(self):
        ambiente = mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""})
        ambiente.start()
        self.addCleanup(ambiente.stop)
        hoje = mock.patch("django.utils.timezone.localdate", return_value=HOJE)
        hoje.start()
        self.addCleanup(hoje.stop)


class LeituraDoCorpusTests(_SemChave):
    """Cada campo, de cada documento, como a tela de conferência abre."""

    @classmethod
    def setUpTestData(cls):
        cls.produtos = criar_base()

    def test_cada_documento_cai_nos_campos_certos(self):
        for nome in DOCUMENTOS:
            esperado = esperado_de(nome)
            with self.subTest(documento=nome):
                leitura = {"arquivo": nome, "formato": "pdf" if nome.endswith(".pdf") else "docx",
                           "linhas": linhas_do_arquivo(nome), "ia": {"usada": False}, "escolhas": {}}
                proposta = conferencia.montar_proposta(leitura, hoje=HOJE)
                tela = campos_da_tela(proposta, formulario.envio_inicial(proposta))
                for chave in ("modo", "cliente_existente"):
                    self.assertEqual(tela[chave], esperado[chave], f"{nome}: {chave}")
                for grupo in ("cliente", "endereco"):
                    for campo, valor in esperado[grupo].items():
                        self.assertEqual(tela[grupo][campo], valor, f"{nome}: {grupo}.{campo}")
                self.assertEqual(len(tela["itens"]), len(esperado["itens"]), f"{nome}: quantos itens")
                for posicao, (lido, certo) in enumerate(zip(tela["itens"], esperado["itens"]), start=1):
                    for campo, valor in certo.items():
                        self.assertEqual(lido[campo], valor, f"{nome}: item {posicao}.{campo}")
                # Documento certo não acende vermelho: alerta vermelho é
                # conta que não bate ou valor em dúvida, e nenhum destes tem.
                vermelhos = [a["titulo"] for a in proposta["alertas"] if a["nivel"] == conferencia.NIVEL_VERMELHO]
                self.assertEqual(vermelhos, [], f"{nome}: alertas vermelhos")
                if esperado["modo"] == "orcamento":
                    for campo in ("frete", "desconto", "valor_final", "validade", "forma_pagamento",
                                  "forma_envio", "prazo", "observacoes"):
                        self.assertEqual(tela[campo], esperado[campo], f"{nome}: {campo}")

    def test_nada_da_lazer_e_sport_vai_para_o_cliente(self):
        da_empresa = ("54.486.908/0001-86", "54486908000186", "(11) 96056-3135", "contato@lazersport.com",
                      "Av. Industrial", "07220-000", "Cumbica", "Lazer & Sport")
        for nome in DOCUMENTOS:
            with self.subTest(documento=nome):
                leitura = {"arquivo": nome, "linhas": linhas_do_arquivo(nome), "ia": {"usada": False}}
                proposta = conferencia.montar_proposta(leitura, hoje=HOJE)
                envio = formulario.envio_inicial(proposta)
                cliente = " | ".join(str(envio[c]) for c in (
                    "nome", "estabelecimento", "documento", "telefone", "email", "contato", "cep",
                    "endereco", "numero", "complemento", "bairro", "cidade", "estado",
                ))
                for marca in da_empresa:
                    self.assertNotIn(marca, cliente, f"{nome}: “{marca}” entrou no cliente")

    def test_o_pdf_e_o_word_do_mesmo_orcamento_leem_igual(self):
        def tela(nome):
            leitura = {"arquivo": nome, "linhas": linhas_do_arquivo(nome), "ia": {"usada": False}}
            proposta = conferencia.montar_proposta(leitura, hoje=HOJE)
            return campos_da_tela(proposta, formulario.envio_inicial(proposta))

        self.assertEqual(tela("06-pdf-tabela-buffet-alegria.pdf"), tela("01-tabela-buffet-alegria.docx"))


class GravacaoDoCorpusTests(_SemChave):
    """Pela tela, do envio do arquivo ao que fica no banco."""

    def setUp(self):
        super().setUp()
        self.produtos = criar_base()
        self.vendedor = User.objects.create_user("vendedora", "v@exemplo.com", "senha")
        atribuir_funcoes(self.vendedor, ["vendas"])
        self.client.force_login(self.vendedor)

    def importar_e_criar(self, nome):
        """Sobe o arquivo e cria com o que a tela abriu, fazendo só o que
        a pessoa faria: conferir o produto sugerido e marcar como avulsa a
        linha sem produto do catálogo."""
        conteudo = (PASTA / nome).read_bytes()
        resposta = self.client.post("/orcamentos/importar/", {"arquivo": SimpleUploadedFile(nome, conteudo)}, **HOST)
        self.assertEqual(resposta.status_code, 302, resposta.content[:300])
        url = resposta["Location"]
        tela = self.client.get(url, **HOST)
        self.assertEqual(tela.status_code, 200)
        self.assertNotContains(tela, "ANTHROPIC")
        envio = tela.context["envio"]
        dados = {"action": "criar", "itens_ordem": ",".join(i["uid"] for i in envio["itens"])}
        for chave, valor in envio.items():
            if isinstance(valor, (str, int)) and chave not in ("itens", "justificativas"):
                dados[chave] = valor
        if envio["cliente_confirmado"]:
            dados["cliente_confirmado"] = "1"
        for item in envio["itens"]:
            prefixo = f"item-{item['uid']}-"
            dados[prefixo + "descricao"] = item["descricao"]
            dados[prefixo + "produto"] = item["produto"]
            dados[prefixo + "quantidade"] = item["quantidade"]
            dados[prefixo + "valor_unitario"] = item["valor_unitario"]
            dados[prefixo + "conferido"] = "1"
            if not item["produto"]:
                dados[prefixo + "avulsa"] = "1"
        resposta = self.client.post(url, dados, **HOST)
        if resposta.status_code != 302:
            self.fail(f"{nome}: não criou -- {resposta.context['validado']['pendencias']}")
        return resposta

    def conferir_cliente(self, nome, cliente):
        esperado = esperado_de(nome)
        dados = esperado["cliente"]
        self.assertEqual(cliente.nome_cliente, dados["nome"], f"{nome}: nome")
        self.assertEqual(cliente.nome_estabelecimento, dados["estabelecimento"], f"{nome}: estabelecimento")
        self.assertEqual(cliente.documento, dados["documento"], f"{nome}: documento")
        self.assertEqual(cliente.telefone, dados["telefone"], f"{nome}: telefone")
        self.assertEqual(
            cliente.canal_telefone,
            Cliente.CanalTelefone.WHATSAPP if dados["whatsapp"] == "sim" else Cliente.CanalTelefone.TELEFONE,
            f"{nome}: WhatsApp",
        )
        self.assertEqual(cliente.email, dados["email"], f"{nome}: e-mail")
        endereco = cliente.endereco_principal
        certo = esperado["endereco"]
        self.assertIsNotNone(endereco, f"{nome}: endereço")
        self.assertEqual(
            (endereco.cep, endereco.endereco, endereco.numero, endereco.complemento,
             endereco.bairro, endereco.cidade, endereco.estado),
            (certo["cep"], certo["rua"], certo["numero"], certo["complemento"],
             certo["bairro"], certo["cidade"], certo["uf"]),
            f"{nome}: endereço",
        )

    def test_cada_documento_vira_cliente_e_orcamento_certos(self):
        for nome in DOCUMENTOS:
            if nome.endswith(".pdf"):
                continue  # o PDF tem o seu teste, num banco sem o 01
            esperado = esperado_de(nome)
            with self.subTest(documento=nome):
                antes = set(Orcamento.objects.values_list("pk", flat=True))
                resposta = self.importar_e_criar(nome)
                novos = Orcamento.objects.exclude(pk__in=antes)
                if esperado["modo"] == "cliente":
                    self.assertFalse(novos.exists(), f"{nome}: criou orçamento no modo só cliente")
                    cliente = Cliente.objects.get(nome_cliente=esperado["cliente"]["nome"])
                    self.assertIn("/clientes/", resposta["Location"])
                    self.assertIn(f"abrir={cliente.pk}", resposta["Location"])
                    self.conferir_cliente(nome, cliente)
                    continue
                orcamento = novos.get()
                self.assertIn(f"/orcamentos/importar/concluido/{orcamento.pk}/", resposta["Location"])
                self.conferir_cliente(nome, orcamento.cliente)
                salvo = esperado["salvo"]
                self.assertEqual(orcamento.status, Orcamento.Status.RASCUNHO)
                self.assertEqual(str(orcamento.total), salvo["total"], f"{nome}: total")
                self.assertEqual(str(orcamento.desconto), salvo["desconto"], f"{nome}: desconto")
                self.assertEqual(
                    str(orcamento.valor_final) if orcamento.valor_final is not None else None,
                    salvo["valor_final"], f"{nome}: valor final",
                )
                self.assertEqual(orcamento.frete, Decimal(esperado["frete"].replace(".", "").replace(",", ".")))
                self.assertEqual(orcamento.validade.isoformat(), esperado["validade"], f"{nome}: validade")
                self.assertEqual(orcamento.forma_pagamento, esperado["forma_pagamento"], f"{nome}: pagamento")
                self.assertEqual(orcamento.forma_envio, esperado["forma_envio"], f"{nome}: envio")
                self.assertEqual(orcamento.observacoes, salvo["observacoes"], f"{nome}: observações")
                self.assertEqual(orcamento.contato, esperado["cliente"]["contato"], f"{nome}: contato")
                itens = list(ItemOrcamento.objects.filter(orcamento=orcamento).order_by("id"))
                self.assertEqual(len(itens), len(esperado["itens"]))
                for item, certo in zip(itens, esperado["itens"]):
                    self.assertEqual(item.descricao, certo["descricao"], f"{nome}: descrição")
                    self.assertEqual(
                        item.brinquedo.nome_brinquedo if item.brinquedo else None, certo["produto"],
                        f"{nome}: produto de “{certo['descricao']}”",
                    )
                    self.assertEqual(item.quantidade, int(certo["quantidade"]))
                    self.assertEqual(
                        item.valor_unitario,
                        Decimal(certo["valor_unitario"].replace(".", "").replace(",", ".")),
                    )

    def test_o_pdf_cria_o_mesmo_que_o_word(self):
        nome = "06-pdf-tabela-buffet-alegria.pdf"
        resposta = self.importar_e_criar(nome)
        orcamento = Orcamento.objects.get()
        self.assertIn(f"/orcamentos/importar/concluido/{orcamento.pk}/", resposta["Location"])
        self.conferir_cliente(nome, orcamento.cliente)
        self.assertEqual(str(orcamento.total), "25284.00")
        self.assertEqual(
            [(i.descricao, i.quantidade, i.valor_unitario) for i in orcamento.itens.order_by("id")],
            [("Cama elástica 3 m", 2, Decimal("2800.00")), ("Pula-pula", 1, Decimal("1234.00")),
             ("Air Game Kids", 1, Decimal("18000.00"))],
        )
        # O cliente que já existia foi LIGADO e completado -- não duplicado.
        self.assertEqual(Cliente.objects.filter(nome_cliente="Buffet Alegria").count(), 1)
