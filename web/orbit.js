/* Orbit Reports Help Center – small, dependency-free enhancements */
(function () {
  'use strict';

  // Mobile navigation toggle
  var toggle = document.querySelector('.nav-toggle');
  var nav = document.getElementById('site-nav');
  if (toggle && nav) {
    toggle.addEventListener('click', function () {
      var open = toggle.getAttribute('aria-expanded') === 'true';
      toggle.setAttribute('aria-expanded', String(!open));
      toggle.setAttribute('aria-label', open ? 'Open menu' : 'Close menu');
      nav.classList.toggle('is-open', !open);
    });
    nav.addEventListener('click', function (e) {
      if (e.target.closest('a')) {
        toggle.setAttribute('aria-expanded', 'false');
        toggle.setAttribute('aria-label', 'Open menu');
        nav.classList.remove('is-open');
      }
    });
  }

  // Non-functional search: never navigates, just explains itself
  var form = document.querySelector('.search');
  var input = document.getElementById('q');
  var hint = document.querySelector('.search-hint');
  if (form && input && hint) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var q = input.value.trim();
      hint.textContent = q
        ? 'Search is disabled in this demo. Try the help chat in the corner, or browse the articles below.'
        : 'Type a question, or browse the articles below.';
    });
    input.addEventListener('input', function () { hint.textContent = ''; });
  }

  // Suggestion chips fill the search box
  var chips = document.querySelectorAll('.chip[data-q]');
  Array.prototype.forEach.call(chips, function (chip) {
    chip.addEventListener('click', function () {
      if (!input) { return; }
      input.value = chip.getAttribute('data-q');
      input.focus();
      if (hint) { hint.textContent = ''; }
    });
  });
})();
