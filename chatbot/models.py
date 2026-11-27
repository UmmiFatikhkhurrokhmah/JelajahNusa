from django.db import models


class ChatMessage(models.Model):
    """Riwayat percakapan chatbot per sesi browser (tanpa akun pengunjung)."""

    ROLE_CHOICES = [("user", "Pengunjung"), ("assistant", "Asisten")]

    session_key = models.CharField(max_length=64, db_index=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    mode = models.CharField(max_length=20, blank=True, help_text="ai / dasar (hanya untuk balasan asisten)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name = "Pesan chatbot"
        verbose_name_plural = "Pesan chatbot"

    def __str__(self):
        return f"[{self.role}] {self.content[:50]}"
