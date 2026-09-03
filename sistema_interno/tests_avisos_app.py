"""A loja falando com o celular de quem baixou o aplicativo.

O QUE ESTES TESTES PROTEGEM, EM UMA FRASE: que a mensagem só saia quando
alguém mandar, que ela vá para o público certo, e que nunca se misture
com o aviso de trabalho da equipe.

O último é o que mais assusta na hora de escrever a feature. As duas
coisas são "notificação no celular" e usam o mesmo transporte; um
`for aparelho in ...` na lista errada manda o anúncio de Natal para o
telefone do montador -- ou, pior, um aviso de operação para o cliente.
Por isso a lista de aparelhos é outra tabela, e há teste dizendo isso.
"""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from .models import AparelhoDoCliente, AvisoDoAplicativo, InscricaoPush
from .permissoes import atribuir_funcoes


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class AvisosDoAplicativoTests(TestCase):

    URL = "/aplicativo/avisos/"

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            "gestor-avisos", "gestor-avisos@example.com", "x",
        )
        self.client.force_login(self.gestor)

    def post(self, dados):
        return self.client.post(
            self.URL, dados,
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def aparelho(self, plataforma="android", usuario=None, sufixo="1"):
        return AparelhoDoCliente.objects.create(
            usuario=usuario,
            endpoint=f"https://push.example/{plataforma}-{sufixo}",
            p256dh="chave-publica", auth="segredo",
            plataforma=plataforma,
        )

    def rascunho(self, **extra):
        dados = {
            "titulo": "Chegou o Touro Mecânico",
            "mensagem": "Reserve para o fim de semana.",
            "publico": "todos",
        }
        dados.update(extra)
        return AvisoDoAplicativo.objects.create(autor=self.gestor, **dados)

    # ------------------------------------------------------ escrever
    def test_o_aviso_nasce_rascunho_e_nao_sai_sozinho(self):
        """Notificação é a única coisa que a loja diz e não desdiz."""
        self.aparelho()

        resposta = self.post({
            "action": "save",
            "titulo": "Chegou o Touro Mecânico",
            "mensagem": "Reserve para o fim de semana.",
            "publico": "todos",
        })

        self.assertEqual(resposta.status_code, 200, resposta.content)
        aviso = AvisoDoAplicativo.objects.get()
        self.assertEqual(aviso.status, AvisoDoAplicativo.Status.RASCUNHO)
        self.assertIsNone(aviso.enviado_em)
        self.assertEqual(aviso.entregues, 0)

    def test_rascunho_pode_ser_corrigido_quantas_vezes_precisar(self):
        aviso = self.rascunho()

        self.post({
            "action": "save", "id": aviso.pk,
            "titulo": "Chegou o Touro Mecânico 2.0",
            "mensagem": "Agora com montagem inclusa.",
            "publico": "android",
        })

        aviso.refresh_from_db()
        self.assertEqual(aviso.titulo, "Chegou o Touro Mecânico 2.0")
        self.assertEqual(aviso.publico, AvisoDoAplicativo.Publico.ANDROID)

    def test_aviso_enviado_nao_se_reescreve(self):
        """O que está no celular das pessoas não muda; o registro também não."""
        aviso = self.rascunho(status=AvisoDoAplicativo.Status.ENVIADO)

        resposta = self.post({
            "action": "save", "id": aviso.pk,
            "titulo": "Outra coisa", "mensagem": "Outra mensagem",
            "publico": "todos",
        })

        self.assertEqual(resposta.status_code, 400)
        aviso.refresh_from_db()
        self.assertEqual(aviso.titulo, "Chegou o Touro Mecânico")

    def test_duplicar_devolve_um_rascunho_editavel(self):
        enviado = self.rascunho(status=AvisoDoAplicativo.Status.ENVIADO)

        self.post({"action": "duplicar", "id": enviado.pk})

        copia = AvisoDoAplicativo.objects.exclude(pk=enviado.pk).get()
        self.assertEqual(copia.status, AvisoDoAplicativo.Status.RASCUNHO)
        self.assertEqual(copia.mensagem, enviado.mensagem)

    def test_endereco_de_fora_nao_vira_notificacao_nossa(self):
        """Aviso que leva para outro domínio é o formato clássico do golpe.

        Quem recebe não tem como conferir o endereço antes de tocar, e o
        remetente que aparece na tela é a Lazer & Sport.
        """
        resposta = self.post({
            "action": "save", "titulo": "Promoção",
            "mensagem": "Confira", "publico": "todos",
            "url": "https://site-de-fora.example/promo",
        })

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("caminho dentro do site", resposta.json()["msg"])
        self.assertFalse(AvisoDoAplicativo.objects.exists())

    def test_caminho_relativo_ganha_a_barra_da_frente(self):
        self.post({
            "action": "save", "titulo": "Promoção",
            "mensagem": "Confira", "publico": "todos", "url": "loja/",
        })
        self.assertEqual(AvisoDoAplicativo.objects.get().url, "/loja/")

    # -------------------------------------------------------- enviar
    def test_enviar_entrega_e_guarda_o_resultado(self):
        self.aparelho(sufixo="a")
        self.aparelho(sufixo="b")
        aviso = self.rascunho()

        with patch("sistema_interno.push.configurado", return_value=True), \
             patch("sistema_interno.push.enviar", return_value=True) as enviar:
            resposta = self.post({"action": "enviar", "id": aviso.pk})

        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertEqual(enviar.call_count, 2)
        aviso.refresh_from_db()
        self.assertEqual(aviso.status, AvisoDoAplicativo.Status.ENVIADO)
        self.assertEqual(aviso.entregues, 2)
        self.assertEqual(aviso.aparelhos_no_envio, 2)
        self.assertIsNotNone(aviso.enviado_em)

    def test_o_publico_escolhido_e_respeitado(self):
        android = self.aparelho("android", sufixo="a")
        self.aparelho("ios", sufixo="b")
        aviso = self.rascunho(publico=AvisoDoAplicativo.Publico.ANDROID)

        with patch("sistema_interno.push.configurado", return_value=True), \
             patch("sistema_interno.push.enviar", return_value=True) as enviar:
            self.post({"action": "enviar", "id": aviso.pk})

        self.assertEqual(enviar.call_count, 1)
        self.assertEqual(enviar.call_args[0][0], android.endpoint)

    def test_aparelho_com_aplicativo_desinstalado_sai_da_lista(self):
        """`InscricaoMorta` é o serviço do fabricante dizendo "não existe".

        Insistir para sempre num endereço morto é o que transforma uma
        lista viva numa lista de fantasmas -- e faz o relatório de
        entrega mentir para sempre.
        """
        from sistema_interno import push

        self.aparelho(sufixo="morto")
        aviso = self.rascunho()

        with patch("sistema_interno.push.configurado", return_value=True), \
             patch("sistema_interno.push.enviar", side_effect=push.InscricaoMorta("x")):
            self.post({"action": "enviar", "id": aviso.pk})

        self.assertFalse(AparelhoDoCliente.objects.exists())
        aviso.refresh_from_db()
        self.assertEqual(aviso.entregues, 0)

    def test_sem_aparelho_nenhum_o_envio_explica_em_vez_de_fingir(self):
        aviso = self.rascunho()

        with patch("sistema_interno.push.configurado", return_value=True):
            resposta = self.post({"action": "enviar", "id": aviso.pk})

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("Nenhum aparelho", resposta.json()["msg"])
        aviso.refresh_from_db()
        self.assertEqual(aviso.status, AvisoDoAplicativo.Status.RASCUNHO)

    def test_enviar_duas_vezes_o_mesmo_aviso_e_recusado(self):
        self.aparelho()
        aviso = self.rascunho(status=AvisoDoAplicativo.Status.ENVIADO)

        with patch("sistema_interno.push.configurado", return_value=True), \
             patch("sistema_interno.push.enviar", return_value=True) as enviar:
            resposta = self.post({"action": "enviar", "id": aviso.pk})

        self.assertEqual(resposta.status_code, 400)
        enviar.assert_not_called()

    def test_o_aviso_do_cliente_nunca_toca_o_aparelho_da_equipe(self):
        """As duas listas são separadas, e é este teste que garante isso."""
        InscricaoPush.objects.create(
            usuario=self.gestor,
            endpoint="https://push.example/equipe-1",
            p256dh="k", auth="a",
        )
        self.aparelho(sufixo="cliente")
        aviso = self.rascunho()

        with patch("sistema_interno.push.configurado", return_value=True), \
             patch("sistema_interno.push.enviar", return_value=True) as enviar:
            self.post({"action": "enviar", "id": aviso.pk})

        endpoints = [chamada[0][0] for chamada in enviar.call_args_list]
        self.assertEqual(endpoints, ["https://push.example/android-cliente"])

    # ------------------------------------------------------- acesso
    def test_producao_nao_manda_recado_para_a_base_de_clientes(self):
        """Quem não tem a função vai para a própria tela, como no resto do painel."""
        tecnico = User.objects.create_user("tecnico-app", password="x")
        atribuir_funcoes(tecnico, ["producao"])
        self.client.force_login(tecnico)

        resposta = self.client.get(self.URL, HTTP_HOST="interno.testserver")

        self.assertEqual(resposta.status_code, 302)
        self.assertNotIn("aplicativo", resposta["Location"])
        # E a porta dos fundos também está fechada: sem a função, o POST
        # não escreve nada.
        self.post({
            "action": "save", "titulo": "Oi", "mensagem": "Tudo bem?",
            "publico": "todos",
        })
        self.assertFalse(AvisoDoAplicativo.objects.exists())


@override_settings(ALLOWED_HOSTS=["testserver", "interno.testserver"])
class InscricaoDeAparelhoDoClienteTests(TestCase):
    """A porta pública: este celular quer ser avisado."""

    URL = "/aplicativo/avisos/aparelho/"

    def test_visitante_sem_conta_pode_aceitar_receber(self):
        """Quem instalou e ainda não criou login é quem mais precisa."""
        resposta = self.client.post(self.URL, {
            "endpoint": "https://push.example/visitante",
            "p256dh": "chave", "auth": "segredo", "plataforma": "android",
        })

        self.assertEqual(resposta.status_code, 200)
        aparelho = AparelhoDoCliente.objects.get()
        self.assertIsNone(aparelho.usuario)
        self.assertEqual(aparelho.plataforma, "android")

    def test_o_mesmo_aparelho_troca_de_dono_em_vez_de_duplicar(self):
        dono = User.objects.create_user("cliente-um", password="x")
        self.client.force_login(dono)
        self.client.post(self.URL, {
            "endpoint": "https://push.example/compartilhado",
            "p256dh": "chave", "auth": "segredo", "plataforma": "ios",
        })

        outro = User.objects.create_user("cliente-dois", password="x")
        self.client.force_login(outro)
        self.client.post(self.URL, {
            "endpoint": "https://push.example/compartilhado",
            "p256dh": "chave", "auth": "segredo", "plataforma": "ios",
        })

        aparelho = AparelhoDoCliente.objects.get()
        self.assertEqual(aparelho.usuario, outro)

    def test_cancelar_apaga_o_aparelho(self):
        AparelhoDoCliente.objects.create(
            endpoint="https://push.example/desistente",
            p256dh="k", auth="a",
        )

        self.client.post(self.URL, {
            "endpoint": "https://push.example/desistente", "acao": "cancelar",
        })

        self.assertFalse(AparelhoDoCliente.objects.exists())

    def test_plataforma_desconhecida_vira_outro_em_vez_de_erro(self):
        """O campo é filtro de envio, não identidade: não vale barrar por ele."""
        self.client.post(self.URL, {
            "endpoint": "https://push.example/estranho",
            "p256dh": "k", "auth": "a", "plataforma": "symbian",
        })

        self.assertEqual(AparelhoDoCliente.objects.get().plataforma, "outro")

    def test_o_service_worker_responde_na_raiz_do_site(self):
        """Em /static/ ele não controlaria página nenhuma -- e push não chegaria."""
        resposta = self.client.get("/app-sw.js")

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta["Service-Worker-Allowed"], "/")
        corpo = resposta.content.decode()
        self.assertIn('addEventListener("push"', corpo)
        self.assertIn('addEventListener("notificationclick"', corpo)
