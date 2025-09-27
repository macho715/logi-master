"""
Base models for logistics domain
"""

from typing import Any, Dict, Optional


class Field:
    """Field descriptor for logistics metadata"""

    def __init__(self, default: Any = None, description: str = ""):
        self.default = default
        self.description = description

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return getattr(instance, f"_{self.name}", self.default)

    def __set__(self, instance, value):
        setattr(instance, f"_{self.name}", value)

    def __set_name__(self, owner, name):
        self.name = name


class LogiBaseModel:
    """Base model for logistics entities"""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def dict(self, exclude_none: bool = False) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = {}
        for key, value in self.__dict__.items():
            if not key.startswith("_"):
                if exclude_none and value is None:
                    continue
                result[key] = value
        return result


class LogisticsMetadata(LogiBaseModel):
    """Logistics metadata container"""

    def __init__(
        self,
        hs_code: Optional[str] = None,
        incoterm: Optional[str] = None,
        origin_country: Optional[str] = None,
        destination_country: Optional[str] = None,
        weight: Optional[float] = None,
        volume: Optional[float] = None,
        value: Optional[float] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.hs_code = hs_code
        self.incoterm = incoterm
        self.origin_country = origin_country
        self.destination_country = destination_country
        self.weight = weight
        self.volume = volume
        self.value = value

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return self.dict(exclude_none=True)
