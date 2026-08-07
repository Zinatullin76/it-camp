import { api, type RoleInfo } from '../../api';
import { ROLE_LABELS } from '../../auth';
import { Card, Chip, Empty, Err, Loader, Page, useAsync } from '../../lms/ui';

export default function RolesPage() {
  const { data, error, loading, reload } = useAsync<RoleInfo[]>(() => api.listRoles(), []);

  if (loading && !data) return <Loader />;
  if (error && !data) return <Err text={error} />;

  const roles = data ?? [];

  return (
    <Page
      title="Роли"
      subtitle="Права доступа по ролям системы"
      actions={<button className="btn" onClick={() => void reload()}>Обновить</button>}
    >
      {roles.length === 0 ? (
        <Card><Empty text="Роли не найдены" /></Card>
      ) : (
        roles.map((r) => (
          <Card
            key={r.code}
            title={ROLE_LABELS[r.code] ?? r.name}
            subtitle={r.description || r.code}
            actions={<Chip tone="accent">{r.permissions.length} прав</Chip>}
          >
            <div className="row" style={{ gap: 5, flexWrap: 'wrap' }}>
              {r.permissions.map((p) => (
                <Chip key={p}>{p}</Chip>
              ))}
            </div>
          </Card>
        ))
      )}
    </Page>
  );
}
