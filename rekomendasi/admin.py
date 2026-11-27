from django.contrib import admin

from .models import SearchHistory


@admin.register(SearchHistory)
class SearchHistoryAdmin(admin.ModelAdmin):
    list_display = ("created_at", "jenis", "query", "kota", "package_id", "session_key")
    list_filter = ("jenis", "kota", "created_at")
    search_fields = ("query", "kota", "session_key")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at",)
