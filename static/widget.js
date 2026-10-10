(function() {
    // Determine Domain from script src
    const scripts = document.getElementsByTagName('script');
    let domainName = '';
    let hostUrl = 'https://ai-agent-zeta-gules.vercel.app';
    for (let i = 0; i < scripts.length; i++) {
        if (scripts[i].src.includes('widget.js')) {
            const url = new URL(scripts[i].src);
            domainName = url.searchParams.get('id') || 'demo';
            hostUrl = url.origin;
        }
    }

    // Generate Session ID
    let sessionId = localStorage.getItem('ai_widget_session');
    if (!sessionId) {
        sessionId = 'web_' + Math.random().toString(36).substr(2, 9);
        localStorage.setItem('ai_widget_session', sessionId);
    }

    // Inject Styles
    const style = document.createElement('style');
    style.innerHTML = `
        #ai-widget-btn {
            position: fixed; bottom: 20px; right: 20px;
            width: 60px; height: 60px; border-radius: 50%;
            background: #2563eb; color: white; border: none;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15); cursor: pointer;
            z-index: 999999; display: flex; align-items: center; justify-content: center;
            transition: transform 0.2s;
        }
        #ai-widget-btn:hover { transform: scale(1.05); }
        #ai-widget-panel {
            position: fixed; bottom: 90px; right: 20px;
            width: 350px; height: 500px; background: white;
            border-radius: 12px; box-shadow: 0 5px 20px rgba(0,0,0,0.15);
            z-index: 999999; display: flex; flex-direction: column;
            overflow: hidden; opacity: 0; pointer-events: none;
            transition: opacity 0.3s, transform 0.3s; transform: translateY(20px);
            font-family: sans-serif;
        }
        #ai-widget-panel.open {
            opacity: 1; pointer-events: all; transform: translateY(0);
        }
        #ai-widget-header {
            background: #2563eb; color: white; padding: 15px;
            font-weight: bold; font-size: 16px;
        }
        #ai-widget-messages {
            flex: 1; overflow-y: auto; padding: 15px;
            background: #f8fafc; display: flex; flex-direction: column; gap: 10px;
        }
        .ai-msg, .user-msg {
            max-width: 80%; padding: 10px 14px; border-radius: 16px; font-size: 14px; line-height: 1.4;
        }
        .ai-msg { background: white; color: #1e293b; align-self: flex-start; border: 1px solid #e2e8f0; border-bottom-left-radius: 4px; }
        .user-msg { background: #2563eb; color: white; align-self: flex-end; border-bottom-right-radius: 4px; }
        #ai-widget-input-area {
            display: flex; padding: 10px; background: white; border-top: 1px solid #e2e8f0;
        }
        #ai-widget-input {
            flex: 1; border: 1px solid #cbd5e1; border-radius: 20px;
            padding: 8px 15px; font-size: 14px; outline: none;
        }
        #ai-widget-send {
            background: #2563eb; color: white; border: none; border-radius: 50%;
            width: 36px; height: 36px; margin-left: 8px; cursor: pointer;
            display: flex; align-items: center; justify-content: center;
        }
        .typing { display: flex; gap: 4px; align-items: center; height: 20px; padding: 0 10px; }
        .typing span { width: 6px; height: 6px; background: #94a3b8; border-radius: 50%; animation: bounce 1.4s infinite ease-in-out both; }
        .typing span:nth-child(1) { animation-delay: -0.32s; }
        .typing span:nth-child(2) { animation-delay: -0.16s; }
        @keyframes bounce { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1); } }
    `;
    document.head.appendChild(style);

    // Inject HTML
    const container = document.createElement('div');
    container.innerHTML = `
        <button id="ai-widget-btn">
            <svg width="28" height="28" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2v10z"></path></svg>
        </button>
        <div id="ai-widget-panel">
            <div id="ai-widget-header">Trợ lý ảo AI</div>
            <div id="ai-widget-messages">
                <div class="ai-msg">Xin chào! Tôi có thể giúp gì cho bạn hôm nay?</div>
            </div>
            <div id="ai-widget-input-area">
                <input type="text" id="ai-widget-input" placeholder="Nhập tin nhắn..." autocomplete="off">
                <button id="ai-widget-send">
                    <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"></path></svg>
                </button>
            </div>
        </div>
    `;
    document.body.appendChild(container);

    // Logic
    const btn = document.getElementById('ai-widget-btn');
    const panel = document.getElementById('ai-widget-panel');
    const msgs = document.getElementById('ai-widget-messages');
    const input = document.getElementById('ai-widget-input');
    const send = document.getElementById('ai-widget-send');

    let isOpen = false;
    btn.onclick = () => {
        isOpen = !isOpen;
        if (isOpen) {
            panel.classList.add('open');
            btn.innerHTML = `<svg width="28" height="28" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M6 18L18 6M6 6l12 12"></path></svg>`;
            input.focus();
        } else {
            panel.classList.remove('open');
            btn.innerHTML = `<svg width="28" height="28" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2v10z"></path></svg>`;
        }
    };

    const scrollToBottom = () => { msgs.scrollTop = msgs.scrollHeight; };

    const sendMessage = async () => {
        const text = input.value.trim();
        if (!text) return;
        
        // Add user msg
        msgs.innerHTML += `<div class="user-msg">${text.replace(/</g, "&lt;")}</div>`;
        input.value = '';
        scrollToBottom();

        // Add typing indicator
        const typingId = 'typing_' + Date.now();
        msgs.innerHTML += `<div class="ai-msg" id="${typingId}"><div class="typing"><span></span><span></span><span></span></div></div>`;
        scrollToBottom();

        try {
            const res = await fetch(`${hostUrl}/api/widget/${domainName}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sessionId, message: text })
            });
            const data = await res.json();
            
            document.getElementById(typingId).remove();
            msgs.innerHTML += `<div class="ai-msg">${data.answer.replace(/\n/g, "<br>")}</div>`;
            scrollToBottom();
        } catch (e) {
            document.getElementById(typingId).remove();
            msgs.innerHTML += `<div class="ai-msg" style="color:red">Lỗi kết nối máy chủ!</div>`;
            scrollToBottom();
        }
    };

    send.onclick = sendMessage;
    input.onkeypress = (e) => { if (e.key === 'Enter') sendMessage(); };
})();
