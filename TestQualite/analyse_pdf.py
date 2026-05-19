# # Avis-au-public-023-du-29.11.2022-unite-tarifaire
# from pdf2image import convert_from_path
# import cv2
# import numpy as np

# PDF_PATH = r"D:\VSCODE\Projet\Projet_OCR\TestQualite\AvisPublic.pdf"

# # Conversion PDF -> images
# pages = convert_from_path(PDF_PATH, dpi=300)

# print(f"\nNombre de pages : {len(pages)}\n")

# for index, page in enumerate(pages):

#     print("=" * 50)
#     print(f"PAGE {index + 1}")
#     print("=" * 50)

#     # Convertir PIL -> OpenCV
#     image = np.array(page)
#     image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

#     gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

#     # ----------------------------
#     # 1. RESOLUTION
#     # ----------------------------

#     height, width = gray.shape

#     print(f"Résolution : {width} x {height}")

#     # ----------------------------
#     # 2. LUMINOSITE
#     # ----------------------------

#     brightness = np.mean(gray)

#     print(f"Luminosité : {brightness:.2f}")

#     if brightness < 80:
#         print("→ Image sombre")

#     elif brightness > 200:
#         print("→ Image trop lumineuse")

#     else:
#         print("→ Luminosité correcte")

#     # ----------------------------
#     # 3. CONTRASTE
#     # ----------------------------

#     contrast = np.std(gray)

#     print(f"Contraste : {contrast:.2f}")

#     if contrast < 30:
#         print("→ Contraste faible")

#     else:
#         print("→ Contraste correct")

#     # ----------------------------
#     # 4. FLOU / NETTETE
#     # ----------------------------

#     blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()

#     print(f"Netteté (Blur Score) : {blur_score:.2f}")

#     if blur_score < 50:
#         print("→ Image très floue")

#     elif blur_score < 100:
#         print("→ Image légèrement floue")

#     else:
#         print("→ Image nette")

#     print("\n")


# ----------------------------------------CODE 2-------------------------------------------
# import json
# from pdf_analyzer import PDFAnalyzer


# PDF_PATH = r"D:\VSCODE\Projet\Projet_OCR\TestQualite\AvisPublic.pdf"


# def main():

#     analyzer = PDFAnalyzer(PDF_PATH)

#     report = analyzer.analyze()

#     print("\n===== PDF ANALYSIS REPORT =====\n")

#     print(json.dumps(report, indent=4))


# if __name__ == "__main__":
#     main()


# ----------------------------------------CODE 3-------------------------------------------
import json
from pdf_ocr import PDFOCR


PDF_PATH = r"D:\VSCODE\Projet\Projet_OCR\TestQualite\AvisPublic.pdf"


def main():

    ocr = PDFOCR(PDF_PATH)

    result = ocr.extract_text()

    print("\n===== OCR RESULT =====\n")

    print(json.dumps(result, indent=4, ensure_ascii=False))


if __name__ == "__main__":
    main()