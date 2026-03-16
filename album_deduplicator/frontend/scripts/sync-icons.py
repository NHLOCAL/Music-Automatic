from pathlib import Path
import shutil

from PIL import Image


ICON_SIZES = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)]


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    frontend_root = script_dir.parent
    project_root = frontend_root.parent

    source_png = project_root / "9-Photoroom.png"
    public_icon = frontend_root / "public" / "app-icon.png"
    desktop_png = frontend_root / "electron" / "assets" / "icons" / "app-icon.png"
    desktop_ico = frontend_root / "electron" / "assets" / "icons" / "app-icon.ico"

    if not source_png.is_file():
        raise FileNotFoundError(f"Missing source icon: {source_png}")

    for destination in (public_icon, desktop_png, desktop_ico):
        destination.parent.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(source_png, public_icon)
    shutil.copyfile(source_png, desktop_png)

    with Image.open(source_png) as source_image:
        source_image.convert("RGBA").save(desktop_ico, format="ICO", sizes=ICON_SIZES)

    print("Synced desktop icon assets from 9-Photoroom.png")


if __name__ == "__main__":
    main()
