#!/usr/bin/env python3
"""
Build caricatures for secret-santa.html.

  python3 scripts/build-caricatures.py [--src caricatures-src] [--participants participants.txt]

- Reads one image per person from caricatures-src/ (named by full Georgian name,
  .png/.jpg/.jpeg/.jfif/.webp). That folder is private and git-ignored.
- Center-crops to a square, resizes to 800×800, saves WebP (<150 KB) as
  caricatures/01.webp, 02.webp, ... numbered in a RANDOM order.
- Rewrites the CARICATURES object in secret-santa.html between
  // CARICATURES:START and // CARICATURES:END. Keys are a salted SHA-256 of the
  normalized name (not the name itself), so no participant names end up in the repo.
- Safe to re-run: caricatures/ and the mapping are rebuilt from scratch each time.
- Prints a report (in Georgian). The participant list comes from participants.txt
  (git-ignored) or is pasted into the terminal.
"""
import argparse
import hashlib
import io
import json
import re
import secrets
import sys
import unicodedata
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
EXTS = {'.png', '.jpg', '.jpeg', '.jfif', '.webp'}
SIZE = 800
MAX_BYTES = 150 * 1024
BACKGROUND = (0xF5, 0xF3, 0xEF)  # off-white, used to flatten transparency
# Must match CARICATURE_SALT and caricatureKey() in secret-santa.html.
SALT = 'arci-santa-2026|'
HEADER_RE = re.compile(r'e-?mail|სახელი|ელ[- ]?ფოსტა', re.I)


def normalize(name: str) -> str:
    """NFC, trim, collapse whitespace, lowercase (affects Latin; Georgian has no case)."""
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFC', name)).strip().lower()


def key_for(name: str) -> str:
    return hashlib.sha256((SALT + normalize(name)).encode('utf-8')).hexdigest()[:16]


def parse_participants(text: str) -> dict:
    """'name', 'name, email' or 'name<TAB>email' per line → {normalized: original name}."""
    out = {}
    lines = [l for l in text.splitlines() if l.strip(' \t,')]
    for i, line in enumerate(lines):
        if i == 0 and '@' not in line and HEADER_RE.search(line):
            continue
        name = re.split(r'[\t,]', line, maxsplit=1)[0]
        name = re.sub(r'\s+', ' ', unicodedata.normalize('NFC', name)).strip().strip('"')
        if name:
            out.setdefault(normalize(name), name)
    return out


def read_participants(path: Path):
    if path.exists():
        print(f'მონაწილეების სია წაკითხულია ფაილიდან: {path.name}')
        return parse_participants(path.read_text(encoding='utf-8'))
    if not sys.stdin.isatty():
        return None
    print('ჩასვით მონაწილეების სია (თითო ხაზზე „სახელი“ ან „სახელი, ელ-ფოსტა“).')
    print('დასრულებისთვის დატოვეთ ცარიელი ხაზი (ან დააჭირეთ Enter-ს გამოსატოვებლად):')
    lines = []
    for line in sys.stdin:
        if not line.strip():
            break
        lines.append(line.rstrip('\n'))
    return parse_participants('\n'.join(lines)) if lines else None


def encode(src: Path) -> bytes:
    im = Image.open(src)
    im = ImageOps.exif_transpose(im)
    if im.mode in ('RGBA', 'LA', 'P'):
        im = im.convert('RGBA')
        bg = Image.new('RGB', im.size, BACKGROUND)
        bg.paste(im, mask=im.getchannel('A'))
        im = bg
    else:
        im = im.convert('RGB')
    im = ImageOps.fit(im, (SIZE, SIZE), Image.LANCZOS, centering=(0.5, 0.5))
    data = b''
    for quality in (80, 74, 68, 62, 56, 50):
        buf = io.BytesIO()
        im.save(buf, 'WEBP', quality=quality, method=6)  # no EXIF/metadata is written
        data = buf.getvalue()
        if len(data) <= MAX_BYTES:
            break
    return data


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--src', default=ROOT / 'caricatures-src', type=Path)
    ap.add_argument('--out', default=ROOT / 'caricatures', type=Path)
    ap.add_argument('--html', default=ROOT / 'secret-santa.html', type=Path)
    ap.add_argument('--participants', default=ROOT / 'participants.txt', type=Path)
    args = ap.parse_args()

    if not args.src.is_dir():
        sys.exit(f'საქაღალდე ვერ მოიძებნა: {args.src}')

    participants = read_participants(args.participants)

    # Collect source images; one per normalized name.
    images = {}
    duplicates = []
    for f in sorted(args.src.iterdir()):
        if f.suffix.lower() not in EXTS or not f.is_file():
            continue
        k = normalize(f.stem)
        if k in images:
            duplicates.append(f.name)
            continue
        images[k] = f

    unmatched = []
    if participants is not None:
        unmatched = [f.name for k, f in images.items() if k not in participants]
        images = {k: f for k, f in images.items() if k in participants}

    # Random, non-alphabetical numbering.
    order = list(images.items())
    secrets.SystemRandom().shuffle(order)
    width = max(2, len(str(len(order))))

    # Rebuild output folder from scratch.
    args.out.mkdir(exist_ok=True)
    for old in args.out.glob('*.webp'):
        old.unlink()

    mapping = {}
    processed = []
    for i, (k, f) in enumerate(order, 1):
        num = str(i).zfill(width)
        data = encode(f)
        (args.out / f'{num}.webp').write_bytes(data)
        mapping[key_for(f.stem)] = num
        processed.append((f.name, len(data)))

    # Rewrite the mapping block in the HTML (sorted by key so the order reveals nothing).
    html = args.html.read_text(encoding='utf-8')
    body = ',\n'.join(f'  {json.dumps(k)}: {json.dumps(v)}' for k, v in sorted(mapping.items()))
    block = '// CARICATURES:START\nconst CARICATURES = {\n' + (body + '\n' if body else '') + '};\n// CARICATURES:END'
    new_html, n = re.subn(r'// CARICATURES:START.*?// CARICATURES:END', lambda _: block, html, flags=re.S)
    if n != 1:
        sys.exit('secret-santa.html-ში ვერ მოიძებნა // CARICATURES:START … // CARICATURES:END ბლოკი.')
    args.html.write_text(new_html, encoding='utf-8')

    # ---- Report ----
    print()
    print(f'✅ დამუშავდა {len(processed)} სურათი → {args.out.name}/')
    for name, size in sorted(processed):
        print(f'   • {name}  ({size // 1024} KB)')
    if duplicates:
        print(f'\n⚠️  გამოტოვებულია (იგივე სახელი მეორედ): {", ".join(duplicates)}')
    if participants is None:
        print('\nℹ️  მონაწილეების სია არ არის მითითებული — სახელების შემოწმება გამოტოვებულია.')
        print('   შექმენით participants.txt ან ჩასვით სია სკრიპტის გაშვებისას.')
    else:
        if unmatched:
            print(f'\n❌ სურათები, რომლებიც არცერთ მონაწილეს არ ემთხვევა ({len(unmatched)}) — შეასწორეთ ფაილის სახელი:')
            for name in unmatched:
                print(f'   • {name}')
        else:
            print('\n✅ ყველა სურათი ემთხვევა მონაწილეს.')
        missing = [orig for k, orig in participants.items() if k not in images]
        if missing:
            print(f'\n🖼️  მონაწილეები, რომლებსაც ჯერ არ აქვთ კარიკატურა ({len(missing)}):')
            for name in missing:
                print(f'   • {name}')
        else:
            print('\n✅ ყველა მონაწილეს აქვს კარიკატურა.')
    print(f'\nგანახლდა: {args.html.name} (CARICATURES — {len(mapping)} ჩანაწერი)')


if __name__ == '__main__':
    main()
