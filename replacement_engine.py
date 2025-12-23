import re
from rapidfuzz import fuzz

# -------------------------------------------------
# NORMALIZE TEXT (OCR-ROBUST)
# -------------------------------------------------
def normalize(text):
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# -------------------------------------------------
# FIND APPROXIMATE SPANS IN ORIGINAL TEXT
# -------------------------------------------------
def find_spans(original_text, target, threshold):
    """
    Returns list of (start, end) spans in original_text
    that approximately match target.
    """
    norm_target = normalize(target)
    target_len = len(norm_target.split())

    spans = []

    words = list(re.finditer(r"\S+", original_text))
    for i in range(len(words)):
        window_words = words[i:i + target_len + 1]
        if not window_words:
            continue

        span_text = original_text[
            window_words[0].start(): window_words[-1].end()
        ]

        score = fuzz.token_set_ratio(
            normalize(span_text),
            norm_target
        )

        if score >= threshold:
            spans.append((window_words[0].start(), window_words[-1].end()))

    return spans


# -------------------------------------------------
# SMART FIND + REPLACE ENGINE
# -------------------------------------------------
def smart_replace(text, replace_map, field_thresholds=None):
    """
    replace_map format:
    {
        "NAME::satya prakash": {
            "field": "NAME",
            "original": "Satya Prakash",
            "dummy": "John Doe"
        }
    }
    """

    if field_thresholds is None:
        field_thresholds = {}

    # Collect all replacements as spans first
    replacements = []

    for entry in replace_map.values():
        original = entry.get("original", "")
        dummy = entry.get("dummy", "")
        field = entry.get("field", "")

        if not original or not dummy:
            continue

        threshold = field_thresholds.get(field, 80)

        spans = find_spans(text, original, threshold)

        for start, end in spans:
            replacements.append((start, end, dummy))

    # Sort by start index descending (safe replacement)
    replacements.sort(key=lambda x: x[0], reverse=True)

    for start, end, dummy in replacements:
        text = text[:start] + dummy + text[end:]

    return text
