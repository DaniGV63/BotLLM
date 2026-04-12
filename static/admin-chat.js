/**
 * admin-chat.js — Chat handoff para fisioterapeuta (v1.3.0)
 * Gestiona WebSocket, lista de derivaciones activas y panel de chat.
 */

let chatWs = null;
let chatReconnectDelay = 1000;
let chatMaxDelay = 30000;
let activeChatConvId = null;
let derivationsMap = {}; // convId -> {patient_name, wa_phone, ...}
let chatReconnectTimer = null;

// ---------------------------------------------------------------------------
// Init — se llama desde admin.js cuando se carga el tab de chat o al login
// ---------------------------------------------------------------------------

function initChat() {
    if (chatWs && chatWs.readyState === WebSocket.OPEN) return;
    connectChatWs();
    refreshDerivations();
}

function teardownChat() {
    if (chatReconnectTimer) clearTimeout(chatReconnectTimer);
    if (chatWs) { chatWs.close(); chatWs = null; }
}

// ---------------------------------------------------------------------------
// WebSocket
// ---------------------------------------------------------------------------

function connectChatWs() {
    const token = sessionStorage.getItem('admin_token');
    if (!token) return;

    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const wsUrl = `${proto}://${location.host}/admin/chat/ws?token=${encodeURIComponent(token)}`;

    chatWs = new WebSocket(wsUrl);

    chatWs.onopen = () => {
        chatReconnectDelay = 1000;
        console.debug('[chat] WS conectado');
    };

    chatWs.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            handleWsMessage(msg);
        } catch (e) {
            console.error('[chat] parse error', e);
        }
    };

    chatWs.onclose = () => {
        console.debug('[chat] WS cerrado, reconectando en', chatReconnectDelay, 'ms');
        chatReconnectTimer = setTimeout(() => {
            chatReconnectDelay = Math.min(chatReconnectDelay * 2, chatMaxDelay);
            connectChatWs();
        }, chatReconnectDelay);
    };

    chatWs.onerror = () => chatWs.close();
}

function handleWsMessage(msg) {
    switch (msg.type) {
        case 'derivation_new':
            onDerivationNew(msg);
            break;
        case 'patient_message':
            onPatientMessage(msg);
            break;
        case 'derivation_ended':
            onDerivationEnded(msg);
            break;
        case 'conversation_updated':
            // Refresca la tab conversaciones si está activa
            if (document.getElementById('tab-conversaciones') &&
                !document.getElementById('tab-conversaciones').classList.contains('hidden')) {
                if (typeof loadConversations === 'function') loadConversations(1);
            }
            break;
        case 'calendar_event_changed':
            // Refresca el calendario si está activo
            if (typeof calendarInstance !== 'undefined' && calendarInstance) {
                calendarInstance.refetchEvents();
            }
            break;
        case 'error':
            console.warn('[chat] WS error:', msg.detail);
            break;
    }
}

function onDerivationNew(msg) {
    derivationsMap[msg.conversation_id] = {
        patient_name: msg.patient_name,
        wa_phone: msg.phone,
        motivo: msg.motivo,
    };
    renderDerivationsList();
    updateChatBadge();
    playNotificationSound();
}

function onPatientMessage(msg) {
    if (msg.conversation_id === activeChatConvId) {
        appendChatBubble('user', msg.content, msg.timestamp);
    } else {
        // Resaltar en la lista
        const el = document.getElementById(`deriv-item-${msg.conversation_id}`);
        if (el) el.classList.add('bg-teal-50');
        updateChatBadge();
    }
}

function onDerivationEnded(msg) {
    delete derivationsMap[msg.conversation_id];
    renderDerivationsList();
    updateChatBadge();
    if (msg.conversation_id === activeChatConvId) {
        activeChatConvId = null;
        document.getElementById('chat-panel').classList.add('hidden');
        document.getElementById('chat-empty').classList.remove('hidden');
    }
}

// ---------------------------------------------------------------------------
// Derivations list
// ---------------------------------------------------------------------------

async function refreshDerivations() {
    const token = sessionStorage.getItem('admin_token');
    if (!token) return;
    try {
        const res = await fetch('/admin/chat/active', {
            headers: { Authorization: `Bearer ${token}` }
        });
        if (!res.ok) return;
        const list = await res.json();
        derivationsMap = {};
        list.forEach(d => {
            derivationsMap[d.conversation_id] = {
                patient_name: d.patient_name,
                wa_phone: d.wa_phone,
                ultimo_mensaje_at: d.ultimo_mensaje_at,
            };
        });
        renderDerivationsList();
        updateChatBadge();
    } catch (e) {
        console.error('[chat] refreshDerivations error', e);
    }
}

function renderDerivationsList() {
    const container = document.getElementById('derivations-list');
    if (!container) return;
    const entries = Object.entries(derivationsMap);
    if (entries.length === 0) {
        container.innerHTML = '<p class="text-center text-gray-400 text-xs p-6">Sin derivaciones activas</p>';
        return;
    }
    container.innerHTML = entries.map(([convId, d]) => {
        const name = d.patient_name || 'Desconocido';
        const phone = d.wa_phone || '';
        const active = convId === activeChatConvId ? 'bg-teal-50 border-l-2 border-teal-500' : 'hover:bg-gray-50';
        return `
            <div id="deriv-item-${convId}" class="p-3 cursor-pointer ${active} transition-colors" onclick="openChat('${convId}')">
                <div class="font-medium text-gray-900 text-sm truncate">${escapeHtml(name)}</div>
                <div class="text-gray-400 text-xs mt-0.5">${escapeHtml(formatPhone(phone))}</div>
            </div>
        `;
    }).join('');
}

function updateChatBadge() {
    const badge = document.getElementById('chat-badge');
    if (!badge) return;
    const count = Object.keys(derivationsMap).length;
    if (count > 0) {
        badge.textContent = count;
        badge.classList.remove('hidden');
    } else {
        badge.classList.add('hidden');
    }
}

// ---------------------------------------------------------------------------
// Chat panel
// ---------------------------------------------------------------------------

async function openChat(convId) {
    activeChatConvId = convId;
    const d = derivationsMap[convId] || {};
    document.getElementById('chat-patient-name').textContent = d.patient_name || 'Desconocido';
    document.getElementById('chat-patient-phone').textContent = formatPhone(d.wa_phone) || '';
    document.getElementById('chat-empty').classList.add('hidden');
    document.getElementById('chat-panel').classList.remove('hidden');
    document.getElementById('chat-messages').innerHTML = '';
    renderDerivationsList();

    const token = sessionStorage.getItem('admin_token');
    try {
        const res = await fetch(`/admin/chat/messages/${convId}`, {
            headers: { Authorization: `Bearer ${token}` }
        });
        if (!res.ok) return;
        const messages = await res.json();
        messages.forEach(m => appendChatBubble(m.role, m.content, m.created_at, m.sender_name));
        scrollChatToBottom();
    } catch (e) {
        console.error('[chat] load messages error', e);
    }
}

async function sendChatMessage() {
    const input = document.getElementById('chat-input');
    const content = (input.value || '').trim();
    if (!content || !activeChatConvId) return;

    input.value = '';

    // Enviar via WS si disponible, sino REST
    if (chatWs && chatWs.readyState === WebSocket.OPEN) {
        chatWs.send(JSON.stringify({
            type: 'therapist_send',
            conversation_id: activeChatConvId,
            content,
        }));
        appendChatBubble('therapist', content, new Date().toISOString());
    } else {
        const token = sessionStorage.getItem('admin_token');
        try {
            await fetch('/admin/chat/send', {
                method: 'POST',
                headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify({ conversation_id: activeChatConvId, content }),
            });
            appendChatBubble('therapist', content, new Date().toISOString());
        } catch (e) {
            console.error('[chat] send error', e);
        }
    }
    scrollChatToBottom();
}

async function endDerivation() {
    if (!activeChatConvId) return;
    const token = sessionStorage.getItem('admin_token');
    try {
        await fetch('/admin/chat/end', {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ conversation_id: activeChatConvId }),
        });
        delete derivationsMap[activeChatConvId];
        activeChatConvId = null;
        document.getElementById('chat-panel').classList.add('hidden');
        document.getElementById('chat-empty').classList.remove('hidden');
        renderDerivationsList();
        updateChatBadge();
    } catch (e) {
        console.error('[chat] end derivation error', e);
    }
}

function appendChatBubble(role, content, timestamp, senderName) {
    const container = document.getElementById('chat-messages');
    if (!container) return;

    const isTherapist = role === 'therapist';
    const isUser = role === 'user';
    const align = isTherapist ? 'justify-end' : 'justify-start';
    const bubbleClass = isTherapist
        ? 'bg-green-600 text-white rounded-2xl rounded-br-sm'
        : isUser
            ? 'bg-gray-100 text-gray-900 rounded-2xl rounded-bl-sm'
            : 'bg-teal-50 text-teal-800 rounded-2xl border border-teal-200 italic';

    const timeStr = timestamp ? new Date(timestamp).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' }) : '';
    const sender = senderName ? `<div class="text-xs text-gray-400 mb-0.5">${escapeHtml(senderName)}</div>` : '';

    const div = document.createElement('div');
    div.className = `flex ${align}`;
    div.innerHTML = `
        <div class="max-w-xs lg:max-w-md">
            ${!isTherapist ? sender : ''}
            <div class="px-3 py-2 text-sm ${bubbleClass}">${escapeHtml(content)}</div>
            <div class="text-xs text-gray-400 mt-0.5 ${isTherapist ? 'text-right' : 'text-left'}">${timeStr}</div>
        </div>
    `;
    container.appendChild(div);
}

function scrollChatToBottom() {
    const el = document.getElementById('chat-messages');
    if (el) el.scrollTop = el.scrollHeight;
}

// ---------------------------------------------------------------------------
// Utils
// ---------------------------------------------------------------------------

function playNotificationSound() {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.frequency.value = 880;
        gain.gain.setValueAtTime(0.3, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);
        osc.start(ctx.currentTime);
        osc.stop(ctx.currentTime + 0.4);
    } catch (_) { /* audio no disponible */ }
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
