/* RBC-TESTER Dashboard JavaScript */

const API = '/api';
let pollInterval = null;
let currentTab = 'logs';

// ---- API helpers ----

async function api(path, opts = {}) {
    try {
        const res = await fetch(API + path, opts);
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || res.statusText);
        }
        return await res.json();
    } catch (e) {
        console.error('API error:', e);
        return null;
    }
}

// ---- Stats ----

async function loadStats() {
    const data = await api('/stats');
    if (!data) return;

    document.getElementById('stat-input').textContent = data.input_files;
    document.getElementById('stat-output').textContent = data.output_files;
    document.getElementById('stat-completed').textContent = data.completed;
    document.getElementById('stat-failed').textContent = data.failed;
    document.getElementById('stat-pending').textContent = data.pending;
    document.getElementById('stat-size').textContent = data.output_size_mb;

    // Knowledge stats
    const k = data.knowledge || {};
    document.getElementById('stat-embeddings').textContent = k.total_embeddings || 0;
    document.getElementById('stat-backlinks').textContent = k.total_backlinks || 0;
    document.getElementById('stat-tags').textContent = k.total_tags || 0;
    document.getElementById('stat-people').textContent = k.total_people || 0;
    document.getElementById('stat-dates').textContent = k.total_dates || 0;

    // File types
    const typesEl = document.getElementById('file-types');
    typesEl.innerHTML = '';
    const typeFilter = document.getElementById('file-type-filter');
    const existingOptions = typeFilter.querySelectorAll('option:not(:first-child)');
    existingOptions.forEach(o => o.remove());

    for (const [type, count] of Object.entries(data.file_types || {})) {
        const badge = document.createElement('span');
        badge.className = 'type-badge';
        badge.innerHTML = `${type}<span class="count">${count}</span>`;
        typesEl.appendChild(badge);

        const opt = document.createElement('option');
        opt.value = type;
        opt.textContent = type;
        typeFilter.appendChild(opt);
    }
}

async function loadSystemStats() {
    const data = await api('/stats/system');
    if (!data) return;

    setBar('cpu', data.cpu_percent);
    setBar('mem', data.memory_percent);
    setBar('disk', data.disk_percent);
}

function setBar(prefix, percent) {
    const bar = document.getElementById(prefix + '-bar');
    const val = document.getElementById(prefix + '-val');
    if (bar) bar.style.width = percent + '%';
    if (val) val.textContent = percent + '%';

    // Color based on usage
    if (bar) {
        if (percent > 80) bar.style.background = '#e17055';
        else if (percent > 60) bar.style.background = '#fdcb6e';
        else bar.style.background = '#6c5ce7';
    }
}

// ---- Progress ----

async function loadProgress() {
    const data = await api('/progress');
    if (!data) return;

    const section = document.getElementById('progress-section');
    const btnStart = document.getElementById('btn-start');
    const btnStop = document.getElementById('btn-stop');

    if (data.running) {
        section.style.display = 'block';
        btnStart.disabled = true;
        btnStop.disabled = false;

        document.getElementById('progress-text').textContent =
            `${data.processed} / ${data.total}`;
        document.getElementById('progress-percent').textContent =
            `${data.percent || 0}%`;
        document.getElementById('progress-fill').style.width =
            `${data.percent || 0}%`;

        if (data.eta_seconds) {
            const mins = Math.floor(data.eta_seconds / 60);
            const secs = data.eta_seconds % 60;
            document.getElementById('progress-eta').textContent =
                `ETA: ${mins}m ${secs}s`;
        }

        if (data.current_file) {
            document.getElementById('progress-current').textContent =
                `Processing: ${data.current_file}`;
        }

        if (!pollInterval) startPolling();
    } else {
        btnStart.disabled = false;
        btnStop.disabled = true;
        if (data.processed > 0) {
            section.style.display = 'block';
            document.getElementById('progress-current').textContent = 'Conversion complete';
        }
    }
}

// ---- Controls ----

async function startConversion() {
    const data = await api('/convert/start', { method: 'POST' });
    if (data) {
        startPolling();
        loadProgress();
    }
}

async function stopConversion() {
    await api('/convert/stop', { method: 'POST' });
    loadProgress();
}

async function retryFailed() {
    const data = await api('/convert/retry', { method: 'POST' });
    if (data && data.status === 'no_failed_files') {
        alert('No failed files to retry');
    }
    loadStats();
}

async function resetState() {
    if (!confirm('Reset all conversion tracking? This will not delete output files.')) return;
    await api('/convert/reset', { method: 'POST' });
    loadStats();
    loadProgress();
}

// ---- Logs ----

async function loadLogs() {
    const level = document.getElementById('log-level').value;
    const params = level ? `?level=${level}` : '';
    const data = await api('/logs' + params);
    if (!data) return;

    const container = document.getElementById('logs');
    container.innerHTML = '';

    for (const log of data.logs) {
        const entry = document.createElement('div');
        entry.className = 'log-entry';
        const time = log.timestamp.split('T')[1]?.split('.')[0] || '';
        entry.innerHTML = `<span class="log-time">${time}</span>` +
            `<span class="log-level ${log.level}">${log.level}</span>` +
            `<span class="log-msg">${escapeHtml(log.message)}</span>`;
        container.appendChild(entry);
    }

    container.scrollTop = container.scrollHeight;
}

// ---- Timeline ----

async function loadTimeline() {
    const data = await api('/timeline');
    if (!data) return;

    const container = document.getElementById('timeline');
    const timeline = data.timeline || {};
    const dates = Object.keys(timeline).sort().reverse();

    if (dates.length === 0) {
        container.innerHTML = '<p class="placeholder">No timeline data yet. Run a conversion to generate timeline entries.</p>';
        return;
    }

    container.innerHTML = '';
    for (const date of dates) {
        const files = timeline[date] || [];
        const div = document.createElement('div');
        div.className = 'timeline-date';
        div.innerHTML = `<div class="timeline-date-label">${date}</div>` +
            `<ul class="timeline-files">${files.map(f => {
                const name = f.split('/').pop();
                return `<li>${escapeHtml(name)}</li>`;
            }).join('')}</ul>`;
        container.appendChild(div);
    }
}

// ---- Graph ----

async function loadGraph() {
    const data = await api('/graph');
    if (!data) return;

    const statsEl = document.getElementById('graph-stats');
    const s = data.stats || {};
    statsEl.innerHTML = `
        <span>Nodes: <strong>${s.total_nodes || 0}</strong></span>
        <span>Edges: <strong>${s.total_edges || 0}</strong></span>
        <span>Files: <strong>${s.file_nodes || 0}</strong></span>
        <span>Tags: <strong>${s.tag_nodes || 0}</strong></span>
        <span>People: <strong>${s.person_nodes || 0}</strong></span>
        <span>Density: <strong>${s.density || 0}</strong></span>
    `;

    drawGraph(data.nodes || [], data.edges || []);
}

function drawGraph(nodes, edges) {
    const canvas = document.getElementById('graph-canvas');
    const ctx = canvas.getContext('2d');
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (nodes.length === 0) {
        ctx.fillStyle = '#8b8fa3';
        ctx.font = '14px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('No graph data yet. Run a conversion to build the knowledge graph.', canvas.width / 2, canvas.height / 2);
        return;
    }

    // Simple force-directed layout
    const positions = {};
    const cx = canvas.width / 2;
    const cy = canvas.height / 2;
    const radius = Math.min(cx, cy) * 0.7;

    nodes.forEach((node, i) => {
        const angle = (2 * Math.PI * i) / nodes.length;
        positions[node.id] = {
            x: cx + radius * Math.cos(angle) + (Math.random() - 0.5) * 30,
            y: cy + radius * Math.sin(angle) + (Math.random() - 0.5) * 30,
        };
    });

    // Draw edges
    ctx.strokeStyle = 'rgba(108, 92, 231, 0.3)';
    ctx.lineWidth = 1;
    for (const edge of edges) {
        const from = positions[edge.source];
        const to = positions[edge.target];
        if (from && to) {
            ctx.beginPath();
            ctx.moveTo(from.x, from.y);
            ctx.lineTo(to.x, to.y);
            ctx.stroke();
        }
    }

    // Draw nodes
    const colors = { file: '#6c5ce7', tag: '#00b894', person: '#fdcb6e', unknown: '#74b9ff' };
    for (const node of nodes) {
        const pos = positions[node.id];
        if (!pos) continue;

        const color = colors[node.type] || colors.unknown;
        const r = node.type === 'file' ? 5 : 4;

        ctx.beginPath();
        ctx.arc(pos.x, pos.y, r, 0, 2 * Math.PI);
        ctx.fillStyle = color;
        ctx.fill();

        // Label (only for small graphs)
        if (nodes.length < 50) {
            ctx.fillStyle = '#e4e6f0';
            ctx.font = '10px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(truncate(node.label || '', 15), pos.x, pos.y - 8);
        }
    }
}

// ---- Files table ----

async function loadFiles() {
    const status = document.getElementById('file-status-filter').value;
    const type = document.getElementById('file-type-filter').value;
    let params = '?limit=200';
    if (status) params += `&status=${status}`;
    if (type) params += `&file_type=${type}`;

    const data = await api('/files' + params);
    if (!data) return;

    const tbody = document.getElementById('files-tbody');
    tbody.innerHTML = '';

    for (const file of data.files) {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td title="${escapeHtml(file.path)}">${escapeHtml(file.name)}</td>
            <td><span class="type-badge">${file.type}</span></td>
            <td>${file.size_kb} KB</td>
            <td><span class="status-${file.status}">${file.status}</span></td>
        `;
        tbody.appendChild(tr);
    }
}

// ---- Tabs ----

function switchTab(tabName) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));

    document.querySelector(`.tab[onclick="switchTab('${tabName}')"]`).classList.add('active');
    document.getElementById('tab-' + tabName).classList.add('active');

    currentTab = tabName;

    if (tabName === 'logs') loadLogs();
    if (tabName === 'timeline') loadTimeline();
    if (tabName === 'graph') loadGraph();
    if (tabName === 'files') loadFiles();
}

// ---- Polling ----

function startPolling() {
    if (pollInterval) return;
    pollInterval = setInterval(() => {
        loadProgress();
        loadSystemStats();
        if (currentTab === 'logs') loadLogs();
    }, 2000);
}

function stopPolling() {
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
}

// ---- Utilities ----

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function truncate(str, len) {
    return str.length > len ? str.substring(0, len) + '...' : str;
}

// ---- Init ----

document.addEventListener('DOMContentLoaded', () => {
    loadStats();
    loadSystemStats();
    loadProgress();
    loadLogs();

    // Refresh stats periodically
    setInterval(loadStats, 10000);
    setInterval(loadSystemStats, 5000);
});
