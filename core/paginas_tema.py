"""Páginas por tema de busca: /boliche/, /fliperama/ e /brinquedos-para-shopping/.

POR QUE EXISTEM. Quem procura "boliche" no Google não chegava aqui: o site
não tinha uma página sequer sobre boliche. A palavra aparecia só dentro da
ficha de dois jogos. O Google mostra a página que responde a busca, e
quem não tem a página não entra na disputa, por melhor que seja a máquina.

O QUE CADA UMA TEM. Conteúdo de verdade sobre o que a fábrica faz: as
máquinas daquele tema (com a prévia jogável de cada uma), os brinquedos do
catálogo que casam com o tema, perguntas frequentes e o caminho do
orçamento. Nada de página-porta (o mesmo texto com a palavra trocada), que
o Google trata como spam: cada tema tem texto, máquinas e perguntas
próprios. E nada que a fábrica não faça -- aqui não se fala em aluguel,
porque a Lazer & Sport fabrica e vende.

Para criar um tema novo: um item em TEMAS com o mesmo formato. A rota, o
mapa do site, os links do rodapé e o teste já leem esta lista.
"""

from __future__ import annotations

from urllib.parse import quote

WHATSAPP = "5511960563135"


def link_whatsapp(texto: str) -> str:
    return f"https://wa.me/{WHATSAPP}?text={quote(texto)}"


TEMAS = {
    "boliche": {
        "titulo_seo": "Máquina de boliche para shopping e parque: virtual e infantil | Lazer & Sport",
        "descricao_seo": (
            "Boliche virtual de arcade e boliche infantil de 5 sensores, feitos pela fábrica "
            "Lazer & Sport em São Paulo. Jogue a prévia, veja as máquinas e peça orçamento."
        ),
        "menu": "Boliche",
        "kicker": "Boliche virtual · Boliche infantil",
        "h1": "Máquinas de boliche para o seu espaço",
        "intro": (
            "Boliche que cabe no shopping, no parque e no quiosque: a Lazer & Sport fabrica em "
            "São Paulo o boliche virtual de arcade e o boliche infantil, com a pista, o telão e o "
            "placar que fazem a fila voltar. Dá para jogar a prévia de cada um aqui no site antes "
            "de pedir o orçamento."
        ),
        "jogos": ["dragon-bowling", "strike-kids"],
        "palavras": ["boliche", "bowling", "strike"],
        "secoes": [
            {
                "titulo": "Boliche virtual de arcade",
                "texto": (
                    "O Boliche Virtual roda o Dragon Bowling, o boliche de arcade da casa: 1 ou 2 "
                    "jogadores, mapa dos pinos na tela, STRIKE, ACERTO e PRA FORA no telão e o "
                    "recorde da casa para quem quer bater. É a máquina para corredor de shopping e "
                    "área de jogos, onde o jogo rápido gira o público."
                ),
            },
            {
                "titulo": "Boliche infantil de 5 sensores",
                "texto": (
                    "O Strike Kids é o boliche feito para as crianças: cinco sensores leem a "
                    "jogada, o Bob e a Mia torcem a cada bola, a pista muda de cenário e os pinos "
                    "caem com física de verdade. Para espaço kids, buffet e parque infantil."
                ),
            },
            {
                "titulo": "Direto da fábrica",
                "texto": (
                    "Fabricar aqui quer dizer conversar com quem monta a máquina: projeto sob "
                    "medida para o espaço, cores e adesivagem combinadas no orçamento, e peças de "
                    "reposição e manutenção com a mesma equipe depois que a máquina está rodando."
                ),
            },
        ],
        "perguntas": [
            (
                "Qual a diferença entre o boliche virtual e o boliche infantil?",
                "O boliche virtual (Dragon Bowling) é uma máquina de arcade para todas as idades, "
                "com 1 ou 2 jogadores e recorde da casa. O boliche infantil (Strike Kids) é pensado "
                "para crianças, com cinco sensores, personagens que torcem e cenários que mudam.",
            ),
            (
                "Dá para testar o jogo antes de comprar?",
                "Sim. As prévias do Dragon Bowling e do Strike Kids rodam aqui no site, no celular "
                "ou no computador, sem instalar nada.",
            ),
            (
                "A Lazer & Sport vende ou aluga as máquinas de boliche?",
                "A Lazer & Sport é fábrica: projeta, fabrica e vende as máquinas, e cuida das peças "
                "de reposição e da manutenção depois.",
            ),
            (
                "Como peço um orçamento?",
                "Pelo WhatsApp (11) 96056-3135 ou pela conta no site. Conte o espaço e o público, "
                "e a equipe monta a proposta.",
            ),
        ],
        "relacionados": ["fliperama", "brinquedos-para-shopping"],
        "mensagem": "Olá! Vi as máquinas de boliche no site e quero um orçamento.",
    },
    "fliperama": {
        "titulo_seo": "Máquinas de fliperama e arcade para shopping e parque | Lazer & Sport",
        "descricao_seo": (
            "Fliperamas e máquinas de arcade da fábrica Lazer & Sport: boxe de força, tiro ao "
            "alvo, basquete com placar de LED, chute ao gol, ritmo e futebol de mesa. Jogue as prévias."
        ),
        "menu": "Fliperama",
        "kicker": "Arcade · Força · Basquete · Ritmo",
        "h1": "Máquinas de fliperama e arcade",
        "intro": (
            "Fliperama é a máquina que chama pelo barulho e segura pelo recorde. A Lazer & Sport "
            "fabrica em São Paulo as máquinas de arcade para shoppings, parques e quiosques: força, "
            "mira, basquete, chute ao gol, ritmo e futebol de mesa -- e cada uma tem a prévia "
            "jogável aqui no site."
        ),
        "jogos": ["super-boxing", "lazer-shot", "swish-arena", "slam-arena", "gol-flash-arena",
                  "hit-music", "craque-de-botao"],
        "palavras": ["fliperama", "arcade", "pimbal", "pinball", "boxe", "basquete", "tiro", "zumbi"],
        "secoes": [
            {
                "titulo": "Força, mira e esporte",
                "texto": (
                    "O Super Boxing mede a força do soco contra um adversário 3D no ringue; o Lazer "
                    "Shot é tiro ao alvo com pistola de luz em cenários do Egito, de Atlântida e do "
                    "deserto; o Swish Arena e o Slam Arena são basquete de arcade, e o Gol Flash Arena "
                    "é chute ao gol com alvos de luz."
                ),
            },
            {
                "titulo": "Ritmo e mesa",
                "texto": (
                    "O Hit Music é jogo de ritmo com tela circular, e o Craque de Botão leva o "
                    "futebol de botão para a tela, com dois jogadores frente a frente."
                ),
            },
            {
                "titulo": "Feito para rodar o dia todo",
                "texto": (
                    "Máquina de fábrica é máquina com peça de reposição: a mesma equipe que monta "
                    "o fliperama faz a manutenção e manda a peça quando precisa."
                ),
            },
        ],
        "perguntas": [
            (
                "Quais máquinas de fliperama a Lazer & Sport fabrica?",
                "Boxe de força (Super Boxing), tiro ao alvo (Lazer Shot), basquete (Swish Arena e "
                "Slam Arena), chute ao gol (Gol Flash Arena), ritmo (Hit Music) e futebol de mesa "
                "(Craque de Botão), além dos brinquedos do catálogo.",
            ),
            (
                "Posso jogar antes de comprar?",
                "Sim. Cada máquina tem a prévia jogável no site, em /jogos/, sem instalar nada.",
            ),
            (
                "Vocês fazem manutenção e vendem peças?",
                "Sim. O site tem a seção de peças de reposição, e a manutenção é feita pela equipe "
                "da fábrica.",
            ),
        ],
        "relacionados": ["boliche", "brinquedos-para-shopping"],
        "mensagem": "Olá! Vi os fliperamas no site e quero um orçamento.",
    },
    "brinquedos-para-shopping": {
        "titulo_seo": "Brinquedos para shopping, quiosque e parque: fábrica em São Paulo | Lazer & Sport",
        "descricao_seo": (
            "Fábrica de brinquedos para shoppings, quiosques e parques: brinquedões, espaço "
            "esportivo kids, fliperamas e boliche, com projeto sob medida, peças e manutenção."
        ),
        "menu": "Para shopping",
        "kicker": "Shopping · Quiosque · Parque",
        "h1": "Brinquedos para shopping, quiosque e parque",
        "intro": (
            "A Lazer & Sport é fábrica de brinquedos em São Paulo: brinquedões, espaço esportivo "
            "kids, fliperamas e boliche para quem vive de diversão -- shoppings, quiosques, parques e "
            "espaços de festa. Do projeto sob medida à peça de reposição, é a mesma equipe."
        ),
        "jogos": ["gol-flash-arena", "swish-arena", "strike-kids", "dragon-bowling"],
        "palavras": ["brinquedão", "brinquedao", "espaço", "playground", "kids", "trampolim", "piscina"],
        "secoes": [
            {
                "titulo": "Brinquedões e espaço esportivo kids",
                "texto": (
                    "Brinquedões com escorregador, rede e tubo, e o Espaço Esportivo: quadras, "
                    "trampolins e as máquinas Gol Flash e Swish juntas num espaço só. Na Arena 3D do "
                    "site dá para passear por dentro deles antes de decidir."
                ),
            },
            {
                "titulo": "Máquinas que giram o público",
                "texto": (
                    "Fliperamas e boliches de partida rápida, com placar e recorde da casa: o tipo "
                    "de máquina que faz o cliente jogar de novo e chamar o amigo."
                ),
            },
            {
                "titulo": "Projeto, peça e manutenção",
                "texto": (
                    "O projeto é feito para o espaço que você tem, com cores e adesivagem combinadas "
                    "no orçamento. Depois, as peças de reposição e a manutenção ficam com a fábrica."
                ),
            },
        ],
        "perguntas": [
            (
                "A Lazer & Sport fabrica brinquedos sob medida?",
                "Sim. O projeto é feito para o espaço do cliente, e as cores e a adesivagem são "
                "combinadas no orçamento.",
            ),
            (
                "Dá para ver os brinquedos antes?",
                "Sim: a Arena 3D do site mostra os brinquedos em 3D, e as máquinas de jogo têm a "
                "prévia jogável.",
            ),
            (
                "Onde fica a fábrica?",
                "Na Rua São Roque de Minas, 104, Jardim Peri, zona norte de São Paulo (SP).",
            ),
        ],
        "relacionados": ["boliche", "fliperama"],
        "mensagem": "Olá! Quero um orçamento de brinquedos para o meu espaço.",
    },
}


def tema(slug: str) -> dict | None:
    dados = TEMAS.get(slug)
    if not dados:
        return None
    return {"slug": slug, "whatsapp": link_whatsapp(dados["mensagem"]), **dados}


def menu():
    """[(slug, rótulo)] para o rodapé e as sugestões do topo."""
    return [(slug, dados["menu"]) for slug, dados in TEMAS.items()]
