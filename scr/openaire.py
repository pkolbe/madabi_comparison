import requests
import csv

# -------------------------------------------------------------------
# 1) Organisation "University of Mannheim" über ROR finden
# -------------------------------------------------------------------

ROR_ID = "https://ror.org/031bsb921"

ORG_SEARCH_URL = "https://api.openaire.eu/graph/v1/organizations"
RP_SEARCH_URL = "https://api.openaire.eu/graph/v2/researchProducts"

def get_org_id_from_ror(ror_id: str) -> str:
    """
    Holt die OpenAIRE-Organisations-ID für eine gegebene ROR-URL.
    Benutzt den Query-Parameter `pid` für Organisationen.:contentReference[oaicite:2]{index=2}
    """
    params = {
        "pid": ror_id,
        "pageSize": 1
    }
    resp = requests.get(ORG_SEARCH_URL, params=params)
    resp.raise_for_status()
    data = resp.json()

    results = data.get("results", [])
    if not results:
        raise RuntimeError(f"Keine Organisation für ROR {ror_id} gefunden.")

    org = results[0]
    org_id = org.get("id")
    legal_name = org.get("legalName", "(ohne Name)")
    print(f"Gefundene Organisation: {legal_name} (id={org_id})")

    if not org_id:
        raise RuntimeError("Organisation gefunden, aber keine 'id' im Ergebnis.")
    return org_id


# -------------------------------------------------------------------
# 2) Datasets (researchProducts type=dataset) für diese Organisation holen
# -------------------------------------------------------------------

def extract_doi(product: dict) -> str:
    """
    Versucht, einen DOI aus den PIDs und ggf. Instanz-Alternativ-IDs zu ziehen.
    """
    if not isinstance(product, dict):
        return ""

    # Zuerst pids auf oberster Ebene – wenn None, dann leere Liste
    pids = product.get("pids") or []
    for pid in pids:
        if not isinstance(pid, dict):
            continue
        if pid.get("scheme", "").lower() == "doi":
            return pid.get("value", "")

    # Falls dort nichts, in instances[].alternateIdentifiers nach 'doi' schauen
    instances = product.get("instances") or []
    for inst in instances:
        if not isinstance(inst, dict):
            continue
        for alt in inst.get("alternateIdentifiers") or []:
            if not isinstance(alt, dict):
                continue
            if alt.get("scheme", "").lower() == "doi":
                return alt.get("value", "")

    return ""


def extract_title(product: dict) -> str:
    """
    Titel aus dem Feld mainTitle.:contentReference[oaicite:4]{index=4}
    """
    return product.get("mainTitle", "")


def extract_authors(product: dict) -> str:
    authors = product.get("authors") or []
    names = [a.get("fullName") for a in authors if isinstance(a, dict) and a.get("fullName")]
    return "; ".join(names)


def fetch_datasets_for_org(org_id: str, max_pages: int = 1000):
    """
    Holt alle Research Products vom Typ 'dataset' mit Beziehung zur gegebenen Organisation.
    Nutzt:
      - type=dataset, um nur Daten zu holen:contentReference[oaicite:6]{index=6}
      - relOrganizationId=<org_id>, um auf die Organisation zu filtern:contentReference[oaicite:7]{index=7}
      - cursor-basierte Pagination
    """
    all_items = []

    params = {
        "type": "dataset",
        "relOrganizationId": org_id,
        "pageSize": 100,
        "cursor": "*"  # initialer Cursor
    }

    for _ in range(max_pages):
        resp = requests.get(RP_SEARCH_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

        header = data.get("header", {})
        results = data.get("results", [])
        print(f"Seite: {header.get('page')} – Datensätze in dieser Seite: {len(results)}")

        for rp in results:
            row = {
                "DOI": extract_doi(rp),
                "Title": extract_title(rp),
                "Creators": extract_authors(rp),
            }
            all_items.append(row)

        next_cursor = header.get("nextCursor")
        if not next_cursor:
            break

        params["cursor"] = next_cursor

    return all_items


# -------------------------------------------------------------------
# 3) CSV schreiben
# -------------------------------------------------------------------

def write_csv(rows, filename: str):
    fieldnames = ["DOI", "Title", "Creators"]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    print(f"CSV geschrieben: {filename} (Zeilen: {len(rows)})")


# -------------------------------------------------------------------
# 4) Alles zusammen ausführen
# -------------------------------------------------------------------

if __name__ == "__main__":
    # 1) Organisations-ID holen
    org_id = get_org_id_from_ror(ROR_ID)

    # 2) Datasets für diese Organisation holen
    datasets = fetch_datasets_for_org(org_id)

    # 3) In CSV speichern
    write_csv(datasets, '../data/raw/openaire.csv')
