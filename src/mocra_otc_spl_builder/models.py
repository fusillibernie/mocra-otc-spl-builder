"""What we know about a product before it becomes SPL. Empty strings mean "not known yet"."""

from dataclasses import dataclass, field
from enum import Enum


@dataclass
class Address:
    street: list[str]  # one or two lines (IG 2.1.6.1)
    city: str
    country_code: str  # ISO 3166 alpha-3, e.g. "USA" (IG 2.1.6.2)
    country_name: str
    state: str = ""  # 2-letter, required for USA (IG 2.1.6.4)
    postal_code: str = ""


class BusinessType(Enum):
    """Responsible person's role (IG 36.1.4.5)."""

    MANUFACTURER = "manufacture"
    PACKER = "pack"
    DISTRIBUTOR = "distribute"


@dataclass
class ResponsiblePerson:
    """MoCRA responsible person: the company named on the label (the SPL "labeler")."""

    name: str
    phone: str  # +1-aaa-bbb-cccc[;ext=n] (IG 2.1.7.3 to 2.1.7.10)
    duns: str = ""  # optional for cosmetics (IG 36.1.2.2)
    business_type: BusinessType | None = None
    small_business: bool = False


@dataclass
class Facility:
    """A facility that manufactures or processes the products (ours or a contract manufacturer)."""

    fei: str = ""  # required unless small_business (IG 36.1.5.6)
    small_business: bool = False
    # Only used for a small business facility with no FEI (IG 36.1.5.9).
    name: str = ""
    address: Address | None = None
    # Legacy field from the first skeleton; kept for the OTC model.
    duns: str = ""


@dataclass
class Category:
    """FDA cosmetic product category (IG 3.4.3). Code and display name from FDA's list."""

    code: str
    display_name: str


@dataclass
class Ingredient:
    name: str
    unii: str = ""  # optional for cosmetics (IG 3.4.4.5)
    color_additive: bool = False  # COLR instead of INGR (IG 3.4.4.1)


@dataclass
class CosmeticProduct:
    name: str  # statement of identity as on the label; no ® or ™ (IG 3.4.2)
    categories: list[Category]
    ingredients: list[Ingredient]  # label order (IG 3.4.4)
    facilities: list[Facility]  # where it is made or processed (IG 36.1.6)
    listing_number: str = ""  # 53-XXXXXX-XXXXXX once FDA assigns it (IG 36.2.2.3)
    label_images: list[str] = field(default_factory=list)  # .jpg file names (IG 3.4.9)
    web_page: str = ""  # absolute http(s) URL (IG 3.4.7)
    professional_use: bool = False  # IG 3.4.8


@dataclass
class Signer:
    """Who signs the listing for the responsible person (IG 36.1.7)."""

    full_name: str
    signature: str  # the electronic signature text, e.g. "P. Bauer"


class ListingType(Enum):
    INITIAL = "initial"  # Cosmetic Product Listing (103572-4)
    UPDATE = "update"  # Cosmetic – Update (X8888-5)


@dataclass
class CosmeticListing:
    responsible_person: ResponsiblePerson
    products: list[CosmeticProduct]
    signer: Signer | None = None
    listing_type: ListingType = ListingType.INITIAL
    # For an update, the set id and next version number of the earlier listing (IG 36.1.1.4).
    set_id: str = ""
    version: int = 1


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
