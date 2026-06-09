"use client";

import { FormEvent, useState } from "react";
import { Borrower, BorrowerStatus, CreateBorrowerPayload, UpdateBorrowerPayload } from "@/lib/borrowers";

type BorrowerFormProps = {
  mode: "create" | "update";
  initialValue?: Borrower;
  onSubmit: (payload: CreateBorrowerPayload | UpdateBorrowerPayload) => Promise<void>;
  submitText: string;
};

const statuses: BorrowerStatus[] = ["ACTIVE", "CLOSED", "BLOCKED"];

export function BorrowerForm({ mode, initialValue, onSubmit, submitText }: BorrowerFormProps) {
  const [fullName, setFullName] = useState(initialValue?.fullName ?? "");
  const [phoneNumber, setPhoneNumber] = useState(initialValue?.phoneNumber ?? "");
  const [status, setStatus] = useState<BorrowerStatus>(initialValue?.status ?? "ACTIVE");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedFullName = fullName.trim();
    const trimmedPhoneNumber = phoneNumber.trim();
    if (trimmedFullName.length < 2) {
      setError("Full name must contain at least 2 characters");
      return;
    }
    if (!/^[0-9]{10,15}$/.test(trimmedPhoneNumber)) {
      setError("Phone number must be 10 to 15 digits");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      if (mode === "create") {
        await onSubmit({ fullName: trimmedFullName, phoneNumber: trimmedPhoneNumber });
      } else {
        await onSubmit({ fullName: trimmedFullName, phoneNumber: trimmedPhoneNumber, status });
      }
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Unable to submit borrower form");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form className="borrowerForm" onSubmit={handleSubmit}>
      <label className="field">
        <span>Full name</span>
        <input
          className="input"
          value={fullName}
          onChange={(event) => setFullName(event.target.value)}
          required
          minLength={2}
        />
      </label>
      <label className="field">
        <span>Phone number</span>
        <input
          className="input"
          value={phoneNumber}
          onChange={(event) => setPhoneNumber(event.target.value)}
          required
          pattern="[0-9]{10,15}"
        />
      </label>
      {mode === "update" ? (
        <label className="field">
          <span>Status</span>
          <select className="input" value={status} onChange={(event) => setStatus(event.target.value as BorrowerStatus)}>
            {statuses.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      {error ? <p className="formError">{error}</p> : null}
      <div className="actions">
        <button type="submit" className="button" disabled={loading}>
          {loading ? "Saving..." : submitText}
        </button>
      </div>
    </form>
  );
}
