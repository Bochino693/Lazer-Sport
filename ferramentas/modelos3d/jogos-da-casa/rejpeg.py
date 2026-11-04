"""Regrava as texturas PNG de um .glb como JPEG (as artes não têm transparência).

Uso: python3 -I jpeg_no_glb.py entrada.glb saida.glb [qualidade]
A geometria, os nomes e os materiais ficam iguais: só os bufferViews das
imagens trocam de conteúdo, e o bloco binário é remontado com os novos
deslocamentos (alinhados de 4 em 4 bytes, como a especificação pede).
"""
import io
import json
import struct
import sys

from PIL import Image

entrada, saida = sys.argv[1], sys.argv[2]
qualidade = int(sys.argv[3]) if len(sys.argv) > 3 else 90
LADO = int(sys.argv[4]) if len(sys.argv) > 4 else 4096
b = open(entrada, "rb").read()
n_json, = struct.unpack("<I", b[12:16])
gltf = json.loads(b[20:20 + n_json])
n_bin, = struct.unpack("<I", b[20 + n_json:24 + n_json])
binario = b[28 + n_json:28 + n_json + n_bin]

views = gltf["bufferViews"]
conteudo = [binario[v.get("byteOffset", 0):v.get("byteOffset", 0) + v["byteLength"]] for v in views]
for imagem in gltf.get("images", []):
    i = imagem["bufferView"]
    if imagem.get("mimeType") not in ("image/png", "image/jpeg"):
        continue
    png = Image.open(io.BytesIO(conteudo[i]))
    if max(png.size) > LADO: png.thumbnail((LADO, LADO), Image.LANCZOS)
    if png.mode in ("RGBA", "LA", "P") and "A" in png.getbands():
        continue  # com transparência: fica PNG
    saida_jpg = io.BytesIO()
    png.convert("RGB").save(saida_jpg, "JPEG", quality=qualidade, optimize=True, progressive=False)
    conteudo[i] = saida_jpg.getvalue()
    imagem["mimeType"] = "image/jpeg"

novo = bytearray()
for v, dados in zip(views, conteudo):
    while len(novo) % 4:
        novo += b"\0"
    v["byteOffset"] = len(novo)
    v["byteLength"] = len(dados)
    novo += dados
while len(novo) % 4:
    novo += b"\0"
gltf["buffers"] = [{"byteLength": len(novo)}]

texto = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
while len(texto) % 4:
    texto += b" "
total = 12 + 8 + len(texto) + 8 + len(novo)
with open(saida, "wb") as f:
    f.write(struct.pack("<4sII", b"glTF", 2, total))
    f.write(struct.pack("<II", len(texto), 0x4E4F534A) + texto)
    f.write(struct.pack("<II", len(novo), 0x004E4942) + bytes(novo))
print(f"{entrada}: {len(b) // 1024} KB -> {saida}: {total // 1024} KB")
