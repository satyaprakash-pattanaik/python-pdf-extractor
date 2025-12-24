"""
PII Replacer - Smart Find & Replace Engine
Finds PII values (even with OCR errors) and replaces them with dummy data
"""

import re
from rapidfuzz import fuzz

# -------------------------------------------------
# CONFIGURATION FOR DIFFERENT FIELD TYPES
# -------------------------------------------------
FIELD_CONFIG = {
    'Name': {
        'threshold': 75,        # 75% similarity needed
        'window_extra': 2,      # Allow +2 extra words (for "satya p rakash")
        'preserve_case': True   # Keep original capitalization
    },
    'MRN': {
        'threshold': 85,
        'window_extra': 0,
        'preserve_case': False
    },
    'SSN': {
        'threshold': 90,
        'window_extra': 0,
        'preserve_case': False
    },
    'DOB': {
        'threshold': 85,
        'window_extra': 0,
        'preserve_case': False
    },
    'Phone': {
        'threshold': 85,
        'window_extra': 0,
        'preserve_case': False
    },
    'Email': {
        'threshold': 90,
        'window_extra': 0,
        'preserve_case': False
    },
    'Address': {
        'threshold': 75,
        'window_extra': 3,
        'preserve_case': True
    },
    'DEFAULT': {
        'threshold': 80,
        'window_extra': 1,
        'preserve_case': True
    }
}


# -------------------------------------------------
# NORMALIZE TEXT (OCR-ROBUST)
# -------------------------------------------------
def normalize(text):
    """
    Normalize text for fuzzy matching
    Removes punctuation, extra spaces, makes lowercase
    """
    if not text:
        return ""
    text = str(text).lower()
    text = re.sub(r"[^\w\s]", " ", text)  # Remove punctuation
    text = re.sub(r"\s+", " ", text)       # Multiple spaces → single
    return text.strip()


# -------------------------------------------------
# CASE PRESERVATION
# -------------------------------------------------
def preserve_case(original_text, replacement_text):
    """
    Apply the case pattern of original to replacement
    
    Examples:
        "SATYA PRAKASH" + "john doe" → "JOHN DOE"
        "Satya Prakash" + "john doe" → "John Doe"
        "satya prakash" + "john doe" → "john doe"
    """
    if not original_text or not replacement_text:
        return replacement_text
    
    # All uppercase
    if original_text.isupper():
        return replacement_text.upper()
    
    # Title case (first letter of each word)
    if original_text[0].isupper():
        words = replacement_text.split()
        return ' '.join(word.capitalize() for word in words)
    
    # All lowercase
    return replacement_text.lower()


# -------------------------------------------------
# SMART SPAN FINDER
# -------------------------------------------------
def find_spans(original_text, target_value, field_type='DEFAULT', custom_threshold=None):
    """
    Find all occurrences of target_value in original_text
    Handles OCR errors using fuzzy matching
    
    Args:
        original_text: The full extracted text
        target_value: The PII value to find (e.g., "Satya Prakash")
        field_type: Type of field (Name, MRN, etc.)
        custom_threshold: Override default threshold
    
    Returns:
        List of (start_pos, end_pos, matched_text, similarity_score)
    """
    
    # Get configuration for this field type
    config = FIELD_CONFIG.get(field_type, FIELD_CONFIG['DEFAULT'])
    threshold = custom_threshold if custom_threshold else config['threshold']
    
    # Normalize target for comparison
    norm_target = normalize(target_value)
    target_words = norm_target.split()
    target_len = len(target_words)
    
    if target_len == 0:
        return []
    
    # Find all word positions in text
    words = list(re.finditer(r"\S+", original_text))
    
    if not words:
        return []
    
    spans = []
    
    # Try different window sizes
    # e.g., for "satya prakash" (2 words), try 2, 3, 4 words windows
    min_window = max(1, target_len - 1)
    max_window = target_len + config['window_extra']
    
    for window_size in range(min_window, max_window + 1):
        for i in range(len(words) - window_size + 1):
            window_words = words[i:i + window_size]
            
            if not window_words:
                continue
            
            # Extract the text span
            start_pos = window_words[0].start()
            end_pos = window_words[-1].end()
            span_text = original_text[start_pos:end_pos]
            
            # Calculate fuzzy similarity
            similarity = fuzz.token_set_ratio(
                normalize(span_text),
                norm_target
            )
            
            # If similarity meets threshold, add to results
            if similarity >= threshold:
                spans.append((start_pos, end_pos, span_text, similarity))
    
    # Remove overlapping spans - keep highest scoring ones
    spans.sort(key=lambda x: (-x[3], x[0]))  # Sort by score (desc), then position
    
    non_overlapping = []
    used_ranges = []
    
    for start, end, text, score in spans:
        # Check if this span overlaps with any already selected span
        overlaps = False
        for used_start, used_end in used_ranges:
            if start < used_end and end > used_start:
                overlaps = True
                break
        
        if not overlaps:
            non_overlapping.append((start, end, text, score))
            used_ranges.append((start, end))
    
    return non_overlapping


# -------------------------------------------------
# SMART REPLACE ENGINE
# -------------------------------------------------
def smart_replace(text, replacement_map, custom_thresholds=None, verbose=False):
    """
    Replace PII in text using the replacement map
    
    Args:
        text: Original extracted text
        replacement_map: Dict of format:
            {
                "Name::satya prakash": {
                    "field": "Name",
                    "original": "Satya Prakash",
                    "dummy": "John Doe"
                }
            }
        custom_thresholds: Optional dict like {"Name": 80, "MRN": 90}
        verbose: If True, return detailed log of replacements
    
    Returns:
        (replaced_text, replacements_made) or (replaced_text, detailed_log) if verbose
    """
    
    if custom_thresholds is None:
        custom_thresholds = {}
    
    # Collect all replacements as (position, dummy_text, field, etc.)
    all_replacements = []
    replacement_log = []
    
    # Process each entry in replacement map
    for key, entry in replacement_map.items():
        original = entry.get("original", "")
        dummy = entry.get("dummy", "")
        field = entry.get("field", "DEFAULT")
        
        if not original or not dummy:
            continue
        
        # Get custom threshold if provided
        threshold = custom_thresholds.get(field)
        
        # Find all spans matching this PII value
        spans = find_spans(text, original, field, threshold)
        
        # Get field config for case preservation
        config = FIELD_CONFIG.get(field, FIELD_CONFIG['DEFAULT'])
        
        for start, end, matched_text, score in spans:
            # Apply case preservation if needed
            if config['preserve_case']:
                final_dummy = preserve_case(matched_text, dummy)
            else:
                final_dummy = dummy
            
            all_replacements.append((start, end, final_dummy))
            
            if verbose:
                replacement_log.append({
                    'field': field,
                    'original_value': original,
                    'matched_text': matched_text,
                    'dummy_value': final_dummy,
                    'similarity': score,
                    'position': (start, end)
                })
    
    # Sort replacements by position (reverse order for safe replacement)
    all_replacements.sort(key=lambda x: x[0], reverse=True)
    
    # Apply replacements from end to start (so positions don't shift)
    result_text = text
    for start, end, dummy in all_replacements:
        result_text = result_text[:start] + dummy + result_text[end:]
    
    if verbose:
        return result_text, replacement_log
    else:
        return result_text, len(all_replacements)


# -------------------------------------------------
# EXAMPLE USAGE
# -------------------------------------------------
if __name__ == "__main__":
    # Example replacement map
    replacement_map = {
        "Name::satya prakash": {
            "field": "Name",
            "original": "Satya Prakash",
            "dummy": "John Doe"
        },
        "MRN::swh123": {
            "field": "MRN",
            "original": "SWH123",
            "dummy": "MRN-000001"
        }
    }
    
    # Test text with OCR errors
    test_text = """
    Patient Name: Satya Prakash
    MRN: SWH123
    
    Follow-up with satya p rakash (OCR error)
    Record number: SWH 123 (spacing error)
    Contact: SATYA PRAKASH (uppercase)
    """
    
    # Replace
    replaced, log = smart_replace(test_text, replacement_map, verbose=True)
    
    print("="*60)
    print("ORIGINAL TEXT:")
    print("="*60)
    print(test_text)
    
    print("\n" + "="*60)
    print("REPLACED TEXT:")
    print("="*60)
    print(replaced)
    
    print("\n" + "="*60)
    print(f"REPLACEMENTS MADE: {len(log)}")
    print("="*60)
    for item in log:
        print(f"\n{item['field']}:")
        print(f"  Found: '{item['matched_text']}'")
        print(f"  Original: '{item['original_value']}'")
        print(f"  Replaced with: '{item['dummy_value']}'")
        print(f"  Similarity: {item['similarity']}%")