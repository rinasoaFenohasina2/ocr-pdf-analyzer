#!/usr/bin/env python
"""Script de vérification des prérequis"""

import sys
import subprocess
from pathlib import Path

def check_python():
    print(f"✅ Python version: {sys.version}")
    return True

def check_poetry_packages():
    try:
        import pytesseract
        from PIL import Image
        import cv2
        from pdf2image import convert_from_path
        print("✅ All Python packages installed")
        return True
    except ImportError as e:
        print(f"❌ Missing package: {e}")
        return False

def check_tesseract():
    try:
        result = subprocess.run(
            ["tesseract", "--version"], 
            capture_output=True, 
            text=True
        )
        if result.returncode == 0:
            print("✅ Tesseract installed")
            # Vérifier la langue française
            result = subprocess.run(
                ["tesseract", "--list-langs"], 
                capture_output=True, 
                text=True
            )
            if "eng" in result.stdout:
                print("✅ English language pack available")
            else:
                print("⚠️  English language pack not found")
            return True
    except FileNotFoundError:
        print("❌ Tesseract not found in PATH")
        return False

def check_poppler():
    try:
        # Test simple : juste vérifier que la commande existe
        subprocess.run(["pdfinfo", "-v"], capture_output=True, text=True)
        print("✅ Poppler utils installed")
        return True
    except FileNotFoundError:
        print("❌ Poppler utils not found")
        return False

def main():
    print("🔍 Vérification des prérequis...\n")
    
    checks = [
        ("Python", check_python),
        ("Poetry packages", check_poetry_packages),
        ("Tesseract", check_tesseract),
        ("Poppler", check_poppler),
    ]
    
    all_passed = True
    for name, check_func in checks:
        if not check_func():
            all_passed = False
        print()
    
    if all_passed:
        print("🎉 Tous les prérequis sont satisfaits !")
        sys.exit(0)
    else:
        print("❌ Certains prérequis sont manquants. Voir les messages ci-dessus.")
        sys.exit(1)

if __name__ == "__main__":
    main()