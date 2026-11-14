"""Fotografa as nossas máquinas 3D no estúdio (Blender Cycles) e grava as fotos do site.

    # uma vez: o Blender como módulo do Python (o bpy do pip pede o Python 3.11)
    python3.11 -m venv ~/blender-venv
    ~/blender-venv/bin/pip install bpy==5.0.1 numpy Pillow

    # tudo, num comando (os mestres numa pasta fora do repositório; as fotos do site no lugar
    # delas). O render sai em 2x a foto do site (3200 px na capa de 1600) com até 12 amostras
    # e o OpenImageDenoise; --fator 2.4 dá o 4K (3840) -- a arte da fábrica tem ~600-1000 px
    # por peça, então o 4K custa ~1,4x mais e não aparece na foto de 1600
    ~/blender-venv/bin/python ferramentas/fotos3d/renderizar.py --mestres /tmp/fotos3d --site

    # só uma máquina, um adesivo ou uma tomada; --previa 960 renderiza pequeno (para conferir)
    ~/blender-venv/bin/python ferramentas/fotos3d/renderizar.py --produto strike-kids --tomada capa --previa 960

O que cada máquina fotografa está em produtos.py; o estúdio (a luz, o fundo, os materiais, a
câmera) em estudio.py; o acabamento (a vinheta, a redução, o realce, o .webp) em
acabamento.py. Melhorou o .glb? É só rodar de novo: o enquadramento sai das medidas de
verdade, o mesmo para todos os adesivos da máquina. Sem --site, as fotos do site vão para
<mestres>/<produto>/<adesivo>/site/ (para conferir antes). Com --site, também anota a caixa
da máquina em cada foto em ferramentas/categorias/areas-dos-produtos.json (os testes da
"vida" das fotos medem ali). Depois, no servidor, a migração de dados das fotos de estúdio
(core/fotos_estudio.py) sobe para o Cloudinary só as que mudaram.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

import bpy  # noqa: E402

import acabamento  # noqa: E402
import estudio  # noqa: E402
from produtos import PRODUTOS, RAIZ  # noqa: E402

#: Os dois modos de luz: o estúdio e o estúdio apagado (os LEDs acesos).
LUZ = {
    "estudio": {"brancas": 1.0, "cor": 1.0, "fundo": 1.0, "led": 1.0, "exposicao": -0.3, "brilho": 0.18},
    "noite": {"brancas": 0.045, "cor": 0.3, "fundo": 0.22, "led": 2.2, "exposicao": 0.0, "brilho": 0.4},
}
LADO_4K = 3840
AREAS = RAIZ / "ferramentas" / "categorias" / "areas-dos-produtos.json"


class Estudio:
    """A cena de uma máquina (um adesivo) montada no estúdio, pronta para as tomadas."""

    def __init__(self, produto, variante, amostras):
        self.produto = produto
        self.variante = variante
        self.cena = estudio.nova_cena(amostras=amostras)
        self.glare = estudio.compositor(self.cena)
        altura, largura, profundidade = produto["medidas"]
        self.escala = max(altura, largura, profundidade) / 2.5
        self.malhas = []
        self.relatorio = {}
        self.avisos = []
        if "glb" in variante:
            self.giro, self.malhas, self.medidas = estudio.importar_maquina(RAIZ / variante["glb"], altura)
            larg, prof, alt = self.medidas
            for nome, real, do_glb in (("largura", largura, min(larg, prof)), ("profundidade", profundidade, max(larg, prof))):
                if abs(do_glb - real) / real > 0.03:
                    self.avisos.append(f"{variante['chave']}: a {nome} do .glb na escala é {do_glb:.2f} m; "
                                       f"o cadastro diz {real:.2f} m")
            artes = RAIZ / variante["artes"] if variante.get("artes") else None
            self.relatorio = estudio.aplicar_materiais(self.malhas, emissao=produto.get("emissao"), artes=artes)
        else:
            self.giro = None
        self.fundo = estudio.criar_fundo(escala=self.escala, centro_brilho=altura * 0.55,
                                         raio_brilho=1.6 * max(altura, largura, profundidade) + 0.8,
                                         brilho_fundo=1.5 * produto.get("fundo", 1.0))
        self.luzes = estudio.criar_luzes(escala=self.escala, centro=(0, 0, altura * 0.5))
        self.energias = {luz.name: luz.data.energy * produto.get("luzes", {}).get(luz.name, 1.0) for luz in self.luzes}
        arvore = self.fundo.data.materials[0].node_tree
        self.fundo_brilho = next(n for n in arvore.nodes if n.type == "MATH")
        self.fundo_forca = self.fundo_brilho.inputs[1].default_value
        self.leds = []
        for obj in self.malhas:
            for slot in obj.material_slots:
                mat = slot.material
                if mat is not None and self.relatorio.get(mat.name) in ("luz", "tela", "adesivo"):
                    b = estudio._bsdf(mat)
                    if b is not None and b.inputs["Emission Strength"].default_value > 0 and \
                            all(b is not x[0] for x in self.leds):
                        self.leds.append((b, b.inputs["Emission Strength"].default_value))
        self.camera = estudio.criar_camera()
        self.cartao = None

    def girar(self, graus):
        if self.giro is not None:
            self.giro.rotation_euler = (0, 0, math.radians(graus + self.produto.get("frente", 0)))
            bpy.context.view_layer.update()

    def pontos(self, filtro=None):
        return estudio.pontos_da_maquina(self.malhas, filtro)

    def luz(self, modo):
        cfg = LUZ[modo]
        for luz in self.luzes:
            fator = cfg["cor"] if luz.name.startswith("recorte") else cfg["brancas"]
            luz.data.energy = self.energias[luz.name] * fator
        self.fundo_brilho.inputs[1].default_value = self.fundo_forca * cfg["fundo"]
        for b, forca in self.leds:
            b.inputs["Emission Strength"].default_value = forca * cfg["led"]
        self.cena.view_settings.exposure = cfg["exposicao"] + self.produto.get("exposicao", 0.0)
        self.glare.inputs["Strength"].default_value = cfg["brilho"]

    def render(self, quadro, tamanho, destino, transparente=False):
        estudio.posicionar_camera(self.camera, quadro)
        self.cena.render.resolution_x, self.cena.render.resolution_y = tamanho
        self.cena.render.resolution_percentage = 100
        self.cena.render.film_transparent = transparente
        self.cena.render.image_settings.color_mode = "RGBA" if transparente else "RGB"
        self.fundo.hide_render = transparente
        self.cena.render.filepath = str(destino)
        Path(destino).parent.mkdir(parents=True, exist_ok=True)
        inicio = time.time()
        bpy.ops.render.render(write_still=True)
        return time.time() - inicio


def lado_da_lateral(graus):
    """De que lado da foto aparece a lateral da máquina (as faces x+ e x- do .glb): -1 esquerda, +1 direita.

    A lateral x+ gira para (cos g, sen g) e aparece se sen g < 0, do lado de cos g; a x-, o
    contrário: os dois casos dão -sinal(sen 2g). De frente, de costas ou de lado: a esquerda.
    """
    dobro = math.sin(math.radians(2 * graus))
    return 1 if dobro < -1e-6 else -1


def tamanho_do_mestre(saida, previa, fator=0.0):
    """O tamanho do render: o lado maior `previa`; ou `fator` x a foto do site; ou o 4K (3840)."""
    largura, altura = saida
    lado = previa or (round(max(saida) * fator) if fator else LADO_4K)
    return (lado, round(lado * altura / largura)) if largura >= altura else (round(lado * largura / altura), lado)


def enquadramentos(produto, est):
    """O quadro de cada tomada, calculado no adesivo de referência (o primeiro com 3D)."""
    quadros = {}
    for nome, tomada in produto["tomadas"].items():
        est.girar(tomada["giro"])
        pontos = est.pontos(tomada.get("detalhe"))
        largura, altura = tomada["saida"]
        quadros[nome] = estudio.enquadrar(
            pontos, tomada["camera"], largura / altura, margem=tomada.get("margem", 0.075),
            lente=tomada.get("lente", 60.0), inclinacao_fixa=tomada.get("inclinacao"))
        if tomada.get("detalhe"):  # a caixa que vale na foto é a da máquina inteira (cortada)
            caixa = estudio.projetar_no_quadro(est.pontos(), quadros[nome])
            quadros[nome]["caixa_maquina"] = tuple(min(max(c, 0.0), 1.0) for c in caixa)
    return quadros


def destinos(variante, tomada, dados=None):
    """Os arquivos do site desta foto (caminhos no repositório)."""
    if dados is not None and dados.get("so_mestre"):
        return []
    if "glb" in variante:
        return [f"{variante['pasta']}/{tomada}.webp", *variante.get("extras", {}).get(tomada, ())]
    caminho = variante.get("fotos", {}).get(tomada)
    return [caminho] if caminho else []


def chave_da_area(caminho, tomada):
    caminho = Path(caminho)
    if caminho.parent.name == "capas_catalogo":
        return f"produto_{caminho.stem}"
    if tomada == "capa":
        return f"capa_{caminho.parent.name}"
    return f"vista_{caminho.parent.name}_{caminho.stem}"


def fotografar(chave, args, relatorio):
    produto = PRODUTOS[chave]
    referencia = next(v for v in produto["variantes"] if "glb" in v)
    variantes = [v for v in produto["variantes"] if not args.variante or v["chave"] in args.variante]
    quadros = None
    areas = {}
    for variante in [referencia] + [v for v in produto["variantes"] if v is not referencia]:
        if variante not in variantes and quadros is not None:
            continue
        est = Estudio(produto, variante, args.amostras)
        if quadros is None:
            quadros = enquadramentos(produto, est)
            if variante not in variantes:
                continue
        for aviso in est.avisos:
            print("AVISO:", aviso)
        relatorio.setdefault(chave, {}).setdefault("avisos", []).extend(est.avisos)
        relatorio[chave].setdefault("materiais", {})[variante["chave"]] = est.relatorio
        tomadas = [t for t, dados in produto["tomadas"].items() if (not args.tomada or t in args.tomada) and (
            destinos(variante, t, dados) or (dados.get("so_mestre") and "glb" in variante))]
        for nome in tomadas:
            tomada = produto["tomadas"][nome]
            quadro = dict(quadros[nome])
            caixa = quadro.get("caixa_maquina", quadro["caixa"])
            if est.malhas:
                est.girar(tomada["giro"])
                propria = estudio.projetar_no_quadro(est.pontos(), quadro)
                if not tomada.get("detalhe") and (min(propria[:2]) < 0.005 or max(propria[2:]) > 0.995):
                    aviso = f"{variante['chave']}/{nome}: a máquina passa da borda da foto ({propria})"
                    print("AVISO:", aviso)
                    relatorio[chave]["avisos"].append(aviso)
            elif est.cartao is None or est.cartao_tomada != nome:
                if est.cartao is not None:
                    bpy.data.objects.remove(est.cartao, do_unlink=True)
                est.cartao, caixa, est.cartao_png = estudio.cartao_da_foto(RAIZ / variante["foto"], quadro, quadro["caixa"])
                est.cartao_tomada = nome
            est.luz(tomada.get("luz", "estudio"))
            # a principal do lado em que a face grande da máquina (as laterais, x do .glb) aparece
            estudio.espelhar_luzes(est.luzes, tomada.get("principal", lado_da_lateral(tomada["giro"] + produto.get("frente", 0))))
            transparente = bool(tomada.get("transparente"))
            tamanho = tamanho_do_mestre(tomada["saida"], args.previa, args.fator)
            mestre = Path(args.mestres) / chave / variante["chave"] / f"{nome}.png"
            if args.acabar and mestre.exists():  # (só o acabamento, do mestre que já está na pasta)
                segundos = 0.0
            else:
                segundos = est.render(quadro, tamanho, mestre, transparente)
                if not est.malhas:  # a foto da fábrica entra no lugar do cartão
                    from PIL import Image

                    acabamento.colar_foto(Image.open(mestre), est.cartao_png, caixa).save(mestre)
            print(f"{chave}/{variante['chave']}/{nome}: {tamanho[0]}x{tamanho[1]} em {segundos:.0f} s")
            relatorio[chave].setdefault("tempos", {})[f"{variante['chave']}/{nome}"] = round(segundos, 1)
            final = acabamento.acabar(mestre, tomada["saida"], transparente=transparente)
            if tomada.get("so_mestre"):  # (a foto pronta fica junto do mestre, fora do site)
                acabamento.gravar_webp(final, Path(args.mestres) / chave / variante["chave"] / "site" / f"{nome}.webp")
            for caminho in destinos(variante, nome, tomada):
                alvo = RAIZ / caminho if args.site else Path(args.mestres) / chave / variante["chave"] / "site" / Path(caminho).name
                if "capas_catalogo" in caminho and not args.site:
                    alvo = alvo.with_name("catalogo-" + alvo.name)
                # o peso que o site aceita: a capa do card até 250 KB, as vistas da galeria até 200 KB
                limite = 250 * 1024 if nome == "capa" or "capas_catalogo" in caminho else 200 * 1024
                q = acabamento.gravar_webp(final, alvo, limite=limite)
                print(f"   -> {alvo} (webp q{q}, {alvo.stat().st_size // 1024} KB)")
                if not transparente:
                    areas[chave_da_area(caminho, nome)] = [round(c, 3) for c in caixa]
    if args.site and areas:
        dados = json.loads(AREAS.read_text(encoding="utf-8"))
        dados.update(areas)
        AREAS.write_text(json.dumps(dict(sorted(dados.items())), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    relatorio[chave]["quadros"] = {n: {k: (list(v) if isinstance(v, tuple) else v) for k, v in q.items()}
                                   for n, q in (quadros or {}).items()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--produto", nargs="*", choices=sorted(PRODUTOS), help="as máquinas (todas, sem nada)")
    parser.add_argument("--variante", nargs="*", help="só estes adesivos (as chaves de produtos.py)")
    parser.add_argument("--tomada", nargs="*", help="só estas tomadas (capa, frente, lado_direito...)")
    parser.add_argument("--mestres", default=str(AQUI / "saida"), help="a pasta dos mestres (fora do repositório)")
    parser.add_argument("--previa", type=int, default=0, help="o lado maior do render, para conferir (no lugar do --fator)")
    parser.add_argument("--fator", type=float, default=2.0,
                        help="o render em N vezes a foto do site (2 = 3200 px na capa de 1600; 2,4 = o 4K); 0 = 3840")
    parser.add_argument("--amostras", type=int, default=12,
                        help="as amostras máximas (adaptativas) por pixel; o OpenImageDenoise limpa o resto")
    parser.add_argument("--site", action="store_true", help="grava as fotos no site (core/static/...)")
    parser.add_argument("--acabar", action="store_true",
                        help="não renderiza o que já tem mestre na pasta: só refaz o acabamento e as fotos do site")
    args = parser.parse_args(argv)
    arquivo = Path(args.mestres) / "relatorio.json"
    try:  # (o relatório soma as rodadas na mesma pasta: uma máquina por vez, se quiser)
        relatorio = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        relatorio = {}
    for chave in args.produto or PRODUTOS:
        relatorio.pop(chave, None)
    inicio = time.time()
    Path(args.mestres).mkdir(parents=True, exist_ok=True)
    for chave in args.produto or PRODUTOS:
        fotografar(chave, args, relatorio)
        # (a cada máquina: uma rodada interrompida não perde o que já fez)
        arquivo.write_text(json.dumps(relatorio, indent=1, ensure_ascii=False), encoding="utf-8")
    relatorio["total_s"] = round(time.time() - inicio)
    arquivo.write_text(json.dumps(relatorio, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Pronto em {relatorio['total_s']} s. Relatório: {arquivo}")


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None)
