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

  resultDiv.innerHTML = `
    <p><strong>Purchase Price:</strong> ${formatCurrency(data.purchasePrice)}</p>
    <p><strong>Current Rent:</strong> ${formatCurrency(data.rent)}</p>
    <p><strong>Proposed 3% Rent:</strong> ${formatCurrency(data.rentAfter3Percent)}</p>
    <p><strong>Cash Flow:</strong> ${formatCurrency(data.cashflow)}</p>
    <p><strong>Required Threshold:</strong> ${formatCurrency(data.threshold)}</p>

    <fieldset>
      <legend><strong>Update Rent Decision</strong></legend>

      <label class="inline">
        <input type="radio" name="rentChoice" value="system" checked />
        Use system 3% increase (${formatCurrency(data.rentAfter3Percent)})
      </label>

      <label class="inline">
        <input type="radio" name="rentChoice" value="custom" />
        Enter custom rent
      </label>

      <label>
        New Rent:
        <input type="number" id="approvedRent" value="${data.rentAfter3Percent}" step="0.01" />
      </label>

      <label>
        Lease Start Date:
        <input type="date" id="leaseStartDate" />
      </label>

      <label>
        <input type="checkbox" id="sendLeaseCheckbox" checked />
        Send Lease?
      </label>

      <button onclick="submitDecision('${opp_id}', ${data.rowNumber}, ${data.rentAfter3Percent})">Submit Update</button>
    </fieldset>
  `;

  // Enable toggle logic
  document.querySelectorAll('input[name="rentChoice"]').forEach(radio => {
    radio.addEventListener('change', () => {
      const approvedRentInput = document.getElementById('approvedRent');
      if (radio.value === 'system' && radio.checked) {
        approvedRentInput.value = data.rentAfter3Percent;
        approvedRentInput.readOnly = true;
      } else if (radio.value === 'custom' && radio.checked) {
        approvedRentInput.readOnly = false;
        approvedRentInput.focus();
      }
    });
  });

  // Start with system value locked
  document.getElementById('approvedRent').readOnly = true;
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
