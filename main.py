from extraction import extract_pdf_to_text
from mapping_engine import build_global_mapping, build_master_pii, load_json, save_json
from replacement_engine import smart_replace
from pathlib import Path
import sys
import json

# ----------------------------
# CONFIGURATION
# ----------------------------
PDF_PATH = r"D:\Demands\Ronald Handrop\Medical Provider Records\2024.05.28 Dermatology.pdf"
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

EXTRACTED_TEXT_FILE = OUTPUT_DIR / "extracted_text.txt"
SANITIZED_TEXT_FILE = OUTPUT_DIR / "sanitized_text.txt"
DUMMY_FILE = "dummy_val.json"
PII_FILE = "pii.json"
REPLACEMENT_PII_FILE = OUTPUT_DIR / "replacement_pii.json"
MASTER_PII_FILE = OUTPUT_DIR / "master_pii.json"

FIELD_THRESHOLDS = {
    "Name": 75,
    "MRN": 85,
    "Date": 90
}

# ----------------------------
# MAIN FUNCTION
# ----------------------------
def main():
    print(f"{'='*70}")
    print("PDF SANITIZATION PIPELINE")
    print(f"{'='*70}\n")

    # 1️⃣ Validate PDF
    pdf_file = Path(PDF_PATH)
    if not pdf_file.exists():
        print(f"❌ Error: PDF not found at {PDF_PATH}")
        sys.exit(1)

    # 2️⃣ Load input files
    print("📂 Loading input files...")
    dummy_pool = load_json(DUMMY_FILE)
    combined_pii = load_json(PII_FILE)

    if not combined_pii:
        print(f"❌ Error: combined_pii.json is empty or missing!")
        sys.exit(1)
    if not dummy_pool:
        print(f"❌ Error: dummy.json is empty or missing!")
        sys.exit(1)

    print(f"✅ Loaded dummy.json and combined_pii.json\n")

    # 3️⃣ Extract text from PDF
    print("📄 Extracting text from PDF...")
    extracted_text, stats = extract_pdf_to_text(
        PDF_PATH,
        use_advanced_table_ocr=True,
        aggressive_ocr=True,
        verbose=True
    )

    with open(EXTRACTED_TEXT_FILE, "w", encoding="utf-8") as f:
        f.write(extracted_text)
    print(f"💾 Extracted text saved: {EXTRACTED_TEXT_FILE}\n")

    # 4️⃣ Build replacement mapping (dummy values)
    print("🔄 Building replacement PII mapping...")
    replacement_map = build_global_mapping(combined_pii, dummy_pool, REPLACEMENT_PII_FILE)
    build_master_pii(replacement_map, MASTER_PII_FILE)
    print(f"💾 Replacement PII mapping saved: {REPLACEMENT_PII_FILE}")
    print(f"💾 Master PII mapping saved: {MASTER_PII_FILE}\n")

    # 5️⃣ Sanitize text using smart replace
    print("🛡️  Performing smart replacement...")
    sanitized_text = smart_replace(extracted_text, replacement_map, FIELD_THRESHOLDS)
    with open(SANITIZED_TEXT_FILE, "w", encoding="utf-8") as f:
        f.write(sanitized_text)
    print(f"✅ Sanitized text saved: {SANITIZED_TEXT_FILE}\n")

    # 6️⃣ Summary
    print(f"{'='*70}")
    print("🎯 PIPELINE COMPLETED SUCCESSFULLY")
    print(f"📂 Input PDF: {pdf_file.name}")
    print(f"💾 Extracted Text: {EXTRACTED_TEXT_FILE}")
    print(f"💾 Sanitized Text: {SANITIZED_TEXT_FILE}")
    print(f"💾 Replacement PII: {REPLACEMENT_PII_FILE}")
    print(f"💾 Master PII: {MASTER_PII_FILE}")
    print(f"{'='*70}")

# ----------------------------
# RUN
# ----------------------------
if __name__ == "__main__":
    main()
