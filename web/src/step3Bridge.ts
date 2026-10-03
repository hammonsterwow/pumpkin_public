type AnalysisPayload = {
  robot_response?: string;
};

let latestResponse = '';

function renderStep3(): void {
  const grid = document.querySelector<HTMLElement>('.page-grid');
  if (!grid || !latestResponse) return;

  let panel = document.getElementById('step3-robot-response');
  if (!panel) {
    panel = document.createElement('article');
    panel.id = 'step3-robot-response';
    panel.className = 'panel';
    panel.style.gridColumn = '1 / -1';
    panel.innerHTML = `
      <div class="panel-heading">
        <div><span>STEP 3</span><h2>로봇 대응</h2></div>
      </div>
      <div id="step3-response-text" role="status" aria-live="polite"></div>
    `;
    grid.appendChild(panel);
  }

  const text = panel.querySelector<HTMLElement>('#step3-response-text');
  if (text) {
    text.textContent = latestResponse;
    text.style.background = '#f8f4f1';
    text.style.border = '2px solid #d7c7bd';
    text.style.borderRadius = '14px';
    text.style.padding = '24px';
    text.style.fontSize = '28px';
    text.style.fontWeight = '900';
    text.style.lineHeight = '1.5';
  }
}

const originalFetch = window.fetch.bind(window);
window.fetch = async (...args): Promise<Response> => {
  const response = await originalFetch(...args);
  const requestUrl = typeof args[0] === 'string' ? args[0] : args[0] instanceof Request ? args[0].url : '';

  if (requestUrl.includes('/api/orders/analyze') && response.ok) {
    response.clone().json().then((payload: AnalysisPayload) => {
      latestResponse = payload.robot_response?.trim() || '';
      renderStep3();
    }).catch(() => undefined);
  }

  return response;
};

new MutationObserver(renderStep3).observe(document.documentElement, {
  childList: true,
  subtree: true,
});
