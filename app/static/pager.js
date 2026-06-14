// Horizontal pager: swipe (touch), arrow buttons, and dot indicators move
// between full-screen pages. Kiosk-friendly — no scrollbars, no libraries.
function initPager() {
    const pager = document.getElementById("pager");
    const pages = Array.from(pager.querySelectorAll(".page"));
    const dotsEl = document.getElementById("pager-dots");
    const prevBtn = document.getElementById("pager-prev");
    const nextBtn = document.getElementById("pager-next");

    let index = 0;
    const SWIPE_THRESHOLD = 60; // px of horizontal travel to flip a page

    // Build one dot per page.
    const dots = pages.map((_, i) => {
        const dot = document.createElement("button");
        dot.className = "pager-dot";
        dot.type = "button";
        dot.setAttribute("aria-label", `go to page ${i + 1}`);
        dot.addEventListener("click", () => goTo(i));
        dotsEl.append(dot);
        return dot;
    });

    function goTo(i) {
        index = Math.max(0, Math.min(pages.length - 1, i));
        pager.style.transform = `translateX(-${index * 100}vw)`;
        dots.forEach((d, di) => d.classList.toggle("active", di === index));
        prevBtn.classList.toggle("hidden", index === 0);
        nextBtn.classList.toggle("hidden", index === pages.length - 1);
    }

    prevBtn.addEventListener("click", () => goTo(index - 1));
    nextBtn.addEventListener("click", () => goTo(index + 1));

    // Touch swipe. Only act on a clearly-horizontal gesture so vertical list
    // scrolling and taps on todo items still work.
    let startX = 0;
    let startY = 0;
    let tracking = false;

    pager.addEventListener("touchstart", (e) => {
        const t = e.changedTouches[0];
        startX = t.clientX;
        startY = t.clientY;
        tracking = true;
    }, { passive: true });

    pager.addEventListener("touchend", (e) => {
        if (!tracking) return;
        tracking = false;
        const t = e.changedTouches[0];
        const dx = t.clientX - startX;
        const dy = t.clientY - startY;
        if (Math.abs(dx) > SWIPE_THRESHOLD && Math.abs(dx) > Math.abs(dy)) {
            goTo(index + (dx < 0 ? 1 : -1));
        }
    }, { passive: true });

    // Arrow keys help during development on a desktop.
    document.addEventListener("keydown", (e) => {
        if (e.key === "ArrowRight") goTo(index + 1);
        if (e.key === "ArrowLeft") goTo(index - 1);
    });

    goTo(0);
}

initPager();
