// Made-up names from docs/design/content-kit.md. There are no logins yet (ACCESS.md), so the
// clinic and the clinician in the top bar are fixed demo values, not data from the backend.
export const DEMO_CLINIC = "Demo ART Clinic · Room 3";
export const DEMO_CLINICIAN = { name: "Dr. A. Okello", initials: "AO" };

// A copy of artemis/screen_text.py DISCLAIMER for the footer, which shows before any visit check
// has run (the API sends the disclaimer only with a check). The browser test fails if the two
// differ.
export const DISCLAIMER = "Decision support only. Clinician retains final authority. Synthetic data only.";
