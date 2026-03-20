// ── CHART DEFAULTS ───────────────────────────────────────────────────────────
Chart.defaults.font.family = "'Inter', -apple-system, sans-serif";
Chart.defaults.font.size   = 12;
Chart.defaults.color       = '#718096';

const C = {
    us:               '#2b77e6',
    texas:            '#d4500a',
    dfw:              '#0f9b6e',
    lubbock:          '#7c3aed',
    target:           '#a0aec0',
    naturalLW:        '#d97706',
    naturalRichmond:  '#0891b2',
    ffr:              '#e53e3e',
};

const BASE_OPTIONS = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
        legend: {
            position: 'bottom',
            labels: { usePointStyle: true, pointStyleWidth: 10, padding: 18, font: { size: 12 } },
        },
        tooltip: {
            backgroundColor: 'rgba(26,54,93,0.93)',
            padding: 12,
            titleFont: { size: 12, weight: '600' },
            bodyFont:  { size: 12 },
            cornerRadius: 6,
            callbacks: {
                title: items => items[0].label,
            },
        },
    },
    scales: {
        x: {
            grid:  { color: 'rgba(0,0,0,0.04)' },
            ticks: { maxTicksLimit: 10, font: { size: 11 } },
        },
        y: {
            grid:  { color: 'rgba(0,0,0,0.04)' },
            ticks: { font: { size: 11 } },
        },
    },
};

function lineDataset(label, data, color, opts = {}) {
    return {
        label,
        data,
        borderColor:     color,
        backgroundColor: opts.fill ? color.replace(')', ', 0.12)').replace('rgb', 'rgba') : 'transparent',
        borderWidth:     opts.width  ?? 2,
        borderDash:      opts.dash   ?? [],
        pointRadius:     opts.points ?? 0,
        pointHoverRadius: 4,
        fill: opts.fillTarget ?? false,
        tension: 0.3,
    };
}

// ── TAB NAVIGATION ────────────────────────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(s => s.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(btn.dataset.tab).classList.add('active');
    });
});

// ── LOAD DASHBOARD ────────────────────────────────────────────────────────────
async function loadDashboard() {
    try {
        const [price, money, labor, wages, meta] = await Promise.all([
            fetch('data/price_pressures.json').then(r => r.json()),
            fetch('data/money_matters.json').then(r => r.json()),
            fetch('data/labor.json').then(r => r.json()),
            fetch('data/wages.json').then(r => r.json()),
            fetch('data/metadata.json').then(r => r.json()),
        ]);

        document.getElementById('last-updated-date').textContent = meta.last_updated;

        renderPricePressures(price);
        renderMoneyMatters(money);
        renderLaborMarket(labor);
        renderWages(wages);

    } catch (err) {
        console.error('Dashboard load error:', err);
        document.getElementById('last-updated-date').textContent = 'data unavailable';
    }
}

// ── PRICE PRESSURES ───────────────────────────────────────────────────────────
function renderPricePressures(d) {
    new Chart(document.getElementById('cpi-levels-chart'), {
        type: 'line',
        data: {
            labels: d.dates,
            datasets: [
                lineDataset('United States',     d.us_index,    C.us),
                lineDataset('Texas',             d.texas_index, C.texas),
                lineDataset('Dallas-Fort Worth', d.dfw_index,   C.dfw),
                lineDataset('2% Target Path',    d.target_path, C.target, { dash: [5,4], width: 1.5 }),
            ],
        },
        options: {
            ...BASE_OPTIONS,
            scales: {
                ...BASE_OPTIONS.scales,
                y: { ...BASE_OPTIONS.scales.y, title: { display: true, text: 'Index (Jan 2020 = 100)', font: { size: 11 } } },
            },
        },
    });

    new Chart(document.getElementById('cpi-yoy-chart'), {
        type: 'line',
        data: {
            labels: d.dates,
            datasets: [
                lineDataset('United States',     d.us_yoy,    C.us),
                lineDataset('Texas',             d.texas_yoy, C.texas),
                lineDataset('Dallas-Fort Worth', d.dfw_yoy,   C.dfw),
                lineDataset('2% Target',         d.dates.map(() => 2.0), C.target, { dash: [5,4], width: 1.5 }),
            ],
        },
        options: {
            ...BASE_OPTIONS,
            scales: {
                ...BASE_OPTIONS.scales,
                y: { ...BASE_OPTIONS.scales.y, title: { display: true, text: 'Year-Over-Year Change (%)', font: { size: 11 } } },
            },
        },
    });
}

// ── MONEY MATTERS ─────────────────────────────────────────────────────────────
function renderMoneyMatters(d) {
    new Chart(document.getElementById('rates-chart'), {
        type: 'line',
        data: {
            labels: d.dates,
            datasets: [
                {
                    label: 'Real FFR Range',
                    data: d.real_ffr_upper,
                    borderColor: C.ffr,
                    backgroundColor: 'rgba(229,62,62,0.08)',
                    borderWidth: 1.5,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    fill: '+1',
                    tension: 0.3,
                },
                {
                    label: '',
                    data: d.real_ffr_lower,
                    borderColor: C.ffr,
                    backgroundColor: 'rgba(229,62,62,0.08)',
                    borderWidth: 1.5,
                    pointRadius: 0,
                    fill: false,
                    tension: 0.3,
                },
                lineDataset('Natural Rate — Laubach-Williams (NY Fed)',      d.natural_rate_lw,       C.naturalLW,       { dash: [5,3] }),
                lineDataset('Natural Rate — Median Estimate (Richmond Fed)', d.natural_rate_richmond, C.naturalRichmond, { dash: [5,3] }),
                lineDataset('Zero',  d.dates.map(() => 0), '#cbd5e0', { dash: [2,4], width: 1, points: 0 }),
            ],
        },
        options: {
            ...BASE_OPTIONS,
            plugins: {
                ...BASE_OPTIONS.plugins,
                legend: {
                    ...BASE_OPTIONS.plugins.legend,
                    labels: {
                        ...BASE_OPTIONS.plugins.legend.labels,
                        filter: item => item.text !== '',
                    },
                },
            },
            scales: {
                ...BASE_OPTIONS.scales,
                y: { ...BASE_OPTIONS.scales.y, title: { display: true, text: 'Interest Rate (%)', font: { size: 11 } } },
            },
        },
    });
}

// ── LABOR MARKET ──────────────────────────────────────────────────────────────
function renderLaborMarket(d) {
    new Chart(document.getElementById('unemployment-chart'), {
        type: 'line',
        data: {
            labels: d.dates,
            datasets: [
                lineDataset('Lubbock',           d.lubbock_unemployment, C.lubbock),
                lineDataset('Dallas-Fort Worth', d.dfw_unemployment,     C.dfw),
                lineDataset('Texas',             d.texas_unemployment,   C.texas),
                lineDataset('United States',     d.us_unemployment,      C.us),
            ],
        },
        options: {
            ...BASE_OPTIONS,
            scales: {
                ...BASE_OPTIONS.scales,
                y: { ...BASE_OPTIONS.scales.y, title: { display: true, text: 'Unemployment Rate (%)', font: { size: 11 } } },
            },
        },
    });

    new Chart(document.getElementById('employment-growth-chart'), {
        type: 'line',
        data: {
            labels: d.dates,
            datasets: [
                lineDataset('Lubbock',           d.lubbock_emp_growth, C.lubbock),
                lineDataset('Dallas-Fort Worth', d.dfw_emp_growth,     C.dfw),
                lineDataset('Texas',             d.texas_emp_growth,   C.texas),
                lineDataset('United States',     d.us_emp_growth,      C.us),
            ],
        },
        options: {
            ...BASE_OPTIONS,
            scales: {
                ...BASE_OPTIONS.scales,
                y: { ...BASE_OPTIONS.scales.y, title: { display: true, text: 'Year-Over-Year Growth (%)', font: { size: 11 } } },
            },
        },
    });

    new Chart(document.getElementById('employment-levels-chart'), {
        type: 'line',
        data: {
            labels: d.dates,
            datasets: [
                lineDataset('Lubbock',           d.lubbock_emp_index, C.lubbock),
                lineDataset('Dallas-Fort Worth', d.dfw_emp_index,     C.dfw),
                lineDataset('Texas',             d.texas_emp_index,   C.texas),
                lineDataset('United States',     d.us_emp_index,      C.us),
            ],
        },
        options: {
            ...BASE_OPTIONS,
            scales: {
                ...BASE_OPTIONS.scales,
                y: { ...BASE_OPTIONS.scales.y, title: { display: true, text: 'Index (Jan 2020 = 100)', font: { size: 11 } } },
            },
        },
    });
}

// ── WAGES ─────────────────────────────────────────────────────────────────────
function renderWages(d) {
    new Chart(document.getElementById('wages-levels-chart'), {
        type: 'line',
        data: {
            labels: d.dates,
            datasets: [
                lineDataset('Lubbock',           d.lubbock_wages, C.lubbock, { points: 3 }),
                lineDataset('Dallas-Fort Worth', d.dfw_wages,     C.dfw,     { points: 3 }),
                lineDataset('Texas',             d.texas_wages,   C.texas,   { points: 3 }),
                lineDataset('United States',     d.us_wages,      C.us,      { points: 3 }),
            ],
        },
        options: {
            ...BASE_OPTIONS,
            scales: {
                ...BASE_OPTIONS.scales,
                y: {
                    ...BASE_OPTIONS.scales.y,
                    title: { display: true, text: 'Average Weekly Wages ($)', font: { size: 11 } },
                    ticks: { callback: v => '$' + v.toLocaleString() },
                },
            },
        },
    });

    new Chart(document.getElementById('wages-growth-chart'), {
        type: 'line',
        data: {
            labels: d.dates,
            datasets: [
                lineDataset('Lubbock',           d.lubbock_wage_growth, C.lubbock, { points: 3 }),
                lineDataset('Dallas-Fort Worth', d.dfw_wage_growth,     C.dfw,     { points: 3 }),
                lineDataset('Texas',             d.texas_wage_growth,   C.texas,   { points: 3 }),
                lineDataset('United States',     d.us_wage_growth,      C.us,      { points: 3 }),
            ],
        },
        options: {
            ...BASE_OPTIONS,
            scales: {
                ...BASE_OPTIONS.scales,
                y: { ...BASE_OPTIONS.scales.y, title: { display: true, text: 'Year-Over-Year Growth (%)', font: { size: 11 } } },
            },
        },
    });

    new Chart(document.getElementById('wages-ratio-chart'), {
        type: 'line',
        data: {
            labels: d.dates,
            datasets: [
                lineDataset('Lubbock / Texas',         d.lubbock_texas_ratio, C.texas, { points: 3 }),
                lineDataset('Lubbock / United States', d.lubbock_us_ratio,    C.us,    { points: 3 }),
            ],
        },
        options: {
            ...BASE_OPTIONS,
            scales: {
                ...BASE_OPTIONS.scales,
                y: {
                    ...BASE_OPTIONS.scales.y,
                    title: { display: true, text: 'Ratio', font: { size: 11 } },
                    ticks: { callback: v => (v * 100).toFixed(1) + '%' },
                },
            },
        },
    });
}

// ── INIT ──────────────────────────────────────────────────────────────────────
loadDashboard();
