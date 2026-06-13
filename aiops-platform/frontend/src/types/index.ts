export interface ApiResponse<T = unknown> {
  code: number;
  message: string;
  data: T;
}

export interface UserInfo {
  userId: number;
  username: string;
  email: string;
  avatar?: string;
  roles: string[];
  permissions: string[];
  scope: string[];
  isAdmin: boolean;
}

export interface LoginParams {
  username: string;
  password: string;
}

export interface LoginResult {
  token: string;
  user: UserInfo;
}

export interface RegisterParams {
  username: string;
  email: string;
  password: string;
  isAdmin?: boolean;
}

export interface Log {
  id: number;
  timestamp: string;
  level: string;
  content: string;
  source: string;
  is_anomaly: boolean;
  anomaly_score: number | null;
  user_feedback: boolean | null;
}

export interface LogStats {
  total_logs: number;
  anomaly_count: number;
  anomaly_rate: number;
  level_distribution: Record<string, number>;
  top_patterns: Array<{ content: string; score: number }>;
}

export interface AgentTask {
  task_id: string;
  user_input?: string;
  status: string;
  intent_data: IntentData | null;
  analysis_report: AnalysisReport | null;
  knowledge_context: KnowledgeContext | null;
  decision: Decision | null;
  action_result: ActionResult | null;
  created_at: string;
  updated_at: string;
  warning_cleared?: boolean;
  ansible_playbook?: AnsiblePlaybook | null;
  server_status_check?: ServerStatusCheck | null;
  mode?: string;
  iterations?: number;
  diagnosis_plan?: DiagnosisPlan | null;
  execution_outputs?: ExecutionOutput[];
  saved_outputs?: SavedOutput[];
  raw_response?: string;
  skill_matching?: SkillMatchInfo | null;
  email_approval?: EmailApprovalInfo | null;
  saved_to?: string;
}

export interface SkillMatchInfo {
  matched_skills: string[];
  skill_summary: string;
  skills_preview: string;
}

export interface EmailApprovalInfo {
  email_sent: boolean;
  approval_id: string;
  to_email: string;
  operation: string;
  risk: string;
  message: string;
  status: string;
}

export interface DiagnosisPlan {
  plan_name: string;
  check_type: string;
  commands: string[];
  reasoning: string;
  expected_findings?: string[];
  created_at?: string;
}

export interface ExecutionOutput {
  command: string;
  output: string;
  success: boolean;
  target_host: string;
}

export interface SavedOutput {
  success: boolean;
  target_host: string;
  command?: string;
  saved_to: string;
}

export interface AnsiblePlaybook {
  target_host: string;
  playbook: Record<string, unknown>;
  symptoms: string[];
  metrics: string[];
}

export interface ServerStatusCheck {
  success: boolean;
  warning_cleared: boolean;
  memory_usage?: number;
  cpu_usage?: number;
  disk_usage?: number;
  shm_usage?: number;
  anomalies: string[];
  raw_output?: string;
  error?: string;
}

export interface IntentData {
  intent: string;
  entities: {
    service: string;
    ip: string | null;
    symptom: string;
    time_range: string;
  };
  confidence: string;
  normalized_query: string;
  clarification_needed: boolean;
}

export interface AnalysisReport {
  service?: string;
  analysis_report: string;
  metrics_summary?: Record<string, string | number>;
  log_patterns?: string[];
  trace_anomalies?: Array<{ span: string; duration: string; anomaly: string }>;
  diagnosis_plan?: DiagnosisPlan | null;
}

export interface KnowledgeContext {
  service?: string;
  symptom?: string;
  knowledge_report: string;
  topology_info?: Record<string, unknown>;
  similar_incidents?: Record<string, unknown>;
  sop_docs?: Record<string, unknown>;
}

export interface Decision {
  root_cause_summary?: string;
  decision?: string;
  action_plan?: string;
  target_agent?: string | null;
  risk_level: string;
  reasoning?: string;
  is_final?: boolean;
  problem_type?: string;
  root_cause?: string;
  impact?: string;
  recommendation?: string;
  confirmation_request?: ConfirmationRequest;
}

export interface ConfirmationRequest {
  success: boolean;
  requires_confirmation: boolean;
  operation: string;
  risk: string;
  impact: string;
  message: string;
}

export interface ActionResult {
  tool_name: string;
  template_name: string | null;
  parameters: Record<string, unknown>;
  risk_assessment: string;
  requires_approval: boolean;
  execution_note: string;
}

export interface DiagnoseRequest {
  user_input: string;
  session_id?: string;
}

export interface DiagnoseResponse {
  task_id: string;
  status: string;
  message: string;
}

export interface Alert {
  id: string;
  fingerprint: string;
  status: 'firing' | 'resolved';
  labels: Record<string, string>;
  annotations: Record<string, string>;
  startsAt: string;
  endsAt?: string;
  severity: 'critical' | 'warning' | 'info';
  service?: string;
  cluster_id?: number;
}

export interface ClusteredAlerts {
  total_alerts: number;
  cluster_count: number;
  clusters: AlertCluster[];
  lookback: string;
}

export interface AlertCluster {
  cluster_id: number;
  pattern: string;
  count: number;
  severity: string;
  services: string[];
  first_occurrence: string;
  last_occurrence: string;
  sample_alerts: Alert[];
}

export interface AlertStats {
  total: number;
  firing: number;
  resolved: number;
  by_severity: Record<string, number>;
  by_service: Record<string, number>;
  trend: Array<{ time: string; count: number }>;
}

export interface AlertIngestResponse {
  success: boolean;
  message: string;
  total_alerts: number;
  firing_count: number;
  resolved_count: number;
  cluster_result?: ClusteredAlerts;
}

export interface TraceSearchResult {
  total: number;
  traces: TraceInfo[];
  lookback: string;
}

export interface TraceInfo {
  traceID: string;
  rootServiceName: string;
  rootTraceName: string;
  startTime: string;
  durationMs: number;
  spanCount: number;
  hasError: boolean;
  services: string[];
}

export interface TraceDetail {
  traceID: string;
  spans: Span[];
  services: string[];
  totalDurationMs: number;
  hasError: boolean;
  errorSpans: Span[];
  spanTree: SpanTreeNode[];
}

export interface Span {
  spanID: string;
  parentSpanID?: string;
  operationName: string;
  serviceName: string;
  startTime: string;
  durationMs: number;
  tags: Record<string, string | number | boolean>;
  hasError: boolean;
  statusCode: string;
}

export interface SpanTreeNode {
  span: Span;
  children: SpanTreeNode[];
}

export interface ServiceDependency {
  nodes: Array<{ id: string; name: string }>;
  edges: ServiceEdge[];
  total_services: number;
  total_edges: number;
  lookback: string;
}

export interface ServiceEdge {
  source: string;
  target: string;
  call_count: number;
  error_count: number;
  error_rate: number;
  avg_latency_ms: number;
  p99_latency_ms: number;
}

export interface TraceAnalysis {
  success: boolean;
  trace_id?: string;
  trace?: TraceDetail;
  performance_analysis?: TracePerformance;
  error_analysis?: TraceErrorAnalysis;
  services_involved?: string[];
  error_count?: number;
  total_duration_ms?: number;
  error?: string;
}

export interface TracePerformance {
  bottleneck_spans: Span[];
  slow_operations: Array<{ operation: string; avg_duration_ms: number }>;
  latency_breakdown: Record<string, number>;
}

export interface TraceErrorAnalysis {
  error_spans: Span[];
  error_types: string[];
  error_propagation_path: string[];
}

export interface RCAReport {
  report_id: string;
  service_name: string;
  time_window_minutes: number;
  hypotheses: RCAHypothesis[];
  root_confidence: number;
  recommendations: string[];
  algorithms_used: string[];
  created_at: string;
}

export interface RCAHypothesis {
  hypothesis_id: string;
  title: string;
  description: string;
  affected_component: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  confidence_score: number;
  evidences: Evidence[];
  remediation_steps: string[];
}

export interface Evidence {
  evidence_id: string;
  evidence_type: string;
  source: string;
  description: string;
  confidence: number;
  timestamp: string;
}

export interface MetricsData {
  query: string;
  result_type: string;
  data: Array<{
    metric: Record<string, string>;
    values: Array<[number, number]>;
  }>;
}

export interface SystemHealth {
  status: 'healthy' | 'degraded' | 'unhealthy';
  components: Array<{
    name: string;
    status: string;
    message?: string;
  }>;
  services: ServiceHealth[];
}

export interface ServiceHealth {
  name: string;
  status: 'up' | 'down' | 'degraded';
  error_rate: number;
  latency_p99: number;
  throughput: number;
}

export interface ServiceInfo {
  name: string;
  namespace?: string;
  instance_count: number;
  error_rate: number;
  latency_p99: number;
}
