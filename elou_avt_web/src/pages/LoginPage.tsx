import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth';
import { useTheme } from '../lms/theme';

const DEMO: { username: string; label: string }[] = [
  { username: 'operator', label: 'Консольный оператор' },
  { username: 'field_operator', label: 'Полевой оператор' },
  { username: 'instructor', label: 'Инструктор' },
  { username: 'admin', label: 'Администратор' },
];

export default function LoginPage() {
  const { login } = useAuth();
  const { toggle } = useTheme();
  const navigate = useNavigate();
  const location = useLocation() as { state?: { from?: { pathname?: string } } };
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const doLogin = async (u: string, p: string) => {
    setError('');
    setBusy(true);
    try {
      await login(u, p);
      const from = location.state?.from?.pathname ?? '/';
      navigate(from, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка входа');
    } finally {
      setBusy(false);
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    await doLogin(username.trim(), password);
  };

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={submit}>
        <div className="row-between">
          <span />
          <button type="button" className="theme-toggle" onClick={toggle}>◐ Тема</button>
        </div>
        <div className="login-logo">Э</div>
        <div className="login-title">ЭЛОУ-АВТ Тренажер</div>
        <div className="login-sub">Компьютерный тренажерный комплекс · вход в систему</div>
        {error && <div className="login-error">{error}</div>}
        <div className="form-field">
          <label className="form-label" htmlFor="username">Логин</label>
          <input
            id="username"
            className="form-input"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoFocus
          />
        </div>
        <div className="form-field">
          <label className="form-label" htmlFor="password">Пароль</label>
          <input
            id="password"
            type="password"
            className="form-input"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <button className="btn btn-start" type="submit" disabled={busy}>
          {busy ? 'Вход…' : 'Войти'}
        </button>
        <div className="login-sub" style={{ marginTop: 4 }}>Демо-доступ (пароль = логин):</div>
        <div className="login-quick">
          {DEMO.map((d) => (
            <span
              key={d.username}
              className={`picker-chip${username === d.username ? ' on' : ''}`}
              onClick={() => {
                setUsername(d.username);
                setPassword(d.username);
              }}
            >
              {d.label}
            </span>
          ))}
        </div>
      </form>
    </div>
  );
}
