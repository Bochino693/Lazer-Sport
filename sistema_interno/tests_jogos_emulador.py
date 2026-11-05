"""Os arquivos do emulador pelo painel (/site/jogos/, só o superadministrador).

O que se garante:
* o jogo de console é salvo sem endereço nem .html, e o painel pede os
  arquivos logo depois (fica fora do site até eles chegarem);
* conferir ANTES de enviar só com o começo dos arquivos diz o que falta;
* pelo armazenamento de sempre, o conjunto só é guardado inteiro: faltou
  uma faixa ou passou do limite, nada é guardado; o .cue fica no banco (já
  reescrito) e cada faixa no armazenamento; enviar de novo troca tudo e
  apaga o antigo; tirar os arquivos e excluir o jogo apagam também;
* pelo armazenamento de jogos grandes, o navegador recebe um link por
  arquivo, e o site só guarda depois de conferir o que chegou no balde.
"""
import json
from unittest import mock

from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from core import armazenamento_grande
from core.models import ArquivoEmulador, JogoCadastrado
from core.tests_jogos_emulador import AUDIO, CUE, FAIXA_PSX, NES

from .tests_jogos import HOST, BaseTela


def arquivo(nome, dados):
    return SimpleUploadedFile(nome, dados, content_type="application/octet-stream")


class BaseEmulador(BaseTela):
    def setUp(self):
        super().setUp()
        trocar = mock.patch.object(ArquivoEmulador._meta.get_field("arquivo"), "storage", self.disco)
        trocar.start()
        self.addCleanup(trocar.stop)

    def novo_jogo(self, **extra):
        resposta = self.enviar(self.dados(endereco="", sistema="auto", **extra))
        self.assertEqual(resposta.status_code, 200, resposta.content)
        return resposta.json(), JogoCadastrado.objects.get(slug="corrida-maluca")

    def enviar_disco(self, jogo, *arquivos, sistema="auto"):
        self.client.force_login(self.super)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                "/site/jogos/", {"action": "emulador_enviar", "id": jogo.pk, "sistema": sistema, "arquivos": list(arquivos)},
                HTTP_HOST=HOST, HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )

    def disco_completo(self):
        return [arquivo("Jogo.cue", CUE), arquivo("Track 01.bin", FAIXA_PSX), arquivo("Track 02.bin", AUDIO)]

    def conferir(self, jogo, arquivos):
        """O que o navegador manda antes de enviar: nomes, tamanhos e o começo de cada arquivo."""
        trechos, manifesto = b"", []
        for nome, dados in arquivos:
            cabeca = dados[:128 * 1024]
            manifesto.append({"nome": nome, "tamanho": len(dados), "cabeca": [len(trechos), len(cabeca)], "cauda": None})
            trechos += cabeca
        self.client.force_login(self.super)
        return self.client.post("/site/jogos/", {
            "action": "emulador_conferir", "id": jogo.pk, "sistema": "auto",
            "manifesto": json.dumps(manifesto), "trechos": SimpleUploadedFile("trechos.bin", trechos),
        }, HTTP_HOST=HOST, HTTP_X_REQUESTED_WITH="XMLHttpRequest")


class CadastroDoJogoDeConsoleTests(BaseEmulador):
    def test_salvar_com_o_sistema_pede_os_arquivos_e_o_jogo_fica_fora_do_site(self):
        json_, jogo = self.novo_jogo()
        self.assertTrue(json_["abrir_emulador"])
        self.assertEqual(jogo.sistema, "auto")
        self.assertFalse(jogo.emulador_pronto)
        self.assertNotContains(self.client.get(reverse("jogos")), "Corrida Maluca")
        pagina = self.client.get("/site/jogos/", HTTP_HOST=HOST)
        self.assertContains(pagina, "Faltam os arquivos")
        self.assertContains(pagina, 'data-emulador="%d"' % jogo.pk)

    def test_o_sistema_de_licenca_nao_comercial_e_recusado(self):
        resposta = self.enviar(self.dados(endereco="", sistema="snes"))
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("licença", resposta.json()["msg"])


class ConferirAntesDeEnviarTests(BaseEmulador):
    def test_diz_o_que_falta_sem_subir_o_disco(self):
        _, jogo = self.novo_jogo()
        resposta = self.conferir(jogo, [("Jogo.cue", CUE), ("Track 01.bin", FAIXA_PSX)])
        analise = resposta.json()["analise"]
        self.assertFalse(analise["ok"])
        self.assertTrue(any("Track 02.bin" in e for e in analise["erros"]))
        self.assertEqual(resposta.json()["modo"], "direto")
        self.assertFalse(ArquivoEmulador.objects.exists())

    def test_completo_volta_pronto_e_com_o_sistema(self):
        _, jogo = self.novo_jogo()
        analise = self.conferir(jogo, [("Jogo.cue", CUE), ("Track 01.bin", FAIXA_PSX), ("Track 02.bin", AUDIO)]).json()["analise"]
        self.assertTrue(analise["ok"], analise["erros"])
        self.assertEqual(analise["sistema"], "psx")

    def test_trechos_quebrados_sao_recusados(self):
        _, jogo = self.novo_jogo()
        self.client.force_login(self.super)
        resposta = self.client.post("/site/jogos/", {
            "action": "emulador_conferir", "id": jogo.pk,
            "manifesto": json.dumps([{"nome": "a.nes", "tamanho": 10, "cabeca": [0, 999999]}]),
            "trechos": SimpleUploadedFile("trechos.bin", b"abc"),
        }, HTTP_HOST=HOST, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(resposta.status_code, 400)


class EnvioDiretoTests(BaseEmulador):
    def test_o_disco_completo_e_guardado_com_o_cue_no_banco_e_as_faixas_no_armazenamento(self):
        _, jogo = self.novo_jogo()
        resposta = self.enviar_disco(jogo, *self.disco_completo())
        self.assertEqual(resposta.status_code, 200, resposta.content)
        jogo.refresh_from_db()
        self.assertEqual(jogo.sistema, "psx")
        self.assertIn("PlayStation", jogo.emulador_resumo)
        arquivos = {a.nome: a for a in jogo.arquivos_emulador.all()}
        self.assertEqual(sorted(arquivos), ["Jogo.cue", "Track 01.bin", "Track 02.bin"])
        self.assertEqual(arquivos["Jogo.cue"].papel, ArquivoEmulador.JOGO)
        self.assertIn('FILE "Track 01.bin"', arquivos["Jogo.cue"].conteudo)
        self.assertFalse(arquivos["Jogo.cue"].arquivo)
        with self.disco.open(arquivos["Track 01.bin"].arquivo.name) as guardado:
            self.assertEqual(guardado.read(), FAIXA_PSX)
        # e o jogo entra no site, pelo quadro do emulador
        self.assertContains(self.client.get(reverse("jogos")), "Corrida Maluca")
        self.assertEqual(self.client.get(reverse("jogo_emulador", args=["corrida-maluca"])).status_code, 200)

    def test_faltou_uma_faixa_nada_e_guardado(self):
        _, jogo = self.novo_jogo()
        resposta = self.enviar_disco(jogo, arquivo("Jogo.cue", CUE), arquivo("Track 01.bin", FAIXA_PSX))
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("Track 02.bin", resposta.json()["msg"])
        self.assertFalse(ArquivoEmulador.objects.exists())
        self.assertFalse(self.disco.exists("jogos/emulador"))  # nem a faixa que veio subiu

    @override_settings(JOGOS_ARMAZENAMENTO_LIMITE_MB="1")
    def test_o_limite_do_armazenamento_e_avisado_antes(self):
        _, jogo = self.novo_jogo()
        grande = arquivo("Track 01.bin", FAIXA_PSX + bytes(2 * 1024 * 1024))
        resposta = self.enviar_disco(jogo, arquivo("Jogo.cue", CUE), grande, arquivo("Track 02.bin", AUDIO))
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("até 1,0 MB", resposta.json()["msg"])
        self.assertFalse(ArquivoEmulador.objects.exists())

    def test_enviar_de_novo_troca_o_conjunto_e_apaga_o_antigo(self):
        _, jogo = self.novo_jogo()
        self.enviar_disco(jogo, *self.disco_completo())
        antigos = [a.arquivo.name for a in jogo.arquivos_emulador.all() if a.arquivo]
        resposta = self.enviar_disco(jogo, arquivo("verde.nes", NES))
        self.assertEqual(resposta.status_code, 200, resposta.content)
        jogo.refresh_from_db()
        self.assertEqual(jogo.sistema, "nes")
        self.assertEqual([a.nome for a in jogo.arquivos_emulador.all()], ["verde.nes"])
        for nome in antigos:
            self.assertFalse(self.disco.exists(nome), nome)

    def test_tirar_os_arquivos_e_excluir_o_jogo_apagam_do_armazenamento(self):
        _, jogo = self.novo_jogo()
        self.enviar_disco(jogo, *self.disco_completo())
        nomes = [a.arquivo.name for a in jogo.arquivos_emulador.all() if a.arquivo]
        with self.captureOnCommitCallbacks(execute=True):
            resposta = self.enviar({"action": "emulador_remover", "id": jogo.pk})
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(jogo.arquivos_emulador.exists())
        self.assertTrue(all(not self.disco.exists(n) for n in nomes))

        self.enviar_disco(jogo, arquivo("verde.nes", NES))
        nome = jogo.arquivos_emulador.get().arquivo.name
        with self.captureOnCommitCallbacks(execute=True):
            self.enviar({"action": "delete", "id": jogo.pk, "confirmacao_exclusao": "confirmar"})
        self.assertFalse(JogoCadastrado.objects.filter(pk=jogo.pk).exists())
        self.assertFalse(self.disco.exists(nome))

    def test_excluir_apaga_tambem_a_versao_para_computador(self):
        exe = SimpleUploadedFile("jogo.exe", b"MZ" + bytes(200))
        resposta = self.enviar(self.dados(versao_pc=exe))
        self.assertEqual(resposta.status_code, 200, resposta.content)
        jogo = JogoCadastrado.objects.get()
        nome = jogo.versao_pc.name
        self.assertTrue(self.disco.exists(nome))
        with self.captureOnCommitCallbacks(execute=True):
            self.enviar({"action": "delete", "id": jogo.pk, "confirmacao_exclusao": "confirmar"})
        self.assertFalse(self.disco.exists(nome))


class BaldeDeMentira:
    """Um armazenamento de jogos grandes em memória: o que o navegador mandou por PUT."""

    def __init__(self):
        self.objetos = {}
        self.problemas = []

    def instalar(self, teste):
        for nome, valor in {
            "configurado": lambda: True,
            "url_para_enviar": lambda chave: "https://balde.exemplo/enviar/" + chave,
            "url_publica": lambda chave: "https://pub.exemplo/" + chave,
            "tamanho": lambda chave: len(self.objetos[chave]) if chave in self.objetos else None,
            "ler": lambda chave, inicio, quantos: self.objetos[chave][inicio:inicio + quantos],
            "apagar": lambda chaves: [self.objetos.pop(c, None) for c in chaves],
            "diagnosticar": lambda chave, origem, principal=None: list(self.problemas),
        }.items():
            trocar = mock.patch.object(armazenamento_grande, nome, valor)
            trocar.start()
            teste.addCleanup(trocar.stop)


class EnvioGrandeTests(BaseEmulador):
    def setUp(self):
        super().setUp()
        self.balde = BaldeDeMentira()
        self.balde.instalar(self)

    def confirmar(self, jogo, plano, *indices):
        self.client.force_login(self.super)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post("/site/jogos/", {
                "action": "emulador_confirmar", "id": jogo.pk, "sistema": "auto", "plano": plano, "indices": list(indices),
            }, HTTP_HOST=HOST, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

    def test_cada_arquivo_vai_direto_ao_balde_e_o_site_confere_no_fim(self):
        _, jogo = self.novo_jogo()
        arquivos = {"Jogo.cue": CUE, "Track 01.bin": FAIXA_PSX, "Track 02.bin": AUDIO}
        resposta = self.conferir(jogo, list(arquivos.items())).json()
        self.assertEqual(resposta["modo"], "grande")
        envios = {e["nome"]: e for e in resposta["envios"]}
        self.assertEqual(sorted(envios), ["Track 01.bin", "Track 02.bin"])  # o .cue fica no site
        self.assertTrue(envios["Track 01.bin"]["url"].startswith("https://balde.exemplo/enviar/jogos/emulador/corrida-maluca/"))

        # antes de o navegador mandar, confirmar não guarda nada
        falta = self.confirmar(jogo, resposta["plano"], arquivo("Jogo.cue", CUE))
        self.assertEqual(falta.status_code, 400)
        self.assertIn("não chegou", falta.json()["msg"])

        for nome, envio in envios.items():  # o PUT do navegador
            self.balde.objetos[envio["chave"]] = arquivos[nome]
        pronto = self.confirmar(jogo, resposta["plano"], arquivo("Jogo.cue", CUE))
        self.assertEqual(pronto.status_code, 200, pronto.content)
        jogo.refresh_from_db()
        self.assertEqual(jogo.sistema, "psx")
        faixa = jogo.arquivos_emulador.get(nome="Track 01.bin")
        self.assertEqual(faixa.chave, envios["Track 01.bin"]["chave"])
        self.assertEqual(faixa.url, "https://pub.exemplo/" + faixa.chave)

    def test_o_plano_de_outro_jogo_ou_adulterado_e_recusado(self):
        _, jogo = self.novo_jogo()
        resposta = self.conferir(jogo, [("verde.nes", NES)]).json()
        self.assertEqual(self.confirmar(jogo, resposta["plano"] + "x").status_code, 400)
        outro = JogoCadastrado.objects.create(nome="Outro", slug="outro", sistema="auto", capa="c.png")
        self.assertIn("outro jogo", self.confirmar(outro, resposta["plano"]).json()["msg"])

    def test_chegou_com_outro_tamanho_apaga_e_pede_de_novo(self):
        _, jogo = self.novo_jogo()
        resposta = self.conferir(jogo, [("verde.nes", NES)]).json()
        chave = resposta["envios"][0]["chave"]
        self.balde.objetos[chave] = NES[:100]
        falha = self.confirmar(jogo, resposta["plano"])
        self.assertIn("outro tamanho", falha.json()["msg"])
        self.assertNotIn(chave, self.balde.objetos)

    def test_balde_sem_acesso_publico_ou_cors_e_avisado(self):
        _, jogo = self.novo_jogo()
        resposta = self.conferir(jogo, [("verde.nes", NES)]).json()
        self.balde.objetos[resposta["envios"][0]["chave"]] = NES
        self.balde.problemas = ["O balde não deixa o site baixar os arquivos: falta a regra de CORS."]
        pronto = self.confirmar(jogo, resposta["plano"])
        self.assertEqual(pronto.status_code, 200, pronto.content)
        self.assertIn("ATENÇÃO", pronto.json()["msg"])
        self.assertEqual(pronto.json()["problemas_do_balde"], self.balde.problemas)


class DiagnosticoDoBaldeTests(BaseEmulador):
    """`diagnosticar` pergunta ao balde como o navegador do visitante pergunta."""

    def resposta(self, status, cors="", head=200):
        falsa = mock.Mock(status_code=status, headers={"Access-Control-Allow-Origin": cors} if cors else {})
        return mock.patch("requests.get", return_value=falsa), mock.patch("requests.head", return_value=mock.Mock(status_code=head, headers={}))

    def diagnostico(self, *args, **kwargs):
        get, head = self.resposta(*args, **kwargs)
        with get, head:
            return armazenamento_grande.diagnosticar("a/b.bin", "https://www.lazersport.com.br", "a/b.bin")

    @override_settings(JOGOS_S3_URL_PUBLICA="https://pub.exemplo")
    def test_cada_problema_com_o_que_ligar(self):
        origem = "https://www.lazersport.com.br"
        self.assertIn("acesso público", self.diagnostico(403)[0])
        self.assertIn("CORS", self.diagnostico(206)[0])
        self.assertEqual(self.diagnostico(206, origem), [])
        self.assertEqual(self.diagnostico(200, "*"), [])
        self.assertIn("HEAD", self.diagnostico(206, origem, head=403)[0])
        # disco com .cue: o emulador abre o índice, que vem do site -- o HEAD do balde não importa
        get, head = self.resposta(206, origem, head=403)
        with get, head:
            self.assertEqual(armazenamento_grande.diagnosticar("a/b.bin", origem), [])
