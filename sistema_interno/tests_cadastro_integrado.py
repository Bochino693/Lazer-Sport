"""Integração de identidade, mapa e cadastro completo em orçamento."""
from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch
from pathlib import Path
import shutil
import subprocess

from PIL import Image
from django.contrib.auth.models import User
from allauth.account.models import EmailAddress
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase
from core.models import ImagemBrinquedo, ImagemPeca, Brinquedos, PecasReposicao
from .models import Cliente, EnderecoCliente, Orcamento, EmailIdentidade
from .clientes import com_publicacao_mapa


class CadastroIntegradoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('integracao', 'gestor-integracao@example.com', 'teste')
        self.client.force_login(self.user)

    def post(self, path, dados):
        return self.client.post(path, dados, HTTP_HOST='interno.testserver', HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def test_email_repetido_e_bloqueado_dentro_do_cadastro_e_livre_entre_eles(self):
        """A mesma pessoa pode ser conta E cliente com o mesmo endereço.

        O que continua barrado é a duplicidade dentro do mesmo cadastro:
        dois clientes com o mesmo contato, ou duas contas com o mesmo
        e-mail. Ver `core/identidade_email.py`.
        """
        usuario = User.objects.create_user('titular', email='Titular@Example.com')
        EmailAddress.objects.create(user=usuario, email='titular@example.com')

        # Conta e cliente com o mesmo endereço: caso normal, não conflito.
        cliente = Cliente.objects.create(
            nome_cliente='Mesma pessoa', email=' titular@example.com ',
        )
        self.assertTrue(
            EmailIdentidade.objects.filter(
                escopo='cliente', email='titular@example.com',
            ).exists()
        )

        # Dois clientes com o mesmo contato continuam sendo duplicidade.
        with self.assertRaises(IntegrityError), transaction.atomic():
            Cliente.objects.create(nome_cliente='Outra pessoa', email='TITULAR@example.com')

        # Duas contas com o mesmo endereço, também.
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user('nova-conta', email='titular@example.com')

        outro = Cliente.objects.create(
            nome_cliente='Cliente único', email='cliente-unico@example.com',
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Cliente.objects.filter(pk=outro.pk).update(email='titular@example.com')

        # A reserva da CONTA sobrevive enquanto o alias do allauth existir.
        usuario.email = 'novo-endereco@example.com'
        usuario.save()
        self.assertTrue(
            EmailIdentidade.objects.filter(
                escopo='usuario', email='titular@example.com',
            ).exists()
        )
        EmailAddress.objects.filter(user=usuario).delete()
        self.assertFalse(
            EmailIdentidade.objects.filter(
                escopo='usuario', email='titular@example.com',
            ).exists()
        )
        # A do CLIENTE não foi tocada: são gavetas separadas.
        self.assertTrue(
            EmailIdentidade.objects.filter(
                escopo='cliente', email='titular@example.com',
            ).exists()
        )
        cliente.delete()
        self.assertFalse(
            EmailIdentidade.objects.filter(email='titular@example.com').exists()
        )

    def test_endereco_repetido_no_mesmo_cliente_bloqueado_mas_local_compartilhado_permitido(self):
        c = Cliente.objects.create(nome_cliente='Responsável A')
        outro = Cliente.objects.create(nome_cliente='Responsável B')
        campos = dict(endereco='Rua A', numero='10', cidade='São Paulo', latitude=0, longitude=0)
        EnderecoCliente.objects.create(cliente=c, **campos)
        with self.assertRaises(IntegrityError), transaction.atomic():
            EnderecoCliente.objects.create(cliente=c, **{**campos, 'endereco':' rua a '})
        EnderecoCliente.objects.create(cliente=outro, **campos)
        self.assertEqual(EnderecoCliente.objects.count(), 2)

    def test_buffet_com_proposta_ativa_ou_marcacao_manual(self):
        c = Cliente.objects.create(nome_cliente='Thiago de teste', tipo='buffet', nome_estabelecimento='Buffet de teste')
        EnderecoCliente.objects.create(cliente=c, endereco='Rua A', cidade='São Paulo', latitude=0, longitude=0)
        o = Orcamento.objects.create(cliente=c, nome_cliente=c.nome_cliente)
        self.assertFalse(com_publicacao_mapa().get(pk=c.pk).no_mapa)
        for status in ('aguardando_resposta', 'em_negociacao', 'aprovado'):
            o.status = status; o.save()
            self.assertTrue(com_publicacao_mapa().get(pk=c.pk).no_mapa)
        o.status = 'recusado'; o.save()
        self.assertFalse(com_publicacao_mapa().get(pk=c.pk).no_mapa)
        c.publicar_no_mapa=True; c.save()
        self.assertTrue(com_publicacao_mapa().get(pk=c.pk).no_mapa)

    def test_mapa_edita_negocio_sem_apagar_documento_observacoes_ou_local_zero(self):
        c = Cliente.objects.create(nome_cliente='Responsável teste', telefone='11999991111',
            documento='52998224725', observacoes='Preservar histórico', nome_estabelecimento='Buffet anterior')
        EnderecoCliente.objects.create(cliente=c, endereco='Rua A', cidade='São Paulo', latitude=0, longitude=0)
        payload = dict(action='save', id=c.pk, nome_cliente=c.nome_cliente, tipo='buffet',
                       telefone=c.telefone, documento=c.documento, observacoes=c.observacoes,
                       nome_estabelecimento='Buffet novo', cnpj_estabelecimento='11222333000181',
                       endereco='Rua A', cidade='São Paulo', latitude='0', longitude='0', publicar_no_mapa='1')
        r=self.post('/site/clientes-mapa/',payload)
        self.assertEqual(r.status_code,200,r.content)
        c.refresh_from_db()
        self.assertEqual(c.observacoes,'Preservar histórico')
        self.assertEqual(c.nome_estabelecimento,'Buffet novo')
        self.assertEqual(c.cnpj_estabelecimento,'11222333000181')
        self.assertIsNone(c.estabelecimento_id)
        self.assertTrue(c.no_mapa)
        self.assertEqual(c.enderecos.count(),1)

    def test_erro_no_endereco_nao_grava_cliente_pela_metade(self):
        r=self.post('/site/clientes-mapa/',dict(action='save',nome_cliente='Não persistir',
            email='atomic@example.com',endereco='Rua sem cidade'))
        self.assertEqual(r.status_code,400,r.content)
        self.assertFalse(Cliente.objects.filter(nome_cliente='Não persistir').exists())
        self.assertFalse(EmailIdentidade.objects.filter(email='atomic@example.com').exists())

    @staticmethod
    def foto():
        b=BytesIO();Image.new('RGB',(3,3),'red').save(b,'PNG')
        return SimpleUploadedFile('foto.png',b.getvalue(),content_type='image/png')

    def test_cadastro_de_catalogo_guarda_fotos_e_medidas(self):
        with TemporaryDirectory() as pasta:
            storage=FileSystemStorage(location=pasta)
            with patch.object(ImagemBrinquedo._meta.get_field('imagem'),'storage',storage), patch.object(ImagemPeca._meta.get_field('imagem'),'storage',storage):
                r=self.post('/orcamentos/',dict(action='brinquedo_novo',nome='Máquina completa',
                    valor='123,45',altura_m='2,30',largura_m='0,80',profundidade_m='1,85',
                    foto_perfil=self.foto(),foto_verso=self.foto()))
                self.assertEqual(r.status_code,200,r.content)
                brinquedo=Brinquedos.objects.get(pk=r.json()['brinquedo']['id'])
                self.assertEqual(str(brinquedo.altura_m),'2.30')
                self.assertEqual(brinquedo.imagens_brinquedo.count(),2)
                self.assertTrue(brinquedo.imagem_perfil)
                self.assertFalse(brinquedo.ativo)
                r=self.post('/orcamentos/',dict(action='peca_nova',nome='Peça completa',uso='loja',
                    preco_venda='50',preco_fornecedor='20',foto_frente=self.foto(),foto_detalhe=self.foto()))
                self.assertEqual(r.status_code,200,r.content)
                peca=PecasReposicao.objects.get(pk=r.json()['peca']['id'])
                self.assertEqual(peca.imagem_peca_reposicao.count(),2)
                self.assertEqual(peca.uso,'loja')

    def test_foto_invalida_nao_cria_item_parcial(self):
        r=self.post('/orcamentos/',dict(action='brinquedo_novo',nome='Arquivo inválido',
            foto_perfil=SimpleUploadedFile('falsa.png',b'nao e imagem',content_type='image/png')))
        self.assertEqual(r.status_code,400,r.content)
        self.assertFalse(Brinquedos.objects.filter(nome_brinquedo='Arquivo inválido').exists())

    def test_acoes_do_mapa_apos_menu_ser_movido(self):
        node=shutil.which('node')
        if not node or subprocess.run([node,'-e',"require('jsdom')"],capture_output=True).returncode:
            self.skipTest('jsdom opcional')
        Cliente.objects.create(nome_cliente='Cliente para editar',email='editar@example.com')
        html=self.client.get('/site/clientes-mapa/',HTTP_HOST='interno.testserver').content.decode()
        result=subprocess.run([node,str(Path(__file__).parent/'tests_js'/'clientes_mapa.cjs')],
            input=html,capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_mapa_publico_reflete_proposta_e_mostra_um_ponto_por_cliente(self):
        from core.views import HomeView
        from core.home_cache import get_cached_home_context
        from django.core.cache import cache
        cache.clear()
        c = Cliente.objects.create(nome_cliente='Responsável reservado', nome_estabelecimento='Nome público do buffet')
        EnderecoCliente.objects.create(cliente=c,endereco='Rua principal',cidade='São Paulo',latitude=0,longitude=0)
        EnderecoCliente.objects.create(cliente=c,endereco='Outro endereço',cidade='São Paulo',latitude=1,longitude=1)
        inicial=get_cached_home_context(HomeView()._build_public_context)
        self.assertFalse(any(p['nome']=='Nome público do buffet' for p in inicial['clientes_mapa']))
        with self.captureOnCommitCallbacks(execute=True):
            o=Orcamento.objects.create(cliente=c,nome_cliente=c.nome_cliente,status='aguardando_resposta')
        dados=get_cached_home_context(HomeView()._build_public_context)
        pontos=[p for p in dados['clientes_mapa'] if p['nome']=='Nome público do buffet']
        self.assertEqual(len(pontos),1)
        self.assertEqual(pontos[0]['lat'],0)
        with self.captureOnCommitCallbacks(execute=True):
            o.status='recusado';o.save()
        dados=get_cached_home_context(HomeView()._build_public_context)
        self.assertFalse(any(p['nome']=='Nome público do buffet' for p in dados['clientes_mapa']))

    def test_falha_no_upload_desfaz_objeto_e_limpa_fotos_desta_tentativa(self):
        with TemporaryDirectory() as pasta:
            storage=FileSystemStorage(location=pasta)
            original=storage.save
            chamadas=[]
            def falhar(name, content, **kwargs):
                chamadas.append(name)
                if len(chamadas)==2:
                    raise OSError('storage temporariamente indisponível')
                return original(name,content,**kwargs)
            with patch.object(ImagemBrinquedo._meta.get_field('imagem'),'storage',storage), patch.object(storage,'save',side_effect=falhar):
                r=self.post('/orcamentos/',dict(action='brinquedo_novo',nome='Upload incompleto',foto_perfil=self.foto(),foto_verso=self.foto()))
            self.assertEqual(r.status_code,400,r.content)
            self.assertFalse(Brinquedos.objects.filter(nome_brinquedo='Upload incompleto').exists())
            self.assertFalse(any(p.is_file() for p in Path(pasta).rglob('*')))

    def test_regra_de_unicidade_nao_bloqueia_recuperacao_de_senha(self):
        from allauth.account.forms import ResetPasswordForm
        form = ResetPasswordForm(data={"email": self.user.email})
        self.assertTrue(form.is_valid(), form.errors)

    def test_signup_aceita_email_de_cliente_e_recusa_o_de_outra_conta(self):
        """Cliente virando usuário é o caso normal, não uma duplicidade.

        Quem já está cadastrado como cliente cria a conta dele com o
        mesmo e-mail -- é a mesma pessoa em dois papéis. O que a conta
        não pode repetir é o endereço de OUTRA conta, que deixaria a
        recuperação de senha sem saber qual atender.
        """
        from core.adapters import AccountAdapter
        from django.core.exceptions import ValidationError
        Cliente.objects.create(nome_cliente="Contato sem conta",email="reservado@example.com")
        self.assertEqual(
            AccountAdapter().validate_unique_email("RESERVADO@example.com"),
            "reservado@example.com",
        )
        User.objects.create_user("ja-tem-conta", email="ocupado@example.com")
        with self.assertRaises(ValidationError):
            AccountAdapter().validate_unique_email("OCUPADO@example.com")
