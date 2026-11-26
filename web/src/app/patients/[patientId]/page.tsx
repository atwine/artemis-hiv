import { Suspense } from "react";

import { VisitScreen } from "./visit-screen";

export default function PatientPage({ params }: PageProps<"/patients/[patientId]">) {
  return (
    <Suspense fallback={<p>Loading…</p>}>
      <VisitScreen params={params} />
    </Suspense>
  );
}
