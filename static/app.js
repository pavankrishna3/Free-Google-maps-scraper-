// DOM Elements
const scrapeForm = document.getElementById('scrape-form');
const queryInput = document.getElementById('query-input');
const maxResultsInput = document.getElementById('max-results-input');
const headlessCheckbox = document.getElementById('headless-checkbox');
const startBtn = document.getElementById('start-btn');
const stopBtn = document.getElementById('stop-btn');
const downloadBtn = document.getElementById('download-btn');
const clearLogsBtn = document.getElementById('clear-logs-btn');

const statusBadge = document.getElementById('status-badge');
const consoleLogs = document.getElementById('console-logs');
const leadsTbody = document.getElementById('leads-tbody');
const emptyRow = document.getElementById('empty-row');
const tableCountLabel = document.getElementById('table-count-label');

// Stat Counters Elements
const statFound = document.getElementById('stat-found');
const statWebsites = document.getElementById('stat-websites');
const statEmails = document.getElementById('stat-emails');
const statOwners = document.getElementById('stat-owners');

let eventSource = null;
let leadCount = 0;
let websiteCount = 0;
let emailCount = 0;
let ownerCount = 0;

// Log function to append message to console box
function addLog(message, type = 'info') {
    const timeString = new Date().toLocaleTimeString();
    const logLine = document.createElement('div');
    logLine.className = `log-line ${type}`;
    logLine.innerHTML = `<span class="text-muted">[${timeString}]</span> ${message}`;
    consoleLogs.appendChild(logLine);
    consoleLogs.scrollTop = consoleLogs.scrollHeight;
}

// Reset stats counters in UI
function resetStats() {
    leadCount = 0;
    websiteCount = 0;
    emailCount = 0;
    ownerCount = 0;
    
    statFound.textContent = '0';
    statWebsites.textContent = '0';
    statEmails.textContent = '0';
    statOwners.textContent = '0';
    tableCountLabel.textContent = '0 records';
}

// Reset table rows
function resetTable() {
    leadsTbody.innerHTML = '';
    leadsTbody.appendChild(emptyRow);
}

// Handle Scrape Start
scrapeForm.addEventListener('submit', (e) => {
    e.preventDefault();
    
    const query = queryInput.value.trim();
    const maxResults = maxResultsInput.value;
    const headless = headlessCheckbox.checked;

    if (!query) return;

    // Reset UI State
    resetStats();
    resetTable();
    addLog(`Initiating scraping session for: "${query}"...`, 'system');
    
    // Toggle Button States
    startBtn.disabled = true;
    stopBtn.disabled = false;
    downloadBtn.disabled = true;
    
    // Set Status
    statusBadge.textContent = 'Scraping';
    statusBadge.className = 'badge scraping';

    // Construct URL with query parameters
    const params = new URLSearchParams({
        q: query,
        max_results: maxResults,
        headless: headless
    });

    const sseUrl = `/api/scrape?${params.toString()}`;

    // Initialize EventSource
    eventSource = new EventSource(sseUrl);

    eventSource.onmessage = (event) => {
        const payload = JSON.parse(event.data);

        if (payload.type === 'log') {
            // Handle logs from python server
            let logType = 'info';
            if (payload.message.includes('Error') || payload.message.includes('Failed')) {
                logType = 'error';
            } else if (payload.message.includes('Successfully') || payload.message.includes('completed')) {
                logType = 'success';
            }
            addLog(payload.message, logType);
            
            // Adjust badge class dynamically if website crawling starts
            if (payload.message.includes('Crawling website')) {
                statusBadge.textContent = 'Crawling';
                statusBadge.className = 'badge crawling';
            }
        } 
        else if (payload.type === 'data') {
            // Handle scraped listing data
            const item = payload.data;
            
            // Remove empty row if first item is added
            if (leadCount === 0) {
                leadsTbody.innerHTML = '';
            }

            leadCount++;
            statFound.textContent = leadCount;
            tableCountLabel.textContent = `${leadCount} record${leadCount > 1 ? 's' : ''}`;

            if (item.website) {
                websiteCount++;
                statWebsites.textContent = websiteCount;
            }

            if (item.emails && item.emails.length > 0) {
                emailCount += item.emails.length;
                statEmails.textContent = emailCount;
            }

            if (item.owner_name) {
                ownerCount++;
                statOwners.textContent = ownerCount;
            }

            // Append new row to table
            const row = document.createElement('tr');
            
            // Website field
            const websiteCell = item.website 
                ? `<a href="${item.website}" target="_blank" class="table-link">${item.website_status === 'Accessible' ? 'Visit Site' : 'Link'} <i class="fa-solid fa-up-right-from-square" style="font-size: 10px;"></i></a>`
                : '<span class="text-muted">N/A</span>';
                
            // Emails field
            const emailsCell = item.emails && item.emails.length > 0
                ? item.emails.map(email => `<div><i class="fa-regular fa-envelope"></i> ${email}</div>`).join('')
                : '<span class="text-muted">None found</span>';

            // Socials field
            let socialsHTML = '';
            if (item.facebook) socialsHTML += `<a href="${item.facebook}" target="_blank" title="Facebook"><i class="fa-brands fa-facebook"></i></a>`;
            if (item.instagram) socialsHTML += `<a href="${item.instagram}" target="_blank" title="Instagram"><i class="fa-brands fa-instagram"></i></a>`;
            if (item.linkedin) socialsHTML += `<a href="${item.linkedin}" target="_blank" title="LinkedIn"><i class="fa-brands fa-linkedin"></i></a>`;
            if (item.twitter) socialsHTML += `<a href="${item.twitter}" target="_blank" title="Twitter/X"><i class="fa-brands fa-x-twitter"></i></a>`;
            if (!socialsHTML) socialsHTML = '<span class="text-muted">-</span>';
            
            row.innerHTML = `
                <td><strong>${item.name}</strong></td>
                <td>${item.phone || '<span class="text-muted">-</span>'}</td>
                <td>${websiteCell}</td>
                <td>${emailsCell}</td>
                <td>${item.owner_name || '<span class="text-muted">Unknown</span>'}</td>
                <td><i class="fa-solid fa-star" style="color: var(--color-gold);"></i> ${item.rating || 'N/A'} <span class="text-muted">(${item.reviews_count || '0'})</span></td>
                <td><div class="social-links">${socialsHTML}</div></td>
                <td><span class="text-muted" title="${item.address}">${item.address ? (item.address.length > 30 ? item.address.slice(0, 30) + '...' : item.address) : '-'}</span></td>
            `;
            leadsTbody.appendChild(row);
        }
        else if (payload.type === 'done') {
            // Processing done
            addLog(payload.message, 'success');
            statusBadge.textContent = 'Done';
            statusBadge.className = 'badge done';
            closeSSE();
            downloadBtn.disabled = false;
        }
        else if (payload.type === 'error') {
            // Error occurred
            addLog(payload.message, 'error');
            statusBadge.textContent = 'Error';
            statusBadge.className = 'badge error';
            closeSSE();
        }
    };

    eventSource.onerror = (err) => {
        addLog("EventSource connection lost or error occurred.", "error");
        statusBadge.textContent = 'Error';
        statusBadge.className = 'badge error';
        closeSSE();
    };
});

// Close connection helper
function closeSSE() {
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
    startBtn.disabled = false;
    stopBtn.disabled = true;
}

// Handle Scrape Stop manually
stopBtn.addEventListener('click', () => {
    addLog("Scraping session cancelled by user.", "system");
    statusBadge.textContent = 'Idle';
    statusBadge.className = 'badge idle';
    closeSSE();
});

// Clear Logs
clearLogsBtn.addEventListener('click', () => {
    consoleLogs.innerHTML = '';
    addLog("Logs cleared.", "system");
});

// Handle CSV Download
downloadBtn.addEventListener('click', () => {
    // Navigate to download route which returns the CSV file attachment
    window.location.href = '/api/download';
});
