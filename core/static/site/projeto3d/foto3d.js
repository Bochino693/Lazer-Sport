/* O PROJETO NA FOTO DO CLIENTE: de onde a foto foi tirada, pelos pontos marcados no chão.

   No "Monte seu espaço" o cliente sobe uma foto do lugar e arrasta quatro
   pontos até o chão do espaço. Daqui sai a câmera da foto: a posição, a
   direção e a lente. Com ela o 3D do projeto é desenhado por cima da foto,
   do mesmo ângulo em que ela foi tirada (projeto3d.js, "Veja no seu espaço").

   AS DUAS MANEIRAS DE MARCAR
   - Os quatro cantos aparecem (frente = true): os pontos são os cantos do
     espaço, que tem largura × comprimento conhecidos. Um canto fora da foto
     vai para fora dela, onde ele estaria.
   - A frente ficou fora (frente = false), o mais comum quando a foto é tirada
     da porta: os dois de cima são os cantos do fundo e os dois de baixo ficam
     em cima das linhas das paredes, na mesma distância do fundo. A distância
     sai da própria foto (o retângulo marcado só fecha com uma profundidade).

   A CONTA. Os quatro pares (chão em metros -> pixel) dão a homografia H.
   Com o centro da foto como centro da lente, H = K [r1 r3 t]: os dois eixos
   do chão (r1, r3) têm de ser perpendiculares e do mesmo tamanho, e disso
   saem a lente (f) e, no segundo caso, a profundidade. A lente que melhor
   fecha os quatro pontos (a conta tolera o canto marcado meio torto) dá a
   rotação R e a posição t. Sem dependências: só números.

   `giro` gira o projeto na foto (qual parede do projeto fica no fundo dela).
*/

export const NOMES_DOS_CANTOS = ["fundo esq.", "fundo dir.", "frente dir.", "frente esq."];

/** Os cantos do chão do projeto (x, z), na ordem dos nomes. A entrada fica no meio da frente (+z). */
export function cantosDaSala(largura, comprimento) {
  const w = largura / 2, d = comprimento / 2;
  return [[-w, -d], [w, -d], [w, d], [-w, d]];
}

/** Resolve A x = b (n × n), com pivô parcial. null se não tiver solução. */
export function resolver(A, b) {
  const n = b.length;
  const M = A.map((linha, i) => [...linha, b[i]]);
  for (let c = 0; c < n; c++) {
    let p = c;
    for (let i = c + 1; i < n; i++) if (Math.abs(M[i][c]) > Math.abs(M[p][c])) p = i;
    if (Math.abs(M[p][c]) < 1e-12) return null;
    [M[c], M[p]] = [M[p], M[c]];
    for (let i = c + 1; i < n; i++) {
      const k = M[i][c] / M[c][c];
      for (let j = c; j <= n; j++) M[i][j] -= k * M[c][j];
    }
  }
  const x = new Array(n).fill(0);
  for (let i = n - 1; i >= 0; i--) {
    let s = M[i][n];
    for (let j = i + 1; j < n; j++) s -= M[i][j] * x[j];
    x[i] = s / M[i][i];
  }
  return x;
}

/** A homografia de 4 pares (de -> para): 9 números, linha a linha (h33 = 1). */
export function homografia(de, para) {
  const A = [], b = [];
  for (let i = 0; i < 4; i++) {
    const [x, y] = de[i], [u, v] = para[i];
    A.push([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.push(u);
    A.push([0, 0, 0, x, y, 1, -v * x, -v * y]); b.push(v);
  }
  const h = resolver(A, b);
  return h ? [...h, 1] : null;
}

const norma = (v) => Math.hypot(v[0], v[1], v[2]);
const vezes = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];

/* A matriz mais perto de M que é uma rotação (decomposição polar, pelas iterações de Newton). */
function rotacaoMaisPerto(M) {
  let R = M.map((l) => [...l]);
  for (let it = 0; it < 12; it++) {
    const [a, b, c] = R[0], [d, e, f] = R[1], [g, h, i] = R[2];
    const det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g);
    if (Math.abs(det) < 1e-12) return null;
    // (R^-1)^T = cofatores / det
    const C = [
      [(e * i - f * h) / det, -(d * i - f * g) / det, (d * h - e * g) / det],
      [-(b * i - c * h) / det, (a * i - c * g) / det, -(a * h - b * g) / det],
      [(b * f - c * e) / det, -(a * f - c * d) / det, (a * e - b * d) / det],
    ];
    R = R.map((l, r) => l.map((v, k) => (v + C[r][k]) / 2));
  }
  return R;
}

/* Com a lente f, a rotação e a posição que H (chão -> pixel centrado) pede. */
function decompor(H, f, sinal) {
  const a1 = [H[0] / f, H[3] / f, H[6]];
  const a2 = [H[1] / f, H[4] / f, H[7]];
  const a3 = [H[2] / f, H[5] / f, H[8]];
  const lambda = (sinal * 2) / (norma(a1) + norma(a2));
  const r1 = a1.map((v) => v * lambda), r3 = a2.map((v) => v * lambda), t = a3.map((v) => v * lambda);
  const r2 = vezes(r3, r1);
  // colunas r1 r2 r3 (os eixos do mundo vistos da câmera)
  const R = rotacaoMaisPerto([[r1[0], r2[0], r3[0]], [r1[1], r2[1], r3[1]], [r1[2], r2[2], r3[2]]]);
  return R ? { R, t } : null;
}

/** Leva um ponto do mundo (x, y, z) ao pixel da foto: [u, v, profundidade]. */
export function projetar(pose, x, y, z) {
  const { R, t, f, cx, cy } = pose;
  const X = R[0][0] * x + R[0][1] * y + R[0][2] * z + t[0];
  const Y = R[1][0] * x + R[1][1] * y + R[1][2] * z + t[1];
  const Z = R[2][0] * x + R[2][1] * y + R[2][2] * z + t[2];
  return [cx + (f * X) / Z, cy + (f * Y) / Z, Z];
}

function erroDosPontos(pose, mundo, pixels) {
  let s = 0;
  for (let i = 0; i < 4; i++) {
    const [u, v, z] = projetar(pose, mundo[i][0], 0, mundo[i][1]);
    if (!(z > 0)) return Infinity;
    s += (u - pixels[i][0]) ** 2 + (v - pixels[i][1]) ** 2;
  }
  return Math.sqrt(s / 4);
}

/* Gira R por um vetor de rotação pequeno (Rodrigues), pela esquerda: R' = exp([w]x) R. */
function girar(R, w) {
  const th = Math.hypot(w[0], w[1], w[2]);
  const a = th < 1e-12 ? 1 : Math.sin(th) / th, b = th < 1e-12 ? 0.5 : (1 - Math.cos(th)) / (th * th);
  const K = [[0, -w[2], w[1]], [w[2], 0, -w[0]], [-w[1], w[0], 0]];
  const K2 = K.map((l, i) => l.map((_, j) => K[i][0] * K[0][j] + K[i][1] * K[1][j] + K[i][2] * K[2][j]));
  const E = K.map((l, i) => l.map((v, j) => (i === j ? 1 : 0) + a * v + b * K2[i][j]));
  return E.map((l) => [0, 1, 2].map((j) => l[0] * R[0][j] + l[1] * R[1][j] + l[2] * R[2][j]));
}

/* O ajuste fino (Levenberg-Marquardt, derivadas numéricas): a rotação, a posição e a lente que
   levam os quatro cantos o mais perto possível dos pontos marcados (com um puxão fraco para a lente comum). */
function ajustar(p0, mundo, pontos, f0, M) {
  const montar = (q) => ({ R: girar(p0.R, q.slice(0, 3)), t: [p0.t[0] + q[3], p0.t[1] + q[4], p0.t[2] + q[5]], f: p0.f * Math.exp(q[6]), cx: p0.cx, cy: p0.cy });
  const residuos = (q) => {
    const p = montar(q), r = [];
    for (let i = 0; i < 4; i++) {
      const [u, v, z] = projetar(p, mundo[i][0], 0, mundo[i][1]);
      if (!(z > 0)) return null;
      r.push(u - pontos[i][0], v - pontos[i][1]);
    }
    r.push(0.005 * M * Math.log(p.f / f0));
    return r;
  };
  const soma = (r) => r.reduce((s, v) => s + v * v, 0);
  let q = [0, 0, 0, 0, 0, 0, 0];
  let r = residuos(q);
  if (!r) return p0;
  let custo = soma(r), mu = 1e-3;
  for (let it = 0; it < 40 && custo > 1e-10; it++) {
    const J = q.map((_, k) => {
      const passo = k < 3 ? 1e-6 : k < 6 ? 1e-6 * (1 + Math.abs(p0.t[k - 3])) : 1e-6;
      const q2 = q.slice(); q2[k] += passo;
      const r2 = residuos(q2);
      return r2 ? r2.map((v, i) => (v - r[i]) / passo) : null;
    });
    if (J.some((c) => !c)) break;
    const A = J.map((a) => J.map((b) => a.reduce((s, v, i) => s + v * b[i], 0)));
    const g = J.map((a) => a.reduce((s, v, i) => s + v * r[i], 0));
    let melhorou = false;
    for (let tentativa = 0; tentativa < 8 && !melhorou; tentativa++) {
      const delta = resolver(A.map((l, i) => l.map((v, j) => v + (i === j ? mu * (A[i][i] + 1e-9) : 0))), g.map((v) => -v));
      if (!delta) { mu *= 10; continue; }
      const q2 = q.map((v, i) => v + delta[i]);
      const r2 = residuos(q2);
      if (r2 && soma(r2) < custo) { q = q2; r = r2; custo = soma(r2); mu = Math.max(1e-9, mu / 3); melhorou = true; } else mu *= 10;
    }
    if (!melhorou) break;
  }
  return montar(q);
}

/* As duas lentes que a homografia (centrada) pede: eixos perpendiculares e eixos do mesmo tamanho. */
function lentesDaConta(H) {
  const [h11, h12, , h21, h22, , h31, h32] = H;
  const lentes = [];
  const orto = -(h11 * h12 + h21 * h22) / (h31 * h32);
  if (Number.isFinite(orto) && orto > 0) lentes.push(Math.sqrt(orto));
  const igual = (h11 * h11 + h21 * h21 - h12 * h12 - h22 * h22) / (h32 * h32 - h31 * h31);
  if (Number.isFinite(igual) && igual > 0) lentes.push(Math.sqrt(igual));
  return lentes;
}

/**
 * A câmera da foto.
 *   pontos: os 4 pontos marcados, em pixels da foto ([u, v], u para a direita e v para baixo),
 *           na ordem dos nomes (fundo esq., fundo dir., frente dir., frente esq.) -- girados por `giro`.
 *   largura, altura: o tamanho da foto em pixels.
 *   sala: {largura, comprimento} do projeto, em metros.
 *   opcoes: {giro: 0-3, frente: true (os 4 cantos) | false (a frente ficou fora)}.
 * Devolve {ok, motivo, f, R, t, C, cx, cy, erro (fração da diagonal), mundo (o chão de cada ponto),
 * profundidade (no "a frente ficou fora": quantos metros do fundo os pontos de baixo estão)}.
 */
export function cameraDaFoto(pontos, largura, altura, sala, opcoes = {}) {
  const giro = ((opcoes.giro || 0) % 4 + 4) % 4;
  const frente = opcoes.frente !== false;
  const cx = largura / 2, cy = altura / 2;
  const M = Math.max(largura, altura);
  const diagonal = Math.hypot(largura, altura);
  const px = pontos.map(([u, v]) => [u - cx, v - cy]);
  const sala4 = cantosDaSala(sala.largura, sala.comprimento);
  const canto = (k) => sala4[(k + giro) % 4];
  const falha = (motivo) => ({ ok: false, motivo });

  // o chão de cada ponto
  let mundo = [0, 1, 2, 3].map(canto);
  let profundidade = null;
  let fDaConta = null;
  if (!frente) {
    // os pontos de baixo andam pela linha das paredes, a uma distância L do fundo (que a foto diz)
    const p0 = canto(0), p1 = canto(1), p2 = canto(2);
    const lado = Math.hypot(p2[0] - p1[0], p2[1] - p1[1]);
    const dir = [(p2[0] - p1[0]) / lado, (p2[1] - p1[1]) / lado];
    const unidade = [p0, p1, [p1[0] + dir[0], p1[1] + dir[1]], [p0[0] + dir[0], p0[1] + dir[1]]];
    const G = homografia(unidade, px);
    if (!G) return falha("pontos");
    // só a conta dos eixos perpendiculares vale aqui: o tamanho de um dos eixos é o que se procura
    const orto = -(G[0] * G[1] + G[3] * G[4]) / (G[6] * G[7]);
    let f;
    if (Number.isFinite(orto) && orto > 0) f = Math.sqrt(orto);
    else if (Math.abs(G[6]) < 1e-9 || Math.abs(G[7]) < 1e-9) f = 0.78 * M; // de frente para o chão: a foto não diz a lente
    else return falha("retangulo"); // não fecha com lente nenhuma (os pontos de baixo mais juntos que os de cima, por exemplo)
    // o eixo da profundidade é o x ou o z do chão (conforme o giro): a coluna dele na homografia
    const eixoProf = Math.abs(dir[0]) > 0.5 ? 0 : 1;
    const a = [G[eixoProf] / f, G[3 + eixoProf] / f, G[6 + eixoProf]];
    const b = [G[1 - eixoProf] / f, G[4 - eixoProf] / f, G[7 - eixoProf]];
    profundidade = norma(a) / norma(b);
    if (!(profundidade > 0.2 && profundidade < 1000)) return falha("retangulo");
    mundo = [p0, p1, [p1[0] + dir[0] * profundidade, p1[1] + dir[1] * profundidade], [p0[0] + dir[0] * profundidade, p0[1] + dir[1] * profundidade]];
    fDaConta = f;
  }

  const H = homografia(mundo, px);
  if (!H) return falha("pontos");
  // de que lado da câmera está o chão: o sinal que põe os pontos marcados na frente dela
  const w = mundo.map(([x, z]) => H[6] * x + H[7] * z + H[8]);
  if (!(w.every((v) => v > 0) || w.every((v) => v < 0))) return falha("pontos");
  const sinal = w[0] > 0 ? 1 : -1;

  const pose = (f) => {
    const d = decompor(H, f, sinal);
    return d ? { ...d, f, cx, cy } : null;
  };
  const f0 = 0.78 * M; // a lente comum de celular (uns 26 mm)
  const custo = (f) => {
    const p = pose(f);
    if (!p) return Infinity;
    // o erro em pixels, com um empurrão leve para a lente comum quando a foto não decide
    return erroDosPontos(p, mundo, pontos) + 0.004 * M * Math.log(f / f0) ** 2;
  };

  let f;
  if (fDaConta) {
    f = fDaConta;
  } else {
    // as lentes da conta e uma varredura (de grande-angular a zoom), e depois o ajuste fino
    const candidatas = [...lentesDaConta(H)];
    for (let i = 0; i <= 64; i++) candidatas.push(M * 0.25 * Math.pow(24, i / 64));
    let melhor = f0, menor = custo(f0);
    for (const c of candidatas) {
      if (!(c > 0.2 * M && c < 8 * M)) continue;
      const k = custo(c);
      if (k < menor) { menor = k; melhor = c; }
    }
    let a = melhor / 1.06, b = melhor * 1.06;
    const ouro = (Math.sqrt(5) - 1) / 2;
    for (let it = 0; it < 40; it++) {
      const c = b - ouro * (b - a), d = a + ouro * (b - a);
      if (custo(c) < custo(d)) b = d; else a = c;
    }
    f = (a + b) / 2;
    if (custo(melhor) < custo(f)) f = melhor;
  }

  let p = pose(f);
  if (!p) return falha("pontos");
  // com os quatro cantos (8 números para 7 incógnitas), o ajuste fino da câmera inteira
  if (!fDaConta) p = ajustar(p, mundo, pontos, f0, M);
  const { R, t } = p;
  f = p.f;
  // onde a câmera está no mundo: C = -R^T t; acima do chão e de pé (o "para cima" do mundo para cima na foto)
  const C = [0, 1, 2].map((i) => -(R[0][i] * t[0] + R[1][i] * t[1] + R[2][i] * t[2]));
  if (!(C[1] > 0.05) || R[1][1] > 0.35) return falha("invertido");
  const erro = erroDosPontos(p, mundo, pontos) / diagonal;
  return { ok: true, motivo: erro > 0.025 ? "torto" : "", f, R, t, C, cx, cy, erro, mundo, profundidade, largura, altura };
}

/** A câmera da foto como a do three.js: {fov (graus, vertical), aspecto, posicao [3], base [9] (eixos x, y, z da câmera)}. */
export function cameraThree(pose) {
  const { R, C, f, largura, altura } = pose;
  // o x da câmera é a 1ª linha de R; o y do three.js aponta para cima (o da foto, para baixo) e ele olha para -z
  return {
    fov: (2 * Math.atan(altura / 2 / f) * 180) / Math.PI,
    aspecto: largura / altura,
    posicao: C,
    eixos: [R[0], R[1].map((v) => -v), R[2].map((v) => -v)],
  };
}
