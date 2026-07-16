"""Create the Windows .ico asset used by the packaged executable."""

from pathlib import Path

from PIL import Image, ImageDraw


root = Path(__file__).resolve().parents[1]
target = root / "windows" / "clipforge.ico"
size = 256
image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((8, 8, 248, 248), radius=58, fill="#7C3AED")
draw.line((76, 58, 76, 198), fill="#FFFFFF", width=24)
draw.polygon(((104, 67), (104, 189), (198, 128)), outline="#FFFFFF", width=20)
image.save(target, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(target)
