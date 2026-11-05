"""A migração das descrições novas (0126): troca só o que deve.

O que se garante: troca o texto quando o id e o nome conferem e o texto
ainda é o antigo (mesmo com espaços e quebras de linha diferentes);
respeita a descrição que a equipe reescreveu depois; não toca brinquedo
de outro nome com o mesmo id; desfazer volta o antigo; e nenhuma
descrição nova passa do tamanho do campo.
"""
import importlib

from django.apps import apps
from django.test import TestCase

from .migrations._descricoes_brinquedos import DESCRICOES
from .models import Brinquedos

migracao = importlib.import_module("core.migrations.0126_descricoes_dos_brinquedos")


def brinquedo(pk, nome, descricao):
    return Brinquedos.objects.create(pk=pk, nome_brinquedo=nome, descricao=descricao, avaliacao=5, voltz="220V")


class DescricoesNovasTests(TestCase):
    def test_troca_quando_o_texto_ainda_e_o_antigo(self):
        dados = DESCRICOES[2]
        brinquedo(2, dados["nome"], dados["antiga"])
        migracao.aplicar(apps, None)
        self.assertEqual(Brinquedos.objects.get(pk=2).descricao, dados["nova"])

    def test_espacos_e_quebras_de_linha_diferentes_ainda_contam_como_o_antigo(self):
        dados = DESCRICOES[8]
        brinquedo(8, dados["nome"].lower(), dados["antiga"].replace(" ", "  ").replace(".", ".\r\n"))
        migracao.aplicar(apps, None)
        self.assertEqual(Brinquedos.objects.get(pk=8).descricao, dados["nova"])

    def test_respeita_a_descricao_reescrita_pela_equipe(self):
        dados = DESCRICOES[3]
        brinquedo(3, dados["nome"], "Texto que a equipe escreveu no painel.")
        migracao.aplicar(apps, None)
        self.assertEqual(Brinquedos.objects.get(pk=3).descricao, "Texto que a equipe escreveu no painel.")

    def test_outro_brinquedo_com_o_mesmo_id_nao_e_tocado(self):
        brinquedo(1, "Brinquedo do computador", DESCRICOES[1]["antiga"])
        migracao.aplicar(apps, None)
        self.assertEqual(Brinquedos.objects.get(pk=1).descricao, DESCRICOES[1]["antiga"])

    def test_desfazer_volta_o_antigo_e_rodar_duas_vezes_nao_muda_nada(self):
        dados = DESCRICOES[35]
        brinquedo(35, dados["nome"], dados["antiga"])
        migracao.aplicar(apps, None)
        migracao.aplicar(apps, None)
        self.assertEqual(Brinquedos.objects.get(pk=35).descricao, dados["nova"])
        migracao.desfazer(apps, None)
        self.assertEqual(Brinquedos.objects.get(pk=35).descricao, dados["antiga"])

    def test_cabem_no_campo_e_nenhuma_ficou_vazia(self):
        limite = Brinquedos._meta.get_field("descricao").max_length
        for pk, dados in DESCRICOES.items():
            with self.subTest(pk=pk):
                self.assertLessEqual(len(dados["nova"]), limite)
                self.assertGreater(len(dados["nova"]), 300)
                self.assertNotEqual(dados["nova"].strip(), dados["antiga"].strip())


renomes = importlib.import_module("core.migrations.0127_nomes_dos_brinquedos")


class NomesCorrigidosTests(TestCase):
    def test_corrige_o_flappy_e_separa_os_dois_pinballs(self):
        brinquedo(24, "FLAPYY BIRD", "jogo do passarinho")
        brinquedo(18, "PIMBAL", DESCRICOES[18]["nova"])
        brinquedo(19, "PIMBAL", DESCRICOES[19]["nova"])
        renomes.aplicar(apps, None)
        self.assertEqual(Brinquedos.objects.get(pk=24).nome_brinquedo, "FLAPPY BIRD")
        self.assertEqual(Brinquedos.objects.get(pk=18).nome_brinquedo, "PINBALL 32 POLEGADAS")
        self.assertEqual(Brinquedos.objects.get(pk=19).nome_brinquedo, "PINBALL 40 POLEGADAS")
        renomes.desfazer(apps, None)
        self.assertEqual(Brinquedos.objects.get(pk=18).nome_brinquedo, "PIMBAL")

    def test_nao_mexe_em_nome_ja_trocado_nem_em_outro_brinquedo(self):
        brinquedo(24, "Flappy Bird Deluxe", "outro")
        brinquedo(18, "PIMBAL", "um pinball sem a tela na descrição")
        renomes.aplicar(apps, None)
        self.assertEqual(Brinquedos.objects.get(pk=24).nome_brinquedo, "Flappy Bird Deluxe")
        self.assertEqual(Brinquedos.objects.get(pk=18).nome_brinquedo, "PIMBAL")

    def test_a_arena_continua_reconhecendo_o_pinball(self):
        from . import arena

        self.assertEqual(arena.modelo_3d("PINBALL 40 POLEGADAS"), arena.modelo_3d("PIMBAL"))
        self.assertEqual(arena.modelo_3d("FLAPPY BIRD"), arena.modelo_3d("FLAPYY BIRD"))
