import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Navigate, NavLink, Outlet, Route, Routes } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import { AuthProvider, RequireAuth, RequirePermission, ROLE_LABELS, useAuth } from './auth';
import { ThemeProvider } from './lms/theme';

// ---- Кабинет оператора ----
import OperatorHomePage from './pages/operator/HomePage';
import CoursesPage from './pages/operator/CoursesPage';
import PracticePage from './pages/operator/PracticePage';
import ExamsPage from './pages/operator/ExamsPage';
import CompetenciesPage from './pages/operator/CompetenciesPage';
import HistoryPage from './pages/operator/HistoryPage';
import ProfilePage from './pages/operator/ProfilePage';
import ModuleStudyPage from './pages/operator/ModuleStudyPage';

// ---- Кабинет инструктора ----
import InstructorHomePage from './pages/instructor/HomePage';
import InstructorGroupsPage from './pages/instructor/GroupsPage';
import GroupDetailPage from './pages/instructor/GroupDetailPage';
import InstructorCoursesPage from './pages/instructor/CoursesPage';
import InstructorTasksPage from './pages/instructor/TasksPage';
import MonitoringPage from './pages/instructor/MonitoringPage';
import AnalyticsPage from './pages/instructor/AnalyticsPage';
import ReportsPage from './pages/instructor/ReportsPage';
import ModuleConstructorPage from './pages/instructor/ModuleConstructorPage';

// ---- Кабинет администратора ----
import AdminUsersPage from './pages/admin/UsersPage';
import RolesPage from './pages/admin/RolesPage';
import AdminGroupsPage from './pages/admin/GroupsPage';
import AdminCoursesPage from './pages/admin/CoursesPage';
import AdminTasksPage from './pages/admin/TasksPage';
import AdminScenariosPage from './pages/admin/ScenariosPage';
import SettingsPage from './pages/admin/SettingsPage';
import LogsPage from './pages/admin/LogsPage';

// ---- Общие ----
import PracticeRunner from './pages/PracticeRunner';
import DebriefPage from './pages/DebriefPage';
import HmiPage from './pages/HmiPage';

import './index.css';

interface NavItem {
  to: string;
  label: string;
  ico: string;
}

const OPERATOR_NAV: NavItem[] = [
  { to: '/', label: 'Главная', ico: '⌂' },
  { to: '/courses', label: 'Мои курсы', ico: '▤' },
  { to: '/practice', label: 'Практика', ico: '▶' },
  { to: '/exams', label: 'Экзамены', ico: '✎' },
  { to: '/competencies', label: 'Мои компетенции', ico: '◍' },
  { to: '/history', label: 'История', ico: '☷' },
  { to: '/profile', label: 'Профиль', ico: '◉' },
];

const FIELD_OPERATOR_NAV: NavItem[] = [
  { to: '/', label: 'Главная', ico: '⌂' },
  { to: '/courses', label: 'Мои курсы', ico: '▤' },
  { to: '/practice', label: 'Практика', ico: '▶' },
  { to: '/exams', label: 'Экзамены', ico: '✎' },
  { to: '/competencies', label: 'Мои компетенции', ico: '◍' },
  { to: '/history', label: 'История', ico: '☷' },
  { to: '/profile', label: 'Профиль', ico: '◉' },
];

const INSTRUCTOR_NAV: NavItem[] = [
  { to: '/instructor', label: 'Главная', ico: '⌂' },
  { to: '/instructor/groups', label: 'Группы', ico: '▦' },
  { to: '/instructor/courses', label: 'Курсы · конструктор', ico: '▤' },
  { to: '/instructor/tasks', label: 'Практические задания', ico: '▣' },
  { to: '/instructor/reports', label: 'Отчёты по практике', ico: '☰' },
  { to: '/instructor/monitoring', label: 'Мониторинг', ico: '◉' },
  { to: '/instructor/analytics', label: 'Аналитика', ico: '◔' },
];

const ADMIN_NAV: NavItem[] = [
  { to: '/admin/users', label: 'Пользователи', ico: '◈' },
  { to: '/admin/roles', label: 'Роли', ico: '◐' },
  { to: '/admin/groups', label: 'Группы', ico: '▦' },
  { to: '/admin/courses', label: 'Курсы', ico: '▤' },
  { to: '/admin/tasks', label: 'Задания', ico: '▣' },
  { to: '/admin/scenarios', label: 'Сценарии', ico: '▸' },
  { to: '/admin/settings', label: 'Настройки', ico: '☰' },
  { to: '/admin/logs', label: 'Журнал системы', ico: '☷' },
];

type Cabinet = 'admin' | 'instructor' | 'operator' | 'field';

function cabinetOf(permissions: string[]): Cabinet {
  if (permissions.includes('manage_users')) return 'admin';
  if (
    permissions.includes('manage_groups') ||
    permissions.includes('view_analytics') ||
    permissions.includes('monitor_operators')
  ) {
    return 'instructor';
  }
  if (permissions.includes('view_field_operator_screen')) return 'field';
  return 'operator';
}

const CABINET_TITLE: Record<Cabinet, string> = {
  admin: 'Кабинет администратора',
  instructor: 'Кабинет инструктора',
  operator: 'Кабинет консольного оператора',
  field: 'Кабинет полевого оператора',
};

function SidebarNav() {
  const { user } = useAuth();
  const cabinet = cabinetOf(user?.permissions ?? []);
  const nav =
    cabinet === 'admin'
      ? ADMIN_NAV
      : cabinet === 'instructor'
        ? INSTRUCTOR_NAV
        : cabinet === 'field'
          ? FIELD_OPERATOR_NAV
          : OPERATOR_NAV;

  const items = [...nav];
  if (user?.permissions.includes('view_scheme') && !items.some((n) => n.to === '/hmi')) {
    items.push({ to: '/hmi', label: 'Тренажер · SCADA', ico: '◈' });
  }

  return (
    <>
      <div className="side-section">{CABINET_TITLE[cabinet]}</div>
      {items.map((n) => (
        <NavLink key={n.to} to={n.to} end={n.to === '/'} className={({ isActive }) => `side-link${isActive ? ' on' : ''}`}>
          <span className="side-ico">{n.ico}</span>
          <span>{n.label}</span>
        </NavLink>
      ))}
    </>
  );
}

function Shell() {
  const { user, logout } = useAuth();
  const roleLabel = (user?.roles ?? []).map((r) => ROLE_LABELS[r] ?? r).join(', ');
  const fullName = user?.full_name || user?.username || '';
  const initials = (fullName || '?').slice(0, 1).toUpperCase();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="side-brand">
          <div className="logo">Э</div>
          <div>
            <div className="side-brand-title">ОРБИТА</div>
            <div className="side-brand-sub">Образовательный портал</div>
          </div>
        </div>
        <nav className="side-nav">
          <SidebarNav />
        </nav>
        <div className="side-foot">
          <div className="side-user">
            <span className="avatar">{initials}</span>
            <div>
              <div className="side-user-name">{fullName}</div>
              <div className="side-user-role">{roleLabel}</div>
            </div>
          </div>
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <div className="topbar-title">{CABINET_TITLE[cabinetOf(user?.permissions ?? [])]}</div>
          <div className="topbar-right">
            <button className="btn" onClick={logout}>Выйти</button>
          </div>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function HomeRedirect() {
  const { user } = useAuth();
  const cabinet = cabinetOf(user?.permissions ?? []);
  if (cabinet === 'admin') return <Navigate to="/admin/users" replace />;
  if (cabinet === 'instructor') return <Navigate to="/instructor" replace />;
  return <Navigate to="/" replace />;
}

function RootPage() {
  const { user } = useAuth();
  const cabinet = cabinetOf(user?.permissions ?? []);
  if (cabinet === 'admin') return <Navigate to="/admin/users" replace />;
  if (cabinet === 'instructor') return <Navigate to="/instructor" replace />;
  return <OperatorHomePage />;
}

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <ThemeProvider>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route element={<RequireAuth><Shell /></RequireAuth>}>
              <Route path="/" element={<RootPage />} />
              <Route path="/courses" element={<RequirePermission permissions={['view_courses']}><CoursesPage /></RequirePermission>} />
              <Route path="/practice" element={<RequirePermission permissions={['view_courses']}><PracticePage /></RequirePermission>} />
              <Route path="/exams" element={<RequirePermission permissions={['view_courses']}><ExamsPage /></RequirePermission>} />
              <Route path="/competencies" element={<RequirePermission permissions={['view_competencies']}><CompetenciesPage /></RequirePermission>} />
              <Route path="/history" element={<RequirePermission permissions={['view_history']}><HistoryPage /></RequirePermission>} />
              <Route path="/profile" element={<RequirePermission permissions={['view_profile']}><ProfilePage /></RequirePermission>} />
              <Route path="/run/:taskId" element={<RequirePermission permissions={['view_courses']}><PracticeRunner /></RequirePermission>} />
              <Route path="/debrief/:sessionId" element={<RequirePermission permissions={['view_history']}><DebriefPage /></RequirePermission>} />
              <Route path="/study/:moduleId" element={<RequirePermission permissions={['view_courses']}><ModuleStudyPage /></RequirePermission>} />

              <Route path="/instructor" element={<RequirePermission permissions={['view_analytics', 'view_group_progress']}><InstructorHomePage /></RequirePermission>} />
              <Route path="/instructor/groups" element={<RequirePermission permissions={['view_group_progress']}><InstructorGroupsPage /></RequirePermission>} />
              <Route path="/instructor/groups/:groupId" element={<RequirePermission permissions={['view_group_progress']}><GroupDetailPage /></RequirePermission>} />
              <Route path="/instructor/tasks" element={<RequirePermission permissions={['view_group_progress', 'manage_practice_tasks']}><InstructorTasksPage /></RequirePermission>} />
              <Route path="/instructor/monitoring" element={<RequirePermission permissions={['monitor_operators']}><MonitoringPage /></RequirePermission>} />
              <Route path="/instructor/analytics" element={<RequirePermission permissions={['view_analytics']}><AnalyticsPage /></RequirePermission>} />
              <Route path="/instructor/reports" element={<RequirePermission permissions={['view_training_sessions']}><ReportsPage /></RequirePermission>} />
              <Route path="/instructor/reports/:sessionId" element={<RequirePermission permissions={['view_training_sessions']}><DebriefPage mode="instructor" /></RequirePermission>} />
              <Route path="/instructor/modules/:moduleId" element={<RequirePermission permissions={['manage_courses']}><ModuleConstructorPage /></RequirePermission>} />
              <Route path="/instructor/courses" element={<RequirePermission permissions={['manage_courses', 'view_courses']}><InstructorCoursesPage /></RequirePermission>} />

              <Route path="/admin/users" element={<RequirePermission permissions={['manage_users']}><AdminUsersPage /></RequirePermission>} />
              <Route path="/admin/roles" element={<RequirePermission permissions={['manage_users']}><RolesPage /></RequirePermission>} />
              <Route path="/admin/groups" element={<RequirePermission permissions={['manage_users', 'manage_groups']}><AdminGroupsPage /></RequirePermission>} />
              <Route path="/admin/courses" element={<RequirePermission permissions={['manage_courses']}><AdminCoursesPage /></RequirePermission>} />
              <Route path="/admin/tasks" element={<RequirePermission permissions={['manage_practice_tasks']}><AdminTasksPage /></RequirePermission>} />
              <Route path="/admin/scenarios" element={<RequirePermission permissions={['manage_courses']}><AdminScenariosPage /></RequirePermission>} />
              <Route path="/admin/settings" element={<RequirePermission permissions={['manage_settings']}><SettingsPage /></RequirePermission>} />
              <Route path="/admin/logs" element={<RequirePermission permissions={['view_logs']}><LogsPage /></RequirePermission>} />

              <Route path="/field" element={<HomeRedirect />} />

              <Route path="/hmi" element={<RequirePermission permissions={['view_scheme']}><HmiPage /></RequirePermission>} />
              <Route path="*" element={<HomeRedirect />} />
            </Route>
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  </React.StrictMode>,
);
