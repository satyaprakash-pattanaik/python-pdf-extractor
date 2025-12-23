import fitz
import pdfplumber
import pytesseract
from PIL import Image, ImageEnhance
import io
import re
import time
from pathlib import Path
import cv2
import numpy as np

# Configure Tesseract path
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
# AGGRESSIVE IMAGE PREPROCESSING
# -------------------------------
def preprocess_image_for_ocr(image_bytes, enhance_level="medium"):
    """
    Preprocess image with multiple enhancement techniques
    
    Args:
        image_bytes: Raw image bytes
        enhance_level: "light", "medium", "aggressive"
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        
        # Convert to OpenCV format
        img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        
        # Convert to grayscale
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # Check and upscale if resolution is too low
        height, width = gray.shape
        if width < 1500 and enhance_level in ["medium", "aggressive"]:
            scale = 1500 / width
            new_width = int(width * scale)
            new_height = int(height * scale)
            gray = cv2.resize(gray, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
        
        if enhance_level == "light":
            # Simple thresholding
            _, processed = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
        elif enhance_level == "medium":
            # Denoise + Adaptive threshold
            denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
            processed = cv2.adaptiveThreshold(
                denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 11, 2
            )
            
        else:  # aggressive
            # Full enhancement pipeline
            # 1. Denoise
            denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
            
            # 2. CLAHE (Contrast Limited Adaptive Histogram Equalization)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(denoised)
            
            # 3. Sharpen
            kernel_sharpen = np.array([[-1,-1,-1],
                                       [-1, 9,-1],
                                       [-1,-1,-1]])
            sharpened = cv2.filter2D(enhanced, -1, kernel_sharpen)
            
            # 4. Adaptive threshold
            processed = cv2.adaptiveThreshold(
                sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 11, 2
            )
            
            # 5. Morphological operations
            kernel_morph = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
            processed = cv2.morphologyEx(processed, cv2.MORPH_CLOSE, kernel_morph)
        
        return Image.fromarray(processed)
        
    except Exception as e:
        print(f"  ⚠️ Preprocessing Error: {e}")
        # Return original if preprocessing fails
        return Image.open(io.BytesIO(image_bytes))

# -------------------------------
# OCR WITH MULTIPLE ATTEMPTS
# -------------------------------
def ocr_image_with_layout(image_bytes, try_multiple_methods=True):
    """
    OCR with multiple preprocessing methods and PSM modes
    Returns best result based on text length and confidence
    """
    try:
        if not try_multiple_methods:
            # Simple approach
            image = Image.open(io.BytesIO(image_bytes))
            img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            enhanced_image = Image.fromarray(thresh)
            custom_config = r'--oem 3 --psm 6'
            text = pytesseract.image_to_string(enhanced_image, config=custom_config)
            return clean_text(text)
        
        # Try multiple combinations
        best_text = ""
        best_score = 0
        
        preprocessing_levels = ["light", "medium", "aggressive"]
        psm_modes = [6, 4, 3, 1]  # Different page segmentation modes
        
        for preprocess_level in preprocessing_levels:
            processed_img = preprocess_image_for_ocr(image_bytes, preprocess_level)
            
            for psm in psm_modes:
                try:
                    config = f'--oem 3 --psm {psm}'
                    
                    # Get text with data for confidence calculation
                    data = pytesseract.image_to_data(
                        processed_img, 
                        config=config, 
                        output_type=pytesseract.Output.DICT
                    )
                    
                    # Calculate confidence
                    confidences = [int(conf) for conf in data['conf'] if conf != '-1']
                    avg_conf = sum(confidences) / len(confidences) if confidences else 0
                    
                    # Get text
                    text = pytesseract.image_to_string(processed_img, config=config)
                    text_cleaned = clean_text(text)
                    
                    # Score = confidence * text_length
                    score = avg_conf * len(text_cleaned)
                    
                    if score > best_score:
                        best_text = text_cleaned
                        best_score = score
                        
                except Exception:
                    continue
        
        return best_text
        
    except Exception as e:
        print(f"  ⚠️ OCR Error: {e}")
        return ""

# -------------------------------
# EXTRACT TABLE FROM IMAGE USING OCR
# -------------------------------
def extract_table_from_image_ocr(image_bytes):
    """
    Advanced table extraction from scanned images
    Uses Tesseract's TSV output to preserve cell structure
    """
    try:
        # Preprocess with medium enhancement
        enhanced_image = preprocess_image_for_ocr(image_bytes, "medium")
        
        # Get TSV data (includes position info)
        tsv_data = pytesseract.image_to_data(
            enhanced_image, 
            output_type=pytesseract.Output.DICT
        )
        
        # Group text by line based on vertical position
        lines = {}
        for i, text in enumerate(tsv_data['text']):
            if text.strip():
                top = tsv_data['top'][i]
                left = tsv_data['left'][i]
                
                # Group by similar Y coordinate (same line)
                line_key = top // 15  # Tolerance of 15 pixels
                if line_key not in lines:
                    lines[line_key] = []
                lines[line_key].append((left, text))
        
        # Sort lines by Y position and cells by X position
        result = []
        for line_key in sorted(lines.keys()):
            line_cells = sorted(lines[line_key], key=lambda x: x[0])
            line_text = " | ".join([cell[1] for cell in line_cells])
            result.append(line_text)
        
        return "\n".join(result) if result else ""
        
    except Exception as e:
        print(f"  ⚠️ Table OCR Error: {e}")
        return ""

# -------------------------------
# DETECT IF IMAGE CONTAINS TABLE
# -------------------------------
def image_contains_table(image_bytes):
    """
    Detect if an image likely contains a table structure
    Uses line detection
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # Edge detection
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        
        # Detect horizontal and vertical lines
        lines = cv2.HoughLinesP(
            edges, 1, np.pi/180, 
            threshold=100, 
            minLineLength=100, 
            maxLineGap=10
        )
        
        if lines is None:
            return False
        
        # Count horizontal and vertical lines
        h_lines = 0
        v_lines = 0
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.abs(np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi)
            
            if angle < 10 or angle > 170:  # Horizontal
                h_lines += 1
            elif 80 < angle < 100:  # Vertical
                v_lines += 1
        
        # If both horizontal and vertical lines exist, likely a table
        return h_lines >= 3 and v_lines >= 2
        
    except Exception as e:
        return False

# -------------------------------
# CHECK IF IMAGE IS WORTH PROCESSING
# -------------------------------
def should_process_image(image_bytes):
    try:
        image = Image.open(io.BytesIO(image_bytes))
        width, height = image.size
        # Process larger images (more likely to contain meaningful text)
        return width > 100 and height > 100
    except:
        return False

# -------------------------------
# TABLE EXTRACTION (NATIVE PDF)
# -------------------------------
def extract_tables_native(pdf_path, page_number):
    """Extract tables from native (non-scanned) PDFs"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[page_number]
            tables = page.extract_tables()

            if not tables:
                return None

            tables_text = []
            for table in tables:
                for row in table:
                    line = " | ".join(str(cell or "") for cell in row)
                    tables_text.append(line)
                tables_text.append("")

            return "\n".join(tables_text).strip()
    except Exception as e:
        return None

# -------------------------------
# MAIN EXTRACTION FUNCTION
# -------------------------------
def extract_pdf_to_text(pdf_path, use_advanced_table_ocr=True, 
                        aggressive_ocr=True, verbose=True):
    """
    Extract text from PDF with advanced table handling for scanned docs
    
    Args:
        pdf_path: Path to PDF file
        use_advanced_table_ocr: Use advanced OCR for table detection in scanned docs
        aggressive_ocr: Try multiple OCR methods for best results (slower but more accurate)
        verbose: Print progress information
    """
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    start_time = time.time()
    doc = fitz.open(pdf_path)
    output_pages = []
    
    stats = {
        'total_pages': len(doc),
        'pages_with_tables': 0,
        'scanned_tables_found': 0,
        'images_processed': 0,
        'pages_with_ocr': 0
    }
    
    if verbose:
        print(f"📄 Processing: {pdf_file.name}")
        print(f"📊 Total Pages: {stats['total_pages']}")
        print(f"🔧 Aggressive OCR: {'Enabled' if aggressive_ocr else 'Disabled'}\n")
    
    for page_index in range(len(doc)):
        page = doc[page_index]
        page_no = page_index + 1
        page_start = time.time()
        
        if verbose:
            print(f"Page {page_no}/{stats['total_pages']}...", end=" ")

        page_text_parts = []
        page_text_parts.append(f"\n{'='*60}\nPAGE {page_no}\n{'='*60}\n")

        # 1️⃣ Try native text extraction first
        text_blocks = page.get_text("blocks")
        has_native_text = False
        for block in text_blocks:
            text = clean_text(block[4])
            if text:
                page_text_parts.append(text)
                has_native_text = True

        # 2️⃣ Try native table extraction
        table_text = extract_tables_native(pdf_path, page_index)
        if table_text:
            page_text_parts.append("\n[TABLE - NATIVE]\n")
            page_text_parts.append(table_text)
            stats['pages_with_tables'] += 1

        # 3️⃣ Process images (for scanned documents)
        images = page.get_images(full=True)
        
        if images:
            # Check if this is a scanned page (little/no native text)
            is_scanned = not has_native_text or len("".join([clean_text(b[4]) for b in text_blocks])) < 50
            
            if is_scanned:
                if verbose:
                    print("(scanned)", end=" ")
                stats['pages_with_ocr'] += 1
            
            for img in images:
                xref = img[0]
                try:
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    
                    if not should_process_image(image_bytes):
                        continue
                    
                    stats['images_processed'] += 1
                    
                    # Only do OCR if page is scanned
                    if is_scanned:
                        # Check if image contains a table
                        if use_advanced_table_ocr and image_contains_table(image_bytes):
                            if verbose:
                                print("(table)", end=" ")
                            
                            table_ocr = extract_table_from_image_ocr(image_bytes)
                            if table_ocr:
                                page_text_parts.append("\n[TABLE - SCANNED/OCR]\n")
                                page_text_parts.append(table_ocr)
                                stats['scanned_tables_found'] += 1
                        else:
                            # Regular OCR with layout preservation
                            ocr_text = ocr_image_with_layout(
                                image_bytes, 
                                try_multiple_methods=aggressive_ocr
                            )
                            if ocr_text:
                                page_text_parts.append("\n[TEXT - OCR]\n")
                                page_text_parts.append(ocr_text)
                
                except Exception as e:
                    if verbose:
                        print(f"(err)", end=" ")

        output_pages.append("\n".join(page_text_parts))
        
        page_time = time.time() - page_start
        if verbose:
            print(f"✓ ({page_time:.1f}s)")

    doc.close()
    
    total_time = time.time() - start_time
    
    if verbose:
        print(f"\n{'='*60}")
        print(f"✅ Extraction Complete!")
        print(f"⏱️  Total Time: {total_time:.2f}s")
        print(f"📊 Statistics:")
        print(f"   - Total pages: {stats['total_pages']}")
        print(f"   - Pages with native tables: {stats['pages_with_tables']}")
        print(f"   - Scanned tables found: {stats['scanned_tables_found']}")
        print(f"   - Pages requiring OCR: {stats['pages_with_ocr']}")
        print(f"   - Images processed: {stats['images_processed']}")
        print(f"{'='*60}\n")
    
    return "\n".join(output_pages), stats

# -------------------------------
# USAGE
# -------------------------------
if __name__ == "__main__":
    pdf_file = r"D:\Demands\Rupal Patel\Medical Provider Records\2024.02.28 - 2024.04.12 EJ CHIRO.pdf"
    
    try:
        text, stats = extract_pdf_to_text(
            pdf_file,
            use_advanced_table_ocr=True,  # Enable table detection
            aggressive_ocr=True,           # Try multiple OCR methods (slower but better)
            verbose=True
        )
        
        output_file = "extracted_text.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(text)
        
        print(f"💾 Saved to: {output_file}")
        print(f"📝 Total characters extracted: {len(text):,}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()