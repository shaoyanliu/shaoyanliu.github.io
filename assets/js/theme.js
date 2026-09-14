(function () {
  const root = document.documentElement;
  const button = document.getElementById("theme-toggle");
  const systemTheme = window.matchMedia("(prefers-color-scheme: dark)");
  let selectedTheme = readPreference();

  function readPreference() {
    try {
      const value = localStorage.getItem("site-theme");
      return value === "light" || value === "dark" ? value : null;
    } catch (error) {
      return null;
    }
  }

  function applyTheme(theme) {
    root.setAttribute("data-theme", theme);
    const themeColor = document.querySelector('meta[name="theme-color"]');
    if (themeColor) themeColor.content = theme === "dark" ? "#121212" : "#ffffff";
    if (button) {
      const label = theme === "dark" ? "Switch to light mode" : "Switch to dark mode";
      button.setAttribute("aria-label", label);
      button.title = label;
    }
  }

  function applyPreference() {
    applyTheme(selectedTheme || (systemTheme.matches ? "dark" : "light"));
  }

  applyPreference();
  if (button) {
    button.hidden = false;
    button.addEventListener("click", function () {
      selectedTheme = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      applyTheme(selectedTheme);
      try {
        localStorage.setItem("site-theme", selectedTheme);
      } catch (error) {
        // Keep the current page usable even if storage is disabled.
      }
    });
  }

  systemTheme.addEventListener("change", function () {
    if (!selectedTheme) applyPreference();
  });

  // Keep other open pages in sync with a choice made in another tab.
  window.addEventListener("storage", function (event) {
    if (event.key === "site-theme" || event.key === null) {
      selectedTheme = readPreference();
      applyPreference();
    }
  });
})();
