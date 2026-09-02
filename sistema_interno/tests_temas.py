"""Sol, lua e eclipse: um vocabulário, três valores.

O painel tinha 255 cores escritas à mão. Enquanto ele foi só escuro, isso
era inconsistência tolerável -- quatro âmbares claros para o mesmo
trabalho, doze marrons quase iguais para a mesma superfície. Com três
temas vira defeito estrutural: cada cor teria de ser reescrita três
vezes, e é sempre na terceira que o contraste quebra sem ninguém ver.

O que estes testes protegem, em ordem de importância:

  1. NENHUMA COR LITERAL fora dos dois lugares onde ela é legítima -- a
     definição dos temas e a folha de etiquetas, que é preta sobre papel
     branco porque vai para uma impressora laser de galpão. Uma cor solta
     é uma cor que não muda de tema, e ela só aparece no tema errado.
  2. OS TRÊS TEMAS DEFINEM O MESMO VOCABULÁRIO. Um token esquecido num
     tema herda o valor do escuro -- texto creme sobre papel creme, e
     ninguém percebe até alguém abrir aquela tela nesse tema.
  3. A SEPARAÇÃO ENTRE A COR QUE SE PREENCHE E A QUE SE LÊ. É ela que faz
     o tema claro funcionar; sem ela, o âmbar de 2,0:1 volta a ser texto.
  4. O TEMA APLICADO ANTES DO PRIMEIRO PIXEL, senão a tela pisca branca
     na cara de quem escolheu escuro, a cada abertura.
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

RAIZ = Path(__file__).resolve().parent
FOLHA = RAIZ / "static" / "interno" / "interno_modern.css"

TEMAS = ("lua", "sol", "eclipse")

#: Famílias de acento. Cada uma tem os mesmos papéis nos três temas.
FAMILIAS = ("acento", "apoio", "green", "red", "yellow", "violet", "info")


def sem_comentarios(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def bloco_do_tema(css, tema):
    marca = (':root,\n:root[data-tema="lua"]{' if tema == "lua"
             else f':root[data-tema="{tema}"]{{')
    inicio = css.index(marca)
    return css[inicio:css.index("\n}", inicio)]


def tokens_do_tema(css, tema):
    return dict(re.findall(r"(--[a-z0-9-]+)\s*:\s*([^;]+);", bloco_do_tema(css, tema)))


class VocabularioDosTemasTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.css = FOLHA.read_text(encoding="utf-8")
        cls.limpo = sem_comentarios(cls.css)

    def test_os_tres_temas_definem_o_mesmo_vocabulario(self):
        """Token faltando num tema herda o valor do escuro, calado.

        É o defeito mais caro deste arquivo: creme sobre creme não levanta
        erro nenhum, não aparece em teste de view, e só é descoberto por
        alguém que abriu aquela tela naquele tema.
        """
        base = set(tokens_do_tema(self.limpo, "lua"))
        # Medidas e nomes históricos são definidos uma vez só, no tema
        # padrão: eles não mudam com a cor.
        estruturais = {t for t in base if not self._e_cor(t)}

        for tema in ("sol", "eclipse"):
            faltando = (base - estruturais) - set(tokens_do_tema(self.limpo, tema))
            self.assertEqual(
                faltando, set(),
                f"o tema {tema} não define: {sorted(faltando)}",
            )

    @staticmethod
    def _e_cor(token):
        estrutura = ("radius", "sidebar-w", "sidebar-rail", "topbar-h",
                     "blue", "cyan", "shadow", "sombra-forca", "filtro-")
        return not any(parte in token for parte in estrutura)

    def test_cada_familia_tem_os_quatro_papeis_nos_tres_temas(self):
        """Preencher, ler, contornar e tingir são quatro trabalhos.

        No escuro dava para usar a mesma variável nos quatro: qualquer
        acento aceso tem contraste de sobra contra quase-preto. No papel
        não: o âmbar que preenche precisa continuar aceso, e o que é lido
        precisa escurecer.
        """
        for tema in TEMAS:
            tokens = tokens_do_tema(self.limpo, tema)
            for familia in FAMILIAS:
                for papel in ("", "-texto", "-brilho"):
                    nome = f"--{familia}{papel}"
                    self.assertIn(nome, tokens, f"{nome} falta no tema {tema}")

    def test_o_preenchimento_aceso_nao_escurece_com_o_tema(self):
        """`--x-brilho` é o topo claro de um degradê de botão.

        Ele foi criado porque o claro de preenchimento tinha sido
        classificado junto com o claro de LEITURA: no tema de papel o
        botão nascia com um degradê que ia de marrom escuro a âmbar.
        """
        valores = {
            tema: {f"--{f}-brilho": tokens_do_tema(self.limpo, tema)[f"--{f}-brilho"]
                   for f in FAMILIAS}
            for tema in TEMAS
        }
        self.assertEqual(valores["lua"], valores["sol"])
        self.assertEqual(valores["lua"], valores["eclipse"])

    def test_a_tinta_sobre_acento_nao_inverte(self):
        """O botão âmbar continua âmbar no claro, e a letra dele preta.

        Inverter `--tinta` junto com o tema escreveria creme sobre âmbar.
        """
        for tema in TEMAS:
            tinta = tokens_do_tema(self.limpo, tema)["--tinta"]
            self.assertTrue(
                self._luminancia(tinta) < 0.15,
                f"--tinta clareou no tema {tema}: {tinta}",
            )

    @staticmethod
    def _luminancia(cor):
        cor = cor.strip().lstrip("#")
        if len(cor) == 3:
            cor = "".join(c * 2 for c in cor)
        canais = []
        for i in (0, 2, 4):
            v = int(cor[i:i + 2], 16) / 255
            canais.append(v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4)
        return 0.2126 * canais[0] + 0.7152 * canais[1] + 0.0722 * canais[2]

    def test_a_escala_de_superficie_anda_no_sentido_certo(self):
        """Claro é claro, escuro é escuro, e o eclipse fica no meio.

        Sem isto, "tema claro" vira uma promessa que o CSS não cumpre --
        e foi o que aconteceu com o eclipse na primeira tentativa: os
        fundos ficaram em 16% de luminosidade, indistinguíveis da lua.
        """
        luz = {tema: self._luminancia(tokens_do_tema(self.limpo, tema)["--bg-0"])
               for tema in TEMAS}

        self.assertLess(luz["lua"], luz["eclipse"], "o eclipse não é mais claro que a lua")
        self.assertLess(luz["eclipse"], luz["sol"], "o sol não é mais claro que o eclipse")
        # E a distância entre eles precisa ser visível, não medida.
        self.assertGreater(luz["eclipse"] / max(luz["lua"], 0.001), 2.0)


class NenhumaCorSoltaTests(SimpleTestCase):
    """Cor literal é cor que não muda de tema."""

    def ler(self, caminho):
        return sem_comentarios(Path(caminho).read_text(encoding="utf-8"))

    def corpo_tematizavel(self, css):
        """O CSS sem a definição dos temas e sem a folha de etiquetas.

        A folha de etiquetas fica de fora porque ali a tinta é preta sobre
        papel branco DE PROPÓSITO: impressora de galpão é laser preta,
        quase sempre com toner no fim, e cor vira chapado cinza.
        """
        for m in re.finditer(r":root[^\{]*\{", css):
            fim = css.index("}", m.end())
            css = css[:m.start()] + " " * (fim - m.start()) + css[fim:]
        marca = re.search(r"^\.ls-folha-etiquetas\{", css, flags=re.M)
        if marca:
            css = css[:marca.start()]
        return css

    def test_a_folha_do_painel_nao_tem_cor_escrita_a_mao(self):
        corpo = self.corpo_tematizavel(self.ler(FOLHA))

        soltas = re.findall(r"#[0-9a-fA-F]{3,8}\b", corpo)
        self.assertEqual(
            sorted(set(soltas)), [],
            f"cor literal fora do tema: {sorted(set(soltas))}",
        )

    def test_as_folhas_auxiliares_tambem_nao_tem(self):
        base = RAIZ / "static" / "interno"
        for nome in ("gestao_integrada.css", "campanhas.css"):
            with self.subTest(folha=nome):
                soltas = re.findall(
                    r"#[0-9a-fA-F]{3,8}\b", self.corpo_tematizavel(self.ler(base / nome)),
                )
                self.assertEqual(sorted(set(soltas)), [], nome)

    def test_o_estilo_de_tela_dentro_do_template_tambem_segue_o_tema(self):
        """Sete telas trazem estilo próprio dentro do template.

        Cada uma delas era uma ilha que continuava escura no papel -- e é
        exatamente onde o texto sumia na primeira auditoria de contraste.

        Login e logout ficam de fora: são as duas telas sem barra de tema
        (ninguém escolheu nada ainda, porque ninguém entrou) e vivem no
        escuro de propósito, como porta de entrada da marca.
        """
        modelos = RAIZ / "templates"
        # As três telas que se bastam sozinhas. Login e logout vivem no
        # escuro de propósito (ninguém escolheu tema ainda, porque
        # ninguém entrou). A de recuperação é mais séria: ela aparece
        # quando o banco não responde, e todo o estilo dela mora dentro
        # dela justamente para não depender de nenhum arquivo externo
        # carregar. Tokenizá-la a faria abrir sem cor nenhuma.
        fora = {"login_inner.html", "logout_inner.html",
                "erro_temporario_inner.html"}
        for arquivo in sorted(modelos.glob("*.html")):
            if arquivo.name in fora:
                continue
            html = arquivo.read_text(encoding="utf-8")
            for bloco in re.finditer(r"<style>(.*?)</style>", html, flags=re.S):
                with self.subTest(tela=arquivo.name):
                    soltas = re.findall(
                        r"#[0-9a-fA-F]{3,8}\b", sem_comentarios(bloco.group(1)),
                    )
                    self.assertEqual(sorted(set(soltas)), [], arquivo.name)

    def test_a_tela_de_recuperacao_continua_se_bastando(self):
        """Ela aparece quando o banco não responde.

        Uma página de erro que depende de outro arquivo carregar é uma
        página de erro que às vezes não aparece. O estilo dela mora
        dentro dela, e por isso ela NÃO pode usar os tokens de tema: sem
        a folha do painel, `var(--acento)` não resolve para nada e a tela
        abre sem cor nenhuma -- justamente no pior momento.
        """
        pagina = (RAIZ / "templates" / "erro_temporario_inner.html").read_text(
            encoding="utf-8",
        )
        estilo = pagina[pagina.index("<style>"):pagina.index("</style>")]

        self.assertNotIn("interno_modern.css", pagina)
        self.assertNotIn("var(--", estilo)
        self.assertRegex(estilo, r"#[0-9a-fA-F]{3,8}\b")

    def test_toda_variavel_usada_tem_dono(self):
        """`var(--card)` sem `--card` definido não pinta nada.

        Era o caso dos cards de campanha: `background:var(--card)`, e
        `--card` não existia em folha nenhuma. No escuro passava
        despercebido -- fundo transparente sobre página quase preta é
        quase igual a fundo de painel. No claro vira texto solto no meio
        da página.
        """
        base = RAIZ / "static" / "interno"
        definidos, usados = set(), set()

        fontes = [base / "interno_modern.css", base / "gestao_integrada.css",
                  base / "campanhas.css"]
        textos = [f.read_text(encoding="utf-8") for f in fontes]
        for arquivo in sorted((RAIZ / "templates").glob("*.html")):
            html = arquivo.read_text(encoding="utf-8")
            textos += [b.group(1) for b in re.finditer(r"<style>(.*?)</style>",
                                                       html, flags=re.S)]

        for texto in textos:
            limpo = sem_comentarios(texto)
            definidos |= set(re.findall(r"(--[a-z0-9-]+)\s*:", limpo))
            # `var(--x, algo)` traz o próprio plano B e não precisa de dono.
            usados |= set(re.findall(r"var\(\s*(--[a-z0-9-]+)\s*\)", limpo))

        # Definidas na marcação, por atributo `style`.
        definidos |= {"--progress"}
        orfas = sorted(u for u in usados - definidos if not u.startswith("--bs-"))
        self.assertEqual(orfas, [], f"variáveis sem dono: {orfas}")

    def test_o_veu_das_sobreposicoes_vem_do_tema(self):
        """Branco a 6% sobre papel não existe.

        Metade do painel separa uma camada da outra com um véu branco de
        opacidade baixa. Transposto para o tema claro, ele desaparece: o
        card deixa de ter borda, o realce deixa de realçar.
        """
        corpo = self.corpo_tematizavel(self.ler(FOLHA))

        self.assertNotIn("rgba(255,255,255", corpo.replace(" ", ""))
        self.assertIn("var(--verniz-rgb)", corpo)


class TemaAplicadoAntesDoPrimeiroPixelTests(SimpleTestCase):

    def base(self):
        return (RAIZ / "templates" / "base_inner.html").read_text(encoding="utf-8")

    def test_a_escolha_e_lida_no_head_e_de_forma_sincrona(self):
        """Depois do primeiro pixel já é tarde.

        Aplicado com `defer`, ou no fim do corpo, o navegador desenha a
        tela inteira no tema padrão e só então troca: um lampejo branco na
        cara de quem escolheu escuro, toda vez que abre uma tela.
        """
        base = self.base()
        cabeca = base[:base.index("</head>")]

        self.assertIn('localStorage.getItem("ls-tema")', cabeca)
        self.assertIn('setAttribute("data-tema"', cabeca)
        # Antes da folha do painel, que é quem pinta.
        self.assertLess(
            cabeca.index('localStorage.getItem("ls-tema")'),
            cabeca.index('id="lsFolhaBase"'),
        )

    def test_o_acesso_ao_armazenamento_e_protegido(self):
        """`localStorage` LEVANTA em navegador com armazenamento bloqueado.

        Uma exceção neste ponto derrubaria o resto do `<head>` -- e com
        ele o menu.
        """
        base = self.base()
        trecho = base[base.index('localStorage.getItem("ls-tema")') - 400:]
        self.assertIn("try", trecho[:400])
        self.assertIn("catch", trecho[:600])

    def test_a_barra_tem_os_tres_e_diz_qual_esta_valendo(self):
        """Um botão que cicla obriga a passar pelo tema errado.

        E não diz em que tema você está sem que você decore o desenho do
        ícone. `aria-pressed` é o que faz o leitor de tela anunciar qual
        está valendo -- num grupo de três ícones sem texto, é a única
        informação que existe para quem não vê o realce.
        """
        base = self.base()
        for tema in TEMAS:
            self.assertIn(f'data-tema-escolha="{tema}"', base)
        self.assertEqual(base.count('aria-pressed="false"'), 3)
        self.assertIn('role="group"', base)
        self.assertIn("bi-brightness-high-fill", base)  # sol
        self.assertIn("bi-circle-half", base)           # eclipse
        self.assertIn("bi-moon-stars-fill", base)       # lua

    def test_a_barra_do_aparelho_acompanha_o_tema(self):
        """`theme-color` mora fora do documento e não acompanha CSS.

        Sem reescrevê-la, o topo do aplicativo instalado fica grafite com
        o painel em papel -- uma faixa escura que não pertence a nada.
        """
        base = self.base()
        self.assertIn('id="lsTemaCorBarra"', base)
        self.assertIn("COR_DA_BARRA", base)
        for tema in TEMAS:
            self.assertIn(f"{tema}:", base)


class ContrasteDosTemasTests(SimpleTestCase):
    """As combinações que o painel usa o tempo todo, medidas.

    Não substitui a auditoria no navegador -- essa percorre o DOM real e
    resolve fundo composto. Aqui ficam os pares fixos, que precisam
    continuar valendo mesmo que ninguém rode o navegador.
    """

    #: (tinta, fundo, mínimo) -- 4,5:1 é texto normal; 3:1, texto grande.
    PARES = (
        ("--text", "--bg-0", 4.5),
        ("--text", "--panel", 4.5),
        ("--text-2", "--panel", 4.5),
        ("--muted", "--panel", 4.5),
        ("--muted", "--bg-0", 4.5),
        ("--muted-2", "--bg-0", 4.5),
        ("--muted-2", "--panel", 4.5),
        ("--acento-texto", "--bg-0", 4.5),
        ("--acento-texto", "--panel", 4.5),
        ("--green-texto", "--panel", 4.5),
        ("--red-texto", "--panel", 4.5),
        ("--apoio-texto", "--panel", 4.5),
        ("--info-texto", "--panel", 4.5),
        ("--violet-texto", "--panel", 4.5),
        ("--yellow-texto", "--panel", 4.5),
        ("--tinta", "--acento", 4.5),
        ("--acento-tinta", "--acento", 4.5),
    )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.limpo = sem_comentarios(FOLHA.read_text(encoding="utf-8"))

    @staticmethod
    def _rgb(cor):
        cor = cor.strip().lstrip("#")
        if len(cor) == 3:
            cor = "".join(c * 2 for c in cor)
        return tuple(int(cor[i:i + 2], 16) for i in (0, 2, 4))

    @classmethod
    def _luz(cls, rgb):
        canais = []
        for v in rgb:
            v /= 255
            canais.append(v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4)
        return 0.2126 * canais[0] + 0.7152 * canais[1] + 0.0722 * canais[2]

    @classmethod
    def _razao(cls, a, b):
        la, lb = cls._luz(cls._rgb(a)), cls._luz(cls._rgb(b))
        return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)

    def test_toda_combinacao_de_uso_passa_do_minimo(self):
        for tema in TEMAS:
            tokens = tokens_do_tema(self.limpo, tema)
            for tinta, fundo, minimo in self.PARES:
                with self.subTest(tema=tema, par=f"{tinta} sobre {fundo}"):
                    razao = self._razao(tokens[tinta], tokens[fundo])
                    self.assertGreaterEqual(
                        round(razao, 2), minimo,
                        f"{tema}: {tinta} ({tokens[tinta]}) sobre "
                        f"{fundo} ({tokens[fundo]}) dá {razao:.2f}:1",
                    )
