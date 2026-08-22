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
    const pg = data.power.powerguess;
    let html = '';

    // PowerGuess estimate — main power display
    if (pg) {
      const tag = pg.measured ? 'measured' : `±${pg.error_margin_w}W`;
      html += metricHTML('power', 'System Power', pg.power_w, 'W');
      html += `<div class="metric power">
        <div class="label">Source</div>
        <div class="value" style="font-size:0.9rem">${pg.source}<span class="unit"> ${tag}</span></div>
      </div>`;
      if (pg.voltage_v > 0) {
        html += metricHTML('volt', 'AC Voltage', pg.voltage_v, 'V');
      }
      if (pg.current_a > 0) {
        html += metricHTML('current', 'AC Current', pg.current_a, 'A');
      }
    }

    // Any hwmon power sensors
    const sensors = data.power.sensors;
    if (sensors.length) {
      html += sensors.map(s =>
        metricHTML('power', `${s.name} #${s.channel}`, s.value, s.unit)
      ).join('');
    }

    // GPU power
    const gpuW = data.power.gpu_total_w;
    if (gpuW > 0) {
      html += metricHTML('power', 'GPU Power', gpuW, 'W');
    }

    if (!html) {
      grid.innerHTML = '<p class="no-data">No power sensors detected. Motherboard may not expose INA219/INA3221 via hwmon.</p>';
    } else {
      grid.innerHTML = html;
    }

    const gpuEl = $('gpuPower');
    gpuEl.textContent = '';
  }

  function renderTemps(data) {
    const grid = $('tempGrid');
    if (!data.temperatures.length) {
      grid.innerHTML = '<p class="no-data">No temperature sensors found.</p>';
      return;
    }
    grid.innerHTML = data.temperatures.map(s => {
      const hot = s.value > 80 ? ' hot' : '';
      return metricHTML('temp' + hot, s.label, s.value, s.unit);
    }).join('');
  }

  function renderFans(data) {
    const grid = $('fanGrid');
    if (!data.fans.length) {
      grid.innerHTML = '<p class="no-data">No fan sensors found.</p>';
      return;
    }
    grid.innerHTML = data.fans.map(s =>
      metricHTML('fan', s.label, s.value, s.unit)
    ).join('');
  }

  function renderVoltages(data) {
    const grid = $('voltGrid');
    if (!data.voltages.length) {
      grid.innerHTML = '<p class="no-data">No voltage sensors found.</p>';
      return;
    }
    grid.innerHTML = data.voltages.map(s =>
      metricHTML('volt', s.label, s.value, s.unit)
    ).join('');
  }

  function renderEcoflow(data) {
    const card = $('ecoflowCard');
    const grid = $('ecoflowGrid');
    const ef = data.ecoflow;
    if (!ef) {
      card.style.display = 'none';
      return;
    }
    card.style.display = '';
    let html = '';
    if (ef.charge_pct != null) html += metricHTML('power', 'Battery', ef.charge_pct, '%');
    if (ef.total_load_w != null) html += metricHTML('power', 'Total Load', ef.total_load_w, 'W');
    if (ef.total_draw_w != null) html += metricHTML('power', 'Total Draw', ef.total_draw_w, 'W');
    if (ef.ac_load_w != null) html += metricHTML('fan', 'AC Load', ef.ac_load_w, 'W');
    if (ef.dc_load_w != null) html += metricHTML('fan', 'DC Load', ef.dc_load_w, 'W');
    if (ef.usb_a_w != null) html += metricHTML('fan', 'USB-A', ef.usb_a_w, 'W');
    if (ef.usb_c_w != null) html += metricHTML('fan', 'USB-C', ef.usb_c_w, 'W');
    if (ef.solar_w != null) html += metricHTML('volt', 'Solar/DC', ef.solar_w, 'W');
    if (ef.time_left_min != null) html += metricHTML('temp', 'Time Left', ef.time_left_min, 'min');
    grid.innerHTML = html || '<p class="no-data">EcoFlow connected but no data returned.</p>';
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
      renderEcoflow(data);

      $('lastUpdate').textContent = 'Last update: ' + new Date(data.timestamp).toLocaleTimeString();
    } catch (e) {
      $('lastUpdate').textContent = 'Error fetching data — retrying…';
    }
  }

  // Initial load + poll
  poll();
  setInterval(poll, POLL_INTERVAL);
})();
