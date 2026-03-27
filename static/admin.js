const API = window.location.origin;
let token = sessionStorage.getItem('admin_token');
let userRole = sessionStorage.getItem('admin_role');
let tenantId = sessionStorage.getItem('admin_tenant_id') || null;
let superAdminToken = sessionStorage.getItem('super_admin_token') || null;
let botActivo = false;
let convRefreshInterval = null;
let dashboardRefreshInterval = null;
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
        await loadTenant(); showTab('configuracion');
    }
}
function renderTabsForRole() {
    const isSuperOnly = userRole === 'super_admin' && !tenantId;
    const hasTenant = !!tenantId;
    const isSuperWithTenant = userRole === 'super_admin' && hasTenant;
    const show = (id, v) => { const el = document.getElementById('tab-btn-' + id); if (el) el.classList.toggle('hidden', !v); };
    show('tenants', isSuperOnly); show('usuarios', isSuperOnly);
    show('configuracion', hasTenant); show('google', isSuperWithTenant);
    show('conversaciones', hasTenant); show('dashboard', hasTenant);
}
const ALL_TABS = ['tenants','usuarios','configuracion','google','conversaciones','dashboard'];
function showTab(name) {
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
    if (name === 'conversaciones') { loadConversations(1); convRefreshInterval = setInterval(() => loadConversations(1), 10000); }
    if (name === 'dashboard') { loadMetrics(); dashboardRefreshInterval = setInterval(() => loadMetrics(), 10000); if (typeof lucide !== 'undefined') lucide.createIcons(); }
    if (name === 'tenants') loadTenants();
    if (name === 'usuarios') loadUsers();
    if (name === 'configuracion') loadTenant();
}

// ===== TENANT DATA =====
async function loadTenant() {
    const t = await apiCall('GET', '/admin/tenant');
    document.getElementById('nav-nombre').textContent = t.nombre_negocio;
    const badge = document.getElementById('nav-role-badge');
    if (userRole === 'super_admin') { badge.textContent = 'Super Admin'; badge.className = 'text-xs font-medium px-2 py-0.5 rounded-full bg-purple-100 text-purple-700'; badge.classList.remove('hidden'); }
    else { badge.classList.add('hidden'); }
    document.getElementById('f-nombre').value = t.nombre_negocio;
    document.getElementById('f-email').value = t.email_notificaciones;
    botActivo = t.bot_activo; updateBotToggle();
    document.getElementById('f-rate-limit').value = t.rate_limit_per_minute;
    document.getElementById('f-max-citas').value = t.max_citas_activas;
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

// ===== SUPER ADMIN: TENANTS =====
async function loadTenants() {
    try {
        const data = await apiCall('GET', '/superadmin/tenants');
        tenantsCache = data.tenants;
        const tbody = document.getElementById('tenants-table');
        if (!data.tenants.length) {
            tbody.innerHTML = '<tr><td colspan="5" class="py-4 text-center text-gray-400">Sin tenants</td></tr>';
            return;
        }
        const demo = data.tenants[0];
        if (demo) { document.getElementById('demo-tenant-name').textContent = demo.nombre_negocio; document.getElementById('demo-tenant-btn').onclick = () => impersonateTenant(demo.id, demo.nombre_negocio); document.getElementById('demo-tenant-card').classList.remove('hidden'); }
        tbody.innerHTML = data.tenants.map(function(t) {
            const botB = t.bot_activo ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500';
            const botTxt = t.bot_activo ? 'Activo' : 'Inactivo';
            const escId = escapeHtml(t.id);
            const escName = escapeHtml(t.nombre_negocio);
            const escSlug = escapeHtml(t.slug);
            return '<tr class="border-b hover:bg-gray-50 transition-colors duration-100">'
                + '<td class="py-2 pr-4 font-mono text-xs">' + escSlug + '</td>'
                + '<td class="py-2 pr-4">' + escName + '</td>'
                + '<td class="py-2 pr-4"><span class="px-2 py-0.5 rounded-full text-xs ' + botB + '">' + botTxt + '</span></td>'
                + '<td class="py-2 pr-4 text-gray-500 text-xs">' + new Date(t.created_at).toLocaleDateString('es-ES') + '</td>'
                + '<td class="py-2"><button onclick="impersonateTenant(\'' + escId + '\',\'' + escName + '\')" class="text-teal-600 hover:text-teal-800 text-xs font-medium">Gestionar</button></td>'
                + '</tr>';
        }).join('');
    } catch(e) { showMsg('err', e.message); }
}
function showCreateTenantForm() { document.getElementById('create-tenant-form').classList.remove('hidden'); }
function hideCreateTenantForm() { document.getElementById('create-tenant-form').classList.add('hidden'); }
async function createTenant() {
    const slug = document.getElementById('nt-slug').value.trim();
    const nombre = document.getElementById('nt-nombre').value.trim();
    const email = document.getElementById('nt-email').value.trim();
    const phoneId = document.getElementById('nt-phone-id').value.trim();
    if (!slug || !nombre || !email || !phoneId) { showMsg('err', 'Todos los campos son obligatorios'); return; }
    try {
        await apiCall('POST', '/superadmin/tenants', {
            slug: slug, nombre_negocio: nombre, email_notificaciones: email, whatsapp_phone_number_id: phoneId
        });
        hideCreateTenantForm();
        ['nt-slug','nt-nombre','nt-email','nt-phone-id'].forEach(function(id) { document.getElementById(id).value = ''; });
        await loadTenants(); showMsg('ok', "Tenant '" + slug + "' creado");
    } catch(e) { showMsg('err', e.message); }
}

// ===== SUPER ADMIN: USUARIOS =====
async function loadUsers() {
    try {
        const users = await apiCall('GET', '/superadmin/users');
        const sel = document.getElementById('nu-tenant');
        sel.innerHTML = '<option value="">Selecciona tenant...</option>'
            + tenantsCache.map(function(t) { return '<option value="' + t.id + '">' + t.nombre_negocio + ' (' + t.slug + ')</option>'; }).join('');
        const tbody = document.getElementById('users-table');
        if (!users.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="py-4 text-center text-gray-400">Sin usuarios</td></tr>';
            return;
        }
        const tenantMap = {};
        tenantsCache.forEach(function(t) { tenantMap[t.id] = t.slug; });
        tbody.innerHTML = users.map(function(u) {
            const rolB = u.role === 'super_admin' ? 'bg-purple-100 text-purple-700' : 'bg-teal-100 text-teal-700';
            const rolTxt = u.role === 'super_admin' ? 'Super Admin' : 'Tenant Admin';
            const slug = u.tenant_id ? (tenantMap[u.tenant_id] || u.tenant_id.slice(0,8)) : '\u2014';
            const escId = escapeHtml(u.id);
            const escUsername = escapeHtml(u.username);
            const escEmail = escapeHtml(u.email || '');
            const del = u.role !== 'super_admin'
                ? '<button onclick="deleteUser(\'' + escId + '\',\'' + escUsername + '\')" class="text-red-500 hover:text-red-700 text-xs">Eliminar</button>'
                : '<span class="text-gray-300 text-xs">\u2014</span>';
            return '<tr class="border-b hover:bg-gray-50 transition-colors duration-100">'
                + '<td class="py-2 pr-4 font-medium">' + escUsername + '</td>'
                + '<td class="py-2 pr-4"><span class="px-2 py-0.5 rounded-full text-xs ' + rolB + '">' + rolTxt + '</span></td>'
                + '<td class="py-2 pr-4 font-mono text-xs">' + slug + '</td>'
                + '<td class="py-2 pr-4 text-gray-500 text-xs">' + (escEmail || '\u2014') + '</td>'
                + '<td class="py-2 pr-4 text-gray-500 text-xs">' + new Date(u.created_at).toLocaleDateString('es-ES') + '</td>'
                + '<td class="py-2">' + del + '</td></tr>';
        }).join('');
    } catch(e) { showMsg('err', e.message); }
}
function showCreateUserForm() {
    if (!tenantsCache.length) { showMsg('err', 'Carga la lista de tenants primero (tab Tenants)'); return; }
    document.getElementById('create-user-form').classList.remove('hidden');
}
function hideCreateUserForm() { document.getElementById('create-user-form').classList.add('hidden'); }
async function createUser() {
    const username = document.getElementById('nu-username').value.trim();
    const password = document.getElementById('nu-password').value;
    const email = document.getElementById('nu-email').value.trim();
    const tid = document.getElementById('nu-tenant').value;
    if (!username || !password || !tid) { showMsg('err', 'Username, contrasena y tenant son obligatorios'); return; }
    try {
        await apiCall('POST', '/superadmin/users', { username: username, password: password, tenant_id: tid, email: email || null });
        hideCreateUserForm();
        ['nu-username','nu-password','nu-email'].forEach(function(id) { document.getElementById(id).value = ''; });
        document.getElementById('nu-tenant').value = '';
        await loadUsers(); showMsg('ok', "Usuario '" + username + "' creado");
    } catch(e) { showMsg('err', e.message); }
}
async function deleteUser(userId, username) {
    if (!await showConfirmModal('Eliminar usuario', "Eliminar '" + username + "'? Esta acción no se puede deshacer.", true)) return;
    try {
        await apiCall('DELETE', '/superadmin/users/' + userId);
        await loadUsers(); showMsg('ok', "Usuario '" + username + "' eliminado");
    } catch(e) { showMsg('err', e.message); }
}

// ===== CONVERSACIONES =====
async function loadConversations(page) {
    try {
        const data = await apiCall('GET', '/admin/conversations?page=' + page + '&page_size=15');
        const tbody = document.getElementById('conv-table');
        if (!data.conversations.length) {
            tbody.innerHTML = '<tr><td colspan="5" class="py-4 text-center text-gray-400">Sin conversaciones</td></tr>';
        } else {
            tbody.innerHTML = data.conversations.map(function(c) {
                const b = c.estado === 'ACTIVA' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500';
                const escId = escapeHtml(c.id);
                const escPhone = escapeHtml(formatPhone(c.wa_phone));
                const escName = escapeHtml(c.nombre_paciente || '');
                return '<tr class="border-b hover:bg-gray-50 transition-colors duration-100">'
                    + '<td class="py-2 pr-4 font-mono">' + escPhone + '</td>'
                    + '<td class="py-2 pr-4">' + (escName || '\u2014') + '</td>'
                    + '<td class="py-2 pr-4"><span class="px-2 py-0.5 rounded-full text-xs font-medium ' + b + '">' + c.estado + '</span></td>'
                    + '<td class="py-2 pr-4 text-gray-500">' + new Date(c.ultimo_mensaje_at).toLocaleString('es-ES') + '</td>'
                    + '<td class="py-2"><button onclick="viewMessages(\'' + escId + '\',\'' + escPhone + '\',\'' + escName + '\')" class="text-[#1F2937] hover:text-black text-xs font-medium border border-[#1F2937] rounded-lg px-3 py-1">Ver</button></td></tr>';
            }).join('');
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
async function viewMessages(convId, phone, name) {
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
        if (typeof lucide !== 'undefined') lucide.createIcons();
    } catch (e) { showMsg('err', e.message); }
}
function closeMessages() { document.getElementById('messages-panel').classList.add('hidden'); }

// ===== METRICAS =====
async function loadMetrics() {
    try {
        const d = await apiCall('GET', '/admin/metrics');
        document.getElementById('v-msgs-hoy').textContent = d.mensajes_hoy;
        document.getElementById('v-citas-mes').textContent = d.citas_agendadas_mes;
        document.getElementById('v-avg-ms').textContent = d.avg_processing_ms || '\u2014';
        document.getElementById('v-activas').textContent = d.conversaciones_activas;
        document.getElementById('metrics-detail').innerHTML =
            '<p>Mensajes esta semana: <strong>' + d.mensajes_semana + '</strong></p>'
            + '<p>Cancelaciones este mes: <strong>' + d.citas_canceladas_mes + '</strong> &nbsp;|&nbsp; Derivaciones: <strong>' + d.derivaciones_mes + '</strong></p>';
    } catch (e) { showMsg('err', e.message); }
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

// ===== INIT =====
if (typeof lucide !== 'undefined') lucide.createIcons();
if (token && userRole) { showDashboard(); }
