import { useState } from 'react';
import { api, type AuthUser } from '../../api';
import { ROLE_LABELS } from '../../auth';
import { Card, Err, Loader, Page, notifyToast, useAsync } from '../../lms/ui';

const ALL_ROLE_CODES = Object.keys(ROLE_LABELS);

export default function UsersPage() {
  const { data: users, error, loading, reload } = useAsync<AuthUser[]>(() => api.listUsers(), []);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [newRoles, setNewRoles] = useState<string[]>(['operator']);

  const toggleNewRole = (code: string) =>
    setNewRoles((prev) => (prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]));

  const createUser = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createUser(username.trim(), password, fullName.trim(), newRoles);
      notifyToast(`Пользователь «${username.trim()}» создан`);
      setUsername('');
      setPassword('');
      setFullName('');
      setNewRoles(['operator']);
      await reload();
    } catch (err) {
      notifyToast(`Ошибка: ${err instanceof Error ? err.message : err}`);
    }
  };

  const assignRoles = async (userId: number, roles: string[]) => {
    try {
      await api.assignRoles(userId, roles);
      await reload();
    } catch (err) {
      notifyToast(`Ошибка: ${err instanceof Error ? err.message : err}`);
    }
  };

  const toggleUserRole = (userId: number, code: string, current: string[]) =>
    void assignRoles(
      userId,
      current.includes(code) ? current.filter((c) => c !== code) : [...current, code],
    );

  const deactivate = async (userId: number) => {
    try {
      await api.deactivateUser(userId);
      notifyToast('Пользователь деактивирован');
      await reload();
    } catch (err) {
      notifyToast(`Ошибка: ${err instanceof Error ? err.message : err}`);
    }
  };

  if (loading && !users) return <Loader />;
  if (error && !users) return <Err text={error} />;

  const list = users ?? [];

  return (
    <Page
      title="Пользователи"
      subtitle="Создание пользователей и управление ролями (RBAC)"
      actions={<button className="btn" onClick={() => void reload()}>Обновить</button>}
    >
      <Card title={`Пользователи · ${list.length}`}>
        {list.length === 0 && <div className="empty">Загрузка…</div>}
        {list.map((u) => (
          <div className="row-between" key={u.id} style={{ padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
            <div className="row" style={{ minWidth: 0, flex: 1 }}>
              <span
                className="status-dot"
                style={{ background: u.is_active ? 'var(--ok)' : 'var(--danger)' }}
                title={u.is_active ? 'активен' : 'деактивирован'}
              />
              <div style={{ minWidth: 0 }}>
                <div className="bold">{u.username}</div>
                {u.full_name && <div className="muted" style={{ fontSize: 11 }}>{u.full_name}</div>}
              </div>
            </div>
            <div className="picker" style={{ maxWidth: 420 }}>
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
              <button className="btn btn-danger" onClick={() => void deactivate(u.id)}>
                Деактивировать
              </button>
            )}
          </div>
        ))}
      </Card>

      <Card title="Создать пользователя">
        <form className="row" onSubmit={createUser} style={{ alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div className="form-field">
            <label className="form-label">Логин</label>
            <input className="form-input" value={username} onChange={(e) => setUsername(e.target.value)} required />
          </div>
          <div className="form-field">
            <label className="form-label">Пароль</label>
            <input className="form-input" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </div>
          <div className="form-field">
            <label className="form-label">ФИО</label>
            <input className="form-input" value={fullName} onChange={(e) => setFullName(e.target.value)} />
          </div>
          <div className="form-field" style={{ flex: 1, minWidth: 200 }}>
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
          <button type="submit" className="btn btn-start">Создать</button>
        </form>
      </Card>
    </Page>
  );
}
