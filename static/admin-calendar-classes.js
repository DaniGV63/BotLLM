/* admin-calendar-classes.js — Gestión de sesiones grupales desde el calendario */

var _chooserStart = null;
var _chooserEnd = null;
var _currentSessionData = null;

const _DAY_NAMES_FULL = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];

function showClassWarning(text) {
    var existing = document.getElementById('class-warning-toast');
    if (existing) existing.remove();
    var toast = document.createElement('div');
    toast.id = 'class-warning-toast';
    toast.style.cssText = 'position:fixed;top:1.25rem;left:50%;transform:translateX(-50%);z-index:9999;max-width:36rem;width:90%;background:#fef3c7;border:1px solid #f59e0b;border-radius:0.75rem;padding:1rem 1.25rem;box-shadow:0 4px 16px rgba(0,0,0,0.12);display:flex;gap:0.75rem;align-items:flex-start;';
    toast.innerHTML = '<span style="font-size:1.25rem;line-height:1;">⚠️</span>'
        + '<div style="flex:1;font-size:0.875rem;color:#92400e;line-height:1.4;">'
        + '<strong style="display:block;margin-bottom:0.25rem;">Clase creada con aviso</strong>'
        + _escHtml(text)
        + '</div>'
        + '<button onclick="document.getElementById(\'class-warning-toast\').remove()" '
        + 'style="background:none;border:none;cursor:pointer;font-size:1rem;color:#92400e;padding:0;line-height:1;" title="Cerrar">✕</button>';
    document.body.appendChild(toast);
}

function _escHtml(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function _formatCalTime(start, end) {
    var dayOpts = { weekday: 'long', day: 'numeric', month: 'long' };
    var timeOpts = { hour: '2-digit', minute: '2-digit', hour12: false };
    return start.toLocaleDateString('es-ES', dayOpts) + ', '
        + start.toLocaleTimeString('es-ES', timeOpts) + ' - '
        + end.toLocaleTimeString('es-ES', timeOpts);
}

// ===== CHOOSER =====

function showActionChooser(start, end) {
    _chooserStart = start;
    _chooserEnd = end;
    document.getElementById('chooser-time').textContent = _formatCalTime(start, end);
    document.getElementById('action-chooser-modal').classList.remove('hidden');
}

function closeChooserModal() {
    document.getElementById('action-chooser-modal').classList.add('hidden');
    if (calendarInstance) calendarInstance.unselect();
    _chooserStart = null;
    _chooserEnd = null;
}

function chooserPickBlock() {
    var start = _chooserStart;
    var end = _chooserEnd;
    closeChooserModal();
    blockStart = start;
    blockEnd = end;
    document.getElementById('block-modal-time').textContent = _formatCalTime(start, end);
    document.getElementById('block-modal-title').value = '';
    document.getElementById('block-modal').classList.remove('hidden');
}

function chooserPickClass() {
    var start = _chooserStart;
    var end = _chooserEnd;
    closeChooserModal();
    // Rellenar modal crear sesión
    document.getElementById('cal-class-time').textContent = _formatCalTime(start, end);
    document.getElementById('cal-class-nombre').value = '';
    document.getElementById('cal-class-aforo').value = '8';
    document.getElementById('cal-class-duracion').value = String(Math.round((end - start) / 60000));
    document.getElementById('cal-class-recurrente').checked = false;
    document.getElementById('cal-class-days-row').classList.add('hidden');
    // Reset day buttons
    document.querySelectorAll('.cal-day-btn').forEach(function(btn) {
        btn.classList.remove('bg-green-500', 'text-white', 'border-green-500');
        btn.classList.add('border-gray-200', 'text-gray-500');
    });
    // Pre-select the day of the clicked slot
    var dayIdx = (start.getDay() + 6) % 7; // JS Sunday=0 → Monday=0 mapping
    var dayBtn = document.querySelector('.cal-day-btn[data-day="' + dayIdx + '"]');
    if (dayBtn) {
        dayBtn.classList.add('bg-green-500', 'text-white', 'border-green-500');
        dayBtn.classList.remove('border-gray-200', 'text-gray-500');
    }
    // Store start info for submission
    document.getElementById('cal-class-modal').dataset.fecha = start.toISOString().split('T')[0];
    var hh = String(start.getHours()).padStart(2, '0');
    var mm = String(start.getMinutes()).padStart(2, '0');
    document.getElementById('cal-class-modal').dataset.hora = hh + ':' + mm;
    document.getElementById('cal-class-modal').classList.remove('hidden');
}

// ===== CREATE SESSION =====

function toggleCalClassDays() {
    var checked = document.getElementById('cal-class-recurrente').checked;
    document.getElementById('cal-class-days-row').classList.toggle('hidden', !checked);
}

// Day button toggle
document.addEventListener('click', function(e) {
    var btn = e.target.closest('.cal-day-btn');
    if (!btn) return;
    btn.classList.toggle('bg-green-500');
    btn.classList.toggle('text-white');
    btn.classList.toggle('border-green-500');
    btn.classList.toggle('border-gray-200');
    btn.classList.toggle('text-gray-500');
});

function closeCalClassModal() {
    document.getElementById('cal-class-modal').classList.add('hidden');
    document.getElementById('cal-class-error').classList.add('hidden');
    if (calendarInstance) calendarInstance.unselect();
}

function _showClassError(msg) {
    var el = document.getElementById('cal-class-error');
    el.textContent = msg;
    el.classList.remove('hidden');
    setTimeout(function() { el.classList.add('hidden'); }, 5000);
}

async function confirmCalClass() {
    var errEl = document.getElementById('cal-class-error');
    errEl.classList.add('hidden');

    var nombre = document.getElementById('cal-class-nombre').value.trim();
    var aforo = parseInt(document.getElementById('cal-class-aforo').value);
    var duracion = parseInt(document.getElementById('cal-class-duracion').value);
    var recurrente = document.getElementById('cal-class-recurrente').checked;

    // Validaciones con mensajes específicos dentro del modal
    if (!nombre) { _showClassError('Introduce un nombre para la sesión (ej: Pilates, Yoga...)'); return; }
    if (!aforo || aforo < 1) { _showClassError('El aforo debe ser al menos 1 persona'); return; }
    if (!duracion || duracion < 15) { _showClassError('La duración debe ser al menos 15 minutos'); return; }

    var modal = document.getElementById('cal-class-modal');
    var fecha = modal.dataset.fecha;
    var hora = modal.dataset.hora;

    var dias_semana = [];
    if (recurrente) {
        document.querySelectorAll('.cal-day-btn.bg-green-500').forEach(function(btn) {
            dias_semana.push(parseInt(btn.dataset.day));
        });
        if (dias_semana.length < 2) { _showClassError('Selecciona al menos 2 días para una sesión recurrente. Si solo quieres un día, desmarca "Repetir semanalmente"'); return; }
    }

    try {
        var res = await apiCall('POST', '/admin/calendar/create-class', {
            nombre: nombre,
            fecha: fecha,
            hora: hora,
            duracion_min: duracion,
            max_capacidad: aforo,
            recurrente: recurrente,
            dias_semana: dias_semana,
        });
        closeCalClassModal();
        if (calendarInstance) calendarInstance.refetchEvents();
        if (res && res.warning) {
            showClassWarning(res.warning);
        } else {
            showMsg('ok', recurrente ? 'Sesión recurrente creada' : 'Sesión grupal creada');
        }
    } catch (e) {
        showMsg('err', e.message);
    }
}

// ===== SESSION DETAIL =====

async function showSessionDetail(sessionId) {
    try {
        var data = await apiCall('GET', '/admin/calendar/session/' + sessionId);
        _currentSessionData = data;

        document.getElementById('sd-nombre').textContent = data.nombre;
        document.getElementById('sd-fecha').textContent = new Date(data.fecha + 'T00:00:00').toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
        document.getElementById('sd-horario').textContent = data.hora;
        document.getElementById('sd-duracion').textContent = data.duracion_min;
        document.getElementById('sd-aforo').textContent = data.inscritos + ' / ' + data.max_capacidad + ' inscritos';

        var estadoBadge = document.getElementById('sd-estado-badge');
        if (data.estado === 'PROGRAMADA') {
            estadoBadge.innerHTML = '<span class="px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">PROGRAMADA</span>';
        } else {
            estadoBadge.innerHTML = '<span class="px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">CANCELADA</span>';
        }

        // Recurrente info
        var recInfo = document.getElementById('sd-recurrente-info');
        if (data.activa) {
            recInfo.classList.remove('hidden');
            var daysText = data.dias_semana.map(function(d) { return _DAY_NAMES_FULL[d]; }).join(', ');
            document.getElementById('sd-dias-text').textContent = daysText;
        } else {
            recInfo.classList.add('hidden');
        }

        // Inscriptions list
        var container = document.getElementById('sd-inscriptions');
        if (!data.inscriptions || !data.inscriptions.length) {
            container.innerHTML = '<p class="text-sm text-gray-400">Sin inscritos</p>';
        } else {
            container.innerHTML = '<table class="w-full text-xs"><thead><tr class="text-gray-400 uppercase"><th class="text-left pb-1">Teléfono</th><th class="text-left pb-1">Nombre</th><th class="text-left pb-1">Fecha</th></tr></thead><tbody>'
                + data.inscriptions.map(function(i) {
                    return '<tr class="border-t border-gray-100"><td class="py-1.5 text-gray-700">' + _escHtml(i.wa_phone)
                        + '</td><td class="py-1.5 text-gray-700">' + _escHtml(i.nombre_paciente || '—')
                        + '</td><td class="py-1.5 text-gray-500">' + new Date(i.created_at).toLocaleDateString('es-ES') + '</td></tr>';
                }).join('') + '</tbody></table>';
        }

        // Show/hide buttons based on state
        var btnCancelSession = document.getElementById('sd-btn-cancel-session');
        btnCancelSession.disabled = data.estado !== 'PROGRAMADA';
        if (data.estado !== 'PROGRAMADA') {
            btnCancelSession.classList.add('opacity-50', 'cursor-not-allowed');
        } else {
            btnCancelSession.classList.remove('opacity-50', 'cursor-not-allowed');
        }

        // Series delete button
        var btnDeleteSeries = document.getElementById('sd-btn-delete-series');
        if (data.activa) {
            btnDeleteSeries.classList.remove('hidden');
            btnDeleteSeries.onclick = function() { deleteDefinitionSeries(data.definition_id); };
        } else {
            btnDeleteSeries.classList.add('hidden');
        }

        // Ensure we're in info mode (not edit)
        exitEditMode();

        document.getElementById('session-detail-modal').classList.remove('hidden');
    } catch (e) {
        showMsg('err', e.message);
    }
}

function closeSessionDetailModal() {
    document.getElementById('session-detail-modal').classList.add('hidden');
    _currentSessionData = null;
}

// ===== EDIT MODE =====

function enterEditMode() {
    if (!_currentSessionData) return;
    document.getElementById('sd-info').classList.add('hidden');
    document.getElementById('sd-edit').classList.remove('hidden');
    document.getElementById('sd-btn-edit').classList.add('hidden');
    document.getElementById('sd-btn-save').classList.remove('hidden');
    document.getElementById('sd-btn-cancel-edit').classList.remove('hidden');

    document.getElementById('sd-edit-nombre').value = _currentSessionData.nombre;
    document.getElementById('sd-edit-aforo').value = _currentSessionData.max_capacidad;
    document.getElementById('sd-edit-duracion').value = _currentSessionData.duracion_min;
}

function exitEditMode() {
    document.getElementById('sd-info').classList.remove('hidden');
    document.getElementById('sd-edit').classList.add('hidden');
    document.getElementById('sd-btn-edit').classList.remove('hidden');
    document.getElementById('sd-btn-save').classList.add('hidden');
    document.getElementById('sd-btn-cancel-edit').classList.add('hidden');
}

async function saveSessionEdit() {
    if (!_currentSessionData) return;
    var defId = _currentSessionData.definition_id;
    var body = {
        nombre: document.getElementById('sd-edit-nombre').value.trim(),
        max_capacidad: parseInt(document.getElementById('sd-edit-aforo').value) || 8,
        duracion_min: parseInt(document.getElementById('sd-edit-duracion').value) || 60,
    };
    if (!body.nombre) { showMsg('err', 'El nombre no puede estar vacío'); return; }
    try {
        await apiCall('PUT', '/admin/classes/' + defId, body);
        closeSessionDetailModal();
        if (calendarInstance) calendarInstance.refetchEvents();
        showMsg('ok', 'Sesión actualizada');
    } catch (e) {
        showMsg('err', e.message);
    }
}

// ===== CANCEL / DELETE =====

async function cancelSessionFromDetail() {
    if (!_currentSessionData) return;
    var msg = '¿Cancelar esta sesión?';
    if (_currentSessionData.inscritos > 0) {
        msg += ' Hay ' + _currentSessionData.inscritos + ' inscrito(s).';
    }
    if (!confirm(msg)) return;
    try {
        await apiCall('DELETE', '/admin/calendar/session/' + _currentSessionData.session_id);
        closeSessionDetailModal();
        if (calendarInstance) calendarInstance.refetchEvents();
        showMsg('ok', 'Sesión cancelada');
    } catch (e) {
        showMsg('err', e.message);
    }
}

async function deleteDefinitionSeries(defId) {
    if (!confirm('¿Eliminar TODAS las sesiones de esta serie? Esta acción no se puede deshacer.')) return;
    try {
        await apiCall('DELETE', '/admin/classes/' + defId);
        closeSessionDetailModal();
        if (calendarInstance) calendarInstance.refetchEvents();
        showMsg('ok', 'Serie completa eliminada');
    } catch (e) {
        showMsg('err', e.message);
    }
}
