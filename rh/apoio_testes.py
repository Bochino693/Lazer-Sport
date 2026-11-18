"""Dados SINTÉTICOS para os testes do RH (nenhum dado real).

CPF e PIS são gerados aqui com os dígitos verificadores calculados, a
partir de bases inventadas. Arquivos (PDF, JPG, assinatura) são montados na
hora. A pasta privada dos documentos vai para um diretório temporário.
"""

from __future__ import annotations

import base64
import io
import shutil
import tempfile
from datetime import date, time

from django.contrib.auth import get_user_model
from django.test import override_settings

from sistema_interno.permissoes import atribuir_funcoes

from .models import Colaborador

INTERNO = {"HTTP_HOST": "interno.testserver"}


def _dv11(base, pesos):
    resto = sum(int(d) * p for d, p in zip(base, pesos)) % 11
    return 0 if resto < 2 else 11 - resto


def cpf_sintetico(n: int) -> str:
    base = f"{(n * 7919 + 123456) % 1_000_000_000:09d}"
    if len(set(base)) == 1:
        base = "1" + base[1:]
    d1 = _dv11(base, range(10, 1, -1))
    d2 = _dv11(base + str(d1), range(11, 1, -1))
    return f"{base}{d1}{d2}"


def pis_sintetico(n: int) -> str:
    base = f"{(n * 104729 + 1200000000) % 10_000_000_000:010d}"
    return base + str(_dv11(base, (3, 2, 9, 8, 7, 6, 5, 4, 3, 2)))


def criar_conta(username, *funcoes, superusuario=False):
    Usuario = get_user_model()
    if superusuario:
        return Usuario.objects.create_superuser(username, f"{username}@exemplo.invalid", "senha-de-teste")
    conta = Usuario.objects.create_user(username, f"{username}@exemplo.invalid", "senha-de-teste",
                                        first_name=username.capitalize())
    if funcoes:
        atribuir_funcoes(conta, funcoes)
    return conta


def criar_colaborador(n=1, *, usuario=None, **campos) -> Colaborador:
    dados = {
        "nome": f"Pessoa Teste {n} Silva",
        "cpf": cpf_sintetico(n),
        "rg": f"{n:08d}",
        "data_nascimento": date(1990, 1, 1),
        "pis": pis_sintetico(n),
        "cep": "01001000",
        "logradouro": "Rua Inventada",
        "numero": str(n),
        "bairro": "Bairro Exemplo",
        "cidade": "Cidade Exemplo",
        "uf": "SP",
        "telefone": f"119{n:08d}"[:11],
        "emergencia_nome": "Contato Exemplo",
        "emergencia_telefone": f"118{n:08d}"[:11],
        "cargo": "Montador",
        "setor": "producao",
        "data_admissao": date(2026, 1, 5),
        "vinculo": "clt",
        "salario": "2500.00",
        "jornada_inicio": time(8, 0),
        "jornada_fim": time(17, 0),
        "jornada_intervalo_min": 60,
        "jornada_dias": "12345",
    }
    dados.update(campos)
    colaborador = Colaborador(usuario=usuario, **dados)
    colaborador.full_clean()
    colaborador.save()
    return colaborador


def pdf_sintetico(texto="Documento de teste") -> bytes:
    from .pdf_simples import Documento

    doc = Documento(titulo="Teste")
    doc.texto(texto)
    return doc.gerar()


def imagem_sintetica(formato="JPEG", lado=200) -> bytes:
    from PIL import Image

    imagem = Image.new("RGB", (lado, lado), (200, 180, 160))
    saida = io.BytesIO()
    imagem.save(saida, format=formato)
    return saida.getvalue()


def assinatura_sintetica() -> str:
    """Um traço escuro sobre fundo transparente, como o quadro manda."""
    from PIL import Image, ImageDraw

    imagem = Image.new("RGBA", (500, 180), (0, 0, 0, 0))
    ImageDraw.Draw(imagem).line([(20, 140), (160, 30), (300, 150), (480, 40)], fill=(20, 18, 26, 255), width=6)
    saida = io.BytesIO()
    imagem.save(saida, format="PNG")
    return "data:image/png;base64," + base64.b64encode(saida.getvalue()).decode("ascii")


class PastaPrivadaTemporaria:
    """Mixin: cada classe de teste guarda os documentos numa pasta própria."""

    @classmethod
    def setUpClass(cls):
        cls._pasta_rh = tempfile.mkdtemp(prefix="rh-privado-")
        cls._override_rh = override_settings(RH_ARQUIVOS_PRIVADOS_DIR=cls._pasta_rh, RH_ARMAZENAMENTO="local")
        cls._override_rh.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._override_rh.disable()
        shutil.rmtree(cls._pasta_rh, ignore_errors=True)
