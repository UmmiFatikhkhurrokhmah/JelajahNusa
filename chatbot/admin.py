from django.contrib import admin

from .models import ChatMessage


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("created_at", "role", "mode", "short_content", "session_key")
    list_filter = ("role", "mode", "created_at")
    search_fields = ("content", "session_key")
    readonly_fields = ("created_at",)

    @admin.display(description="Isi pesan")
    def short_content(self, obj):
        return obj.content[:80]
