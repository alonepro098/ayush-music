document.addEventListener('DOMContentLoaded', () => {
    // ============== STATE VARIABLES ==============
    let currentMethod = 'mobile'; // 'mobile', 'aadhaar', or 'eid'
    let userId = '';
    let referralLink = '';
    
    // Captcha & Transaction state
    let captchaTxnId = '';
    let transactionId = '';
    let otpTxnId = '';
    
    // Data collected during the steps
    let mobileNum = '';
    let userName = 'MR';
    let documentId = ''; // Holds Aadhaar or EID or retrieved EID
    
    // Sub-stage tracking for Mobile Flow
    // Mobile flow has two stages: 'retrieve_eid' (Step 1-3) and 'download_pdf' (Step 4-6)
    let mobileFlowStage = 'retrieve_eid'; 

    // ============== DOM ELEMENTS ==============
    const userIdDisplay = document.querySelector('#userIdDisplay .value');
    const userCreditsDisplay = document.getElementById('userCreditsDisplay');
    const referralLinkInput = document.getElementById('referralLinkInput');
    const referralCount = document.getElementById('referralCount');
    const referralCreditsEarned = document.getElementById('referralCreditsEarned');
    
    const methodBtns = document.querySelectorAll('.method-btn');
    const telegramGate = document.getElementById('telegramGate');
    const wizardContainer = document.getElementById('wizardContainer');
    
    // Step Cards
    const inputFormCard = document.getElementById('inputFormCard');
    const captchaFormCard = document.getElementById('captchaFormCard');
    const otpFormCard = document.getElementById('otpFormCard');
    const resultFormCard = document.getElementById('resultFormCard');
    
    // Inputs & Fields
    const formTitle = document.getElementById('formTitle');
    const primaryInputLabel = document.getElementById('primaryInputLabel');
    const primaryInputIcon = document.getElementById('primaryInputIcon');
    const primaryInput = document.getElementById('primaryInput');
    const nameInputWrapper = document.getElementById('nameInputWrapper');
    const nameInput = document.getElementById('nameInput');
    
    const captchaImage = document.getElementById('captchaImage');
    const captchaInput = document.getElementById('captchaInput');
    const otpInput = document.getElementById('otpInput');
    const otpTargetMessage = document.getElementById('otpTargetMessage');
    
    // Results DOM
    const resultName = document.getElementById('resultName');
    const resultStatus = document.getElementById('resultStatus');
    const resultPassword = document.getElementById('resultPassword');
    const passwordResultRow = document.getElementById('passwordResultRow');
    const manualPassRow = document.getElementById('manualPassRow');
    const downloadPdfBtn = document.getElementById('downloadPdfBtn');
    
    // Overlays
    const loadingOverlay = document.getElementById('loadingOverlay');
    const loadingMessage = document.getElementById('loadingMessage');
    
    // Triggers & Actions
    const submitFormBtn = document.getElementById('submitFormBtn');
    const submitCaptchaBtn = document.getElementById('submitCaptchaBtn');
    const refreshCaptchaBtn = document.getElementById('refreshCaptchaBtn');
    const submitOtpBtn = document.getElementById('submitOtpBtn');
    
    const backToInputBtn = document.getElementById('backToInputBtn');
    const backToCaptchaBtn = document.getElementById('backToCaptchaBtn');
    const restartFlowBtn = document.getElementById('restartFlowBtn');
    
    // Modals
    const adminPanelBtn = document.getElementById('adminPanelBtn');
    const adminModal = document.getElementById('adminModal');
    const closeAdminModalBtn = document.getElementById('closeAdminModalBtn');
    const authenticateAdminBtn = document.getElementById('authenticateAdminBtn');
    const adminKeyInput = document.getElementById('adminKeyInput');
    const adminAuthSection = document.getElementById('adminAuthSection');
    const adminMainSection = document.getElementById('adminMainSection');
    
    const paymentModal = document.getElementById('paymentModal');
    const closePaymentModalBtn = document.getElementById('closePaymentModalBtn');
    const selectedPlanDisplay = document.getElementById('selectedPlanDisplay');
    const selectedPlanPrice = document.getElementById('selectedPlanPrice');
    
    const loginBtn = document.getElementById('loginBtn');
    const telegramVerificationModal = document.getElementById('telegramVerificationModal');
    const closeTelegramModalBtn = document.getElementById('closeTelegramModalBtn');
    const verifyTelegramJoinBtn = document.getElementById('verifyTelegramJoinBtn');
    const telegramIdInput = document.getElementById('telegramIdInput');
    const executeTelegramVerifyBtn = document.getElementById('executeTelegramVerifyBtn');
    
    // TOAST
    const toast = document.getElementById('toast');
    const toastMessage = toast.querySelector('.toast-message');

    // ============== TOAST HELPERS ==============
    function showToast(message, type = 'info') {
        toastMessage.textContent = message;
        const icon = toast.querySelector('.toast-icon');
        
        if (type === 'success') {
            icon.className = 'fa-solid fa-circle-check toast-icon success-text';
            toast.style.borderColor = 'var(--accent-green)';
            toast.style.boxShadow = '0 4px 20px rgba(16, 185, 129, 0.25)';
        } else if (type === 'error') {
            icon.className = 'fa-solid fa-triangle-exclamation toast-icon text-gradient-red';
            toast.style.borderColor = 'var(--accent-red)';
            toast.style.boxShadow = '0 4px 20px rgba(239, 68, 68, 0.25)';
        } else {
            icon.className = 'fa-solid fa-circle-info toast-icon';
            toast.style.borderColor = 'var(--accent-blue)';
            toast.style.boxShadow = '0 4px 20px rgba(59, 130, 246, 0.25)';
        }
        
        toast.classList.remove('hidden');
        setTimeout(() => {
            toast.classList.add('hidden');
        }, 4000);
    }

    // ============== LOADER OVERLAY HELPERS ==============
    function showLoader(message) {
        loadingMessage.textContent = message;
        loadingOverlay.classList.remove('hidden');
    }
    
    function hideLoader() {
        loadingOverlay.classList.add('hidden');
    }

    function handleTelegramRequired() {
        hideLoader();
        telegramGate.classList.remove('hidden');
        telegramVerificationModal.classList.remove('hidden');
        localStorage.setItem('tg_verified', 'false');
        showToast("Join our Telegram channel @UR_IMAGE to continue using the service!", "error");
    }

    // ============== USER PROFILE & INITIALIZATION ==============
    function initUser() {
        // Find existing User ID in local storage
        let id = localStorage.getItem('aadhaar_portal_uid');
        if (!id) {
            id = `AD-${Math.floor(100000 + Math.random() * 900000)}`;
            localStorage.setItem('aadhaar_portal_uid', id);
        }
        userId = id;
        
        // Find ref parameter in URL
        const urlParams = new URLSearchParams(window.location.search);
        const ref = urlParams.get('ref');
        
        // Fetch stats from backend
        let fetchUrl = `/api/user/info?user_id=${userId}`;
        if (ref) {
            fetchUrl += `&ref=${ref}`;
        }
        
        fetch(fetchUrl)
            .then(res => res.json())
            .then(data => {
                userIdDisplay.textContent = data.user_id;
                userCreditsDisplay.textContent = data.credits;
                referralCount.textContent = data.referral_count;
                referralCreditsEarned.textContent = data.referral_count;
                
                // Build referral link
                const base = window.location.origin;
                referralLink = `${base}/?ref=${data.user_id}`;
                referralLinkInput.value = referralLink;
                
                // Check telegram membership
                if (data.tg_verified || data.lifetime) {
                    telegramGate.classList.add('hidden');
                    localStorage.setItem('tg_verified', 'true');
                } else {
                    telegramGate.classList.remove('hidden');
                    localStorage.setItem('tg_verified', 'false');
                }
            })
            .catch(err => {
                console.error("User profile load error:", err);
                showToast("Failed to initialize user session", "error");
            });
            
        // Setup User ID copy trigger
        document.getElementById('userIdDisplay').addEventListener('click', () => {
            navigator.clipboard.writeText(userId);
            showToast("User ID copied to clipboard!", "success");
        });
        
        // Setup Referral Link copy trigger
        document.getElementById('copyRefBtn').addEventListener('click', () => {
            navigator.clipboard.writeText(referralLink);
            showToast("Referral link copied to clipboard!", "success");
        });
    }

    // ============== METHOD TAB HANDLERS ==============
    methodBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            methodBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            const method = btn.dataset.method;
            currentMethod = method;
            resetFlow();
            updateFormLayout();
        });
    });

    function updateFormLayout() {
        if (currentMethod === 'mobile') {
            formTitle.textContent = "Mobile Verification";
            primaryInputLabel.textContent = "Mobile Number";
            primaryInputIcon.className = "fa-solid fa-phone";
            primaryInput.placeholder = "Enter 10-digit number";
            primaryInput.value = "";
            nameInputWrapper.classList.remove('hidden');
            nameInput.value = "";
            inputFormCard.querySelector('.step-badge').textContent = "Step 1 of 3";
            mobileFlowStage = 'retrieve_eid';
        } else if (currentMethod === 'aadhaar') {
            formTitle.textContent = "Direct Aadhaar Download";
            primaryInputLabel.textContent = "Aadhaar Number";
            primaryInputIcon.className = "fa-solid fa-id-card";
            primaryInput.placeholder = "Enter 12-digit Aadhaar";
            primaryInput.value = "";
            nameInputWrapper.classList.remove('hidden');
            nameInput.value = "";
            inputFormCard.querySelector('.step-badge').textContent = "Step 1 of 3";
        } else if (currentMethod === 'eid') {
            formTitle.textContent = "Enrollment ID Download";
            primaryInputLabel.textContent = "Enrollment ID (EID)";
            primaryInputIcon.className = "fa-solid fa-folder-open";
            primaryInput.placeholder = "Enter 14 or 28-digit EID";
            primaryInput.value = "";
            nameInputWrapper.classList.remove('hidden');
            nameInput.value = "";
            inputFormCard.querySelector('.step-badge').textContent = "Step 1 of 3";
        }
    }

    function resetFlow() {
        // Reset state
        captchaTxnId = '';
        transactionId = '';
        otpTxnId = '';
        mobileNum = '';
        userName = 'MR';
        documentId = '';
        mobileFlowStage = 'retrieve_eid';
        
        // Hide/Show step panels
        inputFormCard.classList.remove('hidden');
        captchaFormCard.classList.add('hidden');
        otpFormCard.classList.add('hidden');
        resultFormCard.classList.add('hidden');
        
        captchaInput.value = '';
        otpInput.value = '';
    }

    // ============== CAPTCHA UTILITIES ==============
    function loadCaptcha(callback) {
        showLoader("Connecting to UIDAI gateway...");
        fetch(`/api/captcha/get?user_id=${userId}`)
            .then(res => res.json())
            .then(data => {
                hideLoader();
                if (data.telegram_required) {
                    handleTelegramRequired();
                    return;
                }
                if (data.success) {
                    captchaImage.src = data.image;
                    captchaTxnId = data.captcha_txn_id;
                    transactionId = data.transaction_id;
                    captchaInput.value = '';
                    if (callback) callback();
                } else {
                    showToast(data.message, "error");
                }
            })
            .catch(err => {
                hideLoader();
                showToast("Failed to fetch captcha from server", "error");
            });
    }

    refreshCaptchaBtn.addEventListener('click', () => {
        loadCaptcha();
    });

    // ============== FLOW CONTROLLERS (STEP TRANSITIONS) ==============
    
    // STEP 1 -> STEP 2 (Details Submission)
    submitFormBtn.addEventListener('click', () => {
        const val = primaryInput.value.trim().replace(/\s/g, '');
        const nameVal = nameInput.value.trim();
        
        if (currentMethod === 'mobile') {
            if (!/^\d{10}$/.test(val)) {
                showToast("Please enter a valid 10-digit mobile number", "error");
                return;
            }
            mobileNum = val;
            userName = nameVal || 'MR';
        } else if (currentMethod === 'aadhaar') {
            if (!/^\d{12}$/.test(val)) {
                showToast("Please enter a valid 12-digit Aadhaar number", "error");
                return;
            }
            documentId = val;
            userName = nameVal || 'MR';
        } else if (currentMethod === 'eid') {
            if (val.length < 10) {
                showToast("Please enter a valid Enrollment ID (EID)", "error");
                return;
            }
            documentId = val;
            userName = nameVal || 'MR';
        }
        
        // Load captcha and shift to step 2
        loadCaptcha(() => {
            inputFormCard.classList.add('hidden');
            
            // Adjust step badge texts dynamically
            if (currentMethod === 'mobile' && mobileFlowStage === 'retrieve_eid') {
                captchaFormCard.querySelector('h3').textContent = "Step 2: Security Captcha";
                captchaFormCard.querySelector('.step-badge').textContent = "Step 2 of 4";
            } else {
                captchaFormCard.querySelector('h3').textContent = "Step 2: Security Captcha";
                captchaFormCard.querySelector('.step-badge').textContent = "Step 2 of 3";
            }
            
            captchaFormCard.classList.remove('hidden');
        });
    });

    // STEP 2 -> STEP 3 (Captcha Verification & Send OTP)
    submitCaptchaBtn.addEventListener('click', () => {
        const code = captchaInput.value.trim();
        if (code.length < 3) {
            showToast("Please enter the security captcha code", "error");
            return;
        }

        showLoader("Verifying captcha and sending OTP...");
        
        if (currentMethod === 'mobile' && mobileFlowStage === 'retrieve_eid') {
            // Mobile retrieve EID API call
            fetch('/api/flow/mobile/send-otp', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: userId,
                    mobile: mobileNum,
                    name: userName,
                    captcha: code,
                    captcha_txn_id: captchaTxnId,
                    transaction_id: transactionId
                })
            })
            .then(res => res.json())
            .then(data => {
                hideLoader();
                if (data.telegram_required) {
                    handleTelegramRequired();
                    return;
                }
                if (data.success) {
                    otpTxnId = data.otp_txn_id;
                    otpTargetMessage.textContent = `UIDAI has sent a 6-digit EID retrieval OTP to mobile number: +91 ******${mobileNum.slice(-4)}`;
                    captchaFormCard.classList.add('hidden');
                    
                    otpFormCard.querySelector('.step-badge').textContent = "Step 3 of 4";
                    otpFormCard.classList.remove('hidden');
                } else {
                    showToast(data.message || "Failed to send OTP", "error");
                    // Reload captcha to allow retry
                    loadCaptcha();
                }
            })
            .catch(err => {
                hideLoader();
                showToast("Request failed", "error");
            });
            
        } else {
            // Direct PDF Download OTP call (Aadhaar, EID, or Stage 2 of Mobile Flow)
            const targetEID = (currentMethod === 'mobile') ? documentId : documentId;
            
            fetch('/api/flow/pdf/send-otp', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: userId,
                    eid: targetEID,
                    captcha: code,
                    captcha_txn_id: captchaTxnId,
                    transaction_id: transactionId
                })
            })
            .then(res => res.json())
            .then(data => {
                hideLoader();
                if (data.telegram_required) {
                    handleTelegramRequired();
                    return;
                }
                if (data.success) {
                    otpTxnId = data.otp_txn_id;
                    otpTargetMessage.textContent = "Enter the 6-digit e-Aadhaar PDF download OTP sent to your linked mobile number.";
                    captchaFormCard.classList.add('hidden');
                    
                    if (currentMethod === 'mobile') {
                        otpFormCard.querySelector('.step-badge').textContent = "Step 4 of 4";
                    } else {
                        otpFormCard.querySelector('.step-badge').textContent = "Step 3 of 3";
                    }
                    
                    otpFormCard.classList.remove('hidden');
                } else {
                    showToast(data.message || "Failed to send OTP", "error");
                    loadCaptcha();
                }
            })
            .catch(err => {
                hideLoader();
                showToast("Request failed", "error");
            });
        }
    });

    // STEP 3 -> RESULT OR STAGE 2 OF MOBILE FLOW (OTP Verification)
    submitOtpBtn.addEventListener('click', () => {
        const otpVal = otpInput.value.trim();
        if (!/^\d{6}$/.test(otpVal)) {
            showToast("Please enter a valid 6-digit numeric OTP", "error");
            return;
        }

        if (currentMethod === 'mobile' && mobileFlowStage === 'retrieve_eid') {
            // Stage 1 Verification: Mobile Retrieve EID OTP
            showLoader("Verifying EID retrieval OTP...");
            fetch('/api/flow/mobile/verify-otp', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    mobile: mobileNum,
                    name: userName,
                    otp: otpVal,
                    otp_txn_id: otpTxnId,
                    captcha_txn_id: captchaTxnId,
                    captcha: captchaInput.value.trim()
                })
            })
            .then(res => res.json())
            .then(data => {
                hideLoader();
                if (data.success) {
                    documentId = data.eid;
                    userName = data.name || userName;
                    showToast("EID retrieved successfully!", "success");
                    
                    // Transition to Stage 2: PDF OTP Captcha
                    mobileFlowStage = 'download_pdf';
                    otpFormCard.classList.add('hidden');
                    
                    // Load PDF captcha automatically
                    loadCaptcha(() => {
                        captchaFormCard.querySelector('h3').textContent = "Stage 2: PDF Download Captcha";
                        captchaFormCard.querySelector('.step-badge').textContent = "Step 3 of 4";
                        captchaFormCard.classList.remove('hidden');
                    });
                } else {
                    showToast(data.message || "Verification failed", "error");
                }
            })
            .catch(err => {
                hideLoader();
                showToast("Verification request failed", "error");
            });
            
        } else {
            // Direct e-Aadhaar PDF Download Verification
            showLoader("Downloading e-Aadhaar PDF and cracking security...");
            fetch('/api/flow/pdf/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: userId,
                    eid: documentId,
                    otp: otpVal,
                    otp_txn_id: otpTxnId,
                    transaction_id: transactionId,
                    name: userName
                })
            })
            .then(res => res.json())
            .then(data => {
                hideLoader();
                if (data.telegram_required) {
                    handleTelegramRequired();
                    return;
                }
                if (data.success) {
                    showToast("Aadhaar decrypted successfully!", "success");
                    otpFormCard.classList.add('hidden');
                    
                    // Update result card details
                    resultName.textContent = userName.toUpperCase();
                    downloadPdfBtn.href = data.download_url;
                    
                    if (data.unlocked) {
                        resultStatus.className = "val success-text";
                        resultStatus.innerHTML = `<i class="fa-solid fa-lock-open"></i> Decrypted Successfully`;
                        resultPassword.textContent = data.password;
                        passwordResultRow.classList.remove('hidden');
                        manualPassRow.classList.add('hidden');
                    } else {
                        resultStatus.className = "val text-gradient-orange";
                        resultStatus.innerHTML = `<i class="fa-solid fa-lock"></i> Password Protected`;
                        passwordResultRow.classList.add('hidden');
                        manualPassRow.classList.remove('hidden');
                    }
                    
                    resultFormCard.classList.remove('hidden');
                    
                    // Reload credits
                    initUser();
                } else {
                    showToast(data.message || "Download failed", "error");
                }
            })
            .catch(err => {
                hideLoader();
                showToast("Download request failed", "error");
            });
        }
    });

    // BACK NAVIGATION HANDLERS
    backToInputBtn.addEventListener('click', () => {
        captchaFormCard.classList.add('hidden');
        inputFormCard.classList.remove('hidden');
    });

    backToCaptchaBtn.addEventListener('click', () => {
        otpFormCard.classList.add('hidden');
        captchaFormCard.classList.remove('hidden');
    });

    restartFlowBtn.addEventListener('click', () => {
        resetFlow();
    });

    // ============== MODAL DISPLAYS & TRIGGERS ==============
    
    // ADMIN PANEL TRIGGERS
    adminPanelBtn.addEventListener('click', () => {
        adminKeyInput.value = '';
        adminAuthSection.classList.remove('hidden');
        adminMainSection.classList.add('hidden');
        adminModal.classList.remove('hidden');
    });

    closeAdminModalBtn.addEventListener('click', () => {
        adminModal.classList.add('hidden');
    });

    authenticateAdminBtn.addEventListener('click', () => {
        const key = adminKeyInput.value.trim();
        if (!key) {
            showToast("Enter admin passkey", "error");
            return;
        }

        fetch(`/api/admin/stats?admin_key=${key}`)
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    adminAuthSection.classList.add('hidden');
                    adminMainSection.classList.remove('hidden');
                    
                    // Display stats
                    document.getElementById('adminTotalUsers').textContent = data.total_users;
                    document.getElementById('adminLifetimeUsers').textContent = data.lifetime_users;
                    document.getElementById('adminTotalCredits').textContent = data.credits_in_use;
                    
                    // Load Users table
                    loadAdminUsersTable(key);
                } else {
                    showToast("Invalid admin key", "error");
                }
            })
            .catch(err => {
                showToast("Admin check failed", "error");
            });
    });

    function loadAdminUsersTable(key) {
        fetch(`/api/admin/users?admin_key=${key}`)
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    const tbody = document.querySelector('#adminUsersTable tbody');
                    tbody.innerHTML = '';
                    
                    const users = data.users;
                    Object.keys(users).forEach(uid => {
                        const u = users[uid];
                        const tr = document.createElement('tr');
                        
                        const creditsDisplay = u.lifetime ? "Lifetime" : (u.credits === "inf" || u.credits === null ? "Lifetime" : u.credits);
                        const dateDisplay = u.joined ? u.joined.slice(0,10) : '—';
                        
                        tr.innerHTML = `
                            <td><code>${uid}</code></td>
                            <td>${creditsDisplay}</td>
                            <td>${u.referral_count || 0}</td>
                            <td>${dateDisplay}</td>
                        `;
                        tbody.appendChild(tr);
                    });
                }
            });
    }

    // ADMIN ADD CREDITS SUBMISSION
    document.getElementById('adminSendCreditsBtn').addEventListener('click', () => {
        const key = adminKeyInput.value.trim();
        const target = document.getElementById('adminTargetUser').value.trim();
        const amount = document.getElementById('adminCreditAmount').value.trim();
        
        if (!target || amount === '') {
            showToast("Fill in both target user and credit amount", "error");
            return;
        }

        fetch('/api/admin/send-credits', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                admin_key: key,
                target_user_id: target,
                amount: amount
            })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                showToast(data.message, "success");
                // Reload stats
                authenticateAdminBtn.click();
            } else {
                showToast(data.message, "error");
            }
        });
    });

    // PRICING / BUY TRIGGERS
    document.querySelectorAll('.buy-plan-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const planCode = btn.dataset.plan;
            const priceText = btn.previousElementSibling.textContent;
            let labelText = "10 Credits";
            
            if (planCode === '10') labelText = "10 Credits";
            if (planCode === '20') labelText = "20 Credits";
            if (planCode === '50') labelText = "50 Credits";
            if (planCode === '100') labelText = "Lifetime Access";
            
            selectedPlanDisplay.textContent = labelText;
            selectedPlanPrice.textContent = priceText;
            document.querySelectorAll('.userIdToPay').forEach(el => el.textContent = userId);
            
            paymentModal.classList.remove('hidden');
        });
    });

    closePaymentModalBtn.addEventListener('click', () => {
        paymentModal.classList.add('hidden');
    });

    // TELEGRAM MODAL ACTIONS
    if (loginBtn) {
        loginBtn.addEventListener('click', () => {
            telegramIdInput.value = '';
            telegramVerificationModal.classList.remove('hidden');
        });
    }

    verifyTelegramJoinBtn.addEventListener('click', () => {
        telegramIdInput.value = '';
        telegramVerificationModal.classList.remove('hidden');
    });

    closeTelegramModalBtn.addEventListener('click', () => {
        telegramVerificationModal.classList.add('hidden');
    });

    executeTelegramVerifyBtn.addEventListener('click', () => {
        const tgId = telegramIdInput.value.trim();
        if (!tgId) {
            showToast("Please enter your Telegram Numeric ID", "error");
            return;
        }

        showLoader("Checking Telegram channel membership...");
        fetch('/api/telegram/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, telegram_id: tgId })
        })
        .then(res => res.json())
        .then(data => {
            hideLoader();
            if (data.success) {
                showToast(data.message, "success");
                if (data.user_id) {
                    userId = data.user_id;
                    localStorage.setItem('aadhaar_portal_uid', userId);
                }
                localStorage.setItem('tg_verified', 'true');
                telegramVerificationModal.classList.add('hidden');
                telegramGate.classList.add('hidden');
                initUser();
            } else {
                showToast(data.message || "Failed to verify. Make sure you joined.", "error");
            }
        })
        .catch(err => {
            hideLoader();
            showToast("Verification failed", "error");
        });
    });

    // Global Modal Click-Away
    window.addEventListener('click', (e) => {
        if (e.target === adminModal) adminModal.classList.add('hidden');
        if (e.target === paymentModal) paymentModal.classList.add('hidden');
        if (e.target === telegramVerificationModal) telegramVerificationModal.classList.add('hidden');
    });

    // ============== STARTUP INITIALIZATION ==============
    initUser();
    updateFormLayout();
});
