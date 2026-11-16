(() => {
  const TZ = "America/Chicago";
  const DATA_URL = "data/news.json";
  const SAVED_KEY = "nt-saved";
  const THEME_KEY = "nt-theme";
  const SECTIONS = [
    { id: "top", label: "Top Stories" },
    { id: "us", label: "U.S." },
    { id: "world", label: "World" },
    { id: "politics", label: "Politics" },
    { id: "business", label: "Business & Markets" },
    { id: "health", label: "Health" },
    { id: "tech", label: "Tech" },
    { id: "sports", label: "Sports" },
    { id: "video", label: "Video / Shows" },
    { id: "saved", label: "Saved" },
    { id: "about", label: "About" }
  ];

  const NEUTRAL_SOURCES = ["ap", "reuters", "newsnation"];
  const TOP_STORY_CAP = 10;

  const state = {
    data: null,
    section: "top",
    source: "all",
    query: "",
    lastHourOnly: false,
    saved: loadSaved()
  };

  const main = document.getElementById("main");
  const updatedLine = document.getElementById("updatedLine");
  const sectionNav = document.getElementById("sectionNav");
  const searchBox = document.getElementById("searchBox");
  const refreshBtn = document.getElementById("refreshBtn");
  const themeBtn = document.getElementById("themeBtn");
  const lastHourBtn = document.getElementById("lastHourBtn");
  const toastEl = document.getElementById("toast");

  function loadSaved() {
    try {
      const raw = JSON.parse(localStorage.getItem(SAVED_KEY) || "[]");
      return Array.isArray(raw) ? raw : [];
    } catch (e) {
      return [];
    }
  }

  function persistSaved() {
    try { localStorage.setItem(SAVED_KEY, JSON.stringify(state.saved)); } catch (e) {}
  }

  function toast(msg) {
    toastEl.textContent = msg;
    toastEl.classList.add("show");
    clearTimeout(toast.t);
    toast.t = setTimeout(() => toastEl.classList.remove("show"), 2200);
  }

  function el(tag, attrs, children) {
    const n = document.createElement(tag);
    if (attrs) {
      for (const [k, v] of Object.entries(attrs)) {
        if (v == null || v === false) continue;
        if (k === "class") n.className = v;
        else if (k === "text") n.textContent = v;
        else if (k.startsWith("on") && typeof v === "function") n.addEventListener(k.slice(2), v);
        else if (k === "dataset") Object.assign(n.dataset, v);
        else n.setAttribute(k, v === true ? "" : v);
      }
    }
    if (children) for (const c of children) if (c) n.appendChild(c);
    return n;
  }

  function allowedHost(url, extra) {
    try {
      const u = new URL(url);
      if (u.protocol !== "https:" && u.protocol !== "http:") return false;
      let host = u.hostname.toLowerCase().replace(/^www\./, "");
      const blocked = ["cnn.com", "msn.com", "msnbc.com"];
      if (blocked.some((h) => host === h || host.endsWith("." + h))) return false;
      const ok = extra.concat([
        "foxnews.com", "foxbusiness.com", "fncstatic.com",
        "youtube.com", "youtu.be", "ytimg.com",
        "apnews.com", "reuters.com", "newsnationnow.com",
        "news.google.com", "flipboard.com"
      ]);
      return ok.some((h) => host === h || host.endsWith("." + h));
    } catch (e) {
      return false;
    }
  }

  function parsePublished(item) {
    if (!item || !item.published) return null;
    const d = new Date(item.published);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  function formatExact(d) {
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone: TZ,
      weekday: "short",
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
      hour12: true
    }).formatToParts(d);
    const get = (t) => (parts.find((p) => p.type === t) || {}).value || "";
    return `${get("weekday")}, ${get("month")} ${get("day")}, ${get("year")}, ${get("hour")}:${get("minute")} ${get("dayPeriod")} CT`;
  }

  function formatDateOnly(d) {
    return new Intl.DateTimeFormat("en-US", {
      timeZone: TZ,
      weekday: "short",
      month: "short",
      day: "numeric",
      year: "numeric"
    }).format(d) + " CT";
  }

  function timeAgo(d, now) {
    const sec = Math.round((now - d) / 1000);
    if (sec < 45) return "Just now";
    if (sec < 90) return "1 minute ago";
    if (sec < 3600) return `${Math.round(sec / 60)} minutes ago`;
    if (sec < 5400) return "1 hour ago";
    if (sec < 86400) return `${Math.round(sec / 3600)} hours ago`;
    if (sec < 172800) return "1 day ago";
    return `${Math.round(sec / 86400)} days ago`;
  }

  function timeLabel(item, now) {
    const d = parsePublished(item);
    const prec = item.published_precision || (d ? "minute" : "unknown");
    if (d && prec === "minute") return `${timeAgo(d, now)} · ${formatExact(d)}`;
    if (d && prec === "day") return `${formatDateOnly(d)} · Exact time not listed`;
    if (d && prec === "relative") return `${timeAgo(d, now)} · Exact time not listed`;
    if (item.published_text) return `${item.published_text} · Exact time not listed`;
    if (item.published_date_text) return `${item.published_date_text} · Exact time not listed`;
    return "Time not listed";
  }

  function isLastHour(item, now) {
    const d = parsePublished(item);
    if (!d || item.published_precision !== "minute") return false;
    return (now - d) >= 0 && (now - d) <= 60 * 60 * 1000;
  }

  function formatUpdated(iso) {
    const d = iso ? new Date(iso) : null;
    if (!d || Number.isNaN(d.getTime())) return "Update time not listed";
    return "Last updated " + formatExact(d);
  }


  function aboutPage() {
    const box = el("section", { class: "about" });
    box.appendChild(el("h2", { text: "About News Tracker" }));
    box.appendChild(el("p", { text: "This app lists headlines from Fox News, Fox Business, the Associated Press, Reuters, NewsNation, Tousi TV and the PBD Podcast. Each card shows the source’s headline, summary, time and link. The app does not add commentary or invent stories." }));
    box.appendChild(el("h3", { text: "Bias ratings" }));
    box.appendChild(el("p", { text: "AllSides, an independent media-bias rater, was checked on Nov 15, 2026. It rates Reuters as Center and NewsNation as Center, and it rates the Associated Press as Lean Left. Those ratings are for online news coverage, not TV. Because the Associated Press is not rated Center, this app does not describe all three as center-rated." }));
    const allsides = el("p");
    allsides.appendChild(document.createTextNode("AllSides pages: "));
    const links = [
      ["Associated Press", "https://www.allsides.com/news-source/associated-press-media-bias"],
      ["Reuters", "https://www.allsides.com/news-source/reuters-media-bias"],
      ["NewsNation", "https://www.allsides.com/news-source/newsnation-media-bias"]
    ];
    links.forEach((pair, i) => {
      if (i) allsides.appendChild(document.createTextNode(", "));
      allsides.appendChild(el("a", { href: pair[1], target: "_blank", rel: "noopener noreferrer", text: pair[0] }));
    });
    allsides.appendChild(document.createTextNode("."));
    box.appendChild(allsides);
    box.appendChild(el("h3", { text: "The Neutral filter" }));
    box.appendChild(el("p", { text: "The Neutral filter shows Associated Press, Reuters and NewsNation together, so you can read those outlets side by side with Fox News, Fox Business, Tousi TV and the PBD Podcast. You can also tap AP, Reuters or NewsNation alone." }));
    box.appendChild(el("h3", { text: "Where the headlines come from" }));
    const ul = el("ul");
    [
      "Fox News and Fox Business: official RSS feeds on moxie.foxnews.com and moxie.foxbusiness.com.",
      "Associated Press: AP no longer publishes a working public RSS feed on apnews.com. This app uses AP’s official Flipboard magazines. Each card opens the article on apnews.com.",
      "Reuters: Reuters ended its public RSS feeds in 2020. This app uses a Google News RSS search limited to reuters.com. Each card opens the Reuters article through Google News, not through MSN or another aggregator.",
      "NewsNation: official RSS feeds on newsnationnow.com.",
      "Tousi TV and the PBD Podcast: official YouTube channels."
    ].forEach((line) => ul.appendChild(el("li", { text: line })));
    box.appendChild(ul);
    box.appendChild(el("p", { text: "This app does not use CNN, MSN or MSNBC. Times are shown in Central Time. Saved stories stay on this device only. Fox News does not publish a Texas or DFW RSS feed, so that section is not included. Top Stories keeps a cap of the newest stories from each source so one outlet cannot fill the whole list." }));
    return box;
  }

  function currentItems(now) {
    const q = state.query.trim().toLowerCase();
    let items;
    if (state.section === "saved") {
      items = state.saved.slice();
    } else if (state.section === "about") {
      items = [];
    } else if (state.section === "top") {
      items = (state.data && state.data.items) || [];
    } else {
      items = ((state.data && state.data.items) || []).filter((it) => (it.sections || []).includes(state.section));
    }
    if (state.source === "neutral") {
      items = items.filter((it) => NEUTRAL_SOURCES.includes(it.source_id));
    } else if (state.source !== "all") {
      items = items.filter((it) => it.source_id === state.source);
    }
    if (state.section === "top" && (state.source === "all" || state.source === "neutral")) {
      const counts = {};
      items = items.filter((it) => {
        const sid = it.source_id || "other";
        const n = counts[sid] || 0;
        if (n >= TOP_STORY_CAP) return false;
        counts[sid] = n + 1;
        return true;
      });
    }
    if (state.lastHourOnly) items = items.filter((it) => isLastHour(it, now));
    if (q) {
      items = items.filter((it) => {
        const hay = `${it.title || ""} ${it.summary || ""} ${it.source || ""}`.toLowerCase();
        return hay.includes(q);
      });
    }
    return items;
  }

  function isSaved(id) {
    return state.saved.some((s) => s.id === id);
  }

  function toggleSave(item) {
    if (isSaved(item.id)) {
      state.saved = state.saved.filter((s) => s.id !== item.id);
      persistSaved();
      toast("Removed from saved stories");
    } else {
      state.saved = [{
        id: item.id,
        title: item.title,
        summary: item.summary,
        url: item.url,
        source: item.source,
        source_id: item.source_id,
        sections: item.sections,
        published: item.published,
        published_precision: item.published_precision,
        published_text: item.published_text,
        published_date_text: item.published_date_text,
        thumbnail: item.thumbnail,
        kind: item.kind,
        savedAt: new Date().toISOString()
      }, ...state.saved];
      persistSaved();
      toast("Saved on this device");
    }
    render();
  }

  function card(item, now) {
    const hour = isLastHour(item, now);
    const href = allowedHost(item.url, []) ? item.url : null;
    const thumb = item.thumbnail && allowedHost(item.thumbnail, []) ? item.thumbnail : null;
    const saved = isSaved(item.id);
    const node = el("article", { class: "card" + (hour ? " last-hour" : "") });
    const link = el(href ? "a" : "div", href ? {
      class: "story",
      href,
      target: "_blank",
      rel: "noopener noreferrer"
    } : { class: "story" });
    if (thumb) {
      link.appendChild(el("img", {
        class: "thumb",
        src: thumb,
        alt: "",
        loading: "lazy",
        width: "640",
        height: "360"
      }));
    }
    const body = el("div", { class: "card-body" });
    const meta = el("div", { class: "meta" });
    meta.appendChild(el("span", { class: "badge " + (item.source_id || ""), text: item.source || "Source not listed" }));
    if (hour) meta.appendChild(el("span", { class: "badge hour", text: "Last hour" }));
    meta.appendChild(el("span", { text: timeLabel(item, now) }));
    body.appendChild(meta);
    body.appendChild(el("h2", { text: item.title || "Headline not listed" }));
    if (item.summary) body.appendChild(el("p", { class: "summary", text: item.summary }));
    link.appendChild(body);
    node.appendChild(link);
    const actions = el("div", { class: "card-actions" });
    let hint = "Link not available";
    if (href) {
      if (item.kind === "video") hint = "Opens the video on YouTube";
      else if (item.via === "google-news") hint = "Opens the " + (item.source || "publisher") + " article through Google News";
      else hint = "Opens the article on the source’s site";
    }
    actions.appendChild(el("span", { class: "open-hint", text: hint }));
    const saveBtn = el("button", {
      type: "button",
      class: "save",
      "aria-pressed": saved ? "true" : "false",
      "aria-label": saved ? "Remove from saved stories" : "Save this story on this device",
      text: saved ? "★" : "☆",
      onclick: (ev) => { ev.preventDefault(); ev.stopPropagation(); toggleSave(item); }
    });
    actions.appendChild(saveBtn);
    node.appendChild(actions);
    return node;
  }

  function sourceIssues() {
    const status = (state.data && state.data.status) || [];
    return status.filter((s) => !s.ok);
  }

  function renderNav() {
    sectionNav.innerHTML = "";
    for (const s of SECTIONS) {
      const b = el("button", {
        type: "button",
        class: "sec" + (state.section === s.id ? " on" : ""),
        text: s.label,
        "aria-current": state.section === s.id ? "page" : null,
        onclick: () => { state.section = s.id; render(); }
      });
      sectionNav.appendChild(b);
    }
  }

  function render() {
    const now = new Date();
    renderNav();
    lastHourBtn.classList.toggle("on", state.lastHourOnly);
    lastHourBtn.setAttribute("aria-pressed", state.lastHourOnly ? "true" : "false");
    document.querySelectorAll(".filters [data-source]").forEach((b) => {
      b.classList.toggle("on", b.dataset.source === state.source);
    });
    const theme = document.documentElement.dataset.theme === "dark" ? "dark" : "light";
    themeBtn.textContent = theme === "dark" ? "Light mode" : "Dark mode";
    themeBtn.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");

    if (state.data && state.data.updated) {
      updatedLine.textContent = formatUpdated(state.data.updated);
    }

    main.innerHTML = "";
    const failed = sourceIssues();
    if (failed.length) {
      const box = el("div", { class: "banner" });
      box.appendChild(el("strong", { text: "Some sources did not update on the last check." }));
      const ul = el("ul", { class: "status-list" });
      for (const s of failed) {
        ul.appendChild(el("li", { class: "fail", text: `${s.name}: ${s.error || "No items returned"}` }));
      }
      box.appendChild(ul);
      main.appendChild(box);
    }

    const items = currentItems(now);
    const sectionLabel = (SECTIONS.find((s) => s.id === state.section) || {}).label || "";
    if (state.section === "about") {
      main.appendChild(aboutPage());
      return;
    }
    if (!state.data && !items.length) {
      main.appendChild(el("p", { class: "loading", text: "Loading headlines…" }));
      return;
    }
    if (!items.length) {
      const msg = state.section === "saved"
        ? "No saved stories yet. Tap the star on a story to keep it on this device."
        : state.lastHourOnly
          ? "No stories from the last hour match these filters. Times are used only when the source gives an exact time."
          : "No stories match these filters.";
      main.appendChild(el("p", { class: "empty", text: msg }));
    } else {
      if (state.section === "top" && !state.lastHourOnly && !state.query) {
        const recent = items.filter((it) => isLastHour(it, now));
        if (recent.length) {
          const wrap = el("section", { class: "hour-strip" });
          wrap.appendChild(el("h2", { text: "Last hour" }));
          const lead = el("div", { class: "grid lead" });
          // Show last-hour items once in this highlight; they also appear in the full list below.
          for (const it of recent) lead.appendChild(card(it, now));
          wrap.appendChild(lead);
          main.appendChild(wrap);
        }
      }
      main.appendChild(el("h2", { class: "list-head", text: `${sectionLabel} · ${items.length} ${items.length === 1 ? "story" : "stories"}` }));
      const grid = el("div", { class: "grid" });
      for (const it of items) grid.appendChild(card(it, now));
      main.appendChild(grid);
    }

    const note = el("footer", { class: "note" });
    note.appendChild(document.createTextNode("Headlines, summaries and times are shown as published by each source. This app does not add commentary. Saved stories stay on this device only. See About for source details."));
    main.appendChild(note);
  }

  async function loadData(manual) {
    try {
      const r = await fetch(DATA_URL + "?t=" + Date.now(), { cache: "no-store" });
      if (!r.ok) throw new Error("Could not load headlines (" + r.status + ")");
      state.data = await r.json();
      updatedLine.textContent = formatUpdated(state.data.updated);
      render();
      if (manual) toast("Headlines refreshed");
    } catch (e) {
      if (!state.data) {
        updatedLine.textContent = "Headlines could not be loaded";
        main.innerHTML = "";
        main.appendChild(el("p", { class: "empty", text: "The headline list could not be loaded. Check your connection, then tap Refresh." }));
      }
      if (manual) toast("Refresh failed. Showing the last list this app already had, if any.");
    }
  }

  searchBox.addEventListener("input", () => {
    state.query = searchBox.value;
    render();
  });
  document.querySelectorAll(".filters [data-source]").forEach((b) => {
    b.addEventListener("click", () => { state.source = b.dataset.source; render(); });
  });
  lastHourBtn.addEventListener("click", () => { state.lastHourOnly = !state.lastHourOnly; render(); });
  refreshBtn.addEventListener("click", () => loadData(true));
  themeBtn.addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem(THEME_KEY, next); } catch (e) {}
    render();
  });

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("sw.js").catch(() => {});
  }

  loadData(false);
  setInterval(() => loadData(false), 15 * 60 * 1000);
})();
