"""Script OCR adapté spécifiquement au format du tableau avec pipes - VERSION FINALE"""

import os
import json
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from collections import OrderedDict

import pytesseract
from PIL import Image
from pdf2image import convert_from_path
from loguru import logger

# ===== CONFIGURATION =====
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if Path(TESSERACT_PATH).exists():
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
    logger.info(f"✅ Tesseract trouvé: {TESSERACT_PATH}")

DEFAULT_LANG = "eng"  # Anglais fonctionne bien, meilleur support
TESSERACT_CONFIG = f'--oem 3 --psm 6 -l {DEFAULT_LANG}'

INPUT_DIR = Path("inputs")
OUTPUT_DIR = Path("outputs")

class SpecificTableParser:
    """Parseur spécialisé pour le tableau à la française"""
    
    def extract_dates_from_header(self, text: str) -> List[str]:
        """Extrait les dates de l'en-tête (format: du JJ/MM/AAAA au JJ/MM/AAAA)"""
        # Pattern pour "du 20/04/2026 au 24/04/2026"
        match = re.search(r'du\s+(\d{2}/\d{2}/\d{4})\s+au\s+(\d{2}/\d{2}/\d{4})', text)
        if match:
            start_str = match.group(1)
            end_str = match.group(2)
            
            start_date = datetime.strptime(start_str, '%d/%m/%Y')
            end_date = datetime.strptime(end_str, '%d/%m/%Y')
            
            dates = []
            current = start_date
            while current <= end_date:
                dates.append(current.strftime('%Y-%m-%d'))
                current += timedelta(days=1)
            
            logger.info(f"✅ Dates extraites via intervalle: {len(dates)} jours ({dates[0]} → {dates[-1]})")
            return dates
        
        # Fallback: chercher les dates individuelles dans le texte
        date_pattern = r'(\d{2}/\d{2}/\d{4})'
        matches = re.findall(date_pattern, text)
        
        # Garder l'ordre et dédupliquer
        seen = set()
        unique_dates = []
        for d in matches:
            if d not in seen:
                seen.add(d)
                # Convertir en format ISO
                unique_dates.append(datetime.strptime(d, '%d/%m/%Y').strftime('%Y-%m-%d'))
        
        if unique_dates:
            logger.info(f"✅ Dates trouvées (fallback): {unique_dates}")
            return unique_dates
        
        logger.warning("⚠️ Aucune date trouvée")
        return []
    
    def clean_number(self, value: str) -> Optional[float]:
        """Nettoie un nombre (supprime espaces, convertit virgule, gère N.D.)"""
        if not value or not value.strip():
            return None
        
        value = value.strip().upper()
        
        # Valeurs non disponibles
        if value in ['N.D.', 'N.D', 'ND', 'N.D,', '.', '...', 'NO', 'IND', '']:
            return None
        
        # Garder seulement chiffres, virgule, point, tiret
        cleaned = re.sub(r'[^\d\s,\.-]', '', value)
        
        # Enlever les espaces
        cleaned = cleaned.replace(' ', '')
        
        # Remplacer virgule européenne par point
        cleaned = cleaned.replace(',', '.')
        
        # Enlever les points de milliers (si format 1.234,56 → on veut 1234.56)
        # Mais attention à ne pas tout casser
        if cleaned.count('.') > 1:
            # Si plusieurs points, c'est probablement des milliers
            parts = cleaned.split('.')
            cleaned = ''.join(parts[:-1]) + '.' + parts[-1]
        
        try:
            return float(cleaned)
        except ValueError:
            return None
    
    def parse_line_with_pipes(self, line: str) -> Optional[tuple]:
        """Parse une ligne contenant des pipes | (format tableau)"""
        # Séparer par pipe
        parts = [p.strip() for p in line.split('|')]
        
        if len(parts) < 2:
            return None
        
        # La première partie contient pays + code devise
        first_part = parts[0].strip()
        if not first_part:
            return None
        
        # Extraire le code devise (3 lettres majuscules)
        # Liste des codes communs
        common_codes = ['EUR', 'USD', 'GBP', 'CHF', 'JPY', 'CAD', 'DKK', 'NOK', 'SEK', 
                        'XDR', 'AUD', 'HKD', 'SGD', 'NZD', 'ZAR', 'CNY', 'INR', 'BRL']
        
        currency_code = None
        country = first_part
        
        for code in common_codes:
            if code in first_part:
                currency_code = code
                country = first_part.replace(code, '').strip()
                break
        
        # Si pas trouvé, chercher un pattern de 3 lettres majuscules
        if not currency_code:
            match = re.search(r'([A-Z]{3})$', first_part)
            if match:
                currency_code = match.group(1)
                country = first_part.replace(currency_code, '').strip()
        
        if not currency_code:
            return None
        
        # Nettoyer le pays (enlever les caractères spéciaux)
        country = re.sub(r'[^A-Za-zÀ-ÿ\s\-]', '', country).strip()
        # Nettoyer les caractères bizarres comme ':'
        country = re.sub(r'[:\*]', '', country)
        
        # Les valeurs sont dans les parties suivantes
        values = []
        for part in parts[1:]:
            # Nettoyer la valeur
            val = re.sub(r'[^\d\s,\.]', '', part).strip()
            if val:
                values.append(val)
        
        if not values:
            return None
        
        return (country, currency_code, values)
    
    def parse_line_plain(self, line: str) -> Optional[tuple]:
        """Parse une ligne sans pipes (fallback)"""
        # Pattern: pays + code devise + valeurs
        # Exemple: "COMMUNAUTE EUROPEENNE EUR 4 790,54 4 793,12"
        
        # Trouver le code devise
        common_codes = ['EUR', 'USD', 'GBP', 'CHF', 'JPY', 'CAD', 'DKK', 'NOK', 'SEK', 'XDR']
        
        best_match = None
        best_code = None
        
        for code in common_codes:
            if code in line:
                # Trouver la position du code
                pos = line.find(code)
                if best_match is None or pos < best_match:
                    best_match = pos
                    best_code = code
        
        if not best_code:
            # Chercher pattern générique
            match = re.search(r'([A-Z]{3})\s+', line)
            if match:
                best_code = match.group(1)
                best_match = line.find(best_code)
        
        if not best_code:
            return None
        
        # Extraire pays (avant le code)
        country = line[:best_match].strip()
        
        # Extraire valeurs (après le code)
        after_code = line[best_match + len(best_code):].strip()
        values = after_code.split()
        
        # Nettoyer pays
        country = re.sub(r'[^A-Za-zÀ-ÿ\s\-]', '', country).strip()
        
        return (country, best_code, values)
    
    def parse_text(self, text: str) -> tuple:
        """Parse le texte OCR complet"""
        lines = text.strip().split('\n')
        
        # 1. Extraire les dates
        dates = self.extract_dates_from_header(text)
        
        # 2. Trouver où commence le tableau
        start_idx = 0
        for i, line in enumerate(lines):
            # Chercher une ligne qui ressemble à une ligne de tableau
            if ('|' in line or 
                any(code in line for code in ['EUR', 'USD', 'GBP']) or
                (len(line) > 20 and re.search(r'[A-Z]{3}', line))):
                start_idx = i
                break
        
        logger.info(f"Début du tableau détecté à la ligne {start_idx}")
        
        # 3. Parser chaque ligne
        currencies = OrderedDict()
        
        for line in lines[start_idx:]:
            if not line.strip() or len(line.strip()) < 10:
                continue
            
            # Essayer d'abord le format avec pipes
            parsed = self.parse_line_with_pipes(line)
            
            # Si pas de pipes, essayer format simple
            if not parsed:
                parsed = self.parse_line_plain(line)
            
            if not parsed:
                continue
            
            country, currency_code, values = parsed
            
            # Ignorer les codes invalides
            if not currency_code or len(currency_code) != 3:
                continue
            
            if currency_code not in currencies:
                currencies[currency_code] = {
                    'country': country,
                    'currency_code': currency_code,
                    'rates': {}
                }
            
            # Aligner valeurs avec dates
            for i, date in enumerate(dates):
                if i < len(values):
                    rate = self.clean_number(values[i])
                    if rate is not None:  # Ne garder que les valeurs valides
                        currencies[currency_code]['rates'][date] = rate
        
        return dates, currencies

class OCRProcessor:
    def __init__(self):
        self.parser = SpecificTableParser()
    
    def process_pdf(self, pdf_path: Path) -> Dict[str, Any]:
        logger.info(f"📄 Traitement de {pdf_path}")
        
        # Convertir PDF en images
        images = convert_from_path(str(pdf_path), dpi=300)
        logger.info(f"📸 PDF converti en {len(images)} page(s)")
        
        all_text = []
        combined_text = ""
        
        for i, img in enumerate(images):
            logger.info(f"🔍 OCR sur la page {i+1}...")
            text = pytesseract.image_to_string(img, config=TESSERACT_CONFIG)
            all_text.append(text)
            combined_text += text + "\n"
        
        # Sauvegarder texte brut pour debug
        OUTPUT_DIR.mkdir(exist_ok=True)
        with open(OUTPUT_DIR / "debug_raw_text.txt", "w", encoding="utf-8") as f:
            f.write(combined_text)
        
        # Parser
        dates, currencies = self.parser.parse_text(combined_text)
        
        # Construire résultat
        return self.build_result(pdf_path, dates, currencies, all_text)
    
    def build_result(self, pdf_path: Path, dates: List[str], 
                     currencies: Dict, raw_texts: List[str]) -> Dict:
        
        # Format liste plate
        flat_rates = []
        for curr_code, curr_data in currencies.items():
            for date, rate in curr_data['rates'].items():
                flat_rates.append({
                    "date": date,
                    "country": curr_data['country'],
                    "currency_code": curr_code,
                    "exchange_rate": rate
                })
        
        # Trier par date
        flat_rates.sort(key=lambda x: x['date'])
        
        return {
            "metadata": {
                "source_file": str(pdf_path.name),
                "extraction_date": datetime.now().isoformat(),
                "pages_processed": len(raw_texts),
                "ocr_language": DEFAULT_LANG,
                "date_range": {
                    "start": dates[0] if dates else None,
                    "end": dates[-1] if dates else None,
                    "count": len(dates)
                },
                "currencies_found": len(currencies),
                "total_rates": len(flat_rates)
            },
            "dates": dates,
            "currencies": {
                code: {
                    "country": data['country'],
                    "rates": data['rates']
                }
                for code, data in currencies.items()
            },
            "rates": flat_rates
        }

def main():
    """Point d'entrée principal"""
    # Créer les dossiers
    INPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Trouver les PDFs
    pdf_files = list(INPUT_DIR.glob("*.pdf"))
    if not pdf_files:
        logger.error(f"❌ Aucun PDF trouvé dans {INPUT_DIR}")
        logger.info(f"Placez votre PDF dans {INPUT_DIR.absolute()}")
        return
    
    input_file = pdf_files[0]
    logger.info(f"📁 Fichier trouvé: {input_file.name}")
    
    # Traiter
    processor = OCRProcessor()
    result = processor.process_pdf(input_file)
    
    # Sauvegarder
    output_file = OUTPUT_DIR / f"{input_file.stem}_structured.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    logger.success(f"✅ Résultat sauvegardé dans {output_file}")
    
    # Afficher résumé
    print("\n" + "="*60)
    print("📊 RÉSUMÉ DE L'EXTRACTION")
    print("="*60)
    print(f"📅 Période: {result['metadata']['date_range']['start']} → {result['metadata']['date_range']['end']}")
    print(f"💰 Devises trouvées: {result['metadata']['currencies_found']}")
    print(f"📈 Taux extraits: {result['metadata']['total_rates']}")
    
    if result['currencies']:
        print("\n🏦 Devises détectées:")
        for code in list(result['currencies'].keys())[:10]:
            print(f"   - {code}")
    
    if result['rates']:
        print("\n📝 Exemple de taux extraits (premiers):")
        for rate in result['rates'][:5]:
            print(f"   {rate['date']} | {rate['currency_code']} | {rate['country'][:20]}... | {rate['exchange_rate']}")

if __name__ == "__main__":
    main()