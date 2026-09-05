document.addEventListener("DOMContentLoaded", () => {

    /* =====================================================
       TAB NAVIGATION
    ===================================================== */

    const navItems = document.querySelectorAll(".nav-item[data-tab]");

    const panels = {
        analyze: document.getElementById("panel-analyze"),
        family: document.getElementById("panel-family"),
        history: document.getElementById("panel-history")
    };

    function activateTab(tab) {

        navItems.forEach(item => {
            item.classList.toggle(
                "is-active",
                item.dataset.tab === tab
            );
        });

        Object.entries(panels).forEach(([key, panel]) => {

            if (!panel) return;

            panel.hidden = key !== tab;
        });

        if (tab === "family") {
            loadFamily();
        }

        if (tab === "history") {
            loadHistory();
        }
    }

    navItems.forEach(item => {

        item.addEventListener("click", () => {
            activateTab(item.dataset.tab);
        });

    });


    /* =====================================================
       ANALYZE FORM
    ===================================================== */

    const form = document.getElementById("analyze-form");
    const button = document.getElementById("analyze-btn");

    const messageInput = document.getElementById("message-input");
    const linkInput = document.getElementById("link-input");
    const attachmentInput = document.getElementById("attachments");

    const charCount = document.getElementById("char-count");
    const fileList = document.getElementById("file-list");

    const stateEls = {
        empty: document.getElementById("result-empty"),
        loading: document.getElementById("result-loading"),
        error: document.getElementById("result-error"),
        content: document.getElementById("result-content")
    };


    /* =====================================================
       RESULT STATES
    ===================================================== */

    function showState(name) {

        Object.entries(stateEls).forEach(([key, el]) => {

            if (!el) return;

            const active = key === name;

            el.hidden = !active;
            el.style.display = active ? "" : "none";
        });

        const target = stateEls[name];

        if (target && name !== "empty") {

            requestAnimationFrame(() => {
                scrollToElement(target, 90);
            });

        }
    }


    function scrollToElement(el, offset) {

        if (!el) return;

        const rect = el.getBoundingClientRect();

        const targetY =
            window.scrollY +
            rect.top -
            offset;

        window.scrollTo({
            top: Math.max(targetY, 0),
            behavior: "smooth"
        });
    }


    window.state = showState;


    /* =====================================================
       CHARACTER COUNT
    ===================================================== */

    if (messageInput && charCount) {

        messageInput.addEventListener("input", () => {

            charCount.textContent =
                messageInput.value.length;

        });

    }


    /* =====================================================
       FILE DISPLAY
    ===================================================== */

    if (attachmentInput && fileList) {

        attachmentInput.addEventListener("change", () => {

            const files =
                Array.from(
                    attachmentInput.files || []
                );

            fileList.innerHTML = files.length

                ? files
                    .map(file =>
                        `<div>${escapeHtml(file.name)}</div>`
                    )
                    .join("")

                : "";

        });

    }


    /* =====================================================
       ANALYZE FORM SUBMIT
    ===================================================== */

    if (form) {

        form.addEventListener(
            "submit",
            async (event) => {

                event.preventDefault();

                const message =
                    messageInput?.value.trim() || "";

                const link =
                    linkInput?.value.trim() || "";

                const files =
                    attachmentInput?.files || [];


                if (!message && !link && !files.length) {

                    showFormError(
                        "Please enter a message, suspicious link, or upload a file."
                    );

                    return;
                }


                if (button) {
                    button.disabled = true;
                }

                showState("loading");


                const formData =
                    new FormData();

                formData.append(
                    "message",
                    message
                );

                formData.append(
                    "link",
                    link
                );


                if (files.length > 0) {

                    formData.append(
                        "file",
                        files[0]
                    );

                }


                try {

                    const response =
                        await fetch(
                            "/api/analyze",
                            {
                                method: "POST",
                                body: formData
                            }
                        );


                    const raw =
                        await response.text();

                    let data;


                    try {

                        data =
                            JSON.parse(raw);

                    } catch {

                        throw new Error(
                            "Server returned an invalid response."
                        );

                    }


                    if (!response.ok) {

                        throw new Error(
                            data.error ||
                            data.message ||
                            `Analysis failed (${response.status})`
                        );

                    }


                    renderResult(data);


                } catch (err) {

                    console.error(
                        "RakshaCircle scan error:",
                        err
                    );

                    showFormError(
                        err.message ||
                        "Please check your connection and try again."
                    );


                } finally {

                    if (button) {
                        button.disabled = false;
                    }

                }

            }
        );

    }


    /* =====================================================
       FORM ERROR
    ===================================================== */

    function showFormError(message) {

        showState("error");

        const errorText =
            stateEls.error?.querySelector("p");

        if (errorText) {

            errorText.textContent =
                message;

        }

    }


    /* =====================================================
       RISK COLOR
    ===================================================== */

    function riskColor(score) {

        if (score >= 60) {
            return "#dc3d4b";
        }

        if (score >= 30) {
            return "#d88a00";
        }

        return "#169b62";
    }


    /* =====================================================
       RENDER ANALYSIS RESULT
    ===================================================== */

    function renderResult(data) {

        const score =
            Math.max(
                0,
                Math.min(
                    100,
                    Number(data.score) || 0
                )
            );


        const risk =
            data.risk || "Safe";


        const language =
            data.language || "Unknown";


        const evidence =
            Array.isArray(data.evidence)
                ? data.evidence
                : [];


        const flags =
            Array.isArray(data.red_flags)
                ? data.red_flags
                : [];


        const explanation =
            data.explanation ||
            "No detailed explanation was returned.";


        const action =
            data.action ||
            "Do not share personal or financial information.";


        const color =
            riskColor(score);


        const scoreNumber =
            document.getElementById(
                "score-number"
            );


        const meterFill =
            document.getElementById(
                "meter-fill"
            );


        const riskLabel =
            document.getElementById(
                "risk-label"
            );


        const langDetected =
            document.getElementById(
                "lang-detected"
            );


        const evidenceEl =
            document.getElementById(
                "evidence"
            );


        const flagsEl =
            document.getElementById(
                "flags-list"
            );


        const explanationEl =
            document.getElementById(
                "explanation-text"
            );


        const actionEl =
            document.getElementById(
                "action-text"
            );


        const alertTag =
            document.getElementById(
                "alert-tag"
            );


        if (scoreNumber) {

            scoreNumber.textContent =
                score;

        }


        if (meterFill) {

            const circumference =
                326.7;

            const offset =
                circumference -
                (
                    circumference *
                    score /
                    100
                );


            meterFill.style.stroke =
                color;

            meterFill.style.strokeDashoffset =
                offset;

        }


        if (riskLabel) {

            riskLabel.textContent =
                risk;

            riskLabel.style.color =
                color;

        }


        if (langDetected) {

            langDetected.textContent =
                language;

        }


        if (evidenceEl) {

            evidenceEl.innerHTML =
                evidence.length

                    ? evidence
                        .map(item =>
                            `<span>${escapeHtml(String(item))}</span>`
                        )
                        .join("")

                    : `<span>No specific evidence extracted.</span>`;

        }


        if (flagsEl) {

            flagsEl.innerHTML =
                flags.length

                    ? flags
                        .map(item =>
                            `<li>${escapeHtml(String(item))}</li>`
                        )
                        .join("")

                    : `<li>No specific red flags detected.</li>`;

        }


        if (explanationEl) {

            explanationEl.textContent =
                explanation;

        }


        if (actionEl) {

            actionEl.textContent =
                action;

        }


        if (alertTag) {

            const familyAlert =
                data.family_alert;


            const triggered =
                score >= 70 ||
                Boolean(
                    familyAlert &&
                    familyAlert.sent
                );


            alertTag.hidden =
                !triggered;

        }


        showState("content");

    }


    /* =====================================================
       FAMILY CIRCLE
    ===================================================== */

    const familyForm =
        document.getElementById(
            "family-form"
        );


    const familyList =
        document.getElementById(
            "family-list"
        );


    const familyEmpty =
        document.getElementById(
            "family-empty"
        );


    /* =====================================================
       LOAD FAMILY MEMBERS
    ===================================================== */

    async function loadFamily() {

        if (!familyList) return;


        try {

            const response =
                await fetch(
                    "/api/family"
                );


            if (!response.ok) {

                throw new Error(
                    `Failed to load family members (${response.status})`
                );

            }


            const members =
                await response.json();


            if (
                !Array.isArray(members) ||
                members.length === 0
            ) {

                familyList.innerHTML = "";

                if (familyEmpty) {
                    familyEmpty.hidden = false;
                }

                return;

            }


            if (familyEmpty) {
                familyEmpty.hidden = true;
            }


            familyList.innerHTML =
                members
                    .map(member => `

                        <li>

                            <strong>
                                ${escapeHtml(member.name)}
                            </strong>

                            ${
                                member.relation
                                    ? `<span> · ${escapeHtml(member.relation)}</span>`
                                    : ""
                            }

                            <div>

                                ${
                                    member.phone
                                        ? `<small>${escapeHtml(member.phone)}</small>`
                                        : ""
                                }

                                ${
                                    member.email
                                        ? `<small>${escapeHtml(member.email)}</small>`
                                        : ""
                                }

                            </div>

                            <button
                                type="button"
                                class="secondary-btn"
                                data-delete="${member.id}"
                            >
                                Remove
                            </button>

                        </li>

                    `)
                    .join("");


            /* DELETE BUTTONS */

            familyList
                .querySelectorAll(
                    "[data-delete]"
                )
                .forEach(button => {

                    button.addEventListener(
                        "click",
                        async () => {

                            const id =
                                button.dataset.delete;


                            try {

                                const response =
                                    await fetch(
                                        `/api/family/${id}`,
                                        {
                                            method: "DELETE"
                                        }
                                    );


                                const data =
                                    await response.json();


                                if (!response.ok) {

                                    throw new Error(
                                        data.error ||
                                        "Failed to remove family member."
                                    );

                                }


                                await loadFamily();


                            } catch (err) {

                                console.error(
                                    "Delete family member error:",
                                    err
                                );


                                alert(
                                    "Could not remove family member: " +
                                    err.message
                                );

                            }

                        }
                    );

                });


        } catch (err) {

            console.error(
                "RakshaCircle: failed to load family circle.",
                err
            );


            familyList.innerHTML = `
                <li>
                    Could not load family members.
                </li>
            `;

        }

    }


    /* =====================================================
       ADD FAMILY MEMBER
    ===================================================== */

    if (familyForm) {

        familyForm.addEventListener(
            "submit",
            async (event) => {

                event.preventDefault();


                const name =
                    document
                        .getElementById(
                            "member-name"
                        )
                        ?.value
                        .trim() || "";


                const relation =
                    document
                        .getElementById(
                            "member-relation"
                        )
                        ?.value
                        .trim() || "";


                const phone =
                    document
                        .getElementById(
                            "member-phone"
                        )
                        ?.value
                        .trim() || "";


                const email =
                    document
                        .getElementById(
                            "member-email"
                        )
                        ?.value
                        .trim() || "";


                if (!name) {

                    alert(
                        "Please enter family member name."
                    );

                    return;

                }


                /* BUTTON */

                const submitButton =
                    familyForm.querySelector(
                        'button[type="submit"]'
                    );


                if (submitButton) {

                    submitButton.disabled =
                        true;

                    submitButton.dataset.originalText =
                        submitButton.textContent;

                    submitButton.textContent =
                        "Adding...";

                }


                try {

                    const response =
                        await fetch(
                            "/api/family",
                            {
                                method: "POST",

                                headers: {
                                    "Content-Type":
                                        "application/json"
                                },

                                body:
                                    JSON.stringify({
                                        name:
                                            name,

                                        relation:
                                            relation,

                                        phone:
                                            phone,

                                        email:
                                            email
                                    })
                            }
                        );


                    const data =
                        await response.json();


                    console.log(
                        "Family API response:",
                        data
                    );


                    if (!response.ok) {

                        throw new Error(
                            data.error ||
                            data.message ||
                            `Failed to add family member (${response.status})`
                        );

                    }


                    /* SUCCESS */

                    familyForm.reset();


                    await loadFamily();


                    alert(
                        "Family member added successfully! ✅"
                    );


                } catch (err) {

                    console.error(
                        "RakshaCircle: failed to add family member.",
                        err
                    );


                    alert(
                        "Could not add family member:\n\n" +
                        err.message
                    );


                } finally {

                    if (submitButton) {

                        submitButton.disabled =
                            false;

                        submitButton.textContent =
                            submitButton.dataset.originalText ||
                            "+ Add to family circle";

                    }

                }

            }
        );

    }


    /* =====================================================
       SCAN HISTORY
    ===================================================== */

    const historyList =
        document.getElementById(
            "history-list"
        );


    async function loadHistory() {

        if (!historyList) return;


        historyList.innerHTML =
            `<div class="history-loading">
                Loading scan history...
            </div>`;


        try {

            const response =
                await fetch(
                    "/api/history"
                );


            if (!response.ok) {

                throw new Error(
                    `Failed to load history (${response.status})`
                );

            }


            const scans =
                await response.json();


            if (
                !Array.isArray(scans) ||
                scans.length === 0
            ) {

                historyList.innerHTML =
                    `<div class="history-loading">
                        No scans yet.
                    </div>`;

                return;

            }


            historyList.innerHTML =
                scans
                    .map(scan => `

                        <div>

                            <strong
                                style="color:${riskColor(scan.score)}"
                            >
                                ${escapeHtml(scan.risk)}
                                ·
                                ${escapeHtml(scan.score)}/100
                            </strong>

                            <p>
                                ${escapeHtml(
                                    scan.explanation || ""
                                )}
                            </p>

                            <small>
                                ${escapeHtml(
                                    scan.created_at || ""
                                )}
                            </small>

                        </div>

                    `)
                    .join("");


        } catch (err) {

            console.error(
                "RakshaCircle: failed to load history.",
                err
            );


            historyList.innerHTML =
                `<div class="history-loading">
                    Couldn't load scan history.
                </div>`;

        }

    }


    /* =====================================================
       HTML ESCAPE
    ===================================================== */

    function escapeHtml(value) {

        return String(
            value ?? ""
        )
            .replace(
                /&/g,
                "&amp;"
            )
            .replace(
                /</g,
                "&lt;"
            )
            .replace(
                />/g,
                "&gt;"
            )
            .replace(
                /"/g,
                "&quot;"
            )
            .replace(
                /'/g,
                "&#039;"
            );

    }


    /* =====================================================
       INITIAL STATE
    ===================================================== */

    showState("empty");

});