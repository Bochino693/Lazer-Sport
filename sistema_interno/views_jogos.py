"""Os jogos que a equipe sobe pelo painel interno (`JogoCadastrado`).

POR QUE AQUI, SE O /system/ JÁ TEM A TELA. O /system/ é o admin genérico
do Django: serve, mas é outro aplicativo, com outra cara, e qualquer
conta de equipe com `is_staff` chega perto dele. Esta tela mora no painel
que a equipe já usa e só abre para o SUPERADMINISTRADOR -- o cadastro de
um jogo é o que decide o que roda dentro do site, então fica com quem
responde pelo site.

O QUE SE PROTEGE AQUI (além da permissão):

* o arquivo .html é lido antes de guardar: tem de ser texto, com cara de
  página, sem byte nulo e dentro do tamanho; o .apk tem de ser um ZIP de
  verdade (todo APK é), não um executável renomeado;
* a capa e a imagem grande passam pelo Pillow (ImageField) e têm teto de
  tamanho; o endereço hospedado tem de ser https (regra do modelo);
* excluir exige a palavra de confirmação, como o resto do painel, e
  apaga também os arquivos guardados;
* tudo o que muda fica no log com quem fez (`sistema_interno.jogos`).

O jogo em si roda na página pública num quadro isolado (iframe com
sandbox): mesmo um .html malicioso não lê cookie, sessão nem a página.
"""

from __future__ import annotations

import logging

from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.views import View

from core import arena
from core.models import JogoCadastrado
from core.objetos_3d import tabela_pronta
from sistema_interno.templatetags.interno_extras import estatico

from .utils import ErroDeFormulario, endereco_do_site, exigir_confirmacao_exclusao
from .views import RespostaJSONMixin, SuperusuarioInternoRequiredMixin

log = logging.getLogger("sistema_interno.jogos")

MB = 1024 * 1024

#: Teto de cada arquivo. O .html de 15 MB repete a regra do modelo; o APK
#: é maior porque leva o jogo inteiro da máquina.
LIMITES = {
    "capa": 4 * MB,
    "poster": 6 * MB,
    "arquivo_html": 15 * MB,
    "apk": 200 * MB,
}

#: O que um .html de jogo precisa ter em algum lugar dos primeiros bytes.
MARCAS_DE_HTML = ("<!doctype", "<html", "<head", "<body", "<script", "<canvas")


def _tamanho_legivel(bytes_):
    return f"{bytes_ / MB:.0f} MB"


class JogoForm(forms.ModelForm):
    """O formulário da janela: os campos do modelo e a inspeção dos arquivos."""

    class Meta:
        model = JogoCadastrado
        fields = [
            "nome", "slug", "chamada", "descricao", "comandos", "cor", "ordem", "ativo",
            "capa", "poster", "endereco", "arquivo_html", "proporcao", "apk", "liberar_download",
        ]

    def _conferir_tamanho(self, campo):
        arquivo = self.cleaned_data.get(campo)
        if isinstance(arquivo, UploadedFile) and arquivo.size > LIMITES[campo]:
            raise forms.ValidationError(
                f"Esse arquivo tem {_tamanho_legivel(arquivo.size)}; o limite é {_tamanho_legivel(LIMITES[campo])}."
            )
        return arquivo

    def clean_capa(self):
        return self._conferir_tamanho("capa")

    def clean_poster(self):
        return self._conferir_tamanho("poster")

    def clean_arquivo_html(self):
        arquivo = self._conferir_tamanho("arquivo_html")
        if not isinstance(arquivo, UploadedFile):
            return arquivo
        if not arquivo.name.lower().endswith((".html", ".htm")):
            raise forms.ValidationError("Envie um arquivo .html.")
        arquivo.seek(0)
        inicio = arquivo.read(8192)
        arquivo.seek(0)
        if b"\x00" in inicio:
            raise forms.ValidationError("Esse arquivo não é uma página: tem conteúdo binário.")
        try:
            texto = inicio.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise forms.ValidationError("O .html precisa estar em UTF-8.") from exc
        if not any(marca in texto.lower() for marca in MARCAS_DE_HTML):
            raise forms.ValidationError(
                "Esse arquivo não parece uma página de jogo (não tem <html>, <script> nem <canvas>)."
            )
        return arquivo

    def clean_apk(self):
        arquivo = self._conferir_tamanho("apk")
        if not isinstance(arquivo, UploadedFile):
            return arquivo
        if not arquivo.name.lower().endswith(".apk"):
            raise forms.ValidationError("O arquivo de download precisa ser um .apk.")
        arquivo.seek(0)
        assinatura = arquivo.read(4)
        arquivo.seek(0)
        if assinatura[:2] != b"PK":
            raise forms.ValidationError("Esse arquivo não é um APK de verdade (um APK é um pacote ZIP).")
        return arquivo

    def primeiro_erro(self):
        """Uma frase só para a tarja do modal: o campo e o motivo."""
        for campo, erros in self.errors.items():
            rotulo = self.fields[campo].label if campo in self.fields else ""
            texto = str(erros[0])
            return f"{rotulo}: {texto}" if rotulo else texto
        return "Confira os campos e tente de novo."


class JogosInnerView(RespostaJSONMixin, SuperusuarioInternoRequiredMixin, View):
    """Lista, cria, edita, liga/desliga e exclui jogos cadastrados."""

    rota_padrao = "jogos_inner"
    template_name = "jogos_inner.html"

    def get(self, request):
        if not tabela_pronta(JogoCadastrado):
            # deploy antes do migrate: a tela explica em vez de cair
            return render(request, self.template_name, {"tabela_ausente": True, "jogos": [], "busca": ""})

        busca = (request.GET.get("q") or "").strip()
        jogos = JogoCadastrado.objects.order_by("ordem", "nome")
        if busca:
            jogos = jogos.filter(Q(nome__icontains=busca) | Q(slug__icontains=busca) | Q(chamada__icontains=busca))
        jogos = list(jogos)
        site = endereco_do_site(request).rstrip("/")
        for jogo in jogos:
            jogo.url_publica = f"{site}/jogos/{jogo.slug}/"
            jogo.como_roda = "Endereço hospedado" if jogo.endereco else ("Arquivo .html" if jogo.arquivo_html else "Sem onde jogar")

        todos = JogoCadastrado.objects.all()
        oficiais = self._oficiais(site, busca)
        return render(request, self.template_name, {
            "jogos": jogos,
            "jogos_dados": [self._serializar(jogo) for jogo in jogos],
            "oficiais": oficiais,
            "total_oficiais": len(arena.JOGOS),
            "busca": busca,
            "total": todos.count(),
            "total_ativos": todos.filter(ativo=True).count(),
            "total_com_apk": todos.exclude(apk="").count(),
            "total_apk_liberado": todos.exclude(apk="").filter(liberar_download=True).count(),
            "proporcoes": JogoCadastrado.PROPORCOES,
            "site": site,
        })

    @staticmethod
    def _oficiais(site, busca=""):
        """Os jogos que vêm com o site (core/arena.JOGOS), com o material deles.

        São motores feitos à mão, listados no código: não se editam por
        aqui e NÃO têm APK no site -- o jogo de verdade fica na máquina. A
        capa, o pôster e os textos são os mesmos do simulador.
        """
        texto = busca.lower()
        lista = []
        for jogo in arena.JOGOS:
            if texto and texto not in f"{jogo['titulo']} {jogo['slug']} {jogo['maquina']} {jogo['chamada']}".lower():
                continue
            lista.append({
                "slug": jogo["slug"],
                "titulo": jogo["titulo"],
                "maquina": jogo["maquina"],
                "chamada": jogo["chamada"],
                "descricao": jogo["descricao"],
                "comandos": jogo["comandos"],
                "cor": jogo["cor"],
                "capa": estatico(jogo["capa"]),
                "poster": estatico(jogo["poster"]) if jogo.get("poster") else "",
                "url_publica": f"{site}/jogos/{jogo['slug']}/",
            })
        return lista

    @staticmethod
    def _nome_do_arquivo(campo):
        try:
            return campo.name.rsplit("/", 1)[-1] if campo else ""
        except Exception:
            return ""

    def _serializar(self, jogo):
        return {
            "id": jogo.pk,
            "nome": jogo.nome,
            "slug": jogo.slug,
            "chamada": jogo.chamada,
            "descricao": jogo.descricao,
            "comandos": jogo.comandos,
            "cor": jogo.cor,
            "ordem": jogo.ordem,
            "ativo": jogo.ativo,
            "endereco": jogo.endereco,
            "proporcao": jogo.proporcao,
            "liberar_download": jogo.liberar_download,
            "capa": jogo.capa_url,
            "poster": self._nome_do_arquivo(jogo.poster),
            "arquivo_html": self._nome_do_arquivo(jogo.arquivo_html),
            "apk": self._nome_do_arquivo(jogo.apk),
        }

    # ------------------------------------------------------------ ações

    def _jogo_do_pedido(self, request):
        bruto = (request.POST.get("id") or "").strip()
        if not bruto.isdigit():
            return None
        return get_object_or_404(JogoCadastrado, pk=int(bruto))

    def acao_salvar(self, request):
        jogo = self._jogo_do_pedido(request)
        form = JogoForm(request.POST, request.FILES, instance=jogo)
        if not form.is_valid():
            raise ErroDeFormulario(form.primeiro_erro())
        salvo = form.save()
        log.info(
            "jogo %s %s por %s (ativo=%s, endereco=%s, html=%s, apk=%s)",
            "editado" if jogo else "criado", salvo.slug, request.user.username,
            salvo.ativo, bool(salvo.endereco), bool(salvo.arquivo_html), bool(salvo.apk),
        )
        return self.sucesso(
            request,
            f"Jogo \"{salvo.nome}\" {'salvo' if jogo else 'cadastrado'}. "
            + ("Já está no ar em /jogos/%s/." % salvo.slug if salvo.ativo else "Está desligado: ligue quando quiser publicar."),
            jogo=self._serializar(salvo),
        )

    def acao_alternar(self, request):
        jogo = self._jogo_do_pedido(request)
        if jogo is None:
            raise ErroDeFormulario("Jogo não encontrado.")
        jogo.ativo = not jogo.ativo
        jogo.save(update_fields=["ativo", "atualizado"])
        log.info("jogo %s %s por %s", jogo.slug, "ligado" if jogo.ativo else "desligado", request.user.username)
        return self.sucesso(request, f"\"{jogo.nome}\" {'está no ar' if jogo.ativo else 'saiu do ar'}.")

    def acao_delete(self, request):
        # "delete" é a ação que a janela de confirmação compartilhada envia
        jogo = self._jogo_do_pedido(request)
        if jogo is None:
            raise ErroDeFormulario("Jogo não encontrado.")
        exigir_confirmacao_exclusao(request)
        nome, slug = jogo.nome, jogo.slug
        arquivos = [campo for campo in (jogo.capa, jogo.poster, jogo.arquivo_html, jogo.apk) if campo]
        jogo.delete()
        for arquivo in arquivos:  # melhor esforço: o registro já se foi
            try:
                arquivo.storage.delete(arquivo.name)
            except Exception as erro:  # noqa: BLE001
                log.warning("arquivo do jogo %s não apagado: %r", slug, erro)
        log.warning("jogo %s EXCLUÍDO por %s", slug, request.user.username)
        return self.sucesso(request, f"\"{nome}\" foi excluído, com os arquivos.")
