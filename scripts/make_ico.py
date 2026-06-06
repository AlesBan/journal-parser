from __future__ import annotations

from pathlib import Path

from PIL import Image


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    src = repo / "assets" / "app.png"
    dst = repo / "installer" / "payload" / "app.ico"
    dst.parent.mkdir(parents=True, exist_ok=True)

    # Keep the icon exactly "as is" (no background removal, no sharpening).
    # We embed only the 256x256 frame and let Windows scale it as needed.
    im = Image.open(src).convert("RGBA")
    sizes = [(256, 256)]
    im.save(dst, format="ICO", sizes=sizes)
    print(f"Wrote {dst}")


if __name__ == "__main__":
    main()

