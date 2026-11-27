/* JelajahNusa – navigasi sidebar & chatbot */
(function () {
  "use strict";

  // ---------- sidebar (mobile) ----------
  document.querySelectorAll("[data-nav-toggle]").forEach(function (b) {
    b.addEventListener("click", function () { document.body.classList.toggle("nav-open"); });
  });
  document.querySelectorAll("[data-nav-close]").forEach(function (b) {
    b.addEventListener("click", function () { document.body.classList.remove("nav-open"); });
  });

  // ---------- chatbot ----------
  var root = document.getElementById("jn-chat");
  if (!root) return;

  var csrf = (document.querySelector('meta[name="csrf-token"]') || {}).content || "";
  var panel = document.getElementById("chatPanel");
  var toggle = document.getElementById("chatToggle");
  var body = document.getElementById("chatBody");
  var typing = document.getElementById("chatTyping");
  var form = document.getElementById("chatForm");
  var input = document.getElementById("chatInput");
  var send = document.getElementById("chatSend");
  var modeLabel = document.getElementById("chatMode");
  var historyPromise = null;
  var busy = false;

  function escapeHtml(s) {
    return s.replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function format(text) {
    return escapeHtml(text).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/\n/g, "<br>");
  }
  function setMode(mode) {
    modeLabel.textContent = mode === "ai" ? "Mode AI eksternal" : "Mode dasar (aturan + dataset)";
  }
  function scrollDown() { body.scrollTop = body.scrollHeight; }

  function addMessage(role, text, links) {
    var div = document.createElement("div");
    div.className = "msg " + role;
    div.innerHTML = format(text);
    if (links && links.length) {
      var wrap = document.createElement("div");
      wrap.className = "msg-links";
      links.forEach(function (l) {
        var a = document.createElement("a");
        a.href = l.url;
        a.textContent = l.label;
        wrap.appendChild(a);
      });
      div.appendChild(wrap);
    }
    body.insertBefore(div, typing);
    scrollDown();
  }

  function greet() {
    addMessage("assistant", "Halo! Saya JelajahNusa AI Assistant. Tanyakan cara memakai website, penjelasan metode rekomendasi, paket di suatu kota, atau paket yang mirip dengan paket tertentu.");
  }

  function loadHistory() {
    if (historyPromise) return historyPromise;
    historyPromise = fetch(root.dataset.urlRiwayat, { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        setMode(d.mode);
        if (!d.messages.length) greet();
        d.messages.forEach(function (m) { addMessage(m.role, m.content); });
      })
      .catch(function () { setMode("dasar"); greet(); });
    return historyPromise;
  }

  function openChat() {
    panel.classList.add("open");
    toggle.setAttribute("aria-expanded", "true");
    toggle.innerHTML = '<i class="fa-solid fa-xmark"></i>';
    loadHistory().then(function () { input.focus(); });
  }
  function closeChat() {
    panel.classList.remove("open");
    toggle.setAttribute("aria-expanded", "false");
    toggle.innerHTML = '<i class="fa-solid fa-comments"></i>';
  }

  function sendMessage(text) {
    text = (text || "").trim();
    if (!text || busy) return;
    busy = true;
    send.disabled = true;
    addMessage("user", text);
    input.value = "";
    typing.classList.add("on");
    scrollDown();

    fetch(root.dataset.urlKirim, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      body: JSON.stringify({ message: text })
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
      .then(function (res) {
        if (!res.ok) throw new Error(res.data.error || "Terjadi kesalahan.");
        setMode(res.data.mode);
        addMessage("assistant", res.data.reply, res.data.links);
      })
      .catch(function (err) {
        addMessage("assistant", "Maaf, pesan tidak terkirim: " + err.message);
      })
      .finally(function () {
        typing.classList.remove("on");
        busy = false;
        send.disabled = false;
        input.focus();
      });
  }

  toggle.addEventListener("click", function () {
    panel.classList.contains("open") ? closeChat() : openChat();
  });
  document.getElementById("chatClose").addEventListener("click", closeChat);
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeChat(); });

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    sendMessage(input.value);
  });

  document.getElementById("chatClear").addEventListener("click", function () {
    if (!confirm("Hapus seluruh percakapan chatbot?")) return;
    fetch(root.dataset.urlHapus, {
      method: "POST", credentials: "same-origin", headers: { "X-CSRFToken": csrf }
    }).then(function () {
      body.querySelectorAll(".msg").forEach(function (n) { n.remove(); });
      greet();
    });
  });

  // Tombol contoh pertanyaan (di widget maupun halaman Asisten AI)
  document.querySelectorAll("[data-chat-prompt]").forEach(function (b) {
    b.addEventListener("click", function () {
      var prompt = b.getAttribute("data-chat-prompt");
      var ready = panel.classList.contains("open") ? Promise.resolve() : (openChat(), loadHistory());
      ready.then(function () { sendMessage(prompt); });
    });
  });
  document.querySelectorAll("[data-chat-open]").forEach(function (b) {
    b.addEventListener("click", openChat);
  });
})();
