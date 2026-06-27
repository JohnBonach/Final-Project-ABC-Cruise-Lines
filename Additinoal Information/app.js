/* ABC Cruise Lines — Reservation system
   - Step-by-step booking wizard (Destination → Ship → Room → Dining → Guest → Payment → Confirmation)
   - Ship Dashboard: registry of ALL reservations (including newly booked ones)
   Pure vanilla JS, zero external deps, works offline. */
(function () {
  const data = window.DASHBOARD_DATA;

  /* ---------------- persistence (browser localStorage) ---------------- */
  const STORAGE_KEY = "abc_cruise_bookings_v1";
  function loadSaved() { try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"); } catch (e) { return []; } }
  function persist(r) { try { const s = loadSaved(); s.push(r); localStorage.setItem(STORAGE_KEY, JSON.stringify(s)); return true; } catch (e) { return false; } }
  function clearSaved() { try { localStorage.removeItem(STORAGE_KEY); } catch (e) {} }
  (function hydrate() {
    const saved = loadSaved();
    if (saved.length) {
      const ids = new Set(data.reservations.map((r) => r.id));
      saved.forEach((r) => { if (!ids.has(r.id)) data.reservations.push(r); });
    }
  })();

  /* ---------------- helpers ---------------- */
  const fmtMoney = (n) => "$" + Math.round(n).toLocaleString("en-US");
  const fmtDate = (s) => new Date(s + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  const STATUS_COLORS = { Confirmed: "#1f6fb2", Pending: "#b8860b", "Checked-in": "#1c8a4d", Completed: "#7a8a9a", Cancelled: "#c0392b" };
  const shipByName = (n) => data.ships.find((s) => s.name === n);
  const shipLabel = (n) => { const s = shipByName(n); return s ? `${s.name} (${s.designation})` : n; };
  const cabinTier = (t) => { const c = data.cabins.find((x) => x.type === t); return c ? c.tier : ""; };
  const shortPort = (p) => p.replace(" (Casino)", "").split(",")[0];

  function el(spec, attrs, ...children) {
    const [tagPart, ...classParts] = spec.split(".");
    let tag = tagPart, id = null;
    if (tag.includes("#")) [tag, id] = tag.split("#");
    const node = document.createElement(tag || "div");
    if (id) node.id = id;
    if (classParts.length) node.className = classParts.join(" ");
    if (attrs && typeof attrs === "object" && attrs.nodeType === undefined && !Array.isArray(attrs)) {
      for (const k in attrs) {
        if (k === "html") node.innerHTML = attrs[k];
        else if (k.startsWith("on") && typeof attrs[k] === "function") node.addEventListener(k.slice(2).toLowerCase(), attrs[k]);
        else if (k === "style" && typeof attrs[k] === "object") Object.assign(node.style, attrs[k]);
        else if (attrs[k] != null && attrs[k] !== false) node.setAttribute(k, attrs[k]);
      }
    } else if (attrs != null) children.unshift(attrs);
    for (const c of children.flat()) {
      if (c == null || c === false) continue;
      node.appendChild(typeof c === "object" ? c : document.createTextNode(String(c)));
    }
    return node;
  }

  // SVG element builder (for line / Pareto charts) — separate from el() because SVG needs a namespace
  function sv(tag, attrs, ...children) {
    const n = document.createElementNS("http://www.w3.org/2000/svg", tag);
    if (attrs) for (const k in attrs) if (attrs[k] != null) n.setAttribute(k, attrs[k]);
    for (const c of children.flat()) { if (c == null || c === false) continue; n.appendChild(typeof c === "object" ? c : document.createTextNode(String(c))); }
    return n;
  }
  // line chart: pts = [{label, val}]
  function lineChart(pts, opts) {
    opts = opts || {};
    const W = 760, H = 260, mL = 64, mR = 16, mT = 16, mB = 46;
    const max = Math.max(1, ...pts.map((p) => p.val)) * 1.1;
    const x = (i) => mL + (pts.length <= 1 ? 0 : (i / (pts.length - 1)) * (W - mL - mR));
    const y = (v) => H - mB - (v / max) * (H - mT - mB);
    const g = [];
    for (let i = 0; i <= 4; i++) { const gv = max * i / 4; const gy = y(gv); g.push(sv("line", { x1: mL, y1: gy, x2: W - mR, y2: gy, stroke: "#e3e9f0", "stroke-width": 1 })); g.push(sv("text", { x: mL - 8, y: gy + 4, "text-anchor": "end", "font-size": 10, fill: "#6b7a8d" }, "$" + Math.round(gv / 1000) + "k")); }
    const splitAt = opts.forecastFrom != null ? opts.forecastFrom : pts.length;
    const path = (from, to, dash) => {
      const d = pts.slice(from, to).map((p, k) => (k === 0 ? "M" : "L") + x(from + k) + " " + y(p.val)).join(" ");
      return sv("path", { d, fill: "none", stroke: dash ? "#b8860b" : "#0a85c4", "stroke-width": 2.5, "stroke-dasharray": dash ? "6 5" : null, "stroke-linejoin": "round" });
    };
    const dots = pts.map((p, i) => sv("circle", { cx: x(i), cy: y(p.val), r: 3.2, fill: i >= splitAt - 1 && opts.forecastFrom != null && i >= opts.forecastFrom - 1 ? "#b8860b" : "#0a85c4" }));
    const labs = pts.map((p, i) => (pts.length <= 12 || i % 2 === 0) ? sv("text", { x: x(i), y: H - mB + 16, "text-anchor": "middle", "font-size": 9.5, fill: "#6b7a8d", transform: "rotate(35 " + x(i) + " " + (H - mB + 16) + ")" }, p.label) : null);
    const lines = [];
    lines.push(path(0, splitAt, false));
    if (opts.forecastFrom != null && splitAt < pts.length) lines.push(path(splitAt - 1, pts.length, true));
    const svg = sv("svg", { viewBox: "0 0 " + W + " " + H, width: "100%", preserveAspectRatio: "xMidYMid meet" }, ...g, ...lines, ...dots, ...labs);
    return el("div.chart-wrap", svg);
  }
  // Pareto chart: entries = [[label, val]] (auto-sorted desc + cumulative % line)
  function paretoChart(entries) {
    const data2 = entries.slice().sort((a, b) => b[1] - a[1]);
    const total = data2.reduce((s, e) => s + e[1], 0) || 1;
    const W = 760, H = 270, mL = 64, mR = 44, mT = 16, mB = 64;
    const max = Math.max(1, ...data2.map((e) => e[1])) * 1.1;
    const bw = (W - mL - mR) / Math.max(1, data2.length);
    const y = (v) => H - mB - (v / max) * (H - mT - mB);
    const yPct = (p) => H - mB - (p / 100) * (H - mT - mB);
    const bars = data2.map((e, i) => sv("rect", { x: mL + i * bw + bw * 0.15, y: y(e[1]), width: bw * 0.7, height: (H - mB) - y(e[1]), rx: 3, fill: "#0a85c4" }));
    let cum = 0; const cumPts = data2.map((e, i) => { cum += e[1]; return [mL + i * bw + bw / 2, yPct(cum / total * 100)]; });
    const cumPath = sv("path", { d: cumPts.map((p, k) => (k === 0 ? "M" : "L") + p[0] + " " + p[1]).join(" "), fill: "none", stroke: "#c0392b", "stroke-width": 2.5 });
    const cumDots = cumPts.map((p) => sv("circle", { cx: p[0], cy: p[1], r: 3, fill: "#c0392b" }));
    const ref80 = sv("line", { x1: mL, y1: yPct(80), x2: W - mR, y2: yPct(80), stroke: "#c0392b", "stroke-dasharray": "4 4", "stroke-width": 1, opacity: 0.6 });
    const gl = []; for (let i = 0; i <= 4; i++) { const gy = y(max * i / 4); gl.push(sv("text", { x: mL - 8, y: gy + 4, "text-anchor": "end", "font-size": 10, fill: "#6b7a8d" }, "$" + Math.round(max * i / 4 / 1000) + "k")); }
    const pctLab = []; [0, 50, 80, 100].forEach((p) => pctLab.push(sv("text", { x: W - mR + 6, y: yPct(p) + 4, "font-size": 10, fill: "#c0392b" }, p + "%")));
    const labs = data2.map((e, i) => sv("text", { x: mL + i * bw + bw / 2, y: H - mB + 14, "text-anchor": "end", "font-size": 9.5, fill: "#6b7a8d", transform: "rotate(35 " + (mL + i * bw + bw / 2) + " " + (H - mB + 14) + ")" }, e[0]));
    const svg = sv("svg", { viewBox: "0 0 " + W + " " + H, width: "100%", preserveAspectRatio: "xMidYMid meet" }, ...gl, ref80, ...bars, cumPath, ...cumDots, ...pctLab, ...labs);
    return el("div.chart-wrap", svg);
  }

  /* ---------------- image helpers ---------------- */
  // destination cards now use looping VIDEO indicators (poster image until played).
  const DV = {
    a: "Videos/11335975-uhd_3840_2160_30fps.mp4",
    b: "Videos/14735703_3840_2160_30fps.mp4",
    c: "Videos/15607224_3840_2160_60fps.mp4",
  };
  const DEST_THEME = {
    // Canada ports
    "Halifax, NS": { g: "linear-gradient(135deg,#155a7d,#3aa9c9)", e: "⚓", s: "halifax", v: DV.a },
    "Quebec City, QC": { g: "linear-gradient(135deg,#5b4486,#a98fd4)", e: "🏰", s: "quebec-city", v: DV.b },
    "Saint John, NB": { g: "linear-gradient(135deg,#1f6e52,#56c596)", e: "🌲", s: "saint-john", v: DV.c },
    "Charlottetown, PEI": { g: "linear-gradient(135deg,#a85a2b,#e0a06a)", e: "🦞", s: "charlottetown", v: DV.b },
    // Elsewhere (international-waters gambling) destinations
    "International Waters (Casino)": { g: "linear-gradient(135deg,#7d2a47,#d46a8f)", e: "🎰", s: "intl-waters", v: DV.c },
    "Atlantic Casino Waters": { g: "linear-gradient(135deg,#5a2740,#c46a8f)", e: "🎲", s: "casino-star", v: DV.a },
    "Bermuda Casino Waters": { g: "linear-gradient(135deg,#2a6f8f,#7fd0e0)", e: "🏖️", s: "casino-star", v: DV.b },
    "Gulf Casino Waters": { g: "linear-gradient(135deg,#7a4a1f,#e0b070)", e: "🎲", s: "intl-waters", v: DV.c },
  };
  const imgBg = (slug, gradient) => `url('images/${slug}.jpg'), url('images/${slug}.png'), ${gradient}`;
  const imgBgSize = "cover, cover, cover";
  const imgBgPos = "center, center, center";

  const ADDON_DESC = {
    "Transportation": "Round-trip transfers between home and the departure port",
    "Meal Plan": "Specialty dining package across onboard restaurants",
    "Onboard Credit": "Spend onboard on drinks, spa, shops & more",
    "Port Excursions": "Guided shore tours at each port of call",
  };
  const ADDON_ICON = { "Transportation": "🚐", "Meal Plan": "🍽️", "Onboard Credit": "💳", "Port Excursions": "🏝️" };

  /* ---------------- app state ---------------- */
  const state = {
    tab: "book",
    adminView: "pricing",
    revGran: "month",
    aScope: "all", aPeriod: null,
    fcTarget: null, calMonth: null, calOpen: false,
    holt: { alpha: 0.6, beta: 0.3 },
    // Cost & Savings what-if assumptions (from the case study)
    cs: { revenue: 80000000, commPct: 12.5, capture: null, target: 50, opCost: 1000000 },
    wizardStep: 0,
    confirmed: null,
    form: null,
    flashId: null,
    // dashboard filters
    q: "", dShip: "All", dStatus: "All",
    sortKey: "departDate", sortDir: "asc",
  };

  function nextDate(days) {
    const d = new Date(data.today + "T00:00:00"); d.setDate(d.getDate() + days);
    return d.toISOString().slice(0, 10);
  }
  function freshForm() {
    return {
      first: "", last: "", email: "", country: "USA",
      category: "Canada", toPort: data.destinations.Canada[0],
      departDate: nextDate(21), nights: 7, duration: "1 Day",
      ship: data.ships.find((s) => s.category === "Canada").name,
      tripType: "Round Trip", cabinType: data.cabins[0].type, fareClass: "Standard",
      guests: 2, customerType: "Individual", company: "", addOns: [],
      pay: { name: "", number: "", expiry: "", cvv: "" },
    };
  }

  /* ---------------- pricing / summary ---------------- */
  function dqOf(f) { return data.dynamicQuote(f.category, f.ship, f.departDate); }
  function priceOf(f) {
    return data.priceReservation({
      category: f.category, nights: parseInt(f.nights, 10), duration: f.duration,
      cabinType: f.cabinType, fareClass: f.fareClass, tripType: f.tripType,
      guests: Math.max(1, parseInt(f.guests, 10) || 1), addOns: f.addOns, customerType: f.customerType,
      dynamicMult: dqOf(f).mult,
    });
  }

  function orderSummary(f, opts) {
    opts = opts || {};
    const guests = Math.max(1, parseInt(f.guests, 10) || 1);
    const p = priceOf(f);
    const box = el("div.summary-card" + (opts.flat ? ".flat" : ""));
    box.appendChild(el("h3", "Booking Summary"));
    const line = (a, b, cls) => box.appendChild(el("div.sum-line" + (cls ? "." + cls : ""), el("span", a), el("span", b)));
    line("Cruise type", f.category === "Canada" ? "Canada Cruise" : "Cruise to Somewhere");
    line("Route", `NY → ${shortPort(f.toPort)}`);
    line("Trip type", f.tripType + (f.tripType === "One-way" ? " (" + (data.currentPrices().oneWayPct) + "% fare)" : ""));
    line("Ship", f.ship);
    line("Departs", fmtDate(f.departDate));
    line("Duration", f.category === "Canada" ? `${f.nights} nights` : f.duration);
    if (f.category === "Canada") {
      line("Cabin", `${f.cabinType} (${cabinTier(f.cabinType)})`);
      line("Fare class", f.fareClass);
    }
    line("Guests", String(guests));
    if (f.addOns.length) line("Add-ons", f.addOns.join(", "));
    const dq = data.dynamicQuote(f.category, f.ship, f.departDate);
    if (dq.mult !== 1) {
      const pct = Math.round((dq.mult - 1) * 100);
      const up = pct > 0;
      box.appendChild(el("div.dyn-line" + (up ? ".up" : ".down"),
        el("span", (up ? "▲ Demand & timing  +" : "▼ Demand & timing  ") + pct + "%"),
        el("span.dyn-why", dq.reason)));
    }
    box.appendChild(el("div", { style: { height: "8px" } }));
    line("Cruise fare", fmtMoney(p.fare), "muted");
    if (p.addOnTotal) line("Add-ons", fmtMoney(p.addOnTotal), "muted");
    if (p.groupDiscount) line("Group discount", "−" + fmtMoney(p.groupDiscount), "muted");
    line("Taxes & fees", fmtMoney(p.taxes), "muted");
    line("Total", fmtMoney(p.total), "total");
    return { box, price: p };
  }

  /* ================================================================
     BOOKING WIZARD
     ================================================================ */
  function wizardSteps(f) {
    return f.category === "Canada"
      ? ["destination", "ship", "room", "dining", "guest", "payment"]
      : ["destination", "ship", "guest", "payment"];
  }
  const STEP_TITLE = {
    destination: "Destination & Date", ship: "Choose Ship", room: "Choose Room",
    dining: "Dining & Extras", guest: "Guest Details", payment: "Payment",
  };

  // live contextual summary of the choices made so far + running total
  function buildTripChips(f) {
    const guests = Math.max(1, parseInt(f.guests, 10) || 1);
    const p = priceOf(f);
    const chips = [
      "📍 NY → " + shortPort(f.toPort),
      (f.category === "Canada" ? "🗓️ " + f.nights + " nights" : "🗓️ " + f.duration),
      "🚢 " + f.ship,
    ];
    if (f.category === "Canada") chips.push("🛏️ " + f.cabinType + " · " + f.fareClass);
    if (f.addOns.length) chips.push("✨ " + f.addOns.length + " add-on" + (f.addOns.length > 1 ? "s" : ""));
    chips.push("👥 " + guests);
    chips.push("💲 " + fmtMoney(p.total) + " total");
    return el("div.trip-chips", ...chips.map((c) => el("span.trip-chip", c)));
  }

  function buildStepper(steps, current) {
    const bar = el("div.wizard-steps");
    steps.forEach((key, i) => {
      const cls = i < current ? ".done" : i === current ? ".active" : "";
      const node = el("div.wstep" + cls,
        el("div.wnum", i < current ? "✓" : String(i + 1)),
        el("div.wlabel", STEP_TITLE[key]));
      if (i < current) node.addEventListener("click", () => { state.wizardStep = i; mountApp(); });
      bar.appendChild(node);
    });
    return bar;
  }

  // small reusable controls bound to the persistent form
  function field(label, control) { return el("div.field", el("label", label), control); }
  function textInput(obj, key, type, attrs) {
    const i = el("input", Object.assign({ type: type || "text", value: obj[key] || "" }, attrs || {}));
    i.addEventListener("input", (e) => { obj[key] = e.target.value; });
    return i;
  }
  function selectInput(f, key, opts, onAfter) {
    const s = el("select");
    opts.forEach((o) => s.appendChild(el("option", o)));
    s.value = f[key];
    s.addEventListener("change", (e) => { f[key] = e.target.value; if (onAfter) onAfter(); mountApp(); });
    return s;
  }
  function dateInput(f, key) {
    const i = el("input", { type: "date", value: f[key] });
    i.addEventListener("change", (e) => { f[key] = e.target.value; mountApp(); });
    return i;
  }
  function numInput(f, key, attrs) {
    const i = el("input", Object.assign({ type: "number", value: f[key] }, attrs || {}));
    i.addEventListener("change", (e) => { f[key] = e.target.value; mountApp(); });
    return i;
  }

  function setCategory(f, cat) {
    f.category = cat;
    if (cat === "Canada") {
      if (!data.destinations.Canada.includes(f.toPort)) f.toPort = data.destinations.Canada[0];
      f.ship = data.ships.find((s) => s.category === "Canada").name;
      if (!f.cabinType) f.cabinType = data.cabins[0].type;
    } else {
      f.toPort = data.destinations.Somewhere[0];
      f.ship = data.ships.find((s) => s.category === "Somewhere").name;
      f.addOns = [];
    }
  }

  // scheduled sailings for a destination (and optionally a ship), upcoming only
  function upcomingSailings(toPort, ship) {
    return data.schedule
      .filter((s) => s.toPort === toPort && s.departDate >= data.today && (!ship || s.ship === ship))
      .sort((a, b) => a.departDate.localeCompare(b.departDate));
  }
  function applySailing(f, s) {
    // schedule fixes the date + ship only; nights/duration stay the customer's choice
    f.departDate = s.departDate; f.ship = s.ship; f.sailingId = s.id;
  }
  // make sure f points at a REAL scheduled sailing for its destination (keeps ship if it serves it)
  function syncSailing(f) {
    const all = upcomingSailings(f.toPort);
    if (!all.length) { f.noTrip = true; return; }
    f.noTrip = false;
    const byShip = upcomingSailings(f.toPort, f.ship);
    const pool = byShip.length ? byShip : all;
    applySailing(f, pool.find((s) => s.departDate === f.departDate && s.ship === f.ship) || pool[0]);
  }

  // date field button (toggles the calendar open/closed)
  function buildDateButton(f) {
    const dp = el("div.dp");
    const display = el("button.dp-display", fmtDate(f.departDate), el("span.dp-caret", state.calOpen ? "▴" : "▾"));
    display.addEventListener("click", (e) => { e.stopPropagation(); state.calOpen = !state.calOpen; state.calMonth = f.departDate.slice(0, 7); mountApp(); });
    dp.appendChild(display);
    return dp;
  }
  // full-width calendar block; ONLY trip days are selectable, no-trip days are disabled
  function buildCalendarBlock(f) {
    const sails = upcomingSailings(f.toPort);
    const byDate = {};
    sails.forEach((s) => { (byDate[s.departDate] = byDate[s.departDate] || []).push(s); });
    const months = Array.from(new Set(sails.map((s) => s.departDate.slice(0, 7)))).sort();
    const minM = months[0] || data.today.slice(0, 7), maxM = months[months.length - 1] || minM;
    if (!state.calMonth) state.calMonth = f.departDate.slice(0, 7);
    if (state.calMonth < minM) state.calMonth = minM;
    if (state.calMonth > maxM) state.calMonth = maxM;
    const cm = state.calMonth, y = +cm.slice(0, 4), mo = +cm.slice(5, 7);
    const startDow = new Date(y, mo - 1, 1).getDay(), days = new Date(y, mo, 0).getDate();
    const cal = el("div.cal");
    const prev = el("button.cal-nav", "‹"); prev.disabled = cm <= minM;
    prev.addEventListener("click", (e) => { e.stopPropagation(); state.calMonth = addMonths(cm, -1); mountApp(); });
    const next = el("button.cal-nav", "›"); next.disabled = cm >= maxM;
    next.addEventListener("click", (e) => { e.stopPropagation(); state.calMonth = addMonths(cm, 1); mountApp(); });
    cal.appendChild(el("div.cal-head", prev,
      el("div.cal-title", new Date(y, mo - 1, 1).toLocaleDateString("en-US", { month: "long", year: "numeric" })), next));
    const dow = el("div.cal-grid");
    ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"].forEach((d) => dow.appendChild(el("div.cal-dow", d)));
    cal.appendChild(dow);
    const gridc = el("div.cal-grid.cal-days");
    for (let i = 0; i < startDow; i++) gridc.appendChild(el("div.cal-cell.empty"));
    for (let d = 1; d <= days; d++) {
      const ds = cm + "-" + String(d).padStart(2, "0");
      const has = byDate[ds];
      // trip day = highlighted & clickable; no-trip day = disabled (not selectable)
      const cell = el("div.cal-cell" + (has ? ".has" : ".off") + (f.departDate === ds ? ".sel" : ""), String(d));
      if (has) {
        cell.appendChild(el("div.cal-dot"));
        cell.addEventListener("click", (e) => { e.stopPropagation(); applySailing(f, has.find((x) => x.ship === f.ship) || has[0]); state.calOpen = false; mountApp(); });
      }
      gridc.appendChild(cell);
    }
    while (gridc.children.length < 42) gridc.appendChild(el("div.cal-cell.empty")); // always 6 rows → consistent height
    cal.appendChild(gridc);
    cal.appendChild(el("div.cal-legend", el("span.lg.lg-has"), "trip available", el("span.lg.lg-off"), "no trip"));
    return el("div.cal-block", cal);
  }

  /* ----- STEP 1: Destination & Date ----- */
  function stepDestination(f) {
    const wrap = el("div");
    wrap.appendChild(el("p.step-lead", "Where would you like to sail, and when?"));

    const toggle = el("div.fc-toggle");
    [["Canada", "Canada Cruise (7 / 9 nights)"], ["Somewhere", "Cruise to Somewhere (Day / Casino)"]]
      .forEach(([cat, label]) => {
        const b = el("button" + (f.category === cat ? ".on" : ""), label);
        b.addEventListener("click", () => { setCategory(f, cat); state.calOpen = false; state.calMonth = null; mountApp(); });
        toggle.appendChild(b);
      });
    wrap.appendChild(toggle);

    // date / length / guests / trip type — plain native date picker (all dates selectable)
    const lengthField = f.category === "Canada"
      ? el("div.fc-field", el("label", "Number of nights"), selectInput(f, "nights", [7, 9]))
      : el("div.fc-field", el("label", "Duration"), selectInput(f, "duration", ["1 Day", "Half Day"]));
    wrap.appendChild(el("div.fc-row", { style: { marginTop: "6px" } },
      el("div.fc-field", el("label", "Departure date"), dateInput(f, "departDate")),
      lengthField,
      el("div.fc-field", el("label", "Guests"), numInput(f, "guests", { min: 1, max: 60 })),
      el("div.fc-field", el("label", "Trip type"), selectInput(f, "tripType", ["Round Trip", "One-way"]))));

    // destination "offers" cards
    wrap.appendChild(el("div.section-head", { style: { marginTop: "22px" } }, "Available Cruises"));
    const ports = f.category === "Canada" ? data.destinations.Canada : data.destinations.Somewhere;
    const grid = el("div.dest-cards");
    ports.forEach((port) => {
      const theme = DEST_THEME[port] || { g: "linear-gradient(135deg,#155a7d,#3aa9c9)", e: "🚢", s: "sea-bg" };
      const selected = f.toPort === port;
      const video = el("video.dc-video", { loop: "", playsinline: "", preload: "none", poster: `images/${theme.s}.jpg` });
      video.muted = true;
      if (theme.v) video.appendChild(el("source", { src: theme.v, type: "video/mp4" }));
      const play = () => { try { video.play(); } catch (e) {} };
      const stop = () => { try { video.pause(); } catch (e) {} };
      const card = el("div.dest-card" + (selected ? ".selected" : ""),
        { style: { background: imgBg(theme.s, theme.g), backgroundSize: imgBgSize, backgroundPosition: imgBgPos } },
        video, el("div.dest-emoji", theme.e),
        el("div.dc-body", el("div.dc-name", port),
          el("div.dc-sub", f.category === "Canada" ? "7 / 9-night cruise" : "Day cruise · casino")));
      card.addEventListener("mouseenter", play);
      card.addEventListener("mouseleave", () => { if (!selected) stop(); });
      card.addEventListener("click", () => { f.toPort = port; state.calOpen = false; state.calMonth = null; mountApp(); });
      if (selected) requestAnimationFrame(play);
      grid.appendChild(card);
    });
    wrap.appendChild(grid);
    return wrap;
  }

  /* ----- STEP 2: Ship ----- */
  function stepShip(f) {
    const wrap = el("div");
    wrap.appendChild(el("p.step-lead", "Choose your ship for this " + (f.category === "Canada" ? "Canada cruise." : "day cruise.")));
    const shipOpts = data.ships.filter((s) => s.category === f.category);
    if (!shipOpts.find((s) => s.name === f.ship)) f.ship = shipOpts[0].name;
    const grid = el("div.ship-cards");
    shipOpts.forEach((s) => {
      const thumb = el("div.ship-thumb", { style: { background: imgBg(s.slug, "linear-gradient(135deg,#155a7d,#3aa9c9)"), backgroundSize: imgBgSize, backgroundPosition: imgBgPos } });
      const card = el("div.ship-card" + (f.ship === s.name ? ".selected" : ""), thumb,
        el("div",
          el("div.ship-name", s.name),
          el("div.ship-desig", s.designation),
          el("div.ship-meta", `${s.shipClass} · ${s.capacity.toLocaleString()} ${s.category === "Canada" ? "guests · " + s.rooms + " rooms" : "seats"} · ${s.decks} decks`),
          el("div.ship-meta", s.route)));
      card.addEventListener("click", () => { f.ship = s.name; mountApp(); });
      grid.appendChild(card);
    });
    wrap.appendChild(grid);
    return wrap;
  }

  /* ----- STEP 3: Room (cabin) ----- */
  function stepRoom(f) {
    const wrap = el("div");
    wrap.appendChild(el("p.step-lead", "Select your stateroom. Prices are the total for your dates, guests and fare class."));
    const gN = Math.max(1, parseInt(f.guests, 10) || 1);
    const gNights = parseInt(f.nights, 10) || 7;
    const dynM = dqOf(f).mult;
    const priced = data.cabins.map((c) => ({
      c, total: data.priceReservation({ category: "Canada", nights: gNights, cabinType: c.type, fareClass: f.fareClass, tripType: f.tripType, guests: gN, addOns: f.addOns, customerType: f.customerType, dynamicMult: dynM }).total,
    }));
    const lowest = Math.min(...priced.map((x) => x.total));
    const grid = el("div.cabin-rich");
    priced.forEach(({ c, total }) => {
      const isLow = total === lowest;
      const img = el("div.crc-img", { style: { backgroundImage: `url('images/${c.img}.jpg'), url('images/${c.img}.png')` } });
      if (isLow) img.appendChild(el("div.crc-badge", "Lowest price"));
      const btn = el("button.crc-select", f.cabinType === c.type ? "✓ Selected" : "Select");
      btn.addEventListener("click", () => { f.cabinType = c.type; mountApp(); });
      grid.appendChild(el("div.crc" + (f.cabinType === c.type ? ".selected" : ""), img,
        el("div.crc-body",
          el("div.crc-top",
            el("div", el("span.crc-name", c.type), el("span.crc-tier." + c.tier, c.tier)),
            el("div.crc-price" + (isLow ? ".low" : ""), fmtMoney(total))),
          el("div.crc-perperson", "~" + fmtMoney(total / gN) + " / guest · " + c.sqft),
          el("div.crc-sleeps", "👥 Sleeps " + c.sleeps),
          el("ul.crc-feat", ...c.features.map((ft) => el("li", ft))),
          el("div.crc-foot", btn))));
    });
    wrap.appendChild(grid);

    wrap.appendChild(el("div.section-head", { style: { marginTop: "20px" } }, "Fare Class"));
    const fareGrid = el("div.fare-toggle");
    data.fareClasses.forEach((fc) => {
      const opt = el("div.fare-opt" + (f.fareClass === fc.name ? ".selected" : ""),
        el("div.fo-name", fc.name + (fc.extra > 0 ? `  (+${fmtMoney(fc.extra)}/guest)` : "")),
        el("div.fo-blurb", fc.blurb));
      opt.addEventListener("click", () => { f.fareClass = fc.name; mountApp(); });
      fareGrid.appendChild(opt);
    });
    wrap.appendChild(fareGrid);
    return wrap;
  }

  /* ----- STEP 4: Dining & Extras ----- */
  function stepDining(f) {
    const wrap = el("div");
    wrap.appendChild(el("p.step-lead", "Add dining and extras (optional). Prices are per guest."));
    const grid = el("div.extra-grid");
    data.addOns.forEach((a) => {
      const on = f.addOns.includes(a.name);
      const card = el("div.extra-card" + (on ? ".on" : ""),
        el("div.ex-ico", ADDON_ICON[a.name] || "✨"),
        el("div.ex-body",
          el("div.ex-name", a.name),
          el("div.ex-desc", ADDON_DESC[a.name] || "")),
        el("div.ex-price", "+" + fmtMoney(a.price) + "/guest"),
        el("div.ex-check", on ? "✓" : "+"));
      card.addEventListener("click", () => {
        if (on) f.addOns = f.addOns.filter((x) => x !== a.name);
        else f.addOns.push(a.name);
        mountApp();
      });
      grid.appendChild(card);
    });
    wrap.appendChild(grid);
    return wrap;
  }

  /* ----- STEP 5: Guest details ----- */
  function stepGuest(f) {
    const wrap = el("div");
    wrap.appendChild(el("p.step-lead", "Tell us who's sailing (this signs the lead guest up with ABC Cruise Lines)."));
    wrap.appendChild(el("div.field-row",
      field("First name", textInput(f, "first")),
      field("Last name", textInput(f, "last"))));
    wrap.appendChild(el("div.field-row",
      field("Email", textInput(f, "email", "email", { placeholder: "name@example.com" })),
      field("Country", selectInput(f, "country", ["USA", "Canada", "UK", "Germany", "Jordan", "France", "Mexico", "Brazil"]))));
    wrap.appendChild(el("div.field-row",
      field("Guests", numInput(f, "guests", { min: 1, max: 60 })),
      field("Customer type", selectInput(f, "customerType", data.customerTypes))));
    if (f.customerType === "Corporate Group")
      wrap.appendChild(field("Company", textInput(f, "company", "text", { placeholder: "Company name" })));
    return wrap;
  }

  /* ----- STEP 6: Payment ----- */
  function stepPayment(f) {
    const wrap = el("div.pay-grid");
    const { box, price } = orderSummary(f, { flat: true });
    wrap.appendChild(box);

    const form = el("div.panel.pay-form");
    form.appendChild(el("h3", "Payment"));
    form.appendChild(el("p.form-note", "Demo only — no real card is processed. Enter any test values."));
    form.appendChild(field("Cardholder name", textInput(f.pay, "name", "text", { placeholder: "Name on card" })));
    form.appendChild(field("Card number", textInput(f.pay, "number", "text", { placeholder: "4111 1111 1111 1111", maxlength: 23, inputmode: "numeric" })));
    form.appendChild(el("div.field-row",
      field("Expiry (MM/YY)", textInput(f.pay, "expiry", "text", { placeholder: "08/29", maxlength: 5 })),
      field("CVV", textInput(f.pay, "cvv", "text", { placeholder: "123", maxlength: 4, inputmode: "numeric" }))));

    const pay = el("button.btn", "Pay " + fmtMoney(price.total) + " & Confirm");
    pay.addEventListener("click", () => submit(f, price));
    form.appendChild(pay);
    form.appendChild(el("div.saved-note", "💾 On confirmation your reservation is saved in this browser and registered in the Ship Dashboard."));
    wrap.appendChild(form);
    return wrap;
  }

  function validateStep(f, key) {
    if (key === "guest") {
      if (!f.first.trim() || !f.last.trim()) { showToast("Please enter the lead guest's first and last name.", true); return false; }
    }
    return true;
  }

  function submit(f, price) {
    const pay = f.pay;
    const digits = (pay.number || "").replace(/\D/g, "");
    if (!pay.name.trim()) { showToast("Enter the cardholder name.", true); return; }
    if (digits.length < 12) { showToast("Enter a valid card number.", true); return; }
    if (!/^\d{2}\/\d{2}$/.test(pay.expiry || "")) { showToast("Enter expiry as MM/YY.", true); return; }
    if ((pay.cvv || "").length < 3) { showToast("Enter a valid CVV.", true); return; }

    const guests = Math.max(1, parseInt(f.guests, 10) || 1);
    const nights = f.category === "Canada" ? parseInt(f.nights, 10) : 0;
    const d = new Date(f.departDate + "T00:00:00");
    if (f.category === "Canada") d.setDate(d.getDate() + nights);
    const ret = d.toISOString().slice(0, 10);
    const maxId = data.reservations.reduce((m, r) => { const n = parseInt(String(r.id).replace("ABC-", ""), 10); return isNaN(n) ? m : Math.max(m, n); }, 100000);
    const id = "ABC-" + String(maxId + 1);
    const commissionSaved = Math.round(price.total * data.commissionRate);

    const r = {
      id, leadGuest: `${f.first} ${f.last}`.trim(), email: f.email || "n/a", country: f.country,
      company: f.customerType === "Corporate Group" ? (f.company || "Group") : null,
      customerType: f.customerType, channel: "In-house", category: f.category,
      fromPort: data.fromPort, toPort: f.toPort, tripType: f.tripType, ship: f.ship,
      departDate: f.departDate, returnDate: ret, nights,
      duration: f.category === "Somewhere" ? f.duration : null,
      cabinType: f.category === "Canada" ? f.cabinType : null,
      cabinNo: f.category === "Canada" ? `${10}${String(((data.reservations.length * 7) % 60) + 1).padStart(3, "0")}` : "",
      deck: f.category === "Canada" ? 10 : 0, fareClass: f.fareClass,
      dynamicMult: dqOf(f).mult, dynReason: dqOf(f).reason,
      guests, addOns: f.addOns.slice(),
      fare: price.fare, addOnTotal: price.addOnTotal, groupDiscount: price.groupDiscount, taxes: price.taxes,
      total: price.total, balanceDue: 0, amountPaid: price.total, paymentStatus: "Paid",
      cardLast4: digits.slice(-4), commissionSaved, commissionPaid: 0,
      status: "Confirmed", bookedOn: data.today,
    };
    data.reservations.push(r);
    persist(r);
    state.confirmed = id;
    mountApp();
  }

  /* ----- Confirmation ----- */
  function buildConfirmation() {
    const r = data.reservations.find((x) => x.id === state.confirmed);
    const card = el("div.confirm-card");
    card.appendChild(el("img.confirm-logo", { src: "images/abc_cruise_logo_v5.svg", alt: data.company + " logo" }));
    card.appendChild(el("div.confirm-ico", "🎉"));
    card.appendChild(el("h2", "Reservation Confirmed!"));
    card.appendChild(el("p.confirm-sub", "Booking " + (r ? r.id : "") + " is paid and registered."));
    if (r) {
      card.appendChild(el("div.confirm-line", `${r.leadGuest} · ${r.ship}`));
      card.appendChild(el("div.confirm-line", `${r.fromPort} → ${shortPort(r.toPort)} · ${r.category === "Canada" ? r.nights + " nights" : r.duration} · departs ${fmtDate(r.departDate)}`));
      card.appendChild(el("div.confirm-total", "Paid " + fmtMoney(r.total)));
    }
    card.appendChild(el("p.confirm-note", "A confirmation has been sent to " + (r ? r.email : "your email") + ". Your reservation is now registered with ABC Cruise Lines."));
    const again = el("button.btn", "Book another cruise");
    again.addEventListener("click", () => { state.confirmed = null; state.wizardStep = 0; state.form = null; mountApp(); });
    card.appendChild(again);
    return el("div.panel", card);
  }

  function buildWizard() {
    if (!state.form) state.form = freshForm();
    const f = state.form;
    if (state.confirmed) return buildConfirmation();

    const steps = wizardSteps(f);
    if (state.wizardStep >= steps.length) state.wizardStep = steps.length - 1;
    const key = steps[state.wizardStep];

    const panel = el("div.panel.res-panel");
    panel.appendChild(el("h2", "Book a Cruise ", el("span.hint", "ABC Cruise Lines · " + data.fromPort)));

    panel.appendChild(el("div.step-title-lg",
      el("span.step-count", `Step ${state.wizardStep + 1} of ${steps.length}`),
      " · " + STEP_TITLE[key]));

    const body =
      key === "destination" ? stepDestination(f) :
      key === "ship" ? stepShip(f) :
      key === "room" ? stepRoom(f) :
      key === "dining" ? stepDining(f) :
      key === "guest" ? stepGuest(f) :
      stepPayment(f);
    panel.appendChild(body);

    // nav (payment step has its own Pay button, no Next)
    const nav = el("div.wizard-nav");
    const back = el("button.btn-back", "‹ Back");
    back.disabled = state.wizardStep === 0;
    back.addEventListener("click", () => { if (state.wizardStep > 0) { state.wizardStep--; mountApp(); } });
    nav.appendChild(back);
    if (key !== "payment") {
      const next = el("button.btn-next", "Continue ›");
      next.addEventListener("click", () => { if (validateStep(f, key)) { state.wizardStep++; mountApp(); } });
      nav.appendChild(next);
    } else {
      nav.appendChild(el("div"));
    }
    panel.appendChild(nav);
    return panel;
  }

  /* ================================================================
     SHIP DASHBOARD (registry of all reservations)
     ================================================================ */
  function dashStats() {
    const all = data.reservations;
    const active = all.filter((r) => r.status !== "Cancelled");
    const guests = active.reduce((s, r) => s + r.guests, 0);
    const revenue = active.reduce((s, r) => s + r.total, 0);
    const cards = [
      ["🧾", "Total Reservations", all.length],
      ["👥", "Guests Booked", guests.toLocaleString()],
      ["💵", "Total Revenue", fmtMoney(revenue)],
    ];
    return el("div.kpis.kpis-3",
      cards.map(([ico, label, val]) => el("div.kpi.k1", el("div.kicon", ico), el("div.label", label), el("div.value", String(val)))));
  }

  function getRows() {
    const needle = state.q.trim().toLowerCase();
    let rows = data.reservations.filter((r) => {
      if (state.dShip !== "All" && r.ship !== state.dShip) return false;
      if (state.dStatus !== "All" && r.status !== state.dStatus) return false;
      if (needle) {
        const hay = (r.id + " " + r.leadGuest + " " + r.toPort + " " + (r.company || "")).toLowerCase();
        if (!hay.includes(needle)) return false;
      }
      return true;
    });
    const { sortKey: k, sortDir: dir } = state;
    rows.sort((a, b) => { let av = a[k], bv = b[k]; if (typeof av === "string") { av = av.toLowerCase(); bv = bv.toLowerCase(); } return av < bv ? (dir === "asc" ? -1 : 1) : av > bv ? (dir === "asc" ? 1 : -1) : 0; });
    return rows;
  }

  const COLUMNS = [
    { key: "id", label: "Booking" }, { key: "leadGuest", label: "Guest" }, { key: "ship", label: "Ship" },
    { key: "toPort", label: "Destination" }, { key: "departDate", label: "Departs" },
    { key: "paymentStatus", label: "Payment" }, { key: "status", label: "Status" }, { key: "total", label: "Total", num: true },
  ];

  /* ----- CSV export (Excel-friendly) ----- */
  const CSV_COLS = [
    ["id", "Booking ID"], ["leadGuest", "Lead Guest"], ["email", "Email"], ["country", "Country"],
    ["customerType", "Customer Type"], ["company", "Company"], ["channel", "Channel"],
    ["category", "Cruise Type"], ["ship", "Ship"], ["fromPort", "From"], ["toPort", "Destination"],
    ["departDate", "Departs"], ["returnDate", "Returns"], ["nights", "Nights"], ["duration", "Duration"],
    ["cabinType", "Cabin"], ["fareClass", "Fare Class"], ["guests", "Guests"], ["addOns", "Add-ons"],
    ["fare", "Fare"], ["addOnTotal", "Add-on Total"], ["groupDiscount", "Group Discount"],
    ["taxes", "Taxes"], ["total", "Total"], ["paymentStatus", "Payment Status"],
    ["cardLast4", "Card Last4"], ["status", "Status"], ["bookedOn", "Booked On"],
  ];
  function exportCSV() {
    const rows = getRows(); // respects current search/filters
    const esc = (v) => {
      if (v == null) v = "";
      if (Array.isArray(v)) v = v.join("; ");
      v = String(v);
      return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
    };
    const header = CSV_COLS.map(([, label]) => esc(label)).join(",");
    const body = rows.map((r) => CSV_COLS.map(([k]) => esc(r[k])).join(",")).join("\n");
    const csv = "﻿" + header + "\n" + body; // BOM so Excel reads UTF-8
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = el("a", { href: url, download: "abc_reservations_" + data.today + ".csv" });
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast(rows.length + " reservation" + (rows.length === 1 ? "" : "s") + " exported to CSV.");
  }

  function buildDashboardTable(mount) {
    const search = el("input", { type: "search", placeholder: "Search guest, booking #, destination…", value: state.q });
    search.addEventListener("input", (e) => { state.q = e.target.value; render(); pill(); });
    function sel(val, opts, set) { const s = el("select"); opts.forEach((o) => s.appendChild(el("option", o))); s.value = val; s.addEventListener("change", (e) => { set(e.target.value); render(); pill(); }); return s; }
    const shipSel = sel(state.dShip, ["All", ...data.ships.map((s) => s.name)], (v) => (state.dShip = v));
    const statusSel = sel(state.dStatus, ["All", ...data.statuses], (v) => (state.dStatus = v));
    const pillEl = el("span.count-pill", "");
    function pill() { pillEl.textContent = `${getRows().length} of ${data.reservations.length}`; }
    const toolbar = el("div.toolbar", search, shipSel, statusSel, el("div.spacer"), pillEl);
    const tableWrap = el("div.table-wrap");
    function render() {
      tableWrap.innerHTML = "";
      const rows = getRows();
      const thead = el("thead", el("tr", ...COLUMNS.map((c) => {
        const th = el("th" + (c.num ? ".num" : ""), c.label);
        if (state.sortKey === c.key) th.appendChild(el("span.arrow", state.sortDir === "asc" ? " ▲" : " ▼"));
        th.addEventListener("click", () => { if (state.sortKey === c.key) state.sortDir = state.sortDir === "asc" ? "desc" : "asc"; else { state.sortKey = c.key; state.sortDir = "asc"; } render(); });
        return th;
      })));
      const tbody = el("tbody");
      if (!rows.length) tbody.appendChild(el("tr", el("td.empty", { colspan: COLUMNS.length }, "No reservations match your filters.")));
      // group rows by departure MONTH (chronological)
      const groups = {};
      rows.forEach((r) => { const k = r.departDate.slice(0, 7); (groups[k] = groups[k] || []).push(r); });
      Object.keys(groups).sort().forEach((mk) => {
        const [y, m] = mk.split("-");
        const label = new Date(+y, +m - 1, 1).toLocaleDateString("en-US", { month: "long", year: "numeric" });
        const g = groups[mk];
        const monthTotal = g.filter((r) => r.status !== "Cancelled").reduce((s, r) => s + r.total, 0);
        tbody.appendChild(el("tr.month-row",
          el("td", { colspan: COLUMNS.length },
            label + "  ·  " + g.length + " reservation" + (g.length > 1 ? "s" : "") + "  ·  " + fmtMoney(monthTotal))));
        g.forEach((r) => {
          const tr = el("tr" + (r.id === state.flashId ? ".flash" : ""),
            el("td.mono", r.id),
            el("td", el("div.guest-name", r.leadGuest), el("div.sub-line", r.customerType === "Corporate Group" ? (r.company + " · " + r.guests + " pax") : (r.guests + " guest" + (r.guests > 1 ? "s" : "")))),
            el("td", r.ship),
            el("td", shortPort(r.toPort), el("div.sub-line", r.category === "Canada" ? (r.nights + "-night") : r.duration)),
            el("td.mono", fmtDate(r.departDate)),
            el("td", r.paymentStatus === "Paid" ? el("span.badge.Checked-in", "Paid") : el("span.badge.Pending", r.paymentStatus || "—")),
            el("td", el("span.badge." + r.status, r.status)),
            el("td.num.mono", r.total ? fmtMoney(r.total) : "—"));
          tr.addEventListener("click", () => openDrawer(r));
          tbody.appendChild(tr);
        });
      });
      tableWrap.appendChild(el("table", thead, tbody));
    }
    pill(); render();
    mount.appendChild(toolbar); mount.appendChild(tableWrap);
  }

  function openDrawer(r) {
    closeDrawer();
    const close = el("button.close", "×"); close.addEventListener("click", closeDrawer);
    const rows = [
      ["Cruise type", r.category === "Canada" ? "Canada Cruise" : "Cruise to Somewhere"],
      ["Route", `${r.fromPort} → ${r.toPort}`], ["Ship", shipLabel(r.ship)],
      ["Duration", r.category === "Canada" ? `${r.nights} nights` : r.duration],
      ["Departs", fmtDate(r.departDate)], ["Returns", fmtDate(r.returnDate)], ["Trip type", r.tripType],
      r.cabinType ? ["Cabin", `${r.cabinType} (${cabinTier(r.cabinType)}) — #${r.cabinNo} (Deck ${r.deck})`] : null,
      r.cabinType ? ["Fare class", r.fareClass || "Standard"] : null,
      ["Guests", String(r.guests)], ["Customer", r.customerType + (r.company ? ` · ${r.company}` : "")],
      ["Country", r.country], ["Email", r.email],
      r.addOns && r.addOns.length ? ["Add-ons", r.addOns.join(", ")] : null,
      ["Payment", (r.paymentStatus || "—") + (r.cardLast4 ? ` · card ••••${r.cardLast4}` : "")],
      ["Booked on", fmtDate(r.bookedOn)],
    ].filter(Boolean);
    const dl = el("dl.dl", ...rows.flatMap(([k, v]) => [el("dt", k), el("dd", v)]));
    const fare = el("div.fare-box",
      el("div.fare-line", el("span", "Cruise fare"), el("span", fmtMoney(r.fare))),
      r.addOnTotal ? el("div.fare-line", el("span", "Add-ons"), el("span", fmtMoney(r.addOnTotal))) : null,
      r.groupDiscount ? el("div.fare-line", el("span", "Group discount"), el("span", "−" + fmtMoney(r.groupDiscount))) : null,
      el("div.fare-line", el("span", "Taxes & fees"), el("span", fmtMoney(r.taxes))),
      el("div.fare-line.total", el("span", "Total paid"), el("span", r.total ? fmtMoney(r.total) : "—")),
      r.status === "Cancelled" ? el("div.fare-line", el("span", "Status"), el("span.due", "Cancelled")) : null);
    const drawer = el("div.drawer", { onclick: (e) => e.stopPropagation() },
      el("div.drawer-head", { style: { position: "relative" } }, close, el("div.id", r.id), el("h3", r.leadGuest), el("span.badge." + r.status, r.status)),
      el("div.drawer-body", dl, el("div.drawer-section-title", "Fare Summary"), fare));
    const scrim = el("div.drawer-scrim", { onclick: closeDrawer }, drawer); scrim.id = "drawerScrim";
    document.body.appendChild(scrim);
  }
  function closeDrawer() { const s = document.getElementById("drawerScrim"); if (s) s.remove(); }
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawer(); });

  /* ----- decision-support analytics (admin page only) ----- */
  function countUp(node, target, fmt, dur) {
    const start = performance.now(); dur = dur || 800;
    function step(now) { const t = Math.min(1, (now - start) / dur); node.textContent = fmt(target * (1 - Math.pow(1 - t, 3))); if (t < 1) requestAnimationFrame(step); }
    requestAnimationFrame(step);
  }
  const fmtMoneyShort = (n) => Math.abs(n) >= 1e6 ? "$" + (n / 1e6).toFixed(2) + "M" : Math.abs(n) >= 1e3 ? "$" + (n / 1e3).toFixed(1) + "K" : "$" + Math.round(n);

  function adminKpis() {
    const all = data.reservations, active = all.filter((r) => r.status !== "Cancelled");
    const revenue = active.reduce((s, r) => s + r.total, 0);
    const commSaved = all.reduce((s, r) => s + r.commissionSaved, 0);
    const inhouse = active.filter((r) => r.channel === "In-house").length;
    const capture = active.length ? (inhouse / active.length) * 100 : 0;
    const cards = [
      ["k1", "🛟", "Booked Revenue", revenue, fmtMoneyShort, active.length + " active bookings"],
      ["k2", "💰", "Commission Saved", commSaved, fmtMoneyShort, "in-house @ " + (data.commissionRate * 100) + "%"],
      ["k3", "🎯", "In-house Capture", capture, (n) => n.toFixed(0) + "%", "target " + (data.captureTarget * 100) + "%"],
      ["k4", "👥", "Guests Booked", active.reduce((s, r) => s + r.guests, 0), (n) => Math.round(n).toLocaleString(), "across all sailings"],
    ];
    return el("div.kpis", cards.map(([cls, ico, label, val, fmt, sub]) => {
      const v = el("div.value", fmt(0)); countUp(v, val, fmt);
      return el("div.kpi." + cls, el("div.kicon", ico), el("div.label", label), v, el("div.sub", sub));
    }));
  }

  function shipChart() {
    const m = {}; data.reservations.filter((r) => r.status !== "Cancelled").forEach((r) => { m[r.ship] = (m[r.ship] || 0) + r.total; });
    const rows = data.ships.map((s) => [s.name, m[s.name] || 0]).sort((a, b) => b[1] - a[1]);
    const max = Math.max(1, ...rows.map((r) => r[1]));
    return el("div.panel", el("h2", "Revenue by Ship ", el("span.hint", "active bookings")),
      ...rows.map(([ship, val]) => { const fill = el("div.bar-fill"); requestAnimationFrame(() => requestAnimationFrame(() => { fill.style.width = (val / max) * 100 + "%"; }));
        return el("div.bar-row", el("div.name", ship), el("div.bar-track", fill), el("div.val", fmtMoneyShort(val))); }));
  }

  function statusDonut(rows) {
    rows = rows || data.reservations;
    const m = {}; rows.forEach((r) => (m[r.status] = (m[r.status] || 0) + 1));
    const order = ["Confirmed", "Pending", "Checked-in", "Completed", "Cancelled"];
    const entries = order.filter((s) => m[s]).map((s) => [s, m[s]]); const total = entries.reduce((s, e) => s + e[1], 0) || 1;
    let acc = 0; const stops = entries.map(([s, c]) => { const a = (acc / total) * 360; acc += c; return `${STATUS_COLORS[s]} ${a}deg ${(acc / total) * 360}deg`; });
    const donut = el("div", { style: { width: "120px", height: "120px", borderRadius: "50%", background: `conic-gradient(${stops.join(",")})`, flexShrink: "0", display: "grid", placeItems: "center" } },
      el("div", { style: { width: "72px", height: "72px", borderRadius: "50%", background: "#fff", display: "grid", placeItems: "center", fontWeight: "720", fontSize: "20px" } }, String(total)));
    const legend = el("div.status-list", { style: { flex: "1" } }, ...entries.map(([s, c]) => el("div.status-item", el("span.swatch", { style: { background: STATUS_COLORS[s] } }), s, el("span.count", `${c} · ${Math.round((c / total) * 100)}%`))));
    return el("div.panel", el("h2", "Reservation Status"), el("div.donut-wrap", donut, legend));
  }

  function fleetPanel() {
    const byShip = {}; data.reservations.filter((r) => r.status !== "Cancelled").forEach((r) => { byShip[r.ship] = (byShip[r.ship] || 0) + 1; });
    return el("div.panel", el("h2", "Our Fleet ", el("span.hint", "3 ships")),
      ...data.ships.map((s) => el("div.fleet-row", el("div.fl-emoji", s.emoji),
        el("div", el("div.fl-name", s.name), el("div.fl-desig", s.designation + " · " + s.shipClass), el("div.fl-meta", s.route)),
        el("div.fl-cap", el("strong", s.capacity.toLocaleString()), (byShip[s.name] || 0) + " active bookings"))));
  }

  function occupancyPanel() {
    const cap = {}; data.ships.forEach((s) => (cap[s.name] = s.capacity));
    const sail = {};
    data.reservations.filter((r) => r.status !== "Cancelled" && r.departDate >= data.today).forEach((r) => {
      const k = r.ship + "|" + r.departDate; if (!sail[k]) sail[k] = { ship: r.ship, date: r.departDate, guests: 0, to: r.toPort }; sail[k].guests += r.guests;
    });
    const list = Object.values(sail).map((s) => { const occ = Math.min(100, Math.round((s.guests / (cap[s.ship] || 1)) * 100));
      const rec = occ >= 80 ? ["Raise price", "up"] : occ >= 50 ? ["Hold", "hold"] : ["Discount / promote", "down"]; return { ...s, occ, rec: rec[0], recCls: rec[1] }; })
      .sort((a, b) => a.date.localeCompare(b.date)).slice(0, 8);
    const col = (o) => (o >= 80 ? "#1c8a4d" : o >= 50 ? "#0a85c4" : "#b8860b");
    return el("div.panel", el("h2", "Demand & Dynamic Pricing ", el("span.hint", "upcoming sailings")),
      el("table.dss-table", el("thead", el("tr", el("th", "Ship"), el("th", "Departs"), el("th", "Destination"), el("th", "Occupancy"), el("th", "Recommendation"))),
        el("tbody", ...(list.length ? list : []).map((s) => el("tr", el("td", s.ship), el("td", fmtDate(s.date)), el("td", shortPort(s.to)),
          el("td", el("span.occ-bar", el("span.occ-fill", { style: { width: s.occ + "%", background: col(s.occ) } })), el("span", { style: { marginLeft: "8px" } }, s.occ + "%")),
          el("td", el("span.rec." + s.recCls, s.rec)))), list.length === 0 && el("tr", el("td.empty", { colspan: 5 }, "No upcoming sailings.")))));
  }

  // Pricing Control — the company sets prices here; the customer site reads them
  function buildPricingPanel() {
    const work = JSON.parse(JSON.stringify(data.currentPrices()));
    const panel = el("div.panel.admin-pricing");
    panel.appendChild(el("h2", "Pricing Control ", el("span.hint", "revenue management — sets the prices customers pay")));

    function numField(label, obj, key, pre) {
      const inp = el("input", { type: "number", min: 0, step: "1", value: obj[key] });
      inp.addEventListener("input", (e) => { obj[key] = e.target.value; });
      return el("div.price-field", el("label", label),
        el("div.price-input", pre ? el("span.price-pre", pre) : null, inp));
    }
    function group(title, obj, pre) {
      panel.appendChild(el("div.price-group-title", title));
      const g = el("div.price-grid");
      Object.keys(obj).forEach((k) => g.appendChild(numField(k, obj, k, pre)));
      panel.appendChild(g);
    }
    // base cost for the trip (airline-style)
    panel.appendChild(el("div.price-group-title", "Base fare — base cost for the trip, per guest"));
    const baseGrid = el("div.price-grid");
    const base = { canada: work.baseCanada, day: work.baseDay, oneway: work.oneWayPct };
    baseGrid.appendChild(numField("Canada cruise base", base, "canada", "$"));
    baseGrid.appendChild(numField("Day cruise base", base, "day", "$"));
    baseGrid.appendChild(numField("One-way fare (% of round trip)", base, "oneway", "%"));
    panel.appendChild(baseGrid);

    group("Cabins — extra per night, per guest", work.cabins, "$");
    group("Day cruises — rate per guest", work.dayRates, "$");
    group("Add-ons — extra per guest", work.addOns, "$");

    panel.appendChild(el("div.price-group-title", "Premium option & taxes"));
    const misc = el("div.price-grid");
    const extra = { premium: work.premiumExtra, tax: work.taxPct };
    misc.appendChild(numField("Premium option (extra/guest)", extra, "premium", "$"));
    misc.appendChild(numField("Tax", extra, "tax", "%"));
    panel.appendChild(misc);

    const save = el("button.btn", "💾 Save prices → apply to customer site");
    save.addEventListener("click", () => {
      work.baseCanada = base.canada; work.baseDay = base.day; work.oneWayPct = base.oneway;
      work.premiumExtra = extra.premium; work.taxPct = extra.tax;
      data.savePrices(work);
      showToast("Prices saved — the customer booking site now uses these prices.");
    });
    const reset = el("button.btn.secondary", "Reset to defaults");
    reset.addEventListener("click", () => {
      data.resetPrices(); showToast("Prices reset to defaults — reloading…");
      setTimeout(() => { try { location.reload(); } catch (e) {} }, 500);
    });
    panel.appendChild(el("div.price-actions", save, reset));
    panel.appendChild(el("div.saved-note",
      "Saved in this browser and read by the customer site (index.html) on the same browser. Keep a customer tab open and it updates live when you save."));
    return panel;
  }

  // Dynamic Pricing tab — controls + instructions + live preview
  function buildDynamicPanel() {
    const work = JSON.parse(JSON.stringify(data.currentPrices()));
    if (!work.dyn) work.dyn = { enabled: true, surgePct: 25, discountPct: 12, earlyBirdPct: 8, lastMinutePct: 20 };
    const d = work.dyn;
    const wrap = el("div");

    // controls
    const panel = el("div.panel.admin-pricing");
    panel.appendChild(el("h2", "Dynamic Pricing ", el("span.hint", "revenue management — demand + time-to-departure")));
    const en = el("input", { type: "checkbox" }); en.checked = !!d.enabled;
    en.addEventListener("change", () => { d.enabled = en.checked; });
    panel.appendChild(el("label.addon-chk", { style: { maxWidth: "360px", marginBottom: "12px" } },
      en, "Enable dynamic pricing"));
    function numField(label, obj, key, pre) {
      const inp = el("input", { type: "number", min: 0, step: "1", value: obj[key] });
      inp.addEventListener("input", (e) => { obj[key] = e.target.value; });
      return el("div.price-field", el("label", label), el("div.price-input", pre ? el("span.price-pre", pre) : null, inp));
    }
    // demand thresholds — when the system calls a sailing "high" / "low" demand
    panel.appendChild(el("div.price-group-title", "Demand thresholds (occupancy % of the ship)"));
    const thr = el("div.price-grid");
    thr.appendChild(numField("High demand if occupancy ≥", d, "highPct", "%"));
    thr.appendChild(numField("Low demand if occupancy <", d, "lowPct", "%"));
    panel.appendChild(thr);

    panel.appendChild(el("div.price-group-title", "Price adjustments"));
    const grid = el("div.price-grid");
    grid.appendChild(numField("High-demand surge", d, "surgePct", "%"));
    grid.appendChild(numField("Low-demand discount", d, "discountPct", "%"));
    grid.appendChild(numField("Early-booking saver", d, "earlyBirdPct", "%"));
    grid.appendChild(numField("Last-minute swing", d, "lastMinutePct", "%"));
    panel.appendChild(grid);
    const save = el("button.btn", "💾 Save → apply to customer site");
    save.addEventListener("click", () => { data.savePrices(work); showToast("Dynamic pricing saved — customer fares now use these rules."); mountApp(); });
    panel.appendChild(el("div.price-actions", save));
    wrap.appendChild(panel);

    // instructions
    const info = el("div.panel");
    info.appendChild(el("h2", "How Dynamic Pricing Works"));
    info.appendChild(el("ul.dyn-rules",
      el("li", el("b", "Demand (from the live log): "), `a sailing is HIGH demand when it is ≥ ${d.highPct}% full → +${d.surgePct}% surge; LOW demand when under ${d.lowPct}% full → −${d.discountPct}% discount; in between, no change.`),
      el("li", el("b", "Time to departure: "), `more than 120 days out → −${d.earlyBirdPct}% early-booking saver · 4–21 days → +${Math.round(d.surgePct / 2)}% departing soon.`),
      el("li", el("b", "Last-minute (≤3 days): "), `surge +${d.lastMinutePct}% if the sailing is filling, or a −${d.lastMinutePct}% clearance deal if it is still empty.`),
      el("li", el("b", "Applied to: "), "the cruise fare (base + cabin/day rate). The flat Premium add-on and taxes are not surged. Final multiplier is capped between 0.6× and 1.8×."),
      el("li", el("b", "Where it shows: "), "the customer sees a transparent line (e.g. “▲ Demand & timing +25%”), cabin prices reprice, and each booking locks in its rate.")));
    wrap.appendChild(info);

    // live preview of upcoming sailings
    const sail = {};
    data.reservations.filter((r) => r.status !== "Cancelled" && r.departDate >= data.today)
      .forEach((r) => { const k = r.ship + "|" + r.departDate; if (!sail[k]) sail[k] = { ship: r.ship, date: r.departDate, cat: r.category }; });
    const list = Object.values(sail).map((s) => ({ s, q: data.dynamicQuote(s.cat, s.ship, s.date) }))
      .sort((a, b) => a.s.date.localeCompare(b.s.date)).slice(0, 12);
    const prev = el("div.panel");
    prev.appendChild(el("h2", "Live Price Preview ", el("span.hint", "upcoming sailings · current rules")));
    const prevRows = list.map((it) => {
      const s = it.s, q = it.q;
      const pct = Math.round((q.mult - 1) * 100);
      const cls = pct > 0 ? "up" : pct < 0 ? "down" : "hold";
      const label = pct === 0 ? "base price" : (pct > 0 ? "+" : "") + pct + "%";
      return el("tr",
        el("td", s.ship), el("td", fmtDate(s.date)), el("td", q.days + "d"),
        el("td", Math.round(q.occ * 100) + "%"),
        el("td", el("span.rec." + cls, label), el("div.sub-line", q.reason || "—")));
    });
    if (!prevRows.length) prevRows.push(el("tr", el("td.empty", { colspan: 5 }, "No upcoming sailings.")));
    prev.appendChild(el("table.dss-table",
      el("thead", el("tr", el("th", "Ship"), el("th", "Departs"), el("th", "Days out"), el("th", "Occupancy"), el("th", "Price effect"))),
      el("tbody", ...prevRows)));
    wrap.appendChild(prev);
    return wrap;
  }

  /* ----- Log Analytics — all computed live from data.reservations ----- */
  function aKpi(cls, ico, label, val, sub) {
    return el("div.kpi." + cls, el("div.kicon", ico), el("div.label", label), el("div.value", String(val)), el("div.sub", sub || ""));
  }
  function hbar(title, hint, entries, fmtVal) {
    const max = Math.max(1, ...entries.map((e) => e[1]));
    return el("div.panel", el("h2", title, hint ? el("span.hint", hint) : null),
      ...(entries.length ? entries.map(([label, val]) => {
        const fill = el("div.bar-fill");
        requestAnimationFrame(() => requestAnimationFrame(() => { fill.style.width = (val / max * 100) + "%"; }));
        return el("div.bar-row", el("div.name", label), el("div.bar-track", fill), el("div.val", fmtVal ? fmtVal(val) : String(val)));
      }) : [el("p.step-lead", "No data yet.")]));
  }
  function weekdayChart(rows) {
    rows = rows || data.reservations;
    const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
    const counts = [0, 0, 0, 0, 0, 0, 0];
    rows.forEach((r) => { counts[new Date(r.departDate + "T00:00:00").getDay()]++; });
    const order = [1, 2, 3, 4, 5, 6, 0];
    const entries = order.map((i) => [days[i], counts[i]]);
    const max = Math.max(1, ...entries.map((e) => e[1]));
    return el("div.panel", el("h2", "Reservations by Weekday ", el("span.hint", "by departure day")),
      el("div.vbars", ...entries.map(([lab, v]) => {
        const fill = el("div.vfill");
        requestAnimationFrame(() => requestAnimationFrame(() => { fill.style.height = (v / max * 100) + "%"; }));
        return el("div.vbar", el("div.vbar-val", String(v)), el("div.vbar-track", fill), el("div.vbar-lab", lab));
      })));
  }
  // revenue grouped by day / month / year (excludes cancelled), from the live log
  function revenueByPeriod(gran, rows) {
    rows = rows || data.reservations;
    const m = {};
    rows.filter((r) => r.status !== "Cancelled").forEach((r) => {
      const k = gran === "day" ? r.departDate : gran === "year" ? r.departDate.slice(0, 4) : r.departDate.slice(0, 7);
      if (!m[k]) m[k] = { rev: 0, count: 0, guests: 0 };
      m[k].rev += r.total; m[k].count++; m[k].guests += r.guests;
    });
    return Object.keys(m).sort().map((k) => Object.assign({ key: k }, m[k]));
  }
  function periodLabel(gran, k) {
    if (gran === "day") return fmtDate(k);
    if (gran === "year") return k;
    const p = k.split("-"); return new Date(+p[0], +p[1] - 1, 1).toLocaleDateString("en-US", { month: "short", year: "numeric" });
  }
  function buildRevenuePanel(rows) {
    const gran = state.revGran || "month";
    const periods = revenueByPeriod(gran, rows);
    const max = Math.max(1, ...periods.map((p) => p.rev));
    const totalRev = periods.reduce((s, p) => s + p.rev, 0);

    const panel = el("div.panel");
    const head = el("h2", "Revenue Over Time ", el("span.hint", "excludes cancelled · " + fmtMoney(totalRev) + " total"));
    panel.appendChild(head);

    // Day / Month / Year selector
    const sel = el("div.fc-toggle", { style: { marginBottom: "14px" } });
    [["day", "Per Day"], ["month", "Per Month"], ["year", "Per Year"]].forEach(([g, label]) => {
      const b = el("button" + (gran === g ? ".on" : ""), label);
      b.addEventListener("click", () => { state.revGran = g; mountApp(); });
      sel.appendChild(b);
    });
    panel.appendChild(sel);

    // line chart (revenue over time — proper case for a line)
    panel.appendChild(lineChart(periods.map((p) => ({ label: periodLabel(gran, p.key), val: p.rev }))));

    // list / table
    const tableRows = periods.map((p) => el("tr",
      el("td", periodLabel(gran, p.key)),
      el("td.num.mono", String(p.count)),
      el("td.num.mono", p.guests.toLocaleString()),
      el("td.num.mono", fmtMoney(p.rev))));
    if (!tableRows.length) tableRows.push(el("tr", el("td.empty", { colspan: 4 }, "No revenue yet.")));
    panel.appendChild(el("div.table-wrap", { style: { marginTop: "16px" } },
      el("table",
        el("thead", el("tr", el("th", gran === "day" ? "Day" : gran === "year" ? "Year" : "Month"),
          el("th.num", "Reservations"), el("th.num", "Guests"), el("th.num", "Revenue"))),
        el("tbody", ...tableRows))));
    return panel;
  }

  // scope: all time, a specific month, or a specific day (by departure date)
  function analyticsRows() {
    const all = data.reservations;
    if (state.aScope === "month" && state.aPeriod) return all.filter((r) => r.departDate.slice(0, 7) === state.aPeriod);
    if (state.aScope === "day" && state.aPeriod) return all.filter((r) => r.departDate === state.aPeriod);
    return all;
  }
  function periodKeys(gran) {
    const set = {};
    data.reservations.forEach((r) => { set[gran === "day" ? r.departDate : r.departDate.slice(0, 7)] = true; });
    return Object.keys(set).sort();
  }
  function buildScopeBar() {
    const panel = el("div.panel");
    panel.appendChild(el("h2", "Analytics Scope ", el("span.hint", "show all, or pick a specific month / day")));
    const toggle = el("div.fc-toggle");
    [["all", "All time"], ["month", "By Month"], ["day", "By Day"]].forEach(([s, label]) => {
      const b = el("button" + (state.aScope === s ? ".on" : ""), label);
      b.addEventListener("click", () => {
        state.aScope = s;
        if (s !== "all") { const ks = periodKeys(s); state.aPeriod = ks.indexOf(state.aPeriod) >= 0 ? state.aPeriod : (ks[ks.length - 1] || null); }
        mountApp();
      });
      toggle.appendChild(b);
    });
    panel.appendChild(toggle);
    if (state.aScope !== "all") {
      const ks = periodKeys(state.aScope);
      if (ks.indexOf(state.aPeriod) < 0) state.aPeriod = ks[ks.length - 1] || null;
      const sel = el("select");
      ks.forEach((k) => sel.appendChild(el("option", { value: k }, periodLabel(state.aScope, k))));
      sel.value = state.aPeriod || "";
      sel.addEventListener("change", (e) => { state.aPeriod = e.target.value; mountApp(); });
      panel.appendChild(el("div.field", { style: { maxWidth: "280px", marginTop: "12px" } },
        el("label", state.aScope === "month" ? "Select month" : "Select day"), sel));
    }
    return panel;
  }

  function buildAnalytics() {
    const all = analyticsRows();
    const active = all.filter((r) => r.status !== "Cancelled");
    const revenue = active.reduce((s, r) => s + r.total, 0);
    const guests = active.reduce((s, r) => s + r.guests, 0);
    const cancelled = all.length - active.length;

    const isDay = state.aScope === "day"; // single day → hide time-series & weekday charts

    const wrap = el("div");
    wrap.appendChild(buildScopeBar());
    wrap.appendChild(el("div", { style: { height: "18px" } }));
    wrap.appendChild(el("div.kpis",
      aKpi("k1", "📈", "Demand (reservations)", all.length, active.length + " active"),
      aKpi("k2", "💵", "Total $ (excl. cancelled)", fmtMoney(revenue), guests + " guests"),
      aKpi("k3", "🚢", "Active Guests", guests.toLocaleString(), "currently booked"),
      aKpi("k4", "🚫", "Cancelled", cancelled, (all.length ? Math.round(cancelled / all.length * 100) : 0) + "% of demand")));
    wrap.appendChild(el("div", { style: { height: "18px" } }));

    // Revenue over time — only meaningful across a range, hidden for a single day
    if (!isDay) {
      wrap.appendChild(buildRevenuePanel(all));
      wrap.appendChild(el("div", { style: { height: "18px" } }));
    }

    // demand by destination (count) — useful at every scope
    const dem = {};
    all.forEach((r) => { const k = shortPort(r.toPort); dem[k] = (dem[k] || 0) + 1; });
    const demEntries = Object.entries(dem).sort((a, b) => b[1] - a[1]);

    // ship utilization (active guests per ship; share of fleet guests)
    const totalG = guests || 1;
    const utilEntries = data.ships.map((s) => [s.name, active.filter((r) => r.ship === s.name).reduce((x, r) => x + r.guests, 0)]);
    const utilFmt = (v) => v.toLocaleString() + " · " + Math.round(v / totalG * 100) + "%";

    wrap.appendChild(el("div.grid2",
      hbar("Demand by Destination", "reservation count", demEntries),
      hbar("Ship Utilization", "active guests · share", utilEntries, utilFmt)));

    // Pareto (revenue by destination) — needs a range, hidden for a single day
    if (!isDay) {
      const revByDest = {};
      active.forEach((r) => { const k = shortPort(r.toPort); revByDest[k] = (revByDest[k] || 0) + r.total; });
      wrap.appendChild(el("div.panel",
        el("h2", "Revenue by Destination — Pareto ", el("span.hint", "bars = revenue · line = cumulative %")),
        paretoChart(Object.entries(revByDest))));
    }

    // status always; weekday only across a range
    if (isDay) wrap.appendChild(statusDonut(all));
    else wrap.appendChild(el("div.grid2", statusDonut(all), weekdayChart(all)));

    if (isDay) wrap.appendChild(el("footer.note",
      "Showing a single day — time-series (revenue trend), Pareto and weekday charts are hidden because they need a date range. Switch scope to All time or By Month to see them."));
    else wrap.appendChild(el("footer.note",
      "Live analytics — computed directly from the reservations log; they update automatically as the log changes (excludes cancelled from $)."));
    return wrap;
  }

  /* ----- Forecast: multiple linear regression (revenue ~ time + season + vacation + school) ----- */
  function solveLin(A, b) { // Gaussian elimination
    const n = b.length, M = A.map((r, i) => r.concat([b[i]]));
    for (let c = 0; c < n; c++) {
      let piv = c; for (let r = c + 1; r < n; r++) if (Math.abs(M[r][c]) > Math.abs(M[piv][c])) piv = r;
      const tmp = M[c]; M[c] = M[piv]; M[piv] = tmp;
      const d = M[c][c] || 1e-9;
      for (let j = c; j <= n; j++) M[c][j] /= d;
      for (let r = 0; r < n; r++) if (r !== c) { const f = M[r][c]; for (let j = c; j <= n; j++) M[r][j] -= f * M[c][j]; }
    }
    return M.map((r) => r[n]);
  }
  function regress(X, y, lambda) { // ridge OLS -> coefficients
    const n = X.length, p = X[0].length, A = [], b = [];
    for (let i = 0; i < p; i++) { A[i] = []; b[i] = 0; for (let j = 0; j < p; j++) { let s = 0; for (let k = 0; k < n; k++) s += X[k][i] * X[k][j]; A[i][j] = s + (i === j ? lambda : 0); } for (let k = 0; k < n; k++) b[i] += X[k][i] * y[k]; }
    return solveLin(A, b);
  }
  function addMonths(ym, k) { const p = ym.split("-"); let y = +p[0], m = +p[1] - 1 + k; y += Math.floor(m / 12); m = ((m % 12) + 12) % 12; return y + "-" + String(m + 1).padStart(2, "0"); }
  // Holt's linear (double exponential) smoothing
  function holtFit(series, alpha, beta) {
    if (!series.length) return { fitted: [], level: 0, trend: 0 };
    let level = series[0], trend = series.length > 1 ? series[1] - series[0] : 0;
    const fitted = [level];
    for (let t = 1; t < series.length; t++) {
      const prev = level;
      level = alpha * series[t] + (1 - alpha) * (level + trend);
      trend = beta * (level - prev) + (1 - beta) * trend;
      fitted.push(level);
    }
    return { fitted, level, trend };
  }
  // feature vector: [intercept, time-trend, summer/school-break, holiday/vacation, spring season]
  function fcFeat(t, mo) { return [1, t, (mo >= 6 && mo <= 8) ? 1 : 0, (mo === 12) ? 1 : 0, (mo >= 4 && mo <= 5) ? 1 : 0]; }
  const FC_LABELS = ["Base (intercept)", "Time trend (per month)", "Summer / school break (Jun–Aug)", "Holiday / vacation (Dec)", "Spring season (Apr–May)"];

  function buildForecast() {
    // today is June 2026 → only months up to now are ACTUAL; later months are forecast
    const curMonth = data.today.slice(0, 7);
    const m = {}, gm = {};
    data.reservations.filter((r) => r.status !== "Cancelled" && r.departDate.slice(0, 7) <= curMonth).forEach((r) => {
      const k = r.departDate.slice(0, 7); m[k] = (m[k] || 0) + r.total; gm[k] = (gm[k] || 0) + r.guests;
    });
    const md = Object.keys(m).sort().map((k) => ({ ym: k, rev: m[k] }));
    const wrap = el("div");
    if (md.length < 4) {
      wrap.appendChild(el("div.panel", el("h2", "Revenue Forecast"),
        el("p.step-lead", "Need at least 4 months of reservations to fit a regression model. There are " + md.length + " so far.")));
      return wrap;
    }
    const sp = md[0].ym.split("-"), sy = +sp[0], sm = +sp[1];
    const tOf = (ym) => { const p = ym.split("-"); return (+p[0] - sy) * 12 + (+p[1] - sm); };
    const moOf = (ym) => +ym.split("-")[1];
    const X = md.map((d) => fcFeat(tOf(d.ym), moOf(d.ym)));
    const y = md.map((d) => d.rev);
    const beta = regress(X, y, 1);
    const pred = (t, mo) => fcFeat(t, mo).reduce((s, v, i) => s + v * beta[i], 0);
    const ybar = y.reduce((a, b) => a + b, 0) / y.length;
    let ssRes = 0, ssTot = 0;
    md.forEach((d, i) => { const f = pred(tOf(d.ym), moOf(d.ym)); ssRes += Math.pow(y[i] - f, 2); ssTot += Math.pow(y[i] - ybar, 2); });
    const r2 = ssTot ? Math.max(0, 1 - ssRes / ssTot) : 0;

    // --- model summary ---
    const model = el("div.panel");
    model.appendChild(el("h2", "Revenue Forecast Model ", el("span.hint", "multiple linear regression · R² = " + r2.toFixed(2))));
    model.appendChild(el("p.step-lead", "Revenue is modelled from the log as: time trend + seasonality + vacation + school-break. Coefficients (effect on monthly revenue):"));
    const coefGrid = el("div.kpis");
    beta.forEach((b, i) => {
      const v = i === 1 ? (b >= 0 ? "+" : "") + fmtMoney(b) + "/mo" : (i === 0 ? fmtMoney(b) : (b >= 0 ? "+" : "−") + fmtMoney(Math.abs(b)));
      coefGrid.appendChild(el("div.kpi.k" + ((i % 4) + 1), el("div.label", FC_LABELS[i]), el("div.value", { style: { fontSize: "18px" } }, v)));
    });
    model.appendChild(coefGrid);
    wrap.appendChild(model);

    // --- actual + forecast line chart ---
    const series = md.map((d) => ({ label: periodLabel("month", d.ym), val: d.rev }));
    const lastYm = md[md.length - 1].ym, lastT = tOf(lastYm);
    for (let k = 1; k <= 6; k++) { const ym = addMonths(lastYm, k); series.push({ label: periodLabel("month", ym), val: Math.max(0, Math.round(pred(lastT + k, moOf(ym)))) }); }
    const chartP = el("div.panel");
    chartP.appendChild(el("h2", "Revenue — Actual vs Forecast ", el("span.hint", "as of " + periodLabel("month", curMonth) + " · solid = actual · dashed = forecast")));
    chartP.appendChild(lineChart(series, { forecastFrom: md.length }));
    wrap.appendChild(chartP);

    // --- Holt's double-exponential smoothing on DEMAND (guests) ---
    const dmonths = Object.keys(gm).sort();
    if (dmonths.length >= 3) {
      const a = Math.min(1, Math.max(0, +state.holt.alpha)), b = Math.min(1, Math.max(0, +state.holt.beta));
      const dseries = dmonths.map((k) => gm[k]);
      const hf = holtFit(dseries, a, b);
      const hpts = dmonths.map((k, i) => ({ label: periodLabel("month", k), val: dseries[i] }));
      const lastdm = dmonths[dmonths.length - 1];
      for (let k = 1; k <= 6; k++) hpts.push({ label: periodLabel("month", addMonths(lastdm, k)), val: Math.max(0, Math.round(hf.level + k * hf.trend)) });
      const hp = el("div.panel");
      hp.appendChild(el("h2", "Demand Forecast — Holt's smoothing ", el("span.hint", "guests/month · level + trend · solid = actual · dashed = forecast")));
      hp.appendChild(lineChart(hpts, { forecastFrom: dmonths.length }));
      // smoothing controls
      function holtNum(label, key) {
        const inp = el("input", { type: "number", min: 0, max: 1, step: 0.05, value: state.holt[key] });
        inp.addEventListener("change", (e) => { state.holt[key] = e.target.value; mountApp(); });
        return el("div.price-field", el("label", label), el("div.price-input", inp));
      }
      hp.appendChild(el("div.price-grid", { style: { marginTop: "12px", maxWidth: "420px" } },
        holtNum("α (level smoothing)", "alpha"), holtNum("β (trend smoothing)", "beta")));
      hp.appendChild(el("p.step-lead", { style: { marginTop: "10px" } },
        "Smoothed level ≈ " + Math.round(hf.level).toLocaleString() + " guests/mo, trend ≈ " + (hf.trend >= 0 ? "+" : "") + Math.round(hf.trend) + "/mo. Higher α reacts faster to recent demand; higher β tracks the trend more aggressively."));
      wrap.appendChild(hp);
    }

    // --- interactive predictor ---
    const future = Array.from({ length: 12 }, (_, k) => addMonths(lastYm, k + 1));
    if (future.indexOf(state.fcTarget) < 0) state.fcTarget = future[0];
    const tt = tOf(state.fcTarget), mm = moOf(state.fcTarget), f = fcFeat(tt, mm);
    const predVal = Math.max(0, Math.round(pred(tt, mm)));

    const predictor = el("div.panel");
    predictor.appendChild(el("h2", "Predict Revenue ", el("span.hint", "pick a future month")));
    const sel = el("select");
    future.forEach((ym) => sel.appendChild(el("option", { value: ym }, periodLabel("month", ym))));
    sel.value = state.fcTarget;
    sel.addEventListener("change", (e) => { state.fcTarget = e.target.value; mountApp(); });
    predictor.appendChild(el("div.field", { style: { maxWidth: "260px" } }, el("label", "Target month"), sel));
    predictor.appendChild(el("div.fc-predict", el("span", "Predicted revenue"), el("strong", fmtMoney(predVal))));
    const tags = [];
    if (f[2]) tags.push("summer / school break");
    if (f[3]) tags.push("holiday / vacation");
    if (f[4]) tags.push("spring season");
    predictor.appendChild(el("p.step-lead", "Active factors for " + periodLabel("month", state.fcTarget) + ": " + (tags.length ? tags.join(", ") : "off-peak month") + "."));
    predictor.appendChild(el("div.fc-breakdown",
      ...beta.map((b, i) => el("div.fc-row2", el("span", FC_LABELS[i]), el("span", (b * f[i] >= 0 ? "+" : "−") + fmtMoney(Math.abs(b * f[i])))))));
    predictor.appendChild(el("div.saved-note",
      "Indicative model from limited data — best for relative trends (which months are higher/lower), not exact dollars. For sell-out probability you'd use logistic regression (future work)."));
    wrap.appendChild(predictor);
    return wrap;
  }

  /* ----- Trip Schedule (monthly) — prices stay in sync with the pricing engine ----- */
  function schedFrom(s) {
    const dq = data.dynamicQuote(s.category, s.ship, s.departDate);
    const p = data.priceReservation({
      category: s.category, nights: s.nights, duration: s.duration, cabinType: "Interior",
      fareClass: "Standard", guests: 1, addOns: [], customerType: "Individual", dynamicMult: dq.mult,
    });
    return { total: p.total, dq };
  }
  function buildScheduleTab() {
    const wrap = el("div");
    wrap.appendChild(el("div.admin-banner",
      "🧠 Intelligent schedule — generated from forecasted demand (seasonality + destination popularity in the log), not random. " +
      "Peak months sail more often & longer to popular ports; low months lay up capacity. Prices stay in sync with Pricing & Dynamic Pricing."));
    const byMonth = {};
    data.schedule.forEach((s) => { const k = s.departDate.slice(0, 7); (byMonth[k] = byMonth[k] || []).push(s); });
    const demLabel = (v) => v >= 0.7 ? ["High demand", "up"] : v >= 0.4 ? ["Medium demand", "hold"] : ["Low demand", "down"];
    Object.keys(byMonth).sort().forEach((mk) => {
      const list = byMonth[mk];
      const di = data.monthDemand[+mk.slice(5, 7)] || 0;
      const dl = demLabel(di);
      const panel = el("div.panel");
      panel.appendChild(el("h2", periodLabel("month", mk) + " ",
        el("span.hint", list.length + " sailings · "), el("span.rec." + dl[1], dl[0])));
      const rows = list.map((s) => {
        const fp = schedFrom(s);
        const pct = Math.round((fp.dq.mult - 1) * 100);
        const badge = pct === 0 ? null : el("span.rec." + (pct > 0 ? "up" : "down"), { style: { marginLeft: "8px" } }, (pct > 0 ? "+" : "") + pct + "%");
        const ship = data.ships.find((x) => x.name === s.ship) || {};
        const booked = data.reservations.filter((r) => r.status !== "Cancelled" && r.ship === s.ship && r.departDate === s.departDate);
        let capCell, availCell;
        if (s.category === "Canada") {
          const usedRooms = booked.length;
          const avail = Math.max(0, ship.rooms - usedRooms);
          const low = avail < ship.rooms * 0.15;
          capCell = el("td.num.mono", ship.rooms.toLocaleString() + " rooms", el("div.sub-line", ship.capacity.toLocaleString() + " guests"));
          availCell = el("td.num.mono", el("span", { style: { color: low ? "#c0392b" : "#1c8a4d", fontWeight: "700" } }, avail.toLocaleString() + " rooms"), el("div.sub-line", usedRooms + " booked"));
        } else {
          const usedGuests = booked.reduce((x, r) => x + r.guests, 0);
          const availSeats = Math.max(0, ship.capacity - usedGuests);
          capCell = el("td.num.mono", ship.capacity.toLocaleString() + " seats", el("div.sub-line", "day cruise · no cabins"));
          availCell = el("td.num.mono", availSeats.toLocaleString() + " seats");
        }
        return el("tr",
          el("td", el("b", s.ship.replace("Seven Seas ", "")), el("div.sub-line", s.category === "Canada" ? "Canada cruise" : "Day · casino")),
          el("td", "NY → " + shortPort(s.toPort)),
          el("td.mono", fmtDate(s.departDate)),
          el("td", s.category === "Canada" ? (s.nights + " nights") : s.duration),
          capCell, availCell,
          el("td.num.mono", "from " + fmtMoney(fp.total), badge));
      });
      panel.appendChild(el("div.table-wrap", el("table",
        el("thead", el("tr", el("th", "Ship"), el("th", "Route"), el("th", "Departs"), el("th", "Length"),
          el("th.num", "Total capacity"), el("th.num", "Available rooms"), el("th.num", "From price"))),
        el("tbody", ...rows))));
      wrap.appendChild(panel);
      wrap.appendChild(el("div", { style: { height: "16px" } }));
    });
    return wrap;
  }

  /* ----- Cost & Savings (the case-study commission model) ----- */
  function buildCostSavings() {
    const cs = state.cs;
    const active = data.reservations.filter((r) => r.status !== "Cancelled");
    const inhouse = active.filter((r) => r.channel === "In-house").length;
    const logCapture = active.length ? Math.round(inhouse / active.length * 100) : 0;
    if (cs.capture == null) cs.capture = logCapture;

    const rev = +cs.revenue || 0, cp = (+cs.commPct || 0) / 100;
    const cur = (+cs.capture || 0) / 100, tgt = (+cs.target || 0) / 100, op = +cs.opCost || 0;
    const baseAllAgent = rev * cp;             // commission if 100% via agents (the case's ~$10M)
    const paidNow = rev * cp * (1 - cur);      // commission still paid at current capture
    const paidTgt = rev * cp * (1 - tgt);      // commission paid at target capture
    const grossSaveTgt = baseAllAgent - paidTgt;
    const netTgt = grossSaveTgt - op;

    const wrap = el("div");

    // intro / case quote
    const intro = el("div.panel");
    intro.appendChild(el("h2", "Cost & Savings ", el("span.hint", "in-house reservations vs travel-agent commission")));
    intro.appendChild(el("p.step-lead",
      "The case: ABC pays travel agents 10–15% commission on 100% of bookings (~$10M/yr). " +
      "Capturing bookings in-house pays $0 commission. Match the ~50% industry average and ABC saves several $M/yr."));
    wrap.appendChild(intro);

    // KPIs (live capture from the log + projected savings)
    wrap.appendChild(el("div.kpis",
      aKpi("k1", "🎯", "In-house Capture (live)", logCapture + "%", inhouse + " of " + active.length + " active"),
      aKpi("k2", "🧾", "Commission if all-agent", fmtMoneyShort(baseAllAgent), "@ " + cs.commPct + "%"),
      aKpi("k3", "💰", "Net Savings at " + cs.target + "%", fmtMoneyShort(netTgt), "after DSS op. cost"),
      aKpi("k4", "📉", "Commission still paid", fmtMoneyShort(paidTgt), "at " + cs.target + "% capture")));
    wrap.appendChild(el("div", { style: { height: "18px" } }));

    // what-if inputs
    const panel = el("div.panel.admin-pricing");
    panel.appendChild(el("h2", "Assumptions ", el("span.hint", "edit to model your scenario")));
    function numField(label, key, pre, step) {
      const inp = el("input", { type: "number", min: 0, step: step || 1, value: cs[key] });
      inp.addEventListener("input", (e) => { cs[key] = e.target.value; });
      inp.addEventListener("change", () => mountApp());
      return el("div.price-field", el("label", label), el("div.price-input", pre ? el("span.price-pre", pre) : null, inp));
    }
    const grid = el("div.price-grid");
    grid.appendChild(numField("Annual commissionable revenue", "revenue", "$", 100000));
    grid.appendChild(numField("Blended commission", "commPct", "%", 0.5));
    grid.appendChild(numField("Current in-house capture", "capture", "%", 1));
    grid.appendChild(numField("Target capture", "target", "%", 1));
    grid.appendChild(numField("DSS annual operating cost", "opCost", "$", 100000));
    panel.appendChild(grid);
    const useLive = el("button.btn.secondary", "↺ Use live capture from log (" + logCapture + "%)");
    useLive.addEventListener("click", () => { cs.capture = logCapture; mountApp(); });
    panel.appendChild(el("div.price-actions", useLive));
    wrap.appendChild(panel);

    // results
    const res = el("div.panel");
    res.appendChild(el("h2", "Annual Cost & Savings"));
    const line = (a, b, cls) => res.appendChild(el("div.sum-line" + (cls ? "." + cls : ""), el("span", a), el("span", b)));
    line("Commission if 100% via agents", fmtMoney(baseAllAgent), "muted");
    line("Commission paid now (" + cs.capture + "% in-house)", fmtMoney(paidNow), "muted");
    line("Commission paid at target (" + cs.target + "%)", fmtMoney(paidTgt), "muted");
    line("Gross savings at target", fmtMoney(grossSaveTgt));
    line("− DSS annual operating cost", "−" + fmtMoney(op), "muted");
    line("= Net annual savings", fmtMoney(netTgt), "total");
    wrap.appendChild(res);

    // comparison chart
    wrap.appendChild(el("div.panel",
      el("h2", "Commission Cost — scenarios"),
      hbar("", "", [
        ["100% via agents", Math.round(baseAllAgent)],
        ["Now (" + cs.capture + "% in-house)", Math.round(paidNow)],
        ["Target (" + cs.target + "% in-house)", Math.round(paidTgt)],
      ], fmtMoneyShort)));

    wrap.appendChild(el("footer.note",
      "Live capture comes from the reservations log (channel = In-house vs Travel Agent). " +
      "Every booking made on the customer site is in-house → $0 commission, so driving traffic to it grows the capture % and the savings."));
    return wrap;
  }

  function adminTabs() {
    const tabs = [["pricing", "💲 Pricing Control"], ["dynamic", "⚡ Dynamic Pricing"], ["schedule", "🗓️ Trip Schedule"], ["log", "📋 Reservations Log"], ["analytics", "📊 Log Analytics"], ["cost", "💰 Cost & Savings"], ["forecast", "📈 Forecast"]];
    return el("div.tabs.admin-subtabs", ...tabs.map(([id, label]) => {
      const b = el("button.tab" + (state.adminView === id ? ".active" : ""), label);
      b.addEventListener("click", () => { state.adminView = id; mountApp(); });
      return b;
    }));
  }

  function buildAdmin() {
    const wrap = el("div");
    wrap.appendChild(el("div.admin-banner", "🔒 Staff / Decision-Maker view — not visible to customers."));
    wrap.appendChild(adminTabs());

    if (state.adminView === "pricing") {
      wrap.appendChild(buildPricingPanel());
      return wrap;
    }
    if (state.adminView === "dynamic") {
      wrap.appendChild(buildDynamicPanel());
      return wrap;
    }
    if (state.adminView === "schedule") {
      wrap.appendChild(buildScheduleTab());
      return wrap;
    }
    if (state.adminView === "analytics") {
      wrap.appendChild(buildAnalytics());
      return wrap;
    }
    if (state.adminView === "cost") {
      wrap.appendChild(buildCostSavings());
      return wrap;
    }
    if (state.adminView === "forecast") {
      wrap.appendChild(buildForecast());
      return wrap;
    }

    // --- Reservations Log ---
    wrap.appendChild(el("h2", { style: { color: "#fff", textShadow: "0 1px 4px rgba(0,0,0,.4)", margin: "0 0 12px" } }, "All Registered Reservations"));
    buildDashboardTable(wrap);

    // bottom export bar — download the (filtered) log as CSV for Excel
    const exportBtn = el("button.csv-btn", "⬇  Export to CSV (Excel)");
    exportBtn.addEventListener("click", exportCSV);
    wrap.appendChild(el("div.export-bar", exportBtn,
      el("span.export-hint", "Downloads the rows currently shown (search/filters apply). Opens in Excel / Google Sheets.")));

    const savedCount = loadSaved().length;
    const footer = el("footer.note", savedCount + " booking" + (savedCount === 1 ? "" : "s") + " from customers saved in this browser · ");
    const clearBtn = el("button.clear-link", "clear saved bookings");
    clearBtn.addEventListener("click", () => {
      if (!savedCount) { showToast("No saved bookings to clear."); return; }
      const ids = new Set(loadSaved().map((r) => r.id)); clearSaved();
      data.reservations = data.reservations.filter((r) => !ids.has(r.id));
      showToast("Saved bookings cleared."); mountApp();
    });
    footer.appendChild(clearBtn); wrap.appendChild(footer);
    return wrap;
  }

  function buildDashboard() {
    const wrap = el("div");
    wrap.appendChild(dashStats());
    wrap.appendChild(el("div", { style: { height: "20px" } }));
    buildDashboardTable(wrap);
    const savedCount = loadSaved().length;
    const footer = el("footer.note", savedCount + " booking" + (savedCount === 1 ? "" : "s") + " saved in this browser · ");
    const clearBtn = el("button.clear-link", "clear my saved bookings");
    clearBtn.addEventListener("click", () => {
      if (!savedCount) { showToast("No saved bookings to clear."); return; }
      const ids = new Set(loadSaved().map((r) => r.id)); clearSaved();
      data.reservations = data.reservations.filter((r) => !ids.has(r.id));
      showToast("Saved bookings cleared."); mountApp();
    });
    footer.appendChild(clearBtn); wrap.appendChild(footer);
    return wrap;
  }

  /* ================================================================
     SHELL
     ================================================================ */
  function showToast(msg, isError) {
    const t = el("div.toast", msg); if (isError) t.style.background = "#c0392b";
    document.body.appendChild(t); setTimeout(() => t.remove(), 2600);
  }
  const APP_MODE = (window.APP_MODE === "admin") ? "admin" : "customer";

  // live link: when the company changes prices in the admin tab, refresh the
  // customer tab's fares automatically (same-browser localStorage 'storage' event)
  window.addEventListener("storage", (e) => {
    if (e.key !== data.priceKey) return;
    if (e.newValue == null) { try { location.reload(); } catch (err) {} return; }
    data.applyPriceOverrides();
    if (APP_MODE !== "admin") mountApp();
  });

  /* ----- real-website-style info footer (customer page) ----- */
  function buildSiteFooter() {
    const col = (title, items) => el("div.foot-col", el("h4", title),
      ...items.map((it) => el("div.foot-link", it)));
    const footer = el("footer.site-footer",
      el("div.foot-grid",
        el("div.foot-col.foot-about",
          el("img.foot-logo", { src: "images/abc_cruise_logo_v5.svg", alt: data.company }),
          el("p.foot-tagline", "Sailing from " + data.fromPort + " to Canada & beyond since 1998. " +
            "Award-winning cruises, in-house reservations, and unforgettable voyages.")),
        col("Explore", ["Canada Cruises", "Cruises to Somewhere", "Our Fleet", "Destinations", "Deals & Offers"]),
        col("About", ["Our Story", "Careers", "Sustainability", "Press Room", "Investor Relations"]),
        col("Support", ["Help Center", "Manage Booking", "Travel Documents", "Accessibility", "FAQ"]),
        el("div.foot-col.foot-contact",
          el("h4", "Contact Us"),
          el("div.foot-contact-line", "📞 1-800-ABC-SAIL"),
          el("div.foot-contact-line", "☎️ +1 (607) 555-0142"),
          el("div.foot-contact-line", "✉️ reservations@abccruises.com"),
          el("div.foot-contact-line", "📍 12 Harbor Way, Binghamton, NY 13901"),
          el("div.foot-social", el("span", "📘"), el("span", "📸"), el("span", "🐦"), el("span", "▶️")))),
      el("div.foot-bottom",
        el("span", "© 2026 ABC Cruise Lines, Inc. All rights reserved."),
        el("span.foot-legal", "Privacy Policy · Terms & Conditions · Cookie Settings · Guest Ticket Contract")));
    return footer;
  }

  function buildTopbar() {
    const isAdmin = APP_MODE === "admin";
    return el("div.topbar" + (isAdmin ? ".topbar-admin" : ""),
      el("div.brand",
        el("img.logo", { src: "images/abc_cruise_logo_v5.svg", alt: data.company + " logo" }),
        el("div",
          el("h1", data.company + (isAdmin ? " — Ship Dashboard" : "")),
          el("p", isAdmin ? "Decision-maker view (staff only) · HQ " + data.hq : "Book a cruise · " + data.fromPort + " · HQ " + data.hq))),
      el("div.asof", "As of", el("strong", fmtDate(data.today))));
  }
  function mountApp() {
    const root = document.getElementById("root");
    if (!data) { root.innerHTML = ""; root.appendChild(el("div", { style: { padding: "40px", color: "#c0392b" } }, "Error: data.js failed to load.")); return; }
    root.innerHTML = "";
    root.appendChild(buildTopbar());
    const wrap = el("div.wrap");
    wrap.appendChild(APP_MODE === "admin" ? buildAdmin() : buildWizard());
    root.appendChild(wrap);
    if (APP_MODE !== "admin") root.appendChild(buildSiteFooter());
    if (state.flashId) setTimeout(() => { state.flashId = null; }, 1700);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mountApp);
  else mountApp();
})();
