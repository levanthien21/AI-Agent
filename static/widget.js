/* Nhúng: <script src="https://YOUR_SERVER/static/widget.js" data-domain="shop"></script>
   data-server (tuỳ chọn): URL server, mặc định là nơi chứa widget.js */
(function () {
  var script = document.currentScript;
  var domain = script.getAttribute("data-domain");
  var server = script.getAttribute("data-server") || new URL(script.src).origin;
  var color = script.getAttribute("data-color") || "#2563eb";
  var sid = localStorage.getItem("aiagent_sid");
  if (!sid) { sid = Math.random().toString(36).slice(2) + Date.now().toString(36); localStorage.setItem("aiagent_sid", sid); }

  var css = document.createElement("style");
  css.textContent = [
    ".aia-btn{position:fixed;bottom:20px;right:20px;width:58px;height:58px;border-radius:50%;border:0;background:" + color + ";color:#fff;font-size:26px;cursor:pointer;box-shadow:0 4px 14px rgba(0,0,0,.3);z-index:99998}",
    ".aia-box{position:fixed;bottom:90px;right:20px;width:340px;max-width:calc(100vw - 30px);height:480px;max-height:calc(100vh - 110px);background:#fff;border-radius:14px;box-shadow:0 8px 30px rgba(0,0,0,.25);display:none;flex-direction:column;overflow:hidden;font:14px system-ui,sans-serif;z-index:99999}",
    ".aia-box.open{display:flex}",
    ".aia-head{background:" + color + ";color:#fff;padding:14px;font-weight:600}",
    ".aia-msgs{flex:1;overflow-y:auto;padding:12px;background:#f5f6f8}",
    ".aia-m{max-width:80%;margin:6px 0;padding:8px 12px;border-radius:14px;white-space:pre-wrap;line-height:1.4;word-wrap:break-word}",
    ".aia-m.bot{background:#fff;color:#111;border-bottom-left-radius:4px}",
    ".aia-m.me{background:" + color + ";color:#fff;margin-left:auto;border-bottom-right-radius:4px}",
    ".aia-form{display:flex;border-top:1px solid #e5e7eb}",
    ".aia-form input{flex:1;border:0;padding:13px;font-size:14px;outline:none}",
    ".aia-form button{border:0;background:none;color:" + color + ";font-weight:600;padding:0 16px;cursor:pointer}",
    ".aia-form button.aia-mic{font-size:22px;padding:0;color:#fff;background:" + color + ";margin:6px;border-radius:50%;width:44px;height:44px;flex:none;line-height:44px}",
    ".aia-form button.aia-mic.on{background:#dc2626;animation:aia-pulse 1s infinite}",
    "@keyframes aia-pulse{0%{box-shadow:0 0 0 0 rgba(220,38,38,.6)}70%{box-shadow:0 0 0 14px rgba(220,38,38,0)}100%{box-shadow:0 0 0 0 rgba(220,38,38,0)}}"
  ].join("\n");
  document.head.appendChild(css);

  var btn = document.createElement("button"); btn.className = "aia-btn"; btn.textContent = "💬";
  var box = document.createElement("div"); box.className = "aia-box";
  box.innerHTML = '<div class="aia-head">Hỗ trợ</div><div class="aia-msgs"></div>' +
    '<form class="aia-form"><button type="button" class="aia-mic" title="Bấm để nói" aria-label="Nói để soạn tin">🎤</button><input placeholder="Nhập hoặc bấm 🎤 để nói..." maxlength="2000"><button>Gửi</button></form>';
  document.body.append(btn, box);
  var msgs = box.querySelector(".aia-msgs"), form = box.querySelector("form"), input = box.querySelector("input");

  function add(text, who) {
    var d = document.createElement("div"); d.className = "aia-m " + who; d.textContent = text;
    msgs.appendChild(d); msgs.scrollTop = msgs.scrollHeight; return d;
  }

  fetch(server + "/api/domains/" + encodeURIComponent(domain) + "/public").then(function (r) { return r.json(); })
    .then(function (i) { box.querySelector(".aia-head").textContent = i.display_name; add(i.greeting, "bot"); })
    .catch(function () { add("Xin chào! Mình có thể giúp gì cho bạn?", "bot"); });

  btn.onclick = function () { box.classList.toggle("open"); if (box.classList.contains("open")) input.focus(); };

  // ----- Giọng nói: nói để soạn tin, tự gửi, và đọc to câu trả lời -----
  var micBtn = box.querySelector(".aia-mic");
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  var voiceMode = false, rec = null, listening = false, heard = "";

  function speak(text) {
    if (!("speechSynthesis" in window) || !text) return;
    window.speechSynthesis.cancel();
    var u = new SpeechSynthesisUtterance(text);
    u.lang = "vi-VN"; u.rate = 0.95;
    window.speechSynthesis.speak(u);
  }

  if (!SR) {
    micBtn.style.display = "none"; // trình duyệt không hỗ trợ (vd. Firefox)
  } else {
    rec = new SR();
    rec.lang = "vi-VN"; rec.interimResults = true; rec.continuous = false;
    rec.onstart = function () { listening = true; micBtn.classList.add("on"); input.placeholder = "Đang nghe bạn nói..."; };
    rec.onresult = function (ev) {
      var t = "";
      for (var i = 0; i < ev.results.length; i++) t += ev.results[i][0].transcript;
      heard = t; input.value = t;
    };
    rec.onerror = function (ev) {
      if (ev.error === "not-allowed" || ev.error === "service-not-allowed") add("Bạn hãy cho phép trình duyệt dùng micro nhé.", "bot");
      else if (ev.error === "no-speech") add("Mình chưa nghe thấy gì, bạn thử nói lại nhé.", "bot");
      heard = "";
    };
    rec.onend = function () {
      listening = false; micBtn.classList.remove("on"); input.placeholder = "Nhập hoặc bấm 🎤 để nói...";
      if (heard.trim()) { voiceMode = true; form.requestSubmit ? form.requestSubmit() : form.dispatchEvent(new Event("submit", { cancelable: true })); }
      heard = "";
    };
    micBtn.onclick = function () {
      if (window.speechSynthesis) window.speechSynthesis.cancel();
      if (listening) { rec.stop(); return; }
      input.value = ""; heard = "";
      try { rec.start(); } catch (e) { /* đang chạy */ }
    };
  }

  form.onsubmit = function (e) {
    e.preventDefault();
    var text = input.value.trim(); if (!text) return;
    var spoken = voiceMode; voiceMode = false;
    input.value = ""; add(text, "me");
    var typing = add("...", "bot");
    fetch(server + "/api/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ domain: domain, session_id: sid, message: text })
    }).then(async function (r) {
      if (!r.ok) {
         var j = await r.json().catch(function(){return {};});
         throw new Error(j.detail || "L?i k?t n?i");
      }
      typing.textContent = "";
      var reader = r.body.getReader();
      var decoder = new TextDecoder("utf-8");
      return (function readStream() {
        return reader.read().then(function (result) {
          if (result.done) {
             if (spoken) speak(typing.textContent);
             return;
          }
          typing.textContent += decoder.decode(result.value, { stream: true });
          msgs.scrollTop = msgs.scrollHeight;
          return readStream();
        });
      })();
    }).catch(function (err) { typing.textContent = err.message || "L?i k?t n?i, vui l�ng th? l?i."; });
  };
})();

