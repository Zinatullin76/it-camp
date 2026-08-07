import { api } from '../../api';
import type { LmsCompetency } from '../../types';
import { Bar, Card, Empty, Err, Grid, Loader, Page, useAsync } from '../../lms/ui';

function toneOf(v: number) {
  return v >= 80 ? 'ok' : v >= 50 ? 'warn' : 'bad';
}

export default function CompetenciesPage() {
  const { data, error, loading, reload } = useAsync<LmsCompetency[]>(() => api.lmsCompetencies(), []);

  if (loading && !data) return <Loader />;
  if (error && !data) return <Err text={error} />;

  const list = data ?? [];

  return (
    <Page
      title="Мои компетенции"
      subtitle="Профессиональный профиль — карта освоения компетенций оператора"
      actions={<button className="btn" onClick={() => void reload()}>Обновить</button>}
    >
      {list.length === 0 ? (
        <Card><Empty text="Компетенции ещё не развиты. Пройдите практику, чтобы сформировать профиль." /></Card>
      ) : (
        <Grid min={360}>
          {list.map((c) => (
            <Card key={c.code}>
              <div className="row-between">
                <div>
                  <div className="card-title" style={{ marginBottom: 4 }}>{c.title}</div>
                  <div className="muted" style={{ fontSize: 11 }}>{c.code}</div>
                </div>
                <span className="bold num" style={{ fontSize: 22, color: 'var(--text)' }}>
                  {c.level_percent.toFixed(0)}%
                </span>
              </div>
              <div style={{ marginTop: 12 }}>
                <Bar value={c.level_percent} tone={toneOf(c.level_percent)} height={10} />
              </div>
              {c.description && <div className="muted" style={{ fontSize: 11, marginTop: 8 }}>{c.description}</div>}
            </Card>
          ))}
        </Grid>
      )}
    </Page>
  );
}
