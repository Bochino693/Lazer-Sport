"""Os arquivos de um jogo de console pelo painel (/site/jogos/, só o superadministrador).

O caminho que se testa é o do navegador (sistema_interno/static/interno/emulador-envio.js):
CONFERIR (nomes, tamanhos e o começo de cada arquivo) -> subir cada PEDAÇO ->
CONFIRMAR. O que se garante:
* o jogo de console é salvo sem endereço nem .html, e fica fora do site até
  os arquivos chegarem; conferir sem o jogo salvo só confere (sem plano);
* um disco grande vira pedaços (aqui, de ~30 KB) e volta INTEIRO, byte a
  byte, quando o quadro do emulador junta os pedaços;
* faltou uma faixa, faltou um pedaço, pedaço com resposta falsa, passou do
  limite: nada é guardado, e o que já tinha subido sai do armazenamento;
* enviar de novo troca o conjunto e apaga o antigo; tirar os arquivos e
  excluir o jogo apagam também;
* com o Cloudinary, cada pedaço vai assinado para a API dele e a resposta
  só vale com a assinatura dele;
* com o balde de jogos grandes, cada arquivo vai inteiro, por link assinado.
"""
import json
from unittest import mock

from cloudinary.utils import api_sign_request
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from core import armazenamento_grande, armazenamento_pedacos
from core.models import ArquivoEmulador, JogoCadastrado
from core.tests_jogos_emulador import AUDIO, CUE, FAIXA_PSX, NES
from core.views_jogos import config_do_emulador

from .tests_jogos import HOST, BaseTela

DISCO = [("Jogo.cue", CUE), ("Track 01.bin", FAIXA_PSX), ("Track 02.bin", AUDIO)]
INDICES = ("cue", "ccd", "toc", "m3u")


def arquivo(nome, dados):
    return SimpleUploadedFile(nome, dados, content_type="application/octet-stream")


@override_settings(JOGOS_PEDACO_MB="0.03")  # ~31 KB: a faixa de dados (46 KB) vira 2 pedaços
class BaseEmulador(BaseTela):
    def setUp(self):
        super().setUp()
        for alvo in (
            mock.patch.object(ArquivoEmulador._meta.get_field("arquivo"), "storage", self.disco),
            mock.patch("django.core.files.storage.default_storage", self.disco),
        ):
            alvo.start()
            self.addCleanup(alvo.stop)

    def post(self, dados):
        self.client.force_login(self.super)
        return self.client.post("/site/jogos/", dados, HTTP_HOST=HOST, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

    def novo_jogo(self, **extra):
        resposta = self.enviar(self.dados(endereco="", sistema="auto", **extra))
        self.assertEqual(resposta.status_code, 200, resposta.content)
        return resposta.json(), JogoCadastrado.objects.get(slug="corrida-maluca")

    def conferir(self, jogo, arquivos, sistema="auto"):
        """O que o navegador manda antes de enviar: nomes, tamanhos e o começo de cada arquivo."""
        trechos, manifesto = b"", []
        for nome, dados in arquivos:
            cabeca = dados[:128 * 1024]
            manifesto.append({"nome": nome, "tamanho": len(dados), "cabeca": [len(trechos), len(cabeca)], "cauda": None})
            trechos += cabeca
        campos = {"action": "emulador_conferir", "sistema": sistema, "manifesto": json.dumps(manifesto),
                  "trechos": SimpleUploadedFile("trechos.bin", trechos)}
        if jogo is not None:
            campos["id"] = jogo.pk
        return self.post(campos)

    def subir(self, corpo, arquivos, pular=None, adulterar=None):
        """Os PEDAÇOS, como o navegador manda (aqui, para o próprio site)."""
        dados, respostas = dict(arquivos), {}
        for envio in corpo["envios"]:
            for numero, parte in enumerate(envio["partes"]):
                if pular == (envio["nome"], numero):
                    continue
                pedaco = dados[envio["enviado"]][parte["inicio"]:parte["fim"]]
                resposta = self.post({**parte["campos"], "file": arquivo("p", pedaco)})
                self.assertEqual(resposta.status_code, 200, resposta.content)
                respostas[parte["id"]] = resposta.json()
                if adulterar == (envio["nome"], numero):
                    respostas[parte["id"]]["signature"] = "falsa"
        return respostas

    def confirmar(self, jogo, corpo, respostas, arquivos, sistema="auto"):
        indices = [arquivo(n, d) for n, d in arquivos if n.rsplit(".", 1)[-1].lower() in INDICES]
        with self.captureOnCommitCallbacks(execute=True):
            return self.post({"action": "emulador_confirmar", "id": jogo.pk, "sistema": sistema, "plano": corpo["plano"],
                              "respostas": json.dumps(respostas), "indices": indices})

    def enviar_disco(self, jogo, arquivos=DISCO, **kw):
        resposta = self.conferir(jogo, arquivos)
        corpo = resposta.json()
        if resposta.status_code != 200 or not corpo["analise"]["ok"]:
            return resposta
        return self.confirmar(jogo, corpo, self.subir(corpo, arquivos, **kw), arquivos)

    def no_armazenamento(self):
        pastas, arquivos = self.disco.listdir("jogos/emulador") if self.disco.exists("jogos/emulador") else ([], [])
        nomes = []
        for pasta in pastas:
            for lote in self.disco.listdir(f"jogos/emulador/{pasta}")[0]:
                nomes += self.disco.listdir(f"jogos/emulador/{pasta}/{lote}")[1]
        return nomes


class CadastroDoJogoDeConsoleTests(BaseEmulador):
    def test_salvar_com_o_sistema_deixa_o_jogo_fora_do_site_ate_os_arquivos_chegarem(self):
        json_, jogo = self.novo_jogo()
        self.assertTrue(json_["abrir_emulador"])
        self.assertEqual(jogo.sistema, "auto")
        self.assertFalse(jogo.emulador_pronto)
        self.assertNotContains(self.client.get(reverse("jogos")), "Corrida Maluca")
        pagina = self.client.get("/site/jogos/", HTTP_HOST=HOST)
        self.assertContains(pagina, "Faltam os arquivos")
        self.assertContains(pagina, 'data-ir-arquivos="1"')
        # a janela do jogo tem o lugar de anexar tudo, e o envio em pedaços está na tela
        self.assertContains(pagina, 'id="jogoArquivos" multiple')
        self.assertContains(pagina, "emulador-envio.js")

    def test_o_sistema_de_licenca_nao_comercial_e_recusado(self):
        resposta = self.enviar(self.dados(endereco="", sistema="snes"))
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("licença", resposta.json()["msg"])


class ConferirAntesDeEnviarTests(BaseEmulador):
    def test_sem_o_jogo_salvo_so_confere_e_diz_o_que_falta(self):
        resposta = self.conferir(None, [("Jogo.cue", CUE), ("Track 01.bin", FAIXA_PSX)])
        corpo = resposta.json()
        self.assertFalse(corpo["analise"]["ok"])
        self.assertTrue(any("Track 02.bin" in e for e in corpo["analise"]["erros"]))
        self.assertEqual(corpo["modo"], "pedacos")
        self.assertNotIn("plano", corpo)

    def test_com_o_jogo_salvo_vem_o_plano_em_pedacos(self):
        _, jogo = self.novo_jogo()
        corpo = self.conferir(jogo, DISCO).json()
        self.assertTrue(corpo["analise"]["ok"], corpo["analise"]["erros"])
        self.assertEqual(corpo["analise"]["sistema"], "psx")
        envios = {e["nome"]: e for e in corpo["envios"]}
        self.assertEqual(sorted(envios), ["Track 01.bin", "Track 02.bin"])  # o .cue fica no banco
        self.assertEqual(len(envios["Track 01.bin"]["partes"]), 2)  # 47040 bytes em pedaços de ~31 KB
        self.assertEqual(envios["Track 01.bin"]["partes"][-1]["fim"], len(FAIXA_PSX))

    def test_um_disco_de_ps1_de_verdade_nao_e_mais_barrado_pelo_tamanho(self):
        _, jogo = self.novo_jogo()
        grande = [("Jogo.cue", CUE), ("Track 01.bin", FAIXA_PSX), ("Track 02.bin", AUDIO)]
        trechos, manifesto = b"", []
        for nome, dados in grande:
            tamanho = 450 * 1024 * 1024 if nome == "Track 01.bin" else len(dados)
            manifesto.append({"nome": nome, "tamanho": tamanho, "cabeca": [len(trechos), len(dados)], "cauda": None})
            trechos += dados
        with override_settings(JOGOS_PEDACO_MB="9"):
            corpo = self.post({"action": "emulador_conferir", "id": jogo.pk, "manifesto": json.dumps(manifesto),
                               "trechos": SimpleUploadedFile("t.bin", trechos)}).json()
        self.assertTrue(corpo["analise"]["ok"], corpo["analise"]["erros"])
        faixa = next(e for e in corpo["envios"] if e["nome"] == "Track 01.bin")
        self.assertEqual(len(faixa["partes"]), 50)  # 450 MB em pedaços de 9 MB

    def test_trechos_quebrados_sao_recusados(self):
        resposta = self.post({
            "action": "emulador_conferir",
            "manifesto": json.dumps([{"nome": "a.nes", "tamanho": 10, "cabeca": [0, 999999]}]),
            "trechos": SimpleUploadedFile("trechos.bin", b"abc"),
        })
        self.assertEqual(resposta.status_code, 400)


class EnvioEmPedacosTests(BaseEmulador):
    def test_o_disco_volta_inteiro_quando_o_emulador_junta_os_pedacos(self):
        _, jogo = self.novo_jogo()
        resposta = self.enviar_disco(jogo)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        jogo.refresh_from_db()
        self.assertEqual(jogo.sistema, "psx")
        arquivos = {a.nome: a for a in jogo.arquivos_emulador.all()}
        self.assertEqual(sorted(arquivos), ["Jogo.cue", "Track 01.bin", "Track 02.bin"])
        self.assertIn('FILE "Track 01.bin"', arquivos["Jogo.cue"].conteudo)
        faixa = arquivos["Track 01.bin"]
        self.assertEqual(len(faixa.pedacos), 2)
        juntado = b"".join(self.disco.open(p["id"]).read() for p in faixa.pedacos)
        self.assertEqual(juntado, FAIXA_PSX)
        # o quadro do emulador recebe as partes, na ordem, e o jogo entra no site
        config = config_do_emulador(jogo)
        do_quadro = {a["caminho"]: a for a in config["arquivos"]}
        self.assertEqual(len(do_quadro["/Track 01.bin"]["partes"]), 2)
        self.assertEqual(do_quadro["/Track 01.bin"]["tamanho"], len(FAIXA_PSX))
        self.assertTrue(do_quadro["/Jogo.cue"]["principal"])
        self.assertEqual(config["nome"], "corrida-maluca.cue")
        self.assertContains(self.client.get(reverse("jogos")), "Corrida Maluca")
        self.assertEqual(self.client.get(reverse("jogo_emulador", args=["corrida-maluca"])).status_code, 200)

    def test_faltou_uma_faixa_nao_vem_plano_e_nada_sobe(self):
        _, jogo = self.novo_jogo()
        resposta = self.enviar_disco(jogo, [("Jogo.cue", CUE), ("Track 01.bin", FAIXA_PSX)])
        self.assertFalse(resposta.json()["analise"]["ok"])
        self.assertNotIn("plano", resposta.json())
        self.assertFalse(ArquivoEmulador.objects.exists())
        self.assertEqual(self.no_armazenamento(), [])

    def test_faltou_um_pedaco_nada_e_guardado_e_o_que_subiu_sai(self):
        _, jogo = self.novo_jogo()
        resposta = self.enviar_disco(jogo, pular=("Track 01.bin", 1))
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("pedaço 2 de 2", resposta.json()["msg"])
        self.assertFalse(ArquivoEmulador.objects.exists())

    def test_resposta_adulterada_e_recusada(self):
        _, jogo = self.novo_jogo()
        resposta = self.enviar_disco(jogo, adulterar=("Track 02.bin", 0))
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("assinatura", resposta.json()["msg"])
        self.assertFalse(ArquivoEmulador.objects.exists())

    @override_settings(JOGOS_PEDACOS_MAX_MB="0.01")  # 10 KB
    def test_o_limite_por_arquivo_e_avisado_antes(self):
        _, jogo = self.novo_jogo()
        corpo = self.conferir(jogo, DISCO).json()
        self.assertFalse(corpo["analise"]["ok"])
        self.assertTrue(any("Track 01.bin" in e and "até" in e for e in corpo["analise"]["erros"]))

    def test_enviar_de_novo_troca_o_conjunto_e_apaga_o_antigo(self):
        _, jogo = self.novo_jogo()
        self.enviar_disco(jogo)
        antigos = [p["id"] for a in jogo.arquivos_emulador.all() for p in a.pedacos]
        resposta = self.enviar_disco(jogo, [("verde.nes", NES)])
        self.assertEqual(resposta.status_code, 200, resposta.content)
        jogo.refresh_from_db()
        self.assertEqual(jogo.sistema, "nes")
        self.assertEqual([a.nome for a in jogo.arquivos_emulador.all()], ["verde.nes"])
        for nome in antigos:
            self.assertFalse(self.disco.exists(nome), nome)

    def test_tirar_os_arquivos_e_excluir_o_jogo_apagam_do_armazenamento(self):
        _, jogo = self.novo_jogo()
        self.enviar_disco(jogo)
        nomes = [p["id"] for a in jogo.arquivos_emulador.all() for p in a.pedacos]
        with self.captureOnCommitCallbacks(execute=True):
            resposta = self.post({"action": "emulador_remover", "id": jogo.pk})
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(jogo.arquivos_emulador.exists())
        self.assertTrue(all(not self.disco.exists(n) for n in nomes))

        self.enviar_disco(jogo, [("verde.nes", NES)])
        nome = jogo.arquivos_emulador.get().pedacos[0]["id"]
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


@override_settings(JOGOS_PEDACOS_DESTINO="cloudinary")
class PedacosNoCloudinaryTests(BaseEmulador):
    """Com o Cloudinary, o pedaço vai assinado para a API dele e só vale a resposta assinada por ele."""

    SEGREDO = "teste-local-sem-rede"  # lazer/settings_test.py

    def resposta_do_cloudinary(self, parte, dados, versao=1700000000):
        assinatura = api_sign_request({"public_id": parte["id"], "version": versao}, self.SEGREDO, signature_version=1)
        return {"public_id": parte["id"], "version": versao, "signature": assinatura, "bytes": len(dados),
                "secure_url": "https://res.cloudinary.com/teste-local/raw/upload/v1/" + parte["id"]}

    def test_cada_pedaco_vai_assinado_e_a_resposta_e_conferida(self):
        _, jogo = self.novo_jogo()
        corpo = self.conferir(jogo, DISCO).json()
        parte = corpo["envios"][0]["partes"][0]
        self.assertEqual(parte["url"], "https://api.cloudinary.com/v1_1/teste-local/raw/upload")
        campos = parte["campos"]
        self.assertEqual(campos["signature"], api_sign_request({"public_id": parte["id"], "timestamp": campos["timestamp"]}, self.SEGREDO))

        dados, respostas, por_url = dict(DISCO), {}, {}
        for envio in corpo["envios"]:
            for p in envio["partes"]:
                pedaco = dados[envio["enviado"]][p["inicio"]:p["fim"]]
                respostas[p["id"]] = self.resposta_do_cloudinary(p, pedaco)
                por_url[respostas[p["id"]]["secure_url"]] = pedaco

        def baixar(url, headers=None, timeout=None):  # o site relê o começo das faixas no Cloudinary
            inicio, fim = (int(x) for x in headers["Range"].split("=")[1].split("-"))
            return mock.Mock(status_code=206, content=por_url[url][inicio:fim + 1], raise_for_status=lambda: None)

        with mock.patch("requests.get", side_effect=baixar):
            resposta = self.confirmar(jogo, corpo, respostas, DISCO)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        faixa = jogo.arquivos_emulador.get(nome="Track 01.bin")
        self.assertTrue(all(p["url"].startswith("https://res.cloudinary.com/") for p in faixa.pedacos))

    def test_resposta_sem_a_assinatura_do_cloudinary_nao_vale(self):
        parte = {"id": "jogos/emulador/x/abc/00-0000.parte"}
        resposta = self.resposta_do_cloudinary(parte, b"1234")
        self.assertEqual(armazenamento_pedacos.conferir_cloudinary(resposta, parte["id"], 4)["tamanho"], 4)
        for campo, valor in (("signature", "x"), ("bytes", 5), ("public_id", "outro")):
            with self.subTest(campo=campo), self.assertRaises(ValueError):
                armazenamento_pedacos.conferir_cloudinary({**resposta, campo: valor}, parte["id"], 4)


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

    def put(self, corpo, arquivos):
        dados = dict(arquivos)
        for envio in corpo["envios"]:
            parte = envio["partes"][0]
            self.balde.objetos[parte["id"]] = dados[envio["enviado"]]

    def test_cada_arquivo_vai_inteiro_ao_balde_e_o_site_confere_no_fim(self):
        _, jogo = self.novo_jogo()
        corpo = self.conferir(jogo, DISCO).json()
        self.assertEqual(corpo["modo"], "grande")
        envios = {e["nome"]: e for e in corpo["envios"]}
        self.assertEqual(sorted(envios), ["Track 01.bin", "Track 02.bin"])
        parte = envios["Track 01.bin"]["partes"][0]
        self.assertEqual((parte["metodo"], parte["fim"]), ("PUT", len(FAIXA_PSX)))
        self.assertTrue(parte["url"].startswith("https://balde.exemplo/enviar/jogos/emulador/corrida-maluca/"))

        falta = self.confirmar(jogo, corpo, {}, DISCO)
        self.assertEqual(falta.status_code, 400)
        self.assertIn("não chegou", falta.json()["msg"])

        corpo = self.conferir(jogo, DISCO).json()
        self.put(corpo, DISCO)
        pronto = self.confirmar(jogo, corpo, {}, DISCO)
        self.assertEqual(pronto.status_code, 200, pronto.content)
        faixa = jogo.arquivos_emulador.get(nome="Track 01.bin")
        self.assertEqual(faixa.url, "https://pub.exemplo/" + faixa.chave)

    def test_o_plano_de_outro_jogo_ou_adulterado_e_recusado(self):
        _, jogo = self.novo_jogo()
        corpo = self.conferir(jogo, [("verde.nes", NES)]).json()
        self.assertEqual(self.confirmar(jogo, {"plano": corpo["plano"] + "x"}, {}, []).status_code, 400)
        outro = JogoCadastrado.objects.create(nome="Outro", slug="outro", sistema="auto", capa="c.png")
        self.assertIn("outro jogo", self.confirmar(outro, corpo, {}, []).json()["msg"])

    def test_chegou_com_outro_tamanho_apaga_e_pede_de_novo(self):
        _, jogo = self.novo_jogo()
        corpo = self.conferir(jogo, [("verde.nes", NES)]).json()
        chave = corpo["envios"][0]["partes"][0]["id"]
        self.balde.objetos[chave] = NES[:100]
        falha = self.confirmar(jogo, corpo, {}, [])
        self.assertIn("outro tamanho", falha.json()["msg"])
        self.assertNotIn(chave, self.balde.objetos)

    def test_balde_sem_acesso_publico_ou_cors_e_avisado(self):
        _, jogo = self.novo_jogo()
        corpo = self.conferir(jogo, [("verde.nes", NES)]).json()
        self.put(corpo, [("verde.nes", NES)])
        self.balde.problemas = ["O balde não deixa o site baixar os arquivos: falta a regra de CORS."]
        pronto = self.confirmar(jogo, corpo, {}, [])
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
