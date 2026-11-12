"""Os adesivos: a mesma máquina com outra arte, num objeto só (LEIA-ME, seção 72).

O cliente: "DEVE MUDAR A ESTRUTURA DOS OBJETOS, DEIXAR SOMENTE UM MAS COM O
OUTRO ADESIVO E SEU RESPECTIVO OBJETO 3D, A ESTRUTURA DEVE SER ASSIM, NÃO DOIS
OBJETOS" e "TUDO DEVE AFUNILAR PARA UM OBJETO SÓ, PODENDO VISUALIZAR, EM ÁREAS
3D E ETC, TAMBÉM DEVE SER POSSÍVEL MUDAR PARA VER OS ADESIVOS".

A ESTRUTURA (core.models.VarianteAdesivo): o produto é UM `Brinquedos`; cada
adesivo é dele, com as fotos dele (`ImagemBrinquedo.variante`) e o 3D dele
(`arquivo_3d` / `arquivo_estatico_3d`); o adesivo padrão usa as fotos e o 3D
do próprio produto. No site, em toda área 3D (a página, a Arena, o "Ver em
3D" da proposta), o controle "Adesivo: A · B" (site/arena/adesivos3d.js)
troca o .glb ali mesmo (`modelos_3d`); a galeria tem as fotos dos adesivos.

A HISTÓRIA (as migrações antigas ainda chamam as funções daqui, com os
modelos de então): a 0161 juntava o par deixando a outra arte como um produto
à parte desativado (`origem`; `juntar`, `migrar`); a 0166 copiava as fotos e
as medidas (`unificar_todos`); a 0169 (`estruturar`) passa para o produto
tudo o que era da ficha à parte -- as fotos, o 3D e TODAS as referências
(orçamentos, carrinhos, pedidos, promoções, combos, favoritos...) -- e a
APAGA; o endereço antigo redireciona pelo `id_antigo` do adesivo.

UM PAR NOVO: pelo painel (a seção "Adesivos" do cadastro do brinquedo), ou
um item em PARES e uma migração de dados como a 0169.
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

#: O preço do produto que fica, à força, na 0169 (o cliente: "MUDE O VALOR PARA 6990,00 DO AIR GAME").
PRECO_DO_PRODUTO = {"Air Game Kids": "6990.00"}

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
        medidas_das_fichas = [_medidas_da_ficha(f) for f in fichas]
        for i, campo in enumerate(MEDIDAS):
            if getattr(base, campo) in (None, ""):
                valor = next((m[i] for m in medidas_das_fichas if m and m[i] not in (None, "")), None)
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


def _medidas_da_ficha(ficha):
    """(altura, largura, profundidade) da ficha; sem elas no cadastro, as do 3D dela (core/cadastro_modelos.py)."""
    medidas = tuple(getattr(ficha, campo) for campo in MEDIDAS)
    if None not in medidas:
        return medidas
    from decimal import Decimal

    from .cadastro_modelos import CADASTROS

    alvo = _normalizar(ficha.nome_brinquedo)
    for dados in CADASTROS.values():
        nomes = {_normalizar(n) for n in (dados.get("nomes") or ()) + (dados["nome"],)}
        if alvo in nomes and dados.get("medidas"):
            return tuple(Decimal(v) for v in dados["medidas"])
    return medidas


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
# A 0169: a estrutura nova (a ficha à parte vira parte do produto e é apagada)
# ----------------------------------------------------------------------


def _modelos_com_tipo_de_conteudo(apps):
    """Os modelos com uma chave genérica (content_type + object_id): o carrinho, o pedido..."""
    saida = []
    for modelo in apps.get_models():
        campos = {f.name: f for f in modelo._meta.get_fields() if getattr(f, "concrete", False)}
        for campo in campos.values():
            alvo = getattr(campo, "related_model", None)
            if campo.is_relation and alvo is not None and alvo._meta.label_lower == "contenttypes.contenttype":
                id_do_objeto = campo.name.replace("content_type", "object_id")
                if id_do_objeto in campos:
                    saida.append((modelo, campo.name, id_do_objeto))
    return saida


def _repassar(linhas, campo, base, avisar, nome):
    """Aponta as `linhas` (um queryset) para o produto; a linha repetida (o favorito do mesmo usuário) sai."""
    from django.db import IntegrityError

    try:
        with transaction.atomic():
            n = linhas.update(**{campo: base.pk})
        return n
    except IntegrityError:
        pass
    n = 0
    for linha in list(linhas):
        try:
            with transaction.atomic():
                type(linha).objects.filter(pk=linha.pk).update(**{campo: base.pk})
            n += 1
        except IntegrityError:
            type(linha).objects.filter(pk=linha.pk).delete()
            avisar(f"{nome} #{linha.pk}: já havia o mesmo para o {base.nome_brinquedo}; o repetido saiu.")
    return n


def _passar_para_o_produto(apps, variante, avisar):
    """Tudo o que era da ficha à parte (a `origem` do adesivo) passa para o produto; a ficha é apagada."""
    from . import arena

    Brinquedos = apps.get_model("core", "Brinquedos")
    ImagemBrinquedo = apps.get_model("core", "ImagemBrinquedo")
    ObjetoTresD = apps.get_model("core", "ObjetoTresD")
    VarianteAdesivo = apps.get_model("core", "VarianteAdesivo")
    ficha, base = variante.origem, variante.brinquedo
    if ficha.pk == base.pk:
        return

    # o 3D da ficha passa para o adesivo (o arquivo é o mesmo: nada sobe)
    objeto = ObjetoTresD.objects.filter(brinquedo=ficha).first()
    if not (variante.arquivo_3d or variante.arquivo_estatico_3d):
        if objeto is not None:
            variante.arquivo_3d = objeto.arquivo.name if objeto.arquivo else ""
            variante.arquivo_estatico_3d = objeto.arquivo_estatico or ""
            variante.codigo_3d = objeto.codigo or ""
            variante.cores_3d = list(objeto.cores or [])
            variante.medidas_3d = list(objeto.medidas or [])
        else:
            modelo = arena.modelo_da_maquina(ficha.nome_brinquedo)
            if modelo:
                variante.arquivo_estatico_3d = modelo["arquivo"]
                variante.codigo_3d = modelo["id"]
                variante.medidas_3d = list(modelo["medidas"])
    variante.id_antigo = ficha.pk
    variante.save()

    # as fotos da ficha viram fotos do produto, do adesivo (os mesmos arquivos)
    do_produto = {f.imagem.name: f for f in ImagemBrinquedo.objects.filter(brinquedo=base)}
    ordem = max([f.ordem for f in do_produto.values()] or [0])
    for foto in ImagemBrinquedo.objects.filter(brinquedo=ficha).order_by("ordem", "id"):
        copia = do_produto.get(foto.imagem.name)
        if copia is not None:  # a cópia da 0166: fica, agora do adesivo
            ImagemBrinquedo.objects.filter(pk=copia.pk).update(variante=variante, tipo=None)
            foto.delete()
            continue
        ordem += 1
        ImagemBrinquedo.objects.filter(pk=foto.pk).update(
            brinquedo=base, variante=variante, tipo=None, ordem=ordem, papel_na_capa="outra_arte")

    # TODAS as referências à ficha passam para o produto (pelas relações que apontam para Brinquedos)
    for relacao in Brinquedos._meta.related_objects:
        modelo = relacao.related_model
        if modelo in (ImagemBrinquedo, ObjetoTresD, VarianteAdesivo):
            continue
        campo = relacao.field.name
        if relacao.many_to_many:
            for obj in modelo.objects.filter(**{campo: ficha}):
                lista = getattr(obj, campo)
                lista.add(base)
                lista.remove(ficha)
                avisar(f"{modelo._meta.verbose_name} #{obj.pk}: {ficha.nome_brinquedo} -> {base.nome_brinquedo}.")
            continue
        linhas = modelo.objects.filter(**{campo: ficha})
        if relacao.one_to_one:
            if modelo.objects.filter(**{campo: base}).exists():
                linhas.delete()
            else:
                linhas.update(**{campo: base.pk})
            continue
        n = _repassar(linhas, relacao.field.attname, base, avisar, modelo._meta.verbose_name)
        if n:
            avisar(f"{modelo._meta.verbose_name}: {n} de {ficha.nome_brinquedo} -> {base.nome_brinquedo}.")
        # a composição do produto com ele mesmo (o conjunto e o item iguais) não fica
        outros = [f.name for f in modelo._meta.fields if f.is_relation and f.related_model is Brinquedos and f.name != campo]
        for outro in outros:
            modelo.objects.filter(**{campo: base, outro: base}).delete()

    # as chaves genéricas (o item do carrinho, o item do pedido): o produto, com o adesivo
    ContentType = apps.get_model("contenttypes", "ContentType")
    tipo = ContentType.objects.filter(app_label="core", model="brinquedos").first()
    if tipo is not None:
        for modelo, campo_tipo, campo_id in _modelos_com_tipo_de_conteudo(apps):
            linhas = modelo.objects.filter(**{campo_tipo: tipo, campo_id: ficha.pk})
            nomes = {f.name for f in modelo._meta.fields}
            for linha in list(linhas):
                igual = None
                if {"carrinho", "quantidade"} <= nomes:
                    filtro = {"carrinho_id": linha.carrinho_id, campo_tipo: tipo, campo_id: base.pk}
                    if "adesivo" in nomes:
                        filtro["adesivo"] = linha.adesivo or variante.nome
                    igual = modelo.objects.filter(**filtro).exclude(pk=linha.pk).first()
                if igual is not None:  # a mesma linha no carrinho: soma
                    modelo.objects.filter(pk=igual.pk).update(quantidade=igual.quantidade + linha.quantidade)
                    modelo.objects.filter(pk=linha.pk).delete()
                    continue
                mudar = {campo_id: base.pk}
                if "adesivo" in nomes and not linha.adesivo:
                    mudar["adesivo"] = variante.nome  # o item era da outra arte: o adesivo dela
                modelo.objects.filter(pk=linha.pk).update(**mudar)

    # a ficha sai (nada mais aponta para ela)
    VarianteAdesivo.objects.filter(origem=ficha).update(origem=None)
    nome = ficha.nome_brinquedo
    Brinquedos.objects.filter(pk=ficha.pk).delete()
    avisar(f"{nome} (id {variante.id_antigo}) agora é o adesivo {variante.nome} do {base.nome_brinquedo}; "
           "a ficha à parte foi apagada.")


def estruturar(apps, schema_editor=None, avisar=print):
    """A 0169: cada ficha à parte vira parte do produto (fotos, 3D, referências) e é apagada. Idempotente."""
    from decimal import Decimal

    Brinquedos = apps.get_model("core", "Brinquedos")
    VarianteAdesivo = apps.get_model("core", "VarianteAdesivo")
    for variante in VarianteAdesivo.objects.filter(origem__isnull=False).select_related("origem", "brinquedo"):
        with transaction.atomic():
            _passar_para_o_produto(apps, variante, avisar)
    for nome, preco in PRECO_DO_PRODUTO.items():
        produto = _achar(nome, Brinquedos)
        if produto is not None and produto.valor_brinquedo != Decimal(preco):
            produto.valor_brinquedo = Decimal(preco)
            produto.save(update_fields=["valor_brinquedo"])
            avisar(f"{produto.nome_brinquedo}: o preço agora é R$ {preco}.")


# ----------------------------------------------------------------------
# A 0173: todo brinquedo com o adesivo padrão (as fotos das posições e o 3D)
# ----------------------------------------------------------------------

#: O nome do adesivo padrão quando o brinquedo não tem um (os pares já têm: Astronautas, Azul).
NOME_DO_PADRAO = "Padrão"


def _posicao_pelo_arquivo(nome):
    """A posição (o `tipo`) de uma foto do cadastro dos nossos 3D, pelo nome do arquivo; None se não é."""
    from .cadastro_modelos import CADASTROS

    for chave, dados in CADASTROS.items():
        if f"{chave}-" not in nome:
            continue
        for arquivo, tipo, _texto in dados.get("fotos", ()):
            if tipo and f"{chave}-{arquivo.rsplit('.', 1)[0]}" in nome:
                return tipo
    return None


def padronizar(apps, schema_editor=None, avisar=print):
    """A 0173, em todo lugar e idempotente: todo brinquedo ganha o adesivo padrão explícito.

      * o adesivo padrão (o que já existe, ou um "Padrão") vira o
        `adesivo_padrao` do brinquedo, e as fotos sem adesivo passam para ele;
      * o 3D do brinquedo (o `ObjetoTresD`, ligado e ativo) é copiado para o
        adesivo padrão (o mesmo arquivo; o `ObjetoTresD` fica, para a Arena);
      * nas fotos dos outros adesivos, a posição volta pelo nome do arquivo
        (a 0169 a tinha tirado: a frente, os lados e o verso do Alienígenas).
    """
    Brinquedos = apps.get_model("core", "Brinquedos")
    VarianteAdesivo = apps.get_model("core", "VarianteAdesivo")
    ImagemBrinquedo = apps.get_model("core", "ImagemBrinquedo")
    ObjetoTresD = apps.get_model("core", "ObjetoTresD")
    criados = 0
    for brinquedo in Brinquedos.objects.order_by("id"):
        with transaction.atomic():
            padrao = (VarianteAdesivo.objects.filter(brinquedo=brinquedo, padrao=True).order_by("ordem", "id").first())
            if padrao is None:
                slug = "padrao"
                while VarianteAdesivo.objects.filter(brinquedo=brinquedo, slug=slug).exists():
                    slug += "-1"
                padrao = VarianteAdesivo.objects.create(brinquedo=brinquedo, nome=NOME_DO_PADRAO, slug=slug, ordem=1, padrao=True)
                criados += 1
            if brinquedo.adesivo_padrao_id != padrao.pk:
                Brinquedos.objects.filter(pk=brinquedo.pk).update(adesivo_padrao=padrao)
            ImagemBrinquedo.objects.filter(brinquedo=brinquedo, variante__isnull=True).update(variante=padrao)
            objeto = ObjetoTresD.objects.filter(brinquedo=brinquedo, ativo=True).first()
            if objeto is not None and not (padrao.arquivo_3d or padrao.arquivo_estatico_3d):
                VarianteAdesivo.objects.filter(pk=padrao.pk).update(
                    arquivo_3d=objeto.arquivo.name if objeto.arquivo else "",
                    arquivo_estatico_3d=objeto.arquivo_estatico or "",
                    codigo_3d=objeto.codigo or "", cores_3d=list(objeto.cores or []), medidas_3d=list(objeto.medidas or []),
                )
            # as posições das fotos dos outros adesivos
            for variante in VarianteAdesivo.objects.filter(brinquedo=brinquedo, padrao=False):
                tomadas = set(ImagemBrinquedo.objects.filter(variante=variante).exclude(tipo=None).values_list("tipo", flat=True))
                for foto in ImagemBrinquedo.objects.filter(variante=variante, tipo=None).order_by("ordem", "id"):
                    tipo = _posicao_pelo_arquivo(foto.imagem.name or "")
                    if tipo and tipo not in tomadas:
                        ImagemBrinquedo.objects.filter(pk=foto.pk).update(tipo=tipo)
                        tomadas.add(tipo)
    avisar(f"Adesivo padrão: {criados} criados; todo brinquedo tem o dele, com as fotos e o 3D.")


#: As posições tiradas do 3D (as vistas em core/static/site/arena/modelos/<pasta>/), por produto e adesivo.
POSICOES_DO_3D = {
    ("Air Game Kids", "Astronautas"): ("air-game-kids-astronautas", (
        ("lado_direito.webp", "lado_direito", "lado direito"),
        ("lado_esquerdo.webp", "lado_esquerdo", "lado esquerdo"),
        ("verso.webp", "verso", "verso"),
        ("frente.webp", None, "de frente, em 3/4"),
        ("tampo.webp", None, "o tampo, de cima"),
    )),
}


def subir_posicoes(Brinquedos, VarianteAdesivo, ImagemBrinquedo, avisar=print):
    """As posições que saem do 3D (POSICOES_DO_3D) sobem como fotos do adesivo. Pode rodar de novo."""
    from django.contrib.staticfiles import finders
    from django.core.files import File

    for (produto, adesivo), (pasta, fotos) in POSICOES_DO_3D.items():
        brinquedo = _achar(produto, Brinquedos)
        variante = VarianteAdesivo.objects.filter(brinquedo=brinquedo, nome=adesivo).first() if brinquedo else None
        if variante is None:
            continue
        ordem = max(ImagemBrinquedo.objects.filter(brinquedo=brinquedo).values_list("ordem", flat=True), default=1)
        for arquivo, tipo, rotulo in fotos:
            caminho = finders.find(f"site/arena/modelos/{pasta}/{arquivo}")
            if not caminho:
                continue
            nome = f"{pasta}-{arquivo}"
            ja = ImagemBrinquedo.objects.filter(variante=variante)
            if (tipo and ja.filter(tipo=tipo).exists()) or ja.filter(imagem__contains=f"{pasta}-{arquivo.rsplit('.', 1)[0]}").exists():
                continue
            ordem += 1
            foto = ImagemBrinquedo(brinquedo=brinquedo, variante=variante, tipo=tipo, ordem=ordem,
                                   texto_alternativo=f"{brinquedo.nome_brinquedo} ({adesivo}): {rotulo}"[:180])
            with open(caminho, "rb") as origem:
                foto.imagem.save(nome, File(origem), save=True)
            avisar(f"{brinquedo.nome_brinquedo} ({adesivo}): a foto {rotulo} subiu.")


def subir_posicoes_no_deploy(apps, schema_editor=None, avisar=print):
    """A 0174: só no Render (o Cloudinary só está lá); se a subida falhar, o deploy segue."""
    from django.conf import settings

    if not getattr(settings, "IS_RENDER", False):
        return
    try:
        subir_posicoes(apps.get_model("core", "Brinquedos"), apps.get_model("core", "VarianteAdesivo"),
                       apps.get_model("core", "ImagemBrinquedo"), avisar=avisar)
    except Exception as erro:  # o deploy segue; o comando refaz depois
        avisar(f"As posições do 3D não subiram agora ({erro!r}). Rode: python manage.py posicoes_dos_adesivos")


# ----------------------------------------------------------------------
# O que as telas usam (a estrutura nova)
# ----------------------------------------------------------------------


def _objeto_3d_do_produto(brinquedo):
    """O .glb do próprio produto: o do cadastro (ativo) ou o do site ligado pelo nome; None sem nenhum."""
    from . import arena
    from .models import ObjetoTresD
    from .objetos_3d import tabela_pronta

    registro = ObjetoTresD.objects.filter(brinquedo=brinquedo).first() if tabela_pronta() else None
    if registro is not None:
        if registro.ativo and registro.url:
            return {"url": registro.url, "codigo": registro.codigo or ""}
        return None
    modelo = arena.modelo_da_maquina(brinquedo.nome_brinquedo)
    if modelo:
        from sistema_interno.templatetags.interno_extras import estatico

        return {"url": estatico(modelo["arquivo"]), "codigo": modelo["id"]}
    return None


def modelos_3d(brinquedo):
    """Os 3D do produto, um por adesivo: [{"nome", "url", "codigo", "padrao"}] (o padrão primeiro); [] sem adesivos.

    O adesivo padrão é o 3D do próprio produto; os outros, o 3D de cada um
    (`VarianteAdesivo.url_3d`). Adesivo sem 3D não entra. É o que o controle
    "Adesivo: A · B" das áreas 3D troca.
    """
    from .models import VarianteAdesivo

    variantes = list(VarianteAdesivo.objects.filter(brinquedo=brinquedo, ativo=True).order_by("ordem", "id"))
    if len(variantes) < 2 and not any(not v.padrao for v in variantes):
        return []
    saida = []
    for variante in variantes:
        url, codigo = _tres_d_do_adesivo(brinquedo, variante)
        if url and url not in {m["url"] for m in saida}:
            saida.append({"nome": variante.nome, "slug": variante.slug, "url": url, "codigo": codigo, "padrao": variante.padrao})
    saida.sort(key=lambda m: not m["padrao"])
    return saida


def _tres_d_do_adesivo(brinquedo, variante):
    """(url, código) do 3D do adesivo: o dele; o padrão sem um, o do produto (o do cadastro ou o do site)."""
    if variante.url_3d:
        return variante.url_3d, variante.codigo_3d
    if variante.padrao:
        objeto = _objeto_3d_do_produto(brinquedo)
        if objeto:
            return objeto["url"], objeto["codigo"]
    return "", ""


def adesivos_da_pagina(brinquedo):
    """Os adesivos para a página do produto: [{"nome", "slug", "padrao", "fotos", "url_3d"}] (o padrão primeiro).

    `fotos`: as fotos das posições DO adesivo (core.models.galeria_publica:
    nunca as de fundo branco). Trocar o adesivo troca as fotos e o 3D.
    """
    from .models import VarianteAdesivo, galeria_publica

    fotos = list(brinquedo.imagens_brinquedo.all())
    saida = []
    for variante in VarianteAdesivo.objects.filter(brinquedo=brinquedo, ativo=True).order_by("-padrao", "ordem", "id"):
        url, _codigo = _tres_d_do_adesivo(brinquedo, variante)
        if variante.padrao or variante.pk == brinquedo.adesivo_padrao_id:
            galeria = galeria_publica(fotos, brinquedo.adesivo_padrao_id or variante.pk)
        else:
            galeria = galeria_publica(fotos, adesivo_id=variante.pk)
        saida.append({"nome": variante.nome, "slug": variante.slug, "padrao": variante.padrao, "fotos": galeria, "url_3d": url})
    return saida


def produtos_com_adesivos():
    """Os ids dos produtos com outro adesivo (uma consulta)."""
    from .models import VarianteAdesivo

    try:
        return set(VarianteAdesivo.objects.filter(padrao=False, ativo=True).values_list("brinquedo_id", flat=True))
    except Exception:  # a tabela ainda sem as colunas (o código chegou antes da migração)
        return set()


def modelos_do_item(item, com_adesivos=None):
    """Os 3D dos adesivos da linha da proposta: os do produto dela; [] sem.

    `com_adesivos`: os ids dos produtos com adesivos (`produtos_com_adesivos`,
    uma consulta para a proposta inteira). Sem ele, só os brinquedos dos
    PARES (pelo nome, sem consulta) são olhados: a lista do painel não paga
    nada a mais.
    """
    brinquedo = getattr(item, "brinquedo", None) if getattr(item, "brinquedo_id", None) else None
    if brinquedo is None:
        return []
    if com_adesivos is not None:
        if brinquedo.pk not in com_adesivos:
            return []
    elif _normalizar(brinquedo.nome_brinquedo) not in _nomes_dos_pares():
        return []
    return modelos_3d(brinquedo)


def _nomes_dos_pares():
    nomes = set()
    for (produto, _padrao), fichas in PARES:
        nomes.add(_normalizar(produto))
        nomes.update(_normalizar(f[0]) for f in fichas)
    nomes.update(_normalizar(antigo) for _chave, antigo in RENOMEADAS)
    return nomes


def redirecionamento(brinquedo_id):
    """O produto para onde vai o endereço do produto à parte que virou o adesivo dele, ou None."""
    from .models import VarianteAdesivo

    try:
        variante = (
            VarianteAdesivo.objects.filter(id_antigo=brinquedo_id, brinquedo__ativo=True, ativo=True)
            .only("brinquedo_id").first()
        )
    except Exception:
        return None
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
    com_adesivos = produtos_com_adesivos() & set(ids)
    if not com_adesivos:
        return
    produtos = {b.pk: b for b in Brinquedos.objects.filter(pk__in=com_adesivos)}
    for item in dados:
        if item.get("id") not in com_adesivos:
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
