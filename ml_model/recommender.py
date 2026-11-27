"""Content-Based Filtering: TF-IDF + Cosine Similarity untuk paket wisata."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .preprocessing import PLACE_COLUMNS, DatasetError, load_dataset


class PackageRecommender:
    """Membangun matriks TF-IDF dari dataset dan menghitung kemiripan antar paket."""

    def __init__(self, df: pd.DataFrame):
        self.df = df.reset_index(drop=True)
        self._index_by_package = {int(p): i for i, p in enumerate(self.df["Package"])}
        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            token_pattern=r"(?u)\b[a-z0-9]{2,}\b",
            sublinear_tf=True,
        )
        self.tfidf = self.vectorizer.fit_transform(self.df["Fitur_Teks"])
        self.terms = np.array(self.vectorizer.get_feature_names_out())

    # ---------- data paket ----------
    def has_package(self, package_id: int) -> bool:
        return int(package_id) in self._index_by_package

    def _row_to_dict(self, idx: int) -> dict:
        row = self.df.iloc[idx]
        return {
            "id": int(row["Package"]),
            "label": f"Paket {int(row['Package'])}",
            "kota": row["City"],
            "tempat": list(row["Places"]),
            "jumlah_destinasi": int(row["Jumlah_Destinasi"]),
        }

    def get_package(self, package_id: int) -> dict | None:
        idx = self._index_by_package.get(int(package_id))
        return None if idx is None else self._row_to_dict(idx)

    def all_packages(self) -> list[dict]:
        return [self._row_to_dict(i) for i in range(len(self.df))]

    def cities(self) -> list[str]:
        return sorted(self.df["City"].unique())

    def stats(self) -> dict:
        places = {p for plist in self.df["Places"] for p in plist}
        per_city = self.df.groupby("City").size().sort_values(ascending=False)
        return {
            "total_paket": int(len(self.df)),
            "total_kota": int(self.df["City"].nunique()),
            "total_destinasi": int(len(places)),
            "per_kota": [(city, int(n)) for city, n in per_city.items()],
            "metode": "Content-Based Filtering",
        }

    def search(self, query: str = "", city: str = "") -> list[dict]:
        """Cari berdasarkan nama/nomor paket, kota, atau nama destinasi."""
        mask = pd.Series(True, index=self.df.index)
        if city:
            mask &= self.df["City"].str.lower() == city.strip().lower()
        q = (query or "").strip().lower()
        if q:
            haystack = (
                "paket " + self.df["Package"].astype(str) + " "
                + self.df["City"] + " " + self.df[PLACE_COLUMNS].agg(" ".join, axis=1)
            ).str.lower()
            for token in q.split():
                mask &= haystack.str.contains(token, regex=False)
        return [self._row_to_dict(i) for i in self.df.index[mask]]

    # ---------- rekomendasi ----------
    def similarity_scores(self, package_id: int) -> np.ndarray:
        """Cosine similarity paket terpilih terhadap semua paket (urutan sama dengan df)."""
        idx = self._index_by_package[int(package_id)]
        return cosine_similarity(self.tfidf[idx], self.tfidf).ravel()

    def shared_terms(self, a_idx: int, b_idx: int, limit: int = 5) -> list[str]:
        """Kata yang muncul di kedua paket, diurutkan dari kontribusi bobot terbesar."""
        prod = self.tfidf[a_idx].multiply(self.tfidf[b_idx]).toarray().ravel()
        order = np.argsort(-prod)
        words = [self.terms[i] for i in order if prod[i] > 0]
        return [w for w in words if not w.startswith("paket")][:limit]

    def recommend(self, package_id: int, top_n: int = 5) -> list[dict]:
        package_id = int(package_id)
        if not self.has_package(package_id):
            raise KeyError(f"Paket {package_id} tidak ada di dataset.")
        src = self._index_by_package[package_id]
        scores = self.similarity_scores(package_id)
        scores[src] = -1.0  # paket yang dipilih tidak boleh direkomendasikan

        # Urut skor menurun; jika sama, nomor paket kecil lebih dulu (deterministik).
        order = sorted(
            (i for i in range(len(scores)) if i != src),
            key=lambda i: (-scores[i], int(self.df.iloc[i]["Package"])),
        )[: max(1, int(top_n))]

        results = []
        for rank, i in enumerate(order, start=1):
            item = self._row_to_dict(i)
            item.update(
                rank=rank,
                similarity=float(scores[i]),
                persen=round(float(scores[i]) * 100, 1),
                istilah_sama=self.shared_terms(src, i),
            )
            results.append(item)
        return results


# ---------- cache sederhana (dibaca ulang jika file berubah) ----------
_cache: dict[str, tuple[float, PackageRecommender]] = {}


def get_recommender(path: str | Path) -> PackageRecommender:
    path = Path(path)
    if not path.exists():
        raise DatasetError(f"File dataset tidak ditemukan: {path}")
    key = str(path.resolve())
    mtime = path.stat().st_mtime
    cached = _cache.get(key)
    if cached and cached[0] == mtime:
        return cached[1]
    rec = PackageRecommender(load_dataset(path))
    _cache[key] = (mtime, rec)
    return rec


def clear_cache() -> None:
    _cache.clear()
