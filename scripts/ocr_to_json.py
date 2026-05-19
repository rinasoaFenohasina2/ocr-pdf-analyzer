import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime
from loguru import logger

import pytesseract
from PIL import Image
from pdf2image import convert_from_path

# ===== CONFIGURATION TESSERACT =====
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if Path(TESSERACT_PATH).exists():
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
    logger.info(f"✅ Tesseract trouvé: {TESSERACT_PATH}")
else:
    logger.warning("Tesseract non trouvé, utilisation du PATH par défaut")

# Configuration pour l'anglais (pas besoin de fichier de langue supplémentaire)
DEFAULT_LANG = "eng"  # ← CHANGÉ DE 'fra' VERS 'eng'
TESSERACT_CONFIG = f'--oem 3 --psm 6 -l {DEFAULT_LANG}'

INPUT_DIR = Path("inputs")
OUTPUT_DIR = Path("outputs")

def extract_table_to_json(pdf_path: Path, output_path: Path):
    """Extrait un tableau de taux de change d'un PDF vers JSON"""
    
    logger.info(f"Traitement de {pdf_path}")
    logger.info(f"Langue OCR: {DEFAULT_LANG}")
    
    try:
        # Convertir PDF en images
        images = convert_from_path(str(pdf_path), dpi=300)
        logger.info(f"PDF converti en {len(images)} page(s)")
    except Exception as e:
        logger.error(f"Erreur conversion PDF: {e}")
        return None
    
    all_text = []
    
    for i, img in enumerate(images):
        logger.info(f"OCR sur la page {i+1}...")
        
        # Extraire texte avec config anglaise
        try:
            text = pytesseract.image_to_string(img, config=TESSERACT_CONFIG)
            all_text.append(text)
            logger.info(f"   → {len(text)} caractères extraits")
        except Exception as e:
            logger.error(f"Erreur OCR page {i+1}: {e}")
            all_text.append("")
        
        # Sauvegarder l'image (debug)
        OUTPUT_DIR.mkdir(exist_ok=True)
        img.save(OUTPUT_DIR / f"page_{i+1}_raw.png")
    
    # Sauvegarder le texte brut
    with open(OUTPUT_DIR / "raw_text.txt", "w", encoding="utf-8") as f:
        for i, text in enumerate(all_text):
            f.write(f"\n{'='*60}\nPAGE {i+1}\n{'='*60}\n")
            f.write(text)
    
    # Version JSON simplifiée
    result = {
        "metadata": {
            "source": str(pdf_path),
            "extraction_date": datetime.now().isoformat(),
            "pages": len(images),
            "ocr_language": DEFAULT_LANG,
            "ocr_engine": f"Tesseract {pytesseract.get_tesseract_version()}"
        },
        "pages_raw_text": all_text
    }
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    logger.success(f"Résultat sauvegardé dans {output_path}")
    
    # Afficher un aperçu
    print("\n" + "="*60)
    print("📝 APERÇU DU TEXTE EXTRAIT (page 1):")
    print("="*60)
    print(all_text[0][:1000] if all_text else "(vide)")
    
    return result

def main():
    # Créer les dossiers si nécessaire
    INPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Chercher tous les PDFs dans inputs
    pdf_files = list(INPUT_DIR.glob("*.pdf"))
    
    if not pdf_files:
        logger.error(f"Aucun PDF trouvé dans {INPUT_DIR}")
        logger.info(f"Placez votre PDF dans {INPUT_DIR.absolute()}")
        return
    
    # Prendre le premier PDF
    input_file = pdf_files[0]
    logger.info(f"Fichier trouvé: {input_file.name}")
    
    output_file = OUTPUT_DIR / f"{input_file.stem}_output.json"
    extract_table_to_json(input_file, output_file)

if __name__ == "__main__":
    main()