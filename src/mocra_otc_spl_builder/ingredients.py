"""Ingredients for a cosmetic listing, taken from fragrance-reg-core's US ingredient list.

The listing must match the label (IG 36.2.2.12), so the label list fragrance-reg-core
generates for the US is used as is, in its order. Nothing is re-sorted here.

Needs the optional dependency: pip install "mocra-otc-spl-builder[core]".
"""

from dataclasses import dataclass, field
from datetime import date

from .completeness import Finding
from .models import Ingredient


@dataclass
class IngredientResult:
    ingredients: list[Ingredient]
    label_text: str  # "Ingredients: ...", to compare with the printed label
    findings: list[Finding] = field(default_factory=list)  # block the listing until resolved
    warnings: list[str] = field(default_factory=list)  # a person should read these

    @property
    def ok(self) -> bool:
        return not self.findings


def ingredients_from_product(product, as_of: date | None = None, labeling_service=None) -> IngredientResult:
    """US label ingredients for a fragrance_reg_core FinishedProduct."""
    from fragrance_reg_core.models.findings import Severity
    from fragrance_reg_core.models.product import ComponentRole
    from fragrance_reg_core.models.regulatory import Market
    from fragrance_reg_core.services.labeling_service import LabelingService

    service = labeling_service or LabelingService()
    label = service.generate(product, Market.US, as_of)

    findings, warnings = [], []
    if not label.rules_verified:
        findings.append(Finding("ingredients", "fragrance-reg-core's US labeling rules are not marked verified"))
    for f in label.findings:
        text = f"{f.code}: {f.message}" + (f" ({f.component})" if f.component else "")
        if f.severity == Severity.ERROR:
            findings.append(Finding("ingredients", text))
        elif f.severity == Severity.WARNING:
            warnings.append(text)

    colorants = {c.name for c in product.components if c.role == ComponentRole.COLORANT}
    ingredients = [
        Ingredient(name=e.name, color_additive=bool(colorants) and set(e.sources) <= colorants)
        for e in label.entries
    ]
    first_color = next((i for i, ing in enumerate(ingredients) if ing.color_additive), None)
    if first_color is not None and any(not ing.color_additive for ing in ingredients[first_color:]):
        warnings.append(
            "A color additive is listed before other ingredients (fragrance-reg-core orders by weight). "
            "US labels may group colors at the end; the listing must follow the printed label."
        )
    fragrance = [e for e in label.entries if e.kind == "fragrance"]
    if len(fragrance) > 1:
        findings.append(Finding("ingredients", "more than one fragrance entry (IG 3.4.4.7)"))
    return IngredientResult(ingredients=ingredients, label_text=label.text, findings=findings, warnings=warnings)
