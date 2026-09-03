/* PFZ Advisory presentation-only refinements.
 * Removes the redundant "How this works" footer and increases readable type/spacing
 * inside PFZ Advisory only. No data, ranking, API or other UI behavior is changed.
 */
(function () {
  const STYLE_ID = 'pfz-advisory-ui-enhancements';
  const ROOT_CLASS = 'pfz-advisory-ui';
  const RANKED_CLASS = 'pfz-ranked-section';

  function addStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .${ROOT_CLASS} { font-size: 14px; }
      .${ROOT_CLASS} [class*="text-[9px]"] { font-size: 11px !important; line-height: 1.5 !important; }
      .${ROOT_CLASS} [class*="text-[10px]"] { font-size: 12px !important; line-height: 1.45 !important; }
      .${ROOT_CLASS} [class*="text-[11px]"] { font-size: 13px !important; line-height: 1.5 !important; }
      .${ROOT_CLASS} [class*="text-xs"] { font-size: 13px !important; line-height: 1.5 !important; }
      .${ROOT_CLASS} [class*="text-sm"] { font-size: 15px !important; }
      .${ROOT_CLASS} > section,
      .${ROOT_CLASS} > div { padding: 16px !important; }
      .${ROOT_CLASS} .h-72 { height: 330px !important; }
      .${ROOT_CLASS} .space-y-4 > :not([hidden]) ~ :not([hidden]) { margin-top: 1.15rem !important; }
      .${ROOT_CLASS} input,
      .${ROOT_CLASS} select { font-size: 14px !important; padding-top: 10px !important; padding-bottom: 10px !important; }
      .${ROOT_CLASS} button { font-size: 13px !important; }

      /* Make the Ranked PFZ advisories block and every item underneath it noticeably larger. */
      .${RANKED_CLASS} { padding: 20px !important; }
      .${RANKED_CLASS} > div:first-child { margin-bottom: 16px !important; }
      .${RANKED_CLASS} > div:first-child > div:first-child { font-size: 14px !important; line-height: 1.4 !important; }
      .${RANKED_CLASS} > div:first-child > div:last-child { font-size: 12px !important; }
      .${RANKED_CLASS} > div.space-y-2 { gap: 12px !important; }
      .${RANKED_CLASS} > div.space-y-2 > div { padding: 16px !important; }
      .${RANKED_CLASS} > div.space-y-2 > div span.rounded-full { font-size: 12px !important; padding: 4px 9px !important; }
      .${RANKED_CLASS} > div.space-y-2 > div span.truncate { font-size: 15px !important; line-height: 1.4 !important; }
      .${RANKED_CLASS} > div.space-y-2 > div svg { width: 14px !important; height: 14px !important; }
      .${RANKED_CLASS} > div.space-y-2 > div .text-right > div:first-child { font-size: 16px !important; line-height: 1.35 !important; }
      .${RANKED_CLASS} > div.space-y-2 > div .text-right > div:last-child { font-size: 12px !important; }
      .${RANKED_CLASS} > div.space-y-2 > div > div:nth-child(2) { font-size: 12px !important; line-height: 1.5 !important; }
      .${RANKED_CLASS} > div.space-y-2 > div > div:nth-child(3) { font-size: 12px !important; line-height: 1.5 !important; }
      .${RANKED_CLASS} > div.space-y-2 > div > div:nth-child(3) b { font-size: 13px !important; }
      .${RANKED_CLASS} > div.space-y-2 > div > div:last-child { font-size: 12px !important; line-height: 1.55 !important; }
    `;
    document.head.appendChild(style);
  }

  function enhance() {
    const headings = Array.from(document.querySelectorAll('div, h1, h2, h3, span'));
    const title = headings.find((el) =>
      el.textContent && el.textContent.trim() === 'Potential Fishing Zone Advisory'
    );
    if (!title) return;

    const root = title.closest('div.space-y-4') || title.parentElement?.parentElement?.parentElement;
    if (!root) return;
    root.classList.add(ROOT_CLASS);

    root.querySelectorAll('section').forEach((section) => {
      const text = section.textContent?.trim() || '';
      if (text.startsWith('How this works')) {
        section.remove();
        return;
      }
      if (text.startsWith('Ranked PFZ advisories')) {
        section.classList.add(RANKED_CLASS);
      }
    });

    addStyles();
  }

  const observer = new MutationObserver(enhance);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  enhance();
})();
