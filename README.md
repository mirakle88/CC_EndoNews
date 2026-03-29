# EndoNews Weekly

Veille hebdomadaire automatisée sur les principales revues scientifiques en endocrinologie.

## Revues suivies

| Revue | Abréviation |
|-------|-------------|
| The Journal of Clinical Endocrinology & Metabolism | JCEM |
| Endocrine Reviews | Endocr Rev |
| Thyroid | Thyroid |
| Diabetes Care | Diabetes Care |
| Diabetes | Diabetes |
| European Journal of Endocrinology | EJE |
| Endocrinology | Endocrinology |
| The Lancet Diabetes & Endocrinology | Lancet D&E |
| Frontiers in Endocrinology | Front Endocrinol |
| Nature Reviews Endocrinology | Nat Rev Endocrinol |

## Fonctionnement

- **Source** : API PubMed E-utilities (NCBI) — gratuite et fiable
- **Dépendances** : aucune (bibliothèque standard Python uniquement)
- **Fréquence** : chaque lundi à 7h UTC (GitHub Actions)
- **Sortie** : page HTML statique déployée sur GitHub Pages
- **Coût** : 100% gratuit

## Utilisation locale

```bash
python fetch_articles.py
# Ouvrir output/index.html
```

## Déploiement

Le workflow GitHub Actions s'exécute automatiquement chaque lundi.
Pour un lancement manuel : Actions → EndoNews Weekly → Run workflow.

Après la première exécution, activer GitHub Pages :
Settings → Pages → Source : Deploy from a branch → `gh-pages` / `/ (root)`
