"""Logika chatbot JelajahNusa.

Dua mode:
- "ai"    : memakai API eksternal (Anthropic / kompatibel OpenAI) jika dikonfigurasi di .env.
            Jawaban dibatasi pada data dataset yang kita sisipkan sebagai konteks.
- "dasar" : mesin aturan (rule-based) yang membaca dataset secara langsung. Ini bukan AI generatif.
"""
from __future__ import annotations

import logging
import re

import requests
from django.conf import settings
from django.urls import reverse

from ml_model.preprocessing import DatasetError
from ml_model.recommender import get_recommender

logger = logging.getLogger(__name__)

STOPWORDS = {
    "apa", "ada", "yang", "di", "ke", "dari", "dan", "atau", "untuk", "dengan", "saya", "aku", "mau",
    "ingin", "cari", "carikan", "tolong", "dong", "ya", "paket", "wisata", "tempat", "kota", "destinasi",
    "berikan", "tampilkan", "lihat", "info", "informasi", "tentang", "mengenai", "itu", "ini", "bisa",
    "apakah", "ada", "yg", "pada", "dalam", "list", "daftar", "semua", "rekomendasi", "mirip", "serupa",
}
MAX_MESSAGE_LEN = 500
HOURLY_LIMIT = 40


def ai_enabled() -> bool:
    return bool(settings.CHATBOT_PROVIDER in {"anthropic", "openai"} and settings.CHATBOT_API_KEY)


def _rec():
    return get_recommender(settings.DATASET_PATH)


def _pkg_link(pkg: dict) -> dict:
    return {"label": f"{pkg['label']} · {pkg['kota']}", "url": reverse("detail_paket", args=[pkg["id"]])}


def _fmt_pkg(pkg: dict) -> str:
    return f"**{pkg['label']}** ({pkg['kota']}): " + ", ".join(pkg["tempat"])


# ---------------------------------------------------------------- penjelasan statis
EXPLAIN_CBF = (
    "**Content-Based Filtering** merekomendasikan item berdasarkan kemiripan isi/karakteristiknya. "
    "Di JelajahNusa, setiap paket wisata diwakili oleh teks gabungan: nomor paket, kota, dan lima destinasi. "
    "Paket yang teksnya paling mirip dengan paket pilihanmu akan muncul sebagai rekomendasi. "
    "Sistem tidak memakai rating atau data pengguna lain."
)
EXPLAIN_TFIDF = (
    "**TF-IDF** (Term Frequency – Inverse Document Frequency) mengubah teks menjadi angka. "
    "Kata yang sering muncul di satu paket tetapi jarang di paket lain (misalnya nama destinasi khas) diberi bobot tinggi, "
    "sedangkan kata yang ada di hampir semua paket diberi bobot rendah. Hasilnya adalah vektor angka untuk tiap paket."
)
EXPLAIN_COSINE = (
    "**Cosine Similarity** mengukur kemiripan dua vektor TF-IDF lewat sudut di antaranya. "
    "Nilainya 0 sampai 1 (ditampilkan sebagai persen): makin mendekati 100% berarti makin mirip. "
    "Paket diurutkan dari nilai tertinggi, dan paket yang sedang dipilih tidak ikut direkomendasikan."
)
HOW_TO_USE = (
    "Cara memakai JelajahNusa (tanpa login):\n"
    "1. **Jelajahi Wisata**: cari paket berdasarkan nomor, kota, atau nama destinasi, lalu filter per kota.\n"
    "2. **Rekomendasi Paket**: pilih satu paket, atur jumlah rekomendasi, lalu lihat paket paling mirip beserta persentasenya.\n"
    "3. **Semua Paket**: tabel seluruh paket di dataset.\n"
    "4. **Riwayat Pencarian**: daftar pencarian di sesi browser kamu; bisa dihapus kapan saja.\n"
    "5. **Tentang Sistem**: penjelasan metode dan alur algoritma."
)
NOT_IN_DATASET = (
    "Dataset yang dipakai hanya berisi nomor paket, kota, dan lima destinasi per paket. "
    "Informasi seperti harga, rating, fasilitas, atau durasi perjalanan tidak tersedia di dataset, "
    "jadi saya tidak bisa menjawabnya."
)


# ---------------------------------------------------------------- mesin aturan (mode dasar)
def _detect(text: str, rec) -> dict:
    """Ekstrak entitas dari pesan: nomor paket, kota, kata kunci."""
    low = text.lower()
    m = re.search(r"paket\s*(?:no\.?|nomor|ke)?\s*#?\s*(\d{1,4})", low) or re.search(r"\b(\d{1,4})\b", low)
    pkg_id = int(m.group(1)) if m else None
    city = next((c for c in rec.cities() if c.lower() in low), "")
    tokens = [t for t in re.findall(r"[a-z0-9]{3,}", low) if t not in STOPWORDS and not t.isdigit()]
    return {"low": low, "pkg_id": pkg_id, "city": city, "tokens": tokens}


def retrieve_context(text: str, last_pkg: int | None = None) -> dict:
    """Ambil data dataset yang relevan untuk pesan. Dipakai mode dasar & AI."""
    rec = _rec()
    ent = _detect(text, rec)
    ctx = {"stats": rec.stats(), "entities": ent, "packages": [], "recs": [], "source": None}
    low = ent["low"]

    wants_similar = bool(re.search(r"mirip|serupa|rekomendasi|rekomendasikan|similar|saran", low))
    explain = bool(re.search(r"kenapa|mengapa|alasan|jelaskan hasil|penjelasan hasil", low))
    pkg_id = ent["pkg_id"]
    if pkg_id is None and (wants_similar or explain) and last_pkg:
        pkg_id = last_pkg

    if pkg_id is not None and rec.has_package(pkg_id):
        pkg = rec.get_package(pkg_id)
        ctx["source"] = pkg
        ctx["packages"] = [pkg]
        if wants_similar or explain:
            ctx["recs"] = rec.recommend(pkg_id, 3)
    elif ent["city"]:
        ctx["packages"] = rec.search("", ent["city"])
    elif ent["tokens"]:
        ctx["packages"] = rec.search(" ".join(ent["tokens"]), "")
        if not ctx["packages"]:  # coba satu kata kunci pertama yang cocok
            for tok in ent["tokens"]:
                found = rec.search(tok, "")
                if found:
                    ctx["packages"] = found
                    break
    return ctx


def rule_based_answer(text: str, last_pkg: int | None = None) -> dict:
    low = text.lower().strip()
    links: list[dict] = []
    new_last = last_pkg

    def done(reply):
        return {"reply": reply, "links": links[:6], "last_package": new_last}

    if re.search(r"\b(halo|hai|hi|hello|selamat (pagi|siang|sore|malam))\b", low):
        return done(
            "Halo! Saya JelajahNusa Assistant (mode dasar, berbasis aturan dan dataset). "
            "Tanyakan cara memakai website, metode rekomendasi, paket di suatu kota, atau paket yang mirip dengan paket tertentu."
        )
    if re.search(r"harga|biaya|tarif|rating|fasilitas|durasi|jam buka|tiket|hotel|penginapan", low):
        return done(NOT_IN_DATASET)
    if re.search(r"content[- ]?based|\bcbf\b", low):
        return done(EXPLAIN_CBF)
    if re.search(r"tf[- ]?idf", low):
        return done(EXPLAIN_TFIDF)

    # Pertanyaan yang tidak membutuhkan dataset dijawab lebih dulu.
    if re.search(r"cosine|kosinus", low):
        return done(EXPLAIN_COSINE)
    if re.search(r"cara|bagaimana|gimana", low) and re.search(r"pakai|gunakan|menggunakan|website|aplikasi|fitur|menu", low):
        return done(HOW_TO_USE)
    if "riwayat" in low:
        return done("Riwayat pencarian tersimpan di sesi browser kamu tanpa akun. Buka menu **Riwayat Pencarian**; tombol hapus tersedia di sana.")
    if re.search(r"\badmin\b", low):
        return done("Halaman admin (/admin/) khusus administrator dan memakai login bawaan Django. Pengunjung tidak perlu login.")

    rec = _rec()
    ctx = retrieve_context(text, last_pkg)
    ent = ctx["entities"]

    if re.search(r"daftar kota|kota apa|kota mana|kota saja", low):
        names = ", ".join(f"{c} ({n} paket)" for c, n in ctx["stats"]["per_kota"])
        return done(f"Dataset mencakup {ctx['stats']['total_kota']} kota: {names}.")
    if re.search(r"berapa|jumlah|total", low) and re.search(r"paket|kota|destinasi|data", low) and not ent["city"]:
        s = ctx["stats"]
        return done(
            f"Dataset berisi **{s['total_paket']} paket**, **{s['total_kota']} kota**, dan **{s['total_destinasi']} destinasi unik**."
        )

    if ctx["source"] and ctx["recs"]:
        src = ctx["source"]
        new_last = src["id"]
        lines = [f"Paket paling mirip dengan {_fmt_pkg(src)}:"]
        for r in ctx["recs"]:
            alasan = f" (kata yang sama: {', '.join(r['istilah_sama'])})" if r["istilah_sama"] else ""
            lines.append(f"{r['rank']}. **{r['label']}** ({r['kota']}) – kemiripan {r['persen']}%{alasan}")
            links.append(_pkg_link(r))
        lines.append("Nilai berasal dari perhitungan TF-IDF + Cosine Similarity pada dataset.")
        if re.search(r"kenapa|mengapa|alasan", low):
            lines.append("Paket muncul lebih tinggi bila kota dan nama destinasinya banyak yang sama dengan paket pilihan.")
        return done("\n".join(lines))
    if ctx["source"]:
        new_last = ctx["source"]["id"]
        links.append(_pkg_link(ctx["source"]))
        return done(_fmt_pkg(ctx["source"]) + f"\nIngin paket yang mirip? Tanyakan \"paket mirip paket {ctx['source']['id']}\".")
    if ent["pkg_id"] is not None and not rec.has_package(ent["pkg_id"]) and "paket" in low:
        return done(f"Paket {ent['pkg_id']} tidak ada di dataset. Nomor paket yang tersedia: {rec.all_packages()[0]['id']}–{rec.all_packages()[-1]['id']}.")
    if ctx["packages"]:
        pk = ctx["packages"]
        shown = pk[:5]
        links.extend(_pkg_link(p) for p in shown)
        head = f"Ditemukan {len(pk)} paket" + (f" di {ent['city']}" if ent["city"] else "") + ":"
        body = "\n".join(f"- {_fmt_pkg(p)}" for p in shown)
        tail = f"\n…dan {len(pk) - len(shown)} paket lainnya. Gunakan menu Jelajahi Wisata untuk daftar lengkap." if len(pk) > len(shown) else ""
        return done(f"{head}\n{body}{tail}")

    return done(
        "Maaf, saya belum menemukan data yang cocok. Coba sebut nama kota (mis. Bandung), nomor paket "
        "(mis. \"paket mirip paket 5\"), nama destinasi, atau tanya cara kerja TF-IDF dan Cosine Similarity."
    )


# ---------------------------------------------------------------- AI eksternal (opsional)
def _system_prompt(ctx: dict) -> str:
    s = ctx["stats"]
    lines = [
        "Kamu adalah JelajahNusa AI Assistant untuk website rekomendasi paket wisata Indonesia.",
        "Jawab dalam bahasa Indonesia, ringkas, ramah, maksimal sekitar 150 kata.",
        "ATURAN: gunakan hanya data pada bagian DATA di bawah. Dataset hanya berisi nomor paket, kota, dan 5 destinasi per paket. "
        "JANGAN mengarang harga, rating, fasilitas, durasi, jam buka, atau info destinasi lain. "
        "Jika data tidak ada, katakan tidak tersedia di dataset.",
        "Metode: Content-Based Filtering dengan TF-IDF dan Cosine Similarity (hasil dihitung oleh sistem, bukan olehmu).",
        f"DATA: {s['total_paket']} paket, {s['total_kota']} kota ({', '.join(c for c, _ in s['per_kota'])}), {s['total_destinasi']} destinasi unik.",
    ]
    if ctx["packages"]:
        lines.append("Paket relevan:")
        lines += [f"- {p['label']} | {p['kota']} | {', '.join(p['tempat'])}" for p in ctx["packages"][:8]]
    if ctx["recs"]:
        lines.append("Hasil rekomendasi hasil perhitungan sistem (nilai kemiripan):")
        lines += [f"- {r['label']} ({r['kota']}): {r['persen']}% ; kata sama: {', '.join(r['istilah_sama'])}" for r in ctx["recs"]]
    return "\n".join(lines)


def _call_external(history: list[dict], system: str) -> str:
    provider = settings.CHATBOT_PROVIDER
    if provider == "anthropic":
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": settings.CHATBOT_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": settings.CHATBOT_MODEL or "claude-haiku-5-5",
                "max_tokens": 600,
                "system": system,
                "messages": history,
            },
            timeout=25,
        )
        resp.raise_for_status()
        parts = resp.json().get("content", [])
        return "".join(p.get("text", "") for p in parts if p.get("type") == "text").strip()
    # provider "openai" (kompatibel OpenAI)
    base = settings.CHATBOT_BASE_URL.rstrip("/")
    resp = requests.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {settings.CHATBOT_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": settings.CHATBOT_MODEL or "gpt-4o-mini",
            "max_tokens": 600,
            "messages": [{"role": "system", "content": system}, *history],
        },
        timeout=25,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def answer(text: str, history: list[dict], last_pkg: int | None = None) -> dict:
    """Kembalikan {reply, mode, links, last_package}. `history` = pesan sebelumnya (role/content)."""
    text = text.strip()[:MAX_MESSAGE_LEN]
    try:
        base = rule_based_answer(text, last_pkg)
    except DatasetError:
        return {
            "reply": "Dataset belum tersedia di server ini, sehingga saya belum bisa menjawab soal paket. "
            "Penjelasan metode tetap bisa: tanyakan tentang TF-IDF atau Cosine Similarity.",
            "mode": "dasar",
            "links": [],
            "last_package": last_pkg,
        }

    if ai_enabled():
        try:
            ctx = retrieve_context(text, last_pkg)
            msgs = [m for m in history[-6:] if m["role"] in {"user", "assistant"}] + [{"role": "user", "content": text}]
            while msgs and msgs[0]["role"] != "user":  # API mensyaratkan mulai dari user
                msgs.pop(0)
            reply = _call_external(msgs, _system_prompt(ctx))
            if reply:
                base["reply"] = reply
                base["mode"] = "ai"
                return base
        except Exception as exc:  # jaringan / kunci salah / kuota
            logger.warning("Chatbot AI eksternal gagal, memakai mode dasar: %s", exc)
            base["reply"] += "\n\n(AI eksternal tidak dapat dihubungi, jawaban ini dari mode dasar.)"
    base["mode"] = "dasar"
    return base
