import cv2
import numpy as np
import pytesseract
from pdf2image import convert_from_path


class PDFOCR:

    def __init__(self, pdf_path, dpi=300):
        self.pdf_path = pdf_path
        self.dpi = dpi
        self.pages = []

    # -------------------------
    # LOAD PDF
    # -------------------------
    def load_pdf(self):
        self.pages = convert_from_path(self.pdf_path, dpi=self.dpi)
        return len(self.pages)

    # -------------------------
    # CONVERT IMAGE
    # -------------------------
    def _to_gray(self, page):
        img = np.array(page)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return gray

    # -------------------------
    # OCR PAGE
    # -------------------------
    def ocr_page(self, page, lang="fra"):
        gray = self._to_gray(page)

        # amélioration image (optionnel mais important)
        gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

        text = pytesseract.image_to_string(gray, lang=lang)

        return text

    # -------------------------
    # FULL OCR
    # -------------------------
    def extract_text(self):

        total_pages = self.load_pdf()

        results = []

        for i, page in enumerate(self.pages):

            text = self.ocr_page(page)

            results.append({
                "page": i + 1,
                "text": text
            })

        return {
            "total_pages": total_pages,
            "pages": results
        }
    
    # def ocr_page(self, page, lang="fra"):

    #     img = np.array(page)
    #     img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    #     gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    #     # 🔥 1. agrandissement
    #     gray = cv2.resize(gray, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)

    #     # 🔥 2. réduction bruit
    #     gray = cv2.GaussianBlur(gray, (3, 3), 0)

    #     # 🔥 3. binarisation
    #     gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    #     # 🔥 4. config OCR
    #     config = r"--oem 3 --psm 6"

    #     text = pytesseract.image_to_string(
    #         gray,
    #         lang=lang,
    #         config=config
    #     )

    #     return text