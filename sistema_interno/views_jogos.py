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
from django.db import transaction
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, render
from django.views import View

from core import arena, emulador_envio as envio, jogos_apk
from core import jogos_emulador as emu
from core.jogos_pc import CAMINHO_PARA_O_SITE, MOTORES
from core.models import ArquivoEmulador, JogoCadastrado
from core.objetos_3d import tabela_pronta
from sistema_interno.templatetags.interno_extras import estatico

from .utils import ErroDeFormulario, endereco_do_site, exigir_confirmacao_exclusao
from .views import RespostaJSONMixin, SuperusuarioInternoRequiredMixin

log = logging.getLogger("sistema_interno.jogos")

MB = 1024 * 1024


def _limite_de_arquivo_grande():
    """Teto do APK e da versão para computador, em bytes (JOGOS_ARQUIVO_MAX_MB, padrão 200).

    O armazenamento também tem o seu teto por arquivo (o Cloudinary, conforme
    o plano): o que passar daqui mas não de lá volta com aviso para usar o link.
    """
    from django.conf import settings

    try:
        proprio = max(1, int(getattr(settings, "JOGOS_ARQUIVO_MAX_MB", 200))) * MB
    except (TypeError, ValueError):
        proprio = 200 * MB
    # com o limite do armazenamento informado (JOGOS_ARMAZENAMENTO_LIMITE_MB), o
    # painel avisa antes de enviar -- em vez de o Cloudinary recusar no fim
    bruto = str(getattr(settings, "JOGOS_ARMAZENAMENTO_LIMITE_MB", "") or "").strip()
    try:
        return min(proprio, max(1, int(bruto)) * MB) if bruto else proprio
    except ValueError:
        return proprio


#: Teto de cada arquivo. O .html de 15 MB repete a regra do modelo; o APK
#: e a versão para computador são maiores porque levam o jogo inteiro.
LIMITES = {
    "capa": 4 * MB,
    "poster": 6 * MB,
    "arquivo_html": 15 * MB,
    "apk": None,        # _limite_de_arquivo_grande()
    "versao_pc": None,  # _limite_de_arquivo_grande()
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
            "versao_pc", "versao_pc_link", "sistema",
        ]

    def _conferir_tamanho(self, campo):
        arquivo = self.cleaned_data.get(campo)
        limite = LIMITES[campo] or _limite_de_arquivo_grande()
        if isinstance(arquivo, UploadedFile) and arquivo.size > limite:
            raise forms.ValidationError(
                f"Esse arquivo tem {_tamanho_legivel(arquivo.size)}; o limite é {_tamanho_legivel(limite)}."
                + (" Para um build maior, use o campo do link." if campo == "versao_pc" else "")
            )
        return arquivo

    def clean_sistema(self):
        sistema = self.cleaned_data.get("sistema") or ""
        if sistema not in ("", JogoCadastrado.AUTOMATICO) and sistema not in emu.sistemas_ligados():
            nucleo = emu.SISTEMAS[sistema]
            raise forms.ValidationError(
                f"{nucleo.nome}: o emulador ({nucleo.nucleo}) tem licença {nucleo.licenca}; "
                "só liga com a permissão dos autores (veja o LEIA-ME)."
            )
        return sistema

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
        """O APK: um ZIP com o AndroidManifest.xml (não só "começa com PK"), e o motor reconhecido."""
        from core import jogos_apk

        arquivo = self._conferir_tamanho("apk")
        if not isinstance(arquivo, UploadedFile):
            return arquivo
        if not arquivo.name.lower().endswith(".apk"):
            raise forms.ValidationError("O arquivo de download precisa ser um .apk.")
        try:
            self.apk_reconhecido, _ = jogos_apk.conferir(arquivo)
        except jogos_apk.ApkInvalido as exc:
            raise forms.ValidationError(str(exc)) from exc
        return arquivo

    def clean_versao_pc(self):
        """O .exe ou o .zip do jogo: conferido por dentro, e o motor reconhecido."""
        from core import jogos_pc

        arquivo = self._conferir_tamanho("versao_pc")
        if not isinstance(arquivo, UploadedFile):
            return arquivo
        try:
            self.motor_reconhecido = jogos_pc.conferir(arquivo)
        except jogos_pc.ArquivoInvalido as exc:
            raise forms.ValidationError(str(exc)) from exc
        return arquivo

    def save(self, commit=True):
        jogo = super().save(commit=False)
        motor = getattr(self, "motor_reconhecido", None)
        if motor:
            jogo.motor = motor
        elif not jogo.versao_pc:
            jogo.motor = ""
        apk_motor = getattr(self, "apk_reconhecido", None)
        if apk_motor:
            jogo.apk_motor = apk_motor
        elif not jogo.apk:
            jogo.apk_motor = ""
        if commit:
            jogo.save()
        return jogo

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
        emulador_pronto = tabela_pronta(ArquivoEmulador)
        if emulador_pronto:
            jogos = jogos.prefetch_related(Prefetch("arquivos_emulador", queryset=ArquivoEmulador.objects.order_by("ordem", "id")))
        if busca:
            jogos = jogos.filter(Q(nome__icontains=busca) | Q(slug__icontains=busca) | Q(chamada__icontains=busca))
        jogos = list(jogos)
        site = endereco_do_site(request).rstrip("/")
        for jogo in jogos:
            jogo.url_publica = f"{site}/jogos/{jogo.slug}/"
            sistema = emu.SISTEMAS.get(jogo.sistema)
            jogo.como_roda = (
                "Endereço hospedado" if jogo.endereco
                else "Arquivo .html" if jogo.arquivo_html
                else f"Emulador · {sistema.nome}" if sistema and emulador_pronto and jogo.emulador_pronto
                else "Emulador · faltam os arquivos" if jogo.sistema
                else "Só versão para computador" if jogo.so_versao_pc
                else "Sem onde jogar"
            )
            jogo.aguardando_arquivos = bool(jogo.sistema) and not (jogo.endereco or jogo.arquivo_html) and not (emulador_pronto and jogo.emulador_pronto)
            jogo.motor_nome = MOTORES.get(jogo.motor, "") if jogo.motor else ""
            jogo.caminho_para_o_site = CAMINHO_PARA_O_SITE.get(jogo.motor or "desconhecido", "")
            jogo.versao_pc_url = self._url_do_arquivo(jogo.versao_pc)
            jogo.apk_motor_nome = jogos_apk.MOTORES.get(jogo.apk_motor, "") if jogo.apk_motor else ""
            jogo.apk_caminho = jogos_apk.caminho_para_o_site(jogo.apk_motor) if jogo.apk and jogo.apk_motor else ""

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
            "total_so_pc": sum(1 for jogo in todos.only("endereco", "arquivo_html", "versao_pc", "versao_pc_link") if jogo.so_versao_pc),
            "total_apk_liberado": todos.exclude(apk="").filter(liberar_download=True).count(),
            "proporcoes": JogoCadastrado.PROPORCOES,
            "site": site,
            "emulador": self._emulador_contexto(),
        })

    @staticmethod
    def _emulador_contexto():
        """O que a janela dos arquivos do emulador precisa saber: os sistemas e onde os arquivos vão."""
        return {**envio.contexto(), "limite_arquivo_mb": round(_limite_de_arquivo_grande() / MB)}

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
    def _url_do_arquivo(campo):
        try:
            return campo.url if campo else ""
        except Exception:
            return ""

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
            "versao_pc": self._nome_do_arquivo(jogo.versao_pc),
            "versao_pc_link": jogo.versao_pc_link,
            "motor": jogo.motor,
            "apk_motor": jogo.apk_motor,
            "sistema": jogo.sistema,
            "emulador_resumo": jogo.emulador_resumo,
            "emulador_arquivos": self._arquivos_do_emulador(jogo),
        }

    @staticmethod
    def _arquivos_do_emulador(jogo):
        if not jogo.pk or not tabela_pronta(ArquivoEmulador):
            return []
        return [
            {"nome": a.nome, "papel": a.papel, "disco": a.disco, "tamanho": a.tamanho}
            for a in jogo.arquivos_emulador.all()
        ]

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
        try:
            salvo = form.save()
        except Exception as erro:  # noqa: BLE001 -- o armazenamento recusou (tamanho, tipo, rede)
            if erro.__class__.__module__.split(".")[0] not in ("cloudinary", "urllib3", "requests", "botocore"):
                raise
            log.warning("armazenamento recusou um arquivo do jogo %s: %r", form.cleaned_data.get("slug"), erro)
            raise ErroDeFormulario(
                "O armazenamento de arquivos recusou o envio (o plano tem um limite por arquivo, ou a conexão "
                "caiu). Para a versão para computador, use o campo do link (Google Drive, Dropbox...)."
            ) from erro
        log.info(
            "jogo %s %s por %s (ativo=%s, endereco=%s, html=%s, apk=%s, pc=%s %s)",
            "editado" if jogo else "criado", salvo.slug, request.user.username,
            salvo.ativo, bool(salvo.endereco), bool(salvo.arquivo_html), bool(salvo.apk),
            bool(salvo.versao_pc or salvo.versao_pc_link), salvo.motor,
        )
        aguardando = salvo.roda_no_emulador and not (tabela_pronta(ArquivoEmulador) and salvo.emulador_pronto)
        if aguardando:
            situacao = "Agora envie os arquivos do jogo (o .cue e os .bin, a ROM...): a janela já abre."
        elif salvo.so_versao_pc:
            situacao = (
                "Ficou guardada a versão para computador: o jogo ainda não aparece no site, "
                "porque o navegador não roda .exe. Quando a versão para navegador ficar pronta, é só "
                "informar o endereço ou enviar o .html."
            )
        elif salvo.ativo:
            situacao = "Já está no ar em /jogos/%s/." % salvo.slug
        else:
            situacao = "Está desligado: ligue quando quiser publicar."
        return self.sucesso(
            request,
            f"Jogo \"{salvo.nome}\" {'salvo' if jogo else 'cadastrado'}. " + situacao,
            jogo=self._serializar(salvo),
            abrir_emulador=aguardando,
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
        # a versão para computador também ocupa espaço: antes ela ficava órfã no armazenamento
        arquivos = [campo for campo in (jogo.capa, jogo.poster, jogo.arquivo_html, jogo.apk, jogo.versao_pc) if campo]
        do_emulador = list(jogo.arquivos_emulador.all()) if tabela_pronta(ArquivoEmulador) else []
        jogo.delete()

        def apagar_depois():  # melhor esforço, e só depois de o registro sair de verdade
            for arquivo in arquivos:
                try:
                    arquivo.storage.delete(arquivo.name)
                except Exception as erro:  # noqa: BLE001
                    log.warning("arquivo do jogo %s não apagado: %r", slug, erro)
            envio.apagar_do_armazenamento(do_emulador, slug)

        transaction.on_commit(apagar_depois)
        log.warning("jogo %s EXCLUÍDO por %s", slug, request.user.username)
        return self.sucesso(request, f"\"{nome}\" foi excluído, com os arquivos.")

    # ------------------------------------------------- arquivos do emulador
    # O caminho inteiro (conferir, pedaços, confirmar) mora em
    # core/emulador_envio.py: o /system/ usa o mesmo. Aqui é só a casca.

    def _jogo_para_emulador(self, request):
        jogo = self._jogo_do_pedido(request)
        if jogo is None:
            raise ErroDeFormulario("Salve o jogo antes de enviar os arquivos.")
        if not tabela_pronta(ArquivoEmulador):
            raise ErroDeFormulario("O banco ainda não tem a tabela dos arquivos do emulador: rode a migração.")
        return jogo

    def acao_emulador_conferir(self, request):
        """Confere antes de enviar (sem `id`: só confere; com `id`: volta o plano de envio)."""
        jogo = self._jogo_do_pedido(request)
        if jogo is not None and not tabela_pronta(ArquivoEmulador):
            raise ErroDeFormulario("O banco ainda não tem a tabela dos arquivos do emulador: rode a migração.")
        analise, resposta = envio.conferir(jogo, request.POST, request.FILES, request.path)
        return self.sucesso(request, analise.resumo() if analise.ok else "Confira os arquivos.", **resposta)

    def acao_emulador_pedaco(self, request):
        """Um pedaço que veio para o próprio site (sem o Cloudinary: no computador, nos testes)."""
        return self.sucesso(request, "Pedaço guardado.", **envio.guardar_pedaco(request.POST, request.FILES))

    def acao_emulador_confirmar(self, request):
        jogo = self._jogo_para_emulador(request)
        analise, problemas = envio.confirmar(jogo, request.POST, request.FILES, endereco_do_site(request).rstrip("/"))
        log.info(
            "arquivos do emulador de %s guardados por %s: %s (%d arquivos)",
            jogo.slug, request.user.username, analise.resumo(), len(analise.pecas),
        )
        return self.sucesso(
            request, envio.mensagem_de_pronto(jogo, analise, problemas),
            analise=analise.para_json(), problemas_do_balde=list(problemas),
        )

    def acao_emulador_remover(self, request):
        jogo = self._jogo_para_emulador(request)
        envio.remover(jogo)
        log.info("arquivos do emulador de %s removidos por %s", jogo.slug, request.user.username)
        return self.sucesso(request, f"Os arquivos de \"{jogo.nome}\" saíram. O jogo sai do site até receber outros.")
