"""A tela que escreve, guarda e dispara o aviso do aplicativo.

DUAS PORTAS, E ELAS NÃO SE PARECEM.

A primeira é do CLIENTE: o celular dele chega aqui uma vez, pedindo para
ser avisado, e some daqui quando o aplicativo é desinstalado. É pública,
aceita visitante sem conta e não sabe fazer mais nada além de guardar e
apagar um endereço de entrega.

A segunda é da EQUIPE: escrever a mensagem, reler, corrigir, mandar. Ela
é do Comercial e da Criação -- quem cuida do que a loja diz --, e cada
disparo fica registrado com quem apertou o botão.

O QUE NÃO EXISTE AQUI, DE PROPÓSITO: mandar sem salvar. O aviso é sempre
gravado antes de sair, mesmo quando a pessoa escreve e dispara no mesmo
minuto. Notificação não tem "desfazer", e o mínimo que o sistema deve a
quem apertou é o registro exato do que foi dito.
"""

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.generic import View

from . import avisos_app, push
from .models import AparelhoDoCliente, AvisoDoAplicativo
from .permissoes import CRIACAO, GESTAO, VENDAS
from .utils import ErroDeFormulario, endereco_do_site, texto
from .views import InternoRequiredMixin, RespostaJSONMixin


class AvisosDoAplicativoView(RespostaJSONMixin, InternoRequiredMixin, View):
    """Painel de notificações do aplicativo."""

    rota_padrao = "avisos_app"

    #: Falar com o cliente é do Comercial e de quem cuida da vitrine.
    #: Produção e Financeiro não mandam recado para a base inteira.
    #:
    #: `InternoRequiredMixin` cobra isto no dispatch, então vale para o
    #: GET e para TODAS as ações -- inclusive as que forem escritas
    #: depois, que é o tipo de esquecimento que abre porta sem ninguém
    #: perceber.
    funcoes_necessarias = (VENDAS, CRIACAO, GESTAO)

    def get(self, request):
        avisos = list(AvisoDoAplicativo.objects.all()[:60])
        return render(request, "avisos_app.html", {
            "avisos": avisos,
            "publico": avisos_app.resumo_do_publico(),
            "publicos": AvisoDoAplicativo.Publico.choices,
            "push_configurado": push.configurado(),
            "avisos_dados": [self.serializar(a) for a in avisos],
            "ultimos_aparelhos": list(
                AparelhoDoCliente.objects.order_by("-criacao", "-id")[:12]
            ),
        })

    @staticmethod
    def serializar(aviso):
        return {
            "id": aviso.pk,
            "titulo": aviso.titulo,
            "mensagem": aviso.mensagem,
            "url": aviso.url,
            "publico": aviso.publico,
            "status": aviso.status,
            "editavel": aviso.editavel,
        }

    # ------------------------------------------------------------ ações
    def acao_save(self, request):
        """Cria ou corrige um rascunho. Enviado não se reescreve."""
        aviso_id = (request.POST.get("id") or "").strip()
        aviso = (
            get_object_or_404(AvisoDoAplicativo, pk=aviso_id)
            if aviso_id.isdigit() else AvisoDoAplicativo(autor=request.user)
        )
        if not aviso.editavel:
            raise ErroDeFormulario(
                "Este aviso já foi entregue aos celulares e não pode ser "
                "reescrito. Use “Duplicar” para mandar uma nova versão."
            )

        aviso.titulo = texto(
            request, "titulo", obrigatorio=True, rotulo="o título do aviso", limite=65,
        )
        aviso.mensagem = texto(
            request, "mensagem", obrigatorio=True, rotulo="a mensagem", limite=240,
        )
        aviso.url = self._destino(request)
        publico = (request.POST.get("publico") or "").strip()
        if publico not in AvisoDoAplicativo.Publico.values:
            raise ErroDeFormulario("Escolha quem recebe: todos, Android ou iPhone.")
        aviso.publico = publico
        aviso.save()

        return self.sucesso(
            request, f"Aviso “{aviso.titulo}” salvo.", aviso=self.serializar(aviso),
        )

    @staticmethod
    def _destino(request):
        """O endereço do toque, sempre dentro do site da casa.

        Um aviso que leva para fora é o formato clássico do golpe -- e
        quem recebe não tem como conferir o endereço antes de tocar. Só
        caminho relativo passa; endereço completo é recusado com uma
        explicação, e não silenciosamente convertido.
        """
        destino = texto(request, "url", limite=300)
        if not destino:
            return ""
        if destino.startswith(("http://", "https://", "//")):
            raise ErroDeFormulario(
                "Escreva só o caminho dentro do site (por exemplo /loja/). "
                "Endereço de fora não pode virar notificação nossa."
            )
        if not destino.startswith("/"):
            destino = "/" + destino
        return destino

    def acao_duplicar(self, request):
        original = get_object_or_404(AvisoDoAplicativo, pk=request.POST.get("id"))
        copia = AvisoDoAplicativo.objects.create(
            titulo=original.titulo[:65],
            mensagem=original.mensagem,
            url=original.url,
            publico=original.publico,
            autor=request.user,
        )
        return self.sucesso(
            request,
            "Cópia criada como rascunho: ajuste o texto antes de enviar.",
            aviso=self.serializar(copia),
        )

    def acao_delete(self, request):
        aviso = get_object_or_404(AvisoDoAplicativo, pk=request.POST.get("id"))
        if not aviso.editavel:
            raise ErroDeFormulario(
                "Aviso enviado é histórico: ele fica registrado com o que "
                "foi dito e para quantos aparelhos saiu."
            )
        titulo = aviso.titulo
        aviso.delete()
        return self.sucesso(request, f"Rascunho “{titulo}” removido.")

    def acao_enviar(self, request):
        """Grava o texto e entrega. Nesta ordem, sempre."""
        aviso = get_object_or_404(AvisoDoAplicativo, pk=request.POST.get("id"))
        if not aviso.editavel:
            raise ErroDeFormulario(
                "Este aviso já foi enviado. Para mandar de novo, duplique-o."
            )
        if not avisos_app.aparelhos_do_publico(aviso.publico).exists():
            raise ErroDeFormulario(
                "Nenhum aparelho deste público aceitou receber avisos ainda. "
                "O convite aparece para o cliente na seção Aplicativo do site."
            )

        resultado = avisos_app.disparar(aviso, endereco_do_site(request))
        if not resultado["enviado"]:
            raise ErroDeFormulario(resultado["motivo"])

        recado = (
            f"Aviso entregue a {resultado['entregues']} de "
            f"{resultado['alcance']} aparelho(s)."
        )
        if resultado["falhas"]:
            recado += f" {resultado['falhas']} não responderam."
        if resultado.get("removidos"):
            recado += (
                f" {resultado['removidos']} aparelho(s) saíram da lista: "
                "o aplicativo foi desinstalado."
            )

        return self.sucesso(
            request, recado,
            aviso=self.serializar(aviso),
            resultado=resultado,
            publico=avisos_app.resumo_do_publico(),
        )

    def acao_testar(self, request):
        """Manda só para os aparelhos de quem está pedindo o teste.

        É o ensaio que faltava: ver a notificação de verdade -- com o
        corte do título no aparelho, com o toque abrindo a página certa
        -- antes de ela ir para a base inteira.
        """
        aviso = get_object_or_404(AvisoDoAplicativo, pk=request.POST.get("id"))
        meus = AparelhoDoCliente.objects.filter(usuario=request.user)
        if not meus.exists():
            raise ErroDeFormulario(
                "Para testar, abra a loja neste celular e aceite receber "
                "avisos. O teste vai só para os seus aparelhos."
            )

        dados = avisos_app.corpo_do_aviso(aviso, endereco_do_site(request))
        entregues = 0
        for aparelho in meus:
            try:
                if push.enviar(aparelho.endpoint, aparelho.p256dh, aparelho.auth, dados):
                    entregues += 1
            except push.InscricaoMorta:
                aparelho.delete()

        if not entregues:
            raise ErroDeFormulario(
                "O teste não chegou a nenhum aparelho seu. Confira se a "
                "permissão continua ligada no celular."
            )
        return self.sucesso(
            request, f"Teste enviado para {entregues} aparelho(s) seu(s).",
        )


class InscricaoDoAplicativoView(View):
    """A porta do cliente: este celular quer (ou não quer mais) ser avisado.

    Pública de propósito. Quem instalou o aplicativo e ainda não criou
    conta é justamente quem mais precisa de um empurrão de volta, e
    exigir login aqui trocaria um aviso que funciona por um cadastro que
    ninguém faz. Quando há login, o aparelho fica preso à pessoa -- é o
    que permite o teste do painel e a limpeza quando ela sai.

    O endereço de inscrição É a credencial de entrega: quem o tem manda
    notificação para aquele aparelho. Por isso ele nunca é devolvido por
    esta rota, nem listado para ninguém além do painel.
    """

    #: Web Push não existe fora de HTTPS, então o campo `plataforma` é o
    #: que o próprio aparelho declara. Não é identidade -- é só o filtro
    #: de "mandar só para iPhone", e um valor estranho vira "outro".
    PLATAFORMAS = dict(AparelhoDoCliente.Plataforma.choices)

    def get(self, request):
        """A chave pública da aplicação, que o navegador precisa ter."""
        return JsonResponse({
            "configurado": push.configurado(),
            "chave": push.chave_publica(),
        })

    def post(self, request):
        endpoint = (request.POST.get("endpoint") or "").strip()
        if not endpoint or len(endpoint) > 600:
            return JsonResponse({"ok": False, "erro": "endpoint"}, status=400)

        if (request.POST.get("acao") or "") == "cancelar":
            AparelhoDoCliente.objects.filter(endpoint=endpoint).delete()
            return JsonResponse({"ok": True, "inscrito": False})

        p256dh = (request.POST.get("p256dh") or "").strip()
        auth = (request.POST.get("auth") or "").strip()
        if not p256dh or not auth:
            return JsonResponse({"ok": False, "erro": "chaves"}, status=400)

        plataforma = (request.POST.get("plataforma") or "").strip().lower()
        if plataforma not in self.PLATAFORMAS:
            plataforma = AparelhoDoCliente.Plataforma.OUTRO

        usuario = request.user if request.user.is_authenticated else None
        AparelhoDoCliente.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                "usuario": usuario,
                "p256dh": p256dh[:200],
                "auth": auth[:100],
                "plataforma": plataforma,
                "aparelho": (request.POST.get("aparelho") or "")[:120],
            },
        )
        return JsonResponse({"ok": True, "inscrito": True})
