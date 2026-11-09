// O projeto na foto (core/static/site/projeto3d/foto3d.js), conferido de fora: node core/tests_js/foto3d.mjs
// Tira "fotos" de mentira (uma câmera conhecida olhando a sala), marca os pontos onde eles cairiam
// e confere que a conta acha a mesma câmera -- e que a câmera do three.js leva os cantos aos mesmos pixels.
// Sai com código 1 e a lista dos problemas quando algo não confere.
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const ESTATICO = path.join(AQUI, "..", "static");
const foto = await import(pathToFileURL(path.join(ESTATICO, "site/projeto3d/foto3d.js")));
const T = await import(pathToFileURL(path.join(ESTATICO, "vendor/three/three.module.min.js")));
const problemas = [];
const confere = (cond, msg) => { if (!cond) problemas.push(msg); };
const perto = (a, b, tol) => Math.abs(a - b) <= tol;

// uma câmera de verdade (a da visão computacional: x direita, y para baixo, z para frente)
function olhar(C, alvo) {
  const z = alvo.map((v, i) => v - C[i]);
  const Z = z.map((v) => v / Math.hypot(...z));
  let X = [Z[1] * 0 - Z[2] * 1, Z[2] * 0 - Z[0] * 0, Z[0] * 1 - Z[1] * 0];
  X = X.map((v) => v / Math.hypot(...X));
  const Y = [Z[1] * X[2] - Z[2] * X[1], Z[2] * X[0] - Z[0] * X[2], Z[0] * X[1] - Z[1] * X[0]];
  const R = [X, Y, Z];
  return { R, t: R.map((l) => -(l[0] * C[0] + l[1] * C[1] + l[2] * C[2])) };
}

const W = 12, D = 10, largura = 1600, altura = 1200;
const sala = { largura: W, comprimento: D };
const casos = [
  { C: [2, 2.5, 9], alvo: [0, 0, -2], f: 1100, nome: "da porta, meio de lado" },
  { C: [-4, 3.2, 13], alvo: [1, 0, -1], f: 1500, nome: "de longe, com zoom" },
  { C: [0, 6, 4], alvo: [0, 0, -3], f: 800, nome: "do alto, de frente" },
  { C: [7, 1.6, 6], alvo: [-1, 0.5, -2], f: 1250, nome: "de um canto, na altura do olho" },
];

for (const caso of casos) {
  const { R, t } = olhar(caso.C, caso.alvo);
  const verdade = { R, t, f: caso.f, cx: largura / 2, cy: altura / 2 };
  const cantos = foto.cantosDaSala(W, D).map(([x, z]) => foto.projetar(verdade, x, 0, z).slice(0, 2));

  // 1. os quatro cantos: a lente e o lugar da câmera
  const r = foto.cameraDaFoto(cantos, largura, altura, sala, { frente: true });
  confere(r.ok && !r.motivo, `${caso.nome}: não achou a câmera (${r.motivo})`);
  if (r.ok) {
    confere(perto(r.f, caso.f, caso.f * 0.01), `${caso.nome}: lente ${r.f.toFixed(0)} em vez de ${caso.f}`);
    r.C.forEach((v, i) => confere(perto(v, caso.C[i], 0.03), `${caso.nome}: câmera em ${r.C.map((x) => x.toFixed(2))} em vez de ${caso.C}`));

    // 2. a câmera do three.js leva os cantos (e um ponto no alto) aos mesmos pixels
    const c3 = foto.cameraThree(r);
    const cam = new T.PerspectiveCamera(c3.fov, c3.aspecto, 0.05, 500);
    cam.position.fromArray(c3.posicao);
    cam.quaternion.setFromRotationMatrix(new T.Matrix4().makeBasis(...c3.eixos.map((e) => new T.Vector3(...e))));
    cam.updateMatrixWorld();
    const pontos = [...foto.cantosDaSala(W, D).map(([x, z]) => [x, 0, z]), [1.5, 2.2, -3]];
    for (const p of pontos) {
      const [u, v] = foto.projetar(verdade, ...p);
      const q = new T.Vector3(...p).project(cam);
      const u3 = ((q.x + 1) / 2) * largura, v3 = ((1 - q.y) / 2) * altura;
      confere(perto(u3, u, 1) && perto(v3, v, 1), `${caso.nome}: o three.js põe ${p} em ${u3.toFixed(1)},${v3.toFixed(1)} e a foto em ${u.toFixed(1)},${v.toFixed(1)}`);
    }
  }

  // 3. marcado meio torto (uns pixels): ainda acha, perto
  const torto = cantos.map(([u, v], i) => [u + [6, -5, 4, -7][i], v + [-4, 6, -6, 5][i]]);
  const rt = foto.cameraDaFoto(torto, largura, altura, sala, { frente: true });
  confere(rt.ok && rt.erro < 0.01, `${caso.nome}: marcado meio torto não fechou (${rt.motivo}, erro ${rt.erro})`);
  if (rt.ok) confere(Math.hypot(...rt.C.map((v, i) => v - caso.C[i])) < 1.2, `${caso.nome}: torto, a câmera foi para ${rt.C.map((x) => x.toFixed(2))}`);

  // 4. girado: a mesma foto lida com o projeto de lado (a sala D × W) bate com giro 1
  const deLado = foto.cantosDaSala(D, W).map(([x, z]) => foto.projetar(verdade, x, 0, z).slice(0, 2));
  const rg = foto.cameraDaFoto(deLado, largura, altura, sala, { frente: true, giro: 1 });
  confere(rg.ok && !rg.motivo && perto(rg.f, caso.f, caso.f * 0.01), `${caso.nome}: girado não fechou (${rg.motivo})`);

  // 5. trocado (esquerda <-> direita): a câmera ficaria debaixo do chão -- avisa
  const trocado = [cantos[1], cantos[0], cantos[3], cantos[2]];
  const rx = foto.cameraDaFoto(trocado, largura, altura, sala, { frente: true });
  confere(!rx.ok && rx.motivo === "invertido", `${caso.nome}: os pontos trocados passaram (${rx.motivo})`);
}

// 6. a frente fora da foto: os pontos de baixo a 6 m do fundo; com a câmera de lado, a foto diz a lente e a distância
{
  const caso = casos[0];
  const { R, t } = olhar(caso.C, caso.alvo);
  const verdade = { R, t, f: caso.f, cx: largura / 2, cy: altura / 2 };
  const L = 6;
  const pontos = [[-W / 2, -D / 2], [W / 2, -D / 2], [W / 2, -D / 2 + L], [-W / 2, -D / 2 + L]].map(([x, z]) => foto.projetar(verdade, x, 0, z).slice(0, 2));
  const r = foto.cameraDaFoto(pontos, largura, altura, sala, { frente: false });
  confere(r.ok && perto(r.profundidade, L, 0.05), `a frente fora: ${r.motivo} profundidade ${r.profundidade}`);
  if (r.ok) confere(perto(r.f, caso.f, caso.f * 0.01), `a frente fora: lente ${r.f}`);
  // o retângulo que não fecha (os de baixo mais juntos que os de cima, abrindo para o fundo)
  const aoContrario = [[500, 400], [1100, 400], [900, 1000], [700, 1000]];
  const rc = foto.cameraDaFoto(aoContrario, largura, altura, sala, { frente: false });
  confere(!rc.ok, "a frente fora: um trapézio que abre para o fundo passou");
}

// 7. a marcação de partida (a que a tela põe) dá uma câmera de pé
{
  const partida = [[0.28, 0.42], [0.72, 0.42], [0.96, 0.95], [0.04, 0.95]].map(([a, b]) => [a * largura, b * altura]);
  for (const frente of [true, false]) {
    const r = foto.cameraDaFoto(partida, largura, altura, { largura: 20, comprimento: 15 }, { frente });
    confere(r.ok && r.C[1] > 0.5, `a marcação de partida (frente ${frente}) não deu câmera (${r.motivo})`);
  }
}

if (problemas.length) {
  console.error(problemas.join("\n"));
  process.exit(1);
}
console.log("ok");
