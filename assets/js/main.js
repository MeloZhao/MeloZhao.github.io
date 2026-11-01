/* ============================================================
   Melo Zhao — interactions
   ============================================================ */
(function () {
  "use strict";

  var root = document.documentElement;
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- theme ---------- */
  var STORE_KEY = "melo-theme";

  function applyTheme(t) {
    if (t === "light" || t === "dark") {
      root.setAttribute("data-theme", t);
    } else {
      root.removeAttribute("data-theme");
    }
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) {
      var dark = t === "dark" || (!t && window.matchMedia("(prefers-color-scheme: dark)").matches);
      meta.setAttribute("content", dark ? "#05070d" : "#e9eef7");
    }
  }

  var saved = null;
  try { saved = localStorage.getItem(STORE_KEY); } catch (e) {}
  applyTheme(saved);

  var toggle = document.querySelector(".theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var current = root.getAttribute("data-theme");
      if (!current) {
        current = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
      }
      var next = current === "dark" ? "light" : "dark";
      applyTheme(next);
      try { localStorage.setItem(STORE_KEY, next); } catch (e) {}
    });
  }

  /* ---------- nav ---------- */
  var nav = document.querySelector(".nav");
  var burger = document.querySelector(".nav-burger");
  var links = document.querySelector(".nav-links");

  if (burger && links) {
    burger.addEventListener("click", function (e) {
      e.stopPropagation();
      links.classList.toggle("is-open");
      burger.setAttribute("aria-expanded", links.classList.contains("is-open") ? "true" : "false");
    });
    document.addEventListener("click", function (e) {
      if (!links.contains(e.target) && e.target !== burger) links.classList.remove("is-open");
    });
  }

  var lastY = window.scrollY;
  function onScroll() {
    if (nav) nav.classList.toggle("is-scrolled", window.scrollY > 12);
    lastY = window.scrollY;
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  /* ---------- hero parallax ---------- */
  var heroBg = document.querySelector(".hero-bg");
  if (heroBg && !reduce) {
    var hero = heroBg.parentElement;
    var ticking = false;
    var applyParallax = function () {
      var y = window.scrollY;
      var h = hero.offsetHeight || 1;
      if (y <= h) {
        heroBg.style.translate = "0 " + (y * 0.24).toFixed(1) + "px";
      }
      ticking = false;
    };
    window.addEventListener("scroll", function () {
      if (!ticking) {
        window.requestAnimationFrame(applyParallax);
        ticking = true;
      }
    }, { passive: true });
    applyParallax();
  }

  /* ---------- reveal on scroll ---------- */
  var reveals = document.querySelectorAll(".reveal");
  if (reveals.length) {
    if (reduce || !("IntersectionObserver" in window)) {
      reveals.forEach(function (el) { el.classList.add("is-in"); });
    } else {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-in");
            io.unobserve(entry.target);
          }
        });
      }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
      reveals.forEach(function (el) { io.observe(el); });
    }
  }

  /* ---------- reading progress ---------- */
  var bar = document.querySelector(".progress");
  if (bar) {
    var article = document.querySelector(".prose");
    function updateProgress() {
      if (!article) return;
      var rect = article.getBoundingClientRect();
      var total = rect.height - window.innerHeight * 0.5;
      var scrolled = -rect.top + window.innerHeight * 0.35;
      var pct = total > 0 ? Math.min(1, Math.max(0, scrolled / total)) : 0;
      bar.style.width = (pct * 100).toFixed(2) + "%";
    }
    window.addEventListener("scroll", updateProgress, { passive: true });
    window.addEventListener("resize", updateProgress);
    updateProgress();
  }

  /* ---------- TOC active state ---------- */
  var tocLinks = Array.prototype.slice.call(document.querySelectorAll(".toc a"));
  if (tocLinks.length) {
    var targets = tocLinks
      .map(function (a) {
        var id = decodeURIComponent(a.getAttribute("href").slice(1));
        return document.getElementById(id);
      })
      .filter(Boolean);

    var setActive = function (id) {
      tocLinks.forEach(function (a) {
        a.classList.toggle("is-on", a.getAttribute("href") === "#" + id);
      });
    };

    var tocObserver = new IntersectionObserver(function (entries) {
      var visible = entries
        .filter(function (e) { return e.isIntersecting; })
        .sort(function (a, b) { return a.boundingClientRect.top - b.boundingClientRect.top; });
      if (visible.length) setActive(visible[0].target.id);
    }, { rootMargin: "-96px 0px -70% 0px", threshold: 0 });

    targets.forEach(function (t) { tocObserver.observe(t); });
  }

  /* ---------- copy code ---------- */
  document.querySelectorAll(".copy-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var block = btn.closest(".codeblock");
      var code = block && block.querySelector("code");
      if (!code) return;
      var text = code.textContent;
      var done = function () {
        var old = btn.textContent;
        btn.textContent = "COPIED";
        setTimeout(function () { btn.textContent = old; }, 1600);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, done);
      } else {
        var ta = document.createElement("textarea");
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand("copy"); } catch (e) {}
        document.body.removeChild(ta);
        done();
      }
    });
  });

  /* ---------- blog tag filter ---------- */
  var filterBar = document.querySelector(".filter-bar");
  if (filterBar) {
    var cards = Array.prototype.slice.call(document.querySelectorAll("[data-tags]"));
    var empty = document.querySelector(".empty-state");

    filterBar.addEventListener("click", function (e) {
      var btn = e.target.closest(".filter-btn");
      if (!btn) return;
      var tag = btn.dataset.filter;
      filterBar.querySelectorAll(".filter-btn").forEach(function (b) {
        b.classList.toggle("is-on", b === btn);
      });
      var shown = 0;
      cards.forEach(function (card) {
        var tags = (card.dataset.tags || "").split("|");
        var match = tag === "all" || tags.indexOf(tag) !== -1;
        card.style.display = match ? "" : "none";
        if (match) shown++;
      });

      // 分组列表：没有可见行的分组连同它的年份标签一起收起
      document.querySelectorAll(".grouped").forEach(function (group) {
        var rows = group.querySelectorAll(".row");
        var visible = 0;
        rows.forEach(function (r) {
          if (r.style.display !== "none") visible++;
        });
        group.style.display = visible ? "" : "none";
        var label = group.previousElementSibling;
        if (label && label.classList.contains("group-label")) {
          label.style.display = visible ? "" : "none";
        }
      });

      if (empty) empty.style.display = shown ? "none" : "";
    });
  }
})();
