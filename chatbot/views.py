import json
from datetime import timedelta

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from . import services
from .models import ChatMessage


def _session_key(request) -> str:
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


@require_GET
def riwayat_chat(request):
    key = request.session.session_key
    msgs = ChatMessage.objects.filter(session_key=key).order_by("-id")[:50] if key else []
    items = [{"role": m.role, "content": m.content, "mode": m.mode} for m in reversed(list(msgs))]
    return JsonResponse(
        {
            "messages": items,
            "mode": "ai" if services.ai_enabled() else "dasar",
        }
    )


@require_POST
def kirim(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "Format permintaan tidak valid."}, status=400)
    text = str(payload.get("message", "")).strip()
    if not text:
        return JsonResponse({"error": "Pesan tidak boleh kosong."}, status=400)
    if len(text) > services.MAX_MESSAGE_LEN:
        return JsonResponse({"error": f"Pesan maksimal {services.MAX_MESSAGE_LEN} karakter."}, status=400)

    key = _session_key(request)
    since = timezone.now() - timedelta(hours=1)
    if ChatMessage.objects.filter(session_key=key, role="user", created_at__gte=since).count() >= services.HOURLY_LIMIT:
        return JsonResponse({"error": "Batas pesan per jam tercapai. Coba lagi nanti."}, status=429)

    history = [
        {"role": m.role, "content": m.content}
        for m in ChatMessage.objects.filter(session_key=key).order_by("-id")[:8][::-1]
    ]
    ChatMessage.objects.create(session_key=key, role="user", content=text)
    result = services.answer(text, history, request.session.get("chat_last_package"))
    ChatMessage.objects.create(session_key=key, role="assistant", content=result["reply"], mode=result["mode"])
    if result.get("last_package"):
        request.session["chat_last_package"] = result["last_package"]
    return JsonResponse({"reply": result["reply"], "mode": result["mode"], "links": result["links"]})


@require_POST
def hapus_chat(request):
    key = request.session.session_key
    if key:
        ChatMessage.objects.filter(session_key=key).delete()
        request.session.pop("chat_last_package", None)
    return JsonResponse({"ok": True})
