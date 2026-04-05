/* admin-superadmin.js — Funciones exclusivas del panel de super admin */

// ===== SUPER ADMIN: TENANTS =====
async function loadTenants() {
    try {
        const data = await apiCall('GET', '/superadmin/tenants');
        tenantsCache = data.tenants;
        const tbody = document.getElementById('tenants-table');
        if (!data.tenants.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="py-4 text-center text-gray-400">Sin tenants</td></tr>';
            return;
        }
        const demo = data.tenants[0];
        if (demo) { document.getElementById('demo-tenant-name').textContent = demo.nombre_negocio; document.getElementById('demo-tenant-btn').onclick = () => impersonateTenant(demo.id, demo.nombre_negocio); document.getElementById('demo-tenant-card').classList.remove('hidden'); }
        tbody.innerHTML = data.tenants.map(function(t) {
            const botB = t.bot_activo ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500';
            const botTxt = t.bot_activo ? 'Activo' : 'Inactivo';
            const planColors = { 'PAID': 'bg-green-100 text-green-700', 'FREE_TRIAL': 'bg-yellow-100 text-yellow-700', 'SIN_PLAN': 'bg-gray-100 text-gray-500' };
            const planCls = planColors[t.plan] || planColors['SIN_PLAN'];
            const planLabel = t.plan || 'SIN_PLAN';
            const escId = escapeHtml(t.id);
            const escName = escapeHtml(t.nombre_negocio);
            const escSlug = escapeHtml(t.slug);
            return '<tr class="border-b hover:bg-gray-50 transition-colors duration-100">'
                + '<td class="py-2 pr-4 font-mono text-xs">' + escSlug + '</td>'
                + '<td class="py-2 pr-4">' + escName + '</td>'
                + '<td class="py-2 pr-4"><span class="px-2 py-0.5 rounded-full text-xs ' + botB + '">' + botTxt + '</span></td>'
                + '<td class="py-2 pr-4"><span class="px-2 py-0.5 rounded-full text-xs ' + planCls + '">' + escapeHtml(planLabel) + '</span></td>'
                + '<td class="py-2 pr-4 text-gray-500 text-xs">' + new Date(t.created_at).toLocaleDateString('es-ES') + '</td>'
                + '<td class="py-2 pr-4 text-xs">' + (t.plan_expires_at ? '<span class="text-orange-600">' + new Date(t.plan_expires_at).toLocaleDateString('es-ES') + '</span>' : '<span class="text-gray-300">&mdash;</span>') + '</td>'
                + '<td class="py-2"><div class="flex flex-wrap gap-2"><button onclick="openPlanModal(\'' + escId + '\',\'' + escName + '\',\'' + escapeHtml(planLabel) + '\')" class="text-orange-600 hover:text-orange-800 text-xs font-medium">Plan</button>'
                + '<button onclick="openFeaturesModal(\'' + escId + '\',\'' + escName + '\')" class="text-purple-600 hover:text-purple-800 text-xs font-medium">Features</button>'
                + '<button onclick="impersonateTenant(\'' + escId + '\',\'' + escName + '\')" class="text-teal-600 hover:text-teal-800 text-xs font-medium">Gestionar</button></div></td>'
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

// ===== PLAN MANAGEMENT =====
let planTenantId = null;
function openPlanModal(tenantId, tenantName, currentPlan) {
    planTenantId = tenantId;
    document.getElementById('plan-modal-tenant-name').textContent = tenantName;
    document.getElementById('plan-modal-select').value = currentPlan || 'SIN_PLAN';
    document.getElementById('plan-modal-expires').value = '';
    document.getElementById('plan-modal-expires').classList.add('hidden');
    var toggle = document.getElementById('plan-expires-toggle');
    toggle.classList.remove('bg-teal-500');
    toggle.classList.add('bg-gray-200');
    toggle.setAttribute('aria-checked', 'false');
    toggle.querySelector('span').classList.remove('translate-x-4');
    toggle.querySelector('span').classList.add('translate-x-0');
    document.getElementById('plan-modal').classList.remove('hidden');
}
function togglePlanExpires() {
    var toggle = document.getElementById('plan-expires-toggle');
    var input = document.getElementById('plan-modal-expires');
    var isOn = toggle.getAttribute('aria-checked') === 'true';
    if (isOn) {
        toggle.setAttribute('aria-checked', 'false');
        toggle.classList.remove('bg-teal-500'); toggle.classList.add('bg-gray-200');
        toggle.querySelector('span').classList.remove('translate-x-4'); toggle.querySelector('span').classList.add('translate-x-0');
        input.classList.add('hidden'); input.value = '';
    } else {
        toggle.setAttribute('aria-checked', 'true');
        toggle.classList.remove('bg-gray-200'); toggle.classList.add('bg-teal-500');
        toggle.querySelector('span').classList.remove('translate-x-0'); toggle.querySelector('span').classList.add('translate-x-4');
        input.classList.remove('hidden');
    }
}
function closePlanModal() { document.getElementById('plan-modal').classList.add('hidden'); planTenantId = null; }
async function saveTenantPlan() {
    if (!planTenantId) return;
    const plan = document.getElementById('plan-modal-select').value;
    const expires = document.getElementById('plan-modal-expires').value;
    const body = { plan, plan_expires_at: expires ? new Date(expires).toISOString() : null };
    try {
        await apiCall('PUT', '/superadmin/tenants/' + planTenantId + '/plan', body);
        closePlanModal();
        await loadTenants();
        showMsg('ok', 'Plan actualizado: ' + plan);
    } catch(e) { showMsg('err', e.message); }
}

// ===== FEATURE OVERRIDES =====
let featuresTenantId = null;
async function openFeaturesModal(tenantId, tenantName) {
    featuresTenantId = tenantId;
    document.getElementById('features-tenant-name').textContent = tenantName;
    try {
        const data = await apiCall('GET', '/superadmin/tenants/' + tenantId + '/features');
        const overrides = data.feature_overrides || {};
        const tbody = document.getElementById('features-table-body');
        tbody.innerHTML = data.features.map(function(f) {
            const isPending = f.status === 'pendiente';
            const hasOverride = f.key in overrides;
            const overrideVal = hasOverride ? (overrides[f.key] ? 'true' : 'false') : 'default';
            const enabledCls = f.enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500';
            const enabledTxt = f.enabled ? 'Sí' : 'No';
            const rowCls = isPending ? ' opacity-50' : '';
            const pendingBadge = isPending ? ' <span class="ml-1 px-1.5 py-0.5 rounded text-xs bg-yellow-100 text-yellow-600 font-medium">Pendiente</span>' : '';
            const selectDisabled = isPending ? ' disabled' : '';
            return '<tr class="border-b' + rowCls + '">'
                + '<td class="py-2 pr-3"><span class="font-medium text-gray-' + (isPending ? '400' : '900') + '">' + escapeHtml(f.name) + pendingBadge + '</span><br><span class="text-xs text-gray-400">' + escapeHtml(f.key) + '</span></td>'
                + '<td class="py-2 pr-3"><span class="px-2 py-0.5 rounded-full text-xs ' + enabledCls + '">' + enabledTxt + '</span></td>'
                + '<td class="py-2"><select data-feature-key="' + escapeHtml(f.key) + '" class="text-xs border rounded p-1"' + selectDisabled + '>'
                + '<option value="default"' + (overrideVal === 'default' ? ' selected' : '') + '>Plan default</option>'
                + '<option value="true"' + (overrideVal === 'true' ? ' selected' : '') + '>Forzar ON</option>'
                + '<option value="false"' + (overrideVal === 'false' ? ' selected' : '') + '>Forzar OFF</option>'
                + '</select></td></tr>';
        }).join('');
        document.getElementById('features-modal').classList.remove('hidden');
    } catch(e) { showMsg('err', e.message); }
}
async function resetFeatureOverrides() {
    if (!await showConfirmModal('Reset features', 'Se eliminarán todos los overrides y las features volverán al comportamiento por defecto del plan actual. ¿Continuar?', false)) return;
    try {
        await apiCall('PUT', '/superadmin/tenants/' + featuresTenantId + '/features', {});
        closeFeaturesModal();
        showMsg('ok', 'Features reseteadas al plan por defecto');
    } catch(e) { showMsg('err', e.message); }
}
async function saveFeatureOverrides() {
    const selects = document.querySelectorAll('#features-table-body select');
    const overrides = {};
    selects.forEach(function(sel) {
        if (sel.value === 'true') overrides[sel.dataset.featureKey] = true;
        else if (sel.value === 'false') overrides[sel.dataset.featureKey] = false;
    });
    try {
        await apiCall('PUT', '/superadmin/tenants/' + featuresTenantId + '/features', overrides);
        closeFeaturesModal();
        showMsg('ok', 'Feature overrides guardados');
    } catch(e) { showMsg('err', e.message); }
}
function closeFeaturesModal() { document.getElementById('features-modal').classList.add('hidden'); }
