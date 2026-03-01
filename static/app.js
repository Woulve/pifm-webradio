const logsContent = document.getElementById('logsContent');
const logsText = document.getElementById('logsText');
const autoRefreshCheckbox = document.getElementById('autoRefresh');
const logsSection = document.getElementById('logsSection');
let refreshInterval = null;

function scrollLogsToBottom() {
    logsContent.scrollTop = logsContent.scrollHeight;
}

async function refreshLogs() {
    try {
        const response = await fetch('/logs');
        if (response.ok) {
            const text = await response.text();
            logsText.textContent = text;
            scrollLogsToBottom();
        }
    } catch (e) {
        console.error('Failed to refresh logs:', e);
    }
}

autoRefreshCheckbox.addEventListener('change', function() {
    if (this.checked) {
        refreshLogs();
        refreshInterval = setInterval(refreshLogs, 3000);
    } else {
        if (refreshInterval) {
            clearInterval(refreshInterval);
            refreshInterval = null;
        }
    }
});

scrollLogsToBottom();

function loadPreset(index) {
    const preset = window.presetsData[index];
    if (preset) {
        document.getElementById('stream_url').value = preset.url || '';
        document.getElementById('ps_name').value = preset.ps_name || '';
        document.getElementById('rt_text').value = preset.rt_text || '';
    }
}

async function saveAsPreset() {
    const name = prompt('Enter preset name:');
    if (!name || !name.trim()) return;

    const preset = {
        name: name.trim(),
        url: document.getElementById('stream_url').value,
        ps_name: document.getElementById('ps_name').value,
        rt_text: document.getElementById('rt_text').value
    };

    try {
        const response = await fetch('/presets', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(preset)
        });
        if (response.ok) {
            location.reload();
        } else {
            alert('Failed to save preset');
        }
    } catch (e) {
        alert('Error saving preset: ' + e.message);
    }
}

async function deletePreset(index, event) {
    event.stopPropagation();
    if (!confirm('Delete this preset?')) return;

    try {
        const response = await fetch('/presets/' + index, {
            method: 'DELETE'
        });
        if (response.ok) {
            location.reload();
        } else {
            alert('Failed to delete preset');
        }
    } catch (e) {
        alert('Error deleting preset: ' + e.message);
    }
}
