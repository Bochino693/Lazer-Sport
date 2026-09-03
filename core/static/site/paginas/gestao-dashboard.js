/* Comportamento de gestao / dashboard.
 *
 * NASCEU DE DENTRO DO HTML. Eram 5 KB de <script> no template --
 * peso repetido a cada abertura da página, que o navegador não tinha
 * como guardar: script dentro do HTML não tem endereço para cachear.
 *
 * O <script src> ficou na MESMA posição do bloco antigo, e sem `defer`
 * de propósito: script clássico externo executa na ordem do documento,
 * igual ao inline. Com `defer` ele passaria para depois da análise da
 * página, e qualquer trecho que dependesse dele antes disso quebraria
 * sem aviso.
 */

(function () {
  const rankingTabs = Array.from(document.querySelectorAll('[data-ranking]'));
  const rankingPanels = Array.from(document.querySelectorAll('[data-ranking-panel]'));

  rankingTabs.forEach(function (tab) {
    tab.addEventListener('click', function () {
      const target = tab.dataset.ranking;
      rankingTabs.forEach(item => item.classList.toggle('is-active', item === tab));
      rankingPanels.forEach(panel => {
        panel.classList.toggle('is-active', panel.dataset.rankingPanel === target);
      });
    });
  });

  /* -----------------------------------------------------------------
     VENDAS POR PERÍODO, DESENHADO AQUI MESMO

     Uma série, alguns pontos: cabe num SVG. Ele é responsivo pelo
     `viewBox` (sem redesenhar no `resize`), escala sozinho ao maior
     valor do período e cai fora sem barulho quando não há dado.
     ----------------------------------------------------------------- */
  const grafico = document.getElementById('dashboardSalesChart');
  const labelsNode = document.getElementById('dashboard-chart-labels');
  const dataNode = document.getElementById('dashboard-chart-data');

  if (grafico && labelsNode && dataNode) {
    let rotulos = [], valores = [];
    try {
      rotulos = JSON.parse(labelsNode.textContent) || [];
      valores = (JSON.parse(dataNode.textContent) || []).map(Number);
    } catch (erro) { rotulos = []; valores = []; }

    const dinheiro = function (valor) {
      return 'R$ ' + Number(valor || 0).toLocaleString('pt-BR', {
        minimumFractionDigits: 2, maximumFractionDigits: 2,
      });
    };

    if (valores.length) {
      const L = 56, R = 14, T = 16, B = 34;   // margens do desenho
      const LARG = 720, ALT = 310;
      const util = { x: LARG - L - R, y: ALT - T - B };

      /* O TETO SOBE UM POUCO ACIMA DO MAIOR VALOR. Sem essa folga o
         pico -- que é justamente o que a pessoa está olhando -- nasce
         colado na linha de cima e parece cortado. */
      const bruto = Math.max.apply(null, valores.concat([0]));
      const passo = Math.pow(10, Math.max(0, String(Math.round(bruto)).length - 2));
      const teto = bruto > 0 ? Math.ceil((bruto * 1.08) / passo) * passo : 1;

      const px = function (i) {
        return valores.length === 1
          ? L + util.x / 2
          : L + (util.x * i) / (valores.length - 1);
      };
      const py = function (v) { return T + util.y - (util.y * (v || 0)) / teto; };

      const pontos = valores.map(function (v, i) { return px(i) + ',' + py(v); });

      /* UM PERÍODO SÓ NÃO TEM LINHA. Com um ponto, a área ia da base
         até ele e voltava -- desenhando um risco vertical no meio do
         quadro, que se lê como um pico e não como "um mês, um valor".
         Nesse caso fica só a bolinha. */
      const serie = valores.length > 1
        ? '<path d="M' + px(0) + ',' + (T + util.y) + ' L' + pontos.join(' L') +
          ' L' + px(valores.length - 1) + ',' + (T + util.y) + ' Z" ' +
          'fill="url(#lsVendasFundo)"/>' +
          '<polyline points="' + pontos.join(' ') + '" fill="none" stroke="#F2A93B" ' +
          'stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>'
        : "";

      // Quatro linhas de apoio: menos vira adivinhação, mais vira grade.
      let apoio = '', escala = '';
      for (let n = 0; n <= 4; n++) {
        const v = (teto / 4) * n;
        const y = py(v);
        apoio += '<line x1="' + L + '" y1="' + y + '" x2="' + (LARG - R) +
                 '" y2="' + y + '" stroke="rgba(196,182,160,.09)" stroke-width="1"/>';
        escala += '<text x="' + (L - 8) + '" y="' + (y + 4) +
                  '" text-anchor="end" fill="#A2917A" font-size="11">R$ ' +
                  Math.round(v).toLocaleString('pt-BR') + '</text>';
      }

      /* Nem todo rótulo cabe embaixo: com 30 dias eles viram um borrão.
         Mostra-se um a cada N, sempre incluindo o último. */
      const salto = Math.max(1, Math.ceil(valores.length / 8));
      let datas = '';
      rotulos.forEach(function (rotulo, i) {
        if (i % salto !== 0 && i !== valores.length - 1) return;
        /* AS PONTAS SE ENCOSTAM NA BORDA, EM VEZ DE CENTRALIZAR. O
           último ponto fica no fim do desenho: um rótulo centralizado
           nele passa metade para fora do quadro, e "08/2026" aparecia
           como "08/202". */
        const ancora = i === 0 ? "start"
          : (i === valores.length - 1 ? "end" : "middle");
        datas += '<text x="' + px(i) + '" y="' + (ALT - 12) +
                 '" text-anchor="' + ancora + '" fill="#A2917A" font-size="11">' +
                 String(rotulo).replace(/[<&>]/g, '') + '</text>';
      });

      let bolinhas = '';
      valores.forEach(function (v, i) {
        bolinhas += '<circle class="dashboard-chart-ponto" cx="' + px(i) + '" cy="' + py(v) +
                    '" r="3.4" fill="#FFD08A" stroke="#D98E22" stroke-width="2">' +
                    '<title>' + String(rotulos[i] || '').replace(/[<&>]/g, '') +
                    ': ' + dinheiro(v) + '</title></circle>';
      });

      grafico.innerHTML =
        '<svg viewBox="0 0 ' + LARG + ' ' + ALT + '" preserveAspectRatio="none" ' +
        'role="img" aria-label="Vendas por período" style="width:100%;height:100%">' +
        '<defs><linearGradient id="lsVendasFundo" x1="0" y1="0" x2="0" y2="1">' +
        '<stop offset="0" stop-color="#F2A93B" stop-opacity=".46"/>' +
        '<stop offset="1" stop-color="#F2A93B" stop-opacity=".035"/>' +
        '</linearGradient></defs>' +
        apoio + serie + bolinhas + escala + datas +
        '</svg>';
    }
  }
})();
