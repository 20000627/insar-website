// Navigation
document.addEventListener('DOMContentLoaded', () => {
  const toggle = document.querySelector('.mobile-toggle');
  const nav = document.querySelector('.nav-links');
  if (toggle) toggle.addEventListener('click', () => nav.classList.toggle('open'));
  // Mark current page
  const page = location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.nav-links a').forEach(a => {
    if (a.getAttribute('href') === page) a.classList.add('active');
  });
});

// Scroll animations
const observer = new IntersectionObserver(entries => {
  entries.forEach(e => {
    if (e.isIntersecting) e.target.style.opacity = '1';
  });
}, { threshold: 0.1 });
document.querySelectorAll('.card, .solution-detail, .process-step').forEach(el => {
  el.style.opacity = '0';
  el.style.transition = 'opacity .6s ease';
  observer.observe(el);
});
