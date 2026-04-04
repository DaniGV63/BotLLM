// admin-classes.js — Gestión de clases grupales

const DAY_NAMES = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];
let _currentClassId = null;

async function loadClasses() {
    const token = localStorage.getItem('token');
    try {
        const res = await fetch('/admin/classes', { headers: { Authorization: 'Bearer ' + token } });
        if (!res.ok) { document.getElementById('classes-table-body').innerHTML = '<tr><td colspan="6" class="px-4 py-6 text-center text-gray-400 text-sm">No disponible en tu plan actual.</td></tr>'; return; }
        const classes = await res.json();
        _renderClassesTable(classes);
    } catch (e) {
        console.error('loadClasses error', e);
    }
}

function _renderClassesTable(classes) {
    const tbody = document.getElementById('classes-table-body');
    if (!classes.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="px-4 py-8 text-center text-gray-400 text-sm">Sin clases creadas. Crea la primera con el botón de arriba.</td></tr>';
        return;
    }
    tbody.innerHTML = classes.map(c => `
        <tr class="hover:bg-gray-50">
            <td class="px-4 py-3 font-medium text-gray-900">${_esc(c.nombre)}</td>
            <td class="px-4 py-3 text-gray-600">${(c.dias_semana || []).map(d => DAY_NAMES[d]).join(', ')}</td>
            <td class="px-4 py-3 text-gray-600">${_esc(c.hora)}</td>
            <td class="px-4 py-3 text-gray-600">${c.max_capacidad} pers.</td>
            <td class="px-4 py-3">
                <span class="px-2 py-0.5 rounded-full text-xs font-medium ${c.activa ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}">${c.activa ? 'Activa' : 'Inactiva'}</span>
            </td>
            <td class="px-4 py-3">
                <div class="flex gap-2">
                    <button onclick="showSessions('${c.id}', '${_esc(c.nombre)}')" class="text-teal-600 hover:text-teal-800 text-xs">Sesiones</button>
                    <button onclick="editClass(${JSON.stringify(c).replace(/"/g, '&quot;')})" class="text-blue-600 hover:text-blue-800 text-xs">Editar</button>
                    <button onclick="deleteClass('${c.id}')" class="text-red-500 hover:text-red-700 text-xs">Borrar</button>
                </div>
            </td>
        </tr>
    `).join('');
}

function showCreateClassForm() {
    _currentClassId = null;
    document.getElementById('class-form-title').textContent = 'Nueva clase';
    document.getElementById('class-form-id').value = '';
    document.getElementById('class-form-nombre').value = '';
    document.getElementById('class-form-hora').value = '';
    document.getElementById('class-form-duracion').value = '60';
    document.getElementById('class-form-aforo').value = '8';
    document.querySelectorAll('.day-check').forEach(cb => cb.checked = false);
    document.getElementById('class-form').classList.remove('hidden');
}

function editClass(c) {
    _currentClassId = c.id;
    document.getElementById('class-form-title').textContent = 'Editar clase';
    document.getElementById('class-form-id').value = c.id;
    document.getElementById('class-form-nombre').value = c.nombre;
    document.getElementById('class-form-hora').value = c.hora;
    document.getElementById('class-form-duracion').value = c.duracion_min;
    document.getElementById('class-form-aforo').value = c.max_capacidad;
    document.querySelectorAll('.day-check').forEach(cb => { cb.checked = (c.dias_semana || []).includes(parseInt(cb.value)); });
    document.getElementById('class-form').classList.remove('hidden');
}

async function saveClass() {
    const token = localStorage.getItem('token');
    const dias = Array.from(document.querySelectorAll('.day-check:checked')).map(cb => parseInt(cb.value));
    const body = {
        nombre: document.getElementById('class-form-nombre').value.trim(),
        dias_semana: dias,
        hora: document.getElementById('class-form-hora').value.trim(),
        duracion_min: parseInt(document.getElementById('class-form-duracion').value) || 60,
        max_capacidad: parseInt(document.getElementById('class-form-aforo').value) || 8,
    };
    if (!body.nombre || !body.hora || !dias.length) { alert('Completa nombre, hora y al menos un día.'); return; }
    const isEdit = !!_currentClassId;
    const url = isEdit ? `/admin/classes/${_currentClassId}` : '/admin/classes';
    const method = isEdit ? 'PUT' : 'POST';
    try {
        const res = await fetch(url, { method, headers: { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        if (!res.ok) { alert('Error al guardar.'); return; }
        document.getElementById('class-form').classList.add('hidden');
        loadClasses();
    } catch (e) { alert('Error de red.'); }
}

async function deleteClass(id) {
    if (!confirm('¿Eliminar esta clase y todas sus sesiones?')) return;
    const token = localStorage.getItem('token');
    try {
        await fetch(`/admin/classes/${id}`, { method: 'DELETE', headers: { Authorization: 'Bearer ' + token } });
        loadClasses();
    } catch (e) { alert('Error al eliminar.'); }
}

async function showSessions(classId, nombre) {
    _currentClassId = classId;
    document.getElementById('sessions-panel-title').textContent = `Sesiones — ${nombre}`;
    document.getElementById('sessions-panel').classList.remove('hidden');
    document.getElementById('inscriptions-panel').classList.add('hidden');
    const token = localStorage.getItem('token');
    try {
        const res = await fetch(`/admin/classes/${classId}/sessions`, { headers: { Authorization: 'Bearer ' + token } });
        const sessions = await res.json();
        const tbody = document.getElementById('sessions-table-body');
        if (!sessions.length) { tbody.innerHTML = '<tr><td colspan="5" class="px-3 py-4 text-center text-gray-400 text-sm">Sin sesiones. Usa "Generar 14 días".</td></tr>'; return; }
        tbody.innerHTML = sessions.map(s => `
            <tr class="hover:bg-gray-50">
                <td class="px-3 py-2">${s.fecha}</td>
                <td class="px-3 py-2">${s.hora}</td>
                <td class="px-3 py-2"><span class="px-2 py-0.5 rounded-full text-xs ${s.estado === 'PROGRAMADA' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}">${s.estado}</span></td>
                <td class="px-3 py-2">${s.inscritos} / ${s.inscritos + s.plazas_libres}</td>
                <td class="px-3 py-2"><button onclick="showInscriptions('${s.id}', '${s.fecha}')" class="text-teal-600 hover:text-teal-800 text-xs">Ver inscritos</button></td>
            </tr>
        `).join('');
    } catch (e) { console.error('showSessions error', e); }
}

async function generateSessions() {
    if (!_currentClassId) return;
    const token = localStorage.getItem('token');
    try {
        await fetch(`/admin/classes/${_currentClassId}/sessions/generate?days_ahead=14`, { method: 'POST', headers: { Authorization: 'Bearer ' + token } });
        showSessions(_currentClassId, document.getElementById('sessions-panel-title').textContent.replace('Sesiones — ', ''));
    } catch (e) { alert('Error al generar.'); }
}

async function showInscriptions(sessionId, fecha) {
    document.getElementById('inscriptions-panel-title').textContent = `Inscritos — sesión ${fecha}`;
    document.getElementById('inscriptions-panel').classList.remove('hidden');
    const token = localStorage.getItem('token');
    try {
        const res = await fetch(`/admin/classes/sessions/${sessionId}/inscriptions`, { headers: { Authorization: 'Bearer ' + token } });
        const list = await res.json();
        const tbody = document.getElementById('inscriptions-table-body');
        if (!list.length) { tbody.innerHTML = '<tr><td colspan="3" class="px-3 py-4 text-center text-gray-400 text-sm">Sin inscritos.</td></tr>'; return; }
        tbody.innerHTML = list.map(i => `
            <tr class="hover:bg-gray-50">
                <td class="px-3 py-2 text-gray-700">${_esc(i.wa_phone)}</td>
                <td class="px-3 py-2 text-gray-700">${_esc(i.nombre_paciente || '—')}</td>
                <td class="px-3 py-2 text-gray-500 text-xs">${new Date(i.created_at).toLocaleString('es-ES')}</td>
            </tr>
        `).join('');
    } catch (e) { console.error('showInscriptions error', e); }
}

function _esc(s) { return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
