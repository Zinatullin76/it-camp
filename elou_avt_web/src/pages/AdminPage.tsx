import { useCallback, useEffect, useState } from 'react';
import { api, type AuthUser, type RoleInfo } from '../api';
import { ROLE_LABELS } from '../auth';

const ALL_ROLE_CODES = Object.keys(ROLE_LABELS);

export default function AdminPage() {
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [roles, setRoles] = useState<RoleInfo[]>([]);
  const [error, setError] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [newRoles, setNewRoles] = useState<string[]>(['operator']);

  const reload = useCallback(async () => {
    try {
      const [u, r] = await Promise.all([api.listUsers(), api.listRoles()]);
      setUsers(u);
      setRoles(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось загрузить данные');
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const toggleNewRole = (code: string) =>
    setNewRoles((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code],
    );

  const createUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      await api.createUser(username.trim(), password, fullName.trim(), newRoles);
      setUsername('');
      setPassword('');
      setFullName('');
      setNewRoles(['operator']);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка создания пользователя');
    }
  };

  const assignRoles = async (userId: number, roles: string[]) => {
    try {
      await api.assignRoles(userId, roles);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка смены ролей');
    }
  };

  const deactivate = async (userId: number) => {
    try {
      await api.deactivateUser(userId);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка деактивации');
    }
  };

  const toggleUserRole = (userId: number, code: string, current: string[]) =>
    assignRoles(
      userId,
      current.includes(code) ? current.filter((c) => c !== code) : [...current, code],
    );

  return (
    <div className="admin-wrap">
      <div className="admin">
        <div className="dash-hero">
          <div>
            <div className="dash-hero-title">Администрирование</div>
            <div className="dash-empty">Управление пользователями и ролями (RBAC)</div>
          </div>
        </div>

        {error && <div className="login-error">{error}</div>}

        <div className="admin-grid">
          <div className="dash-card">
            <div className="dash-card-title">Пользователи · {users.length}</div>
            {users.length === 0 && <div className="dash-empty">Загрузка…</div>}
            {users.map((u) => (
              <div className="user-row" key={u.id}>
                <span
                  className="status-dot"
                  style={{ background: u.is_active ? 'var(--ok)' : 'var(--danger)' }}
                  title={u.is_active ? 'активен' : 'деактивирован'}
                />
                <span className="user-name">{u.username}</span>
                <span className="user-meta">
                  {u.full_name && <span>{u.full_name}</span>}
                  {u.roles.map((r) => (
                    <span className="perm-tag on" key={r}>
                      {ROLE_LABELS[r] ?? r}
                    </span>
                  ))}
                </span>
                <div className="picker" style={{ maxWidth: 320 }}>
                  {ALL_ROLE_CODES.map((code) => {
                    const on = u.roles.includes(code);
                    return (
                      <span
                        key={code}
                        className={`picker-chip${on ? ' on' : ''}`}
                        onClick={() => toggleUserRole(u.id, code, u.roles)}
                      >
                        {ROLE_LABELS[code]}
                      </span>
                    );
                  })}
                </div>
                {u.is_active && u.username !== 'admin' && (
                  <button className="btn btn-danger" onClick={() => deactivate(u.id)}>
                    Деактивировать
                  </button>
                )}
              </div>
            ))}
          </div>

          <div className="dash-card">
            <div className="dash-card-title">Создать пользователя</div>
            <form className="param-editor" onSubmit={createUser}>
              <div className="form-field">
                <label className="form-label">Логин</label>
                <input
                  className="form-input"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                />
              </div>
              <div className="form-field">
                <label className="form-label">Пароль</label>
                <input
                  className="form-input"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>
              <div className="form-field">
                <label className="form-label">ФИО</label>
                <input
                  className="form-input"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                />
              </div>
              <div className="form-field">
                <span className="form-label">Роли</span>
                <div className="picker">
                  {ALL_ROLE_CODES.map((code) => (
                    <span
                      key={code}
                      className={`picker-chip${newRoles.includes(code) ? ' on' : ''}`}
                      onClick={() => toggleNewRole(code)}
                    >
                      {ROLE_LABELS[code]}
                    </span>
                  ))}
                </div>
              </div>
              <button className="btn btn-start" type="submit">
                Создать
              </button>
            </form>
          </div>
        </div>

        <div className="dash-card">
          <div className="dash-card-title">Роли и права</div>
          {roles.map((r) => (
            <div className="user-row" key={r.code}>
              <span className="user-name">{r.name}</span>
              <span className="user-meta">{r.description}</span>
              <span className="user-meta" style={{ flex: 0, maxWidth: 380 }}>
                {r.permissions.map((p) => (
                  <span className="perm-tag" key={p}>
                    {p}
                  </span>
                ))}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
