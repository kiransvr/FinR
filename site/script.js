const navbar = document.getElementById('navbar');
const hamburger = document.getElementById('hamburger');
const navLinks = document.getElementById('navLinks');
const contactForm = document.getElementById('contactForm');
const formMsg = document.getElementById('formMsg');
const scoreForm = document.getElementById('scoreForm');
const scoreStroke = document.getElementById('scoreStroke');
const sections = document.querySelectorAll('section[id]');
const navItems = document.querySelectorAll('.nav-links a');

window.addEventListener('scroll', () => {
  navbar.classList.toggle('scrolled', window.scrollY > 24);

  let currentSection = '';
  sections.forEach((section) => {
    if (window.scrollY >= section.offsetTop - 140) {
      currentSection = section.getAttribute('id');
    }
  });

  navItems.forEach((link) => {
    link.classList.toggle('is-active', link.getAttribute('href') === `#${currentSection}`);
  });
});

if (hamburger && navLinks) {
  hamburger.addEventListener('click', () => {
    navLinks.classList.toggle('open');
  });

  navLinks.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', () => navLinks.classList.remove('open'));
  });
}

document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
  anchor.addEventListener('click', (event) => {
    const target = document.querySelector(anchor.getAttribute('href'));
    if (!target) {
      return;
    }

    event.preventDefault();
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
});

const revealObserver = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (!entry.isIntersecting) {
      return;
    }

    entry.target.classList.add('is-visible');
    revealObserver.unobserve(entry.target);
  });
}, { threshold: 0.14 });

document.querySelectorAll('.card, .glass-card, .timeline-item, .architecture-card').forEach((element) => {
  element.classList.add('will-reveal');
  revealObserver.observe(element);
});

function animateCounter(element, target, suffix) {
  let startTimestamp = 0;
  const duration = 1400;

  const update = (timestamp) => {
    if (!startTimestamp) {
      startTimestamp = timestamp;
    }

    const progress = Math.min((timestamp - startTimestamp) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    const value = Math.round(target * eased);
    element.textContent = `${value}${suffix}`;

    if (progress < 1) {
      requestAnimationFrame(update);
    }
  };

  requestAnimationFrame(update);
}

const statsObserver = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (!entry.isIntersecting) {
      return;
    }

    entry.target.querySelectorAll('.stat-num').forEach((stat) => {
      animateCounter(
        stat,
        Number(stat.dataset.target || 0),
        stat.dataset.suffix || ''
      );
    });

    statsObserver.unobserve(entry.target);
  });
}, { threshold: 0.45 });

const heroStats = document.querySelector('.hero-stats');
if (heroStats) {
  statsObserver.observe(heroStats);
}

const hero = document.querySelector('.hero');
const glow1 = document.querySelector('.glow-1');
const glow2 = document.querySelector('.glow-2');

if (hero && glow1 && glow2) {
  hero.addEventListener('mousemove', (event) => {
    const rect = hero.getBoundingClientRect();
    const offsetX = (event.clientX - rect.left) / rect.width - 0.5;
    const offsetY = (event.clientY - rect.top) / rect.height - 0.5;

    glow1.style.transform = `translate(${offsetX * 20}px, ${offsetY * 20}px)`;
    glow2.style.transform = `translate(${offsetX * -18}px, ${offsetY * -18}px)`;
  });

  hero.addEventListener('mouseleave', () => {
    glow1.style.transform = 'translate(0, 0)';
    glow2.style.transform = 'translate(0, 0)';
  });
}

const simulatorState = {
  deviceTenure: { new: -45, mid: 0, established: 38 },
  employmentType: { variable: -18, salary: 30, merchant: 12 },
  utilityHistory: { none: -28, partial: 4, strong: 24 },
};

function formatCurrency(value) {
  return new Intl.NumberFormat('en-US').format(Math.round(value));
}

function describeReasons({ rechargeFrequency, mobileMoney, geoConsistency, deviceTenure, employmentType, utilityHistory, requestedLoan }) {
  const reasons = [];

  reasons.push(
    rechargeFrequency >= 16
      ? 'Frequent airtime recharges indicate steady phone usage.'
      : 'Recharge behavior is still light, so usage history is less predictive.'
  );
  reasons.push(
    mobileMoney >= 65
      ? 'Transaction activity supports stronger cash-flow confidence.'
      : 'Transaction intensity is moderate and should be paired with policy controls.'
  );
  reasons.push(
    geoConsistency >= 70
      ? 'Movement patterns look stable enough for relationship-based lending.'
      : 'Movement inconsistency increases uncertainty for thin-file underwriting.'
  );

  if (deviceTenure === 'established') {
    reasons.push('Longer device tenure improves identity and continuity confidence.');
  } else if (deviceTenure === 'new') {
    reasons.push('Very recent device tenure reduces continuity confidence.');
  }

  if (employmentType === 'salary') {
    reasons.push('Salary-backed income reduces volatility in repayment expectations.');
  } else if (employmentType === 'merchant') {
    reasons.push('Merchant cash cycles can be strong, but may need seasonal policy tuning.');
  }

  if (utilityHistory === 'strong') {
    reasons.push('On-time utility behavior reinforces repayment discipline signals.');
  }

  if (requestedLoan > 30000) {
    reasons.push('Requested amount is high relative to observed alternative-signal confidence.');
  }

  return reasons.slice(0, 4);
}

function updateSimulator() {
  if (!scoreForm) {
    return;
  }

  const formData = new FormData(scoreForm);
  const rechargeFrequency = Number(formData.get('rechargeFrequency'));
  const mobileMoney = Number(formData.get('mobileMoney'));
  const geoConsistency = Number(formData.get('geoConsistency'));
  const deviceTenure = formData.get('deviceTenure');
  const employmentType = formData.get('employmentType');
  const utilityHistory = formData.get('utilityHistory');
  const requestedLoan = Number(formData.get('loanRequest'));

  document.querySelector('[data-output="rechargeFrequency"]').textContent = `${rechargeFrequency} / month`;
  document.querySelector('[data-output="mobileMoney"]').textContent = `${mobileMoney}`;
  document.querySelector('[data-output="geoConsistency"]').textContent = `${geoConsistency}`;

  let score = 500;
  score += rechargeFrequency * 5;
  score += mobileMoney * 1.2;
  score += geoConsistency * 1.1;
  score += simulatorState.deviceTenure[deviceTenure];
  score += simulatorState.employmentType[employmentType];
  score += simulatorState.utilityHistory[utilityHistory];
  score -= Math.max(0, (requestedLoan - 15000) / 500);
  score = Math.max(320, Math.min(850, Math.round(score)));

  const pd = Math.max(0.04, Math.min(0.42, (850 - score) / 950));
  const recommendedLoanCap = Math.max(5000, Math.round((score - 300) * 55));

  let riskBand = 'Medium risk';
  let decision = 'Review manually';
  let approvalMode = 'Conditional approval';
  let tagClass = 'pill';

  if (score >= 720) {
    riskBand = 'Low risk';
    decision = 'Approve';
    approvalMode = 'Auto-approve threshold';
    tagClass = 'pill pill-safe';
  } else if (score < 580) {
    riskBand = 'High risk';
    decision = 'Restrict';
    approvalMode = 'Manual review or decline';
    tagClass = 'pill pill-risk';
  }

  document.getElementById('creditScore').textContent = score;
  document.getElementById('pdValue').textContent = `${(pd * 100).toFixed(1)}%`;
  document.getElementById('loanCap').textContent = `ETB ${formatCurrency(recommendedLoanCap)}`;
  document.getElementById('riskBand').textContent = riskBand;
  document.getElementById('decisionTag').textContent = decision;
  document.getElementById('decisionTag').className = tagClass;
  document.getElementById('approvalMode').textContent = approvalMode;

  const scorePercent = ((score - 320) / (850 - 320)) * 327;
  scoreStroke.style.strokeDashoffset = `${327 - scorePercent}`;

  const reasonList = document.getElementById('reasonList');
  reasonList.innerHTML = '';

  describeReasons({
    rechargeFrequency,
    mobileMoney,
    geoConsistency,
    deviceTenure,
    employmentType,
    utilityHistory,
    requestedLoan,
  }).forEach((reason) => {
    const item = document.createElement('li');
    item.textContent = reason;
    reasonList.appendChild(item);
  });
}

if (scoreForm) {
  scoreForm.addEventListener('input', updateSimulator);
  scoreForm.addEventListener('change', updateSimulator);
  updateSimulator();
}

if (contactForm) {
  contactForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const button = contactForm.querySelector('button[type="submit"]');
    button.disabled = true;
    button.textContent = 'Sending...';

    window.setTimeout(() => {
      button.disabled = false;
      button.textContent = 'Request pilot discussion';
      formMsg.textContent = 'Pilot request captured. Use this flow to connect the form to your CRM or FastAPI backend.';
      contactForm.reset();
      updateSimulator();
    }, 900);
  });
}
