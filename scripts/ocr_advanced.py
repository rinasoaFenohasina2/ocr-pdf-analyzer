"""Script OCR adapté spécifiquement au format du tableau avec pipes"""

import os
import json
import re
from pathlib import Path
from datetime import datetime
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

DEFAULT_LANG = "eng"
TESSERACT_CONFIG = f'--oem 3 --psm 6 -l {DEFAULT_LANG}'

INPUT_DIR = Path("inputs")
OUTPUT_DIR = Path("outputs")

class SpecificTableParser:
    """Parseur spécialisé pour le tableau avec pipes '|' """
    
    def extract_dates_from_header(self, text: str) -> List[str]:
        """Extrait les dates de l'en-tête"""
        # Chercher le pattern "du 20/04/2026 au 24/04/2026"
        match = re.search(r'du\s+(\d{2}/\d{2}/\d{4})\s+au\s+(\d{2}/\d{2}/\d{4})', text)
        if match:
            start = match.group(1)
            end = match.group(2)
            # Générer toutes les dates entre start et end
            from datetime import datetime, timedelta
            start_date = datetime.strptime(start, '%d/%m/%Y')
            end_date = datetime.strptime(end, '%d/%m/%Y')
            dates = []
            current = start_date
            while current <= end_date:
                dates.append(current.strftime('%Y-%m-%d'))
                current += timedelta(days=1)
            logger.info(f"Dates trouvées via intervalle: {dates}")
            return dates
        
        # Fallback: chercher les dates individuelles
        date_pattern = r'(\d{2}/\d{2}/\d{4})'
        dates = re.findall(date_pattern, text)
        dates = list(OrderedDict.fromkeys(dates))  # déduplication
        
        if dates:
            logger.info(f"Dates trouvées: {dates}")
            return [d.replace('/', '-') for d in dates]
        
        return []
    
    def clean_number(self, value: str) -> Optional[float]:
        """Nettoie un nombre"""
        if not value or value.upper() in ['N.D.', 'N.D', 'ND', '.', '', 'NO', 'IND']:
            return None
        
        # Enlever les caractères indésirables
        cleaned = value.strip()
        # Enlever les espaces
        cleaned = cleaned.replace(' ', '')
        # Remplacer virgule par point
        cleaned = cleaned.replace(',', '.')
        # Garder seulement chiffres, point et moins
        cleaned = re.sub(r'[^\d.-]', '', cleaned)
        
        try:
            return float(cleaned)
        except ValueError:
            return None
    
    def parse_line_with_pipes(self, line: str) -> Optional[tuple]:
        """Parse une ligne contenant des pipes | """
        # Séparer par pipe
        parts = [p.strip() for p in line.split('|')]
        
        if len(parts) < 3:
            return None
        
        # La première partie contient pays + code devise
        first_part = parts[0].strip()
        
        # Extraire pays et devise
        # Pattern: pays suivi d'un code devise (3 lettres majuscules)
        # Exemple: "COMMUNAUTE EUROPENNE aun" ou "ETATS:UNIS DOLLAR: aa"
        
        # Chercher un code devise de 3 lettres
        match = re.search(r'([A-Z]{3})$', first_part)
        if not match:
            # Essayer de trouver un code devise commun
            common_codes = ['EUR', 'USD', 'GBP', 'CHF', 'JPY', 'CAD', 'DKK', 'NOK', 'SEK', 'XDR']
            for code in common_codes:
                if code in first_part:
                    currency_code = code
                    country = first_part.replace(code, '').strip()
                    # Nettoyer le pays
                    country = re.sub(r'[^A-Za-zÀ-ÿ\s-]', '', country).strip()
                    break
            else:
                return None
        else:
            currency_code = match.group(1)
            country = first_part.replace(currency_code, '').strip()
            country = re.sub(r'[^A-Za-zÀ-ÿ\s-]', '', country).strip()
        
        # Les valeurs sont dans les parties suivantes
        values = []
        for part in parts[1:]:
            # Nettoyer la valeur (enlever les caractères spéciaux)
            val = re.sub(r'[^\d\s,\.]', '', part).strip()
            if val:
                values.append(val)
        
        return (country, currency_code, values)
    
    def parse_line_plain(self, line: str) -> Optional[tuple]:
        """Parse une ligne sans pipes (format texte simple)"""
        # Pattern: pays + code devise (3 lettres) + valeurs
        # Exemple: "COMMUNAUTE EUROPENNE EUR 4790,54 4793,12"
        
        # Trouver le code devise (3 lettres majuscules)
        match = re.match(r'^(.+?)\s+([A-Z]{3})\s+(.+)$', line.strip())
        if not match:
            return None
        
        country = match.group(1).strip()
        currency_code = match.group(2)
        values_str = match.group(3).strip().split()
        
        # Nettoyer le pays (enlever caractères spéciaux)
        country = re.sub(r'[^A-Za-zÀ-ÿ\s-]', '', country).strip()
        
        return (country, currency_code, values_str)
    
    def parse_text(self, text: str) -> tuple:
        """Parse le texte OCR complet"""
        lines = text.strip().split('\n')
        
        # 1. Extraire les dates
        dates = self.extract_dates_from_header(text)
        
        # 2. Trouver où commence le tableau
        start_idx = 0
        for i, line in enumerate(lines):
            if '|' in line or ('EUR' in line and 'USD' in line):
                start_idx = i
                break
        
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
            
            if not currency_code or currency_code in ['IND', 'NO']:
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
                    currencies[currency_code]['rates'][date] = rate
        
        return dates, currencies

class OCRProcessor:
    def __init__(self):
        self.parser = SpecificTableParser()
    
    def process_pdf(self, pdf_path: Path) -> Dict[str, Any]:
        logger.info(f"Traitement de {pdf_path}")
        
        # Convertir PDF en images
        images = convert_from_path(str(pdf_path), dpi=300)
        logger.info(f"PDF converti en {len(images)} page(s)")
        
        all_text = []
        combined_text = ""
        
        for i, img in enumerate(images):
            logger.info(f"OCR sur la page {i+1}...")
            text = pytesseract.image_to_string(img, config=TESSERACT_CONFIG)
            all_text.append(text)
            combined_text += text + "\n"
        
        # Sauvegarder texte brut pour debug
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
                if rate is not None:
                    flat_rates.append({
                        "date": date,
                        "country": curr_data['country'],
                        "currency_code": curr_code,
                        "exchange_rate": rate
                    })
        
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
    INPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    pdf_files = list(INPUT_DIR.glob("*.pdf"))
    if not pdf_files:
        logger.error(f"Aucun PDF trouvé dans {INPUT_DIR}")
        return
    
    processor = OCRProcessor()
    result = processor.process_pdf(pdf_files[0])
    
    output_file = OUTPUT_DIR / "exchange_rates.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    logger.success(f"Résultat sauvegardé dans {output_file}")
    
    # Afficher résumé
    print("\n" + "="*60)
    print("📊 RÉSUMÉ DE L'EXTRACTION")
    print("="*60)
    print(f"📅 Dates: {result['metadata']['date_range']['start']} → {result['metadata']['date_range']['end']}")
    print(f"💰 Devises trouvées: {result['metadata']['currencies_found']}")
    print(f"📈 Taux extraits: {result['metadata']['total_rates']}")
    
    if result['rates']:
        print("\n📝 Exemple de taux extraits:")
        for rate in result['rates'][:5]:
            print(f"   {rate['date']} | {rate['currency_code']} | {rate['country'][:20]}... | {rate['exchange_rate']}")

if __name__ == "__main__":
    main()