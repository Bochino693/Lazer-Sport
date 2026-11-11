"""As fotos do site no tamanho que a tela usa, e não no original.

A foto que se cadastra chega com 3000 px e alguns MB. Num cartão que tem
300 px de largura na tela, isso é o site inteiro esperando um arquivo
que vai ser encolhido no próprio celular. O Cloudinary (onde as fotos
moram em produção) entrega a foto já reduzida e no formato mais leve que
o navegador aceita (WebP/AVIF) só de mudar o endereço: é o que
`reduzir_imagem` faz. Fora do Cloudinary (desenvolvimento) a URL volta
como está.

O ENDEREÇO DO CLOUDINARY É MONTADO UMA VEZ POR FOTO E POR PROCESSO.
Montar a URL não vai à rede, mas passa pela configuração inteira do SDK
(transformações, domínio, assinatura): ~30 µs por foto, medido no
LEIA-ME-V10, seção 63. A loja tem ~80 fotos, a Arena ~600 ao montar os
dados -- e a resposta só depende do nome do arquivo e da conta do
Cloudinary, que não mudam enquanto o processo vive. `url_da_imagem`
guarda o endereço já montado; o resto do armazenamento (o disco do
computador, o dos testes) continua perguntando ao storage a cada vez,
porque ali o endereço depende de `MEDIA_URL`.
"""

#: Endereços já montados: (classe do storage, tipo, conta, nome) -> URL.
_URLS = {}
#: Um teto folgado (o catálogo inteiro tem poucos milhares de fotos): sem
#: ele, um defeito que gerasse nomes novos sem fim viraria vazamento.
_LIMITE_DE_URLS = 20000


def reduzir_imagem(url, largura=768):
    """A mesma foto do Cloudinary, com no máximo `largura` px de largura."""
    if not url or "res.cloudinary.com" not in url or "/upload/" not in url:
        return url
    antes, depois = url.split("/upload/", 1)
    if depois.startswith(("c_", "w_", "f_", "q_")):
        return url
    return f"{antes}/upload/c_limit,w_{int(largura)},f_auto,q_auto/{depois}"


def _url_do_arquivo(imagem):
    storage = getattr(imagem, "storage", None)
    nome = getattr(imagem, "name", None)
    if not nome or storage is None or not type(storage).__module__.startswith("cloudinary_storage"):
        return imagem.url
    import cloudinary

    chave = (type(storage), getattr(storage, "RESOURCE_TYPE", ""), cloudinary.config().cloud_name, nome)
    url = _URLS.get(chave)
    if url is None:
        url = imagem.url
        if len(_URLS) < _LIMITE_DE_URLS:
            _URLS[chave] = url
    return url


def url_da_imagem(imagem):
    """A URL de um campo de imagem (ou de uma URL já pronta); "" se não houver."""
    if not imagem:
        return ""
    if isinstance(imagem, str):
        return imagem
    try:
        return _url_do_arquivo(imagem)
    except Exception:
        # arquivo sem nome ou storage fora do ar: o cartão segue sem foto
        return ""
