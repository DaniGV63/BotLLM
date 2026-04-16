const API = window.location.origin;
let token = sessionStorage.getItem('admin_token');
let userRole = sessionStorage.getItem('admin_role');
let tenantId = sessionStorage.getItem('admin_tenant_id') || null;
let superAdminToken = sessionStorage.getItem('super_admin_token') || null;
let botActivo = false;
let convRefreshInterval = null;
let dashboardRefreshInterval = null;
let currentViewConvId = null;
let currentViewPhone = null;
let currentViewName = null;
let tenantsCache = [];

// ===== SECURITY: HTML ESCAPE =====
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, char => map[char]);
}

function formatPhone(p) {
    return p ? '+' + p.slice(0,2) + ' ' + p.slice(2,5) + ' ' + p.slice(5,8) + ' ' + p.slice(8) : p;
}

// ===== API =====
async function apiCall(method, path, body) {
    const opts = { method, headers: {} };
    if (token) opts.headers['Authorization'] = 'Bearer ' + token;
    if (body) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
    const res = await fetch(API + path, opts);
    if (res.status === 401) { logout(); throw new Error('No autorizado'); }
    if (res.status === 204) return null;
    if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail || 'Error del servidor'); }
    return res.json();
}
function showMsg(type, text) {
    const ok = document.getElementById('msg-ok'), err = document.getElementById('msg-err');
    ok.classList.add('hidden'); err.classList.add('hidden');
    const el = type === 'ok' ? ok : err;
    el.textContent = text; el.classList.remove('hidden');
    setTimeout(() => el.classList.add('hidden'), 4000);
}

// ===== AUTH =====
async function login() {
    sessionStorage.clear(); token = null; userRole = null; tenantId = null; superAdminToken = null;
    const user = document.getElementById('login-user').value.trim();
    const pass = document.getElementById('login-pass').value;
    const errEl = document.getElementById('login-error');
    errEl.classList.add('hidden');
    try {
        const data = await apiCall('POST', '/admin/login', { username: user, password: pass });
        token = data.access_token; userRole = data.role; tenantId = data.tenant_id || null;
        sessionStorage.setItem('admin_token', token);
        sessionStorage.setItem('admin_role', userRole);
        sessionStorage.setItem('admin_tenant_id', tenantId || '');
        showDashboard();
    } catch (e) { errEl.textContent = e.message; errEl.classList.remove('hidden'); }
}
function logout() {
    token = null; userRole = null; tenantId = null; superAdminToken = null;
    sessionStorage.clear(); clearInterval(convRefreshInterval); clearInterval(dashboardRefreshInterval);
    document.getElementById('login-section').classList.remove('hidden');
    document.getElementById('dashboard-section').classList.add('hidden');
}

// ===== IMPERSONACION =====
async function impersonateTenant(tid, tenantName) {
    try {
        const data = await apiCall('POST', '/admin/impersonate/' + tid);
        superAdminToken = token;
        sessionStorage.setItem('super_admin_token', superAdminToken);
        token = data.access_token; userRole = data.role; tenantId = data.tenant_id;
        sessionStorage.setItem('admin_token', token);
        sessionStorage.setItem('admin_role', userRole);
        sessionStorage.setItem('admin_tenant_id', tenantId || '');
        document.getElementById('banner-tenant-name').textContent = tenantName;
        document.getElementById('impersonation-banner').classList.remove('hidden');
        renderTabsForRole(); await loadTenant(); showTab('configuracion');
    } catch(e) { showMsg('err', e.message); }
}
function stopImpersonating() {
    token = superAdminToken; superAdminToken = null;
    userRole = 'super_admin'; tenantId = null;
    sessionStorage.setItem('admin_token', token);
    sessionStorage.setItem('admin_role', userRole);
    sessionStorage.setItem('admin_tenant_id', '');
    sessionStorage.removeItem('super_admin_token');
    document.getElementById('impersonation-banner').classList.add('hidden');
    document.getElementById('nav-nombre').textContent = '';
    document.getElementById('nav-plan-badge').classList.add('hidden');
    renderTabsForRole(); showTab('tenants'); loadTenants();
}

// ===== DASHBOARD =====
function toggleMobileSidebar() {
    const s = document.getElementById('sidebar');
    if (s.classList.contains('hidden')) {
        s.classList.remove('hidden');
        s.classList.add('flex', 'fixed', 'inset-y-0', 'left-0', 'z-50');
    } else {
        s.classList.add('hidden');
        s.classList.remove('flex', 'fixed', 'inset-y-0', 'left-0', 'z-50');
    }
}
async function showDashboard() {
    document.getElementById('login-section').classList.add('hidden');
    document.getElementById('dashboard-section').classList.remove('hidden');
    if (typeof lucide !== 'undefined') lucide.createIcons();
    if (superAdminToken) document.getElementById('impersonation-banner').classList.remove('hidden');
    renderTabsForRole();
    if (userRole === 'super_admin' && !tenantId) {
        const badge = document.getElementById('nav-role-badge');
        badge.textContent = 'Super Admin'; badge.className = 'text-xs font-medium px-2 py-0.5 rounded-full bg-purple-100 text-purple-700'; badge.classList.remove('hidden');
        await loadTenants(); showTab('tenants');
    } else {
        await loadTenant();
        const savedTab = localStorage.getItem('atendoo_active_tab');
        const validTabs = ALL_TABS.filter(t => {
            const btn = document.getElementById('tab-btn-' + t);
            return btn && !btn.classList.contains('hidden');
        });
        const initialTab = savedTab && validTabs.includes(savedTab) ? savedTab : 'configuracion';
        showTab(initialTab);
        // Conectar WS al login para recibir eventos en tiempo real desde cualquier tab
        if (typeof initChat === 'function') initChat();
    }
}
function renderTabsForRole() {
    const isSuperOnly = userRole === 'super_admin' && !tenantId;
    const hasTenant = !!tenantId;
    const isSuperWithTenant = userRole === 'super_admin' && hasTenant;
    const show = (id, v) => { const el = document.getElementById('tab-btn-' + id); if (el) el.classList.toggle('hidden', !v); };
    show('tenants', isSuperOnly); show('usuarios', isSuperOnly);
    show('configuracion', hasTenant); show('google', isSuperWithTenant);
    show('conversaciones', hasTenant); show('calendario', hasTenant); show('dashboard', hasTenant); show('chat', hasTenant);
}
const ALL_TABS = ['tenants','usuarios','configuracion','google','conversaciones','calendario','chat','dashboard'];
function showTab(name) {
    localStorage.setItem('atendoo_active_tab', name);
    ALL_TABS.forEach(t => {
        document.getElementById('tab-' + t).classList.toggle('hidden', t !== name);
        const btn = document.getElementById('tab-btn-' + t);
        if (!btn || btn.classList.contains('hidden')) return;
        btn.classList.remove('bg-white/10','text-white','text-gray-300','hover:bg-white/10','hover:text-white');
        if (t === name) btn.classList.add('bg-white/10','text-white');
        else btn.classList.add('text-gray-300','hover:bg-white/10','hover:text-white');
    });
    clearInterval(convRefreshInterval); convRefreshInterval = null;
    clearInterval(dashboardRefreshInterval); dashboardRefreshInterval = null;
    if (name === 'conversaciones') { loadConversations(1); convRefreshInterval = setInterval(() => loadConversations(1), 30000); }
    if (name === 'dashboard') { loadMetrics(); dashboardRefreshInterval = setInterval(() => loadMetrics(), 10000); if (typeof lucide !== 'undefined') lucide.createIcons(); }
    if (name === 'calendario') { if (typeof initCalendar === 'function') initCalendar(); }
    if (name === 'chat') { if (typeof initChat === 'function') initChat(); }
    if (name === 'tenants') loadTenants();
    if (name === 'usuarios') loadUsers();
    if (name === 'configuracion') loadTenant();
    // En móvil: cerrar sidebar al navegar (remover también clases de posicionamiento)
    const sidebar = document.getElementById('sidebar');
    if (sidebar && window.innerWidth < 768) {
        sidebar.classList.add('hidden');
        sidebar.classList.remove('flex', 'fixed', 'inset-y-0', 'left-0', 'z-50');
    }
}

// ===== TENANT DATA =====
async function loadTenant() {
    const t = await apiCall('GET', '/admin/tenant');
    window.currentTenant = t;
    document.getElementById('nav-nombre').textContent = t.nombre_negocio;
    const planBadge = document.getElementById('nav-plan-badge');
    const planMap = { 'PAID': { text: 'PAID', cls: 'bg-green-900/50 text-green-300' }, 'FREE_TRIAL': { text: 'Free Trial', cls: 'bg-yellow-900/50 text-yellow-300' }, 'SIN_PLAN': { text: 'Sin plan', cls: 'bg-gray-700 text-gray-400' } };
    const pi = planMap[t.plan] || planMap['SIN_PLAN'];
    planBadge.textContent = pi.text; planBadge.className = 'text-xs font-medium px-2 py-0.5 rounded-full mx-3 ' + pi.cls; planBadge.classList.remove('hidden');
    const badge = document.getElementById('nav-role-badge');
    if (userRole === 'super_admin') { badge.textContent = 'Super Admin'; badge.className = 'text-xs font-medium px-2 py-0.5 rounded-full bg-purple-100 text-purple-700'; badge.classList.remove('hidden'); }
    else { badge.classList.add('hidden'); }
    document.getElementById('f-nombre').value = t.nombre_negocio;
    document.getElementById('f-email').value = t.email_notificaciones;
    botActivo = t.bot_activo; updateBotToggle();
    document.getElementById('f-rate-limit').value = t.rate_limit_per_minute;
    document.getElementById('f-max-citas').value = t.max_citas_activas;
    document.getElementById('f-slot-duration').value = t.slot_duration_minutes || 60;
    renderWorkBlocksEditor(t.work_blocks || {});
    document.getElementById('f-calendar-id').value = t.google_calendar_id || '';
    document.getElementById('f-token-expiry').value = t.google_token_expiry
        ? new Date(t.google_token_expiry).toLocaleString('es-ES') : 'Sin configurar';
    const s = document.getElementById('google-status');
    s.textContent = t.has_google_credentials ? 'Credenciales configuradas' : 'Sin credenciales Google configuradas';
    s.className = 'text-sm p-3 rounded mb-2 ' + (t.has_google_credentials ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700');
}
async function toggleBot() {
    if (botActivo && !await showConfirmModal('Desactivar bot', 'Los mensajes llegarán pero no se responderá automáticamente.', true)) return;
    botActivo = !botActivo; updateBotToggle();
}
function updateBotToggle() {
    const btn = document.getElementById('f-bot-toggle'), dot = btn.querySelector('span');
    btn.className = 'w-12 h-6 rounded-full relative transition-colors duration-200 ' + (botActivo ? 'bg-green-500' : 'bg-gray-300');
    dot.style.left = botActivo ? '26px' : '2px';
}
async function saveDatos() {
    try {
        await apiCall('PUT', '/admin/tenant', {
            nombre_negocio: document.getElementById('f-nombre').value.trim(),
            email_notificaciones: document.getElementById('f-email').value.trim(),
            bot_activo: botActivo,
            rate_limit_per_minute: parseInt(document.getElementById('f-rate-limit').value) || 10,
            max_citas_activas: parseInt(document.getElementById('f-max-citas').value) || 5,
            slot_duration_minutes: parseInt(document.getElementById('f-slot-duration').value) || 60,
            work_blocks: collectWorkBlocks(),
        });
        await loadTenant(); showMsg('ok', 'Datos guardados correctamente');
    } catch (e) { showMsg('err', e.message); }
}
async function saveGoogle() {
    const body = { google_calendar_id: document.getElementById('f-calendar-id').value.trim() };
    const at = document.getElementById('f-access-token').value.trim();
    const rt = document.getElementById('f-refresh-token').value.trim();
    if (at) body.google_access_token = at;
    if (rt) body.google_refresh_token = rt;
    try {
        await apiCall('PUT', '/admin/tenant', body);
        document.getElementById('f-access-token').value = '';
        document.getElementById('f-refresh-token').value = '';
        await loadTenant(); showMsg('ok', 'Credenciales Google guardadas');
    } catch (e) { showMsg('err', e.message); }
}

// (loadTenants, createTenant, loadUsers, createUser, deleteUser → admin-superadmin.js)

// ===== CONVERSACIONES =====
async function loadConversations(page) {
    try {
        const data = await apiCall('GET', '/admin/conversations?page=' + page + '&page_size=15');
        const tbody = document.getElementById('conv-table');
        if (!data.conversations.length) {
            tbody.innerHTML = '<tr><td colspan="5" class="py-4 text-center text-gray-400">Sin conversaciones</td></tr>';
        } else {
            tbody.innerHTML = data.conversations.map(function(c) {
                const estadoCls = { 'ACTIVA': 'bg-green-100 text-green-700', 'DERIVADA': 'bg-orange-100 text-orange-700', 'INACTIVA': 'bg-gray-100 text-gray-500' };
                const b = estadoCls[c.estado] || 'bg-gray-100 text-gray-500';
                const escId = escapeHtml(c.id);
                const escPhone = escapeHtml(formatPhone(c.wa_phone));
                const escName = escapeHtml(c.nombre_paciente || '');
                return '<tr class="border-b hover:bg-gray-50 transition-colors duration-100 cursor-pointer"'
                    + ' data-id="' + escId + '" data-phone="' + escPhone + '" data-name="' + escName + '"'
                    + ' onclick="handleConvRowClick(this)">'
                    + '<td class="py-2 pr-4 font-mono">' + escPhone + '</td>'
                    + '<td class="py-2 pr-4">' + (escName || '\u2014') + '</td>'
                    + '<td class="py-2 pr-4"><span class="px-2 py-0.5 rounded-full text-xs font-medium ' + b + '">' + c.estado + '</span></td>'
                    + '<td class="py-2 pr-4 text-gray-500">' + new Date(c.ultimo_mensaje_at).toLocaleString('es-ES') + '</td>'
                    + '<td id="appts-' + escId + '" class="py-2 pr-4 text-xs text-gray-400">\u2026</td></tr>';
            }).join('');
            _loadAllRowAppointments(data.conversations);
        }
        const tp = Math.ceil(data.total / data.page_size) || 1;
        document.getElementById('conv-pagination').innerHTML =
            '<span class="text-gray-500">' + data.total + ' conversaciones</span>'
            + '<div class="space-x-2">'
            + '<button onclick="loadConversations(' + (page-1) + ')" ' + (page<=1?'disabled':'') + ' class="px-3 py-1 rounded border ' + (page<=1?'text-gray-300':'hover:bg-gray-100') + '">Anterior</button>'
            + '<span class="text-gray-500">' + page + ' / ' + tp + '</span>'
            + '<button onclick="loadConversations(' + (page+1) + ')" ' + (page>=tp?'disabled':'') + ' class="px-3 py-1 rounded border ' + (page>=tp?'text-gray-300':'hover:bg-gray-100') + '">Siguiente</button>'
            + '</div>';
    } catch (e) { showMsg('err', e.message); }
}
function handleConvRowClick(row) {
    var id = row.getAttribute('data-id');
    var phone = row.getAttribute('data-phone');
    var name = row.getAttribute('data-name');
    viewMessages(id, phone, name);
}
async function _loadAllRowAppointments(conversations) {
    await Promise.allSettled(conversations.map(async function(c) {
        var cell = document.getElementById('appts-' + c.id);
        if (!cell) return;
        try {
            var data = await apiCall('GET', '/admin/conversations/' + c.id + '/appointments');
            var items = [];
            (data.individual || []).forEach(function(a) {
                if (a.datetime) {
                    var dt = new Date(a.datetime).toLocaleString('es-ES', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
                    items.push('Cita \u00b7 ' + dt);
                }
            });
            (data.group || []).forEach(function(g) {
                items.push(escapeHtml(g.nombre) + ' \u00b7 ' + escapeHtml(g.fecha));
            });
            if (items.length === 0) {
                cell.textContent = '\u2014';
            } else if (items.length === 1) {
                cell.textContent = items[0];
            } else {
                cell.innerHTML = escapeHtml(items[0]) + ' <span class="text-gray-400">+' + (items.length - 1) + '</span>';
            }
        } catch (_) { cell.textContent = '\u2014'; }
    }));
}
async function viewMessages(convId, phone, name) {
    currentViewConvId = convId;
    currentViewPhone = phone;
    currentViewName = name;
    document.getElementById('msg-phone').textContent = name || phone;
    try {
        const data = await apiCall('GET', '/admin/conversations/' + convId + '/messages');
        const list = document.getElementById('messages-list');
        list.innerHTML = data.messages.map(function(m) {
            const u = m.role === 'user';
            const escContent = escapeHtml(m.content);
            return '<div class="flex ' + (u?'justify-start':'justify-end') + '">'
                + '<div class="max-w-xs lg:max-w-md px-4 py-2 rounded-lg text-sm ' + (u?'bg-gray-200 text-gray-800':'bg-green-600 text-white') + '">'
                + '<p>' + escContent + '</p>'
                + '<div class="text-xs mt-1 ' + (u?'text-gray-400':'text-green-200') + '">'
                + new Date(m.created_at).toLocaleTimeString('es-ES')
                + '</div></div></div>';
        }).join('');
        document.getElementById('messages-panel').classList.remove('hidden');
        list.scrollTop = list.scrollHeight;
        setTimeout(function() { list.scrollTop = list.scrollHeight; }, 50);
        if (typeof lucide !== 'undefined') lucide.createIcons();
    } catch (e) { showMsg('err', e.message); }
    _loadConvAppointments(convId);
}
async function _loadConvAppointments(convId) {
    var card = document.getElementById('conv-appointments-card');
    if (!card) return;
    card.innerHTML = '<p class="text-xs text-gray-400">Cargando citas...</p>';
    try {
        var data = await apiCall('GET', '/admin/conversations/' + convId + '/appointments');
        var items = [];
        (data.individual || []).forEach(function(a) {
            var dt = a.datetime ? new Date(a.datetime).toLocaleString('es-ES', {day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}) : '—';
            items.push('<li class="text-xs text-gray-700">• ' + escapeHtml(a.service || 'Cita') + ' — ' + dt + '</li>');
        });
        (data.group || []).forEach(function(g) {
            items.push('<li class="text-xs text-gray-700">• ' + escapeHtml(g.nombre) + ' grupal — ' + escapeHtml(g.fecha) + ' ' + escapeHtml(g.hora) + '</li>');
        });
        if (items.length === 0) {
            card.innerHTML = '<p class="text-xs text-gray-400">Sin próximas citas.</p>';
        } else {
            card.innerHTML = '<p class="text-xs font-medium text-gray-600 mb-1">Próximas citas</p><ul class="space-y-0.5">' + items.join('') + '</ul>';
        }
    } catch (_) {
        card.innerHTML = '<p class="text-xs text-gray-400">No se pudieron cargar las citas.</p>';
    }
}
function closeMessages() {
    document.getElementById('messages-panel').classList.add('hidden');
    currentViewConvId = null;
    currentViewPhone = null;
    currentViewName = null;
}

// ===== METRICAS =====
async function loadMetrics() {
    try {
        const d = await apiCall('GET', '/admin/metrics');
        document.getElementById('dashboard-upgrade-overlay').classList.add('hidden');
        document.getElementById('v-msgs-hoy').textContent = d.mensajes_hoy;
        document.getElementById('v-citas-mes').textContent = d.citas_agendadas_mes;
        document.getElementById('v-avg-ms').textContent = d.avg_processing_ms || '\u2014';
        document.getElementById('v-activas').textContent = d.conversaciones_activas;
        document.getElementById('metrics-detail').innerHTML =
            '<p>Mensajes esta semana: <strong>' + d.mensajes_semana + '</strong></p>'
            + '<p>Cancelaciones este mes: <strong>' + d.citas_canceladas_mes + '</strong> &nbsp;|&nbsp; Derivaciones: <strong>' + d.derivaciones_mes + '</strong></p>';
    } catch (e) {
        if (e.message && e.message.includes('no disponible')) {
            document.getElementById('dashboard-upgrade-overlay').classList.remove('hidden');
            clearInterval(dashboardRefreshInterval); dashboardRefreshInterval = null;
        } else { showMsg('err', e.message); }
    }
}

// ===== MODAL CONFIRMACION =====
let confirmResolve = null;
function showConfirmModal(title, text, danger) {
    document.getElementById('confirm-title').textContent = title; document.getElementById('confirm-text').textContent = text;
    document.getElementById('confirm-action-btn').className = 'px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors ' + (danger ? 'bg-red-600 hover:bg-red-700' : 'bg-green-600 hover:bg-green-700');
    document.getElementById('confirm-modal').classList.remove('hidden');
    return new Promise(r => { confirmResolve = r; });
}
function closeConfirmModal(result) { document.getElementById('confirm-modal').classList.add('hidden'); if (confirmResolve) { confirmResolve(result); confirmResolve = null; } }

// ===== WORK BLOCKS EDITOR =====
const WB_DAYS = ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo'];
let currentWorkBlocks = {};

function renderWorkBlocksEditor(workBlocks) {
    currentWorkBlocks = workBlocks || {};
    const container = document.getElementById('work-blocks-editor');
    container.innerHTML = '';
    for (let d = 0; d < 7; d++) {
        const blocks = (currentWorkBlocks[String(d)] || []);
        const row = document.createElement('div');
        row.className = 'flex items-start gap-3';
        let blocksHtml = '';
        if (blocks.length === 0) {
            blocksHtml = '<span class="text-xs text-gray-400 pt-1">Cerrado</span>';
        } else {
            blocksHtml = blocks.map(function(b, i) {
                return '<div class="flex items-center gap-1">'
                    + '<input type="time" value="' + b[0] + '" class="wb-start border rounded p-1 text-xs" data-day="' + d + '" data-idx="' + i + '">'
                    + '<span class="text-gray-400">-</span>'
                    + '<input type="time" value="' + b[1] + '" class="wb-end border rounded p-1 text-xs" data-day="' + d + '" data-idx="' + i + '">'
                    + '<button onclick="removeWbBlock(' + d + ',' + i + ')" class="text-red-400 hover:text-red-600 text-xs ml-1">&times;</button>'
                    + '</div>';
            }).join('');
        }
        row.innerHTML = '<span class="w-24 text-sm text-gray-600 pt-1 shrink-0">' + WB_DAYS[d] + '</span>'
            + '<div class="flex flex-wrap gap-2">' + blocksHtml + '</div>'
            + '<button onclick="addWbBlock(' + d + ')" class="text-teal-600 hover:text-teal-800 text-xs shrink-0 pt-1">+ Bloque</button>';
        container.appendChild(row);
    }
}
function addWbBlock(day) {
    if (!currentWorkBlocks[String(day)]) currentWorkBlocks[String(day)] = [];
    currentWorkBlocks[String(day)].push(['09:00', '14:00']);
    renderWorkBlocksEditor(currentWorkBlocks);
}
function removeWbBlock(day, idx) {
    var blocks = currentWorkBlocks[String(day)] || [];
    blocks.splice(idx, 1);
    if (blocks.length === 0) delete currentWorkBlocks[String(day)];
    else currentWorkBlocks[String(day)] = blocks;
    renderWorkBlocksEditor(currentWorkBlocks);
}
function collectWorkBlocks() {
    var result = {};
    for (var d = 0; d < 7; d++) {
        var starts = document.querySelectorAll('.wb-start[data-day="' + d + '"]');
        var ends = document.querySelectorAll('.wb-end[data-day="' + d + '"]');
        var blocks = [];
        starts.forEach(function(s, i) {
            if (s.value && ends[i] && ends[i].value) blocks.push([s.value, ends[i].value]);
        });
        if (blocks.length > 0) result[String(d)] = blocks;
    }
    return result;
}

// (openFeaturesModal, saveFeatureOverrides, closeFeaturesModal → admin-superadmin.js)

// ===== INIT =====
if (typeof lucide !== 'undefined') lucide.createIcons();
if (token && userRole) { showDashboard(); }
