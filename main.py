from extraction import extract_pdf_to_text

PDF_PATH = "C:/Users/DELL/Downloads/PDF32000.book.pdf"
OUTPUT_PATH = "output/extracted.txt"

text = extract_pdf_to_text(PDF_PATH)

with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    f.write(text)

print("✅ Extraction completed")
print(f"📄 Output saved to {OUTPUT_PATH}")
