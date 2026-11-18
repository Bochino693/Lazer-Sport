"""Tarefas, o ponto de ligação com a produção e "Minhas tarefas"."""

from datetime import timedelta

from django.contrib.auth.models import Group
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from sistema_interno.models import Colaborador as NomeNaProducao
from sistema_interno.models import OrdemProducao, ProdutoInterno
from sistema_interno.permissoes import FUNCOES_POR_CODIGO

from . import tarefas
from .apoio_testes import INTERNO, criar_colaborador, criar_conta
from .models import Setor, Tarefa


class SetorCasaComAsFuncoesTests(SimpleTestCase):
    def test_os_setores_sao_as_funcoes_do_painel(self):
        self.assertEqual(set(Setor.values), set(FUNCOES_POR_CODIGO))

    def test_etapa_da_producao_vira_especialidade(self):
        for etapa, esperado in (("Corte de MDF", "corte"), ("Adesivo", "adesivo"), ("Eletrônica", "eletronica"),
                                ("ELETRONICA", "eletronica"), ("Teste de qualidade", "teste"),
                                ("Embalagem", "embalagem"), ("Finalização", "finalizacao"), ("Montagem", "montagem")):
            with self.subTest(etapa=etapa):
                self.assertEqual(tarefas.especialidade_da_etapa(etapa), esperado)
                self.assertEqual(tarefas.setor_da_etapa(etapa), "producao")
        self.assertIsNone(tarefas.setor_da_etapa("Reunião"))


class AtribuirTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.adesivo = criar_colaborador(1, nome="Pessoa Adesivo Teste", especialidades=["adesivo"])
        cls.montagem = criar_colaborador(2, nome="Pessoa Montagem Teste", especialidades=["montagem"])
        cls.vendas = criar_colaborador(3, nome="Pessoa Vendas Teste", setor="vendas", cargo="Vendedor")
        cls.desligada = criar_colaborador(4, nome="Pessoa Desligada Teste", especialidades=["adesivo"],
                                          situacao="desligado", data_desligamento=timezone.localdate())
        # Qualquer objeto do sistema serve de origem: aqui, um grupo.
        cls.unidade = Group.objects.create(name="Unidade 12 · Air Game (teste)")

    def test_sugere_a_especialidade_primeiro_e_so_quem_esta_ativo(self):
        nomes = [p.nome for p in tarefas.sugerir_responsaveis("Adesivo")]
        self.assertEqual(nomes[0], "Pessoa Adesivo Teste")
        self.assertIn("Pessoa Montagem Teste", nomes)
        self.assertNotIn("Pessoa Vendas Teste", nomes)
        self.assertNotIn("Pessoa Desligada Teste", nomes)

    def test_o_menos_ocupado_vem_antes_no_mesmo_grupo(self):
        outra = criar_colaborador(5, nome="Outra Adesivo Teste", especialidades=["adesivo"])
        Tarefa.objects.create(titulo="Ocupada", colaborador=self.adesivo)
        nomes = [p.nome for p in tarefas.sugerir_responsaveis("adesivo")]
        self.assertEqual(nomes[:2], ["Outra Adesivo Teste", "Pessoa Adesivo Teste"])
        self.assertEqual(outra.situacao, "ativo")

    def test_atribuir_cria_uma_por_etapa_e_reatribui(self):
        prazo = timezone.localdate() + timedelta(days=3)
        t1 = tarefas.atribuir(self.adesivo, self.unidade, etapa="Adesivo", prazo=prazo)
        self.assertEqual((t1.colaborador, t1.etapa, t1.setor, t1.prazo), (self.adesivo, "Adesivo", "producao", prazo))
        self.assertEqual(t1.objeto, self.unidade)
        self.assertIn("Unidade 12", t1.titulo)
        t2 = tarefas.atribuir(self.montagem, self.unidade, etapa="Adesivo")
        self.assertEqual(t1.pk, t2.pk)
        self.assertEqual(t2.colaborador, self.montagem)
        t3 = tarefas.atribuir(self.montagem, self.unidade, etapa="Montagem")
        self.assertNotEqual(t3.pk, t1.pk)
        self.assertEqual(tarefas.tarefas_do_objeto(self.unidade).count(), 2)

    def test_sem_colaborador_vai_para_o_sugerido(self):
        tarefa = tarefas.atribuir(None, self.unidade, etapa="Adesivo")
        self.assertEqual(tarefa.colaborador, self.adesivo)

    def test_nao_atribui_a_quem_foi_desligado(self):
        with self.assertRaises(ValueError):
            tarefas.atribuir(self.desligada, self.unidade, etapa="Adesivo")

    def test_concluir_pela_origem_e_os_sinais(self):
        recebidos = []

        def ouvir(sender, **kwargs):
            recebidos.append(kwargs["situacao"])

        tarefas.tarefa_mudou.connect(ouvir)
        try:
            tarefas.atribuir(self.adesivo, self.unidade, etapa="Adesivo")
            self.assertEqual(tarefas.concluir(self.unidade, etapa="Adesivo"), 1)
        finally:
            tarefas.tarefa_mudou.disconnect(ouvir)
        tarefa = tarefas.tarefas_do_objeto(self.unidade).get()
        self.assertEqual(tarefa.situacao, "feita")
        self.assertIsNotNone(tarefa.concluida_em)
        self.assertEqual(recebidos, ["feita"])


class MinhasTarefasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.conta = criar_conta("montadora", "producao")
        cls.eu = criar_colaborador(1, usuario=cls.conta)
        cls.outro = criar_colaborador(2)
        cls.gestora = criar_conta("gestora-tarefas", "gestao")
        cls.unidade = Group.objects.create(name="Unidade 7 (teste)")

    def test_minhas_tarefas_mostram_avulsas_producao_e_ordens(self):
        Tarefa.objects.create(titulo="Organizar a bancada", colaborador=self.eu)
        Tarefa.objects.create(titulo="Tarefa do outro", colaborador=self.outro)
        tarefas.atribuir(self.eu, self.unidade, etapa="Adesivo", rotulo="Unidade 7 · Strike Kids")
        nome = NomeNaProducao.objects.create(nome="Montadora Teste")
        self.eu.colaborador_producao = nome
        self.eu.save()
        OrdemProducao.objects.create(produto=ProdutoInterno.objects.create(nome="Air Game (teste)"),
                                     quantidade=2, colaborador=nome)
        self.client.force_login(self.conta)
        html = self.client.get("/rh/tarefas/", **INTERNO).content.decode()
        self.assertIn("Organizar a bancada", html)
        self.assertIn("Adesivo · Unidade 7 · Strike Kids", html)
        self.assertIn("Air Game (teste)", html)
        self.assertNotIn("Tarefa do outro", html)

    def test_muda_a_propria_situacao_mas_nao_a_do_outro(self):
        minha = Tarefa.objects.create(titulo="Minha", colaborador=self.eu)
        alheia = Tarefa.objects.create(titulo="Alheia", colaborador=self.outro)
        self.client.force_login(self.conta)
        self.client.post(f"/rh/tarefas/{minha.pk}/situacao/", {"situacao": "fazendo"}, **INTERNO)
        minha.refresh_from_db()
        self.assertEqual(minha.situacao, "fazendo")
        self.assertIsNotNone(minha.iniciada_em)
        resposta = self.client.post(f"/rh/tarefas/{alheia.pk}/situacao/", {"situacao": "feita"}, **INTERNO)
        self.assertEqual(resposta.status_code, 404)
        alheia.refresh_from_db()
        self.assertEqual(alheia.situacao, "a_fazer")

    def test_gestao_cria_e_o_colaborador_nao(self):
        self.client.force_login(self.conta)
        self.client.post("/rh/tarefas/", {"titulo": "Criada pelo colaborador", "prioridade": "normal"}, **INTERNO)
        self.assertFalse(Tarefa.objects.filter(titulo="Criada pelo colaborador").exists())
        self.client.force_login(self.gestora)
        resposta = self.client.post("/rh/tarefas/", {
            "titulo": "Lixar as laterais", "prioridade": "alta", "colaborador": self.eu.pk,
            "etapa": "Montagem", "prazo": (timezone.localdate() + timedelta(days=2)).isoformat(),
        }, **INTERNO)
        self.assertEqual(resposta.status_code, 302)
        tarefa = Tarefa.objects.get(titulo="Lixar as laterais")
        self.assertEqual((tarefa.colaborador, tarefa.setor, tarefa.criada_por), (self.eu, "producao", self.gestora))

    def test_sugestao_em_json(self):
        criar_colaborador(3, nome="Especialista Eletronica Teste", especialidades=["eletronica"])
        self.client.force_login(self.gestora)
        corpo = self.client.get("/rh/tarefas/sugerir/?etapa=Eletrônica", **INTERNO).json()
        self.assertEqual(corpo["especialidade"], "eletronica")
        self.assertEqual(corpo["pessoas"][0]["nome"], "Especialista Eletronica Teste")
        self.assertTrue(corpo["pessoas"][0]["especialista"])

    def test_atrasada(self):
        t = Tarefa.objects.create(titulo="Velha", colaborador=self.eu, prazo=timezone.localdate() - timedelta(days=1))
        self.assertTrue(t.atrasada)
        t.mudar_situacao("feita")
        self.assertFalse(t.atrasada)
