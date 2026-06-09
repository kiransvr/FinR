import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { BorrowerForm } from "@/components/borrower-form";

describe("BorrowerForm", () => {
  it("validates create input before submit", async () => {
    const submit = vi.fn();

    render(<BorrowerForm mode="create" submitText="Create borrower" onSubmit={submit} />);

    fireEvent.change(screen.getByLabelText("Full name"), { target: { value: "A" } });
    fireEvent.change(screen.getByLabelText("Phone number"), { target: { value: "9876543210" } });

    fireEvent.click(screen.getByRole("button", { name: "Create borrower" }));

    expect(await screen.findByText("Full name must contain at least 2 characters")).toBeInTheDocument();
    expect(submit).not.toHaveBeenCalled();
  });

  it("submits update payload including status", async () => {
    const submit = vi.fn().mockResolvedValue(undefined);

    render(
      <BorrowerForm
        mode="update"
        submitText="Update borrower"
        initialValue={{
          id: "1",
          fullName: "Asha Kumar",
          phoneNumber: "9876543210",
          status: "ACTIVE",
          createdAt: "2026-06-09T00:00:00Z",
          updatedAt: "2026-06-09T00:00:00Z"
        }}
        onSubmit={submit}
      />
    );

    fireEvent.change(screen.getByDisplayValue("ACTIVE"), { target: { value: "BLOCKED" } });
    fireEvent.click(screen.getByRole("button", { name: "Update borrower" }));

    await waitFor(() => {
      expect(submit).toHaveBeenCalledWith({
        fullName: "Asha Kumar",
        phoneNumber: "9876543210",
        status: "BLOCKED"
      });
    });
  });
});
