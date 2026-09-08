"""Regression test for the V8.4.0 f-string JSON format-specifier failure."""
import ast
import unittest
from dataclasses import dataclass
from pathlib import Path


class PromptRegressionV841Tests(unittest.TestCase):
    def test_build_prompt_renders_visual_requirement_json(self):
        source=Path(__file__).parents[1].joinpath("app.py").read_text(encoding="utf-8")
        tree=ast.parse(source)
        selected=[node for node in tree.body if isinstance(node,(ast.ClassDef,ast.FunctionDef)) and node.name in {"LessonConfig","build_prompt"}]
        module=ast.Module(body=selected,type_ignores=[])
        namespace={"dataclass":dataclass}
        exec(compile(module,"app.py","exec"),namespace)
        config=namespace["LessonConfig"]("GV","Trường","Toán 12","Kết nối tri thức","Tính đơn điệu",2,"Trung bình – khá",20,"Xanh học thuật",True,True)
        prompt=namespace["build_prompt"](config)
        self.assertIn('"visual_requirement":{"required":false',prompt.replace("\t",""))
        self.assertIn('"type":"function_graph|variation_table|source_image"',prompt)


if __name__ == "__main__":
    unittest.main()
