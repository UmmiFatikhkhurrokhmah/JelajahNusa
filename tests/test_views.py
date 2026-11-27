import tempfile
from pathlib import Path

from django.test import TestCase, override_settings
from django.urls import reverse

from chatbot.models import ChatMessage
from ml_model.recommender import clear_cache
from rekomendasi.models import SearchHistory

from .helpers import write_fixture_csv

_TMP = tempfile.TemporaryDirectory()
FIXTURE = write_fixture_csv(Path(_TMP.name) / "package_tourism.csv")


def tearDownModule():
    _TMP.cleanup()


@override_settings(DATASET_PATH=FIXTURE)
class ViewTests(TestCase):
    def setUp(self):
        clear_cache()

    def test_dashboard_open_without_login(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Jelajahi Keindahan Indonesia Bersama JelajahNusa")
        self.assertEqual(r.context["stats"]["total_paket"], 10)
        self.assertEqual(r.context["stats"]["total_kota"], 3)
        self.assertNotContains(r, "login", status_code=200)

    def test_admin_requires_login(self):
        r = self.client.get("/admin/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/admin/login/", r["Location"])

    def test_all_public_pages_open(self):
        for name in ["dashboard", "wisata", "rekomendasi", "semua_paket", "riwayat", "asisten", "tentang"]:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_search_and_city_filter(self):
        r = self.client.get(reverse("wisata"), {"q": "curug"})
        self.assertEqual({p["id"] for p in r.context["page_obj"]}, {4, 5})
        r = self.client.get(reverse("wisata"), {"kota": "Kota Uji C"})
        self.assertEqual(r.context["total"], 3)
        r = self.client.get(reverse("wisata"), {"q": "zzzz"})
        self.assertContains(r, "Tidak ada paket yang cocok")

    def test_pagination(self):
        r = self.client.get(reverse("wisata"))
        self.assertEqual(len(r.context["page_obj"]), 9)
        r2 = self.client.get(reverse("wisata"), {"page": 2})
        self.assertEqual(len(r2.context["page_obj"]), 1)

    def test_detail_and_404(self):
        r = self.client.get(reverse("detail_paket", args=[4]))
        self.assertContains(r, "Gunung Uji Satu")
        self.assertContains(r, "Cari paket serupa")
        self.assertEqual(self.client.get(reverse("detail_paket", args=[999])).status_code, 404)

    def test_recommendation_flow_and_history(self):
        r = self.client.get(reverse("rekomendasi"), {"paket": 1, "n": 3})
        self.assertEqual(r.status_code, 200)
        results = r.context["results"]
        self.assertEqual(len(results), 3)
        self.assertNotIn(1, [x["id"] for x in results])
        self.assertEqual(results[0]["id"], 2)
        self.assertContains(r, "%")
        self.assertEqual(SearchHistory.objects.filter(jenis="rekomendasi", package_id=1).count(), 1)
        # riwayat tampil, lalu dihapus
        self.assertContains(self.client.get(reverse("riwayat")), "Paket 1")
        self.client.post(reverse("riwayat_hapus"))
        self.assertEqual(SearchHistory.objects.count(), 0)

    def test_invalid_package_shows_error(self):
        r = self.client.get(reverse("rekomendasi"), {"paket": 999})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "tidak ditemukan")

    def test_search_is_recorded_per_session(self):
        self.client.get(reverse("wisata"), {"q": "pantai"})
        self.assertEqual(SearchHistory.objects.filter(query="pantai").count(), 1)
        other = self.client_class()
        self.assertNotContains(other.get(reverse("riwayat")), "pantai")

    def test_missing_dataset_shows_guidance_not_crash(self):
        with override_settings(DATASET_PATH=Path(_TMP.name) / "tidak_ada.csv"):
            clear_cache()
            r = self.client.get("/")
            self.assertEqual(r.status_code, 503)
            self.assertContains(r, "Dataset belum siap", status_code=503)


@override_settings(DATASET_PATH=FIXTURE, CHATBOT_PROVIDER="", CHATBOT_API_KEY="")
class ChatbotTests(TestCase):
    def setUp(self):
        clear_cache()

    def ask(self, text):
        r = self.client.post(reverse("chatbot_kirim"), data={"message": text}, content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def test_fallback_mode_is_labelled_honestly(self):
        d = self.ask("Apa itu TF-IDF?")
        self.assertEqual(d["mode"], "dasar")
        self.assertIn("TF-IDF", d["reply"])

    def test_explains_methods(self):
        self.assertIn("Cosine", self.ask("jelaskan cosine similarity")["reply"])
        self.assertIn("Content-Based", self.ask("apa itu content based filtering")["reply"])

    def test_dataset_stats_and_cities(self):
        self.assertIn("10 paket", self.ask("berapa jumlah paket?")["reply"])
        self.assertIn("Kota Uji B", self.ask("kota apa saja?")["reply"])

    def test_city_and_similar_queries_use_dataset(self):
        d = self.ask("paket di Kota Uji C")
        self.assertIn("Paket 7", d["reply"])
        self.assertTrue(d["links"])
        d = self.ask("paket mirip paket 4")
        self.assertIn("Paket 5", d["reply"])
        self.assertIn("%", d["reply"])

    def test_does_not_invent_prices(self):
        self.assertIn("tidak tersedia", self.ask("berapa harga paket 1?")["reply"])

    def test_unknown_package(self):
        self.assertIn("tidak ada di dataset", self.ask("paket 999")["reply"])

    def test_history_and_clear(self):
        self.ask("halo")
        h = self.client.get(reverse("chatbot_riwayat")).json()
        self.assertEqual(h["mode"], "dasar")
        self.assertEqual([m["role"] for m in h["messages"]], ["user", "assistant"])
        self.client.post(reverse("chatbot_hapus"))
        self.assertEqual(ChatMessage.objects.count(), 0)

    def test_validation(self):
        r = self.client.post(reverse("chatbot_kirim"), data={"message": "  "}, content_type="application/json")
        self.assertEqual(r.status_code, 400)
        r = self.client.post(reverse("chatbot_kirim"), data={"message": "x" * 501}, content_type="application/json")
        self.assertEqual(r.status_code, 400)
        r = self.client.post(reverse("chatbot_kirim"), data="bukan json", content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.client.get(reverse("chatbot_kirim")).status_code, 405)

    def test_works_without_dataset(self):
        with override_settings(DATASET_PATH=Path(_TMP.name) / "tidak_ada.csv"):
            clear_cache()
            self.assertIn("TF-IDF", self.ask("apa itu tf-idf")["reply"])
            self.assertIn("belum tersedia", self.ask("paket di bandung")["reply"])

    def test_api_key_never_exposed_to_frontend(self):
        with override_settings(CHATBOT_PROVIDER="anthropic", CHATBOT_API_KEY="sk-rahasia-123"):
            page = self.client.get("/").content.decode()
            hist = self.client.get(reverse("chatbot_riwayat")).content.decode()
            self.assertNotIn("sk-rahasia-123", page + hist)
