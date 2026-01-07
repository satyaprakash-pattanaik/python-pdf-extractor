import json
import re


def normalize(value: str) -> str:
    """
    Normalize values to catch format variations:
    - lowercase
    - remove spaces and common separators
    """
    return re.sub(r"[\s\-\(\)\.,#]", "", value.lower())


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_pii_values(pii_data: dict) -> list:
    """
    Extract all string values from pii.json (recursive-safe)
    """
    values = []

    def walk(obj):
        if isinstance(obj, dict):
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)
        elif isinstance(obj, str):
            values.append(obj)

    walk(pii_data)
    return values


def check_pii_leak(pii_path="pii.json", leaks_path="detected-leaks.json"):
    pii_data = load_json(pii_path)
    leaks_data = load_json(leaks_path)

    original_values = extract_pii_values(pii_data)
    normalized_originals = [normalize(v) for v in original_values if v.strip()]

    confirmed_leaks = []

    for item in leaks_data.get("leaked_fields", []):
        detected_value = item.get("matched_text", "")
        normalized_detected = normalize(detected_value)

        for original in normalized_originals:
            if original and (
                original in normalized_detected
                or normalized_detected in original
            ):
                confirmed_leaks.append({
                    "pii_type": item.get("pii_type"),
                    "matched_text": detected_value,
                    "page": item.get("page"),
                    "confidence": item.get("confidence")
                })
                break

    if confirmed_leaks:
        return {
            "real_pii_leak": True,
            "total_real_leaks": len(confirmed_leaks),
            "leaks": confirmed_leaks
        }

    return {
        "real_pii_leak": False,
        "total_real_leaks": 0,
        "message": "No original PII leakage found"
    }


if __name__ == "__main__":
    result = check_pii_leak()
    print(json.dumps(result, indent=2))
    