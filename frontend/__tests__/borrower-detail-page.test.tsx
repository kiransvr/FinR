import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import BorrowerDetailPage from "@/app/borrowers/[borrowerId]/page";

const getBorrower = vi.fn();
const updateBorrower = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => ({ borrowerId: "b-1" })
}));

vi.mock("@/components/app-shell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>
}));

vi.mock("@/components/protected-route", () => ({
  ProtectedRoute: ({ children }: { children: React.ReactNode }) => <>{children}</>
}));

vi.mock("@/lib/borrowers", () => ({
  getBorrower: (...args: unknown[]) => getBorrower(...args),
  updateBorrower: (...args: unknown[]) => updateBorrower(...args)
}));

describe("BorrowerDetailPage", () => {
  it("loads borrower and submits update", async () => {
    getBorrower.mockResolvedValue({
      id: "b-1",
      fullName: "Asha Kumar",
      phoneNumber: "9876543210",
      status: "ACTIVE",
      createdAt: "2026-06-09T00:00:00Z",
      updatedAt: "2026-06-09T00:00:00Z"
    });

    updateBorrower.mockResolvedValue({
      id: "b-1",
      fullName: "Asha Kumar",
      phoneNumber: "9876543210",
      status: "BLOCKED",
      createdAt: "2026-06-09T00:00:00Z",
      updatedAt: "2026-06-10T00:00:00Z"
    });

    render(<BorrowerDetailPage />);

    expect(await screen.findByText(/Borrower profile/i)).toBeInTheDocument();
    expect(getBorrower).toHaveBeenCalledWith("b-1");

    fireEvent.change(screen.getByDisplayValue("ACTIVE"), { target: { value: "BLOCKED" } });
    fireEvent.click(screen.getByRole("button", { name: "Update borrower" }));

    await waitFor(() => {
      expect(updateBorrower).toHaveBeenCalledWith("b-1", {
        fullName: "Asha Kumar",
        phoneNumber: "9876543210",
        status: "BLOCKED"
      });
    });
  });
});
