// Global Aitesty client scripts
function showToast(message, type = 'info') {
  const container = document.createElement('div');
  container.className = `fixed bottom-5 right-5 z-50 rounded-xl px-4 py-3 shadow-lg text-xs font-medium flex items-center space-x-2 transition-all duration-300 transform translate-y-2 opacity-0 ${
    type === 'success' ? 'bg-emerald-600 text-white shadow-emerald-600/30' :
    type === 'error' ? 'bg-rose-600 text-white shadow-rose-600/30' :
    'bg-slate-900 text-white shadow-slate-900/30'
  }`;

  const icon = document.createElement('i');
  icon.className = type === 'success' ? 'fa-solid fa-circle-check' :
                   type === 'error' ? 'fa-solid fa-triangle-exclamation' :
                   'fa-solid fa-circle-info';

  const text = document.createElement('span');
  text.textContent = message;

  container.appendChild(icon);
  container.appendChild(text);
  document.body.appendChild(container);

  requestAnimationFrame(() => {
    container.classList.remove('translate-y-2', 'opacity-0');
  });

  setTimeout(() => {
    container.classList.add('translate-y-2', 'opacity-0');
    setTimeout(() => container.remove(), 350);
  }, 3000);
}
