from django.db import models


class SearchHistory(models.Model):
    """Riwayat pencarian/rekomendasi pengunjung, terikat ke sesi browser (tanpa akun)."""

    JENIS_PENCARIAN = "pencarian"
    JENIS_REKOMENDASI = "rekomendasi"
    JENIS_CHOICES = [
        (JENIS_PENCARIAN, "Pencarian wisata"),
        (JENIS_REKOMENDASI, "Rekomendasi paket"),
    ]

    session_key = models.CharField(max_length=64, db_index=True)
    jenis = models.CharField(max_length=20, choices=JENIS_CHOICES)
    query = models.CharField(max_length=200, blank=True)
    kota = models.CharField(max_length=100, blank=True)
    package_id = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Riwayat pencarian"
        verbose_name_plural = "Riwayat pencarian"

    def __str__(self):
        if self.jenis == self.JENIS_REKOMENDASI:
            return f"Rekomendasi untuk Paket {self.package_id}"
        return f"Pencarian: {self.query or '(semua)'}"
