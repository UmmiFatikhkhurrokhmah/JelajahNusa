from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("wisata/", views.wisata, name="wisata"),
    path("rekomendasi/", views.rekomendasi, name="rekomendasi"),
    path("paket/", views.semua_paket, name="semua_paket"),
    path("paket/<int:package_id>/", views.detail_paket, name="detail_paket"),
    path("riwayat/", views.riwayat, name="riwayat"),
    path("riwayat/hapus/", views.riwayat_hapus, name="riwayat_hapus"),
    path("asisten/", views.asisten, name="asisten"),
    path("tentang/", views.tentang, name="tentang"),
]
