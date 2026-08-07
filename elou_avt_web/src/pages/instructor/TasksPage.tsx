import { api } from '../../api';
import type { LmsPracticeTask } from '../../types';
import { Card, Chip, DifficultyTag, Empty, Err, Loader, Page, useAsync } from '../../lms/ui';

export default function InstructorTasksPage() {
  const { data, error, loading, reload } = useAsync<LmsPracticeTask[]>(() => api.lmsPracticeTasks(true), []);

  if (loading && !data) return <Loader />;
  if (error && !data) return <Err text={error} />;

  const tasks = data ?? [];

  return (
    <Page
      title="Практические задания"
      subtitle="Библиотека заданий тренажёра"
      actions={<button className="btn" onClick={() => void reload()}>Обновить</button>}
    >
      <Card>
        {tasks.length === 0 ? (
          <Empty text="Заданий нет" />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Задание</th>
                  <th>Сценарий</th>
                  <th>Категория</th>
                  <th>Сложность</th>
                  <th>Длительность</th>
                  <th>Компетенции</th>
                  <th>Случайное</th>
                  <th>Активно</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map((t) => (
                  <tr key={t.id}>
                    <td className="bold">{t.title}</td>
                    <td className="muted">{t.scenario_name || t.scenario_id}</td>
                    <td><Chip tone={t.category === 'exam' ? 'bad' : 'ok'}>{t.category}</Chip></td>
                    <td><DifficultyTag d={t.difficulty} /></td>
                    <td className="num">⏱ {t.duration_min} мин</td>
                    <td style={{ maxWidth: 280 }}>
                      <div className="row" style={{ gap: 4, flexWrap: 'wrap' }}>
                        {t.required_competencies.map((c) => (
                          <Chip key={c}>{c}</Chip>
                        ))}
                      </div>
                    </td>
                    <td><Chip tone={t.is_random ? 'warn' : 'muted'}>{t.is_random ? 'да' : 'нет'}</Chip></td>
                    <td><Chip tone={t.enabled ? 'ok' : 'bad'}>{t.enabled ? 'да' : 'нет'}</Chip></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </Page>
  );
}
