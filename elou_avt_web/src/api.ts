import type {
  ApiState,
  AssessmentView,
  ControllerSnap,
  EquipmentItem,
  EquipmentSpec,
  HistoryResponse,
  Lesson,
  LessonBlock,
  ModuleAuthoringView,
  ModuleStudy,
  PracticeStartResult,
  Question,
  ScenarioDefinition,
  ScenarioStatus,
  Scheme,
  SchemeNodeData,
  SchemeEdgeData,
  ScadaLogEventType,
  LmsAnalytics,
  LmsCourse,
  LmsDashboard,
  LmsDebrief,
  LmsGroup,
  LmsGroupView,
  LmsHistoryRow,
  LmsMonitorOperator,
  LmsPracticeTask,
  LmsProfile,
  LmsScenario,
  ModuleKind,
  QuestionKind,
  SystemLogEntry,
  TaskCategory,
  TestConfig,
  TrainingTask,
  Difficulty,
} from './types';

const API = '';

export interface AuthUser {
  id: number;
  username: string;
  full_name: string;
  is_active: boolean;
  roles: string[];
  permissions: string[];
}

export interface RoleInfo {
  code: string;
  name: string;
  description: string;
  permissions: string[];
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: AuthUser;
}

const TOKEN_KEY = 'elou_avt_token';

export const authStore = {
  getToken: () => localStorage.getItem(TOKEN_KEY),
  setToken: (t: string | null) =>
    t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY),
};

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const token = authStore.getToken();
  const headers = new Headers(init?.headers);
  if (!headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const res = await fetch(url, { ...init, headers });
  if (res.status === 401) authStore.setToken(null);
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
  return res.json() as Promise<T>;
}

function wsUrl(): string {
  const token = authStore.getToken() ?? '';
  const base = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/simulation`;
  return token ? `${base}?token=${encodeURIComponent(token)}` : base;
}

export const api = {
  login: (username: string, password: string) =>
    json<LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),

  getMe: () => json<AuthUser>('/auth/me'),

  listUsers: () => json<AuthUser[]>('/auth/users'),
  listRoles: () => json<RoleInfo[]>('/auth/roles'),
  createUser: (username: string, password: string, fullName: string, roles: string[]) =>
    json<AuthUser>('/auth/users', {
      method: 'POST',
      body: JSON.stringify({ username, password, full_name: fullName, role_codes: roles }),
    }),
  assignRoles: (userId: number, roles: string[]) =>
    json<AuthUser>(`/auth/users/${userId}/roles`, {
      method: 'POST',
      body: JSON.stringify({ role_codes: roles }),
    }),
  deactivateUser: (userId: number) =>
    json<{ ok: boolean }>(`/auth/users/${userId}/deactivate`, { method: 'POST' }),

  getState: () => json<ApiState>('/state'),
  getHistory: (limit = 600) => json<HistoryResponse>(`/history?limit=${limit}`),
  getScheme: () => json<Scheme>('/scheme'),

  listSchemes: () => json<{ current: string; schemes: string[] }>('/schemes'),

  loadScheme: (name: string) =>
    json<ApiState>('/scheme/load', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    }),

  saveScheme: (nodes: SchemeNodeData[], edges: SchemeEdgeData[]) =>
    json<ApiState>('/scheme', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nodes, edges }),
    }),

  createScheme: (name: string) =>
    json<ApiState>('/scheme/new', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    }),

  action: (equipmentId: string, actionType: string, value?: number | null) =>
    json<ApiState>('/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ equipment_id: equipmentId, action_type: actionType, value: value ?? null }),
    }),

  setInput: (partial: { flow_kg_s?: number; temperature_c?: number; pressure_bar?: number }) =>
    json<ApiState>('/input', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(partial),
    }),

  injectFailure: (equipmentId: string) => json<ApiState>(`/failure/${equipmentId}`, { method: 'POST' }),

  getEquipmentSpec: (nodeId: string) => json<EquipmentSpec>(`/equipment/spec/${nodeId}`),

  updateEquipmentParams: (equipmentId: string, params: Record<string, number>) =>
    json<ApiState>('/equipment/params', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ equipment_id: equipmentId, params }),
    }),

  startScenario: (scenarioId: string) =>
    json<ApiState>('/scenario/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario_id: scenarioId }),
    }),

  startTrainingSession: (scenarioId: string, operatorId = 'demo') =>
    json<{ session_id: string; scenario_id: string; status: string }>('/training/session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario_id: scenarioId, operator_id: operatorId }),
    }),

  finishTrainingSession: () =>
    json<{ session_id: string; status: string; performance_score?: number | null }>('/training/session/finish', {
      method: 'POST',
    }),

  resetScenario: () => json<ApiState>('/scenario/reset', { method: 'POST' }),

  step: () => json<ApiState>('/scenario/step', { method: 'POST' }),

  command: (tag: string, action: string, value?: number | string | null) =>
    json<{ ok: boolean; controller: ControllerSnap }>('/command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tag, action, value: value ?? null, operator_id: 'hmi' }),
    }),

  // ---- LMS: оператор ----
  lmsDashboard: () => json<LmsDashboard>('/lms/dashboard'),
  lmsProfile: () => json<LmsProfile>('/lms/profile'),
  lmsCourses: () => json<LmsCourse[]>('/lms/courses'),
  lmsCourse: (id: number) => json<LmsCourse>(`/lms/courses/${id}`),
  lmsCompetencies: () => json<import('./types').LmsCompetency[]>('/lms/competencies'),
  lmsHistory: (limit = 200) => json<LmsHistoryRow[]>(`/lms/history?limit=${limit}`),
  lmsDebrief: (sessionId: string) => json<LmsDebrief>(`/lms/sessions/${sessionId}/debrief`),
  lmsPracticeTasks: (includeExam = true) =>
    json<LmsPracticeTask[]>(`/lms/practice-tasks?include_exam=${includeExam}`),
  lmsPracticeTask: (id: number) => json<LmsPracticeTask>(`/lms/practice-tasks/${id}`),
  lmsPracticeCatalog: () => json<LmsPracticeTask[]>('/lms/practice-library'),
  lmsPracticeCatalogTask: (id: number) => json<LmsPracticeTask>(`/lms/practice-library/${id}`),
  lmsScenarios: () => json<LmsScenario[]>('/lms/scenarios'),
  lmsModuleTheory: (moduleId: number) =>
    json<{ ok: boolean }>(`/lms/modules/${moduleId}/theory`, { method: 'POST' }),

  // ---- LMS: инструктор ----
  lmsGroups: () => json<LmsGroup[]>('/lms/groups'),
  lmsGroup: (id: number) => json<LmsGroupView>(`/lms/groups/${id}`),
  lmsCreateGroup: (name: string, description: string, courseId: number | null) =>
    json<LmsGroup>('/lms/groups', {
      method: 'POST',
      body: JSON.stringify({ name, description, course_id: courseId }),
    }),
  lmsSetGroupMembers: (id: number, userIds: number[]) =>
    json<{ ok: boolean }>(`/lms/groups/${id}/members`, {
      method: 'PUT',
      body: JSON.stringify({ user_ids: userIds }),
    }),
  lmsAnalytics: () => json<LmsAnalytics>('/lms/analytics'),
  lmsMonitoring: () => json<LmsMonitorOperator[]>('/lms/monitoring'),

  // ---- LMS: администратор ----
  lmsSettings: () => json<Record<string, string>>('/lms/settings'),
  lmsUpdateSettings: (values: Record<string, string>) =>
    json<{ ok: boolean }>('/lms/settings', { method: 'PUT', body: JSON.stringify({ values }) }),
  lmsLogs: (limit = 200) => json<SystemLogEntry[]>(`/lms/logs?limit=${limit}`),
  lmsCreateCourse: (title: string, description: string) =>
    json<LmsCourse>('/lms/courses', {
      method: 'POST',
      body: JSON.stringify({ title, description }),
    }),
  lmsUpdateCourse: (id: number, patch: { title?: string; description?: string; status?: string }) =>
    json<LmsCourse>(`/lms/courses/${id}`, { method: 'PUT', body: JSON.stringify(patch) }),
  lmsAddModule: (
    courseId: number,
    module: {
      kind: ModuleKind;
      title: string;
      description?: string;
      content?: string;
      scenario_id?: string | null;
      practice_task_id?: number | null;
    },
  ) =>
    json<unknown>(`/lms/courses/${courseId}/modules`, {
      method: 'POST',
      body: JSON.stringify(module),
    }),
  lmsRemoveModule: (courseId: number, moduleId: number) =>
    json<{ ok: boolean }>(`/lms/courses/${courseId}/modules/${moduleId}`, { method: 'DELETE' }),
  lmsCreateTask: (
    task: {
      title: string;
      description?: string;
      scenario_id: string;
      category: TaskCategory;
      difficulty: Difficulty;
      duration_min: number;
      required_competencies?: string[];
      is_random?: boolean;
      enabled?: boolean;
    },
  ) =>
    json<LmsPracticeTask>('/lms/practice-tasks', {
      method: 'POST',
      body: JSON.stringify(task),
    }),
  lmsUpdateTask: (
    id: number,
    patch: { title?: string; description?: string; scenario_id?: string; category?: TaskCategory; difficulty?: Difficulty; duration_min?: number; required_competencies?: string[]; is_random?: boolean; enabled?: boolean },
  ) => json<LmsPracticeTask>(`/lms/practice-tasks/${id}`, { method: 'PUT', body: JSON.stringify(patch) }),

  // ---- LMS: конструктор (авторство контента) ----
  lmsAuthoringModule: (id: number) => json<ModuleAuthoringView>(`/lms/authoring/modules/${id}`),
  lmsAuthoringEquipment: () => json<EquipmentItem[]>('/lms/authoring/equipment'),
  lmsPublishModule: (id: number, published = true) =>
    json<ModuleAuthoringView>(`/lms/modules/${id}/publish`, {
      method: 'POST',
      body: JSON.stringify({ published }),
    }),

  lmsCreateLesson: (
    moduleId: number,
    lesson: { title: string; blocks?: LessonBlock[]; equipment_ids?: string[]; competency_codes?: string[] },
  ) =>
    json<Lesson>(`/lms/modules/${moduleId}/lessons`, {
      method: 'POST',
      body: JSON.stringify(lesson),
    }),
  lmsUpdateLesson: (
    id: number,
    lesson: { title: string; blocks?: LessonBlock[]; equipment_ids?: string[]; competency_codes?: string[] },
  ) => json<Lesson>(`/lms/lessons/${id}`, { method: 'PUT', body: JSON.stringify(lesson) }),
  lmsDeleteLesson: (id: number) => json<{ ok: boolean }>(`/lms/lessons/${id}`, { method: 'DELETE' }),

  lmsSaveTest: (
    moduleId: number,
    test: { title: string; passing_score?: number; attempts?: number; retry_required?: boolean; shuffle?: boolean; competency_codes?: string[] },
  ) =>
    json<TestConfig>(`/lms/modules/${moduleId}/test`, {
      method: 'PUT',
      body: JSON.stringify(test),
    }),
  lmsDeleteTest: (id: number) => json<{ ok: boolean }>(`/lms/tests/${id}`, { method: 'DELETE' }),

  lmsCreateQuestion: (
    testId: number,
    q: { kind: QuestionKind; title: string; text?: string; options?: Record<string, unknown>[]; answer?: unknown; max_score?: number; penalty?: number; required?: boolean; hint?: string },
  ) =>
    json<Question>(`/lms/tests/${testId}/questions`, {
      method: 'POST',
      body: JSON.stringify(q),
    }),
  lmsUpdateQuestion: (
    id: number,
    q: { kind: QuestionKind; title: string; text?: string; options?: Record<string, unknown>[]; answer?: unknown; max_score?: number; penalty?: number; required?: boolean; hint?: string },
  ) => json<Question>(`/lms/questions/${id}`, { method: 'PUT', body: JSON.stringify(q) }),
  lmsDeleteQuestion: (id: number) => json<{ ok: boolean }>(`/lms/questions/${id}`, { method: 'DELETE' }),

  lmsSaveTask: (
    moduleId: number,
    task: {
      title: string;
      goal?: string;
      scenario_id?: string;
      duration_min?: number;
      initial_state?: Record<string, unknown>;
      target_state?: Record<string, unknown>[];
      restrictions?: Record<string, unknown>[];
      criteria?: Record<string, unknown>[];
      expected_actions?: Record<string, unknown>[];
      critical_errors?: Record<string, unknown>[];
      competency_codes?: string[];
      equipment_ids?: string[];
      enabled?: boolean;
    },
  ) =>
    json<TrainingTask>(`/lms/modules/${moduleId}/task`, {
      method: 'PUT',
      body: JSON.stringify(task),
    }),
  lmsDeleteTask: (id: number) => json<{ ok: boolean }>(`/lms/tasks/${id}`, { method: 'DELETE' }),

  lmsSaveScenario: (
    moduleId: number,
    sc: {
      title: string;
      description?: string;
      goal?: string;
      initial_state?: Record<string, unknown>;
      events?: Record<string, unknown>[];
      expected_actions?: Record<string, unknown>[];
      success_criteria?: Record<string, unknown>[];
      critical_errors?: Record<string, unknown>[];
      final_state?: Record<string, unknown>;
      competency_codes?: string[];
      equipment_ids?: string[];
      duration_min?: number;
      is_exam?: boolean;
    },
  ) =>
    json<ScenarioDefinition>(`/lms/modules/${moduleId}/scenario`, {
      method: 'PUT',
      body: JSON.stringify(sc),
    }),
  lmsDeleteScenario: (id: number) => json<{ ok: boolean }>(`/lms/scenarios/${id}`, { method: 'DELETE' }),
  lmsSetScenarioStatus: (id: number, status: ScenarioStatus) =>
    json<ScenarioDefinition>(`/lms/scenarios/${id}/status`, {
      method: 'POST',
      body: JSON.stringify({ status }),
    }),

  // ---- LMS: оператор (прохождение модуля) ----
  lmsModuleStudy: (id: number) => json<ModuleStudy>(`/lms/modules/${id}/study`),
  lmsSubmitTest: (testId: number, answers: Record<string, unknown>, duration_s = 0) =>
    json<AssessmentView>(`/lms/tests/${testId}/submit`, {
      method: 'POST',
      body: JSON.stringify({ answers, duration_s }),
    }),
  lmsPracticeStart: (moduleId: number) =>
    json<PracticeStartResult>(`/lms/modules/${moduleId}/practice/start`, { method: 'POST' }),
  lmsPracticeReady: (sessionId: string) =>
    json<{ session_id: string; status: string; sim_time: number }>(`/lms/practice/${sessionId}/ready`, { method: 'POST' }),
  lmsPracticeFinish: (sessionId: string) =>
    json<AssessmentView>(`/lms/practice/${sessionId}/finish`, { method: 'POST' }),

  // ---- SCADA: журнал кликов и времени в окне ----
  logScadaEvent: (ev: { event_type: ScadaLogEventType; object_id?: string; object_name?: string; duration_s?: number | null }) =>
    json<{ ok: boolean }>('/lms/scada-log', {
      method: 'POST',
      keepalive: true,
      body: JSON.stringify({
        event_type: ev.event_type,
        object_id: ev.object_id ?? '',
        object_name: ev.object_name ?? '',
        duration_s: ev.duration_s ?? null,
      }),
    }),
};

export function connectWs(onState: (s: ApiState) => void): () => void {
  let ws: WebSocket | null = null;
  let retry = 0;

  const open = () => {
    ws = new WebSocket(wsUrl());
    ws.onmessage = (e) => {
      try {
        onState(JSON.parse(e.data as string) as ApiState);
      } catch {
        /* ignore malformed frame */
      }
    };
    ws.onclose = () => {
      retry += 1;
      if (retry < 5) setTimeout(open, 2000 * retry);
    };
    ws.onopen = () => (retry = 0);
  };

  open();
  return () => ws?.close();
}
