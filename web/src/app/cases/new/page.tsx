"use client";

import dynamic from "next/dynamic";

// Adding a patient case (Paper FINAL S8a and S8b). Drawn in the browser only: the form starts
// from the draft kept in this browser, which the server can't see.
const NewCaseScreen = dynamic(() => import("./new-case-screen").then((m) => m.NewCaseScreen), {
  ssr: false,
  loading: () => <p>Loading…</p>,
});

export default function NewCasePage() {
  return <NewCaseScreen />;
}
