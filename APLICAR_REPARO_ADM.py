#!/usr/bin/env python3
from __future__ import annotations

import argparse
import py_compile
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


def fail(message: str) -> None:
    raise RuntimeError(message)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        fail(f"{label}: esperava 1 ocorrência, encontrei {count}.")
    return text.replace(old, new, 1)


def copy_payload(script_dir: Path, root: Path, relative: str) -> None:
    src = script_dir / "payload" / relative
    dst = root / relative
    if not src.is_file():
        fail(f"Arquivo do pacote ausente: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def run_git(root: Path, *args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return ""
    return (proc.stdout or "") + (proc.stderr or "")


def patch_models(text: str) -> str:
    if 'TIPO_PERFIL = "perfil"' in text and 'uniq_imagem_brinquedo_tipo' in text:
        return text

    old_methods = '''    @property
    def imagens_ordenadas(self):
        """Galeria pronta para consumo, sempre na ordem definida no admin."""
        return self.imagens_brinquedo.all()

    @property
    def imagem_catalogo(self):
        """Imagem principal com fallback para o campo legado.

        O fallback permite migrar as telas aos poucos sem quebrar cards,
        integrações ou registros antigos que ainda usem ``imagem_brinquedo``.
        """
        principal = self.imagens_brinquedo.first()
        if principal and principal.imagem:
            return principal.imagem
        return self.imagem_brinquedo

    def sincronizar_imagem_legada_com_galeria(self):
        """Coloca a imagem antiga na posição 1 da galeria.

        O método é idempotente: pode ser executado mais de uma vez sem criar
        fotos duplicadas. Ele será removível quando todas as telas e rotinas de
        cadastro já trabalharem exclusivamente com a galeria.
        """
        if not self.pk or not self.imagem_brinquedo:
            return None

        principal = self.imagens_brinquedo.filter(ordem=1).first()
        if principal is None:
            return ImagemBrinquedo.objects.create(
                brinquedo=self,
                imagem=self.imagem_brinquedo.name,
                ordem=1,
                texto_alternativo=f"Foto principal de {self.nome_brinquedo}",
            )

        if principal.imagem.name != self.imagem_brinquedo.name:
            principal.imagem = self.imagem_brinquedo.name
            principal.texto_alternativo = (
                principal.texto_alternativo
                or f"Foto principal de {self.nome_brinquedo}"
            )
            principal.save(
                update_fields=["imagem", "texto_alternativo", "atualizado"]
            )
        return principal
'''

    new_methods = '''    @property
    def imagens_ordenadas(self):
        """Galeria pública: somente imagens tipadas, no máximo três."""
        return [
            foto
            for foto in self.imagens_brinquedo.all()
            if foto.tipo and foto.imagem
        ][:3]

    @property
    def imagem_perfil(self):
        """Foto frontal usada obrigatoriamente como capa.

        O fallback legado existe apenas para registros antigos durante a
        transição. Novos cadastros no painel exigem uma imagem PERFIL.
        """
        imagens = list(self.imagens_brinquedo.all())
        perfil = next(
            (foto for foto in imagens if foto.tipo == "perfil" and foto.imagem),
            None,
        )
        if perfil:
            return perfil.imagem

        if self.imagem_brinquedo:
            return self.imagem_brinquedo

        primeira = next((foto for foto in imagens if foto.imagem), None)
        if primeira:
            return primeira.imagem
        return None

    @property
    def imagem_catalogo(self):
        """Capa única do brinquedo: sempre PERFIL / FRENTE."""
        return self.imagem_perfil

    def sincronizar_imagem_legada_com_galeria(self):
        """Mantém o campo legado e a imagem PERFIL apontando para a mesma capa."""
        if not self.pk or not self.imagem_brinquedo:
            return None

        principal = (
            self.imagens_brinquedo
            .filter(tipo="perfil")
            .order_by("ordem", "id")
            .first()
        )
        if principal is None:
            principal = self.imagens_brinquedo.filter(ordem=1).first()

        if principal is None:
            return ImagemBrinquedo.objects.create(
                brinquedo=self,
                imagem=self.imagem_brinquedo.name,
                tipo="perfil",
                ordem=1,
                texto_alternativo=(
                    f"Perfil / frente de {self.nome_brinquedo}"
                ),
            )

        campos_atualizados = []

        if principal.tipo != "perfil":
            principal.tipo = "perfil"
            campos_atualizados.append("tipo")

        if principal.ordem != 1:
            principal.ordem = 1
            campos_atualizados.append("ordem")

        if principal.imagem.name != self.imagem_brinquedo.name:
            principal.imagem = self.imagem_brinquedo.name
            campos_atualizados.append("imagem")

        if not principal.texto_alternativo:
            principal.texto_alternativo = (
                f"Perfil / frente de {self.nome_brinquedo}"
            )
            campos_atualizados.append("texto_alternativo")

        if campos_atualizados:
            campos_atualizados.append("atualizado")
            principal.save(update_fields=campos_atualizados)

        return principal
'''

    text = replace_once(
        text,
        old_methods,
        new_methods,
        "models.py / propriedades da galeria",
    )

    old_class_head = '''class ImagemBrinquedo(Prime):
    brinquedo = models.ForeignKey(
'''
    new_class_head = '''class ImagemBrinquedo(Prime):
    TIPO_PERFIL = "perfil"
    TIPO_VERSO = "verso"
    TIPO_LADO_DIREITO = "lado_direito"
    TIPO_LADO_ESQUERDO = "lado_esquerdo"

    TIPO_CHOICES = (
        (TIPO_PERFIL, "Perfil / Frente"),
        (TIPO_VERSO, "Verso / Costas"),
        (TIPO_LADO_DIREITO, "Lado direito"),
        (TIPO_LADO_ESQUERDO, "Lado esquerdo"),
    )

    brinquedo = models.ForeignKey(
'''
    text = replace_once(
        text,
        old_class_head,
        new_class_head,
        "models.py / constantes de tipo",
    )

    old_after_image = '''    imagem = models.ImageField(
        upload_to="imagens_brinquedos/galeria/",
        storage=MediaCloudinaryStorage(),
        verbose_name="Imagem",
    )
    ordem = models.PositiveSmallIntegerField(
'''
    new_after_image = '''    imagem = models.ImageField(
        upload_to="imagens_brinquedos/galeria/",
        storage=MediaCloudinaryStorage(),
        verbose_name="Imagem",
    )
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Tipo da imagem",
    )
    ordem = models.PositiveSmallIntegerField(
'''
    text = replace_once(
        text,
        old_after_image,
        new_after_image,
        "models.py / campo tipo",
    )

    old_str = '''    def __str__(self):
        return f"{self.brinquedo} — foto {self.ordem}"
'''
    new_str = '''    def __str__(self):
        tipo = self.get_tipo_display() if self.tipo else f"Foto {self.ordem}"
        return f"{self.brinquedo} — {tipo}"
'''
    text = replace_once(
        text,
        old_str,
        new_str,
        "models.py / __str__ da imagem",
    )

    old_indexes = '''        indexes = [
            models.Index(
                fields=["brinquedo", "ordem"],
                name="img_brinquedo_ordem_idx",
            )
        ]
'''
    new_indexes = '''        indexes = [
            models.Index(
                fields=["brinquedo", "ordem"],
                name="img_brinquedo_ordem_idx",
            )
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["brinquedo", "tipo"],
                name="uniq_imagem_brinquedo_tipo",
            )
        ]
'''
    text = replace_once(
        text,
        old_indexes,
        new_indexes,
        "models.py / constraint por tipo",
    )

    return text


def patch_pedido_admin(text: str) -> str:
    start = text.find("class PedidoAdminView(AdminOnlyMixin, View):")
    end = text.find("\n\nclass BrinquedoAdmin(AdminOnlyMixin, View):", start)
    if start < 0 or end < 0:
        fail("views.py: não encontrei PedidoAdminView.")

    old = text[start:end]
    if "total_nao_impressos" in old:
        return text

    new = '''class PedidoAdminView(AdminOnlyMixin, View):
    template_name = "gestao/pedidos_adm.html"

    def get(self, request):
        impresso = (request.GET.get("impresso") or "").strip()
        pagamento = (request.GET.get("pagamento") or "").strip()
        status = (request.GET.get("status") or "").strip()

        pedidos = (
            Pedido.objects
            .select_related("cliente", "cliente__user")
            .prefetch_related("itens")
        )

        if impresso == "true":
            pedidos = pedidos.filter(impresso=True)
        elif impresso == "false":
            pedidos = pedidos.filter(impresso=False)

        if pagamento:
            pedidos = pedidos.filter(forma_pagamento=pagamento)

        if status:
            pedidos = pedidos.filter(status=status)

        pedidos = pedidos.order_by("-id")

        todos = Pedido.objects.all()

        ctx = {
            "pedidos": pedidos,
            "impresso_atual": impresso,
            "pagamento_atual": pagamento,
            "status_atual": status,
            "total_pedidos": todos.count(),
            "total_aguardando": todos.filter(
                status="aguardando_pagamento"
            ).count(),
            "total_pagos": todos.filter(status="pago").count(),
            "total_nao_impressos": todos.filter(impresso=False).count(),
        }

        return render(request, self.template_name, ctx)
'''
    return text[:start] + new + text[end:]


def patch_brinquedo_admin(text: str) -> str:
    old_prefetch = '.prefetch_related("categorias_brinquedos", "tags")'
    admin_start = text.find("class BrinquedoAdmin(AdminOnlyMixin, View):")
    if admin_start < 0:
        fail("views.py: BrinquedoAdmin não encontrado.")
    admin_end = text.find("\n\nclass NovaCategoria", admin_start)
    if admin_end < 0:
        fail("views.py: fim de BrinquedoAdmin não encontrado.")

    prefix = text[:admin_start]
    admin = text[admin_start:admin_end]
    suffix = text[admin_end:]

    if old_prefetch in admin:
        admin = admin.replace(
            old_prefetch,
            '''.prefetch_related(
                "categorias_brinquedos",
                "tags",
                "imagens_brinquedo",
            )''',
            1,
        )

    old_json_image = '''                "imagem_url": (
                    brinquedo.imagem_brinquedo.url
                    if brinquedo.imagem_brinquedo else ""
                ),
                "categorias_ids": list(
'''
    new_json_image = '''                "imagem_url": (
                    brinquedo.imagem_catalogo.url
                    if brinquedo.imagem_catalogo else ""
                ),
                "imagens": [
                    {
                        "id": foto.id,
                        "tipo": foto.tipo,
                        "tipo_label": foto.get_tipo_display(),
                        "url": foto.imagem.url,
                    }
                    for foto in brinquedo.imagens_brinquedo.all()
                    if foto.tipo and foto.imagem
                ][:3],
                "categorias_ids": list(
'''
    if old_json_image in admin:
        admin = replace_once(
            admin,
            old_json_image,
            new_json_image,
            "views.py / JSON de imagens do brinquedo",
        )
    elif '"imagens": [' not in admin:
        fail("views.py: não encontrei imagem_url do BrinquedoAdmin.")

    old_inputs = '''            nome = request.POST.get("nome_brinquedo", "").strip()
            imagens = request.FILES.getlist("imagens_brinquedo")
            if not imagens:
                imagem_legada = request.FILES.get("imagem_brinquedo")
                imagens = [imagem_legada] if imagem_legada else []
            imagem = imagens[0] if imagens else None
            descricao = request.POST.get("descricao", "").strip()
'''
    new_inputs = '''            nome = request.POST.get("nome_brinquedo", "").strip()

            tipos_imagem = (
                ("perfil", "Perfil / Frente", 1),
                ("verso", "Verso / Costas", 2),
                ("lado_direito", "Lado direito", 3),
                ("lado_esquerdo", "Lado esquerdo", 4),
            )
            arquivos_imagem = {
                tipo: request.FILES.get(f"imagem_{tipo}")
                for tipo, _rotulo, _ordem in tipos_imagem
            }
            remover_tipos = {
                tipo
                for tipo, _rotulo, _ordem in tipos_imagem
                if request.POST.get(f"remover_imagem_{tipo}") == "on"
            }

            imagens_existentes = {}
            if brinquedo.pk:
                imagens_existentes = {
                    foto.tipo: foto
                    for foto in brinquedo.imagens_brinquedo.all()
                    if foto.tipo
                }

            tipos_finais = set(imagens_existentes)
            tipos_finais.difference_update(remover_tipos)
            tipos_finais.update(
                tipo
                for tipo, arquivo in arquivos_imagem.items()
                if arquivo
            )

            descricao = request.POST.get("descricao", "").strip()
'''
    if old_inputs in admin:
        admin = replace_once(
            admin,
            old_inputs,
            new_inputs,
            "views.py / inputs de imagens",
        )
    elif "tipos_imagem = (" not in admin:
        fail("views.py: não encontrei o bloco antigo de upload.")

    old_validation = '''            if not brinquedo.pk and not imagem:
                messages.error(
                    request,
                    "Selecione uma imagem para o novo brinquedo."
                )
                return redirect("brinquedos_admin")

            if len(imagens) > 8:
                messages.error(
                    request,
                    "Selecione no máximo 8 imagens por brinquedo."
                )
                return redirect("brinquedos_admin")

            for arquivo in imagens:
                if arquivo.size > 15 * 1024 * 1024:
                    messages.error(
                        request,
                        f"A imagem '{arquivo.name}' ultrapassa o limite de 15 MB."
                    )
                    return redirect("brinquedos_admin")
                if not (arquivo.content_type or "").startswith("image/"):
                    messages.error(
                        request,
                        f"O arquivo '{arquivo.name}' não é uma imagem válida."
                    )
                    return redirect("brinquedos_admin")
'''
    new_validation = '''            if "perfil" not in tipos_finais:
                messages.error(
                    request,
                    "A imagem PERFIL / FRENTE é obrigatória e será a capa."
                )
                return redirect("brinquedos_admin")

            if len(tipos_finais) > 3:
                messages.error(
                    request,
                    "Cada brinquedo aceita no máximo 3 imagens: PERFIL "
                    "e até duas vistas complementares."
                )
                return redirect("brinquedos_admin")

            for tipo, arquivo in arquivos_imagem.items():
                if not arquivo:
                    continue
                if arquivo.size > 15 * 1024 * 1024:
                    messages.error(
                        request,
                        f"A imagem '{arquivo.name}' ultrapassa o limite de 15 MB."
                    )
                    return redirect("brinquedos_admin")
                if not (arquivo.content_type or "").startswith("image/"):
                    messages.error(
                        request,
                        f"O arquivo '{arquivo.name}' não é uma imagem válida."
                    )
                    return redirect("brinquedos_admin")
'''
    if old_validation in admin:
        admin = replace_once(
            admin,
            old_validation,
            new_validation,
            "views.py / validação das imagens",
        )
    elif 'Cada brinquedo aceita no máximo 3 imagens' not in admin:
        fail("views.py: não encontrei validação antiga das imagens.")

    old_save = '''            if imagem:
                brinquedo.imagem_brinquedo = imagem

            criando = not brinquedo.pk
            brinquedo.save()
            if imagens:
                brinquedo.imagens_brinquedo.all().delete()
                brinquedo.sincronizar_imagem_legada_com_galeria()
                for ordem, arquivo in enumerate(imagens[1:], start=2):
                    ImagemBrinquedo.objects.create(
                        brinquedo=brinquedo,
                        imagem=arquivo,
                        ordem=ordem,
                        texto_alternativo=(
                            f"{brinquedo.nome_brinquedo} — foto {ordem}"
                        ),
                    )
            brinquedo.categorias_brinquedos.set(categorias_ids)
'''
    new_save = '''            imagem_perfil_nova = arquivos_imagem.get("perfil")
            if imagem_perfil_nova:
                # Campo legado e PERFIL continuam apontando para a mesma capa.
                brinquedo.imagem_brinquedo = imagem_perfil_nova

            criando = not brinquedo.pk
            brinquedo.save()

            # Remoção individual. Se o mesmo tipo recebeu um arquivo novo,
            # o upload vence sobre a marcação de remoção.
            for tipo in remover_tipos:
                if arquivos_imagem.get(tipo):
                    continue
                brinquedo.imagens_brinquedo.filter(tipo=tipo).delete()

            # PERFIL usa o arquivo já salvo no campo legado; evita upload duplo.
            if imagem_perfil_nova:
                brinquedo.sincronizar_imagem_legada_com_galeria()
            elif not brinquedo.imagens_brinquedo.filter(tipo="perfil").exists():
                brinquedo.sincronizar_imagem_legada_com_galeria()

            for tipo, rotulo, ordem in tipos_imagem:
                arquivo = arquivos_imagem.get(tipo)
                if not arquivo or tipo == "perfil":
                    continue

                ImagemBrinquedo.objects.update_or_create(
                    brinquedo=brinquedo,
                    tipo=tipo,
                    defaults={
                        "imagem": arquivo,
                        "ordem": ordem,
                        "texto_alternativo": (
                            f"{rotulo} de {brinquedo.nome_brinquedo}"
                        ),
                    },
                )

            ordem_por_tipo = {
                tipo: ordem
                for tipo, _rotulo, ordem in tipos_imagem
            }
            for foto in brinquedo.imagens_brinquedo.filter(
                tipo__in=tipos_finais
            ):
                ordem_correta = ordem_por_tipo.get(foto.tipo, foto.ordem)
                if foto.ordem != ordem_correta:
                    foto.ordem = ordem_correta
                    foto.save(update_fields=["ordem", "atualizado"])

            brinquedo.categorias_brinquedos.set(categorias_ids)
'''
    if old_save in admin:
        admin = replace_once(
            admin,
            old_save,
            new_save,
            "views.py / salvamento das imagens",
        )
    elif "imagem_perfil_nova = arquivos_imagem.get" not in admin:
        fail("views.py: não encontrei salvamento antigo das imagens.")

    return prefix + admin + suffix


def patch_request_covers(text: str) -> str:
    old_promo_qs = '''        promocoes = (
            Promocoes.objects
            .filter(ativo=True)
            .select_related('brinquedos')
        )
'''
    new_promo_qs = '''        promocoes = (
            Promocoes.objects
            .filter(ativo=True)
            .select_related('brinquedos')
            .prefetch_related('brinquedos__imagens_brinquedo')
        )
'''
    if old_promo_qs in text:
        text = text.replace(old_promo_qs, new_promo_qs, 1)

    old_promo_img = '''                'imagem': (
                    promo.brinquedos.imagem_brinquedo.url
                    if promo.brinquedos and promo.brinquedos.imagem_brinquedo else None
                ),
'''
    new_promo_img = '''                'imagem': (
                    promo.brinquedos.imagem_catalogo.url
                    if promo.brinquedos and promo.brinquedos.imagem_catalogo else None
                ),
'''
    if old_promo_img in text:
        text = text.replace(old_promo_img, new_promo_img, 1)

    old_toys_qs = '''        brinquedos_na_loja = (
            Brinquedos.objects
            .filter(ativo=True, exibir_na_loja=True)
        )
'''
    new_toys_qs = '''        brinquedos_na_loja = (
            Brinquedos.objects
            .filter(ativo=True, exibir_na_loja=True)
            .prefetch_related("imagens_brinquedo")
        )
'''
    if old_toys_qs in text:
        text = text.replace(old_toys_qs, new_toys_qs, 1)

    old_toy_img = (
        "'imagem': brinquedo.imagem_brinquedo.url "
        "if brinquedo.imagem_brinquedo else None,"
    )
    new_toy_img = (
        "'imagem': brinquedo.imagem_catalogo.url "
        "if brinquedo.imagem_catalogo else None,"
    )
    if old_toy_img in text:
        text = text.replace(old_toy_img, new_toy_img, 1)

    search_anchor = "class SearchView(View):"
    search_pos = text.find(search_anchor)
    if search_pos >= 0:
        before, tail = text[:search_pos], text[search_pos:]
        old_search_prefetch = '.prefetch_related("categorias_brinquedos", "tags")'
        if old_search_prefetch in tail:
            tail = tail.replace(
                old_search_prefetch,
                '''.prefetch_related(
                    "categorias_brinquedos",
                    "tags",
                    "imagens_brinquedo",
                )''',
                1,
            )
        tail = tail.replace(
            "                    brinquedo.imagem_brinquedo,\n",
            "                    brinquedo.imagem_catalogo,\n",
            1,
        )
        text = before + tail

    return text


def patch_views(text: str) -> str:
    text = patch_pedido_admin(text)
    text = patch_brinquedo_admin(text)
    text = patch_request_covers(text)
    return text


def patch_api_views(text: str) -> str:
    old_list = '''            Brinquedos.objects
            .filter(ativo=True)
            .only(
'''
    new_list = '''            Brinquedos.objects
            .filter(ativo=True)
            .prefetch_related("imagens_brinquedo")
            .only(
'''
    if old_list in text:
        text = text.replace(old_list, new_list, 1)

    old_detail = '.prefetch_related("categorias_brinquedos")'
    new_detail = '.prefetch_related("categorias_brinquedos", "imagens_brinquedo")'
    if old_detail in text:
        text = text.replace(old_detail, new_detail, 1)

    old_promo = '''            .filter(ativo=True)
            .select_related("brinquedos")
            .order_by("-id")
'''
    new_promo = '''            .filter(ativo=True)
            .select_related("brinquedos")
            .prefetch_related("brinquedos__imagens_brinquedo")
            .order_by("-id")
'''
    if old_promo in text:
        text = text.replace(old_promo, new_promo, 1)

    return text


def patch_serializer(text: str) -> str:
    text = text.replace(
        "return _url_cloudinary(obj.imagem_brinquedo, THUMB)",
        "return _url_cloudinary(obj.imagem_catalogo, THUMB)",
        1,
    )
    text = text.replace(
        "return _url_cloudinary(obj.imagem_brinquedo, DETALHE)",
        "return _url_cloudinary(obj.imagem_catalogo, DETALHE)",
        1,
    )
    text = text.replace(
        'getattr(obj.brinquedos, "imagem_brinquedo", None)',
        'getattr(obj.brinquedos, "imagem_catalogo", None)',
        1,
    )
    return text


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Aplica reparo do ADM de pedidos e imagens tipadas."
    )
    parser.add_argument(
        "project_root",
        nargs="?",
        default=".",
        help="Raiz do projeto Django (padrão: diretório atual).",
    )
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    script_dir = Path(__file__).resolve().parent

    required = [
        "manage.py",
        "core/models.py",
        "core/views.py",
        "core/api/views.py",
        "core/api/serializer.py",
        "core/templates/gestao/brinquedos_adm.html",
        "core/templates/gestao/pedidos_adm.html",
    ]
    for relative in required:
        if not (root / relative).is_file():
            fail(f"Projeto inválido: não encontrei {relative}")

    migration_conflicts = [
        p for p in (root / "core/migrations").glob("0099_*.py")
        if p.name != "0099_imagembrinquedo_tipo.py"
    ]
    if migration_conflicts:
        fail(
            "Já existe outra migration 0099 no projeto: "
            + ", ".join(p.name for p in migration_conflicts)
            + ". Ajuste a sequência de migrations antes de aplicar."
        )

    targets = [
        "core/models.py",
        "core/views.py",
        "core/api/views.py",
        "core/api/serializer.py",
        "core/templates/gestao/brinquedos_adm.html",
        "core/templates/gestao/pedidos_adm.html",
    ]

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = Path(tempfile.gettempdir()) / f"lazer_sport_reparo_adm_{stamp}"
    backup.mkdir(parents=True, exist_ok=False)

    for relative in targets:
        src = root / relative
        dst = backup / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    migration_path = root / "core/migrations/0099_imagembrinquedo_tipo.py"
    if migration_path.exists():
        dst = backup / "core/migrations/0099_imagembrinquedo_tipo.py"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(migration_path, dst)

    print(f"Backup: {backup}")

    models_path = root / "core/models.py"
    views_path = root / "core/views.py"
    api_views_path = root / "core/api/views.py"
    serializer_path = root / "core/api/serializer.py"

    models_new = patch_models(models_path.read_text(encoding="utf-8"))
    views_new = patch_views(views_path.read_text(encoding="utf-8"))
    api_views_new = patch_api_views(api_views_path.read_text(encoding="utf-8"))
    serializer_new = patch_serializer(serializer_path.read_text(encoding="utf-8"))

    models_path.write_text(models_new, encoding="utf-8", newline="\n")
    views_path.write_text(views_new, encoding="utf-8", newline="\n")
    api_views_path.write_text(api_views_new, encoding="utf-8", newline="\n")
    serializer_path.write_text(serializer_new, encoding="utf-8", newline="\n")

    copy_payload(script_dir, root, "core/templates/gestao/brinquedos_adm.html")
    copy_payload(script_dir, root, "core/templates/gestao/pedidos_adm.html")
    copy_payload(script_dir, root, "core/migrations/0099_imagembrinquedo_tipo.py")

    for relative in [
        "core/models.py",
        "core/views.py",
        "core/api/views.py",
        "core/api/serializer.py",
        "core/migrations/0099_imagembrinquedo_tipo.py",
    ]:
        py_compile.compile(str(root / relative), doraise=True)

    print("\nPython: OK")

    check = subprocess.run(
        [sys.executable, "manage.py", "check"],
        cwd=root,
        check=False,
        text=True,
    )
    if check.returncode != 0:
        print(
            "\nATENÇÃO: manage.py check falhou. "
            f"Restaure pelo backup em {backup}",
            file=sys.stderr,
        )
        return check.returncode

    print("\nDjango check: OK")
    print("\nA migration foi criada, mas ainda NÃO foi executada.")
    print("\nPróximos comandos:")
    print("  python manage.py migrate")
    print("  python manage.py runserver")
    print("\nTeste:")
    print("  /adm/pedidos/")
    print("  /adm/brinquedos/")
    print("  /api/v1/brinquedos/")
    print("\nDepois confira:")
    print("  git diff --check")
    print("  git status")
    print("\nNenhum commit ou push foi feito.")

    status_text = run_git(root, "status", "--short")
    if status_text.strip():
        print("\nArquivos alterados:")
        print(status_text.rstrip())

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\nERRO: {exc}", file=sys.stderr)
        raise SystemExit(1)
