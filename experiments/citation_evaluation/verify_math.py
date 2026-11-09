"""Independent rational/Decimal reference calculation (synthetic only)."""

from decimal import Decimal, localcontext
from fractions import Fraction
import json


def references():
    # No imports from evaluate.py: separate arithmetic reference, not copied floats.
    sensitivity = Fraction(9, 10)
    false_positive_rate = Fraction(1, 100)
    prevalence = Fraction(1, 1000)
    ppv = sensitivity * prevalence / (sensitivity * prevalence + false_positive_rate * (1 - prevalence))
    with localcontext() as context:
        context.prec = 40
        n = Decimal(3)
        x = Decimal(2)
        p = x / n
        z = Decimal("1.959963984540054")
        # Algebraically equivalent Wilson score roots, evaluated with Decimal.
        center_numerator = x + z**2 / 2
        radius_numerator = z * (n * p * (1 - p) + z**2 / 4).sqrt()
        lower = (center_numerator - radius_numerator) / (n + z**2)
        upper = (center_numerator + radius_numerator) / (n + z**2)
        return {
            "purpose": "hypothetical_arithmetic_not_measured_performance",
            "precision_at_budget_fraction": str(Fraction(2, 3)),
            "recall_fraction": str(Fraction(2, 4)),
            "selective_accuracy_fraction": str(Fraction(3, 5)),
            "coverage_fraction": str(Fraction(5, 6)),
            "wilson95_precision": [str(lower), str(upper)],
            "illustrative_ppv_fraction": str(ppv),
            "illustrative_expected_true_alerts": str(100_000 * prevalence * sensitivity),
            "illustrative_expected_false_alerts": str(100_000 * (1 - prevalence) * false_positive_rate),
        }


if __name__ == "__main__":
    print(json.dumps(references(), sort_keys=True, allow_nan=False))
