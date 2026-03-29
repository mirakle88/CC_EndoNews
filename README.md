# EndoNews Weekly

Veille hebdomadaire automatisée sur les principales revues scientifiques en endocrinologie.

## Revues suivies

| Revue | Éditeur |
|-------|---------|
| The Journal of Clinical Endocrinology & Metabolism | Oxford Academic |
| Endocrine Reviews | Oxford Academic |
| Thyroid | Mary Ann Liebert |
| Diabetes Care | ADA |
| Diabetes | ADA |
| European Journal of Endocrinology | Oxford Academic |
| Endocrinology | Oxford Academic |
| The Lancet Diabetes & Endocrinology | Elsevier |
| Frontiers in Endocrinology | Frontiers |
| BMC Endocrine Disorders | Springer Nature |

## Fonctionnement

- **Source** : flux RSS publics des revues
- **Fréquence** : chaque lundi à 7h UTC (GitHub Actions)
- **Sortie** : page HTML statique déployée sur GitHub Pages
- **Coût** : 100% gratuit

## Utilisation locale

```bash
pip install -r requirements.txt
python fetch_articles.py
# Ouvrir output/index.html
```

## Déploiement

Le workflow GitHub Actions s'exécute automatiquement chaque lundi.
Pour un lancement manuel : Actions → EndoNews Weekly → Run workflow.

Après la première exécution, activer GitHub Pages :
Settings → Pages → Source : Deploy from a branch → `gh-pages` / `/ (root)`
