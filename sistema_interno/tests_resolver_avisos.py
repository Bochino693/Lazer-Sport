"""A folha que resolve o aviso ali mesmo (LEIA-ME-V10, seção 116).

"Melhore as notificações, deixe modais para solucionar problemas
pequenos." O sino dizia o que estava errado e mandava a pessoa para outra
tela procurar onde consertar. Agora o aviso abre uma folha com a lista do
que falta e as ações que já existem nas telas.

O que estes testes seguram, nesta ordem:

  1. a folha MOSTRA o que o número contou -- a mesma lista, do mesmo
     tamanho, e em cada linha só o que falta;
  2. o que se SALVA pela folha faz o número cair na hora (o cliente
     completo sai, a proposta com contrato sai, a recusada sai);
  3. a PERMISSÃO: quem não recebe o aviso não abre a folha, e cada ação
     de dentro só aparece para a função que a tela de origem deixaria.
"""

import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import Pedido

from . import avisos as mod
from .context_processors import _apurar
from .models import (
    Cliente,
    EnderecoCliente,
    EstoqueMaterial,
    ItemOrcamento,
    Material,
    Orcamento,
)
from .permissoes import atribuir_funcoes

AJAX = {"HTTP_HOST": "interno.testserver", "HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
CPF_VALIDO = "529.982.247-25"
CPF_INVALIDO = "529.982.247-24"
RAIZ = Path(__file__).resolve().parent


def usuario(nome, *funcoes):
    pessoa = User.objects.create_user(username=nome, password="x", email=f"{nome}@example.com")
    atribuir_funcoes(pessoa, funcoes)
    return pessoa


def quantidade_do_aviso(user, chave):
    for aviso in mod.coletar(user):
        if aviso.chave == chave:
            return aviso.quantidade
    return 0


class Base(TestCase):

    def setUp(self):
        cache.clear()
        self.gestor = User.objects.create_superuser("gestor-folha", "g@example.com", "x")
        self.client.force_login(self.gestor)

    def folha(self, chave, quem=None):
        if quem is not None:
            self.client.force_login(quem)
        return self.client.get(f"/avisos/resolver/{chave}/", **AJAX)

    def proposta(self, nome="Buffet Alegria", itens=1, **campos):
        padrao = {
            "nome_cliente": nome,
            "whatsapp_cliente": "(11) 97777-6655",
            "email_cliente": "cliente@example.com",
            "status": Orcamento.Status.AGUARDANDO_RESPOSTA,
            "validade": timezone.localdate() + timedelta(days=10),
            "responsavel": self.gestor,
        }
        padrao.update(campos)
        orcamento = Orcamento.objects.create(**padrao)
        for numero in range(itens):
            ItemOrcamento.objects.create(
                orcamento=orcamento, descricao=f"Cama elástica {numero + 1}",
                quantidade=1, valor_unitario=Decimal("480.00"),
            )
        return orcamento


# ======================================================================
# O AVISO EM SI: diz o que fazer, o número certo e a ação
# ======================================================================
class AvisoMaisClaroTests(Base):

    def test_incompletos_dizem_quanto_falta_de_cada_coisa(self):
        Cliente.objects.create(nome_cliente="Sem nada")
        Cliente.objects.create(
            nome_cliente="Sem CPF", telefone="(11) 97777-6655",
        )
        com_endereco = Cliente.objects.create(
            nome_cliente="Só sem CPF", email="a@example.com",
        )
        EnderecoCliente.objects.create(cliente=com_endereco, endereco="Rua A", cidade="Campinas")

        aviso = next(a for a in mod.coletar(self.gestor) if a.chave == "clientes_incompletos")

        self.assertEqual(aviso.quantidade, 3)
        self.assertIn("CPF/CNPJ válido em 3", aviso.detalhe)
        self.assertIn("endereço em 2", aviso.detalhe)
        self.assertIn("contato em 1", aviso.detalhe)
        self.assertEqual(aviso.acao, "Completar")
        self.assertTrue(aviso.resolvivel)

    def test_arquivado_nao_conta_no_aviso_nem_na_tela(self):
        """O sino dizia 19 e a lista abria com os arquivados junto."""
        Cliente.objects.create(nome_cliente="Ativo incompleto")
        Cliente.objects.create(nome_cliente="Arquivado incompleto", ativo=False)

        self.assertEqual(quantidade_do_aviso(self.gestor, "clientes_incompletos"), 1)
        html = self.client.get("/clientes/?incompletos=1", HTTP_HOST="interno.testserver").content.decode()
        self.assertIn("Ativo incompleto", html)
        self.assertNotIn("Arquivado incompleto", html)

    def test_em_aberto_conta_cada_situacao(self):
        self.proposta("Rascunho", status=Orcamento.Status.RASCUNHO)
        self.proposta("Esperando 1")
        self.proposta("Esperando 2")

        aviso = next(a for a in mod.coletar(self.gestor) if a.chave == "orcamentos_em_aberto")

        self.assertEqual(aviso.quantidade, 3)
        self.assertIn("1 rascunho por enviar e 2 esperando o cliente", aviso.detalhe)
        self.assertEqual(aviso.acao, "Acompanhar")

    def test_o_estado_ao_vivo_leva_a_acao_e_a_folha(self):
        Cliente.objects.create(nome_cliente="Sem nada")
        self.proposta("Esperando")

        corpo = self.client.get("/avisos/estado/", **AJAX).json()
        por_chave = {a["chave"]: a for a in corpo["avisos"]}

        self.assertEqual(por_chave["clientes_incompletos"]["acao"], "Completar")
        self.assertTrue(por_chave["clientes_incompletos"]["resolver"])
        self.assertTrue(por_chave["orcamentos_em_aberto"]["resolver"])

    def test_aviso_sem_conserto_pequeno_continua_levando_a_tela(self):
        Pedido.objects.create(status="pago")
        avisos = {a.chave: a for a in mod.coletar(self.gestor)}
        self.assertTrue(avisos["pedidos"].resolvivel)
        for chave in ("vendas", "manutencoes", "ordens_servico", "producao", "orcamentos_atividade"):
            self.assertNotIn(chave, mod.RESOLVIVEIS)
        self.assertEqual(self.folha("vendas").status_code, 404)

    def test_quem_nao_recebe_o_aviso_nao_tem_folha_dele(self):
        """A capacidade que abre a folha é a mesma que dá o aviso."""
        for chave, capacidade in mod.RESOLVIVEIS.items():
            with self.subTest(chave=chave):
                self.assertIn(capacidade, (
                    "clientes", "orcamentos", "pedidos", "estoque",
                ))


# ======================================================================
# CADASTROS INCOMPLETOS
# ======================================================================
class FolhaDeClientesTests(Base):

    def test_mostra_so_o_que_falta_de_cada_um(self):
        sem_nada = Cliente.objects.create(nome_cliente="Sem nada")
        so_cpf = Cliente.objects.create(nome_cliente="Só o CPF", telefone="(11) 97777-6655")
        EnderecoCliente.objects.create(cliente=so_cpf, endereco="Rua A", cidade="Campinas")
        completo = Cliente.objects.create(
            nome_cliente="Completo", telefone="(11) 97777-1111", documento=CPF_VALIDO,
        )
        EnderecoCliente.objects.create(cliente=completo, endereco="Rua B", cidade="Campinas")

        corpo = self.folha("clientes_incompletos").json()

        self.assertEqual(corpo["tipo"], "clientes")
        self.assertEqual(corpo["quantidade"], 2)
        self.assertEqual(corpo["quantidade"], quantidade_do_aviso(self.gestor, "clientes_incompletos"))
        por_id = {item["id"]: item for item in corpo["itens"]}
        self.assertNotIn(completo.pk, por_id)
        self.assertEqual(por_id[sem_nada.pk]["faltas"], ["contato", "documento", "endereco"])
        self.assertEqual(por_id[so_cpf.pk]["faltas"], ["documento"])
        self.assertIn("/clientes/?incompletos=1", corpo["tela"]["url"])
        self.assertEqual(corpo["urls"]["salvar"], "/clientes/")
        self.assertEqual(corpo["urls"]["cep"], "/clientes/consultar-cep/")

    def test_a_regra_da_linha_e_a_regra_do_numero(self):
        """`faltas_do_cliente` (a folha) e `filtro_incompletos` (o sino) concordam."""
        from .completude_clientes import faltas_do_cliente, filtro_incompletos

        casos = [
            Cliente.objects.create(nome_cliente="Nada"),
            Cliente.objects.create(nome_cliente="Só e-mail", email="a@example.com"),
            Cliente.objects.create(nome_cliente="CPF errado", telefone="(11) 97777-6655", documento=CPF_INVALIDO),
            Cliente.objects.create(
                nome_cliente="WhatsApp não confirmado", telefone="(11) 97777-1111",
                documento=CPF_VALIDO, canal_telefone=Cliente.CanalTelefone.NAO_CONFIRMADO,
            ),
        ]
        EnderecoCliente.objects.create(cliente=casos[3], endereco="Rua C", cidade="Campinas")

        for cliente in casos:
            with self.subTest(cliente=cliente.nome_cliente):
                cliente = Cliente.objects.get(pk=cliente.pk)
                no_numero = Cliente.objects.filter(pk=cliente.pk).filter(filtro_incompletos()).exists()
                self.assertEqual(bool(faltas_do_cliente(cliente)), no_numero)
        # O WhatsApp não confirmado é lembrete da tela, não deixa incompleto.
        self.assertEqual(faltas_do_cliente(Cliente.objects.get(pk=casos[3].pk)), [])

    def test_o_cpf_so_viaja_quando_e_ele_que_esta_errado(self):
        errado = Cliente.objects.create(
            nome_cliente="CPF errado", telefone="(11) 97777-6655", documento=CPF_INVALIDO,
        )
        certo = Cliente.objects.create(
            nome_cliente="CPF certo, sem endereço", telefone="(11) 97777-1111", documento=CPF_VALIDO,
        )

        corpo = self.folha("clientes_incompletos").json()
        por_id = {item["id"]: item for item in corpo["itens"]}

        self.assertEqual(por_id[errado.pk]["documento"], CPF_INVALIDO)
        self.assertTrue(por_id[errado.pk]["documento_invalido"])
        self.assertEqual(por_id[certo.pk]["documento"], "")
        self.assertEqual(por_id[certo.pk]["faltas"], ["endereco"])
        # Nem telefone nem e-mail: quem está na lista é quem não os tem.
        texto = json.dumps(corpo)
        self.assertNotIn("97777", texto)
        self.assertNotIn(CPF_VALIDO, texto)

    def test_quem_tem_proposta_viva_vem_primeiro(self):
        Cliente.objects.create(nome_cliente="Antônio sem proposta")
        com_proposta = Cliente.objects.create(nome_cliente="Zeca com proposta")
        self.proposta("Zeca com proposta", cliente=com_proposta)

        itens = self.folha("clientes_incompletos").json()["itens"]

        self.assertEqual(itens[0]["id"], com_proposta.pk)
        self.assertTrue(itens[0]["com_proposta"])

    def test_salvar_um_tira_ele_do_numero_na_hora(self):
        cliente = Cliente.objects.create(nome_cliente="Joana Ribeiro")
        Cliente.objects.create(nome_cliente="Outro incompleto")
        self.assertEqual(_apurar(self.gestor)["count_clientes_incompletos"], 2)

        resposta = self.client.post("/clientes/", {
            "action": "completar", "id": cliente.pk,
            "telefone": "(11) 97777-6655", "canal_telefone": "whatsapp",
            "documento": CPF_VALIDO,
            "cep": "01001-000", "endereco": "Praça da Sé", "numero": "1",
            "bairro": "Sé", "cidade": "São Paulo", "estado": "SP",
        }, **AJAX)

        self.assertEqual(resposta.status_code, 200, resposta.content)
        corpo = resposta.json()
        self.assertEqual(corpo["faltas"], [])
        self.assertFalse(corpo["incompleto"])
        cache.clear()
        self.assertEqual(_apurar(self.gestor)["count_clientes_incompletos"], 1)
        ids = [item["id"] for item in self.folha("clientes_incompletos").json()["itens"]]
        self.assertNotIn(cliente.pk, ids)

    def test_salvar_parte_diz_o_que_ainda_segura_o_cliente(self):
        cliente = Cliente.objects.create(nome_cliente="Joana Ribeiro")

        corpo = self.client.post("/clientes/", {
            "action": "completar", "id": cliente.pk,
            "telefone": "(11) 97777-6655", "canal_telefone": "whatsapp",
        }, **AJAX).json()

        self.assertEqual(corpo["faltas"], ["documento", "endereco"])
        self.assertTrue(corpo["incompleto"])

    def test_cpf_com_digito_errado_e_recusado(self):
        cliente = Cliente.objects.create(nome_cliente="Joana Ribeiro", telefone="(11) 97777-6655")

        resposta = self.client.post("/clientes/", {
            "action": "completar", "id": cliente.pk, "documento": CPF_INVALIDO,
        }, **AJAX)

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("dígitos verificadores", resposta.json()["msg"])
        cliente.refresh_from_db()
        self.assertEqual(cliente.documento, "")

    def test_producao_e_financeiro_nao_abrem_a_folha_de_clientes(self):
        for funcao in ("producao", "financeiro", "criacao"):
            with self.subTest(funcao=funcao):
                quem = usuario(f"sem-clientes-{funcao}", funcao)
                self.assertEqual(self.folha("clientes_incompletos", quem).status_code, 403)

    def test_vendas_e_ambulante_abrem(self):
        Cliente.objects.create(nome_cliente="Sem nada")
        for funcao in ("vendas", "ambulante"):
            with self.subTest(funcao=funcao):
                quem = usuario(f"com-clientes-{funcao}", funcao)
                resposta = self.folha("clientes_incompletos", quem)
                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(resposta.json()["quantidade"], 1)

    def test_quem_nao_e_da_equipe_nao_le_nada(self):
        visitante = User.objects.create_user("visitante", password="x")
        self.client.force_login(visitante)
        resposta = self.client.get("/avisos/resolver/clientes_incompletos/", **AJAX)
        self.assertEqual(resposta.status_code, 302)

    def test_a_lista_tem_teto_e_diz_o_total(self):
        from .resolver_avisos import LIMITE

        for numero in range(LIMITE + 4):
            Cliente.objects.create(nome_cliente=f"Incompleto {numero:02d}")

        corpo = self.folha("clientes_incompletos").json()

        self.assertEqual(corpo["quantidade"], LIMITE + 4)
        self.assertEqual(corpo["mostrando"], LIMITE)

    def test_a_resposta_nao_fica_guardada(self):
        resposta = self.folha("clientes_incompletos")
        self.assertIn("no-store", resposta["Cache-Control"])


# ======================================================================
# PROPOSTAS EM ABERTO, A VENCER, VENCIDAS, RECUSADAS
# ======================================================================
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class FolhaDePropostasTests(Base):

    def test_lista_uma_linha_por_negociacao(self):
        primeira = self.proposta("Versão 1", status=Orcamento.Status.SUBSTITUIDO)
        refeita = self.proposta("Versão 2", orcamento_anterior=primeira, versao=2)
        self.proposta("Outra")

        corpo = self.folha("orcamentos_em_aberto").json()

        self.assertEqual(corpo["tipo"], "propostas")
        self.assertEqual(corpo["quantidade"], 2)
        self.assertEqual(corpo["quantidade"], quantidade_do_aviso(self.gestor, "orcamentos_em_aberto"))
        ids = [item["id"] for item in corpo["itens"]]
        self.assertIn(refeita.pk, ids)
        self.assertNotIn(primeira.pk, ids)

    def test_cada_linha_traz_as_acoes_que_a_lista_tem(self):
        esperando = self.proposta("Esperando")
        rascunho = self.proposta("Rascunho", status=Orcamento.Status.RASCUNHO)
        sem_whats = self.proposta("Sem WhatsApp", whatsapp_cliente="")

        itens = {i["id"]: i for i in self.folha("orcamentos_em_aberto").json()["itens"]}

        self.assertTrue(itens[esperando.pk]["acoes"]["whatsapp"])
        self.assertEqual(itens[esperando.pk]["acoes"]["whatsapp_rotulo"], "Reenviar no WhatsApp")
        self.assertTrue(itens[esperando.pk]["acoes"]["email"])
        self.assertTrue(itens[esperando.pk]["acoes"]["recusar"])
        self.assertFalse(itens[esperando.pk]["acoes"]["expirar"])
        self.assertEqual(itens[rascunho.pk]["acoes"]["whatsapp_rotulo"], "Enviar no WhatsApp")
        self.assertFalse(itens[rascunho.pk]["acoes"]["email"])
        self.assertFalse(itens[sem_whats.pk]["acoes"]["whatsapp"])
        self.assertTrue(itens[sem_whats.pk]["acoes"]["sem_whatsapp"])
        self.assertEqual(itens[esperando.pk]["abrir"], f"/orcamentos/?q={esperando.pk}")

    def test_vencida_nao_reenvia_e_pode_ser_expirada(self):
        vencida = self.proposta("Vencida", validade=timezone.localdate() - timedelta(days=2))

        corpo = self.folha("orcamentos_vencidos").json()
        item = corpo["itens"][0]

        self.assertEqual(item["id"], vencida.pk)
        self.assertFalse(item["acoes"]["whatsapp"])
        self.assertTrue(item["acoes"]["expirar"])
        self.assertEqual(item["validade_texto"], "Venceu há 2 dias")

    def test_a_vencer_e_so_o_que_vence_em_tres_dias(self):
        perto = self.proposta("Perto", validade=timezone.localdate() + timedelta(days=1))
        self.proposta("Longe", validade=timezone.localdate() + timedelta(days=20))

        corpo = self.folha("orcamentos_vencendo").json()

        self.assertEqual([i["id"] for i in corpo["itens"]], [perto.pk])
        self.assertEqual(corpo["itens"][0]["validade_texto"], "Vence em 1 dia")

    def test_registrar_a_recusa_pela_folha_tira_do_numero(self):
        orcamento = self.proposta("Vai recusar")
        self.assertEqual(quantidade_do_aviso(self.gestor, "orcamentos_em_aberto"), 1)

        resposta = self.client.post("/orcamentos/", {
            "action": "status", "id": orcamento.pk, "status": "recusado",
            "motivo": "Preço: comprou de outro",
        }, **AJAX)

        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertEqual(quantidade_do_aviso(self.gestor, "orcamentos_em_aberto"), 0)

    def test_aprovacao_manual_num_toque(self):
        """"Também deve deixar fácil a aprovação manual" (seção 121): o
        "Cliente aprovou" ao lado da recusa, com quem registrou e quando, e
        o caminho do contrato logo em seguida."""
        orcamento = self.proposta("Aprovou por telefone")
        sem_itens = self.proposta("Sem itens", itens=0)
        itens = {i["id"]: i for i in self.folha("orcamentos_em_aberto").json()["itens"]}
        self.assertTrue(itens[orcamento.pk]["acoes"]["aprovar"])
        self.assertFalse(itens[sem_itens.pk]["acoes"]["aprovar"])
        self.assertEqual(itens[orcamento.pk]["contrato_url"], f"/orcamentos/{orcamento.pk}/documento/")

        resposta = self.client.post("/orcamentos/", {
            "action": "status", "id": orcamento.pk, "status": "aprovado",
            "motivo": "Aprovada pelo cliente (registrada pela equipe).",
        }, **AJAX)

        self.assertEqual(resposta.status_code, 200, resposta.content)
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, Orcamento.Status.APROVADO)
        self.assertIn("informado pela equipe", orcamento.respondido_por)
        self.assertIsNotNone(orcamento.respondido_em)
        ids = [i["id"] for i in self.folha("orcamentos_em_aberto").json()["itens"]]
        self.assertNotIn(orcamento.pk, ids)

    def test_recusada_mostra_o_motivo_do_cliente(self):
        orcamento = self.proposta("Recusou")
        orcamento.registrar_recusa(motivo="Achou caro", por="Maria")

        corpo = self.folha("orcamentos_recusados").json()

        self.assertEqual(corpo["itens"][0]["id"], orcamento.pk)
        self.assertEqual(corpo["itens"][0]["motivo"], "Achou caro")
        self.assertIn("Recusada por Maria", corpo["itens"][0]["resposta"])

    def test_o_ambulante_ve_so_a_carteira_dele(self):
        ambulante = usuario("ambulante-folha", "ambulante")
        minha = self.proposta("Minha", responsavel=ambulante)
        self.proposta("Do colega")

        corpo = self.folha("orcamentos_em_aberto", ambulante).json()

        self.assertEqual([i["id"] for i in corpo["itens"]], [minha.pk])
        self.assertEqual(corpo["quantidade"], 1)

    def test_o_financeiro_ve_a_lista_sem_as_acoes_do_comercial(self):
        """Ele recebe o aviso pelo bloco de preço; falar com o cliente não é dele."""
        financeiro = usuario("financeiro-folha", "financeiro")
        self.proposta("Esperando")

        item = self.folha("orcamentos_em_aberto", financeiro).json()["itens"][0]

        self.assertFalse(any(
            valor for chave, valor in item["acoes"].items() if chave != "whatsapp_rotulo"
        ))

    def test_o_financeiro_nao_manda_lembrete_por_fora_da_folha(self):
        financeiro = usuario("financeiro-lembrete", "financeiro")
        orcamento = self.proposta("Esperando", validade=timezone.localdate() + timedelta(days=1))
        self.client.force_login(financeiro)

        resposta = self.client.post(f"/orcamentos/{orcamento.pk}/lembrar/", **AJAX)

        self.assertEqual(resposta.status_code, 403)
        self.assertFalse(orcamento.envios.exists())

    def test_producao_nao_abre_folha_de_proposta(self):
        producao = usuario("producao-folha", "producao")
        for chave in ("orcamentos_em_aberto", "orcamentos_aprovados", "orcamentos_vencidos"):
            with self.subTest(chave=chave):
                self.assertEqual(self.folha(chave, producao).status_code, 403)

    def test_reenviar_pelo_whatsapp_e_o_envio_de_sempre(self):
        orcamento = self.proposta("Esperando")

        resposta = self.client.post("/orcamentos/", {
            "action": "enviar", "id": orcamento.pk, "canal": "whatsapp",
        }, **AJAX)

        self.assertEqual(resposta.status_code, 200, resposta.content)
        corpo = resposta.json()
        self.assertIn("wa.me/5511977776655", corpo["whatsapp_url"])
        self.assertTrue(orcamento.envios.filter(canal="whatsapp").exists())


# ======================================================================
# PROPOSTA APROVADA: o prazo de entrega e o contrato
# ======================================================================
class FolhaDeAprovadasTests(Base):

    def aprovada(self, **campos):
        orcamento = self.proposta("Aprovou", status=Orcamento.Status.APROVADO, **campos)
        Orcamento.objects.filter(pk=orcamento.pk).update(
            respondido_em=timezone.now(), respondido_por="Maria Alegria",
        )
        orcamento.refresh_from_db()
        return orcamento

    def test_mostra_o_resumo_o_prazo_e_o_contrato(self):
        orcamento = self.aprovada()

        corpo = self.folha("orcamentos_aprovados").json()
        item = corpo["itens"][0]

        self.assertEqual(item["id"], orcamento.pk)
        self.assertIn("Aprovada por Maria Alegria", item["resposta"])
        self.assertIn("Cama elástica", item["itens"])
        self.assertEqual(item["total"], "R$ 480,00")
        self.assertEqual(item["prazo"]["url"], f"/producao/prazo/orcamento/{orcamento.pk}/")
        self.assertTrue(item["prazo"]["editavel"])
        self.assertEqual(item["contrato"]["situacao"], "gerar")
        self.assertEqual(item["contrato"]["gerar"], f"/orcamentos/{orcamento.pk}/documento/")
        self.assertEqual(item["contrato"]["link"], f"/orcamentos/{orcamento.pk}/documento/link/")
        self.assertIn("filtro=aprovados", corpo["tela"]["url"])

    def test_combinar_o_prazo_vai_para_o_contrato(self):
        from . import contrato

        orcamento = self.aprovada()

        resposta = self.client.post(
            f"/producao/prazo/orcamento/{orcamento.pk}/", {"prazo": "15"}, **AJAX,
        )

        self.assertEqual(resposta.status_code, 200, resposta.content)
        orcamento.refresh_from_db()
        self.assertEqual(contrato.prazo_de_entrega_do_orcamento(orcamento), 15)
        item = self.folha("orcamentos_aprovados").json()["itens"][0]
        self.assertEqual(item["prazo"]["dias"], 15)
        self.assertEqual(item["prazo"]["contrato"], 15)

    def test_gerar_o_contrato_tira_a_aprovada_do_sino(self):
        from .tests_documento_assinatura import preencher_dados_do_contrato

        preencher_dados_do_contrato()
        orcamento = self.aprovada()
        self.assertEqual(quantidade_do_aviso(self.gestor, "orcamentos_aprovados"), 1)

        resposta = self.client.post(
            f"/orcamentos/{orcamento.pk}/documento/", {"action": "gerar"}, **AJAX,
        )

        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertEqual(quantidade_do_aviso(self.gestor, "orcamentos_aprovados"), 0)
        # E o link de assinatura sai do mesmo endereço do cartão.
        link = self.client.post(f"/orcamentos/{orcamento.pk}/documento/link/", **AJAX).json()
        self.assertIn("wa.me/", link["whatsapp"])

    def test_o_financeiro_ve_o_resumo_sem_o_contrato(self):
        """O contrato é de quem edita o bloco comercial (views_documento_assinatura)."""
        financeiro = usuario("financeiro-aprovada", "financeiro")
        self.aprovada()

        item = self.folha("orcamentos_aprovados", financeiro).json()["itens"][0]

        self.assertNotIn("contrato", item)
        self.assertIn("prazo", item)

    def test_a_producao_combina_o_prazo_pela_tela_dela_e_nao_abre_esta_folha(self):
        producao = usuario("producao-aprovada", "producao")
        self.aprovada()
        self.assertEqual(self.folha("orcamentos_aprovados", producao).status_code, 403)


# ======================================================================
# PEDIDOS E ESTOQUE
# ======================================================================
class FolhaDePedidosEEstoqueTests(Base):

    def test_pedidos_trazem_o_andamento_da_tela_de_pedidos(self):
        pedido = Pedido.objects.create(status="pago")
        Pedido.objects.create(status="finalizado")

        corpo = self.folha("pedidos").json()

        self.assertEqual(corpo["quantidade"], 1)
        item = corpo["itens"][0]
        self.assertEqual(item["id"], pedido.pk)
        self.assertEqual(item["andamento"]["url"], f"/pedidos/{pedido.pk}/andamento/")
        self.assertTrue(item["andamento"]["opcoes"])

    def test_pedidos_sao_do_financeiro_e_da_gestao(self):
        Pedido.objects.create(status="pago")
        self.assertEqual(self.folha("pedidos", usuario("fin-pedidos", "financeiro")).status_code, 200)
        self.assertEqual(self.folha("pedidos", usuario("ven-pedidos", "vendas")).status_code, 403)

    def test_estoque_lista_o_que_comprar(self):
        material = Material.objects.create(nome_material="Lona PVC")
        EstoqueMaterial.objects.create(
            material=material, descricao_local="Galpão A", quantidade=2,
            estoque_minimo=10, preco_fornecedor=Decimal("12.00"),
        )
        EstoqueMaterial.objects.create(
            material=material, descricao_local="Galpão B", quantidade=50,
            estoque_minimo=10, preco_fornecedor=Decimal("12.00"),
        )

        corpo = self.folha("estoque").json()

        self.assertEqual(corpo["quantidade"], 1)
        self.assertEqual(corpo["itens"][0]["local"], "Galpão A")
        self.assertEqual(corpo["itens"][0]["minimo"], 10)

    def test_estoque_e_da_producao_e_da_gestao(self):
        self.assertEqual(self.folha("estoque", usuario("prod-estoque", "producao")).status_code, 200)
        self.assertEqual(self.folha("estoque", usuario("ven-estoque", "vendas")).status_code, 403)


# ======================================================================
# NA TELA: o sino e o Início abrem a folha, e as regras do painel valem
# ======================================================================
class FolhaNaTelaTests(Base):

    def test_o_inicio_mostra_os_avisos_com_a_folha(self):
        Cliente.objects.create(nome_cliente="Sem nada")

        html = self.client.get("/", HTTP_HOST="interno.testserver").content.decode()

        self.assertIn("data-avisos-lista", html)
        self.assertIn('data-resolver="clientes_incompletos"', html)
        self.assertIn("Completar", html)

    def test_o_sino_e_o_inicio_desenham_o_aviso_do_mesmo_jeito(self):
        """O servidor (Início sem JavaScript) e o painel.js (a cada estado)."""
        modelo = (RAIZ / "templates" / "partes" / "aviso_item.html").read_text(encoding="utf-8")
        painel = (RAIZ / "static" / "interno" / "painel.js").read_text(encoding="utf-8")
        trecho = painel[painel.index("function montarLista("):painel.index("function mostrarEstadoDaSincronia(")]
        for marca in ("data-aviso=", "data-resolver=", 'aria-haspopup="dialog"', "ls-aviso-acao",
                      "ls-aviso-quantidade", "ls-aviso-detalhe", " resolvivel"):
            with self.subTest(marca=marca):
                self.assertIn(marca, modelo)
                self.assertIn(marca, trecho)
        # E todo container `data-avisos-lista` é repintado com a lista do sino.
        self.assertIn('querySelectorAll("[data-avisos-lista]")', painel)

    def test_o_aviso_sem_folha_no_inicio_continua_sendo_link(self):
        from core.models import Manutencao, ClientePerfil

        dono = User.objects.create_user("cliente-site", password="x")
        perfil, _ = ClientePerfil.objects.get_or_create(user=dono)
        Manutencao.objects.create(descricao="Rasgou a lona", status="P", usuario=perfil)

        html = self.client.get("/", HTTP_HOST="interno.testserver").content.decode()

        self.assertIn('data-aviso="manutencoes"', html)
        self.assertNotIn('data-resolver="manutencoes"', html)

    def test_o_painel_carrega_a_folha_uma_vez_em_toda_tela(self):
        html = self.client.get("/clientes/", HTTP_HOST="interno.testserver").content.decode()
        self.assertIn("interno/avisos-resolver.js", html)
        self.assertIn("interno/avisos-resolver.css", html)
        self.assertIn('data-resolver-url="/avisos/resolver/', html)

    def test_o_script_liga_uma_vez_e_segue_as_regras_do_painel(self):
        js = (RAIZ / "static" / "interno" / "avisos-resolver.js").read_text(encoding="utf-8")
        self.assertIn("if (window.LSResolverAvisos) return;", js)
        self.assertNotRegex(js, r"(?<![\w.])(alert|confirm)\(")
        self.assertNotIn("<select", js)
        self.assertIn("LSAviso.confirmar", js)

    def test_a_folha_de_estilo_so_usa_as_cores_do_tema(self):
        import re

        css = (RAIZ / "static" / "interno" / "avisos-resolver.css").read_text(encoding="utf-8")
        sem_comentarios = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b", sem_comentarios), [])
        self.assertNotIn("rgba(255", sem_comentarios.replace(" ", ""))
        self.assertNotRegex(sem_comentarios, r"background\s*:\s*(white|#fff|gray|grey)")

    def test_a_regra_nova_nao_entrou_na_folha_do_painel(self):
        painel = (RAIZ / "static" / "interno" / "interno_modern.css").read_text(encoding="utf-8")
        self.assertNotIn("ls-folha-resolver", painel)
