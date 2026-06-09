import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import BorrowersPage from "@/app/borrowers/page";

const searchBorrowers = vi.fn();

vi.mock("@/components/app-shell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>
}));

vi.mock("@/components/protected-route", () => ({
  ProtectedRoute: ({ children }: { children: React.ReactNode }) => <>{children}</>
}));

vi.mock("@/lib/borrowers", () => ({
  searchBorrowers: (...args: unknown[]) => searchBorrowers(...args)
}));

describe("BorrowersPage", () => {
  it("loads and renders paginated borrower results", async () => {
    searchBorrowers.mockResolvedValue({
      items: [
        {
          id: "b-1",
          fullName: "Asha Kumar",
          phoneNumber: "9876543210",
          status: "ACTIVE",
          createdAt: "2026-06-09T00:00:00Z",
          updatedAt: "2026-06-09T00:00:00Z"
        }
      ],
      page: 0,
      size: 20,
      totalElements: 1,
      totalPages: 1
    });

    render(<BorrowersPage />);

    expect(await screen.findByText("Asha Kumar")).toBeInTheDocument();
    expect(searchBorrowers).toHaveBeenCalledWith({
      id: "",
      phoneNumber: "",
      fullName: "",
      page: 0,
      size: 20
    });
  });

  it("sends filters when search button is clicked", async () => {
    searchBorrowers.mockResolvedValue({
      items: [],
      page: 0,
      size: 20,
      totalElements: 0,
      totalPages: 0
    });

    render(<BorrowersPage />);

    await screen.findByText("No borrowers found for current filters.");

    fireEvent.change(screen.getByPlaceholderText("Search by borrower ID"), {
      target: { value: "123e4567-e89b-12d3-a456-426614174000" }
    });
    fireEvent.change(screen.getByPlaceholderText("Search by phone number"), {
      target: { value: "9000000000" }
    });
    fireEvent.change(screen.getByPlaceholderText("Search by full name"), {
      target: { value: "Asha" }
    });

    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      expect(searchBorrowers).toHaveBeenLastCalledWith({
        id: "123e4567-e89b-12d3-a456-426614174000",
        phoneNumber: "9000000000",
        fullName: "Asha",
        page: 0,
        size: 20
      });
    });
  });
});
