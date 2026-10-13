"""What we know about a product before it becomes SPL. Empty strings mean "not known yet"."""

from dataclasses import dataclass, field


@dataclass
class ResponsiblePerson:
    """MoCRA responsible person: the company named on the label."""

    name: str
    address: str
    phone: str = ""
    email: str = ""


@dataclass
class Facility:
    """A manufacturing or processing facility (ours or a contract manufacturer's)."""

    name: str
    address: str
    duns: str = ""
    fei: str = ""
    cosmetic_registration_number: str = ""


@dataclass
class CosmeticProduct:
    name: str
    responsible_person: ResponsiblePerson
    facilities: list[Facility]
    # Codes from FDA's cosmetic product category list (see sources/). Not validated yet.
    category_codes: list[str] = field(default_factory=list)
    # Label order. Build from fragrance_reg_core.services.labeling_service for the US market.
    ingredients: list[str] = field(default_factory=list)
    # Label text or image file paths; listing requires the label.
    label_files: list[str] = field(default_factory=list)
    # FDA-assigned once listed.
    product_listing_number: str = ""


@dataclass
class ActiveIngredient:
    name: str
    unii: str = ""
    strength: str = ""  # e.g. "2 g/100 mL", as on the Drug Facts label


@dataclass
class OtcProduct:
    name: str
    labeler_name: str
    labeler_code: str  # NDC labeler code; "" until FDA assigns one
    facilities: list[Facility]
    monograph_id: str  # e.g. "M020"; must exist in data/otc_monographs.json
    active_ingredients: list[ActiveIngredient]
    inactive_ingredients: list[str] = field(default_factory=list)
    drug_facts_file: str = ""
    ndc_product_code: str = ""
