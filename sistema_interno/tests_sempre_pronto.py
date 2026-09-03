"""A instância não dorme, e a conexão do banco não esfria.

É o item que mais pesa na percepção de lentidão e o único que não tem
nada a ver com o código das telas. Medido: o Django deste projeto sobe em
menos de um segundo, e uma tela do painel resolve em dezenas de
milissegundos. O que custa vinte a sessenta segundos é a hospedagem
trazendo de volta um contêiner suspenso.

A suspensão é decidida por ausência de requisição de ENTRADA. Uma batida
periódica no endereço público é requisição de entrada — e, indo em
`/pronto/`, ainda aquece a conexão do Supabase na thread certa.
"""

import sys
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from core import sempre_pronto

RAIZ = Path(__file__).resolve().parent.parent


class QuandoBaterTests(SimpleTestCase):

    def setUp(self):
        sempre_pronto._ligado = False

    @override_settings(SEMPRE_PRONTO=False)
    def test_desligado_nao_sobe_thread(self):
        self.assertFalse(sempre_pronto.ligar())

    @override_settings(
        SEMPRE_PRONTO=True, INTERNO_BASE_URL="https://interno.exemplo.com.br",
    )
    def test_comando_de_manutencao_nao_bate(self):
        """`migrate` e `collectstatic` também carregam os apps.

        Uma thread de rede ali polui o log do deploy com falhas contra um
        endereço que ainda não está no ar, e no `test` deixaria uma
        thread viva entre casos.
        """
        for comando in ("migrate", "collectstatic", "test", "makemigrations"):
            with self.subTest(comando=comando):
                with patch.object(sys, "argv", ["manage.py", comando]):
                    self.assertFalse(sempre_pronto._ativo())

    @override_settings(
        SEMPRE_PRONTO=True, INTERNO_BASE_URL="https://interno.exemplo.com.br",
    )
    def test_processos_longos_batem(self):
        """`runserver` e o worker são justamente onde a batida importa."""
        for comando in ("runserver", "observar_pendencias"):
            with self.subTest(comando=comando):
                with patch.object(sys, "argv", ["manage.py", comando]):
                    self.assertTrue(sempre_pronto._ativo())

    @override_settings(SEMPRE_PRONTO=True, INTERNO_BASE_URL="", SITE_URL="")
    def test_sem_endereco_nao_bate(self):
        """Bater em lugar nenhum é só um aviso de falha a cada 4 minutos."""
        with patch.object(sys, "argv", ["gunicorn"]):
            self.assertFalse(sempre_pronto._ativo())

    @override_settings(
        SEMPRE_PRONTO=True,
        SEMPRE_PRONTO_URL="",
        INTERNO_BASE_URL="https://interno.exemplo.com.br/",
        SITE_URL="https://www.exemplo.com.br",
    )
    def test_o_painel_tem_precedencia_sobre_o_site(self):
        """É o painel que a fábrica usa o dia inteiro."""
        self.assertEqual(
            sempre_pronto._endereco(), "https://interno.exemplo.com.br",
        )

    @override_settings(
        SEMPRE_PRONTO=True,
        SEMPRE_PRONTO_URL="https://outro.exemplo.com.br/painel/",
        INTERNO_BASE_URL="https://interno.exemplo.com.br",
    )
    def test_o_endereco_explicito_ganha_e_perde_o_caminho(self):
        self.assertEqual(
            sempre_pronto._endereco(), "https://outro.exemplo.com.br",
        )

    @override_settings(SEMPRE_PRONTO=True, INTERNO_BASE_URL="interno.exemplo")
    def test_endereco_sem_esquema_e_recusado(self):
        self.assertEqual(sempre_pronto._endereco(), "")


class ComoBaterTests(SimpleTestCase):

    def test_a_batida_vai_em_pronto_e_nao_em_healthz(self):
        """`/healthz/` não toca o banco -- e isso é obrigatório nele.

        Ele é o health check da hospedagem: se dependesse do Supabase,
        uma oscilação do banco derrubaria o processo web inteiro. Só que
        resolver apenas "a instância não dorme" é metade do problema.
        `/pronto/` faz um `SELECT 1` e chega pela rede, caindo numa das
        threads que atendem requisição -- que é onde a conexão precisa
        estar quente. Aquecer o banco dentro da thread da batida não
        serviria: conexão em Django é por thread, e a dela nunca atende
        ninguém.
        """
        sessao = _SessaoFalsa(200)

        sempre_pronto._bater("https://interno.exemplo.com.br", sessao)

        self.assertEqual(len(sessao.pedidos), 1)
        self.assertIn("/pronto/", sessao.pedidos[0])
        self.assertNotIn("/healthz/", sessao.pedidos[0])

    def test_falha_de_rede_nunca_derruba_o_ciclo(self):
        """Ela roda sozinha e para sempre: uma exceção encerraria tudo.

        E o dia em que ela mais falha é justamente o dia em que ela mais
        precisa continuar tentando.
        """
        sessao = _SessaoQueFalha()

        sempre_pronto._bater("https://interno.exemplo.com.br", sessao)  # não levanta

    def test_resposta_ruim_e_registrada_mas_nao_levanta(self):
        with self.assertLogs("lazer.performance", level="WARNING") as registro:
            sempre_pronto._bater("https://interno.exemplo.com.br", _SessaoFalsa(503))

        self.assertIn("sempre_pronto", registro.output[0])

    def test_o_intervalo_cabe_na_janela_de_suspensao(self):
        """A suspensão acontece com 15 minutos de silêncio.

        O padrão precisa deixar folga para uma batida falhar sem que a
        instância durma antes da próxima.
        """
        from django.conf import settings

        self.assertLessEqual(settings.SEMPRE_PRONTO_INTERVALO, 420)
        self.assertGreaterEqual(settings.SEMPRE_PRONTO_INTERVALO, 60)


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class ProntoRespondeNoPainelTests(TestCase):
    """`/pronto/` precisa existir NO SUBDOMÍNIO, que é quem o chama.

    Ele mora em `core/urls.py`, e o painel atende por `interno.`, onde o
    urlconf é outro. Sem estar na lista de rotas globais do
    `SubdomainURLMiddleware`, toda chamada voltava 404.

    O estrago não era um endereço quebrado: o painel lê 404 como "o
    servidor não respondeu", então concluía que a instância estava
    dormindo em TODA gravação feita depois de dois minutos parado -- e
    pagava a escada de espera inteira antes de mandar o POST, com o
    servidor de pé o tempo todo. A tarja "Servidor acordando…" aparecia
    com o servidor acordado.
    """

    def test_o_painel_alcanca_pronto(self):
        resposta = self.client.get(
            "/pronto/?painel=1", HTTP_HOST="interno.testserver",
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.json()["ok"])

    def test_o_site_publico_tambem(self):
        self.assertEqual(
            self.client.get("/pronto/", HTTP_HOST="testserver").status_code, 200,
        )

    def test_healthz_continua_alcancavel_dos_dois_lados(self):
        for host in ("interno.testserver", "testserver"):
            with self.subTest(host=host):
                self.assertEqual(
                    self.client.get("/healthz/", HTTP_HOST=host).status_code, 200,
                )

    def test_toda_rota_global_responde_no_subdominio(self):
        """A lista existe para isso; um endereço fora dela vira 404 mudo."""
        from core.middleware import SubdomainURLMiddleware

        self.assertIn("/pronto/", SubdomainURLMiddleware.ROTAS_GLOBAIS)
        self.assertIn("/healthz/", SubdomainURLMiddleware.ROTAS_GLOBAIS)

    def test_o_painel_pede_pronto_e_nao_healthz(self):
        """`/healthz/` não toca o banco: acordaria só metade do caminho."""
        painel = (
            RAIZ / "sistema_interno" / "static" / "interno" / "painel.js"
        ).read_text(encoding="utf-8")

        self.assertIn('fetch("/pronto/?painel=1"', painel)


class OndeBaterTests(SimpleTestCase):

    def test_o_processo_web_liga_a_batida_ao_subir(self):
        apps = (RAIZ / "core" / "apps.py").read_text(encoding="utf-8")

        self.assertIn("sempre_pronto", apps)
        self.assertIn("sempre_pronto.ligar()", apps)

    def test_o_worker_tambem_liga(self):
        """Dois processos batendo é redundância barata.

        Se a thread do web morrer por qualquer motivo, o worker continua
        segurando a instância de pé.
        """
        comando = (
            RAIZ / "sistema_interno" / "management" / "commands"
            / "observar_pendencias.py"
        ).read_text(encoding="utf-8")

        self.assertIn("sempre_pronto.ligar()", comando)


class EsperaDoDespertarTests(SimpleTestCase):
    """Enquanto a instância acorda, o painel não pode atrapalhar.

    Repetir tentativas curtas contra um servidor que está subindo é o pior
    formato possível: cada estouro de prazo é um `abort`, e cada `abort`
    joga fora o pedido que já estava na fila. A instância que ia responder
    no segundo 40 nunca chega a responder.
    """

    def ler(self, nome):
        return (
            RAIZ / "sistema_interno" / "static" / "interno" / nome
        ).read_text(encoding="utf-8")

    def test_a_navegacao_sonda_uma_vez_e_depois_espera_de_verdade(self):
        navegacao = self.ler("ls-soft-navigation.js")

        self.assertIn("var TIMEOUT_REDE = 8000;", navegacao)
        self.assertIn("var TIMEOUT_REDE_DESPERTAR = 50000;", navegacao)
        self.assertIn("var MAX_TENTATIVAS_REDE = 2;", navegacao)
        # A sondagem é a primeira; a espera longa, todas as outras.
        self.assertIn("tentativa === 0 ? TIMEOUT_REDE : TIMEOUT_REDE_DESPERTAR", navegacao)

    def test_a_gravacao_sonda_uma_vez_e_depois_espera_de_verdade(self):
        painel = self.ler("painel.js")

        self.assertIn("var PRAZOS_DO_PULSO = [6000, 50000];", painel)
        self.assertIn("PRAZOS_DO_PULSO[Math.min(tentativa,", painel)

    def test_a_busca_de_fundo_nao_fala_com_a_tela(self):
        """Era o defeito que a fábrica viu: 351 segundos sobre tela pronta.

        A antecipação -- o `prefetch` que dispara quando o dedo encosta
        num link -- usava o mesmo caminho da navegação de verdade. Quando
        ela demorava, e ela demora justamente porque busca a tela que
        ainda não está em lugar nenhum, a segunda tentativa acendia
        "Servidor acordando…" por cima de uma tela carregada e
        funcionando.

        E ninguém apagava: `esconderLoader` só roda quando uma navegação
        termina, e não havia navegação nenhuma. A tarja ficava contando
        segundos para sempre.
        """
        navegacao = self.ler("ls-soft-navigation.js")

        # O pedido sabe se é de fundo, e o aviso respeita isso.
        self.assertIn(
            "function requisitar(url, tentativa, silencioso, pedaco, versao)", navegacao
        )
        self.assertIn("if (tentativa > 0 && !silencioso && versao === navegacao && navegacaoPendente) escalarLoader(tentativa);", navegacao)
        # O silêncio atravessa as repetições, senão a segunda volta a falar.
        self.assertEqual(
            navegacao.count("requisitar(url, tentativa + 1, silencioso, pedaco, versao)"), 2
        )
        # E a antecipação pede calada.
        self.assertIn("buscar(url, true, pedaco)", navegacao)

    def test_a_tarja_nunca_sobrevive_a_propria_causa(self):
        """Ela informa uma espera; se a espera acaba, ela tem de sair.

        Qualquer caminho que a mostre e não a esconda a deixaria presa na
        tela. O teto é a rede de segurança: passou da maior espera
        legítima, ou a resposta chegou por outro caminho, ou ela não vem
        mais -- e nos dois casos a tarja está mentindo.
        """
        painel = self.ler("painel.js")

        self.assertIn("var TETO_DA_TARJA = 70000;", painel)
        self.assertIn("tetoOcupado = global.setTimeout(Painel.pronto, TETO_DA_TARJA)", painel)
        # E `pronto` desarma o teto, senão ele apagaria a tarja seguinte.
        pronto = painel[painel.index("Painel.pronto = function ()"):]
        self.assertIn("clearTimeout(tetoOcupado)", pronto[:400])

    def test_so_anuncia_o_despertar_que_tem_alguem_esperando(self):
        """O despertar acontece em quatro momentos; um só tem gente parada.

        O pulso de quatro em quatro minutos, a volta para a aba e o toque
        depois de um tempo parado são aquecimento por precaução. Enquanto
        todos anunciavam, um aquecimento que falhasse escrevia "Servidor
        acordando…" numa tela que estava perfeita -- aviso de espera para
        quem não estava esperando nada.
        """
        painel = self.ler("painel.js")

        self.assertIn("function acordarServidor(forcar, anunciar)", painel)
        self.assertIn("if (anunciar && anunciar()) avisarEspera", painel)
        # O POST sai diretamente: nenhum aquecimento segura a gravação.
        self.assertEqual(painel.count("acordarServidor(false, true)"), 0)
        # Os aquecimentos por precaução continuam mudos.
        self.assertEqual(painel.count("acordarServidor(true).catch"), 1)
        self.assertEqual(painel.count("acordarServidor(false).catch"), 3)

    def test_a_espera_diz_quanto_costuma_levar(self):
        """Sem isso, quem está olhando toca de novo.

        E o toque cancela justamente o pedido que ia ser respondido.
        """
        navegacao = self.ler("ls-soft-navigation.js")

        self.assertIn("Aguardando resposta da conexão", navegacao)

    def test_recuperacao_nao_reinicia_tentativas_em_loop(self):
        navegacao = self.ler("ls-soft-navigation.js")
        bloco = navegacao.split("function mostrarRecuperacao(", 1)[1].split("function fecharMenuMovel(", 1)[0]
        self.assertNotIn("setTimeout", bloco)
        self.assertIn("A tentativa terminou", bloco)
        self.assertIn("versao !== navegacao", navegacao)
        self.assertIn("return garantirFolhas(novoDoc).then", navegacao)


class _SessaoFalsa:
    def __init__(self, status):
        self.status = status
        self.pedidos = []

    def get(self, url, **_):
        self.pedidos.append(url)
        return type("Resposta", (), {"status_code": self.status})()


class _SessaoQueFalha:
    def get(self, *_args, **_kwargs):
        raise OSError("rede fora")
