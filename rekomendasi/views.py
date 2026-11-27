from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from chatbot.services import ai_enabled
from ml_model.preprocessing import DatasetError
from ml_model.recommender import get_recommender

from .models import SearchHistory


def get_rec():
    return get_recommender(settings.DATASET_PATH)


def needs_dataset(view):
    """Tampilkan halaman panduan jika dataset belum ada / rusak (bukan error 500)."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except DatasetError as exc:
            return render(
                request,
                "dataset_missing.html",
                {"error": str(exc), "dataset_path": settings.DATASET_PATH},
                status=503,
            )

    return wrapper


def ensure_session(request) -> str:
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def record_history(request, jenis, query="", kota="", package_id=None):
    """Simpan riwayat; lewati jika sama persis dengan catatan terakhir (<60 detik)."""
    key = ensure_session(request)
    recent = SearchHistory.objects.filter(
        session_key=key,
        jenis=jenis,
        query=query[:200],
        kota=kota[:100],
        package_id=package_id,
        created_at__gte=timezone.now() - timedelta(seconds=60),
    ).exists()
    if not recent:
        SearchHistory.objects.create(
            session_key=key, jenis=jenis, query=query[:200], kota=kota[:100], package_id=package_id
        )


def _int(value, default, low=None, high=None):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    if low is not None:
        number = max(low, number)
    if high is not None:
        number = min(high, number)
    return number


@needs_dataset
def dashboard(request):
    rec = get_rec()
    stats = rec.stats()
    biggest = max((n for _, n in stats["per_kota"]), default=1)
    per_kota = [
        {"kota": c, "jumlah": n, "lebar": round(n / biggest * 100)} for c, n in stats["per_kota"]
    ]
    # Rekomendasi pilihan: paket pertama dari tiap kota (deterministik, dari dataset).
    featured, seen = [], set()
    for pkg in rec.all_packages():
        if pkg["kota"] not in seen:
            seen.add(pkg["kota"])
            featured.append(pkg)
    return render(
        request,
        "dashboard.html",
        {"stats": stats, "per_kota": per_kota, "featured": featured[:6], "page_title": "Dashboard"},
    )


@needs_dataset
def wisata(request):
    rec = get_rec()
    q = request.GET.get("q", "").strip()
    kota = request.GET.get("kota", "").strip()
    if kota and kota not in rec.cities():
        kota = ""
    results = rec.search(q, kota)
    page = Paginator(results, 9).get_page(request.GET.get("page"))
    if q:
        record_history(request, SearchHistory.JENIS_PENCARIAN, query=q, kota=kota)
    params = request.GET.copy()
    params.pop("page", None)
    return render(
        request,
        "wisata.html",
        {
            "page_obj": page,
            "total": len(results),
            "q": q,
            "kota": kota,
            "cities": rec.cities(),
            "querystring": params.urlencode(),
            "page_title": "Jelajahi Wisata",
        },
    )


@needs_dataset
def semua_paket(request):
    rec = get_rec()
    kota = request.GET.get("kota", "").strip()
    if kota and kota not in rec.cities():
        kota = ""
    results = rec.search("", kota)
    page = Paginator(results, 20).get_page(request.GET.get("page"))
    for item in page.object_list:  # tepat 5 kolom destinasi agar tabel rata
        item["slots"] = (item["tempat"] + [""] * 5)[:5]
    params = request.GET.copy()
    params.pop("page", None)
    return render(
        request,
        "semua_paket.html",
        {
            "page_obj": page,
            "total": len(results),
            "kota": kota,
            "cities": rec.cities(),
            "querystring": params.urlencode(),
            "page_title": "Semua Paket",
        },
    )


@needs_dataset
def rekomendasi(request):
    rec = get_rec()
    packages = rec.all_packages()
    grouped = {}
    for pkg in packages:
        grouped.setdefault(pkg["kota"], []).append(pkg)

    top_n = _int(request.GET.get("n"), settings.DEFAULT_TOP_N, 1, settings.MAX_TOP_N)
    selected_id = _int(request.GET.get("paket"), None)
    selected, results = None, []

    if selected_id is not None:
        selected = rec.get_package(selected_id)
        if selected is None:
            messages.error(request, f"Paket {selected_id} tidak ditemukan di dataset.")
        else:
            results = rec.recommend(selected_id, top_n)
            record_history(
                request,
                SearchHistory.JENIS_REKOMENDASI,
                query=f"Paket {selected_id} ({selected['kota']})",
                kota=selected["kota"],
                package_id=selected_id,
            )
    return render(
        request,
        "rekomendasi.html",
        {
            "grouped": sorted(grouped.items()),
            "selected_id": selected_id,
            "selected": selected,
            "results": results,
            "top_n": top_n,
            "top_n_choices": range(1, settings.MAX_TOP_N + 1),
            "page_title": "Rekomendasi Paket",
        },
    )


@needs_dataset
def detail_paket(request, package_id):
    rec = get_rec()
    pkg = rec.get_package(package_id)
    if pkg is None:
        raise Http404("Paket tidak ditemukan")
    slots = [
        {"nomor": i + 1, "nama": pkg["tempat"][i] if i < len(pkg["tempat"]) else ""}
        for i in range(5)
    ]
    return render(
        request,
        "detail_paket.html",
        {"pkg": pkg, "slots": slots, "page_title": pkg["label"]},
    )


def riwayat(request):
    key = request.session.session_key
    items = SearchHistory.objects.filter(session_key=key) if key else SearchHistory.objects.none()
    return render(request, "riwayat.html", {"items": items[:100], "page_title": "Riwayat Pencarian"})


@require_POST
def riwayat_hapus(request):
    key = request.session.session_key
    if key:
        deleted, _ = SearchHistory.objects.filter(session_key=key).delete()
        messages.success(request, "Riwayat pencarian dihapus.")
    return redirect("riwayat")


def asisten(request):
    return render(
        request,
        "asisten.html",
        {"page_title": "Asisten AI", "ai_aktif": ai_enabled(), "provider": settings.CHATBOT_PROVIDER},
    )


@needs_dataset
def tentang(request):
    rec = get_rec()
    return render(request, "tentang.html", {"stats": rec.stats(), "page_title": "Tentang Sistem"})
