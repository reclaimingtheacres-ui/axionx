---
name: Bootstrap Modal Stacking Context Trap
description: Why Bootstrap modals inside .ax-shell are non-interactive, and the fix.
---

## Rule
Any Bootstrap modal rendered inside `.ax-shell` (or any element with `position:relative; z-index:N`) must be moved to `<body>` via JavaScript before it can be interacted with.

## Why
`.ax-shell` has `position:relative; z-index:1`, which creates a CSS stacking context. Bootstrap appends its `.modal-backdrop` to `<body>` at `z-index:1040`. In the paint order, the backdrop (z-index:1040 in body's context) sits **above** the entire `.ax-shell` context (z-index:1 in body), regardless of the modal dialog's own z-index:1055 — that z-index is relative to `.ax-shell`'s context, not body's. The backdrop absorbs all click events, making the modal appear but be completely non-interactive.

## How to Apply
At the bottom of any template's `<script>` block (inside the IIFE, after init), add:

```javascript
['myModal1','myModal2'].forEach(function(id) {
  var el = document.getElementById(id);
  if (el && el.parentNode !== document.body) document.body.appendChild(el);
});
```

This puts the modals in body's stacking context, where Bootstrap's backdrop and modal dialog z-index comparisons work correctly.

Note: layout.html's `idleWarningModal` and `axPhoneSheet` are already direct children of `<body>` (defined outside `.ax-shell`) and are unaffected.
