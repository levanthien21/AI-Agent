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
    ".aia-form button{border:0;background:none;color:" + color + ";font-weight:600;padding:0 16px;cursor:pointer}"
  ].join("\n");
  document.head.appendChild(css);

  var btn = document.createElement("button"); btn.className = "aia-btn"; btn.textContent = "💬";
  var box = document.createElement("div"); box.className = "aia-box";
  box.innerHTML = '<div class="aia-head">Hỗ trợ</div><div class="aia-msgs"></div>' +
    '<form class="aia-form"><input placeholder="Nhập tin nhắn..." maxlength="2000"><button>Gửi</button></form>';
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

  form.onsubmit = function (e) {
    e.preventDefault();
    var text = input.value.trim(); if (!text) return;
    input.value = ""; add(text, "me");
    var typing = add("...", "bot");
    fetch(server + "/api/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ domain: domain, session_id: sid, message: text })
    }).then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.detail); return j; }); })
      .then(function (j) { typing.textContent = j.answer; msgs.scrollTop = msgs.scrollHeight; })
      .catch(function (err) { typing.textContent = err.message || "Lỗi kết nối, vui lòng thử lại."; });
  };
})();
