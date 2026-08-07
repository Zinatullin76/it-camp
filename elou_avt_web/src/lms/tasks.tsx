import { useNavigate } from 'react-router-dom';
import type { LmsPracticeTask } from '../types';
import { Bar, Chip, DifficultyTag, Empty, Grid, KindTag } from './ui';

export function TaskCards({ tasks }: { tasks: LmsPracticeTask[] }) {
  const navigate = useNavigate();

  if (tasks.length === 0) return <Empty text="Заданий пока нет" />;

  return (
    <Grid min={300}>
      {tasks.map((t) => (
        <div className="card task-card" key={t.id}>
          <div className="task-card-head">
            <div>
              <div className="task-card-title">{t.title}</div>
              <div className="muted" style={{ marginTop: 2 }}>{t.scenario_name || t.scenario_id}</div>
            </div>
            <Chip tone={t.is_random ? 'warn' : 'ok'}>{t.is_random ? 'Случайное' : t.category === 'exam' ? 'Экзамен' : 'Практика'}</Chip>
          </div>
          <div className="task-card-desc">{t.description || 'Практическое задание на тренажёре.'}</div>
          <div className="task-tags">
            <DifficultyTag d={t.difficulty} />
            <Chip>⏱ {t.duration_min} мин</Chip>
            {t.required_competencies.map((c) => (
              <Chip key={c}>{c}</Chip>
            ))}
          </div>
          <div className="col" style={{ gap: 4 }}>
            <div className="row-between">
              <span className="muted" style={{ fontSize: 11 }}>Готовность по компетенциям</span>
              <span className="bold num" style={{ fontSize: 11 }}>{t.readiness_percent.toFixed(0)}%</span>
            </div>
            <Bar value={t.readiness_percent} tone={t.is_ready ? 'ok' : 'warn'} height={7} />
          </div>
          <div className="task-card-foot">
            <span className="muted" style={{ fontSize: 11 }}>
              {t.is_ready ? 'Вы готовы к выполнению' : 'Рекомендуется повторить теорию'}
            </span>
            <button
              className={`btn ${t.category === 'exam' ? 'btn-danger' : 'btn-start'}`}
              onClick={() => navigate(`/run/${t.id}${t.category === 'exam' ? '?kind=exam' : ''}`)}
            >
              {t.category === 'exam' ? 'Пройти экзамен' : 'Начать задание'}
            </button>
          </div>
        </div>
      ))}
    </Grid>
  );
}
