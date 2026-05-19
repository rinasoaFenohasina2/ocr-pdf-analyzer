import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Config:
    BASE_DIR = Path(__file__).parent.parent
    INPUT_DIR = BASE_DIR / os.getenv("INPUT_DIR", "inputs")
    OUTPUT_DIR = BASE_DIR / os.getenv("OUTPUT_DIR", "outputs")
    
    # Créer les dossiers s'ils n'existent pas
    INPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Tesseract
    TESSERACT_CMD = os.getenv("TESSERACT_CMD", "tesseract")
    TESSERACT_LANG = os.getenv("TESSERACT_LANG", "eng")
    TESSERACT_PSM = os.getenv("TESSERACT_PSM", "6")
    TESSERACT_OEM = os.getenv("TESSERACT_OEM", "3")
    
    # Options
    DEBUG = os.getenv("DEBUG_MODE", "false").lower() == "true"
    SAVE_IMAGES = os.getenv("SAVE_INTERMEDIATE_IMAGES", "true").lower() == "true"
    
    # DPI pour la conversion PDF
    PDF_DPI = 300