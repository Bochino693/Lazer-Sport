"""Dados SINTÉTICOS para os testes do RH (nenhum dado real).

CPF e PIS são gerados aqui com os dígitos verificadores calculados, a
partir de bases inventadas. Arquivos (PDF, JPG, assinatura) são montados na
hora. A pasta privada dos documentos vai para um diretório temporário.
"""

from __future__ import annotations

import base64
import io
import re
import shutil
import tempfile
from datetime import date, datetime, time, timedelta

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


# ======================================================================
# O CARTÃO DE PONTO DO RELÓGIO, SINTÉTICO (LEIA-ME-V10, seção 125)
# ======================================================================
# O desenho é o do "Cartão de Ponto" que o sistema do relógio (REP-P)
# exporta: o cabeçalho com os rótulos, o quadro "HORÁRIO DE TRABALHO", a
# tabela dos dias com as colunas nas mesmas posições (x) e os totais
# esparsos, a linha TOTAIS, a legenda e as "Alterações". TODOS os dados são
# inventados aqui (nome, CPF e PIS sintéticos). As contas dos totais
# imitam as do relógio: falta e atraso descontam 10 minutos de tolerância
# no dia completo; a hora noturna (22h-5h) é contada no relógio.

SEMANA_PADRAO = {
    1: ("08:00", "12:00", "13:00", "18:00"), 2: ("08:00", "12:00", "13:00", "18:00"),
    3: ("08:00", "12:00", "13:00", "18:00"), 4: ("08:00", "12:00", "13:00", "18:00"),
    5: ("08:00", "12:00", "13:00", "17:00"),
}
_SIGLA = {1: "SEG", 2: "TER", 3: "QUA", 4: "QUI", 5: "SEX", 6: "SAB", 7: "DOM"}
#: Onde começa cada coluna da tabela (x, em pontos) e o nome dela, em uma ou duas linhas.
COLUNAS_DO_CARTAO = (
    (33.1, ("DIA",), "dia"), (92.0, ("PREVISTO",), "previsto"),
    (163.5, ("ENT. 1",), "ent1"), (187.1, ("SAÍ. 1",), "sai1"), (209.8, ("ENT. 2",), "ent2"), (233.3, ("SAÍ. 2",), "sai2"),
    (256.9, ("TOTAL", "NORMAIS"), "normais"), (289.2, ("TOTAL", "NOTURNO"), "noturno"),
    (323.6, ("DIA", "FALTA"), "dia_falta"), (346.7, ("FALTA E", "ATRASO"), "falta_atraso"), (375.1, ("ABONO",), "abono"),
    (403.0, ("EXTRA", "50%D"), "extra_50d"), (428.3, ("EXTRA", "50%N"), "extra_50n"),
    (453.6, ("EXTRA", "DIURNA"), "extra_diurna"), (482.0, ("EXTRA", "NOTURNA"), "extra_noturna"),
    (516.0, ("BANCO", "TOTAL"), "banco_total"), (543.5, ("BANCO", "SALDO"), "banco_saldo"),
)


def _min_hhmm(texto):
    h, m = texto.split(":")
    return int(h) * 60 + int(m)


def _hhmm_de(minutos, largura=2):
    return f"{minutos // 60:0{largura}d}:{minutos % 60:02d}"


def _noturno_do_par(a, b):
    return sum(max(0, min(b, fim) - max(a, inicio)) for inicio, fim in ((0, 300), (1320, 1440)))


def totais_como_o_relogio(previsto, marcas):
    """Os totais de um dia, pela regra do relógio (para o PDF sintético conferir com a linha TOTAIS)."""
    esperado = sum(_min_hhmm(previsto[i + 1]) - _min_hhmm(previsto[i]) for i in range(0, len(previsto) - 1, 2)) if previsto else 0
    horas = [re.match(r"\d{1,2}:\d{2}", m).group(0) for m in marcas if m and re.match(r"\d{1,2}:\d{2}", m)]
    faltas = sum(1 for m in marcas if m == "Falta")
    totais = {}
    if not horas:
        if esperado and faltas:
            totais = {"dia_falta": 1, "falta_atraso": esperado}
        return totais
    minutos = [_min_hhmm(h) for h in horas]
    trabalhado = sum(minutos[i + 1] - minutos[i] for i in range(0, len(minutos) - 1, 2))
    noturno = sum(_noturno_do_par(minutos[i], minutos[i + 1]) for i in range(0, len(minutos) - 1, 2))
    completo = not faltas and len(minutos) % 2 == 0
    normais = min(trabalhado, esperado) if esperado else 0
    if normais:
        totais["normais"] = normais
    if noturno:
        totais["noturno"] = noturno
    deficit = esperado - trabalhado
    if deficit > 0:
        desconto = (deficit - 10 if deficit > 10 else 0) if completo else deficit
        if desconto:
            totais["falta_atraso"] = desconto
    excesso = trabalhado - esperado
    if completo and excesso > 10:
        extra = excesso - 10
        noturna = min(noturno, extra)
        diurna = extra - noturna
        if diurna:
            totais["extra_50d"] = totais["extra_diurna"] = diurna
        if noturna:
            totais["extra_50n"] = totais["extra_noturna"] = noturna
    return totais


def _dias_do_funcionario(func):
    semana = func.get("semana", SEMANA_PADRAO)
    dias = func.get("dias", {})
    linhas = []
    dia = func["inicio"]
    while dia <= func["fim"]:
        previsto = semana.get(dia.isoweekday())
        especial = dias.get(dia)
        if especial is None:
            marcas = list(previsto) if previsto else ["Folga", "", "", ""]
        elif especial == "Falta":
            marcas = ["Falta"] * 4
        elif especial == "Folga":
            marcas = ["Folga", "", "", ""]
        elif especial == "Feriado":
            marcas = ["Feriado", "", "Feriado", ""]
        elif isinstance(especial, str):
            marcas = [especial, "", "", ""]
        else:
            marcas = list(especial) + [""] * (4 - len(especial))
        prev_texto = f"{previsto[0]}-{previsto[1]} {previsto[2]}-{previsto[3]}" if previsto else ""
        totais = totais_como_o_relogio(previsto if previsto and especial not in ("Feriado", "Folga") else None, marcas)
        linhas.append((dia, prev_texto, marcas, totais))
        dia += timedelta(days=1)
    return linhas


def cartao_ponto_pdf(*funcionarios, cnpj="54486908000186", empresa="EMPRESA SINTETICA DE BRINQUEDOS LTDA",
                     emitido=None, linhas_por_pagina=40, totais_errados=None) -> bytes:
    """Um PDF de cartão de ponto como o do relógio, com uma ou várias pessoas (e páginas).

    `funcionarios`: dicts com nome, cpf, pis, admissao, matricula, inicio, fim, e
    opcionais `semana` ({1: ("08:00","12:00","13:00","18:00"), ...}), `dias`
    ({date: ["07:58 (I)", "12:00", ...] | "Falta" | "Folga" | "Feriado"}) e
    `alteracoes`. `totais_errados`: {chave: minutos} para a linha TOTAIS mentir.
    """
    from .pdf_simples import A4, Documento, _texto_pdf, largura

    emitido = emitido or datetime(2026, 11, 18, 16, 45)
    doc = Documento(titulo="Cartao")
    doc.paginas = []
    paginas = []
    for func in funcionarios:
        linhas = _dias_do_funcionario(func)
        pedacos = [linhas[i:i + linhas_por_pagina] for i in range(0, len(linhas), linhas_por_pagina)] or [[]]
        for indice, pedaco in enumerate(pedacos):
            paginas.append((func, pedaco, indice == len(pedacos) - 1, linhas))
    total = len(paginas)

    def escrever(ops, x, y, texto, corpo=6.0, negrito=False):
        fonte = "F2" if negrito else "F1"
        ops.append(
            b"0 g BT /" + fonte.encode() + b" " + f"{corpo:.2f}".encode() + b" Tf "
            + f"{x:.2f} {y:.2f}".encode() + b" Td (" + _texto_pdf(texto) + b") Tj ET"
        )

    for numero, (func, pedaco, ultima, todas) in enumerate(paginas, start=1):
        ops = []
        escrever(ops, 522.1, 784.5, f"Página {numero:02d} de {total:02d}")
        escrever(ops, 484.6, 776.6, f"Emitido em {emitido:%d/%m/%Y} às {emitido:%H:%M}")
        escrever(ops, 29.2, 756.1, "Cartão", 16, True)
        escrever(ops, 29.2, 736.9, "de Ponto", 16, True)
        escrever(ops, 441.8, 736.0, f"DE {func['inicio']:%d/%m/%Y} ATÉ {func['fim']:%d/%m/%Y}", 8, True)
        cabecalho = (
            (33.6, 716.8, "NOME DA EMPRESA:", empresa),
            (33.6, 708.1, "CNPJ DA EMPRESA:", cnpj),
            (277.8, 708.1, "INSCRIÇÃO ESTADUAL DA EMPRESA:", "1"),
            (33.6, 699.4, "NOME DO FUNCIONÁRIO:", func["nome"]),
            (277.8, 699.4, "CPF DO FUNCIONÁRIO:", func["cpf"]),
            (33.6, 690.7, "PIS DO FUNCIONÁRIO:", func.get("pis", "")),
            (277.8, 690.7, "DATA DE ADMISSÃO DO FUNCIONÁRIO:", f"{func['admissao']:%d/%m/%Y}" if func.get("admissao") else ""),
            (33.6, 681.9, "NÚMERO DE MATRÍCULA:", func.get("matricula", "0")),
        )
        for x, y, rotulo, valor in cabecalho:
            escrever(ops, x, y, rotulo, 5.5, True)
            if valor:
                escrever(ops, x + largura(rotulo, "F2", 5.5) + 2, y, " " + str(valor), 5.5)
        escrever(ops, 478.9, 717.3, "HORÁRIO DE TRABALHO", 5.5, True)
        for x, rotulo in ((477.2, "ENT. 1"), (501.2, "SAÍ. 1"), (523.4, "ENT. 2"), (547.4, "SAÍ. 2")):
            escrever(ops, x, 707.7, rotulo, 5.5, True)
        semana = func.get("semana", SEMANA_PADRAO)
        for i in range(1, 8):
            y = 701.1 - (i - 1) * 6.5
            escrever(ops, 456.2, y, _SIGLA[i], 5.5)
            for x, hora in zip((477.2, 501.2, 523.4, 547.4), semana.get(i) or ()):
                escrever(ops, x, y, hora, 5.5)
        for x, nomes, _ in COLUNAS_DO_CARTAO:
            if len(nomes) == 2:
                escrever(ops, x, 642.7, nomes[0], 5, True)
                escrever(ops, x, 637.5, nomes[1], 5, True)
            else:
                escrever(ops, x, 637.5, nomes[0], 5, True)
        y = 628.7
        posicao = {chave: x for x, _, chave in COLUNAS_DO_CARTAO}
        for dia, prev_texto, marcas, totais in pedaco:
            escrever(ops, posicao["dia"], y, f"{dia:%d/%m/%Y} - {_SIGLA[dia.isoweekday()]}", 6)
            if prev_texto:
                escrever(ops, posicao["previsto"], y, prev_texto, 6)
            for chave, marca in zip(("ent1", "sai1", "ent2", "sai2"), marcas):
                if marca:
                    escrever(ops, posicao[chave], y, marca, 6)
            for chave, valor in totais.items():
                escrever(ops, posicao[chave], y, str(valor) if chave == "dia_falta" else _hhmm_de(valor), 6)
            y -= 10.0
        if ultima:
            soma = {}
            for _, _, _, totais in todas:
                for chave, valor in totais.items():
                    soma[chave] = soma.get(chave, 0) + valor
            soma.update(totais_errados or {})
            escrever(ops, posicao["dia"], y, "TOTAIS", 6, True)
            for chave, valor in soma.items():
                escrever(ops, posicao[chave], y, str(valor) if chave == "dia_falta" else _hhmm_de(valor), 6, True)
            y -= 17.4
            escrever(ops, 28.8, y, "(I)=Incluído, (P)=Pré-assinalado, (M)=Coletor REP-P Mobile/Web, "
                                   "(C)=Coletor REP-P (iDFace/iDFlex)", 5.5)
            y -= 11.4
            escrever(ops, 28.5, y, "Alterações", 6, True)
            for alteracao in func.get("alteracoes", ()):
                y -= 9.6
                escrever(ops, 46.2, y, alteracao, 6)
            escrever(ops, 108.6, max(60, y - 36), func["nome"], 6)
            escrever(ops, 349.4, max(60, y - 36), empresa, 6)
        doc.paginas.append(ops)
    # sem o rodapé do Documento (o relógio não põe): gerar sem ele
    doc.titulo = "Cartao"
    dados = doc.gerar()
    return dados


def funcionario_do_cartao(n=1, **campos):
    """Um funcionário sintético para o cartão: o CPF e o PIS da `criar_colaborador(n)`."""
    dados = {
        "nome": f"PESSOA TESTE {n} SILVA", "cpf": cpf_sintetico(n), "pis": pis_sintetico(n),
        "admissao": date(2026, 1, 5), "matricula": "0",
        "inicio": date(2026, 10, 1), "fim": date(2026, 10, 31),
    }
    dados.update(campos)
    return dados


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
