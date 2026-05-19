"""Script OCR avec export JSON + Excel"""

import os
import json
import re
import csv
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from collections import OrderedDict

import pytesseract
import pandas as pd
from PIL import Image
from pdf2image import convert_from_path
from loguru import logger
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows

# ===== CONFIGURATION =====
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if Path(TESSERACT_PATH).exists():
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
    logger.info(f"✅ Tesseract trouvé: {TESSERACT_PATH}")

DEFAULT_LANG = "eng"
TESSERACT_CONFIG = f'--oem 3 --psm 6 -l {DEFAULT_LANG}'

INPUT_DIR = Path("inputs")
OUTPUT_DIR = Path("outputs")
EXCEL_DIR = Path("outputs/excel")  # Dossier pour les Excel

class SpecificTableParser:
    """Parseur spécialisé pour le tableau à la française"""
    
    def extract_dates_from_header(self, text: str) -> List[str]:
        """Extrait les dates de l'en-tête"""
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
            logger.info(f"✅ Dates extraites: {len(dates)} jours")
            return dates
        
        date_pattern = r'(\d{2}/\d{2}/\d{4})'
        matches = re.findall(date_pattern, text)
        seen = set()
        unique_dates = []
        for d in matches:
            if d not in seen:
                seen.add(d)
                unique_dates.append(datetime.strptime(d, '%d/%m/%Y').strftime('%Y-%m-%d'))
        return unique_dates
    
    def clean_number(self, value: str) -> Optional[float]:
        """Nettoie un nombre"""
        if not value or not value.strip():
            return None
        value = value.strip().upper()
        if value in ['N.D.', 'N.D', 'ND', 'N.D,', '.', '...', 'NO', 'IND', '']:
            return None
        cleaned = re.sub(r'[^\d\s,\.-]', '', value)
        cleaned = cleaned.replace(' ', '').replace(',', '.')
        if cleaned.count('.') > 1:
            parts = cleaned.split('.')
            cleaned = ''.join(parts[:-1]) + '.' + parts[-1]
        try:
            return float(cleaned)
        except ValueError:
            return None
    
    def parse_line_with_pipes(self, line: str) -> Optional[tuple]:
        """Parse une ligne avec pipes |"""
        parts = [p.strip() for p in line.split('|')]
        if len(parts) < 2:
            return None
        first_part = parts[0].strip()
        if not first_part:
            return None
        
        common_codes = ['EUR', 'USD', 'GBP', 'CHF', 'JPY', 'CAD', 'DKK', 'NOK', 'SEK', 
                        'XDR', 'AUD', 'HKD', 'SGD', 'NZD', 'ZAR', 'CNY', 'INR', 'BRL']
        
        currency_code = None
        country = first_part
        for code in common_codes:
            if code in first_part:
                currency_code = code
                country = first_part.replace(code, '').strip()
                break
        
        if not currency_code:
            match = re.search(r'([A-Z]{3})$', first_part)
            if match:
                currency_code = match.group(1)
                country = first_part.replace(currency_code, '').strip()
        
        if not currency_code:
            return None
        
        country = re.sub(r'[^A-Za-zÀ-ÿ\s\-]', '', country).strip()
        country = re.sub(r'[:\*]', '', country)
        
        values = []
        for part in parts[1:]:
            val = re.sub(r'[^\d\s,\.]', '', part).strip()
            if val:
                values.append(val)
        
        return (country, currency_code, values)
    
    def parse_line_plain(self, line: str) -> Optional[tuple]:
        """Parse une ligne sans pipes"""
        common_codes = ['EUR', 'USD', 'GBP', 'CHF', 'JPY', 'CAD', 'DKK', 'NOK', 'SEK', 'XDR']
        best_match = None
        best_code = None
        for code in common_codes:
            if code in line:
                pos = line.find(code)
                if best_match is None or pos < best_match:
                    best_match = pos
                    best_code = code
        if not best_code:
            match = re.search(r'([A-Z]{3})\s+', line)
            if match:
                best_code = match.group(1)
                best_match = line.find(best_code)
        if not best_code:
            return None
        country = line[:best_match].strip()
        after_code = line[best_match + len(best_code):].strip()
        values = after_code.split()
        country = re.sub(r'[^A-Za-zÀ-ÿ\s\-]', '', country).strip()
        return (country, best_code, values)
    
    def parse_text(self, text: str) -> tuple:
        """Parse le texte OCR complet"""
        lines = text.strip().split('\n')
        dates = self.extract_dates_from_header(text)
        start_idx = 0
        for i, line in enumerate(lines):
            if ('|' in line or any(code in line for code in ['EUR', 'USD', 'GBP']) or
                (len(line) > 20 and re.search(r'[A-Z]{3}', line))):
                start_idx = i
                break
        
        currencies = OrderedDict()
        for line in lines[start_idx:]:
            if not line.strip() or len(line.strip()) < 10:
                continue
            parsed = self.parse_line_with_pipes(line)
            if not parsed:
                parsed = self.parse_line_plain(line)
            if not parsed:
                continue
            country, currency_code, values = parsed
            if not currency_code or len(currency_code) != 3:
                continue
            if currency_code not in currencies:
                currencies[currency_code] = {
                    'country': country,
                    'currency_code': currency_code,
                    'rates': {}
                }
            for i, date in enumerate(dates):
                if i < len(values):
                    rate = self.clean_number(values[i])
                    if rate is not None:
                        currencies[currency_code]['rates'][date] = rate
        return dates, currencies
class ExcelExporter:
    """Exporte les données vers Excel (multiple feuilles)"""
    
    @staticmethod
    def export_to_excel(data: Dict[str, Any], output_path: Path) -> None:
        """Exporte les données vers un fichier Excel multi-feuilles"""
        
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            
            # ===== Feuille 1 : Liste plate des taux =====
            df_flat = pd.DataFrame(data['rates'])
            if not df_flat.empty:
                df_flat.to_excel(writer, sheet_name='Taux_plats', index=False)
                
                # Ajuster les colonnes
                worksheet = writer.sheets['Taux_plats']
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 30)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
            
            # ===== Feuille 2 : Tableau croisé (devises en lignes, dates en colonnes) =====
            if data['currencies']:
                # Construire le dataframe croisé
                cross_data = []
                for code, curr_data in data['currencies'].items():
                    row = {
                        'Devise': code,
                        'Pays': curr_data.get('country', ''),
                    }
                    # Ajouter les taux par date
                    for date, rate in curr_data.get('rates', {}).items():
                        row[date] = rate
                    cross_data.append(row)
                
                df_cross = pd.DataFrame(cross_data)
                
                if not df_cross.empty:
                    df_cross.to_excel(writer, sheet_name='Tableau_croise', index=False)
                    
                    # Mettre en forme (gras pour l'en-tête)
                    worksheet = writer.sheets['Tableau_croise']
                    for cell in worksheet[1]:
                        cell.font = Font(bold=True)
                        cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
                        cell.font = Font(color="FFFFFF", bold=True)
                    
                    # Ajuster les colonnes
                    for column in worksheet.columns:
                        max_length = 0
                        column_letter = column[0].column_letter
                        for cell in column:
                            try:
                                if len(str(cell.value)) > max_length:
                                    max_length = len(str(cell.value))
                            except:
                                pass
                        adjusted_width = min(max_length + 2, 20)
                        worksheet.column_dimensions[column_letter].width = adjusted_width
            
            # ===== Feuille 3 : Métadonnées =====
            df_meta = pd.DataFrame([
                ['Fichier source', data['metadata']['source_file']],
                ['Date extraction', data['metadata']['extraction_date']],
                ['Pages traitées', data['metadata']['pages_processed']],
                ['Langue OCR', data['metadata']['ocr_language']],
                ['Date début', data['metadata']['date_range']['start']],
                ['Date fin', data['metadata']['date_range']['end']],
                ['Nombre de jours', data['metadata']['date_range']['count']],
                ['Devises trouvées', data['metadata']['currencies_found']],
                ['Taux extraits', data['metadata']['total_rates']],
            ])
            df_meta.to_excel(writer, sheet_name='Metadonnees', index=False, header=False)
            
            # ===== Feuille 4 : Résumé statistique =====
            if data['rates']:
                df_rates = pd.DataFrame(data['rates'])
                stats = df_rates.groupby('currency_code')['exchange_rate'].agg([
                    ('Nombre', 'count'),
                    ('Moyenne', 'mean'),
                    ('Minimum', 'min'),
                    ('Maximum', 'max'),
                    ('Écart-type', 'std')
                ]).round(4)
                stats.to_excel(writer, sheet_name='Statistiques')
                
                worksheet = writer.sheets['Statistiques']
                for cell in worksheet[1]:
                    cell.font = Font(bold=True)
            
            # ===== Feuille 5 : Dates et devises disponibles =====
            if data['dates']:
                df_dates = pd.DataFrame({'Dates': data['dates']})
                df_dates.to_excel(writer, sheet_name='Dates', index=False)
            
            # ===== Feuille 6 : Export par devise (feuilles séparées) =====
            for code, curr_data in data['currencies'].items():
                # Créer un nom de feuille valide (Excel limite à 31 caractères)
                sheet_name = code[:31]
                
                # Récupérer les taux pour cette devise
                currency_rates = []
                for date, rate in curr_data.get('rates', {}).items():
                    if rate is not None:
                        currency_rates.append({'Date': date, 'Taux': rate})
                
                if currency_rates:
                    df_curr = pd.DataFrame(currency_rates)
                    df_curr.to_excel(writer, sheet_name=sheet_name, index=False)
                    
                    # Ajuster les colonnes
                    worksheet = writer.sheets[sheet_name]
                    worksheet.column_dimensions['A'].width = 15
                    worksheet.column_dimensions['B'].width = 15
class OCRProcessor:
    def __init__(self):
        self.parser = SpecificTableParser()
        self.excel_exporter = ExcelExporter()
    
    def process_pdf(self, pdf_path: Path) -> Dict[str, Any]:
        logger.info(f"📄 Traitement de {pdf_path}")
        
        images = convert_from_path(str(pdf_path), dpi=300)
        logger.info(f"📸 PDF converti en {len(images)} page(s)")
        
        all_text = []
        combined_text = ""
        
        for i, img in enumerate(images):
            logger.info(f"🔍 OCR sur la page {i+1}...")
            text = pytesseract.image_to_string(img, config=TESSERACT_CONFIG)
            all_text.append(text)
            combined_text += text + "\n"
        
        OUTPUT_DIR.mkdir(exist_ok=True)
        with open(OUTPUT_DIR / "debug_raw_text.txt", "w", encoding="utf-8") as f:
            f.write(combined_text)
        
        dates, currencies = self.parser.parse_text(combined_text)
        
        return self.build_result(pdf_path, dates, currencies, all_text)
    
    def build_result(self, pdf_path: Path, dates: List[str], 
                     currencies: Dict, raw_texts: List[str]) -> Dict:
        
        flat_rates = []
        for curr_code, curr_data in currencies.items():
            for date, rate in curr_data['rates'].items():
                flat_rates.append({
                    "date": date,
                    "country": curr_data['country'],
                    "currency_code": curr_code,
                    "exchange_rate": rate
                })
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
    # Créer les dossiers
    INPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    EXCEL_DIR.mkdir(exist_ok=True, parents=True)
    
    # Trouver les PDFs
    pdf_files = list(INPUT_DIR.glob("*.pdf"))
    if not pdf_files:
        logger.error(f"❌ Aucun PDF trouvé dans {INPUT_DIR}")
        return
    
    input_file = pdf_files[0]
    logger.info(f"📁 Fichier trouvé: {input_file.name}")
    
    # Traiter
    processor = OCRProcessor()
    result = processor.process_pdf(input_file)
    
    # 1. Sauvegarder JSON
    json_output = OUTPUT_DIR / f"{input_file.stem}_structured.json"
    with open(json_output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    logger.success(f"✅ JSON sauvegardé: {json_output}")
    
    # 2. Exporter vers Excel (NOUVEAU)
    excel_output = EXCEL_DIR / f"{input_file.stem}_taux_change.xlsx"
    ExcelExporter.export_to_excel(result, excel_output)
    logger.success(f"✅ Excel sauvegardé: {excel_output}")
    
    # 3. Optionnel : Export CSV
    csv_output = EXCEL_DIR / f"{input_file.stem}_rates.csv"
    df_rates = pd.DataFrame(result['rates'])
    if not df_rates.empty:
        df_rates.to_csv(csv_output, index=False, encoding='utf-8-sig')
        logger.success(f"✅ CSV sauvegardé: {csv_output}")
    
    # Afficher résumé
    print("\n" + "="*60)
    print("📊 RÉSUMÉ DE L'EXTRACTION")
    print("="*60)
    print(f"📅 Période: {result['metadata']['date_range']['start']} → {result['metadata']['date_range']['end']}")
    print(f"💰 Devises trouvées: {result['metadata']['currencies_found']}")
    print(f"📈 Taux extraits: {result['metadata']['total_rates']}")
    
    print("\n📁 Fichiers générés:")
    print(f"   📄 JSON: {json_output}")
    print(f"   📊 Excel: {excel_output}")
    print(f"   📝 CSV: {csv_output}")
    
    if result['rates']:
        print("\n📝 Aperçu des taux (3 premiers):")
        for rate in result['rates'][:3]:
            print(f"   {rate['date']} | {rate['currency_code']} | {rate['country'][:25]} | {rate['exchange_rate']}")

if __name__ == "__main__":
    main()  