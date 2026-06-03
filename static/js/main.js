/* ConstructLearn Pro — JS principal */

// ── Menu utilisateur ──────────────────────────────────────
function toggleUserMenu() {
  document.getElementById('user-menu')?.classList.toggle('open');
}
document.addEventListener('click', (e) => {
  if (!e.target.closest('.nav-avatar-menu')) {
    document.getElementById('user-menu')?.classList.remove('open');
  }
});

// ── Fermeture auto des flash après 4s ────────────────────
document.querySelectorAll('.flash').forEach(f => {
  setTimeout(() => f.remove(), 4000);
});

// ── Confirmation avant suppression ───────────────────────
document.querySelectorAll('[data-confirm]').forEach(el => {
  el.addEventListener('click', (e) => {
    if (!confirm(el.dataset.confirm)) e.preventDefault();
  });
});
