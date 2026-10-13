"""FDA SPL builder for MoCRA cosmetic registration/listing and OTC drug listing (own brands)."""

from .completeness import Finding, check_otc_product
from .cosmetic_spl import ListingNotValid, build_cosmetic_listing
from .spl_xml import SplFile, SplNotValid
from .cosmetic_validation import validate_cosmetic_listing
from .ingredients import IngredientResult, ingredients_from_product
from .facility_registration import build_facility_registration, validate_facility_registration
from .models import (
    ActiveIngredient,
    Address,
    AuthorizedAgent,
    ContactParty,
    FacilityRegistration,
    RegisteredFacility,
    RegisteredProduct,
    RegistrationType,
    USAgent,
    BusinessType,
    Category,
    CosmeticListing,
    CosmeticProduct,
    Facility,
    Ingredient,
    ListingType,
    OtcProduct,
    ResponsiblePerson,
    Signer,
)

__version__ = "0.0.1"

__all__ = [
    "ActiveIngredient",
    "Address",
    "AuthorizedAgent",
    "ContactParty",
    "FacilityRegistration",
    "RegisteredFacility",
    "RegisteredProduct",
    "RegistrationType",
    "USAgent",
    "build_facility_registration",
    "validate_facility_registration",
    "BusinessType",
    "Category",
    "CosmeticListing",
    "CosmeticProduct",
    "Facility",
    "Finding",
    "Ingredient",
    "IngredientResult",
    "ingredients_from_product",
    "ListingNotValid",
    "ListingType",
    "OtcProduct",
    "ResponsiblePerson",
    "Signer",
    "SplFile",
    "SplNotValid",
    "build_cosmetic_listing",
    "check_otc_product",
    "validate_cosmetic_listing",
]
