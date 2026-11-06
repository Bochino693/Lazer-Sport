"""Os objetos 3D (.glb) dos brinquedos, numa tela só do painel interno.

O cadastro do brinquedo já aceita o .glb (BrinquedoAdmin). O que faltava
era um lugar para VER o conjunto: qual máquina tem objeto, qual não tem,
qual está na Arena, as cores e as medidas lidas do arquivo -- e abrir o
3D ali mesmo, sem sair do painel. Daqui também se sobe um objeto para um
brinquedo, se liga um dos objetos que vêm com o site a um brinquedo, e,
quando a máquina tem jogo no simulador, se abre a prévia.

TUDO-OU-NADA. Cada ação roda numa transação (RespostaJSONMixin). O .glb
só vai para o armazenamento depois de conferido (cabeçalho, cores e
medidas lidos: `core.objetos_3d.validar_glb`); se a gravação no banco
falhar depois disso, o arquivo recém-guardado é apagado -- não fica
objeto sem registro nem registro sem objeto. Só o superadministrador
entra aqui, como na tela dos jogos.
"""

from __future__ import annotations

import logging
import unicodedata

from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.text import slugify
from django.views import View

import json

from core import arena, composicao, conversor_3d, modelo_fotos, produtos_parecidos
from core.fotos import reduzir_imagem
from core.models import (
    Brinquedos,
    BrinquedosProjeto,
    ComponenteBrinquedo,
    ModuloTresD,
    ObjetoTresD,
    ObjetoTresDProjeto,
)
from core.objetos_3d import ler_glb_do_site, tabela_pronta, validar_glb

from .templatetags.interno_extras import estatico
from .utils import ErroDeFormulario, endereco_do_site, exigir_confirmacao_exclusao
from .views import RespostaJSONMixin, SuperusuarioInternoRequiredMixin

log = logging.getLogger("sistema_interno.objetos_3d")

#: Os objetos que vêm com o site, pelo caminho em static (o que o formulário
#: pode escolher). Qualquer outro caminho é recusado.
MODELOS_DO_SITE = {modelo["arquivo"]: modelo for modelo in arena.MODELOS_3D}


#: O maior arquivo 3D que se converte (o .zip com as texturas) e a maior foto.
TETO_DO_ARQUIVO_3D = 80 * 1024 * 1024
TETO_DA_FOTO = 20 * 1024 * 1024


def _titulo_e_texto_do_projeto(projeto):
    """O nome e o texto de um projeto: o do Projeto (a vitrine), senão o do brinquedo projetado."""
    try:
        vitrine = projeto.projeto
    except Exception:  # noqa: BLE001 -- brinquedo projetado sem projeto na vitrine
        vitrine = None
    titulo = (vitrine.titulo if vitrine else "") or projeto.nome_brinquedo_projeto
    texto = "\n".join(t for t in ((vitrine.descricao if vitrine else ""), projeto.descricao) if t)
    return titulo, texto


#: A vista de cada foto pela legenda ("Lateral direita", "vista de cima"...).
_VISTAS_DA_LEGENDA = (
    ("esquerda", ("esquerd",)),
    ("direita", ("direit",)),
    ("costas", ("costa", "tras", "traseir", "fundo")),
    ("cima", ("cima", "topo", "superior", "planta", "aerea")),
    ("frente", ("frente", "frontal")),
)


def vista_provavel(legenda, indice):
    """A vista da foto pela legenda; sem pista, a 1ª é a frente e a 2ª o lado direito."""
    texto = _texto_de_busca(legenda or "")
    for vista, pistas in _VISTAS_DA_LEGENDA:
        if any(p in texto for p in pistas):
            return vista
    return {0: "frente", 1: "direita"}.get(indice, "")


def _medidas_texto(medidas):
    try:
        altura, largura, profundidade = (float(x) for x in medidas)
    except (TypeError, ValueError):
        return ""
    return f"{altura:.2f} m × {largura:.2f} m × {profundidade:.2f} m".replace(".", ",")


def _texto_de_busca(*partes):
    """O que a busca da tela compara: tudo junto, minúsculo e sem acento.

    A busca roda no navegador, sem ir ao servidor (ver o script da tela),
    e tira o acento do que se digita do mesmo jeito: "pião" acha "Pião".
    """
    texto = " ".join(str(parte) for parte in partes if parte)
    sem_acento = "".join(c for c in unicodedata.normalize("NFD", texto) if not unicodedata.combining(c))
    return " ".join(sem_acento.lower().split())


def _jogos_do_modelo_do_site(modelo, site):
    """Os jogos da casa ligados a um objeto do site: o da máquina e os do espaço."""
    slugs = ([modelo["jogo"]] if modelo.get("jogo") else []) + list(modelo.get("jogos", ()))
    vistos, saida = set(), []
    for slug in slugs:
        jogo = arena.JOGOS_POR_SLUG.get(slug)
        if jogo and slug not in vistos:
            vistos.add(slug)
            saida.append({"slug": slug, "titulo": jogo["titulo"], "url": f"{site}/jogos/{slug}/"})
    return saida


def _foto_do_modelo_do_site(modelo):
    """A primeira foto da fábrica (o perfil), para o cartão; "" se não há."""
    fotos = modelo.get("fotos") or ()
    if not fotos or not modelo.get("pasta"):
        return ""
    return estatico(modelo["pasta"] + fotos[0][1])


class Objetos3DInnerView(RespostaJSONMixin, SuperusuarioInternoRequiredMixin, View):
    """Lista os brinquedos com o seu objeto 3D; sobe, liga, mostra/esconde e remove."""

    rota_padrao = "objetos_3d_inner"
    template_name = "objetos_3d_inner.html"

    def get(self, request):
        if not tabela_pronta(ObjetoTresD):
            return render(request, self.template_name, {"tabela_ausente": True, "linhas": []})

        site = endereco_do_site(request).rstrip("/")
        brinquedos = list(
            Brinquedos.objects.filter(ativo=True)
            .prefetch_related("objeto_3d", "categorias_brinquedos")
            .order_by("nome_brinquedo")
        )
        # o que vem dentro de cada conjunto (brinquedão, espaço esportivo) e o inverso
        nomes = {b.pk: b.nome_brinquedo for b in brinquedos}
        dentro, fora = {}, {}
        if tabela_pronta(ComponenteBrinquedo):
            for c in ComponenteBrinquedo.objects.filter(conjunto__ativo=True, item__ativo=True).order_by("ordem", "id"):
                dentro.setdefault(c.conjunto_id, []).append({"id": c.item_id, "nome": nomes.get(c.item_id, ""), "quantidade": c.quantidade})
                fora.setdefault(c.item_id, []).append({"id": c.conjunto_id, "nome": nomes.get(c.conjunto_id, "")})
        catalogo = list(nomes.items())
        linhas = []
        usados = {}
        usados_ligados = set()
        for brinquedo in brinquedos:
            objeto = getattr(brinquedo, "objeto_3d", None) if Brinquedos.objeto_3d.is_cached(brinquedo) else None
            slug_jogo = arena.jogo_da_maquina(brinquedo.nome_brinquedo)
            jogo = arena.JOGOS_POR_SLUG.get(slug_jogo)
            sugestao = arena.modelo_da_maquina(brinquedo.nome_brinquedo) if objeto is None else None
            linha = {
                "id": brinquedo.pk,
                "nome": brinquedo.nome_brinquedo,
                "capa": self._capa(brinquedo),
                "url_site": f"{site}/brinquedo/{brinquedo.pk}/#ver-3d",
                "jogo": {"slug": slug_jogo, "titulo": jogo["titulo"], "url": f"{site}/jogos/{slug_jogo}/"} if jogo else None,
                "objeto": None,
                "sugestao": {"arquivo": sugestao["arquivo"], "titulo": sugestao["titulo"]} if sugestao else None,
                "componentes": dentro.get(brinquedo.pk, []),
                "faz_parte_de": fora.get(brinquedo.pk, []),
                "pode_conter": composicao.pode_conter(brinquedo, [c.nome_categoria for c in brinquedo.categorias_brinquedos.all()]),
            }
            linha["pode_conter"] = linha["pode_conter"] or bool(linha["componentes"])
            linha["sugestoes_conjunto"] = (
                composicao.sugestoes(brinquedo, catalogo, [c["id"] for c in linha["componentes"]]) if linha["pode_conter"] else []
            )
            if objeto is not None:
                origem = "enviado" if objeto.arquivo else "do site"
                if objeto.arquivo_estatico:
                    usados[objeto.arquivo_estatico] = brinquedo.nome_brinquedo
                    if objeto.ativo:
                        usados_ligados.add(objeto.arquivo_estatico)
                linha["objeto"] = {
                    "id": objeto.pk,
                    "origem": origem,
                    "arquivo": (objeto.arquivo.name if objeto.arquivo else objeto.arquivo_estatico).rsplit("/", 1)[-1],
                    "url": objeto.url,
                    "cores": list(objeto.cores or []),
                    "medidas": _medidas_texto(objeto.medidas or []),
                    "codigo": objeto.codigo,
                    "exibir_na_arena": objeto.exibir_na_arena,
                    "ativo": objeto.ativo,
                    "no_ar": bool(objeto.ativo and objeto.url),
                }
            objeto_linha = linha["objeto"] or {}
            linha["busca"] = _texto_de_busca(
                linha["nome"], objeto_linha.get("arquivo"), objeto_linha.get("origem"),
                " ".join(objeto_linha.get("cores") or []), jogo["titulo"] if jogo else "",
                linha["sugestao"]["titulo"] if linha["sugestao"] else "",
            )
            linhas.append(linha)

        modelos_do_site = []
        for modelo in arena.MODELOS_3D:
            jogos = _jogos_do_modelo_do_site(modelo, site)
            usado_por = usados.get(modelo["arquivo"], "")
            modelos_do_site.append({
                "id": modelo["id"],
                "arquivo": modelo["arquivo"],
                "arquivo_nome": modelo["arquivo"].rsplit("/", 1)[-1],
                "titulo": modelo["titulo"],
                "medidas": _medidas_texto(modelo["medidas"]),
                "jogo": modelo.get("jogo", ""),
                "jogos": jogos,
                "usado_por": usado_por,
                "usado_ligado": modelo["arquivo"] in usados_ligados,
                # o cartão mostra a foto da fábrica e tira a prévia do próprio .glb
                "foto": _foto_do_modelo_do_site(modelo),
                "url": estatico(modelo["arquivo"]),
                "busca": _texto_de_busca(
                    modelo["titulo"], modelo["arquivo"], usado_por, "do site",
                    " ".join(j["titulo"] for j in jogos),
                ),
            })

        # Os três grupos da tela: no ar, desligados (voltam com "Religar") e
        # sem objeto -- estes com os que o site já tem pronto na frente.
        com_objeto = [l for l in linhas if l["objeto"] and l["objeto"]["no_ar"]]
        desligados = [l for l in linhas if l["objeto"] and not l["objeto"]["no_ar"]]
        sem_objeto_sugeridos = [l for l in linhas if not l["objeto"] and l["sugestao"]]
        sem_objeto_outros = [l for l in linhas if not l["objeto"] and not l["sugestao"]]
        modulos = [self._serializar_modulo(modulo) for modulo in ModuloTresD.objects.all()] if tabela_pronta(ModuloTresD) else []
        projetos = self._projetos()
        return render(request, self.template_name, {
            "projetos": projetos,
            "projetos_dados": projetos,
            "projetos_com_3d": [p for p in projetos if p["objeto"] and p["objeto"]["url"]],
            "tabela_projetos_3d": tabela_pronta(ObjetoTresDProjeto),
            "vistas": [(v, modelo_fotos.NOMES_DAS_VISTAS[v]) for v in modelo_fotos.VISTAS],
            "formatos_3d": ", ".join(conversor_3d.FORMATOS),
            "linhas": linhas,
            "linhas_dados": linhas,
            "com_objeto": com_objeto,
            "desligados": desligados,
            "sem_objeto_sugeridos": sem_objeto_sugeridos,
            "sem_objeto_outros": sem_objeto_outros,
            "total_sem_objeto": len(sem_objeto_sugeridos) + len(sem_objeto_outros),
            "modelos_do_site": modelos_do_site,
            "modulos": modulos,
            "modulos_dados": modulos,
            "categorias_modulo": ModuloTresD.Categoria.choices,
            "tabela_modulos": tabela_pronta(ModuloTresD),
            "total": len(linhas),
            "total_com_objeto": len(com_objeto),
            "total_na_arena": sum(1 for l in com_objeto if l["objeto"]["exibir_na_arena"]),
            "total_com_jogo": sum(1 for l in linhas if l["jogo"]),
            "three": "vendor/three/three.module.min.js",
            "site": site,
        })

    def _projetos(self):
        """Os projetos (brinquedos projetados) para a criação do 3D: nome, fotos e o 3D que já têm."""
        consulta = BrinquedosProjeto.objects.prefetch_related("imagens_brinquedo_projeto").order_by("-id")
        com_tabela = tabela_pronta(ObjetoTresDProjeto)
        saida = []
        for projeto in consulta:
            titulo, _texto = _titulo_e_texto_do_projeto(projeto)
            imagens = [img for img in projeto.imagens_brinquedo_projeto.all() if img.imagem]
            capa = ""
            if imagens:
                try:
                    capa = reduzir_imagem(imagens[0].imagem.url, 480)
                except Exception:  # noqa: BLE001
                    capa = ""
            objeto = None
            if com_tabela:
                existente = ObjetoTresDProjeto.objects.filter(projeto=projeto).select_related("produto").first()
                if existente:
                    objeto = {
                        "url": existente.url,
                        "medidas": _medidas_texto(existente.medidas or []),
                        "modo": {"paineis": "Painéis", "volume": "Volume", "arquivo": "Arquivo 3D"}.get(existente.modo, ""),
                        "produto": existente.produto_id,
                        "produto_nome": existente.produto.nome_brinquedo if existente.produto else "",
                    }
            saida.append({"id": projeto.pk, "titulo": titulo, "fotos": len(imagens), "capa": capa, "objeto": objeto,
                          "busca": _texto_de_busca(titulo, "projeto")})
        return saida

    @staticmethod
    def _serializar_modulo(modulo):
        return {
            "id": modulo.pk,
            "nome": modulo.nome,
            "categoria": modulo.categoria,
            "categoria_nome": modulo.get_categoria_display(),
            "descricao": modulo.descricao,
            "arquivo": (modulo.arquivo.name or "").rsplit("/", 1)[-1],
            "url": modulo.url,
            "cores": list(modulo.cores or []),
            "medidas": _medidas_texto(modulo.medidas or []),
            "ativo": modulo.ativo,
            "busca": _texto_de_busca(modulo.nome, modulo.get_categoria_display(), modulo.descricao,
                                     " ".join(modulo.cores or [])),
        }

    @staticmethod
    def _capa(brinquedo):
        try:
            # a foto vai num cartão: a do Cloudinary vem reduzida
            return reduzir_imagem(brinquedo.imagem_brinquedo.url, 640) if brinquedo.imagem_brinquedo else ""
        except Exception:
            return ""

    # ------------------------------------------------------------ ações

    def _brinquedo_do_pedido(self, request):
        bruto = (request.POST.get("brinquedo") or request.POST.get("id") or "").strip()
        if not bruto.isdigit():
            raise ErroDeFormulario("Escolha o brinquedo.")
        return get_object_or_404(Brinquedos, pk=int(bruto))

    def acao_salvar(self, request):
        """Sobe um .glb (ou liga um objeto do site) ao brinquedo, de uma vez só."""
        brinquedo = self._brinquedo_do_pedido(request)
        arquivo = request.FILES.get("arquivo")
        caminho_do_site = (request.POST.get("arquivo_estatico") or "").strip()
        codigo = (request.POST.get("codigo") or "").strip()[:60]
        exibir = request.POST.get("exibir_na_arena") == "on"

        if arquivo and caminho_do_site:
            raise ErroDeFormulario("Escolha UM: o arquivo .glb enviado ou um objeto que vem com o site.")
        if not arquivo and not caminho_do_site:
            raise ErroDeFormulario("Envie o arquivo .glb ou escolha um objeto que vem com o site.")
        if caminho_do_site and caminho_do_site not in MODELOS_DO_SITE:
            raise ErroDeFormulario("Esse objeto do site não existe.")

        if arquivo:
            try:
                lido = validar_glb(arquivo)
            except ValidationError as exc:
                raise ErroDeFormulario(" ".join(exc.messages)) from exc
        else:
            modelo = MODELOS_DO_SITE[caminho_do_site]
            lido = ler_glb_do_site(caminho_do_site)
            lido["medidas"] = lido["medidas"] or list(modelo["medidas"])
            codigo = codigo or modelo["id"]

        objeto = ObjetoTresD.objects.filter(brinquedo=brinquedo).first() or ObjetoTresD(brinquedo=brinquedo)
        arquivo_antigo = objeto.arquivo.name if objeto.arquivo else ""
        nome_novo = ""
        try:
            with transaction.atomic():
                if arquivo:
                    objeto.arquivo.save(arquivo.name, arquivo, save=False)
                    nome_novo = objeto.arquivo.name
                    objeto.arquivo_estatico = ""
                else:
                    if objeto.arquivo:
                        objeto.arquivo = None
                    objeto.arquivo_estatico = caminho_do_site
                objeto.codigo = codigo
                objeto.cores = lido["cores"]
                objeto.medidas = lido["medidas"]
                objeto.exibir_na_arena = exibir
                objeto.ativo = True
                objeto.save()
        except Exception:
            # o banco não gravou: o arquivo que acabou de subir não pode ficar órfão
            if nome_novo:
                try:
                    objeto.arquivo.storage.delete(nome_novo)
                except Exception as erro:  # noqa: BLE001
                    log.warning("arquivo 3D órfão não apagado (%s): %r", nome_novo, erro)
            raise
        if arquivo_antigo and arquivo_antigo != objeto.arquivo.name:
            try:
                objeto.arquivo.storage.delete(arquivo_antigo)
            except Exception as erro:  # noqa: BLE001
                log.warning("arquivo 3D antigo não apagado (%s): %r", arquivo_antigo, erro)

        log.info("objeto 3D de %s gravado por %s (%s)", brinquedo.nome_brinquedo, request.user.username,
                 "enviado" if arquivo else caminho_do_site)
        cores = ", ".join(lido["cores"]) if lido["cores"] else "nenhuma variação de cor"
        return self.sucesso(
            request,
            f"Objeto 3D de \"{brinquedo.nome_brinquedo}\" gravado: {cores}; {_medidas_texto(lido['medidas']) or 'medidas não lidas'}.",
        )

    def acao_conjunto_salvar(self, request):
        """O que vem dentro deste brinquedo (o espaço, o brinquedão): troca a lista inteira."""
        if not tabela_pronta(ComponenteBrinquedo):
            raise ErroDeFormulario("O banco ainda não tem a tabela da composição: rode a migração.")
        conjunto = self._brinquedo_do_pedido(request)
        try:
            itens = [(int(i["id"]), int(i.get("quantidade") or 1)) for i in json.loads(request.POST.get("itens") or "[]")]
        except (TypeError, ValueError, KeyError) as exc:
            raise ErroDeFormulario("A lista veio quebrada.") from exc
        try:
            limpos = composicao.salvar(conjunto, itens)
        except ValueError as exc:
            raise ErroDeFormulario(str(exc)) from exc
        log.info("o que vem em %s trocado por %s: %d brinquedo(s)", conjunto.nome_brinquedo, request.user.username, len(limpos))
        if not limpos:
            return self.sucesso(request, f"“{conjunto.nome_brinquedo}” não traz mais nenhum brinquedo dentro.")
        return self.sucesso(request, f"Pronto: “{conjunto.nome_brinquedo}” traz {len(limpos)} brinquedo{'s' if len(limpos) > 1 else ''} dentro.")

    def acao_alternar_arena(self, request):
        brinquedo = self._brinquedo_do_pedido(request)
        objeto = get_object_or_404(ObjetoTresD, brinquedo=brinquedo)
        objeto.exibir_na_arena = not objeto.exibir_na_arena
        objeto.save(update_fields=["exibir_na_arena", "atualizado"])
        return self.sucesso(
            request,
            f"\"{brinquedo.nome_brinquedo}\" {'aparece' if objeto.exibir_na_arena else 'não aparece mais'} na Arena 3D.",
        )

    def acao_religar(self, request):
        """Um objeto do site que foi tirado do brinquedo volta."""
        brinquedo = self._brinquedo_do_pedido(request)
        objeto = get_object_or_404(ObjetoTresD, brinquedo=brinquedo)
        if not objeto.url:
            raise ErroDeFormulario("Esse objeto não tem arquivo: envie um .glb.")
        objeto.ativo = True
        objeto.save(update_fields=["ativo", "atualizado"])
        return self.sucesso(request, f"O objeto 3D de \"{brinquedo.nome_brinquedo}\" voltou.")

    # ------------------------------------------------- o laboratório (módulos)

    def acao_modulo_salvar(self, request):
        """Uma peça nova da biblioteca de montagem (.glb conferido antes de gravar)."""
        nome = (request.POST.get("nome") or "").strip()[:80]
        categoria = (request.POST.get("categoria") or "").strip()
        descricao = (request.POST.get("descricao") or "").strip()[:2000]
        arquivo = request.FILES.get("arquivo")
        if not nome:
            raise ErroDeFormulario("Dê um nome à peça (ex.: Torre 2 andares).")
        if categoria not in ModuloTresD.Categoria.values:
            raise ErroDeFormulario("Escolha a categoria da peça.")
        if not arquivo:
            raise ErroDeFormulario("Envie o arquivo .glb da peça.")
        try:
            lido = validar_glb(arquivo)
        except ValidationError as exc:
            raise ErroDeFormulario(" ".join(exc.messages)) from exc

        modulo = ModuloTresD(nome=nome, categoria=categoria, descricao=descricao, cores=lido["cores"], medidas=lido["medidas"])
        nome_novo = ""
        try:
            with transaction.atomic():
                modulo.arquivo.save(arquivo.name, arquivo, save=False)
                nome_novo = modulo.arquivo.name
                modulo.save()
        except Exception:
            if nome_novo:
                try:
                    modulo.arquivo.storage.delete(nome_novo)
                except Exception as erro:  # noqa: BLE001
                    log.warning("módulo 3D órfão não apagado (%s): %r", nome_novo, erro)
            raise
        log.info("módulo 3D %s (%s) gravado por %s", modulo.nome, modulo.categoria, request.user.username)
        return self.sucesso(
            request,
            f"Peça \"{modulo.nome}\" guardada no laboratório: {_medidas_texto(lido['medidas']) or 'medidas não lidas'}.",
        )

    def _apagar_modulo(self, request, modulo_id):
        modulo = get_object_or_404(ModuloTresD, pk=modulo_id)
        exigir_confirmacao_exclusao(request)
        nome, arquivo = modulo.nome, modulo.arquivo.name
        modulo.delete()
        try:
            modulo.arquivo.storage.delete(arquivo)
        except Exception as erro:  # noqa: BLE001
            log.warning("arquivo do módulo %s não apagado: %r", arquivo, erro)
        log.warning("módulo 3D %s removido por %s", nome, request.user.username)
        return self.sucesso(request, f"A peça \"{nome}\" foi apagada do laboratório, com o arquivo.")

    def _apagar_do_projeto(self, request, projeto_id):
        """Tira o 3D do projeto (o arquivo é apagado); o paralelo com a loja fica."""
        objeto = get_object_or_404(ObjetoTresDProjeto, projeto_id=projeto_id)
        exigir_confirmacao_exclusao(request)
        nome = objeto.arquivo.name if objeto.arquivo else ""
        titulo, _texto = _titulo_e_texto_do_projeto(objeto.projeto)
        if objeto.produto_id:
            objeto.arquivo = None
            objeto.medidas = []
            objeto.save()
        else:
            objeto.delete()
        if nome:
            try:
                ObjetoTresDProjeto._meta.get_field("arquivo").storage.delete(nome)
            except Exception as erro:  # noqa: BLE001
                log.warning("arquivo 3D do projeto %s não apagado: %r", nome, erro)
        log.warning("objeto 3D do projeto %s removido por %s", titulo, request.user.username)
        return self.sucesso(request, f"O objeto 3D do projeto “{titulo}” foi apagado.")

    def acao_delete(self, request):
        """Tira o objeto do brinquedo (o enviado é apagado; o do site só sai) -- ou apaga uma peça do laboratório."""
        bruto = (request.POST.get("id") or "").strip()
        if bruto.startswith("modulo-") and bruto[7:].isdigit():
            return self._apagar_modulo(request, int(bruto[7:]))
        if bruto.startswith("projeto3d-") and bruto[10:].isdigit():
            return self._apagar_do_projeto(request, int(bruto[10:]))
        brinquedo = self._brinquedo_do_pedido(request)
        objeto = get_object_or_404(ObjetoTresD, brinquedo=brinquedo)
        exigir_confirmacao_exclusao(request)
        if objeto.arquivo_estatico and not objeto.arquivo:
            # o objeto que veio com o site não se apaga: só sai do brinquedo
            # (e desligado, o nome não o traz de volta: ver arena.objeto_3d_do_cadastro)
            objeto.ativo = False
            objeto.save(update_fields=["ativo", "atualizado"])
            texto = "saiu do brinquedo (o arquivo continua no site, para religar quando quiser)"
        else:
            nome = objeto.arquivo.name
            objeto.delete()
            try:
                objeto.arquivo.storage.delete(nome)
            except Exception as erro:  # noqa: BLE001
                log.warning("arquivo 3D %s não apagado: %r", nome, erro)
            texto = "foi apagado, com o arquivo"
        log.warning("objeto 3D de %s removido por %s", brinquedo.nome_brinquedo, request.user.username)
        return self.sucesso(request, f"O objeto 3D de \"{brinquedo.nome_brinquedo}\" {texto}.")

    # ------------------------------------------- criar o objeto 3D aqui mesmo

    def _medidas_do_pedido(self, request):
        """{"largura", "profundidade", "altura"} em metros, do que veio preenchido."""
        saida = {}
        for chave in ("largura", "profundidade", "altura"):
            bruto = (request.POST.get(chave) or "").strip().replace(",", ".")
            if not bruto:
                continue
            try:
                valor = float(bruto)
            except ValueError as exc:
                raise ErroDeFormulario(f"A {chave} precisa ser um número em metros (ex.: 3,20).") from exc
            if not 0.05 <= valor <= 200:
                raise ErroDeFormulario(f"A {chave} precisa estar entre 0,05 m e 200 m.")
            saida[chave] = valor
        return saida

    def _projeto_do_pedido(self, request):
        bruto = (request.POST.get("projeto") or "").strip()
        if not bruto.isdigit():
            raise ErroDeFormulario("Escolha o projeto.")
        return get_object_or_404(BrinquedosProjeto, pk=int(bruto))

    @staticmethod
    def _ler_arquivo(arquivo, teto, rotulo):
        if arquivo.size > teto:
            raise ErroDeFormulario(f"{rotulo} passa de {teto // (1024 * 1024)} MB.")
        arquivo.seek(0)
        return arquivo.read()

    def _fotos_do_projeto(self, request):
        """{vista: bytes} das fotos do projeto, pela escolha de vista de cada uma."""
        projeto = self._projeto_do_pedido(request)
        try:
            escolhas = json.loads(request.POST.get("vistas") or "{}")
        except ValueError as exc:
            raise ErroDeFormulario("A escolha das vistas veio quebrada.") from exc
        fotos = {}
        imagens = {img.pk: img for img in projeto.imagens_brinquedo_projeto.all()}
        for foto_id, vista in escolhas.items():
            if not vista:
                continue
            if vista not in modelo_fotos.VISTAS:
                raise ErroDeFormulario("Vista desconhecida.")
            if vista in fotos:
                raise ErroDeFormulario(f"Duas fotos marcadas como \"{modelo_fotos.NOMES_DAS_VISTAS[vista]}\": deixe uma só.")
            imagem = imagens.get(int(foto_id)) if str(foto_id).isdigit() else None
            if imagem is None or not imagem.imagem:
                raise ErroDeFormulario("Uma das fotos escolhidas não é deste projeto.")
            try:
                with imagem.imagem.open("rb") as aberto:
                    fotos[vista] = aberto.read()
            except Exception as exc:  # noqa: BLE001 -- armazenamento fora do ar
                log.warning("foto %s do projeto %s não abriu: %r", imagem.pk, projeto.pk, exc)
                raise ErroDeFormulario("Uma das fotos do projeto não abriu agora. Tente de novo em instantes.") from exc
        return fotos

    def acao_gerar(self, request):
        """A prévia: monta (ou converte) o objeto e devolve o .glb, sem gravar nada."""
        origem = request.POST.get("origem") or ""
        medidas = self._medidas_do_pedido(request)
        try:
            if origem == "arquivo":
                arquivo = request.FILES.get("arquivo3d")
                if not arquivo:
                    raise ErroDeFormulario("Escolha o arquivo 3D.")
                dados = self._ler_arquivo(arquivo, TETO_DO_ARQUIVO_3D, "O arquivo 3D")
                glb, info = conversor_3d.converter(
                    arquivo.name, dados,
                    eixo=request.POST.get("eixo") or "auto",
                    unidade=request.POST.get("unidade") or "auto",
                    medidas=medidas,
                    limpar=request.POST.get("limpar") == "on",
                )
                info["modo"] = "arquivo"
            elif origem in ("fotos", "projeto"):
                if origem == "fotos":
                    fotos = {}
                    for vista in modelo_fotos.VISTAS:
                        enviada = request.FILES.get(f"foto_{vista}")
                        if enviada:
                            fotos[vista] = self._ler_arquivo(enviada, TETO_DA_FOTO, f"A foto ({modelo_fotos.NOMES_DAS_VISTAS[vista]})")
                else:
                    fotos = self._fotos_do_projeto(request)
                glb, info = modelo_fotos.gerar(
                    fotos, medidas,
                    modo=request.POST.get("modo") or "paineis",
                    recortar_fundo=request.POST.get("recortar") == "on",
                )
            else:
                raise ErroDeFormulario("Escolha de onde vem o objeto: fotos, projeto ou arquivo 3D.")
        except (conversor_3d.ErroDeConversao, modelo_fotos.ErroDasFotos) as exc:
            raise ErroDeFormulario(str(exc)) from exc
        info["origem"] = origem
        resposta = HttpResponse(glb, content_type="model/gltf-binary")
        resposta["X-Objeto3D-Info"] = json.dumps(info, ensure_ascii=True)
        resposta["Cache-Control"] = "no-store"
        return resposta

    def acao_projeto_dados(self, request):
        """As fotos do projeto (com a vista provável de cada uma), as medidas
        da descrição e os produtos da loja mais parecidos com ele."""
        projeto = self._projeto_do_pedido(request)
        titulo, descricao = _titulo_e_texto_do_projeto(projeto)
        fotos = []
        for indice, imagem in enumerate(projeto.imagens_brinquedo_projeto.all().order_by("id")):
            if not imagem.imagem:
                continue
            try:
                url = reduzir_imagem(imagem.imagem.url, 360)
            except Exception:  # noqa: BLE001
                continue
            fotos.append({"id": imagem.pk, "url": url, "legenda": imagem.legenda or "", "vista": vista_provavel(imagem.legenda, indice)})
        medidas = produtos_parecidos.medidas_no_texto(f"{titulo}\n{descricao}")
        catalogo = Brinquedos.objects.filter(ativo=True).prefetch_related("categorias_brinquedos")
        sugestoes = [
            {"id": s["brinquedo"].pk, "nome": s["brinquedo"].nome_brinquedo, "nota": s["nota"],
             "motivos": s["motivos"], "capa": self._capa(s["brinquedo"]),
             "tem_3d": bool(getattr(s["brinquedo"], "objeto_3d", None)) if tabela_pronta() else False}
            for s in produtos_parecidos.parecidos(titulo, descricao, catalogo, medidas)
        ]
        atual = None
        if tabela_pronta(ObjetoTresDProjeto):
            existente = ObjetoTresDProjeto.objects.filter(projeto=projeto).select_related("produto").first()
            if existente:
                atual = {"url": existente.url, "produto": existente.produto_id,
                         "produto_nome": existente.produto.nome_brinquedo if existente.produto else ""}
        return self.sucesso(request, "", projeto={"id": projeto.pk, "titulo": titulo}, fotos=fotos,
                            medidas=medidas, sugestoes=sugestoes, atual=atual)

    def acao_projeto_paralelo(self, request):
        """Só o paralelo: este projeto é (ou parece) aquele produto da loja."""
        if not tabela_pronta(ObjetoTresDProjeto):
            raise ErroDeFormulario("O banco ainda não tem a tabela do 3D dos projetos: rode a migração.")
        projeto = self._projeto_do_pedido(request)
        produto = self._produto_do_pedido(request)
        objeto = ObjetoTresDProjeto.objects.filter(projeto=projeto).first() or ObjetoTresDProjeto(projeto=projeto)
        objeto.produto = produto
        objeto.save()
        titulo, _texto = _titulo_e_texto_do_projeto(projeto)
        if produto:
            return self.sucesso(request, f"Pronto: a ficha de “{titulo}” mostra “{produto.nome_brinquedo}” como o produto da loja.")
        return self.sucesso(request, f"A ficha de “{titulo}” não mostra mais produto da loja.")

    def _produto_do_pedido(self, request):
        bruto = (request.POST.get("produto") or "").strip()
        if not bruto:
            return None
        if not bruto.isdigit():
            raise ErroDeFormulario("Produto inválido.")
        return get_object_or_404(Brinquedos, pk=int(bruto))

    def acao_gerado_salvar(self, request):
        """Grava o objeto da prévia: nos brinquedos escolhidos (um ou vários) e/ou no projeto."""
        arquivo = request.FILES.get("arquivo")
        if not arquivo:
            raise ErroDeFormulario("Gere a prévia antes de gravar.")
        try:
            lido = validar_glb(arquivo)
        except ValidationError as exc:
            raise ErroDeFormulario(" ".join(exc.messages)) from exc
        ids = sorted({int(x) for x in request.POST.getlist("brinquedos") if str(x).isdigit()})
        brinquedos = list(Brinquedos.objects.filter(pk__in=ids)) if ids else []
        projeto = self._projeto_do_pedido(request) if (request.POST.get("projeto") or "").strip() else None
        if not brinquedos and projeto is None:
            raise ErroDeFormulario("Escolha onde o objeto vai: um ou mais brinquedos e/ou o projeto.")
        if projeto is not None and not tabela_pronta(ObjetoTresDProjeto):
            raise ErroDeFormulario("O banco ainda não tem a tabela do 3D dos projetos: rode a migração.")
        produto = self._produto_do_pedido(request) if projeto is not None else None
        exibir = request.POST.get("exibir_na_arena") == "on"
        origem = request.POST.get("origem") if request.POST.get("origem") in ("fotos", "projeto", "arquivo") else ""
        modo = request.POST.get("modo") if request.POST.get("modo") in ("paineis", "volume", "arquivo") else ""

        novos, antigos = [], []
        try:
            with transaction.atomic():
                for brinquedo in brinquedos:
                    objeto = ObjetoTresD.objects.filter(brinquedo=brinquedo).first() or ObjetoTresD(brinquedo=brinquedo)
                    if objeto.arquivo:
                        antigos.append((objeto.arquivo.storage, objeto.arquivo.name))
                    arquivo.seek(0)
                    objeto.arquivo.save(f"{slugify(brinquedo.nome_brinquedo) or 'objeto'}.glb", File(arquivo), save=False)
                    novos.append((objeto.arquivo.storage, objeto.arquivo.name))
                    objeto.arquivo_estatico = ""
                    objeto.codigo = ""  # feito aqui: sem as animações de um objeto do site
                    objeto.cores = lido["cores"]
                    objeto.medidas = lido["medidas"]
                    objeto.exibir_na_arena = exibir
                    objeto.ativo = True
                    objeto.save()
                if projeto is not None:
                    titulo, _texto = _titulo_e_texto_do_projeto(projeto)
                    objeto = ObjetoTresDProjeto.objects.filter(projeto=projeto).first() or ObjetoTresDProjeto(projeto=projeto)
                    if objeto.arquivo:
                        antigos.append((objeto.arquivo.storage, objeto.arquivo.name))
                    arquivo.seek(0)
                    objeto.arquivo.save(f"projeto-{slugify(titulo) or projeto.pk}.glb", File(arquivo), save=False)
                    novos.append((objeto.arquivo.storage, objeto.arquivo.name))
                    objeto.medidas = lido["medidas"]
                    objeto.origem = origem
                    objeto.modo = modo
                    if produto is not None or request.POST.get("produto") == "":
                        objeto.produto = produto
                    objeto.ativo = True
                    objeto.save()
        except Exception:
            for armazenamento, nome in novos:
                try:
                    armazenamento.delete(nome)
                except Exception as erro:  # noqa: BLE001
                    log.warning("arquivo 3D órfão não apagado (%s): %r", nome, erro)
            raise
        for armazenamento, nome in antigos:
            if (armazenamento, nome) in novos:
                continue
            try:
                armazenamento.delete(nome)
            except Exception as erro:  # noqa: BLE001
                log.warning("arquivo 3D antigo não apagado (%s): %r", nome, erro)

        destinos = [f"“{b.nome_brinquedo}”" for b in brinquedos]
        if projeto is not None:
            destinos.append(f"o projeto “{_titulo_e_texto_do_projeto(projeto)[0]}”")
        log.info("objeto 3D criado no painel (%s/%s) gravado por %s em %s", origem, modo, request.user.username, ", ".join(destinos))
        return self.sucesso(
            request,
            f"Objeto 3D gravado em {', '.join(destinos)}: {_medidas_texto(lido['medidas']) or 'medidas não lidas'}.",
        )
