"""Os adesivos: a mesma máquina com outra arte, num produto só (LEIA-ME, seção 72).

O cliente: "vc deve deixar apenas um objeto ... como no boliche" e "EU QUERO
OS DOIS OBJETOS 3D, NO MESMO BRINQUEDO" -- "TUDO DEVE AFUNILAR PARA UM
OBJETO SÓ, PODENDO VISUALIZAR, EM ÁREAS 3D E ETC, TAMBÉM DEVE SER POSSÍVEL
MUDAR PARA VER OS ADESIVOS".

O MECANISMO (para estes pares e os próximos):
  * o produto é UM objeto: uma página, um card, um item no carrinho e no
    orçamento, uma máquina na Arena. A ficha da outra arte (a `origem` do
    core.models.VarianteAdesivo) fica DESATIVADA, sem apagar nada (pedidos,
    orçamentos e favoritos seguem apontando para ela), e o endereço dela
    redireciona (301) para o produto;
  * a galeria do produto tem as fotos das duas artes: as da ficha entram
    depois das dele (`ImagemBrinquedo.PAPEL_OUTRA_ARTE`, os mesmos arquivos
    do Cloudinary, sem subir nada: `unificar`); sem medidas, o produto fica
    com as da ficha;
  * os DOIS 3D ficam no produto: em toda área 3D (a página, a Arena, o "Ver
    em 3D" da proposta) o controle "Adesivo: A · B" (site/arena/adesivos3d.js)
    troca o .glb ali mesmo, sem sair da tela (`modelos_3d`). O adesivo
    escolhido segue para o carrinho como observação.

JUNTAR UM PAR NOVO: um item em PARES e uma migração de dados que chame
`migrar` e `unificar_todos` (como a 0161 e a 0166).
"""

import unicodedata

from django.db import transaction

#: Os pares juntados: o produto (o adesivo padrão, as fotos dele) e as fichas que viram adesivos dele.
#: (nome do produto, (nome do adesivo padrão, slug)), [(nome da ficha, nome do adesivo, slug)].
PARES = (
    (("Air Game Kids", ("Astronautas", "astronautas")),
     [("Air Game Kids Alienígenas", "Alienígenas", "alienigenas")]),
    # o gabinete do Basquete Home (o azul) e o mesmo gabinete com os adesivos em quadrinhos (o
    # "Basquete Street Quadrinhos" de antes: a folha é a do Basquete Home, LEIA-ME 61). O
    # Basquete Street (a estrutura aberta com a rede) fica sozinho.
    (("Basquete Home", ("Azul", "azul")),
     [("Basquete Home Quadrinhos", "Quadrinhos", "quadrinhos")]),
)

#: O preço do produto que fica, quando ele está sem preço (o cliente: "estes dois precisam estar
#: juntos urgentemente, com o valor de 6990,00"). O preço que já está no produto nunca é trocado,
#: e o da ficha que vira adesivo é ignorado (juntar não copia nada da ficha para o produto).
PRECO_SE_VAZIO = {"Air Game Kids": "6990.00"}

#: As fichas renomeadas antes de virar adesivo: (a chave do cadastro, o nome de antes).
RENOMEADAS = (("basquete-street-quadrinhos", "Basquete Street Quadrinhos"),)



def _normalizar(texto):
    texto = unicodedata.normalize("NFD", (texto or "").lower())
    return " ".join("".join(c for c in texto if unicodedata.category(c) != "Mn").split())


def _achar(nome, Brinquedos):
    alvo = _normalizar(nome)
    achados = [b for b in Brinquedos.objects.order_by("-ativo", "id") if _normalizar(b.nome_brinquedo) == alvo]
    return achados[0] if achados else None


def juntar(produto, padrao, fichas, Brinquedos, VarianteAdesivo, avisar=print):
    """Junta as `fichas` ao `produto` como adesivos dele. Pode rodar de novo (não duplica).

    `produto`: o nome; `padrao`: (nome do adesivo, slug) do próprio produto;
    `fichas`: [(nome da ficha, nome do adesivo, slug)]. A ficha vira um adesivo
    (as fotos e o 3D dela) e é desativada. Sem o produto, não faz nada.
    """
    base = _achar(produto, Brinquedos)
    if base is None:
        avisar(f"{produto}: não está no catálogo; nada a juntar.")
        return None
    with transaction.atomic():
        preco = PRECO_SE_VAZIO.get(produto)
        if preco and not base.valor_brinquedo:
            from decimal import Decimal

            base.valor_brinquedo = Decimal(preco)
            base.save(update_fields=["valor_brinquedo"])
            avisar(f"{base.nome_brinquedo}: estava sem preço; agora R$ {preco}.")
        VarianteAdesivo.objects.update_or_create(
            brinquedo=base, slug=padrao[1],
            defaults={"nome": padrao[0], "ordem": 1, "padrao": True, "origem": None},
        )
        for ordem, (nome_da_ficha, nome, slug) in enumerate(fichas, start=2):
            ficha = _achar(nome_da_ficha, Brinquedos)
            if ficha is None or ficha.pk == base.pk:
                avisar(f"{nome_da_ficha}: não está no catálogo; o adesivo {nome} fica para depois.")
                continue
            VarianteAdesivo.objects.update_or_create(
                brinquedo=base, slug=slug,
                defaults={"nome": nome, "ordem": ordem, "padrao": False, "origem": ficha},
            )
            if ficha.ativo:
                ficha.ativo = False
                ficha.save(update_fields=["ativo"])
            avisar(f"{nome_da_ficha} agora é o adesivo {nome} do {base.nome_brinquedo} (a ficha saiu das listas).")
    return base


def separar(produto, Brinquedos, VarianteAdesivo, avisar=print):
    """Desfaz `juntar`: as fichas voltam a ser produtos (ativos) e os adesivos saem."""
    base = _achar(produto, Brinquedos)
    if base is None:
        return None
    with transaction.atomic():
        for variante in VarianteAdesivo.objects.filter(brinquedo=base).select_related("origem"):
            if variante.origem is not None and not variante.origem.ativo:
                variante.origem.ativo = True
                variante.origem.save(update_fields=["ativo"])
        VarianteAdesivo.objects.filter(brinquedo=base).delete()
    avisar(f"{base.nome_brinquedo}: os adesivos voltaram a ser produtos à parte.")
    return base


def migrar(apps, schema_editor, avisar=print):
    """A migração de dados (a 0161): junta os PARES em todo lugar (só o banco: nada sobe).

    Antes, as fichas de RENOMEADAS ganham o nome de hoje (o "Basquete Street
    Quadrinhos" vira o "Basquete Home Quadrinhos", com as descrições das fotos).
    """
    from .cadastro_modelos import renomear_variante

    Brinquedos = apps.get_model("core", "Brinquedos")
    VarianteAdesivo = apps.get_model("core", "VarianteAdesivo")
    for chave, nome_antigo in RENOMEADAS:
        renomear_variante(
            chave, nome_antigo, Brinquedos, apps.get_model("core", "CategoriasBrinquedos"),
            apps.get_model("core", "ImagemBrinquedo"), apps.get_model("core", "ObjetoTresD"), avisar=avisar,
        )
    for (produto, padrao), fichas in PARES:
        juntar(produto, padrao, fichas, Brinquedos, VarianteAdesivo, avisar=avisar)


# ----------------------------------------------------------------------
# Um objeto só: as fotos e os 3D da outra arte no produto (a 0166)
# ----------------------------------------------------------------------

#: O 3D do próprio produto, quando ele não tem um: o dos Astronautas, feito do mesmo móvel do
#: Alienígenas (ferramentas/modelos3d/air-game-kids-astronautas/). (o .glb, o código)
TRES_D_PROPRIO = {"Air Game Kids": ("site/arena/modelos/air-game-kids-astronautas.glb", "air-game-kids-astronautas")}

#: As fotos da outra arte que entram na galeria do produto (as primeiras da galeria pública da ficha).
FOTOS_DA_OUTRA_ARTE = 3

PAPEL_OUTRA_ARTE = "outra_arte"
MEDIDAS = ("altura_m", "largura_m", "profundidade_m")


def _galeria_publica_da_ficha(ficha, ImagemBrinquedo):
    """As fotos que a página da ficha mostrava (as tipadas e a "original"), na ordem."""
    fotos = ImagemBrinquedo.objects.filter(brinquedo=ficha).order_by("ordem", "id")
    return [f for f in fotos if f.tipo or f.papel_na_capa == "original"][:FOTOS_DA_OUTRA_ARTE]


def unificar(base, Brinquedos, ImagemBrinquedo, ObjetoTresD, VarianteAdesivo, avisar=print):
    """Põe no produto o que era da ficha da outra arte. Pode rodar de novo (não duplica).

      * as medidas que faltam no produto (o Basquete Home: as do Quadrinhos);
      * as fotos da ficha na galeria do produto, depois das dele, apontando
        para os MESMOS arquivos (nada sobe para o Cloudinary);
      * o 3D próprio do produto, quando ele não tem um e há um feito para ele
        (TRES_D_PROPRIO: os Astronautas). O 3D da ficha continua nela: os dois
        aparecem no produto (`modelos_3d`).
    Nunca mexe no preço nem em nada que o produto já tenha.
    """
    from .objetos_3d import ler_glb_do_site

    fichas = [v.origem for v in VarianteAdesivo.objects.filter(brinquedo=base, origem__isnull=False).select_related("origem").order_by("ordem", "id")]
    with transaction.atomic():
        mudou = []
        for campo in MEDIDAS:
            if getattr(base, campo) in (None, ""):
                valor = next((getattr(f, campo) for f in fichas if getattr(f, campo) not in (None, "")), None)
                if valor is not None:
                    setattr(base, campo, valor)
                    mudou.append(campo)
        if mudou:
            base.save(update_fields=mudou)
            avisar(f"{base.nome_brinquedo}: as medidas que faltavam vieram da outra arte "
                   f"({', '.join(f'{c}={getattr(base, c)}' for c in mudou)}).")
        ja = set(ImagemBrinquedo.objects.filter(brinquedo=base).values_list("imagem", flat=True))
        ordem = max(ImagemBrinquedo.objects.filter(brinquedo=base).values_list("ordem", flat=True), default=0)
        for ficha in fichas:
            for foto in _galeria_publica_da_ficha(ficha, ImagemBrinquedo):
                nome = foto.imagem.name if hasattr(foto.imagem, "name") else str(foto.imagem)
                if not nome or nome in ja:
                    continue
                ordem += 1
                ImagemBrinquedo.objects.create(
                    brinquedo=base, tipo=None, ordem=ordem, imagem=nome, papel_na_capa=PAPEL_OUTRA_ARTE,
                    texto_alternativo=(foto.texto_alternativo or ficha.nome_brinquedo)[:180],
                )
                ja.add(nome)
                avisar(f"{base.nome_brinquedo}: a foto {nome} (de {ficha.nome_brinquedo}) entrou na galeria.")
        proprio = TRES_D_PROPRIO.get(_nome_da_lista(base.nome_brinquedo))
        if proprio and not ObjetoTresD.objects.filter(brinquedo=base).exists():
            caminho, codigo = proprio
            try:
                lido = ler_glb_do_site(caminho)
            except Exception:  # o .glb não está no static: fica sem, como antes
                lido = None
            if lido is not None:
                ObjetoTresD.objects.create(
                    brinquedo=base, arquivo_estatico=caminho, codigo=codigo,
                    cores=lido["cores"], medidas=lido["medidas"], ativo=True, exibir_na_arena=True,
                )
                avisar(f"{base.nome_brinquedo}: ganhou o 3D próprio ({caminho}).")
    return base


def _nome_da_lista(nome):
    """O nome como está em PARES/TRES_D_PROPRIO (sem acento nem maiúscula)."""
    alvo = _normalizar(nome)
    return next((n for n in TRES_D_PROPRIO if _normalizar(n) == alvo), nome)


def unificar_todos(apps, schema_editor=None, avisar=print):
    """A migração (a 0166): `unificar` em cada produto com outra arte, em todo lugar (só o banco)."""
    Brinquedos = apps.get_model("core", "Brinquedos")
    VarianteAdesivo = apps.get_model("core", "VarianteAdesivo")
    ids = VarianteAdesivo.objects.filter(origem__isnull=False).values_list("brinquedo_id", flat=True).distinct()
    for base in Brinquedos.objects.filter(pk__in=list(ids)).order_by("id"):
        unificar(base, Brinquedos, apps.get_model("core", "ImagemBrinquedo"), apps.get_model("core", "ObjetoTresD"),
                 VarianteAdesivo, avisar=avisar)


# ----------------------------------------------------------------------
# O que as telas usam
# ----------------------------------------------------------------------


def _objeto_3d(ficha):
    """O .glb da ficha: o do cadastro (ativo) ou o do site ligado pelo nome; None sem nenhum."""
    from . import arena
    from .models import ObjetoTresD
    from .objetos_3d import tabela_pronta

    registro = ObjetoTresD.objects.filter(brinquedo=ficha).first() if tabela_pronta() else None
    if registro is not None:
        if registro.ativo and registro.url:
            return {"url": registro.url, "codigo": registro.codigo or "", "cores": list(registro.cores or [])}
        return None
    modelo = arena.modelo_da_maquina(ficha.nome_brinquedo)
    if modelo:
        from sistema_interno.templatetags.interno_extras import estatico

        return {"url": estatico(modelo["arquivo"]), "codigo": modelo["id"], "cores": []}
    return None


def modelos_3d(brinquedo):
    """Os 3D do produto, um por adesivo: [{"nome", "url", "codigo"}] (o dele primeiro); [] sem outra arte.

    É o que o controle "Adesivo: A · B" das áreas 3D troca. O do próprio
    produto leva o nome do adesivo padrão (os Astronautas); o da ficha, o do
    adesivo dela (os Alienígenas). Adesivo sem 3D não entra.
    """
    from .models import VarianteAdesivo

    variantes = list(VarianteAdesivo.objects.filter(brinquedo=brinquedo, ativo=True).select_related("origem").order_by("ordem", "id"))
    if not any(v.origem_id for v in variantes):
        return []
    saida = []
    for variante in variantes:
        objeto = _objeto_3d(variante.origem or brinquedo)
        if objeto and objeto["url"] not in {m["url"] for m in saida}:
            saida.append({"nome": variante.nome, "url": objeto["url"], "codigo": objeto["codigo"], "padrao": variante.padrao})
    saida.sort(key=lambda m: not m["padrao"])
    return saida


def _nomes_dos_pares():
    nomes = set()
    for (produto, _padrao), fichas in PARES:
        nomes.add(_normalizar(produto))
        nomes.update(_normalizar(f[0]) for f in fichas)
    nomes.update(_normalizar(antigo) for _chave, antigo in RENOMEADAS)
    return nomes


def modelos_do_item(item):
    """Os 3D dos adesivos da linha da proposta: os do produto dela (ou do produto da ficha dela); [] sem.

    Só consulta o banco para os brinquedos dos PARES (pelo nome, sem
    consulta): a proposta com outros itens não paga nada a mais.
    """
    brinquedo = getattr(item, "brinquedo", None) if getattr(item, "brinquedo_id", None) else None
    if brinquedo is None or _normalizar(brinquedo.nome_brinquedo) not in _nomes_dos_pares():
        return []
    from .models import VarianteAdesivo

    base = brinquedo
    juntada = VarianteAdesivo.objects.filter(origem=brinquedo, ativo=True).select_related("brinquedo").first()
    if juntada is not None:
        base = juntada.brinquedo
    return modelos_3d(base)


def redirecionamento(brinquedo_id):
    """O produto para onde vai o endereço da ficha que foi juntada a ele, ou None."""
    from .models import VarianteAdesivo

    variante = (
        VarianteAdesivo.objects.filter(origem_id=brinquedo_id, origem__ativo=False, brinquedo__ativo=True, ativo=True)
        .only("brinquedo_id")
        .first()
    )
    return variante.brinquedo_id if variante else None


def completar_na_arena(dados):
    """Na Arena (core/views_arena.py): o produto uma vez, com os 3D dos adesivos para trocar.

    `adesivos3d`: os 3D do produto (o controle da ficha da Arena troca um
    pelo outro); `modelos_variantes`: os códigos deles (a Arena não os põe à
    parte, como objetos fora do catálogo). Sem 3D próprio, o produto entra na
    roda com o primeiro que houver.
    """
    from . import arena
    from .models import Brinquedos

    ids = [item.get("id") for item in dados if isinstance(item.get("id"), int)]
    if not ids:
        return
    from .models import VarianteAdesivo

    com_outra_arte = set(VarianteAdesivo.objects.filter(brinquedo_id__in=ids, origem__isnull=False, ativo=True)
                         .values_list("brinquedo_id", flat=True))
    if not com_outra_arte:
        return
    produtos = {b.pk: b for b in Brinquedos.objects.filter(pk__in=com_outra_arte)}
    for item in dados:
        if item.get("id") not in com_outra_arte:
            continue
        lista = modelos_3d(produtos[item["id"]])
        if not lista:
            continue
        item["modelos_variantes"] = [m["codigo"] for m in lista if m["codigo"]]
        if len(lista) > 1:
            item["adesivos3d"] = [{k: m[k] for k in ("nome", "url", "codigo")} for m in lista]
        if item.get("modelo"):
            continue
        primeiro = lista[0]
        modelo = next((m for m in arena.MODELOS_3D if m["id"] == primeiro["codigo"]), None)
        item["modelo"] = primeiro["url"]
        item["modelo_id"] = primeiro["codigo"]
        if modelo:
            item["medidas_modelo"] = list(modelo["medidas"])
            item["grupo"] = modelo.get("grupo", item.get("grupo"))
            item["reino"] = bool(modelo.get("reino"))
            item["jogos_no_espaco"] = arena.jogos_do_modelo(modelo)
