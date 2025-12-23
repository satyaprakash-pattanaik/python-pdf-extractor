from extraction import extract_pdf_to_text
from pathlib import Path
import sys

# Configuration
PDF_PATH = r"D:\Demands\Peter Begle\Medical Records\2024.06.30 Bear Valley Community.pdf"
OUTPUT_DIR = Path("output")
OUTPUT_FILE = OUTPUT_DIR / "extracted-text.txt"

def main():
    """Enhanced main extraction function with better error handling and options"""
    
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Validate PDF exists
    pdf_file = Path(PDF_PATH)
    if not pdf_file.exists():
        print(f"❌ Error: PDF file not found!")
        print(f"   Looking for: {PDF_PATH}")
        sys.exit(1)
    
    print(f"{'='*70}")
    print(f"PDF TEXT EXTRACTOR")
    print(f"{'='*70}")
    print(f"📂 Input: {pdf_file.name}")
    print(f"💾 Output: {OUTPUT_FILE}")
    print(f"{'='*70}\n")
    
    try:
        # Extract with enhanced options
        text, stats = extract_pdf_to_text(
            PDF_PATH,
            use_advanced_table_ocr=True,  # Enable advanced table detection
            aggressive_ocr=True,           # Use multiple OCR methods for accuracy
            verbose=True                   # Show detailed progress
        )
        
        # Save the extracted text
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(text)
        
        # Print comprehensive summary
        print(f"\n{'='*70}")
        print("✅ EXTRACTION COMPLETE!")
        print(f"{'='*70}")
        print(f"💾 Saved to: {OUTPUT_FILE.absolute()}")
        print(f"\n📊 Detailed Statistics:")
        print(f"   ├─ Total pages: {stats['total_pages']}")
        print(f"   ├─ Native tables found: {stats['pages_with_tables']}")
        print(f"   ├─ Scanned tables found: {stats['scanned_tables_found']}")
        print(f"   ├─ Pages requiring OCR: {stats['pages_with_ocr']}")
        print(f"   ├─ Images processed: {stats['images_processed']}")
        print(f"   └─ Total characters: {len(text):,}")
        
        # Show extraction breakdown
        native_pages = stats['total_pages'] - stats['pages_with_ocr']
        print(f"\n📈 Extraction Breakdown:")
        print(f"   ├─ Native text pages: {native_pages}")
        print(f"   └─ OCR-processed pages: {stats['pages_with_ocr']}")
        
        # Quality indicator
        if stats['pages_with_ocr'] > 0:
            ocr_percentage = (stats['pages_with_ocr'] / stats['total_pages']) * 100
            print(f"\n⚠️  Document Quality: {ocr_percentage:.1f}% scanned pages")
            if ocr_percentage > 50:
                print(f"   Note: High percentage of scanned pages may affect accuracy")
        
        print(f"{'='*70}")
        
        # Show preview
        if len(text) > 0:
            print(f"\n📄 Preview (first 500 characters):")
            print(f"{'-'*70}")
            preview = text[:500].strip()
            print(preview)
            if len(text) > 500:
                print("...")
            print(f"{'-'*70}\n")
        else:
            print(f"\n⚠️  Warning: No text was extracted from the PDF!")
            print(f"   This could mean:")
            print(f"   - The PDF is heavily image-based and OCR failed")
            print(f"   - The PDF is encrypted or corrupted")
            print(f"   - Tesseract is not installed correctly\n")
        
    except FileNotFoundError as e:
        print(f"\n❌ File Error: {e}")
        sys.exit(1)
        
    except PermissionError:
        print(f"\n❌ Permission Error: Cannot write to {OUTPUT_FILE}")
        print(f"   Check if the file is open in another program")
        sys.exit(1)
        
    except Exception as e:
        print(f"\n❌ Unexpected Error: {e}")
        print(f"\nFull error details:")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()