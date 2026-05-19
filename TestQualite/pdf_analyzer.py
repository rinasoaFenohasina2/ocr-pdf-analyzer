import cv2
import numpy as np
from pdf2image import convert_from_path


class PDFAnalyzer:

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
    # IMAGE CONVERSION
    # -------------------------
    def _to_opencv(self, page):
        img = np.array(page)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return gray

    # -------------------------
    # ANALYSE PAGE
    # -------------------------
    def analyze_page(self, page):

        gray = self._to_opencv(page)

        height, width = gray.shape

        brightness = float(np.mean(gray))
        contrast = float(np.std(gray))
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        issues = []

        # -------- CHECK PROBLEMS --------
        if blur_score < 80:
            issues.append("Image floue")

        if contrast < 30:
            issues.append("Contraste faible")

        if brightness < 80:
            issues.append("Image trop sombre")

        if brightness > 200:
            issues.append("Image trop lumineuse")

        if width < 1200:
            issues.append("Résolution faible")

        # -------- QUALITY SCORE --------
        score = self.compute_score(
            blur_score,
            contrast,
            brightness,
            width,
            height
        )

        return {
            "resolution": f"{width}x{height}",
            "brightness": brightness,
            "contrast": contrast,
            "blur_score": blur_score,
            "quality_score": score,
            "issues": issues
        }

    # -------------------------
    # SCORE GLOBAL
    # -------------------------
    def compute_score(self, blur, contrast, brightness, width, height):

        score = 0

        # BLUR
        if blur < 50:
            score += 0
        elif blur < 100:
            score += 15
        else:
            score += 30

        # CONTRAST
        if contrast < 30:
            score += 5
        elif contrast < 60:
            score += 15
        else:
            score += 25

        # BRIGHTNESS
        if brightness < 80 or brightness > 200:
            score += 5
        else:
            score += 25

        # RESOLUTION
        if width < 1000 or height < 1000:
            score += 5
        elif width < 2000:
            score += 10
        else:
            score += 20

        return min(score, 100)

    # -------------------------
    # FULL ANALYSIS
    # -------------------------
    def analyze(self):

        total_pages = self.load_pdf()

        results = []

        for i, page in enumerate(self.pages):

            page_result = self.analyze_page(page)
            page_result["page"] = i + 1

            results.append(page_result)

        # GLOBAL SCORE
        global_score = int(
            sum(r["quality_score"] for r in results) / total_pages
        )

        return {
            "total_pages": total_pages,
            "global_score": global_score,
            "pages": results
        }