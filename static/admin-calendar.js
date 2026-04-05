/* admin-calendar.js — Vista calendario con FullCalendar */

let calendarInstance = null;
let blockStart = null;
let blockEnd = null;

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
        scrollTime: '07:00:00',
        allDaySlot: false,
        height: 'auto',
        nowIndicator: true,
        selectable: true,
        selectMirror: true,
        // 1h slots fuera de horario central, 30min dentro
        slotDuration: '00:30:00',
        slotLabelInterval: '01:00:00',
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
            if (info.start < new Date()) {
                calendarInstance.unselect();
                return;
            }
            blockStart = info.start;
            blockEnd = info.end;
            var opts = { hour: '2-digit', minute: '2-digit', hour12: false };
            var dayOpts = { weekday: 'long', day: 'numeric', month: 'long' };
            document.getElementById('block-modal-time').textContent =
                info.start.toLocaleDateString('es-ES', dayOpts) + ', '
                + info.start.toLocaleTimeString('es-ES', opts) + ' - '
                + info.end.toLocaleTimeString('es-ES', opts);
            document.getElementById('block-modal-title').value = '';
            document.getElementById('block-modal').classList.remove('hidden');
        },

        eventClick: function(info) {
            if (info.event.extendedProps && info.event.extendedProps.type === 'work_block') return;
        },
    });

    calendarInstance.render();
    _injectCalendarStyles();
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
