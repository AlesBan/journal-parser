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
    # Sharpen a bit for small sizes so it stays crisp in titlebar/taskbar.
    def _render(sz: tuple[int, int]) -> Image.Image:
        x = im.resize(sz, Image.LANCZOS)
        if sz[0] <= 32:
            # Unsharp mask: a light touch to avoid halos.
            from PIL import ImageFilter  # noqa: PLC0415

            x = x.filter(ImageFilter.UnsharpMask(radius=1, percent=180, threshold=2))
        return x

    imgs = [_render(s) for s in sizes]
    imgs[0].save(dst, format="ICO", sizes=sizes)
    print(f"Wrote {dst}")


if __name__ == "__main__":
    main()

