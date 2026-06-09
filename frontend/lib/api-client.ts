import { appConfig } from "@/lib/config";

type RequestInterceptor = (input: RequestInfo | URL, init: RequestInit) => Promise<[RequestInfo | URL, RequestInit]> | [RequestInfo | URL, RequestInit];
type ResponseInterceptor = (response: Response) => Promise<Response> | Response;

type ApiValidationError = {
  field: string;
  message: string;
};

type ApiErrorPayload = {
  status: number;
  message: string;
  validationErrors?: ApiValidationError[];
};

export class ApiClientError extends Error {
  status: number;
  validationErrors: ApiValidationError[];

  constructor(status: number, message: string, validationErrors: ApiValidationError[] = []) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.validationErrors = validationErrors;
  }
}

class ApiClient {
  private requestInterceptors: RequestInterceptor[] = [];
  private responseInterceptors: ResponseInterceptor[] = [];

  constructor(private readonly baseUrl: string) {
    this.useRequest(async (input, init) => {
      const token = typeof window === "undefined" ? null : window.localStorage.getItem("fing-auth-token");
      const headers = new Headers(init.headers ?? {});
      headers.set("Content-Type", "application/json");
      if (token) {
        headers.set("Authorization", `Bearer ${token}`);
      }
      return [input, { ...init, headers }];
    });

    this.useResponse(async (response) => {
      if (!response.ok) {
        const payload = await this.parseErrorResponse(response);
        throw new ApiClientError(response.status, payload.message, payload.validationErrors ?? []);
      }
      return response;
    });
  }

  useRequest(interceptor: RequestInterceptor) {
    this.requestInterceptors.push(interceptor);
  }

  useResponse(interceptor: ResponseInterceptor) {
    this.responseInterceptors.push(interceptor);
  }

  async get<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: "GET" });
  }

  async post<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>(path, {
      method: "POST",
      body: JSON.stringify(body)
    });
  }

  async put<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>(path, {
      method: "PUT",
      body: JSON.stringify(body)
    });
  }

  private async request<T>(path: string, init: RequestInit): Promise<T> {
    let input: RequestInfo | URL = `${this.baseUrl}${path}`;
    let requestInit = init;

    for (const interceptor of this.requestInterceptors) {
      [input, requestInit] = await interceptor(input, requestInit);
    }

    let response = await fetch(input, requestInit);

    for (const interceptor of this.responseInterceptors) {
      response = await interceptor(response);
    }

    return response.json() as Promise<T>;
  }

  private async parseErrorResponse(response: Response): Promise<ApiErrorPayload> {
    try {
      const payload = (await response.json()) as Partial<ApiErrorPayload>;
      return {
        status: response.status,
        message: payload.message ?? `API request failed with status ${response.status}`,
        validationErrors: payload.validationErrors ?? []
      };
    } catch {
      return {
        status: response.status,
        message: `API request failed with status ${response.status}`,
        validationErrors: []
      };
    }
  }
}

export const apiClient = new ApiClient(appConfig.apiBaseUrl);
