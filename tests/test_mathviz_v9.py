import json
import unittest

from mathviz_engine import extract_mathviz, question_bank_to_lesson, render_visual, validate_visual


class MathVizV9Tests(unittest.TestCase):
    def test_extracts_visual_from_question(self):
        q="Xem hình.<div data-mathviz='{" + '"type":"dothi","fn":"x^2","xmin":-2,"xmax":2,"ymin":-1,"ymax":4' + "}'></div>"
        clean,visuals,errors=extract_mathviz(q)
        self.assertEqual(clean,"Xem hình."); self.assertEqual(visuals[0]["type"],"dothi"); self.assertFalse(errors)

    def test_rejects_malformed_bbt(self):
        ok,_=validate_visual({"type":"bbt","nodes":["-oo","+oo"],"marks":[""],"signs":["+"],"vals":["-oo","+oo"]})
        self.assertFalse(ok)

    def test_imports_question_bank_and_balanced_answer(self):
        data={"mcq":[{"tag":"chuong1_bai1","lvl":1,"q":"Câu hỏi","opts":["1","2","3","4"],"ans":2,"exp":"Giải"}],"tf":[],"sa":[]}
        lesson,warnings=question_bank_to_lesson(data)
        self.assertEqual(len(lesson["slides"]),1); self.assertIn("Đáp án C",lesson["slides"][0]["answer"]); self.assertFalse(warnings)

    def test_missing_referenced_image_warns(self):
        data={"mcq":[],"tf":[],"sa":[{"q":"Từ tấm bìa, cắt bốn hình vuông như hình bên.","ans":"2","exp":"Giải"}]}
        _,warnings=question_bank_to_lesson(data)
        self.assertTrue(warnings)

    def test_bbt_and_net_render_png(self):
        bbt={"type":"bbt","nodes":["-oo","1","+oo"],"marks":["","0",""],"signs":["+","-"],"vals":[{"t":"-oo"},{"t":"2"},{"t":"-oo"}]}
        net={"type":"net","shape":"open_box","width":16,"height":10,"cut":"x"}
        for payload in (bbt,net): self.assertEqual(render_visual(payload).read(8),b"\x89PNG\r\n\x1a\n")


if __name__=="__main__": unittest.main()
