(function () {
    "use strict";

    const SUPPORTED_LANGUAGES = {
        en: "English",
        hi: "हिन्दी",
        mr: "मराठी",
        ta: "தமிழ்",
        te: "తెలుగు",
        bn: "বাংলা",
        gu: "ગુજરાતી",
        kn: "ಕನ್ನಡ",
        ml: "മലയാളം",
        pa: "ਪੰਜਾਬੀ",
        ur: "اردو"
    };

    function loadGoogleTranslate() {
        if (document.getElementById("google-translate-script")) {
            return;
        }

        window.googleTranslateElementInit = function () {
            if (
                window.google &&
                window.google.translate &&
                document.getElementById("google_translate_element")
            ) {
                new google.translate.TranslateElement(
                    {
                        pageLanguage: "en",
                        includedLanguages: Object.keys(
                            SUPPORTED_LANGUAGES
                        ).join(","),
                        autoDisplay: false
                    },
                    "google_translate_element"
                );
            }
        };

        const script = document.createElement("script");

        script.id = "google-translate-script";
        script.src =
            "https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit";
        script.async = true;

        document.head.appendChild(script);
    }

    function getTranslateSelect() {
        return document.querySelector(
            ".goog-te-combo"
        );
    }

    function changeGoogleLanguage(language) {
        const select = getTranslateSelect();

        if (!select) {
            return false;
        }

        select.value = language;

        select.dispatchEvent(
            new Event("change", {
                bubbles: true
            })
        );

        return true;
    }

    function setLanguage(language) {
        if (!SUPPORTED_LANGUAGES[language]) {
            language = "en";
        }

        localStorage.setItem(
            "rakshacircle_language",
            language
        );

        /*
         * English means return to original page.
         */
        if (language === "en") {
            changeGoogleLanguage("en");
            return;
        }

        /*
         * Google Translate may take a moment to load.
         * Retry a few times instead of making the user
         * refresh the page.
         */
        let attempts = 0;

        const tryTranslate = setInterval(() => {
            attempts++;

            if (changeGoogleLanguage(language)) {
                clearInterval(tryTranslate);
            }

            if (attempts >= 20) {
                clearInterval(tryTranslate);
            }
        }, 300);
    }

    function setupLanguageSelector() {
        const selector =
            document.getElementById("languageSelect");

        if (!selector) {
            return;
        }

        /*
         * Keep the languages already defined by the HTML
         * if they exist. Otherwise create them here.
         */
        if (selector.options.length === 0) {
            Object.entries(SUPPORTED_LANGUAGES)
                .forEach(([code, name]) => {
                    const option =
                        document.createElement("option");

                    option.value = code;
                    option.textContent = name;

                    selector.appendChild(option);
                });
        }

        const savedLanguage =
            localStorage.getItem(
                "rakshacircle_language"
            ) || "en";

        if (
            SUPPORTED_LANGUAGES[savedLanguage]
        ) {
            selector.value = savedLanguage;
        }

        selector.addEventListener(
            "change",
            function () {
                setLanguage(this.value);
            }
        );
    }

    /*
     * Public API
     */
    window.RakshaI18n = {
        languages: SUPPORTED_LANGUAGES,
        setLanguage,
        setupLanguageSelector
    };

    window.setLanguage = setLanguage;

    document.addEventListener(
        "DOMContentLoaded",
        function () {
            setupLanguageSelector();
            loadGoogleTranslate();
        }
    );
})();