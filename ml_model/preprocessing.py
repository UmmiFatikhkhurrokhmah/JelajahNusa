"""Pembacaan dan preprocessing dataset package_tourism.csv dengan Pandas."""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

PLACE_COLUMNS = [
    "Place_Tourism1",
    "Place_Tourism2",
    "Place_Tourism3",
    "Place_Tourism4",
    "Place_Tourism5",
]
EXPECTED_COLUMNS = ["Package", "City", *PLACE_COLUMNS]

# Nilai teks yang dianggap "kosong / tidak valid".
INVALID_VALUES = {"", "-", "--", "nan", "none", "null", "n/a", "na", "?"}


class DatasetError(Exception):
    """Dataset tidak ditemukan atau strukturnya tidak sesuai."""


def clean_text(value) -> str:
    """Rapikan satu nilai teks: hapus spasi berlebih dan nilai tidak valid."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return ""
    text = re.sub(r"\s+", " ", str(value)).strip()
    return "" if text.lower() in INVALID_VALUES else text


def build_text_feature(package_id: int, city: str, places: list[str]) -> str:
    """Gabungkan paket + kota + destinasi menjadi satu fitur teks untuk TF-IDF."""
    raw = f"paket{package_id} {city} {' '.join(places)}"
    raw = re.sub(r"[^0-9a-zA-Z\s]", " ", raw.lower())
    return re.sub(r"\s+", " ", raw).strip()


def load_dataset(path: str | Path) -> pd.DataFrame:
    """Baca CSV lalu kembalikan DataFrame bersih.

    Kolom hasil: Package, City, Place_Tourism1..5, Places (list), Jumlah_Destinasi, Fitur_Teks.
    """
    path = Path(path)
    if not path.exists():
        raise DatasetError(f"File dataset tidak ditemukan: {path}")

    try:
        df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
    except Exception as exc:  # file rusak / bukan CSV
        raise DatasetError(f"Dataset tidak dapat dibaca: {exc}") from exc

    df.columns = [str(c).strip() for c in df.columns]
    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing:
        raise DatasetError(
            "Kolom dataset tidak sesuai. Kolom yang hilang: " + ", ".join(missing)
        )

    df = df[EXPECTED_COLUMNS].copy()
    for col in EXPECTED_COLUMNS:
        df[col] = df[col].map(clean_text)

    # Paket & kota wajib valid.
    df["Package"] = pd.to_numeric(df["Package"], errors="coerce")
    df = df[df["Package"].notna() & (df["City"] != "")].copy()
    df["Package"] = df["Package"].astype(int)

    # Hapus duplikat nomor paket, lalu urutkan.
    df = df.drop_duplicates(subset="Package", keep="first")
    df = df.sort_values("Package").reset_index(drop=True)

    df["Places"] = df[PLACE_COLUMNS].apply(lambda r: [p for p in r if p], axis=1)
    df = df[df["Places"].map(len) > 0].reset_index(drop=True)
    df["Jumlah_Destinasi"] = df["Places"].map(len)
    df["Fitur_Teks"] = [
        build_text_feature(pkg, city, places)
        for pkg, city, places in zip(df["Package"], df["City"], df["Places"])
    ]

    if df.empty:
        raise DatasetError("Dataset tidak berisi baris yang valid setelah preprocessing.")
    return df
