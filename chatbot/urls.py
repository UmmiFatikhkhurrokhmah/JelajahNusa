from django.urls import path

from . import views

urlpatterns = [
    path("kirim/", views.kirim, name="chatbot_kirim"),
    path("riwayat/", views.riwayat_chat, name="chatbot_riwayat"),
    path("hapus/", views.hapus_chat, name="chatbot_hapus"),
]
