import unittest

from grocery_spend_lab.analyze import attributes, classify_brand, classify_category


class ClassificationTests(unittest.TestCase):
    def test_categories_are_explicit_and_unknown_is_preserved(self):
        self.assertEqual(classify_category("Organic Whole Milk 1 gal"), "Dairy and eggs")
        self.assertEqual(classify_category("Fresh Bananas"), "Produce")
        self.assertEqual(classify_category(None), "Unknown")

    def test_private_label_and_ambiguous_brand_stay_distinct(self):
        self.assertEqual(classify_brand("Harris Teeter Whole Milk", False), "Retailer owned")
        self.assertEqual(classify_brand("Mystery Pantry Item", False), "Brand unclear")

    def test_attributes_can_overlap(self):
        self.assertEqual(attributes("Organic frozen vegan meal"), ["Organic", "Explicit diet or nutrition claim", "Convenience format"])


if __name__ == "__main__":
    unittest.main()
