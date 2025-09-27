"""
Logistics validation and processing
"""

from typing import Dict, Any, List, Optional
from .base import LogiBaseModel, LogisticsMetadata


class LogisticsValidator:
    """Logistics data validator"""

    def __init__(self):
        self.hs_codes = set()
        self.incoterms = set()

    def validate_hs_code(self, hs_code: str) -> bool:
        """Validate HS code format"""
        if not hs_code:
            return False
        # Basic HS code validation (6-10 digits)
        return hs_code.isdigit() and 6 <= len(hs_code) <= 10

    def validate_incoterm(self, incoterm: str) -> bool:
        """Validate Incoterm"""
        if not incoterm:
            return False
        valid_incoterms = {
            "EXW",
            "FCA",
            "CPT",
            "CIP",
            "DAP",
            "DPU",
            "DDP",
            "FAS",
            "FOB",
            "CFR",
            "CIF",
        }
        return incoterm.upper() in valid_incoterms

    def validate_metadata(self, metadata: LogisticsMetadata) -> Dict[str, Any]:
        """Validate logistics metadata"""
        errors = []
        warnings = []

        if metadata.hs_code and not self.validate_hs_code(metadata.hs_code):
            errors.append(f"Invalid HS code: {metadata.hs_code}")

        if metadata.incoterm and not self.validate_incoterm(metadata.incoterm):
            errors.append(f"Invalid Incoterm: {metadata.incoterm}")

        if metadata.weight is not None and metadata.weight <= 0:
            warnings.append("Weight should be positive")

        if metadata.volume is not None and metadata.volume <= 0:
            warnings.append("Volume should be positive")

        if metadata.value is not None and metadata.value <= 0:
            warnings.append("Value should be positive")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    def process_shipment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process shipment data"""
        metadata = LogisticsMetadata(**data)
        validation = self.validate_metadata(metadata)

        return {
            "metadata": metadata.to_dict(),
            "validation": validation,
            "processed_at": "2025-09-27T18:52:00Z",
        }
