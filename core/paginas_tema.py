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
        "rodape": "Máquinas de boliche",
        "topo": True,
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
        "rodape": "Fliperamas e arcade",
        "topo": True,
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
        "rodape": "Brinquedos para shopping",
        "topo": True,
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
    "jogos-de-boliche": {
        "titulo_seo": "Jogos de boliche online grátis: boliche virtual e infantil | Lazer & Sport",
        "descricao_seo": (
            "Jogue boliche online grátis, no navegador ou no celular, sem baixar nada: o Dragon "
            "Bowling (boliche virtual de arcade) e o Strike Kids (boliche infantil), com ranking."
        ),
        "menu": "Jogos de boliche",
        "rodape": "Jogos de boliche online",
        "topo": True,
        "jogar": True,
        "kicker": "Jogue grátis · Sem baixar · Com ranking",
        "h1": "Jogos de boliche online grátis",
        "intro": (
            "Bora jogar boliche? Aqui você joga o boliche virtual direto no navegador, no celular ou no "
            "computador, sem baixar nada. São os jogos das máquinas de boliche que a Lazer & Sport "
            "fabrica: a mesma pista, os mesmos pinos e o recorde da casa para bater."
        ),
        "jogos": ["dragon-bowling", "strike-kids"],
        "palavras": ["boliche", "bowling"],
        "secoes": [
            {
                "titulo": "Dragon Bowling: boliche virtual",
                "texto": (
                    "Boliche de arcade com a arte do dragão: arraste a bola para cima e solte. O mapa "
                    "dos pinos mostra o que caiu, e o telão grita STRIKE, ACERTO ou PRA FORA. Dá para "
                    "jogar sozinho e disputar o ranking."
                ),
            },
            {
                "titulo": "Strike Kids: boliche infantil",
                "texto": (
                    "O boliche das crianças: o Bob e a Mia torcem a cada jogada, a pista muda de "
                    "cenário e os pinos caem com física de verdade. Arraste a bola e solte."
                ),
            },
            {
                "titulo": "Grátis, e com ranking",
                "texto": (
                    "Sem conta, você tem 2 jogadas grátis. Com a conta grátis do site, joga "
                    "quanto quiser e o seu recorde entra no ranking."
                ),
            },
        ],
        "perguntas": [
            (
                "Precisa baixar alguma coisa para jogar boliche online?",
                "Não. Os jogos rodam direto no navegador, no celular ou no computador.",
            ),
            (
                "O jogo de boliche é grátis?",
                "É. Sem conta, são 2 jogadas grátis; com a conta grátis do site, você joga à "
                "vontade e entra no ranking.",
            ),
            (
                "Qual a diferença entre o Dragon Bowling e o Strike Kids?",
                "O Dragon Bowling é o boliche virtual de arcade, para todas as idades. O Strike Kids é o "
                "boliche infantil, com personagens que torcem e cenários que mudam.",
            ),
            (
                "Esses jogos existem em máquina de verdade?",
                "Existem: são os jogos das máquinas de boliche que a Lazer & Sport fabrica em São Paulo "
                "para shoppings, parques e espaços kids.",
            ),
        ],
        "relacionados": ["boliche", "fliperama"],
        "mensagem": "Olá! Joguei o boliche no site e quero saber da máquina de boliche.",
    },
    "maquina-de-basquete": {
        "titulo_seo": "Máquina de basquete arcade para shopping e parque | Lazer & Sport",
        "descricao_seo": (
            "Máquinas de basquete de arcade da fábrica Lazer & Sport: Swish Arena com placar de LED e "
            "Slam Arena de neon. Jogue a prévia online e peça orçamento."
        ),
        "menu": "Máquina de basquete",
        "rodape": "Máquinas de basquete",
        "kicker": "Basquete arcade · Placar de LED",
        "h1": "Máquinas de basquete arcade",
        "intro": (
            "Cesta, placar e torcida: as máquinas de basquete da Lazer & Sport são feitas em São Paulo "
            "para shoppings, parques e espaços kids. Jogue a prévia de cada uma aqui no site e veja "
            "como o jogo prende quem passa."
        ),
        "jogos": ["swish-arena", "slam-arena"],
        "palavras": ["basquete", "cesta", "basket"],
        "secoes": [
            {
                "titulo": "Swish Arena",
                "texto": (
                    "Basquete de arcade com placar de LED gigante: nos últimos segundos cada cesta "
                    "vale três, e quatro cestas seguidas ligam o modo EM CHAMAS, que dobra os pontos."
                ),
            },
            {
                "titulo": "Slam Arena",
                "texto": (
                    "Basquete vertical de neon em três fases e sem botão: a própria cesta começa o "
                    "jogo, e cada fase tem uma meta para passar."
                ),
            },
            {
                "titulo": "No Espaço Esportivo também",
                "texto": (
                    "O Swish vem junto com o Gol Flash no Espaço Esportivo da Lazer & Sport, com "
                    "quadras e trampolins: dá para ver tudo em 3D na Arena do site."
                ),
            },
        ],
        "perguntas": [
            (
                "Dá para jogar a máquina de basquete antes de comprar?",
                "Dá: a prévia do Swish Arena e do Slam Arena roda aqui no site, sem baixar nada.",
            ),
            (
                "A Lazer & Sport fabrica a máquina de basquete?",
                "Sim. A fábrica fica em São Paulo e faz também a manutenção e as peças de reposição.",
            ),
        ],
        "relacionados": ["fliperama", "espaco-kids"],
        "mensagem": "Olá! Quero um orçamento da máquina de basquete.",
    },
    "maquina-de-boxe": {
        "titulo_seo": "Máquina de boxe (máquina de força/soco) para shopping | Lazer & Sport",
        "descricao_seo": (
            "Super Boxing: a máquina de força da Lazer & Sport, com adversário 3D no ringue, três socos "
            "e ranking. Jogue a prévia online e peça orçamento direto da fábrica."
        ),
        "menu": "Máquina de boxe",
        "rodape": "Máquina de boxe",
        "kicker": "Máquina de força · Soco · Ranking",
        "h1": "Máquina de boxe: o Super Boxing",
        "intro": (
            "Quem passa quer saber a força do próprio soco -- e volta para bater o recorde. O Super "
            "Boxing é a máquina de força da Lazer & Sport, feita em São Paulo: três socos contra um "
            "adversário 3D no ringue, com ranking da casa."
        ),
        "jogos": ["super-boxing"],
        "palavras": ["boxe", "soco", "força", "boxing"],
        "secoes": [
            {
                "titulo": "Como funciona",
                "texto": (
                    "O adversário 3D sente cada soco: três socos para cravar a maior força da "
                    "arena, nocautear o boxeador e entrar no ranking."
                ),
            },
            {
                "titulo": "Feita para durar",
                "texto": (
                    "Máquina de soco apanha o dia inteiro. Por isso a fábrica cuida da manutenção "
                    "e manda a peça de reposição quando precisa."
                ),
            },
        ],
        "perguntas": [
            (
                "Posso jogar o Super Boxing online?",
                "Pode: a prévia roda aqui no site, no celular ou no computador.",
            ),
            (
                "Onde a máquina de boxe é fabricada?",
                "Na fábrica da Lazer & Sport, na zona norte de São Paulo.",
            ),
        ],
        "relacionados": ["fliperama", "maquina-de-basquete"],
        "mensagem": "Olá! Quero um orçamento da máquina de boxe (Super Boxing).",
    },
    "espaco-kids": {
        "titulo_seo": "Espaço kids e espaço esportivo para shopping e parque | Lazer & Sport",
        "descricao_seo": (
            "Espaço Esportivo kids da Lazer & Sport: quadras, trampolins, Gol Flash e Swish num espaço "
            "só, com projeto sob medida. Passeie em 3D no site e peça orçamento."
        ),
        "menu": "Espaço kids",
        "rodape": "Espaço kids e esportivo",
        "kicker": "Espaço esportivo · Trampolim · Quadras",
        "h1": "Espaço kids e espaço esportivo",
        "intro": (
            "Um espaço inteiro de lazer e curtição para a criançada: o Espaço Esportivo da Lazer & "
            "Sport junta quadras, trampolins e as máquinas Gol Flash e Swish. Na Arena 3D do site dá "
            "para passear por dentro dele antes de decidir."
        ),
        "jogos": ["gol-flash-arena", "swish-arena"],
        "palavras": ["espaço", "kids", "trampolim", "esportivo", "circuito"],
        "secoes": [
            {
                "titulo": "O que vem dentro",
                "texto": (
                    "O Espaço Esportivo Modelo 1 traz dois círculos do Gol Flash, duas cestas do "
                    "Swish, quadras e trampolins -- e a página de cada máquina mostra em que espaço "
                    "ela também vem."
                ),
            },
            {
                "titulo": "Sob medida",
                "texto": (
                    "O projeto é feito para a área que você tem, com cores e adesivagem combinadas "
                    "no orçamento. Depois, peças e manutenção ficam com a fábrica."
                ),
            },
        ],
        "perguntas": [
            (
                "Dá para ver o espaço kids antes de comprar?",
                "Dá: a Arena 3D do site mostra o Espaço Esportivo em 3D, com o passeio por dentro.",
            ),
            (
                "O espaço pode ser adaptado ao meu local?",
                "Pode. O projeto é feito sob medida para a área do cliente.",
            ),
        ],
        "relacionados": ["brinquedos-para-shopping", "maquina-de-basquete"],
        "mensagem": "Olá! Quero um orçamento de espaço kids / espaço esportivo.",
    },
}


def tema(slug: str) -> dict | None:
    dados = TEMAS.get(slug)
    if not dados:
        return None
    return {"slug": slug, "whatsapp": link_whatsapp(dados["mensagem"]), **dados}


def menu():
    """[(slug, rótulo)] das sugestões do topo: só os temas em destaque, para caber."""
    return [(slug, dados["menu"]) for slug, dados in TEMAS.items() if dados.get("topo")]


def rodape():
    """[(slug, rótulo)] de todos os temas, para o rodapé de toda página."""
    return [(slug, dados.get("rodape", dados["menu"])) for slug, dados in TEMAS.items()]


# ---------------------------------------------------------------- os jogos na busca
#
# Quem procura "boliche virtual" quer JOGAR -- é por isso que os portais de
# jogos aparecem primeiro. As prévias das máquinas são jogos de verdade, que
# rodam no navegador; com o título e o texto que essa busca usa, a página
# de cada jogo entra na disputa. `tema` liga o jogo à página da máquina.
BUSCA_DOS_JOGOS = {
    "dragon-bowling": {
        "titulo": "Boliche virtual online grátis: jogue o Dragon Bowling | Lazer & Sport",
        "descricao": "Jogo de boliche online grátis no navegador e no celular, sem baixar: o Dragon Bowling, boliche virtual de arcade com ranking. É o jogo da máquina de boliche da Lazer & Sport.",
        "frase": "Boliche virtual online grátis: jogue no navegador ou no celular, sem baixar nada.",
        "tema": "jogos-de-boliche",
    },
    "strike-kids": {
        "titulo": "Jogo de boliche infantil online grátis: Strike Kids | Lazer & Sport",
        "descricao": "Boliche para crianças online, grátis e sem baixar: o Bob e a Mia torcem a cada jogada. É o jogo do boliche infantil de 5 sensores da Lazer & Sport.",
        "frase": "Jogo de boliche infantil online grátis, no navegador ou no celular.",
        "tema": "jogos-de-boliche",
    },
    "super-boxing": {
        "titulo": "Jogo de boxe online grátis: Super Boxing, a máquina de força | Lazer & Sport",
        "descricao": "Jogo de boxe online grátis: três socos contra um adversário 3D no ringue e ranking da força. É o jogo da máquina de boxe da Lazer & Sport.",
        "frase": "Jogo de boxe online grátis: teste a força do seu soco no navegador.",
        "tema": "maquina-de-boxe",
    },
    "lazer-shot": {
        "titulo": "Jogo de tiro ao alvo online grátis: Lazer Shot | Lazer & Sport",
        "descricao": "Tiro ao alvo online grátis: garrafas, lanternas e vasos em cenários do Egito, de Atlântida e do deserto. É o jogo da máquina Lazer Shot.",
        "frase": "Jogo de tiro ao alvo online grátis, direto no navegador.",
        "tema": "fliperama",
    },
    "slam-arena": {
        "titulo": "Basquete arcade online grátis: Slam Arena | Lazer & Sport",
        "descricao": "Jogo de basquete online grátis: basquete de neon em três fases, sem botão. É o jogo da máquina de basquete Slam Arena da Lazer & Sport.",
        "frase": "Jogo de basquete online grátis: três fases de basquete de neon.",
        "tema": "maquina-de-basquete",
    },
    "swish-arena": {
        "titulo": "Jogo de basquete online grátis: Swish Arena | Lazer & Sport",
        "descricao": "Basquete online grátis com placar de LED e modo EM CHAMAS. É o jogo da máquina de basquete Swish Arena da Lazer & Sport.",
        "frase": "Jogo de basquete online grátis, com placar de LED e modo EM CHAMAS.",
        "tema": "maquina-de-basquete",
    },
    "gol-flash-arena": {
        "titulo": "Jogo de chute ao gol online grátis: Gol Flash Arena | Lazer & Sport",
        "descricao": "Jogo de futebol online grátis: chute no anel de luz que está aceso antes que ele apague. É o jogo da máquina Gol Flash da Lazer & Sport.",
        "frase": "Jogo de chute ao gol online grátis: acerte o anel de luz aceso.",
        "tema": "espaco-kids",
    },
    "craque-de-botao": {
        "titulo": "Futebol de botão online grátis: Craque de Botão | Lazer & Sport",
        "descricao": "Futebol de botão online grátis: escolha a seleção, mire e chute. É o jogo da máquina de futebol de mesa Craque de Botão.",
        "frase": "Futebol de botão online grátis: escolha a seleção e chute.",
        "tema": "fliperama",
    },
    "hit-music": {
        "titulo": "Jogo de ritmo online grátis: Hit Music | Lazer & Sport",
        "descricao": "Jogo de música online grátis: as notas correm do centro para o anel, acerte no tempo e emende combos. É o jogo da máquina Hit Music.",
        "frase": "Jogo de ritmo online grátis: acerte as notas no tempo da música.",
        "tema": "fliperama",
    },
}


def busca_do_jogo(slug: str) -> dict:
    """Título, descrição e frase de busca de um jogo (vazio para jogo sem texto próprio)."""
    return BUSCA_DOS_JOGOS.get(slug, {})
