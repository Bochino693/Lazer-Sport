"""Contas de acesso: e-mail único, login com freio, senha forte e o registro de segurança.

Um lugar só para as regras de quem entra no site, no aplicativo e no painel.
Cada caminho que cria uma conta ou muda o e-mail dela (cadastro do site, API
do aplicativo, Google/Apple, perfil, painel, admin) chama as funções daqui --
nenhum deles decide sozinho se um endereço está livre. Ver LEIA-ME-V10.txt,
seção "Contas e segurança".

    emails.py     normalizar, conferir e trocar o e-mail de uma conta
    guarda.py     a última trava: nenhum User/EmailAddress é gravado com
                  e-mail de outra conta, venha de onde vier
    adapters.py   o allauth (cadastro, Google e Apple) pelas mesmas regras
    freio.py      o limite de senhas erradas por conta e por IP
    backends.py   o freio vale até para quem chama authenticate() direto
    senhas.py     os validadores de senha das contas novas e das trocas
    models.py     OcorrenciaSeguranca: o que foi barrado, para o dono revisar
    views.py      a tela "Segurança das contas" do painel (interno.)
"""
