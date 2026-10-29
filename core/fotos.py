"""As fotos do site no tamanho que a tela usa, e não no original.

A foto que se cadastra chega com 3000 px e alguns MB. Num cartão que tem
300 px de largura na tela, isso é o site inteiro esperando um arquivo
que vai ser encolhido no próprio celular. O Cloudinary (onde as fotos
moram em produção) entrega a foto já reduzida e no formato mais leve que
o navegador aceita (WebP/AVIF) só de mudar o endereço: é o que
`reduzir_imagem` faz. Fora do Cloudinary (desenvolvimento) a URL volta
como está.
"""

def reduzir_imagem(url, largura=768):
    """A mesma foto do Cloudinary, com no máximo `largura` px de largura."""
    if not url or "res.cloudinary.com" not in url or "/upload/" not in url:
        return url
    antes, depois = url.split("/upload/", 1)
    if depois.startswith(("c_", "w_", "f_", "q_")):
        return url
    return f"{antes}/upload/c_limit,w_{int(largura)},f_auto,q_auto/{depois}"


def url_da_imagem(imagem):
    """A URL de um campo de imagem (ou de uma URL já pronta); "" se não houver."""
    if not imagem:
        return ""
    if isinstance(imagem, str):
        return imagem
    try:
        return imagem.url
    except Exception:
        # arquivo sem nome ou storage fora do ar: o cartão segue sem foto
        return ""
