"""Every SPL code value used, with the section of the FDA SPL Implementation Guide it comes from.

Source: "SPL Implementation Guide with Validation Procedures v1", revision 202312080859
(December 2023), sources/spl_ig_vp_dec_2023.pdf. Do not add a value here without a citation.
"""

# XML references (IG 2.1.2)
HL7_NS = "urn:hl7-org:v3"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
STYLESHEET = "https://www.accessdata.fda.gov/spl/stylesheet/spl.xsl"
SCHEMA_LOCATION = "urn:hl7-org:v3 https://www.accessdata.fda.gov/spl/schema/spl.xsd"

# Document and section codes are LOINC (IG 2.1.3.7, 2.2.1.7)
LOINC = "2.16.840.1.113883.6.1"
DOC_COSMETIC_LISTING = ("103572-4", "Cosmetic Product Listing")  # IG 36, Table 10
DOC_COSMETIC_UPDATE = ("X8888-5", "Cosmetic – Update")  # IG 36, Table 10
# Facility registration document types (IG 35, Table 9)
DOC_FACILITY_REGISTRATION = ("103573-2", "Cosmetic Facility Registration")
DOC_FACILITY_AMENDMENT = ("X8888-1", "Cosmetic Facility Registration - Amendment")
DOC_FACILITY_ABBREVIATED_RENEWAL = ("X8888-2", "Cosmetic Facility Registration - Abbreviated Renewal")
DOC_FACILITY_CANCELLATION = ("X8888-3", "Cosmetic Facility Registration - Cancellation")
DOC_FACILITY_BIENNIAL_RENEWAL = ("X8888-4", "Cosmetic Facility Registration - Biennial Renewal")
SECTION_PRODUCT_DATA = ("48780-1", "SPL product data elements section")  # IG 2.2 examples, 3.1

# Identifiers
DUNS_ROOT = "1.3.6.1.4.1.519.1"  # IG 2.1.5
FEI_ROOT = "2.16.840.1.113883.4.82"  # IG 36.1.5.4
COSMETIC_LISTING_NUMBER = "2.16.840.1.113883.3.9848"  # IG 3.1, 36.2.2.2
UNII = "2.16.840.1.113883.4.9"  # IG 3.4.4
ISO_COUNTRY = "1.0.3166.1.2.3"  # IG 2.1.6.2

# Cosmetic product category code system.
# OPEN QUESTION: the guide contradicts itself. Validation rule 3.4.3.2 says
# 2.16.840.1.113883.6.303 (FDA Product Classification), but the chapter 35 and 36 examples
# use 2.16.840.1.113883.6.345. We follow the validation rule until FDA (spl@fda.hhs.gov) or
# the SPL terminology files confirm which one the validator accepts.
COSMETIC_CATEGORY_SYSTEM = "2.16.840.1.113883.6.303"

# Business operation / type of business (IG 36.1.4.4, 36.1.4.5)
NCI_THESAURUS = "2.16.840.1.113883.3.26.1.1"
BUSINESS_TYPE_CODES = {
    "manufacture": "C43360",
    "pack": "C84731",
    "distribute": "C201565",
}
US_AGENT = ("C73330", "United States agent")  # IG 35.1.5

# Characteristics (IG 3.4.8, 3.4.9, 35.1.7)
SPL_CHARACTERISTIC = "2.16.840.1.113883.1.11.19255"
SMALL_BUSINESS = "SPLSMALLBUSINESS"
PROFESSIONAL_USE = "SPLPROFESSIONALUSE"
LABEL_IMAGE = "SPLIMAGE"

# Signing statements, word for word (IG 36.1.7.2 listing, 35.1.3.2 facility registration)
SIGNING_STATEMENT_REGISTRATION = (
    "The data and information in this submission have been reviewed and, to the best of my "
    "knowledge, are certified to be true and accurate. I agree to report changes to this "
    "information and renew as required under section 607 of the Federal Food, Drug, and "
    "Cosmetic Act."
)
SIGNING_STATEMENT = (
    "The data and information in this submission have been reviewed and, to the best of my "
    "knowledge, are certified to be true and accurate. I agree to report changes to this "
    "information as required under section 607 of the Federal Food, Drug, and Cosmetic Act."
)

# Category pairs that cannot both be on one listed product (IG 3.4.3.5 to 3.4.3.30)
LEAVE_ON_RINSE_OFF_PAIRS = [
    ("01D1", "01D2"),
    ("06A1", "06A2"),
    ("06F1", "06F2"),
    ("06I1", "06I2"),
    ("07C1", "07C2"),
    ("07D1", "07D2"),
    ("07I1", "07I2"),
    ("12D1", "12D2"),
    ("12F1", "12F2"),
    ("14C1", "14C2"),
    ("14D1", "14D2"),
    ("14J1", "14J2"),
]
