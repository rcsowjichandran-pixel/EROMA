"""Download and normalize the catalog category photos into the frontend assets."""
import hashlib
import json
import re
import ssl
from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen
import certifi

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent
DEST = ROOT / "frontend" / "public" / "images" / "categories"
MANIFEST = DEST / "image_sources.json"


def slugify(value):
    value = value.lower().replace("&", " ")
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def main():
    sources = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if len(sources) != 48:
        raise SystemExit(f"Expected 48 distinct categories; found {len(sources)}")

    hashes = {}
    for category, info in sources.items():
        path = DEST / f"{slugify(category)}.jpg"
        if path.exists():
            with Image.open(path) as existing:
                if existing.size == (1200, 800):
                    print(f"Already saved: {path.name}")
                    continue
        request = Request(
            info["url"],
            headers={"User-Agent": "Mozilla/5.0 (compatible; EROMA-Catalog/1.0)"},
        )
        with urlopen(
            request, timeout=35, context=ssl.create_default_context(cafile=certifi.where())
        ) as response:
            data = response.read(20_000_001)
        if len(data) > 20_000_000:
            raise SystemExit(f"Image too large: {category}")
        try:
            with Image.open(BytesIO(data)) as source:
                source.seek(0)
                image = ImageOps.exif_transpose(source).convert("RGB")
                image = ImageOps.fit(
                    image, (1200, 800), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5)
                )
        except Exception as error:
            raise SystemExit(f"Cannot decode {category}: {info['url']} ({error})")

        output = BytesIO()
        image.save(output, format="JPEG", quality=88, optimize=True, progressive=True)
        encoded = output.getvalue()
        digest = hashlib.sha256(encoded).hexdigest()
        if digest in hashes:
            raise SystemExit(f"Duplicate photo for {category} and {hashes[digest]}")
        hashes[digest] = category
        path.write_bytes(encoded)
        print(f"{category}: {path.name} ({len(encoded) // 1024} KB)")

    print(f"Saved {len(hashes)} unique 1200x800 images in {DEST}")


if __name__ == "__main__":
    main()
