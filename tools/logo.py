#!/usr/bin/env python3
"""Prépare un logo pour une fiche Premium.

Usage : python3 -I tools/logo.py <image> <nom-du-fichier-sans-extension>
Exemple : python3 -I tools/logo.py ~/Downloads/logo-run-nature.png run-nature

- supprime les marges vides autour du logo (fond transparent ou blanc uni)
- réduit l'image pour tenir dans 600 x 300 px (jamais agrandie, ratio conservé)
- enregistre assets/logos/<nom>.webp (transparence conservée)
Ensuite, dans data/entreprises.json : "logo": "<nom>.webp"
"""
import os
import sys

from PIL import Image, ImageChops

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_L, MAX_H = 600, 300


def rogner(img):
    """Retire les marges transparentes, ou blanches si l'image n'a pas de transparence."""
    img = img.convert("RGBA")
    alpha = img.getchannel("A")
    if alpha.getextrema()[0] < 255:  # il y a de la transparence
        boite = alpha.getbbox()
    else:
        fond = Image.new("RGBA", img.size, (255, 255, 255, 255))
        diff = ImageChops.difference(img, fond).convert("L").point(lambda v: 255 if v > 12 else 0)
        boite = diff.getbbox()
    return img.crop(boite) if boite else img


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    src, nom = sys.argv[1], sys.argv[2]
    if src.lower().endswith(".svg"):
        raise SystemExit("SVG : copiez-le tel quel dans assets/logos/ (il s'adapte déjà à toutes les tailles).")
    img = rogner(Image.open(src))
    img.thumbnail((MAX_L, MAX_H), Image.LANCZOS)
    os.makedirs(os.path.join(ROOT, "assets", "logos"), exist_ok=True)
    dest = os.path.join(ROOT, "assets", "logos", f"{nom}.webp")
    img.save(dest, "WEBP", quality=90, method=6)
    print(f"OK : {dest} ({img.size[0]} x {img.size[1]} px, {os.path.getsize(dest) // 1024} Ko)")
    print(f'À ajouter dans la fiche : "logo": "{nom}.webp"')


if __name__ == "__main__":
    main()
