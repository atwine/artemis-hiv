import { Suspense } from "react";

import { DayScreen } from "./day-screen";

// The clinic day: the first screen of the app (Paper FINAL S1 and S1b).
export default function DayPage() {
  return (
    <Suspense fallback={<p>Loading…</p>}>
      <DayScreen />
    </Suspense>
  );
}
