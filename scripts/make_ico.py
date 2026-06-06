from __future__ import annotations

from pathlib import Path

from PIL import Image


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    src = repo / "assets" / "app.png"
    dst = repo / "installer" / "payload" / "app.ico"
    dst.parent.mkdir(parents=True, exist_ok=True)

    im = Image.open(src).convert("RGBA")
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    imgs = [im.resize(s, Image.LANCZOS) for s in sizes]
    imgs[0].save(dst, format="ICO", sizes=sizes)
    print(f"Wrote {dst}")


if __name__ == "__main__":
    main()

