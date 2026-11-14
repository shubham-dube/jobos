// JobOS generic form extractor. Runs inside a page/frame; returns a plain JSON description of the
// visible application form. Assigns data-jobos-key attributes so the runner can find elements again.
// Keep this file dependency-free; it is evaluated with page.evaluate(source)(opts).
(opts) => {
  const MAX_TEXT = (opts && opts.maxText) || 4000;
  const framePrefix = (opts && opts.framePrefix) || "";

  const clean = (s) => (s || "").replace(/[✱*]+/g, " ").replace(/\s+/g, " ").trim();
  const isVisible = (el) => {
    if (!el || !el.isConnected) return false;
    const st = window.getComputedStyle(el);
    if (st.display === "none" || st.visibility === "hidden") return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const visibleText = (el) => (el ? clean(el.innerText || el.textContent || "") : "");
  const textOfIds = (ids) =>
    clean((ids || "").split(/\s+/).map((id) => visibleText(document.getElementById(id))).join(" "));

  const CONTAINER_RE = /(question|field|form-group|formgroup|input-wrapper|application-|form-item|form-row|_fieldEntry|fieldset)/i;
  const LABELISH = "label, legend, .application-label, [class*='label' i], [class*='Label'], [class*='question-title' i], h3, h4";

  function containerLabel(el, exclude) {
    const n = containerLabelNode(el, exclude);
    return n ? visibleText(n) : "";
  }

  function containerLabelNode(el, exclude) {
    let node = el.parentElement;
    for (let depth = 0; node && depth < 6; depth++, node = node.parentElement) {
      const cls = (node.className && node.className.toString()) || "";
      if (node.tagName === "FIELDSET" || CONTAINER_RE.test(cls) || node.getAttribute("role") === "group" ||
          node.getAttribute("role") === "radiogroup") {
        const legend = node.tagName === "FIELDSET" ? node.querySelector(":scope > legend") : null;
        if (legend && visibleText(legend)) return legend;
        const candidates = Array.from(node.querySelectorAll(LABELISH)).filter((l) => !exclude || !exclude.includes(l));
        for (const c of candidates) {
          // skip labels that belong to individual options
          const forId = c.getAttribute("for");
          const forEl = forId ? document.getElementById(forId) : null;
          if (forEl && (forEl.type === "radio" || forEl.type === "checkbox") && node.querySelectorAll("input[type=radio],input[type=checkbox]").length > 1) continue;
          if (c.querySelector("input[type=radio],input[type=checkbox]")) continue;
          const t = visibleText(c);
          if (t && t.length < 600) return c;
        }
      }
    }
    return null;
  }

  function labelFor(el) {
    if (el.getAttribute("aria-labelledby")) {
      const t = textOfIds(el.getAttribute("aria-labelledby"));
      if (t) return t;
    }
    if (el.labels && el.labels.length) {
      const t = clean(Array.from(el.labels).map((l) => visibleText(l)).join(" "));
      if (t && !/^(attach|upload|browse)$/i.test(t)) return t;
    }
    if (el.getAttribute("aria-label")) return clean(el.getAttribute("aria-label"));
    const c = containerLabel(el);
    if (c) return c;
    if (el.placeholder) return clean(el.placeholder);
    if (el.title) return clean(el.title);
    return clean((el.name || "").replace(/[_\[\]-]+/g, " "));
  }

  function optionLabel(input) {
    if (input.labels && input.labels.length) return clean(visibleText(input.labels[0]));
    if (input.getAttribute("aria-label")) return clean(input.getAttribute("aria-label"));
    const parentLabel = input.closest("label");
    if (parentLabel) return visibleText(parentLabel);
    const next = input.nextElementSibling;
    if (next) return visibleText(next);
    return clean(input.value);
  }

  function isRequired(el, label, rawLabelText) {
    if (el.required || el.getAttribute("aria-required") === "true") return true;
    return /[*✱]/.test(rawLabelText || "");
  }

  function rawLabelText(el) {
    if (el.labels && el.labels.length) {
      const t = el.labels[0].innerText || el.labels[0].textContent || "";
      // visually-hidden "Attach"/"Upload" labels on file inputs: the real (asterisked) label is in the container
      if (!/^\s*(attach|upload|browse)\s*$/i.test(t)) return t;
    }
    if (el.getAttribute("aria-labelledby")) {
      return (el.getAttribute("aria-labelledby").split(/\s+/).map((id) => {
        const n = document.getElementById(id); return n ? n.innerText : "";
      }).join(" "));
    }
    if (el.type === "file") {
      const c = containerLabelNode(el);
      return c ? (c.innerText || c.textContent || "") : "";
    }
    return "";
  }

  const used = new Set();
  function keyFor(el, label) {
    let base = el.id ? "id:" + el.id : el.name ? "name:" + el.name : "lbl:" + clean(label).toLowerCase().slice(0, 40).replace(/[^a-z0-9]+/g, "-");
    base = framePrefix + base;
    let key = base, n = 1;
    while (used.has(key)) key = base + "#" + ++n;
    used.add(key);
    return key;
  }

  const fields = [];
  const seenGroups = new Set();
  const all = Array.from(document.querySelectorAll("input, select, textarea, [role=combobox], [contenteditable=true], [role=radiogroup]"));

  // ---------- Google Forms: every question is a [role=listitem] with ARIA widgets whose options carry data-value
  const isGForm = /(^|\.)docs\.google\.com$/.test(location.hostname) && /\/forms\//.test(location.pathname);
  // Forms restricted to signed-in users render every control disabled behind a "Sign in" prompt.
  const gformLocked = isGForm && Array.from(document.querySelectorAll("[role=listitem] input:not([type=hidden]), [role=listitem] textarea, [role=listitem] [role=radio], [role=listitem] [role=checkbox], [role=listitem] [role=listbox]"))
    .some((el) => el.disabled || el.getAttribute("aria-disabled") === "true");
  if (isGForm) {
    const optValue = (o) => {
      const v = o.getAttribute("data-value") ?? o.getAttribute("data-answer-value") ?? o.getAttribute("aria-label") ?? "";
      return v === "__other_option__" ? "Other" : clean(v);
    };
    document.querySelectorAll("[role=listitem]").forEach((li, idx) => {
      const h = li.querySelector("[role=heading]");
      if (!h || !isVisible(li)) return;
      const lines = (h.innerText || "").split("\n").map(clean).filter((t) => t && t !== "*");
      const label = lines[0] || "";
      if (!label) return;
      const required = !!li.querySelector('[aria-label="Required question"]') || /\*\s*$/.test(h.innerText || "");
      const description = lines.slice(1).join(" ").slice(0, 300);
      const base = { label, required, placeholder: "", description, max_length: null, accept: "" };
      const radios = Array.from(li.querySelectorAll("[role=radio]"));
      const checks = Array.from(li.querySelectorAll("[role=checkbox]"));
      const listbox = li.querySelector("[role=listbox]");
      const key = framePrefix + "gf:" + idx;
      used.add(key);
      if (radios.length || checks.length) {
        const opts = radios.length ? radios : checks;
        li.setAttribute("data-jobos-key", key);
        const picked = opts.filter((o) => o.getAttribute("aria-checked") === "true").map(optValue);
        fields.push({ ...base, key, type: radios.length ? "radio" : (opts.length === 1 ? "checkbox" : "multiselect"),
          options: opts.map(optValue), current_value: picked.length ? picked.join(" | ") : null,
          locator: { key, widget: "gforms-choice", kind: "gforms-choice" } });
      } else if (listbox) {
        li.setAttribute("data-jobos-key", key);
        const options = Array.from(listbox.querySelectorAll("[role=option]")).map(optValue).filter(Boolean);
        const sel = listbox.querySelector('[role=option][aria-selected=true]');
        const cur = sel ? optValue(sel) : "";
        fields.push({ ...base, key, type: "select", options: [...new Set(options)], current_value: cur || null,
          locator: { key, widget: "gforms-listbox" } });
      } else {
        const input = li.querySelector("textarea, input:not([type=hidden])");
        if (!input) {
          if (/add file|upload/i.test(li.innerText || "")) {  // Drive upload: needs the person's Google account UI
            li.setAttribute("data-jobos-key", key);
            fields.push({ ...base, key, type: "file", options: [], current_value: null,
              locator: { key, widget: "gforms-file" } });
          }
          return;
        }
        input.setAttribute("data-jobos-key", key);
        const t = (input.getAttribute("type") || "").toLowerCase();
        const type = input.tagName === "TEXTAREA" ? "textarea"
          : ({ email: "email", tel: "phone", url: "url", number: "number", date: "date" }[t] || "text");
        fields.push({ ...base, key, type, options: [], current_value: input.value || null, locator: { key, widget: "" } });
      }
    });
  }

  for (const el of isGForm ? [] : all) {
    const tag = el.tagName;
    const type = (el.getAttribute("type") || "").toLowerCase();
    if (tag === "INPUT" && ["hidden", "submit", "button", "image", "reset", "search"].includes(type)) continue;
    if (el.disabled || el.readOnly && type !== "file" && el.getAttribute("role") !== "combobox") continue;
    if (el.closest("[aria-hidden=true]") && type !== "file") continue;
    // react-select/validation proxies and honeypots: no identity and not focusable
    const hasIdentity = el.id || el.name || el.getAttribute("aria-label") || el.getAttribute("aria-labelledby") || (el.labels && el.labels.length);
    if (!hasIdentity && type !== "file" && tag !== "SELECT" && tag !== "TEXTAREA") continue;
    if (/honeypot|hp-field|do[-_]?not[-_]?fill/i.test((el.className || "").toString() + " " + (el.name || ""))) continue;

    if (type === "radio" || type === "checkbox" || el.getAttribute("role") === "radiogroup") {
      let group;
      // Group by a shared fieldset/role=group first: some ATSs (Ashby) give every checkbox its own name.
      const box = el.getAttribute("role") === "radiogroup" ? null : el.closest("fieldset, [role=group]");
      const boxMembers = box ? Array.from(box.querySelectorAll(`input[type=${type}]`)) : [];
      let groupId;
      if (el.getAttribute("role") === "radiogroup") {
        group = Array.from(el.querySelectorAll("[role=radio], input[type=radio]"));
        groupId = "rg:" + (el.id || all.indexOf(el));
      } else if (boxMembers.length > 1) {
        group = boxMembers;
        groupId = "fs:" + type + ":" + all.indexOf(boxMembers[0]);
      } else if (el.name) {
        group = Array.from(document.querySelectorAll(`input[type=${type}][name="${CSS.escape(el.name)}"]`));
        groupId = type + ":" + el.name;
      } else {
        group = [el];
        groupId = "single:" + all.indexOf(el);
      }
      if (seenGroups.has(groupId)) continue;
      seenGroups.add(groupId);
      const visibleOpts = group.filter((g) => isVisible(g) || (g.labels && g.labels[0] && isVisible(g.labels[0])) || isVisible(g.parentElement));
      if (!visibleOpts.length) continue;
      const optionLabels = visibleOpts.map((g) => g.getAttribute("role") === "radio" ? visibleText(g) : optionLabel(g));
      let fieldType, label;
      const optionLabelEls = visibleOpts.flatMap((g) => (g.labels ? Array.from(g.labels) : []));
      if (type === "checkbox" && group.length === 1 && !box) {
        fieldType = "checkbox";
        label = containerLabel(el, optionLabelEls) || optionLabels[0] || labelFor(el);
        if (!label) label = optionLabels[0];
      } else {
        fieldType = type === "checkbox" ? "multiselect" : "radio";
        label = containerLabel(el, optionLabelEls) || (el.getAttribute("role") === "radiogroup" ? labelFor(el) : "") || clean(el.name);
      }
      const key = keyFor(el, label);
      group.forEach((g) => g.setAttribute("data-jobos-key", key));
      const raw = (el.closest("fieldset,[role=radiogroup],[class*=question],[class*=field]") || {}).innerText || "";
      fields.push({
        key, label, type: fieldType,
        required: group.some((g) => g.required || g.getAttribute("aria-required") === "true") || /[*✱]/.test(raw.split("\n")[0] || ""),
        options: fieldType === "checkbox" ? [] : optionLabels,
        current_value: fieldType === "checkbox" ? !!el.checked :
          fieldType === "multiselect" ? visibleOpts.filter((g) => g.checked).map((g) => optionLabel(g)) :
          (visibleOpts.find((g) => g.checked || g.getAttribute("aria-checked") === "true") ? optionLabel(visibleOpts.find((g) => g.checked || g.getAttribute("aria-checked") === "true")) : null),
        locator: { key, kind: el.getAttribute("role") === "radiogroup" ? "aria-radiogroup" : "group" },
      });
      continue;
    }

    const role = el.getAttribute("role");
    if (role === "radio") continue; // handled via radiogroup
    const visible = isVisible(el) || (type === "file");
    if (!visible) continue;
    if (type === "file" && !el.isConnected) continue;

    const label = labelFor(el);
    const raw = rawLabelText(el);
    let fieldType = "text";
    let options = [];
    let widget = "";
    if (tag === "SELECT") {
      fieldType = el.multiple ? "multiselect" : "select";
      options = Array.from(el.options).filter((o) => o.value !== "" && !/^(select|choose|please select|--)/i.test(o.text.trim())).map((o) => clean(o.text));
      widget = "native-select";
    } else if (tag === "TEXTAREA" || el.getAttribute("contenteditable") === "true") {
      fieldType = "textarea";
    } else if (role === "combobox") {
      fieldType = "combobox"; // options are harvested by the runner (needs clicks)
      widget = "combobox";
    } else if (type === "file") {
      fieldType = "file";
    } else if (["email", "tel", "url", "number", "date"].includes(type)) {
      fieldType = { email: "email", tel: "phone", url: "url", number: "number", date: "date" }[type];
    }
    const key = keyFor(el, label);
    el.setAttribute("data-jobos-key", key);
    const describedBy = textOfIds(el.getAttribute("aria-describedby"));
    let currentValue = el.value;
    if (tag === "SELECT") currentValue = el.selectedIndex >= 0 && el.options[el.selectedIndex] && el.options[el.selectedIndex].value !== "" ? clean(el.options[el.selectedIndex].text) : "";
    if (role === "combobox") {
      // react-select & co. render the chosen value next to the input, inside the same control
      currentValue = el.value;
      let node = el.parentElement;
      for (let depth = 0; node && depth < 6; depth++, node = node.parentElement) {
        if (node.querySelectorAll("[role=combobox]").length > 1) break; // reached a shared container
        const chosen = node.querySelectorAll("[class*=single-value],[class*=singleValue],[class*=multi-value__label],[class*=multiValue] [class*=label]");
        if (chosen.length) {
          currentValue = Array.from(chosen).map((c) => visibleText(c)).filter(Boolean).join(" | ");
          break;
        }
      }
    }
    if (type === "file") {
      const box = el.closest("[class*=field],[class*=upload],[class*=file],div");
      currentValue = el.files && el.files.length ? el.files[0].name : "";
      if (!currentValue && box && /\.(pdf|docx?)\b/i.test(box.innerText || "")) currentValue = "(file attached)";
    }
    fields.push({
      key, label, type: fieldType,
      required: isRequired(el, label, raw),
      options, placeholder: clean(el.placeholder || ""), description: describedBy.slice(0, 300),
      max_length: el.maxLength > 0 ? el.maxLength : null, accept: el.accept || "",
      current_value: currentValue || null,
      locator: { key, widget },
    });
  }

  // ---------- buttons
  const hasPasswordField = Array.from(document.querySelectorAll("input[type=password]")).some(isVisible);
  const buttonEls = Array.from(document.querySelectorAll("button, input[type=submit], [role=button], a"));
  const meaningful = fields.filter((f) => f.type !== "checkbox" || f.required).length;
  // Rank candidates per kind; the best one wins (e.g. "Submit application" beats a top-of-page "Apply").
  const best = {};
  buttonEls.forEach((b, domIndex) => {
    if (!isVisible(b) || b.disabled || b.getAttribute("aria-disabled") === "true") return;
    const text = clean(b.innerText || b.value || b.getAttribute("aria-label") || "");
    if (!text || text.length > 60) return;
    let kind = null, score = 0;
    const inForm = !!b.closest("form");
    const isSubmitType = (b.getAttribute("type") || "").toLowerCase() === "submit";
    if (meaningful >= 2 || (isGForm && fields.length)) {
      if (/^(submit( (my |your )?application)?|send( application)?|complete( application)?|finish|submit & apply)$/i.test(text)) { kind = "submit"; score = 10; }
      else if (/^apply( now)?$/i.test(text)) { kind = "submit"; score = 4; }
      else if (/^(next|continue|save (and|&) continue|proceed|next step|review( application)?)\b/i.test(text)) { kind = "next"; score = 8; }
    } else if (/^(apply( (now|for this (job|role|position)|here|online))?|i'?m interested|start application)$/i.test(text)) {
      kind = "apply"; score = 8;
    }
    // sign-in walls (Workday & co.): recognised on any page
    const auto = (b.getAttribute("data-automation-id") || "").toLowerCase();
    if (!kind) {
      if (/^(sign in|log in|continue|login) with google$/i.test(text) || auto === "googlesigninbutton" ||
          (isGForm && /^sign in$/i.test(text))) { kind = "sso_google"; score = 10; }
      else if (/^(sign in|continue|log in) with (e-?mail|email address)$/i.test(text) || auto === "signinwithemailbutton") { kind = "email_signin"; score = 10; }
      else if (/^(create (an )?account|sign up|register)$/i.test(text) || auto === "createaccountlink" || auto === "createaccountsubmitbutton") { kind = "create_account"; score = auto === "createaccountsubmitbutton" ? 12 : 8; }
      else if (hasPasswordField && (/^(sign in|log in|login)$/i.test(text) || auto === "signinsubmitbutton")) { kind = "signin"; score = 10; }
    }
    if (!kind) return;
    score += (inForm ? 3 : 0) + (isSubmitType ? 2 : 0) + domIndex / 100000;  // later in DOM ≈ bottom of form
    if (!best[kind] || best[kind].score < score) best[kind] = { el: b, text, score };
  });
  const buttons = [];
  for (const [kind, v] of Object.entries(best)) {
    const bkey = framePrefix + "btn:" + kind;
    document.querySelectorAll(`[data-jobos-button="${bkey}"]`).forEach((n) => n.removeAttribute("data-jobos-button"));
    v.el.setAttribute("data-jobos-button", bkey);
    buttons.push({ kind, label: v.text, locator: { button: bkey } });
  }

  // ---------- page classification
  const bodyText = clean(document.body ? document.body.innerText : "");
  const lower = bodyText.toLowerCase();
  let kind = "other";
  const hasPassword = Array.from(document.querySelectorAll("input[type=password]")).some(isVisible);
  const captchaFrame = Array.from(document.querySelectorAll("iframe")).some((f) => /captcha|challenge|turnstile/i.test(f.src || "") && f.getBoundingClientRect().width > 100 && f.getBoundingClientRect().height > 100);
  if (/(thank(s| you) for (applying|your (application|interest))|application (has been |was )?(received|submitted)|we('ve| have) received your application|successfully (applied|submitted)|your response has been recorded)/i.test(lower) && meaningful < 2) kind = "confirmation";
  else if (isGForm && (gformLocked || (!fields.length && /(sign in to continue|you need permission|only (users|people) in)/i.test(lower)))) kind = "login";
  else if (/(no longer (accepting|available|open)|position (has been )?(filled|closed)|job (posting )?(is )?(not found|closed|expired)|page not found)/i.test(lower) && meaningful < 2) kind = "closed";
  else if (captchaFrame || /verify (that )?you are (a )?human|are you a robot/i.test(lower)) kind = "captcha";
  else if ((hasPassword && meaningful <= 4) || (meaningful < 2 && buttons.some((b) => ["sso_google", "email_signin", "create_account"].includes(b.kind)))) kind = "login";
  else if (meaningful >= 2 || (isGForm && fields.length)) kind = "form";
  else if (buttons.some((b) => b.kind === "apply")) kind = "job_description";

  // ---------- visible errors
  const errors = [];
  document.querySelectorAll("[role=alert], [aria-live=assertive], .error, .errors, .field-error, [class*=error-message], [class*=errorMessage], [class*=helper-text--error]").forEach((e) => {
    if (!isVisible(e)) return;
    const t = visibleText(e);
    if (t && t.length < 300 && !errors.includes(t)) errors.push(t);
  });

  return {
    url: location.href, title: document.title, kind, fields, buttons, errors: errors.slice(0, 20),
    text_excerpt: bodyText.slice(0, MAX_TEXT),
  };
}
