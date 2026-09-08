import unittest

import sympy as sp

from adaptive_engine import variant_consistency
from curriculum_engine import audit_curriculum, normalize_profile, normalize_storyboard
from lesson_engine import audit_lesson, safe_autofix_lesson, verify_variation_table
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

    def test_safe_autofix_removes_only_unverified_table(self):
        lesson={"title":"x","objectives":[],"slides":[{"title":"S","activity":"KHỞI ĐỘNG","layout":"content","bullets":[r"Tập xác định là \\mathbb{R}"],"formulas":[],"question":"","product":"","answer":"","teacher_note":"","source_ref":"","graph":None,"variation_table":{"expression":"x**2","points":["-∞","+∞"],"interval_signs":["+"],"values":["+∞","+∞"]}}]}
        fixed,changes=safe_autofix_lesson(lesson)
        self.assertIsNone(fixed["slides"][0]["variation_table"])
        self.assertIn("ℝ",fixed["slides"][0]["bullets"][0])
        self.assertTrue(changes)
        report=audit_lesson(fixed,1)
        self.assertNotEqual(report["status"],"PASS")


class CurriculumV8Tests(unittest.TestCase):
    def setUp(self):
        self.profile=normalize_profile({
            "source_scope":"SGK Toán 12, bài Cực trị của hàm số",
            "core_knowledge":["Điều kiện cần để hàm số có cực trị"],
            "learning_outcomes":[{"outcome":"Nhận biết và tìm được điểm cực trị", "cognitive_level":"vận dụng", "math_competency":"giải quyết vấn đề toán học", "evidence":"Phiếu học tập có lập luận", "assessment":"Rubric 3 mức"}],
        })
        self.story=normalize_storyboard([
            {"phase":phase,"title":phase.title(),"minutes":minutes,"objective":"Hoàn thành nhiệm vụ","organization":"Cá nhân/cặp đôi","student_task":"Giải quyết tình huống toán học","product":"Phiếu trả lời","assessment":"Quan sát và rubric","guiding_questions":["Vì sao?"],"anticipated_difficulties":["Nhầm dấu"],"support":["Gợi ý bằng bảng dấu"],"conclusion":"Chốt kiến thức","slide_refs":[i]}
            for i,(phase,minutes) in enumerate(zip(("KHỞI ĐỘNG","HÌNH THÀNH KIẾN THỨC","LUYỆN TẬP","VẬN DỤNG","CỦNG CỐ"),(5,18,12,7,3)),1)
        ])

    def test_complete_profile_and_storyboard_pass(self):
        self.assertEqual(audit_curriculum(self.profile,self.story,1,5)["status"],"PASS")

    def test_time_mismatch_fails(self):
        self.story[0]["minutes"]=20
        self.assertEqual(audit_curriculum(self.profile,self.story,1,5)["status"],"FAIL")

    def test_outcome_without_evidence_fails(self):
        self.profile["learning_outcomes"][0]["evidence"]=""
        self.assertEqual(audit_curriculum(self.profile,self.story,1,5)["status"],"FAIL")

    def test_slide_reference_out_of_range_fails(self):
        self.story[-1]["slide_refs"]=[6]
        self.assertEqual(audit_curriculum(self.profile,self.story,1,5)["status"],"FAIL")


if __name__ == "__main__":
    unittest.main()
