/* Mounjaro UK Price Index — reads a locally built price index.
   Every price carries its source page and retrieval time. */

const DOSE_ORDER = ['2.5', '5', '7.5', '10', '12.5', '15'];

const HEART = '<svg class="heart" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s-8.4-5.2-8.4-11A4.9 4.9 0 0 1 12 7.2 4.9 4.9 0 0 1 20.4 10c0 5.8-8.4 11-8.4 11z"/></svg>';

const STEP_META = {
  questionnaire: { label: 'online questionnaire', weight: 10 },
  photo:         { label: 'photo upload', weight: 15 },
  repeat_photo:  { label: 'repeat photos later', weight: 15 },
  video:         { label: 'video consultation', weight: 20 },
  id:            { label: 'ID upload', weight: 10 },
  gp:            { label: 'GP / records check', weight: 10 },
  slow:          { label: 'slow turnaround', weight: 5 },
};

const state = { dose: '7.5', sort: 'ease', showUnread: false, data: null, ordering: {}, gphc: {} };

const $ = (sel) => document.querySelector(sel);
const gbp = (v) => '£' + Number(v).toFixed(2).replace(/\.00$/, '');

function easeFor(provider) {
  const o = state.ordering[provider];
  if (!o || !Array.isArray(o.steps) || o.steps.length === 0) return null;
  const penalty = o.steps.reduce((sum, key) => sum + (STEP_META[key]?.weight ?? 0), 0);
  const score = Math.max(5, Math.min(100, 100 - penalty));
  const label = score >= 80 ? 'Easy' : score >= 60 ? 'Moderate' : 'Heavy checks';
  return { score, label, steps: o.steps, approval: o.approval_days };
}

function pricedOf(provider, dose) {
  const p = provider.prices_gbp?.[dose];
  return typeof p === 'number' ? p : null;
}

// Every listed pharmacy appears at every dose. Plenty of them publish only their
// starting dose, so those rows carry missingDose:true and say which doses they do
// list. Dropping them made the list shorter than the headline count and read as a
// missing-pharmacy bug rather than a missing price.
function doseBuckets(dose) {
  const all = state.data?.providers ?? [];
  const withPrice = all.map((p) => ({ ...p, price: pricedOf(p, dose) }));
  return {
    priced: withPrice.filter((p) => p.price !== null),
    missing: withPrice
      .filter((p) => p.price === null)
      .map((p) => ({ ...p, missingDose: true })),
  };
}

function sortPriced(rows) {
  const p = (r) => r.price;
  const copy = rows.slice();
  if (state.sort === 'ease') {
    return copy.sort((a, b) => {
      const ea = easeFor(a.provider)?.score ?? -1;
      const eb = easeFor(b.provider)?.score ?? -1;
      return eb - ea || p(a) - p(b);
    });
  }
  if (state.sort === 'rating') {
    return copy.sort((a, b) => {
      const ra = Number(state.ordering[a.provider]?.rating ?? -1);
      const rb = Number(state.ordering[b.provider]?.rating ?? -1);
      return rb - ra || p(a) - p(b);
    });
  }
  return copy.sort((a, b) => {
    const diff = p(a) - p(b);
    if (Math.abs(diff) > 0.5) return diff;
    return (easeFor(b.provider)?.score ?? -1) - (easeFor(a.provider)?.score ?? -1);
  });
}

function sortedProviders(dose) {
  const { priced, missing } = doseBuckets(dose);
  const rows = sortPriced(priced).concat(missing);
  if (!state.showUnread) return rows;

  const seen = new Set(rows.map((r) => r.provider));
  const unread = (state.data?.unread ?? [])
    .filter((u) => !seen.has(u.provider))
    .map((u) => ({ ...u, price: null, prices_gbp: {} }));
  return rows.concat(unread);
}

function renderDoses() {
  $('#dose-bar').innerHTML = DOSE_ORDER.map((d) => `
    <button class="dose${d === state.dose ? ' active' : ''}" data-dose="${d}" type="button">${d}mg</button>
  `).join('');
  $('#dose-bar').querySelectorAll('.dose').forEach((btn) => {
    btn.addEventListener('click', () => {
      state.dose = btn.dataset.dose;
      renderDoses();
      renderLowest();
      renderStats();
      renderList();
      afterRender();
      window.scrollTo({ top: $('#list-title').offsetTop - 90, behavior: 'smooth' });
    });
  });
}

function renderLowest() {
  if (!$('#lowest-grid')) return;
  const cards = DOSE_ORDER.map((dose) => {
    const rows = providersForDose(dose).sort((a, b) => a.price - b.price);
    if (!rows.length) {
      return `<div class="low-card"><span class="low-dose">${dose}mg</span>
        <span class="low-price" style="color:var(--ink-soft);font-size:15px">not verified</span>
        <span class="low-pharm">no price found yet</span></div>`;
    }
    const best = rows[0];
    return `<button class="low-card${dose === state.dose ? ' selected' : ''}" data-dose="${dose}" type="button">
      <span class="low-dose">${dose}mg</span>
      <span class="low-price">${gbp(best.price)}</span>
      <span class="low-pharm">${best.provider}</span>
    </button>`;
  }).join('');
  $('#lowest-grid').innerHTML = cards;
  $('#lowest-grid').querySelectorAll('.low-card[data-dose]').forEach((el) => {
    el.addEventListener('click', () => {
      state.dose = el.dataset.dose;
      renderDoses(); renderLowest(); renderStats(); renderList(); afterRender();
      window.scrollTo({ top: $('#list-title').offsetTop - 90, behavior: 'smooth' });
    });
  });
}

function card(provider, index) {
  const ease = easeFor(provider.provider);
  const o = state.ordering[provider.provider] ?? {};
  const isTop = index === 0;
  const missing = Boolean(provider.missingDose);
  const easeClass = ease ? (ease.score >= 80 ? 'good' : ease.score >= 60 ? '' : 'hard') : '';
  const stepText = ease?.steps?.length
    ? ease.steps.map((k) => STEP_META[k]?.label ?? k).join(', ')
    : null;

  const badges = [];
  if (ease) badges.push(`<span class="badge ease ${easeClass}">Ease ${ease.score}</span>`);
  if (o.rating) {
    const adv = o.advertised_rating;
    const note = adv
      ? ` title="${Number(adv.score).toFixed(1)} from ${Number(adv.count).toLocaleString('en-GB')} on their own site (${adv.platform}); Trustpilot, an independent platform, shows ${Number(o.rating).toFixed(1)} from ${Number(o.reviews || 0).toLocaleString('en-GB')}"`
      : '';
    badges.push(`<span class="badge rating"${note}>★ ${Number(o.rating).toFixed(1)}${o.reviews ? ' · ' + Number(o.reviews).toLocaleString('en-GB') : ''}</span>`);
  }
  // no discount codes, no offers: special offers on POM prices may not be promoted
  if (o.delivery) badges.push(`<span class="badge delivery">${o.delivery}</span>`);
  if (missing) badges.push(`<span class="badge gated">No ${state.dose}mg price</span>`);
  else if (provider.price === null) badges.push('<span class="badge gated">No published price</span>');

  const g = state.gphc[provider.provider];
  if (g?.verified) {
    const regName = g.registered_name && g.registered_name.toLowerCase() !== provider.provider.toLowerCase()
      ? ` title="Registered as ${g.registered_name}"` : '';
    const href = g.number ? `https://www.pharmacyregulation.org/registers/pharmacy/registrationnumber/${g.number}` : '';
    badges.push(`<a class="badge gphc" href="${href}" target="_blank" rel="noopener"${regName}>GPhC ${g.number}</a>`);
  }

  const host = (() => {
    try { return new URL(provider.source_url).hostname.replace(/^www\./, ''); }
    catch { return provider.domain || ''; }
  })();

  const unreadNote = (() => {
    const why = (provider.reason || '').toLowerCase();
    if (why.includes('consultation')) return 'asks for a consultation first';
    if (why.includes('did not load')) return 'their site wouldn’t load for us';
    return 'no price found';
  })();
  const listed = Object.keys(provider.prices_gbp ?? {})
    .sort((a, b) => DOSE_ORDER.indexOf(a) - DOSE_ORDER.indexOf(b));
  const doseList = !listed.length
    ? 'no dose published'
    : listed.length === 1
      ? `lists ${listed[0]}mg only`
      : `lists ${listed.slice(0, -1).join(', ')}mg and ${listed[listed.length - 1]}mg`;

  const priceBlock = missing
    ? `<div class="card-price"><strong class="no-price">No ${state.dose}mg</strong><span>${doseList}</span></div>`
    : provider.price === null
      ? `<div class="card-price"><strong class="no-price">No price</strong><span>${unreadNote}</span></div>`
      : `<div class="card-price"><strong>${gbp(provider.price)}</strong><span>${state.dose}mg</span></div>`;

  return `<article class="card${isTop ? ' top' : ''}${provider.price === null ? ' unread' : ''}${missing ? ' missing-dose' : ''}" style="--i:${Math.min(index, 14)}">
    <div class="card-head">
      <div style="display:flex;gap:8px;min-width:0">
        <span class="rank">${missing ? '—' : index + 1}</span>
        <div style="min-width:0">
          <h3 class="card-name">${provider.provider}</h3>
          ${stepText ? `<p class="steps"><b>Asks for:</b> ${stepText}</p>` : ''}
        </div>
      </div>
      ${priceBlock}
    </div>
    <div class="badges">${badges.join('')}</div>
    <div class="card-foot">
      <span class="meta">${host}${provider.retrieved_at ? ' · read ' + provider.retrieved_at.slice(0, 10) : ''}</span>
      ${provider.source_url ? `<a class="visit" href="${provider.source_url}" target="_blank" rel="noopener">Check live price</a>` : ''}
    </div>
  </article>`;
}

function pulseList() {
  const el = $('#list');
  if (!el) return;
  el.classList.remove('swap');
  void el.offsetWidth;      // restart the animation on repeat renders
  el.classList.add('swap');
}

function renderList() {
  const { priced, missing } = doseBuckets(state.dose);
  const total = priced.length + missing.length;
  const rows = sortedProviders(state.dose);
  const pricedRows = rows.filter((r) => r.price !== null);
  const missingRows = rows.filter((r) => r.missingDose);
  const unreadRows = rows.filter((r) => r.price === null && !r.missingDose);

  $('#list-title').textContent = `Every pharmacy, ranked — ${state.dose}mg`;
  $('#sort-note').textContent = state.sort === 'price'
    ? 'Lowest published price first — factual ordering, not a recommendation.'
    : state.sort === 'ease'
      ? 'Least hassle first, from what each pharmacy admits it asks for.'
      : 'Best customer rating first. Pharmacies with no rating sit at the bottom.';

  const coverage = $('#coverage-line');
  if (coverage) {
    coverage.textContent = `All ${total} listed pharmacies appear below. ${priced.length} publish a ${state.dose}mg price`
      + (missing.length ? `, ${missing.length} don’t.` : '.');
  }

  if (!pricedRows.length) {
    $('#list').innerHTML = '<p class="empty">' + HEART + 'Nothing published at this dose yet. That’s a gap in their pricing, not in the index — new pages are read every week.</p>';
    return;
  }

  const gap = missingRows.length
    ? `<div class="dose-gap">
        <p class="dose-gap-title">${missingRows.length} of ${total} publish no ${state.dose}mg price</p>
        <p class="fine">They stay on the list, with the doses they do price. A missing dose is their gap, not a better deal.</p>
      </div>` + missingRows.map(card).join('')
    : '';

  $('#list').innerHTML = pricedRows.map(card).join('')
    + gap
    + (unreadRows.length ? `<p class="fine list-foot">These ${unreadRows.length} publish nothing until you finish their consultation. They’re here because you might already use one — a hidden price is not an expensive one.</p>` : '');
}

function afterRender() { pulseList(); }

function renderStats() {
  const all = state.data?.providers ?? [];
  const withPrice = all.filter((p) => Object.keys(p.prices_gbp ?? {}).length);
  const doses = new Set();
  withPrice.forEach((p) => Object.keys(p.prices_gbp ?? {}).forEach((d) => doses.add(d)));
  // The headline numbers follow the selected dose. A fixed "68" above a 48-row
  // list reads as missing pharmacies; these now match what is actually priced.
  const atDose = withPrice.filter((p) => pricedOf(p, state.dose) !== null);
  const gphcN = atDose.filter((p) => state.gphc?.[p.provider]?.verified).length;
  const set = (sel, value) => { const el = $(sel); if (el) el.textContent = value; };
  set('#stat-pharmacies', atDose.length);
  set('#stat-pharmacies-label', `pharmacies · ${state.dose}mg`);
  set('#stat-doses', doses.size);
  set('#stat-gphc', gphcN || '—');

  const whenRaw = state.data?.generated_at?.slice(0, 10) ?? '';
  const when = whenRaw
    ? new Date(whenRaw + 'T12:00:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
    : '';
  const checkedEl = $('#checked-line');
  if (checkedEl) {
    if (when) {
      checkedEl.innerHTML = HEART + `Read from ${withPrice.length} pharmacy pages on ${when} · every price links to its source`;
    } else {
      checkedEl.textContent = '';
    }
  }
  $('#method-line').textContent = state.data?.method ?? '';
  $('#attribution').textContent = state.data?.attribution ?? '';
}

async function boot() {
  const pill = document.querySelector('.live');
  pill?.classList.add('syncing');   // the sweep tells you a pull is happening
  try {
    const [priceRes, orderRes, gphcRes] = await Promise.all([
      fetch('data/price-index.json', { cache: 'no-store' }),
      fetch('data/ordering.json', { cache: 'no-store' }).catch(() => null),
      fetch('data/gphc.json', { cache: 'no-store' }).catch(() => null),
    ]);
    state.data = await priceRes.json();
    if (orderRes && orderRes.ok) {
      const o = await orderRes.json();
      state.ordering = o.providers ?? {};
    }
    if (gphcRes && gphcRes.ok) {
      const g = await gphcRes.json();
      state.gphc = g.providers ?? {};
    }
  } catch (err) {
    $('#list').innerHTML = '<p class="empty">The index didn’t load. Check your connection, then reopen — the data is served from the app, not the cloud.</p>';
    return;
  }

  pill?.classList.remove('syncing');
  renderStats();
  renderDoses();
  renderLowest();
  renderList();
  afterRender();


  $('#sort-bar').querySelectorAll('.seg').forEach((btn) => {
    btn.addEventListener('click', () => {
      state.sort = btn.dataset.sort;
      $('#sort-bar').querySelectorAll('.seg').forEach((b) => b.classList.toggle('active', b === btn));
      renderList();
      afterRender();
    });
  });

  const toggle = $('#unread-toggle');
  const unreadTotal = (state.data?.unread ?? []).length;
  $('#unread-count').textContent = unreadTotal;
  if (!unreadTotal) toggle.hidden = true;
  toggle.addEventListener('click', () => {
    state.showUnread = !state.showUnread;
    toggle.setAttribute('aria-pressed', String(state.showUnread));
    toggle.classList.toggle('on', state.showUnread);
    renderList();
    afterRender();
  });

  const sheet = $('#about-sheet');
  const aboutBtn = $('#about-btn');
  if (sheet && aboutBtn) {
    aboutBtn.addEventListener('click', () => { sheet.hidden = false; });
    $('#sheet-close')?.addEventListener('click', () => { sheet.hidden = true; });
    sheet.addEventListener('click', (e) => { if (e.target === sheet) sheet.hidden = true; });
  }
}

boot();
