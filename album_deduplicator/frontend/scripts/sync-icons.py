from pathlib import Path
import shutil

from PIL import Image


ICON_SIZES = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)]


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    frontend_root = script_dir.parent

    build_icon_dir = frontend_root / "build" / "icons"
    source_png = build_icon_dir / "app-icon-source.png"
    build_ico = build_icon_dir / "app-icon.ico"
    public_icon = frontend_root / "public" / "app-icon.png"
    desktop_png = frontend_root / "electron" / "assets" / "icons" / "app-icon.png"
    desktop_ico = frontend_root / "electron" / "assets" / "icons" / "app-icon.ico"

    if not source_png.is_file():
        raise FileNotFoundError(f"Missing source icon: {source_png}")

    for destination in (build_ico, public_icon, desktop_png, desktop_ico):
        destination.parent.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(source_png, public_icon)
    shutil.copyfile(source_png, desktop_png)

    with Image.open(source_png) as source_image:
        icon_image = source_image.convert("RGBA")
        icon_image.save(build_ico, format="ICO", sizes=ICON_SIZES)
        icon_image.save(desktop_ico, format="ICO", sizes=ICON_SIZES)

    print(f"Synced desktop icon assets from {source_png.name}")


if __name__ == "__main__":
    main()
