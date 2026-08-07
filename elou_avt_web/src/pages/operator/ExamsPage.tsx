import { api } from '../../api';
import type { LmsPracticeTask } from '../../types';
import { Card, Empty, Err, Loader, Page, useAsync } from '../../lms/ui';
import { TaskCards } from '../../lms/tasks';

export default function ExamsPage() {
  const { data, error, loading, reload } = useAsync<LmsPracticeTask[]>(
    () => api.lmsPracticeCatalog(),
    [],
  );

  if (loading && !data) return <Loader />;
  if (error && !data) return <Err text={error} />;

  const exams = (data ?? []).filter((t) => t.category === 'exam');

  return (
    <Page
      title="Экзамены"
      subtitle="Итоговые проверочные задания. Экзамен фиксируется в истории и влияет на квалификацию."
      actions={<button className="btn" onClick={() => void reload()}>Обновить</button>}
    >
      {exams.length === 0 ? (
        <Card><Empty text="Экзамены не назначены" /></Card>
      ) : (
        <TaskCards tasks={exams} />
      )}
    </Page>
  );
}
