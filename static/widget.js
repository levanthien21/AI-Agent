(function() {
    // --- LUXA AI WIDGET PRO (Intercom & Crisp Level UI/UX) ---
    const scripts = document.getElementsByTagName('script');
    let domainName = '';
    let hostUrl = 'https://www.luxa-ai.click';
    for (let i = 0; i < scripts.length; i++) {
        if (scripts[i].src.includes('widget.js')) {
            try {
                const url = new URL(scripts[i].src);
                domainName = url.searchParams.get('id') || 'demo';
                hostUrl = url.origin;
            } catch(e) {}
        }
    }

    let sessionId = localStorage.getItem('luxa_widget_session');
    if (!sessionId) {
        sessionId = 'web_' + Math.random().toString(36).substr(2, 9);
        localStorage.setItem('luxa_widget_session', sessionId);
    }

    const isMobile = window.innerWidth <= 768;

    // --- SOUND SYNTHESIZER (Web Audio API - No external mp3 required) ---
    const playNotificationSound = () => {
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
            osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.1); // A5
            gain.gain.setValueAtTime(0.08, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.35);
        } catch(e) {}
    };

    // --- STYLES INJECTION ---
    const style = document.createElement('style');
    style.innerHTML = `
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
        
        #luxa-widget-root {
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            position: fixed;
            bottom: 24px;
            right: 24px;
            z-index: 2147483647;
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 16px;
        }

        /* Launcher with Pulse Effect */
        #luxa-launcher-wrap {
            position: relative;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .luxa-pulse {
            position: absolute;
            width: 72px;
            height: 72px;
            border-radius: 50%;
            background: rgba(99, 102, 241, 0.4);
            animation: luxa-ripple 2.5s infinite cubic-bezier(0, 0.2, 0.8, 1);
            pointer-events: none;
        }
        @keyframes luxa-ripple {
            0% { transform: scale(0.8); opacity: 0.8; }
            100% { transform: scale(1.6); opacity: 0; }
        }

        #luxa-launcher {
            width: 64px;
            height: 64px;
            border-radius: 50%;
            background: linear-gradient(135deg, #6366f1 0%, #4f46e5 50%, #3b82f6 100%);
            box-shadow: 0 8px 28px rgba(79, 70, 229, 0.45), 0 2px 8px rgba(0,0,0,0.1);
            border: 2px solid rgba(255, 255, 255, 0.2);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
            position: relative;
            z-index: 2;
        }
        #luxa-launcher:hover {
            transform: scale(1.08) rotate(3deg);
            box-shadow: 0 12px 36px rgba(79, 70, 229, 0.6);
        }
        #luxa-launcher svg { transition: all 0.3s ease; }
        #luxa-launcher.open {
            background: #1e293b;
            transform: rotate(90deg);
            box-shadow: 0 6px 20px rgba(0,0,0,0.25);
        }

        /* Welcome Teaser Bubble */
        #luxa-teaser {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(12px);
            padding: 12px 18px;
            border-radius: 18px;
            border-bottom-right-radius: 4px;
            box-shadow: 0 8px 30px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.06);
            border: 1px solid rgba(226, 232, 240, 0.8);
            font-size: 13.5px;
            color: #0f172a;
            font-weight: 600;
            position: absolute;
            right: 80px;
            bottom: 10px;
            white-space: nowrap;
            transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1);
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 8px;
            user-select: none;
        }
        #luxa-teaser.hidden {
            opacity: 0;
            transform: translateX(15px) scale(0.9);
            pointer-events: none;
        }
        #luxa-teaser .teaser-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #10b981;
            box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.25);
        }

        /* Main Window */
        #luxa-panel {
            width: 400px;
            height: 640px;
            max-height: calc(100vh - 120px);
            background: #ffffff;
            border-radius: 28px;
            box-shadow: 0 20px 60px rgba(15, 23, 42, 0.22), 0 4px 16px rgba(15, 23, 42, 0.08);
            border: 1px solid rgba(226, 232, 240, 0.9);
            display: flex;
            flex-direction: column;
            overflow: hidden;
            opacity: 0;
            pointer-events: none;
            transform: translateY(24px) scale(0.94);
            transform-origin: bottom right;
            transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1);
            position: absolute;
            bottom: 84px;
            right: 0;
            z-index: 1;
        }
        #luxa-panel.open {
            opacity: 1;
            pointer-events: all;
            transform: translateY(0) scale(1);
        }

        @media (max-width: 768px) {
            #luxa-widget-root { bottom: 16px; right: 16px; }
            #luxa-panel {
                position: fixed; top: 0; left: 0; right: 0; bottom: 0;
                width: 100%; height: 100%; max-height: 100vh;
                border-radius: 0; transform: translateY(100%);
                bottom: 0; right: 0;
            }
            #luxa-panel.open { transform: translateY(0); }
            #luxa-launcher-wrap.open { display: none; }
        }

        /* Header */
        #luxa-header {
            background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 60%, #312e81 100%);
            padding: 22px 24px;
            color: white;
            position: relative;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid rgba(255,255,255,0.08);
        }
        .luxa-header-info {
            display: flex;
            align-items: center;
            gap: 14px;
        }
        .luxa-avatar-box {
            position: relative;
            width: 46px;
            height: 46px;
            border-radius: 16px;
            background: linear-gradient(135deg, #6366f1, #a855f7);
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35);
        }
        .luxa-avatar-box svg { width: 26px; height: 26px; color: white; }
        .luxa-online-badge {
            position: absolute;
            bottom: -2px;
            right: -2px;
            width: 12px;
            height: 12px;
            background: #10b981;
            border-radius: 50%;
            border: 2px solid #0f172a;
        }
        .luxa-header-text h3 {
            font-size: 16px;
            font-weight: 700;
            margin: 0;
            letter-spacing: -0.01em;
            color: #f8fafc;
        }
        .luxa-header-text p {
            font-size: 12px;
            margin: 2px 0 0;
            color: #94a3b8;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        #luxa-close-btn {
            background: rgba(255,255,255,0.08);
            border: none;
            width: 34px;
            height: 34px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #cbd5e1;
            cursor: pointer;
            transition: all 0.2s;
        }
        #luxa-close-btn:hover {
            background: rgba(255,255,255,0.18);
            color: white;
            transform: rotate(90deg);
        }

        /* Chat Body */
        #luxa-body {
            flex: 1;
            padding: 20px;
            overflow-y: auto;
            background: #f8fafc;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }
        #luxa-body::-webkit-scrollbar { width: 5px; }
        #luxa-body::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 10px; }

        /* Message Bubbles */
        .luxa-msg-row {
            display: flex;
            flex-direction: column;
            max-width: 82%;
            animation: luxa-fade-up 0.25s ease-out;
        }
        @keyframes luxa-fade-up {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .luxa-msg-row.ai { align-self: flex-start; }
        .luxa-msg-row.user { align-self: flex-end; align-items: flex-end; }

        .luxa-bubble {
            padding: 12px 16px;
            font-size: 14px;
            line-height: 1.55;
            box-shadow: 0 2px 6px rgba(0,0,0,0.03);
            word-break: break-word;
        }
        .luxa-bubble.ai {
            background: #ffffff;
            color: #1e293b;
            border: 1px solid #e2e8f0;
            border-radius: 18px 18px 18px 4px;
        }
        .luxa-bubble.user {
            background: linear-gradient(135deg, #4f46e5 0%, #3b82f6 100%);
            color: #ffffff;
            border-radius: 18px 18px 4px 18px;
            box-shadow: 0 4px 14px rgba(79, 70, 229, 0.25);
        }
        .luxa-msg-time {
            font-size: 10.5px;
            color: #94a3b8;
            margin-top: 4px;
            padding: 0 4px;
            font-weight: 500;
        }

        /* Quick Prompt Chips */
        #luxa-chips {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            padding: 0 20px 14px;
            background: #f8fafc;
        }
        .luxa-chip {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            color: #475569;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            box-shadow: 0 1px 3px rgba(0,0,0,0.02);
            user-select: none;
        }
        .luxa-chip:hover {
            border-color: #6366f1;
            color: #4f46e5;
            background: #eef2ff;
            transform: translateY(-1px);
        }

        /* Input Area */
        #luxa-input-wrap {
            padding: 14px 18px;
            background: #ffffff;
            border-top: 1px solid #f1f5f9;
            display: flex;
            gap: 10px;
            align-items: flex-end;
        }
        #luxa-input {
            flex: 1;
            border: 1.5px solid #e2e8f0;
            border-radius: 22px;
            padding: 10px 16px;
            font-size: 14px;
            outline: none;
            background: #f8fafc;
            max-height: 90px;
            resize: none;
            overflow-y: auto;
            font-family: inherit;
            color: #0f172a;
            transition: all 0.2s;
        }
        #luxa-input:focus {
            border-color: #6366f1;
            background: #ffffff;
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.12);
        }
        #luxa-send-btn {
            width: 42px;
            height: 42px;
            border-radius: 50%;
            background: linear-gradient(135deg, #6366f1, #4f46e5);
            color: white;
            border: none;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.2s;
            flex-shrink: 0;
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
        }
        #luxa-send-btn:hover {
            transform: scale(1.06);
            background: linear-gradient(135deg, #4f46e5, #4338ca);
        }
        #luxa-send-btn:disabled {
            background: #cbd5e1;
            box-shadow: none;
            cursor: not-allowed;
            transform: none;
        }

        /* Footer Branding */
        .luxa-footer {
            text-align: center;
            padding: 6px 0 10px;
            font-size: 11px;
            color: #94a3b8;
            background: #ffffff;
            font-weight: 500;
        }
        .luxa-footer a {
            color: #6366f1;
            text-decoration: none;
            font-weight: 700;
        }

        /* Typing Dots */
        .luxa-typing-dots {
            display: flex;
            gap: 4px;
            align-items: center;
            padding: 4px 2px;
        }
        .luxa-typing-dots span {
            width: 6px;
            height: 6px;
            background: #94a3b8;
            border-radius: 50%;
            animation: luxa-dot-bounce 1.4s infinite ease-in-out both;
        }
        .luxa-typing-dots span:nth-child(1) { animation-delay: -0.32s; }
        .luxa-typing-dots span:nth-child(2) { animation-delay: -0.16s; }
        @keyframes luxa-dot-bounce {
            0%, 80%, 100% { transform: scale(0); opacity: 0.4; }
            40% { transform: scale(1); opacity: 1; }
        }
    `;
    document.head.appendChild(style);

    // Markdown Parser (bold, italic, list, line breaks)
    const renderMarkdown = (text) => {
        return text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/\n/g, '<br>');
    };

    const getClockTime = () => {
        const d = new Date();
        return d.getHours().toString().padStart(2, '0') + ':' + d.getMinutes().toString().padStart(2, '0');
    };

    // --- INJECT DOM ---
    const root = document.createElement('div');
    root.id = 'luxa-widget-root';
    root.innerHTML = `
        <div id="luxa-teaser">
            <span class="teaser-dot"></span>
            <span>Hỏi tôi bất cứ điều gì! 👋</span>
        </div>

        <div id="luxa-panel">
            <div id="luxa-header">
                <div class="luxa-header-info">
                    <div class="luxa-avatar-box">
                        <svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
                        <div class="luxa-online-badge"></div>
                    </div>
                    <div class="luxa-header-text">
                        <h3 id="luxa-bot-title">LUXA AI Assistant</h3>
                        <p><svg width="10" height="10" viewBox="0 0 24 24" fill="#10b981"><circle cx="12" cy="12" r="10"/></svg> Trực tuyến 24/7 • Phản hồi 3s</p>
                    </div>
                </div>
                <button id="luxa-close-btn" title="Đóng">
                    <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"></path></svg>
                </button>
            </div>

            <div id="luxa-body"></div>

            <div id="luxa-chips">
                <div class="luxa-chip" data-q="Tư vấn dịch vụ & báo giá">💰 Báo giá dịch vụ</div>
                <div class="luxa-chip" data-q="Các tính năng nổi bật là gì?">⚡ Tính năng nổi bật</div>
                <div class="luxa-chip" data-q="Tôi muốn gặp chuyên viên tư vấn">📞 Gặp chuyên viên</div>
            </div>

            <div id="luxa-input-wrap">
                <textarea id="luxa-input" rows="1" placeholder="Nhập câu hỏi của bạn..." autocomplete="off"></textarea>
                <button id="luxa-send-btn" title="Gửi">
                    <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"></path></svg>
                </button>
            </div>
            <div class="luxa-footer">Được vận hành bởi <a href="https://www.luxa-ai.click" target="_blank">LUXA AI</a></div>
        </div>

        <div id="luxa-launcher-wrap">
            <div class="luxa-pulse"></div>
            <button id="luxa-launcher" title="Chat với AI">
                <svg width="30" height="30" fill="none" stroke="currentColor" stroke-width="2.2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"></path></svg>
            </button>
        </div>
    `;
    document.body.appendChild(root);

    // --- ELEMENTS ---
    const launcherWrap = document.getElementById('luxa-launcher-wrap');
    const launcher = document.getElementById('luxa-launcher');
    const panel = document.getElementById('luxa-panel');
    const teaser = document.getElementById('luxa-teaser');
    const body = document.getElementById('luxa-body');
    const input = document.getElementById('luxa-input');
    const sendBtn = document.getElementById('luxa-send-btn');
    const closeBtn = document.getElementById('luxa-close-btn');
    const chips = document.querySelectorAll('.luxa-chip');

    let isOpen = false;
    let greetingLoaded = false;

    const toggleChat = () => {
        isOpen = !isOpen;
        if (isOpen) {
            panel.classList.add('open');
            launcher.classList.add('open');
            launcher.innerHTML = `<svg width="26" height="26" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"></path></svg>`;
            teaser.classList.add('hidden');
            input.focus();
            if (!greetingLoaded) {
                fetchGreeting();
                greetingLoaded = true;
            }
        } else {
            panel.classList.remove('open');
            launcher.classList.remove('open');
            launcher.innerHTML = `<svg width="30" height="30" fill="none" stroke="currentColor" stroke-width="2.2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"></path></svg>`;
        }
    };

    launcher.onclick = toggleChat;
    teaser.onclick = toggleChat;
    closeBtn.onclick = toggleChat;

    setTimeout(() => { if (!isOpen) teaser.classList.add('hidden'); }, 8000);

    const scrollToBottom = () => { body.scrollTop = body.scrollHeight; };

    const appendMessage = (text, type) => {
        const row = document.createElement('div');
        row.className = `luxa-msg-row ${type}`;
        row.innerHTML = `
            <div class="luxa-bubble ${type}">${renderMarkdown(text)}</div>
            <div class="luxa-msg-time">${getClockTime()}</div>
        `;
        body.appendChild(row);
        scrollToBottom();
        if (type === 'ai') playNotificationSound();
    };

    const fetchGreeting = async () => {
        const typingId = 'typing_greet_' + Date.now();
        body.innerHTML += `
            <div class="luxa-msg-row ai" id="${typingId}">
                <div class="luxa-bubble ai"><div class="luxa-typing-dots"><span></span><span></span><span></span></div></div>
            </div>`;
        scrollToBottom();

        try {
            const res = await fetch(`${hostUrl}/api/domains/${domainName}/public`);
            const data = await res.json();
            if (data.display_name) {
                document.getElementById('luxa-bot-title').textContent = data.display_name;
            }
            document.getElementById(typingId)?.remove();
            appendMessage(data.greeting || "Xin chào quý khách! Em là Trợ lý AI của LUXA. Em có thể hỗ trợ thông tin gì cho mình hôm nay ạ? ✨", 'ai');
        } catch (e) {
            document.getElementById(typingId)?.remove();
            appendMessage("Xin chào quý khách! Em có thể giúp gì cho mình hôm nay ạ? ✨", 'ai');
        }
    };

    const handleSend = async (customText = null) => {
        const text = customText || input.value.trim();
        if (!text) return;

        if (!customText) {
            input.value = '';
            input.style.height = 'auto';
        }

        appendMessage(text.replace(/</g, "&lt;"), 'user');

        const typingId = 'typing_' + Date.now();
        body.innerHTML += `
            <div class="luxa-msg-row ai" id="${typingId}">
                <div class="luxa-bubble ai"><div class="luxa-typing-dots"><span></span><span></span><span></span></div></div>
            </div>`;
        scrollToBottom();
        sendBtn.disabled = true;

        try {
            const res = await fetch(`${hostUrl}/api/widget/${domainName}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sessionId, message: text })
            });
            const data = await res.json();
            document.getElementById(typingId)?.remove();
            appendMessage(data.answer || "Dạ hiện tại hệ thống đang bận, anh/chị vui lòng để lại số điện thoại để nhân viên hỗ trợ ngay nhé ạ!", 'ai');
        } catch (e) {
            document.getElementById(typingId)?.remove();
            appendMessage("Dạ kết nối máy chủ gián đoạn, anh/chị vui lòng thử lại sau ít giây ạ.", 'ai');
        }

        sendBtn.disabled = false;
        if (!isMobile) input.focus();
    };

    sendBtn.onclick = () => handleSend();

    chips.forEach(chip => {
        chip.onclick = () => {
            const q = chip.getAttribute('data-q');
            handleSend(q);
        };
    });

    input.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 90) + 'px';
    });

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    });

})();
