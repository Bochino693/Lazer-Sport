"""O código do orçamento e o acompanhamento em Meus pedidos (LEIA-ME-V10, seção 104).

O pedido do dono: "quando tiver em meus pedidos, vai ter código do pedido,
para o caso do seguinte: o cliente fez o orçamento conosco pelo telefone,
aí faz o cadastro, mas como saber que aquele orçamento vai virar um pedido
do site? através do código, fazendo assim o acompanhamento e mudança de
fases pela internet sem necessidade de contato."

O que estes testes protegem:

  * o código nasce com o orçamento, no formato "LS-" + 6 sinais de um
    alfabeto sem 0/O/1/I/L, é único (o repetido é sorteado de novo) e é
    aceito do jeito que a pessoa digita;
  * a migração de dados dá um código a quem não tinha, sem repetir, e
    rodar de novo não troca nada; esquema e dados em arquivos separados;
  * vincular: o código certo liga a negociação inteira à conta e avisa a
    equipe (histórico e telefone); o inexistente e o de OUTRA conta não
    vinculam e gastam uma tentativa; o formato errado não gasta; o freio
    segura na 9ª tentativa (por conta e por IP), sem nem procurar o
    código; o código de uma versão antiga leva à mais nova; a versão nova
    nasce na mesma conta; recusado e expirado vinculam e dizem a situação;
  * Meus pedidos mostra só os orçamentos da conta, só a versão mais nova,
    rascunho sem itens nem valores, e não fica mais lento com mais
    orçamentos;
  * as fases saem dos fatos: resposta, termo, pagamento (com a %),
    produção, concluído; recusado e expirado param a corrente;
  * o link de assinatura sai na hora, pela função do painel, só para o
    dono da conta vinculada (outro usuário, anônimo, GET e CSRF ficam de
    fora);
  * o código aparece na página do cliente (e no PDF, que é ela impressa),
    na mensagem do WhatsApp, no e-mail, na prévia e na janela do painel.
"""

import re
from datetime import timedelta
from decimal import Decimal
from importlib import import_module
from types import SimpleNamespace
from unittest import mock

from django.apps import apps
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from sistema_interno import codigo_orcamento as svc
from sistema_interno import documento_assinatura as svc_doc
from sistema_interno.models import (
    ALFABETO_DO_CODIGO,
    AtividadeOrcamento,
    DocumentoAssinatura,
    ItemOrcamento,
    Orcamento,
    OrdemServico,
)

FORMATO = re.compile(r"^LS-[%s]{6}$" % ALFABETO_DO_CODIGO)
VINCULAR = "/meus-pedidos/orcamento/vincular/"
ASSINAR = "/meus-pedidos/orcamento/assinar/"


class Base(TestCase):
    def setUp(self):
        cache.clear()
        # O contrato não sai sem os dados do vendedor (LEIA-ME-V10, seção 109).
        from sistema_interno.tests_documento_assinatura import preencher_dados_do_contrato

        preencher_dados_do_contrato()
        self.cliente = self.conta("cliente-codigo")
        self.outro = self.conta("outra-conta")
        self.equipe = User.objects.create_user("equipe-codigo", password="x", is_staff=True)
        self.client.force_login(self.cliente)

    @staticmethod
    def conta(nome):
        usuario = User.objects.create_user(nome, password="senha-segura", first_name="Cliente", last_name=nome)
        perfil = usuario.perfil
        perfil.telefone = "11999990000"
        perfil.save()
        return usuario

    def orcamento(self, status=Orcamento.Status.AGUARDANDO_RESPOSTA, itens=(("Air Game Kids", 2, "4800.00"),), **campos):
        padrao = {
            "nome_cliente": "Buffet Inventado",
            "status": status,
            "validade": timezone.localdate() + timedelta(days=5),
            "enviado_em": timezone.now() - timedelta(days=1),
            "forma_pagamento": "Pix",
            "responsavel": self.equipe,
        }
        padrao.update(campos)
        orcamento = Orcamento.objects.create(**padrao)
        for descricao, quantidade, valor in itens:
            ItemOrcamento.objects.create(
                orcamento=orcamento, descricao=descricao,
                quantidade=quantidade, valor_unitario=Decimal(valor),
            )
        return orcamento

    def ligar(self, orcamento, conta=None):
        Orcamento.objects.filter(pk=orcamento.pk).update(
            conta=conta or self.cliente, vinculado_em=timezone.now(),
        )
        orcamento.refresh_from_db()
        return orcamento

    def vincular(self, codigo, cliente=None, **extra):
        return (cliente or self.client).post(VINCULAR, {"codigo": codigo}, **extra)

    @staticmethod
    def recados(resposta):
        from django.contrib.messages import get_messages

        return [str(m) for m in get_messages(resposta.wsgi_request)]


# ======================================================================
# 1. O CÓDIGO
# ======================================================================
class CodigoTests(Base):

    def test_nasce_com_o_orcamento_no_formato_que_se_dita(self):
        codigos = {self.orcamento().codigo for _ in range(30)}
        self.assertEqual(len(codigos), 30)
        for codigo in codigos:
            self.assertRegex(codigo, FORMATO)
            self.assertFalse(set(codigo[3:]) & set("0O1IL"), codigo)

    def test_codigo_repetido_e_sorteado_de_novo_na_criacao(self):
        primeiro = self.orcamento()
        segundo = Orcamento.objects.create(nome_cliente="Outro", codigo=primeiro.codigo)
        self.assertNotEqual(segundo.codigo, primeiro.codigo)
        self.assertRegex(segundo.codigo, FORMATO)

    def test_o_codigo_e_unico_no_banco(self):
        from django.db import IntegrityError, transaction

        primeiro, segundo = self.orcamento(), self.orcamento()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Orcamento.objects.filter(pk=segundo.pk).update(codigo=primeiro.codigo)

    def test_aceita_o_que_a_pessoa_digita(self):
        for digitado in ("LS-7K3QX9", " ls-7k3qx9 ", "LS 7K3 QX9", "7K3QX9", "ls7k3qx9", "LS.7K3.QX9"):
            self.assertEqual(svc.normalizar(digitado), "LS-7K3QX9", digitado)
        for invalido in ("", None, "LS-7K3QX", "LS-7K3QX99", "LS-0K3QX9", "LS-OK3QX9", "LS-1K3QX9", "LS-IK3QX9", "LS-LK3QX9"):
            self.assertEqual(svc.normalizar(invalido), "", invalido)

    def test_a_versao_nova_nasce_na_mesma_conta(self):
        v1 = self.ligar(self.orcamento(status=Orcamento.Status.RECUSADO))
        v2 = Orcamento.objects.create(nome_cliente="Buffet Inventado", orcamento_anterior=v1, versao=2)
        self.assertEqual(v2.conta, self.cliente)
        self.assertEqual(v2.vinculado_em, v1.vinculado_em)
        self.assertNotEqual(v2.codigo, v1.codigo)

    def test_refazer_no_painel_herda_a_conta(self):
        from sistema_interno.permissoes import atribuir_funcoes

        atribuir_funcoes(self.equipe, ("vendas",))
        v1 = self.ligar(self.orcamento(status=Orcamento.Status.RECUSADO))
        painel = Client()
        painel.force_login(self.equipe)
        resposta = painel.post(
            "/orcamentos/", {"action": "refazer", "id": v1.pk},
            HTTP_HOST="interno.testserver", HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resposta.status_code, 200, resposta.content[:300])
        v2 = v1.orcamento_refeito
        self.assertEqual((v2.versao, v2.conta_id), (2, self.cliente.pk))


# ======================================================================
# 2. AS MIGRAÇÕES
# ======================================================================
class MigracaoTests(Base):

    def migracao(self):
        return import_module("sistema_interno.migrations.0066_codigos_dos_orcamentos")

    def test_esquema_e_dados_em_arquivos_separados(self):
        esquema = import_module("sistema_interno.migrations.0065_orcamento_codigo_e_conta").Migration
        unico = import_module("sistema_interno.migrations.0067_orcamento_codigo_unico").Migration
        dados = self.migracao().Migration
        self.assertEqual({type(op).__name__ for op in esquema.operations}, {"AddField", "AlterField"})
        self.assertEqual([type(op).__name__ for op in dados.operations], ["RunPython"])
        self.assertEqual([type(op).__name__ for op in unico.operations], ["AlterField"])
        # o código entra nulo e sem "único"; só a 0067 o torna único
        campo = next(op.field for op in esquema.operations if getattr(op, "name", "") == "codigo")
        self.assertTrue(campo.null)
        self.assertFalse(campo.unique)
        self.assertTrue(unico.operations[0].field.unique)

    def test_preenche_quem_nao_tem_sem_repetir_e_sem_trocar_quem_tem(self):
        com_codigo = self.orcamento()
        sem_codigo = self.orcamento()
        Orcamento.objects.filter(pk=sem_codigo.pk).update(codigo="")
        antes = com_codigo.codigo
        modulo = self.migracao()
        # o primeiro sorteio repete um código que já existe: tem de sortear de novo
        with mock.patch.object(modulo, "_sortear", side_effect=[antes, "LS-NNNN22"]):
            modulo.preencher_codigos(apps, SimpleNamespace(connection=connection))
        com_codigo.refresh_from_db()
        sem_codigo.refresh_from_db()
        self.assertEqual(com_codigo.codigo, antes)
        self.assertEqual(sem_codigo.codigo, "LS-NNNN22")
        # rodar de novo não troca nada
        modulo.preencher_codigos(apps, SimpleNamespace(connection=connection))
        sem_codigo.refresh_from_db()
        self.assertEqual(sem_codigo.codigo, "LS-NNNN22")

    def test_o_alfabeto_da_migracao_e_o_do_modelo(self):
        self.assertEqual(self.migracao().ALFABETO, ALFABETO_DO_CODIGO)


# ======================================================================
# 3. VINCULAR
# ======================================================================
@mock.patch("sistema_interno.notificacoes.avisar_orcamento_vinculado")
class VincularTests(Base):

    def test_codigo_certo_vincula_e_avisa_a_equipe(self, aviso):
        orcamento = self.orcamento()
        resposta = self.vincular(orcamento.codigo.lower())
        self.assertRedirects(resposta, f"/meus-pedidos/#orc-{orcamento.codigo}", fetch_redirect_response=False)
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.conta, self.cliente)
        self.assertIsNotNone(orcamento.vinculado_em)
        self.assertIn("agora está na sua conta", " ".join(self.recados(resposta)))
        aviso.assert_called_once()
        atividade = AtividadeOrcamento.objects.get(orcamento=orcamento, tipo=AtividadeOrcamento.Tipo.VINCULADO)
        self.assertIn("@cliente-codigo", atividade.autor_nome)
        self.assertIn(orcamento.codigo, atividade.resumo)
        self.assertIsNone(atividade.autor)

    def test_o_sino_da_equipe_conta_o_vinculo(self, aviso):
        from sistema_interno.avisos import _atividades_orcamento
        from sistema_interno.permissoes import atribuir_funcoes

        atribuir_funcoes(self.equipe, ("gestao",))
        orcamento = self.orcamento()
        self.vincular(orcamento.codigo)
        avisos = _atividades_orcamento(self.equipe)
        self.assertTrue(avisos)
        self.assertIn("vinculou à conta do site o orçamento", avisos[0].detalhe)

    def test_codigo_inexistente_nao_vincula_e_gasta_tentativa(self, aviso):
        resposta = self.vincular("LS-ZZZZZZ")
        self.assertIn("Nenhum orçamento tem o código LS-ZZZZZZ", " ".join(self.recados(resposta)))
        self.assertEqual(svc.tentativas_restantes(self.cliente, "127.0.0.1"), svc.TENTATIVAS_POR_JANELA - 1)
        aviso.assert_not_called()
        # o campo volta preenchido para corrigir a letra
        self.assertContains(self.client.get("/meus-pedidos/"), 'value="LS-ZZZZZZ"')

    def test_formato_errado_nao_vai_ao_banco_nem_gasta_tentativa(self, aviso):
        resposta = self.vincular("LS-0O1IL2")
        self.assertIn("não é um código de orçamento", " ".join(self.recados(resposta)))
        self.assertEqual(svc.tentativas_restantes(self.cliente, "127.0.0.1"), svc.TENTATIVAS_POR_JANELA)

    def test_de_outra_conta_nao_muda_de_dono(self, aviso):
        orcamento = self.ligar(self.orcamento(), self.outro)
        resposta = self.vincular(orcamento.codigo)
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.conta, self.outro)
        texto = " ".join(self.recados(resposta))
        self.assertIn("já está ligado a outra conta", texto)
        self.assertIn("fale com a equipe", texto)
        self.assertNotIn("outra-conta", texto)  # nunca diz qual é a outra conta
        aviso.assert_not_called()
        self.assertEqual(svc.tentativas_restantes(self.cliente, "127.0.0.1"), svc.TENTATIVAS_POR_JANELA - 1)

    def test_ja_e_seu(self, aviso):
        orcamento = self.ligar(self.orcamento())
        resposta = self.vincular(orcamento.codigo)
        self.assertIn("já está na sua conta", " ".join(self.recados(resposta)))
        aviso.assert_not_called()

    def test_o_freio_segura_na_nona_tentativa_sem_procurar_o_codigo(self, aviso):
        certo = self.orcamento()
        for numero in range(svc.TENTATIVAS_POR_JANELA):
            self.vincular(f"LS-ZZZZ{'23456789'[numero]}Z")
        with mock.patch.object(svc, "vincular", wraps=svc.vincular) as vincular:
            resposta = self.vincular(certo.codigo)
        vincular.assert_not_called()
        certo.refresh_from_db()
        self.assertIsNone(certo.conta)
        texto = " ".join(self.recados(resposta))
        self.assertIn("Por segurança, tente de novo a partir das", texto)

    def test_o_freio_vale_por_ip_mesmo_trocando_de_conta(self, aviso):
        for numero in range(svc.TENTATIVAS_POR_JANELA):
            self.vincular(f"LS-ZZZZ{'23456789'[numero]}Z", REMOTE_ADDR="203.0.113.9")
        terceiro = self.conta("terceira-conta")
        outro_cliente = Client()
        outro_cliente.force_login(terceiro)
        certo = self.orcamento()
        resposta = self.vincular(certo.codigo, cliente=outro_cliente, REMOTE_ADDR="203.0.113.9")
        certo.refresh_from_db()
        self.assertIsNone(certo.conta)
        self.assertIn("Por segurança", " ".join(self.recados(resposta)))

    def test_codigo_da_versao_antiga_leva_a_mais_nova(self, aviso):
        v1 = self.orcamento(status=Orcamento.Status.SUBSTITUIDO)
        v2 = self.orcamento(status=Orcamento.Status.SUBSTITUIDO, orcamento_anterior=v1, versao=2)
        v3 = self.orcamento(orcamento_anterior=v2, versao=3)
        resposta = self.vincular(v1.codigo)
        self.assertRedirects(resposta, f"/meus-pedidos/#orc-{v3.codigo}", fetch_redirect_response=False)
        self.assertIn(f"vinculamos a versão 3, a que vale agora (código {v3.codigo})", " ".join(self.recados(resposta)))
        for versao in (v1, v2, v3):
            versao.refresh_from_db()
            self.assertEqual(versao.conta, self.cliente, versao.versao)
        pagina = self.client.get("/meus-pedidos/")
        self.assertContains(pagina, f'id="orc-{v3.codigo}"')
        self.assertNotContains(pagina, f'id="orc-{v1.codigo}"')

    def test_versao_de_outra_conta_na_corrente_bloqueia(self, aviso):
        v1 = self.ligar(self.orcamento(status=Orcamento.Status.SUBSTITUIDO), self.outro)
        v2 = self.orcamento(orcamento_anterior=v1, versao=2)  # herda a outra conta
        Orcamento.objects.filter(pk=v2.pk).update(conta=None)
        self.vincular(v2.codigo)
        v2.refresh_from_db()
        self.assertIsNone(v2.conta)

    def test_recusado_e_expirado_vinculam_e_dizem_a_situacao(self, aviso):
        recusado = self.orcamento(status=Orcamento.Status.RECUSADO)
        texto = " ".join(self.recados(self.vincular(recusado.codigo)))
        self.assertIn("Situação: recusado", texto)
        expirado = self.orcamento(validade=timezone.localdate() - timedelta(days=2))
        texto = " ".join(self.recados(self.vincular(expirado.codigo)))
        self.assertIn("Situação: validade encerrada", texto)
        recusado.refresh_from_db()
        self.assertEqual(recusado.conta, self.cliente)

    def test_campo_vazio_pede_o_codigo(self, aviso):
        self.assertIn("Digite o código", " ".join(self.recados(self.vincular(""))))

    def test_so_post_com_login_e_csrf(self, aviso):
        orcamento = self.orcamento()
        self.assertEqual(self.client.get(VINCULAR).status_code, 405)
        anonimo = Client()
        resposta = anonimo.post(VINCULAR, {"codigo": orcamento.codigo})
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("login", resposta["Location"])
        com_csrf = Client(enforce_csrf_checks=True)
        com_csrf.force_login(self.cliente)
        self.assertEqual(com_csrf.post(VINCULAR, {"codigo": orcamento.codigo}).status_code, 403)
        orcamento.refresh_from_db()
        self.assertIsNone(orcamento.conta)


# ======================================================================
# 4. MEUS PEDIDOS
# ======================================================================
class MeusPedidosTests(Base):

    def test_o_quadro_do_codigo_aparece_mesmo_sem_pedido(self):
        pagina = self.client.get("/meus-pedidos/")
        self.assertContains(pagina, "Tem um código de orçamento?")
        self.assertContains(pagina, f'action="{VINCULAR}"')
        self.assertContains(pagina, "csrfmiddlewaretoken")
        self.assertContains(pagina, "Você ainda não fez nenhum pedido")

    def test_o_link_da_proposta_preenche_o_campo(self):
        self.assertContains(self.client.get("/meus-pedidos/?codigo=ls-7k3qx9"), 'value="LS-7K3QX9"')
        self.assertNotContains(self.client.get("/meus-pedidos/?codigo=<script>"), "<script>alert")

    def test_mostra_so_os_da_conta(self):
        meu = self.ligar(self.orcamento(itens=(("Basquete Home", 3, "3100.00"),)))
        alheio = self.ligar(self.orcamento(nome_cliente="Escola Alheia", itens=(("Strike Kids", 1, "9500.00"),)), self.outro)
        solto = self.orcamento(itens=(("Brinquedão 5", 1, "18000.00"),))
        pagina = self.client.get("/meus-pedidos/").content.decode()
        self.assertIn(meu.codigo, pagina)
        self.assertIn("Basquete Home", pagina)
        self.assertIn("× 3", pagina)
        self.assertIn("R$ 9.300,00", pagina)
        for fora in (alheio.codigo, solto.codigo, "Strike Kids", "Escola Alheia", "Brinquedão 5"):
            self.assertNotIn(fora, pagina)
        # nem o nome do cliente do orçamento aparece no cartão
        self.assertNotIn("Buffet Inventado", pagina)

    def test_rascunho_nao_mostra_itens_nem_valores(self):
        rascunho = self.ligar(self.orcamento(status=Orcamento.Status.RASCUNHO, enviado_em=None, itens=(("Segredo da equipe", 1, "777.00"),)))
        pagina = self.client.get("/meus-pedidos/")
        self.assertContains(pagina, rascunho.codigo)
        self.assertContains(pagina, "Em preparação")
        self.assertNotContains(pagina, "Segredo da equipe")
        self.assertNotContains(pagina, "777,00")
        self.assertNotContains(pagina, rascunho.token)

    def test_o_token_da_proposta_so_aparece_para_o_dono(self):
        meu = self.ligar(self.orcamento())
        self.assertContains(self.client.get("/meus-pedidos/"), f"/orcamento/{meu.token}/")
        outro = Client()
        outro.force_login(self.outro)
        self.assertNotContains(outro.get("/meus-pedidos/"), meu.token)

    def test_as_consultas_nao_crescem_com_os_orcamentos(self):
        def contar():
            with CaptureQueriesContext(connection) as capturadas:
                self.assertEqual(self.client.get("/meus-pedidos/").status_code, 200)
            return len(capturadas)

        primeiro = self.ligar(self.orcamento(status=Orcamento.Status.APROVADO, respondido_em=timezone.now()))
        svc_doc.gerar(primeiro, self.equipe)
        contar()
        poucos = contar()
        for _ in range(4):
            outro = self.ligar(self.orcamento(status=Orcamento.Status.APROVADO, respondido_em=timezone.now(), itens=(("A", 1, "10"), ("B", 2, "20"))))
            svc_doc.gerar(outro, self.equipe)
        self.ligar(self.orcamento())
        muitos = contar()
        self.assertEqual(muitos, poucos, "Meus pedidos consulta o banco uma vez por orçamento")

    def test_icones_das_fases_estao_no_recorte_do_site(self):
        from pathlib import Path

        from core.views_codigo_orcamento import ICONES_DAS_FASES

        icones = set((Path(__file__).resolve().parent / "static/vendor/fontawesome-site/icones.txt").read_text().split())
        self.assertLessEqual(set(ICONES_DAS_FASES.values()), icones)
        fases = {fase.chave for fase in svc.acompanhamento(self.orcamento()).fases}
        self.assertEqual(fases, set(ICONES_DAS_FASES))


# ======================================================================
# 5. AS FASES
# ======================================================================
class FasesTests(Base):

    def estados(self, orcamento):
        cartao = svc.acompanhamento(Orcamento.objects.get(pk=orcamento.pk))
        return cartao, {fase.chave: fase.estado for fase in cartao.fases}, {fase.chave: fase.nota for fase in cartao.fases}

    def aprovado(self, **campos):
        return self.orcamento(status=Orcamento.Status.APROVADO, respondido_em=timezone.now() - timedelta(days=2), **campos)

    def assinar(self, orcamento):
        documento = svc_doc.gerar(orcamento, self.equipe)
        DocumentoAssinatura.objects.filter(pk=documento.pk).update(
            situacao=DocumentoAssinatura.Situacao.ASSINADO, assinado_em=timezone.now(),
        )
        return documento

    def test_esperando_a_resposta(self):
        cartao, estados, notas = self.estados(self.orcamento())
        self.assertEqual(estados["proposta"], "feita")
        self.assertEqual(estados["aprovacao"], "atual")
        self.assertEqual(estados["termo"], "futura")
        self.assertIn("Esperando sua resposta", notas["aprovacao"])
        self.assertEqual(cartao.situacao, "resposta")
        self.assertTrue(cartao.pode_responder)
        self.assertFalse(cartao.pode_assinar)

    def test_rascunho_e_a_proposta_sendo_montada(self):
        cartao, estados, _ = self.estados(self.orcamento(status=Orcamento.Status.RASCUNHO))
        self.assertEqual(estados["proposta"], "atual")
        self.assertEqual(cartao.situacao, "preparando")
        self.assertEqual(cartao.itens, [])

    def test_aprovado_sem_termo_espera_a_equipe(self):
        cartao, estados, notas = self.estados(self.aprovado())
        self.assertEqual(estados["aprovacao"], "feita")
        self.assertEqual(estados["termo"], "atual")
        self.assertEqual(notas["termo"], "A equipe está preparando o termo")
        self.assertFalse(cartao.pode_assinar)
        self.assertTrue(cartao.mostra_pix)

    def test_aprovado_com_termo_pede_a_assinatura(self):
        orcamento = self.aprovado()
        svc_doc.gerar(orcamento, self.equipe)
        cartao, estados, notas = self.estados(orcamento)
        self.assertEqual(estados["termo"], "atual")
        self.assertEqual(notas["termo"], "Pronto para você assinar")
        self.assertTrue(cartao.pode_assinar)
        self.assertEqual(cartao.situacao, "assinar")

    def test_assinado_e_pagamento_parcial_com_a_porcentagem(self):
        orcamento = self.aprovado(prazo_producao_dias=15)
        self.assinar(orcamento)
        orcamento.registrar_pagamento(orcamento.total * Decimal("0.4"))
        cartao, estados, notas = self.estados(orcamento)
        self.assertEqual(estados["termo"], "feita")
        self.assertEqual(estados["pagamento"], "atual")
        self.assertEqual(notas["pagamento"], "Parcial · 40% pago")
        self.assertEqual(cartao.percentual_pago, 40)
        self.assertIn("Começou em", notas["producao"])
        self.assertIn("previsão", notas["producao"])
        self.assertIsNotNone(cartao.termo_assinado)

    def test_pago_esta_em_producao(self):
        orcamento = self.aprovado(prazo_producao_dias=10)
        self.assinar(orcamento)
        orcamento.registrar_pagamento(orcamento.total)
        cartao, estados, _ = self.estados(orcamento)
        self.assertEqual(estados["pagamento"], "feita")
        self.assertEqual(estados["producao"], "atual")
        self.assertEqual(cartao.situacao, "producao")
        self.assertFalse(cartao.mostra_pix)

    def test_os_concluida_fecha_a_corrente(self):
        orcamento = self.aprovado()
        self.assinar(orcamento)
        orcamento.registrar_pagamento(orcamento.total)
        OrdemServico.objects.create(
            orcamento=orcamento, equipamento="Air Game Kids",
            status=OrdemServico.Status.CONCLUIDA, concluida_em=timezone.now(),
        )
        cartao, estados, _ = self.estados(orcamento)
        self.assertEqual(set(estados.values()), {"feita"})
        self.assertEqual(cartao.situacao, "concluido")

    def test_recusado_e_expirado_param_a_corrente(self):
        for orcamento, situacao in (
            (self.orcamento(status=Orcamento.Status.RECUSADO, respondido_em=timezone.now()), "recusado"),
            (self.orcamento(validade=timezone.localdate() - timedelta(days=1)), "expirado"),
            (self.orcamento(status=Orcamento.Status.EXPIRADO), "expirado"),
        ):
            cartao, estados, _ = self.estados(orcamento)
            self.assertEqual(estados["aprovacao"], "parada", situacao)
            self.assertNotIn("atual", estados.values(), situacao)
            self.assertEqual(cartao.situacao, situacao)
            self.assertFalse(cartao.pode_responder)

    def test_o_cartao_desenha_as_fases(self):
        orcamento = self.ligar(self.aprovado())
        svc_doc.gerar(orcamento, self.equipe)
        pagina = self.client.get("/meus-pedidos/").content.decode()
        self.assertIn('class="oc-fase is-feita"', pagina)
        self.assertIn('class="oc-fase is-atual" aria-current="step"', pagina)
        self.assertIn("Assinar o contrato", pagina)
        self.assertIn("Pagamento por Pix", pagina)
        self.assertIn("fa-signature", pagina)


# ======================================================================
# 6. ASSINAR O TERMO
# ======================================================================
class AssinarTests(Base):

    def setUp(self):
        super().setUp()
        self.orcamento_aprovado = self.ligar(self.orcamento(status=Orcamento.Status.APROVADO, respondido_em=timezone.now()))
        self.documento = svc_doc.gerar(self.orcamento_aprovado, self.equipe)

    def test_o_dono_ganha_um_link_novo_e_vai_assinar(self):
        resposta = self.client.post(ASSINAR, {"codigo": self.orcamento_aprovado.codigo})
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(resposta["Location"].startswith("/assinar/"))
        token = resposta["Location"].split("/")[2]
        leitura = svc_doc.ler_link(token)
        self.assertEqual(leitura.situacao, "valido")
        self.assertEqual(leitura.documento.pk, self.documento.pk)
        self.documento.refresh_from_db()
        self.assertEqual(self.documento.links_gerados, 1)
        self.assertEqual(self.client.get(resposta["Location"]).status_code, 200)

    def test_outra_conta_nao_ganha_link(self):
        outro = Client()
        outro.force_login(self.outro)
        resposta = outro.post(ASSINAR, {"codigo": self.orcamento_aprovado.codigo})
        self.assertFalse(resposta["Location"].startswith("/assinar/"))
        self.assertIn("não está na sua conta", " ".join(self.recados(resposta)))
        self.documento.refresh_from_db()
        self.assertEqual(self.documento.links_gerados, 0)

    def test_anonimo_get_e_csrf_ficam_de_fora(self):
        anonimo = Client()
        resposta = anonimo.post(ASSINAR, {"codigo": self.orcamento_aprovado.codigo})
        self.assertIn("login", resposta["Location"])
        self.assertEqual(self.client.get(ASSINAR).status_code, 405)
        com_csrf = Client(enforce_csrf_checks=True)
        com_csrf.force_login(self.cliente)
        self.assertEqual(com_csrf.post(ASSINAR, {"codigo": self.orcamento_aprovado.codigo}).status_code, 403)
        self.documento.refresh_from_db()
        self.assertEqual(self.documento.links_gerados, 0)

    def test_sem_termo_assinado_ou_suspenso_nao_gera_link(self):
        sem_termo = self.ligar(self.orcamento(status=Orcamento.Status.APROVADO, respondido_em=timezone.now()))
        resposta = self.client.post(ASSINAR, {"codigo": sem_termo.codigo})
        self.assertIn("ainda não está pronto", " ".join(self.recados(resposta)))

        DocumentoAssinatura.objects.filter(pk=self.documento.pk).update(situacao=DocumentoAssinatura.Situacao.ASSINADO, assinado_em=timezone.now())
        resposta = self.client.post(ASSINAR, {"codigo": self.orcamento_aprovado.codigo})
        self.assertIn("já está assinado", " ".join(self.recados(resposta)))

        outro = self.ligar(self.orcamento(status=Orcamento.Status.APROVADO, respondido_em=timezone.now()))
        documento = svc_doc.gerar(outro, self.equipe)
        outro.registrar_recusa("mudou de ideia")
        resposta = self.client.post(ASSINAR, {"codigo": outro.codigo})
        self.assertFalse(resposta["Location"].startswith("/assinar/"))
        documento.refresh_from_db()
        self.assertEqual(documento.links_gerados, 0)

    def test_termo_assinado_tem_a_copia_no_cartao(self):
        DocumentoAssinatura.objects.filter(pk=self.documento.pk).update(situacao=DocumentoAssinatura.Situacao.ASSINADO, assinado_em=timezone.now())
        self.assertContains(self.client.get("/meus-pedidos/"), f"/assinado/{self.documento.codigo_publico}/")


# ======================================================================
# 7. ONDE O CÓDIGO APARECE
# ======================================================================
class OndeApareceTests(Base):

    def test_pagina_do_cliente_e_pdf(self):
        orcamento = self.orcamento()
        pagina = self.client.get(f"/orcamento/{orcamento.token}/")
        self.assertContains(pagina, orcamento.codigo)
        self.assertContains(pagina, "e informe este código em")
        self.assertContains(pagina, "para acompanhar tudo pela internet")
        # vinculado: a página aberta por link não diz a qual conta
        self.ligar(orcamento)
        pagina = Client().get(f"/orcamento/{orcamento.token}/")
        self.assertContains(pagina, "já está ligado a uma conta do site")
        self.assertNotContains(pagina, "cliente-codigo")

    def test_mensagem_do_whatsapp(self):
        from sistema_interno.views_gestao import OrcamentosInnerView

        orcamento = self.orcamento()
        mensagem = OrcamentosInnerView.mensagem_da_proposta(orcamento, "https://exemplo/orcamento/x/")
        self.assertIn(f"Código do orçamento: *{orcamento.codigo}*", mensagem)
        self.assertIn("informe este código em *Meus pedidos* para acompanhar tudo pela internet", mensagem)
        self.assertNotIn("_", orcamento.codigo)

    def test_email_da_proposta(self):
        from django.template.loader import render_to_string

        orcamento = self.orcamento()
        html = render_to_string("emails/orcamento_enviado.html", {
            "orcamento": orcamento, "itens": orcamento.itens.all(), "link": "https://exemplo/",
            "total_formatado": "9.600,00", "dados_bancarios": {},
        })
        self.assertIn(orcamento.codigo, html)
        self.assertIn("informe este código em <strong>Meus pedidos</strong>", html)

    def test_painel_previa_janela_e_busca(self):
        from sistema_interno.permissoes import atribuir_funcoes
        from sistema_interno.views_gestao import OrcamentosInnerView

        atribuir_funcoes(self.equipe, ("gestao",))
        orcamento = self.ligar(self.orcamento())
        dados = OrcamentosInnerView.serializar(orcamento)
        self.assertEqual(dados["codigo"], orcamento.codigo)
        self.assertEqual(dados["conta"], "@cliente-codigo")
        self.assertTrue(dados["vinculado_em"])

        painel = Client()
        painel.force_login(self.equipe)
        previa = painel.get(f"/orcamentos/{orcamento.pk}/previa/", HTTP_HOST="interno.testserver")
        self.assertContains(previa, f"vinculado à conta @cliente-codigo")
        busca = painel.get(f"/orcamentos/?q={orcamento.codigo}", HTTP_HOST="interno.testserver")
        self.assertEqual(busca.status_code, 200)
        self.assertIn(orcamento.pk, [o["id"] for o in busca.context["orcamentos_dados"]])


# ======================================================================
# 8. A EQUIPE DESFAZ OU TROCA A CONTA
# ======================================================================
class ComandoTests(Base):

    def test_desvincula_e_passa_para_outra_conta_a_corrente_inteira(self):
        from io import StringIO

        from django.core.management import call_command

        v1 = self.ligar(self.orcamento(status=Orcamento.Status.SUBSTITUIDO))
        v2 = self.orcamento(orcamento_anterior=v1, versao=2)
        saida = StringIO()
        call_command("conta_do_orcamento", v1.codigo.lower(), "--desvincular", stdout=saida)
        self.assertIn("@cliente-codigo", saida.getvalue())
        for versao in (v1, v2):
            versao.refresh_from_db()
            self.assertIsNone(versao.conta)
        call_command("conta_do_orcamento", v2.codigo, "--para", "outra-conta", stdout=StringIO())
        for versao in (v1, v2):
            versao.refresh_from_db()
            self.assertEqual(versao.conta, self.outro)
