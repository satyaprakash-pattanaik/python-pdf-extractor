"""
PII Mapper - Build Replacement Maps and Master PII
Reads pii.json + dummy.json → Creates replacement_pii.json + master_pii.json
"""

import json
import random
import re
from pathlib import Path


# -------------------------------------------------
# UTILITIES
# -------------------------------------------------
def normalize(value):
    """Normalize strings for consistent mapping keys"""
    return re.sub(r"\s+", " ", str(value).lower()).strip()


def load_json(path):
    """Load JSON file"""
    path = Path(path)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    print(f"⚠️ Warning: {path} not found, returning empty dict")
    return {}


def save_json(path, data):
    """Save JSON file with pretty formatting"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print(f"✅ Saved: {path}")


# -------------------------------------------------
# BUILD REPLACEMENT MAP
# -------------------------------------------------
def build_replacement_map(pii_data, dummy_data, output_path="replacement_pii.json"):
    """
    Build replacement map from pii.json and dummy.json
    
    Args:
        pii_data: Dict from pii.json - what to find
            {
                "Name": ["Satya Prakash", "Rupal Patel"],
                "MRN": ["SWH123", "SWH456"]
            }
        
        dummy_data: Dict from dummy.json - what to replace with
            {
                "Name": ["John Doe", "Jane Smith", "Bob Lee"],
                "MRN": ["MRN-000001", "MRN-000002", "MRN-000003"]
            }
        
        output_path: Where to save replacement_pii.json
    
    Returns:
        replacement_map: Dict with format:
            {
                "Name::satya prakash": {
                    "field": "Name",
                    "original": "Satya Prakash",
                    "dummy": "John Doe"
                }
            }
    """
    
    print("\n" + "="*60)
    print("BUILDING REPLACEMENT MAP")
    print("="*60)
    
    # Load existing map if it exists (to preserve previous mappings)
    replacement_map = load_json(output_path) if Path(output_path).exists() else {}
    
    # Track which dummy values are already used
    used_dummies = set()
    for entry in replacement_map.values():
        used_dummies.add(entry.get("dummy", ""))
    
    stats = {
        'new_mappings': 0,
        'existing_mappings': 0,
        'pool_exhausted': 0
    }
    
    # Process each field
    for field, pii_values in pii_data.items():
        print(f"\nProcessing field: {field}")
        
        # Ensure pii_values is a list
        if not isinstance(pii_values, list):
            pii_values = [pii_values]
        
        # Get dummy pool for this field
        dummy_pool = dummy_data.get(field, [])
        if not isinstance(dummy_pool, list):
            dummy_pool = [dummy_pool]
        
        if not dummy_pool:
            print(f"  ⚠️ No dummy data available for '{field}'")
            continue
        
        print(f"  PII values: {len(pii_values)}")
        print(f"  Dummy pool: {len(dummy_pool)}")
        
        # Map each PII value to a dummy
        for original_value in pii_values:
            if not original_value:
                continue
            
            # Create unique key
            key = f"{field}::{normalize(original_value)}"
            
            # Skip if already mapped
            if key in replacement_map:
                stats['existing_mappings'] += 1
                print(f"  ✓ Already mapped: '{original_value}'")
                continue
            
            # Find unused dummy from pool
            available_dummies = [d for d in dummy_pool if d not in used_dummies]
            
            if available_dummies:
                # Pick random unused dummy
                dummy_value = random.choice(available_dummies)
            else:
                # Pool exhausted - use fallback
                stats['pool_exhausted'] += 1
                dummy_value = f"[REDACTED-{field}-{len(replacement_map)}]"
                print(f"  ⚠️ Pool exhausted! Using fallback for: '{original_value}'")
            
            # Add to map
            replacement_map[key] = {
                "field": field,
                "original": str(original_value),
                "dummy": dummy_value
            }
            
            used_dummies.add(dummy_value)
            stats['new_mappings'] += 1
            print(f"  + New mapping: '{original_value}' → '{dummy_value}'")
    
    # Save the map
    save_json(output_path, replacement_map)
    
    # Print statistics
    print("\n" + "="*60)
    print("MAPPING STATISTICS")
    print("="*60)
    print(f"New mappings created: {stats['new_mappings']}")
    print(f"Existing mappings: {stats['existing_mappings']}")
    print(f"Pool exhausted (fallbacks): {stats['pool_exhausted']}")
    print(f"Total mappings: {len(replacement_map)}")
    print("="*60)
    
    return replacement_map


# -------------------------------------------------
# BUILD MASTER PII (REVERSE MAP)
# -------------------------------------------------
def build_master_pii(replacement_map, output_path="master_pii.json"):
    """
    Build master PII (reverse mapping for de-anonymization)
    
    Args:
        replacement_map: The replacement_pii.json data
        output_path: Where to save master_pii.json
    
    Returns:
        master_map: Dict with reversed mapping (dummy → original)
            {
                "Name::john doe": {
                    "field": "Name",
                    "original": "John Doe",      ← This was the dummy
                    "dummy": "Satya Prakash"     ← This was the original
                }
            }
    """
    
    print("\n" + "="*60)
    print("BUILDING MASTER PII (REVERSE MAP)")
    print("="*60)
    
    master_map = {}
    
    for key, entry in replacement_map.items():
        field = entry.get("field", "")
        original = entry.get("original", "")  # Real PII
        dummy = entry.get("dummy", "")         # Fake PII
        
        if not dummy or not original:
            continue
        
        # Create reverse key (using dummy as the lookup value)
        reverse_key = f"{field}::{normalize(dummy)}"
        
        # Swap original and dummy
        master_map[reverse_key] = {
            "field": field,
            "original": dummy,      # What appears in anonymized text
            "dummy": original       # What it should be replaced back to
        }
    
    # Save the master map
    save_json(output_path, master_map)
    
    print(f"\nTotal reverse mappings: {len(master_map)}")
    print("="*60)
    
    return master_map


# -------------------------------------------------
# COMPLETE WORKFLOW
# -------------------------------------------------
def create_all_maps(pii_json_path="pii.json", 
                   dummy_json_path="dummy.json",
                   replacement_output="replacement_pii.json",
                   master_output="master_pii.json"):
    """
    Complete workflow: Read PII + Dummy → Create both maps
    
    Args:
        pii_json_path: Path to your pii.json (what to anonymize)
        dummy_json_path: Path to your dummy.json (fake data)
        replacement_output: Where to save replacement map
        master_output: Where to save master PII
    
    Returns:
        (replacement_map, master_map)
    """
    
    print("\n" + "="*70)
    print(" PII MAPPING SYSTEM ")
    print("="*70)
    
    # Step 1: Load input files
    print("\n📂 Loading input files...")
    pii_data = load_json(pii_json_path)
    dummy_data = load_json(dummy_json_path)
    
    if not pii_data:
        print(f"❌ Error: Could not load {pii_json_path}")
        return None, None
    
    if not dummy_data:
        print(f"❌ Error: Could not load {dummy_json_path}")
        return None, None
    
    print(f"✅ Loaded pii.json: {len(pii_data)} fields")
    print(f"✅ Loaded dummy.json: {len(dummy_data)} fields")
    
    # Step 2: Build replacement map
    replacement_map = build_replacement_map(
        pii_data, 
        dummy_data, 
        replacement_output
    )
    
    # Step 3: Build master PII (reverse map)
    master_map = build_master_pii(
        replacement_map, 
        master_output
    )
    
    print("\n" + "="*70)
    print("✅ ALL MAPS CREATED SUCCESSFULLY!")
    print("="*70)
    print(f"📄 Replacement map: {replacement_output}")
    print(f"📄 Master PII: {master_output}")
    print("="*70 + "\n")
    
    return replacement_map, master_map


# -------------------------------------------------
# EXAMPLE USAGE
# -------------------------------------------------
if __name__ == "__main__":
    # Example: Create sample pii.json and dummy.json for testing
    
    sample_pii = {
        "Name": ["Satya Prakash", "Rupal Patel", "Peter Begle"],
        "MRN": ["SWH123", "SWH456", "SWH789"],
        "DOB": ["01/15/1985", "03/22/1990"],
        "Phone": ["555-123-4567", "555-987-6543"]
    }
    
    sample_dummy = {
        "Name": ["John Doe", "Jane Smith", "Bob Lee", "Alice Brown", "Tom White"],
        "MRN": ["MRN-000001", "MRN-000002", "MRN-000003", "MRN-000004"],
        "DOB": ["05/20/1990", "08/15/1985", "12/10/1992"],
        "Phone": ["555-000-0001", "555-000-0002", "555-000-0003"]
    }
    
    # Save sample files
    save_json("pii.json", sample_pii)
    save_json("dummy.json", sample_dummy)
    
    print("📝 Created sample pii.json and dummy.json\n")
    
    # Run the complete workflow
    replacement_map, master_map = create_all_maps(
        pii_json_path="pii.json",
        dummy_json_path="dummy.json",
        replacement_output="replacement_pii.json",
        master_output="master_pii.json"
    )
    
    # Show some examples
    if replacement_map:
        print("\n📋 Sample Replacement Map Entries:")
        print("-" * 60)
        for i, (key, entry) in enumerate(list(replacement_map.items())[:5]):
            print(f"{i+1}. {entry['field']}: '{entry['original']}' → '{entry['dummy']}'")
        if len(replacement_map) > 5:
            print(f"... and {len(replacement_map) - 5} more entries")
    
    if master_map:
        print("\n📋 Sample Master PII Entries (Reverse):")
        print("-" * 60)
        for i, (key, entry) in enumerate(list(master_map.items())[:5]):
            print(f"{i+1}. {entry['field']}: '{entry['original']}' → '{entry['dummy']}'")
        if len(master_map) > 5:
            print(f"... and {len(master_map) - 5} more entries")