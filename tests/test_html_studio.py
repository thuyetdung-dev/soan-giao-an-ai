import io
import unittest

from PIL import Image

from html_studio import image_data_uri, figure_html, graph_png, standalone_html, variation_table_html, visual_from_json


class HtmlStudioTests(unittest.TestCase):
    def test_image_becomes_embedded_data_uri(self):
        out=io.BytesIO(); Image.new("RGB",(20,20),"white").save(out,format="PNG")
        self.assertTrue(image_data_uri(out.getvalue()).startswith("data:image/png;base64,"))

    def test_alt_and_caption_are_escaped(self):
        result=figure_html("data:image/png;base64,AA==",'<x onerror="1">',"A & B")
        self.assertNotIn('<x onerror="1">',result)
        self.assertIn("A &amp; B",result)

    def test_graph_renderer_outputs_png(self):
        data=graph_png("x**2-2*x",-4,4)
        self.assertEqual(data[:8],b"\x89PNG\r\n\x1a\n")

    def test_variation_table_html_has_three_rows(self):
        body=variation_table_html({"points":["-∞","0","+∞"],"interval_signs":["-","+"],"values":["+∞","0","+∞"]})
        self.assertEqual(body.count("<tr>"),3)
        self.assertIn("↘",body); self.assertIn("↗",body)

    def test_json_graph_to_standalone_html(self):
        body,document=visual_from_json('{"expression":"x**2","x_min":-3,"x_max":3}')
        self.assertIn("data:image/png;base64",body)
        self.assertTrue(document.startswith("<!doctype html>"))

    def test_document_has_utf8_and_viewport(self):
        document=standalone_html("<p>Toán học</p>")
        self.assertIn('charset="utf-8"',document); self.assertIn("viewport",document)


if __name__=="__main__":
    unittest.main()
