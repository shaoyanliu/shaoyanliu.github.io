(function () {
  "use strict";

  const dialog = document.getElementById("news-photo-viewer");
  if (!dialog || typeof dialog.showModal !== "function") return;

  const closeButton = dialog.querySelector(".news-photo-close");
  const stage = dialog.querySelector(".news-photo-stage");
  const status = dialog.querySelector(".news-photo-status");
  const caption = dialog.querySelector("#news-photo-caption");
  const original = dialog.querySelector(".news-photo-original");
  let opener = null;
  let requestId = 0;
  let scrollPosition = { x: 0, y: 0 };
  let backdropPointer = false;

  document.querySelectorAll("a[data-news-photo]").forEach(function (link) {
    link.setAttribute("aria-haspopup", "dialog");
    link.setAttribute("aria-controls", dialog.id);
    link.addEventListener("click", function (event) {
      // Modified clicks and unsupported browsers keep the ordinary image link.
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey
          || event.shiftKey || event.altKey) return;
      const url = new URL(link.href, document.baseURI);
      if (!/^https?:$/.test(url.protocol)) return;

      scrollPosition = { x: window.scrollX, y: window.scrollY };
      caption.textContent = link.dataset.newsCaption || link.textContent.trim();
      original.href = url.href;
      stage.querySelectorAll("img").forEach(function (image) { image.remove(); });
      status.hidden = false;
      status.textContent = "Loading photo…";
      try {
        dialog.showModal();
      } catch (error) {
        return;
      }
      event.preventDefault();
      opener = link;
      document.documentElement.classList.add("news-photo-open");

      const id = ++requestId;
      const photo = new Image();
      photo.alt = link.dataset.newsAlt || caption.textContent;
      photo.onload = function () {
        if (id !== requestId || !dialog.open) return;
        status.hidden = true;
        status.textContent = "";
        stage.appendChild(photo);
      };
      photo.onerror = function () {
        if (id !== requestId || !dialog.open) return;
        status.textContent = "Could not load this photo. Use Open image to try it in a new tab.";
      };
      photo.src = url.href;
    });
  });

  closeButton.addEventListener("click", function () { dialog.close(); });

  function isBackdrop(event) {
    if (event.target !== dialog) return false;
    const bounds = dialog.getBoundingClientRect();
    return event.clientX < bounds.left || event.clientX > bounds.right
      || event.clientY < bounds.top || event.clientY > bounds.bottom;
  }

  // A drag starting on the photo should never dismiss the viewer.
  dialog.addEventListener("pointerdown", function (event) {
    backdropPointer = isBackdrop(event);
  });
  dialog.addEventListener("click", function (event) {
    if (backdropPointer && isBackdrop(event)) dialog.close();
    backdropPointer = false;
  });

  // Escape and the close button share scroll/focus cleanup.
  dialog.addEventListener("close", function () {
    ++requestId;
    document.documentElement.classList.remove("news-photo-open");
    if (opener && opener.isConnected) opener.focus({ preventScroll: true });
    window.scrollTo({ left: scrollPosition.x, top: scrollPosition.y, behavior: "instant" });
    opener = null;
    backdropPointer = false;
  });
})();
