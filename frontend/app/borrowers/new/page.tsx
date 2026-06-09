"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { BorrowerForm } from "@/components/borrower-form";
import { ProtectedRoute } from "@/components/protected-route";
import { createBorrower } from "@/lib/borrowers";

export default function NewBorrowerPage() {
  const router = useRouter();

  return (
    <AppShell>
      <ProtectedRoute>
        <section className="panel">
          <p className="badge">Create borrower</p>
          <h2>New borrower</h2>
          <BorrowerForm
            mode="create"
            submitText="Create borrower"
            onSubmit={async (payload) => {
              const borrower = await createBorrower(payload);
              router.push(`/borrowers/${borrower.id}`);
            }}
          />
          <div className="actions">
            <Link className="secondaryButton" href="/borrowers">
              Back to borrowers
            </Link>
          </div>
        </section>
      </ProtectedRoute>
    </AppShell>
  );
}
