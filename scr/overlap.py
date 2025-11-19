#!/usr/bin/env python3
import csv
import re

FILE_MADABI = "../data/processed/unified_mannheim_metadata_cleaned.csv"
FILE_OPENAIRE = "../data/raw/openaire.csv"
FILE_OPENALEX = "../data/raw/openalex.csv"

OUT_OVERLAP_OPENAIRE = "../data/processed/openaire_madabi_overlap.csv"
OUT_OVERLAP_OPENALEX = "../data/processed/openalex_madabi_overlap.csv"
OUT_MADABI_UPDATED = "../data/processed/unified_mannheim_metadata_cleaned_with_overlap.csv"

KEY = "DOI"  # Spaltenname der DOI in MADABI


def normalize_doi(raw):
    if raw is None:
        return ""
    s = str(raw).strip().lower()
    # remove URL prefixes
    s = re.sub(r'^https?://(dx\.)?doi\.org/', '', s)
    # remove leading 'doi:', 'doi =' or similar
    s = re.sub(r'^doi[:\s=]+', '', s)
    s = s.strip()
    # capture core DOI-like token (allow digits, letters, dot, slash, dash, underscore)
    m = re.match(r'([0-9a-z./\-_]+)', s)
    if m:
        s = m.group(1)
    # optionally remove simple version suffixes like '.v1' or '/v1' if they appear at the end
    s = re.sub(r'(\.v|/v)\d+$', '', s)
    return s


def load_generic(path, doi_field, title_field, creators_field):
    """
    Generische Loader-Funktion für eine CSV-Datei mit DOI, Titel und Creators.
    """
    doi_map = {}
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            raw = r.get(doi_field)
            doi = normalize_doi(raw)
            if not doi:
                continue
            if doi not in doi_map:
                doi_map[doi] = {
                    "DOI": doi,
                    "Title": (r.get(title_field) or "").strip(),
                    "Creators": (r.get(creators_field) or "").strip()
                }
    return doi_map


def load_openaire(path):
    # erwartet Spaltennamen: "DOI", "Title", "Creators"
    return load_generic(path, doi_field="DOI", title_field="Title", creators_field="Creators")


def load_openalex(path):
    # erwartet Spaltennamen: "DOI", "Title", "Creators"
    return load_generic(path, doi_field="DOI", title_field="Title", creators_field="Creators")


def main():
    openaire = load_openaire(FILE_OPENAIRE)
    openalex = load_openalex(FILE_OPENALEX)

    # Read MADABI, normalize DOIs, mark overlap and write updated MADABI
    with open(FILE_MADABI, newline='', encoding='utf-8') as f_in, \
         open(OUT_MADABI_UPDATED, 'w', newline='', encoding='utf-8') as f_out:

        reader = csv.DictReader(f_in)
        fieldnames = list(reader.fieldnames)

        # neue Overlap-Spalten anhängen, falls nicht vorhanden
        for col in ["overlap openaire", "overlap openalex"]:
            if col not in fieldnames:
                fieldnames.append(col)

        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()

        madabi_rows = []
        for r in reader:
            raw = r.get(KEY)
            doi_norm = normalize_doi(raw)

            overlap_openaire = "1" if doi_norm and doi_norm in openaire else "0"
            overlap_openalex = "1" if doi_norm and doi_norm in openalex else "0"

            r["overlap openaire"] = overlap_openaire
            r["overlap openalex"] = overlap_openalex

            writer.writerow(r)
            madabi_rows.append((r, doi_norm))

    # Write overlaps from openaire that match madabi (unique DOIs)
    with open(OUT_OVERLAP_OPENAIRE, 'w', newline='', encoding='utf-8') as f_overlap_oa:
        out_fields = ["DOI", "Title", "Creators"]
        writer_oa = csv.DictWriter(f_overlap_oa, fieldnames=out_fields)
        writer_oa.writeheader()
        written_oa = set()
        for _, doi_norm in madabi_rows:
            if doi_norm and doi_norm in openaire and doi_norm not in written_oa:
                writer_oa.writerow(openaire[doi_norm])
                written_oa.add(doi_norm)

    # Write overlaps from openalex that match madabi (unique DOIs)
    with open(OUT_OVERLAP_OPENALEX, 'w', newline='', encoding='utf-8') as f_overlap_ox:
        out_fields = ["DOI", "Title", "Creators"]
        writer_ox = csv.DictWriter(f_overlap_ox, fieldnames=out_fields)
        writer_ox.writeheader()
        written_ox = set()
        for _, doi_norm in madabi_rows:
            if doi_norm and doi_norm in openalex and doi_norm not in written_ox:
                writer_ox.writerow(openalex[doi_norm])
                written_ox.add(doi_norm)

    print(
        f"Fertig. '{OUT_MADABI_UPDATED}' geschrieben, "
        f"'{OUT_OVERLAP_OPENAIRE}' mit {len(written_oa)} Einträgen und "
        f"'{OUT_OVERLAP_OPENALEX}' mit {len(written_ox)} Einträgen erzeugt."
    )


if __name__ == "__main__":
    main()
