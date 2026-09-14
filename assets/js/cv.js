const reader = document.querySelector('.cv-reader');

if (reader) {
  const status = reader.querySelector('.cv-reader-status');
  const toolbar = reader.querySelector('.cv-toolbar');
  const viewport = reader.querySelector('.cv-page-viewport');
  const controls = [...toolbar.querySelectorAll('button')];
  const pages = [];
  const sectionsToggle = reader.querySelector('.cv-sections-toggle');
  const sectionsPanel = reader.querySelector('.cv-sections-panel');
  const sectionButtons = [...sectionsPanel.querySelectorAll('[data-cv-heading]')];
  const destinations = new Map();
  let pdf, zoom = 1, rendering = false, rerender = false;

  function setSectionsOpen(open) {
    sectionsToggle.setAttribute('aria-expanded', String(open));
    sectionsPanel.hidden = !open;
  }

  async function indexSections() {
    const normalize = text => text.replace(/\s+/g, ' ').trim().toUpperCase();
    for (const { page, canvas } of pages) {
      const text = await page.getTextContent();
      const lines = new Map();
      // PDF text may split a heading into several items; join items on its baseline.
      for (const item of text.items) {
        if (!item.str?.trim()) continue;
        const key = Math.round(item.transform[5]);
        if (!lines.has(key)) lines.set(key, []);
        lines.get(key).push(item);
      }
      for (const items of lines.values()) {
        items.sort((a, b) => a.transform[4] - b.transform[4]);
        const heading = normalize(items.map(item => item.str).join(' '));
        const button = sectionButtons.find(button => normalize(button.dataset.cvHeading) === heading);
        if (!button || destinations.has(button)) continue;
        const first = items[0];
        const base = page.getViewport({ scale: 1 });
        const [, top] = base.convertToViewportPoint(first.transform[4], first.transform[5] + first.height);
        destinations.set(button, { canvas, fraction: Math.max(0, top / base.height) });
        button.hidden = false;
      }
    }
    sectionsToggle.hidden = destinations.size === 0;
  }

  sectionsToggle.addEventListener('click', () => setSectionsOpen(sectionsPanel.hidden));
  sectionsPanel.addEventListener('click', event => {
    const destination = destinations.get(event.target.closest('button'));
    if (!destination) return;
    setSectionsOpen(false);
    const { canvas, fraction } = destination;
    const bounds = canvas.getBoundingClientRect();
    // Leave room for the floating Sections button above the destination heading.
    const top = bounds.top - viewport.getBoundingClientRect().top + viewport.scrollTop + fraction * bounds.height - 76;
    viewport.scrollTo({ top, left: 0 });
    viewport.focus({ preventScroll: true });
  });
  reader.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !sectionsPanel.hidden) {
      setSectionsOpen(false);
      sectionsToggle.focus({ preventScroll: true });
    }
  });
  document.addEventListener('click', event => {
    if (!sectionsPanel.hidden && !sectionsPanel.contains(event.target) && !sectionsToggle.contains(event.target)) {
      setSectionsOpen(false);
    }
  });

  function updateControls() {
    controls.forEach(button => {
      const action = button.dataset.cvAction;
      button.disabled = rendering || (action === 'out' && zoom <= 0.75)
        || (action === 'in' && zoom >= 2);
    });
  }

  async function renderPages() {
    if (rendering) { rerender = true; return; }
    rendering = true;
    updateControls();
    const scrollFraction = viewport.scrollTop / Math.max(1, viewport.scrollHeight - viewport.clientHeight);
    try {
      const padding = parseFloat(getComputedStyle(viewport).paddingLeft) * 2;
      const width = viewport.clientWidth - padding;
      const density = Math.min(window.devicePixelRatio || 1, 2);
      // Size every page first so the scroll position remains stable while rendering.
      const layouts = pages.map(({ page, canvas }) => {
        const scale = width / page.getViewport({ scale: 1 }).width * zoom;
        const pageViewport = page.getViewport({ scale });
        canvas.width = Math.floor(pageViewport.width * density);
        canvas.height = Math.floor(pageViewport.height * density);
        canvas.style.width = `${pageViewport.width}px`;
        canvas.style.height = `${pageViewport.height}px`;
        return { page, canvas, pageViewport };
      });
      viewport.scrollTop = scrollFraction * Math.max(0, viewport.scrollHeight - viewport.clientHeight);
      for (const { page, canvas, pageViewport } of layouts) {
        await page.render({ canvasContext: canvas.getContext('2d'), viewport: pageViewport,
          transform: [density, 0, 0, density, 0, 0] }).promise;
      }
      status.hidden = true;
    } catch (error) {
      status.textContent = 'The preview could not be displayed. Please use View PDF above.';
      status.hidden = false;
    } finally {
      rendering = false;
      updateControls();
      if (rerender) { rerender = false; renderPages(); }
    }
  }

  try {
    const pdfjs = await import('../vendor/pdfjs/pdf.min.mjs');
    pdfjs.GlobalWorkerOptions.workerSrc = new URL('../vendor/pdfjs/pdf.worker.min.mjs', import.meta.url).href;
    pdf = await pdfjs.getDocument({ url: reader.dataset.pdfUrl }).promise;
    for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber++) {
      const page = await pdf.getPage(pageNumber);
      const canvas = document.createElement('canvas');
      canvas.setAttribute('role', 'img');
      canvas.setAttribute('aria-label', `CV page ${pageNumber} of ${pdf.numPages}. Use View PDF to read or select the document text.`);
      viewport.append(canvas);
      pages.push({ page, canvas });
    }
    reader.querySelector('[data-cv-total]').textContent = pdf.numPages;
    toolbar.hidden = false;
    viewport.hidden = false;
    await renderPages();
    // A PDF without bookmarks can still provide section navigation from its headings.
    indexSections().catch(() => { sectionsToggle.hidden = true; });
    toolbar.addEventListener('click', event => {
      const button = event.target.closest('button');
      if (!button || button.disabled) return;
      switch (button.dataset.cvAction) {
        case 'out': zoom = Math.max(0.75, zoom - 0.25); break;
        case 'in': zoom = Math.min(2, zoom + 0.25); break;
        case 'fit': zoom = 1; break;
      }
      viewport.scrollLeft = 0;
      renderPages();
    });
    let resizeTimer;
    let lastWidth = reader.clientWidth;
    const observer = new ResizeObserver(() => {
      if (reader.clientWidth === lastWidth) return;
      lastWidth = reader.clientWidth;
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(renderPages, 150);
    });
    observer.observe(reader);
  } catch (error) {
    status.textContent = 'The preview could not be loaded. Please use View PDF above.';
  }
}
