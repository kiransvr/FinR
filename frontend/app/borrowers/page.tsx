"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { ProtectedRoute } from "@/components/protected-route";
import { Borrower, searchBorrowers } from "@/lib/borrowers";

export default function BorrowersPage() {
  const [idQuery, setIdQuery] = useState("");
  const [phoneQuery, setPhoneQuery] = useState("");
  const [nameQuery, setNameQuery] = useState("");
  const [items, setItems] = useState<Borrower[]>([]);
  const [page, setPage] = useState(0);
  const [size, setSize] = useState(20);
  const [totalElements, setTotalElements] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadBorrowers = async (nextPage: number, nextSize: number) => {
    setLoading(true);
    setError(null);
    try {
      const response = await searchBorrowers({
        id: idQuery,
        phoneNumber: phoneQuery,
        fullName: nameQuery,
        page: nextPage,
        size: nextSize
      });
      setItems(response.items);
      setPage(response.page);
      setSize(response.size);
      setTotalElements(response.totalElements);
      setTotalPages(response.totalPages);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load borrowers");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadBorrowers(0, size);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <AppShell>
      <ProtectedRoute>
        <section className="panel">
          <div className="panelHeader">
            <div>
              <p className="badge">Sprint 2 borrower search</p>
              <h2>Borrowers</h2>
            </div>
            <Link className="button" href="/borrowers/new">
              Add borrower
            </Link>
          </div>
          <div className="searchRow">
            <input
              className="input"
              placeholder="Search by borrower ID"
              value={idQuery}
              onChange={(event) => setIdQuery(event.target.value)}
            />
            <input
              className="input"
              placeholder="Search by phone number"
              value={phoneQuery}
              onChange={(event) => setPhoneQuery(event.target.value)}
            />
            <input
              className="input"
              placeholder="Search by full name"
              value={nameQuery}
              onChange={(event) => setNameQuery(event.target.value)}
            />
            <button className="secondaryButton" onClick={() => void loadBorrowers(0, size)}>
              Search
            </button>
            <button
              className="secondaryButton"
              onClick={() => {
                setIdQuery("");
                setPhoneQuery("");
                setNameQuery("");
                void loadBorrowers(0, size);
              }}
            >
              Clear
            </button>
          </div>
          {loading ? <p>Loading borrowers...</p> : null}
          {error ? <p className="formError">{error}</p> : null}
          {!loading && !error ? (
            <>
              <table className="table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Phone</th>
                    <th>Status</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {items.length === 0 ? (
                    <tr>
                      <td colSpan={4}>No borrowers found for current filters.</td>
                    </tr>
                  ) : (
                    items.map((borrower) => (
                      <tr key={borrower.id}>
                        <td>{borrower.fullName}</td>
                        <td>{borrower.phoneNumber}</td>
                        <td>{borrower.status}</td>
                        <td>
                          <Link href={`/borrowers/${borrower.id}`}>View</Link>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
              <div className="paginationRow">
                <p>
                  Showing page {totalPages === 0 ? 0 : page + 1} of {totalPages} ({totalElements} results)
                </p>
                <div className="actions">
                  <label className="fieldInline">
                    <span>Page size</span>
                    <select
                      className="input"
                      value={size}
                      onChange={(event) => {
                        const nextSize = Number(event.target.value);
                        setSize(nextSize);
                        void loadBorrowers(0, nextSize);
                      }}
                    >
                      <option value={10}>10</option>
                      <option value={20}>20</option>
                      <option value={50}>50</option>
                      <option value={100}>100</option>
                    </select>
                  </label>
                  <button
                    className="secondaryButton"
                    onClick={() => void loadBorrowers(page - 1, size)}
                    disabled={page <= 0}
                  >
                    Previous
                  </button>
                  <button
                    className="secondaryButton"
                    onClick={() => void loadBorrowers(page + 1, size)}
                    disabled={totalPages === 0 || page + 1 >= totalPages}
                  >
                    Next
                  </button>
                </div>
              </div>
            </>
          ) : null}
        </section>
      </ProtectedRoute>
    </AppShell>
  );
}
