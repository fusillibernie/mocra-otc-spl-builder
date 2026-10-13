from mocra_otc_spl_builder import (
    Address,
    BusinessType,
    category,
    CosmeticListing,
    CosmeticProduct,
    Facility,
    Ingredient,
    ResponsiblePerson,
    Signer,
)

EXAMPLE_CATEGORY = category("05B")  # Perfumes

FILLER = Facility(fei="1234567")
SMALL_STUDIO = Facility(
    small_business=True,
    name="Small Pour Studio",
    address=Address(["123 Burl Road"], "Brooklyn", "USA", "USA", state="NY", postal_code="11201"),
)


def edp(**kw):
    base = dict(
        name="Moon Dust Eau de Parfum",
        categories=[EXAMPLE_CATEGORY],
        ingredients=[Ingredient("Alcohol Denat."), Ingredient("Fragrance"), Ingredient("Water"), Ingredient("Linalool")],
        facilities=[FILLER],
    )
    return CosmeticProduct(**{**base, **kw})


def listing(**kw):
    base = dict(
        responsible_person=ResponsiblePerson(
            name="Our Brand LLC", phone="+1-212-555-0100", business_type=BusinessType.DISTRIBUTOR
        ),
        products=[edp()],
        signer=Signer(full_name="Pat Example", signature="P. Example"),
    )
    return CosmeticListing(**{**base, **kw})
