"""A nova versão pode ser editada usando os dados do próprio POST."""
import json
from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase
from .models import Orcamento, ItemOrcamento


class RefazerEditorTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser('editor-teste', 'teste@example.com', 'teste'))
        self.anterior = Orcamento.objects.create(
            nome_cliente='Cliente de teste', status=Orcamento.Status.RECUSADO,
            motivo_negociacao='Trocar item e reduzir preço',
        )
        ItemOrcamento.objects.create(
            orcamento=self.anterior, descricao='Item original', quantidade=2,
            valor_unitario=Decimal('100.00'),
        )

    def post(self, dados):
        return self.client.post('/orcamentos/', dados, HTTP_HOST='interno.testserver',
                                HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def test_post_de_refazer_entrega_editor_completo_e_reenvio_entrega_mesmo_id(self):
        dados = self.post({'action': 'refazer', 'id': self.anterior.pk}).json()
        editor = dados['orcamento']
        self.assertEqual(editor['id'], dados['id'])
        self.assertTrue(editor['pode_editar'])
        self.assertEqual(editor['itens'][0]['quantidade'], 2)
        self.assertEqual(editor['itens'][0]['valor_unitario'], '100,00')
        self.assertIn('reduzir preço', editor['motivo_negociacao'])
        repetido = self.post({'action': 'refazer', 'id': self.anterior.pk}).json()
        self.assertEqual(repetido['orcamento']['id'], editor['id'])

    def test_nova_versao_salva_itens_precos_frete_desconto_sem_mudar_itens_anteriores(self):
        editor = self.post({'action': 'refazer', 'id': self.anterior.pk}).json()['orcamento']
        resposta = self.post({
            'action': 'save', 'id': editor['id'], 'nome_cliente': editor['nome_cliente'],
            'validade': editor['validade'], 'frete': '20,00', 'desconto': '10,00',
            'itens': json.dumps([
                {'descricao': 'Item original', 'quantidade': 3, 'valor_unitario': '80,00'},
                {'descricao': 'Item adicional', 'quantidade': 1, 'valor_unitario': '50,00'},
            ]),
        })
        self.assertEqual(resposta.status_code, 200, resposta.content)
        nova = Orcamento.objects.get(pk=editor['id'])
        self.assertEqual(nova.itens.count(), 2)
        self.assertEqual(nova.total, Decimal('300.00'))
        self.assertEqual(self.anterior.itens.count(), 1)
        self.assertEqual(self.anterior.itens.get().valor_unitario, Decimal('100.00'))

    def test_fluxos_no_dom(self):
        """Opcional: NODE_PATH deve oferecer jsdom para executar o frontend."""
        import shutil
        import subprocess
        import tempfile
        from pathlib import Path
        node = shutil.which('node')
        if not node or subprocess.run(
            [node, '-e', "require('jsdom')"], capture_output=True,
        ).returncode:
            self.skipTest('Instale jsdom e configure NODE_PATH para testar o DOM')
        rascunho = Orcamento.objects.create(nome_cliente='Rascunho teste')
        ItemOrcamento.objects.create(orcamento=rascunho, descricao='Item teste',
                                     quantidade=2, valor_unitario=100)
        fixture = {}
        for caminho in ('/orcamentos/', '/orcamentos/?filtro=rascunhos',
                        '/orcamentos/?filtro=recusados'):
            fixture[caminho] = self.client.get(
                caminho, HTTP_HOST='interno.testserver',
                **({'HTTP_X_LS_FRAGMENTO': 'lista'} if '?' in caminho else {}),
            ).content.decode()
        fixture['refazer'] = self.post({'action': 'refazer', 'id': self.anterior.pk}).json()
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / 'fixture.json'
            arquivo.write_text(json.dumps(fixture))
            resultado = subprocess.run(
                [node, str(Path(__file__).parent / 'tests_js' / 'modais.cjs'), str(arquivo)],
                capture_output=True, text=True, timeout=30,
            )
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
