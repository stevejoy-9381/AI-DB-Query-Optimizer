import { AxiosError } from "axios";

export function createMockAxiosError(status: number, data: any, message = "Request failed"): AxiosError {
  const error = new Error(message) as any;
  error.isAxiosError = true;
  error.response = {
    status,
    statusText: status === 400 ? "Bad Request" : status === 422 ? "Unprocessable Entity" : "Internal Server Error",
    headers: {},
    config: {},
    data,
  };
  return error as AxiosError;
}

export function createMockNetworkError(): AxiosError {
  const error = new Error("Network Error") as any;
  error.isAxiosError = true;
  error.response = undefined;
  return error as AxiosError;
}
