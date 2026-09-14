(function () {
  function initializePublications() {
    const root = document.querySelector("[data-publication-list]");
    if (!root) return;

    const papers = Array.from(root.querySelectorAll("[data-publication]"));
    const years = Array.from(root.querySelectorAll("[data-publication-year]"));
    const filters = Array.from(root.querySelectorAll("[data-topic-filter]"));
    const controls = root.querySelector("[data-publication-filters]");
    const filterStatus = root.querySelector("[data-filter-status]");
    const search = root.querySelector("[data-publication-search]");
    const searchControls = root.querySelector("[data-publication-search-controls]");
    const clearSearch = root.querySelector("[data-search-clear]");
    let selectedTopic = "all";

    function normalizeSearch(text) {
      return text.normalize("NFKC").toLowerCase()
        .replace(/[^\p{L}\p{N}\p{M}]+/gu, " ").trim();
    }

    const searchableText = new Map(papers.map(function (paper) {
      return [paper, normalizeSearch(paper.dataset.searchText || paper.textContent || "")];
    }));

    function applyFilters() {
      const terms = normalizeSearch(search ? search.value : "").split(/\s+/).filter(Boolean);
      let visible = 0;
      papers.forEach(function (paper) {
        const topics = (paper.dataset.topics || "").split(/\s+/);
        const matchesTopic = selectedTopic === "all" || topics.includes(selectedTopic);
        const matchesSearch = terms.every(function (term) {
          const text = searchableText.get(paper);
          // Short abbreviations should not match fragments of unrelated words.
          return /^[a-z]{1,2}$/.test(term)
            ? (" " + text + " ").includes(" " + term + " ")
            : text.includes(term);
        });
        paper.hidden = !matchesTopic || !matchesSearch;
        if (!paper.hidden) visible += 1;
      });
      years.forEach(function (year) {
        year.hidden = !Array.from(year.querySelectorAll("[data-publication]"))
          .some(function (paper) { return !paper.hidden; });
      });
      filters.forEach(function (button) {
        button.setAttribute("aria-pressed", String(button.dataset.topicFilter === selectedTopic));
      });
      if (filterStatus) {
        filterStatus.textContent = "Showing " + visible + " of " + papers.length + " papers"
          + (visible === 0 ? ". No publications found. Try another search or topic." : "");
      }
      if (clearSearch) clearSearch.hidden = !search || search.value.length === 0;
    }

    if (controls && filters.length) {
      filters.forEach(function (button) {
        button.addEventListener("click", function () {
          selectedTopic = button.dataset.topicFilter;
          applyFilters();
        });
      });
      controls.hidden = false;
    }

    if (search) {
      search.addEventListener("input", applyFilters);
      search.addEventListener("search", applyFilters);
      if (clearSearch) {
        clearSearch.addEventListener("click", function () {
          search.value = "";
          applyFilters();
          search.focus();
        });
      }
      if (searchControls) searchControls.hidden = false;
    }

    if ((controls && filters.length) || search) {
      applyFilters();
      if (filterStatus) filterStatus.hidden = false;
    }

    root.querySelectorAll("[data-abstract-toggle]").forEach(function (button) {
      const panel = document.getElementById(button.getAttribute("aria-controls"));
      if (!panel || !root.contains(panel)) return;
      panel.hidden = true;
      button.setAttribute("aria-expanded", "false");
      button.hidden = false;
      button.addEventListener("click", function () {
        panel.hidden = !panel.hidden;
        button.setAttribute("aria-expanded", String(!panel.hidden));
      });
    });

    const dialog = document.getElementById("publication-bibtex-dialog");
    if (!dialog || typeof dialog.showModal !== "function" || typeof window.fetch !== "function") return;

    const closeButton = dialog.querySelector("[data-bibtex-close]");
    const title = dialog.querySelector("[data-bibtex-title]");
    const content = dialog.querySelector("[data-bibtex-content]");
    const status = dialog.querySelector("[data-bibtex-status]");
    const copyButton = dialog.querySelector("[data-bibtex-copy]");
    const download = dialog.querySelector("[data-bibtex-download]");
    if (!closeButton || !title || !content || !status || !copyButton || !download) return;

    const copyLabel = copyButton.textContent;
    let opener = null;
    let requestId = 0;
    let controller = null;
    let bibtex = "";
    let copyTimer = null;

    function resetCopyFeedback() {
      window.clearTimeout(copyTimer);
      copyTimer = null;
      copyButton.textContent = copyLabel;
    }

    function cancelRequest() {
      requestId += 1;
      if (controller) controller.abort();
      controller = null;
      bibtex = "";
      copyButton.disabled = true;
      resetCopyFeedback();
      dialog.removeAttribute("aria-busy");
    }

    async function loadBibtex(url, id) {
      const options = { credentials: "same-origin", redirect: "error" };
      if (controller) options.signal = controller.signal;
      try {
        const response = await window.fetch(url.href, options);
        if (!response.ok) throw new Error("BibTeX request failed.");
        const text = await response.text();
        if (!text.trim()) throw new Error("The BibTeX file is empty.");
        if (id !== requestId || !dialog.open) return;
        bibtex = text;
        content.textContent = text;
        copyButton.disabled = false;
        status.textContent = "Ready to copy or download.";
      } catch (error) {
        if (id !== requestId || !dialog.open) return;
        content.textContent = "";
        status.textContent = "Could not load BibTeX. Use Download to open the original file.";
      } finally {
        if (id === requestId && dialog.open) dialog.removeAttribute("aria-busy");
      }
    }

    root.querySelectorAll("a[data-bibtex-link]").forEach(function (link) {
      link.addEventListener("click", function (event) {
        if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey
            || event.shiftKey || event.altKey) return;
        let url;
        try {
          url = new URL(link.href, document.baseURI);
        } catch (error) {
          return;
        }
        if (url.origin !== window.location.origin || !/^https?:$/.test(url.protocol)) return;

        // Keep the original link usable if the dialog cannot be opened.
        try {
          if (!dialog.open) dialog.showModal();
        } catch (error) {
          return;
        }
        event.preventDefault();
        cancelRequest();
        opener = link;
        title.textContent = link.dataset.paperTitle || "BibTeX";
        content.textContent = "";
        status.textContent = "Loading BibTeX…";
        download.href = url.href;
        download.setAttribute("download", url.pathname.split("/").pop().replace(/\.txt$/i, ".bib"));
        download.hidden = false;
        dialog.setAttribute("aria-busy", "true");
        controller = typeof window.AbortController === "function" ? new AbortController() : null;
        loadBibtex(url, requestId);
      });
    });

    copyButton.addEventListener("click", async function () {
      if (!dialog.open || !bibtex || copyButton.disabled) return;
      const id = requestId;
      const text = bibtex;
      resetCopyFeedback();
      copyButton.disabled = true;
      try {
        if (!navigator.clipboard || typeof navigator.clipboard.writeText !== "function") {
          throw new Error("Clipboard access is unavailable.");
        }
        await navigator.clipboard.writeText(text);
        if (id !== requestId || !dialog.open) return;
        copyButton.textContent = "Copied";
        status.textContent = "BibTeX copied to clipboard.";
        copyTimer = window.setTimeout(function () {
          if (id === requestId) resetCopyFeedback();
        }, 2000);
      } catch (error) {
        if (id !== requestId || !dialog.open) return;
        try {
          content.tabIndex = 0;
          content.focus();
          const selection = window.getSelection();
          if (!selection) throw new Error("Text selection is unavailable.");
          const range = document.createRange();
          range.selectNodeContents(content);
          selection.removeAllRanges();
          selection.addRange(range);
          status.textContent = "Automatic copy is unavailable. BibTeX is selected; press Ctrl+C or Command+C to copy.";
        } catch (selectionError) {
          status.textContent = "Automatic copy is unavailable. Select the BibTeX text and copy it manually, or use Download.";
        }
      } finally {
        if (id === requestId && dialog.open) copyButton.disabled = false;
      }
    });

    closeButton.addEventListener("click", function () {
      dialog.close();
    });
    dialog.addEventListener("click", function (event) {
      if (event.target !== dialog) return;
      const bounds = dialog.getBoundingClientRect();
      if (event.clientX < bounds.left || event.clientX > bounds.right
          || event.clientY < bounds.top || event.clientY > bounds.bottom) {
        dialog.close();
      }
    });
    // Native Escape handling closes the dialog and reaches this same cleanup.
    dialog.addEventListener("close", function () {
      if (dialog.open) return;
      cancelRequest();
      if (opener && opener.isConnected) opener.focus();
      opener = null;
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializePublications, { once: true });
  } else {
    initializePublications();
  }
})();
