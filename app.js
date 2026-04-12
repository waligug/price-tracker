const productsEl = document.getElementById('products');
const filterEl = document.getElementById('site-filter');

async function loadConfig() {
  const res = await fetch('config.json');
  return res.json();
}

async function loadData(productId) {
  try {
    const res = await fetch(`data/${productId}.json`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

function formatPrice(price) {
  return '$' + price.toLocaleString('en-CA', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function renderCard(product, data) {
  const card = document.createElement('div');
  card.className = 'product-card';
  card.dataset.site = product.site;

  const history = data ? data.history : [];
  const current = history.length > 0 ? history[history.length - 1].price : null;
  const previous = history.length > 1 ? history[history.length - 2].price : null;

  let changeHtml = '';
  if (current !== null && previous !== null) {
    const diff = current - previous;
    const pct = ((diff / previous) * 100).toFixed(1);
    if (diff < 0) {
      changeHtml = `<span class="price-change down">${pct}%</span>`;
    } else if (diff > 0) {
      changeHtml = `<span class="price-change up">+${pct}%</span>`;
    } else {
      changeHtml = `<span class="price-change same">no change</span>`;
    }
  }

  card.innerHTML = `
    <h2><a href="${product.url}" target="_blank" rel="noopener">${product.name}</a></h2>
    <div class="product-meta">
      <span>${product.site}</span>
      <span>${history.length} data point${history.length !== 1 ? 's' : ''}</span>
    </div>
    <div>
      <span class="product-price">${current !== null ? formatPrice(current) : 'No data yet'}</span>
      ${changeHtml}
    </div>
    <div class="chart-container"><canvas></canvas></div>
  `;

  productsEl.appendChild(card);

  if (history.length > 0) {
    const canvas = card.querySelector('canvas');
    new Chart(canvas, {
      type: 'line',
      data: {
        labels: history.map(h => h.date),
        datasets: [{
          label: 'Price',
          data: history.map(h => h.price),
          borderColor: '#58a6ff',
          backgroundColor: 'rgba(88, 166, 255, 0.1)',
          fill: true,
          tension: 0.3,
          pointRadius: 3,
          pointBackgroundColor: '#58a6ff'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: ctx => formatPrice(ctx.parsed.y)
            }
          }
        },
        scales: {
          x: {
            type: 'time',
            time: { unit: 'day', tooltipFormat: 'MMM d, yyyy' },
            ticks: { color: '#8b949e', maxTicksLimit: 8 },
            grid: { color: '#21262d' }
          },
          y: {
            ticks: {
              color: '#8b949e',
              callback: v => '$' + v
            },
            grid: { color: '#21262d' }
          }
        }
      }
    });
  }

  return card;
}

async function init() {
  const config = await loadConfig();
  const sites = new Set();

  for (const product of config.products) {
    sites.add(product.site);
    const data = await loadData(product.id);
    renderCard(product, data);
  }

  // Populate site filter
  for (const site of sites) {
    const opt = document.createElement('option');
    opt.value = site;
    opt.textContent = site;
    filterEl.appendChild(opt);
  }

  filterEl.addEventListener('change', () => {
    const val = filterEl.value;
    document.querySelectorAll('.product-card').forEach(card => {
      card.style.display = (val === 'all' || card.dataset.site === val) ? '' : 'none';
    });
  });
}

init();
