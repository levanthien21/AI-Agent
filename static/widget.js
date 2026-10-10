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
    let sessionId = localStorage.getItem('omni_widget_session');
    if (!sessionId) {
        sessionId = 'web_' + Math.random().toString(36).substr(2, 9);
        localStorage.setItem('omni_widget_session', sessionId);
    }

    // Check Mobile
    const isMobile = window.innerWidth <= 768;

    // Inject Styles
    const style = document.createElement('style');
    style.innerHTML = `
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        #omni-widget-container {
            font-family: 'Inter', sans-serif;
            position: fixed;
            bottom: 24px;
            right: 24px;
            z-index: 2147483647;
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 16px;
        }

        /* Launcher Button */
        #omni-launcher {
            width: 60px;
            height: 60px;
            border-radius: 50%;
            background: linear-gradient(135deg, #2563eb, #4f46e5);
            box-shadow: 0 4px 14px rgba(37, 99, 235, 0.3);
            border: none;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }
        #omni-launcher:hover { transform: scale(1.05); }
        #omni-launcher svg { transition: transform 0.3s; }
        #omni-launcher.open svg { transform: rotate(90deg) scale(0); opacity: 0; position: absolute; }
        #omni-launcher .close-icon { transform: rotate(-90deg) scale(0); opacity: 0; position: absolute; }
        #omni-launcher.open .close-icon { transform: rotate(0) scale(1); opacity: 1; position: relative; }

        /* Welcome Bubble */
        #omni-welcome {
            background: white;
            padding: 12px 20px;
            border-radius: 20px;
            border-bottom-right-radius: 4px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            border: 1px solid #f1f5f9;
            font-size: 14px;
            color: #1e293b;
            font-weight: 500;
            position: absolute;
            right: 76px;
            bottom: 8px;
            white-space: nowrap;
            transition: opacity 0.3s, transform 0.3s;
            transform-origin: right bottom;
            cursor: pointer;
        }
        #omni-welcome.hidden { opacity: 0; transform: scale(0.8); pointer-events: none; }

        /* Main Chat Panel */
        #omni-panel {
            width: 380px;
            height: 600px;
            max-height: calc(100vh - 100px);
            background: white;
            border-radius: 24px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.15);
            display: flex;
            flex-direction: column;
            overflow: hidden;
            opacity: 0;
            pointer-events: none;
            transform: translateY(20px) scale(0.95);
            transform-origin: bottom right;
            transition: all 0.3s cubic-bezier(0.19, 1, 0.22, 1);
            position: absolute;
            bottom: 76px;
            right: 0;
        }
        #omni-panel.open { opacity: 1; pointer-events: all; transform: translateY(0) scale(1); }

        /* Mobile overrides */
        @media (max-width: 768px) {
            #omni-widget-container { bottom: 16px; right: 16px; }
            #omni-panel { 
                position: fixed; top: 0; left: 0; right: 0; bottom: 0;
                width: 100%; height: 100%; max-height: 100vh;
                border-radius: 0; bottom: 0; right: 0;
                transform: translateY(100%);
            }
            #omni-panel.open { transform: translateY(0); }
            #omni-launcher.open { display: none; }
        }

        /* Header */
        #omni-header {
            background: linear-gradient(135deg, #1e40af, #3b82f6);
            padding: 24px 20px;
            color: white;
            position: relative;
        }
        #omni-header-close {
            position: absolute; top: 16px; right: 16px;
            background: rgba(255,255,255,0.2); border: none; border-radius: 50%;
            width: 32px; height: 32px; color: white; display: none;
            align-items: center; justify-content: center; cursor: pointer;
        }
        @media (max-width: 768px) { #omni-header-close { display: flex; } }

        .omni-avatar {
            width: 48px; height: 48px; border-radius: 50%;
            background: white; display: flex; align-items: center; justify-content: center;
            margin-bottom: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1);
        }
        .omni-title { font-size: 18px; font-weight: 700; margin: 0 0 4px 0; }
        .omni-subtitle { font-size: 13px; color: #bfdbfe; display: flex; align-items: center; gap: 6px; }
        .omni-dot { width: 8px; height: 8px; background: #4ade80; border-radius: 50%; box-shadow: 0 0 0 2px rgba(74,222,128,0.2); }

        /* Messages Area */
        #omni-messages {
            flex: 1; padding: 20px; overflow-y: auto;
            background: #f8fafc; display: flex; flex-direction: column; gap: 16px;
        }
        #omni-messages::-webkit-scrollbar { width: 6px; }
        #omni-messages::-webkit-scrollbar-track { background: transparent; }
        #omni-messages::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 10px; }

        .omni-msg-wrapper { display: flex; flex-direction: column; max-width: 85%; }
        .omni-msg-wrapper.ai { align-self: flex-start; }
        .omni-msg-wrapper.user { align-self: flex-end; align-items: flex-end; }
        
        .omni-msg {
            padding: 12px 16px; font-size: 14.5px; line-height: 1.5;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }
        .omni-msg.ai { background: white; color: #334155; border: 1px solid #e2e8f0; border-radius: 16px 16px 16px 4px; }
        .omni-msg.user { background: #2563eb; color: white; border-radius: 16px 16px 4px 16px; }
        
        .omni-time { font-size: 11px; color: #94a3b8; margin-top: 4px; padding: 0 4px; }

        /* Input Area */
        #omni-input-area {
            padding: 16px; background: white; border-top: 1px solid #f1f5f9;
            display: flex; gap: 12px; align-items: flex-end;
        }
        #omni-input {
            flex: 1; border: 1px solid #e2e8f0; border-radius: 24px;
            padding: 12px 16px; font-size: 14px; outline: none;
            background: #f8fafc; transition: border-color 0.2s;
            max-height: 100px; resize: none; overflow-y: auto; font-family: 'Inter', sans-serif;
        }
        #omni-input:focus { border-color: #3b82f6; background: white; }
        #omni-send {
            width: 44px; height: 44px; border-radius: 50%;
            background: #2563eb; color: white; border: none;
            display: flex; align-items: center; justify-content: center;
            cursor: pointer; transition: background 0.2s; flex-shrink: 0;
        }
        #omni-send:hover { background: #1d4ed8; }
        #omni-send:disabled { background: #94a3b8; cursor: not-allowed; }

        /* Branding */
        .omni-branding { text-align: center; padding: 8px 0 12px; font-size: 11px; color: #cbd5e1; background: white; font-weight: 500; }
        .omni-branding a { color: #94a3b8; text-decoration: none; }
        .omni-branding a:hover { color: #64748b; }

        /* Typing Indicator */
        .omni-typing { display: flex; gap: 4px; align-items: center; padding: 4px 0; }
        .omni-typing span { width: 6px; height: 6px; background: #cbd5e1; border-radius: 50%; animation: omni-bounce 1.4s infinite ease-in-out both; }
        .omni-typing span:nth-child(1) { animation-delay: -0.32s; }
        .omni-typing span:nth-child(2) { animation-delay: -0.16s; }
        @keyframes omni-bounce { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1); } }
        
        /* Markdown basics */
        .omni-msg strong { font-weight: 700; color: #0f172a; }
    `;
    document.head.appendChild(style);

    // Parse Markdown basic
    const parseMD = (text) => {
        return text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n/g, '<br>');
    };

    const getTime = () => {
        const d = new Date();
        return d.getHours().toString().padStart(2, '0') + ':' + d.getMinutes().toString().padStart(2, '0');
    };

    // Inject HTML
    const container = document.createElement('div');
    container.id = 'omni-widget-container';
    container.innerHTML = `
        <div id="omni-welcome">
            Xin chào! Chúng tôi có thể giúp gì cho bạn? 👋
        </div>
        
        <div id="omni-panel">
            <div id="omni-header">
                <button id="omni-header-close"><svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M6 18L18 6M6 6l12 12"></path></svg></button>
                <div class="omni-avatar">
                    <svg width="28" height="28" fill="none" stroke="#2563eb" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23-.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5"></path></svg>
                </div>
                <h3 class="omni-title" id="omni-bot-name">Trợ lý ảo AI</h3>
                <div class="omni-subtitle"><div class="omni-dot"></div> Đang hoạt động</div>
            </div>
            
            <div id="omni-messages">
                <!-- Messages go here -->
            </div>
            
            <div id="omni-input-area">
                <textarea id="omni-input" rows="1" placeholder="Nhập tin nhắn..." autocomplete="off"></textarea>
                <button id="omni-send">
                    <svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"></path></svg>
                </button>
            </div>
            <div class="omni-branding">Powered by <a href="https://ai-agent-zeta-gules.vercel.app" target="_blank">OmniAI</a></div>
        </div>

        <button id="omni-launcher">
            <svg width="28" height="28" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>
            <svg class="close-icon" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><path d="M18 6L6 18M6 6l12 12"></path></svg>
        </button>
    `;
    document.body.appendChild(container);

    // DOM Elements
    const launcher = document.getElementById('omni-launcher');
    const panel = document.getElementById('omni-panel');
    const welcome = document.getElementById('omni-welcome');
    const msgs = document.getElementById('omni-messages');
    const input = document.getElementById('omni-input');
    const send = document.getElementById('omni-send');
    const closeBtn = document.getElementById('omni-header-close');

    let isOpen = false;
    let greetingLoaded = false;

    // Toggle logic
    const toggleWidget = () => {
        isOpen = !isOpen;
        if (isOpen) {
            panel.classList.add('open');
            launcher.classList.add('open');
            welcome.classList.add('hidden');
            input.focus();
            
            // Fetch greeting on first open
            if (!greetingLoaded) {
                fetchGreeting();
                greetingLoaded = true;
            }
        } else {
            panel.classList.remove('open');
            launcher.classList.remove('open');
        }
    };

    launcher.onclick = toggleWidget;
    welcome.onclick = toggleWidget;
    closeBtn.onclick = toggleWidget;

    // Auto-hide welcome after 10s
    setTimeout(() => { if (!isOpen) welcome.classList.add('hidden'); }, 10000);

    const scrollToBottom = () => { msgs.scrollTop = msgs.scrollHeight; };

    const addMessage = (text, type) => {
        const wrap = document.createElement('div');
        wrap.className = `omni-msg-wrapper ${type}`;
        wrap.innerHTML = `
            <div class="omni-msg ${type}">${parseMD(text)}</div>
            <div class="omni-time">${getTime()}</div>
        `;
        msgs.appendChild(wrap);
        scrollToBottom();
    };

    // Load Greeting
    const fetchGreeting = async () => {
        const typingId = 'typing_greet';
        msgs.innerHTML += `<div class="omni-msg-wrapper ai" id="${typingId}"><div class="omni-msg ai"><div class="omni-typing"><span></span><span></span><span></span></div></div></div>`;
        
        try {
            const res = await fetch(`${hostUrl}/api/domains/${domainName}/public`);
            const data = await res.json();
            document.getElementById('omni-bot-name').textContent = data.display_name || "Trợ lý ảo AI";
            document.getElementById(typingId).remove();
            addMessage(data.greeting || "Xin chào! Tôi có thể giúp gì cho bạn?", 'ai');
        } catch (e) {
            document.getElementById(typingId).remove();
            addMessage("Xin chào! Tôi có thể giúp gì cho bạn?", 'ai');
        }
    };

    // Send Message
    const sendMessage = async () => {
        const text = input.value.trim();
        if (!text) return;
        
        input.value = '';
        input.style.height = 'auto'; // reset height
        addMessage(text.replace(/</g, "&lt;"), 'user');

        const typingId = 'typing_' + Date.now();
        msgs.innerHTML += `<div class="omni-msg-wrapper ai" id="${typingId}"><div class="omni-msg ai"><div class="omni-typing"><span></span><span></span><span></span></div></div></div>`;
        scrollToBottom();
        
        send.disabled = true;

        try {
            const res = await fetch(`${hostUrl}/api/widget/${domainName}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sessionId, message: text })
            });
            const data = await res.json();
            
            document.getElementById(typingId).remove();
            addMessage(data.answer || "Xin lỗi, đã xảy ra lỗi.", 'ai');
        } catch (e) {
            document.getElementById(typingId).remove();
            addMessage("Lỗi kết nối máy chủ. Vui lòng thử lại.", 'ai');
        }
        
        send.disabled = false;
        if(!isMobile) input.focus();
    };

    send.onclick = sendMessage;
    
    // Auto-resize textarea
    input.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
        if (this.value.trim() === '') this.style.height = 'auto';
    });
    
    input.addEventListener('keydown', (e) => { 
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

})();
