import unittest

from dashboard.layout_compare import compare_layouts, polygon_key


def shape(points):
    return {"hull": points, "holes": []}


class LayoutCompareTests(unittest.TestCase):
    def test_same_polygon_with_rotated_ring_is_unchanged(self):
        square = shape([[0, 0], [1, 0], [1, 1], [0, 1]])
        rotated = shape([[1, 1], [1, 0], [0, 0], [0, 1]])
        self.assertEqual(polygon_key(square), polygon_key(rotated))
        old = {"top": "inverter", "layers": [{"key": "1/0", "name": "Metal1",
                                             "polygons": [square]}]}
        new = {"top": "inverter", "layers": [{"key": "1/0", "name": "Metal1",
                                             "polygons": [rotated]}]}
        result = compare_layouts(old, new)
        self.assertEqual((result["removed_polygons"], result["added_polygons"]), (0, 0))

    def test_shifted_geometry_is_reported_on_both_sides(self):
        old = {"top": "inverter", "layers": [{"key": "1/0", "name": "Metal1",
            "polygons": [shape([[0, 0], [1, 0], [1, 1], [0, 1]])]}]}
        new = {"top": "inverter", "layers": [{"key": "1/0", "name": "Metal1",
            "polygons": [shape([[1, 0], [2, 0], [2, 1], [1, 1]])]}]}
        result = compare_layouts(old, new)
        self.assertEqual(result["old_only"]["1/0"], [0])
        self.assertEqual(result["new_only"]["1/0"], [0])
        self.assertEqual(result["layers"][0]["shared"], 0)


if __name__ == "__main__":
    unittest.main()
