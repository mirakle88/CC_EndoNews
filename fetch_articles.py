#!/usr/bin/env python3
"""
EndoNews Weekly - Veille hebdomadaire en endocrinologie
Récupère les derniers articles via l'API PubMed (E-utilities) du NCBI
et génère une page HTML statique.

Aucune dépendance externe — uniquement la bibliothèque standard Python.
API PubMed E-utilities : gratuite, fiable, couvre toutes les revues.
"""

import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from html import escape
from urllib.request import Request, urlopen
from urllib.parse import urlencode, quote
from urllib.error import URLError, HTTPError
import time

# ─── Configuration ────────────────────────────────────────────────────

JOURNALS = [
    {
        "name": "The Journal of Clinical Endocrinology & Metabolism",
        "short": "JCEM",
        "query": '"J Clin Endocrinol Metab"[jour]',
        "color": "#1a5276",
    },
    {
        "name": "Endocrine Reviews",
        "short": "Endocr Rev",
        "query": '"Endocr Rev"[jour]',
        "color": "#6c3483",
    },
    {
        "name": "Thyroid",
        "short": "Thyroid",
        "query": '"Thyroid"[jour]',
        "color": "#117864",
    },
    {
        "name": "Diabetes Care",
        "short": "Diabetes Care",
        "query": '"Diabetes Care"[jour]',
        "color": "#c0392b",
    },
    {
        "name": "Diabetes",
        "short": "Diabetes",
        "query": '"Diabetes"[jour] NOT "Diabetes Care"[jour] NOT "Diabetes Obes Metab"[jour]',
        "color": "#e74c3c",
    },
    {
        "name": "European Journal of Endocrinology",
        "short": "EJE",
        "query": '"Eur J Endocrinol"[jour]',
        "color": "#2874a6",
    },
    {
        "name": "Endocrinology",
        "short": "Endocrinology",
        "query": '"Endocrinology"[jour] NOT "Mol Cell Endocrinol"[jour]',
        "color": "#1e8449",
    },
    {
        "name": "The Lancet Diabetes & Endocrinology",
        "short": "Lancet D&E",
        "query": '"Lancet Diabetes Endocrinol"[jour]',
        "color": "#d35400",
    },
    {
        "name": "Frontiers in Endocrinology",
        "short": "Front Endocrinol",
        "query": '"Front Endocrinol (Lausanne)"[jour]',
        "color": "#2e86c1",
    },
    {
        "name": "Nature Reviews Endocrinology",
        "short": "Nat Rev Endocrinol",
        "query": '"Nat Rev Endocrinol"[jour]',
        "color": "#8e44ad",
    },
]

MAX_ARTICLES_PER_JOURNAL = 10
DAYS_LOOKBACK = 14  # 2 semaines pour couvrir les revues mensuelles

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
USER_AGENT = "EndoNewsWeekly/1.0 (Academic Literature Monitor; mailto:endonews@example.com)"
REQUEST_DELAY = 0.35  # NCBI demande max 3 requêtes/sec sans API key


# ─── PubMed E-utilities ──────────────────────────────────────────────

def eutils_request(endpoint, params):
    """Effectue une requête vers l'API E-utilities."""
    url = f"{EUTILS_BASE}/{endpoint}?{urlencode(params, quote_via=quote)}"
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def search_pubmed(query, max_results=10, reldate=14):
    """Recherche des articles récents sur PubMed."""
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "sort": "date",
        "datetype": "pdat",
        "reldate": reldate,
        "retmode": "xml",
    }
    xml_str = eutils_request("esearch.fcgi", params)
    root = ET.fromstring(xml_str)

    ids = []
    id_list = root.find("IdList")
    if id_list is not None:
        ids = [id_el.text for id_el in id_list.findall("Id") if id_el.text]

    return ids


def fetch_articles_details(pmids):
    """Récupère les détails des articles via efetch."""
    if not pmids:
        return []

    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
    }
    xml_str = eutils_request("efetch.fcgi", params)
    root = ET.fromstring(xml_str)

    articles = []
    for article_el in root.findall(".//PubmedArticle"):
        try:
            articles.append(parse_pubmed_article(article_el))
        except Exception:
            continue

    return articles


def parse_pubmed_article(article_el):
    """Parse un élément PubmedArticle XML."""
    medline = article_el.find("MedlineCitation")
    article = medline.find("Article")

    # PMID
    pmid = ""
    pmid_el = medline.find("PMID")
    if pmid_el is not None:
        pmid = pmid_el.text or ""

    # Titre
    title = ""
    title_el = article.find("ArticleTitle")
    if title_el is not None:
        title = "".join(title_el.itertext()).strip()

    # Auteurs
    authors = []
    author_list = article.find("AuthorList")
    if author_list is not None:
        for author_el in author_list.findall("Author"):
            last = author_el.find("LastName")
            init = author_el.find("Initials")
            if last is not None and last.text:
                name = last.text
                if init is not None and init.text:
                    name += f" {init.text}"
                authors.append(name)

    author_str = ", ".join(authors[:3])
    if len(authors) > 3:
        author_str += " et al."

    # Abstract
    abstract = ""
    abstract_el = article.find("Abstract")
    if abstract_el is not None:
        parts = []
        for text_el in abstract_el.findall("AbstractText"):
            txt = "".join(text_el.itertext()).strip()
            if txt:
                parts.append(txt)
        abstract = " ".join(parts)
        if len(abstract) > 300:
            abstract = abstract[:297] + "..."

    # Date de publication
    pub_date = ""
    date_el = article.find(".//ArticleDate")
    if date_el is None:
        date_el = article.find(".//PubDate")
    if date_el is not None:
        year = date_el.find("Year")
        month = date_el.find("Month")
        day = date_el.find("Day")
        parts = []
        if day is not None and day.text:
            parts.append(day.text.zfill(2))
        if month is not None and month.text:
            # Mois peut être numérique ou textuel
            m = month.text
            month_map = {
                "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
                "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
                "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
            }
            parts.append(month_map.get(m, m.zfill(2)))
        if year is not None and year.text:
            parts.append(year.text)
        pub_date = "/".join(parts)

    # DOI → lien
    link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    doi_list = article_el.find(".//ArticleIdList")
    if doi_list is not None:
        for aid in doi_list.findall("ArticleId"):
            if aid.get("IdType") == "doi" and aid.text:
                link = f"https://doi.org/{aid.text}"
                break

    # Type d'article
    pub_types = []
    pt_list = article.find("PublicationTypeList")
    if pt_list is not None:
        for pt in pt_list.findall("PublicationType"):
            if pt.text:
                pub_types.append(pt.text)

    return {
        "pmid": pmid,
        "title": title or "Sans titre",
        "authors": author_str,
        "abstract": abstract,
        "date": pub_date,
        "link": link,
        "pub_types": pub_types,
    }


# ─── Logique principale ──────────────────────────────────────────────

def fetch_journal(journal_info):
    """Récupère les articles récents d'une revue via PubMed."""
    print(f"  {journal_info['short']}...", end=" ", flush=True)
    try:
        pmids = search_pubmed(
            journal_info["query"],
            max_results=MAX_ARTICLES_PER_JOURNAL,
            reldate=DAYS_LOOKBACK,
        )
        time.sleep(REQUEST_DELAY)

        if not pmids:
            print("0 articles")
            return []

        articles = fetch_articles_details(pmids)
        time.sleep(REQUEST_DELAY)

        # Enrichir avec les infos de la revue
        for art in articles:
            art["journal"] = journal_info["short"]
            art["journal_full"] = journal_info["name"]
            art["color"] = journal_info["color"]

        print(f"{len(articles)} articles")
        return articles

    except (URLError, HTTPError) as e:
        print(f"erreur réseau: {e}")
        return []
    except Exception as e:
        print(f"erreur: {e}")
        return []


def fetch_all():
    """Récupère tous les articles de toutes les revues."""
    print("=" * 60)
    print("EndoNews Weekly — PubMed E-utilities")
    print(f"Période : {DAYS_LOOKBACK} derniers jours")
    print("=" * 60)

    all_data = {}
    total = 0

    for journal in JOURNALS:
        articles = fetch_journal(journal)
        if articles:
            all_data[journal["short"]] = {
                "name": journal["name"],
                "short": journal["short"],
                "color": journal["color"],
                "articles": articles,
            }
            total += len(articles)

    print(f"\n{'=' * 60}")
    print(f"Total : {total} articles de {len(all_data)} revues")
    print(f"{'=' * 60}")
    return all_data


# ─── Génération HTML ─────────────────────────────────────────────────

def generate_html(all_data):
    """Génère la page HTML statique."""
    now = datetime.now()
    week_start = now - timedelta(days=DAYS_LOOKBACK)
    date_range = f"{week_start.strftime('%d/%m/%Y')} — {now.strftime('%d/%m/%Y')}"

    total_articles = sum(len(j["articles"]) for j in all_data.values())
    total_journals = len(all_data)

    # ── Sections par revue ──
    journal_sections = ""
    for key, journal in all_data.items():
        articles_html = ""
        for art in journal["articles"]:
            authors_line = (
                f'<span class="authors">{escape(art["authors"])}</span>'
                if art["authors"]
                else ""
            )
            date_badge = (
                f'<span class="date-badge">{escape(art["date"])}</span>'
                if art["date"]
                else ""
            )
            abstract_p = (
                f'<p class="summary">{escape(art["abstract"])}</p>'
                if art["abstract"]
                else ""
            )
            pmid_badge = (
                f'<span class="pmid">PMID: {escape(art["pmid"])}</span>'
                if art["pmid"]
                else ""
            )

            articles_html += f"""
                <article class="article-card">
                    <a href="{escape(art['link'])}" target="_blank" rel="noopener noreferrer">
                        <h3>{escape(art['title'])}</h3>
                    </a>
                    <div class="article-meta">
                        {authors_line}
                        {date_badge}
                        {pmid_badge}
                    </div>
                    {abstract_p}
                </article>"""

        journal_sections += f"""
        <section class="journal-section">
            <div class="journal-header" style="border-left: 4px solid {journal['color']}">
                <h2>{escape(journal['name'])}</h2>
                <span class="article-count">{len(journal['articles'])} article{"s" if len(journal['articles']) > 1 else ""}</span>
            </div>
            <div class="articles-grid">
                {articles_html}
            </div>
        </section>"""

    # ── Navigation ──
    nav_items = ""
    for key, journal in all_data.items():
        nav_items += f'<span class="nav-tag" style="background-color: {journal["color"]}">{escape(journal["short"])} ({len(journal["articles"])})</span>\n'

    empty_state = (
        '<div class="empty-state">'
        "<h2>Aucun article cette semaine</h2>"
        "<p>PubMed n'a retourné aucun article récent pour ces revues.</p>"
        "</div>"
    )

    content = journal_sections if journal_sections else empty_state

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EndoNews Weekly</title>
    <style>
        :root {{
            --bg: #fafbfc;
            --card-bg: #ffffff;
            --text: #1a1a2e;
            --text-light: #555;
            --text-muted: #888;
            --border: #e8e8e8;
            --accent: #2c3e6b;
            --accent-light: #eef2f7;
            --link: #1a5276;
            --shadow: 0 1px 3px rgba(0,0,0,0.06);
            --shadow-hover: 0 4px 12px rgba(0,0,0,0.1);
            --radius: 8px;
        }}
        @media (prefers-color-scheme: dark) {{
            :root {{
                --bg: #0d1117;
                --card-bg: #161b22;
                --text: #e6edf3;
                --text-light: #b1bac4;
                --text-muted: #7d8590;
                --border: #30363d;
                --accent: #6e8fcf;
                --accent-light: #1c2333;
                --link: #58a6ff;
                --shadow: 0 1px 3px rgba(0,0,0,0.3);
                --shadow-hover: 0 4px 12px rgba(0,0,0,0.4);
            }}
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: var(--bg); color: var(--text); line-height: 1.6; min-height: 100vh;
        }}
        .container {{ max-width: 960px; margin: 0 auto; padding: 0 20px; }}

        header {{
            background: linear-gradient(135deg, #1a1a2e 0%, #2c3e6b 50%, #1e6b5a 100%);
            color: white; padding: 44px 0 32px; text-align: center;
        }}
        header h1 {{ font-size: 2.1rem; font-weight: 700; letter-spacing: -0.5px; margin-bottom: 4px; }}
        header h1 span {{ font-weight: 300; opacity: 0.85; }}
        .subtitle {{ font-size: 0.95rem; opacity: 0.75; margin-bottom: 4px; }}
        .header-stats {{ display: flex; justify-content: center; gap: 28px; margin-top: 18px; }}
        .stat {{ text-align: center; }}
        .stat-number {{ font-size: 1.8rem; font-weight: 700; display: block; }}
        .stat-label {{ font-size: 0.72rem; text-transform: uppercase; letter-spacing: 1px; opacity: 0.65; }}

        .nav-bar {{
            background: var(--card-bg); border-bottom: 1px solid var(--border);
            padding: 12px 0; position: sticky; top: 0; z-index: 100; box-shadow: var(--shadow);
        }}
        .nav-tags {{ display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }}
        .nav-tag {{
            display: inline-block; color: white; padding: 4px 12px;
            border-radius: 20px; font-size: 0.76rem; font-weight: 500; opacity: 0.9;
        }}

        main {{ padding: 32px 0 60px; }}
        .journal-section {{ margin-bottom: 36px; }}
        .journal-header {{
            padding: 10px 16px; margin-bottom: 14px; background: var(--accent-light);
            border-radius: var(--radius); display: flex; align-items: center;
            justify-content: space-between;
        }}
        .journal-header h2 {{ font-size: 1.05rem; font-weight: 600; }}
        .article-count {{ font-size: 0.8rem; color: var(--text-muted); font-weight: 500; }}

        .articles-grid {{ display: flex; flex-direction: column; gap: 10px; }}
        .article-card {{
            background: var(--card-bg); border: 1px solid var(--border);
            border-radius: var(--radius); padding: 16px 20px; transition: box-shadow 0.2s;
        }}
        .article-card:hover {{ box-shadow: var(--shadow-hover); }}
        .article-card a {{ text-decoration: none; color: var(--link); }}
        .article-card a:hover {{ text-decoration: underline; }}
        .article-card h3 {{ font-size: 0.95rem; font-weight: 600; line-height: 1.4; margin-bottom: 6px; }}
        .article-meta {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 6px; }}
        .authors {{ font-size: 0.8rem; color: var(--text-light); font-style: italic; }}
        .date-badge {{
            font-size: 0.72rem; color: var(--text-muted); background: var(--accent-light);
            padding: 2px 8px; border-radius: 10px;
        }}
        .pmid {{
            font-size: 0.7rem; color: var(--text-muted); font-family: monospace;
        }}
        .summary {{ font-size: 0.85rem; color: var(--text-light); line-height: 1.5; }}

        footer {{
            text-align: center; padding: 30px 0; border-top: 1px solid var(--border);
            color: var(--text-muted); font-size: 0.8rem;
        }}
        footer a {{ color: var(--text-muted); }}

        .empty-state {{ text-align: center; padding: 60px 20px; color: var(--text-muted); }}
        .empty-state h2 {{ font-size: 1.3rem; margin-bottom: 10px; }}

        @media (max-width: 600px) {{
            header h1 {{ font-size: 1.5rem; }}
            .header-stats {{ gap: 16px; }}
            .stat-number {{ font-size: 1.4rem; }}
            .article-card {{ padding: 12px 14px; }}
        }}
    </style>
</head>
<body>
    <header>
        <div class="container">
            <h1>EndoNews <span>Weekly</span></h1>
            <p class="subtitle">Veille scientifique en endocrinologie</p>
            <p class="subtitle">{date_range}</p>
            <div class="header-stats">
                <div class="stat">
                    <span class="stat-number">{total_articles}</span>
                    <span class="stat-label">Articles</span>
                </div>
                <div class="stat">
                    <span class="stat-number">{total_journals}</span>
                    <span class="stat-label">Revues</span>
                </div>
            </div>
        </div>
    </header>

    <nav class="nav-bar">
        <div class="container">
            <div class="nav-tags">
                {nav_items}
            </div>
        </div>
    </nav>

    <main>
        <div class="container">
            {content}
        </div>
    </main>

    <footer>
        <div class="container">
            <p>EndoNews Weekly &mdash; Généré le {now.strftime('%d/%m/%Y à %H:%M')}</p>
            <p>Source : PubMed / NCBI E-utilities</p>
            <p style="margin-top: 6px;">
                <a href="https://github.com/mirakle88/CC_EndoNews" target="_blank">GitHub</a>
            </p>
        </div>
    </footer>
</body>
</html>"""

    os.makedirs("output", exist_ok=True)
    with open("output/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    with open("output/articles.json", "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    print(f"\n-> Page HTML : output/index.html")
    print(f"-> Données   : output/articles.json")


def main():
    data = fetch_all()
    generate_html(data)


if __name__ == "__main__":
    main()
