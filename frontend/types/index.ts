// ChainSentinel API types — mirror backend serializers.

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export type Severity = "info" | "low" | "medium" | "high" | "critical";
export type Role = "owner" | "admin" | "analyst" | "viewer";

export interface UserProfile {
  company: string;
  job_title: string;
  timezone: string;
}

export interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  is_email_verified: boolean;
  date_joined: string;
  profile?: UserProfile;
}

export interface Workspace {
  id: number;
  name: string;
  slug: string;
  plan: string;
  role: Role | null;
  member_count: number | null;
  suspended_at: string | null;
  created_at: string;
}

export interface Member {
  id: number;
  user_id: number;
  email: string;
  name: string;
  role: Role;
  joined_at: string;
}

export interface Invitation {
  id: number;
  email: string;
  role: Role;
  invited_by_email: string | null;
  created_at: string;
  expires_at: string;
  accepted_at: string | null;
  revoked_at: string | null;
  is_pending: boolean;
}

export interface Chain {
  id: number;
  name: string;
  slug: string;
  chain_id: number;
  native_symbol: string;
  explorer_url: string;
  is_testnet: boolean;
  is_active: boolean;
  required_confirmations: number;
  block_time_seconds: number;
}

export interface ProviderHealth {
  id: number;
  name: string;
  chain_slug: string;
  chain_name: string;
  priority: number;
  is_active: boolean;
  health_status: "healthy" | "degraded" | "unhealthy" | "unknown";
  consecutive_failures: number;
  last_success_at: string | null;
  last_failure_at: string | null;
  last_failure_reason: string;
  last_latency_ms: number | null;
}

export type Direction = "incoming" | "outgoing" | "both";

export interface WalletMonitor {
  id: number;
  name: string;
  address: string;
  chain: string;
  chain_name: string;
  direction: Direction;
  event_types: string[];
  token_contract: string;
  min_value_wei: string | null;
  large_tx_threshold_wei: string | null;
  confirmations_override: number | null;
  required_confirmations: number;
  severity: Severity;
  is_active: boolean;
  tags: string[];
  notes: string;
  last_processed_block: number;
  last_event_at: string | null;
  error_count: number;
  last_error: string;
  created_at: string;
  updated_at: string;
}

export interface AbiEventInput {
  name: string;
  type: string;
  indexed: boolean;
}

export interface AbiEvent {
  name: string;
  signature: string;
  topic0: string;
  anonymous: boolean;
  inputs: AbiEventInput[];
}

export interface ContractAbiDoc {
  id: number;
  name: string;
  sha256: string;
  events: AbiEvent[];
  created_at: string;
}

export interface ContractMonitor {
  id: number;
  name: string;
  label: string;
  address: string;
  chain: string;
  chain_name: string;
  abi_document: ContractAbiDoc | null;
  selected_events: string[];
  available_events: AbiEvent[];
  topic_filters: Record<string, Record<string, string>>;
  confirmations_override: number | null;
  required_confirmations: number;
  severity: Severity;
  is_active: boolean;
  tags: string[];
  notes: string;
  last_processed_block: number;
  last_event_at: string | null;
  error_count: number;
  last_error: string;
  created_at: string;
  updated_at: string;
}

export type EventStatus = "pending" | "confirmed" | "reverted" | "failed" | "ignored";

export interface BlockchainEvent {
  id: number;
  event_type: string;
  status: EventStatus;
  severity: Severity;
  is_large: boolean;
  chain_slug: string;
  chain_name: string;
  monitor_name: string;
  monitor_kind: "wallet" | "contract";
  block_number: number;
  tx_hash: string;
  log_index: number | null;
  from_address: string;
  to_address: string;
  spender_address: string;
  token_address: string;
  token_symbol: string;
  token_decimals: number | null;
  token_id: string;
  amount_wei: string | null;
  occurred_at: string | null;
  created_at: string;
}

export interface TimelineEntry {
  at: string;
  label: string;
  detail: string;
}

export interface BlockchainEventDetail extends BlockchainEvent {
  block_hash: string;
  tx_index: number | null;
  contract_address: string;
  event_signature: string;
  topic0: string;
  decoded: { event?: string; signature?: string; params?: Record<string, unknown> } | null;
  raw: Record<string, unknown> | null;
  decode_error: string;
  confirmations_required: number;
  current_confirmations: number | null;
  confirmed_at: string | null;
  reverted_at: string | null;
  explorer_tx_url: string;
  wallet_monitor_id: number | null;
  contract_monitor_id: number | null;
  related_alerts: { id: number; title: string; severity: Severity; status: string; created_at: string }[];
  timeline: TimelineEntry[];
}

export type AlertStatus = "open" | "acknowledged" | "resolved";

export interface Alert {
  id: number;
  title: string;
  message: string;
  severity: Severity;
  status: AlertStatus;
  rule: number | null;
  rule_name: string | null;
  event_id: number | null;
  chain_slug: string | null;
  count: number;
  first_seen_at: string;
  last_seen_at: string;
  acknowledged_by_email: string | null;
  acknowledged_at: string | null;
  resolved_by_email: string | null;
  resolved_at: string | null;
  created_at: string;
}

export interface AlertNote {
  id: number;
  body: string;
  author_email: string | null;
  created_at: string;
}

export interface AlertDetail extends Alert {
  notes: AlertNote[];
  timeline: TimelineEntry[];
}

export interface AlertRule {
  id: number;
  name: string;
  description: string;
  is_active: boolean;
  wallet_monitor: number | null;
  wallet_monitor_name: string | null;
  contract_monitor: number | null;
  contract_monitor_name: string | null;
  chain: string | null;
  event_types: string[];
  token_address: string;
  min_amount_wei: string | null;
  max_amount_wei: string | null;
  from_address: string;
  to_address: string;
  spender_address: string;
  topic0: string;
  trigger_on: "confirmed" | "reverted";
  severity: Severity | "";
  cooldown_seconds: number;
  group_window_seconds: number;
  notify_in_app: boolean;
  notify_email: boolean;
  notify_webhook: boolean;
  webhook: number | null;
  telegram_enabled: boolean;
  slack_enabled: boolean;
  last_triggered_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface WebhookEndpoint {
  id: number;
  name: string;
  url: string;
  enabled: boolean;
  event_types: string[];
  max_retries: number;
  timeout_seconds: number;
  last_status: string;
  last_success_at: string | null;
  last_failure_reason: string;
  created_at: string;
  updated_at: string;
  secret?: string; // present only in create/regenerate responses
}

export type DeliveryStatus = "pending" | "success" | "retrying" | "exhausted";

export interface WebhookDelivery {
  id: number;
  endpoint: number;
  endpoint_name: string;
  event_type: string;
  payload: Record<string, unknown>;
  status: DeliveryStatus;
  attempt_count: number;
  max_attempts: number;
  response_status: number | null;
  response_time_ms: number | null;
  failure_reason: string;
  next_retry_at: string | null;
  delivered_at: string | null;
  replay_of: number | null;
  created_at: string;
}

export interface Notification {
  id: number;
  type: string;
  severity: Severity;
  title: string;
  body: string;
  link: string;
  workspace: number | null;
  workspace_name: string | null;
  alert_id: number | null;
  read_at: string | null;
  created_at: string;
}

export interface NotificationPrefs {
  min_severity_in_app: Severity;
  min_severity_email: Severity;
  email_critical_alerts: boolean;
  email_failed_webhooks: boolean;
  email_provider_outage: boolean;
  email_daily_summary: boolean;
}

export interface ApiKey {
  id: number;
  workspace: number;
  name: string;
  prefix: string;
  scopes: ("read" | "write")[];
  created_by_email: string | null;
  created_at: string;
  expires_at: string | null;
  last_used_at: string | null;
  revoked_at: string | null;
  is_valid: boolean;
  key?: string; // present only in the create response
}

export interface UserSession {
  id: number;
  user_agent: string;
  ip_address: string | null;
  created_at: string;
  last_seen_at: string;
  revoked_at: string | null;
  is_current: boolean;
}

export interface AuditLog {
  id: number;
  action: string;
  actor_label: string;
  target_type: string;
  target_id: string;
  target_label: string;
  metadata: Record<string, unknown>;
  ip_address: string | null;
  created_at: string;
}

export interface AnalyticsOverview {
  active_monitors: number;
  total_monitors: number;
  events_today: number;
  events_24h: number;
  critical_alerts_open: number;
  open_alerts: number;
  webhook_success_rate_24h: number | null;
  webhook_deliveries_24h: number;
  providers_healthy: number;
  providers_total: number;
  transactions_monitored: number;
}

export interface AnalyticsCharts {
  days: number;
  events_by_chain: { date: string; chain__slug: string; count: number }[];
  events_over_time: { date: string; count: number; confirmed: number }[];
  alerts_by_severity: { severity: Severity; count: number }[];
  top_wallets: { wallet_monitor__name: string; wallet_monitor__address: string; count: number }[];
  top_contract_events: { contract_monitor__name: string; event_signature: string; count: number }[];
  webhook_trend: { date: string; total: number; ok: number; failed: number }[];
}

export interface CsvImportReport {
  id: number;
  filename: string;
  total_rows: number;
  created_count: number;
  failed_count: number;
  report: {
    rows: {
      row: number;
      status: "created" | "error";
      name: string;
      address: string;
      errors?: string[];
      monitor_id?: number;
    }[];
    created_ids: number[];
  };
  created_at: string;
}

export interface MonitorStats {
  monitor_id: number;
  total_events: number;
  events_24h: number;
  events_7d: number;
  alerts_total: number;
  last_event_at: string | null;
  last_processed_block: number;
  error_count: number;
  last_error: string;
  events_by_type: { event_type: string; count: number }[];
  events_daily: { date: string; count: number }[];
}
