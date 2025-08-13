function formatCurrency(num) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD'
  }).format(num);
}

function getOppIdFromUrl() {
  const params = new URLSearchParams(window.location.search);
  return params.get('opp_id')?.trim();
}

window.addEventListener('DOMContentLoaded', () => {
  const opp_id = getOppIdFromUrl();
  if (opp_id) {
    fetchData(opp_id);
  } else {
    document.getElementById('result').innerHTML = `<p style="color:red;">Missing Opportunity ID in URL.</p>`;
  }
});

async function fetchData(opp_id) {
  const response = await fetch(`/fetch-data?opp_id=${opp_id}`);
  if (!response.ok) {
    document.getElementById('result').innerHTML = `<p style="color:red;">${await response.text()}</p>`;
    return;
  }

  const data = await response.json();
  const resultDiv = document.getElementById('result');

  const currentRent = data.rentValue;
  const currentCashflow = data.cashflowValue;
  const threshold = data.thresholdValue;

  resultDiv.innerHTML = `
    <p><strong>Purchase Price:</strong> ${formatCurrency(data.purchasePriceValue)}</p>
    <p><strong>Current Rent:</strong> ${formatCurrency(currentRent)}</p>
    <p><strong>Proposed 3% Rent:</strong> ${formatCurrency(data.rentAfter3PercentValue)}</p>
    <p><strong>Cash Flow:</strong> ${formatCurrency(currentCashflow)}</p>
    <p><strong>Required Threshold:</strong> ${formatCurrency(threshold)}</p>
    <p id="cashflowStatus"></p>

    <fieldset>
      <legend><strong>Update Rent Decision</strong></legend>

      <label class="inline">
        <input type="radio" name="rentChoice" value="system" checked />
        Use system 3% increase (${formatCurrency(data.rentAfter3PercentValue)})
      </label>

      <label class="inline">
        <input type="radio" name="rentChoice" value="custom" />
        Enter custom rent
      </label>

      <label>
        New Rent:
        <input type="number" id="approvedRent" value="${data.rentAfter3PercentValue}" step="0.01" />
      </label>

      <label>
        Lease Start Date:
        <input type="date" id="leaseStartDate" />
      </label>

      <label>
        <input type="checkbox" id="sendLeaseCheckbox" checked />
        Send Lease?
      </label>

      <button onclick="submitDecision('${opp_id}', ${data.rowNumber}, ${data.rentAfter3PercentValue})">Submit Update</button>
    </fieldset>
  `;

  const approvedRentInput = document.getElementById('approvedRent');

  async function updateCashflowDisplay() {
    const newRent = parseFloat(approvedRentInput.value);
    if (isNaN(newRent)) return;
    try {
      const resp = await fetch('/calculate-cashflow', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          currentRent,
          currentCashflow,
          threshold,
          newRent
        })
      });
      if (!resp.ok) return;
      const res = await resp.json();
      const statusEl = document.getElementById('cashflowStatus');
      const diffAbs = Math.abs(res.difference);
      const msg = res.meets_threshold
        ? `Cash flow is ${formatCurrency(diffAbs)} above threshold.`
        : `Cash flow is ${formatCurrency(diffAbs)} below threshold.`;
      statusEl.textContent = msg;
      statusEl.style.color = res.meets_threshold ? 'green' : 'red';
    } catch (e) {
      console.error(e);
    }
  }

  // Enable toggle logic
  document.querySelectorAll('input[name="rentChoice"]').forEach(radio => {
    radio.addEventListener('change', () => {
      if (radio.value === 'system' && radio.checked) {
        approvedRentInput.value = data.rentAfter3PercentValue;
        approvedRentInput.readOnly = true;
      } else if (radio.value === 'custom' && radio.checked) {
        approvedRentInput.readOnly = false;
        approvedRentInput.focus();
      }
      updateCashflowDisplay();
    });
  });

  approvedRentInput.addEventListener('input', updateCashflowDisplay);

  // Start with system value locked and display initial status
  approvedRentInput.readOnly = true;
  updateCashflowDisplay();
}

async function submitDecision(opp_id, row, fallbackRent) {
  const approvedRentInput = document.getElementById('approvedRent');
  const leaseStartDate = document.getElementById('leaseStartDate').value;
  const sendLease = document.getElementById('sendLeaseCheckbox').checked;

  let approvedRent = parseFloat(approvedRentInput.value);
  if (isNaN(approvedRent)) {
    alert('Please enter a valid rent amount.');
    return;
  }

  const payload = {
    opportunityId: opp_id,
    approvedRent,
    row,
    leaseStartDate: leaseStartDate || null,
    sendLease
  };

  const response = await fetch('/submit-decision', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  if (response.ok) {
    alert('✅ Rent update submitted successfully.');
    window.close();
  } else {
    const errorMsg = await response.text();
    alert('❌ Update failed: ' + errorMsg);
  }
}