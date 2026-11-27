from django import template
from pathlib import Path
from django import template
from django.conf import settings
from django.template.defaultfilters import slugify
from django.templatetags.static import static
register = template.Library()

CITY_ICONS = {
    "jakarta": "fa-city",
    "bandung": "fa-mountain-sun",
    "yogyakarta": "fa-landmark",
    "semarang": "fa-church",
    "surabaya": "fa-ship",
}


@register.filter
def city_icon(city):
    """Ikon Font Awesome untuk kota (ilustrasi, bukan data dataset)."""
    return CITY_ICONS.get(str(city).strip().lower(), "fa-location-dot")

_EXT = ("jpg", "jpeg", "png", "webp")


def _cari(folder, nama):
    for ext in _EXT:
        if (Path(settings.BASE_DIR) / "static" / folder / f"{nama}.{ext}").exists():
            return static(f"{folder}/{nama}.{ext}")
    return ""


@register.simple_tag
def foto_kota(city):
    return _cari("images/kota", slugify(str(city)))


@register.simple_tag
def foto_hero():
    return _cari("images", "hero")