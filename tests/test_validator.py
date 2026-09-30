"""
tests/test_validator.py — Unit tests for src/validator.py.

These tests exercise the deterministic validator in isolation: no LLM calls,
no network, no dependency on generator.py or strategy.py. The whole suite
runs in well under a second.
"""

import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.validator import (
    WPM,
    check_no_boilerplate_cta,
    check_required_fields,
    check_runtime_tolerance,
    estimate_seconds,
    validate,
)


def budget_for(target_seconds: int) -> dict:
    """Mirror pipeline._compute_budget with the fixed 20/68/12 split."""
    total = round((target_seconds / 60) * WPM)
    hook = round(total * 0.20)
    cta = round(total * 0.12)
    body = total - hook - cta
    return {"total_words": total, "hook_words": hook, "body_words": body, "cta_words": cta}


def output_with_exact_budget(target_seconds: int, cta_text: str = "Save this for your next payment check.") -> dict:
    """Build an output whose sections hit the budget word counts exactly."""
    b = budget_for(target_seconds)
    # word_count = len(text.split()); sections built to land on the budget exactly
    hook = " ".join(["Stop"] * b["hook_words"])
    body = " ".join(["Point"] * b["body_words"])
    cta = " ".join(cta_text.split()[: b["cta_words"]]) if cta_text.split() else "Save"
    return {"hook": hook, "body": body, "cta": cta}


class TestRequiredFields(unittest.TestCase):
    def test_all_fields_present(self):
        output = {"hook": "Your bank is quietly draining you.", "body": "Here is the math.", "cta": "Save this."}
        self.assertEqual(check_required_fields(output), [])

    def test_fields_missing_or_empty(self):
        emptyish = {"hook": "", "body": "   ", "cta": "Save this."}
        errors = check_required_fields(emptyish)
        self.assertEqual(len(errors), 2)
        self.assertTrue(any("hook" in e for e in errors))
        self.assertTrue(any("body" in e for e in errors))

        missing = {"hook": "x"}
        errors = check_required_fields(missing)
        self.assertEqual(len(errors), 2)  # body + cta missing


class TestBoilerplateCTA(unittest.TestCase):
    def test_clean_cta_passes(self):
        self.assertEqual(check_no_boilerplate_cta("Save this for the next time you get paid."), [])

    def test_boilerplate_caught_case_insensitive(self):
        for phrase in ("Like and subscribe!", "FOLLOW FOR MORE", "Smash the like button"):
            errors = check_no_boilerplate_cta(phrase)
            self.assertEqual(len(errors), 1, phrase)


class TestRuntimeTolerance(unittest.TestCase):
    def test_pass_at_upper_boundary(self):
        target = 60
        b = budget_for(target)
        # CTA text padded with filler words so total lands exactly at +10% boundary
        output = output_with_exact_budget(target)
        current_total = len(output["hook"].split()) + len(output["body"].split()) + len(output["cta"].split())
        wanted_total = round(b["total_words"] * 1.10)
        output["body"] = output["body"] + " " + " ".join(["more"] * (wanted_total - current_total))
        errors, offending = check_runtime_tolerance(output, b, target)
        self.assertEqual(errors, [])
        self.assertEqual(offending, [])

    def test_fail_just_above_upper_boundary(self):
        target = 60
        b = budget_for(target)
        output = output_with_exact_budget(target)
        current_total = len(output["hook"].split()) + len(output["body"].split()) + len(output["cta"].split())
        wanted_total = round(b["total_words"] * 1.10) + 2  # just past tolerance
        output["body"] = output["body"] + " " + " ".join(["more"] * (wanted_total - current_total))
        errors, offending = check_runtime_tolerance(output, b, target)
        self.assertEqual(len(errors), 1)
        self.assertEqual(offending, ["body"])  # body deviates most from its budget seconds

    def test_fail_below_lower_boundary(self):
        target = 60
        b = budget_for(target)
        output = {"hook": "Short.", "body": "Also short.", "cta": "Save it."}  # far under budget
        errors, offending = check_runtime_tolerance(output, b, target)
        self.assertEqual(len(errors), 1)
        self.assertEqual(len(offending), 1)  # repair target identified


class TestValidateEntryPoint(unittest.TestCase):
    def test_full_pass_on_in_budget_output(self):
        target = 45
        output = output_with_exact_budget(target)
        result = validate(output, target, budget_for(target))
        self.assertTrue(result.passed)
        self.assertEqual(result.errors, [])

    def test_full_fail_flags_boilerplate_and_offending_section(self):
        target = 45
        output = output_with_exact_budget(target, cta_text="Like and subscribe for more!")
        result = validate(output, target, budget_for(target))
        self.assertFalse(result.passed)
        self.assertTrue(any("boilerplate" in e for e in result.errors))
        self.assertIn("cta", result.offending_sections)


class TestEstimateSeconds(unittest.TestCase):
    def test_estimate_is_deterministic(self):
        text = "one two three four five six seven"  # 7 words
        expected = 7 / WPM * 60
        self.assertAlmostEqual(estimate_seconds(text), expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
