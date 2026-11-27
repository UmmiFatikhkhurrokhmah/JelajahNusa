import tempfile
import unittest
from pathlib import Path

import numpy as np
from django.conf import settings

from ml_model.preprocessing import EXPECTED_COLUMNS, DatasetError, clean_text, load_dataset
from ml_model.recommender import PackageRecommender, clear_cache, get_recommender

from .helpers import write_fixture_csv


class PreprocessingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = write_fixture_csv(Path(cls.tmp.name) / "package_tourism.csv")
        cls.df = load_dataset(cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_clean_text(self):
        self.assertEqual(clean_text("  Taman   Uji  "), "Taman Uji")
        for bad in (None, float("nan"), "", "-", "NaN", "  none "):
            self.assertEqual(clean_text(bad), "")

    def test_invalid_rows_are_dropped_and_duplicates_removed(self):
        self.assertEqual(list(self.df["Package"]), list(range(1, 11)))

    def test_missing_values_are_handled(self):
        self.assertEqual(self.df.loc[self.df["Package"] == 1, "Jumlah_Destinasi"].iloc[0], 3)
        self.assertEqual(self.df.loc[self.df["Package"] == 4, "Jumlah_Destinasi"].iloc[0], 5)

    def test_extra_spaces_removed(self):
        places = self.df.loc[self.df["Package"] == 5, "Places"].iloc[0]
        self.assertIn("Taman Uji Dua", places)

    def test_text_feature_combines_package_city_and_places(self):
        text = self.df.loc[self.df["Package"] == 1, "Fitur_Teks"].iloc[0]
        self.assertEqual(text, "paket1 kota uji a pantai uji satu pantai uji dua pantai uji tiga")

    def test_missing_file_and_bad_columns(self):
        with self.assertRaises(DatasetError):
            load_dataset(Path(self.tmp.name) / "tidak_ada.csv")
        bad = Path(self.tmp.name) / "bad.csv"
        bad.write_text("Package,City\n1,A\n", encoding="utf-8")
        with self.assertRaises(DatasetError):
            load_dataset(bad)


class RecommenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        path = write_fixture_csv(Path(cls.tmp.name) / "package_tourism.csv")
        cls.rec = PackageRecommender(load_dataset(path))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_selected_package_never_recommended(self):
        for pkg in self.rec.df["Package"]:
            ids = [r["id"] for r in self.rec.recommend(int(pkg), 20)]
            self.assertNotIn(int(pkg), ids)
            self.assertEqual(len(ids), len(self.rec.df) - 1)

    def test_sorted_descending_and_ranked(self):
        res = self.rec.recommend(1, 5)
        scores = [r["similarity"] for r in res]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual([r["rank"] for r in res], [1, 2, 3, 4, 5])

    def test_most_similar_is_expected(self):
        self.assertEqual(self.rec.recommend(1, 1)[0]["id"], 2)   # sama-sama pantai, kota sama
        self.assertEqual(self.rec.recommend(4, 1)[0]["id"], 5)   # gunung + curug, kota sama

    def test_similarity_matches_independent_cosine(self):
        dense = self.rec.tfidf.toarray()
        norm = dense / np.linalg.norm(dense, axis=1, keepdims=True)
        src = 0  # paket 1
        manual = norm @ norm[src]
        for r in self.rec.recommend(1, 9):
            idx = list(self.rec.df["Package"]).index(r["id"])
            self.assertAlmostEqual(r["similarity"], float(manual[idx]), places=9)
            self.assertAlmostEqual(r["persen"], round(float(manual[idx]) * 100, 1), places=6)
            self.assertTrue(0.0 <= r["similarity"] <= 1.0 + 1e-9)

    def test_unknown_package(self):
        with self.assertRaises(KeyError):
            self.rec.recommend(999)

    def test_stats_from_data(self):
        s = self.rec.stats()
        self.assertEqual((s["total_paket"], s["total_kota"]), (10, 3))
        unique_places = {p for places in self.rec.df["Places"] for p in places}
        self.assertEqual(s["total_destinasi"], len(unique_places))

    def test_search_and_city_filter(self):
        self.assertEqual({p["id"] for p in self.rec.search("curug")}, {4, 5})
        self.assertEqual({p["id"] for p in self.rec.search("", "Kota Uji C")}, {7, 8, 9})
        self.assertEqual([p["id"] for p in self.rec.search("paket 6")], [6])
        self.assertEqual(self.rec.search("tidak-ada-kata-ini"), [])

    def test_cache_reloads_when_file_changes(self):
        clear_cache()
        path = Path(self.tmp.name) / "package_tourism.csv"
        a = get_recommender(path)
        self.assertIs(a, get_recommender(path))


@unittest.skipUnless(Path(settings.DATASET_PATH).exists(), "dataset/package_tourism.csv asli belum diletakkan")
class RealDatasetTests(unittest.TestCase):
    def test_real_dataset_structure_and_recommendations(self):
        import pandas as pd

        raw = pd.read_csv(settings.DATASET_PATH)
        self.assertEqual(list(raw.columns), EXPECTED_COLUMNS)
        rec = get_recommender(settings.DATASET_PATH)
        self.assertGreater(len(rec.df), 0)
        for pkg in rec.df["Package"]:
            ids = [r["id"] for r in rec.recommend(int(pkg), 5)]
            self.assertNotIn(int(pkg), ids)
