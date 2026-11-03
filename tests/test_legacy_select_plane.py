import unittest
from unittest.mock import MagicMock

from solidworks_com import SolidWorksCOM
try:
    from test_plane_lookup import localized_doc
except ImportError:
    from tests.test_plane_lookup import localized_doc


def legacy(doc):
    com = SolidWorksCOM.__new__(SolidWorksCOM)
    com.get_active_document = lambda: doc
    return com


class LegacySelectPlaneTests(unittest.TestCase):
    def test_english_name_is_selected_directly(self):
        doc, planes = localized_doc(select_by_name=True)
        self.assertTrue(legacy(doc).select_plane("Top"))
        self.assertFalse(any(f.selected for f in planes.values()))

    def test_localized_plane_is_found_by_orientation(self):
        for key in ["Front", "Top", "Right"]:
            doc, planes = localized_doc()
            self.assertTrue(legacy(doc).select_plane(key), key)
            self.assertTrue(planes[key.lower()].selected)

    def test_unknown_plane_is_rejected_and_create_sketch_does_not_insert(self):
        doc, _ = localized_doc(select_by_name=True)
        com = legacy(doc)
        self.assertFalse(com.select_plane("Diagonal"))
        ok, _ = com.create_sketch("Diagonal")
        self.assertFalse(ok)
        doc.InsertSketch2.assert_not_called()

    def test_failed_selection_does_not_insert_a_sketch(self):
        doc = MagicMock()
        doc.FirstFeature = None
        doc.Extension.SelectByID2.return_value = False
        ok, _ = legacy(doc).create_sketch("Front")
        self.assertFalse(ok)
        doc.InsertSketch2.assert_not_called()

    def test_create_sketch_succeeds_on_localized_plane(self):
        doc, _ = localized_doc()
        ok, _ = legacy(doc).create_sketch("Right")
        self.assertTrue(ok)
        doc.InsertSketch2.assert_called_once_with(True)


if __name__ == "__main__":
    unittest.main()
