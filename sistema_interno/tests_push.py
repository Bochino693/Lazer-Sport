"""A notificação que chega no celular de quem está na estrada.

O teste que mais importa aqui é o do VETOR DO RFC: a criptografia é
escrita neste projeto, e um erro nela não aparece como exceção -- aparece
como um celular que simplesmente nunca toca, meses depois, sem ninguém
ligar uma coisa à outra. Com o vetor oficial na suíte, a regressão é
apontada na hora.
"""

import json
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric import ec
from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from . import push
from .models import InscricaoPush
from .permissoes import atribuir_funcoes


class CriptografiaTests(TestCase):

    # Dados do exemplo do RFC 8291, seção 5.
    TEXTO = b"When I grow up, I want to be a watermelon"
    DESTINO_PUBLICO = (
        "BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcx"
        "aOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4"
    )
    AUTH = "BTBZMqHH6r4Tts7J_aSIgg"
    EFEMERA_PRIVADA = "yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw"
    SAL = "DGv6ra1nlYgDCS1FRnbzlw"
    ESPERADO = (
        "DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27ml"
        "mlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A_yl95bQpu6cVPT"
        "pK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qulcy4a-fN"
    )

    def test_cifra_exatamente_como_o_rfc_8291(self):
        """Byte a byte igual ao exemplo oficial.

        Com o sal e a chave efêmera fixados, a saída é determinística --
        e qualquer desvio (rótulo do HKDF, ordem das chaves no info,
        delimitador de registro) muda o resultado inteiro.
        """
        efemera = ec.derive_private_key(
            int.from_bytes(push.deb64(self.EFEMERA_PRIVADA), "big"),
            ec.SECP256R1(),
        )

        with patch.object(push.os, "urandom", return_value=push.deb64(self.SAL)):
            saida = push.cifrar(
                self.TEXTO, self.DESTINO_PUBLICO, self.AUTH, efemera=efemera,
            )

        self.assertEqual(push.b64(saida), self.ESPERADO)

    def test_cada_envio_usa_sal_e_chave_novos(self):
        """Reaproveitar qualquer um dos dois quebraria o AES-GCM."""
        primeira = push.cifrar(b"oi", self.DESTINO_PUBLICO, self.AUTH)
        segunda = push.cifrar(b"oi", self.DESTINO_PUBLICO, self.AUTH)

        self.assertNotEqual(primeira, segunda)

    def test_sem_chave_na_hospedagem_nada_e_enviado(self):
        """Silêncio de propósito.

        Uma hospedagem sem a variável configurada não pode virar erro em
        toda tela que salva alguma coisa.
        """
        with override_settings(PUSH_VAPID_PRIVADA="", PUSH_VAPID_PUBLICA=""):
            self.assertFalse(push.configurado())
            self.assertFalse(
                push.enviar("https://exemplo/x", self.DESTINO_PUBLICO,
                            self.AUTH, {"titulo": "oi"})
            )

    def test_o_par_gerado_serve_para_cifrar_e_se_identificar(self):
        privada, publica = push.gerar_par()

        with override_settings(
            PUSH_VAPID_PRIVADA=privada, PUSH_VAPID_PUBLICA=publica,
        ):
            self.assertTrue(push.configurado())
            cabecalhos = push.cabecalho_vapid("https://fcm.googleapis.com/fcm/send/x")
            self.assertIn("Authorization", cabecalhos)
            self.assertIn(f"k={publica}", cabecalhos["Authorization"])

    def test_endereco_morto_pede_para_ser_apagado(self):
        """Aplicativo desinstalado devolve 404/410, e é para sempre.

        Insistir contra um endereço morto é gastar rede todo dia até
        alguém perceber.
        """
        privada, publica = push.gerar_par()

        class RespostaFalsa:
            status_code = 410
            text = ""

        with override_settings(PUSH_VAPID_PRIVADA=privada, PUSH_VAPID_PUBLICA=publica):
            with patch.object(push.requests, "post", return_value=RespostaFalsa()):
                with self.assertRaises(push.InscricaoMorta):
                    push.enviar(
                        "https://fcm.googleapis.com/fcm/send/x",
                        self.DESTINO_PUBLICO, self.AUTH, {"titulo": "oi"},
                    )

    def test_servico_fora_do_ar_nao_levanta(self):
        """Um push que não sai não pode derrubar o salvamento de nada."""
        privada, publica = push.gerar_par()

        with override_settings(PUSH_VAPID_PRIVADA=privada, PUSH_VAPID_PUBLICA=publica):
            with patch.object(
                push.requests, "post",
                side_effect=push.requests.RequestException("caiu"),
            ):
                self.assertFalse(push.enviar(
                    "https://fcm.googleapis.com/fcm/send/x",
                    self.DESTINO_PUBLICO, self.AUTH, {"titulo": "oi"},
                ))


class InscricaoDoAparelhoTests(TestCase):

    URL = "/avisos/aparelho/"
    P256DH = CriptografiaTests.DESTINO_PUBLICO
    AUTH = CriptografiaTests.AUTH

    def setUp(self):
        self.pessoa = User.objects.create_user(
            username="vendedora", password="x", is_staff=True,
        )
        atribuir_funcoes(self.pessoa, ["vendas"])
        self.client.force_login(self.pessoa)

    def inscrever(self, endpoint="https://fcm.googleapis.com/fcm/send/abc", **extra):
        dados = {"endpoint": endpoint, "p256dh": self.P256DH, "auth": self.AUTH}
        dados.update(extra)
        return self.client.post(self.URL, dados, HTTP_HOST="interno.testserver")

    def test_o_aparelho_se_inscreve_e_fica_preso_a_quem_esta_logado(self):
        self.assertEqual(self.inscrever().status_code, 200)

        inscricao = InscricaoPush.objects.get()
        self.assertEqual(inscricao.usuario, self.pessoa)
        self.assertEqual(inscricao.p256dh, self.P256DH)

    def test_o_mesmo_aparelho_troca_de_dono_em_vez_de_duplicar(self):
        """Tablet da bancada com a conta trocada é rotina.

        Sem isto o dono antigo continuaria recebendo os avisos do novo --
        na tela de bloqueio, com nome de cliente e valor de proposta.
        """
        self.inscrever()

        outra = User.objects.create_user(username="chefe", password="x", is_staff=True)
        atribuir_funcoes(outra, ["gestao"])
        self.client.force_login(outra)
        self.inscrever()

        self.assertEqual(InscricaoPush.objects.count(), 1)
        self.assertEqual(InscricaoPush.objects.get().usuario, outra)

    def test_desligar_apaga_so_este_aparelho(self):
        self.inscrever("https://fcm.googleapis.com/fcm/send/celular")
        self.inscrever("https://fcm.googleapis.com/fcm/send/tablet")

        self.client.post(
            self.URL,
            {"endpoint": "https://fcm.googleapis.com/fcm/send/celular",
             "acao": "cancelar"},
            HTTP_HOST="interno.testserver",
        )

        restantes = list(InscricaoPush.objects.values_list("endpoint", flat=True))
        self.assertEqual(restantes, ["https://fcm.googleapis.com/fcm/send/tablet"])

    def test_quem_nao_e_da_equipe_nao_se_inscreve(self):
        """O endereço da inscrição É a credencial de quem manda o aviso."""
        cliente = User.objects.create_user(username="cliente", password="x")
        self.client.force_login(cliente)

        self.assertEqual(self.inscrever().status_code, 403)
        self.assertFalse(InscricaoPush.objects.exists())

    def test_sem_as_chaves_a_inscricao_e_recusada(self):
        resposta = self.client.post(
            self.URL,
            {"endpoint": "https://fcm.googleapis.com/fcm/send/x"},
            HTTP_HOST="interno.testserver",
        )

        self.assertEqual(resposta.status_code, 400)

    def test_a_tela_descobre_se_vale_a_pena_oferecer(self):
        """Sem chave na hospedagem o botão nem aparece."""
        with override_settings(PUSH_VAPID_PRIVADA="", PUSH_VAPID_PUBLICA=""):
            dados = self.client.get(self.URL, HTTP_HOST="interno.testserver").json()

        self.assertFalse(dados["configurado"])


class AvisoDaRespostaTests(TestCase):
    """O cliente respondeu: o telefone de quem cuida da proposta toca.

    É o aviso mais importante do painel. Sem ele, um "aprovado" fica
    parado até alguém sentar na bancada -- e nesse meio-tempo a data pode
    ser vendida de novo.
    """

    def setUp(self):
        from .models import ItemOrcamento, Orcamento

        self.gestor = User.objects.create_superuser(
            username="chefe", password="x", email="c@example.com",
        )
        self.de_fora = User.objects.create_user(username="cliente", password="x")

        self.orcamento = Orcamento.objects.create(
            nome_cliente="Festa da Ana",
            contato="(11) 90000-0000",
            status=Orcamento.Status.AGUARDANDO_RESPOSTA,
        )
        ItemOrcamento.objects.create(
            orcamento=self.orcamento, descricao="Cama elástica",
            quantidade=1, valor_unitario=100,
        )

    def inscrever(self, usuario, endpoint):
        return InscricaoPush.objects.create(
            usuario=usuario,
            endpoint=endpoint,
            p256dh=CriptografiaTests.DESTINO_PUBLICO,
            auth=CriptografiaTests.AUTH,
        )

    def test_a_equipe_e_avisada_e_quem_nao_e_da_equipe_nao(self):
        """Notificação aparece na tela de bloqueio, sem desbloquear.

        Mandar o nome do cliente e o valor da proposta para quem não pode
        abrir a tela seria vazar por ali.
        """
        from .models import Orcamento
        from .notificacoes import avisar_resposta_do_cliente

        self.inscrever(self.gestor, "https://fcm.googleapis.com/fcm/send/chefe")
        self.inscrever(self.de_fora, "https://fcm.googleapis.com/fcm/send/estranho")

        self.orcamento.registrar_resposta(aprovado=True, nome="Ana")

        privada, publica = push.gerar_par()
        enviados = []

        def espiar(endpoint, p256dh, auth, dados):
            enviados.append((endpoint, dados))
            return True

        with override_settings(PUSH_VAPID_PRIVADA=privada, PUSH_VAPID_PUBLICA=publica):
            with patch.object(push, "enviar", side_effect=espiar):
                avisar_resposta_do_cliente(self.orcamento)

        destinos = [e for e, _ in enviados]
        self.assertEqual(destinos, ["https://fcm.googleapis.com/fcm/send/chefe"])

        _, aviso = enviados[0]
        self.assertIn(str(self.orcamento.pk), aviso["titulo"])
        self.assertIn("aprovada", aviso["titulo"])
        self.assertIn("Ana", aviso["corpo"])
        self.assertIn("/orcamentos/", aviso["url"])
        # Aprovação vibra; recusa não. Uma vibração para cada coisa que
        # acontece no dia treina a pessoa a ignorar todas.
        self.assertTrue(aviso["urgente"])

    def test_recusa_avisa_sem_vibrar(self):
        from .notificacoes import avisar_resposta_do_cliente

        self.inscrever(self.gestor, "https://fcm.googleapis.com/fcm/send/chefe")
        self.orcamento.registrar_resposta(aprovado=False, nome="Ana", motivo="caro")

        privada, publica = push.gerar_par()
        vistos = []

        with override_settings(PUSH_VAPID_PRIVADA=privada, PUSH_VAPID_PUBLICA=publica):
            with patch.object(
                push, "enviar",
                side_effect=lambda e, p, a, d: vistos.append(d) or True,
            ):
                avisar_resposta_do_cliente(self.orcamento)

        self.assertIn("recusada", vistos[0]["titulo"])
        self.assertFalse(vistos[0]["urgente"])

    def test_endereco_morto_e_apagado_na_primeira_tentativa(self):
        from .notificacoes import avisar_resposta_do_cliente

        self.inscrever(self.gestor, "https://fcm.googleapis.com/fcm/send/sumiu")
        self.orcamento.registrar_resposta(aprovado=True, nome="Ana")

        privada, publica = push.gerar_par()

        with override_settings(PUSH_VAPID_PRIVADA=privada, PUSH_VAPID_PUBLICA=publica):
            with patch.object(push, "enviar", side_effect=push.InscricaoMorta):
                avisar_resposta_do_cliente(self.orcamento)

        self.assertFalse(InscricaoPush.objects.exists())

    def test_a_resposta_do_cliente_e_registrada_mesmo_com_o_push_quebrado(self):
        """A página do cliente não pode dar erro porque um aviso falhou."""
        from .models import Orcamento

        self.inscrever(self.gestor, "https://fcm.googleapis.com/fcm/send/chefe")
        privada, publica = push.gerar_par()

        with override_settings(PUSH_VAPID_PRIVADA=privada, PUSH_VAPID_PUBLICA=publica):
            with patch.object(push, "enviar", side_effect=RuntimeError("boom")):
                resposta = self.client.post(
                    self.orcamento.caminho_publico,
                    {"decisao": "aprovar", "nome": "Ana"},
                )

        self.assertEqual(resposta.status_code, 302)
        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.status, Orcamento.Status.APROVADO)
