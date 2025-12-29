from .models import CategoriasBrinquedos, Estabelecimentos

def categorias_globais(request):
    return {
        "categorias_header": CategoriasBrinquedos.objects.all().order_by("nome_categoria")
    }

def estabelecimentos_globais(request):
    return {
        "estabelecimentos_globais": Estabelecimentos.objects.all()
    }