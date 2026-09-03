from io import BytesIO
from importlib import import_module
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from django.apps import apps
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase, override_settings
from PIL import Image

from .models import Material, SequenciaMaterial, TipoMaterial


class CodigosMaterialTests(TestCase):
    def test_sequencia_por_tipo_e_sem_reuso(self):
        tipo = TipoMaterial.objects.create(descricao="Arduino")
        nano = Material.objects.create(nome_material="Nano", tipo_material=tipo)
        uno = Material.objects.create(nome_material="Uno", tipo_material=tipo)
        self.assertEqual(nano.codigo_interno, "ard-0001")
        self.assertEqual(uno.codigo_interno, "ard-0002")
        uno.delete()
        mega = Material.objects.create(nome_material="Mega", tipo_material=tipo)
        self.assertEqual(mega.codigo_interno, "ard-0003")

    def test_tipo_renomeado_e_material_editado_preservam_codigo(self):
        tipo = TipoMaterial.objects.create(descricao="Arduino")
        material = Material.objects.create(nome_material="Nano", tipo_material=tipo)
        tipo.descricao = "Placas Arduino"
        tipo.save()
        material.nome_material = "Nano atualizado"
        material.tipo_material = TipoMaterial.objects.create(descricao="Eletrônica")
        material.save()
        self.assertEqual(tipo.prefixo, "ard")
        self.assertEqual(material.codigo_interno, "ard-0001")

    def test_prefixos_colidentes_e_sem_tipo(self):
        a = TipoMaterial.objects.create(descricao="Arduino")
        b = TipoMaterial.objects.create(descricao="Arduinos especiais")
        self.assertEqual((a.prefixo, b.prefixo), ("ard", "ard2"))
        material = Material.objects.create(nome_material="Genérico")
        self.assertEqual(material.codigo_interno, "mat-0001")
        tipo = TipoMaterial.objects.create(descricao="Materiais diversos")
        self.assertNotEqual(tipo.prefixo, "mat")

    def test_codigo_legado_nao_colide_com_novo(self):
        tipo = TipoMaterial.objects.create(descricao="Arduino")
        Material.objects.create(nome_material="Antigo", codigo_interno="ARD-0001")
        novo = Material.objects.create(nome_material="Nano", tipo_material=tipo)
        self.assertEqual(novo.codigo_interno, "ard-0002")

    def test_exclusao_de_tipo_nao_libera_prefixo(self):
        tipo = TipoMaterial.objects.create(descricao="Arduino")
        tipo.delete()
        self.assertEqual(TipoMaterial.objects.create(descricao="Arduino").prefixo, "ard2")

    def test_migracao_preserva_legados_e_preenche_vazios(self):
        # bulk_create simula os registros antigos, sem executar os novos save().
        TipoMaterial.objects.bulk_create([TipoMaterial(descricao="Arduino"), TipoMaterial(descricao="Arduinos")])
        tipo = TipoMaterial.objects.order_by("id").first()
        Material.objects.bulk_create([
            Material(nome_material="Legado", tipo_material=tipo, codigo_interno="ARD-0007"),
            Material(nome_material="Nano", tipo_material=tipo),
            Material(nome_material="Diverso"),
        ])
        SequenciaMaterial.objects.all().delete()
        migracao = import_module("sistema_interno.migrations.0050_preencher_codigos_materiais")
        migracao.preencher_codigos(apps, SimpleNamespace(connection=connection))
        self.assertEqual(Material.objects.get(nome_material="Legado").codigo_interno, "ARD-0007")
        self.assertEqual(Material.objects.get(nome_material="Nano").codigo_interno, "ard-0008")
        self.assertEqual(Material.objects.get(nome_material="Diverso").codigo_interno, "mat-0001")
        tipo.refresh_from_db()
        self.assertEqual(Material.objects.create(nome_material="Uno", tipo_material=tipo).codigo_interno, "ard-0009")


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class FotosMaterialTests(TestCase):
    URL = "/estoque/materiais/"

    def setUp(self):
        self.pasta = TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.config = override_settings(MEDIA_ROOT=self.pasta.name)
        self.config.enable()
        self.addCleanup(self.config.disable)
        self.client.force_login(User.objects.create_superuser("gestor-foto", "foto@example.com", "x"))
        self.tipo = TipoMaterial.objects.create(descricao="Arduino")

    def foto(self):
        dados = BytesIO()
        Image.new("RGB", (1800, 1200), "orange").save(dados, "JPEG")
        return SimpleUploadedFile("material.jpg", dados.getvalue(), content_type="image/jpeg")

    def salvar(self, **extra):
        dados = {"action": "save_material", "nome_material": "Nano", "tipo_material": self.tipo.pk, "ativo": "on"}
        dados.update(extra)
        return self.client.post(self.URL, dados, HTTP_HOST="interno.testserver", HTTP_X_REQUESTED_WITH="XMLHttpRequest")

    def test_foto_gera_webp_e_miniatura_sem_cortar(self):
        resposta = self.salvar(foto=self.foto(), codigo_interno="codigo-forjado")
        self.assertEqual(resposta.status_code, 200, resposta.content)
        material = Material.objects.get()
        self.assertEqual(material.codigo_interno, "ard-0001")
        for campo, dimensoes in ((material.foto, (960, 640)), (material.foto_miniatura, (160, 107))):
            with campo.open("rb") as arquivo, Image.open(arquivo) as imagem:
                self.assertEqual(imagem.format, "WEBP")
                self.assertEqual(imagem.size, dimensoes)
        html = self.client.get(self.URL, HTTP_HOST="interno.testserver")
        self.assertContains(html, 'loading="lazy"')
        self.assertContains(html, material.foto_miniatura.url)

    def test_editar_sem_upload_preserva_foto_e_codigo(self):
        self.salvar(foto=self.foto())
        material = Material.objects.get()
        nome = material.foto.name
        self.salvar(id=material.pk, codigo_interno="alterado")
        material.refresh_from_db()
        self.assertEqual(material.foto.name, nome)
        self.assertEqual(material.codigo_interno, "ard-0001")
        self.salvar(id=material.pk, remover_foto="on")
        material.refresh_from_db()
        self.assertFalse(material.foto)
        self.assertFalse(material.foto_miniatura)

    def test_recusa_arquivo_invalido_sem_cadastrar(self):
        resposta = self.salvar(foto=SimpleUploadedFile("falsa.jpg", b"nao e imagem", content_type="image/jpeg"))
        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(Material.objects.exists())

    def test_recusa_foto_grande(self):
        resposta = self.salvar(foto=SimpleUploadedFile("grande.jpg", b"x" * (5 * 1024 * 1024 + 1)))
        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(Material.objects.exists())

    def test_cadastro_rapido_aceita_foto(self):
        self.URL = "/stock/"
        self.assertEqual(self.salvar(foto=self.foto()).status_code, 200)
        self.assertTrue(Material.objects.get().foto_miniatura)

    def test_pagina_limita_materiais_e_busca_codigo(self):
        for n in range(31):
            Material.objects.create(nome_material=f"Material {n:02d}", tipo_material=self.tipo)
        resposta = self.client.get(self.URL, HTTP_HOST="interno.testserver")
        self.assertEqual(len(resposta.context["materiais"]), 30)
        self.assertEqual(resposta.context["total_materiais"], 31)
        resposta = self.client.get(self.URL, {"page": "2"}, HTTP_HOST="interno.testserver")
        self.assertEqual(len(resposta.context["materiais"]), 1)
        resposta = self.client.get(self.URL, {"q": "ard-0031"}, HTTP_HOST="interno.testserver")
        self.assertEqual(len(resposta.context["materiais"]), 1)
