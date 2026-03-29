#!/usr/bin/env python3
"""
EndoNews Weekly - Veille hebdomadaire en endocrinologie
Récupère les derniers articles des principales revues d'endocrinologie
via leurs flux RSS/Atom publics et génère une page HTML statique.

Aucune dépendance externe requise — uniquement la bibliothèque standard Python.
"""

import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from html import escape
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from email.utils import parsedate_to_datetime

# ─── Configuration des revues ────────────────────────────────────────
FEEDS = [
    {
        "name": "The Journal of Clinical Endocrinology & Metabolism",
        "short": "JCEM",
        "url": "https://academic.oup.com/rss/site_5/3.xml",
        "color": "#1a5276"
    },
    {
        "name": "Endocrine Reviews",
        "short": "Endocr Rev",
        "url": "https://academic.oup.com/rss/site_5/4.xml",
        "color": "#6c3483"
    },
    {
        "name": "Thyroid",
        "short": "Thyroid",
        "url": "https://www.liebertpub.com/action/showFeed?type=etoc&feed=rss&jc=thy",
        "color": "#117864"
    },
    {
        "name": "Diabetes Care",
        "short": "Diabetes Care",
        "url": "https://diabetesjournals.org/care/issue.rss",
        "color": "#c0392b"
    },
    {
        "name": "Diabetes",
        "short": "Diabetes",
        "url": "https://diabetesjournals.org/diabetes/issue.rss",
        "color": "#e74c3c"
    },
    {
        "name": "European Journal of Endocrinology",
        "short": "EJE",
        "url": "https://academic.oup.com/rss/site_5/3722.xml",
        "color": "#2874a6"
    },
    {
        "name": "Endocrinology",
        "short": "Endocrinology",
        "url": "https://academic.oup.com/rss/site_5/6.xml",
        "color": "#1e8449"
    },
    {
        "name": "The Lancet Diabetes & Endocrinology",
        "short": "Lancet D&E",
        "url": "https://www.thelancet.com/rssfeed/landia_current.xml",
        "color": "#d35400"
    },
    {
        "name": "Frontiers in Endocrinology",
        "short": "Front Endocrinol",
        "url": "https://www.frontiersin.org/journals/endocrinology/rss",
        "color": "#2e86c1"
    },
    {
        "name": "BMC Endocrine Disorders",
        "short": "BMC Endocr Disord",
        "url": "https://bmcendocrdisord.biomedcentral.com/articles/most-recent/rss.xml",
        "color": "#16a085"
    },
]

MAX_ARTICLES_PER_FEED = 10
DAYS_LOOKBACK = 7
USER_AGENT = "EndoNewsWeekly/1.0 (Academic RSS Reader)"
TIMEOUT = 20  # seconds


# ─── Utilitaires ─────────────────────────────────────────────────────

def clean_html(text):
    """Supprime les balises HTML et nettoie le texte."""
    if not text:
        return ""
    clean = re.sub(r'<[^>]+>', '', text)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean[:297] + "..." if len(clean) > 300 else clean


def parse_rss_date(date_str):
    """Parse une date RSS (RFC 822) ou Atom (ISO 8601)."""
    if not date_str:
        return None
    date_str = date_str.strip()
    # RFC 822 (RSS)
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        pass
    # ISO 8601 (Atom)
    for fmt in ('%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%SZ',
                '%Y-%m-%dT%H:%M:%S.%f%z', '%Y-%m-%d'):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.replace(tzinfo=None) if dt.tzinfo else dt
        except ValueError:
            continue
    return None


def fetch_xml(url):
    """Télécharge et parse un document XML."""
    req = Request(url, headers={'User-Agent': USER_AGENT})
    with urlopen(req, timeout=TIMEOUT) as resp:
        return ET.parse(resp)


def get_text(element, tag, namespaces=None):
    """Extrait le texte d'un sous-élément."""
    if namespaces:
        for ns_prefix, ns_uri in namespaces.items():
            child = element.find(f'{{{ns_uri}}}{tag}')
            if child is not None and child.text:
                return child.text.strip()
    child = element.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return ""


def parse_rss_items(tree):
    """Parse les items d'un flux RSS 2.0."""
    root = tree.getroot()
    items = root.findall('.//item')
    results = []

    dc_ns = {'dc': 'http://purl.org/dc/elements/1.1/'}

    for item in items:
        title = get_text(item, 'title') or 'Sans titre'
        link = get_text(item, 'link') or '#'
        desc = get_text(item, 'description')
        pub_date_str = get_text(item, 'pubDate')
        author = get_text(item, 'creator', dc_ns) or get_text(item, 'author')

        results.append({
            'title': title,
            'link': link,
            'summary': clean_html(desc),
            'authors': author,
            'date_raw': pub_date_str,
        })

    return results


def parse_atom_entries(tree):
    """Parse les entrées d'un flux Atom."""
    root = tree.getroot()
    ns = ''
    if root.tag.startswith('{'):
        ns = root.tag.split('}')[0] + '}'

    entries = root.findall(f'.//{ns}entry')
    results = []

    for entry in entries:
        title = ''
        title_el = entry.find(f'{ns}title')
        if title_el is not None and title_el.text:
            title = title_el.text.strip()

        link = '#'
        link_el = entry.find(f'{ns}link')
        if link_el is not None:
            link = link_el.get('href', '#')

        summary = ''
        for tag in ('summary', 'content'):
            el = entry.find(f'{ns}{tag}')
            if el is not None and el.text:
                summary = clean_html(el.text)
                break

        pub_date_str = ''
        for tag in ('published', 'updated'):
            el = entry.find(f'{ns}{tag}')
            if el is not None and el.text:
                pub_date_str = el.text.strip()
                break

        authors = []
        for author_el in entry.findall(f'{ns}author'):
            name_el = author_el.find(f'{ns}name')
            if name_el is not None and name_el.text:
                authors.append(name_el.text.strip())

        author_str = ', '.join(authors[:3])
        if len(authors) > 3:
            author_str += ' et al.'

        results.append({
            'title': title or 'Sans titre',
            'link': link,
            'summary': summary,
            'authors': author_str,
            'date_raw': pub_date_str,
        })

    return results


# ─── Logique principale ──────────────────────────────────────────────

def fetch_feed(feed_info):
    """Récupère et parse un flux RSS/Atom."""
    print(f"  Fetching: {feed_info['name']}...")
    try:
        tree = fetch_xml(feed_info['url'])
        root = tree.getroot()

        # Détecte RSS vs Atom
        tag = root.tag.lower().split('}')[-1]
        if tag == 'feed':
            raw_items = parse_atom_entries(tree)
        else:
            raw_items = parse_rss_items(tree)

        cutoff = datetime.now() - timedelta(days=DAYS_LOOKBACK)
        articles = []

        for item in raw_items:
            pub_date = parse_rss_date(item['date_raw'])

            # Filtre par date si disponible
            if pub_date and pub_date.replace(tzinfo=None) < cutoff:
                continue

            articles.append({
                'title': item['title'],
                'link': item['link'],
                'summary': item['summary'],
                'authors': item['authors'],
                'date': pub_date.strftime('%d/%m/%Y') if pub_date else '',
                'journal': feed_info['short'],
                'journal_full': feed_info['name'],
                'color': feed_info['color'],
            })

            if len(articles) >= MAX_ARTICLES_PER_FEED:
                break

        print(f"    -> {len(articles)} articles")
        return articles

    except (URLError, HTTPError) as e:
        print(f"    ✗ Réseau: {e}")
        return []
    except ET.ParseError as e:
        print(f"    ✗ XML invalide: {e}")
        return []
    except Exception as e:
        print(f"    ✗ Erreur: {e}")
        return []


def fetch_all():
    """Récupère tous les flux."""
    print("=" * 60)
    print("EndoNews Weekly — Récupération des articles")
    print("=" * 60)

    all_articles = {}
    total = 0

    for feed in FEEDS:
        articles = fetch_feed(feed)
        if articles:
            all_articles[feed['short']] = {
                'name': feed['name'],
                'short': feed['short'],
                'color': feed['color'],
                'articles': articles,
            }
            total += len(articles)

    print(f"\n{'=' * 60}")
    print(f"Total: {total} articles de {len(all_articles)} revues")
    print(f"{'=' * 60}")
    return all_articles


def generate_html(all_articles):
    """Génère la page HTML statique élégante."""
    now = datetime.now()
    week_start = now - timedelta(days=DAYS_LOOKBACK)
    date_range = f"{week_start.strftime('%d/%m/%Y')} — {now.strftime('%d/%m/%Y')}"

    total_articles = sum(len(j['articles']) for j in all_articles.values())
    total_journals = len(all_articles)

    # ── Sections par revue ──
    journal_sections = ""
    for key, journal in all_articles.items():
        articles_html = ""
        for art in journal['articles']:
            authors_line = f'<span class="authors">{escape(art["authors"])}</span>' if art['authors'] else ''
            date_badge = f'<span class="date-badge">{art["date"]}</span>' if art['date'] else ''
            summary_p = f'<p class="summary">{escape(art["summary"])}</p>' if art['summary'] else ''

            articles_html += f"""
                <article class="article-card">
                    <a href="{escape(art['link'])}" target="_blank" rel="noopener noreferrer">
                        <h3>{escape(art['title'])}</h3>
                    </a>
                    <div class="article-meta">
                        {authors_line}
                        {date_badge}
                    </div>
                    {summary_p}
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

    empty_state = '<div class="empty-state"><h2>Aucun article cette semaine</h2><p>Aucun article récent trouvé.</p></div>'

    # ── Tags de navigation ──
    nav_items = ""
    for key, journal in all_articles.items():
        nav_items += f'<span class="nav-tag" style="background-color: {journal["color"]}">{escape(journal["short"])} ({len(journal["articles"])})</span>\n'

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

        /* Header */
        header {{
            background: linear-gradient(135deg, #1a1a2e 0%, #2c3e6b 50%, #1e6b5a 100%);
            color: white; padding: 44px 0 32px; text-align: center;
        }}
        header h1 {{ font-size: 2.1rem; font-weight: 700; letter-spacing: -0.5px; margin-bottom: 4px; }}
        header h1 span {{ font-weight: 300; opacity: 0.85; }}
        .subtitle {{ font-size: 0.95rem; opacity: 0.75; margin-bottom: 4px; }}
        .header-stats {{
            display: flex; justify-content: center; gap: 28px; margin-top: 18px;
        }}
        .stat {{ text-align: center; }}
        .stat-number {{ font-size: 1.8rem; font-weight: 700; display: block; }}
        .stat-label {{ font-size: 0.72rem; text-transform: uppercase; letter-spacing: 1px; opacity: 0.65; }}

        /* Nav */
        .nav-bar {{
            background: var(--card-bg); border-bottom: 1px solid var(--border);
            padding: 12px 0; position: sticky; top: 0; z-index: 100; box-shadow: var(--shadow);
        }}
        .nav-tags {{ display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }}
        .nav-tag {{
            display: inline-block; color: white; padding: 4px 12px;
            border-radius: 20px; font-size: 0.76rem; font-weight: 500; opacity: 0.9;
        }}

        /* Main */
        main {{ padding: 32px 0 60px; }}
        .journal-section {{ margin-bottom: 36px; }}
        .journal-header {{
            padding: 10px 16px; margin-bottom: 14px; background: var(--accent-light);
            border-radius: var(--radius); display: flex; align-items: center; justify-content: space-between;
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
        .summary {{ font-size: 0.85rem; color: var(--text-light); line-height: 1.5; }}

        /* Footer */
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
            {journal_sections if journal_sections else empty_state}
        </div>
    </main>

    <footer>
        <div class="container">
            <p>EndoNews Weekly &mdash; Généré le {now.strftime('%d/%m/%Y à %H:%M')}</p>
            <p>Sources : flux RSS publics des revues scientifiques</p>
            <p style="margin-top: 6px;"><a href="https://github.com/mirakle88/CC_EndoNews" target="_blank">GitHub</a></p>
        </div>
    </footer>
</body>
</html>"""

    os.makedirs('output', exist_ok=True)
    with open('output/index.html', 'w', encoding='utf-8') as f:
        f.write(html)
    with open('output/articles.json', 'w', encoding='utf-8') as f:
        json.dump(all_articles, f, ensure_ascii=False, indent=2)

    print(f"\n-> Page HTML : output/index.html")
    print(f"-> Données   : output/articles.json")


def main():
    articles = fetch_all()
    generate_html(articles)


if __name__ == '__main__':
    main()
