/* ABC Cruise Lines — Decision Support System (DSS)
   Mock data model built to match the SSIE 510 case study + "Manage My Cruise" checklist.

   Business context (from the case):
   - ABC Cruise Lines sails out of New York, NY.
   - Canada cruises: 7-night or 9-night.
   - "Cruises to somewhere": 1-day or half-day gambling cruises to international waters.
   - 3 ships total.
   - Goal: bring reservations in-house (currently 100% via travel agents @ 10-15% commission,
     ~$10M/yr). Industry captures ~50% in-house -> target capture rate 50%, saving commission.

   Deterministic generation (seeded PRNG) so the dataset is stable across reloads.
*/
(function () {
  function mulberry32(seed) {
    return function () {
      seed |= 0;
      seed = (seed + 0x6d2b79f5) | 0;
      let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  const rand = mulberry32(510);
  const pick = (arr) => arr[Math.floor(rand() * arr.length)];
  const between = (lo, hi) => lo + Math.floor(rand() * (hi - lo + 1));

  // --- Reference data ---------------------------------------------------------
  const FROM_PORT = "New York, NY";

  /* The case says ABC owns THREE ships but does not name them (fictional case ->
     "make any assumptions necessary"). Designations assigned here:
       - 2 ships serve the 7/9-night Canada cruises
       - 1 ship serves the 1-day / half-day "cruise to somewhere" (gambling). */
  // Sized to fit the case: ~300 shipboard employees across 3 ships (~100 crew each).
  // At a realistic ~1 crew : 2–3 guests, that means small ships (a small cruise line).
  //   rooms = staterooms; capacity (guests) = rooms × 2 (double occupancy).
  //   The casino day-cruise ship has no cabins (rooms: 0) — capacity is by seats, and
  //   day trips need far less crew, so it can carry more guests.
  const SHIPS = [
    { name: "Queen Victoria", designation: "MV Queen Victoria · AC-7N", shipClass: "Victoria-class",
      category: "Canada", rooms: 130, capacity: 260, crew: 110, decks: 8, yearBuilt: 2019,
      route: "7 & 9-night Canada / New England", emoji: "🚢", slug: "aurora" },
    { name: "Crystal Symphony", designation: "MV Crystal Symphony · AC-9N", shipClass: "Crystal-class",
      category: "Canada", rooms: 150, capacity: 300, crew: 120, decks: 9, yearBuilt: 2022,
      route: "7 & 9-night Canada", emoji: "🛳️", slug: "borealis" },
    { name: "Seven Seas Splendor", designation: "MV Seven Seas Splendor · CS-1D", shipClass: "Splendor-class",
      category: "Somewhere", rooms: 0, capacity: 600, crew: 70, decks: 6, yearBuilt: 2017,
      route: "Day & half-day cruises to international waters", emoji: "🎰", slug: "casino-star" },
  ];

  // 2 destinations per category, each matching its category:
  //   Canada   = real Canadian ports (7/9-night cruises)
  //   Somewhere = international-waters day/half-day gambling cruises
  const DESTINATIONS = {
    Canada: ["Halifax, NS", "Quebec City, QC", "Saint John, NB", "Charlottetown, PEI"],
    Somewhere: ["International Waters (Casino)", "Atlantic Casino Waters", "Bermuda Casino Waters", "Gulf Casino Waters"],
  };

  // Cabins apply to Canada cruises (multi-night). Per-night, per-guest base price.
  // tier classifies each cabin as a "Normal" or "Premium" accommodation.
  const CABINS = [
    { type: "Interior", perNight: 95, tier: "Normal", img: "cabin-interior",
      sleeps: "1-4", sqft: "101 - 285 sq. ft.",
      features: ["Our most budget-friendly option", "Cozy, comfortable retreat after an adventure-filled day"] },
    { type: "Oceanview", perNight: 140, tier: "Normal", img: "cabin-oceanview",
      sleeps: "1-4", sqft: "182 - 302 sq. ft.",
      features: ["Endless ocean views from your in-stateroom window", "Great for families with small children"] },
    { type: "Balcony", perNight: 210, tier: "Premium", img: "cabin-balcony",
      sleeps: "1-4", sqft: "200 - 320 sq. ft.",
      features: ["Crowd favorite: our most popular option", "Private balcony with stunning ocean views"] },
    { type: "Suite", perNight: 360, tier: "Premium", img: "cabin-suite",
      sleeps: "1-8", sqft: "350 - 1,000 sq. ft.",
      features: ["Live the 'suite' life with extra space", "Top-deck luxury with exclusive perks & inclusions"] },
  ];

  // Fare class = the "Premium vs Normal" experience tier (airline style):
  // Standard adds nothing; Premium adds a flat EXTRA amount per guest.
  const FARE_CLASSES = [
    { name: "Standard", extra: 0, blurb: "Cruise fare only" },
    { name: "Premium", extra: 200, blurb: "Free at Sea perks: priority boarding, Wi-Fi & drinks" },
  ];

  // Gambling day-cruise flat rate per guest.
  const DAY_RATES = { "1 Day": 199, "Half Day": 119 };

  const ADD_ONS = [
    { name: "Transportation", price: 120 },   // to/from departure port
    { name: "Meal Plan", price: 240 },
    { name: "Onboard Credit", price: 100 },
    { name: "Port Excursions", price: 180 },
  ];

  const STATUSES = ["Confirmed", "Checked-in", "Cancelled"];
  const CHANNELS = ["In-house", "Travel Agent"]; // DSS goal: grow In-house share
  const CUSTOMER_TYPES = ["Individual", "Corporate Group"];

  const COMMISSION_RATE = 0.125; // blended 10-15% paid to travel agents
  const CAPTURE_TARGET = 0.5;    // industry benchmark: 50% booked in-house

  const FIRST = ["Emma", "Liam", "Olivia", "Noah", "Ava", "Sophia", "Mason", "Isabella",
    "James", "Mia", "Heba", "Omar", "Layla", "Yusuf", "Maya", "Daniel", "Grace",
    "Ethan", "Chloe", "Lucas", "Amelia", "Henry", "Zoe", "Aiden", "Sara", "Jane", "Doug"];
  const LAST = ["Johnson", "Smith", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Jaradat", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Khan",
    "Nguyen", "Patel", "Kim", "Chen", "Ali", "Haddad", "Wilson", "Anderson"];
  const COUNTRIES = ["USA", "Canada", "UK", "Germany", "Jordan", "France", "Mexico", "Brazil"];
  const COMPANIES = ["Apex Logistics", "Northwind Group", "BinghamCorp", "Quanta LLC",
    "Vertex Partners", "Summit Realty", "Helios Tech"];

  const fullName = () => `${pick(FIRST)} ${pick(LAST)}`;

  const TODAY = new Date("2026-06-20T00:00:00");
  const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
  const iso = (d) => d.toISOString().slice(0, 10);

  // --- Editable pricing (the company sets these in the admin page; persisted to
  //     localStorage and shared with the customer booking site on the same browser) ---
  const PRICE_KEY = "abc_cruise_prices_v1";
  let TAX_RATE = 0.12;
  let BASE_CANADA = 200;  // base cost for the trip, per guest (Canada cruise)
  let BASE_DAY = 40;      // base cost for the trip, per guest (day / casino cruise)
  let ONEWAY_PCT = 65;    // a one-way fare is this % of the round-trip cruise fare
  // Dynamic pricing (revenue management) — demand + time-to-departure
  // highPct / lowPct = occupancy thresholds that define "high" and "low" demand
  let DYN = { enabled: true, highPct: 70, lowPct: 30, surgePct: 25, discountPct: 12, earlyBirdPct: 8, lastMinutePct: 20 };
  const PRICE_DEFAULTS = {
    baseCanada: 200, baseDay: 40, oneWayPct: 65,
    cabins: { Interior: 95, Oceanview: 140, Balcony: 210, Suite: 360 },
    dayRates: { "1 Day": 199, "Half Day": 119 },
    addOns: { Transportation: 120, "Meal Plan": 240, "Onboard Credit": 100, "Port Excursions": 180 },
    premiumExtra: 200,
    taxPct: 12,
    dyn: { enabled: true, highPct: 70, lowPct: 30, surgePct: 25, discountPct: 12, earlyBirdPct: 8, lastMinutePct: 20 },
  };
  function loadPriceOverrides() { try { return JSON.parse(localStorage.getItem(PRICE_KEY) || "null"); } catch (e) { return null; } }
  function applyPriceOverrides() {
    const o = loadPriceOverrides(); if (!o) return;
    const num = (v) => (v != null && !isNaN(+v));
    if (num(o.baseCanada)) BASE_CANADA = +o.baseCanada;
    if (num(o.baseDay)) BASE_DAY = +o.baseDay;
    if (num(o.oneWayPct)) ONEWAY_PCT = +o.oneWayPct;
    if (o.cabins) CABINS.forEach((c) => { if (num(o.cabins[c.type])) c.perNight = +o.cabins[c.type]; });
    if (o.dayRates) Object.keys(DAY_RATES).forEach((k) => { if (num(o.dayRates[k])) DAY_RATES[k] = +o.dayRates[k]; });
    if (o.addOns) ADD_ONS.forEach((a) => { if (num(o.addOns[a.name])) a.price = +o.addOns[a.name]; });
    if (num(o.premiumExtra)) { const f = FARE_CLASSES.find((x) => x.name === "Premium"); if (f) f.extra = +o.premiumExtra; }
    if (num(o.taxPct)) TAX_RATE = (+o.taxPct) / 100;
    if (o.dyn) {
      if (typeof o.dyn.enabled === "boolean") DYN.enabled = o.dyn.enabled;
      ["highPct", "lowPct", "surgePct", "discountPct", "earlyBirdPct", "lastMinutePct"].forEach((k) => { if (num(o.dyn[k])) DYN[k] = +o.dyn[k]; });
    }
  }
  function savePrices(o) { try { localStorage.setItem(PRICE_KEY, JSON.stringify(o)); applyPriceOverrides(); return true; } catch (e) { return false; } }
  function resetPrices() { try { localStorage.removeItem(PRICE_KEY); } catch (e) {} }
  function currentPrices() {
    const premium = FARE_CLASSES.find((x) => x.name === "Premium");
    return {
      baseCanada: BASE_CANADA, baseDay: BASE_DAY, oneWayPct: ONEWAY_PCT,
      cabins: CABINS.reduce((m, c) => ((m[c.type] = c.perNight), m), {}),
      dayRates: Object.assign({}, DAY_RATES),
      addOns: ADD_ONS.reduce((m, a) => ((m[a.name] = a.price), m), {}),
      premiumExtra: premium ? premium.extra : 200,
      taxPct: Math.round(TAX_RATE * 100),
      dyn: Object.assign({}, DYN),
    };
  }

  // Dynamic price quote for a specific sailing (ship + date), based on the LIVE log.
  // Returns a multiplier applied to the cruise fare, plus the human-readable reasons.
  function dynamicQuote(category, shipName, departDate) {
    if (!DYN.enabled || !departDate) return { mult: 1, occ: 0, days: 0, reason: "" };
    const res = (typeof window !== "undefined" && window.DASHBOARD_DATA && window.DASHBOARD_DATA.reservations) || RESERVATIONS;
    const ship = SHIPS.find((s) => s.name === shipName);
    const cap = ship ? ship.capacity : 1;
    const days = Math.round((new Date(departDate + "T00:00:00") - TODAY) / 86400000);
    const guests = res.filter((r) => r.ship === shipName && r.departDate === departDate && r.status !== "Cancelled")
      .reduce((s, r) => s + r.guests, 0);
    const occ = cap ? guests / cap : 0;
    const hi = (DYN.highPct || 70) / 100, lo = (DYN.lowPct || 30) / 100;
    let mult = 1; const why = [];
    // --- demand signal (thresholds are set by the company) ---
    if (occ >= hi) { mult *= 1 + DYN.surgePct / 100; why.push("high demand (" + Math.round(occ * 100) + "% full ≥ " + Math.round(hi * 100) + "%)"); }
    else if (occ < lo) { mult *= 1 - DYN.discountPct / 100; why.push("low demand (" + Math.round(occ * 100) + "% full < " + Math.round(lo * 100) + "%)"); }
    // --- time-to-departure signal ---
    if (days > 120) { mult *= 1 - DYN.earlyBirdPct / 100; why.push("early-booking saver"); }
    else if (days >= 0 && days <= 3) {
      if (occ >= lo) { mult *= 1 + DYN.lastMinutePct / 100; why.push("last-minute surge"); }
      else { mult *= 1 - DYN.lastMinutePct / 100; why.push("last-minute deal"); }
    } else if (days > 3 && days <= 21) { mult *= 1 + DYN.surgePct / 200; why.push("departing soon"); }
    mult = Math.max(0.6, Math.min(1.8, mult));
    return { mult: Math.round(mult * 100) / 100, occ, days, reason: why.join(" · ") };
  }

  // apply any saved company prices BEFORE generating the dataset so everything is consistent
  applyPriceOverrides();

  // --- Pricing engine (shared with the booking form) -------------------------
  function priceReservation(o) {
    // o: {category, nights, duration, cabinType, fareClass, guests, addOns[], customerType}
    // base cost for the trip (per guest) + the room/day rate
    let perGuest = 0;
    if (o.category === "Canada") {
      const cabin = CABINS.find((c) => c.type === o.cabinType) || CABINS[0];
      perGuest = BASE_CANADA + cabin.perNight * o.nights;
    } else {
      perGuest = BASE_DAY + (DAY_RATES[o.duration] || DAY_RATES["1 Day"]);
    }
    // one-way trips cost a fraction of the round-trip cruise fare
    if (o.tripType === "One-way") perGuest = Math.round(perGuest * (ONEWAY_PCT / 100));
    // dynamic pricing multiplier scales the cruise fare (not the flat premium add-on)
    const dyn = o.dynamicMult || 1;
    // Premium fare class = flat extra money per guest (airline-style upgrade)
    const fc = FARE_CLASSES.find((x) => x.name === o.fareClass) || FARE_CLASSES[0];
    let fare = Math.round((perGuest * dyn + (fc.extra || 0)) * o.guests);
    const addOnTotal = (o.addOns || []).reduce((s, n) => {
      const a = ADD_ONS.find((x) => x.name === n);
      return s + (a ? a.price * (o.category === "Canada" ? o.guests : 1) : 0);
    }, 0);
    let subtotal = fare + addOnTotal;
    // Corporate groups are handled differently -> 10% group rate
    const groupDiscount = o.customerType === "Corporate Group" ? Math.round(subtotal * 0.1) : 0;
    subtotal -= groupDiscount;
    const taxes = Math.round(subtotal * TAX_RATE);
    const total = subtotal + taxes;
    return { fare: Math.round(fare), addOnTotal, groupDiscount, taxes, total };
  }

  // --- Generate historical / current reservations ----------------------------
  function makeReservation(i) {
    const ship = pick(SHIPS);
    const category = ship.category;
    const customerType = category === "Somewhere"
      ? (rand() < 0.45 ? "Corporate Group" : "Individual")   // groups common on day cruises
      : (rand() < 0.15 ? "Corporate Group" : "Individual");
    const channel = rand() < 0.42 ? "In-house" : "Travel Agent"; // ~42% captured so far

    // mostly historical (about a year back) with some future bookings — so the
    // forecast has real history and "today" (June) cleanly splits actual vs forecast
    const offset = between(-340, 100);
    const depart = addDays(TODAY, offset);

    let nights = 0, duration = null, cabinType = null, cabinNo = "", deck = 0, toPort, ret, addOns = [];
    if (category === "Canada") {
      nights = rand() < 0.5 ? 7 : 9;
      toPort = pick(DESTINATIONS.Canada);
      ret = addDays(depart, nights);
      cabinType = pick(CABINS).type;
      deck = between(8, 16);
      cabinNo = `${deck}${String(between(1, 60)).padStart(3, "0")}`;
      ADD_ONS.forEach((a) => { if (rand() < 0.4) addOns.push(a.name); });
    } else {
      duration = rand() < 0.6 ? "1 Day" : "Half Day";
      toPort = pick(DESTINATIONS.Somewhere);
      ret = depart; // same-day
    }

    const fareClass = rand() < 0.35 ? "Premium" : "Standard";
    const guests = customerType === "Corporate Group" ? between(8, 40) : between(1, 4);

    // only 3 statuses: past sailings = Checked-in (or Cancelled); upcoming = Confirmed (or Cancelled)
    let status;
    if (offset < 0) status = rand() < 0.85 ? "Checked-in" : "Cancelled";
    else status = rand() < 0.85 ? "Confirmed" : "Cancelled";

    const p = priceReservation({ category, nights, duration, cabinType, fareClass, guests, addOns, customerType });
    const total = status === "Cancelled" ? 0 : p.total;
    const balanceDue = status === "Pending" ? Math.round(total * (0.4 + rand() * 0.6)) : 0;
    // commission we DIDN'T pay because it was booked in-house (the DSS value driver)
    const commissionSaved = channel === "In-house" && status !== "Cancelled"
      ? Math.round(total * COMMISSION_RATE) : 0;
    // commission we DID pay to a travel agent (avoidable cost)
    const commissionPaid = channel === "Travel Agent" && status !== "Cancelled"
      ? Math.round(total * COMMISSION_RATE) : 0;

    return {
      id: "ABC-" + String(100000 + i),
      leadGuest: fullName(),
      email: "guest" + i + "@example.com",
      country: pick(COUNTRIES),
      company: customerType === "Corporate Group" ? pick(COMPANIES) : null,
      customerType,
      channel,
      category,
      fromPort: FROM_PORT,
      toPort,
      tripType: "Round Trip",
      ship: ship.name,
      departDate: iso(depart),
      returnDate: iso(ret),
      nights, duration, cabinType, cabinNo, deck, fareClass,
      guests,
      addOns,
      fare: p.fare,
      addOnTotal: p.addOnTotal,
      groupDiscount: p.groupDiscount,
      taxes: p.taxes,
      total,
      balanceDue,
      commissionSaved,
      commissionPaid,
      status,
      bookedOn: iso(addDays(depart, -between(20, 160))),
    };
  }

  const RESERVATIONS = Array.from({ length: 72 }, (_, i) => makeReservation(i + 1));

  // --- INTELLIGENT trip schedule -------------------------------------------------
  // Not random: driven by forecasted demand from the log —
  //   * seasonality (demand index per month-of-year) → peak months sail more
  //     frequently & longer; low months lay up capacity (fewer sailings).
  //   * destination popularity (booking weight) → more sailings to popular ports.
  function demandIndexByMonth() {
    const c = {}; let max = 0;
    RESERVATIONS.filter((r) => r.status !== "Cancelled").forEach((r) => { const mo = +r.departDate.slice(5, 7); c[mo] = (c[mo] || 0) + r.guests; });
    for (let mo = 1; mo <= 12; mo++) if ((c[mo] || 0) > max) max = c[mo] || 0;
    const idx = {}; for (let mo = 1; mo <= 12; mo++) idx[mo] = max ? (c[mo] || 0) / max : 0.5;
    return idx;
  }
  function destWeights(cat) {
    const w = {}; DESTINATIONS[cat].forEach((p) => (w[p] = 1)); // base weight so every port can appear
    RESERVATIONS.filter((r) => r.status !== "Cancelled" && r.category === cat).forEach((r) => { w[r.toPort] = (w[r.toPort] || 1) + 2; });
    return w;
  }
  function weightedPick(weights, keys) {
    const total = keys.reduce((s, k) => s + (weights[k] || 0), 0) || 1;
    let r = rand() * total;
    for (let i = 0; i < keys.length; i++) { r -= (weights[keys[i]] || 0); if (r <= 0) return keys[i]; }
    return keys[keys.length - 1];
  }
  const MONTH_DEMAND = demandIndexByMonth();

  function buildScheduleData() {
    const out = [];
    let sid = 1;
    SHIPS.forEach((ship) => {
      const cat = ship.category;
      const weights = destWeights(cat);
      const keys = DESTINATIONS[cat];
      let cursor = addDays(TODAY, -21);
      const end = addDays(TODAY, 210);
      let guard = 0;
      while (cursor < end && guard++ < 500) {
        const idx = MONTH_DEMAND[cursor.getMonth() + 1]; // 0..1 demand for this month
        if (cat === "Canada") {
          if (idx < 0.35 && rand() > 0.45) { cursor = addDays(cursor, 8); continue; } // low season → lay up gap
          const nights = idx >= 0.7 ? 9 : 7;             // longer cruises in peak demand
          const dep = new Date(cursor);
          const ret = addDays(dep, nights);
          out.push({ id: "SCH-" + (sid++), ship: ship.name, category: "Canada",
            toPort: weightedPick(weights, keys), departDate: iso(dep), returnDate: iso(ret),
            nights, duration: null, capacity: ship.capacity, demand: idx });
          cursor = addDays(ret, idx >= 0.6 ? 1 : 3);     // tighter turnaround when busy
        } else {
          const dep = new Date(cursor);
          out.push({ id: "SCH-" + (sid++), ship: ship.name, category: "Somewhere",
            toPort: weightedPick(weights, keys), departDate: iso(dep), returnDate: iso(dep),
            nights: 0, duration: rand() < 0.6 ? "1 Day" : "Half Day", capacity: ship.capacity, demand: idx });
          cursor = addDays(dep, idx >= 0.7 ? 2 : idx >= 0.4 ? 3 : 5); // more frequent day cruises in peak
        }
      }
    });
    return out.sort((a, b) => a.departDate.localeCompare(b.departDate));
  }
  const SCHEDULE = buildScheduleData();

  window.DASHBOARD_DATA = {
    company: "ABC Cruise Lines",
    hq: "Binghamton, NY",
    today: iso(TODAY),
    fromPort: FROM_PORT,
    ships: SHIPS,
    destinations: DESTINATIONS,
    cabins: CABINS,
    fareClasses: FARE_CLASSES,
    dayRates: DAY_RATES,
    addOns: ADD_ONS,
    statuses: STATUSES,
    channels: CHANNELS,
    customerTypes: CUSTOMER_TYPES,
    commissionRate: COMMISSION_RATE,
    captureTarget: CAPTURE_TARGET,
    priceReservation,
    dynamicQuote,
    reservations: RESERVATIONS,
    schedule: SCHEDULE,
    monthDemand: MONTH_DEMAND,
    // pricing control (admin sets, customer reads)
    priceKey: PRICE_KEY,
    priceDefaults: PRICE_DEFAULTS,
    currentPrices,
    savePrices,
    resetPrices,
    applyPriceOverrides,
  };
})();
