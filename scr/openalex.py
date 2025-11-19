import requests
import csv
import time

BASE_URL = "https://api.openalex.org/works"

# ROR-ID der University of Mannheim
ROR_ID = "https://ror.org/031bsb921"

# E-Mail für das mailto-Parameter 
MAILTO = "phil.kolbe@uni-mannheim.de"

# Ausgabe-Datei
OUTPUT_CSV = "../data/raw/openalex.csv"


def normalize_doi(doi_url: str) -> str:
    """
    OpenAlex liefert den DOI meist als URL, z.B. 'https://doi.org/10.1234/abcd.1'.
    Diese Funktion schneidet das Präfix ab, so dass nur '10.1234/abcd.1' übrig bleibt.
    """
    if not doi_url:
        return ""
    prefix = "https://doi.org/"
    if doi_url.startswith(prefix):
        return doi_url[len(prefix):]
    return doi_url


def extract_authors(work: dict) -> str:
    """
    Nimmt ein Work-Objekt aus OpenAlex und extrahiert die Autorennamen
    aus work['authorships'][i]['author']['display_name'].

    Gibt einen String mit Namen, getrennt durch '; ', zurück.
    """
    authors = []
    for auth in work.get("authorships", []):
        author_info = auth.get("author") or {}
        name = author_info.get("display_name")
        if name:
            authors.append(name)
    return "; ".join(authors)


def fetch_works_for_institution(ror_id: str):
    """
    Generator, der alle Works zu einer Institution via ROR-ID aus OpenAlex holt.
    Es wird Cursor-Pagination verwendet, bis keine weiteren Ergebnisse mehr existieren.
    """
    cursor = "*"

    # Basisfilter: alle Werke, bei denen mind. ein Autor mit dieser Institution verbunden ist
    filter_parts = [f"institutions.ror:{ror_id}"]

    filter_parts.append("type:dataset")

    filter_param = ",".join(filter_parts)

    while True:
        params = {
            "filter": filter_param,
            "per-page": 200,        # maximal 200 pro Seite
            "cursor": cursor,       # Cursor-Pagination
            "mailto": MAILTO        # empfohlen, aber nicht zwingend
        }

        response = requests.get(BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()

        results = data.get("results", [])
        if not results:
            break

        for work in results:
            yield work

        # Nächsten Cursor holen; wenn keiner mehr da ist, sind wir fertig
        meta = data.get("meta", {})
        cursor = meta.get("next_cursor")
        if not cursor:
            break

        # kleine Pause, um nicht an Rate Limits zu rennen
        time.sleep(0.2)


def main():
    fieldnames = ["DOI", "Title", "Creators"]

    with open(OUTPUT_CSV, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        # Header schreiben
        writer.writeheader()

        count = 0
        for work in fetch_works_for_institution(ROR_ID):
            row = {
                "DOI": normalize_doi(work.get("doi", "")),
                "Title": work.get("title", ""),
                "Creators": extract_authors(work),
            }
            writer.writerow(row)
            count += 1

        print(f"Fertig. {count} Datensätze in '{OUTPUT_CSV}' geschrieben.")


if __name__ == "__main__":
    main()
