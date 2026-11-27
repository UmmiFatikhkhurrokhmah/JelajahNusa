NAV_ITEMS = [
    {"name": "dashboard", "label": "Dashboard", "icon": "fa-gauge-high"},
    {"name": "wisata", "label": "Jelajahi Wisata", "icon": "fa-compass"},
    {"name": "rekomendasi", "label": "Rekomendasi Paket", "icon": "fa-wand-magic-sparkles"},
    {"name": "semua_paket", "label": "Semua Paket", "icon": "fa-table-list"},
    {"name": "riwayat", "label": "Riwayat Pencarian", "icon": "fa-clock-rotate-left"},
    {"name": "asisten", "label": "Asisten AI", "icon": "fa-robot"},
    {"name": "tentang", "label": "Tentang Sistem", "icon": "fa-circle-info"},
]


def site_info(request):
    match = getattr(request, "resolver_match", None)
    return {
        "nav_items": NAV_ITEMS,
        "current_url_name": match.url_name if match else "",
        "app_name": "JelajahNusa",
    }
