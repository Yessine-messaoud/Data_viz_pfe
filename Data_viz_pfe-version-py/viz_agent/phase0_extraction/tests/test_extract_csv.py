import os
from viz_agent.phase0_extraction.pipeline import MetadataExtractor

def test_extract_csv():
    extractor = MetadataExtractor()
    # Remplacer par un chemin réel vers un CSV de test
    test_csv = os.path.join(os.path.dirname(__file__), "test_data", "sample.csv")
    if not os.path.exists(test_csv):
        print("Fichier de test CSV manquant :", test_csv)
        return
    model = extractor.extract(test_csv, enable_profiling=True)
    assert model.tables, "Aucune table extraite"
    for table in model.tables:
        print(f"Table: {table.name}")
        for col in table.columns:
            print(f"  Col: {col.name} | Profil: distinct={col.distinct_count}, null_ratio={col.null_ratio}")
    print("Extraction CSV OK")

if __name__ == "__main__":
    test_extract_csv()
