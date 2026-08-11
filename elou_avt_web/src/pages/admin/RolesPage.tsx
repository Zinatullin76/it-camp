import { useEffect, useState } from 'react';
import { api, type PermissionInfo, type RoleInfo } from '../../api';
import { Card, Chip, Empty, Err, Loader, Page, notifyToast, useAsync } from '../../lms/ui';

const BUILTIN_ROLES = ['administrator', 'instructor', 'operator', 'field_operator'];

export default function RolesPage() {
  const { data, error, loading, reload } = useAsync<RoleInfo[]>(() => api.listRoles(), []);
  const [permissions, setPermissions] = useState<PermissionInfo[]>([]);

  const [edits, setEdits] = useState<Record<string, { name: string; description: string }>>({});
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const [createCode, setCreateCode] = useState('');
  const [createName, setCreateName] = useState('');
  const [createDesc, setCreateDesc] = useState('');
  const [createPerms, setCreatePerms] = useState<string[]>([]);

  const loadPermissions = () =>
    api
      .listPermissions()
      .then(setPermissions)
      .catch(() => undefined);

  useEffect(() => {
    void loadPermissions();
  }, []);

  const roles = (data ?? []).slice().sort((a, b) => a.code.localeCompare(b.code));

  const togglePerm = async (r: RoleInfo, perm: string) => {
    const next = r.permissions.includes(perm)
      ? r.permissions.filter((p) => p !== perm)
      : [...r.permissions, perm].sort();
    try {
      await api.setRolePermissions(r.code, next);
      await reload();
    } catch (err) {
      notifyToast(`Ошибка: ${err instanceof Error ? err.message : err}`);
    }
  };

  const saveEdits = async (r: RoleInfo) => {
    const patch = edits[r.code];
    if (!patch) return;
    try {
      const updated = await api.updateRole(r.code, patch);
      setEdits((prev) => {
        const next = { ...prev };
        delete next[r.code];
        return next;
      });
      notifyToast(`Роль «${updated.name}» обновлена`);
      await reload();
    } catch (err) {
      notifyToast(`Ошибка: ${err instanceof Error ? err.message : err}`);
    }
  };

  const doDelete = async (code: string) => {
    try {
      await api.deleteRole(code);
      setConfirmDelete(null);
      notifyToast('Роль удалена');
      await reload();
    } catch (err) {
      setConfirmDelete(null);
      notifyToast(`Ошибка: ${err instanceof Error ? err.message : err}`);
    }
  };

  const createRole = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!createCode.trim() || !createName.trim()) return;
    try {
      const role = await api.createRole({
        code: createCode.trim(),
        name: createName.trim(),
        description: createDesc.trim(),
        permission_codes: createPerms,
      });
      notifyToast(`Роль «${role.name}» создана`);
      setCreateCode('');
      setCreateName('');
      setCreateDesc('');
      setCreatePerms([]);
      await reload();
    } catch (err) {
      notifyToast(`Ошибка: ${err instanceof Error ? err.message : err}`);
    }
  };

  const toggleCreatePerm = (perm: string) =>
    setCreatePerms((prev) =>
      prev.includes(perm) ? prev.filter((p) => p !== perm) : [...prev, perm],
    );

  if (loading && !data) return <Loader />;
  if (error && !data) return <Err text={error} />;

  return (
    <Page
      title="Роли"
      subtitle="Создание, редактирование и назначение прав доступа по ролям (RBAC)"
      actions={<button className="btn" onClick={() => void reload()}>Обновить</button>}
    >
      {roles.length === 0 ? (
        <Card><Empty text="Роли не найдены" /></Card>
      ) : (
        roles.map((r) => {
          const edit = edits[r.code];
          const name = edit?.name ?? r.name;
          const description = edit?.description ?? r.description;
          const builtin = BUILTIN_ROLES.includes(r.code);
          const dirty = Boolean(edit);
          return (
            <Card
              key={r.code}
              title={
                <span className="row" style={{ gap: 8 }}>
                  <span className="bold">{r.name}</span>
                  <code className="mono">{r.code}</code>
                  {builtin && <Chip tone="muted">встроенная</Chip>}
                </span>
              }
              subtitle={r.description || (builtin ? 'Системная роль' : '')}
              actions={
                <div className="row" style={{ gap: 8 }}>
                  <Chip tone="accent">{r.permissions.length} прав</Chip>
                  {!builtin &&
                    (confirmDelete === r.code ? (
                      <>
                        <button className="btn btn-danger" onClick={() => void doDelete(r.code)}>Удалить?</button>
                        <button className="btn" onClick={() => setConfirmDelete(null)}>Отмена</button>
                      </>
                    ) : (
                      <button className="btn btn-danger" onClick={() => setConfirmDelete(r.code)}>Удалить</button>
                    ))}
                </div>
              }
            >
              <div className="row" style={{ gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
                <div className="form-field" style={{ flex: '1 1 220px', minWidth: 200 }}>
                  <label className="form-label">Название</label>
                  <input
                    className="form-input"
                    value={name}
                    onChange={(e) =>
                      setEdits((prev) => ({ ...prev, [r.code]: { name: e.target.value, description } }))
                    }
                  />
                </div>
                <div className="form-field" style={{ flex: '1 1 300px', minWidth: 220 }}>
                  <label className="form-label">Описание</label>
                  <input
                    className="form-input"
                    value={description}
                    onChange={(e) =>
                      setEdits((prev) => ({ ...prev, [r.code]: { name, description: e.target.value } }))
                    }
                  />
                </div>
                <div className="row" style={{ alignItems: 'flex-end', paddingBottom: 4, gap: 8 }}>
                  <button
                    className={`btn${dirty ? ' btn-start' : ''}`}
                    disabled={!dirty}
                    onClick={() => void saveEdits(r)}
                  >
                    {dirty ? 'Сохранить' : 'Сохранено'}
                  </button>
                  {dirty && (
                    <button
                      className="btn"
                      onClick={() =>
                        setEdits((prev) => {
                          const next = { ...prev };
                          delete next[r.code];
                          return next;
                        })
                      }
                    >
                      Отмена
                    </button>
                  )}
                </div>
              </div>

              <div className="form-label" style={{ marginBottom: 4 }}>
                Права доступа{' '}
                {builtin ? (
                  <span className="muted">(встроенная роль — права заданы каталогом)</span>
                ) : (
                  <span className="muted">(клик — включить/выключить)</span>
                )}
              </div>
              <div className="picker" style={{ flexWrap: 'wrap', gap: 4 }}>
                {permissions.map((p) => {
                  const on = r.permissions.includes(p.code);
                  return builtin ? (
                    <Chip key={p.code} tone={on ? 'accent' : 'muted'}>{p.code}</Chip>
                  ) : (
                    <span
                      key={p.code}
                      className={`picker-chip${on ? ' on' : ''}`}
                      title={p.description}
                      onClick={() => void togglePerm(r, p.code)}
                    >
                      {p.code}
                    </span>
                  );
                })}
              </div>
            </Card>
          );
        })
      )}

      <Card title="Создать роль">
        <form className="row" onSubmit={createRole} style={{ alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div className="form-field" style={{ minWidth: 160 }}>
            <label className="form-label">Код (латиница/_/цифры)</label>
            <input
              className="form-input"
              value={createCode}
              onChange={(e) => setCreateCode(e.target.value)}
              placeholder="shift_supervisor"
              required
            />
          </div>
          <div className="form-field" style={{ minWidth: 160 }}>
            <label className="form-label">Название</label>
            <input
              className="form-input"
              value={createName}
              onChange={(e) => setCreateName(e.target.value)}
              placeholder="Начальник смены"
              required
            />
          </div>
          <div className="form-field" style={{ minWidth: 220 }}>
            <label className="form-label">Описание</label>
            <input
              className="form-input"
              value={createDesc}
              onChange={(e) => setCreateDesc(e.target.value)}
            />
          </div>
          <button type="submit" className="btn btn-start">Создать</button>
        </form>
        <div className="form-label" style={{ margin: '8px 0 4px' }}>Права доступа новой роли</div>
        <div className="picker" style={{ flexWrap: 'wrap', gap: 4 }}>
          {permissions.map((p) => {
            const on = createPerms.includes(p.code);
            return (
              <span
                key={p.code}
                className={`picker-chip${on ? ' on' : ''}`}
                title={p.description}
                onClick={() => toggleCreatePerm(p.code)}
              >
                {p.code}
              </span>
            );
          })}
        </div>
      </Card>
    </Page>
  );
}
