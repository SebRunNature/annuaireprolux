# Annuaire Pro Luxembourg

Annuaire professionnel statique pour le Luxembourg, hébergé sur GitHub Pages.

## Utilisation

1. Ajouter ou modifier des entreprises dans `data/entreprises.json`. Chaque fiche a un `groupe` et un `metier` définis dans `data/categories.json` (12 groupes, métiers à l'intérieur).
2. Lancer `python3 build.py` : le site est généré dans `docs/`.
3. Commit + push : GitHub Pages publie `docs/` (Settings → Pages → Branch `main`, dossier `/docs`).

## Réglages (`data/config.json`)

- `url_site` / `base_path` : à changer quand le domaine personnalisé est branché (`base_path` = `""`).
- `domaine_perso` : ex. `annuaireprolux.eu` (génère le fichier CNAME).
- `formulaire_action` : URL Formspree du formulaire « Ajouter votre entreprise ».
- `offres` : tarifs et liens de paiement (Stripe Payment Links).
- `legal` : éditeur, adresse et contact pour les mentions légales.

## Règles

- Une page métier ou commune n'est créée qu'à partir de `seuil_pages` fiches (3 par défaut, dans `data/config.json`) ; un groupe vide est en `noindex`.
- Les fiches Premium et articles sponsorisés utilisent `rel="sponsored"`, les fiches gratuites `rel="nofollow"`.
- Les fiches du fichier de données sont des **exemples fictifs** à remplacer.
