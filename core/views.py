from django.utils.decorators import method_decorator
from django.views.generic import View
from django.contrib.auth.models import User

from django.contrib.auth import authenticate, login
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import logging

from .forms import (
    UserForm,
    PerfilForm,
)

from django.contrib.auth.mixins import LoginRequiredMixin

from .models import Brinquedos, ImagemBrinquedo, CategoriasBrinquedos, Projetos, Eventos, ClientePerfil, Combos, Cupom, Promocoes, \
    TagsBrinquedos, ImagensSite, BrinquedosProjeto, Estabelecimentos, Manutencao, ManutencaoImagem, \
    BrinquedoClick, ComboClick, PromocaoClick, CategoriaClick, PecasReposicao, CategoriaPeca, \
    ImagemProjetoBrinquedo, ImagemEvento, Clientes, EnderecoEmpresa
from django.templatetags.static import static
from .utils import LAT_EMPRESA, LON_EMPRESA
from .home_cache import (
    get_cached_catalog_metadata,
    get_cached_home_context,
    home_cache_timeout,
)

import mimetypes
from pathlib import Path
from django.http import FileResponse, Http404, HttpResponse
from django.conf import settings
from django.utils.http import http_date
from random import shuffle, sample


def media_serve(request, path):
    media_root = Path(settings.MEDIA_ROOT).resolve()
    file_path = (media_root / path).resolve()

    if (
        file_path == media_root
        or media_root not in file_path.parents
        or not file_path.is_file()
    ):
        raise Http404("Arquivo não encontrado")

    stat = file_path.stat()
    etag = f'"{stat.st_mtime_ns:x}-{stat.st_size:x}"'
    cache_control = "public, max-age=86400, stale-while-revalidate=604800"

    if request.headers.get("If-None-Match") == etag:
        response = HttpResponse(status=304)
    else:
        content_type, encoding = mimetypes.guess_type(str(file_path))
        response = FileResponse(
            file_path.open("rb"),
            content_type=content_type or "application/octet-stream",
        )
        if encoding:
            response["Content-Encoding"] = encoding

    response["Cache-Control"] = cache_control
    response["ETag"] = etag
    response["Last-Modified"] = http_date(stat.st_mtime)
    return response


from django.http import HttpResponseNotFound, HttpResponseServerError
from django.template.loader import render_to_string


def erro_404(request, exception):
    try:
        html = render_to_string("404.html", request=request)
        return HttpResponseNotFound(html)
    except Exception:
        return HttpResponseNotFound(
            "<h1>Página não encontrada (404)</h1>"
            "<p>O conteúdo que você procura não existe ou foi movido.</p>"
        )


def erro_500(request):
    try:
        html = render_to_string("500.html", request=request)
        return HttpResponseServerError(html)
    except Exception:
        return HttpResponseServerError(
            "<h1>Erro interno (500)</h1>"
            "<p>Algo deu errado no nosso servidor. Já estamos verificando.</p>"
        )


def healthz(request):
    """Health check barato para o Render, sem consultas ao banco ou APIs."""
    return HttpResponse("ok", content_type="text/plain")


class HomeView(View):
    def head(self, request):
        # O Render verifica a raiz com HEAD. Não monte toda a vitrine nem
        # consulte o banco para uma resposta cujo corpo será descartado.
        return HttpResponse(status=200)

    def get(self, request):
        context = get_cached_home_context(self._build_public_context)
        context["home_cache_ttl"] = home_cache_timeout()

        return render(
            request,
            "home.html",
            context,
        )

    def _build_public_context(self):
        """Monta apenas a vitrine pública, segura para compartilhar em cache."""
        imagens_site = list(ImagensSite.objects.order_by("-id")[:5])

        # Todos os brinquedos ativos. A paginação de 9 por página já é
        # feita no JS do template (inicializarProdutosClientSide), então
        # aqui manda a lista completa -- se cortar em [:9] aqui, sobra
        # só uma página inteira pro JS paginar.
        brinquedos_todos = list(
            Brinquedos.objects
            .filter(ativo=True)
            .only(
                "id",
                "nome_brinquedo",
                "imagem_brinquedo",
                "descricao",
                "avaliacao",
                "valor_brinquedo",
                "voltz",
                "altura_m",
                "largura_m",
                "profundidade_m",
                "exibir_na_loja",
            )
            .prefetch_related(
                "categorias_brinquedos",
                "tags",
                "estabelecimentos",
            )
            .order_by("nome_brinquedo")
        )

        categorias_brinquedos = list(
            CategoriasBrinquedos.objects
            .filter(ativo=True)
            .annotate(
                total_produtos=Count(
                    "brinquedos",
                    distinct=True,
                )
            )
            .order_by(
                "-total_produtos",
                "nome_categoria",
                "id",
            )
        )

        combos = list(
            Combos.objects
            .all()
            .prefetch_related("brinquedos")
        )

        promocoes = list(
            Promocoes.objects
            .select_related("brinquedos")
        )

        eventos = list(
            Eventos.objects
            .prefetch_related(
                "imagens_evento",
                "brinquedos",
            )
            .order_by("-id")
        )

        projetos = list(
            Projetos.objects
            .select_related("brinquedo_projetado")
            .prefetch_related(
                "brinquedo_projetado__imagens_brinquedo_projeto"
            )
            .order_by("-id")
        )

        for combo in combos:
            total_original = sum(
                (
                        brinquedo.valor_brinquedo
                        or Decimal("0")
                )
                for brinquedo in combo.brinquedos.all()
            )

            valor_combo = (
                    combo.valor_combo
                    or Decimal("0")
            )

            economia = total_original - valor_combo

            porcentagem = (
                economia / total_original * 100
                if total_original > 0
                else 0
            )

            combo.total_original = total_original
            combo.economia = economia
            combo.porcentagem = porcentagem

        categorias_peca = list(CategoriaPeca.objects.all())

        from .models import ImagemPeca

        ids_com_imagem = list(
            PecasReposicao.objects
            .filter(
                ativo=True,
                imagem_peca_reposicao__isnull=False,
            )
            .values_list("id", flat=True)
            .distinct()
        )

        # A vitrine rotativa (o slider "Produtos em Geral" na categoria
        # premium fixa) continua sendo só uma amostra de 9 peças -- isso
        # aqui não tem relação com a paginação da grade principal, é só
        # pra não sobrecarregar o carrossel giratório.
        ids_amostra = sample(
            ids_com_imagem,
            min(9, len(ids_com_imagem)),
        )

        pecas_preview = (
            list(
                PecasReposicao.objects
                .filter(
                    ativo=True,
                    id__in=ids_amostra,
                )
                .prefetch_related(
                    Prefetch(
                        "imagem_peca_reposicao",
                        queryset=ImagemPeca.objects.order_by(
                            "ordem",
                            "id",
                        ),
                    )
                )
            )
            if ids_amostra
            else []
        )

        # Todas as peças ativas. Mesma lógica do brinquedos_todos: a
        # paginação de 9 por página já é feita no JS
        # (inicializarPecasClientSide), então manda a lista completa.
        pecas_todas = list(
            PecasReposicao.objects
            .filter(ativo=True)
            .prefetch_related(
                "imagem_peca_reposicao",
                "categoria_peca",
            )
            .order_by("nome")
        )

        # Clientes com localização cadastrada, para o mapa da seção "Clientes"
        clientes_com_mapa = list(
            Clientes.objects
            .filter(
                ativo=True,
                exibir_no_mapa=True,
                latitude__isnull=False,
                longitude__isnull=False,
            )
            .only(
                "descricao_cliente",
                "cidade",
                "estado",
                "pais",
                "latitude",
                "longitude",
                "site_cliente",
            )
        )

        clientes_mapa = [
            {
                "tipo": "cliente",
                "nome": c.descricao_cliente or "Cliente Lazer & Sport",
                "cidade": c.cidade or "",
                "estado": c.estado or "",
                "pais": c.pais or "Brasil",
                "lat": float(c.latitude),
                "lng": float(c.longitude),
                "site": c.site_cliente or "",
            }
            for c in clientes_com_mapa
        ]

        # Pino especial da fábrica. EnderecoEmpresa continua editável pelo
        # admin. Se não houver cadastro, a home usa as coordenadas fixas já
        # validadas; geocodificação externa nunca deve bloquear a vitrine.
        endereco_fabrica = (
            EnderecoEmpresa.objects
            .filter(ativo=True, latitude__isnull=False, longitude__isnull=False)
            .first()
        )

        fabrica_endereco_texto = "Rua São Roque de Minas, 104 — Jardim Peri"
        fabrica_cidade = "São Paulo"
        fabrica_estado = "SP"

        if endereco_fabrica:
            fabrica_lat = float(endereco_fabrica.latitude)
            fabrica_lng = float(endereco_fabrica.longitude)
            fabrica_cidade = endereco_fabrica.cidade or fabrica_cidade
            fabrica_estado = endereco_fabrica.estado or fabrica_estado
            fabrica_endereco_texto = (
                f"{endereco_fabrica.rua}, {endereco_fabrica.numero}"
                f" — {endereco_fabrica.bairro or ''}"
            ).strip(" —")
        else:
            fabrica_lat = LAT_EMPRESA
            fabrica_lng = LON_EMPRESA

        fabrica_mapa = {
            "tipo": "fabrica",
            "nome": "Lazer & Sport Brinquedos",
            "cidade": fabrica_cidade,
            "estado": fabrica_estado,
            "pais": "Brasil",
            "lat": fabrica_lat,
            "lng": fabrica_lng,
            "site": "",
            "logo": static("images/logoofi.png"),
            "endereco": fabrica_endereco_texto,
        }

        # pontos_mapa = tudo que vai pro mapa (fábrica + clientes).
        # clientes_mapa continua existindo separado pra lista de SEO,
        # que é só sobre clientes mesmo.
        pontos_mapa = [fabrica_mapa] + clientes_mapa

        # Lista única de cidades atendidas -- usada tanto no schema.org
        # (areaServed) quanto na lista de chips visível, pra reforçar
        # "Lazer & Sport" associado a cada cidade (bom pra SEO local e
        # serve de referência pronta pra replicar nas áreas de
        # atendimento do Google Business Profile).
        cidades_atendidas = sorted({
            c["cidade"] for c in clientes_mapa if c["cidade"]
        })

        context = {
            "categorias_brinquedos": categorias_brinquedos,
            "brinquedos_todos": brinquedos_todos,
            "brinquedos_count": len(brinquedos_todos),
            "eventos": eventos,
            "categorias_peca": categorias_peca,
            "pecas_todas": pecas_todas,
            "pecas_count": len(pecas_todas),
            "pecas_preview": pecas_preview,
            "projetos": projetos,
            "combos": combos,
            "promocoes": promocoes,
            "estabelecimentos": list(Estabelecimentos.objects.all()),
            "imagens_site": imagens_site,
            "clientes_mapa": clientes_mapa,
            "pontos_mapa": pontos_mapa,
            "cidades_atendidas": cidades_atendidas,
        }

        return context


from django.template.loader import render_to_string

from .models import PecasReposicao


class ReposicaoView(View):

    def get(self, request):
        categorias_peca = CategoriaPeca.objects.all()

        ctx = {
            'categorias_peca': categorias_peca,
            'pecas': PecasReposicao.objects.all(),

        }

        return render(request, 'reposicao.html', ctx)


class ReposicaoDetalheView(View):
    def get(self, request, pk):
        peca = get_object_or_404(
            PecasReposicao.objects.prefetch_related(
                "imagem_peca_reposicao",
                "categoria_peca",
            ),
            pk=pk,
            ativo=True,
        )
        imagens = list(peca.imagens_ordenadas)

        return render(request, 'reposicao_info.html', {
            'peca': peca,
            'imagens_peca': imagens,
            'categorias_peca': list(peca.categoria_peca.all()),
        })


from django.views import View


class ManutencaoView(View):
    template_name = 'manutencao.html'

    # A Vercel rejeita o request inteiro antes de chegar ao Django quando o
    # multipart ultrapassa 4,5 MB. Mantemos margem para campos e cabeçalhos.
    LIMITE_IMAGENS = 5
    TAMANHO_MAXIMO_IMAGEM = 3 * 1024 * 1024
    TAMANHO_MAXIMO_TOTAL = 3_800_000
    TIPOS_IMAGEM_PERMITIDOS = {
        'image/jpeg': '.jpg',
        'image/png': '.png',
        'image/webp': '.webp',
    }

    def get_usuario(self, request):
        if not request.user.is_authenticated:
            return None
        perfil, _ = ClientePerfil.objects.get_or_create(user=request.user)
        return perfil

    def get_contexto(self, request, form=None, tab_ativa=None):
        usuario = self.get_usuario(request)
        tab_ativa = tab_ativa or request.GET.get('tab', 'nova')

        if not usuario:
            return {
                'form': None,
                'manutencoes': [],
                'brinquedos': [],
                'tab_ativa': tab_ativa,
                'mostrar_modal_sucesso': False,
            }

        return {
            'form': form if form is not None else ManutencaoForm(),
            'manutencoes': (
                Manutencao.objects
                .filter(usuario=usuario)
                .select_related('brinquedo')
                .order_by('-criado_em')
            ),
            'brinquedos': Brinquedos.objects.all().order_by('nome_brinquedo'),
            'tab_ativa': tab_ativa,
            'mostrar_modal_sucesso': (
                    request.GET.get('sucesso') == '1'
            ),
        }

    def get(self, request):
        return render(
            request,
            self.template_name,
            self.get_contexto(request),
        )

    def validar_imagens(self, imagens):
        if len(imagens) > self.LIMITE_IMAGENS:
            return (
                f"Você pode enviar no máximo "
                f"{self.LIMITE_IMAGENS} imagens."
            )

        tamanho_total = sum(
            int(getattr(imagem, 'size', 0) or 0)
            for imagem in imagens
        )

        if tamanho_total > self.TAMANHO_MAXIMO_TOTAL:
            return (
                "O conjunto das fotos ficou muito pesado. "
                "Remova uma foto ou selecione imagens menores."
            )

        for imagem in imagens:
            content_type = (
                    getattr(imagem, 'content_type', '') or ''
            ).lower()

            if content_type not in self.TIPOS_IMAGEM_PERMITIDOS:
                return (
                    "Envie somente imagens JPG, PNG ou WEBP."
                )

            if not imagem.size:
                return "Uma das imagens enviadas está vazia."

            if imagem.size > self.TAMANHO_MAXIMO_IMAGEM:
                return (
                    "Cada imagem deve ter no máximo 3 MB "
                    "antes da otimização."
                )

        return None

    def salvar_imagem(self, manutencao, arquivo):
        """Salva o arquivo com nome único e devolve storage + nome."""
        content_type = (
                getattr(arquivo, 'content_type', '') or ''
        ).lower()
        extensao = self.TIPOS_IMAGEM_PERMITIDOS[content_type]

        registro = ManutencaoImagem(manutencao=manutencao)
        campo = registro._meta.get_field('imagem')
        storage = campo.storage

        nome_gerado = campo.generate_filename(
            registro,
            f"{uuid.uuid4().hex}{extensao}",
        )
        nome_salvo = storage.save(
            nome_gerado,
            arquivo,
            max_length=campo.max_length,
        )

        try:
            registro.imagem.name = nome_salvo
            registro.imagem._committed = True
            registro.save(force_insert=True)
        except Exception:
            # O arquivo não pertence ao banco se a linha não foi criada.
            try:
                storage.delete(nome_salvo)
            except Exception:
                logging.getLogger(__name__).exception(
                    "Falha ao remover imagem órfã de manutenção: %s",
                    nome_salvo,
                )
            raise

        return storage, nome_salvo

    def post(self, request):
        usuario = self.get_usuario(request)

        if not usuario:
            return redirect('login')

        form = ManutencaoForm(request.POST, request.FILES)

        if not form.is_valid():
            messages.error(
                request,
                "Confira os campos destacados antes de enviar.",
            )
            return self.render_form(request, form)

        imagens = request.FILES.getlist('imagens')
        erro_imagens = self.validar_imagens(imagens)

        if erro_imagens:
            messages.error(request, erro_imagens)
            return self.render_form(request, form)

        arquivos_gravados = []

        try:
            # Tudo no banco é confirmado junto ou totalmente desfeito.
            with transaction.atomic():
                manutencao = form.save(commit=False)
                manutencao.usuario = usuario
                manutencao.save()

                for imagem in imagens:
                    arquivos_gravados.append(
                        self.salvar_imagem(manutencao, imagem)
                    )

        except Exception:
            # FileField pode usar armazenamento externo, que não participa da
            # transação SQL. Removemos os arquivos já enviados manualmente.
            for storage, nome in reversed(arquivos_gravados):
                try:
                    storage.delete(nome)
                except Exception:
                    logging.getLogger(__name__).exception(
                        "Falha ao limpar imagem após rollback: %s",
                        nome,
                    )

            logging.getLogger(__name__).exception(
                "Falha atômica ao criar solicitação de manutenção."
            )
            messages.error(
                request,
                "Não foi possível registrar a manutenção. "
                "Nenhum dado foi gravado. Tente novamente.",
            )
            return self.render_form(request, form)

        messages.success(
            request,
            "Manutenção solicitada com sucesso!",
        )
        return redirect(
            f"{request.path}?tab=lista&sucesso=1"
        )

    def render_form(self, request, form):
        contexto = self.get_contexto(
            request,
            form=form,
            tab_ativa='nova',
        )
        contexto['mostrar_modal_sucesso'] = False
        return render(request, self.template_name, contexto)


from django.views.decorators.http import require_POST
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages


@require_POST
def cancelar_manutencao(request):
    usuario = request.user.perfil

    manutencao = get_object_or_404(
        Manutencao,
        id=request.POST.get("manutencao_id"),
        usuario=usuario
    )

    if manutencao.status in ['P', 'A']:
        manutencao.status = 'X'
        manutencao.save()
        messages.success(request, "Manutenção cancelada com sucesso.")
    else:
        messages.error(request, "Esta manutenção não pode ser cancelada.")

    return redirect('/manutencoes?tab=lista')


class ClientePerfilView(LoginRequiredMixin, View):
    template_name = "profile.html"

    def get_perfil(self, user):
        """Garante que o usuário tenha um perfil"""
        perfil, created = ClientePerfil.objects.get_or_create(user=user)
        return perfil

    def get(self, request):
        perfil = self.get_perfil(request.user)
        user_form = UserForm(instance=request.user)
        perfil_form = PerfilForm(instance=perfil)
        return render(request, self.template_name, {
            'user_form': user_form,
            'perfil_form': perfil_form
        })

    def post(self, request):
        perfil = self.get_perfil(request.user)
        user_form = UserForm(request.POST, instance=request.user)
        perfil_form = PerfilForm(request.POST, instance=perfil)

        if user_form.is_valid() and perfil_form.is_valid():
            user_form.save()
            perfil_form.save()
            messages.success(request, "Perfil atualizado com sucesso!")
            return redirect('perfil')

        messages.error(request, "Por favor, corrija os erros abaixo.")
        return render(request, self.template_name, {
            'user_form': user_form,
            'perfil_form': perfil_form
        })


class BrinquedoInfoView(View):

    def get(self, request, id):
        from urllib.parse import quote
        from unicodedata import normalize

        brinquedo = get_object_or_404(
            Brinquedos.objects.prefetch_related(
                "categorias_brinquedos",
                "tags",
                "imagens_brinquedo",
            ),
            id=id,
            ativo=True,
        )

        obj, created = BrinquedoClick.objects.get_or_create(
            brinquedo_clicado=brinquedo,
            defaults={'quantidade_click': 1}
        )

        if not created:
            BrinquedoClick.objects.filter(id=obj.id).update(
                quantidade_click=F('quantidade_click') + 1
            )

        valor = brinquedo.valor_brinquedo
        disponivel_loja = bool(
            brinquedo.exibir_na_loja
            and valor is not None
            and valor > 0
        )

        preco_formatado = ""
        preco_schema = ""
        if disponivel_loja:
            valor_decimal = Decimal(valor).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
            preco_formatado = (
                f"R$ {valor_decimal:,.2f}"
                .replace(",", "X")
                .replace(".", ",")
                .replace("X", ".")
            )
            preco_schema = f"{valor_decimal:.2f}"

        produto_url = request.build_absolute_uri()

        def formatar_medida(valor_medida):
            if valor_medida is None:
                return ""
            return (
                f"{Decimal(valor_medida):.2f}"
                .replace(".", ",")
            )

        mensagem = [
            "Olá! Gostaria de solicitar um orçamento.",
            "",
            f"Brinquedo: {brinquedo.nome_brinquedo}",
        ]
        if brinquedo.voltz:
            mensagem.append(f"Voltagem: {brinquedo.voltz}")

        medidas = [
            ("Altura", brinquedo.altura_m),
            ("Largura", brinquedo.largura_m),
            ("Profundidade", brinquedo.profundidade_m),
        ]
        medidas_validas = [
            f"{rotulo}: {formatar_medida(medida)} m"
            for rotulo, medida in medidas
            if medida is not None
        ]
        if medidas_validas:
            mensagem.extend(["", "Medidas:", *medidas_validas])

        mensagem.extend(["", f"Página do produto: {produto_url}"])
        whatsapp_url = (
            "https://wa.me/5511960563135?text="
            f"{quote(chr(10).join(mensagem))}"
        )

        categorias = list(brinquedo.categorias_brinquedos.all())

        def normalizar_texto(texto):
            return "".join(
                caractere
                for caractere in normalize("NFD", texto.lower())
                if ord(caractere) < 128
            )

        permite_sob_medida = any(
            "brinquedao" in normalizar_texto(categoria.nome_categoria)
            or "trampolim" in normalizar_texto(categoria.nome_categoria)
            for categoria in categorias
        )

        imagens_brinquedo = list(brinquedo.imagens_ordenadas)
        imagem_catalogo = brinquedo.imagem_catalogo
        imagem_url = ""
        if imagem_catalogo:
            imagem_url = request.build_absolute_uri(
                imagem_catalogo.url
            )

        context = {
            "brinquedo": brinquedo,
            "categorias_produto": categorias,
            "disponivel_loja": disponivel_loja,
            "preco_formatado": preco_formatado,
            "preco_schema": preco_schema,
            "produto_url": produto_url,
            "imagem_url": imagem_url,
            "imagens_brinquedo": imagens_brinquedo,
            "whatsapp_url": whatsapp_url,
            "permite_sob_medida": permite_sob_medida,
        }

        return render(request, "brinquedo_info.html", context)


class CategoriasInfoView(View):

    def get(self, request, pk):

        categoria = get_object_or_404(
            CategoriasBrinquedos,
            id=pk,
            ativo=True,
        )

        # REGISTRA CLICK
        obj, created = CategoriaClick.objects.get_or_create(
            categoria=categoria,
            defaults={
                'nome_categoria': categoria.nome_categoria,
                'quantidade_click': 1
            }
        )

        if not created:
            CategoriaClick.objects.filter(id=obj.id).update(
                quantidade_click=F('quantidade_click') + 1
            )

        brinquedos = (
            categoria.brinquedos
            .filter(ativo=True)
            .prefetch_related(
                "categorias_brinquedos",
                "tags",
                "imagens_brinquedo",
            )
        )

        ordenar = request.GET.get("ordenar", "az")

        if ordenar == "az":
            brinquedos = brinquedos.order_by("nome_brinquedo")
        elif ordenar == "za":
            brinquedos = brinquedos.order_by("-nome_brinquedo")
        elif ordenar == "melhor-avaliados":
            brinquedos = brinquedos.order_by("-avaliacao")
        elif ordenar == "custo-beneficio":
            brinquedos = brinquedos.order_by("-avaliacao", "valor_brinquedo")

        paginator = Paginator(brinquedos, 12)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        ctx = {
            "categoria": categoria,
            "page_obj": page_obj,
            "ordenar": ordenar,
        }

        return render(request, "categorias_info.html", ctx)


from django.core.paginator import Paginator
from django.db.models import F, FloatField, ExpressionWrapper, Prefetch
from django.db.models import (
    F,
    Q,
    Count,
    Case,
    When,
    Value,
    FloatField,
    DecimalField,
    ExpressionWrapper,
    Min,
    Max,
)
from django.db.models.functions import Cast, TruncDate, Coalesce

from django.views.generic import ListView
from .models import Estabelecimentos


class EstabelecimentosListView(ListView):
    model = Estabelecimentos
    template_name = "estabelecimentos_info.html"
    context_object_name = "estabelecimentos"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # brinquedos para o carrossel (limite para não pesar)
        context["brinquedos_carrossel"] = (
            Brinquedos.objects
            .exclude(imagem_brinquedo="")
            [:8]
        )

        return context


class BrinquedosView(View):
    @staticmethod
    def _formatar_decimal_br(valor):
        """Formata Decimal no padrão 1.234,56, sem depender do locale do SO."""
        if valor is None:
            return ""
        numero = Decimal(valor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return f"{numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    @staticmethod
    def _decimal_html(valor):
        """Valor decimal estável para atributos numéricos do HTML."""
        if valor is None:
            return "0.00"
        return f"{Decimal(valor).quantize(Decimal('0.01')):.2f}"

    @staticmethod
    def _build_catalog_metadata():
        catalogo_ativo = Brinquedos.objects.filter(ativo=True)
        loja_valida = Q(
            exibir_na_loja=True,
            valor_brinquedo__isnull=False,
            valor_brinquedo__gt=0,
        )

        categorias = list(
            CategoriasBrinquedos.objects
            .filter(ativo=True)
            .values("id", "nome_categoria")
            .annotate(
                total_brinquedos=Count(
                    "brinquedos",
                    filter=Q(brinquedos__ativo=True),
                    distinct=True,
                )
            )
            .filter(total_brinquedos__gt=0)
            .order_by("nome_categoria")
        )
        voltagens = list(
            catalogo_ativo
            .exclude(voltz__isnull=True)
            .exclude(voltz="")
            .values_list("voltz", flat=True)
            .distinct()
            .order_by("voltz")
        )
        totais = catalogo_ativo.aggregate(
            total_catalogo=Count("id"),
            total_loja=Count("id", filter=loja_valida),
            menor_preco_loja=Min("valor_brinquedo", filter=loja_valida),
            maior_preco_loja=Max("valor_brinquedo", filter=loja_valida),
        )

        return {
            "categorias": categorias,
            "voltagens": voltagens,
            "total_categorias": len(categorias),
            **totais,
        }

    def get(self, request):
        busca = request.GET.get("q", "").strip()[:120]
        categoria = request.GET.get("categoria", "").strip()
        voltagem = request.GET.get("voltagem", "").strip()[:20]
        disponibilidade = request.GET.get("disponibilidade", "todos").strip()
        ordenar = request.GET.get("ordenar", "novidades").strip()
        preco_min_input = request.GET.get("preco_min", "").strip()[:24]
        preco_max_input = request.GET.get("preco_max", "").strip()[:24]

        def converter_preco_filtro(valor):
            if not valor:
                return None

            texto = valor.replace("R$", "").replace(" ", "")
            if "," in texto:
                texto = texto.replace(".", "").replace(",", ".")

            try:
                numero = Decimal(texto)
                if (
                        not numero.is_finite()
                        or numero < 0
                        or numero > Decimal("99999999.99")
                ):
                    return None
            except (InvalidOperation, ValueError, TypeError):
                return None

            return numero

        preco_min = converter_preco_filtro(preco_min_input)
        preco_max = converter_preco_filtro(preco_max_input)

        if preco_min is None:
            preco_min_input = ""
        else:
            preco_min_input = self._formatar_decimal_br(preco_min)
        if preco_max is None:
            preco_max_input = ""
        else:
            preco_max_input = self._formatar_decimal_br(preco_max)

        if preco_min is not None and preco_max is not None and preco_min > preco_max:
            preco_min, preco_max = preco_max, preco_min
            preco_min_input = self._formatar_decimal_br(preco_min)
            preco_max_input = self._formatar_decimal_br(preco_max)

        ordens_validas = {
            "novidades",
            "az",
            "za",
            "melhor-avaliados",
            "menor-preco",
            "maior-preco",
            "custo-beneficio",
        }
        if ordenar not in ordens_validas:
            ordenar = "novidades"

        disponibilidades_validas = {"todos", "loja", "orcamento"}
        if disponibilidade not in disponibilidades_validas:
            disponibilidade = "todos"

        catalogo_ativo = Brinquedos.objects.filter(ativo=True)
        metadata = get_cached_catalog_metadata(self._build_catalog_metadata)
        categorias = metadata["categorias"]
        voltagens = metadata["voltagens"]

        brinquedos_list = (
            catalogo_ativo
            .prefetch_related("categorias_brinquedos", "tags")
        )

        if busca:
            brinquedos_list = brinquedos_list.filter(
                Q(nome_brinquedo__icontains=busca)
                | Q(descricao__icontains=busca)
                | Q(categorias_brinquedos__nome_categoria__icontains=busca)
            ).distinct()

        if categoria.isdigit():
            brinquedos_list = brinquedos_list.filter(
                categorias_brinquedos__id=int(categoria)
            ).distinct()
        else:
            categoria = ""

        if voltagem:
            brinquedos_list = brinquedos_list.filter(voltz__iexact=voltagem)

        ordens_por_valor = {"menor-preco", "maior-preco", "custo-beneficio"}
        filtro_por_valor = (
                preco_min is not None
                or preco_max is not None
                or ordenar in ordens_por_valor
        )

        # Preço e custo-benefício só existem para produtos realmente vendáveis.
        # Se o usuário usa qualquer filtro monetário, a disponibilidade de loja
        # é aplicada automaticamente e refletida de volta na interface.
        if filtro_por_valor:
            disponibilidade = "loja"
            brinquedos_list = brinquedos_list.filter(
                exibir_na_loja=True,
                valor_brinquedo__isnull=False,
                valor_brinquedo__gt=0,
            )
        elif disponibilidade == "loja":
            brinquedos_list = brinquedos_list.filter(
                exibir_na_loja=True,
                valor_brinquedo__isnull=False,
                valor_brinquedo__gt=0,
            )
        elif disponibilidade == "orcamento":
            brinquedos_list = brinquedos_list.filter(
                Q(exibir_na_loja=False)
                | Q(valor_brinquedo__isnull=True)
                | Q(valor_brinquedo__lte=0)
            )

        if preco_min is not None:
            brinquedos_list = brinquedos_list.filter(
                valor_brinquedo__gte=preco_min
            )

        if preco_max is not None:
            brinquedos_list = brinquedos_list.filter(
                valor_brinquedo__lte=preco_max
            )

        if ordenar == "az":
            brinquedos_list = brinquedos_list.order_by("nome_brinquedo", "id")
        elif ordenar == "za":
            brinquedos_list = brinquedos_list.order_by("-nome_brinquedo", "-id")
        elif ordenar == "melhor-avaliados":
            brinquedos_list = brinquedos_list.order_by(
                "-avaliacao",
                "nome_brinquedo",
            )
        elif ordenar == "menor-preco":
            brinquedos_list = brinquedos_list.order_by(
                "valor_brinquedo",
                "nome_brinquedo",
            )
        elif ordenar == "maior-preco":
            brinquedos_list = brinquedos_list.order_by(
                "-valor_brinquedo",
                "nome_brinquedo",
            )
        elif ordenar == "custo-beneficio":
            score_valido = ExpressionWrapper(
                Cast(F("avaliacao"), FloatField())
                / Cast(F("valor_brinquedo"), FloatField()),
                output_field=FloatField(),
            )
            brinquedos_list = brinquedos_list.annotate(
                score=Case(
                    When(
                        exibir_na_loja=True,
                        valor_brinquedo__gt=0,
                        then=score_valido,
                    ),
                    default=Value(-1.0),
                    output_field=FloatField(),
                )
            ).order_by("-score", "nome_brinquedo")
        else:
            brinquedos_list = brinquedos_list.order_by("-criacao", "-id")

        total_encontrados = brinquedos_list.count()

        paginator = Paginator(brinquedos_list, 12)
        page_obj = paginator.get_page(request.GET.get("page"))

        query_params = request.GET.copy()
        query_params.pop("page", None)

        menor_preco_loja = metadata.get("menor_preco_loja")
        maior_preco_loja = metadata.get("maior_preco_loja")
        faixa_preco_disponivel = (
            menor_preco_loja is not None and maior_preco_loja is not None
        )
        preco_min_range = preco_min if preco_min is not None else menor_preco_loja
        preco_max_range = preco_max if preco_max is not None else maior_preco_loja

        context = {
            "brinquedos": page_obj,
            "page_obj": page_obj,
            "ordenar": ordenar,
            "busca": busca,
            "categorias": categorias,
            "categoria_ativa": categoria,
            "voltagens": voltagens,
            "voltagem_ativa": voltagem,
            "disponibilidade": disponibilidade,
            "preco_min": preco_min_input,
            "preco_max": preco_max_input,
            "faixa_preco_disponivel": faixa_preco_disponivel,
            "menor_preco_loja": self._decimal_html(menor_preco_loja),
            "maior_preco_loja": self._decimal_html(maior_preco_loja),
            "menor_preco_loja_br": self._formatar_decimal_br(menor_preco_loja),
            "maior_preco_loja_br": self._formatar_decimal_br(maior_preco_loja),
            "preco_min_range": self._decimal_html(preco_min_range),
            "preco_max_range": self._decimal_html(preco_max_range),
            "preco_min_range_br": self._formatar_decimal_br(preco_min_range),
            "preco_max_range_br": self._formatar_decimal_br(preco_max_range),
            "filtro_valor_ativo": filtro_por_valor,
            "total_encontrados": total_encontrados,
            "total_catalogo": metadata["total_catalogo"],
            "total_loja": metadata["total_loja"],
            "total_categorias": metadata["total_categorias"],
            "querystring": query_params.urlencode(),
        }

        return render(request, "brinquedos.html", context)


class LojaView(View):
    """
    Loja: reúne num catálogo só tudo que já está pronto pra vender --
    todas as peças de reposição, todas as promoções e todos os combos
    entram automaticamente. Brinquedos "normais" NÃO entram por padrão
    (Brinquedos.exibir_na_loja é False por padrão) -- só aparecem aqui
    os que foram marcados explicitamente no admin.
    """
    template_name = 'loja.html'

    def get(self, request):
        itens = []

        pecas = (
            PecasReposicao.objects
            .filter(ativo=True)
            .prefetch_related('imagem_peca_reposicao', 'categoria_peca')
        )
        for peca in pecas:
            imagem_obj = peca.imagem_principal
            itens.append({
                'id': peca.id,
                'tipo': 'peca',
                'tipo_label': 'Peça de Reposição',
                'titulo': peca.nome,
                'imagem': imagem_obj.imagem.url if imagem_obj and imagem_obj.imagem else None,
                'preco': peca.preco_venda,
                'url': reverse('reposicao_detalhe', args=[peca.id]),
            })

        promocoes = (
            Promocoes.objects
            .filter(ativo=True)
            .select_related('brinquedos')
        )
        for promo in promocoes:
            itens.append({
                'id': promo.id,
                'tipo': 'promocao',
                'tipo_label': 'Promoção',
                'titulo': promo.descricao,
                'imagem': (
                    promo.brinquedos.imagem_brinquedo.url
                    if promo.brinquedos and promo.brinquedos.imagem_brinquedo else None
                ),
                'preco': promo.preco_promocao,
                'preco_original': promo.brinquedos.valor_brinquedo if promo.brinquedos else None,
                'url': reverse('promocao', args=[promo.id]),
            })

        combos = Combos.objects.filter(ativo=True).prefetch_related('brinquedos')
        for combo in combos:
            itens.append({
                'id': combo.id,
                'tipo': 'combo',
                'tipo_label': 'Combo',
                'titulo': combo.descricao,
                'imagem': combo.imagem_combo.url if combo.imagem_combo else None,
                'preco': combo.valor_combo,
                'url': reverse('combo', args=[combo.id]),
            })

        brinquedos_na_loja = (
            Brinquedos.objects
            .filter(ativo=True, exibir_na_loja=True)
        )
        for brinquedo in brinquedos_na_loja:
            itens.append({
                'id': brinquedo.id,
                'tipo': 'brinquedo',
                'tipo_label': 'Brinquedo',
                'titulo': brinquedo.nome_brinquedo,
                'imagem': brinquedo.imagem_brinquedo.url if brinquedo.imagem_brinquedo else None,
                'preco': brinquedo.valor_brinquedo,
                'url': reverse('brinquedo_detalhe', args=[brinquedo.id]),
            })

        contagem_por_tipo = {
            'peca': sum(1 for i in itens if i['tipo'] == 'peca'),
            'promocao': sum(1 for i in itens if i['tipo'] == 'promocao'),
            'combo': sum(1 for i in itens if i['tipo'] == 'combo'),
            'brinquedo': sum(1 for i in itens if i['tipo'] == 'brinquedo'),
        }

        context = {
            'itens_loja': itens,
            'total_itens': len(itens),
            'contagem_por_tipo': contagem_por_tipo,
        }

        return render(request, self.template_name, context)


class ComboInfoView(View):

    def get(self, request, pk):
        combo = get_object_or_404(Combos, id=pk)

        # REGISTRA O CLICK
        obj, created = ComboClick.objects.get_or_create(
            combo_clicado=combo,
            defaults={
                'descricao_combo': combo.descricao,
                'valor_combo': combo.valor_combo,
                'quantidade_click': 1
            }
        )

        if not created:
            ComboClick.objects.filter(id=obj.id).update(
                quantidade_click=F('quantidade_click') + 1
            )

        # ===== CÁLCULOS =====
        total_original = sum(
            Decimal(b.valor_brinquedo) for b in combo.brinquedos.all()
        )

        valor_combo = Decimal(combo.valor_combo)
        economia = total_original - valor_combo
        porcentagem = (economia / total_original * Decimal(100)) if total_original else Decimal(0)

        combo.total_original = total_original
        combo.economia = economia
        combo.porcentagem = porcentagem

        return render(request, 'combo_info.html', {'combo': combo})


class PromocaoInfoView(View):

    def get(self, request, pk):
        promocao = get_object_or_404(Promocoes, pk=pk)

        obj, created = PromocaoClick.objects.get_or_create(
            promocao=promocao,
            defaults={
                'descricao_promocao': promocao.descricao,
                'preco_promocao': promocao.preco_promocao,
                'quantidade_click': 1
            }
        )

        if not created:
            PromocaoClick.objects.filter(id=obj.id).update(
                quantidade_click=F('quantidade_click') + 1
            )

        return render(request, 'promocao_info.html', {
            'promocao': promocao
        })


class EstabelecimentoInfoView(View):
    def get(self, request, pk):
        estabelecimento = get_object_or_404(Estabelecimentos, pk=pk)

        order = request.GET.get("order", "")

        brinquedos = estabelecimento.brinquedos.all()

        if order == "az":
            brinquedos = brinquedos.order_by("nome_brinquedo")
        elif order == "za":
            brinquedos = brinquedos.order_by("-nome_brinquedo")
        elif order == "avaliacao":
            brinquedos = brinquedos.order_by("-avaliacao")
        elif order == "custo":
            brinquedos = brinquedos.order_by("valor_brinquedo")

        return render(request, "estabelecimento_info.html", {
            "estabelecimento": estabelecimento,
            "brinquedos": brinquedos,
            "order": order
        })


class SobreView(View):

    def get(self, request):
        context = {
            'brinquedos': Brinquedos.object.all()
        }
        return render(request, 'home_inner.html', context)


class EventosView(View):

    def get(self, request):
        context = {
            'eventos': Eventos.objects.all(),
        }
        return render(request, "eventos.html", context)


class ProjetosView(View):
    def get(self, request):
        context = {
            'projetos': Projetos.objects.all(),
        }
        return render(request, 'projetos.html', context)


from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from .models import Combos

from django.core.cache import cache
import time


class AdminLoginView(View):
    template_name = 'admin_login.html'

    MAX_ATTEMPTS = 3
    BLOCK_TIME = 600  # 10 minutos (em segundos)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

    def get(self, request):
        if request.user.is_authenticated and request.user.is_staff and request.user.is_superuser:
            return redirect('/adm/banners/')

        ip = self.get_client_ip(request)
        cache_key = f'admin_login:{ip}'
        data = cache.get(cache_key)

        # ⛔ IP bloqueado
        if data and data.get('blocked_until', 0) > time.time():
            return redirect('acesso_negado')

        return render(request, self.template_name)

    def post(self, request):
        ip = self.get_client_ip(request)
        cache_key = f'admin_login:{ip}'

        data = cache.get(cache_key, {
            'attempts': 0,
            'blocked_until': 0
        })

        # ⛔ Ainda bloqueado
        if data['blocked_until'] > time.time():
            return redirect('acesso_negado')

        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        # ❌ Login inválido
        if not user or not (user.is_staff and user.is_superuser):
            data['attempts'] += 1

            # 🔒 Estourou limite
            if data['attempts'] >= self.MAX_ATTEMPTS:
                data['blocked_until'] = time.time() + self.BLOCK_TIME
                cache.set(cache_key, data, timeout=self.BLOCK_TIME)
                return redirect('acesso_negado')

            cache.set(cache_key, data, timeout=self.BLOCK_TIME)

            return render(request, self.template_name, {
                'error': 'Usuário ou senha inválidos.'
            })

        # ✅ Login OK → limpa tudo
        cache.delete(cache_key)
        login(request, user)

        return redirect('/adm/banners/')


class AcessoNegadoView(View):
    def get(self, request):
        return render(request, 'acesso_negado.html', {
            'bloqueio': True
        })


class AdminOnlyMixin(View):
    def dispatch(self, request, *args, **kwargs):

        if not request.user.is_authenticated:
            return redirect('acesso_negado')

        if not (request.user.is_superuser and request.user.is_staff):
            return redirect('acesso_negado')

        return super().dispatch(request, *args, **kwargs)


class ClienteAdminView(AdminOnlyMixin, View):
    """
    Tela de admin pra cadastrar/editar os Clientes que aparecem no mapa
    da home. Criação e edição pelo mesmo modal. A geolocalização
    (latitude/longitude) é sempre automática -- calculada a partir do
    CEP (Brasil) ou cidade/país (fora do Brasil) no Clientes.save().

    Diferença importante em relação a editar direto pelo /system/: aqui,
    se o CEP/cidade/rua de um cliente que já existe for alterado, a
    geolocalização é refeita automaticamente na hora (limpa lat/long
    antes de salvar) -- não precisa lembrar de limpar os campos na mão
    toda vez que o endereço mudar.
    """
    template_name = "gestao/clientes_adm.html"

    def get(self, request):
        clientes = Clientes.objects.all().order_by("-criacao")

        # Dados pro modal de edição preencher os campos via JS -- vai
        # via json_script (mais seguro que interpolar direto no HTML).
        clientes_dados = [
            {
                "id": c.id,
                "descricao_cliente": c.descricao_cliente or "",
                "cep": c.cep or "",
                "rua": c.rua or "",
                "numero": c.numero or "",
                "bairro": c.bairro or "",
                "cidade": c.cidade or "",
                "estado": c.estado or "",
                "pais": c.pais or "Brasil",
                "site_cliente": c.site_cliente or "",
                "logo_url": c.logo_cliente.url if c.logo_cliente else "",
                "ativo": c.ativo,
                "exibir_no_mapa": c.exibir_no_mapa,
            }
            for c in clientes
        ]

        return render(request, self.template_name, {
            "clientes": clientes,
            "clientes_dados": clientes_dados,
        })

    def post(self, request):
        action = request.POST.get("action", "save")

        if action == "delete":
            cliente = get_object_or_404(Clientes, pk=request.POST.get("id"))
            nome = cliente.descricao_cliente or "Cliente"
            frase_esperada = f"CONFIRMAR EXCLUSÃO {nome}"
            frase_informada = request.POST.get("confirmacao_exclusao", "").strip()

            if frase_informada != frase_esperada:
                messages.error(
                    request,
                    "Exclusão cancelada: o texto de confirmação não corresponde "
                    "ao nome do cliente."
                )
                return redirect("clientes_admin")

            cliente.delete()
            messages.success(request, f"Cliente '{nome}' excluído com sucesso.")
            return redirect("clientes_admin")

        if action == "recalcular":
            cliente = get_object_or_404(Clientes, pk=request.POST.get("id"))
            cliente.latitude = None
            cliente.longitude = None
            cliente.save()

            if cliente.latitude and cliente.longitude:
                messages.success(
                    request,
                    f"'{cliente.descricao_cliente}': localização recalculada -- "
                    f"{cliente.latitude}, {cliente.longitude}."
                )
            else:
                messages.warning(
                    request,
                    f"'{cliente.descricao_cliente}': não foi possível localizar "
                    f"automaticamente. Confira o CEP/cidade cadastrados."
                )
            return redirect("clientes_admin")

        cliente_id = request.POST.get("id")
        cliente = get_object_or_404(Clientes, pk=cliente_id) if cliente_id else Clientes()

        descricao = request.POST.get("descricao_cliente", "").strip()
        if not descricao:
            messages.error(request, "Preencha o nome do cliente.")
            return redirect("clientes_admin")

        logo = request.FILES.get("logo_cliente")
        if not logo and not cliente.pk:
            messages.error(request, "A logo é obrigatória pra criar um cliente novo.")
            return redirect("clientes_admin")

        # Guarda o endereço ANTES de sobrescrever, pra comparar depois
        # e saber se precisa geocodificar de novo.
        campos_endereco = ["cep", "rua", "numero", "bairro", "cidade", "estado", "pais"]
        endereco_antigo = {campo: getattr(cliente, campo) for campo in campos_endereco}

        cliente.descricao_cliente = descricao
        if logo:
            cliente.logo_cliente = logo

        cliente.cep = request.POST.get("cep", "").strip()
        cliente.rua = request.POST.get("rua", "").strip()
        cliente.numero = request.POST.get("numero", "").strip()
        cliente.bairro = request.POST.get("bairro", "").strip()
        cliente.cidade = request.POST.get("cidade", "").strip()
        cliente.estado = request.POST.get("estado", "").strip().upper()
        cliente.pais = request.POST.get("pais", "").strip() or "Brasil"
        cliente.site_cliente = request.POST.get("site_cliente", "").strip()
        cliente.exibir_no_mapa = request.POST.get("exibir_no_mapa") == "on"
        cliente.ativo = request.POST.get("ativo") == "on"

        endereco_mudou = any(
            (getattr(cliente, campo) or "") != (endereco_antigo[campo] or "")
            for campo in campos_endereco
        )
        forcar_geocode = request.POST.get("forcar_geocode") == "on"

        if endereco_mudou or forcar_geocode:
            cliente.latitude = None
            cliente.longitude = None

        cliente.save()

        if cliente.latitude and cliente.longitude:
            messages.success(
                request,
                f"'{cliente.descricao_cliente}' salvo! Localização encontrada: "
                f"{cliente.latitude}, {cliente.longitude} -- já aparece no mapa."
            )
        else:
            messages.warning(
                request,
                f"'{cliente.descricao_cliente}' foi salvo, mas NÃO foi possível "
                f"localizar automaticamente pelo CEP/cidade informado. Confira se "
                f"o CEP está certo, ou preencha latitude/longitude manualmente "
                f"editando este cliente novamente."
            )

        return redirect("clientes_admin")


from django.db import transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from .models import Brinquedos, Promocoes


class PromocaoAdminView(AdminOnlyMixin, View):
    """
    Única view da administração de promoções.

    GET:
        Exibe, pesquisa e filtra as promoções.

    POST:
        Cria, edita ou exclui conforme o campo "acao" enviado pelo
        formulário da própria página.
    """

    template_name = "gestao/promocoes_adm.html"

    def get_queryset(self):
        queryset = (
            Promocoes.objects
            .select_related("brinquedos")
            .order_by("-id")
        )

        busca = self.request.GET.get("q", "").strip()
        status = self.request.GET.get("status", "todos").strip().lower()

        if busca:
            queryset = queryset.filter(
                Q(descricao__icontains=busca)
                | Q(brinquedos__nome_brinquedo__icontains=busca)
            )

        if status == "ativas":
            queryset = queryset.filter(ativo=True)
        elif status == "inativas":
            queryset = queryset.filter(ativo=False)

        return queryset

    def get(self, request, *args, **kwargs):
        todas = Promocoes.objects.all()

        context = {
            "promocoes": self.get_queryset(),
            "brinquedos": (
                Brinquedos.objects
                .all()
                .order_by("nome_brinquedo")
            ),
            "busca": request.GET.get("q", "").strip(),
            "status_atual": request.GET.get("status", "todos"),
            "total_promocoes": todas.count(),
            "total_ativas": todas.filter(ativo=True).count(),
            "total_inativas": todas.filter(ativo=False).count(),
        }
        return render(request, self.template_name, context)

    @staticmethod
    def _converter_preco(valor):
        """
        Aceita 10990.00, 10990,00 e 10.990,00.
        O retorno é Decimal, adequado para DecimalField.
        """
        valor = (valor or "").strip().replace("R$", "").replace(" ", "")

        if not valor:
            raise InvalidOperation

        if "," in valor:
            valor = valor.replace(".", "").replace(",", ".")
        elif valor.count(".") > 1:
            partes = valor.split(".")
            valor = "".join(partes[:-1]) + "." + partes[-1]

        preco = Decimal(valor)
        if preco < 0:
            raise InvalidOperation

        return preco.quantize(Decimal("0.01"))

    def post(self, request, *args, **kwargs):
        acao = request.POST.get("acao", "").strip().lower()

        if acao == "excluir":
            return self._excluir(request)

        if acao not in {"criar", "editar"}:
            messages.error(request, "Ação inválida.")
            return redirect("promocoes_admin")

        return self._salvar(request, acao)

    @transaction.atomic
    def _salvar(self, request, acao):
        promocao_id = request.POST.get("promocao_id")
        descricao = request.POST.get("descricao", "").strip()
        brinquedo_id = request.POST.get("brinquedos", "").strip()
        imagem = request.FILES.get("imagem_promocao")
        ativo = request.POST.get("ativo") == "on"

        if acao == "editar":
            promocao = get_object_or_404(Promocoes, pk=promocao_id)
        else:
            promocao = Promocoes()

        if not descricao:
            messages.error(request, "Informe o título da promoção.")
            return redirect("promocoes_admin")

        if not brinquedo_id:
            messages.error(request, "Selecione o brinquedo da promoção.")
            return redirect("promocoes_admin")

        brinquedo = get_object_or_404(Brinquedos, pk=brinquedo_id)

        try:
            preco = self._converter_preco(
                request.POST.get("preco_promocao")
            )
        except (InvalidOperation, TypeError, ValueError):
            messages.error(
                request,
                "Informe um preço válido, por exemplo: 10.990,00.",
            )
            return redirect("promocoes_admin")

        promocao.descricao = descricao
        promocao.preco_promocao = preco
        promocao.brinquedos = brinquedo
        promocao.ativo = ativo

        if imagem:
            promocao.imagem_promocao = imagem
        elif (
                acao == "editar"
                and request.POST.get("remover_imagem") == "on"
                and promocao.imagem_promocao
        ):
            promocao.imagem_promocao.delete(save=False)
            promocao.imagem_promocao = ""

        promocao.save()

        if acao == "criar":
            messages.success(request, "Promoção criada com sucesso.")
        else:
            messages.success(request, "Promoção atualizada com sucesso.")

        return redirect("promocoes_admin")

    @transaction.atomic
    def _excluir(self, request):
        promocao_id = request.POST.get("promocao_id")
        promocao = get_object_or_404(Promocoes, pk=promocao_id)

        if request.POST.get("confirmacao", "").strip().upper() != "EXCLUIR":
            messages.error(request, "Digite EXCLUIR para confirmar.")
            return redirect("promocoes_admin")

        try:
            promocao.delete()
        except ProtectedError:
            messages.error(
                request,
                "Esta promoção possui registros vinculados e não pode "
                "ser excluída.",
            )
        else:
            messages.success(request, "Promoção excluída com sucesso.")

        return redirect("promocoes_admin")


class CupomAdminView(AdminOnlyMixin, View):
    template_name = "gestao/cupons_adm.html"

    def get(self, request):
        busca = request.GET.get("q", "").strip()
        cupons = (
            Cupom.objects
            .select_related("brinquedo", "categoria")
            .prefetch_related("cliente__user")
            .order_by("-ativo", "codigo")
        )
        if busca:
            cupons = cupons.filter(codigo__icontains=busca)

        return render(request, self.template_name, {
            "cupons": cupons,
            "busca": busca,
            "brinquedos": Brinquedos.objects.filter(ativo=True).order_by("nome_brinquedo"),
            "categorias": CategoriasBrinquedos.objects.filter(ativo=True).order_by("nome_categoria"),
            "clientes": ClientePerfil.objects.select_related("user").order_by("user__username"),
        })

    @transaction.atomic
    def post(self, request):
        acao = request.POST.get("acao", "salvar")
        cupom_id = request.POST.get("cupom_id")

        if acao == "excluir":
            cupom = get_object_or_404(Cupom, pk=cupom_id)
            cupom.delete()
            messages.success(request, "Cupom excluído com sucesso.")
            return redirect("cupons_admin")

        cupom = get_object_or_404(Cupom, pk=cupom_id) if cupom_id else Cupom()
        codigo = request.POST.get("codigo", "").strip().upper()
        try:
            desconto = Decimal(request.POST.get("desconto_percentual", ""))
            quantidade = int(request.POST.get("quantidade_uso", "1"))
        except (InvalidOperation, TypeError, ValueError):
            messages.error(request, "Informe desconto e quantidade válidos.")
            return redirect("cupons_admin")

        if not codigo or len(codigo) > 12:
            messages.error(request, "O código deve ter entre 1 e 12 caracteres.")
            return redirect("cupons_admin")
        if not Decimal("0") < desconto <= Decimal("100"):
            messages.error(request, "O desconto deve ser maior que 0 e no máximo 100%.")
            return redirect("cupons_admin")
        if quantidade < 1:
            messages.error(request, "A quantidade de usos deve ser pelo menos 1.")
            return redirect("cupons_admin")
        if Cupom.objects.filter(codigo__iexact=codigo).exclude(pk=cupom.pk).exists():
            messages.error(request, "Já existe um cupom com esse código.")
            return redirect("cupons_admin")

        cupom.codigo = codigo
        cupom.desconto_percentual = desconto
        cupom.quantidade_uso = quantidade
        cupom.ativo = request.POST.get("ativo") == "on"
        cupom.brinquedo_id = request.POST.get("brinquedo") or None
        cupom.categoria_id = request.POST.get("categoria") or None
        cupom.save()
        cupom.cliente.set(request.POST.getlist("clientes"))
        messages.success(request, "Cupom atualizado." if cupom_id else "Cupom criado com sucesso.")
        return redirect("cupons_admin")


from django.db import transaction
from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views import View

from .models import BrinquedosProjeto, ImagemProjetoBrinquedo, Projetos


class ProjetoAdminView(AdminOnlyMixin, View):
    """
    Única view administrativa dos projetos.

    GET:
        Exibe e pesquisa os projetos.

    POST:
        Cria, edita ou exclui conforme o campo "acao".
    """

    template_name = "gestao/projetos_adm.html"
    maximo_imagens = 5
    tamanho_maximo_imagem = 8 * 1024 * 1024
    tipos_imagem_permitidos = {
        "image/jpeg",
        "image/png",
        "image/webp",
    }

    def get_queryset(self):
        queryset = (
            Projetos.objects
            .select_related("brinquedo_projetado")
            .annotate(
                total_imagens=Count(
                    "brinquedo_projetado__imagens_brinquedo_projeto",
                    distinct=True,
                )
            )
            .prefetch_related(
                "brinquedo_projetado__imagens_brinquedo_projeto"
            )
            .order_by("-id")
        )

        busca = self.request.GET.get("q", "").strip()
        if busca:
            queryset = queryset.filter(
                Q(titulo__icontains=busca)
                | Q(descricao__icontains=busca)
                | Q(
                    brinquedo_projetado__nome_brinquedo_projeto__icontains=busca
                )
            ).distinct()

        return queryset

    def get(self, request, *args, **kwargs):
        projetos = list(self.get_queryset())
        todos = Projetos.objects.all()

        projetos_com_imagem = (
            todos
            .filter(
                brinquedo_projetado__imagens_brinquedo_projeto__isnull=False
            )
            .distinct()
            .count()
        )

        projetos_json = []
        for projeto in projetos:
            brinquedo = projeto.brinquedo_projetado
            imagens = (
                list(brinquedo.imagens_brinquedo_projeto.all())
                if brinquedo
                else []
            )

            projetos_json.append({
                "id": projeto.id,
                "titulo": projeto.titulo or "",
                "descricao": projeto.descricao or "",
                "nome_brinquedo": (
                    brinquedo.nome_brinquedo_projeto or ""
                    if brinquedo
                    else ""
                ),
                "descricao_brinquedo": (
                    brinquedo.descricao or ""
                    if brinquedo
                    else ""
                ),
                "imagens": [
                    {
                        "id": imagem.id,
                        "url": imagem.imagem.url,
                    }
                    for imagem in imagens
                    if imagem.imagem
                ],
            })

        context = {
            "projetos": projetos,
            "projetos_json": projetos_json,
            "busca": request.GET.get("q", "").strip(),
            "total_projetos": todos.count(),
            "total_com_imagem": projetos_com_imagem,
            "total_imagens": ImagemProjetoBrinquedo.objects.count(),
            "maximo_imagens": self.maximo_imagens,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        acao = request.POST.get("acao", "").strip().lower()

        if acao == "excluir":
            return self._excluir(request)

        if acao not in {"criar", "editar"}:
            return self._erro("Ação inválida.")

        return self._salvar(request, acao)

    @staticmethod
    def _erro(mensagem, status=400):
        return JsonResponse(
            {"success": False, "error": mensagem},
            status=status,
        )

    def _validar_imagens(self, imagens):
        for imagem in imagens:
            if imagem.size > self.tamanho_maximo_imagem:
                return (
                    f'A imagem "{imagem.name}" excede o limite de 8 MB.'
                )

            if imagem.content_type not in self.tipos_imagem_permitidos:
                return (
                    f'O arquivo "{imagem.name}" não é uma imagem '
                    "JPG, PNG ou WEBP válida."
                )

        return None

    @transaction.atomic
    def _salvar(self, request, acao):
        projeto_id = request.POST.get("projeto_id")
        titulo = request.POST.get("titulo", "").strip()
        descricao = request.POST.get("descricao", "").strip()
        nome_brinquedo = request.POST.get("nome_brinquedo", "").strip()
        descricao_brinquedo = request.POST.get(
            "descricao_brinquedo",
            "",
        ).strip()
        novas_imagens = request.FILES.getlist("imagens")

        if not titulo:
            return self._erro("Informe o título do projeto.")

        if not descricao:
            return self._erro("Informe a descrição do projeto.")

        if not nome_brinquedo:
            return self._erro("Informe o nome do brinquedo projetado.")

        erro_imagem = self._validar_imagens(novas_imagens)
        if erro_imagem:
            return self._erro(erro_imagem)

        if acao == "editar":
            projeto = get_object_or_404(
                Projetos.objects.select_related("brinquedo_projetado"),
                pk=projeto_id,
            )
            brinquedo = projeto.brinquedo_projetado
        else:
            projeto = Projetos()
            brinquedo = None

        ids_remover = request.POST.getlist("remover_imagens")
        try:
            ids_remover = list({
                int(item)
                for item in ids_remover
            })
        except (TypeError, ValueError):
            return self._erro("A lista de imagens removidas é inválida.")

        imagens_existentes = (
            brinquedo.imagens_brinquedo_projeto.all()
            if brinquedo
            else ImagemProjetoBrinquedo.objects.none()
        )
        total_removido = (
            imagens_existentes.filter(pk__in=ids_remover).count()
            if brinquedo
            else 0
        )
        total_final = (
                imagens_existentes.count()
                - total_removido
                + len(novas_imagens)
        )

        if total_final > self.maximo_imagens:
            return self._erro(
                f"Cada projeto pode possuir no máximo "
                f"{self.maximo_imagens} imagens."
            )

        if brinquedo is None:
            brinquedo = BrinquedosProjeto.objects.create(
                nome_brinquedo_projeto=nome_brinquedo,
                descricao=descricao_brinquedo,
            )
            projeto.brinquedo_projetado = brinquedo

        brinquedo.nome_brinquedo_projeto = nome_brinquedo
        brinquedo.descricao = descricao_brinquedo
        brinquedo.save()

        projeto.titulo = titulo
        projeto.descricao = descricao
        projeto.brinquedo_projetado = brinquedo
        projeto.save()

        if ids_remover:
            imagens_existentes.filter(pk__in=ids_remover).delete()

        for imagem in novas_imagens:
            ImagemProjetoBrinquedo.objects.create(
                brinquedo=brinquedo,
                imagem=imagem,
            )

        return JsonResponse({
            "success": True,
            "message": (
                "Projeto criado com sucesso."
                if acao == "criar"
                else "Projeto atualizado com sucesso."
            ),
        })

    @transaction.atomic
    def _excluir(self, request):
        projeto_id = request.POST.get("projeto_id")
        projeto = get_object_or_404(
            Projetos.objects.select_related("brinquedo_projetado"),
            pk=projeto_id,
        )

        if request.POST.get("confirmacao", "").strip().upper() != "EXCLUIR":
            return self._erro("Digite EXCLUIR para confirmar.")

        brinquedo = projeto.brinquedo_projetado

        try:
            projeto.delete()

            if (
                    brinquedo
                    and not Projetos.objects.filter(
                brinquedo_projetado=brinquedo
            ).exists()
            ):
                brinquedo.delete()
        except ProtectedError:
            return self._erro(
                "Este projeto possui registros vinculados e não pode "
                "ser excluído."
            )

        return JsonResponse({
            "success": True,
            "message": "Projeto excluído com sucesso.",
        })


class EventoAdminView(AdminOnlyMixin, View):
    template_name = "gestao/eventos_adm.html"

    def get(self, request):
        # Use prefetch_related para otimizar a busca das imagens também
        eventos = Eventos.objects.prefetch_related('brinquedos', 'imagens_evento').order_by('-id')
        return render(request, self.template_name, {
            "eventos": eventos,
            "brinquedos": Brinquedos.objects.filter(ativo=True).order_by('nome_brinquedo')
        })

    @transaction.atomic
    def post(self, request):
        action = request.POST.get("action")

        if action == "delete":
            evento = get_object_or_404(Eventos, pk=request.POST.get("id"))
            evento.delete()
            return JsonResponse({"success": True})

        if action != "save":
            return JsonResponse({"success": False, "error": "Acao invalida."}, status=400)

        titulo = request.POST.get("titulo", "").strip()
        descricao = request.POST.get("descricao", "").strip()
        if not titulo or not descricao:
            return JsonResponse({
                "success": False, "error": "Preencha o titulo e a descricao."
            }, status=400)

        evento_id = request.POST.get("id")
        evento = get_object_or_404(Eventos, pk=evento_id) if evento_id else Eventos()
        evento.titulo = titulo
        evento.descricao = descricao
        evento.save()
        evento.brinquedos.set(request.POST.getlist("brinquedos"))

        ids_remover = request.POST.getlist("remover_imagens")
        if ids_remover:
            ImagemEvento.objects.filter(id__in=ids_remover, evento=evento).delete()

        imagens = request.FILES.getlist("imagens")
        if evento.imagens_evento.count() + len(imagens) > 5:
            transaction.set_rollback(True)
            return JsonResponse({
                "success": False, "error": "Cada evento pode ter no maximo 5 imagens."
            }, status=400)
        for imagem in imagens:
            ImagemEvento.objects.create(evento=evento, imagem=imagem)

        return JsonResponse({"success": True})


class PedidoAdminView(AdminOnlyMixin, View):
    template_name = "gestao/pedidos_adm.html"

    def get(self, request):

        pedidos = (
            Pedido.objects
            .select_related("cliente", "cliente__user")
            .prefetch_related("itens")
        )
        # dnadocrime
        filtros = {}

        impresso = request.GET.get("impresso")
        pagamento = request.GET.get("pagamento")
        status = request.GET.get("status")

        if impresso == "true":
            filtros["impresso"] = True
        elif impresso == "false":
            filtros["impresso"] = False

        if pagamento:
            filtros["forma_pagamento"] = pagamento

        if status:
            filtros["status"] = status

        if filtros:
            pedidos = pedidos.filter(**filtros)

        pedidos = pedidos.order_by("-id")

        ctx = {
            "pedidos": pedidos,
        }

        return render(request, self.template_name, ctx)


class BrinquedoAdmin(AdminOnlyMixin, View):

    def get(self, request):
        categoria = request.GET.get("categoria", "todas")
        busca = request.GET.get("q", "").strip()

        brinquedos = (
            Brinquedos.objects
            .prefetch_related(
                "categorias_brinquedos",
                "tags",
                "imagens_brinquedo",
            )
            .order_by("nome_brinquedo", "id")
        )

        if categoria != "todas":
            brinquedos = brinquedos.filter(
                categorias_brinquedos__id=categoria
            ).distinct()

        if busca:
            brinquedos = brinquedos.filter(
                nome_brinquedo__icontains=busca
            )

        paginator = Paginator(brinquedos, 50)
        page = request.GET.get("page")
        brinquedos_page = paginator.get_page(page)

        categorias = CategoriasBrinquedos.objects.order_by("nome_categoria", "id")
        tags = TagsBrinquedos.objects.order_by("nome_tags", "id")

        def formatar_decimal_br(valor, casas=2, milhares=False):
            if valor is None:
                return ""
            numero = Decimal(valor).quantize(
                Decimal("1." + ("0" * casas)),
                rounding=ROUND_HALF_UP,
            )
            texto = (
                f"{numero:,.{casas}f}"
                if milhares else
                f"{numero:.{casas}f}"
            )
            return (
                texto
                .replace(",", "X")
                .replace(".", ",")
                .replace("X", ".")
            )

        brinquedos_dados = [
            {
                "id": brinquedo.id,
                "nome_brinquedo": brinquedo.nome_brinquedo or "",
                "descricao": brinquedo.descricao or "",
                "valor_brinquedo": (
                    formatar_decimal_br(
                        brinquedo.valor_brinquedo,
                        casas=2,
                        milhares=True,
                    )
                    if brinquedo.valor_brinquedo is not None else ""
                ),
                "avaliacao": (
                    formatar_decimal_br(brinquedo.avaliacao, casas=1)
                    if brinquedo.avaliacao is not None else ""
                ),
                "voltz": brinquedo.voltz or "",
                "altura_m": (
                    formatar_decimal_br(brinquedo.altura_m, casas=2)
                    if brinquedo.altura_m is not None else ""
                ),
                "largura_m": (
                    formatar_decimal_br(brinquedo.largura_m, casas=2)
                    if brinquedo.largura_m is not None else ""
                ),
                "profundidade_m": (
                    formatar_decimal_br(brinquedo.profundidade_m, casas=2)
                    if brinquedo.profundidade_m is not None else ""
                ),
                "exibir_na_loja": brinquedo.exibir_na_loja,
                "imagem_url": (
                    brinquedo.imagem_brinquedo.url
                    if brinquedo.imagem_brinquedo else ""
                ),
                "categorias_ids": list(
                    brinquedo.categorias_brinquedos.values_list("id", flat=True)
                ),
                "tags_ids": list(
                    brinquedo.tags.values_list("id", flat=True)
                ),
            }
            for brinquedo in brinquedos_page
        ]

        todos = Brinquedos.objects.all()

        context = {
            "brinquedos": brinquedos_page,
            "categorias": categorias,
            "tags": tags,
            "categoria_ativa": categoria,
            "busca": busca,
            "page_obj": brinquedos_page,
            "brinquedos_dados": brinquedos_dados,
            "total_brinquedos": todos.count(),
            "total_loja": todos.filter(exibir_na_loja=True).count(),
            "total_com_imagem": todos.exclude(
                imagem_brinquedo__isnull=True
            ).exclude(imagem_brinquedo="").count(),
            "total_categorias": categorias.count(),
        }

        return render(request, "gestao/brinquedos_adm.html", context)

    @transaction.atomic
    def post(self, request):
        try:
            action = request.POST.get("action", "save")

            if action == "delete":
                brinquedo = get_object_or_404(
                    Brinquedos,
                    pk=request.POST.get("id")
                )
                nome = brinquedo.nome_brinquedo or "Brinquedo"
                frase_esperada = f"CONFIRMAR EXCLUSÃO {nome}"
                frase_informada = request.POST.get(
                    "confirmacao_exclusao", ""
                ).strip()

                if frase_informada != frase_esperada:
                    messages.error(
                        request,
                        "Exclusão cancelada: o texto de confirmação não "
                        "corresponde ao nome do brinquedo."
                    )
                    return redirect("brinquedos_admin")

                brinquedo.delete()
                messages.success(
                    request,
                    f"Brinquedo '{nome}' excluído com sucesso."
                )
                return redirect("brinquedos_admin")

            if action != "save":
                messages.error(request, "Ação inválida.")
                return redirect("brinquedos_admin")

            brinquedo_id = request.POST.get("id")
            brinquedo = (
                get_object_or_404(Brinquedos, pk=brinquedo_id)
                if brinquedo_id else Brinquedos()
            )

            nome = request.POST.get("nome_brinquedo", "").strip()
            imagens = request.FILES.getlist("imagens_brinquedo")
            if not imagens:
                imagem_legada = request.FILES.get("imagem_brinquedo")
                imagens = [imagem_legada] if imagem_legada else []
            imagem = imagens[0] if imagens else None
            descricao = request.POST.get("descricao", "").strip()
            preco = request.POST.get("valor_brinquedo")
            avaliacao = request.POST.get("avaliacao")
            voltz = request.POST.get("voltz")
            categorias_ids = request.POST.getlist("categorias_brinquedos")
            tags_ids = request.POST.getlist("tags")
            altura = request.POST.get("altura_m")
            largura = request.POST.get("largura_m")
            profundidade = request.POST.get("profundidade_m")

            if not nome or not descricao:
                messages.error(request, "Preencha todos os campos obrigatórios.")
                return redirect("brinquedos_admin")

            if not brinquedo.pk and not imagem:
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

            def parse_decimal(v, nome_campo, limite=None):
                if v is None or not str(v).strip():
                    return None
                normalizado = (
                    str(v)
                    .strip()
                    .replace("R$", "")
                    .replace("m", "")
                    .replace(" ", "")
                )

                # Formato brasileiro: 10.990,00 -> 10990.00.
                # Também aceita o formato técnico 10990.00.
                if "," in normalizado:
                    normalizado = (
                        normalizado
                        .replace(".", "")
                        .replace(",", ".")
                    )
                elif normalizado.count(".") > 1:
                    normalizado = normalizado.replace(".", "")

                try:
                    numero = Decimal(normalizado)
                except (InvalidOperation, ValueError):
                    raise ValueError(
                        f"{nome_campo}: informe um número válido."
                    )

                if numero < 0:
                    raise ValueError(
                        f"{nome_campo}: o valor não pode ser negativo."
                    )
                if limite is not None and numero > limite:
                    raise ValueError(
                        f"{nome_campo}: o máximo permitido é "
                        f"{str(limite).replace('.', ',')}."
                    )
                return numero.quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP,
                )

            preco = parse_decimal(
                preco,
                "Valor",
                Decimal("99999999.99"),
            )
            avaliacao = parse_decimal(
                avaliacao,
                "Avaliação",
                Decimal("5"),
            )
            altura = parse_decimal(
                altura,
                "Altura",
                Decimal("9999.99"),
            )
            largura = parse_decimal(
                largura,
                "Largura",
                Decimal("9999.99"),
            )
            profundidade = parse_decimal(
                profundidade,
                "Profundidade",
                Decimal("9999.99"),
            )

            if avaliacao is None:
                avaliacao = Decimal("0")
            if avaliacao < 0 or avaliacao > 5:
                messages.error(request, "A avaliação deve estar entre 0 e 5.")
                return redirect("brinquedos_admin")

            brinquedo.nome_brinquedo = nome
            brinquedo.descricao = descricao
            brinquedo.valor_brinquedo = preco
            brinquedo.avaliacao = avaliacao
            brinquedo.voltz = voltz or ""
            brinquedo.altura_m = altura
            brinquedo.largura_m = largura
            brinquedo.profundidade_m = profundidade
            brinquedo.exibir_na_loja = (
                    request.POST.get("exibir_na_loja") == "on"
            )
            if imagem:
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
            brinquedo.tags.set(tags_ids)

            messages.success(
                request,
                (
                    f"Brinquedo '{brinquedo.nome_brinquedo}' cadastrado "
                    "com sucesso."
                    if criando else
                    f"Brinquedo '{brinquedo.nome_brinquedo}' atualizado "
                    "com sucesso."
                )
            )
            return redirect("brinquedos_admin")

        except (ArithmeticError, InvalidOperation, ValueError) as exc:
            messages.error(
                request,
                str(exc)
            )
            return redirect("brinquedos_admin")
        except Exception as exc:
            logging.getLogger(__name__).exception(
                "Erro ao salvar brinquedo no painel administrativo"
            )
            messages.error(
                request,
                "Não foi possível salvar o brinquedo. "
                f"Erro: {type(exc).__name__}. Confira a imagem e os campos."
            )
            return redirect("brinquedos_admin")


from django.http import JsonResponse
from django.db import IntegrityError


class NovaCategoria(AdminOnlyMixin, View):

    def post(self, request):
        try:
            nome = request.POST.get("nome_categoria")
            img = request.FILES.get("imagem_categoria")

            if not nome or not img:
                return JsonResponse({"status": "erro", "msg": "Preencha todos os campos."})

            try:
                nova = CategoriasBrinquedos.objects.create(
                    nome_categoria=nome,
                    imagem_categoria=img
                )
            except IntegrityError:
                # Captura o erro de UNIQUE
                return JsonResponse({
                    "status": "erro",
                    "msg": f"Já existe uma categoria com o nome '{nome}'"
                })

            return JsonResponse({
                "status": "sucesso",
                "msg": "Categoria adicionada!",
                "id": nova.id,
                "nome": nova.nome_categoria
            })

        except Exception as e:
            return JsonResponse({"status": "erro", "msg": f"Erro inesperado: {str(e)}"})


class NovaTag(AdminOnlyMixin, View):
    def post(self, request):
        nome = request.POST.get("nome_tag", "").strip()
        if not nome:
            return JsonResponse({
                "status": "erro",
                "msg": "Informe o nome da tag."
            }, status=400)

        nova = TagsBrinquedos.objects.create(nome_tags=nome)
        return JsonResponse({
            "status": "sucesso",
            "msg": "Tag criada com sucesso.",
            "id": nova.id,
            "nome": nova.nome_tags,
        })


from django.utils.timesince import timesince
from django.utils import timezone

from .forms import ImagensSiteForm

MAX_BANNERS = 5


class BannerAdminView(LoginRequiredMixin, View):
    template_name = "gestao/banner_adm.html"

    def get(self, request):
        imagens_site = ImagensSite.objects.all()
        total = imagens_site.count()
        limite_restante = max(0, MAX_BANNERS - total)

        for banner in imagens_site:
            if banner.atualizado and banner.atualizado != banner.criacao:
                dias = timesince(banner.atualizado, timezone.now())
                banner.status_atualizacao = f'Atualizado há {dias}'
            else:
                banner.status_atualizacao = 'Nunca foi alterado'

        form = ImagensSiteForm()

        return render(request, self.template_name, {
            'imagens_site': imagens_site,
            'form': form,
            'limite_restante': limite_restante,
            'max_banners': MAX_BANNERS,
        })

    def post(self, request):
        # =============================
        # ATUALIZAÇÃO DE BANNER
        # =============================
        update_id = request.POST.get('update_id')
        imagem_update = request.FILES.get('imagem')

        if update_id and imagem_update:
            banner = get_object_or_404(ImagensSite, pk=update_id)
            banner.imagem = imagem_update
            banner.atualizado = timezone.now()
            banner.save()

            messages.success(request, 'Banner atualizado com sucesso.')
            return redirect('banner_adm')

        # =============================
        # UPLOAD DE NOVOS BANNERS
        # =============================
        imagens = request.FILES.getlist('imagens')

        if not imagens:
            messages.warning(request, 'Nenhuma imagem selecionada.')
            return redirect('banner_adm')

        total_atual = ImagensSite.objects.count()
        restante = MAX_BANNERS - total_atual

        if restante <= 0:
            messages.error(
                request,
                f'Limite máximo de {MAX_BANNERS} banners atingido.'
            )
            return redirect('banner_adm')

        if len(imagens) > restante:
            messages.error(
                request,
                f'Você só pode adicionar mais {restante} banner(s).'
            )
            return redirect('banner_adm')

        for imagem in imagens:
            ImagensSite.objects.create(imagem=imagem)

        messages.success(request, 'Banner(s) adicionados com sucesso.')
        return redirect('banner_adm')


class BannerDeleteView(LoginRequiredMixin, View):

    def post(self, request, pk):
        banner = get_object_or_404(ImagensSite, pk=pk)
        banner.delete()
        messages.success(request, 'Banner removido com sucesso.')
        return redirect('banner_adm')


from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views import View


class DashboardAdminView(AdminOnlyMixin, View):
    template_name = "gestao/dashboard.html"

    def get(self, request):
        filtro = request.GET.get("filtro", "geral")
        agora = timezone.now()

        if filtro == "7dias":
            data_inicio = agora - timedelta(days=7)
        elif filtro == "30dias":
            data_inicio = agora - timedelta(days=30)
        elif filtro == "ano":
            data_inicio = agora.replace(
                month=1,
                day=1,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
        else:
            filtro = "geral"
            data_inicio = None

        clientes_qs = ClientePerfil.objects.select_related("user").filter(
            user__is_staff=False,
            user__is_superuser=False,
        )

        if data_inicio:
            clientes_qs = clientes_qs.filter(
                criado_em__gte=data_inicio
            )

        total_clientes = clientes_qs.count()

        pedidos_qs = Pedido.objects.all()

        if data_inicio:
            pedidos_qs = pedidos_qs.filter(
                criacao__gte=data_inicio
            )

        total_pedidos = pedidos_qs.count()

        pedidos_finalizados_qs = pedidos_qs.filter(
            status="finalizado"
        )

        pedidos_finalizados = pedidos_finalizados_qs.count()

        taxa_conversao = (
            pedidos_finalizados / total_pedidos * 100
            if total_pedidos
            else 0
        )

        vendas_total = (
                pedidos_finalizados_qs.aggregate(
                    total=Sum("total_liquido")
                ).get("total")
                or Decimal("0.00")
        )

        vendas_total_formatado = (
            f"R$ {vendas_total:,.2f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )

        labels = []
        vendas_data = []

        vendas_agrupadas = (
            pedidos_finalizados_qs
            .exclude(criacao__isnull=True)
            .annotate(data=TruncDate("criacao"))
            .values("data")
            .annotate(total=Sum("total_liquido"))
            .order_by("data")
        )

        if filtro in ("geral", "ano"):
            vendas_por_mes = defaultdict(Decimal)

            for item in vendas_agrupadas:
                if not item["data"]:
                    continue

                mes = item["data"].strftime("%m/%Y")
                total = item["total"] or Decimal("0.00")
                vendas_por_mes[mes] += total

            labels = list(vendas_por_mes.keys())
            vendas_data = [
                float(valor)
                for valor in vendas_por_mes.values()
            ]

        else:
            for item in vendas_agrupadas:
                if not item["data"]:
                    continue

                labels.append(
                    item["data"].strftime("%d/%m")
                )

                vendas_data.append(
                    float(item["total"] or Decimal("0.00"))
                )

        # ------------------------------------------------------------
        # ESTATÍSTICAS DE ACESSOS
        # Agora fazem parte do dashboard e respeitam o mesmo filtro.
        # ------------------------------------------------------------
        brinquedos_clicks = BrinquedoClick.objects.all()
        combos_clicks = ComboClick.objects.all()
        promocoes_clicks = PromocaoClick.objects.all()
        categorias_clicks = CategoriaClick.objects.all()

        if data_inicio:
            brinquedos_clicks = brinquedos_clicks.filter(criacao__gte=data_inicio)
            combos_clicks = combos_clicks.filter(criacao__gte=data_inicio)
            promocoes_clicks = promocoes_clicks.filter(criacao__gte=data_inicio)
            categorias_clicks = categorias_clicks.filter(criacao__gte=data_inicio)

        top_brinquedos = (
            brinquedos_clicks
            .values("brinquedo_clicado__nome_brinquedo")
            .annotate(total=Sum("quantidade_click"))
            .order_by("-total")[:20]
        )
        top_combos = (
            combos_clicks
            .values("descricao_combo")
            .annotate(total=Sum("quantidade_click"))
            .order_by("-total")[:20]
        )
        top_promocoes = (
            promocoes_clicks
            .values("descricao_promocao")
            .annotate(total=Sum("quantidade_click"))
            .order_by("-total")[:20]
        )
        top_categorias = (
            categorias_clicks
            .values("nome_categoria")
            .annotate(total=Sum("quantidade_click"))
            .order_by("-total")[:20]
        )

        total_brinquedo_clicks = (
                brinquedos_clicks.aggregate(total=Sum("quantidade_click"))["total"]
                or 0
        )
        total_combo_clicks = (
                combos_clicks.aggregate(total=Sum("quantidade_click"))["total"]
                or 0
        )
        total_promocao_clicks = (
                promocoes_clicks.aggregate(total=Sum("quantidade_click"))["total"]
                or 0
        )
        total_categoria_clicks = (
                categorias_clicks.aggregate(total=Sum("quantidade_click"))["total"]
                or 0
        )
        total_geral = (
                total_brinquedo_clicks
                + total_combo_clicks
                + total_promocao_clicks
                + total_categoria_clicks
        )

        crescimento_por_dia = defaultdict(int)
        for queryset in (
                brinquedos_clicks,
                combos_clicks,
                promocoes_clicks,
                categorias_clicks,
        ):
            dados_diarios = (
                queryset
                .exclude(criacao__isnull=True)
                .annotate(dia=TruncDate("criacao"))
                .values("dia")
                .annotate(total=Sum("quantidade_click"))
                .order_by("dia")
            )
            for item in dados_diarios:
                if item["dia"]:
                    crescimento_por_dia[item["dia"]] += item["total"] or 0

        crescimento_diario = [
            {"dia": dia, "total": total}
            for dia, total in sorted(
                crescimento_por_dia.items(),
                key=lambda item: item[0],
                reverse=True,
            )[:15]
        ]

        context = {
            "filtro": filtro,
            "total_clientes": total_clientes,
            "total_pedidos": total_pedidos,
            "pedidos_finalizados": pedidos_finalizados,
            "taxa_conversao": f"{taxa_conversao:.1f}%",
            "vendas_total": vendas_total_formatado,
            "chart_labels": labels,
            "chart_data": vendas_data,
            "top_brinquedos": top_brinquedos,
            "top_combos": top_combos,
            "top_promocoes": top_promocoes,
            "top_categorias": top_categorias,
            "total_brinquedo_clicks": total_brinquedo_clicks,
            "total_combo_clicks": total_combo_clicks,
            "total_promocao_clicks": total_promocao_clicks,
            "total_categoria_clicks": total_categoria_clicks,
            "total_geral": total_geral,
            "crescimento_diario": crescimento_diario,
        }

        return render(
            request,
            self.template_name,
            context,
        )


from django.http import HttpResponseForbidden
from django.db.models.functions import TruncDate


class EstatisticasGeraisView(AdminOnlyMixin, View):
    def get(self, request):
        filtro = request.GET.get("filtro", "geral")
        return redirect(f"{reverse('dashboards')}?filtro={filtro}#estatisticas-acessos")


class ManutencaoAdminView(AdminOnlyMixin, View):
    """
    Central de atendimento das solicitações de manutenção.

    A tela:
    - pesquisa por protocolo, cliente, equipamento, contato, cidade e problema;
    - filtra por status e período;
    - valida o formato do telefone antes de montar links de ligação/WhatsApp;
    - usa o telefone informado na solicitação e, como reserva, o telefone do perfil;
    - permite atualizar o status pela própria tela;
    - evita N+1 com select_related/prefetch_related.
    """

    template_name = "gestao/manutencao_adm.html"
    ITENS_POR_PAGINA = 12
    STATUS_VALIDOS = dict(Manutencao.STATUS_CHOICES)

    # Texto usado no e-mail de aviso enviado ao cliente quando o status muda.
    STATUS_MENSAGEM_CLIENTE = {
        "P": "sua solicitação voltou para a fila de pendentes",
        "A": "nossa equipe técnica já está com o atendimento em andamento",
        "C": "seu atendimento foi concluído",
        "X": "sua solicitação foi cancelada",
    }

    @staticmethod
    def _nome_cliente(manutencao):
        perfil = manutencao.usuario
        user = perfil.user

        candidatos = [
            perfil.nome_completo,
            user.get_full_name(),
            user.username,
        ]
        return next(
            (str(valor).strip() for valor in candidatos if valor and str(valor).strip()),
            f"Cliente #{perfil.pk}",
        )

    @staticmethod
    def _iniciais(nome):
        partes = [parte for parte in (nome or "").split() if parte]
        if not partes:
            return "CL"
        if len(partes) == 1:
            return partes[0][:2].upper()
        return f"{partes[0][0]}{partes[-1][0]}".upper()

    @staticmethod
    def _normalizar_telefone(valor):
        """
        Aceita telefone nacional com DDD ou telefone com código do Brasil.

        Isto valida o FORMATO necessário para links tel: e wa.me. Não existe
        verificação pública confiável, sem API oficial, para confirmar se o
        número realmente possui uma conta ativa no WhatsApp.
        """
        import re

        original = (valor or "").strip()
        digitos = re.sub(r"\D", "", original)

        if digitos.startswith("00"):
            digitos = digitos[2:]

        if digitos.startswith("55") and len(digitos) in (12, 13):
            nacional = digitos[2:]
        elif len(digitos) in (10, 11):
            nacional = digitos
            digitos = f"55{digitos}"
        else:
            return {
                "original": original,
                "valido": False,
                "internacional": "",
                "formatado": original or "Não informado",
                "motivo": "Informe DDD + número, com 10 ou 11 dígitos.",
            }

        ddd = nacional[:2]
        numero = nacional[2:]

        # Impede DDD iniciado em zero e números locais incompletos.
        if not ddd.isdigit() or ddd.startswith("0") or len(numero) not in (8, 9):
            return {
                "original": original,
                "valido": False,
                "internacional": "",
                "formatado": original or "Não informado",
                "motivo": "DDD ou quantidade de dígitos inválida.",
            }

        if len(numero) == 9:
            formatado = f"({ddd}) {numero[:5]}-{numero[5:]}"
        else:
            formatado = f"({ddd}) {numero[:4]}-{numero[4:]}"

        return {
            "original": original,
            "valido": True,
            "internacional": digitos,
            "formatado": formatado,
            "motivo": "Formato válido para ligação e abertura do WhatsApp.",
        }

    @staticmethod
    def _email_valido(email):
        from django.core.exceptions import ValidationError
        from django.core.validators import validate_email

        email = (email or "").strip()
        if not email:
            return False

        try:
            validate_email(email)
        except ValidationError:
            return False
        return True

    @staticmethod
    def _endereco_completo(manutencao):
        linha_principal = ", ".join(
            parte for parte in [
                (manutencao.endereco or "").strip(),
                (manutencao.numero or "").strip(),
            ]
            if parte
        )

        if manutencao.complemento:
            linha_principal = ", ".join(
                parte for parte in [
                    linha_principal,
                    manutencao.complemento.strip(),
                ]
                if parte
            )

        linha_local = " - ".join(
            parte for parte in [
                (manutencao.bairro or "").strip(),
                "/".join(
                    parte for parte in [
                        (manutencao.cidade or "").strip(),
                        (manutencao.estado or "").strip(),
                    ]
                    if parte
                ),
            ]
            if parte
        )

        endereco = ", ".join(
            parte for parte in [linha_principal, linha_local] if parte
        )

        if manutencao.cep:
            endereco = f"{endereco} • CEP {manutencao.cep}" if endereco else f"CEP {manutencao.cep}"

        return endereco or "Endereço não informado"

    def _preparar_manutencao(self, manutencao):
        from django.utils import timezone
        from urllib.parse import quote, urlencode

        manutencao.cliente_nome = self._nome_cliente(manutencao)
        manutencao.cliente_iniciais = self._iniciais(manutencao.cliente_nome)
        manutencao.cliente_username = manutencao.usuario.user.username
        manutencao.cliente_email = (manutencao.usuario.user.email or "").strip()
        manutencao.email_valido = self._email_valido(manutencao.cliente_email)

        telefone_solicitacao = (manutencao.telefone_contato or "").strip()
        telefone_perfil = (manutencao.usuario.telefone or "").strip()
        telefone_escolhido = telefone_solicitacao or telefone_perfil

        telefone = self._normalizar_telefone(telefone_escolhido)
        manutencao.telefone_exibicao = telefone["formatado"]
        manutencao.telefone_valido = telefone["valido"]
        manutencao.telefone_motivo = telefone["motivo"]
        manutencao.telefone_origem = (
            "Informado nesta solicitação"
            if telefone_solicitacao
            else "Telefone salvo no perfil"
            if telefone_perfil
            else "Não informado"
        )

        equipamento = manutencao.nome_equipamento
        protocolo = f"MAN-{manutencao.pk:05d}"

        mensagem_whatsapp = (
            f"Olá, {manutencao.cliente_nome}. "
            f"Aqui é da Lazer & Sport Brinquedos. "
            f"Estamos entrando em contato sobre a solicitação {protocolo}, "
            f"referente ao equipamento {equipamento}."
        )

        if telefone["valido"]:
            manutencao.telefone_url = f"tel:+{telefone['internacional']}"
            manutencao.whatsapp_url = (
                f"https://wa.me/{telefone['internacional']}"
                f"?text={quote(mensagem_whatsapp)}"
            )
        else:
            manutencao.telefone_url = ""
            manutencao.whatsapp_url = ""

        if manutencao.email_valido:
            assunto = f"Lazer & Sport | Manutenção {protocolo}"
            corpo = (
                f"Olá, {manutencao.cliente_nome}.\n\n"
                f"Estamos entrando em contato sobre a solicitação {protocolo}, "
                f"referente ao equipamento {equipamento}.\n\n"
                "Atenciosamente,\nLazer & Sport Brinquedos"
            )
            manutencao.email_url = (
                f"mailto:{manutencao.cliente_email}?"
                f"{urlencode({'subject': assunto, 'body': corpo})}"
            )
        else:
            manutencao.email_url = ""

        manutencao.endereco_completo = self._endereco_completo(manutencao)
        manutencao.mapa_url = (
            "https://www.google.com/maps/search/?api=1&query="
            f"{quote(manutencao.endereco_completo)}"
            if manutencao.endereco_completo != "Endereço não informado"
            else ""
        )

        agora = timezone.now()
        idade = agora - manutencao.criado_em
        horas = max(0, int(idade.total_seconds() // 3600))
        dias = horas // 24

        if horas < 1:
            manutencao.tempo_aberto = "Aberta há poucos minutos"
        elif horas < 24:
            manutencao.tempo_aberto = f"Aberta há {horas}h"
        elif dias == 1:
            manutencao.tempo_aberto = "Aberta há 1 dia"
        else:
            manutencao.tempo_aberto = f"Aberta há {dias} dias"

        manutencao.precisa_atencao = (
                manutencao.status in {"P", "A"} and horas >= 72
        )
        manutencao.atencao_moderada = (
                manutencao.status in {"P", "A"} and 24 <= horas < 72
        )

        if manutencao.precisa_atencao:
            manutencao.prioridade_texto = "Atenção: mais de 3 dias"
        elif manutencao.atencao_moderada:
            manutencao.prioridade_texto = "Aguardando há mais de 24h"
        else:
            manutencao.prioridade_texto = ""

        manutencao.protocolo = protocolo
        manutencao.imagens_cache = list(manutencao.imagens.all())
        manutencao.total_imagens = len(manutencao.imagens_cache)

        return manutencao

    def _queryset_filtrado(self, request):
        from datetime import timedelta
        from django.db.models import Case, IntegerField, Q, Value, When
        from django.utils import timezone

        qs = (
            Manutencao.objects
            .select_related("brinquedo", "usuario__user")
            .prefetch_related("imagens")
        )

        busca = (request.GET.get("q") or "").strip()
        status = (request.GET.get("status") or "").strip().upper()
        periodo = (request.GET.get("periodo") or "").strip()
        ordem = (request.GET.get("ordem") or "recentes").strip()

        if busca:
            filtro = (
                    Q(usuario__nome_completo__icontains=busca)
                    | Q(usuario__user__username__icontains=busca)
                    | Q(usuario__user__first_name__icontains=busca)
                    | Q(usuario__user__last_name__icontains=busca)
                    | Q(usuario__user__email__icontains=busca)
                    | Q(usuario__telefone__icontains=busca)
                    | Q(telefone_contato__icontains=busca)
                    | Q(brinquedo__nome_brinquedo__icontains=busca)
                    | Q(brinquedo_descricao_livre__icontains=busca)
                    | Q(descricao__icontains=busca)
                    | Q(cidade__icontains=busca)
                    | Q(estado__icontains=busca)
                    | Q(cep__icontains=busca)
            )
            busca_protocolo = busca.upper().replace("MAN-", "").lstrip("0")
            if busca_protocolo.isdigit():
                filtro |= Q(pk=int(busca_protocolo))
            qs = qs.filter(filtro)

        if status in self.STATUS_VALIDOS:
            qs = qs.filter(status=status)
        else:
            status = ""

        periodos = {
            "hoje": timedelta(days=1),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30),
            "90d": timedelta(days=90),
        }
        if periodo in periodos:
            qs = qs.filter(criado_em__gte=timezone.now() - periodos[periodo])
        else:
            periodo = ""

        if ordem == "antigas":
            qs = qs.order_by("criado_em")
        elif ordem == "atualizadas":
            qs = qs.order_by("-atualizada_em", "-criado_em")
        elif ordem == "prioridade":
            qs = (
                qs.annotate(
                    _ordem_status=Case(
                        When(status="P", then=Value(0)),
                        When(status="A", then=Value(1)),
                        When(status="C", then=Value(2)),
                        default=Value(3),
                        output_field=IntegerField(),
                    )
                )
                .order_by("_ordem_status", "criado_em")
            )
        else:
            ordem = "recentes"
            qs = qs.order_by("-criado_em")

        filtros = {
            "q": busca,
            "status": status,
            "periodo": periodo,
            "ordem": ordem,
        }
        return qs, filtros

    def get(self, request):
        from datetime import timedelta
        from django.core.paginator import Paginator
        from django.db.models import Count, Q
        from django.utils import timezone

        base = Manutencao.objects.all()
        limite_atencao = timezone.now() - timedelta(days=3)

        metricas = base.aggregate(
            total=Count("id"),
            pendentes=Count("id", filter=Q(status="P")),
            andamento=Count("id", filter=Q(status="A")),
            concluidas=Count("id", filter=Q(status="C")),
            canceladas=Count("id", filter=Q(status="X")),
            atencao=Count(
                "id",
                filter=Q(
                    status__in=["P", "A"],
                    criado_em__lte=limite_atencao,
                ),
            ),
        )

        qs, filtros = self._queryset_filtrado(request)
        paginator = Paginator(qs, self.ITENS_POR_PAGINA)
        page_obj = paginator.get_page(request.GET.get("page"))

        manutencoes_preparadas = [
            self._preparar_manutencao(item)
            for item in page_obj.object_list
        ]
        page_obj.object_list = manutencoes_preparadas

        query_sem_pagina = request.GET.copy()
        query_sem_pagina.pop("page", None)

        contexto = {
            "manutencoes": page_obj,
            "page_obj": page_obj,
            "metricas": metricas,
            "filtros": filtros,
            "status_choices": Manutencao.STATUS_CHOICES,
            "querystring_sem_pagina": query_sem_pagina.urlencode(),
            "total_filtrado": paginator.count,
        }
        return render(request, self.template_name, contexto)

    def _notificar_mudanca_status(self, manutencao, novo_status):
        """
        Avisa o cliente por e-mail que o status do atendimento mudou.

        Nunca deve derrubar a requisição que atualizou o status -- qualquer
        problema de envio só é registrado no log e devolvido pro chamador
        decidir se avisa o administrador. Retorna:
        - True: e-mail enviado.
        - False: havia e-mail válido, mas o envio falhou (SMTP fora do
          ar, credencial ausente/errada, etc.) -- vale avisar o admin.
        - None: cliente não tem e-mail válido cadastrado -- não é uma
          falha, só não tinha pra quem mandar.
        """
        from django.core.mail import send_mail
        from django.conf import settings

        email = (manutencao.usuario.user.email or "").strip()
        if not email or not self._email_valido(email):
            return None

        try:
            protocolo = f"MAN-{manutencao.pk:05d}"
            rotulo_status = self.STATUS_VALIDOS.get(novo_status, novo_status)
            explicacao = self.STATUS_MENSAGEM_CLIENTE.get(
                novo_status, f"o status mudou para {rotulo_status}",
            )
            nome_cliente = self._nome_cliente(manutencao)

            assunto = f"Lazer & Sport | Atualização da manutenção {protocolo}"
            corpo = (
                f"Olá, {nome_cliente}.\n\n"
                f"Sua solicitação de manutenção {protocolo} "
                f"({manutencao.nome_equipamento}) foi atualizada: {explicacao}.\n\n"
                f"Novo status: {rotulo_status}\n\n"
                "Se tiver dúvidas, é só responder este e-mail ou chamar a "
                "gente no WhatsApp.\n\n"
                "Atenciosamente,\nEquipe técnica Lazer & Sport Brinquedos"
            )

            enviados = send_mail(
                assunto,
                corpo,
                getattr(settings, "DEFAULT_FROM_EMAIL", None),
                [email],
                fail_silently=False,
            )
            # send_mail devolve quantas mensagens foram entregues ao
            # backend -- 0 também conta como falha, mesmo sem exceção.
            return bool(enviados)
        except Exception:
            logging.getLogger(__name__).exception(
                "Falha ao enviar e-mail de atualização de status "
                "(manutenção %s, novo status %s)",
                getattr(manutencao, "pk", None), novo_status,
            )
            return False

    def post(self, request):
        """
        Atualiza o status de uma manutenção a partir das ações rápidas do
        card ou do seletor dentro do modal.

        Qualquer falha inesperada (id inválido, corrida entre duas
        atualizações simultâneas, etc.) é capturada e vira uma mensagem
        amigável -- nunca deve estourar como erro 500 pro administrador.
        """
        from django.db import transaction
        from django.utils.http import url_has_allowed_host_and_scheme

        def montar_proxima_url(manutencao_id=None):
            destino = request.POST.get("next") or request.path

            if not url_has_allowed_host_and_scheme(
                    destino,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure(),
            ):
                destino = request.path

            if manutencao_id:
                separador = "&" if "?" in destino else "?"
                destino = f"{destino}{separador}foco={manutencao_id}"

            return destino

        manutencao_id_bruto = request.POST.get("manutencao_id")
        novo_status = (request.POST.get("status") or "").strip().upper()

        try:
            manutencao_id = int(manutencao_id_bruto)
        except (TypeError, ValueError):
            messages.error(request, "Solicitação de manutenção inválida.")
            return redirect(montar_proxima_url())

        if novo_status not in self.STATUS_VALIDOS:
            messages.error(request, "Selecione um status válido.")
            return redirect(montar_proxima_url(manutencao_id))

        try:
            cliente_para_notificar = None

            with transaction.atomic():
                # IMPORTANTE: o Postgres proíbe "FOR UPDATE" no lado anulável
                # de um LEFT OUTER JOIN. Pra não depender de saber de cor
                # quais FKs são opcionais (e não ser pego de surpresa de
                # novo se o schema mudar), o lock aqui NÃO usa nenhum
                # select_related -- trava só a linha da Manutencao, sem
                # join nenhum. Os dados de usuario/user/brinquedo usados
                # logo abaixo (nome_equipamento, notificação por e-mail)
                # são buscados em consultas lazy separadas, já fora do
                # risco de outer join -- 1 ou 2 queries extras pequenas,
                # sem custo real numa ação de clique único.
                manutencao = (
                    Manutencao.objects
                    .select_for_update()
                    .get(pk=manutencao_id)
                )

                status_anterior = manutencao.status
                if status_anterior == novo_status:
                    messages.info(
                        request,
                        f"{manutencao.nome_equipamento} já está com esse status.",
                    )
                else:
                    manutencao.status = novo_status
                    manutencao.save(
                        update_fields=["status", "atualizada_em"]
                    )
                    messages.success(
                        request,
                        (
                            f"Manutenção MAN-{manutencao.pk:05d} atualizada: "
                            f"{self.STATUS_VALIDOS[status_anterior]} → "
                            f"{self.STATUS_VALIDOS[novo_status]}."
                        ),
                    )
                    # Guardamos a instância pra avisar o cliente só depois
                    # do commit -- o e-mail é I/O externo e não deve
                    # segurar o lock da linha nem desfazer a atualização
                    # se o envio falhar.
                    cliente_para_notificar = manutencao

            if cliente_para_notificar is not None:
                enviado = self._notificar_mudanca_status(
                    cliente_para_notificar, novo_status,
                )
                if enviado is False:
                    messages.warning(
                        request,
                        "Status atualizado, mas não foi possível avisar o "
                        "cliente por e-mail agora. Confira as configurações "
                        "de e-mail do servidor.",
                    )

        except Manutencao.DoesNotExist:
            messages.error(request, "A manutenção informada não foi encontrada.")

        except Exception:
            # Rede instável, corrida com outra aba, etc. -- nunca deixa
            # vazar como erro 500; o administrador só tenta de novo.
            logging.getLogger(__name__).exception(
                "Falha ao atualizar status da manutenção %s", manutencao_id,
            )
            messages.error(
                request,
                "Não foi possível atualizar o status agora. Tente novamente "
                "em instantes.",
            )

        return redirect(montar_proxima_url(manutencao_id))


class UserAdminView(AdminOnlyMixin, View):
    template_name = "gestao/users_adm.html"

    def get(self, request):
        busca = request.GET.get("q", "").strip()
        tipo = request.GET.get("tipo", "todos")
        usuarios = User.objects.select_related("perfil").order_by("-date_joined")
        if busca:
            usuarios = usuarios.filter(
                Q(username__icontains=busca)
                | Q(email__icontains=busca)
                | Q(first_name__icontains=busca)
                | Q(last_name__icontains=busca)
                | Q(perfil__nome_completo__icontains=busca)
            )
        if tipo == "admins":
            usuarios = usuarios.filter(is_staff=True)
        elif tipo == "clientes":
            usuarios = usuarios.filter(is_staff=False)
        elif tipo == "inativos":
            usuarios = usuarios.filter(is_active=False)
        return render(request, self.template_name, {
            "usuarios": usuarios,
            "busca": busca,
            "tipo": tipo,
        })

    @transaction.atomic
    def post(self, request):
        acao = request.POST.get("acao", "salvar")
        usuario_id = request.POST.get("usuario_id")
        usuario = get_object_or_404(User, pk=usuario_id) if usuario_id else None

        if acao in {"alternar", "excluir"}:
            if not usuario or usuario.is_superuser or usuario == request.user:
                messages.error(request, "Esse usuário é protegido e não pode ser alterado.")
                return redirect("clients")
            if acao == "alternar":
                usuario.is_active = not usuario.is_active
                usuario.save(update_fields=["is_active"])
                messages.success(request, "Status do usuário atualizado.")
            else:
                usuario.delete()
                messages.success(request, "Usuário excluído com sucesso.")
            return redirect("clients")

        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip().lower()
        nome = request.POST.get("nome_completo", "").strip()
        telefone = request.POST.get("telefone", "").strip()
        senha = request.POST.get("password", "")
        is_staff = request.POST.get("is_staff") == "on"

        if not username:
            messages.error(request, "Informe o nome de usuário.")
            return redirect("clients")
        if User.objects.filter(username__iexact=username).exclude(pk=getattr(usuario, "pk", None)).exists():
            messages.error(request, "Esse nome de usuário já está em uso.")
            return redirect("clients")
        if email and User.objects.filter(email__iexact=email).exclude(pk=getattr(usuario, "pk", None)).exists():
            messages.error(request, "Esse e-mail já está em uso.")
            return redirect("clients")
        if not usuario and not senha:
            messages.error(request, "Informe uma senha para o novo usuário.")
            return redirect("clients")
        if usuario and usuario.is_superuser and not is_staff:
            messages.error(request, "Não é possível remover a permissão do superusuário.")
            return redirect("clients")

        if not usuario:
            usuario = User(username=username)
        usuario.username = username
        usuario.email = email
        usuario.is_staff = is_staff or usuario.is_superuser
        usuario.is_active = request.POST.get("is_active") == "on"
        if senha:
            usuario.set_password(senha)
        usuario.save()
        perfil, _ = ClientePerfil.objects.get_or_create(user=usuario)
        perfil.nome_completo = nome or None
        perfil.telefone = telefone or None
        try:
            perfil.full_clean()
        except Exception as exc:
            transaction.set_rollback(True)
            messages.error(request, "Não foi possível salvar o perfil: " + "; ".join(getattr(exc, "messages", [str(exc)])))
            return redirect("clients")
        perfil.save()
        messages.success(request, "Usuário atualizado." if usuario_id else "Usuário criado com sucesso.")
        return redirect("clients")


from django.views.generic import TemplateView
from django.db.models import Sum, Count
from django.utils.timezone import now
from datetime import datetime

from .models import Venda


class RelatorioVendasView(LoginRequiredMixin, TemplateView):
    template_name = "gestao/relatoriov_adm.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        vendas = Venda.objects.filter(confirmado=True)

        data_inicio = self.request.GET.get('data_inicio')
        data_fim = self.request.GET.get('data_fim')
        forma_pagamento = self.request.GET.get('forma_pagamento')

        if data_inicio:
            vendas = vendas.filter(criacao__date__gte=data_inicio)

        if data_fim:
            vendas = vendas.filter(criacao__date__lte=data_fim)

        if forma_pagamento:
            vendas = vendas.filter(forma_pagamento=forma_pagamento)

        context['total_vendas'] = vendas.count()
        context['total_valor'] = vendas.aggregate(
            total=Sum('valor_pago')
        )['total'] or 0

        context['vendas'] = vendas.select_related('pedido').order_by('-criacao')

        context['formas_pagamento'] = [
            ('pix', 'PIX'),
            ('cartao', 'Cartão'),
            ('dinheiro', 'Dinheiro'),
            ('whatsapp', 'WhatsApp'),
        ]

        context['filtros'] = {
            'data_inicio': data_inicio or '',
            'data_fim': data_fim or '',
            'forma_pagamento': forma_pagamento or '',
        }

        return context


from .forms import ManutencaoForm
from .models import Manutencao

from django.contrib.auth.decorators import login_required
from .models import ItemCarrinho, Carrinho

# Cupons só podem ser usados quando o carrinho contém pelo menos um
# brinquedo avulso ou uma peça de reposição. Combos e promoções, sozinhos,
# não liberam o campo nem a aplicação do desconto.
CUPOM_MODELOS_PERMITIDOS = frozenset({
    "brinquedos",
    "pecasreposicao",
})


def _carrinho_permite_cupom(carrinho):
    return carrinho.itens.filter(
        content_type__model__in=CUPOM_MODELOS_PERMITIDOS
    ).exists()


def _invalidar_pagamento_pendente(carrinho):
    """
    Um QR Code/token de pagamento representa uma composição e um valor
    específicos. Qualquer mudança comercial no carrinho invalida a cobrança
    anterior para impedir que ela seja reutilizada com outro total.
    """
    if carrinho.mp_payment_id:
        carrinho.mp_payment_id = None
        carrinho.save(update_fields=["mp_payment_id"])


def _remover_cupom_se_nao_permitido(carrinho):
    if carrinho.cupom_id and not _carrinho_permite_cupom(carrinho):
        carrinho.cupom = None
        carrinho.mp_payment_id = None
        carrinho.save(update_fields=["cupom", "mp_payment_id"])
        return True
    return False


@require_POST
def adicionar_ao_carrinho(request, tipo, object_id):
    if not request.user.is_authenticated:
        return JsonResponse({'erro': 'Você precisa fazer login'}, status=403)

    if not hasattr(request.user, 'perfil'):
        return JsonResponse({'erro': 'Usuário inválido'}, status=403)

    # ⭐ quantidade vinda do input
    try:
        quantidade = int(request.POST.get('quantidade', 1))
        if quantidade < 1:
            quantidade = 1
    except (ValueError, TypeError):
        quantidade = 1

    cliente = request.user.perfil
    carrinho, _ = Carrinho.objects.get_or_create(cliente=cliente)

    modelos = {
        'brinquedo': Brinquedos,
        'combo': Combos,
        'promocao': Promocoes,
        'peca': PecasReposicao,
    }

    model = modelos.get(tipo)
    if not model:
        return JsonResponse({'erro': 'Tipo inválido'}, status=400)

    # O botão só é exibido para brinquedos marcados para venda, mas a
    # validação também precisa existir no servidor para impedir que uma
    # requisição manual adicione ao carrinho um item apenas para orçamento.
    if tipo == 'brinquedo':
        objeto = get_object_or_404(
            Brinquedos,
            id=object_id,
            ativo=True,
            exibir_na_loja=True,
            valor_brinquedo__isnull=False,
            valor_brinquedo__gt=0,
        )
    else:
        objeto = get_object_or_404(model, id=object_id)
    content_type = ContentType.objects.get_for_model(objeto)

    item, created = ItemCarrinho.objects.get_or_create(
        carrinho=carrinho,
        content_type=content_type,
        object_id=objeto.id,
        defaults={'quantidade': quantidade}
    )

    if not created:
        item.quantidade += quantidade
        item.save(update_fields=["quantidade"])

    _invalidar_pagamento_pendente(carrinho)

    total_itens = carrinho.itens.aggregate(total=Sum('quantidade'))['total'] or 0

    return JsonResponse({
        'sucesso': True,
        'total_itens': total_itens
    })


from django.views.decorators.http import require_POST


@login_required
@require_POST
def remover_item_carrinho(request):
    item_id = request.POST.get('item_id')

    try:
        item = ItemCarrinho.objects.get(
            id=item_id,
            carrinho__cliente=request.user.perfil
        )
        carrinho = item.carrinho
        item.delete()
        _remover_cupom_se_nao_permitido(carrinho)
        _invalidar_pagamento_pendente(carrinho)
        return JsonResponse({'status': 'success'})
    except ItemCarrinho.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Item não encontrado'}, status=404)


@login_required
@require_POST
def limpar_carrinho(request):
    carrinho = Carrinho.objects.get(cliente=request.user.perfil)
    carrinho.itens.all().delete()
    carrinho.cupom = None
    carrinho.mp_payment_id = None
    carrinho.save(update_fields=["cupom", "mp_payment_id"])

    return JsonResponse({'status': 'success'})


class CarrinhoView(LoginRequiredMixin, View):

    def get(self, request):

        if not hasattr(request.user, 'perfil'):
            return redirect('home')

        cliente = request.user.perfil

        carrinho, _ = Carrinho.objects.select_related(
            'cupom'
        ).get_or_create(cliente=cliente)

        itens = (
            ItemCarrinho.objects
            .filter(carrinho=carrinho)
            .select_related('content_type')
        )

        # garante objeto frete
        Frete.objects.get_or_create(carrinho=carrinho)

        cupom_permitido = _carrinho_permite_cupom(carrinho)

        # Evita manter um desconto antigo caso o cliente tenha removido o
        # último produto elegível e deixado somente combos/promoções.
        if not cupom_permitido and carrinho.cupom_id:
            carrinho.cupom = None
            carrinho.mp_payment_id = None
            carrinho.save(update_fields=["cupom", "mp_payment_id"])

        context = {
            'carrinho': carrinho,
            'itens': itens,
            'cupom_permitido': cupom_permitido,
            'valor_frete': carrinho.valor_frete,
            'total_final': carrinho.total_final
        }

        return render(request, 'carrinho.html', context)


from django.views.decorators.csrf import csrf_exempt
import json
from .models import Carrinho, Frete
from .utils import calcular_frete_por_cep


@csrf_exempt
def calcular_frete(request):
    if request.method != "POST":
        return JsonResponse({"status": "erro"})

    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"status": "erro"})

    cep = data.get("cep")
    rua = data.get("rua")
    bairro = data.get("bairro")
    cidade = data.get("cidade")
    estado = data.get("estado")
    numero = data.get("numero")

    if not cep:
        return JsonResponse({"status": "erro"})

    try:
        carrinho = Carrinho.objects.get(cliente=request.user.perfil)
    except Carrinho.DoesNotExist:
        return JsonResponse({"status": "erro"})

    # calcula frete
    valor_frete, distancia = calcular_frete_por_cep(cep, numero)

    valor_frete = Decimal(str(valor_frete))
    distancia = Decimal(str(distancia))

    # cria ou pega o frete do carrinho
    frete, _ = Frete.objects.get_or_create(carrinho=carrinho)

    # salva endereço
    frete.cep = cep
    frete.rua = rua
    frete.bairro = bairro
    frete.cidade = cidade
    frete.estado = estado
    frete.numero = numero

    # salva valores do frete
    frete.valor = valor_frete
    frete.distancia_km = distancia

    frete.save()
    _invalidar_pagamento_pendente(carrinho)

    return JsonResponse({
        "status": "ok",
        "frete": float(valor_frete),
        "distancia": float(distancia),
        "total_final": float(carrinho.total_final)
    })


from django.views.decorators.http import require_POST


@require_POST
@login_required
def alterar_quantidade_item(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse(
            {"status": "error", "message": "Dados inválidos."},
            status=400,
        )

    item_id = data.get("item_id")
    try:
        delta = int(data.get("delta", 0))
    except (TypeError, ValueError):
        return JsonResponse(
            {"status": "error", "message": "Quantidade inválida."},
            status=400,
        )

    item = get_object_or_404(
        ItemCarrinho,
        id=item_id,
        carrinho__cliente=request.user.perfil,
    )
    carrinho = item.carrinho

    nova_qtd = item.quantidade + delta

    if nova_qtd <= 0:
        item.delete()
        _remover_cupom_se_nao_permitido(carrinho)
    else:
        item.quantidade = nova_qtd
        item.save(update_fields=["quantidade"])

    _invalidar_pagamento_pendente(carrinho)

    return JsonResponse({"status": "ok"})


from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required


@login_required
@require_POST
def aplicar_cupom(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'title': 'Erro',
            'message': 'Dados inválidos enviados'
        }, status=400)

    codigo = data.get('codigo', '').strip()

    if not codigo:
        return JsonResponse({
            'status': 'warning',
            'title': 'Cupom vazio',
            'message': 'Digite um código de cupom'
        })

    if not hasattr(request.user, 'perfil'):
        return JsonResponse({
            'status': 'error',
            'title': 'Erro',
            'message': 'Perfil do cliente não encontrado'
        }, status=400)

    carrinho = Carrinho.objects.filter(cliente=request.user.perfil).first()

    if not carrinho:
        return JsonResponse({
            'status': 'error',
            'title': 'Carrinho vazio',
            'message': 'Crie um carrinho antes de aplicar o cupom'
        })

    if not carrinho.itens.exists():
        if carrinho.cupom_id:
            carrinho.cupom = None
            carrinho.save(update_fields=['cupom'])
        return JsonResponse({
            'status': 'warning',
            'title': 'Carrinho vazio',
            'message': 'Adicione um produto antes de usar um cupom.'
        })

    if not _carrinho_permite_cupom(carrinho):
        if carrinho.cupom_id:
            carrinho.cupom = None
            carrinho.save(update_fields=['cupom'])
        return JsonResponse({
            'status': 'warning',
            'title': 'Cupom não disponível',
            'message': (
                'Combos e promoções já possuem preço especial. '
                'Adicione um brinquedo ou uma peça de reposição '
                'para liberar o uso de cupom.'
            )
        }, status=400)

    try:
        cupom = Cupom.objects.get(codigo__iexact=codigo)
    except Cupom.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'title': 'Cupom inválido',
            'message': 'Este cupom não existe ou é inválido'
        })

    if not cupom.ativo or (cupom.quantidade_uso is not None and cupom.quantidade_uso < 1):
        return JsonResponse({
            'status': 'warning',
            'title': 'Cupom indisponível',
            'message': 'Este cupom está inativo ou esgotado.'
        })

    clientes_permitidos = cupom.cliente.all()
    if clientes_permitidos.exists() and not clientes_permitidos.filter(pk=request.user.perfil.pk).exists():
        return JsonResponse({
            'status': 'warning',
            'title': 'Cupom exclusivo',
            'message': 'Este cupom não está disponível para a sua conta.'
        })

    itens_brinquedo = [
        item.item for item in carrinho.itens.all()
        if isinstance(item.item, Brinquedos)
    ]
    if cupom.brinquedo_id and not any(item.pk == cupom.brinquedo_id for item in itens_brinquedo):
        return JsonResponse({
            'status': 'warning',
            'title': 'Produto não elegível',
            'message': 'Adicione o produto vinculado a este cupom ao carrinho.'
        })
    if cupom.categoria_id and not any(
        item.categorias_brinquedos.filter(pk=cupom.categoria_id).exists()
        for item in itens_brinquedo
    ):
        return JsonResponse({
            'status': 'warning',
            'title': 'Categoria não elegível',
            'message': 'Este cupom não se aplica aos produtos do carrinho.'
        })

    # 🔮 FUTURA REGRA: cupom primeira compra
    if codigo.lower() == 'newuser10':
        ja_comprou = Pedido.objects.filter(cliente=request.user.perfil).exists()
        if ja_comprou:
            return JsonResponse({
                'status': 'warning',
                'title': 'Cupom indisponível',
                'message': 'Este cupom é válido apenas na primeira compra'
            })

    carrinho.cupom = cupom
    carrinho.mp_payment_id = None
    carrinho.save(update_fields=['cupom', 'mp_payment_id'])

    return JsonResponse({
        'status': 'success',
        'title': 'Cupom aplicado 🎉',
        'message': f'Você economizou {cupom.desconto_percentual}% com o cupom {cupom.codigo}'
    })


def salvar_cpf_carrinho(request):
    if request.method != "POST":
        return JsonResponse({"status": "erro"})

    try:
        data = json.loads(request.body)
        cpf = data.get("cpf")
    except:
        return JsonResponse({"status": "erro"})

    carrinho = Carrinho.objects.filter(cliente=request.user.perfil).first()

    if not carrinho:
        return JsonResponse({"status": "erro"})

    carrinho.cpf_cnpj = cpf
    carrinho.save(update_fields=["cpf_cnpj"])

    return JsonResponse({"status": "ok"})


class PaymentView(LoginRequiredMixin, View):

    def get(self, request, carrinho_id):
        carrinho = get_object_or_404(
            Carrinho.objects.select_related("cliente__user", "frete"),
            id=carrinho_id,
            cliente__user=request.user,
        )

        destino_pedidos = reverse("meus_pedidos") + "#pedidos"
        itens = carrinho.itens.select_related('content_type').all()

        # Um payment_id já consumido só representa este checkout quando o
        # carrinho também já foi esvaziado. Se há itens, trata-se de uma nova
        # solicitação e ela precisa receber uma cobrança própria.
        if carrinho.mp_payment_id:
            pedido_existente = Pedido.objects.filter(
                mp_payment_id=str(carrinho.mp_payment_id),
                cliente__user=request.user,
            ).first()
            if pedido_existente and not itens.exists():
                return redirect(destino_pedidos)
            if pedido_existente:
                carrinho.mp_payment_id = None
                carrinho.save(update_fields=["mp_payment_id"])

            # O webhook pode demorar ou falhar temporariamente. Ao voltar para
            # a página, consultamos o Mercado Pago e finalizamos localmente.
            elif settings.MP_ACCESS_TOKEN:
                try:
                    sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)
                    consulta = sdk.payment().get(carrinho.mp_payment_id)
                    payment = consulta.get("response") or {}

                    if payment.get("status") == "approved":
                        _finalizar_pagamento_aprovado(carrinho, payment)
                        return redirect(destino_pedidos)

                    if payment.get("status") in {
                        "rejected",
                        "cancelled",
                        "refunded",
                        "charged_back",
                    }:
                        carrinho.mp_payment_id = None
                        carrinho.save(update_fields=["mp_payment_id"])
                except PagamentoDivergenteError:
                    payment_logger.critical(
                        "Pagamento divergente ao reabrir checkout carrinho=%s",
                        carrinho.id,
                    )
                    carrinho.mp_payment_id = None
                    carrinho.save(update_fields=["mp_payment_id"])
                except Exception:
                    payment_logger.exception(
                        "Falha ao retomar pagamento do carrinho %s",
                        carrinho.id,
                    )

        if not itens.exists():
            return redirect('carrinho')

        # ==========================
        # 🔹 CRIAR OU ATUALIZAR FRETE
        # ==========================
        # Se o carrinho for do tipo 'frete', garante que exista um objeto de Frete
        if carrinho.tipo_envio == 'frete':
            frete, created = Frete.objects.get_or_create(
                carrinho=carrinho,
                defaults={
                    'valor': Decimal("0.00"),
                    'cep': '',
                    'rua': '',
                    'bairro': '',
                    'cidade': '',
                    'estado': '',
                    'numero': '',
                }
            )
        else:
            frete = None  # não precisa criar se for retirada

        valor_frete = frete.valor if frete else Decimal("0.00")

        somente_pix = not request.user.is_authenticated or not itens.exists()

        context = {
            'carrinho': carrinho,
            'itens': itens,
            'carrinho_vazio': not itens.exists(),

            'total_bruto': carrinho.total_bruto,
            'valor_desconto': carrinho.valor_desconto,

            'frete': valor_frete,

            'total_liquido': carrinho.total_liquido,

            # ⭐ TOTAL FINAL COM FRETE
            'total_final': carrinho.total_final,

            'total_itens': itens.count(),
            'somente_pix': somente_pix,
            'mp_public_key': settings.MP_PUBLIC_KEY,
            'max_parcelas': 18 if carrinho.total_final > Decimal("20000.00") else 12,
        }

        return render(request, 'payment.html', context)


from decimal import Decimal
import uuid
from django.views.decorators.http import require_GET
from django.views.decorators.cache import never_cache

payment_logger = logging.getLogger("core.payment")


def _valor_monetario(valor):
    """Converte e fixa qualquer valor financeiro em duas casas decimais."""
    try:
        return Decimal(str(valor)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
    except (InvalidOperation, TypeError, ValueError):
        return None


def _assinatura_carrinho(carrinho):
    """
    Assinatura imutável do estado cobrado.

    Dois carrinhos com o mesmo total, mas itens diferentes, não podem
    compartilhar a mesma cobrança nem a mesma chave de idempotência.
    """
    itens = []
    queryset = (
        carrinho.itens
        .select_related("content_type")
        .order_by("content_type_id", "object_id", "id")
    )

    for item in queryset:
        preco_unitario = _valor_monetario(item.preco_unitario)
        subtotal = _valor_monetario(item.subtotal)
        if preco_unitario is None or subtotal is None:
            raise ValueError(
                f"Item {item.id} possui valor financeiro inválido."
            )

        itens.append({
            "content_type_id": item.content_type_id,
            "object_id": item.object_id,
            "quantidade": item.quantidade,
            "preco_unitario": f"{preco_unitario:.2f}",
            "subtotal": f"{subtotal:.2f}",
        })

    valor_frete = _valor_monetario(carrinho.valor_frete)
    total_final = _valor_monetario(carrinho.total_final)
    if valor_frete is None or total_final is None:
        raise ValueError("O carrinho possui total financeiro inválido.")

    dados = {
        "carrinho_id": carrinho.id,
        "itens": itens,
        "cupom_id": carrinho.cupom_id,
        "tipo_envio": carrinho.tipo_envio,
        "frete": f"{valor_frete:.2f}",
        "total_final": f"{total_final:.2f}",
    }

    serializado = json.dumps(
        dados,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serializado.encode("utf-8")).hexdigest()


def _pagamento_confere_com_carrinho(payment, carrinho, assinatura=None):
    payment_id = str(payment.get("id") or "")
    payment_id_atual = str(carrinho.mp_payment_id or "")
    valor_pago = _valor_monetario(payment.get("transaction_amount"))
    valor_esperado = _valor_monetario(carrinho.total_final)
    referencia = str(payment.get("external_reference") or "")
    metadata = payment.get("metadata") or {}
    assinatura_mp = metadata.get("cart_fingerprint")
    try:
        assinatura_atual = assinatura or _assinatura_carrinho(carrinho)
    except ValueError:
        payment_logger.exception(
            "Não foi possível assinar o carrinho %s.",
            carrinho.id,
        )
        return False

    return (
            bool(payment_id)
            and (not payment_id_atual or payment_id == payment_id_atual)
            and valor_pago is not None
            and valor_esperado is not None
            and valor_pago == valor_esperado
            and referencia == str(carrinho.id)
            and bool(assinatura_mp)
            and assinatura_mp == assinatura_atual
    )


def _carrinho_pagamento_do_usuario(request, carrinho_id):
    """Retorna somente um carrinho pertencente ao usuário autenticado."""
    return (
        Carrinho.objects
        .select_related("cliente__user", "frete")
        .prefetch_related("itens")
        .filter(id=carrinho_id, cliente__user=request.user)
        .first()
    )


def _mp_request_options(chave):
    options = mercadopago.config.RequestOptions()
    options.custom_headers = {"x-idempotency-key": str(chave)}
    return options


def _cancelar_pagamento_pendente_mp(sdk, payment_id):
    """
    Cancela uma cobrança ainda pendente antes de abrir outro meio de
    pagamento para o mesmo carrinho.
    """
    consulta = sdk.payment().get(str(payment_id))
    payment = consulta.get("response") or {}
    status = payment.get("status")

    if status == "approved":
        return "approved", payment

    if status not in {"pending", "in_process", "authorized"}:
        return status or "unknown", payment

    chave = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"lazersport:cancel:{payment_id}",
    )
    resposta = sdk.payment().update(
        str(payment_id),
        {"status": "cancelled"},
        _mp_request_options(chave),
    )
    payment_cancelado = resposta.get("response") or {}
    return payment_cancelado.get("status") or "unknown", payment_cancelado


def _mp_error_message(payment):
    causa = (payment.get("cause") or [{}])[0]
    return (
            causa.get("description")
            or causa.get("code")
            or payment.get("message")
            or payment.get("error")
            or "Mercado Pago recusou a solicitação."
    )


def _dados_pix(payment):
    transaction_data = (
        payment.get("point_of_interaction", {})
        .get("transaction_data", {})
    )
    return {
        "qr_code": transaction_data.get("qr_code_base64"),
        "pix_copia_cola": transaction_data.get("qr_code"),
        "ticket_url": transaction_data.get("ticket_url"),
    }


def _forma_pagamento_mp(payment):
    payment_type = payment.get("payment_type_id")
    if payment_type == "credit_card":
        return "credito"
    if payment_type == "debit_card":
        return "debito"
    return "pix"


class PagamentoDivergenteError(Exception):
    """A cobrança recebida não representa o estado atual do carrinho."""


def _url_meus_pedidos():
    return reverse("meus_pedidos") + "#pedidos"


def _finalizar_pagamento_aprovado(carrinho, payment):
    """
    Cria exatamente um pedido para um pagamento aprovado.

    O bloqueio pessimista no Carrinho serializa webhook, polling e retorno à
    página. Se duas confirmações chegarem juntas, a segunda encontra o pedido
    criado pela primeira e apenas o reutiliza.
    """
    payment_id = str(payment.get("id") or "")
    if not payment_id or payment.get("status") != "approved":
        raise PagamentoDivergenteError(
            "O pagamento ainda não está aprovado."
        )

    with transaction.atomic():
        carrinho_bloqueado = (
            Carrinho.objects
            .select_for_update()
            .get(pk=carrinho.pk)
        )

        # IMPORTANTE:
        # Não combine select_for_update() com select_related("frete").
        # Frete é uma relação opcional e gera LEFT OUTER JOIN; no PostgreSQL,
        # a parte anulável desse JOIN não pode receber FOR UPDATE. O carrinho
        # é bloqueado sozinho e as relações são carregadas dentro da mesma
        # transação, sob o bloqueio do objeto principal.

        # A confirmação precisa pertencer exatamente à cobrança atualmente
        # vinculada ao carrinho. Nunca aceita um pagamento antigo do mesmo
        # usuário, carrinho ou valor.
        payment_id_atual = str(carrinho_bloqueado.mp_payment_id or "")
        if not payment_id_atual or payment_id != payment_id_atual:
            raise PagamentoDivergenteError(
                "O pagamento não pertence à solicitação atual."
            )

        # Idempotência local: o mesmo payment_id nunca cria outro pedido.
        pedido_existente = (
            Pedido.objects
            .select_for_update()
            .filter(mp_payment_id=payment_id)
            .first()
        )
        if pedido_existente:
            return pedido_existente, False

        if not carrinho_bloqueado.itens.exists():
            raise PagamentoDivergenteError(
                "O carrinho não possui itens para gerar o pedido."
            )

        if not _pagamento_confere_com_carrinho(
                payment,
                carrinho_bloqueado,
        ):
            raise PagamentoDivergenteError(
                "O valor ou os itens pagos não correspondem ao carrinho."
            )

        frete = getattr(carrinho_bloqueado, "frete", None)
        cupom = carrinho_bloqueado.cupom
        valor_frete = _valor_monetario(
            carrinho_bloqueado.valor_frete
        ) or Decimal("0.00")

        pedido = Pedido.objects.create(
            cliente=carrinho_bloqueado.cliente,
            carrinho_origem=carrinho_bloqueado,
            status="pago",
            forma_pagamento=_forma_pagamento_mp(payment),
            total_bruto=carrinho_bloqueado.total_bruto,
            valor_desconto=carrinho_bloqueado.valor_desconto,
            total_liquido=carrinho_bloqueado.total_liquido,
            valor_frete=valor_frete,
            total_final=carrinho_bloqueado.total_final,
            cep=frete.cep if frete else None,
            rua=frete.rua if frete else None,
            bairro=frete.bairro if frete else None,
            cidade=frete.cidade if frete else None,
            numero=frete.numero if frete else None,
            cupom_codigo=cupom.codigo if cupom else None,
            cupom_percentual=(
                cupom.desconto_percentual if cupom else None
            ),
            mp_payment_id=payment_id,
            mp_status="approved",
        )

        itens_pedido = []
        for item in carrinho_bloqueado.itens.all():
            itens_pedido.append(
                ItemPedido(
                    pedido=pedido,
                    content_type=item.content_type,
                    object_id=item.object_id,
                    nome_item=(
                        str(item.item)
                        if item.item
                        else "Produto removido"
                    ),
                    tipo_item=item.content_type.model,
                    preco_unitario=(
                            _valor_monetario(item.preco_unitario)
                            or Decimal("0.00")
                    ),
                    quantidade=item.quantidade,
                    subtotal=(
                            _valor_monetario(item.subtotal)
                            or Decimal("0.00")
                    ),
                )
            )
        ItemPedido.objects.bulk_create(itens_pedido)

        # Mantém o payment_id como recibo do último checkout. Ao adicionar
        # qualquer novo item, _invalidar_pagamento_pendente o remove.
        carrinho_bloqueado.itens.all().delete()
        carrinho_bloqueado.cupom = None
        carrinho_bloqueado.mp_payment_id = payment_id
        carrinho_bloqueado.save(
            update_fields=["cupom", "mp_payment_id"]
        )

        return pedido, True


@login_required
@require_GET
@never_cache
def gerar_pix(request):
    carrinho_id = request.GET.get("carrinho_id")
    carrinho = _carrinho_pagamento_do_usuario(request, carrinho_id)

    if not carrinho:
        return JsonResponse(
            {"erro": "Carrinho inválido ou sem permissão."},
            status=404,
        )

    if carrinho.mp_payment_id:
        pedido_existente = Pedido.objects.filter(
            mp_payment_id=str(carrinho.mp_payment_id),
            cliente__user=request.user,
        ).first()
        if pedido_existente and not carrinho.itens.exists():
            return JsonResponse({
                "pago": True,
                "pedido_id": pedido_existente.id,
                "redirect_url": _url_meus_pedidos(),
            })
        if pedido_existente:
            carrinho.mp_payment_id = None
            carrinho.save(update_fields=["mp_payment_id"])

    if not carrinho.itens.exists():
        return JsonResponse(
            {"erro": "O carrinho está vazio."},
            status=400,
        )

    if not settings.MP_ACCESS_TOKEN:
        payment_logger.error("MP_ACCESS_TOKEN não configurado")
        return JsonResponse(
            {"erro": "Pagamento indisponível. Credencial não configurada."},
            status=503,
        )

    payer_email = (request.user.email or "").strip()
    if not payer_email:
        return JsonResponse(
            {"erro": "Cadastre um e-mail válido no seu perfil para pagar."},
            status=400,
        )

    sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)
    total_final = _valor_monetario(carrinho.total_final)
    if total_final is None or total_final <= Decimal("0.00"):
        return JsonResponse(
            {"erro": "O total do carrinho é inválido para pagamento."},
            status=400,
        )

    try:
        assinatura = _assinatura_carrinho(carrinho)
    except ValueError as exc:
        payment_logger.exception(
            "Carrinho %s contém valor inválido.",
            carrinho.id,
        )
        return JsonResponse({"erro": str(exc)}, status=400)
    pagamento_anterior_id = carrinho.mp_payment_id

    # Reutiliza um Pix ainda pendente para não criar cobranças duplicadas
    # quando a página é atualizada, mas somente se valor, referência e todos
    # os itens forem exatamente os mesmos.
    if carrinho.mp_payment_id:
        try:
            consulta = sdk.payment().get(carrinho.mp_payment_id)
            existente = consulta.get("response") or {}
            pix_existente = _dados_pix(existente)

            if existente.get("status") == "approved":
                pedido, _ = _finalizar_pagamento_aprovado(
                    carrinho,
                    existente,
                )
                return JsonResponse({
                    "pago": True,
                    "pedido_id": pedido.id,
                    "redirect_url": _url_meus_pedidos(),
                })

            if (
                    existente.get("status")
                    in {"pending", "in_process", "authorized"}
                    and _pagamento_confere_com_carrinho(
                existente,
                carrinho,
                assinatura,
            )
                    and not (
                    pix_existente["qr_code"]
                    and pix_existente["pix_copia_cola"]
            )
            ):
                return JsonResponse(
                    {
                        "erro": "Já existe outro pagamento em andamento.",
                        "detalhe": (
                            "Aguarde a conclusão do pagamento atual antes "
                            "de gerar um novo Pix."
                        ),
                    },
                    status=409,
                )

            if (
                    existente.get("status") in {"pending", "in_process"}
                    and _pagamento_confere_com_carrinho(
                existente,
                carrinho,
                assinatura,
            )
                    and pix_existente["qr_code"]
                    and pix_existente["pix_copia_cola"]
            ):
                return JsonResponse({
                    **pix_existente,
                    "payment_id": existente.get("id"),
                    "status": existente.get("status"),
                    "valor": (
                        f"{_valor_monetario(existente.get('transaction_amount')):.2f}"
                    ),
                })

            payment_logger.warning(
                "Pix antigo descartado carrinho=%s payment=%s "
                "valor_mp=%s valor_atual=%s",
                carrinho.id,
                existente.get("id"),
                existente.get("transaction_amount"),
                total_final,
            )
        except PagamentoDivergenteError as exc:
            payment_logger.critical(
                "Pix aprovado divergente carrinho=%s payment=%s",
                carrinho.id,
                carrinho.mp_payment_id,
            )
            return JsonResponse(
                {
                    "erro": "Pagamento aprovado com divergência.",
                    "detalhe": str(exc),
                },
                status=409,
            )
        except Exception:
            payment_logger.exception(
                "Falha ao consultar Pix anterior do carrinho %s",
                carrinho.id,
            )

        carrinho.mp_payment_id = None
        carrinho.save(update_fields=["mp_payment_id"])

    payment_data = {
        "transaction_amount": float(total_final),
        "description": f"Lazer & Sport - Carrinho #{carrinho.id}",
        "payment_method_id": "pix",
        "external_reference": str(carrinho.id),
        "notification_url": request.build_absolute_uri(reverse("webhook_mp")),
        "payer": {"email": payer_email},
        "metadata": {
            "cart_fingerprint": assinatura,
            "cart_total": f"{total_final:.2f}",
        },
    }
    idempotency_key = uuid.uuid5(
        uuid.NAMESPACE_URL,
        (
            f"lazersport:pix:{carrinho.id}:{assinatura}:"
            f"{payer_email}:{pagamento_anterior_id or 'novo'}"
        ),
    )

    try:
        response = sdk.payment().create(
            payment_data,
            _mp_request_options(idempotency_key),
        )
    except Exception:
        payment_logger.exception(
            "Erro de comunicação ao criar Pix do carrinho %s",
            carrinho.id,
        )
        return JsonResponse(
            {"erro": "Não foi possível comunicar com o Mercado Pago."},
            status=502,
        )

    payment = response.get("response") or {}
    status_code = int(response.get("status") or 500)
    pix = _dados_pix(payment)
    pagamento_confere = (
            bool(payment.get("id"))
            and _pagamento_confere_com_carrinho(
        payment,
        carrinho,
        assinatura,
    )
    )

    if (
            status_code in {200, 201}
            and payment.get("id")
            and not pagamento_confere
    ):
        valor_retornado = _valor_monetario(
            payment.get("transaction_amount")
        )
        payment_logger.critical(
            "Mercado Pago criou Pix com divergência: "
            "carrinho=%s esperado=%s retornado=%s payment=%s",
            carrinho.id,
            total_final,
            valor_retornado,
            payment.get("id"),
        )
        return JsonResponse(
            {
                "erro": "Cobrança bloqueada por divergência de valor.",
                "detalhe": (
                    f"O pedido vale R$ {total_final:.2f}, mas o "
                    f"Mercado Pago retornou R$ "
                    f"{(valor_retornado or Decimal('0.00')):.2f}."
                ),
            },
            status=409,
        )

    if (
            status_code not in {200, 201}
            or not payment.get("id")
            or not pagamento_confere
            or not pix["qr_code"]
            or not pix["pix_copia_cola"]
    ):
        payment_logger.error(
            "Mercado Pago recusou Pix carrinho=%s http=%s resposta=%r",
            carrinho.id,
            status_code,
            payment,
        )
        return JsonResponse(
            {
                "erro": "Não foi possível gerar o Pix.",
                "detalhe": _mp_error_message(payment),
            },
            status=400 if status_code < 500 else 502,
        )

    carrinho.mp_payment_id = str(payment["id"])
    carrinho.save(update_fields=["mp_payment_id"])

    return JsonResponse({
        **pix,
        "payment_id": payment["id"],
        "status": payment.get("status"),
        "valor": (
            f"{_valor_monetario(payment.get('transaction_amount')):.2f}"
        ),
    })


from django.db import transaction
from django.views.decorators.http import require_GET
import json
import hmac
import hashlib
import os
import mercadopago

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction

from .models import Carrinho, Pedido, ItemPedido


@csrf_exempt
def webhook_mercadopago(request):
    if request.method != "POST":
        return HttpResponse(status=200)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponse(status=200)

    if data.get("type") != "payment":
        return HttpResponse(status=200)

    payment_id = data.get("data", {}).get("id")
    if not payment_id:
        return HttpResponse(status=200)

    sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)
    payment = sdk.payment().get(payment_id)["response"]

    if payment.get("status") != "approved":
        return HttpResponse(status=200)

    carrinho_id = payment.get("external_reference")
    if not carrinho_id:
        return HttpResponse(status=200)

    carrinho = Carrinho.objects.filter(id=carrinho_id).first()
    if not carrinho:
        return HttpResponse(status=200)

    try:
        _finalizar_pagamento_aprovado(carrinho, payment)
    except PagamentoDivergenteError:
        payment_logger.critical(
            "Webhook ignorado por divergência de cobrança: "
            "carrinho=%s payment=%s valor_mp=%s valor_atual=%s",
            carrinho.id,
            payment_id,
            payment.get("transaction_amount"),
            carrinho.total_final,
        )
        return HttpResponse(status=200)

    return HttpResponse(status=200)


from django.http import JsonResponse
from django.db import transaction
import mercadopago


@login_required
@require_GET
@never_cache
def verificar_pagamento(request):
    carrinho_id = request.GET.get("carrinho_id")
    if not carrinho_id:
        return JsonResponse({
            "pago": False,
            "consulta_ok": False,
            "status": "invalid_request",
            "mensagem": "Carrinho não informado.",
        }, status=400)

    carrinho = _carrinho_pagamento_do_usuario(request, carrinho_id)
    if not carrinho:
        return JsonResponse({
            "pago": False,
            "consulta_ok": False,
            "status": "not_found",
            "mensagem": "Carrinho não encontrado.",
        }, status=404)

    if not carrinho.mp_payment_id:
        return JsonResponse({
            "pago": False,
            "consulta_ok": True,
            "status": "waiting_payment",
            "mensagem": "Aguardando a criação da cobrança.",
        })

    pedido_existente = Pedido.objects.filter(
        mp_payment_id=str(carrinho.mp_payment_id),
        cliente__user=request.user,
    ).first()
    if pedido_existente and not carrinho.itens.exists():
        return JsonResponse({
            "pago": True,
            "consulta_ok": True,
            "status": "approved",
            "pedido_id": pedido_existente.id,
            "redirect_url": _url_meus_pedidos(),
        })
    if pedido_existente:
        carrinho.mp_payment_id = None
        carrinho.save(update_fields=["mp_payment_id"])
        return JsonResponse({
            "pago": False,
            "consulta_ok": True,
            "status": "stale_payment",
            "mensagem": "Nova solicitação detectada. Gerando uma cobrança exclusiva.",
        })

    try:
        if not settings.MP_ACCESS_TOKEN:
            raise RuntimeError("MP_ACCESS_TOKEN não configurado.")

        sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)
        payment_info = sdk.payment().get(carrinho.mp_payment_id)
        payment = payment_info.get("response") or {}

    except Exception:
        payment_logger.exception(
            "Falha ao consultar status carrinho=%s payment=%s",
            carrinho.id,
            carrinho.mp_payment_id,
        )
        return JsonResponse({
            "pago": False,
            "consulta_ok": False,
            "status": "temporarily_unavailable",
            "mensagem": (
                "Não foi possível consultar o pagamento agora. "
                "A verificação continuará automaticamente."
            ),
        })

    status_pagamento = payment.get("status")
    if status_pagamento != "approved":
        return JsonResponse({
            "pago": False,
            "consulta_ok": True,
            "status": status_pagamento or "unknown",
            "status_detail": payment.get("status_detail"),
            "mensagem": (
                "Pagamento recebido e em processamento."
                if status_pagamento in {"in_process", "authorized"}
                else "Aguardando o pagamento do Pix."
                if status_pagamento == "pending"
                else "Consultando o status do pagamento."
            ),
        })

    try:
        pedido, _ = _finalizar_pagamento_aprovado(carrinho, payment)
    except PagamentoDivergenteError as exc:
        payment_logger.critical(
            "Pagamento aprovado com dados divergentes: "
            "carrinho=%s payment=%s valor_mp=%s valor_atual=%s",
            carrinho.id,
            carrinho.mp_payment_id,
            payment.get("transaction_amount"),
            carrinho.total_final,
        )
        return JsonResponse({
            "pago": False,
            "consulta_ok": True,
            "status": "payment_mismatch",
            "erro": str(exc),
        }, status=409)
    except Exception:
        # Uma indisponibilidade transitória do banco não deve matar o polling
        # nem deixar o cliente preso com uma tela de erro. O pagamento segue
        # aprovado no provedor e a próxima consulta tenta criar o pedido de
        # forma idempotente novamente.
        payment_logger.exception(
            "Falha transitória ao finalizar pagamento: "
            "carrinho=%s payment=%s",
            carrinho.id,
            carrinho.mp_payment_id,
        )
        return JsonResponse({
            "pago": False,
            "consulta_ok": False,
            "status": "finalization_retry",
            "mensagem": (
                "Pagamento identificado. Estamos concluindo seu pedido "
                "e tentaremos novamente automaticamente."
            ),
        })

    return JsonResponse({
        "pago": True,
        "consulta_ok": True,
        "status": "approved",
        "pedido_id": pedido.id,
        "redirect_url": _url_meus_pedidos(),
    })


@login_required
@require_POST
def processar_cartao(request):
    """Processa apenas o token gerado pelo MercadoPago.js/Payment Brick."""
    try:
        dados = json.loads(request.body.decode("utf-8"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse(
            {"sucesso": False, "mensagem": "Dados de pagamento inválidos."},
            status=400,
        )

    carrinho = _carrinho_pagamento_do_usuario(
        request,
        dados.get("carrinho_id"),
    )
    if not carrinho or not carrinho.itens.exists():
        return JsonResponse(
            {"sucesso": False, "mensagem": "Carrinho inválido ou vazio."},
            status=404,
        )

    if not settings.MP_ACCESS_TOKEN:
        return JsonResponse(
            {"sucesso": False, "mensagem": "Credencial de pagamento ausente."},
            status=503,
        )

    # Nunca mantém Pix e cartão pendentes simultaneamente para o mesmo
    # carrinho. Antes de abrir uma cobrança de cartão, conclui ou cancela
    # a tentativa anterior.
    if carrinho.mp_payment_id:
        try:
            sdk_anterior = mercadopago.SDK(settings.MP_ACCESS_TOKEN)
            status_anterior, payment_anterior = (
                _cancelar_pagamento_pendente_mp(
                    sdk_anterior,
                    carrinho.mp_payment_id,
                )
            )

            if status_anterior == "approved":
                pedido, _ = _finalizar_pagamento_aprovado(
                    carrinho,
                    payment_anterior,
                )
                return JsonResponse({
                    "sucesso": True,
                    "aprovado": True,
                    "pedido_id": pedido.id,
                    "redirect_url": _url_meus_pedidos(),
                    "mensagem": "Pagamento já aprovado.",
                })

            if status_anterior not in {
                "cancelled",
                "rejected",
                "refunded",
                "charged_back",
            }:
                return JsonResponse(
                    {
                        "sucesso": False,
                        "mensagem": (
                            "Já existe um pagamento em andamento. "
                            "Não foi possível cancelá-lo com segurança."
                        ),
                    },
                    status=409,
                )

            carrinho.mp_payment_id = None
            carrinho.save(update_fields=["mp_payment_id"])
        except PagamentoDivergenteError as exc:
            return JsonResponse(
                {"sucesso": False, "mensagem": str(exc)},
                status=409,
            )
        except Exception:
            payment_logger.exception(
                "Falha ao encerrar cobrança anterior carrinho=%s",
                carrinho.id,
            )
            return JsonResponse(
                {
                    "sucesso": False,
                    "mensagem": (
                        "Não foi possível encerrar o pagamento anterior. "
                        "Tente novamente em alguns instantes."
                    ),
                },
                status=502,
            )

    token = dados.get("token")
    payment_method_id = dados.get("payment_method_id")
    payer = dados.get("payer") or {}
    payer_email = (payer.get("email") or request.user.email or "").strip()

    try:
        parcelas = int(dados.get("installments") or 1)
    except (TypeError, ValueError):
        parcelas = 0

    max_parcelas = 18 if carrinho.total_final > Decimal("20000.00") else 12
    if parcelas < 1 or parcelas > max_parcelas:
        return JsonResponse(
            {
                "sucesso": False,
                "mensagem": f"Escolha entre 1 e {max_parcelas} parcelas.",
            },
            status=400,
        )

    if not token or not payment_method_id or not payer_email:
        return JsonResponse(
            {
                "sucesso": False,
                "mensagem": "Preencha e valide todos os dados do cartão.",
            },
            status=400,
        )

    identification = payer.get("identification") or {}
    total_final = _valor_monetario(carrinho.total_final)
    if total_final is None or total_final <= Decimal("0.00"):
        return JsonResponse(
            {
                "sucesso": False,
                "mensagem": "O total do carrinho é inválido.",
            },
            status=400,
        )

    try:
        assinatura = _assinatura_carrinho(carrinho)
    except ValueError as exc:
        payment_logger.exception(
            "Carrinho %s contém valor inválido.",
            carrinho.id,
        )
        return JsonResponse(
            {"sucesso": False, "mensagem": str(exc)},
            status=400,
        )
    payment_data = {
        "transaction_amount": float(total_final),
        "token": token,
        "description": f"Lazer & Sport - Carrinho #{carrinho.id}",
        "installments": parcelas,
        "payment_method_id": payment_method_id,
        "external_reference": str(carrinho.id),
        "notification_url": request.build_absolute_uri(reverse("webhook_mp")),
        "payer": {
            "email": payer_email,
            "identification": {
                "type": identification.get("type") or "CPF",
                "number": identification.get("number") or "",
            },
        },
        "metadata": {
            "cart_fingerprint": assinatura,
            "cart_total": f"{total_final:.2f}",
        },
    }
    if dados.get("issuer_id"):
        payment_data["issuer_id"] = dados["issuer_id"]

    token_fingerprint = hashlib.sha256(token.encode("utf-8")).hexdigest()
    idempotency_key = uuid.uuid5(
        uuid.NAMESPACE_URL,
        (
            f"lazersport:card:{carrinho.id}:{assinatura}:"
            f"{total_final}:{token_fingerprint}"
        ),
    )

    try:
        sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)
        response = sdk.payment().create(
            payment_data,
            _mp_request_options(idempotency_key),
        )
    except Exception:
        payment_logger.exception(
            "Erro de comunicação ao pagar carrinho %s com cartão",
            carrinho.id,
        )
        return JsonResponse(
            {
                "sucesso": False,
                "mensagem": "Não foi possível comunicar com o Mercado Pago.",
            },
            status=502,
        )

    payment = response.get("response") or {}
    status_code = int(response.get("status") or 500)
    payment_id = payment.get("id")
    pagamento_confere = (
            bool(payment_id)
            and _pagamento_confere_com_carrinho(
        payment,
        carrinho,
        assinatura,
    )
    )

    if (
            status_code in {200, 201}
            and payment_id
            and not pagamento_confere
    ):
        valor_retornado = _valor_monetario(
            payment.get("transaction_amount")
        )
        payment_logger.critical(
            "Mercado Pago criou cartão com divergência: "
            "carrinho=%s esperado=%s retornado=%s payment=%s",
            carrinho.id,
            total_final,
            valor_retornado,
            payment_id,
        )
        return JsonResponse(
            {
                "sucesso": False,
                "mensagem": (
                    "Pagamento bloqueado porque o valor retornado não "
                    "corresponde ao pedido."
                ),
            },
            status=409,
        )

    if (
            status_code not in {200, 201}
            or not payment_id
            or not pagamento_confere
    ):
        payment_logger.error(
            "Mercado Pago recusou cartão carrinho=%s http=%s resposta=%r",
            carrinho.id,
            status_code,
            payment,
        )
        return JsonResponse(
            {
                "sucesso": False,
                "mensagem": _mp_error_message(payment),
            },
            status=400 if status_code < 500 else 502,
        )

    carrinho.mp_payment_id = str(payment_id)
    carrinho.save(update_fields=["mp_payment_id"])

    status_pagamento = payment.get("status")
    aprovado = status_pagamento == "approved"
    pendente = status_pagamento in {"pending", "in_process", "authorized"}
    pedido = None

    if aprovado:
        try:
            pedido, _ = _finalizar_pagamento_aprovado(
                carrinho,
                payment,
            )
        except PagamentoDivergenteError as exc:
            payment_logger.critical(
                "Cartão aprovado divergente carrinho=%s payment=%s",
                carrinho.id,
                payment_id,
            )
            return JsonResponse(
                {
                    "sucesso": False,
                    "aprovado": False,
                    "mensagem": str(exc),
                },
                status=409,
            )

    return JsonResponse(
        {
            "sucesso": aprovado or pendente,
            "aprovado": aprovado,
            "pendente": pendente,
            "payment_id": payment_id,
            "pedido_id": pedido.id if pedido else None,
            "status": status_pagamento,
            "status_detail": payment.get("status_detail"),
            "redirect_url": _url_meus_pedidos() if aprovado else None,
            "mensagem": (
                "Pagamento aprovado."
                if aprovado
                else "Pagamento em análise."
                if pendente
                else "Pagamento recusado."
            ),
        },
        status=200 if aprovado or pendente else 402,
    )


@login_required
@require_POST
def criar_pedido_pix(request):
    return JsonResponse({
        "success": False,
        "error": (
            "Rota antiga desativada. Use o checkout seguro do Mercado Pago."
        ),
    }, status=410)


def criar_pedido_do_carrinho(carrinho):
    with transaction.atomic():
        pedido = Pedido.objects.create(
            cliente=carrinho.cliente,
            total_bruto=carrinho.total_bruto,
            valor_desconto=carrinho.valor_desconto,
            total_liquido=carrinho.total_liquido,
            cupom_codigo=carrinho.cupom.codigo if carrinho.cupom else None,
            cupom_percentual=carrinho.cupom.desconto_percentual if carrinho.cupom else None,
        )

        for item in carrinho.itens.all():
            ItemPedido.objects.create(
                pedido=pedido,
                content_type=item.content_type,
                object_id=item.object_id,
                nome_item=str(item.item),
                tipo_item=item.content_type.model,
                preco_unitario=item.preco_unitario,
                quantidade=item.quantidade,
                subtotal=item.subtotal
            )

        # opcional: limpar carrinho
        carrinho.itens.all().delete()
        carrinho.cupom = None
        carrinho.save()

        return pedido


@login_required
@require_POST
def confirmar_cartao(request, carrinho_id):
    return JsonResponse({
        "success": False,
        "error": (
            "Rota antiga desativada. O cartão deve ser confirmado pelo "
            "Mercado Pago."
        ),
    }, status=410)


from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin


# -23.453403648643707, -46.66151816239609  -23.472997309863196, -46.63041992925325
class MeusPedidosView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        perfil = getattr(request.user, 'perfil', None)

        if not perfil:
            messages.error(request, "Perfil não encontrado.")
            return redirect('home')

        pedidos = (
            Pedido.objects
            .filter(cliente=perfil)
            .prefetch_related('itens')
            .order_by('-criacao')
        )

        return render(request, 'meus_pedidos.html', {
            'pedidos': pedidos,
        })


from django.shortcuts import redirect
from django.urls import reverse


def redirecionar_loja(request, *args, **kwargs):
    return redirect(reverse('brinquedos') + '#grid-cards')


def redirecionar_lancamentos(request):
    return redirect(reverse('brinquedos') + '#grid-cards')


def redirecionar_showroom(request):
    return redirect(reverse('eventos') + '#todos-eventos')


def redirecionar_contato(request):
    return redirect(reverse('home') + '#contato')


def redirecionar_categoria_brinquedos(request):
    return redirect(reverse('brinquedo_detalhe', args=[12]))


def redirecionar_categoria_aventura(request):
    return redirect(reverse('categoria_detalhe', args=[12]))


# views.py
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
import json


@login_required
@require_POST
def atualizar_tipo_envio(request, carrinho_id):
    carrinho = get_object_or_404(
        Carrinho,
        id=carrinho_id,
        cliente__user=request.user,
    )

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse(
            {"status": "erro", "message": "Dados inválidos."},
            status=400,
        )

    tipo = data.get("tipo_envio")
    if tipo not in dict(Carrinho.TIPO_ENVIO):
        return JsonResponse(
            {"status": "erro", "message": "Tipo inválido."},
            status=400,
        )

    carrinho.tipo_envio = tipo
    carrinho.mp_payment_id = None
    carrinho.save(update_fields=["tipo_envio", "mp_payment_id"])

    # Se for retirada, remove frete existente.
    if tipo == "retirada":
        Frete.objects.filter(carrinho=carrinho).delete()

    return JsonResponse({
        "status": "ok",
        "total_final": float(carrinho.total_final),
    })


class PedidosParaImpressaoAPI(View):
    def get(self, request):
        pedidos = (
            Pedido.objects
            .filter(impresso=False)
            .select_related("cliente__user", "carrinho_origem__cliente__user", "carrinho_origem__frete")
            .prefetch_related("itens")
            .order_by("criacao")
        )

        data = []

        for pedido in pedidos:
            # Endereço
            endereco_data = None
            if pedido.carrinho_origem:
                frete_obj = getattr(pedido.carrinho_origem, "frete", None)
                if frete_obj:
                    endereco_data = {
                        "rua": getattr(frete_obj, "rua", ""),
                        "numero": getattr(frete_obj, "numero", ""),
                        "bairro": getattr(frete_obj, "bairro", ""),
                        "cidade": getattr(frete_obj, "cidade", ""),
                        "cep": getattr(frete_obj, "cep", "")
                    }

            # Itens
            itens = []
            for item in pedido.itens.all():
                try:
                    nome_item = getattr(item, "item", None)
                    if nome_item:
                        nome_item = str(nome_item)
                    else:
                        nome_item = getattr(item, "nome_item", "Item desconhecido")
                except:
                    nome_item = "Item desconhecido"

                itens.append({
                    "nome": getattr(item, "nome_item", "Item desconhecido"),
                    "quantidade": getattr(item, "quantidade", 0),
                    "preco": float(getattr(item, "preco_unitario", 0) or 0),
                })

            # Cliente: tenta pegar do pedido, senão do carrinho, senão N/A
            cliente = pedido.cliente
            if not cliente and pedido.carrinho_origem:
                cliente = getattr(pedido.carrinho_origem, "cliente", None)

            nome_cliente = getattr(cliente, "nome_completo", None) or (
                getattr(getattr(cliente, "user", None), "username", "N/A")
            )

            telefone_cliente = getattr(cliente, "telefone", "N/A")
            subtotal = getattr(pedido, "total_bruto", 0) or 0
            total_liquido = getattr(pedido, 'total_liquido')
            frete = pedido.valor_frete or (
                pedido.carrinho_origem.valor_frete if pedido.carrinho_origem else 0
            )
            total = getattr(pedido, "total_final", 0) or 0

            data.append({
                "id": pedido.id,
                "cliente": nome_cliente,
                "telefone": telefone_cliente,

                "subtotal": float(subtotal),
                "total_liquido": float(total_liquido),
                "frete_valor": float(frete),
                "total": float(total),

                "tipo_envio": getattr(getattr(pedido, "carrinho_origem", None), "tipo_envio", "frete"),
                "forma_pagamento": pedido.get_forma_pagamento_display() if pedido.forma_pagamento else "N/A",

                "endereco": endereco_data,
                "itens": itens
            })

        return JsonResponse({"pedidos": data})


from django.views.decorators.csrf import csrf_exempt


@method_decorator(csrf_exempt, name='dispatch')
class MarcarPedidoImpressoAPI(View):

    def post(self, request, pedido_id):

        try:

            pedido = Pedido.objects.get(id=pedido_id)

            pedido.impresso = True
            pedido.save(update_fields=["impresso"])

            return JsonResponse({"ok": True})

        except Pedido.DoesNotExist:
            return JsonResponse({"erro": "Pedido não encontrado"}, status=404)


# No Django (Produção)
from django.http import JsonResponse
from django.contrib.auth import authenticate
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt  # Isento para permitir o POST do seu Flask local
def verify_auth_api(request):
    u = request.POST.get('username')
    p = request.POST.get('password')
    key = request.POST.get('app_key')

    # Proteção simples para garantir que só o seu Flask chame esta rota
    if key != 'SUA_CHAVE_DE_SEGURANCA_ENTRE_APPS':
        return JsonResponse({'valid': False}, status=403)

    user = authenticate(username=u, password=p)
    if user:
        return JsonResponse({
            'valid': True,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser
        })
    return JsonResponse({'valid': False}, status=401)


def robots_txt(request):
    """robots.txt do site principal -- antes não existia rota nenhuma
    pra esse caminho, e o Googlebot recebia 500 ao tentar acessá-lo."""
    linhas = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /adm/",
        "Disallow: /carrinho/",
        "Disallow: /perfil/",
        "Disallow: /meus-pedidos/",
        "Disallow: /pagamento/",
        "Disallow: /processar_cartao/",
        "Disallow: /api/",
        "Disallow: /login/",
        "Disallow: /registrar/",
        "Disallow: /acesso-negado/",
        "Disallow: /*?filter_cat=",
        "Disallow: /*&filter_cat=",
        "Disallow: /*?shop_view=",
        "Disallow: /*&shop_view=",
        "Disallow: /*?column=",
        "Disallow: /*&column=",
        "Crawl-delay: 10",
        "",
        "Sitemap: https://www.lazersport.com.br/sitemap.xml",
    ]
    return HttpResponse("\n".join(linhas), content_type="text/plain")


from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from .models import Brinquedos, Combos

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from .models import Brinquedos, Combos


class ComboAdminView(AdminOnlyMixin, View):
    """
    Única view da administração de combos.

    GET:
        Lista, pesquisa e filtra os combos.

    POST:
        Cria, edita ou exclui conforme o campo "acao" enviado pelo
        formulário da própria página.
    """

    template_name = "gestao/combos_adm.html"

    def get_queryset(self):
        queryset = (
            Combos.objects
            .prefetch_related("brinquedos")
            .order_by("-id")
        )

        busca = self.request.GET.get("q", "").strip()
        status = self.request.GET.get("status", "todos").strip().lower()

        if busca:
            queryset = queryset.filter(
                Q(descricao__icontains=busca)
                | Q(brinquedos__nome_brinquedo__icontains=busca)
            ).distinct()

        if status == "ativos":
            queryset = queryset.filter(ativo=True)
        elif status == "inativos":
            queryset = queryset.filter(ativo=False)

        return queryset

    def get(self, request, *args, **kwargs):
        todos = Combos.objects.all()

        context = {
            "combos": self.get_queryset(),
            "brinquedos": (
                Brinquedos.objects
                .filter(ativo=True)
                .order_by("nome_brinquedo")
            ),
            "busca": request.GET.get("q", "").strip(),
            "status_atual": request.GET.get("status", "todos"),
            "total_combos": todos.count(),
            "total_ativos": todos.filter(ativo=True).count(),
            "total_inativos": todos.filter(ativo=False).count(),
        }
        return render(request, self.template_name, context)

    @staticmethod
    def _converter_valor(valor):
        """
        Aceita 10990.00, 10990,00 e 10.990,00.
        """
        valor = (valor or "").strip().replace("R$", "").replace(" ", "")

        if not valor:
            raise InvalidOperation

        if "," in valor:
            valor = valor.replace(".", "").replace(",", ".")
        elif valor.count(".") > 1:
            partes = valor.split(".")
            valor = "".join(partes[:-1]) + "." + partes[-1]

        valor_decimal = Decimal(valor)
        if valor_decimal <= 0:
            raise InvalidOperation

        return valor_decimal.quantize(Decimal("0.01"))

    def post(self, request, *args, **kwargs):
        acao = request.POST.get("acao", "").strip().lower()

        if acao == "excluir":
            return self._excluir(request)

        if acao not in {"criar", "editar"}:
            messages.error(request, "Ação inválida.")
            return redirect("combos_admin")

        return self._salvar(request, acao)

    @transaction.atomic
    def _salvar(self, request, acao):
        combo_id = request.POST.get("combo_id")
        descricao = request.POST.get("descricao", "").strip()
        try:
            brinquedos_ids = list(
                dict.fromkeys(
                    int(item)
                    for item in request.POST.getlist("brinquedos")
                )
            )
        except (TypeError, ValueError):
            brinquedos_ids = []
        imagem = request.FILES.get("imagem_combo")
        ativo = request.POST.get("ativo") == "on"

        if acao == "editar":
            combo = get_object_or_404(Combos, pk=combo_id)
        else:
            combo = Combos()

        if not descricao:
            messages.error(request, "Informe a descrição do combo.")
            return redirect("combos_admin")

        if not brinquedos_ids:
            messages.error(
                request,
                "Selecione pelo menos um brinquedo para o combo.",
            )
            return redirect("combos_admin")

        brinquedos = Brinquedos.objects.filter(pk__in=brinquedos_ids)
        if brinquedos.count() != len(brinquedos_ids):
            messages.error(
                request,
                "Um dos brinquedos selecionados não foi encontrado.",
            )
            return redirect("combos_admin")

        try:
            valor_combo = self._converter_valor(
                request.POST.get("valor_combo")
            )
        except (InvalidOperation, TypeError, ValueError):
            messages.error(
                request,
                "Informe um valor válido, por exemplo: 10.990,00.",
            )
            return redirect("combos_admin")

        combo.descricao = descricao
        combo.valor_combo = valor_combo
        combo.ativo = ativo

        if imagem:
            combo.imagem_combo = imagem
        elif (
                acao == "editar"
                and request.POST.get("remover_imagem") == "on"
                and combo.imagem_combo
        ):
            combo.imagem_combo.delete(save=False)
            combo.imagem_combo = ""

        combo.save()
        combo.brinquedos.set(brinquedos)

        if acao == "criar":
            messages.success(request, "Combo criado com sucesso.")
        else:
            messages.success(request, "Combo atualizado com sucesso.")

        return redirect("combos_admin")

    @transaction.atomic
    def _excluir(self, request):
        combo_id = request.POST.get("combo_id")
        combo = get_object_or_404(Combos, pk=combo_id)

        if request.POST.get("confirmacao", "").strip().upper() != "EXCLUIR":
            messages.error(request, "Digite EXCLUIR para confirmar.")
            return redirect("combos_admin")

        try:
            combo.delete()
        except ProtectedError:
            messages.error(
                request,
                "Este combo possui registros vinculados e não pode "
                "ser excluído.",
            )
        else:
            messages.success(request, "Combo excluído com sucesso.")

        return redirect("combos_admin")


import unicodedata
from difflib import SequenceMatcher

from django.shortcuts import render
from django.urls import reverse
from django.views import View


def normalizar_texto_busca(valor):
    valor = str(valor or "").strip().lower()
    valor = unicodedata.normalize("NFKD", valor)
    valor = "".join(
        caractere
        for caractere in valor
        if not unicodedata.combining(caractere)
    )
    return " ".join(valor.split())


def calcular_similaridade(termo, *campos):
    termo = normalizar_texto_busca(termo)
    melhor_resultado = 0.0

    for campo in campos:
        texto = normalizar_texto_busca(campo)
        if not texto:
            continue

        if termo in texto or texto in termo:
            melhor_resultado = max(melhor_resultado, 1.0)
            continue

        melhor_resultado = max(
            melhor_resultado,
            SequenceMatcher(None, termo, texto).ratio(),
        )

        for palavra in texto.split():
            melhor_resultado = max(
                melhor_resultado,
                SequenceMatcher(None, termo, palavra).ratio(),
            )

    return melhor_resultado


class SearchView(View):
    template_name = "search.html"
    similaridade_minima = 0.60
    limite_resultados = 60

    def get(self, request):
        termo = request.GET.get("q", "").strip()[:100]
        resultados = []

        def adicionar_resultado(tipo, titulo, descricao, url, imagem=None, *campos):
            similaridade = calcular_similaridade(
                termo,
                titulo,
                descricao,
                *campos,
            )

            if similaridade < self.similaridade_minima:
                return

            resultados.append({
                "tipo": tipo,
                "titulo": titulo,
                "descricao": descricao,
                "url": url,
                "imagem": imagem,
                "similaridade": round(similaridade * 100),
            })

        if len(normalizar_texto_busca(termo)) >= 2:
            brinquedos = (
                Brinquedos.objects
                .filter(ativo=True)
                .prefetch_related("categorias_brinquedos", "tags")
            )

            for brinquedo in brinquedos:
                adicionar_resultado(
                    "Brinquedo",
                    brinquedo.nome_brinquedo,
                    brinquedo.descricao,
                    reverse("brinquedo_detalhe", args=[brinquedo.id]),
                    brinquedo.imagem_brinquedo,
                    *(categoria.nome_categoria for categoria in brinquedo.categorias_brinquedos.all()),
                    *(tag.nome_tags for tag in brinquedo.tags.all()),
                )

            pecas = (
                PecasReposicao.objects
                .filter(ativo=True)
                .prefetch_related("categoria_peca", "imagem_peca_reposicao")
            )

            for peca in pecas:
                imagem_principal = peca.imagem_principal
                adicionar_resultado(
                    "Peça de reposição",
                    peca.nome,
                    peca.descricao_peca,
                    reverse("reposicao_detalhe", args=[peca.id]),
                    imagem_principal.imagem if imagem_principal else None,
                    *(categoria.nome_categoria_peca for categoria in peca.categoria_peca.all()),
                )

            combos = Combos.objects.filter(ativo=True).prefetch_related("brinquedos")
            for combo in combos:
                adicionar_resultado(
                    "Combo",
                    combo.descricao,
                    "Combo especial de brinquedos Lazer & Sport.",
                    reverse("combo", args=[combo.id]),
                    combo.imagem_combo,
                    *(brinquedo.nome_brinquedo for brinquedo in combo.brinquedos.all()),
                )

            promocoes = Promocoes.objects.filter(ativo=True).select_related("brinquedos")
            for promocao in promocoes:
                adicionar_resultado(
                    "Promoção",
                    promocao.descricao,
                    promocao.brinquedos.nome_brinquedo,
                    reverse("promocao", args=[promocao.id]),
                    promocao.imagem_promocao,
                    promocao.brinquedos.descricao,
                )

            projetos = (
                Projetos.objects
                .select_related("brinquedo_projetado")
                .prefetch_related("brinquedo_projetado__imagens_brinquedo_projeto")
            )
            for projeto in projetos:
                brinquedo = projeto.brinquedo_projetado
                imagem = brinquedo.imagens_brinquedo_projeto.first() if brinquedo else None
                adicionar_resultado(
                    "Projeto",
                    projeto.titulo,
                    projeto.descricao,
                    reverse("projetos") + "#todos-projetos",
                    imagem.imagem if imagem else None,
                    brinquedo.nome_brinquedo_projeto if brinquedo else "",
                    brinquedo.descricao if brinquedo else "",
                )

            eventos = Eventos.objects.prefetch_related("imagens_evento", "brinquedos")
            for evento in eventos:
                imagem = evento.imagens_evento.first()
                adicionar_resultado(
                    "Evento",
                    evento.titulo,
                    evento.descricao,
                    reverse("eventos") + "#todos-eventos",
                    imagem.imagem if imagem else None,
                    *(brinquedo.nome_brinquedo for brinquedo in evento.brinquedos.all()),
                )

            for categoria in CategoriasBrinquedos.objects.filter(ativo=True):
                adicionar_resultado(
                    "Categoria",
                    categoria.nome_categoria,
                    "Categoria de brinquedos Lazer & Sport.",
                    reverse("categoria_detalhe", args=[categoria.id]),
                    categoria.imagem_categoria,
                )

            for estabelecimento in Estabelecimentos.objects.filter(ativo=True):
                adicionar_resultado(
                    "Estabelecimento",
                    estabelecimento.nome_estabelecimento,
                    "Brinquedos recomendados para este tipo de estabelecimento.",
                    reverse("estabelecimento_brinquedo", args=[estabelecimento.id]),
                    estabelecimento.imagem_estabelecimento,
                )

            resultados.sort(
                key=lambda resultado: (
                    -resultado["similaridade"],
                    resultado["titulo"].lower(),
                )
            )
            resultados = resultados[:self.limite_resultados]

        return render(request, self.template_name, {
            "termo": termo,
            "resultados": resultados,
            "total_resultados": len(resultados),
            "busca_realizada": bool(termo),
        })

