import unittest

import sympy as sp

from adaptive_engine import variant_consistency
from lesson_engine import verify_variation_table
from safe_math_parser import SafeMathError, parse_math_expression
from v5_engine import build_variants, exam_fingerprint


class SafeParserTests(unittest.TestCase):
    def test_valid_expression(self):
        x=sp.Symbol("x", real=True)
        self.assertEqual(sp.expand(parse_math_expression("x**2-3*x", {"x":x})), x**2-3*x)

    def test_rejects_attribute_access(self):
        with self.assertRaises(SafeMathError):
            parse_math_expression("x.__class__")

    def test_rejects_unknown_function(self):
        with self.assertRaises(SafeMathError):
            parse_math_expression("open(1)")


class FingerprintAndVariantTests(unittest.TestCase):
    def test_different_exams_have_different_fingerprints(self):
        a={"questions":[{"id":"Q1","question":"1+1?"}]}
        b={"questions":[{"id":"Q1","question":"2+2?"}]}
        self.assertNotEqual(exam_fingerprint(a),exam_fingerprint(b))

    def test_variant_answer_metadata_stays_aligned(self):
        exam={"questions":[{"id":"Q1","type":"mcq","question":"?","options":["a","b","c","d"],"answer_index":2,"answer_letter":"C","answer":"C","solution":"Vậy chọn C.","check":{"type":"mcq_index","correct_index":2}}]}
        variants=build_variants(exam,n=4,seed=9)
        for variant in variants:
            q=variant["questions"][0]
            self.assertEqual(q["check"]["correct_index"],q["answer_index"])
            self.assertEqual(q["answer_letter"],"ABCD"[q["answer_index"]])
            self.assertEqual(q["answer"],"ABCD"[q["answer_index"]])
            self.assertIn("chọn "+"ABCD"[q["answer_index"]],q["solution"])
        self.assertEqual(variant_consistency(variants)["status"],"PASS")


class VariationTableTests(unittest.TestCase):
    def test_valid_table(self):
        ok,_=verify_variation_table({"expression":"x**3-3*x","points":["-∞","-1","1","+∞"],"interval_signs":["+","-","+"],"values":["-∞","2","-2","+∞"]})
        self.assertTrue(ok)

    def test_wrong_sign_fails(self):
        ok,_=verify_variation_table({"expression":"x**3-3*x","points":["-∞","-1","1","+∞"],"interval_signs":["-","-","+"],"values":["-∞","2","-2","+∞"]})
        self.assertFalse(ok)

    def test_omitted_critical_point_fails(self):
        ok,_=verify_variation_table({"expression":"x**3-3*x","points":["-∞","1","+∞"],"interval_signs":["-","+"],"values":["-∞","-2","+∞"]})
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
