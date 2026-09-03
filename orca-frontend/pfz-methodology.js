/* PFZ-only methodology explanation.
 * Adds transparency to the existing PFZ Advisory card without changing
 * ranking logic, backend behavior, or any other part of the application.
 */
(function () {
  const MARKER = 'data-pfz-methodology-card';

  function makeCard() {
    const card = document.createElement('section');
    card.setAttribute(MARKER, 'true');
    card.className = 'rounded-lg border border-slate-800 bg-slate-950/70 p-3 text-[9px] leading-relaxed text-slate-400';
    card.innerHTML = `
      <div class="mb-2 flex items-center gap-1 font-bold text-slate-300">
        <span class="text-emerald-400">●</span>
        How the PFZ advisory is generated
      </div>
      <p class="mb-2">
        This is a <b class="text-slate-200">decision-support ranking</b>, not a machine-learning prediction of fish abundance.
        Candidate PFZ locations come from the advisory catalogue and are ranked for the entered fisherman location.
      </p>
      <div class="grid gap-1.5 sm:grid-cols-2">
        <div><b class="text-slate-200">1. Proximity — 55%</b><br/>Closer advisory locations receive a higher base score using the distance from the fisherman.</div>
        <div><b class="text-slate-200">2. Advisory freshness — 45%</b><br/>More recent/current forecast-validity periods receive a higher base score; older advisories are progressively down-weighted.</div>
        <div><b class="text-slate-200">3. Wave height adjustment</b><br/>Calmer sea conditions improve the score; high waves reduce it.</div>
        <div><b class="text-slate-200">4. SST adjustment</b><br/>A live SST value in the broad 22–30°C range receives a small positive adjustment.</div>
      </div>
      <p class="mt-2 text-slate-500">
        Bearing, direction, advisory distance, depth, wave direction/period and ocean-current values are shown as operational context for the fisherman; they are not independent ranking weights in the current advisory score.
      </p>
      <div class="mt-2 rounded-md border border-amber-500/20 bg-amber-500/5 px-2.5 py-2 text-amber-300/90">
        <b>Important:</b> This advisory identifies relatively preferable PFZ locations from the available advisory and environmental information.
        It <b>does not guarantee fish presence, catch quantity, or safety</b>. Actual catch depends on many factors not modeled here, including fish movement, fishing effort and gear, weather, local sea conditions, and other ecological and operational factors. Fishermen should use the advisory together with official safety/weather guidance and their own judgement.
      </div>
    `;
    return card;
  }

  function install() {
    const sections = Array.from(document.querySelectorAll('section'));
    const howItWorks = sections.find((section) =>
      section.textContent && section.textContent.trim().startsWith('How this works')
    );
    if (!howItWorks || howItWorks.parentElement?.querySelector(`[${MARKER}]`)) return;
    howItWorks.insertAdjacentElement('afterend', makeCard());
  }

  const observer = new MutationObserver(() => install());
  observer.observe(document.documentElement, { childList: true, subtree: true });
  install();
})();
