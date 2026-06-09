import { apiClient } from "@/lib/api-client";

export type BorrowerStatus = "ACTIVE" | "CLOSED" | "BLOCKED";

export type Borrower = {
  id: string;
  fullName: string;
  phoneNumber: string;
  status: BorrowerStatus;
  createdAt: string;
  updatedAt: string;
};

export type BorrowerSearchResponse = {
  items: Borrower[];
  page: number;
  size: number;
  totalElements: number;
  totalPages: number;
};

export type CreateBorrowerPayload = {
  fullName: string;
  phoneNumber: string;
};

export type UpdateBorrowerPayload = {
  fullName: string;
  phoneNumber: string;
  status: BorrowerStatus;
};

export type BorrowerSearchFilters = {
  id?: string;
  phoneNumber?: string;
  fullName?: string;
  page?: number;
  size?: number;
};

export async function searchBorrowers(filters: BorrowerSearchFilters): Promise<BorrowerSearchResponse> {
  const query = new URLSearchParams();
  if (filters.id?.trim()) {
    query.set("id", filters.id.trim());
  }
  if (filters.phoneNumber?.trim()) {
    query.set("phoneNumber", filters.phoneNumber.trim());
  }
  if (filters.fullName?.trim()) {
    query.set("fullName", filters.fullName.trim());
  }
  if (typeof filters.page === "number") {
    query.set("page", String(filters.page));
  }
  if (typeof filters.size === "number") {
    query.set("size", String(filters.size));
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiClient.get<BorrowerSearchResponse>(`/borrowers${suffix}`);
}

export async function getBorrower(id: string): Promise<Borrower> {
  return apiClient.get<Borrower>(`/borrowers/${id}`);
}

export async function createBorrower(payload: CreateBorrowerPayload): Promise<Borrower> {
  return apiClient.post<Borrower>("/borrowers", payload);
}

export async function updateBorrower(id: string, payload: UpdateBorrowerPayload): Promise<Borrower> {
  return apiClient.put<Borrower>(`/borrowers/${id}`, payload);
}
