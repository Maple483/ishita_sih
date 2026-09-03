/* PFZ Advisory presentation-only refinements.
 * Removes the redundant "How this works" footer and increases readable type/spacing
 * inside PFZ Advisory only. No data, ranking, API or other UI behavior is changed.
 */
(function () {
  const STYLE_ID = 'pfz-advisory-ui-enhancements';
  const ROOT_CLASS = 'pfz-advisory-ui';

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
      if (text.startsWith('How this works')) section.remove();
    });

    addStyles();
  }

  const observer = new MutationObserver(enhance);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  enhance();
})();
