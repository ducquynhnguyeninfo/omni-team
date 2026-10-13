(options = {}) => {
  // omni-team UI probe, in-page half: measures what a machine can measure on the rendered
  // page at the current viewport width, and changes nothing. The whole file is one function
  // expression so any browser tool's "evaluate" can run it as is; ui-probe.mjs runs it at
  // several widths. Findings are leads to confirm on a screenshot, not verdicts.
  const minTarget = options.minTarget ?? 24;   // WCAG 2.2 SC 2.5.8 minimum target size, CSS px
  const maxPerCheck = options.maxPerCheck ?? 8;
  const only = options.only ? new Set(options.only) : null;
  const root = document.documentElement;
  const viewport = root.clientWidth;
  const issues = {};
  const counts = {};
  const colorCache = new Map();
  const canvas = document.createElement("canvas").getContext("2d", { willReadFrequently: true });

  function add(check, el, detail) {
    counts[check] = (counts[check] || 0) + 1;
    issues[check] = issues[check] || [];
    if (issues[check].length < maxPerCheck) issues[check].push({ at: describe(el), text: textOf(el), ...detail });
  }

  function describe(el) {
    const parts = [];
    for (let node = el; node && node !== root && parts.length < 3; node = node.parentElement) {
      const classes = [...node.classList].slice(0, 2).map((c) => `.${c}`).join("");
      parts.unshift(node.tagName.toLowerCase() + (node.id ? `#${node.id}` : "") + classes);
    }
    return parts.join(" > ") || el.tagName.toLowerCase();
  }

  function textOf(el) {
    const raw = el.innerText || el.getAttribute("aria-label") || el.getAttribute("alt") || el.value || "";
    return String(raw).replace(/\s+/g, " ").trim().slice(0, 60);
  }

  function isVisible(el) {
    const rect = el.getBoundingClientRect();
    if (rect.width <= 1 || rect.height <= 1) return false;
    if (el.checkVisibility) return el.checkVisibility({ opacityProperty: true, visibilityProperty: true });
    const style = getComputedStyle(el);
    return style.visibility !== "hidden" && style.display !== "none" && style.opacity !== "0";
  }

  function hasOwnText(el) {
    return [...el.childNodes].some((n) => n.nodeType === Node.TEXT_NODE && n.textContent.trim());
  }

  // Any CSS colour (rgb, hsl, oklch, color-mix…) → [r, g, b, a] by painting one pixel.
  function rgba(color) {
    if (colorCache.has(color)) return colorCache.get(color);
    canvas.clearRect(0, 0, 1, 1);
    canvas.fillStyle = "rgba(0, 0, 0, 0)";
    canvas.fillStyle = color;
    canvas.fillRect(0, 0, 1, 1);
    const [r, g, b, a] = canvas.getImageData(0, 0, 1, 1).data;
    const value = [r, g, b, a / 255];
    colorCache.set(color, value);
    return value;
  }

  function over(top, bottom) {
    const a = top[3];
    return [0, 1, 2].map((i) => top[i] * a + bottom[i] * (1 - a)).concat(1);
  }

  // Background behind el, or null when an image or gradient makes it unknowable.
  function backgroundOf(el) {
    const layers = [];
    for (let node = el; node; node = node.parentElement) {
      const style = getComputedStyle(node);
      if (style.backgroundImage !== "none") return null;
      const color = rgba(style.backgroundColor);
      if (color[3] > 0) layers.push(color);
      if (color[3] >= 1) break;
    }
    return layers.reverse().reduce((below, layer) => over(layer, below), [255, 255, 255, 1]);
  }

  function luminance([r, g, b]) {
    const lin = (v) => (v /= 255) <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
  }

  function contrast(a, b) {
    const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
    return (hi + 0.05) / (lo + 0.05);
  }

  function escapesViewport(el) {
    for (let node = el; node && node !== document.body; node = node.parentElement) {
      const style = getComputedStyle(node);
      if (style.position === "fixed") return false;   // fixed boxes do not widen the page
      if (node !== el && style.overflowX !== "visible") return false;
    }
    return el.getBoundingClientRect().right > viewport + 1;
  }

  function checkHorizontalScroll(elements) {
    if (root.scrollWidth <= viewport + 1) return;
    for (const el of elements) {
      // Report the outermost box that pokes out; its children only follow it.
      if (!isVisible(el) || !escapesViewport(el)) continue;
      if (el.parentElement && el.parentElement !== document.body && escapesViewport(el.parentElement)) continue;
      add("horizontal_scroll", el, { right: Math.round(el.getBoundingClientRect().right), viewport });
    }
    if (!counts.horizontal_scroll) add("horizontal_scroll", root, { right: root.scrollWidth, viewport });
  }

  function checkClippedText(el, style) {
    if (!hasOwnText(el) || el.matches("input, textarea, select")) return;
    const hides = (value) => value === "hidden" || value === "clip";
    const intentional = style.textOverflow === "ellipsis" || (style.webkitLineClamp && style.webkitLineClamp !== "none");
    if (intentional) return;
    const clippedX = hides(style.overflowX) && el.scrollWidth > el.clientWidth + 1;
    const clippedY = hides(style.overflowY) && el.scrollHeight > el.clientHeight + 2;
    if (clippedX || clippedY) add("clipped_text", el, { box: `${el.clientWidth}×${el.clientHeight}`, content: `${el.scrollWidth}×${el.scrollHeight}` });
  }

  // Counts text lines from text nodes only: an icon beside the label sits at its own height.
  function checkWrappedLabel(el, style) {
    const label = (el.innerText || "").trim();
    if (!label || label.length > 40 || label.includes("\n")) return;
    const tops = [];
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const range = document.createRange();
      range.selectNodeContents(node);
      if (node.textContent.trim()) tops.push(...[...range.getClientRects()].filter((r) => r.width > 0).map((r) => r.top));
    }
    const gap = parseFloat(style.fontSize) * 0.6;
    const lines = tops.sort((a, b) => a - b).filter((top, i, all) => i === 0 || top - all[i - 1] > gap).length;
    if (lines > 1) add("wrapped_label", el, { lines });
  }

  function isTarget(el, style) {
    if (el.matches("a") && style.display === "inline") return false;   // links inside a sentence are exempt
    return !(el.matches("input[type=checkbox], input[type=radio]") && el.labels && el.labels.length);
  }

  // SC 2.5.8 spacing exception: an undersized target passes when a circle of the minimum
  // size centred on it touches no other target and no other undersized target's circle.
  function checkTargets(targets) {
    const boxes = targets.map((el) => {
      const r = el.getBoundingClientRect();
      return { el, r, x: r.left + r.width / 2, y: r.top + r.height / 2, small: r.width < minTarget || r.height < minTarget };
    });
    const radius = minTarget / 2;
    const touches = (a, b) => {
      if (b.small && Math.hypot(a.x - b.x, a.y - b.y) < minTarget) return true;
      const dx = Math.max(b.r.left - a.x, 0, a.x - b.r.right);
      const dy = Math.max(b.r.top - a.y, 0, a.y - b.r.bottom);
      return Math.hypot(dx, dy) < radius;
    };
    for (const a of boxes.filter((box) => box.small)) {
      const near = boxes.find((b) => b !== a && !b.el.contains(a.el) && !a.el.contains(b.el) && touches(a, b));
      if (!near) continue;
      add("small_target", a.el, { size: `${Math.round(a.r.width)}×${Math.round(a.r.height)}`, min: minTarget, near: describe(near.el) });
    }
  }

  function accessibleName(el) {
    const labelledBy = (el.getAttribute("aria-labelledby") || "").split(/\s+/).filter(Boolean)
      .map((id) => document.getElementById(id)?.textContent || "").join(" ");
    const labels = el.labels ? [...el.labels].map((l) => l.textContent).join(" ") : "";
    const images = [...el.querySelectorAll("img[alt], svg title")].map((n) => n.getAttribute("alt") || n.textContent).join(" ");
    const isButtonInput = el.matches("input[type=submit], input[type=button], input[type=reset]");
    return [el.getAttribute("aria-label"), labelledBy, labels, el.getAttribute("title"), el.getAttribute("placeholder"),
      isButtonInput ? el.value : "", el.matches("input, select, textarea") ? "" : el.textContent, images]
      .join(" ").trim();
  }

  function checkContrast(el, style) {
    if (!hasOwnText(el) || el.closest(":disabled, [aria-disabled=true]")) return;
    const fg = rgba(style.color);
    const bg = backgroundOf(el);
    if (!bg || fg[3] === 0) return;
    const ratio = contrast(over(fg, bg), bg);
    const size = parseFloat(style.fontSize);
    const large = size >= 24 || (size >= 18.66 && Number(style.fontWeight) >= 700);
    const min = large ? 3 : 4.5;
    if (ratio < min) add("low_contrast", el, { ratio: Math.round(ratio * 100) / 100, min, color: style.color });
  }

  function checkImage(img) {
    if (img.complete && img.currentSrc && img.naturalWidth === 0) add("broken_image", img, { src: img.currentSrc.slice(0, 120) });
    if (!img.hasAttribute("alt")) add("missing_alt", img, { src: (img.currentSrc || img.src).slice(0, 120) });
  }

  const run = (check) => !only || only.has(check);
  const elements = [...document.body.querySelectorAll("*")];
  const interactive = "a[href], button, input:not([type=hidden]), select, textarea, summary, [role=button], [role=link], " +
    "[role=tab], [role=menuitem], [role=checkbox], [role=switch], [tabindex]:not([tabindex='-1'])";
  const buttonLike = "button, [role=button], a[href], [role=tab], [role=menuitem]";

  const targets = [];

  if (run("horizontal_scroll")) checkHorizontalScroll(elements);
  for (const el of elements) {
    if (!isVisible(el)) continue;
    const style = getComputedStyle(el);
    if (run("clipped_text")) checkClippedText(el, style);
    if (run("low_contrast")) checkContrast(el, style);
    if (el.matches("img")) {
      if (run("broken_image") || run("missing_alt")) checkImage(el);
      continue;
    }
    if (!el.matches(interactive) || el.matches(":disabled")) continue;
    if (run("wrapped_label") && el.matches(buttonLike) && style.display !== "inline") checkWrappedLabel(el, style);
    if (isTarget(el, style)) targets.push(el);
    if (run("unlabeled_control") && !accessibleName(el)) add("unlabeled_control", el, {});
  }
  if (run("small_target")) checkTargets(targets);

  return { url: location.href, viewport: { width: viewport, height: innerHeight }, scroll_width: root.scrollWidth, counts, issues };
}
