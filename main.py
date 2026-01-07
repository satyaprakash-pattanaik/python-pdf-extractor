"""
Main Pipeline - PDF Extraction & PII Anonymization
Complete workflow: Extract → Map → Replace → Save
"""

from extraction import extract_pdf_to_text
from mapping_engine import build_replacement_map, build_master_pii, load_json, save_json
from replacement_engine import smart_replace, FIELD_CONFIG
from pathlib import Path
import sys

# ----------------------------
# CONFIGURATION
# ----------------------------
PDF_PATH = r"D:\Demands\Leila Martinez\Medical Records\2024.03.01 Scripps Health.pdf"
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

# Output files
EXTRACTED_TEXT_FILE = OUTPUT_DIR / "extracted_text.txt"
SANITIZED_TEXT_FILE = OUTPUT_DIR / "sanitized_text.txt"
REPLACEMENT_LOG_FILE = OUTPUT_DIR / "replacement_log.txt"

# Input files
PII_FILE = "pii.json"
DUMMY_FILE = "dummy_val.json"

# Generated mapping files
REPLACEMENT_PII_FILE = OUTPUT_DIR / "replacement_pii.json"
MASTER_PII_FILE = OUTPUT_DIR / "master_pii.json"


# ----------------------------
# BUILD THRESHOLDS FROM PII.JSON
# ----------------------------
def build_thresholds_from_pii(pii_data):
    """
    Automatically create thresholds for all fields in pii.json
    Uses defaults from FIELD_CONFIG in replacement_engine.py
    """
    thresholds = {}
    
    for field in pii_data.keys():
        # Get threshold from FIELD_CONFIG, or use DEFAULT
        if field in FIELD_CONFIG:
            thresholds[field] = FIELD_CONFIG[field]['threshold']
        else:
            thresholds[field] = FIELD_CONFIG['DEFAULT']['threshold']
    
    return thresholds


# ----------------------------
# MAIN FUNCTION
# ----------------------------
def main():
    print(f"\n{'='*70}")
    print(" PDF SANITIZATION PIPELINE ")
    print(f"{'='*70}\n")

    # ========================================
    # STEP 1: VALIDATE PDF
    # ========================================
    pdf_file = Path(PDF_PATH)
    if not pdf_file.exists():
        print(f"❌ Error: PDF file not found!")
        print(f"   Looking for: {PDF_PATH}")
        sys.exit(1)
    
    print(f"📄 Input PDF: {pdf_file.name}")
    print(f"📂 Output Directory: {OUTPUT_DIR.absolute()}\n")

    # ========================================
    # STEP 2: LOAD PII & DUMMY DATA
    # ========================================
    print(f"{'─'*70}")
    print("STEP 1: Loading PII and Dummy Data")
    print(f"{'─'*70}")
    
    pii_data = load_json(PII_FILE)
    dummy_data = load_json(DUMMY_FILE)

    if not pii_data:
        print(f"❌ Error: {PII_FILE} is empty or missing!")
        print(f"   Create a pii.json file with your PII values to anonymize")
        sys.exit(1)
    
    if not dummy_data:
        print(f"❌ Error: {DUMMY_FILE} is empty or missing!")
        print(f"   Create a dummy.json file with fake replacement values")
        sys.exit(1)

    print(f"✅ Loaded {PII_FILE}: {len(pii_data)} field types")
    print(f"✅ Loaded {DUMMY_FILE}: {len(dummy_data)} field types")
    
    # Show what fields we found
    print(f"\n📋 Fields to anonymize:")
    for field in pii_data.keys():
        count = len(pii_data[field]) if isinstance(pii_data[field], list) else 1
        print(f"   • {field}: {count} value(s)")
    
    # Build thresholds dynamically from pii.json fields
    field_thresholds = build_thresholds_from_pii(pii_data)
    print(f"\n🎯 Auto-configured thresholds:")
    for field, threshold in field_thresholds.items():
        print(f"   • {field}: {threshold}%")
    
    # Show total
    total_pii_values = sum(len(v) if isinstance(v, list) else 1 for v in pii_data.values())
    print(f"\n📊 Total PII values to anonymize: {total_pii_values}")

    # ========================================
    # STEP 3: EXTRACT TEXT FROM PDF
    # ========================================
    print(f"\n{'─'*70}")
    print("STEP 2: Extracting Text from PDF")
    print(f"{'─'*70}")
    
    try:
        extracted_text, stats = extract_pdf_to_text(
            PDF_PATH,
            use_advanced_table_ocr=True,  # Detect tables in scanned docs
            aggressive_ocr=True,           # Use multiple OCR methods for accuracy
            verbose=True                   # Show progress
        )
    except Exception as e:
        print(f"\n❌ Error during PDF extraction: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Save extracted text
    with open(EXTRACTED_TEXT_FILE, "w", encoding="utf-8") as f:
        f.write(extracted_text)
    
    print(f"\n✅ Extraction complete!")
    print(f"   Characters extracted: {len(extracted_text):,}")
    print(f"   Saved to: {EXTRACTED_TEXT_FILE}")

    # ========================================
    # STEP 4: BUILD REPLACEMENT MAPPINGS
    # ========================================
    print(f"\n{'─'*70}")
    print("STEP 3: Building PII Replacement Maps")
    print(f"{'─'*70}")
    
    # Build replacement map (original → dummy)
    replacement_map = build_replacement_map(
        pii_data, 
        dummy_data, 
        str(REPLACEMENT_PII_FILE)
    )
    
    if not replacement_map:
        print(f"❌ Error: Failed to build replacement map!")
        sys.exit(1)

    # Build master PII (reverse: dummy → original)
    master_map = build_master_pii(
        replacement_map, 
        str(MASTER_PII_FILE)
    )

    # ========================================
    # STEP 5: SANITIZE TEXT (REPLACE PII)
    # ========================================
    print(f"\n{'─'*70}")
    print("STEP 4: Anonymizing PII in Extracted Text")
    print(f"{'─'*70}")
    
    print("🔍 Searching for PII values (including OCR errors)...")
    
    # Perform smart replacement with detailed logging
    sanitized_text, replacement_log = smart_replace(
        extracted_text, 
        replacement_map, 
        custom_thresholds=field_thresholds,  # Use auto-built thresholds
        verbose=True
    )
    
    # Save sanitized text
    with open(SANITIZED_TEXT_FILE, "w", encoding="utf-8") as f:
        f.write(sanitized_text)
    
    print(f"\n✅ Anonymization complete!")
    print(f"   Replacements made: {len(replacement_log)}")
    print(f"   Saved to: {SANITIZED_TEXT_FILE}")

    # ========================================
    # STEP 6: SAVE REPLACEMENT LOG
    # ========================================
    if replacement_log:
        print(f"\n📋 Saving detailed replacement log...")
        
        with open(REPLACEMENT_LOG_FILE, "w", encoding="utf-8") as f:
            f.write("PII REPLACEMENT LOG\n")
            f.write("="*70 + "\n\n")
            
            # Group by field type
            by_field = {}
            for entry in replacement_log:
                field = entry['field']
                if field not in by_field:
                    by_field[field] = []
                by_field[field].append(entry)
            
            # Write grouped entries
            for field, entries in by_field.items():
                f.write(f"\n{field} ({len(entries)} replacements):\n")
                f.write("-"*70 + "\n")
                
                for i, entry in enumerate(entries, 1):
                    f.write(f"\n{i}. Original Value: '{entry['original_value']}'\n")
                    f.write(f"   Matched Text: '{entry['matched_text']}'\n")
                    f.write(f"   Replaced With: '{entry['dummy_value']}'\n")
                    f.write(f"   Similarity: {entry['similarity']}%\n")
                    f.write(f"   Position: {entry['position']}\n")
                
                f.write("\n")
        
        print(f"   Saved to: {REPLACEMENT_LOG_FILE}")

    # ========================================
    # STEP 7: SHOW SUMMARY
    # ========================================
    print(f"\n{'='*70}")
    print("✅ PIPELINE COMPLETED SUCCESSFULLY!")
    print(f"{'='*70}")
    
    print(f"\n📊 Summary:")
    print(f"   PDF processed: {pdf_file.name}")
    print(f"   Pages processed: {stats['total_pages']}")
    print(f"   Characters extracted: {len(extracted_text):,}")
    print(f"   PII values mapped: {len(replacement_map)}")
    print(f"   Replacements made: {len(replacement_log)}")
    
    # Show breakdown by field
    if replacement_log:
        by_field = {}
        for entry in replacement_log:
            field = entry['field']
            by_field[field] = by_field.get(field, 0) + 1
        
        print(f"\n📋 Replacements by field type:")
        for field, count in sorted(by_field.items()):
            print(f"   {field}: {count}")
        
        # Show if any fields had no replacements
        expected_fields = set(pii_data.keys())
        found_fields = set(by_field.keys())
        missing_fields = expected_fields - found_fields
        
        if missing_fields:
            print(f"\n⚠️  Fields with no matches found:")
            for field in sorted(missing_fields):
                print(f"   • {field}")
    
    print(f"\n📁 Output files:")
    print(f"   ├─ Extracted text: {EXTRACTED_TEXT_FILE}")
    print(f"   ├─ Sanitized text: {SANITIZED_TEXT_FILE}")
    print(f"   ├─ Replacement map: {REPLACEMENT_PII_FILE}")
    print(f"   ├─ Master PII (reverse): {MASTER_PII_FILE}")
    if replacement_log:
        print(f"   └─ Replacement log: {REPLACEMENT_LOG_FILE}")
    
    print(f"\n{'='*70}")
    
    # ========================================
    # STEP 8: SHOW PREVIEW
    # ========================================
    print(f"\n📄 Preview of sanitized text (first 500 chars):")
    print(f"{'─'*70}")
    preview = sanitized_text[:500].strip()
    print(preview)
    if len(sanitized_text) > 500:
        print("...")
    print(f"{'─'*70}\n")


# ----------------------------
# RUN PIPELINE
# ----------------------------
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Pipeline interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)