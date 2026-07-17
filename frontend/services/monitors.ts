import { api } from "@/lib/api";
import type {
  AbiEvent,
  BlockchainEvent,
  ContractMonitor,
  CsvImportReport,
  MonitorStats,
  Paginated,
  WalletMonitor,
} from "@/types";

type Query = Record<string, string | number | boolean | undefined | null>;

export const walletMonitorService = {
  list: (query?: Query) => api.get<Paginated<WalletMonitor>>("/api/v1/wallet-monitors/", query),
  get: (id: number) => api.get<WalletMonitor>(`/api/v1/wallet-monitors/${id}/`),
  create: (payload: Partial<WalletMonitor>) =>
    api.post<WalletMonitor>("/api/v1/wallet-monitors/", payload),
  update: (id: number, payload: Partial<WalletMonitor>) =>
    api.patch<WalletMonitor>(`/api/v1/wallet-monitors/${id}/`, payload),
  remove: (id: number) => api.delete(`/api/v1/wallet-monitors/${id}/`),
  pause: (id: number) => api.post<WalletMonitor>(`/api/v1/wallet-monitors/${id}/pause/`),
  resume: (id: number) => api.post<WalletMonitor>(`/api/v1/wallet-monitors/${id}/resume/`),
  stats: (id: number) => api.get<MonitorStats>(`/api/v1/wallet-monitors/${id}/stats/`),
  activity: (id: number) => api.get<BlockchainEvent[]>(`/api/v1/wallet-monitors/${id}/activity/`),
  importCsv: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return api.postForm<CsvImportReport>("/api/v1/wallet-monitors/import-csv/", formData);
  },
  imports: () => api.get<CsvImportReport[]>("/api/v1/wallet-monitors/imports/"),
  exportCsvUrl: (workspaceId: number) =>
    `/api/v1/wallet-monitors/export-csv/?workspace=${workspaceId}`,
};

export const contractMonitorService = {
  list: (query?: Query) => api.get<Paginated<ContractMonitor>>("/api/v1/contract-monitors/", query),
  get: (id: number) => api.get<ContractMonitor>(`/api/v1/contract-monitors/${id}/`),
  create: (payload: Record<string, unknown>) =>
    api.post<ContractMonitor>("/api/v1/contract-monitors/", payload),
  update: (id: number, payload: Record<string, unknown>) =>
    api.patch<ContractMonitor>(`/api/v1/contract-monitors/${id}/`, payload),
  remove: (id: number) => api.delete(`/api/v1/contract-monitors/${id}/`),
  pause: (id: number) => api.post<ContractMonitor>(`/api/v1/contract-monitors/${id}/pause/`),
  resume: (id: number) => api.post<ContractMonitor>(`/api/v1/contract-monitors/${id}/resume/`),
  stats: (id: number) => api.get<MonitorStats>(`/api/v1/contract-monitors/${id}/stats/`),
  activity: (id: number) => api.get<BlockchainEvent[]>(`/api/v1/contract-monitors/${id}/activity/`),
  parseAbi: (abi: string) =>
    api.post<{ valid: boolean; event_count: number; events: AbiEvent[] }>(
      "/api/v1/contract-monitors/parse-abi/",
      { abi }
    ),
};
