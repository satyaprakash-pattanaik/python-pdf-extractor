import json
import random
import re
from pathlib import Path

# -------------------------------------------------
# HELPERS
# -------------------------------------------------
def normalize(value):
    """Normalize strings for consistent mapping"""
    return re.sub(r"\s+", " ", str(value).lower()).strip()


def load_json(path):
    if Path(path).exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# -------------------------------------------------
# BUILD GLOBAL REPLACEMENT MAP
# -------------------------------------------------
def build_global_mapping(combined_pii, dummy_pool, mapping_path):
    """
    Build replacement map from combined_pii and dummy_pool.
    Ensures each original value gets a proper dummy from the pool.

    combined_pii example:
    {
        "Name": ["Satya Prakash", "Ravi Kumar"],
        "MRN": ["SWH123", "SWH456"]
    }

    dummy_pool example:
    {
        "Name": ["John Doe", "Alice Smith", "Bob Lee"],
        "MRN": ["MRN-000001", "MRN-000002", "MRN-000003"]
    }
    """

    global_map = load_json(mapping_path)
    used_dummies = {entry["dummy"] for entry in global_map.values()}

    for field, values in combined_pii.items():
        # Ensure values is always a list
        if not isinstance(values, list):
            values = [values]

        # Ensure dummy options is a proper list
        options = dummy_pool.get(field, [])
        if isinstance(options, str):
            options = [options]

        for original in values:
            key = f"{field}::{normalize(original)}"

            if key in global_map:
                continue

            # Pick unused dummy or fallback
            available = [o for o in options if o not in used_dummies]
            dummy = random.choice(available) if available else "REDACTED"

            global_map[key] = {
                "field": field,
                "original": original,
                "dummy": dummy
            }

            used_dummies.add(dummy)

    save_json(mapping_path, global_map)
    return global_map


# -------------------------------------------------
# BUILD MASTER (REVERSE) PII MAP
# -------------------------------------------------
def build_master_pii(global_map, master_path):
    """
    Reverse the mapping so that dummy -> original
    """
    master = {}

    for key, entry in global_map.items():
        reverse_key = f"{entry['field']}::{normalize(entry['dummy'])}"
        master[reverse_key] = {
            "field": entry["field"],
            "original": entry["dummy"],
            "dummy": entry["original"]
        }

    save_json(master_path, master)
    return master
