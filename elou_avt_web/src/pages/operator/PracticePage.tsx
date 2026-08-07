import { api } from '../../api';
import type { LmsPracticeTask } from '../../types';
import { Err, Loader, Page, useAsync } from '../../lms/ui';
import { TaskCards } from '../../lms/tasks';

export default function PracticePage() {
  const { data, error, loading, reload } = useAsync<LmsPracticeTask[]>(
    () => api.lmsPracticeCatalog(),
    [],
  );

  if (loading && !data) return <Loader />;
  if (error && !data) return <Err text={error} />;

  const tasks = (data ?? []).filter((t) => t.category !== 'exam');

  return (
    <Page
      title="Практика"
      subtitle="Библиотека практических заданий на тренажёре. После выбора задания откроется полноэкранная SCADA."
      actions={<button className="btn" onClick={() => void reload()}>Обновить</button>}
    >
      <TaskCards tasks={tasks} />
    </Page>
  );
}
