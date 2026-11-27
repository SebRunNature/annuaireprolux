#!/usr/bin/env python3
"""Regroupe les enseignes à succursales en UNE seule fiche (« Luxembourg »).

Règle du projet : un annuaire local sert surtout les petites entreprises. Une grande enseigne
(Cactus, Lidl, une banque, une assurance...) n'a pas besoin d'une fiche par commune : on garde
une fiche, rattachée à « Luxembourg », avec le contact général (e-mail, téléphone, site) s'il existe
dans les données. Aucune adresse ni aucun horaire de succursale n'est conservé.

Usage direct (applique la règle à data/entreprises.json) : python3 -I tools/enseignes.py
Utilisé aussi par tools/import_osm.py, pour qu'un nouvel import ne ramène pas les succursales.
"""
import collections
import json
import os
import re
import unicodedata
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (nom affiché, expressions sur le nom normalisé [fullmatch], domaines)
ENSEIGNES = [
    ("Lidl", [r"lidl"], ["lidl.lu"]),
    ("Aldi", [r"aldi"], ["aldi.lu"]),
    ("E.Leclerc", [r"e leclerc", r"leclerc"], ["e.leclerc"]),
    ("Cactus", [r"cactus", r"cactus shoppi", r"cactus markt"], ["cactus.lu"]),
    ("Delhaize", [r"delhaize", r"proxy delhaize", r"shop go", r"shop and go"], ["delhaize.lu", "magasins.delhaize.lu"]),
    ("Auchan", [r"auchan", r"auchan drive", r"my auchan"], ["auchan.lu"]),
    ("Colruyt", [r"colruyt"], ["colruyt.lu"]),
    ("Boulangerie Fischer", [r"fischer", r"boulangerie fischer"], ["fischer.lu", "fischer1913.com"]),
    ("Pâtisserie Hoffmann", [r"hoffmann"], ["patisserie-hoffmann.lu"]),
    ("Maison Steffen", [r"steffen", r"maison steffen"], ["maisonsteffen.lu"]),
    ("Boulangerie Jos & Jean-Marie", [r"jos a jean marie", r"jos jean marie", r"boulangerie jos jean marie", r"jos jean marie sarl"], ["jjm.lu"]),
    ("Boulangerie Berto", [r"boulangerie patisserie berto"], ["berto.lu"]),
    ("Boulangerie Brisbois", [r"brisbois"], ["boulangeriebrisbois.lu"]),
    ("Naturata", [r"naturata.*"], ["naturata.lu"]),
    ("Primavera", [r"primavera", r"primavera market"], ["primavera.lu"]),
    ("Burger King", [r"burger king"], []),
    ("McDonald's", [r"mcdonald s", r"mcdonalds"], ["mcd.lu"]),
    ("Pizza Hut", [r"pizza hut"], ["restaurants.pizzahut.lu"]),
    ("L'Osteria", [r"l osteria.*"], ["losteria.net"]),
    ("Cocottes", [r"cocottes.*"], ["cocottes.lu"]),
    ("K Kiosk", [r"k kiosk"], []),
    ("Batiself", [r"batiself"], []),
    ("Shell", [r"shell"], []),
    ("Devred 1902", [r"devred 1902"], ["devred.com"]),
    ("Kinepolis", [r"kinepolis.*", r"kinepolis kirchberg"], ["kinepolis.lu"]),
    ("Basic-Fit", [r"basic fit"], []),
    ("BCEE", [r"bcee.*", r"spuerkeess.*", r"banque et caisse d epargne de l etat.*"], ["spuerkeess.lu", "spuerkeess.lu"]),
    ("BGL BNP Paribas", [r"bgl.*", r"bnp paribas.*", r"bnp"], ["bgl.lu"]),
    ("BIL", [r"bil", r"banque internationale a luxembourg"], ["bil.lu"]),
    ("ING", [r"ing", r"ing luxembourg"], ["ing.lu"]),
    ("Raiffeisen", [r"raiffeiss?en.*", r"banque raiffeiss?en.*"], ["raiffeisen.lu"]),
    ("BCP", [r"bcp", r"banque bcp", r"banque commerciale du marche commun"], ["banquebcp.lu"]),
    ("Dexia", [r"dexia", r"banque dexia"], []),
    ("Lalux", [r"lalux.*"], ["lalux.lu"]),
    ("Foyer", [r"foyer", r"foyer assurances"], ["foyer.lu"]),
    ("Ketterthill", [r"ketterthill"], ["ketterthill.lu"]),
    ("BioneXt", [r"bionext"], ["bionext.lu"]),
    ("RE/MAX", [r"re ?/? ?max.*", r"remax.*"], ["remax.lu"]),
    ("Laforêt", [r"laforet.*"], ["laforet.com", "laforet.lu"]),
    ("Engel & Völkers", [r"engel (&|et|and)? ?volkers.*"], ["engelvoelkers.com"]),
    ("B Immobilier", [r"b immobilier"], ["b-immobilier.lu"]),
    ("Norauto", [r"norauto.*"], ["norauto.lu"]),
    ("Point S", [r"point s.*"], ["point-s.lu"]),
    ("Feu Vert", [r"feu vert.*"], []),
    ("Carglass", [r"carglass.*"], ["carglass.lu"]),
    ("SNCT", [r"snct.*"], ["snct.lu"]),
    ("Dekra", [r"dekra.*"], ["dekra.lu"]),
    ("Hertz", [r"hertz.*"], []),
    ("Europcar", [r"europcar.*"], []),
    ("Avis", [r"avis"], []),
    ("Sixt", [r"sixt.*"], []),
    ("Euromaster", [r"euromaster.*"], []),
    ("Speedy", [r"speedy.*"], []),
    ("Car Avenue", [r"car avenue.*"], ["caravenue.com"]),
    ("Muller Pneus", [r"mull?er pneus.*"], ["mullerpneus.lu"]),
    ("Merbag", [r"merbag.*", r"mercedes benz.*"], ["merbag.lu"]),
    ("Inter Central Pneus", [r"inter ?central pneus?", r"intercentral pneu"], ["icp.lu"]),
    ("CarLife", [r"carlife"], ["carlife.lu"]),
    ("Auto-École Theis", [r"auto ecole theis"], ["autoecole-theis.lu"]),
    ("Autocenter Goedert", [r"autocenter goedert"], []),
    ("Garage Castermans", [r"castermans.*", r"garage castermans"], ["castermans.lu"]),
    ("Winandy", [r"winandy", r"garage winandy"], []),
    ("Thommes", [r"thommes"], []),
    ("Garage Roby Cruciani", [r"garage roby cruciani.*"], []),
    ("Arnold Kontz", [r"arnold kon?tz"], ["arnoldkontz-group.com"]),
    ("Citroën", [r"citroen"], []),
    ("Laboratoires Réunis", [r"laboratoires reunis"], ["labo.lu"]),
]
# Métiers où chaque enseigne (même nom) n'a qu'une fiche
SIEGE_UNIQUE = {"banque", "assurance"}
# Portails, annuaires et réseaux sociaux : jamais considérés comme une enseigne
LIBELLES = {
    "alimentation": "Commerce d'alimentation", "restaurant": "Restaurant", "cafe": "Café ou bar",
    "hotel": "Hôtel ou hébergement", "banque": "Banque", "assurance": "Assurance",
    "laboratoire": "Laboratoire d'analyses", "mode": "Magasin de mode", "maison": "Magasin maison et décoration",
    "pharmacie": "Pharmacie", "opticien": "Opticien", "loisirs": "Cinéma ou lieu de loisirs",
    "salle-sport": "Salle de sport", "sport-loisirs": "Magasin de sport et loisirs",
    "electronique": "Magasin d'électronique et informatique", "librairie-cadeaux": "Librairie, papeterie ou cadeaux",
    "garage": "Garage", "concessionnaire": "Concessionnaire", "pieces-auto": "Magasin de pièces auto",
    "controle-technique": "Centre de contrôle technique", "location-vehicules": "Location de véhicules", "agence-immobiliere": "Agence immobilière", "fleuriste": "Fleuriste", "animaux": "Animalerie", "clinique": "Clinique ou centre médical",
}
PORTAILS = {"pharmacie.lu", "editus.lu", "doctena.lu", "facebook.com", "salonkee.lu", "simpleviu.com",
            "differdange.lu", "minettpark.lu", "ligue-hmc.lu", "espaces-saveurs.lu", "cnds.lu",
            "instagram.com", "linkedin.com", "google.com", "wixsite.com", "business.site"}


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", s)).strip()


def domaine(url):
    if not url:
        return ""
    h = (urlparse(url if "://" in url else "https://" + url).netloc or "").lower()
    return h[4:] if h.startswith("www.") else h


def cle_explicite(f):
    n, d = norm(f["nom"]), domaine(f.get("site"))
    for nom, regs, doms in ENSEIGNES:
        if d in doms or any(re.fullmatch(r, n) for r in regs):
            return "e:" + norm(nom)
    return None


def regrouper(fiches, afficher=print):
    """Retourne la liste après regroupement (idempotent). Les fiches Premium ou saisies à la main ne sont jamais touchées."""
    eligibles = [f for f in fiches if not f.get("premium") and f.get("source") == "OpenStreetMap"]
    autres = [f for f in fiches if f not in eligibles]
    groupes = {}
    for f in eligibles:
        cle = f.get("enseigne") or cle_explicite(f)
        if not cle and f["metier"] in SIEGE_UNIQUE:
            cle = "n:" + f["metier"] + ":" + norm(f["nom"])
        if cle:
            groupes.setdefault(cle, []).append(f)
    # règle générale : un même site web (hors portails) dans 3 communes et plus, avec un nom qui commence pareil
    par_dom = {}
    for f in eligibles:
        d = domaine(f.get("site"))
        if d and d not in PORTAILS and f["groupe"] in ("commerces", "restauration") and not (f.get("enseigne") or cle_explicite(f)):
            par_dom.setdefault(d, []).append(f)
    for d, l in par_dom.items():
        if "d:" + d in groupes:
            groupes["d:" + d].extend(l)
        elif len({x["ville"] for x in l}) >= 3 and len({norm(x["nom"]).split(" ")[0] for x in l}) == 1:
            groupes.setdefault("d:" + d, []).extend(l)

    regroupes, retires = [], set()
    for cle, membres in groupes.items():
        if len(membres) < 2:
            continue
        membres.sort(key=lambda m: (m["ville"] != "Luxembourg", -len(m)))
        base = dict(membres[0])
        # métier du réseau = le plus fréquent parmi ses fiches (évite qu'une succursale mal classée donne son métier)
        (base["groupe"], base["metier"]), _ = collections.Counter((m["groupe"], m["metier"]) for m in membres).most_common(1)[0]
        # contact général uniquement : un e-mail ou un téléphone présent dans au moins 2 succursales ;
        # sinon on n'affiche rien (le numéro d'une succursale n'est pas le contact de l'enseigne)
        for k in ("telephone", "email"):
            valeurs = [norm(m[k]) for m in membres if m.get(k)]
            commun = next((v for v in valeurs if valeurs.count(v) >= 2), None)
            base[k] = next((m[k] for m in membres if m.get(k) and norm(m[k]) == commun), "") if commun else ""
        # site : la page d'accueil du site (jamais la page d'une succursale)
        sites = [m["site"] for m in membres if m.get("site")]
        if sites:
            h = urlparse(sites[0] if "://" in sites[0] else "https://" + sites[0])
            base["site"] = f"{h.scheme}://{h.netloc}/"
        else:
            base["site"] = ""
        affiche = next((e[0] for e in ENSEIGNES if cle == "e:" + norm(e[0])), base["nom"])
        base.update({"nom": affiche, "ville": "Luxembourg", "enseigne": cle})
        for k in ("adresse", "code_postal", "horaires", "osm"):
            base.pop(k, None)
        libelle = LIBELLES.get(base["metier"], "Entreprise")
        base["description"] = f"{libelle}, enseigne présente dans plusieurs communes du Luxembourg."
        base = {k: v for k, v in base.items() if v != ""}
        retires.update(id(m) for m in membres)
        regroupes.append(base)
        if len(membres) > 1:
            afficher(f"enseigne regroupée : {affiche} ({len(membres)} fiches -> 1)")
    return autres + [f for f in eligibles if id(f) not in retires] + regroupes


if __name__ == "__main__":
    chemin = os.path.join(ROOT, "data", "entreprises.json")
    donnees = json.load(open(chemin, encoding="utf-8"))
    avant = len(donnees)
    apres = regrouper(donnees)
    apres.sort(key=lambda f: f["nom"].lower())
    json.dump(apres, open(chemin, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"{avant} -> {len(apres)} fiches")
