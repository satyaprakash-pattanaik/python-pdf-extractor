"""
PII Replacer - Enhanced Smart Find & Replace Engine
Finds PII values (even with OCR errors) and replaces them with dummy data
"""

import re
from rapidfuzz import fuzz

# -------------------------------------------------
# CONFIGURATION FOR DIFFERENT FIELD TYPES
# -------------------------------------------------
FIELD_CONFIG = {
    'Name': {
        'threshold': 60,        # Lower threshold for names
        'window_extra': 4,      # Allow more extra words
        'preserve_case': True,
        'min_window_factor': 0.4  # Can be 40% smaller than target
    },
    'MRN': {
        'threshold': 75,
        'window_extra': 1,
        'preserve_case': False,
        'min_window_factor': 0.7
    },
    'SSN': {
        'threshold': 80,
        'window_extra': 1,
        'preserve_case': False,
        'min_window_factor': 0.8
    },
    'DOB': {
        'threshold': 75,
        'window_extra': 1,
        'preserve_case': False,
        'min_window_factor': 0.8
    },
    'Sex': {
        'threshold': 85,
        'window_extra': 0,
        'preserve_case': False,
        'min_window_factor': 0.9
    },
    'Phone': {
        'threshold': 75,
        'window_extra': 1,
        'preserve_case': False,
        'min_window_factor': 0.8
    },
    'Email': {
        'threshold': 80,
        'window_extra': 1,
        'preserve_case': False,
        'min_window_factor': 0.8
    },
    'Address': {
        'threshold': 80,        # Increased from 65 - more strict
        'window_extra': 5,
        'preserve_case': True,
        'min_window_factor': 0.75  # Increased from 0.5 - must match 75% of address
    },
    'Healthcare': {
        'threshold': 70,
        'window_extra': 3,
        'preserve_case': True,
        'min_window_factor': 0.6
    },
    'DEFAULT': {
        'threshold': 70,
        'window_extra': 2,
        'preserve_case': True,
        'min_window_factor': 0.6
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
# AGGRESSIVE NORMALIZE (FOR VERY FUZZY MATCHING)
# -------------------------------------------------
def normalize_aggressive(text):
    """
    Super aggressive normalization - removes almost everything
    Use for very fuzzy matching
    """
    if not text:
        return ""
    text = str(text).lower()
    # Remove all non-alphanumeric
    text = re.sub(r"[^a-z0-9]", "", text)
    return text


# -------------------------------------------------
# CASE PRESERVATION
# -------------------------------------------------
def preserve_case(original_text, replacement_text):
    """
    Apply the case pattern of original to replacement
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
# CHARACTER-LEVEL SIMILARITY (FOR SHORT VALUES)
# -------------------------------------------------
def char_similarity(text1, text2):
    """
    Calculate character-level similarity (good for short strings like MRN)
    """
    norm1 = normalize_aggressive(text1)
    norm2 = normalize_aggressive(text2)
    return fuzz.ratio(norm1, norm2)


# -------------------------------------------------
# DIRECT PATTERN SEARCH (FOR EXACT MATCHING)
# -------------------------------------------------
def find_exact_patterns(text, target_value):
    """
    Find exact patterns using regex (case-insensitive)
    Good for catching exact matches even with line breaks
    """
    spans = []
    
    # Create flexible pattern - allow line breaks and extra spaces
    # "Martinez, Lelia M" → "Martinez,?\s*Lelia\s*M?"
    parts = re.split(r'[,\s]+', target_value)
    pattern_parts = []
    
    for part in parts:
        if part:
            pattern_parts.append(re.escape(part))
    
    # Join with flexible spacing (allows newlines, multiple spaces, commas)
    pattern = r'\s*[,\s]*\s*'.join(pattern_parts)
    
    try:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            matched_text = match.group()
            # Calculate how similar it is
            similarity = fuzz.ratio(normalize(matched_text), normalize(target_value))
            spans.append((match.start(), match.end(), matched_text, similarity))
    except:
        pass  # Invalid regex
    
    return spans


# -------------------------------------------------
# ENHANCED SPAN FINDER
# -------------------------------------------------
def find_spans(original_text, target_value, field_type='DEFAULT', custom_threshold=None):
    """
    Enhanced span finder with multiple matching strategies
    """
    
    config = FIELD_CONFIG.get(field_type, FIELD_CONFIG['DEFAULT'])
    threshold = custom_threshold if custom_threshold else config['threshold']
    
    norm_target = normalize(target_value)
    target_words = norm_target.split()
    target_len = len(target_words)
    
    if target_len == 0:
        return []
    
    # SAFETY: Skip very short targets (1-2 chars) for Address/Healthcare fields
    if field_type in ['Address', 'Healthcare', 'FullAddress', 'StreetOnly', 'CityStateZip'] and len(norm_target) < 5:
        return []
    
    all_spans = []
    
    # Strategy 1: Direct pattern search (catches exact matches with line breaks)
    exact_spans = find_exact_patterns(original_text, target_value)
    all_spans.extend(exact_spans)
    
    # Strategy 2: Word-based matching with flexible windows
    words = list(re.finditer(r"\S+", original_text))
    
    if not words:
        return all_spans
    
    min_window = max(1, int(target_len * config['min_window_factor']))
    max_window = target_len + config['window_extra']
    
    for window_size in range(min_window, max_window + 1):
        for i in range(len(words) - window_size + 1):
            window_words = words[i:i + window_size]
            
            if not window_words:
                continue
            
            start_pos = window_words[0].start()
            end_pos = window_words[-1].end()
            span_text = original_text[start_pos:end_pos]
            
            # Use multiple similarity metrics
            token_score = fuzz.token_set_ratio(normalize(span_text), norm_target)
            partial_score = fuzz.partial_ratio(normalize(span_text), norm_target)
            
            # For short strings, also check character-level
            if target_len <= 2 or len(normalize(target_value)) <= 15:
                char_score = char_similarity(span_text, target_value)
                similarity = max(token_score, partial_score, char_score)
            else:
                similarity = max(token_score, partial_score)
            
            if similarity >= threshold:
                all_spans.append((start_pos, end_pos, span_text, similarity))
    
    # Strategy 3: Regex-based matching for specific patterns
    if field_type in ['MRN', 'SSN', 'Phone', 'DOB', 'Email']:
        pattern_parts = re.split(r'[\s\-\.]+', target_value)
        if len(pattern_parts) > 1:
            pattern = r'\s*[\-\.\s]*\s*'.join(re.escape(part) for part in pattern_parts)
            pattern = r'\b' + pattern + r'\b'
            
            try:
                for match in re.finditer(pattern, original_text, re.IGNORECASE):
                    matched_text = match.group()
                    similarity = fuzz.ratio(normalize(matched_text), norm_target)
                    
                    if similarity >= threshold:
                        all_spans.append((match.start(), match.end(), matched_text, similarity))
            except:
                pass
    
    # Strategy 4: Substring matching for partial values
    if target_len >= 2:
        for word_match in words:
            word_text = original_text[word_match.start():word_match.end()]
            
            similarity = fuzz.partial_ratio(normalize(word_text), norm_target)
            
            # Higher threshold for single-word matches
            if similarity >= min(threshold + 15, 95):
                all_spans.append((word_match.start(), word_match.end(), word_text, similarity))
    
    # Remove overlapping spans - keep highest scoring ones
    all_spans.sort(key=lambda x: (-x[3], x[0]))
    
    non_overlapping = []
    used_ranges = []
    
    for start, end, text, score in all_spans:
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
    """
    
    if custom_thresholds is None:
        custom_thresholds = {}
    
    all_replacements = []
    replacement_log = []
    
    print(f"\n🔍 Processing {len(replacement_map)} PII values...")
    
    processed = 0
    for key, entry in replacement_map.items():
        original = entry.get("original", "")
        dummy = entry.get("dummy", "")
        field = entry.get("field", "DEFAULT")
        
        if not original or not dummy:
            continue
        
        processed += 1
        if verbose and processed % 5 == 0:
            print(f"   Processed {processed}/{len(replacement_map)} values...")
        
        threshold = custom_thresholds.get(field)
        
        # Find all spans matching this PII value
        spans = find_spans(text, original, field, threshold)
        
        if spans and verbose:
            print(f"   ✓ Found {len(spans)} match(es) for {field}: '{original}'")
        
        config = FIELD_CONFIG.get(field, FIELD_CONFIG['DEFAULT'])
        
        for start, end, matched_text, score in spans:
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
    
    # Sort by position (reverse)
    all_replacements.sort(key=lambda x: x[0], reverse=True)
    
    # Remove duplicates
    seen_ranges = set()
    unique_replacements = []
    
    for start, end, dummy in all_replacements:
        range_key = (start, end)
        if range_key not in seen_ranges:
            unique_replacements.append((start, end, dummy))
            seen_ranges.add(range_key)
    
    # Apply replacements
    result_text = text
    for start, end, dummy in unique_replacements:
        result_text = result_text[:start] + dummy + result_text[end:]
    
    if verbose:
        seen_positions = set()
        unique_log = []
        for entry in replacement_log:
            pos_key = entry['position']
            if pos_key not in seen_positions:
                unique_log.append(entry)
                seen_positions.add(pos_key)
        
        return result_text, unique_log
    else:
        return result_text, len(unique_replacements)


# -------------------------------------------------
# EXAMPLE USAGE
# -------------------------------------------------
if __name__ == "__main__":
    test_text = """
SCRIPPS HEALTH
Martinez, Lelia M
NS
MRN: 701326527, DOB: 11/9/1948, Sex: F

Social History:
Lelia M Martinez
    """
    
    replacement_map = {
        "Name::martinez lelia m": {
            "field": "Name",
            "original": "Martinez, Lelia M",
            "dummy": "Smith, John A"
        },
        "MRN::701326527": {
            "field": "MRN",
            "original": "701326527",
            "dummy": "000000001"
        }
    }
    
    replaced, log = smart_replace(test_text, replacement_map, verbose=True)
    
    print("\n" + "="*70)
    print("ORIGINAL:")
    print("="*70)
    print(test_text)
    
    print("\n" + "="*70)
    print("REPLACED:")
    print("="*70)
    print(replaced)
    
    print("\n" + "="*70)
    print(f"MATCHES: {len(log)}")
    print("="*70)
    for item in log:
        print(f"\n{item['field']}: {item['similarity']}%")
        print(f"  Found: '{item['matched_text']}'")
        print(f"  Replaced: '{item['dummy_value']}'")