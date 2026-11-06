"""A descrição organizada da ficha de projetos e eventos (core/ficha_texto.py).

    {% load fichas %}
    {% with f=projeto.descricao|ficha %} ... {{ f.lead }} {{ f.secoes }} {{ f.fecho }}
    {{ projeto.descricao|resumo_ficha:160 }}
    {% with o3d=projeto.brinquedo_projetado|objeto_3d_do_projeto %} ... {{ o3d.url }} {{ o3d.produto }}
"""

from django import template

from ..ficha_texto import estruturar, resumo

register = template.Library()


@register.filter
def ficha(texto):
    return estruturar(texto)


@register.filter
def resumo_ficha(texto, limite=170):
    return resumo(texto, int(limite))


@register.filter
def objeto_3d_do_projeto(brinquedo_projetado):
    """O objeto 3D do projeto já trazido com ele (prefetch), ou None.

    Nunca consulta o banco: sem o prefetch (ou sem a tabela, antes da
    migração), a ficha segue só com as fotos -- em vez de cair.
    """
    if brinquedo_projetado is None:
        return None
    from ..models import BrinquedosProjeto

    if not BrinquedosProjeto.objeto_3d.is_cached(brinquedo_projetado):
        return None
    objeto = getattr(brinquedo_projetado, "objeto_3d", None)
    if objeto is None or not objeto.ativo:
        return None
    return objeto
