import { api } from '../../api';
import type { LmsProfile } from '../../types';
import { ROLE_LABELS } from '../../auth';
import {
  Bar,
  Card,
  Chip,
  Empty,
  Err,
  Grid,
  Loader,
  Page,
  Score,
  StageLadder,
  fmtDate,
  useAsync,
} from '../../lms/ui';

export default function ProfilePage() {
  const { data, error, loading, reload } = useAsync<LmsProfile>(() => api.lmsProfile(), []);

  if (loading && !data) return <Loader />;
  if (error && !data) return <Err text={error} />;
  if (!data) return <Empty />;

  const p = data;

  return (
    <Page title="Профиль" subtitle="Данные оператора и результаты подготовки" actions={
      <button className="btn" onClick={() => void reload()}>Обновить</button>
    }>
      <div className="hero-row">
        <div className="hero-main">
          <Card title="Личные данные">
            <div className="row" style={{ gap: 16 }}>
              <div
                className="avatar"
                style={{
                  width: 56,
                  height: 56,
                  borderRadius: '50%',
                  background: 'linear-gradient(135deg,#0ea5e9,#2563eb)',
                  color: '#fff',
                  fontSize: 22,
                  fontWeight: 800,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                {(p.full_name || p.username).slice(0, 1).toUpperCase()}
              </div>
              <div className="col" style={{ gap: 2 }}>
                <div style={{ fontSize: 17, fontWeight: 800, color: 'var(--text)' }}>{p.full_name || p.username}</div>
                <div className="muted">@{p.username}</div>
                <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
                  {p.roles.map((r) => (
                    <Chip key={r} tone="accent">{ROLE_LABELS[r] ?? r}</Chip>
                  ))}
                </div>
              </div>
            </div>
            <div className="muted" style={{ marginTop: 12, fontSize: 11 }}>
              Регистрация: {fmtDate(p.created_at)}
            </div>
          </Card>

          <Card title="Профессиональный статус">
            <StageLadder mastery={p.mastery} />
          </Card>

          <Card title="Компетенции">
            {p.competencies.length === 0 ? (
              <Empty text="Компетенции ещё не развиты" />
            ) : (
              <div className="col">
                {p.competencies.map((c) => (
                  <div key={c.code} className="col" style={{ gap: 3 }}>
                    <div className="row-between">
                      <span className="muted" style={{ fontSize: 12 }}>{c.title}</span>
                      <span className="bold num">{c.level_percent.toFixed(0)}%</span>
                    </div>
                    <Bar
                      value={c.level_percent}
                      tone={c.level_percent >= 80 ? 'ok' : c.level_percent >= 50 ? 'warn' : 'bad'}
                      height={8}
                    />
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        <div className="hero-side">
          <Card title="Индекс мастерства">
            <div style={{ display: 'flex', justifyContent: 'center' }}>
              <Score value={p.mastery.index} size={130} />
            </div>
          </Card>
          <Grid min={130}>
            <Card>
              <div className="card-title" style={{ marginBottom: 4 }}>Сессий</div>
              <div className="bold num" style={{ fontSize: 24 }}>{p.total_sessions}</div>
            </Card>
            <Card>
              <div className="card-title" style={{ marginBottom: 4 }}>Средний балл</div>
              <div className="bold num" style={{ fontSize: 24 }}>{p.avg_score.toFixed(1)}</div>
            </Card>
          </Grid>
          <Card title="Права доступа">
            <div className="col" style={{ gap: 4 }}>
              {p.permissions.map((perm) => (
                <div key={perm} className="muted mono" style={{ fontSize: 11 }}>{perm}</div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </Page>
  );
}
