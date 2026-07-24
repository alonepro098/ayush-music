/* ==========================================================================
   CARD SUITE INTERACTION & LOGIC
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
    initTabNavigation();
    initCardGenerator();
    initBinLookup();
    initAddressGenerator();
    fetchUserId();
});

// Toast notifications system
function showToast(message, isSuccess = true) {
    const toast = document.getElementById('toast');
    const icon = toast.querySelector('.toast-icon');
    const msgSpan = toast.querySelector('.toast-message');
    
    msgSpan.textContent = message;
    if (isSuccess) {
        icon.className = 'fa-solid fa-circle-check toast-icon';
        toast.style.borderLeft = '4px solid var(--accent-green)';
        icon.style.color = 'var(--accent-green)';
    } else {
        icon.className = 'fa-solid fa-circle-exclamation toast-icon';
        toast.style.borderLeft = '4px solid var(--accent-red)';
        icon.style.color = 'var(--accent-red)';
    }
    
    toast.classList.remove('hidden');
    toast.classList.add('visible');
    
    // Auto hide after 3 seconds
    setTimeout(() => {
        toast.classList.remove('visible');
        setTimeout(() => toast.classList.add('hidden'), 300);
    }, 3000);
}

// Fetch user info just to keep the header aligned with existing app profile
function fetchUserId() {
    const userIdDisplay = document.getElementById('userIdDisplay');
    // Read user_id from localStorage if exists
    let userId = localStorage.getItem('aadhaar_portal_uid');
    if (userId) {
        userIdDisplay.querySelector('.value').textContent = userId;
    } else {
        // Fallback to calling user info
        fetch('/api/user/info')
            .then(res => res.json())
            .then(data => {
                if (data.user_id) {
                    localStorage.setItem('aadhaar_portal_uid', data.user_id);
                    userIdDisplay.querySelector('.value').textContent = data.user_id;
                }
            })
            .catch(() => {
                userIdDisplay.querySelector('.value').textContent = 'GUEST';
            });
    }
}

// Copy ID on click
document.getElementById('userIdDisplay').addEventListener('click', () => {
    const userId = document.getElementById('userIdDisplay').querySelector('.value').textContent;
    if (userId && userId !== 'Loading...' && userId !== 'GUEST') {
        navigator.clipboard.writeText(userId)
            .then(() => showToast('User ID copied to clipboard!'))
            .catch(() => showToast('Failed to copy', false));
    }
});

/* ==========================================================================
   TAB NAVIGATION SYSTEM
   ========================================================================== */
function initTabNavigation() {
    const navButtons = document.querySelectorAll('.suite-nav-btn[data-tab]');
    const tabPanels = document.querySelectorAll('.suite-tab-panel');

    navButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.getAttribute('data-tab');
            
            // Remove active classes
            navButtons.forEach(b => b.classList.remove('active'));
            tabPanels.forEach(p => p.classList.remove('active'));
            
            // Add active class to current button & panel
            btn.classList.add('active');
            const panel = document.getElementById(`tab-${targetTab}`);
            if (panel) panel.classList.add('active');
        });
    });
}

/* ==========================================================================
   CARD GENERATOR TOOL
   ========================================================================== */
function initCardGenerator() {
    const genBinInput = document.getElementById('genBin');
    const genMonthSelect = document.getElementById('genMonth');
    const genYearSelect = document.getElementById('genYear');
    const genCvvInput = document.getElementById('genCvv');
    const genQtySelect = document.getElementById('genQty');
    const genFormatSelect = document.getElementById('genFormat');
    const btnGenerate = document.getElementById('btnGenerateCards');
    const outputTextarea = document.getElementById('genOutputText');
    const btnCopy = document.getElementById('btnCopyCards');
    const btnDownload = document.getElementById('btnDownloadCards');

    // Auto replace spaces and non-supported characters in input BIN
    genBinInput.addEventListener('input', (e) => {
        e.target.value = e.target.value.replace(/[^0-9xX]/g, '');
    });

    // Auto replace CVV
    genCvvInput.addEventListener('input', (e) => {
        e.target.value = e.target.value.replace(/\D/g, '');
    });

    btnGenerate.addEventListener('click', () => {
        const binVal = genBinInput.value.trim();
        if (!binVal || binVal.length < 6) {
            showToast('Please enter a valid BIN of at least 6 digits.', false);
            return;
        }

        const qty = parseInt(genQtySelect.value, 10);
        const format = genFormatSelect.value;
        const targetMonth = genMonthSelect.value;
        const targetYear = genYearSelect.value;
        const targetCvv = genCvvInput.value.trim();

        btnGenerate.disabled = true;
        btnGenerate.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Generating...';

        setTimeout(() => {
            try {
                const generatedCards = [];
                for (let i = 0; i < qty; i++) {
                    const cardNum = generateCardNumber(binVal);
                    const month = targetMonth === 'random' ? randomMonth() : targetMonth;
                    const year = targetYear === 'random' ? randomYear() : targetYear;
                    const cvv = targetCvv === '' ? randomCvv(cardNum) : targetCvv;
                    generatedCards.push({ cardNum, month, year, cvv });
                }

                // Format the output
                let outputStr = '';
                if (format === 'pipe') {
                    outputStr = generatedCards.map(c => `${c.cardNum}|${c.month}|${c.year}|${c.cvv}`).join('\n');
                } else if (format === 'csv') {
                    outputStr = 'Card Number,Expiry Month,Expiry Year,CVV\n' + 
                                generatedCards.map(c => `"${c.cardNum}","${c.month}","${c.year}","${c.cvv}"`).join('\n');
                } else if (format === 'json') {
                    outputStr = JSON.stringify(generatedCards, null, 2);
                }

                outputTextarea.value = outputStr;
                showToast(`Successfully generated ${qty} test cards!`);
            } catch (err) {
                console.error(err);
                showToast('Error generating cards.', false);
            } finally {
                btnGenerate.disabled = false;
                btnGenerate.innerHTML = '<i class="fa-solid fa-gear"></i> Generate Cards';
            }
        }, 300);
    });

    // Copy Action
    btnCopy.addEventListener('click', () => {
        const content = outputTextarea.value.trim();
        if (!content) {
            showToast('No cards to copy.', false);
            return;
        }
        navigator.clipboard.writeText(content)
            .then(() => showToast('Cards copied to clipboard!'))
            .catch(() => showToast('Failed to copy cards.', false));
    });

    // Download Action
    btnDownload.addEventListener('click', () => {
        const content = outputTextarea.value.trim();
        if (!content) {
            showToast('No cards to download.', false);
            return;
        }

        const format = genFormatSelect.value;
        let mime = 'text/plain';
        let filename = 'generated_cards.txt';

        if (format === 'csv') {
            mime = 'text/csv';
            filename = 'generated_cards.csv';
        } else if (format === 'json') {
            mime = 'application/json';
            filename = 'generated_cards.json';
        }

        const blob = new Blob([content], { type: mime });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        link.click();
        URL.revokeObjectURL(link.href);
        showToast('Download started!');
    });
}

// Luhn Card Generation Logic
function generateCardNumber(binInput) {
    let cleanedBin = "";
    for (let char of binInput) {
        if (/\d/.test(char)) {
            cleanedBin += char;
        } else if (char.toLowerCase() === 'x') {
            cleanedBin += Math.floor(Math.random() * 10);
        }
    }

    // Determine length
    let length = 16;
    if (cleanedBin.startsWith('34') || cleanedBin.startsWith('37')) {
        length = 15; // Amex
    } else if (cleanedBin.startsWith('300') || cleanedBin.startsWith('301') || cleanedBin.startsWith('302') || cleanedBin.startsWith('303') || cleanedBin.startsWith('304') || cleanedBin.startsWith('305') || cleanedBin.startsWith('36') || cleanedBin.startsWith('38')) {
        length = 14; // Diners
    }

    let ccNumber = cleanedBin;
    while (ccNumber.length < length - 1) {
        ccNumber += Math.floor(Math.random() * 10);
    }

    // Luhn calculation
    let sum = 0;
    let shouldDouble = true;
    
    for (let i = ccNumber.length - 1; i >= 0; i--) {
        let digit = parseInt(ccNumber.charAt(i), 10);
        
        if (shouldDouble) {
            digit *= 2;
            if (digit > 9) digit -= 9;
        }
        
        sum += digit;
        shouldDouble = !shouldDouble;
    }
    
    let checkDigit = (10 - (sum % 10)) % 10;
    ccNumber += checkDigit;
    
    return ccNumber;
}

function randomMonth() {
    const m = Math.floor(Math.random() * 12) + 1;
    return m < 10 ? '0' + m : '' + m;
}

function randomYear() {
    const currentYear = new Date().getFullYear();
    return '' + (currentYear + Math.floor(Math.random() * 8) + 1); // 1-8 years in future
}

function randomCvv(cardNum) {
    const length = (cardNum.startsWith('34') || cardNum.startsWith('37')) ? 4 : 3;
    let cvv = '';
    for (let i = 0; i < length; i++) {
        cvv += Math.floor(Math.random() * 10);
    }
    return cvv;
}

/* ==========================================================================
   BIN LOOKUP TOOL
   ========================================================================== */
function initBinLookup() {
    const lookupInput = document.getElementById('lookupBinInput');
    const btnLookup = document.getElementById('btnLookupBin');
    const binPlaceholder = document.getElementById('binPlaceholder');
    const binItems = document.querySelectorAll('.bin-data-item[data-field]');
    
    // Virtual Card elements
    const previewCard = document.getElementById('previewCard');
    const cardBank = document.getElementById('previewCardBank');
    const cardBrand = document.getElementById('previewCardBrand');
    const cardNumber = document.getElementById('previewCardNumber');
    const cardCountry = document.getElementById('previewCardCountry');
    const countryName = document.getElementById('previewCountryName');

    // Clean lookup input on type
    lookupInput.addEventListener('input', (e) => {
        e.target.value = e.target.value.replace(/\D/g, '');
    });

    btnLookup.addEventListener('click', () => {
        const binVal = lookupInput.value.trim();
        if (binVal.length < 6) {
            showToast('BIN must be at least 6 digits.', false);
            return;
        }

        btnLookup.disabled = true;
        btnLookup.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Fetching...';
        
        // Reset card elements style
        previewCard.className = 'virtual-card';
        cardBank.textContent = 'FETCHING BANK...';
        cardNumber.textContent = binVal.padEnd(8, 'x').slice(0, 4) + ' ' + binVal.padEnd(8, 'x').slice(4, 8) + 'xx xxxx xxxx';

        fetch(`/api/tools/bin-lookup?bin=${binVal}`)
            .then(res => {
                if (!res.ok) throw new Error('BIN not found or server error');
                return res.json();
            })
            .then(resData => {
                if (resData.success && resData.data) {
                    const data = resData.data;
                    
                    // 1. Hide Placeholder
                    binPlaceholder.classList.add('hidden');
                    
                    // 2. Map visual card scheme class
                    const scheme = (data.Scheme || '').toLowerCase();
                    if (scheme.includes('visa')) {
                        previewCard.classList.add('visa');
                        cardBrand.innerHTML = '<i class="fa-brands fa-cc-visa"></i>';
                    } else if (scheme.includes('mastercard')) {
                        previewCard.classList.add('mastercard');
                        cardBrand.innerHTML = '<i class="fa-brands fa-cc-mastercard"></i>';
                    } else if (scheme.includes('amex') || scheme.includes('american express')) {
                        previewCard.classList.add('amex');
                        cardBrand.innerHTML = '<i class="fa-brands fa-cc-amex"></i>';
                    } else {
                        cardBrand.innerHTML = '<i class="fa-solid fa-credit-card"></i>';
                    }

                    // 3. Fill card face details
                    cardBank.textContent = data.Issuer || 'UNKNOWN BANK';
                    const countryInfo = data.Country || {};
                    const flagEmoji = getFlagEmoji(countryInfo.A2);
                    countryName.textContent = countryInfo.Name || 'Unknown Country';
                    cardCountry.querySelector('span:first-child').textContent = flagEmoji;

                    // 4. Fill detailed database list
                    document.getElementById('binValScheme').textContent = data.Scheme || 'N/A';
                    document.getElementById('binValType').textContent = data.Type || 'N/A';
                    document.getElementById('binValTier').textContent = data.CardTier || 'N/A';
                    document.getElementById('binValLuhn').textContent = data.Luhn ? 'Yes (Passes)' : 'No (Fails)';
                    document.getElementById('binValIssuer').textContent = data.Issuer || 'N/A';
                    document.getElementById('binValCountry').textContent = `${countryInfo.Name || 'N/A'} (${countryInfo.A2 || 'N/A'})`;

                    // Show stats divs
                    binItems.forEach(item => item.classList.remove('hidden'));
                    showToast('BIN specifications loaded successfully!');
                } else {
                    throw new Error(resData.message || 'BIN lookup failed');
                }
            })
            .catch(err => {
                console.error(err);
                cardBank.textContent = 'LOOKUP FAILED';
                showToast(err.message || 'BIN details not found.', false);
            })
            .finally(() => {
                btnLookup.disabled = false;
                btnLookup.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Search BIN Info';
            });
    });
}

// Country code ISO to Flag Emoji mapper
function getFlagEmoji(countryCode) {
    if (!countryCode || countryCode.length !== 2) return '🌎';
    const codePoints = countryCode
        .toUpperCase()
        .split('')
        .map(char => 127397 + char.charCodeAt(0));
    return String.fromCodePoint(...codePoints);
}

/* ==========================================================================
   FAKE ADDRESS GENERATOR TOOL
   ========================================================================== */
function initAddressGenerator() {
    const countrySelect = document.getElementById('addressCountry');
    const qtySelect = document.getElementById('addressQty');
    const btnGenerate = document.getElementById('btnGenerateAddress');
    const resultsContainer = document.getElementById('addressesResultContainer');
    const btnCopyAll = document.getElementById('btnCopyAllAddresses');
    let generatedAddressesList = [];

    btnGenerate.addEventListener('click', () => {
        const country = countrySelect.value;
        const qty = qtySelect.value;

        btnGenerate.disabled = true;
        btnGenerate.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Generating...';

        fetch(`/api/tools/fake-address?country=${country}&qty=${qty}`)
            .then(res => {
                if (!res.ok) throw new Error('Server error generating addresses');
                return res.json();
            })
            .then(data => {
                if (data.success && data.addresses) {
                    generatedAddressesList = data.addresses;
                    resultsContainer.innerHTML = ''; // clear
                    
                    data.addresses.forEach(addr => {
                        resultsContainer.appendChild(createAddressCardElement(addr));
                    });

                    // Show copy all button
                    btnCopyAll.classList.remove('hidden');
                    showToast(`Successfully generated ${qty} addresses!`);
                } else {
                    throw new Error(data.message || 'Failed to generate');
                }
            })
            .catch(err => {
                console.error(err);
                showToast(err.message || 'Error fetching fake addresses.', false);
            })
            .finally(() => {
                btnGenerate.disabled = false;
                btnGenerate.innerHTML = '<i class="fa-solid fa-map-pin"></i> Generate Addresses';
            });
    });

    // Copy all addresses combined
    btnCopyAll.addEventListener('click', () => {
        if (generatedAddressesList.length === 0) return;
        
        let copyBlock = '';
        generatedAddressesList.forEach((addr, idx) => {
            copyBlock += `Address #${idx + 1}\n`;
            copyBlock += `Name: ${addr.name}\n`;
            copyBlock += `Gender: ${addr.gender}\n`;
            copyBlock += `Street: ${addr.street}\n`;
            copyBlock += `City: ${addr.city}\n`;
            copyBlock += `State: ${addr.state}\n`;
            copyBlock += `ZIP: ${addr.postcode}\n`;
            copyBlock += `Country: ${addr.country_name}\n`;
            copyBlock += `Phone: ${addr.phone}\n`;
            copyBlock += `Email: ${addr.email}\n`;
            copyBlock += `-------------------------\n\n`;
        });

        navigator.clipboard.writeText(copyBlock.trim())
            .then(() => showToast('All addresses copied!'))
            .catch(() => showToast('Copy failed.', false));
    });
}

function createAddressCardElement(addr) {
    const card = document.createElement('div');
    card.className = 'address-card';

    const genderClass = addr.gender.toLowerCase() === 'female' ? 'female' : '';
    
    card.innerHTML = `
        <div class="address-card-header">
            <span class="address-card-name">
                <i class="fa-solid fa-user-circle"></i> ${addr.name}
            </span>
            <span class="address-gender-tag ${genderClass}">${addr.gender}</span>
        </div>
        <div class="address-card-body">
            <div class="address-detail-item">
                <span class="address-detail-label">Street</span>
                <span class="address-detail-val">
                    <span>${addr.street}</span>
                    <button class="copy-field-btn" data-val="${addr.street}" title="Copy street"><i class="fa-solid fa-copy"></i></button>
                </span>
            </div>
            <div class="address-detail-item">
                <span class="address-detail-label">City</span>
                <span class="address-detail-val">
                    <span>${addr.city}</span>
                    <button class="copy-field-btn" data-val="${addr.city}" title="Copy city"><i class="fa-solid fa-copy"></i></button>
                </span>
            </div>
            <div class="address-detail-item">
                <span class="address-detail-label">State / Province</span>
                <span class="address-detail-val">
                    <span>${addr.state}</span>
                    <button class="copy-field-btn" data-val="${addr.state}" title="Copy state"><i class="fa-solid fa-copy"></i></button>
                </span>
            </div>
            <div class="address-detail-item">
                <span class="address-detail-label">ZIP / Postcode</span>
                <span class="address-detail-val">
                    <span>${addr.postcode}</span>
                    <button class="copy-field-btn" data-val="${addr.postcode}" title="Copy postcode"><i class="fa-solid fa-copy"></i></button>
                </span>
            </div>
            <div class="address-detail-item">
                <span class="address-detail-label">Phone</span>
                <span class="address-detail-val">
                    <span>${addr.phone}</span>
                    <button class="copy-field-btn" data-val="${addr.phone}" title="Copy phone"><i class="fa-solid fa-copy"></i></button>
                </span>
            </div>
            <div class="address-detail-item">
                <span class="address-detail-label">Email</span>
                <span class="address-detail-val">
                    <span>${addr.email}</span>
                    <button class="copy-field-btn" data-val="${addr.email}" title="Copy email"><i class="fa-solid fa-copy"></i></button>
                </span>
            </div>
        </div>
    `;

    // Add copy listener to individual fields
    card.querySelectorAll('.copy-field-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const val = btn.getAttribute('data-val');
            navigator.clipboard.writeText(val)
                .then(() => showToast(`Copied: "${val.length > 20 ? val.slice(0,17)+'...' : val}"`))
                .catch(() => showToast('Failed to copy', false));
        });
    });

    return card;
}
