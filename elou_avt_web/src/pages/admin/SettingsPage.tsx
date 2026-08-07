import { useState } from 'react';
import { api } from '../../api';
import { Card, Empty, Err, Loader, Page, notifyToast, useAsync } from '../../lms/ui';

const LABELS: Record<string, string> = {
  system_name: 'Название системы',
  system_sub: 'Подзаголовок системы',
  min_pass_score: 'Проходной балл (занятие)',
  exam_pass_score: 'Проходной балл (экзамен)',
  mastery_threshold_stage_2: 'Порог этапа «Оператор»',
  mastery_threshold_stage_3: 'Порог этапа «Оператор 2 категории»',
  mastery_threshold_stage_4: 'Порог этапа «Оператор 1 категории»',
  mastery_threshold_stage_5: 'Порог этапа «Старший оператор»',
  notify_on_practice: 'Уведомлять о завершении практики',
};

export default function SettingsPage() {
  const { data, error, loading, reload } = useAsync<Record<string, string>>(() => api.lmsSettings(), []);
  const [draft, setDraft] = useState<Record<string, string> | null>(null);

  const save = async () => {
    if (!draft) return;
    try {
      await api.lmsUpdateSettings(draft);
      notifyToast('Настройки сохранены');
      setDraft(null);
      await reload();
    } catch (err) {
      notifyToast(`Ошибка: ${err instanceof Error ? err.message : err}`);
    }
  };

  if (loading && !data) return <Loader />;
  if (error && !data) return <Err text={error} />;
  if (!data) return <Empty />;

  const current = draft ?? data;

  return (
    <Page
      title="Настройки системы"
      subtitle="Ключевые параметры КТК"
      actions={
        <>
          <button className="btn" onClick={() => void reload()}>Сбросить</button>
          <button className="btn btn-start" disabled={!draft} onClick={() => void save()}>Сохранить</button>
        </>
      }
    >
      <Card title="Параметры">
        <div className="settings-grid">
          {Object.entries(current).map(([k, v]) => (
            <div className="form-field" key={k}>
              <label className="form-label">{LABELS[k] ?? k}</label>
              <input
                className="form-input"
                value={v}
                onChange={(e) => setDraft({ ...current, [k]: e.target.value })}
              />
            </div>
          ))}
        </div>
      </Card>
    </Page>
  );
}
