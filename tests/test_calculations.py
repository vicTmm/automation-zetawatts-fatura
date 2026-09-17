import unittest

from backend.calculations import CalculationError, calculate

EXAMPLE = {
    "consumption": "1000", "te_supply": "0,3", "tusd_supply": "0,5",
    "te_injected": "0,25", "tusd_injected": "0,45", "flag": "0,05",
    "balance_credits": "200", "current_credits": "600", "enel_bill": "180,00",
    "discount_percent": "10",
}


class CalculationTests(unittest.TestCase):
    def test_spec_with_balance_and_current_credits(self):
        result = calculate(EXAMPLE)["results"]
        self.assertEqual(result["supply_rate"], "0.85000000")
        self.assertEqual(result["injected_rate"], "0.70000000")
        self.assertEqual(result["used_credits"], "800.00000000")
        self.assertEqual(result["total"], "850.00")
        self.assertEqual(result["zeta_bill"], "504.00")
        self.assertEqual(result["discount_current"], "42.00")
        self.assertEqual(result["discount_flag"], "40.00")
        self.assertEqual(result["discount_total"], "82.00")
        self.assertEqual(result["electricity_rate"], "0.63000000")

    def test_no_credits(self):
        result = calculate({**EXAMPLE, "balance_credits": "0", "current_credits": "0"})
        self.assertIsNone(result["results"]["electricity_rate"])
        self.assertEqual(result["results"]["zeta_bill"], "0.00")
        self.assertEqual(len(result["warnings"]), 1)

    def test_percent_is_percentage_points(self):
        self.assertEqual(calculate({**EXAMPLE, "discount_percent": "100"})["results"]["zeta_bill"], "0.00")
        self.assertEqual(calculate({**EXAMPLE, "discount_percent": "0"})["results"]["zeta_bill"], "560.00")

    def test_localized_input_and_half_up(self):
        result = calculate({**EXAMPLE, "consumption": "1.234,56", "enel_bill": "2,005"})
        self.assertEqual(result["inputs"]["consumption"], "1234.56")
        self.assertEqual(result["results"]["enel_bill"], "2.01")

    def test_no_intermediate_rate_rounding(self):
        result = calculate({**EXAMPLE, "te_injected": "0.12345678", "tusd_injected": "0.12345678"})
        self.assertEqual(result["results"]["zeta_bill"], "177.78")

    def test_invalid_numbers_rejected(self):
        for invalid in ["", None, "NaN", "Infinity", "-1", "1e3", "1,234.56", "1.234567891", "1000000001", True]:
            with self.subTest(invalid=invalid), self.assertRaises(CalculationError):
                calculate({**EXAMPLE, "consumption": invalid})
        with self.assertRaises(CalculationError):
            calculate({**EXAMPLE, "discount_percent": "101"})

    def test_missing_data_does_not_become_zero(self):
        with self.assertRaises(CalculationError):
            calculate({})

    def test_high_credits_warn_without_changing_the_formula(self):
        result = calculate({**EXAMPLE, "consumption": "10"})
        self.assertEqual(result["results"]["zeta_bill"], "504.00")
        self.assertEqual(len(result["warnings"]), 1)

