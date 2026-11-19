"""O automatizador da Ordem de Serviço: o documento vira O.S. sozinho.

O PEDIDO (LEIA-ME-V10, seção 122): "vc deve também criar um automatizador
na ordem de serviço para ler os documentos e auto salvar no sistema." A
equipe solta uma ou várias fichas de O.S., pedidos de serviço e laudos
(.docx, .pdf, .txt) na tela de Ordens de Serviço; cada um é lido e, com o
essencial no papel, a O.S. é CRIADA na hora -- sem tela de conferência.

REAPROVEITA A LEITURA DO ORÇAMENTO (`importacao_word/`), que já lê Word e
PDF "como uma IA, sem a chave": o leitor numera as linhas, `deterministica`
lê dinheiro, CPF/CNPJ, telefone, e-mail, datas, endereço e as tabelas de
itens, e `identificar` acha o cliente no texto sem rótulo, deixando de fora
a fábrica e a equipe. Aqui só entra o que é da O.S.:

  1. `arquivo`  abre o .docx, o PDF com texto (pypdf, no servidor) e o
                .txt, nas mesmas linhas numeradas; calcula o SHA-256 do
                arquivo e o do texto normalizado (o repetido).
  2. `campos`   os rótulos da O.S. -- equipamento, série, defeito,
                diagnóstico, serviço executado, técnico, tipo, situação,
                prioridade, datas, garantia, peças e serviços, valores,
                pagamento, o número da O.S. escrito no papel.
  3. `cliente`  quem é o cliente (as regras do orçamento) e o cadastro:
                liga ao que já existe pelo CPF/CNPJ, e-mail ou telefone;
                cadastra pelas regras da aba Clientes quando não há.
  4. `gravar`   o essencial, o repetido e a criação: a O.S. pelas mesmas
                regras da criação à mão, os itens, o documento anexado.

NADA SAI DO SERVIDOR. A leitura é toda local, por regra; o documento do
cliente nunca vai para a IA nem para serviço de fora. (Endereço salvo no
cadastro segue o caminho de sempre do cadastro de clientes.)
"""
