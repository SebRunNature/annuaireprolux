#!/usr/bin/env python3
"""Importe un export Overpass (JSON) dans data/entreprises.json.

Usage : python3 -I tools/import_osm.py export.json [groupe]
- fusionne les doublons (même nom, même site web ou même ref:caclr)
- ne garde que les fiches avec une commune (addr:city) ; les autres vont dans
  data/osm_a_completer.json pour être complétées plus tard
- range chaque fiche dans un groupe / métier du site
Les fiches existantes (hors exemples fictifs) sont conservées.
"""
import json
import os
import re
import sys
import unicodedata
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = sys.argv[1]

# artisanat OSM -> (groupe, métier du site)
CRAFT = {
    "plumber": ("batiment", "plombier"),
    "electrician": ("batiment", "electricien"),
    "hvac": ("batiment", "chauffagiste"),
    "painter": ("batiment", "peintre"),
    "carpenter": ("batiment", "menuisier"),
    "roofer": ("batiment", "couvreur"),
    "tiler": ("batiment", "carreleur"),
    "glaziery": ("batiment", "vitrier"),
    "plasterer": ("batiment", "platrier"),
    "builder": ("batiment", "construction"),
}
SINGULIER = {
    "plombier": "Plombier", "electricien": "Électricien", "chauffagiste": "Chauffagiste",
    "peintre": "Peintre", "menuisier": "Menuisier", "couvreur": "Couvreur",
    "carreleur": "Carreleur", "vitrier": "Vitrier", "platrier": "Plâtrier",
    "construction": "Entreprise de construction",
}
# Fournisseurs d'énergie, grossistes, fabricants : ce ne sont pas des artisans
EXCLUS = {"enovos", "metro", "van marcke", "viessmann", "societe electrique de l our"}


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\b(sarl|sarls|sa|s a|s a r l|sàrl|cie|et|and)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def domaine(url):
    if not url:
        return ""
    if "://" not in url:
        url = "https://" + url
    h = (urlparse(url).netloc or "").lower()
    return h[4:] if h.startswith("www.") else h


def propre_tel(t):
    if not t:
        return ""
    t = t.strip()
    t = re.sub(r"^00\s*352", "+352", t)
    return t


def lire(el):
    t = el.get("tags", {})
    craft = t.get("craft", "")
    if craft not in CRAFT:
        return None
    nom = (t.get("name") or "").strip()
    if not nom or norm(nom) in EXCLUS:
        return None
    rue = t.get("addr:street", "")
    num = t.get("addr:housenumber", "")
    site = t.get("website") or t.get("contact:website") or ""
    if site and "://" not in site:
        site = "https://" + site
    return {
        "nom": nom,
        "craft": craft,
        "ville": (t.get("addr:city") or "").strip(),
        "adresse": f"{num} {rue}".strip() if rue else "",
        "code_postal": ("L-" + t["addr:postcode"]) if t.get("addr:postcode") else "",
        "telephone": propre_tel(t.get("phone") or t.get("contact:phone") or t.get("mobile") or ""),
        "email": (t.get("email") or t.get("contact:email") or "").strip(),
        "site": site.strip(),
        "caclr": t.get("ref:caclr", ""),
        "osm": f"{el['type']}/{el['id']}",
        "poids": len(t),
    }


with open(SRC, encoding="utf-8") as f:
    brut = json.load(f)
items = [x for x in (lire(e) for e in brut["elements"]) if x]

# --- fusion des doublons (union-find sur nom normalisé, domaine web, ref:caclr)
parent = list(range(len(items)))


def find(i):
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i


vus = {}
for i, it in enumerate(items):
    cles = [("n", norm(it["nom"]))]
    if it["site"]:
        cles.append(("d", domaine(it["site"])))
    if it["caclr"]:
        cles.append(("c", it["caclr"]))
    for c in cles:
        if c in vus:
            parent[find(i)] = find(vus[c])
        else:
            vus[c] = i

groupes = {}
for i, it in enumerate(items):
    groupes.setdefault(find(i), []).append(it)

fiches, a_completer = [], []
for membres in groupes.values():
    membres.sort(key=lambda m: -m["poids"])
    base = dict(membres[0])
    for m in membres[1:]:
        for k in ("ville", "adresse", "code_postal", "telephone", "email", "site"):
            if not base[k] and m[k]:
                base[k] = m[k]
    g, metier = CRAFT[base["craft"]]
    fiche = {
        "nom": base["nom"], "groupe": g, "metier": metier, "ville": base["ville"],
        "adresse": base["adresse"], "code_postal": base["code_postal"],
        "telephone": base["telephone"], "email": base["email"], "site": base["site"],
        "description": f"{SINGULIER[metier]} à {base['ville']}." if base["ville"] else "",
        "source": "OpenStreetMap", "osm": base["osm"],
    }
    fiche = {k: v for k, v in fiche.items() if v != ""}
    (fiches if base["ville"] else a_completer).append(fiche)

fiches.sort(key=lambda f: f["nom"].lower())
a_completer.sort(key=lambda f: f["nom"].lower())

chemin = os.path.join(ROOT, "data", "entreprises.json")
with open(chemin, encoding="utf-8") as f:
    existantes = json.load(f)
existantes = [e for e in existantes if "EXEMPLE" not in e.get("description", "").upper()]
noms = {norm(e["nom"]) + "|" + norm(e["ville"]) for e in existantes}
nouvelles = [f for f in fiches if norm(f["nom"]) + "|" + norm(f["ville"]) not in noms]

with open(chemin, "w", encoding="utf-8") as f:
    json.dump(existantes + nouvelles, f, ensure_ascii=False, indent=2)
with open(os.path.join(ROOT, "data", "osm_a_completer.json"), "w", encoding="utf-8") as f:
    json.dump(a_completer, f, ensure_ascii=False, indent=2)

print(f"éléments lus : {len(brut['elements'])}, retenus : {len(items)}, après fusion : {len(fiches) + len(a_completer)}")
print(f"ajoutées au site : {len(nouvelles)} ; sans commune (à compléter) : {len(a_completer)}")
