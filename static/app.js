// EVGA SuperNOVA 850 Monitor — Dashboard JS
(function () {
  'use strict';

  const POLL_INTERVAL = 3000; // 3 seconds

  function $(id) { return document.getElementById(id); }

  function metricHTML(cls, label, value, unit) {
    return `<div class="metric ${cls}">
      <div class="label">${label}</div>
      <div class="value">${value}<span class="unit">${unit}</span></div>
    </div>`;
  }

  function renderPower(data) {
    const grid = $('powerGrid');
    const sensors = data.power.sensors;
    if (!sensors.length) {
      grid.innerHTML = '<p class="no-data">No power sensors detected. Motherboard may not expose INA219/INA3221 via hwmon.</p>';
      return;
    }
    grid.innerHTML = sensors.map(s =>
      metricHTML('power', `${s.name} #${s.channel}`, s.value, s.unit)
    ).join('');

    const gpuW = data.power.gpu_total_w;
    const gpuEl = $('gpuPower');
    if (gpuW > 0) {
      gpuEl.textContent = `GPU total: ${gpuW} W`;
    } else {
      gpuEl.textContent = '';
    }
  }

  function renderTemps(data) {
    const grid = $('tempGrid');
    if (!data.temperatures.length) {
      grid.innerHTML = '<p class="no-data">No temperature sensors found.</p>';
      return;
    }
    grid.innerHTML = data.temperatures.map(s => {
      const hot = s.value > 80 ? ' hot' : '';
      return metricHTML('temp' + hot, `${s.label} (${s.name})`, s.value, s.unit);
    }).join('');
  }

  function renderFans(data) {
    const grid = $('fanGrid');
    if (!data.fans.length) {
      grid.innerHTML = '<p class="no-data">No fan sensors found.</p>';
      return;
    }
    grid.innerHTML = data.fans.map(s =>
      metricHTML('fan', `${s.name} #${s.channel}`, s.value, s.unit)
    ).join('');
  }

  function renderVoltages(data) {
    const grid = $('voltGrid');
    if (!data.voltages.length) {
      grid.innerHTML = '<p class="no-data">No voltage sensors found.</p>';
      return;
    }
    grid.innerHTML = data.voltages.map(s =>
      metricHTML('volt', `${s.name} #${s.channel}`, s.value, s.unit)
    ).join('');
  }

  function renderGPU(data) {
    const card = $('gpuCard');
    const details = $('gpuDetails');
    if (!data.gpus.length) {
      card.style.display = 'none';
      return;
    }
    card.style.display = '';
    details.innerHTML = data.gpus.map(g => {
      const rows = [];
      if (g.power_w != null) rows.push(metricHTML('power', 'Power', g.power_w, 'W'));
      if (g.temp_c != null) rows.push(metricHTML('temp', 'Temp', g.temp_c, '°C'));
      if (g.fan_pct != null) rows.push(metricHTML('fan', 'Fan', g.fan_pct, '%'));
      if (g.util_gpu_pct != null) rows.push(metricHTML('fan', 'GPU Util', g.util_gpu_pct, '%'));
      if (g.util_mem_pct != null) rows.push(metricHTML('fan', 'Mem Util', g.util_mem_pct, '%'));
      if (g.mem_used_mb != null) rows.push(metricHTML('volt', 'VRAM', `${Math.round(g.mem_used_mb)}/${Math.round(g.mem_total_mb)}`, 'MB'));
      if (g.clock_gr_mhz != null) rows.push(metricHTML('volt', 'GPU Clock', g.clock_gr_mhz, 'MHz'));
      if (g.clock_mem_mhz != null) rows.push(metricHTML('volt', 'Mem Clock', g.clock_mem_mhz, 'MHz'));
      return `<h3 style="margin:8px 0;font-size:0.9rem;color:var(--muted)">${g.name}</h3>
              <div class="gpu-detail-row">${rows.join('')}</div>`;
    }).join('');
  }

  async function poll() {
    try {
      const resp = await fetch('/api/sensors');
      if (!resp.ok) throw new Error(resp.status);
      const data = await resp.json();

      renderPower(data);
      renderTemps(data);
      renderFans(data);
      renderVoltages(data);
      renderGPU(data);

      $('lastUpdate').textContent = 'Last update: ' + new Date(data.timestamp).toLocaleTimeString();
    } catch (e) {
      $('lastUpdate').textContent = 'Error fetching data — retrying…';
    }
  }

  // Initial load + poll
  poll();
  setInterval(poll, POLL_INTERVAL);
})();
