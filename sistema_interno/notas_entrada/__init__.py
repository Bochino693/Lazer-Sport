"""Entrada de nota fiscal no estoque (LEIA-ME-V10, seção 115).

  * `leitura`     -- o XML da NF-e ou o PDF do DANFE viram `NotaLida`
                     (sem Django: bytes entram, campos saem);
  * `ligacao`     -- cada item ligado a um Material (código do fornecedor,
                     nome sem acento ou semelhança), unidades e a soma dos
                     itens repetidos;
  * `lancamento`  -- a nota em conferência e o lançamento: fornecedor e
                     materiais criados se faltarem, a entrada no estoque
                     pelo `MovimentoEstoque.registrar` e a compra no
                     Financeiro;
  * `armazenamento` -- o arquivo da nota, no cofre privado (sem URL).
"""
