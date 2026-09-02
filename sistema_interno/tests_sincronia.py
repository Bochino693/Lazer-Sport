"""Contagens entre atendentes, payload condicional e proteção de edição."""
import json
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from core.models import ClientePerfil, Manutencao
from .models import Orcamento, OrdemServico
from .sincronia import revisao_modulo


class SincroniaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.usuario = User.objects.create_superuser('sincronia', 's@example.com', 'teste')
        self.client.force_login(self.usuario)

    def get(self, path='/avisos/estado/', **headers):
        return self.client.get(path, HTTP_HOST='interno.testserver', **headers)

    def post(self, path, dados):
        return self.client.post(path, dados, HTTP_HOST='interno.testserver', HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def test_manutencao_invalida_cache_sem_acao_do_atendente(self):
        self.assertEqual(self.get().json()['contagens']['count_manutencao'], 0)
        perfil, _ = ClientePerfil.objects.get_or_create(user=self.usuario)
        m = Manutencao.objects.create(usuario=perfil, descricao='Teste de assistência', status='P')
        novo = self.get().json()
        self.assertEqual(novo['contagens']['count_manutencao'], 1)
        Manutencao.objects.filter(pk=m.pk).update(status='C')
        fechado = self.get().json()
        self.assertEqual(fechado['contagens']['count_manutencao'], 0)
        self.assertNotEqual(novo['revisoes']['manutencoes'], fechado['revisoes']['manutencoes'])

    def test_mudanca_de_preco_ou_descricao_muda_revisao_sem_mudar_contagem(self):
        for modelo, modulo in [(Orcamento, 'orcamentos'), (OrdemServico, 'ordens_servico')]:
            objeto = modelo.objects.create(nome_cliente='Teste')
            antes = self.get().json()
            objeto.observacoes = 'Mudou a proposta'
            objeto.save()
            depois = self.get().json()
            self.assertEqual(antes['contagens'], depois['contagens'])
            self.assertNotEqual(antes['revisoes'][modulo], depois['revisoes'][modulo])

    def test_estado_inalterado_responde_304_e_mudanca_responde_200(self):
        inicial = self.get()
        igual = self.get(HTTP_IF_NONE_MATCH=inicial['ETag'])
        self.assertEqual(igual.status_code, 304)
        self.assertEqual(igual.content, b'')
        Orcamento.objects.create(nome_cliente='Novo atendimento')
        self.assertEqual(self.get(HTTP_IF_NONE_MATCH=inicial['ETag']).status_code, 200)

    def test_shell_nao_espera_consultas_do_sino(self):
        with patch('sistema_interno.context_processors._apurar_com_cache', side_effect=AssertionError('A tela deve carregar sem apurar o sino')):
            html = self.get('/orcamentos/').content.decode()
        for chave in ('count_orcamentos', 'count_ordens_servico', 'count_manutencao'):
            self.assertIn(f'data-selo="{chave}"', html)

    def test_manutencoes_tem_resposta_parcial_com_numero_e_revisao(self):
        resposta = self.get('/manutencoes/inner/', HTTP_X_LS_FRAGMENTO='lista')
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta['X-LS-Fragmento'], 'lista')
        self.assertContains(resposta, 'data-ls-sincronia="manutencoes"')
        self.assertNotContains(resposta, '<html')
        self.assertContains(resposta, revisao_modulo(self.usuario, 'manutencoes'))

    def test_editor_antigo_nao_sobrescreve_atendimento_recente(self):
        for modelo, rota in [(Orcamento, '/orcamentos/'), (OrdemServico, '/ordens-servico/')]:
            obj = modelo.objects.create(nome_cliente='Cliente original')
            revisao = obj.atualizado.isoformat()
            obj.nome_cliente = 'Alterado por colega'
            obj.save()
            resposta = self.post(rota, {'action': 'save', 'id': obj.pk, 'revisao': revisao,
                                       'nome_cliente': 'Valor antigo', 'itens': json.dumps([])})
            self.assertEqual(resposta.status_code, 409, resposta.content)
            obj.refresh_from_db()
            self.assertEqual(obj.nome_cliente, 'Alterado por colega')

    def test_usuario_sem_modulo_nao_recebe_sua_revisao(self):
        user = User.objects.create_user('sem-acesso')
        self.assertIsNone(revisao_modulo(user, 'orcamentos'))
        self.assertIsNone(revisao_modulo(user, 'ordens_servico'))
        self.assertIsNone(revisao_modulo(user, 'manutencoes'))

    def test_contadores_e_sons_no_dom(self):
        import shutil
        import subprocess
        from pathlib import Path
        node = shutil.which('node')
        if not node or subprocess.run([node, '-e', "require('jsdom')"], capture_output=True).returncode:
            self.skipTest('jsdom não está disponível em NODE_PATH')
        resultado = subprocess.run(
            [node, str(Path(__file__).parent / 'tests_js' / 'sincronia.cjs')],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
