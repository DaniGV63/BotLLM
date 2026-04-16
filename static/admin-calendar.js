/* admin-calendar.js — Vista calendario con FullCalendar */

let calendarInstance = null;
let blockStart = null;
let blockEnd = null;

function _calcScrollTime() {
    var now = new Date();
    var scrollMin = Math.max(0, now.getHours() * 60 + now.getMinutes() - 30);
    var sh = Math.floor(scrollMin / 60);
    var sm = scrollMin % 60;
    return String(sh).padStart(2, '0') + ':' + String(sm).padStart(2, '0') + ':00';
}

function initCalendar() {
    const container = document.getElementById('fullcalendar-container');
    if (!container) return;

    if (calendarInstance) {
        calendarInstance.refetchEvents();
        return;
    }

    calendarInstance = new FullCalendar.Calendar(container, {
        initialView: 'timeGridWeek',
        locale: 'es',
        firstDay: 1,
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: 'timeGridWeek,timeGridDay',
        },
        slotMinTime: '00:00:00',
        slotMaxTime: '24:00:00',
        scrollTime: _calcScrollTime(),
        allDaySlot: false,
        height: 'auto',
        nowIndicator: true,
        selectable: true,
        selectMirror: true,
        unselectAuto: false,
        slotDuration: '00:15:00',
        slotLabelInterval: '00:30:00',
        eventTimeFormat: { hour: '2-digit', minute: '2-digit', hour12: false },
        slotLabelFormat: { hour: '2-digit', minute: '2-digit', hour12: false },

        // Franjas antes de las 7 y después de las 23 más estrechas via CSS
        slotLaneClassNames: function(arg) {
            const h = arg.time.hours;
            return (h < 7 || h >= 23) ? ['fc-slot-offhours'] : [];
        },

        events: function(info, successCallback, failureCallback) {
            var start = info.startStr.split('T')[0];
            var end = info.endStr.split('T')[0];
            apiCall('GET', '/admin/calendar/events?start=' + start + '&end=' + end)
                .then(function(data) { successCallback(data); })
                .catch(function(e) { failureCallback(e); });
        },

        select: function(info) {
            var today = new Date();
            today.setHours(0, 0, 0, 0);
            if (info.start < today) {
                calendarInstance.unselect();
                return;
            }
            blockStart = info.start;
            blockEnd = info.end;
            try {
                showActionChooser(info.start, info.end);
            } catch (err) {
                console.error('showActionChooser error:', err);
                // Fallback: mostrar chooser modal directamente
                var chooser = document.getElementById('action-chooser-modal');
                if (chooser) chooser.classList.remove('hidden');
            }
        },

        eventClick: function(info) {
            var props = info.event.extendedProps || {};
            if (props.type === 'work_block') return;
            if (props.type === 'group_class') {
                var sessionId = info.event.id.replace('group_', '');
                showSessionDetail(sessionId);
                return;
            }
            if (props.type === 'blocked') {
                showBlockEditModal(info.event);
                return;
            }
        },
    });

    calendarInstance.render();
    _injectCalendarStyles();
    _injectNavArrows();
}

function _injectNavArrows() {
    if (document.getElementById('fc-nav-prev')) return;
    var container = document.getElementById('fullcalendar-container');
    if (!container) return;
    var btnStyle = 'position:fixed;z-index:20;background:white;border:1px solid #d1d5db;'
        + 'border-radius:50%;width:2rem;height:2rem;display:flex;align-items:center;'
        + 'justify-content:center;cursor:pointer;box-shadow:0 1px 4px rgba(0,0,0,0.1);'
        + 'font-size:1rem;color:#374151;transform:translateY(-50%);';
    var prev = document.createElement('button');
    prev.id = 'fc-nav-prev';
    prev.title = 'Semana anterior';
    prev.style.cssText = btnStyle;
    prev.innerHTML = '&#8249;';
    prev.onclick = function() { if (calendarInstance) calendarInstance.prev(); };
    var next = document.createElement('button');
    next.id = 'fc-nav-next';
    next.title = 'Semana siguiente';
    next.style.cssText = btnStyle;
    next.innerHTML = '&#8250;';
    next.onclick = function() { if (calendarInstance) calendarInstance.next(); };
    document.body.appendChild(prev);
    document.body.appendChild(next);

    function updateArrowPos() {
        var rect = container.getBoundingClientRect();
        var visTop = Math.max(rect.top, 0);
        var visBottom = Math.min(rect.bottom, window.innerHeight);
        if (visBottom <= visTop) {
            prev.style.display = 'none';
            next.style.display = 'none';
            return;
        }
        prev.style.display = 'flex';
        next.style.display = 'flex';
        var mid = (visTop + visBottom) / 2;
        prev.style.top = mid + 'px';
        next.style.top = mid + 'px';
        prev.style.left = Math.max(rect.left - 20, 4) + 'px';
        next.style.left = Math.min(rect.right + 4, window.innerWidth - 36) + 'px';
    }

    window.addEventListener('scroll', updateArrowPos, { passive: true });
    window.addEventListener('resize', updateArrowPos, { passive: true });
    updateArrowPos();
}

function _injectCalendarStyles() {
    if (document.getElementById('fc-custom-styles')) return;
    const style = document.createElement('style');
    style.id = 'fc-custom-styles';
    style.textContent = [
        // Fondo gris suave para todas las franjas (horas cerradas)
        '.fc .fc-timegrid-slot { background-color: #f3f4f6; }',
        // Las horas fuera de horario laboral (antes 7h / después 23h) más estrechas
        '.fc .fc-slot-offhours { height: 1.2em !important; }',
        // Fuente coherente con el admin en labels de hora y cabeceras de día
        '.fc .fc-timegrid-slot-label, .fc .fc-col-header-cell, .fc .fc-toolbar-title {',
        '  font-family: ui-sans-serif, system-ui, -apple-system, sans-serif;',
        '  font-size: 0.78rem;',
        '}',
        '.fc .fc-toolbar-title { font-size: 1rem; font-weight: 600; }',
        '.fc .fc-col-header-cell-cushion { font-weight: 600; color: #374151; text-decoration: none; }',
        '.fc .fc-timegrid-slot-label-cushion { color: #6b7280; font-weight: 500; }',
        // Eliminar borde inferior del header para look más limpio
        '.fc .fc-col-header { border-bottom: 1px solid #e5e7eb; }',
    ].join('\n');
    document.head.appendChild(style);
}

function closeBlockModal() {
    document.getElementById('block-modal').classList.add('hidden');
    if (calendarInstance) calendarInstance.unselect();
    blockStart = null;
    blockEnd = null;
}

async function confirmBlockSlot() {
    if (!blockStart || !blockEnd) return;
    var title = document.getElementById('block-modal-title').value.trim() || 'Bloqueado';
    try {
        var tzOffset = blockStart.getTimezoneOffset();
        var startISO = new Date(blockStart.getTime() - tzOffset * 60000).toISOString().slice(0, 19);
        var endISO = new Date(blockEnd.getTime() - tzOffset * 60000).toISOString().slice(0, 19);
        var sign = tzOffset <= 0 ? '+' : '-';
        var absOff = Math.abs(tzOffset);
        var offStr = sign + String(Math.floor(absOff / 60)).padStart(2, '0') + ':' + String(absOff % 60).padStart(2, '0');
        await apiCall('POST', '/admin/calendar/block', {
            start: startISO + offStr,
            end: endISO + offStr,
            title: title,
        });
        closeBlockModal();
        if (calendarInstance) calendarInstance.refetchEvents();
        showMsg('ok', 'Horario bloqueado');
    } catch (e) {
        showMsg('err', e.message);
    }
}

// ── Modal edición/borrado de bloqueos ─────────────────────────────────────

var _editBlockEventId = null;
var _editBlockEvent = null;

function showBlockEditModal(event) {
    _editBlockEventId = event.id;
    _editBlockEvent = event;

    var title = (event.title || '').replace(/^Bloqueado - ?/, '');
    document.getElementById('block-edit-title').value = title;

    // Mostrar rango horario en el modal
    var fmt = { hour: '2-digit', minute: '2-digit', hour12: false };
    var startStr = event.start ? event.start.toLocaleTimeString('es', fmt) : '';
    var endStr = event.end ? event.end.toLocaleTimeString('es', fmt) : '';
    var dateStr = event.start ? event.start.toLocaleDateString('es', { weekday: 'long', day: 'numeric', month: 'long' }) : '';
    document.getElementById('block-edit-time').textContent = dateStr + (startStr ? ', ' + startStr + ' – ' + endStr : '');

    document.getElementById('block-edit-modal').classList.remove('hidden');
}

function closeBlockEditModal() {
    document.getElementById('block-edit-modal').classList.add('hidden');
    _editBlockEventId = null;
    _editBlockEvent = null;
}

async function confirmDeleteBlock() {
    if (!_editBlockEventId) return;
    try {
        await apiCall('DELETE', '/admin/calendar/block/' + _editBlockEventId);
        closeBlockEditModal();
        if (calendarInstance) calendarInstance.refetchEvents();
        showMsg('ok', 'Bloqueo eliminado');
    } catch (e) {
        showMsg('err', e.message);
    }
}

async function confirmUpdateBlock() {
    if (!_editBlockEventId || !_editBlockEvent) return;
    var title = document.getElementById('block-edit-title').value.trim() || 'Bloqueado';
    try {
        var tzOffset = _editBlockEvent.start.getTimezoneOffset();
        var sign = tzOffset <= 0 ? '+' : '-';
        var absOff = Math.abs(tzOffset);
        var offStr = sign + String(Math.floor(absOff / 60)).padStart(2, '0') + ':' + String(absOff % 60).padStart(2, '0');
        var startISO = new Date(_editBlockEvent.start.getTime() - tzOffset * 60000).toISOString().slice(0, 19);
        var endISO = new Date(_editBlockEvent.end.getTime() - tzOffset * 60000).toISOString().slice(0, 19);
        await apiCall('PATCH', '/admin/calendar/block/' + _editBlockEventId, {
            start: startISO + offStr,
            end: endISO + offStr,
            title: title,
        });
        closeBlockEditModal();
        if (calendarInstance) calendarInstance.refetchEvents();
        showMsg('ok', 'Bloqueo actualizado');
    } catch (e) {
        showMsg('err', e.message);
    }
}
