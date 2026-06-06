from __future__ import annotations

from pathlib import Path

from collections import deque

from PIL import Image, ImageFilter


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    src = repo / "assets" / "app.png"
    dst = repo / "installer" / "payload" / "app.ico"
    dst.parent.mkdir(parents=True, exist_ok=True)

    im = Image.open(src).convert("RGBA")

    # Make only the *outer* white background transparent (flood-fill from corners),
    # so we don't accidentally erase the white paper inside the icon.
    w, h = im.size
    px = im.load()

    def is_bg(r: int, g: int, b: int, a: int) -> bool:
        return a > 0 and r >= 252 and g >= 252 and b >= 252

    q: deque[tuple[int, int]] = deque()
    seen = set()
    for seed in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
        q.append(seed)

    while q:
        x, y = q.popleft()
        if (x, y) in seen:
            continue
        seen.add((x, y))
        r, g, b, a = px[x, y]
        if not is_bg(r, g, b, a):
            continue
        px[x, y] = (r, g, b, 0)
        if x > 0:
            q.append((x - 1, y))
        if x < w - 1:
            q.append((x + 1, y))
        if y > 0:
            q.append((x, y - 1))
        if y < h - 1:
            q.append((x, y + 1))

    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    # Sharpen a bit for small sizes so it stays crisp in titlebar/taskbar.
    def _render(sz: tuple[int, int]) -> Image.Image:
        x = im.resize(sz, Image.LANCZOS)
        if sz[0] <= 32:
            x = x.filter(ImageFilter.UnsharpMask(radius=1, percent=180, threshold=2))
        return x

    imgs = [_render(s) for s in sizes]
    imgs[0].save(dst, format="ICO", sizes=sizes)
    print(f"Wrote {dst}")


if __name__ == "__main__":
    main()

