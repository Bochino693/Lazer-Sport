"""O automatizador da O.S. (LEIA-ME-V10, seção 122): o documento vira O.S. sozinho.

OS DOCUMENTOS SÃO MONTADOS AQUI MESMO -- o .docx com o XML mínimo do Word
(os mesmos montadores dos testes da importação do orçamento), o PDF com o
texto posicionado em colunas, à mão, e o .txt como texto. Nenhum documento
de cliente entra no repositório: clientes, CNPJs e telefones são
inventados (os CNPJs só passam na conta dos dígitos).

NADA SAI DO SERVIDOR: a leitura da IA do orçamento é trocada por uma que
explode se for chamada, e a consulta de CEP do cadastro por uma que não
vai à rede.
"""

from __future__ import annotations

import io
import json
import shutil
import tempfile
import zipfile
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from .importacao_os import arquivo as arq
from .importacao_os import campos, contexto, gravar
from .models import Cliente, DocumentoOrdemServico, EnderecoCliente, ItemOrdemServico, OrdemServico
from .permissoes import atribuir_funcoes
from .tests_importacao_word import montar_docx, montar_pdf, par, tabela

HOST = {"HTTP_HOST": "interno.testserver"}
URL = "/ordens-servico/importar/"
JSON = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest", **HOST}


def _data(dias: int) -> str:
    return (timezone.localdate() + timedelta(days=dias)).strftime("%d/%m/%Y")


def montar_pdf_colunas(linhas):
    """Um PDF de uma página; cada linha é [(x, texto), ...] numa altura própria.

    É assim que o PDF salvo pelo Word ou por um sistema escreve uma tabela:
    cada célula num ponto da página. O pypdf, em "layout", devolve as
    colunas separadas por espaço, e é isso que a leitura remonta.
    """
    comandos = ["BT /F1 10 Tf"]
    altura = 790
    for linha in linhas:
        for x, texto in linha:
            seguro = texto.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            comandos.append(f"1 0 0 1 {x} {altura} Tm ({seguro}) Tj")
        altura -= 16
    comandos.append("ET")
    conteudo = "\n".join(comandos)
    objetos = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(conteudo.encode('latin-1'))} >>\nstream\n{conteudo}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    saida = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    posicoes = []
    for numero, objeto in enumerate(objetos, start=1):
        posicoes.append(len(saida))
        saida += f"{numero} 0 obj\n{objeto}\nendobj\n".encode("latin-1")
    inicio = len(saida)
    saida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    for posicao in posicoes:
        saida += f"{posicao:010d} 00000 n \n".encode()
    saida += f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{inicio}\n%%EOF\n".encode()
    return saida


def recomprimir(docx: bytes) -> bytes:
    """O mesmo .docx salvo de novo: outros bytes, o mesmo texto."""
    entrada = zipfile.ZipFile(io.BytesIO(docx))
    saida = io.BytesIO()
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_STORED) as novo:
        for nome in entrada.namelist():
            novo.writestr(nome, entrada.read(nome))
        novo.writestr("docProps/core.xml", "<cp:coreProperties/>")
    return saida.getvalue()


def recomprimir_trocando(docx: bytes, trocas: dict) -> bytes:
    """O .docx com um texto trocado por outro (o XML vai comprimido no zip)."""
    entrada = zipfile.ZipFile(io.BytesIO(docx))
    saida = io.BytesIO()
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as novo:
        for nome in entrada.namelist():
            conteudo = entrada.read(nome).decode("utf-8")
            for velho, trocado in trocas.items():
                conteudo = conteudo.replace(velho, trocado)
            novo.writestr(nome, conteudo)
    return saida.getvalue()


# ----------------------------------------------------------- os documentos
def ficha_linhas(*, cliente="Buffet Alegria Ltda", telefone="(11) 98765-4321", numero="0457",
                 equipamento="Cama elástica 3 m", extra=""):
    """A ficha comum: rótulos em linha (vários na mesma), seção e tabela de peças."""
    return montar_docx(
        par(f"ORDEM DE SERVIÇO Nº {numero}")
        + par(f"Data de abertura: {_data(-3)}")
        + par(f"Cliente: {cliente}\tCNPJ: 22.333.444/0001-81")
        + par(f"Telefone: {telefone}  E-mail: contato@buffetalegria.com.br")
        + par("Endereço: Rua das Flores, 45 – Centro – Guarulhos/SP – CEP 07010-020")
        + par(f"Equipamento: {equipamento}\tNº de série: CE-3091")
        + par("Técnico: Marcos Lima - (11) 97777-1111")
        + par("DEFEITO RELATADO")
        + par("A lona rasgou na emenda depois da festa.")
        + par("O cliente pediu para ver também as molas.")
        + par("Serviço executado: Troca da lona e recolagem da emenda.")
        + par("PEÇAS UTILIZADAS")
        + tabela(["Peça", "Qtd", "Valor unitário", "Total"],
                 ["Lona 3 m", "1", "R$ 480,00", "R$ 480,00"],
                 ["Mola galvanizada", "4", "R$ 12,50", "R$ 50,00"])
        + par("Mão de obra: R$ 150,00")
        + par("Total: R$ 680,00")
        + par("Garantia: 90 dias")
        + par("Situação: Concluída")
        + extra,
        cabecalho=par("Lazer & Sport Brinquedos — CNPJ 54.486.908/0001-86 — (11) 96056-3135"),
    )


def ficha_em_tabela():
    """A ficha em tabela: rótulo | valor, a linha de títulos com os valores embaixo, e "Tipo"."""
    return montar_docx(
        par("ORDEM DE SERVIÇO")
        + tabela(["Cliente", "Escola Pequeno Príncipe"],
                 ["Telefone", "(21) 99876-1234"],
                 ["E-mail", "secretaria@pequenoprincipe.edu.br"])
        + tabela(["Equipamento", "Nº de série", "Prioridade"],
                 ["Escorregador duplo", "ESC-77", "Urgente"])
        + par("DEFEITO RELATADO")
        + tabela(["Rachadura na rampa, perto da escada."])
        + par(f"Agendado para: {_data(5)} às 14h30")
        + tabela(["Tipo", "Descrição", "Qtd", "Valor", "Total"],
                 ["Peça", "Rampa de fibra", "1", "R$ 900,00", "R$ 900,00"],
                 ["Serviço", "Instalação da rampa", "1", "R$ 250,00", "R$ 250,00"],
                 ["Deslocamento", "Ida e volta", "1", "R$ 120,00", "R$ 120,00"])
        + par("Total geral: R$ 1.270,00")
    )


def visita_em_pdf():
    """O PDF salvo por sistema: rótulo e valor em colunas, sem dois-pontos, e a tabela de peças."""
    return montar_pdf_colunas([
        [(60, "RELATÓRIO DE VISITA TÉCNICA - O.S. Nº 2026/118")],
        [(60, "Cliente: Condomínio Jardim Azul")],
        [(60, "Telefone: (11) 3333-4444")],
        [(60, "Equipamento"), (200, "Playground modular")],
        [(60, f"Data da visita: {_data(7)} às 9h")],
        [(60, "Defeito relatado: Balanço solto do lado esquerdo.")],
        [(60, "Peça"), (300, "Qtd"), (380, "Valor"), (470, "Total")],
        [(60, "Corrente inox"), (300, "2"), (380, "R$ 45,00"), (470, "R$ 90,00")],
        [(60, "Deslocamento"), (300, "1"), (380, "R$ 120,00"), (470, "R$ 120,00")],
        [(60, "Total: R$ 210,00")],
    ])


def pedido_em_txt():
    return (
        "PEDIDO DE SERVIÇO\n"
        "Cliente:\tArena Kids Diversões\n"
        "WhatsApp:\t(31) 98888-2222\n"
        "Equipamento:\tAir Game Kids\n"
        "Tipo:\tRevisão preventiva\n"
        "\n"
        "SERVIÇO EXECUTADO\n"
        "Reaperto geral e troca de 2 parafusos.\n"
        "\n"
        "Descrição            Qtd     Valor unit.     Total\n"
        "Parafuso inox        2       R$ 15,00        R$ 30,00\n"
        "Mão de obra          1       R$ 200,00       R$ 200,00\n"
        "Total: R$ 230,00\n"
    ).encode("utf-8")


def _ia_proibida(*args, **kwargs):
    raise AssertionError("o automatizador da O.S. nunca manda o documento para a IA")


class _Base(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._pasta = tempfile.mkdtemp(prefix="os-docs-teste-")
        cls._pasta_override = override_settings(OS_DOCUMENTOS_PRIVADOS_DIR=cls._pasta)
        cls._pasta_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._pasta_override.disable()
        shutil.rmtree(cls._pasta, ignore_errors=True)
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        cls.producao = cls.usuario("producao", ["producao"], first_name="Paula", last_name="Reis")
        cls.tecnico = cls.usuario("marcos", ["producao"], first_name="Marcos", last_name="Lima")

    @staticmethod
    def usuario(nome, funcoes, **extra):
        conta = User.objects.create_user(nome, f"{nome}@equipe.lazersport.com.br", "senha", **extra)
        atribuir_funcoes(conta, funcoes)
        return conta

    def setUp(self):
        cache.clear()
        contexto.esquecer()
        self.client.force_login(self.producao)
        self._sem_rede = [
            mock.patch("sistema_interno.clientes.buscar_dados_cep", return_value={}),
            mock.patch("sistema_interno.importacao_word.ia.ler_orcamento", side_effect=_ia_proibida),
            mock.patch("sistema_interno.importacao_word.ia.ler_pdf", side_effect=_ia_proibida),
        ]
        for remendo in self._sem_rede:
            remendo.start()
            self.addCleanup(remendo.stop)

    def enviar(self, nome, conteudo, **extra):
        resposta = self.client.post(URL, {"arquivo": SimpleUploadedFile(nome, conteudo)}, **JSON, **extra)
        return resposta

    def importar(self, nome, conteudo):
        resposta = self.enviar(nome, conteudo)
        self.assertEqual(resposta.status_code, 200, resposta.content[:400])
        return resposta.json()

    def completar(self, documento_id, **dados):
        resposta = self.client.post(f"{URL}{documento_id}/", dict(dados, action="completar"), **JSON)
        self.assertEqual(resposta.status_code, 200, resposta.content[:400])
        return resposta.json()


# ======================================================================
# A LEITURA
# ======================================================================
class LeituraTests(_Base):
    def ler(self, nome, conteudo):
        lido = arq.ler(nome, conteudo)
        return gravar.montar(nome, lido, hoje=timezone.localdate(), ctx=contexto.carregar())

    def test_ficha_com_rotulos_em_linha_secao_e_tabela_de_pecas(self):
        leitura = self.ler("os-0457.docx", ficha_linhas())
        os_ = leitura["os"]
        self.assertEqual(os_["numero"], "0457")
        self.assertEqual(os_["equipamento"], "Cama elástica 3 m")
        self.assertEqual(os_["numero_serie"], "CE-3091")
        self.assertEqual(os_["defeito_relatado"],
                         "A lona rasgou na emenda depois da festa.\nO cliente pediu para ver também as molas.")
        self.assertEqual(os_["servico_executado"], "Troca da lona e recolagem da emenda.")
        self.assertEqual(os_["status"], "concluida")
        self.assertEqual(os_["tecnico_id"], self.tecnico.pk)
        self.assertEqual(os_["total_documento"], "680.00")
        self.assertEqual(os_["data_documento"], (timezone.localdate() - timedelta(days=3)).isoformat())
        # Concluída na data do documento; a garantia conta dela (90 dias).
        self.assertEqual(os_["garantia_ate"], (timezone.localdate() + timedelta(days=87)).isoformat())
        itens = [(i["tipo"], i["descricao"], i["quantidade"], i["valor_unitario"]) for i in leitura["itens"]]
        self.assertEqual(itens, [
            ("peca", "Lona 3 m", 1, "480.00"),
            ("peca", "Mola galvanizada", 4, "12.50"),
            ("servico", "Mão de obra", 1, "150.00"),
        ])
        cliente = leitura["cliente"]
        self.assertEqual(cliente["nome"], "Buffet Alegria Ltda")
        self.assertEqual(cliente["documento"], "22.333.444/0001-81")
        self.assertEqual(cliente["telefone"], "(11) 98765-4321")
        self.assertEqual(cliente["email"], "contato@buffetalegria.com.br")
        self.assertEqual(cliente["endereco"]["cidade"], "Guarulhos")
        self.assertEqual(cliente["endereco"]["estado"], "SP")
        self.assertEqual(cliente["endereco"]["cep"], "07010-020")

    def test_a_fabrica_e_o_tecnico_nunca_viram_o_cliente(self):
        leitura = self.ler("os.docx", ficha_linhas())
        cliente = leitura["cliente"]
        # O CNPJ e o telefone do timbre da casa, e o celular do técnico,
        # ficam de fora do cadastro.
        self.assertNotIn("54.486.908", cliente["documento"])
        self.assertNotEqual(cliente["telefone"], "(11) 96056-3135")
        self.assertNotEqual(cliente["telefone"], "(11) 97777-1111")
        self.assertNotIn("Marcos", cliente["nome"])

    def test_ficha_em_tabela_com_titulos_em_cima_e_coluna_tipo(self):
        leitura = self.ler("ficha.docx", ficha_em_tabela())
        os_ = leitura["os"]
        self.assertEqual(os_["equipamento"], "Escorregador duplo")
        self.assertEqual(os_["numero_serie"], "ESC-77")
        self.assertEqual(os_["prioridade"], "urgente")
        self.assertEqual(os_["defeito_relatado"], "Rachadura na rampa, perto da escada.")
        self.assertEqual(os_["status"], "agendada")
        self.assertTrue(os_["agendada_para"].startswith((timezone.localdate() + timedelta(days=5)).isoformat()
                                                         + "T14:30"))
        self.assertEqual([(i["tipo"], i["descricao"]) for i in leitura["itens"]], [
            ("peca", "Rampa de fibra"), ("servico", "Instalação da rampa"), ("deslocamento", "Ida e volta"),
        ])
        self.assertEqual(leitura["cliente"]["nome"], "Escola Pequeno Príncipe")
        self.assertEqual(leitura["cliente"]["email"], "secretaria@pequenoprincipe.edu.br")

    def test_pdf_com_colunas_sem_dois_pontos(self):
        leitura = self.ler("visita.pdf", visita_em_pdf())
        os_ = leitura["os"]
        self.assertEqual(os_["tipo"], "visita")
        self.assertEqual(os_["numero"], "2026/118")
        self.assertEqual(os_["equipamento"], "Playground modular")
        self.assertEqual(os_["status"], "agendada")
        self.assertEqual([(i["tipo"], i["descricao"], i["quantidade"], i["valor_unitario"]) for i in leitura["itens"]], [
            ("peca", "Corrente inox", 2, "45.00"), ("deslocamento", "Deslocamento", 1, "120.00"),
        ])
        self.assertEqual(leitura["cliente"]["telefone"], "(11) 3333-4444")
        self.assertFalse(leitura["cliente"]["whatsapp"])

    def test_txt_com_tabulacoes_e_colunas(self):
        leitura = self.ler("pedido.txt", pedido_em_txt())
        os_ = leitura["os"]
        self.assertEqual(os_["equipamento"], "Air Game Kids")
        self.assertEqual(os_["tipo"], "revisao")
        self.assertEqual(os_["servico_executado"], "Reaperto geral e troca de 2 parafusos.")
        self.assertEqual(os_["status"], "concluida")
        self.assertEqual(sum(Decimal(i["valor_unitario"]) * i["quantidade"] for i in leitura["itens"]),
                         Decimal("230.00"))
        self.assertEqual(leitura["cliente"]["nome"], "Arena Kids Diversões")
        self.assertEqual(leitura["cliente"]["telefone"], "(31) 98888-2222")

    def test_rotulo_de_dois_sentidos_decide_pelo_valor(self):
        self.assertEqual(campos.interpretar("agendada_para", f"{_data(2)}", estrito=True)["data"],
                         (timezone.localdate() + timedelta(days=2)).isoformat())
        self.assertIsNone(campos.interpretar("item_deslocamento", "2 visitas", estrito=True))
        self.assertEqual(campos.interpretar("item_deslocamento", "R$ 80,00", estrito=True), Decimal("80.00"))
        self.assertEqual(campos.interpretar("valor_pago", "R$ 1.234,56", estrito=False), Decimal("1234.56"))
        self.assertIsNone(campos.interpretar("tipo", "Troca da lona e reparo da costura " * 3, estrito=True))
        self.assertEqual(campos.mapear("status", "Aguardando peça"), "aguardando_peca")
        self.assertEqual(campos.mapear("status", "Em andamento"), "em_execucao")
        self.assertEqual(campos.mapear("status", "Finalizado"), "concluida")
        self.assertEqual(campos.ler_duracao("Garantia de 3 (três) meses"), {"meses": 3})

    def test_servico_com_texto_e_o_pedido_e_nao_o_tipo(self):
        leitura = self.ler("pedido.docx", montar_docx(
            par("Cliente: Ana Paula Souza") + par("Celular: (11) 95555-0101")
            + par("Equipamento: Cama elástica") + par("Serviço: Reparo da costura da lona")
            + par("Tipo de serviço: Instalação")
        ))
        self.assertEqual(leitura["os"]["defeito_relatado"], "Reparo da costura da lona")
        self.assertEqual(leitura["os"]["tipo"], "instalacao")
        leitura = self.ler("tipo.docx", montar_docx(
            par("Cliente: Ana Paula Souza") + par("Equipamento: Cama elástica")
            + par("Serviço: Manutenção corretiva") + par("Defeito: Lona solta.")
        ))
        self.assertEqual(leitura["os"]["tipo"], "manutencao")
        self.assertEqual(leitura["os"]["defeito_relatado"], "Lona solta.")

    def test_varios_rotulos_na_mesma_linha_e_hora_nao_corta(self):
        pares = campos.pares_da_linha("Equipamento: Pula-pula  Nº de série: PP-1  Agendado para: 10/01/2027 09:30")
        self.assertEqual([p[2] for p in pares], ["Equipamento", "Nº de série", "Agendado para"])

    def test_texto_do_documento_nao_fica_no_banco_inteiro(self):
        leitura = self.ler("os.docx", ficha_linhas())
        guardado = json.dumps(leitura, ensure_ascii=False)
        self.assertNotIn("linhas", leitura)
        self.assertNotIn("96056-3135", guardado)


# ======================================================================
# CRIAR SOZINHO
# ======================================================================
class CriarSozinhoTests(_Base):
    def test_documento_completo_vira_os_na_hora(self):
        resposta = self.importar("os-0457.docx", ficha_linhas())
        self.assertEqual(resposta["estado"], "criada", resposta)
        ordem = OrdemServico.objects.get(pk=resposta["os"]["id"])
        self.assertEqual(ordem.responsavel, self.producao)
        self.assertEqual(ordem.status, OrdemServico.Status.CONCLUIDA)
        self.assertEqual(ordem.tipo, OrdemServico.Tipo.MANUTENCAO)
        self.assertEqual(ordem.equipamento, "Cama elástica 3 m")
        self.assertEqual(ordem.numero_serie, "CE-3091")
        self.assertEqual(ordem.tecnico, self.tecnico)
        self.assertEqual(ordem.total, Decimal("680.00"))
        self.assertEqual(ordem.itens.count(), 3)
        self.assertEqual(ordem.garantia_ate, timezone.localdate() + timedelta(days=87))
        self.assertEqual(timezone.localtime(ordem.concluida_em).date(), timezone.localdate() - timedelta(days=3))
        self.assertIn("Rua das Flores", ordem.endereco_servico)
        # O cliente foi cadastrado pelas regras da aba Clientes, com o endereço.
        cliente = ordem.cliente
        self.assertEqual(cliente.nome_cliente, "Buffet Alegria Ltda")
        self.assertEqual(cliente.documento_chave, "22333444000181")
        self.assertEqual(cliente.canal_telefone, Cliente.CanalTelefone.WHATSAPP)
        self.assertEqual(EnderecoCliente.objects.get(cliente=cliente).cidade, "Guarulhos")
        self.assertEqual(ordem.whatsapp_cliente, "(11) 98765-4321")
        # O documento original ficou anexado, no cofre.
        documento = DocumentoOrdemServico.objects.get(ordem=ordem)
        self.assertEqual(documento.situacao, DocumentoOrdemServico.Situacao.CRIADA)
        self.assertEqual(documento.enviado_por, self.producao)
        self.assertEqual(documento.numero_no_documento, "0457")
        self.assertTrue(Path(self._pasta, documento.arquivo.name).exists())
        self.assertTrue(documento.arquivo.name.startswith("os/"))
        self.assertNotIn("Buffet", documento.arquivo.name)
        self.assertEqual(resposta["os"]["numero"], ordem.numero_documento)
        self.assertIn(f"abrir_os={ordem.pk}", resposta["os"]["link"])

    def test_sem_situacao_escrita_nasce_como_a_os_nova_da_tela(self):
        doc = montar_docx(
            par("Cliente: Ana Paula Souza")
            + par("Celular: (11) 95555-0101")
            + par("Equipamento: Pula-pula castelo")
            + par("Defeito: O soprador não liga.")
        )
        resposta = self.importar("chamado.docx", doc)
        self.assertEqual(resposta["estado"], "criada", resposta)
        ordem = OrdemServico.objects.get(pk=resposta["os"]["id"])
        self.assertEqual(ordem.status, OrdemServico.Status.AGUARDANDO_RESPOSTA)
        self.assertEqual(ordem.numero_serie, f"LS-PAT-{ordem.pk:06d}")
        self.assertEqual(ordem.itens.count(), 0)
        self.assertEqual(ordem.defeito_relatado, "O soprador não liga.")

    def test_agenda_que_passou_e_garantia_vencida_viram_aviso(self):
        doc = montar_docx(
            par("Cliente: Ana Paula Souza")
            + par("Celular: (11) 95555-0101")
            + par("Equipamento: Pula-pula castelo")
            + par("Defeito: O soprador não liga.")
            + par(f"Agendado para: {_data(-20)} às 10h")
            + par(f"Garantia até: {_data(-1)}")
        )
        resposta = self.importar("velha.docx", doc)
        self.assertEqual(resposta["estado"], "criada", resposta)
        ordem = OrdemServico.objects.get(pk=resposta["os"]["id"])
        self.assertIsNone(ordem.agendada_para)
        self.assertIsNone(ordem.garantia_ate)
        avisos = " ".join(resposta["avisos"])
        self.assertIn("já passou", avisos)
        self.assertIn("garantia", avisos.lower())

    def test_pagamento_so_entra_para_quem_lanca_pagamento(self):
        doc = ficha_linhas(extra=par("Valor pago: R$ 680,00"))
        resposta = self.importar("paga.docx", doc)
        ordem = OrdemServico.objects.get(pk=resposta["os"]["id"])
        self.assertEqual(ordem.status_pagamento, OrdemServico.StatusPagamento.PENDENTE)
        self.assertIn("Financeiro", " ".join(resposta["avisos"]))

        gestor = self.usuario("gestora", ["gestao"])
        self.client.force_login(gestor)
        resposta = self.importar("paga-2.docx", ficha_linhas(numero="0460", telefone="(11) 94444-0000",
                                                             cliente="Buffet Sonho Meu",
                                                             extra=par("Valor pago: R$ 680,00")))
        self.assertEqual(resposta["estado"], "criada", resposta)
        ordem = OrdemServico.objects.get(pk=resposta["os"]["id"])
        self.assertEqual(ordem.status_pagamento, OrdemServico.StatusPagamento.PAGO)
        self.assertEqual(ordem.valor_pago, Decimal("680.00"))

    def test_o_chamado_escrito_no_documento_e_ligado(self):
        from core.models import ClientePerfil, Manutencao

        dono = User.objects.create_user("cliente-site", password="x")
        perfil, _ = ClientePerfil.objects.get_or_create(user=dono)
        chamado = Manutencao.objects.create(descricao="Rasgou a lona", status="P", usuario=perfil)
        doc = montar_docx(
            par(f"Chamado: MAN-{chamado.pk:05d}")
            + par("Cliente: Ana Paula Souza")
            + par("Celular: (11) 95555-0101")
            + par("Equipamento: Cama elástica")
            + par("Defeito: Lona rasgada.")
        )
        resposta = self.importar("chamado.docx", doc)
        ordem = OrdemServico.objects.get(pk=resposta["os"]["id"])
        self.assertEqual(ordem.manutencao, chamado)

    def test_os_criada_aparece_com_o_anexo_na_tela(self):
        resposta = self.importar("os-0457.docx", ficha_linhas())
        ordem_id = resposta["os"]["id"]
        anexos = self.client.get(f"/ordens-servico/{ordem_id}/documentos/?formato=json", **HOST).json()
        self.assertEqual(anexos["documentos"][0]["arquivo"], "os-0457.docx")
        arquivo = self.client.get(anexos["documentos"][0]["url"], **HOST)
        self.assertEqual(arquivo.status_code, 200)
        self.assertEqual(arquivo["Cache-Control"], "no-store, private")
        self.assertTrue(arquivo.content.startswith(b"PK"))
        tela = self.client.get(f"/ordens-servico/?q={resposta['os']['numero']}", **HOST)
        self.assertContains(tela, "Cama elástica 3 m")

    def test_lote_de_dez_documentos_um_por_pedido(self):
        nomes = ("Buffet Arco-Íris", "Escola Monteiro Lobato", "Clube dos Bandeirantes", "Condomínio Vila Rica",
                 "Espaço Mundo Encantado", "Parque das Águas", "Colégio São Bento", "Arena Pinheiros",
                 "Restaurante Sabor Caipira", "Hotel Fazenda Recanto")
        estados = []
        for numero, nome in enumerate(nomes):
            doc = montar_docx(
                par(f"Ordem de serviço nº {900 + numero}")
                + par(f"Cliente: {nome}")
                + par(f"Telefone: (11) 9{numero}{numero}{numero}{numero}-12{numero}{numero}")
                + par(f"Equipamento: Brinquedo número {numero}")
                + par("Defeito: Não liga.")
            )
            estados.append(self.importar(f"lote-{numero}.docx", doc)["estado"])
        self.assertEqual(estados, ["criada"] * 10)
        self.assertEqual(OrdemServico.objects.count(), 10)
        self.assertEqual(Cliente.objects.count(), 10)

    def test_excluir_a_os_apaga_o_documento_e_o_arquivo(self):
        resposta = self.importar("os-0457.docx", ficha_linhas())
        documento = DocumentoOrdemServico.objects.get(pk=resposta["documento"])
        caminho = Path(self._pasta, documento.arquivo.name)
        self.assertTrue(caminho.exists())
        OrdemServico.objects.get(pk=resposta["os"]["id"]).delete()
        self.assertFalse(DocumentoOrdemServico.objects.filter(pk=documento.pk).exists())
        self.assertFalse(caminho.exists())


# ======================================================================
# O CLIENTE QUE JÁ EXISTE
# ======================================================================
class ClienteRepetidoTests(_Base):
    def test_telefone_escrito_de_outro_jeito_liga_ao_cadastro_e_completa_so_o_vazio(self):
        cliente = Cliente.objects.create(nome_cliente="Buffet Alegria", telefone="11987654321",
                                         canal_telefone=Cliente.CanalTelefone.WHATSAPP)
        resposta = self.importar("os.docx", ficha_linhas(cliente="Buffet Alegria Eventos"))
        self.assertEqual(resposta["estado"], "criada", resposta)
        self.assertEqual(Cliente.objects.count(), 1)
        ordem = OrdemServico.objects.get(pk=resposta["os"]["id"])
        self.assertEqual(ordem.cliente, cliente)
        cliente.refresh_from_db()
        self.assertEqual(cliente.nome_cliente, "Buffet Alegria")
        self.assertEqual(cliente.telefone, "11987654321")
        self.assertEqual(cliente.email, "contato@buffetalegria.com.br")
        self.assertEqual(cliente.documento_chave, "22333444000181")
        self.assertTrue(EnderecoCliente.objects.filter(cliente=cliente).exists())
        self.assertIn("completado", " ".join(resposta["avisos"]))

    def test_cnpj_liga_mesmo_com_outro_nome(self):
        cliente = Cliente.objects.create(nome_cliente="Alegria Festas", documento="22.333.444/0001-81",
                                         telefone="(11) 92222-3333")
        resposta = self.importar("os.docx", ficha_linhas())
        self.assertEqual(resposta["estado"], "criada", resposta)
        self.assertEqual(OrdemServico.objects.get(pk=resposta["os"]["id"]).cliente, cliente)
        self.assertEqual(Cliente.objects.count(), 1)

    def test_so_o_nome_bate_pergunta_e_a_escolha_liga(self):
        cliente = Cliente.objects.create(nome_cliente="Ana Paula Souza", telefone="(11) 91111-2222")
        doc = montar_docx(
            par("Cliente: Ana Paula Souza")
            + par("Equipamento: Pula-pula castelo")
            + par("Defeito: O soprador não liga.")
        )
        resposta = self.importar("so-nome.docx", doc)
        self.assertEqual(resposta["estado"], "falta", resposta)
        self.assertEqual(OrdemServico.objects.count(), 0)
        falta = next(f for f in resposta["faltas"] if f["campo"] == "cliente")
        self.assertEqual(falta["candidatos"][0]["id"], cliente.pk)
        self.assertEqual(falta["valores"]["nome"], "Ana Paula Souza")
        criada = self.completar(resposta["documento"], cliente_escolha=f"id:{cliente.pk}")
        self.assertEqual(criada["estado"], "criada", criada)
        self.assertEqual(OrdemServico.objects.get().cliente, cliente)
        self.assertEqual(Cliente.objects.count(), 1)

    def test_dois_dados_apontando_para_cadastros_diferentes_pergunta(self):
        Cliente.objects.create(nome_cliente="Cliente A", telefone="(11) 98765-4321")
        Cliente.objects.create(nome_cliente="Cliente B", email="contato@buffetalegria.com.br",
                               telefone="(11) 93333-0000")
        doc = montar_docx(
            par("Cliente: Buffet Alegria Ltda")
            + par("Telefone: (11) 98765-4321")
            + par("E-mail: contato@buffetalegria.com.br")
            + par("Equipamento: Cama elástica")
            + par("Defeito: Lona rasgada.")
        )
        resposta = self.importar("conflito.docx", doc)
        self.assertEqual(resposta["estado"], "falta")
        falta = next(f for f in resposta["faltas"] if f["campo"] == "cliente")
        self.assertEqual(len(falta["candidatos"]), 2)

    def test_so_o_nome_sem_contato_pede_o_contato_ou_so_o_nome(self):
        doc = montar_docx(
            par("Cliente: Rodrigo Mendes")
            + par("Equipamento: Cama elástica")
            + par("Defeito: Lona rasgada.")
        )
        resposta = self.importar("sem-contato.docx", doc)
        self.assertEqual(resposta["estado"], "falta")
        self.assertIn("telefone", resposta["faltas"][0]["motivo"])
        criada = self.completar(resposta["documento"], cliente_escolha="novo", cliente_nome="Rodrigo Mendes",
                                cliente_telefone="11 96666 7777", cliente_email="")
        self.assertEqual(criada["estado"], "criada", criada)
        cliente = Cliente.objects.get()
        self.assertEqual(cliente.telefone, "(11) 96666-7777")

    def test_so_o_nome_na_os_sem_cadastro(self):
        doc = montar_docx(
            par("Cliente: Rodrigo Mendes")
            + par("Equipamento: Cama elástica")
            + par("Defeito: Lona rasgada.")
        )
        resposta = self.importar("sem-contato.docx", doc)
        criada = self.completar(resposta["documento"], cliente_escolha="sem_cadastro")
        self.assertEqual(criada["estado"], "criada", criada)
        ordem = OrdemServico.objects.get()
        self.assertIsNone(ordem.cliente)
        self.assertEqual(ordem.nome_cliente, "Rodrigo Mendes")
        self.assertEqual(Cliente.objects.count(), 0)


# ======================================================================
# O MESMO DOCUMENTO DUAS VEZES
# ======================================================================
class DocumentoRepetidoTests(_Base):
    def test_o_mesmo_arquivo_nao_cria_duas_os(self):
        doc = ficha_linhas()
        primeira = self.importar("os.docx", doc)
        segunda = self.importar("os (cópia).docx", doc)
        self.assertEqual(segunda["estado"], "repetida", segunda)
        self.assertEqual(segunda["os"]["id"], primeira["os"]["id"])
        self.assertIn("já importad", segunda["motivo"].lower())
        self.assertEqual(OrdemServico.objects.count(), 1)
        self.assertEqual(DocumentoOrdemServico.objects.count(), 1)

    def test_o_mesmo_texto_salvo_de_novo_tambem_repete(self):
        doc = ficha_linhas()
        primeira = self.importar("os.docx", doc)
        segunda = self.importar("os-salva-de-novo.docx", recomprimir(doc))
        self.assertEqual(segunda["estado"], "repetida", segunda)
        self.assertEqual(segunda["os"]["id"], primeira["os"]["id"])

    def test_a_os_impressa_pelo_painel_nao_volta_como_nova(self):
        ordem = OrdemServico.objects.create(nome_cliente="Buffet X", equipamento="Tobogã")
        doc = montar_docx(
            par(f"{ordem.numero_documento} — Ordem de Serviço")
            + par("Cliente: Buffet X")
            + par("Telefone: (11) 98111-2222")
            + par("Equipamento: Tobogã")
            + par("Defeito: Escada solta.")
        )
        resposta = self.importar("impressa.pdf.docx", doc)
        self.assertEqual(resposta["estado"], "repetida", resposta)
        self.assertEqual(resposta["os"]["id"], ordem.pk)
        self.assertEqual(OrdemServico.objects.count(), 1)

    def test_o_numero_escrito_com_o_mesmo_cliente_repete(self):
        self.importar("os.docx", ficha_linhas(numero="0777"))
        outra = ficha_linhas(numero="0777", extra=par("Observações: via do cliente, assinada."))
        resposta = self.importar("os-via-cliente.docx", outra)
        self.assertEqual(resposta["estado"], "repetida", resposta)
        self.assertEqual(OrdemServico.objects.count(), 1)

    def test_o_mesmo_numero_de_outro_cliente_nao_repete(self):
        self.importar("os.docx", ficha_linhas(numero="0778"))
        outra = ficha_linhas(numero="0778", cliente="Escola Sol Nascente", telefone="(11) 92020-3030")
        outra = recomprimir_trocando(outra, {"22.333.444/0001-81": "33.444.555/0001-81",
                                             "contato@buffetalegria.com.br": "diretoria@solnascente.edu.br"})
        resposta = self.importar("outra.docx", outra)
        self.assertEqual(resposta["estado"], "criada", resposta)

    def test_dois_envios_ao_mesmo_tempo_param_no_indice_unico_sem_arquivo_orfao(self):
        """A busca de repetido não viu o primeiro (corrida): o banco segura, e o cofre fica limpo."""
        doc = ficha_linhas()
        primeira = self.importar("os.docx", doc)
        arquivos_antes = sorted(Path(self._pasta).rglob("*.docx"))
        with mock.patch("sistema_interno.importacao_os.gravar.procurar_repetido", return_value=([], "numero")):
            segunda = self.importar("os-de-novo.docx", doc)
        self.assertEqual(segunda["estado"], "repetida", segunda)
        self.assertEqual(segunda["os"]["id"], primeira["os"]["id"])
        self.assertEqual(OrdemServico.objects.count(), 1)
        self.assertEqual(sorted(Path(self._pasta).rglob("*.docx")), arquivos_antes)

    def test_o_pendente_enviado_de_novo_e_o_mesmo(self):
        doc = montar_docx(par("Cliente: Rodrigo Mendes") + par("Defeito: Lona rasgada."))
        primeira = self.importar("pendente.docx", doc)
        segunda = self.importar("pendente.docx", doc)
        self.assertEqual(primeira["estado"], "falta")
        self.assertEqual(segunda["estado"], "falta")
        self.assertEqual(segunda["documento"], primeira["documento"])
        self.assertIn("já foi lido", segunda["recado"])
        self.assertEqual(DocumentoOrdemServico.objects.count(), 1)


# ======================================================================
# COMPLETAR O QUE FALTA
# ======================================================================
class CompletarTests(_Base):
    def test_sem_equipamento_pede_so_o_equipamento(self):
        doc = montar_docx(
            par("Cliente: Ana Paula Souza")
            + par("Celular: (11) 95555-0101")
            + par("Defeito: O motor faz barulho e esquenta.")
        )
        resposta = self.importar("sem-equipamento.docx", doc)
        self.assertEqual(resposta["estado"], "falta")
        self.assertEqual([f["campo"] for f in resposta["faltas"]], ["equipamento"])
        documento = DocumentoOrdemServico.objects.get(pk=resposta["documento"])
        self.assertEqual(documento.situacao, DocumentoOrdemServico.Situacao.PENDENTE)
        self.assertIsNone(documento.ordem)
        self.assertTrue(documento.arquivo)
        criada = self.completar(resposta["documento"], equipamento="Soprador 1 cv")
        self.assertEqual(criada["estado"], "criada", criada)
        documento.refresh_from_db()
        self.assertEqual(documento.situacao, DocumentoOrdemServico.Situacao.CRIADA)
        self.assertEqual(documento.ordem.equipamento, "Soprador 1 cv")
        self.assertEqual(documento.ordem.defeito_relatado, "O motor faz barulho e esquenta.")

    def test_linha_sem_valor_pede_o_valor_e_cria_com_a_conta_certa(self):
        doc = montar_docx(
            par("Cliente: Ana Paula Souza")
            + par("Celular: (11) 95555-0101")
            + par("Equipamento: Cama elástica")
            + par("Defeito: Lona rasgada.")
            + tabela(["Descrição", "Qtd", "Valor unitário"],
                     ["Lona nova", "1", "R$ 480,00"],
                     ["Costura reforçada", "2", ""])
        )
        resposta = self.importar("sem-valor.docx", doc)
        self.assertEqual(resposta["estado"], "falta")
        valores = next(f for f in resposta["faltas"] if f["campo"] == "valores")
        self.assertEqual([i["descricao"] for i in valores["itens"]], ["Lona nova", "Costura reforçada"])
        self.assertEqual(valores["itens"][0]["valor_unitario"], "480,00")
        criada = self.completar(resposta["documento"], itens_valores=json.dumps([
            {"quantidade": "1", "valor_unitario": "480,00"}, {"quantidade": "2", "valor_unitario": "35"},
        ]), frete="", desconto="")
        self.assertEqual(criada["estado"], "criada", criada)
        ordem = OrdemServico.objects.get()
        self.assertEqual(ordem.total, Decimal("550.00"))
        self.assertEqual(ordem.itens.get(descricao="Costura reforçada").tipo, ItemOrdemServico.Tipo.SERVICO)

    def test_total_que_nao_bate_segura_e_o_desconto_fecha(self):
        doc = montar_docx(
            par("Cliente: Ana Paula Souza")
            + par("Celular: (11) 95555-0101")
            + par("Equipamento: Cama elástica")
            + par("Defeito: Lona rasgada.")
            + tabela(["Descrição", "Qtd", "Valor unitário", "Total"],
                     ["Lona nova", "1", "R$ 480,00", "R$ 480,00"],
                     ["Mão de obra", "1", "R$ 150,00", "R$ 150,00"])
            + par("Valor total: R$ 600,00")
        )
        resposta = self.importar("nao-bate.docx", doc)
        self.assertEqual(resposta["estado"], "falta")
        valores = next(f for f in resposta["faltas"] if f["campo"] == "valores")
        self.assertIn("R$ 630,00", valores["motivo"])
        self.assertEqual(valores["diferenca"], "R$ 30,00")
        criada = self.completar(resposta["documento"], usar_total="desconto", itens_valores=json.dumps([
            {"quantidade": "1", "valor_unitario": "480,00"}, {"quantidade": "1", "valor_unitario": "150,00"},
        ]), frete="", desconto="")
        self.assertEqual(criada["estado"], "criada", criada)
        ordem = OrdemServico.objects.get()
        self.assertEqual(ordem.desconto, Decimal("30.00"))
        self.assertEqual(ordem.total, Decimal("600.00"))

    def test_valor_invalido_continua_esperando_com_o_motivo(self):
        doc = montar_docx(
            par("Cliente: Ana Paula Souza")
            + par("Celular: (11) 95555-0101")
            + par("Equipamento: Cama elástica")
            + par("Defeito: Lona rasgada.")
            + tabela(["Descrição", "Qtd", "Valor unitário"], ["Costura", "1", ""])
        )
        resposta = self.importar("invalido.docx", doc)
        de_novo = self.completar(resposta["documento"], itens_valores=json.dumps([
            {"quantidade": "1", "valor_unitario": "trinta reais"},
        ]))
        self.assertEqual(de_novo["estado"], "falta")
        self.assertTrue(de_novo["erros"])
        self.assertEqual(OrdemServico.objects.count(), 0)

    def test_concluida_sem_servico_executado_pede_o_que_foi_feito(self):
        doc = montar_docx(
            par("Cliente: Ana Paula Souza")
            + par("Celular: (11) 95555-0101")
            + par("Equipamento: Cama elástica")
            + par("Defeito: Lona rasgada.")
            + par("Situação: Finalizada")
        )
        resposta = self.importar("concluida.docx", doc)
        self.assertEqual([f["campo"] for f in resposta["faltas"]], ["servico_executado"])
        criada = self.completar(resposta["documento"], servico_executado="Lona trocada.")
        self.assertEqual(criada["estado"], "criada", criada)
        self.assertEqual(OrdemServico.objects.get().status, OrdemServico.Status.CONCLUIDA)

    def test_concluida_so_com_mao_de_obra_ainda_pede_o_que_foi_feito(self):
        doc = montar_docx(
            par("Cliente: Ana Paula Souza") + par("Celular: (11) 95555-0101")
            + par("Equipamento: Cama elástica") + par("Defeito: Lona rasgada.")
            + par("Mão de obra: R$ 150,00") + par("Status: Concluído")
        )
        resposta = self.importar("so-mao-de-obra.docx", doc)
        self.assertEqual([f["campo"] for f in resposta["faltas"]], ["servico_executado"])
        doc = montar_docx(
            par("Cliente: Ana Paula Souza") + par("Celular: (11) 95555-0101")
            + par("Equipamento: Cama elástica") + par("Defeito: Lona rasgada.")
            + tabela(["Serviço", "Qtd", "Valor"], ["Troca da lona", "1", "R$ 300,00"])
            + par("Status: Concluído")
        )
        resposta = self.importar("com-servico.docx", doc)
        self.assertEqual(resposta["estado"], "criada", resposta)
        ordem = OrdemServico.objects.get(pk=resposta["os"]["id"])
        self.assertEqual(ordem.servico_executado, "Troca da lona")
        self.assertIn("montado com as linhas", " ".join(resposta["avisos"]))

    def test_descartar_apaga_o_registro_e_o_arquivo(self):
        doc = montar_docx(par("Cliente: Rodrigo Mendes") + par("Defeito: Lona rasgada."))
        resposta = self.importar("descartar.docx", doc)
        documento = DocumentoOrdemServico.objects.get(pk=resposta["documento"])
        caminho = Path(self._pasta, documento.arquivo.name)
        self.assertTrue(caminho.exists())
        saida = self.client.post(f"{URL}{documento.pk}/", {"action": "descartar"}, **JSON).json()
        self.assertEqual(saida["estado"], "descartado")
        self.assertFalse(DocumentoOrdemServico.objects.exists())
        self.assertFalse(caminho.exists())

    def test_a_lista_de_espera_traz_o_que_falta(self):
        doc = montar_docx(par("Cliente: Rodrigo Mendes") + par("Defeito: Lona rasgada."))
        self.importar("espera.docx", doc)
        pendentes = self.client.get(f"{URL}?formato=json", **HOST).json()["pendentes"]
        self.assertEqual(len(pendentes), 1)
        self.assertEqual(pendentes[0]["arquivo"], "espera.docx")
        self.assertEqual({f["campo"] for f in pendentes[0]["faltas"]}, {"cliente", "equipamento"})


# ======================================================================
# O QUE NÃO DÁ PARA LER
# ======================================================================
class IlegivelTests(_Base):
    def test_pdf_que_e_foto_diz_o_motivo_e_nao_grava_nada(self):
        resposta = self.importar("digitalizado.pdf", montar_pdf(linhas=()))
        self.assertEqual(resposta["estado"], "ilegivel")
        self.assertIn("imagem", resposta["motivo"])
        self.assertNotIn("orçamento", resposta["motivo"])
        self.assertEqual(DocumentoOrdemServico.objects.count(), 0)

    def test_formatos_recusados_com_a_frase_do_que_fazer(self):
        casos = {
            "antigo.doc": b"\xd0\xcf\x11\xe0" + b"0" * 64,
            "foto.jpg": b"\xff\xd8\xff" + b"0" * 64,
            "planilha.xlsx": b"PK\x03\x04" + b"0" * 64,
            "vazio.docx": b"",
            "falso.txt": b"PK\x03\x04" + b"\x00" * 64,
        }
        for nome, conteudo in casos.items():
            with self.subTest(arquivo=nome):
                resposta = self.importar(nome, conteudo)
                self.assertEqual(resposta["estado"], "ilegivel")
                self.assertTrue(resposta["motivo"])
        self.assertEqual(DocumentoOrdemServico.objects.count(), 0)
        self.assertEqual(OrdemServico.objects.count(), 0)

    def test_erro_inesperado_responde_o_motivo_e_o_lote_segue(self):
        with mock.patch("sistema_interno.importacao_os.gravar.montar", side_effect=RuntimeError("quebrou")):
            with self.assertLogs("sistema_interno.views_importacao_os", level="ERROR"), \
                    self.assertLogs("django.request", level="ERROR"):
                resposta = self.enviar("os.docx", ficha_linhas())
        self.assertEqual(resposta.status_code, 500)
        self.assertEqual(resposta.json()["estado"], "ilegivel")
        self.assertIn("Nada foi criado", resposta.json()["motivo"])
        self.assertEqual(DocumentoOrdemServico.objects.count(), 0)
        self.assertEqual(self.importar("pedido.txt", pedido_em_txt())["estado"], "criada")

    def test_sem_arquivo(self):
        resposta = self.client.post(URL, {}, **JSON)
        self.assertEqual(resposta.status_code, 400)


# ======================================================================
# QUEM PODE
# ======================================================================
class PermissoesTests(_Base):
    def test_financeiro_ve_a_os_mas_nao_importa(self):
        financeiro = self.usuario("fin", ["financeiro"])
        self.client.force_login(financeiro)
        tela = self.client.get("/ordens-servico/", **HOST)
        self.assertEqual(tela.status_code, 200)
        self.assertNotContains(tela, "data-osdoc-abrir")
        self.assertNotContains(tela, 'id="osdocFolha"')
        resposta = self.enviar("os.docx", ficha_linhas())
        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(self.client.get(f"{URL}?formato=json", **HOST).status_code, 403)
        self.assertEqual(OrdemServico.objects.count(), 0)

    def test_quem_nao_e_da_os_nem_entra(self):
        vendedor = self.usuario("vend", ["vendas"])
        self.client.force_login(vendedor)
        resposta = self.enviar("os.docx", ficha_linhas())
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(OrdemServico.objects.count(), 0)

    def test_completar_e_descartar_pela_url_tambem_sao_barrados(self):
        doc = montar_docx(par("Cliente: Rodrigo Mendes") + par("Defeito: Lona rasgada."))
        pendente = self.importar("p.docx", doc)
        financeiro = self.usuario("fin2", ["financeiro"])
        self.client.force_login(financeiro)
        for acao in ("completar", "descartar"):
            with self.subTest(acao=acao):
                resposta = self.client.post(f"{URL}{pendente['documento']}/", {"action": acao}, **JSON)
                self.assertEqual(resposta.status_code, 403)
        self.assertTrue(DocumentoOrdemServico.objects.filter(pk=pendente["documento"]).exists())
        # O pendente (ainda sem O.S.) não abre para quem só vê a O.S.
        arquivo = self.client.get(f"/ordens-servico/documentos/{pendente['documento']}/arquivo/", **HOST)
        self.assertEqual(arquivo.status_code, 302)

    def test_financeiro_abre_o_documento_de_uma_os_criada(self):
        criada = self.importar("os.docx", ficha_linhas())
        financeiro = self.usuario("fin3", ["financeiro"])
        self.client.force_login(financeiro)
        arquivo = self.client.get(f"/ordens-servico/documentos/{criada['documento']}/arquivo/", **HOST)
        self.assertEqual(arquivo.status_code, 200)
        self.assertEqual(arquivo["X-Content-Type-Options"], "nosniff")

    def test_producao_e_gestao_veem_o_botao(self):
        for funcao in ("producao", "gestao"):
            with self.subTest(funcao=funcao):
                self.client.force_login(self.usuario(f"u-{funcao}", [funcao]))
                tela = self.client.get("/ordens-servico/", **HOST)
                self.assertContains(tela, "data-osdoc-abrir")
                self.assertContains(tela, "os-automatizador.js")
                self.assertContains(tela, 'id="osdocFolha"')

    def test_get_da_rota_abre_a_tela_com_a_folha(self):
        resposta = self.client.get(URL, **HOST)
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("importar=1", resposta["Location"])


# ======================================================================
# O BANCO LONGE: QUANTAS VIAGENS POR DOCUMENTO
# ======================================================================
class ConsultasPorDocumentoTests(_Base):
    """Com o banco a ~170 ms, cada consulta conta. Os tetos têm folga pequena."""

    def contar(self, nome, conteudo, *, frio=False):
        if not frio:
            # No lote, o contexto e o catálogo são pagos uma vez por minuto.
            contexto.carregar()
            contexto.catalogo()
        with CaptureQueriesContext(connection) as consultas:
            resposta = self.importar(nome, conteudo)
        return resposta, len(consultas.captured_queries)

    def test_cliente_ja_cadastrado(self):
        Cliente.objects.create(nome_cliente="Buffet Alegria", telefone="11987654321",
                               email="contato@buffetalegria.com.br", documento="22.333.444/0001-81",
                               nome_estabelecimento="Buffet Alegria")
        EnderecoCliente.objects.create(cliente=Cliente.objects.get(), endereco="Rua A", cidade="Guarulhos")
        resposta, quantas = self.contar("os.docx", ficha_linhas())
        self.assertEqual(resposta["estado"], "criada", resposta)
        # sessão, usuário e funções (3), o repetido (1), o cliente (1) e a
        # criação: O.S., itens e documento numa transação (5).
        self.assertLessEqual(quantas, 12, f"{quantas} consultas para um documento de cliente cadastrado")

    def test_o_primeiro_documento_do_lote_paga_o_contexto(self):
        Cliente.objects.create(nome_cliente="Buffet Alegria", telefone="11987654321",
                               email="contato@buffetalegria.com.br", documento="22.333.444/0001-81",
                               nome_estabelecimento="Buffet Alegria")
        EnderecoCliente.objects.create(cliente=Cliente.objects.get(), endereco="Rua A", cidade="Guarulhos")
        resposta, quantas = self.contar("os.docx", ficha_linhas(), frio=True)
        self.assertEqual(resposta["estado"], "criada", resposta)
        self.assertLessEqual(quantas, 20, f"{quantas} consultas no primeiro documento do lote")
        resposta, quantas = self.contar("os-2.docx", ficha_linhas(numero="0458", equipamento="Tobogã"), frio=True)
        self.assertLessEqual(quantas, 12, f"{quantas} consultas no segundo documento: o contexto ficou guardado")

    def test_cliente_novo_com_endereco(self):
        resposta, quantas = self.contar("os.docx", ficha_linhas())
        self.assertEqual(resposta["estado"], "criada", resposta)
        # + o nome no cadastro (1) e o cadastro novo pelas regras da aba
        # Clientes: CPF/CNPJ, nome e e-mail repetidos, o cliente e o endereço.
        self.assertLessEqual(quantas, 24, f"{quantas} consultas para um documento de cliente novo")

    def test_documento_repetido_e_barato(self):
        self.importar("os.docx", ficha_linhas())
        resposta, quantas = self.contar("os.docx", ficha_linhas())
        self.assertEqual(resposta["estado"], "repetida")
        self.assertLessEqual(quantas, 6, f"{quantas} consultas para dizer que já foi importado")
