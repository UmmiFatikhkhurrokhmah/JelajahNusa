"""Fixture DATA UJI SINTETIS — hanya untuk pengujian otomatis, BUKAN dataset aplikasi.

Aplikasi sebenarnya membaca dataset/package_tourism.csv (Kaggle). Fixture ini sengaja
memakai nama kota/destinasi fiktif agar tidak tertukar dengan data asli.
"""
import csv
from pathlib import Path

HEADER = ["Package", "City", "Place_Tourism1", "Place_Tourism2", "Place_Tourism3", "Place_Tourism4", "Place_Tourism5"]

ROWS = [
    ["1", "Kota Uji A", "Pantai Uji Satu", "Pantai Uji Dua", "Pantai Uji Tiga", "-", ""],
    ["2", "Kota Uji A", "Pantai Uji Satu", "Pantai Uji Dua", "Pantai Uji Empat", "", ""],
    ["3", "Kota Uji A", "Museum Uji Satu", "Museum Uji Dua", "Taman Uji Satu", "", ""],
    ["4", "Kota Uji B", "Gunung Uji Satu", "Gunung Uji Dua", "Curug Uji Satu", "Curug Uji Dua", "Curug Uji Tiga"],
    ["5", "Kota Uji B", "Gunung Uji Satu", "Curug Uji Satu", "Curug Uji Dua", "Kebun Uji Satu", "  Taman   Uji  Dua  "],
    ["6", "Kota Uji B", "Pasar Uji Satu", "Pasar Uji Dua", "Mal Uji Satu", "", ""],
    ["7", "Kota Uji C", "Pantai Uji Satu", "Benteng Uji Satu", "Benteng Uji Dua", "", ""],
    ["8", "Kota Uji C", "Museum Uji Satu", "Benteng Uji Satu", "Taman Uji Satu", "Taman Uji Dua", ""],
    ["9", "Kota Uji C", "Pasar Uji Satu", "Mal Uji Satu", "Mal Uji Dua", "", ""],
    ["10", "Kota Uji A", "Taman Uji Satu", "Taman Uji Dua", "Museum Uji Dua", "", ""],
    ["10", "Kota Uji A", "Duplikat Dibuang", "", "", "", ""],   # nomor paket ganda -> dibuang
    ["11", "", "Tanpa Kota", "", "", "", ""],                      # kota kosong -> dibuang
    ["abc", "Kota Uji A", "Nomor Tidak Valid", "", "", "", ""],    # nomor bukan angka -> dibuang
]


def write_fixture_csv(path: Path) -> Path:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(HEADER)
        writer.writerows(ROWS)
    return path
