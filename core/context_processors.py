from .models import CategoriasBrinquedos

def categorias_globais(request):
    return {
        "categorias_header": CategoriasBrinquedos.objects.all().order_by("nome_categoria")
    }
