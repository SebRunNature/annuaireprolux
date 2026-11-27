#!/usr/bin/env python3
"""Importe un export Overpass (JSON) dans data/entreprises.json.

Usage : python3 -I tools/import_osm.py export.json
- classe chaque élément dans un groupe / métier du site (artisans du bâtiment, santé)
- fusionne les doublons d'une même commune (même nom, même site web ou même ref:caclr)
  sans fusionner des succursales de communes différentes
- ne garde dans le site que les fiches avec une commune (addr:city) ; les autres vont
  dans data/osm_a_completer.json pour être complétées plus tard
- conserve les fiches déjà présentes (hors exemples fictifs)
"""
import json
import os
import re
import sys
import unicodedata
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = sys.argv[1]

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
    "medecin-generaliste": "Médecin généraliste", "medecin-specialiste": "Médecin spécialiste",
    "medecin": "Médecin", "ophtalmologue": "Ophtalmologue", "dentiste": "Dentiste",
    "kinesitherapeute": "Kinésithérapeute", "pharmacie": "Pharmacie", "opticien": "Opticien",
    "laboratoire": "Laboratoire d'analyses", "clinique": "Clinique ou centre médical",
    "alimentation": "Commerce d'alimentation", "mode": "Magasin de mode", "maison": "Magasin maison et décoration",
    "fleuriste": "Fleuriste", "electronique": "Magasin d'électronique et informatique",
    "sport-loisirs": "Magasin de sport et loisirs", "librairie-cadeaux": "Librairie, papeterie ou cadeaux",
    "animaux": "Animalerie",
    "restaurant": "Restaurant", "cafe": "Café ou bar", "hotel": "Hôtel ou hébergement",
    "coiffeur": "Salon de coiffure", "institut-beaute": "Institut de beauté et bien-être",
    "salle-sport": "Salle de sport ou piscine", "loisirs": "Lieu de loisirs",
    "avocat": "Avocat", "notaire": "Notaire", "huissier": "Huissier de justice", "comptable": "Comptable",
    "fiduciaire": "Fiduciaire ou conseil fiscal", "assurance": "Assurance", "banque": "Banque",
    "conseil-financier": "Conseil financier",
    "psychotherapeute": "Psychothérapeute", "autre-sante": "Professionnel de santé",
}
SHOP = {
    "alimentation": {"supermarket", "convenience", "butcher", "bakery", "greengrocer", "deli", "cheese",
                     "chocolate", "confectionery", "wine", "alcohol", "beverages", "seafood", "pastry",
                     "farm", "health_food", "coffee", "tea", "general"},
    "mode": {"clothes", "shoes", "boutique", "jewelry", "bag", "fashion_accessories", "watches", "fabric",
             "tailor", "leather"},
    "maison": {"furniture", "doityourself", "hardware", "interior_decoration", "kitchen", "bed", "carpet",
               "lighting", "garden_centre", "houseware", "curtain", "bathroom_furnishing", "tiles",
               "paint", "flooring", "antiques"},
    "fleuriste": {"florist"},
    "electronique": {"electronics", "computer", "mobile_phone", "hifi", "appliance", "telecommunication"},
    "sport-loisirs": {"sports", "bicycle", "outdoor", "toys", "games", "musical_instrument", "art", "hobby",
                      "fishing", "video_games"},
    "librairie-cadeaux": {"books", "stationery", "gift", "newsagent", "variety_store", "second_hand",
                          "copyshop", "photo"},
    "animaux": {"pet", "pet_grooming"},
}
SHOP_INV = {v: k for k, vs in SHOP.items() for v in vs}
# Fournisseurs d'énergie, grossistes, fabricants : ce ne sont pas des artisans
EXCLUS = {"enovos", "metro", "van marcke", "viessmann", "societe electrique de l our"}


def classer(t):
    """Retourne (groupe, métier) ou None."""
    if t.get("craft") in CRAFT:
        return CRAFT[t["craft"]]
    hc, am, shop = t.get("healthcare", ""), t.get("amenity", ""), t.get("shop", "")
    spec = t.get("healthcare:speciality", "")
    specs = {s.strip() for s in spec.split(";") if s.strip()}
    if am == "pharmacy" or hc == "pharmacy":
        return ("sante", "pharmacie")
    if shop == "optician" or hc == "optometrist":
        return ("sante", "opticien")
    if am == "dentist" or hc == "dentist" or any(k in spec for k in ("dentist", "dental", "orthodont")):
        return ("sante", "dentiste")
    if hc == "physiotherapist":
        return ("sante", "kinesitherapeute")
    if hc == "laboratory" or am == "laboratory":
        return ("sante", "laboratoire")
    if hc == "psychotherapist":
        return ("sante", "psychotherapeute")
    if am == "clinic" or hc in ("clinic", "centre"):
        return ("sante", "clinique")
    if am == "doctors" or hc == "doctor":
        if "general" in specs:
            return ("sante", "medecin-generaliste")
        if "ophthalmology" in specs:
            return ("sante", "ophtalmologue")
        if specs:
            return ("sante", "medecin-specialiste")
        return ("sante", "medecin")
    if hc in ("midwife", "podiatrist", "medical_imaging", "audiologist", "speech_therapist",
              "occupational_therapist", "nutrition_counselling", "osteopath", "chiropractor"):
        return ("sante", "autre-sante")
    if shop in SHOP_INV:
        return ("commerces", SHOP_INV[shop])
    tour, leis = t.get("tourism", ""), t.get("leisure", "")
    if am in ("restaurant", "fast_food", "food_court"):
        return ("restauration", "restaurant")
    if am in ("cafe", "bar", "pub", "biergarten", "ice_cream"):
        return ("restauration", "cafe")
    if tour in ("hotel", "guest_house", "hostel", "motel", "apartment", "chalet"):
        return ("restauration", "hotel")
    off = t.get("office", "")
    if off == "lawyer":
        return ("droit-finance", "avocat")
    if off == "notary":
        return ("droit-finance", "notaire")
    if off == "bailiff":
        return ("droit-finance", "huissier")
    if off == "accountant":
        return ("droit-finance", "comptable")
    if off == "tax_advisor":
        return ("droit-finance", "fiduciaire")
    if off == "insurance":
        return ("droit-finance", "assurance")
    if am == "bank" or off == "bank":
        return ("droit-finance", "banque")
    if off in ("financial", "financial_advisor", "mortgage_broker"):
        return ("droit-finance", "conseil-financier")
    if shop == "hairdresser":
        return ("beaute-loisirs", "coiffeur")
    if shop in ("beauty", "nails", "massage", "tattoo", "cosmetics") or am == "spa" or leis == "sauna":
        return ("beaute-loisirs", "institut-beaute")
    if leis in ("fitness_centre", "sports_centre", "sports_hall", "swimming_pool") and t.get("name"):
        n = t["name"].lower()
        if re.search(r"bowling|laser game", n):
            return ("beaute-loisirs", "loisirs")
        if re.search(r"club|archery|boulodrome|d[eë]schtennis|[eé]questre|ver[aä]insbau|ancien", n):
            return None  # clubs et associations : hors annuaire (salles communales et salles pro conservées)
        return ("beaute-loisirs", "salle-sport")
    if am in ("cinema", "theatre", "arts_centre", "nightclub", "casino") or leis in ("bowling_alley", "escape_game", "amusement_arcade", "miniature_golf", "water_park", "trampoline_park", "adult_gaming_centre", "dance") or tour in ("museum", "zoo", "theme_park", "aquarium", "attraction"):
        return ("beaute-loisirs", "loisirs")
    return None


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\b(sarl|sarls|sa|s a|s a r l|cie|et|and)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def domaine(url):
    if not url:
        return ""
    if "://" not in url:
        url = "https://" + url
    h = (urlparse(url).netloc or "").lower()
    return h[4:] if h.startswith("www.") else h


JOURS = {"Mo": "Lun", "Tu": "Mar", "We": "Mer", "Th": "Jeu", "Fr": "Ven", "Sa": "Sam", "Su": "Dim", "PH": "jours fériés"}


def horaires_fr(h):
    h = (h or "").strip().replace('"', "")
    if not h or len(h) > 160:
        return ""
    if h == "24/7":
        return "24h/24, 7j/7"
    h = re.sub(r"\b(Mo|Tu|We|Th|Fr|Sa|Su|PH)\b", lambda m: JOURS[m.group(1)], h)
    h = re.sub(r"\boff\b", "fermé", h)
    h = re.sub(r",(?=\d)", ", ", h)
    return re.sub(r"\s*;\s*", " ; ", h)


def propre_tel(t):
    return re.sub(r"^00\s*352", "+352", (t or "").strip())


def lire(el):
    t = el.get("tags", {})
    cl = classer(t)
    nom = (t.get("name") or "").strip()
    if not cl or not nom or norm(nom) in EXCLUS:
        return None
    rue, num = t.get("addr:street", ""), t.get("addr:housenumber", "")
    site = (t.get("website") or t.get("contact:website") or "").strip()
    if site and "://" not in site:
        site = "https://" + site
    return {
        "nom": nom, "classe": cl,
        "ville": (t.get("addr:city") or "").strip(),
        "adresse": f"{num} {rue}".strip() if rue else "",
        "code_postal": ("L-" + t["addr:postcode"]) if t.get("addr:postcode") else "",
        "telephone": propre_tel(t.get("phone") or t.get("contact:phone") or t.get("mobile") or ""),
        "email": (t.get("email") or t.get("contact:email") or "").strip(),
        "site": site, "caclr": t.get("ref:caclr", ""),
        "horaires": horaires_fr(t.get("opening_hours", "")),
        "osm": f"{el['type']}/{el['id']}", "poids": len(t),
    }


with open(SRC, encoding="utf-8") as f:
    brut = json.load(f)
items = [x for x in (lire(e) for e in brut["elements"]) if x]

# --- fusion : d'abord les éléments avec commune (clés limitées à la commune)
parent = list(range(len(items)))


def find(i):
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i


vus = {}
for i, it in enumerate(items):
    if not it["ville"]:
        continue
    cles = [("n", norm(it["nom"]), it["classe"][0], it["ville"])]
    if it["site"]:
        cles.append(("d", domaine(it["site"]), it["ville"]))
    if it["caclr"]:
        cles.append(("c", it["caclr"], it["ville"]))
    for c in cles:
        if c in vus:
            parent[find(i)] = find(vus[c])
        else:
            vus[c] = i

# --- puis ceux sans commune : fusionnés seulement si une seule fiche correspond (même nom ou même site)
par_nom, par_dom = {}, {}
for i, it in enumerate(items):
    if it["ville"]:
        par_nom.setdefault(norm(it["nom"]), set()).add(find(i))
        if it["site"]:
            par_dom.setdefault(domaine(it["site"]), set()).add(find(i))
for i, it in enumerate(items):
    if it["ville"]:
        continue
    cands = set(par_nom.get(norm(it["nom"]), set()))
    if it["site"]:
        cands |= par_dom.get(domaine(it["site"]), set())
    if len(cands) == 1:
        parent[i] = next(iter(cands))

groupes = {}
for i, it in enumerate(items):
    groupes.setdefault(find(i), []).append(it)

fiches, a_completer = [], []
for membres in groupes.values():
    membres.sort(key=lambda m: (not m["ville"], -m["poids"]))
    base = dict(membres[0])
    for m in membres[1:]:
        for k in ("ville", "adresse", "code_postal", "telephone", "email", "site", "horaires"):
            if not base[k] and m[k]:
                base[k] = m[k]
    g, metier = base["classe"]
    fiche = {
        "nom": base["nom"], "groupe": g, "metier": metier, "ville": base["ville"],
        "adresse": base["adresse"], "code_postal": base["code_postal"],
        "telephone": base["telephone"], "email": base["email"], "site": base["site"],
        "horaires": base["horaires"],
        "description": f"{SINGULIER[metier]} à {base['ville']}." if base["ville"] else "",
        "source": "OpenStreetMap", "osm": base["osm"],
    }
    fiche = {k: v for k, v in fiche.items() if v != ""}
    (fiches if base["ville"] else a_completer).append(fiche)

chemin = os.path.join(ROOT, "data", "entreprises.json")
with open(chemin, encoding="utf-8") as f:
    existantes = json.load(f)
existantes = [e for e in existantes if "EXEMPLE" not in e.get("description", "").upper()]
deja = {(norm(e["nom"]), norm(e["ville"])): e for e in existantes}
for f_ in fiches:
    e_ = deja.get((norm(f_["nom"]), norm(f_["ville"])))
    if e_ and e_.get("source") == "OpenStreetMap":
        for k_, v_ in f_.items():
            if k_ not in e_ and k_ != "description":
                e_[k_] = v_
nouvelles = [f for f in fiches if (norm(f["nom"]), norm(f["ville"])) not in deja]
nouvelles.sort(key=lambda f: f["nom"].lower())

chemin_ac = os.path.join(ROOT, "data", "osm_a_completer.json")
ac_exist = json.load(open(chemin_ac, encoding="utf-8")) if os.path.exists(chemin_ac) else []
osm_deja = {x.get("osm") for x in ac_exist}
ac_exist += [x for x in a_completer if x.get("osm") not in osm_deja]

with open(chemin, "w", encoding="utf-8") as f:
    json.dump(existantes + nouvelles, f, ensure_ascii=False, indent=2)
with open(chemin_ac, "w", encoding="utf-8") as f:
    json.dump(ac_exist, f, ensure_ascii=False, indent=2)

print(f"éléments lus : {len(brut['elements'])}, retenus : {len(items)}, après fusion : {len(fiches) + len(a_completer)}")
print(f"ajoutées au site : {len(nouvelles)} ; sans commune (à compléter) : {len(a_completer)}")
