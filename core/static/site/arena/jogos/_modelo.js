/* Modelo provisório: toque nos círculos. Serve só para conferir o console. */
export default {
  largura: 540,
  altura: 960,
  artes: {},
  criar(api) {
    let pontos = 0, tempo = 20, alvo = { x: 270, y: 480, r: 60 };
    const novo = () => { alvo = { x: api.aleatorio(80, api.W - 80), y: api.aleatorio(120, api.H - 120), r: api.aleatorio(40, 70) }; };
    return {
      iniciar() { pontos = 0; tempo = 20; novo(); api.placar({ pontos, tempo, info: api.variante || "" }); },
      atualizar(dt) {
        tempo -= dt; api.placar({ tempo });
        if (tempo <= 0) api.terminar({ pontos, detalhe: "Modelo do console" });
      },
      desenhar(ctx) {
        const g = ctx.createLinearGradient(0, 0, 0, api.H); g.addColorStop(0, "#0b1a44"); g.addColorStop(1, "#02060f");
        ctx.fillStyle = g; ctx.fillRect(0, 0, api.W, api.H);
        ctx.fillStyle = "#e63946"; ctx.beginPath(); ctx.arc(alvo.x, alvo.y, alvo.r, 0, Math.PI * 2); ctx.fill();
        api.texto(ctx, "EM CONSTRUÇÃO", api.W / 2, 60, { tamanho: 30, cor: "#ffd700" });
      },
      apertar(x, y) {
        if (Math.hypot(x - alvo.x, y - alvo.y) < alvo.r) {
          pontos += 10; api.som("acerto"); api.efeitos.explosao(x, y, { cor: ["#ffd700", "#e63946"] });
          api.efeitos.texto("+10", x, y); api.placar({ pontos }); api.tremer(6); novo();
        } else api.som("erro");
      },
    };
  },
};
