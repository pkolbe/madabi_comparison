import re
import pandas as pd

# Regex für DOIs
DOI_PATTERN = re.compile(r'(10\.\d{4,9}/\S+)', re.IGNORECASE)

def extract_doi(value):
    """
    Extrahiert die DOI aus einem String.
    Bereinigt danach störende Zeichen wie '",;: am Ende.
    """
    if pd.isna(value):
        return None
    
    s = str(value).strip()
    match = DOI_PATTERN.search(s)
    if not match:
        return None
    
    doi = match.group(1)

    # Entfernt unerwünschte Zeichen am Ende wie '",;.
    doi = doi.rstrip("',;:\" ")

    return doi


# -----------------------------------------------------------
# Pfade
input_path = "../data/raw/unified_mannheim_metadata_cleaned.csv"
output_path = "../data/processed/unified_mannheim_metadata_cleaned.csv"
# -----------------------------------------------------------

# Datei einlesen
df = pd.read_csv(input_path)

# Annahme: Die Spalte heißt "DOI"
df["DOI"] = df["DOI"].apply(extract_doi)

# Datei speichern
df.to_csv(output_path, index=False)

print("Fertig! Datei gespeichert unter:", output_path)
