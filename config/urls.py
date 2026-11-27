from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "JelajahNusa Admin"
admin.site.site_title = "JelajahNusa Admin"
admin.site.index_title = "Panel Administrator"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("chatbot/", include("chatbot.urls")),
    path("", include("rekomendasi.urls")),
]
