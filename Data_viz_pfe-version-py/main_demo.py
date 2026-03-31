import os
import shutil
import sys
import pandas as pd
from pathlib import Path

INPUT_DIR = Path('input')
OUTPUT_DIR = Path('output')
DASHBOARD_PATH = OUTPUT_DIR / 'dashboard_demo.html'

STEPS = [
    {'name': 'Vérification du fichier input', 'status': 'KO', 'details': ''},
    {'name': 'Export RDL (copie brute)', 'status': 'KO', 'details': ''},
    {'name': 'Aperçu du fichier', 'status': 'KO', 'details': ''},
]


def main():
    if len(sys.argv) < 2:
        print('Usage: python main_demo.py <nom_fichier>')
        sys.exit(1)
    filename = sys.argv[1]
    input_path = INPUT_DIR / filename
    output_path = OUTPUT_DIR / (Path(filename).stem + '.rdl')

    # Étape 1: Vérification input
    if input_path.exists():
        STEPS[0]['status'] = 'OK'
        STEPS[0]['details'] = f'Fichier trouvé: {input_path}'
    else:
        STEPS[0]['details'] = f'Fichier introuvable: {input_path}'
        write_dashboard(None)
        sys.exit(1)

    # Étape 2: Export RDL (copie brute)
    try:
        shutil.copy(input_path, output_path)
        STEPS[1]['status'] = 'OK'
        STEPS[1]['details'] = f'Exporté vers: {output_path}'
    except Exception as e:
        STEPS[1]['details'] = f'Erreur export: {e}'
        write_dashboard(None)
        sys.exit(1)

    # Étape 3: Aperçu du fichier (si CSV)
    preview_html = ''
    if filename.lower().endswith('.csv'):
        try:
            df = pd.read_csv(input_path, nrows=5)
            preview_html = df.to_html(index=False)
            STEPS[2]['status'] = 'OK'
            STEPS[2]['details'] = 'Aperçu généré (5 premières lignes)'
        except Exception as e:
            STEPS[2]['details'] = f'Erreur lecture CSV: {e}'
    else:
        STEPS[2]['details'] = 'Aperçu non disponible pour ce format.'

    write_dashboard(preview_html)
    print(f'Dashboard généré: {DASHBOARD_PATH}')


def write_dashboard(preview_html):
    rows = ''
    for step in STEPS:
        color = '#c8e6c9' if step['status'] == 'OK' else '#ffcdd2'
        rows += f"<tr style='background:{color}'><td>{step['name']}</td><td>{step['status']}</td><td>{step['details']}</td></tr>"
    html = f"""
    <html><head><title>Demo Pipeline Dashboard</title></head><body>
    <h2>État du pipeline de démo</h2>
    <table border='1' cellpadding='6'>
        <tr><th>Étape</th><th>Statut</th><th>Détails</th></tr>
        {rows}
    </table>
    <h3>Aperçu du fichier (si CSV)</h3>
    {preview_html or '<i>Aucun aperçu disponible.</i>'}
    </body></html>
    """
    with open(DASHBOARD_PATH, 'w', encoding='utf-8') as f:
        f.write(html)

if __name__ == '__main__':
    main()
