"""
Logistics resources and data loading
"""

import csv
import yaml
from pathlib import Path
from typing import Dict, List, Any


def load_hs_codes(csv_path: str = "resources/hs2022.csv") -> Dict[str, Dict[str, Any]]:
    """Load HS codes from CSV file"""
    hs_codes = {}
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = row.get("code", "").strip()
                if code:
                    hs_codes[code] = {
                        "description": row.get("description", "").strip(),
                        "category": row.get("category", "").strip(),
                    }
    except FileNotFoundError:
        # Return empty dict if file not found
        pass
    return hs_codes


def load_incoterms(
    yaml_path: str = "resources/incoterm.yaml",
) -> Dict[str, Dict[str, Any]]:
    """Load Incoterms from YAML file"""
    incoterms = {}
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if isinstance(data, dict):
                incoterms = data
    except FileNotFoundError:
        # Return default Incoterms if file not found
        incoterms = {
            "EXW": {
                "name": "Ex Works",
                "description": "Seller makes goods available at their premises",
            },
            "FCA": {
                "name": "Free Carrier",
                "description": "Seller delivers goods to carrier nominated by buyer",
            },
            "CPT": {
                "name": "Carriage Paid To",
                "description": "Seller pays for carriage to named destination",
            },
            "CIP": {
                "name": "Carriage and Insurance Paid To",
                "description": "Seller pays for carriage and insurance to named destination",
            },
            "DAP": {
                "name": "Delivered at Place",
                "description": "Seller delivers goods to named place of destination",
            },
            "DPU": {
                "name": "Delivered at Place Unloaded",
                "description": "Seller delivers goods unloaded at named place of destination",
            },
            "DDP": {
                "name": "Delivered Duty Paid",
                "description": "Seller delivers goods cleared for import at named place of destination",
            },
            "FAS": {
                "name": "Free Alongside Ship",
                "description": "Seller delivers goods alongside the vessel",
            },
            "FOB": {
                "name": "Free on Board",
                "description": "Seller delivers goods on board the vessel",
            },
            "CFR": {
                "name": "Cost and Freight",
                "description": "Seller pays costs and freight to named destination",
            },
            "CIF": {
                "name": "Cost, Insurance and Freight",
                "description": "Seller pays costs, insurance and freight to named destination",
            },
        }
    return incoterms


def get_logistics_data() -> Dict[str, Any]:
    """Get all logistics data"""
    return {"hs_codes": load_hs_codes(), "incoterms": load_incoterms()}
