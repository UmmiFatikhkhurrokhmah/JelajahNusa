# JelajahNusa

Sistem rekomendasi paket wisata Indonesia berbasis **Content-Based Filtering** (TF-IDF + Cosine Similarity), dibangun dengan Django. Proyek UAS Sistem Cerdas.

## Masalah yang diselesaikan
Calon wisatawan sulit memilih di antara banyak paket wisata yang isinya mirip-mirip. JelajahNusa membantu dengan cara pengguna memilih satu paket, lalu sistem menampilkan paket lain yang paling mirip berdasarkan kota dan destinasi di dalamnya, lengkap dengan persentase kemiripan. Ada juga asisten chat untuk bertanya seputar paket dan cara memakai website. Pengguna tidak perlu login.

## Dataset
Sumber: *Indonesia Tourism Destination* (Kaggle, A. Prabowo), berkas `package_tourism.csv`
https://www.kaggle.com/datasets/aprabowo/indonesia-tourism-destination
Lisensi: Data files © Original Authors
Jumlah data: 100 paket, 5 kota, 300 destinasi

Kolom: `Package`, `City`, `Place_Tourism1` sampai `Place_Tourism5`. Dataset tidak memuat harga, rating, fasilitas, atau durasi, sehingga website tidak menampilkannya.


## Metode
**Content-Based Filtering.** Paket direkomendasikan berdasarkan kemiripan isinya (kota dan destinasi), bukan rating atau perilaku pengguna lain.

1. **Preprocessing** (`ml_model/preprocessing.py`, Pandas): memeriksa kolom wajib, merapikan spasi, mengubah nilai kosong atau tidak valid menjadi kosong, membuang baris tanpa nomor paket atau kota yang valid, dan membuang nomor paket ganda.
2. **Fitur teks:** paket, kota, dan destinasi digabung menjadi satu teks huruf kecil tanpa tanda baca, misalnya `paket7 kota destinasi1 destinasi2 ...`.
3. **TF-IDF** (`TfidfVectorizer`, `sublinear_tf=True`): `tfidf(t, d) = tf(t, d) x idf(t)`. Kata yang khas untuk sedikit paket berbobot besar, kata yang ada di banyak paket berbobot kecil.
4. **Cosine Similarity:** `cos(A, B) = (A . B) / (|A| x |B|)`, bernilai 0 sampai 1 dan ditampilkan sebagai persen. Hasil diurutkan dari yang tertinggi, dan paket yang sedang dipilih tidak pernah ikut direkomendasikan.

**Chatbot (JelajahNusa AI Assistant)** punya dua mode:
- *Mode dasar (default):* mesin aturan yang membaca dataset, bukan AI generatif.
- *Mode AI generatif (opsional):* server mengirim pertanyaan beserta data dataset yang relevan ke API model bahasa, dengan instruksi tidak mengarang informasi. Jika API gagal, chatbot otomatis kembali ke mode dasar dan menandainya. API key hanya ada di `.env` dan tidak pernah dikirim ke browser. Batas 40 pesan per jam per sesi.

## Hasil & evaluasi
Sistem ini tidak memakai label benar-salah, jadi evaluasinya berupa **pengujian otomatis** (`python manage.py test`): 35 uji, semuanya lulus, 1 dilewati (uji dataset asli, hanya berjalan jika `package_tourism.csv` ada).

| Preprocessing | baris tidak valid dan nomor ganda dibuang, nilai kosong ditangani, spasi dirapikan | Lulus |
| Rekomendasi | paket terpilih tidak pernah muncul, urutan menurun, paket paling mirip sesuai harapan, nilai sama dengan hitungan cosine independen | Lulus |
| Halaman web | semua halaman publik terbuka tanpa login, pencarian, filter kota, pagination, detail dan 404 | Lulus |
| Riwayat pencarian | tersimpan per sesi, bisa dihapus | Lulus |
| Chatbot | menjelaskan TF-IDF dan Cosine, tidak mengarang harga, mode ditandai jujur, API key tidak bocor ke frontend | Lulus |

## Cara menjalankan
Prasyarat: Python 3.10+. Di Windows (PowerShell, di folder yang berisi `manage.py`):

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py runserver
```

Buka http://127.0.0.1:8000/. Pastikan `dataset/package_tourism.csv` sudah ada.

Foto (`.jpg`): `static/images/hero.jpg` untuk banner, dan `static/images/kota/<nama-kota>.jpg` (jakarta, bandung, yogyakarta, semarang, surabaya) untuk kartu paket.

Pengujian: `python manage.py test`.

## Refleksi singkat
**Berhasil:** rekomendasi berjalan dari dataset asli dengan TF-IDF dan Cosine Similarity, hasilnya bisa diuji otomatis, dan website bisa dipakai. Chatbot tidak mengarang data yang tidak ada di dataset.

**Keterbatasan:** fitur hanya berupa teks kota dan nama destinasi, sehingga kemiripan dipengaruhi kata yang sama (misalnya "Pantai" atau "Museum"). Dataset tidak punya harga, rating, atau durasi, jadi rekomendasi tidak mempertimbangkan budget. Evaluasi masih berupa uji fungsional, belum ada pengukuran kualitas dengan responden. Mode AI generatif bergantung pada API key, kuota, dan koneksi internet.

**Rencana perbaikan:** menambah data atribut (harga, durasi, jenis wisata) agar fitur lebih kaya, menguji kualitas rekomendasi dengan penilaian pengguna, dan menambah foto asli tiap kota.