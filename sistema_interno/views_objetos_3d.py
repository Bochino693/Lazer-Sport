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

from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, render
from django.views import View

from core import arena
from core.models import Brinquedos, ObjetoTresD
from core.objetos_3d import ler_glb_do_site, tabela_pronta, validar_glb

from .utils import ErroDeFormulario, endereco_do_site, exigir_confirmacao_exclusao
from .views import RespostaJSONMixin, SuperusuarioInternoRequiredMixin

log = logging.getLogger("sistema_interno.objetos_3d")

#: Os objetos que vêm com o site, pelo caminho em static (o que o formulário
#: pode escolher). Qualquer outro caminho é recusado.
MODELOS_DO_SITE = {modelo["arquivo"]: modelo for modelo in arena.MODELOS_3D}


def _medidas_texto(medidas):
    try:
        altura, largura, profundidade = (float(x) for x in medidas)
    except (TypeError, ValueError):
        return ""
    return f"{altura:.2f} m × {largura:.2f} m × {profundidade:.2f} m".replace(".", ",")


class Objetos3DInnerView(RespostaJSONMixin, SuperusuarioInternoRequiredMixin, View):
    """Lista os brinquedos com o seu objeto 3D; sobe, liga, mostra/esconde e remove."""

    rota_padrao = "objetos_3d_inner"
    template_name = "objetos_3d_inner.html"

    def get(self, request):
        if not tabela_pronta(ObjetoTresD):
            return render(request, self.template_name, {"tabela_ausente": True, "linhas": []})

        site = endereco_do_site(request).rstrip("/")
        brinquedos = (
            Brinquedos.objects.filter(ativo=True)
            .prefetch_related("objeto_3d")
            .order_by("nome_brinquedo")
        )
        linhas = []
        usados = {}
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
            }
            if objeto is not None:
                origem = "enviado" if objeto.arquivo else "do site"
                if objeto.arquivo_estatico:
                    usados[objeto.arquivo_estatico] = brinquedo.nome_brinquedo
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
            linhas.append(linha)

        modelos_do_site = [
            {
                "arquivo": modelo["arquivo"],
                "titulo": modelo["titulo"],
                "medidas": _medidas_texto(modelo["medidas"]),
                "jogo": modelo.get("jogo", ""),
                "usado_por": usados.get(modelo["arquivo"], ""),
            }
            for modelo in arena.MODELOS_3D
        ]
        com_objeto = [l for l in linhas if l["objeto"] and l["objeto"]["no_ar"]]
        return render(request, self.template_name, {
            "linhas": linhas,
            "linhas_dados": linhas,
            "modelos_do_site": modelos_do_site,
            "total": len(linhas),
            "total_com_objeto": len(com_objeto),
            "total_na_arena": sum(1 for l in com_objeto if l["objeto"]["exibir_na_arena"]),
            "total_com_jogo": sum(1 for l in linhas if l["jogo"]),
            "three": "vendor/three/three.module.min.js",
            "site": site,
        })

    @staticmethod
    def _capa(brinquedo):
        try:
            return brinquedo.imagem_brinquedo.url if brinquedo.imagem_brinquedo else ""
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

    def acao_delete(self, request):
        """Tira o objeto do brinquedo: o enviado é apagado; o do site só sai."""
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
