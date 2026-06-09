"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { BorrowerForm } from "@/components/borrower-form";
import { ProtectedRoute } from "@/components/protected-route";
import { Borrower, getBorrower, updateBorrower } from "@/lib/borrowers";

export default function BorrowerDetailPage() {
  const params = useParams<{ borrowerId: string }>();
  const borrowerId = params.borrowerId;
  const [borrower, setBorrower] = useState<Borrower | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      setError(null);
      try {
        const result = await getBorrower(borrowerId);
        setBorrower(result);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Unable to load borrower detail");
      }
    };
    void load();
  }, [borrowerId]);

  return (
    <AppShell>
      <ProtectedRoute>
        <section className="panel">
          <p className="badge">Borrower detail</p>
          <h2>Borrower profile</h2>
          {error ? <p className="formError">{error}</p> : null}
          {!borrower && !error ? <p>Loading borrower detail...</p> : null}
          {borrower ? (
            <>
              <div className="detailGrid">
                <div>
                  <strong>ID:</strong> {borrower.id}
                </div>
                <div>
                  <strong>Created:</strong> {new Date(borrower.createdAt).toLocaleString()}
                </div>
                <div>
                  <strong>Updated:</strong> {new Date(borrower.updatedAt).toLocaleString()}
                </div>
              </div>
              <BorrowerForm
                mode="update"
                initialValue={borrower}
                submitText="Update borrower"
                onSubmit={async (payload) => {
                  const updated = await updateBorrower(borrower.id, {
                    fullName: payload.fullName,
                    phoneNumber: payload.phoneNumber,
                    status: payload.status ?? borrower.status
                  });
                  setBorrower(updated);
                }}
              />
            </>
          ) : null}
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
