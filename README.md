# Annuaire Pro Luxembourg

Annuaire professionnel statique pour le Luxembourg, hébergé sur GitHub Pages.

## Utilisation

1. Ajouter ou modifier des entreprises dans `data/entreprises.json` (catégories dans `data/categories.json`).
2. Lancer `python3 build.py` : le site est généré dans `docs/`.
3. Commit + push : GitHub Pages publie `docs/` (Settings → Pages → Branch `main`, dossier `/docs`).

## Réglages (`data/config.json`)

- `url_site` / `base_path` : à changer quand le domaine personnalisé est branché (`base_path` = `""`).
- `domaine_perso` : ex. `annuaireprolux.eu` (génère le fichier CNAME).
- `formulaire_action` : URL Formspree du formulaire « Ajouter votre entreprise ».
- `offres` : tarifs et liens de paiement (Stripe Payment Links).
- `legal` : éditeur, adresse et contact pour les mentions légales.

## Règles

- Les fiches Premium et articles sponsorisés utilisent `rel="sponsored"`, les fiches gratuites `rel="nofollow"`.
- Les fiches du fichier de données sont des **exemples fictifs** à remplacer.
