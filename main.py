from extraction import extract_pdf_to_text

# Use raw string (r"...") for Windows paths
PDF_PATH = r"D:\Demands\Peter Begle\Medical Records\2024.06.30 Big Bear Fire Department.pdf"
# Unpack the tuple - it returns (text, stats)
text, stats = extract_pdf_to_text(
    PDF_PATH,
    use_advanced_table_ocr=True,
    verbose=True
    )

# Save the extracted text
with open("output/extracted-text.txt", "w", encoding="utf-8") as f:
    f.write(text)

print("✅ Extraction complete! Check output.txt")
print(f"📊 Pages processed: {stats['total_pages']}")
print(f"📋 Pages with tables: {stats['pages_with_tables']}")
print(f"🖼️ Images processed: {stats['images_processed']}")