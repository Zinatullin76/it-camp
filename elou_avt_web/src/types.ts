// Shared types matching the FastAPI backend contracts.

export interface SchemeNodeData {
  id: string;
  type: string;
  name: string;
  x: number;
  y: number;
  params: Record<string, unknown>;
}

export interface SchemeEdgeData {
  id: string;
  source: string;
  target: string;
  source_port: string;
  target_port: string;
  kind: string;
}

export interface Scheme {
  id: string;
  name: string;
  nodes: SchemeNodeData[];
  edges: SchemeEdgeData[];
}

export interface NodeTelemetry {
  type: string;
  name: string;
  running: boolean | null;
  failed: boolean | null;
  failure_mode: string | null;
  params: Record<string, number | boolean | string | null>;
}

export interface ParamSpec {
  key: string;
  label: string;
  unit: string;
  value: number | null;
  min: number;
  max: number;
  step: number;
  int?: boolean;
}

export interface EquipmentSpec {
  node_id: string;
  node_type: string;
  editable: boolean;
  params: ParamSpec[];
}

export interface AlarmData {
  id: string;
  timestamp: number;
  parameter: string;
  actual_value: number;
  threshold: number;
  severity: string;
  description: string;
  node_id?: string | null;
}

export interface AlarmSetpoint {
  parameter: string;
  node_id: string | null;
  low_low: number | null;
  low: number | null;
  high: number | null;
  high_high: number | null;
  unit: string;
}

export interface AlarmSetpointsResponse {
  setpoints: AlarmSetpoint[];
}

export interface ApiState {
  status: string;
  simulation_time: number;
  speed?: number;
  feed: {
    flow_kg_s: number;
    flow_m3_h: number;
    temperature_c: number;
    pressure_bar: number;
  };
  pressure: Record<string, number>;
  temperature: Record<string, number>;
  feed_flow: number;
  product_flow: number;
  feed_flow_kg_s: number;
  feed_flow_m3_h: number;
  heat_duty: Record<string, number>;
  level: Record<string, number>;
  pump_states: Record<string, boolean>;
  valve_positions: Record<string, number>;
  equipment_states: Record<string, { failed: boolean; failure_mode: string | null; running: boolean }>;
  equipment: Record<string, NodeTelemetry>;
  active_failures: string[];
  alarms: AlarmData[];
  alarm_history?: AlarmData[];
  errors: unknown[];
  controllers?: Record<string, ControllerSnap>;
}

export interface ControllerSnap {
  tag: string;
  desc: string;
  unit: string;
  sp: number;
  pv: number;
  lo: number;
  hi: number;
  kp: number;
  ti: number;
  rev: boolean;
  mode: string;
  out: number;
  i: number;
  man: boolean;
  cascade?: string | null;
  tracked?: boolean;
}

export interface HistoryResponse {
  times: number[];
  series: Record<string, number[]>;
}

export interface PaletteItem {
  type: string;
  label: string;
  category: 'boundary' | 'equipment';
  color: string;
  /** Ключ пресета детальной колонны (К-1..К-4) из mnemo/colPresets. */
  preset?: string;
}

// ---------------------------------------------------------------------------
// LMS (learning management) contracts — mirror lms/models.py of the backend
// ---------------------------------------------------------------------------

export type ModuleKind = 'theory' | 'practice' | 'exam';
export type ModuleStatus = 'NOT_STARTED' | 'IN_PROGRESS' | 'COMPLETED';
export type TaskCategory = 'practice' | 'exam' | 'random';
export type Difficulty = 'EASY' | 'MIDDLE' | 'HARD';

export interface LmsMastery {
  index: number;
  stage_index: number;
  stage: string;
  stages: string[];
  next_stage: string | null;
  to_next: number;
}

export interface LmsModule {
  id: number;
  kind: ModuleKind;
  title: string;
  description: string;
  seq: number;
  content: string;
  scenario_id: string | null;
  practice_task_id: number | null;
  status: ModuleStatus;
  score: number | null;
  attempts: number;
  percent: number;
  practice_title: string;
}

export interface LmsCourse {
  id: number;
  title: string;
  description: string;
  status: 'DRAFT' | 'ACTIVE' | 'ARCHIVED';
  progress_percent: number;
  modules: LmsModule[];
}

export interface LmsCompetency {
  code: string;
  title: string;
  description: string;
  level_percent: number;
}

export interface LmsHistoryRow {
  session_id: string;
  scenario_id: string;
  scenario_name: string;
  task_title: string;
  operator_id: string;
  status: string;
  performance_score: number | null;
  qualification: string;
  sim_start: number;
  sim_end: number | null;
  wall_start: number;
  wall_end: number | null;
  duration_s: number | null;
}

export interface LmsReportRow extends LmsHistoryRow {
  full_name: string;
}

export interface LmsRecommendation {
  kind: 'practice' | 'module' | 'info';
  text: string;
  module_id?: number | null;
  task_id?: number | null;
}

export interface LmsNotification {
  id: number;
  user_id: number;
  text: string;
  kind: string;
  is_read: boolean;
  created_at: number;
}

export interface LmsDashboard {
  username: string;
  full_name: string;
  mastery: LmsMastery;
  current_course: LmsCourse | null;
  nearest_module: LmsModule | null;
  nearest_exam: LmsModule | null;
  recent_practices: LmsHistoryRow[];
  recommendations: LmsRecommendation[];
  competencies: LmsCompetency[];
  notifications: LmsNotification[];
}

export interface LmsPracticeTask {
  id: number;
  title: string;
  description: string;
  goal?: string;
  target_state?: TaskCondition[];
  scenario_id: string;
  category: TaskCategory;
  difficulty: Difficulty;
  duration_min: number;
  required_competencies: string[];
  is_random: boolean;
  enabled: boolean;
  scenario_name: string;
  is_ready: boolean;
  readiness_percent: number;
  module_id?: number;
  module_title?: string;
}

export interface LmsScenario {
  id: string;
  name: string;
  description: string;
}

export interface DebriefStep {
  seq: number;
  kind: string;
  timestamp: number;
  equipment_id: string;
  action_type: string;
  description: string;
  status: string;
  detail: string;
}

export interface DebriefError {
  rule_error_type: string;
  severity: string;
  expected_action: string;
  cause: string;
  consequence: string;
  timestamp: number;
}

export interface CompetencyDelta {
  code: string;
  title: string;
  old: number;
  new: number;
  delta: number;
}

export interface LmsDebrief {
  session_id: string;
  task_title: string;
  scenario_id: string;
  scenario_name: string;
  operator_id: string;
  operator_full_name: string;
  performance_score: number;
  qualification: string;
  duration_s: number;
  sim_start: number;
  sim_end: number;
  steps: DebriefStep[];
  alarms: Record<string, unknown>[];
  errors: DebriefError[];
  remarks: string[];
  recommendations: string[];
  competency_delta: CompetencyDelta[];
}

export interface LmsGroup {
  id: number;
  name: string;
  description: string;
  course_id: number | null;
  course_title: string;
  instructor_id: number | null;
  created_at: number;
  member_count: number;
}

export interface GroupMemberProgress {
  user_id: number;
  username: string;
  full_name: string;
  course_progress: number;
  mastery: number;
  stage: string;
  competencies: LmsCompetency[];
  last_session: LmsHistoryRow | null;
}

export interface LmsGroupView {
  group: LmsGroup;
  course: LmsCourse | null;
  members: GroupMemberProgress[];
}

export interface LmsAnalytics {
  avg_score: number;
  total_sessions: number;
  completed_sessions: number;
  avg_duration_s: number;
  group_rating: { group_id: number; group_name: string; member_count: number; avg_score: number; sessions: number }[];
  frequent_errors: { rule_error_type: string; count: number }[];
  competency_distribution: { code: string; title: string; avg_level: number }[];
  learning_dynamics: { date: string; avg_score: number; count: number }[];
  status_distribution: { status: string; count: number }[];
}

export interface LmsMonitorOperator {
  username: string;
  full_name: string;
  session_id: string;
  scenario_id: string;
  scenario_name: string;
  status: string;
  sim_time: number;
  performance_score: number | null;
  alarms: Record<string, unknown>[];
  actions_count: number;
  errors_count: number;
  last_action: Record<string, unknown> | null;
  is_system: boolean;
}

export interface LmsProfile {
  username: string;
  full_name: string;
  roles: string[];
  permissions: string[];
  created_at: number;
  mastery: LmsMastery;
  competencies: LmsCompetency[];
  total_sessions: number;
  avg_score: number;
}

export interface SystemLogEntry {
  id: number;
  timestamp: number;
  level: string;
  username: string;
  message: string;
  category: string;
}

// ---------------------------------------------------------------------------
// Content authoring & study contracts — mirror lms/content_models.py
// ---------------------------------------------------------------------------

export type LessonBlockKind =
  | 'text'
  | 'image'
  | 'scheme'
  | 'video'
  | 'equipment_card'
  | 'scheme_highlight'
  | 'interactive_scheme';

export type QuestionKind = 'single' | 'multi' | 'match' | 'sequence' | 'object';
export type ScenarioStatus = 'DRAFT' | 'REVIEW' | 'PUBLISHED' | 'ARCHIVED';
export type AssessmentKind = 'test' | 'practice' | 'exam';

export interface LessonBlock {
  kind: LessonBlockKind;
  title: string;
  content: string;
  url: string;
  node_id: string;
}

export interface Lesson {
  id: number | null;
  module_id: number;
  title: string;
  seq: number;
  blocks: LessonBlock[];
  equipment_ids: string[];
  competency_codes: string[];
  created_at: number;
}

export interface Question {
  id: number | null;
  test_id: number | null;
  kind: QuestionKind;
  title: string;
  text: string;
  seq: number;
  options: Record<string, unknown>[];
  answer: unknown;
  max_score: number;
  penalty: number;
  required: boolean;
  hint: string;
}

export interface TestConfig {
  id: number | null;
  module_id: number;
  title: string;
  passing_score: number;
  attempts: number;
  retry_required: boolean;
  shuffle: boolean;
  competency_codes: string[];
  questions: Question[];
}

export interface TaskCondition {
  object_id: string;
  attribute: string;
  relation: string;
  value: unknown;
  value2: unknown;
}

export interface RestrictionRule {
  action_type: string;
  object_id: string;
  relation: string;
  value: unknown;
  severity: string;
  message: string;
}

export interface Criterion {
  key: string;
  title: string;
  weight: number;
}

export interface ExpectedAction {
  seq: number;
  object_id: string;
  action_type: string;
  attribute?: string;
  value: unknown;
  description: string;
  deadline_t: number | null;
  weight: number;
}

export interface TrainingTask {
  id: number | null;
  module_id: number;
  title: string;
  goal: string;
  scenario_id: string;
  duration_min: number;
  initial_state: Record<string, unknown>;
  target_state: TaskCondition[];
  restrictions: RestrictionRule[];
  criteria: Criterion[];
  expected_actions: ExpectedAction[];
  critical_errors: RestrictionRule[];
  competency_codes: string[];
  equipment_ids: string[];
  enabled: boolean;
  created_at: number;
}

export interface ScenarioEventDef {
  time: number;
  event_type: string;
  object_id: string;
  param: string;
  value: unknown;
  severity: string;
  message: string;
}

export interface ScenarioDefinition {
  id: number | null;
  module_id: number;
  title: string;
  description: string;
  goal: string;
  status: ScenarioStatus;
  initial_state: Record<string, unknown>;
  events: ScenarioEventDef[];
  expected_actions: ExpectedAction[];
  success_criteria: Criterion[];
  critical_errors: RestrictionRule[];
  target_state: TaskCondition[];
  final_state: Record<string, unknown>;
  competency_codes: string[];
  equipment_ids: string[];
  duration_min: number;
  is_exam: boolean;
  created_at: number;
}

export interface ScenarioCatalogItem extends ScenarioDefinition {
  module_title: string;
  course_id: number | null;
  course_title: string;
}

export interface EquipmentItem {
  id: string;
  type: string;
  name: string;
  params: Record<string, number>;
}

export interface CompetencyRef {
  code: string;
  title: string;
  description: string;
  level_percent: number;
}

export interface ModuleStudy {
  module: { id: number; title: string; description: string; kind: string; content: string };
  lessons: Lesson[];
  test: TestConfig | null;
  task: TrainingTask | null;
  scenario: ScenarioDefinition | null;
  equipment: EquipmentItem[];
  competencies: CompetencyRef[];
}

export interface ModuleAuthoringView {
  module: {
    id: number;
    title: string;
    description: string;
    kind: string;
    content: string;
    published: boolean;
    course_id: number | null;
  };
  lessons: Lesson[];
  test: TestConfig | null;
  task: TrainingTask | null;
  scenario: ScenarioDefinition | null;
}

export interface AssessmentView {
  id: number;
  user_id: number;
  module_id: number;
  kind: AssessmentKind;
  test_id: number | null;
  task_id: number | null;
  scenario_id: string | null;
  score: number;
  max_score: number;
  passed: boolean;
  criteria_scores: Record<string, unknown>;
  errors_count: number;
  critical_errors_count: number;
  duration_s: number;
  answers: unknown;
  feedback_good: string[];
  feedback_bad: string[];
  session_id: string | null;
  started_at: number;
  finished_at: number;
  created_at: number;
  username: string;
  full_name: string;
  module_title: string;
  task_title: string;
  scenario_title: string;
}

export interface PracticeStartResult {
  session_id: string;
  scenario_id: string;
  scenario_name: string;
  module_id: number;
  task_id: number;
  sim_time: number;
}

export interface ScenarioStatusStep {
  status: ScenarioStatus;
  current: boolean;
  next: string | null;
}

export interface InstructorOperator {
  user_id: number;
  username: string;
  full_name: string;
  total_assessments: number;
  passed_assessments: number;
  avg_score: number;
  last_assessment: AssessmentView | null;
  competencies: LmsCompetency[];
}

export interface ActionLogEntry {
  id: number;
  timestamp: number;
  user_id: number | null;
  username: string;
  object_id: string;
  object_name: string;
  action: string;
  old_state: unknown;
  new_state: unknown;
  source: string;
  session_id: string | null;
  module_id: number | null;
}

export type ScadaLogEventType = 'click' | 'inspector_open' | 'inspector_close' | 'page_enter' | 'page_exit';

export interface ScadaLogEntry {
  id: number;
  timestamp: number;
  user_id: number | null;
  username: string;
  event_type: ScadaLogEventType;
  object_id: string;
  object_name: string;
  duration_s: number | null;
  session_id: string | null;
  module_id: number | null;
}
