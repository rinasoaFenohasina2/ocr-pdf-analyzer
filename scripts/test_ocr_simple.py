"""Test minimal pour vérifier que Tesseract fonctionne"""

import pytesseract
from PIL import Image
from pdf2image import convert_from_path
from pathlib import Path

def quick_test():
    # Créer une image de test simple (texte noir sur blanc)
    from PIL import ImageDraw, ImageFont
    
    img = Image.new('RGB', (800, 200), color='white')
    draw = ImageDraw.Draw(img)
    draw.text((50, 50), "Test: 20/04/2026 EUR 4 790,54", fill='black')
    
    # Tester OCR
    text = pytesseract.image_to_string(img, lang='eng')
    print(f"OCR Result: {text}")
    
    if "EUR" in text:
        print("✅ Test réussi !")
        return True
    else:
        print("❌ Test échoué")
        return False

if __name__ == "__main__":
    quick_test()