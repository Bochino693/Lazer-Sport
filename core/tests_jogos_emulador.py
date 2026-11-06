"""A análise dos arquivos de um jogo de console (core/jogos_emulador.py) e as páginas do emulador.

O que se garante:
* um disco .cue/.bin só passa completo: cada arquivo que o .cue pede tem de
  vir, e o que falta sai pelo nome; maiúscula e acento não atrapalham, e o
  .cue sai reescrito com os nomes que vieram;
* vários discos sem .m3u ganham o .m3u montado na ordem natural dos nomes;
* o sistema é reconhecido pelo conteúdo (o PlayStation no setor 16 do
  disco, o "NES" do cartucho...), também só com o começo dos arquivos (a
  conferência antes de enviar);
* o que o emulador do site não abre, a BIOS obrigatória que faltou e o
  núcleo de licença não comercial voltam como erro, com o motivo;
* a página do emulador entrega ao EmulatorJS o arquivo que ele abre e cada
  um dos outros com o nome exato; o índice sai do próprio site.
"""
import io
import json
import shutil
import tempfile
import zipfile
from unittest import mock

from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from . import jogos_emulador as emu
from .models import ArquivoEmulador, JogoCadastrado
from .views_jogos import config_do_emulador

LIGADOS = ["psx", "nes", "gb", "gba", "n64", "pce", "nds", "atari2600", "atari7800", "c64",
           "psp", "segaSaturn", "vb", "ngp", "ws", "atari5200", "jaguar", "coleco", "pcfx", "amiga", "dos",
           "c128", "vic20", "plus4", "pet"]
SYNC = b"\x00" + b"\xff" * 10 + b"\x00"


def _bcd(n):
    return ((n // 10) << 4) | (n % 10)


def setor(lba, dados=b"", modo=2):
    m, resto = divmod(lba + 150, 75 * 60)
    s, f = divmod(resto, 75)
    cabeca = SYNC + bytes([_bcd(m), _bcd(s), _bcd(f), modo])
    sub = bytes([0, 0, 8, 0]) * 2 if modo == 2 else b""
    return cabeca + sub + dados.ljust(2048, b"\x00")[:2048] + bytes(2352 - 16 - len(sub) - 2048)


def faixa_de_dados(sistema="psx", setores=20):
    """Uma faixa de dados de CD (2352 bytes por setor) com a assinatura do sistema."""
    saida = bytearray()
    for lba in range(setores):
        dados = b""
        if sistema == "psx" and lba == 16:
            dados = b"\x01CD001\x01\x00" + b"PLAYSTATION".ljust(32)
        if sistema == "segaCD" and lba == 0:
            dados = b"SEGADISCSYSTEM  "
        if sistema == "pce" and lba == 1:
            dados = b"\x00" * 32 + b"PC Engine CD-ROM SYSTEM"
        saida += setor(lba, dados, modo=2 if sistema == "psx" else 1)
    return bytes(saida)


FAIXA_PSX = faixa_de_dados("psx")
AUDIO = bytes(2352 * 10)
CUE = (
    'FILE "Track 01.bin" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n'
    'FILE "Track 02.bin" BINARY\n  TRACK 02 AUDIO\n    INDEX 01 00:02:00\n'
).encode()
NES = b"NES\x1a\x01\x01\x00\x00" + bytes(8) + bytes(16384 + 8192)
GBA = bytes(4) + bytes.fromhex("24FFAE51699AA221") + bytes(0xB2 - 12) + b"\x96" + bytes(1024)
GB = bytes(0x104) + bytes.fromhex("CEED6666CC0D000B") + bytes(1024)
N64 = bytes.fromhex("80371240") + bytes(4096)


def E(nome, dados):
    return emu.entrada_de_arquivo(io.BytesIO(dados), nome)


def analisar(*entradas, sistema="", **kw):
    kw.setdefault("ligados", LIGADOS)
    return emu.analisar(list(entradas), sistema, **kw)


def zipar(**arquivos):
    saida = io.BytesIO()
    with zipfile.ZipFile(saida, "w") as z:
        for nome, dados in arquivos.items():
            z.writestr(nome.replace("__", "."), dados)
    return saida.getvalue()


class DiscoTests(SimpleTestCase):
    def test_o_disco_completo_passa_e_o_sistema_vem_do_conteudo(self):
        an = analisar(E("Jogo.cue", CUE), E("Track 01.bin", FAIXA_PSX), E("Track 02.bin", AUDIO))
        self.assertTrue(an.ok, an.erros)
        self.assertEqual(an.sistema, "psx")
        self.assertEqual(an.como, "cabeçalho")
        self.assertEqual(an.principal.nome, "Jogo.cue")
        self.assertEqual(sorted(p.nome for p in an.pecas if p.papel == "faixa"), ["Track 01.bin", "Track 02.bin"])

    def test_a_faixa_que_falta_sai_pelo_nome(self):
        an = analisar(E("Jogo.cue", CUE), E("Track 01.bin", FAIXA_PSX))
        self.assertFalse(an.ok)
        self.assertTrue(any("Track 02.bin" in e and "não veio" in e for e in an.erros), an.erros)

    def test_maiuscula_e_acento_do_windows_nao_atrapalham(self):
        cue = 'FILE "Café Track 01.BIN" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n'.encode("cp1252")
        an = analisar(E("JOGO.CUE", cue), E("café track 01.bin", FAIXA_PSX))
        self.assertTrue(an.ok, an.erros)
        # o .cue sai em UTF-8, com o nome exato do arquivo que veio
        self.assertIn('FILE "café track 01.bin" BINARY', an.principal.conteudo)

    def test_a_pasta_no_caminho_do_cue_some(self):
        cue = 'FILE "CD1\\Track 01.bin" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n'.encode()
        an = analisar(E("Jogo.cue", cue), E("Track 01.bin", FAIXA_PSX))
        self.assertTrue(an.ok, an.erros)
        self.assertIn('FILE "Track 01.bin" BINARY', an.principal.conteudo)

    def test_varios_discos_sem_m3u_ganham_o_m3u_na_ordem_natural(self):
        cue2 = CUE.replace(b"Track 0", b"D2 Track 0")
        cue10 = CUE.replace(b"Track 0", b"D10 Track 0")
        an = analisar(
            E("Jogo (Disc 10).cue", cue10), E("Jogo (Disc 2).cue", cue2),
            E("D2 Track 01.bin", FAIXA_PSX), E("D2 Track 02.bin", AUDIO),
            E("D10 Track 01.bin", FAIXA_PSX), E("D10 Track 02.bin", AUDIO),
        )
        self.assertTrue(an.ok, an.erros)
        self.assertEqual(an.discos, 2)
        self.assertEqual(an.principal.nome, "jogo.m3u")
        self.assertEqual(an.principal.conteudo, "Jogo (Disc 2).cue\nJogo (Disc 10).cue\n")

    def test_o_m3u_enviado_manda_nos_discos(self):
        m3u = b"Disco B.cue\nDisco A.cue\n"
        cue_a = CUE.replace(b"Track 0", b"A Track 0")
        an = analisar(
            E("jogo.m3u", m3u), E("Disco A.cue", cue_a), E("Disco B.cue", CUE),
            E("A Track 01.bin", FAIXA_PSX), E("A Track 02.bin", AUDIO),
            E("Track 01.bin", FAIXA_PSX), E("Track 02.bin", AUDIO),
        )
        self.assertTrue(an.ok, an.erros)
        self.assertEqual(an.principal.nome, "jogo.m3u")
        discos = {p.nome: p.disco for p in an.pecas if p.papel == "disco"}
        self.assertEqual(discos, {"Disco B.cue": 1, "Disco A.cue": 2})

    def test_o_bin_sozinho_passa_com_aviso_e_varios_sem_cue_nao(self):
        an = analisar(E("Jogo.bin", FAIXA_PSX))
        self.assertTrue(an.ok, an.erros)
        self.assertTrue(any("sem o .cue" in a for a in an.avisos))
        an = analisar(E("Track 01.bin", FAIXA_PSX), E("Track 02.bin", AUDIO))
        self.assertFalse(an.ok)
        self.assertTrue(any("sem o índice" in e for e in an.erros))

    def test_o_clonecd_pede_o_img_e_o_sub_e_opcional(self):
        an = analisar(E("Jogo.ccd", b"[CloneCD]\nVersion=3\n"), E("Jogo.img", FAIXA_PSX))
        self.assertTrue(an.ok, an.erros)
        self.assertEqual(an.sistema, "psx")
        an = analisar(E("Jogo.ccd", b"[CloneCD]\n"), E("Outro.img", FAIXA_PSX))
        self.assertTrue(any("Jogo.img" in e for e in an.erros))

    def test_o_ps1_deste_site_nao_abre_chd(self):
        an = analisar(E("Jogo.chd", b"MComprHD" + bytes(200)), sistema="psx")
        self.assertFalse(an.ok)
        self.assertTrue(any("não abre .chd" in e for e in an.erros))

    def test_pbp_e_reconhecido_como_ps1(self):
        an = analisar(E("Jogo.pbp", b"\x00PBP" + bytes(1024)))
        self.assertTrue(an.ok, an.erros)
        self.assertEqual(an.sistema, "psx")

    def test_dvd_de_ps2_nao_roda(self):
        pvd = bytearray(2048 * 17)
        pvd[16 * 2048: 16 * 2048 + 19] = b"\x01CD001\x01\x00PLAYSTATION"
        grande = emu.entrada_de_trechos("Jogo.iso", 4 * 1024 ** 3, bytes(pvd))
        an = analisar(grande)
        self.assertTrue(any("PlayStation 2" in e for e in an.erros), an.erros)


class NomeComCerquilhaTests(SimpleTestCase):
    def test_o_jogo_gravaria_com_o_nome_errado_entao_pede_para_renomear(self):
        an = analisar(E("Jogo #1.nes", NES))
        self.assertFalse(an.ok)
        self.assertTrue(any("renomeie" in e for e in an.erros), an.erros)


class CartuchoTests(SimpleTestCase):
    def test_cada_cartucho_pelo_cabecalho(self):
        for nome, dados, sistema in (
            ("a.nes", NES, "nes"), ("a.gba", GBA, "gba"), ("a.gb", GB, "gb"), ("a.z64", N64, "n64"),
        ):
            with self.subTest(nome=nome):
                an = analisar(E(nome, dados))
                self.assertTrue(an.ok, an.erros)
                self.assertEqual((an.sistema, an.como), (sistema, "cabeçalho"))

    def test_o_cabecalho_vale_mais_que_a_extensao_trocada(self):
        an = analisar(E("jogo.gbc", NES))
        self.assertEqual(an.detectado, "nes")

    def test_o_sistema_escolhido_errado_avisa_e_o_formato_que_nao_abre_e_erro(self):
        an = analisar(E("verde.nes", NES), sistema="psx")
        self.assertFalse(an.ok)
        self.assertTrue(any("parecem de NES" in a for a in an.avisos))
        self.assertTrue(any("não abre .nes" in e for e in an.erros))

    def test_zip_pelo_que_tem_dentro(self):
        an = analisar(E("jogo.zip", zipar(jogo__nes=NES)))
        self.assertEqual(an.sistema, "nes")
        an = analisar(E("sf2.zip", zipar(**{"sf2_09__bin": b"x", "sf2_18__11c": b"y"})))
        self.assertEqual(an.detectado, "arcade")
        self.assertTrue(any("licença" in e for e in an.erros))
        an = analisar(E("disco.zip", zipar(jogo__cue=CUE, **{"Track 01__bin": FAIXA_PSX})))
        self.assertIsNone(an.sistema)
        self.assertTrue(any("escolha na lista" in e for e in an.erros))


class ConjuntoTests(SimpleTestCase):
    def test_dois_jogos_formato_estranho_repetido_e_o_que_fica_de_fora(self):
        self.assertTrue(any("um jogo por vez" in e for e in analisar(E("a.nes", NES), E("b.nes", NES)).erros))
        self.assertTrue(any(".exe" in e for e in analisar(E("a.nes", NES), E("setup.exe", b"MZ")).erros))
        self.assertTrue(any("duas vezes" in e for e in analisar(E("a.nes", NES), E("A.NES", NES)).erros))
        an = analisar(E("a.nes", NES), E("leia-me.txt", b"oi"), E("capa.jpg", b"jpg"))
        self.assertTrue(an.ok, an.erros)
        self.assertEqual(sorted(an.ignorados), ["capa.jpg", "leia-me.txt"])

    def test_a_faixa_que_nenhum_indice_pede_fica_de_fora(self):
        an = analisar(E("Jogo.cue", CUE), E("Track 01.bin", FAIXA_PSX), E("Track 02.bin", AUDIO), E("Track 09.bin", AUDIO))
        self.assertTrue(an.ok, an.erros)
        self.assertIn("Track 09.bin", an.ignorados)
        self.assertNotIn("Track 09.bin", [p.nome for p in an.pecas])

    def test_limite_do_armazenamento_por_arquivo(self):
        an = analisar(E("Jogo.cue", CUE), E("Track 01.bin", FAIXA_PSX), E("Track 02.bin", AUDIO), limite_por_arquivo=10_000)
        self.assertFalse(an.ok)
        self.assertTrue(any("Track 01.bin" in e and "até" in e for e in an.erros), an.erros)

    def test_so_o_comeco_dos_arquivos_basta_para_conferir(self):
        an = analisar(
            emu.entrada_de_trechos("Jogo.cue", len(CUE), CUE),
            emu.entrada_de_trechos("Track 01.bin", 700 * 1024 * 1024, FAIXA_PSX[: emu.CABECA]),
            emu.entrada_de_trechos("Track 02.bin", 50 * 1024 * 1024),
        )
        self.assertTrue(an.ok, an.erros)
        self.assertEqual(an.sistema, "psx")


class BiosELicencaTests(SimpleTestCase):
    def test_sega_cd_e_reconhecido_mas_a_licenca_nao_deixa(self):
        cue = CUE.split(b"FILE \"Track 02")[0].replace(b"MODE2", b"MODE1")
        an = analisar(E("Jogo.cue", cue), E("Track 01.bin", faixa_de_dados("segaCD")))
        self.assertEqual(an.sistema, "segaCD")
        self.assertTrue(any("licença" in e for e in an.erros))

    def test_com_a_permissao_o_sega_cd_pede_a_bios_e_aceita_com_o_nome_oficial(self):
        cue = CUE.split(b"FILE \"Track 02")[0].replace(b"MODE2", b"MODE1")
        ligados = LIGADOS + ["segaCD"]
        an = analisar(E("Jogo.cue", cue), E("Track 01.bin", faixa_de_dados("segaCD")), ligados=ligados)
        self.assertTrue(any("bios_CD_U.bin" in e for e in an.erros), an.erros)
        an = analisar(E("Jogo.cue", cue), E("Track 01.bin", faixa_de_dados("segaCD")), E("BIOS_cd_u.BIN", b"bios"), ligados=ligados)
        self.assertTrue(an.ok, an.erros)
        self.assertEqual([p.nome for p in an.pecas if p.papel == "bios"], ["bios_CD_U.bin"])

    def test_pc_engine_cartucho_sem_bios_e_o_cd_com(self):
        self.assertTrue(analisar(E("jogo.pce", bytes(4096))).ok)
        cue = CUE.split(b"FILE \"Track 02")[0].replace(b"MODE2", b"MODE1")
        an = analisar(E("Jogo.cue", cue), E("Track 01.bin", faixa_de_dados("pce")))
        self.assertEqual(an.sistema, "pce")
        self.assertTrue(any("syscard3.pce" in e for e in an.erros), an.erros)
        an = analisar(E("Jogo.cue", cue), E("Track 01.bin", faixa_de_dados("pce")), E("syscard3.pce", b"bios"))
        self.assertTrue(an.ok, an.erros)

    @override_settings(JOGOS_EMULADORES_NAO_COMERCIAIS="snes, segaMD")
    def test_os_nao_comerciais_so_com_a_configuracao(self):
        self.assertIn("snes", emu.sistemas_ligados())
        self.assertIn("segaMD", emu.sistemas_ligados())
        self.assertNotIn("arcade", emu.sistemas_ligados())

    def test_por_padrao_so_os_de_licenca_livre(self):
        self.assertEqual(sorted(emu.sistemas_ligados()), sorted(LIGADOS))


class EmuladorNoSiteTests(TestCase):
    """A página do quadro e o índice servido pelo site."""

    def setUp(self):
        pasta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, pasta, ignore_errors=True)
        self.disco = FileSystemStorage(location=pasta, base_url="/media/")
        for modelo, campo in ((JogoCadastrado, "capa"), (ArquivoEmulador, "arquivo")):
            trocar = mock.patch.object(modelo._meta.get_field(campo), "storage", self.disco)
            trocar.start()
            self.addCleanup(trocar.stop)
        self.jogo = JogoCadastrado.objects.create(nome="Disco Teste", slug="disco-teste", sistema="psx", capa="capa.png", cor="#22d3ee")
        an = analisar(E("Jogo (Disc 1).cue", CUE), E("Track 01.bin", FAIXA_PSX), E("Track 02.bin", AUDIO))
        for ordem, peca in enumerate(an.pecas):
            registro = ArquivoEmulador(jogo=self.jogo, nome=peca.nome, papel=peca.papel, tamanho=peca.entrada.tamanho, lote="abc", ordem=ordem)
            if peca.conteudo is not None:
                registro.conteudo = peca.conteudo
            else:
                # o armazenamento pode guardar com outro nome: o emulador recebe pelo `nome`
                registro.arquivo.save("guardado_" + peca.nome, ContentFile(peca.entrada.pedaco(0, peca.entrada.tamanho)), save=False)
            registro.save()

    def config(self, resposta):
        html = resposta.content.decode()
        inicio = html.index('<script id="emuladorConfig" type="application/json">') + len('<script id="emuladorConfig" type="application/json">')
        return json.loads(html[inicio: html.index("</script>", inicio)])

    def test_a_pagina_do_quadro_entrega_cada_arquivo_com_o_nome_exato(self):
        resposta = self.client.get(reverse("jogo_emulador", args=["disco-teste"]))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta["X-Frame-Options"], "SAMEORIGIN")
        config = self.config(resposta)
        self.assertEqual(config["core"], "psx")
        arquivos = {a["caminho"]: a for a in config["arquivos"]}
        self.assertEqual(sorted(arquivos), ["/Jogo (Disc 1).cue", "/Track 01.bin", "/Track 02.bin"])
        principal = arquivos["/Jogo (Disc 1).cue"]
        self.assertTrue(principal["principal"])
        # o índice leva a versão: o jogo guardado no aparelho nunca abre o índice velho
        self.assertTrue(principal["partes"][0].startswith(reverse("jogo_emulador_arquivo", args=["disco-teste", "Jogo (Disc 1).cue"]) + "?v="))
        self.assertEqual(config["jogo"], "disco-teste")
        self.assertIn("guardado_Track", arquivos["/Track 01.bin"]["partes"][0])
        self.assertEqual(arquivos["/Track 01.bin"]["tamanho"], len(FAIXA_PSX))
        # o jogo salvo leva o nome do jogo no site (único), com a extensão do que o emulador abre
        self.assertEqual(config["nome"], "disco-teste.cue")
        self.assertTrue(config["dados"].endswith("vendor/emulatorjs/data/"))
        self.assertContains(resposta, "jogo-emulador.js")
        self.assertContains(resposta, "jogo-guardado.js")

    def test_arquivo_em_pedacos_vai_com_as_partes_na_ordem(self):
        faixa = self.jogo.arquivos_emulador.get(nome="Track 01.bin")
        faixa.arquivo = ""
        faixa.pedacos = [{"url": "https://res.cloudinary.com/x/a", "tamanho": 50000, "id": "a"},
                         {"url": "https://res.cloudinary.com/x/b", "tamanho": len(FAIXA_PSX) - 50000, "id": "b"}]
        faixa.save()
        config = config_do_emulador(JogoCadastrado.objects.get(pk=self.jogo.pk))
        item = next(a for a in config["arquivos"] if a["nome"] == "Track 01.bin")
        self.assertEqual(item["partes"], ["https://res.cloudinary.com/x/a", "https://res.cloudinary.com/x/b"])
        self.assertEqual(item["tamanho"], len(FAIXA_PSX))

    def test_o_indice_sai_do_site_e_o_resto_nao(self):
        url = reverse("jogo_emulador_arquivo", args=["disco-teste", "Jogo (Disc 1).cue"])
        resposta = self.client.get(url)
        self.assertEqual(resposta.status_code, 200)
        self.assertIn(b'FILE "Track 01.bin" BINARY', resposta.content)
        self.assertEqual(self.client.head(url).status_code, 200)  # o emulador pede HEAD antes
        self.assertEqual(self.client.get(reverse("jogo_emulador_arquivo", args=["disco-teste", "Track 01.bin"])).status_code, 404)

    def test_o_jogo_aparece_no_simulador_e_a_pagina_abre_o_quadro_do_emulador(self):
        lista = self.client.get(reverse("jogos"))
        self.assertContains(lista, "Disco Teste")
        pagina = self.client.get(reverse("jogo", args=["disco-teste"]))
        self.assertContains(pagina, 'data-jogo-src="/jogos/disco-teste/emulador/"')
        self.assertContains(pagina, 'data-jogo-emulador="1"')
        self.assertContains(pagina, "PlayStation (PS1)")
        # jogo na hora: a página já traz o que guardar no aparelho e pré-carrega o núcleo
        self.assertContains(pagina, 'id="jogoArquivos"')
        self.assertContains(pagina, "jogo-guardado.js")
        self.assertContains(pagina, '"nucleo": "pcsx_rearmed"')
        self.assertContains(pagina, "data-jogo-preparo")

    def test_desligado_sem_arquivos_ou_sistema_sem_licenca_fica_fora(self):
        url = reverse("jogo_emulador", args=["disco-teste"])
        JogoCadastrado.objects.filter(pk=self.jogo.pk).update(ativo=False)
        self.assertEqual(self.client.get(url).status_code, 404)
        JogoCadastrado.objects.filter(pk=self.jogo.pk).update(ativo=True, sistema="snes")
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertNotContains(self.client.get(reverse("jogos")), "Disco Teste")  # nem aparece na lista
        JogoCadastrado.objects.filter(pk=self.jogo.pk).update(sistema="psx")
        self.jogo.arquivos_emulador.all().delete()
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertNotContains(self.client.get(reverse("jogos")), "Disco Teste")

    def test_a_pagina_ensina_os_comandos_no_computador_e_no_celular(self):
        pagina = self.client.get(reverse("jogo", args=["disco-teste"]))
        html = pagina.content.decode()
        self.assertIn("No computador", html)
        self.assertIn("No celular", html)
        # o ✕ do PlayStation é a tecla X; o △, a tecla A (o mapa do próprio emulador)
        # o botão, o que ele FAZ e a tecla
        # o botão, o ícone e o que ele FAZ, e a tecla
        self.assertIn('<li class="jc-tecla"><span>✕</span><em class="jc-funcao"><svg class="jc-ico" aria-hidden="true">'
                      '<use href="#a-confirmar"/></svg>Confirmar e ação principal</em><div><kbd>X</kbd></div></li>', html)
        self.assertIn('<use href="#a-atacar"/></svg>Ação 3 (atacar, usar)</em><div><kbd>S</kbd></div></li>', html)
        self.assertIn('<symbol id="a-pular"', html)  # os desenhos vão junto com a página
        # e no controle de Xbox: o ✕ no botão de baixo (A)
        self.assertIn('<kbd class="jc-xb jc-xb-a">A</kbd>', html)
        self.assertIn("Controle de Xbox", html)
        self.assertIn("o controle do PlayStation (PS1)", html)
        # e o botão "Comandos" sobre o jogo, que vale em tela cheia
        self.assertIn("data-jogo-comandos-botao", html)
        self.assertIn("um controle Bluetooth", html)
        self.assertNotIn("{#", html)  # comentário de template de várias linhas vaza como texto

    def test_no_portal_o_jogo_vai_para_os_consoles_e_o_filtro_playstation(self):
        portal = self.client.get(reverse("jogos"))
        estantes = {e["chave"]: [j["slug"] for j in e["jogos"]] for e in portal.context["estantes"]}
        self.assertEqual(estantes["playstation"], ["disco-teste"])
        self.assertNotIn("disco-teste", estantes["nosso"])
        self.assertContains(portal, '<span class="bj-sigla">PS1</span>')
        # a ficha da biblioteca ensina os comandos do PS1, tecla por tecla
        controles = portal.context["dados_da_biblioteca"]["controles"]["psx"]
        self.assertIn({"acao": "✕", "funcao": "Confirmar e ação principal", "do_jogo": False, "icone": "confirmar",
                       "teclas": ["X"], "celular": "✕, à direita", "controle": ["A"]}, controles)

    def test_o_super_nintendo_leva_o_endereco_do_nucleo_e_a_qualidade(self):
        JogoCadastrado.objects.filter(pk=self.jogo.pk).update(sistema="snes", particular=True)
        config = config_do_emulador(JogoCadastrado.objects.get(pk=self.jogo.pk))
        self.assertEqual(config["nucleo"], "snes9x")
        self.assertTrue(config["nucleoExterno"].startswith("https://cdn.jsdelivr.net/npm/@emulatorjs/core-snes9x@"))
        # no celular o filtro leve; no computador o SABR, mais caprichado
        self.assertEqual(config["opcoes"]["shader"], "2xScaleHQ.glslp")
        self.assertEqual(config["opcoesNoComputador"]["shader"], "sabr")
        JogoCadastrado.objects.filter(pk=self.jogo.pk).update(sistema="psx")
        self.assertEqual(config_do_emulador(JogoCadastrado.objects.get(pk=self.jogo.pk))["nucleoExterno"], "")

    def test_psp_e_dos_abrem_na_pagina_isolada_e_os_outros_no_quadro(self):
        url = reverse("jogo_emulador", args=["disco-teste"])
        normal = self.client.get(url)
        self.assertNotIn("Cross-Origin-Embedder-Policy", normal)
        self.assertFalse(self.config(normal)["threads"])
        JogoCadastrado.objects.filter(pk=self.jogo.pk).update(sistema="psp")
        isolada = self.client.get(url)
        self.assertEqual(isolada["Cross-Origin-Opener-Policy"], "same-origin")
        self.assertEqual(isolada["Cross-Origin-Embedder-Policy"], "require-corp")
        config = self.config(isolada)
        self.assertTrue(config["threads"])
        self.assertEqual(config["voltar"], reverse("jogo", args=["disco-teste"]))
        # o reprodutor: Voltar, Comandos e Tela cheia por cima do jogo
        self.assertContains(isolada, "data-pl-voltar")
        self.assertContains(isolada, "data-pl-tela-cheia")
        self.assertContains(isolada, "Controle Xbox")
        pagina = self.client.get(reverse("jogo", args=["disco-teste"]))
        self.assertContains(pagina, 'data-jogo-tela-propria="1"')
        # o adiantamento do núcleo pede o de várias linhas e os arquivos de apoio do PPSSPP
        self.assertContains(pagina, '"threads": true')
        self.assertContains(pagina, "cores/ppsspp-assets.zip")
        self.assertContains(pagina, "PlayStation Portable (PSP)")

    def test_o_jogo_particular_so_a_equipe_ve_e_roda_qualquer_console(self):
        from django.contrib.auth.models import User

        from .tests_ranking import _cliente

        # Super Nintendo: no site aberto não liga; no particular, roda -- só para a equipe
        JogoCadastrado.objects.filter(pk=self.jogo.pk).update(particular=True, sistema="snes")
        emulador = reverse("jogo_emulador", args=["disco-teste"])
        pagina = reverse("jogo", args=["disco-teste"])
        self.assertEqual(self.client.get(emulador).status_code, 404)
        self.assertEqual(self.client.get(pagina).status_code, 404)
        self.assertNotContains(self.client.get(reverse("jogos")), "Disco Teste")
        self.client.force_login(_cliente("cliente", "cliente@exemplo.com"))
        self.assertEqual(self.client.get(emulador).status_code, 404)  # conta de cliente não basta
        equipe = User.objects.create_superuser("chefe", "chefe@exemplo.com", "x")
        self.client.force_login(equipe)
        resposta = self.client.get(pagina)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Jogo particular")
        self.assertEqual(resposta["X-Robots-Tag"], "noindex, nofollow")
        self.assertIn("no-store", resposta["Cache-Control"])
        self.assertEqual(self.config(self.client.get(emulador))["core"], "snes")
        self.assertNotContains(self.client.get(reverse("jogos")), "Disco Teste")  # nem para a equipe, no portal

    def test_so_o_n64_troca_as_teclas_do_emulador(self):
        normal = config_do_emulador(JogoCadastrado.objects.get(pk=self.jogo.pk))["controles"]["0"]
        self.assertEqual(normal["4"]["value"], "up arrow")  # nos outros, as setas são a cruz
        # o controle de Xbox pela posição: o botão de baixo (A) é o de baixo do console
        self.assertEqual(normal["0"]["value2"], "BUTTON_1")
        self.assertEqual(normal["8"]["value2"], "BUTTON_2")
        JogoCadastrado.objects.filter(pk=self.jogo.pk).update(sistema="n64")
        controles = config_do_emulador(JogoCadastrado.objects.get(pk=self.jogo.pk))["controles"]
        jogador = controles["0"]
        # o analógico nas setas, a cruz em T/F/G/H
        self.assertEqual(jogador["16"], {"value": "right arrow", "value2": "LEFT_STICK_X:+1"})
        self.assertEqual(jogador["19"]["value"], "up arrow")
        self.assertEqual(jogador["4"]["value"], "t")
        self.assertEqual(jogador["0"]["value"], "x")  # o A do N64
        # o que a página ensina bate com o que o emulador recebe
        n64 = {c["acao"]: c["teclas"] for c in emu.controles_do_sistema("n64")}
        self.assertEqual(n64["Analógico"], ["←", "↑", "→", "↓"])
        self.assertEqual(n64["Direcional (cruz)"], ["T", "F", "G", "H"])


class ConsolesDeLicencaLivreTests(TestCase):
    """DS, Atari 2600, Atari 7800 e Commodore 64: núcleos GPL, que moram no site."""

    def test_cada_um_e_reconhecido_pela_extensao_e_tem_o_nucleo_aqui(self):
        from django.contrib.staticfiles import finders
        for nome, sistema in (("jogo.nds", "nds"), ("jogo.a26", "atari2600"), ("jogo.a78", "atari7800"),
                              ("jogo.d64", "c64"), ("jogo.prg", "c64")):
            with self.subTest(arquivo=nome):
                an = analisar(E(nome, bytes(4096)))
                self.assertEqual(an.sistema, sistema, an.erros)
                self.assertTrue(an.ok, an.erros)
                nucleo = emu.SISTEMAS[sistema].nucleo
                self.assertTrue(finders.find(f"vendor/emulatorjs/data/cores/{nucleo}-wasm.data"))
                self.assertTrue(finders.find(f"vendor/emulatorjs/data/cores/{nucleo}-legacy-wasm.data"))

    def test_super_nintendo_explica_o_motivo_e_o_que_fazer(self):
        an = analisar(E("jogo.sfc", bytes(4096)))
        self.assertFalse(an.ok)
        erro = " ".join(an.erros)
        self.assertIn("permissão dos autores", erro)
        self.assertIn("JOGOS_EMULADORES_NAO_COMERCIAIS=snes", erro)


def _iso_de_psp(tamanho_real=None, com_id=True):
    """Um .iso de PSP: o descritor do volume ("PSP GAME") e a pasta PSP_GAME na raiz."""
    dados = bytearray(2048 * 24)
    pvd = bytearray(2048)
    pvd[0:8] = b"\x01CD001\x01\x00"
    if com_id:
        pvd[8:16] = b"PSP GAME"
    pvd[158:162] = (22).to_bytes(4, "little")
    dados[16 * 2048: 17 * 2048] = pvd
    dados[22 * 2048 + 33: 22 * 2048 + 41] = b"PSP_GAME"
    if tamanho_real:
        return emu.entrada_de_trechos("Jogo.iso", tamanho_real, bytes(dados))
    return E("Jogo.iso", bytes(dados))


def _pbp(categoria):
    """Um EBOOT.PBP com o PARAM.SFO dizendo a categoria (ME = PS1; MG = PSP)."""
    chave = b"CATEGORY\x00\x00\x00\x00"
    valor = categoria.encode() + b"\x00\x00"
    sfo = bytearray(b"\x00PSF" + (0x101).to_bytes(4, "little"))
    sfo += (20 + 16).to_bytes(4, "little") + (20 + 16 + len(chave)).to_bytes(4, "little") + (1).to_bytes(4, "little")
    sfo += (0).to_bytes(2, "little") + (0x0204).to_bytes(2, "little") + len(valor).to_bytes(4, "little")
    sfo += len(valor).to_bytes(4, "little") + (0).to_bytes(4, "little")
    sfo += chave + valor
    deslocs = [40, 40 + len(sfo)] + [40 + len(sfo)] * 6
    return b"\x00PBP" + (0x10000).to_bytes(4, "little") + b"".join(d.to_bytes(4, "little") for d in deslocs) + bytes(sfo) + bytes(256)


def _exe(windows):
    """O começo de um .exe: MZ puro (MS-DOS) ou MZ + PE (Windows)."""
    dados = bytearray(1024)
    dados[0:2] = b"MZ"
    if windows:
        dados[0x3C:0x40] = (0x80).to_bytes(4, "little")
        dados[0x80:0x84] = b"PE\x00\x00"
    return bytes(dados)


class MaisConsolesTests(SimpleTestCase):
    """PSP, Saturn, Virtual Boy, Neo Geo Pocket, WonderSwan, Atari 5200/Jaguar, ColecoVision, PC-FX, Amiga, DOS e Commodore."""

    def test_cada_um_e_reconhecido_e_o_nucleo_mora_no_site(self):
        from django.contrib.staticfiles import finders
        for nome, sistema in (("jogo.cso", "psp"), ("jogo.vb", "vb"), ("jogo.ngc", "ngp"), ("jogo.wsc", "ws"),
                              ("jogo.a52", "atari5200"), ("jogo.j64", "jaguar"), ("jogo.adf", "amiga"), ("jogo.com", "dos")):
            with self.subTest(arquivo=nome):
                dados = b"CISO" + bytes(4096) if nome.endswith(".cso") else bytes(4096)
                an = analisar(E(nome, dados))
                self.assertEqual(an.sistema, sistema, an.erros)
                self.assertTrue(an.ok, an.erros)
        for codigo, sistema in emu.SISTEMAS.items():
            if not sistema.uso_comercial:
                continue
            with self.subTest(nucleo=sistema.nucleo):
                variante = "-thread" if sistema.threads else ""
                self.assertTrue(finders.find(f"vendor/emulatorjs/data/cores/{sistema.nucleo}{variante}-wasm.data"), codigo)
                self.assertTrue(finders.find(f"vendor/emulatorjs/data/cores/reports/{sistema.nucleo}.json"), codigo)
        self.assertTrue(finders.find("vendor/emulatorjs/data/cores/ppsspp-assets.zip"))

    def test_o_iso_de_psp_pelo_disco_inclusive_o_grande(self):
        an = analisar(_iso_de_psp())
        self.assertEqual(an.sistema, "psp", an.erros)
        self.assertTrue(an.ok, an.erros)
        # 1,5 GB: maior que um CD -- não é PS2, é UMD de PSP (só a cabeça foi lida)
        an = analisar(_iso_de_psp(1500 * 1024 * 1024))
        self.assertEqual(an.sistema, "psp", an.erros)
        self.assertTrue(any("Jogo grande" in a for a in an.avisos), an.avisos)
        # sem o "PSP GAME" no descritor, a pasta PSP_GAME basta
        self.assertEqual(analisar(_iso_de_psp(com_id=False)).sistema, "psp")

    def test_o_eboot_pbp_do_ps1_e_o_do_psp(self):
        self.assertEqual(analisar(E("EBOOT.PBP", _pbp("ME"))).sistema, "psx")
        self.assertEqual(analisar(E("EBOOT.PBP", _pbp("MG"))).sistema, "psp")
        self.assertEqual(analisar(E("EBOOT.PBP", _pbp("UG"))).sistema, "psp")

    def test_o_saturn_pelo_disco(self):
        faixa = setor(0, b"SEGA SEGASATURN ", modo=1) + b"".join(setor(i, modo=1) for i in range(1, 20))
        cue = CUE.split(b"FILE \"Track 02")[0].replace(b"MODE2", b"MODE1")
        an = analisar(E("Jogo.cue", cue), E("Track 01.bin", faixa))
        self.assertEqual(an.sistema, "segaSaturn")
        self.assertTrue(an.ok, an.erros)

    def test_dos_zipado_ou_solto_e_windows_recusado_com_o_motivo(self):
        an = analisar(E("jogo.zip", zipar(JOGO__EXE=_exe(False), DADOS__DAT=b"x")))
        self.assertEqual(an.sistema, "dos", an.erros)
        self.assertTrue(an.ok, an.erros)
        self.assertTrue(analisar(E("JOGO.EXE", _exe(False))).ok)
        for an in (analisar(E("jogo.exe", _exe(True))), analisar(E("jogo.zip", zipar(JOGO__EXE=_exe(True)))),
                   analisar(E("jogo.zip", zipar(JOGO__EXE=_exe(False), SDL__DLL=b"x")))):
            self.assertFalse(an.ok)
            erro = " ".join(an.erros)
            self.assertIn("programa de Windows", erro)
            self.assertIn("TeknoParrot", erro)

    def test_o_arcade_zipado_continua_arcade(self):
        an = analisar(E("sf2.zip", zipar(sf2_1__bin=b"x", sf2_2__bin=b"y")))
        self.assertEqual(an.detectado, "arcade")

    def test_o_que_nao_roda_no_navegador_diz_o_motivo(self):
        for nome, console in (("jogo.wbfs", "Wii"), ("jogo.nsp", "Switch"), ("jogo.3ds", "3DS"), ("jogo.rvz", "GameCube")):
            with self.subTest(arquivo=nome):
                an = analisar(E(nome, bytes(64)))
                self.assertFalse(an.ok)
                self.assertTrue(any(console in e and "navegador" in e for e in an.erros), an.erros)
        gamecube = bytearray(4096)
        gamecube[0x1C:0x20] = bytes.fromhex("C2339F3D")
        an = analisar(emu.entrada_de_trechos("Jogo.iso", 1400 * 1024 * 1024, bytes(gamecube)))
        self.assertTrue(any("GameCube" in e for e in an.erros), an.erros)

    def test_acima_de_2_gb_nenhum_navegador_abre(self):
        an = analisar(emu.entrada_de_trechos("Jogo.cso", 5 * 1024 ** 3, b"CISO" + bytes(1024)))
        self.assertFalse(an.ok)
        self.assertTrue(any("nenhum navegador" in e for e in an.erros), an.erros)

    def test_os_commodore_irmaos_do_c64_so_pela_lista(self):
        self.assertEqual(analisar(E("jogo.d64", bytes(4096))).sistema, "c64")
        an = analisar(E("jogo.d64", bytes(4096)), sistema="c128")
        self.assertTrue(an.ok, an.erros)
        self.assertEqual(an.sistema, "c128")

    def test_colecovision_pede_a_bios(self):
        self.assertTrue(any("colecovision.rom" in e for e in analisar(E("jogo.col", bytes(4096))).erros))
        self.assertTrue(analisar(E("jogo.col", bytes(4096)), E("colecovision.rom", bytes(8192))).ok)

    def test_cada_console_ligado_ensina_os_comandos_e_o_psp_tem_o_analogico_nas_setas(self):
        for codigo in emu.sistemas_ligados():
            with self.subTest(sistema=codigo):
                self.assertTrue(emu.controles_do_sistema(codigo), codigo)
        psp = emu.controles_do_emulador("psp")["0"]
        self.assertEqual(psp["16"]["value"], "right arrow")
        self.assertEqual(psp["4"]["value"], "t")
        teclas = {c["acao"]: c["teclas"] for c in emu.controles_do_sistema("psp")}
        self.assertEqual(teclas["✕"], ["X"])
        self.assertEqual(teclas["Analógico"], ["←", "↑", "→", "↓"])


class ParticularTests(SimpleTestCase):
    def test_no_particular_rodam_todos_os_reconhecidos(self):
        self.assertEqual(sorted(emu.sistemas_para(True)), sorted(emu.SISTEMAS))
        an = emu.analisar([E("jogo.sfc", bytes(4096))], "", ligados=emu.sistemas_para(True))
        self.assertTrue(an.ok, an.erros)
        self.assertEqual(an.sistema, "snes")
        fora = analisar(E("jogo.sfc", bytes(4096)), ligados=emu.sistemas_ligados())
        self.assertTrue(any("Particular" in e for e in fora.erros), fora.erros)

    def test_o_envio_sabe_quando_e_particular(self):
        from .emulador_envio import particular_pedido

        self.assertTrue(particular_pedido(None, {"particular": "1"}))
        self.assertFalse(particular_pedido(None, {}))
        self.assertTrue(particular_pedido(JogoCadastrado(particular=True), {}))

    def test_o_dos_recebe_o_nome_no_padrao_8_3(self):
        from .views_jogos import _nome_do_dos

        self.assertEqual(_nome_do_dos("LAZER.COM"), "LAZER.COM")
        self.assertEqual(_nome_do_dos("Meu Jogo 2025.exe"), "MEUJOGO2.EXE")
        self.assertEqual(_nome_do_dos("pasta-do-jogo.zip"), "PASTADOJ.ZIP")
        self.assertEqual(_nome_do_dos("çãé.bat"), "JOGO.BAT")

    def test_pecas_soltas_de_fliperama_pedem_a_pasta_ou_o_zip(self):
        an = analisar(E("pm1.ic2", b"x" * 64), E("pm2.ic3", b"y" * 64), E("pacman.6e", b"z" * 64))
        self.assertFalse(an.ok)
        erro = " ".join(an.erros)
        self.assertIn("peças (chips) de um jogo de fliperama", erro)
        self.assertIn("pacman.zip", erro)
        # o .zip que o painel monta com a pasta: fliperama (e roda no particular)
        zipado = E("pacman.zip", zipar(pm1__ic2=b"x" * 64, pm2__ic3=b"y" * 64, pacman__6e=b"z" * 64))
        an = emu.analisar([zipado], "", ligados=emu.sistemas_para(True))
        self.assertEqual(an.sistema, "arcade")
        self.assertTrue(an.ok, an.erros)
        an = emu.analisar([E("pacman.zip", zipar(pm1__ic2=b"x"))], "mame", ligados=emu.sistemas_para(True))
        self.assertTrue(an.ok, an.erros)

    def test_fliperama_de_pc_explica_que_e_do_teknoparrot(self):
        grande = emu.entrada_de_trechos("pacmanbr.zip", 1060 * 1024 * 1024, zipar(a__bin=b"x", b__bin=b"y"))
        an = emu.analisar([grande], "arcade", ligados=emu.sistemas_para(True))
        self.assertFalse(an.ok)
        self.assertTrue(any("TeknoParrot" in e and "baseado em PC" in e for e in an.erros), an.erros)

    def test_pokemon_mini_diz_por_que_nao_roda(self):
        an = analisar(E("jogo.min", bytes(512)))
        self.assertFalse(an.ok)
        self.assertTrue(any("Pokémon Mini" in e for e in an.erros), an.erros)


def _rom_snes(copiadora=False, soma_certa=True):
    """Uma ROM LoROM de 512 KB com o cabeçalho interno do Super Nintendo em 0x7FC0."""
    rom = bytearray(512 * 1024)
    rom[0x7FC0:0x7FC0 + 21] = b"SUPER MARIOWORLD".ljust(21)
    rom[0x7FD5] = 0x20  # LoROM
    soma = 0x1234 if soma_certa else 0x1111
    complemento = soma ^ 0xFFFF if soma_certa else 0x2222
    rom[0x7FDC:0x7FE0] = bytes([complemento & 0xFF, complemento >> 8, soma & 0xFF, soma >> 8])
    return (bytes(512) if copiadora else b"") + bytes(rom)


class FichaDoArquivoTests(SimpleTestCase):
    """O painel diz o que o cabeçalho do jogo diz: é o que ajuda a achar o problema."""

    def test_super_nintendo_titulo_mapa_copiadora_e_soma(self):
        an = emu.analisar([E("mario.smc", _rom_snes(copiadora=True))], "", ligados=emu.sistemas_para(True))
        self.assertEqual(an.sistema, "snes")
        ficha = " ".join(an.ficha)
        self.assertIn("“SUPER MARIOWORLD”", ficha)
        self.assertIn("LoROM", ficha)
        self.assertIn("copiadora de 512 bytes", ficha)
        self.assertIn("Soma de verificação certa", ficha)
        an = emu.analisar([E("mario-hack.sfc", _rom_snes(soma_certa=False))], "snes", ligados=emu.sistemas_para(True))
        self.assertIn("não bate", " ".join(an.ficha))
        self.assertIn("ficha", an.para_json())

    def test_mega_drive_titulo_e_regiao_e_o_smd(self):
        rom = bytearray(256 * 1024)
        rom[0x100:0x110] = b"SEGA MEGA DRIVE "
        rom[0x150:0x150 + 20] = b"SONIC THE HEDGEHOG  "
        rom[0x1F0:0x1F3] = b"JUE"
        an = emu.analisar([E("sonic.md", bytes(rom))], "", ligados=emu.sistemas_para(True))
        self.assertEqual(an.sistema, "segaMD")
        ficha = " ".join(an.ficha)
        self.assertIn("“SONIC THE HEDGEHOG”", ficha)
        self.assertIn("Japão, EUA, Europa", ficha)
        smd = emu.analisar([E("sonic.smd", bytes(512) + bytes(16384 * 4))], "segaMD", ligados=emu.sistemas_para(True))
        self.assertIn(".smd", " ".join(smd.ficha))

    def test_nes_mostra_o_mapper(self):
        self.assertIn("mapper 0", " ".join(analisar(E("jogo.nes", NES)).ficha))


class NucleoEQualidadeTests(SimpleTestCase):
    def test_o_nucleo_que_nao_mora_no_site_vem_do_pacote_oficial(self):
        self.assertEqual(emu.origem_do_nucleo("snes"), "https://cdn.jsdelivr.net/npm/@emulatorjs/core-snes9x@4.2.3/")
        self.assertEqual(emu.origem_do_nucleo("segaMD"), "https://cdn.jsdelivr.net/npm/@emulatorjs/core-genesis_plus_gx@4.2.3/")
        self.assertEqual(emu.origem_do_nucleo("psx"), "")  # mora no site

    def test_filtro_de_imagem_e_o_nucleo_certo(self):
        self.assertEqual(emu.opcoes_do_emulador("snes")["shader"], "2xScaleHQ.glslp")
        self.assertEqual(emu.opcoes_no_computador("snes")["shader"], "sabr")
        self.assertEqual(emu.opcoes_do_emulador("psx")["shader"], "bicubic")
        self.assertNotIn("shader", emu.opcoes_no_computador("psx"))
        self.assertEqual(emu.opcoes_no_computador("psp")["ppsspp_internal_resolution"], "960x544")
        self.assertEqual(emu.opcoes_do_emulador("psx")["pcsx_rearmed_dithering"], "disabled")
        # no Master System o emulador escolheria o smsplus por conta própria
        self.assertEqual(emu.opcoes_do_emulador("segaMS")["retroarch_core"], "genesis_plus_gx")
        self.assertNotIn("retroarch_core", emu.opcoes_do_emulador("n64"))
        self.assertEqual(emu.RESOLUCAO_NO_COMPUTADOR["psp"]["ppsspp_internal_resolution"], "960x544")

    def test_o_portugues_do_emulador_tem_todos_os_textos(self):
        import re
        from django.contrib.staticfiles import finders

        js = open(finders.find("vendor/emulatorjs/data/emulator.min.js"), encoding="utf-8", errors="replace").read()
        pt = json.load(open(finders.find("vendor/emulatorjs/data/localization/pt-BR.json"), encoding="utf-8"))
        usados = {u for u in re.findall(r'localization\("([^"]+)"', js) if "\\u" not in u}
        self.assertEqual(sorted(u for u in usados if u not in pt), [])
        self.assertEqual(pt["Shaders"], "Filtro de imagem")
        self.assertEqual(pt["Save State"], "Salvar o jogo")


class TresAparelhosTests(SimpleTestCase):
    """Teclado, celular e controle de Xbox: cada comando diz onde fica em cada um."""

    def test_o_controle_de_xbox_vai_pela_posicao_dos_botoes(self):
        snes = {c["acao"]: c["controle"] for c in emu.controles_do_sistema("snes")}
        self.assertEqual(snes["B"], ["A"])  # o pulo do Super Nintendo no botão de baixo do Xbox
        self.assertEqual(snes["Y"], ["X"])
        self.assertEqual(snes["L / R"], ["LB", "RB"])
        self.assertEqual(snes["Start"], ["Menu"])
        psx = {c["acao"]: c["controle"] for c in emu.controles_do_sistema("psx")}
        self.assertEqual(psx["✕"], ["A"])
        self.assertEqual(psx["△"], ["Y"])
        self.assertEqual(psx["L2 / R2"], ["LT", "RT"])
        n64 = {c["acao"]: c["controle"] for c in emu.controles_do_sistema("n64")}
        self.assertEqual(n64["Analógico"], ["Analógico esquerdo"])
        self.assertEqual(n64["Botões C"], ["Analógico direito"])
        fliperama = {c["acao"]: c["controle"] for c in emu.controles_do_sistema("arcade")}
        self.assertEqual(fliperama["Botões 1 a 4"], ["A", "B", "X", "Y"])
        self.assertEqual(emu.controles_do_sistema("mame"), emu.controles_do_sistema("arcade"))

    def test_o_teclado_e_o_controle_batem_com_o_que_o_emulador_recebe(self):
        for codigo in emu.SISTEMAS:
            jogador = emu.controles_do_emulador(codigo)["0"]
            mapa = emu._TECLA_DO_RETROPAD_ANALOGICO if codigo in emu.ANALOGICO_NAS_SETAS else emu._TECLA_DO_RETROPAD
            for c in emu.controles_do_sistema(codigo):
                for tecla in c["teclas"]:
                    if tecla not in mapa:
                        continue
                    nome = {"↑": "up arrow", "↓": "down arrow", "←": "left arrow", "→": "right arrow"}.get(tecla, tecla.lower())
                    with self.subTest(sistema=codigo, comando=c["acao"], tecla=tecla):
                        self.assertEqual(jogador[str(mapa[tecla])]["value"], nome)

    def test_o_controle_da_tela_tem_os_nomes_do_console_e_a_legenda_do_jogo(self):
        desenho, legendas = emu.gamepad_na_tela("psx", emu.ler_acoes("X: Pular\nquadrado: Atacar", "psx"))
        textos = [b.get("text") for b in desenho if b["type"] == "button"]
        for simbolo in ("△", "□", "○", "✕", "L1", "R1", "L2", "R2", "START", "SELECT"):
            self.assertIn(simbolo, textos)
        self.assertNotIn("Fast", textos)  # nada de "Fast/Slow/Rewind" no meio da tela
        self.assertEqual(legendas["xis"], {"icone": "pular", "texto": "Pular"})
        self.assertEqual(legendas["quadrado"], {"icone": "atacar", "texto": "Atacar"})
        self.assertEqual(legendas["bola"], {"icone": "voltar", "texto": ""})  # o costume do console, sem texto
        # o botão aperta o que a tecla aperta (o mesmo número do RetroPad)
        xis = next(b for b in desenho if b.get("id") == "xis")
        self.assertEqual(xis["input_value"], emu._TECLA_DO_RETROPAD["X"])
        # o EmulatorJS ignora posição 0: nenhum botão vai com 0
        for b in desenho:
            for lado in ("left", "top", "right"):
                self.assertNotEqual(b.get(lado), 0)
        self.assertEqual(emu.gamepad_na_tela("dos"), (None, {}))  # o do emulador

    def test_cada_botao_da_tela_aperta_o_mesmo_que_o_teclado(self):
        for codigo, desenho in emu.GAMEPAD_NA_TELA.items():
            teclas = {c["acao"]: c["teclas"] for c in emu.controles_do_sistema(codigo)}
            for b in desenho:
                if b["type"] != "button" or not b.get("acao") or b["acao"] not in teclas:
                    continue
                valores = {emu._TECLA_DO_RETROPAD.get(t) for t in teclas[b["acao"]]}
                with self.subTest(sistema=codigo, botao=b["text"]):
                    self.assertIn(b["input_value"], valores)


class IconesDasAcoesTests(SimpleTestCase):
    """A mesma ação, o mesmo ícone, em todo jogo."""

    def test_o_icone_sai_da_primeira_acao_do_texto(self):
        self.assertEqual(emu.icone_da_funcao("Pular"), "pular")
        self.assertEqual(emu.icone_da_funcao("Pular e confirmar (na maioria)"), "pular")
        self.assertEqual(emu.icone_da_funcao("Correr, pegar e atirar"), "correr")
        self.assertEqual(emu.icone_da_funcao("Soco forte"), "atacar")
        self.assertEqual(emu.icone_da_funcao("Chutar"), "atacar")
        self.assertEqual(emu.icone_da_funcao("Atirar"), "atirar")
        self.assertEqual(emu.icone_da_funcao("Defender"), "defender")
        self.assertEqual(emu.icone_da_funcao("Pôr ficha (créditos)"), "ficha")
        self.assertEqual(emu.icone_da_funcao("Ação 1"), "")

    def test_o_pular_do_mario_e_o_do_sonic_sao_o_mesmo(self):
        snes = emu.gamepad_na_tela("snes", emu.ler_acoes("B: Pular", "snes"))[1]
        mega = emu.gamepad_na_tela("segaMD", emu.ler_acoes("C: Pular", "segaMD"))[1]
        self.assertEqual(snes["b"], {"icone": "pular", "texto": "Pular"})
        self.assertEqual(mega["c"], {"icone": "pular", "texto": "Pular"})
        # andar é sempre o de mover, mesmo na cruz do N64 ("Menus e atalhos")
        n64 = {c["acao"]: c["icone"] for c in emu.controles_do_sistema("n64")}
        self.assertEqual(n64["Direcional (cruz)"], "mover")
        self.assertEqual(n64["Analógico"], "mover")

    def test_todo_icone_tem_desenho(self):
        from pathlib import Path
        desenhos = (Path(__file__).parent / "templates" / "partials" / "icones_das_acoes.html").read_text(encoding="utf-8")
        for icone, _ in emu.ICONES_DAS_ACOES:
            with self.subTest(icone=icone):
                self.assertIn(f'<symbol id="a-{icone}"', desenhos)
