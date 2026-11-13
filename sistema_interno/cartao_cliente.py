"""O que o CARTÃO do cliente mostra a mais que a linha da tabela.

O pedido: "no modo card, centralize o conteúdo e se houver logo no cliente,
mostre a logo, tudo moderno e bem otimizado". O cartão da tela de Clientes
abre com o rosto do cadastro -- a logo, ou as iniciais do nome sobre uma cor
que é sempre a mesma para aquele nome -- e traz o contato como atalhos de
tocar (WhatsApp, ligar, e-mail).

Nada aqui vai ao banco: tudo sai do que a lista já carregou. A URL da logo é
conta local (ver core/fotos.py), e por isso o cartão não custa consulta
nenhuma a mais por cliente.
"""

from __future__ import annotations

import unicodedata
import zlib
from urllib.parse import quote

from core import fotos

from .validacoes import somente_digitos

#: A logo aparece num quadro de 84 px; pede-se o dobro para a tela de
#: celular (2x) não mostrar a logo borrada. É a versão reduzida do
#: Cloudinary (~5 KB), nunca o arquivo que a pessoa enviou.
LARGURA_DA_LOGO = 176

#: Quantas cores de avatar o tema oferece (`data-tom="1..6"`; quem diz qual
#: cor é cada tom é o CSS, com as famílias do tema: tangerina, magenta,
#: teal, verde, violeta e azul).
TONS = 6

#: Palavras que não contam para as iniciais: "Maria da Silva" é MS.
_PARTICULAS = frozenset(
    {"de", "da", "do", "das", "dos", "e", "di", "du", "del", "la", "le", "van", "von"}
)


def _sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(letra for letra in decomposto if not unicodedata.combining(letra))


def iniciais(nome: str) -> str:
    """As duas letras do avatar: a primeira das duas primeiras palavras.

    "Buffet Alegria Festas" vira BA, "Marina de Souza" vira MS, "João" vira
    J. Palavra que não começa por letra ou número ("&", "-") não conta.
    """
    palavras = []
    for palavra in (nome or "").split():
        palavra = palavra.strip("\"'()[]{}.,;:-–—&/\\")
        if not palavra or not palavra[0].isalnum():
            continue
        if palavra.lower() in _PARTICULAS and palavras:
            continue
        palavras.append(palavra)
    return "".join(palavra[0] for palavra in palavras[:2]).upper() or "?"


def tom_do_nome(nome: str) -> int:
    """A cor do avatar, de 1 a `TONS`, sempre a mesma para o mesmo nome.

    `zlib.crc32`, e não `hash()`: o `hash()` do Python muda a cada processo
    (é salgado), e o cliente trocaria de cor a cada reinício do servidor.
    Maiúsculas, acentos e espaços a mais não mudam a cor.
    """
    chave = " ".join(_sem_acento(nome or "").casefold().split())
    return zlib.crc32(chave.encode("utf-8")) % TONS + 1


def avatar(cliente) -> dict:
    return {
        "iniciais": iniciais(cliente.nome_cliente),
        "tom": tom_do_nome(cliente.nome_cliente),
    }


def logo_reduzida(cliente) -> str:
    """A URL da logo no tamanho do cartão; "" quando o cliente não tem logo.

    Passa pelo mesmo caminho das fotos do site (`core.fotos`): no Cloudinary
    a URL já pede a imagem com no máximo `LARGURA_DA_LOGO` px e no formato
    mais leve que o navegador aceita. Fora dele (computador de quem
    desenvolve, testes) volta a URL do arquivo como está.
    """
    return fotos.reduzir_imagem(fotos.url_da_imagem(cliente.logo), LARGURA_DA_LOGO)


def atalhos_de_contato(cliente) -> dict:
    """Os links de tocar: WhatsApp, ligar e e-mail ("" no que não houver).

    O número só vira conversa de WhatsApp quando dá para montar o endereço
    internacional (DDD + número ganha o 55 do Brasil) e quando o cadastro
    não diz que aquele telefone é "sem WhatsApp": abrir conversa com um
    fixo é mandar a equipe falar sozinha.
    """
    digitos = somente_digitos(cliente.telefone)
    internacional = "55" + digitos if len(digitos) in (10, 11) else digitos
    tem_numero = len(digitos) >= 8
    pode_whatsapp = (
        len(internacional) >= 12
        and cliente.canal_telefone != cliente.CanalTelefone.TELEFONE
    )
    email = (cliente.email or "").strip()
    return {
        "whatsapp": f"https://wa.me/{internacional}" if pode_whatsapp else "",
        "ligar": (
            f"tel:+{internacional}" if len(internacional) >= 12 else f"tel:{digitos}"
        ) if tem_numero else "",
        "email": f"mailto:{quote(email, safe='@')}" if email else "",
    }
