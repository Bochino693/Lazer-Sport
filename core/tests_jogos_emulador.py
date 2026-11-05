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

LIGADOS = ["psx", "nes", "gb", "gba", "n64", "pce"]
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
        self.assertEqual(config["jogo"], reverse("jogo_emulador_arquivo", args=["disco-teste", "Jogo (Disc 1).cue"]))
        externos = {e["caminho"]: e for e in config["externos"]}
        self.assertEqual(sorted(externos), ["/Track 01.bin", "/Track 02.bin"])
        self.assertIn("guardado_Track", externos["/Track 01.bin"]["url"])
        self.assertEqual(externos["/Track 01.bin"]["tamanho"], len(FAIXA_PSX))
        self.assertTrue(config["dados"].endswith("vendor/emulatorjs/data/"))
        self.assertContains(resposta, "jogo-emulador.js")

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
