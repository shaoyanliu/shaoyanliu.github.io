(function () {
  const button = document.getElementById("navigation-toggle");
  const links = document.getElementById("myLinks");

  if (!button || !links) return;

  function setExpanded(expanded) {
    links.classList.toggle("is-open", expanded);
    button.setAttribute("aria-expanded", String(expanded));
    button.setAttribute("aria-label", expanded ? "Close navigation menu" : "Open navigation menu");
  }

  button.addEventListener("click", function () {
    setExpanded(button.getAttribute("aria-expanded") !== "true");
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && button.getAttribute("aria-expanded") === "true") {
      setExpanded(false);
      button.focus();
    }
  });

  links.addEventListener("click", function (event) {
    if (event.target.closest("a")) setExpanded(false);
  });

  // Reset the mobile menu when crossing the desktop/mobile breakpoint.
  window.matchMedia("(max-width: 960px)").addEventListener("change", function () {
    setExpanded(false);
  });
})();
