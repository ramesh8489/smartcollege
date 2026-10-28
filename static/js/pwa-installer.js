/**
 * Takshashila University - PWA Mobile App Installer & Service Worker Manager
 */
(function() {
  'use strict';

  let deferredInstallPrompt = null;
  const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
  const isStandalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;

  // Mark body if opened as installed standalone native app
  if (isStandalone) {
    document.documentElement.classList.add('app-standalone-mode');
    document.body && document.body.classList.add('app-standalone-mode');
  }

  // 1. Register Service Worker
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js', { scope: '/' })
        .then((registration) => {
          console.log('[Takshashila PWA] Service Worker registered with scope:', registration.scope);
        })
        .catch((error) => {
          console.warn('[Takshashila PWA] Service Worker registration failed:', error);
        });
    });
  }

  // 2. Intercept beforeinstallprompt
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredInstallPrompt = e;
    console.log('[Takshashila PWA] Captured beforeinstallprompt event');

    // Reveal all install triggers on the page
    document.querySelectorAll('.pwa-install-trigger').forEach((el) => {
      el.style.display = 'inline-flex';
      el.removeAttribute('hidden');
    });

    const banner = document.getElementById('pwa-mobile-install-banner');
    if (banner && !sessionStorage.getItem('pwa_banner_dismissed') && !isStandalone) {
      banner.style.display = 'block';
    }
  });

  // Track app installation completion
  window.addEventListener('appinstalled', () => {
    console.log('[Takshashila PWA] App successfully installed!');
    deferredInstallPrompt = null;
    document.querySelectorAll('.pwa-install-trigger').forEach((el) => {
      el.style.display = 'none';
    });
    const banner = document.getElementById('pwa-mobile-install-banner');
    if (banner) banner.style.display = 'none';
    showToast('🎉 Takshashila University App installed on your home screen!');
  });

  // Global trigger function for install buttons
  window.triggerPWAInstall = function() {
    if (deferredInstallPrompt) {
      deferredInstallPrompt.prompt();
      deferredInstallPrompt.userChoice.then((choiceResult) => {
        if (choiceResult.outcome === 'accepted') {
          console.log('[Takshashila PWA] User accepted installation prompt');
        } else {
          console.log('[Takshashila PWA] User dismissed installation prompt');
        }
        deferredInstallPrompt = null;
      });
      return;
    }

    // Chrome PWA requires localhost or HTTPS. If on numeric IP 127.0.0.1, switch to localhost.
    if (window.location.hostname === '127.0.0.1') {
      const target = window.location.href.replace('127.0.0.1', 'localhost');
      window.location.href = target;
      return;
    }

    // Fallback: Open friendly step-by-step installation guide modal
    openInstallGuideModal();
  };

  window.dismissPWABanner = function() {
    const banner = document.getElementById('pwa-mobile-install-banner');
    if (banner) banner.style.display = 'none';
    sessionStorage.setItem('pwa_banner_dismissed', 'true');
  };

  // Open Step-by-Step Installation Modal
  window.openInstallGuideModal = function() {
    let modal = document.getElementById('pwa-install-guide-modal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'pwa-install-guide-modal';
      modal.className = 'pwa-modal-overlay';
      modal.innerHTML = `
        <div class="pwa-modal-dialog">
          <div class="pwa-modal-header">
            <div style="display: flex; align-items: center; gap: 12px;">
              <div class="pwa-modal-logo">
                <img src="/static/images/pwa/icon-192.png" alt="Takshashila App" style="width: 44px; height: 44px; border-radius: 10px; display: block;">
              </div>
              <div>
                <h3 style="margin: 0; font-size: 16px; font-weight: 800; color: var(--ink, #0f172a);">Install Takshashila App</h3>
                <div style="font-size: 12px; color: var(--muted, #64748b);">Fast, Lightweight Mobile & Desktop App</div>
              </div>
            </div>
            <button type="button" class="pwa-modal-close" onclick="closeInstallGuideModal()" aria-label="Close">&times;</button>
          </div>
          <div class="pwa-modal-body">
            <p style="margin-top: 0; font-size: 13.5px; line-height: 1.5; color: var(--ink, #334155);">
              Install the official <b>Takshashila University</b> application directly onto your mobile or computer:
            </p>

            ${isIOS ? `
              <div class="pwa-guide-steps">
                <div class="pwa-step">
                  <div class="pwa-step-num">1</div>
                  <div class="pwa-step-text">Tap the <b>Share</b> button <span style="font-size: 17px;">⎋</span> at the bottom of Safari.</div>
                </div>
                <div class="pwa-step">
                  <div class="pwa-step-num">2</div>
                  <div class="pwa-step-text">Scroll down and tap <b>Add to Home Screen</b> <span style="font-size: 16px;">⊞</span>.</div>
                </div>
                <div class="pwa-step">
                  <div class="pwa-step-num">3</div>
                  <div class="pwa-step-text">Tap <b>Add</b> in the top right corner. The app icon will appear on your home screen!</div>
                </div>
              </div>
            ` : `
              <div class="pwa-guide-steps">
                <div class="pwa-step">
                  <div class="pwa-step-num">1</div>
                  <div class="pwa-step-text">Look at the <b>address bar</b> (top right of browser): Click the <b>Install App (💻 / ⊕)</b> icon.</div>
                </div>
                <div class="pwa-step">
                  <div class="pwa-step-num">2</div>
                  <div class="pwa-step-text">Or tap the browser menu (<b>⋮</b>) &rarr; select <b>"Install Takshashila..."</b> or <b>"Add to Home screen"</b>.</div>
                </div>
                <div class="pwa-step">
                  <div class="pwa-step-num">3</div>
                  <div class="pwa-step-text">Confirm <b>Install</b>. The app will launch in dedicated native fullscreen mode!</div>
                </div>
              </div>
            `}

            <div style="margin-top: 14px;">
              <a href="/app/download-launcher/" class="btn btn-primary btn-sm" style="display: flex; width: 100%; justify-content: center; align-items: center; gap: 8px; text-decoration: none; padding: 10px; font-weight: 800;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                <span>Download Desktop App Launcher (.bat)</span>
              </a>
            </div>

            <div style="margin-top: 14px; padding: 10px 14px; background: #eef2ff; border: 1px solid #c7d2fe; border-radius: 10px; font-size: 12px; color: #3730a3; display: flex; align-items: center; gap: 8px;">
              <span>⚡</span>
              <span><b>Native Experience:</b> Standalone window, instant launch, and offline caching.</span>
            </div>
          </div>
          <div class="pwa-modal-footer">
            <button type="button" class="btn btn-soft btn-sm" style="width: 100%; justify-content: center;" onclick="closeInstallGuideModal()">Close</button>
          </div>
        </div>
      `;
      document.body.appendChild(modal);
    }
    modal.classList.add('is-active');
  };

  window.closeInstallGuideModal = function() {
    const modal = document.getElementById('pwa-install-guide-modal');
    if (modal) modal.classList.remove('is-active');
  };

  // Online / Offline Status Indicators
  window.addEventListener('online', () => {
    showToast('🟢 Internet restored! Connected to Takshashila server.');
  });
  window.addEventListener('offline', () => {
    showToast('⚠️ You are offline. Cached pages remain accessible.');
  });

  function showToast(msg) {
    let toast = document.getElementById('pwa-status-toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'pwa-status-toast';
      toast.className = 'pwa-toast';
      document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(() => {
      toast.classList.remove('show');
    }, 4000);
  }

})();
