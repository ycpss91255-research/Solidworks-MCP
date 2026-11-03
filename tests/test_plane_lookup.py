import unittest
from unittest.mock import MagicMock

from solidworks_mcp.automation.sketches import SketchOperations


def rotation(normal):
    """ArrayData whose normal row (items 6-8) is `normal`."""
    return (1, 0, 0, 0, 1, 0) + tuple(normal) + (0, 0, 0, 1, 0, 0, 0)


class FakeFeature:
    def __init__(self, name, type_name="RefPlane", normal=(0, 0, 1)):
        self.Name = name
        self.GetTypeName2 = type_name
        self.GetNextFeature = None
        spec = MagicMock()
        spec.Transform.ArrayData = rotation(normal)
        self.GetSpecificFeature2 = spec
        self.selected = False

    def Select2(self, append, mark):
        self.selected = True
        return True


def chain(*features):
    for a, b in zip(features, features[1:]):
        a.GetNextFeature = b
    return features[0]


class Sketcher(SketchOperations):
    def __init__(self, doc):
        self.doc = doc

    def get_active_doc(self):
        return self.doc, None

    def _result(self, success, message, error_code=0, data=None):
        return {"success": success, "message": message, "data": data}


def localized_doc(select_by_name=False):
    front = FakeFeature("前基準面", normal=(0, 0, 1))
    top = FakeFeature("上基準面", normal=(0, 1, 0))
    right = FakeFeature("右基準面", normal=(-1, 0, 0))
    origin = FakeFeature("原點", type_name="OriginProfileFeature")
    doc = MagicMock()
    doc.FirstFeature = chain(front, top, right, origin)
    doc.Extension.SelectByID2.return_value = select_by_name
    return doc, {"front": front, "top": top, "right": right}


class PlaneLookupTests(unittest.TestCase):
    def test_english_name_is_used_first(self):
        doc, planes = localized_doc(select_by_name=True)
        result = Sketcher(doc).create_sketch("Right")
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["plane"], "Right Plane")
        self.assertFalse(any(f.selected for f in planes.values()))

    def test_localized_planes_are_found_by_orientation(self):
        for key, name in [("Front", "前基準面"), ("Top", "上基準面"), ("Right", "右基準面")]:
            doc, planes = localized_doc()
            result = Sketcher(doc).create_sketch(key)
            self.assertTrue(result["success"], key)
            self.assertEqual(result["data"]["plane"], name)
            self.assertTrue(planes[key.lower()].selected)
            doc.InsertSketch2.assert_called_once_with(True)

    def test_reordered_template_still_maps_by_orientation(self):
        right = FakeFeature("R", normal=(1, 0, 0))
        front = FakeFeature("F", normal=(0, 0, 1))
        top = FakeFeature("T", normal=(0, -1, 0))
        doc = MagicMock()
        doc.FirstFeature = chain(right, front, top)
        doc.Extension.SelectByID2.return_value = False
        self.assertEqual(Sketcher(doc).create_sketch("Top")["data"]["plane"], "T")

    def test_unknown_plane_is_an_error_and_never_defaults_to_front(self):
        doc, planes = localized_doc(select_by_name=True)
        result = Sketcher(doc).create_sketch("Diagonal")
        self.assertFalse(result["success"])
        doc.Extension.SelectByID2.assert_not_called()
        doc.InsertSketch2.assert_not_called()

    def test_plane_not_found_fails_without_sketching(self):
        doc = MagicMock()
        doc.FirstFeature = FakeFeature("custom", normal=(0.5, 0.5, 0.7))
        doc.Extension.SelectByID2.return_value = False
        result = Sketcher(doc).create_sketch("Front")
        self.assertFalse(result["success"])
        doc.InsertSketch2.assert_not_called()


if __name__ == "__main__":
    unittest.main()
