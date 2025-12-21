import fitz
import pdfplumber
import pytesseract
from PIL import Image
import io
import re

# Configure Tesseract path (adjust if your installation path is different)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# -------------------------------
# CLEAN TEXT
# -------------------------------
def clean_text(text):
    if not text:
        return ""
    text = text.replace("\t", " ")
    text = re.sub(r" +", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

# -------------------------------
# OCR CONFIDENCE (SIMPLE & SAFE)
# -------------------------------
def is_low_confidence(text):
    if not text:
        return True
    alpha_ratio = sum(c.isalpha() for c in text) / max(len(text), 1)
    return alpha_ratio < 0.4

# -------------------------------
# IMAGE → OCR (ONLY WHEN NEEDED)
# -------------------------------
def ocr_image(image_bytes):
    try:
        image = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(image)
        text = clean_text(text)

        if is_low_confidence(text):
            return "<<LOW_CONFIDENCE_IMAGE_TEXT>>"

        return text
    except Exception as e:
        print(f"OCR Error: {e}")
        return ""

# -------------------------------
# TABLE EXTRACTION
# -------------------------------
def extract_tables(pdf_path, page_number):
    tables_text = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[page_number]
            tables = page.extract_tables()

            for table in tables:
                for row in table:
                    line = " | ".join(cell or "" for cell in row)
                    tables_text.append(line)
                tables_text.append("")  # spacing

        return "\n".join(tables_text)
    except Exception as e:
        print(f"Table extraction error on page {page_number + 1}: {e}")
        return ""

# -------------------------------
# MAIN EXTRACTION FUNCTION
# -------------------------------
def extract_pdf_to_text(pdf_path):
    doc = fitz.open(pdf_path)
    output_pages = []

    for page_index in range(len(doc)):
        page = doc[page_index]
        page_no = page_index + 1

        page_text_parts = []
        page_text_parts.append(f"\n\n===== PAGE {page_no} =====\n")

        # 1️⃣ Native text (best source)
        text_blocks = page.get_text("blocks")
        for block in text_blocks:
            text = clean_text(block[4])
            if text:
                page_text_parts.append(text)

        # 2️⃣ Tables
        try:
            table_text = extract_tables(pdf_path, page_index)
            if table_text.strip():
                page_text_parts.append("\n--- TABLE ---\n")
                page_text_parts.append(table_text)
        except Exception as e:
            print(f"Table processing error on page {page_no}: {e}")

        # 3️⃣ Images (OCR fallback)
        try:
            for img in page.get_images(full=True):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]

                ocr_text = ocr_image(image_bytes)
                if ocr_text:
                    page_text_parts.append("\n--- IMAGE TEXT ---\n")
                    page_text_parts.append(ocr_text)
        except Exception as e:
            print(f"Image processing error on page {page_no}: {e}")

        output_pages.append("\n".join(page_text_parts))

    doc.close()
    return "\n".join(output_pages)

# -------------------------------
# USAGE EXAMPLE
# -------------------------------
if __name__ == "__main__":
    # Example usage
    pdf_file = "your_document.pdf"  # Replace with your PDF file path
    
    try:
        extracted_text = extract_pdf_to_text(pdf_file)
        
        # Save to text file
        output_file = "extracted_text.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(extracted_text)
        
        print(f"✅ Extraction complete! Saved to: {output_file}")
        print(f"📄 Total characters extracted: {len(extracted_text)}")
        
    except Exception as e:
        print(f"❌ Error: {e}")