import React, { useState, useEffect } from 'react';
import { ScenarioListItem, ScenarioDetail } from '../types';
import { RangeMatrix } from './RangeMatrix';

export const RangeExplorer: React.FC = () => {
  const [scenarios, setScenarios] = useState<ScenarioListItem[]>([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>('');
  const [detail, setDetail] = useState<ScenarioDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/scenarios')
      .then((r) => r.json())
      .then((data: ScenarioListItem[]) => {
        setScenarios(data);
        if (data.length > 0) {
          setSelectedScenarioId(data[0].id);
        }
      })
      .catch((e) => console.error(e))
      .finally(() => setLoading(false));
  }, []);

  const [selectedStack, setSelectedStack] = useState<string>('');

  const loadDetail = (scenarioId: string, stack: string) => {
    const stackParam = stack ? `?stack=${encodeURIComponent(stack)}` : '';
    fetch(`/api/scenarios/${scenarioId}${stackParam}`)
      .then((r) => r.json())
      .then((data: ScenarioDetail) => setDetail(data))
      .catch((e) => console.error(e));
  };

  // Al cambiar de escenario se resetea el corte y se trae el pintado por defecto.
  useEffect(() => {
    if (selectedScenarioId) {
      setSelectedStack('');
      loadDetail(selectedScenarioId, '');
    }
  }, [selectedScenarioId]);

  const handleStackChange = (stack: string) => {
    setSelectedStack(stack);
    if (selectedScenarioId) {
      loadDetail(selectedScenarioId, stack);
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '4rem 1rem', color: '#94A3B8' }}>
        <h3>Cargando tablas de rangos...</h3>
      </div>
    );
  }

  // Preparar dict para RangeMatrix
  const matrixData: Record<string, any> = {};
  if (detail) {
    Object.entries(detail.hands).forEach(([hand, h]) => {
      const act = detail.actions_config[h.action] || {};
      const fup = h.followup ? detail.followups_config[h.followup] : null;
      matrixData[hand] = {
        action: h.action,
        action_label: act.label || h.action,
        color: act.color || '#334155',
        followup: h.followup,
        followup_label: fup ? fup.label : null,
        followup_color: fup ? fup.color : null,
        frequency: h.frequency,
        marginal: Boolean((h as any).marginal),
      };
    });
  }

  // En by_stack la matriz pinta un corte: el selector muestra cual.
  const stackValue = selectedStack || detail?.hands_stack || '';

  return (
    <div style={{ maxWidth: '1100px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: '#131B2E',
          padding: '1.5rem 2rem',
          borderRadius: '16px',
          border: '1px solid #2D3A54',
          flexWrap: 'wrap',
          gap: '1rem',
        }}
      >
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 800, color: '#F8FAFC' }}>
            🗺 Explorador de Rangos 13x13 (Spin & Go)
          </h1>
          <p style={{ color: '#94A3B8', fontSize: '0.9rem', marginTop: '0.25rem' }}>
            Consulta y memoriza las tablas teóricas completas de cada escenario
          </p>
        </div>

        <select
          value={selectedScenarioId}
          onChange={(e) => setSelectedScenarioId(e.target.value)}
          style={{
            background: '#0F172A',
            color: '#F8FAFC',
            border: '1px solid #334155',
            padding: '0.6rem 1.25rem',
            borderRadius: '8px',
            fontSize: '0.95rem',
            fontWeight: 700,
            cursor: 'pointer',
          }}
        >
          {scenarios.map((sc) => (
            <option key={sc.id} value={sc.id}>
              {sc.name} ({sc.position} - {sc.stack_range} BBs)
            </option>
          ))}
        </select>
      </div>

      {detail && (
        <div style={{ background: '#131B2E', padding: '2rem', borderRadius: '16px', border: '1px solid #2D3A54', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1.5rem' }}>
          {/* Metadata badges */}
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', justifyContent: 'center' }}>
            <span style={{ background: 'rgba(16, 185, 129, 0.2)', color: '#10B981', border: '1px solid #10B981', padding: '0.2rem 0.6rem', borderRadius: '6px', fontWeight: 800 }}>
              {detail.position}
            </span>
            <span style={{ background: '#1E293B', color: '#E2E8F0', padding: '0.2rem 0.6rem', borderRadius: '6px', fontSize: '0.85rem' }}>
              Stack: <strong>{detail.stack_range} BBs</strong>
            </span>
            <span style={{ background: '#1E293B', color: '#E2E8F0', padding: '0.2rem 0.6rem', borderRadius: '6px', fontSize: '0.85rem' }}>
              Spot: <strong>{detail.spot}</strong>
            </span>
            {detail.by_stack_keys && detail.by_stack_keys.length > 0 && (
              <label style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', background: '#0F172A', border: '1px solid #F59E0B', padding: '0.2rem 0.6rem', borderRadius: '6px', fontSize: '0.85rem', color: '#FDE68A' }}>
                Stack:
                <select
                  value={stackValue}
                  onChange={(e) => handleStackChange(e.target.value)}
                  style={{ background: '#0F172A', color: '#FDE68A', border: 'none', fontWeight: 800, fontSize: '0.85rem', cursor: 'pointer' }}
                >
                  {detail.by_stack_keys.map((k) => (
                    <option key={k} value={k}>{k} BB</option>
                  ))}
                </select>
              </label>
            )}
            {detail.tags.map((t) => (
              <span key={t} style={{ background: 'rgba(59, 130, 246, 0.15)', color: '#60A5FA', padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 600 }}>
                {t}
              </span>
            ))}
          </div>

          {/* Estadísticas de referencia si existen */}
          {detail.reference_stats && (
            <div style={{ display: 'flex', gap: '1.5rem', background: '#0F172A', padding: '0.75rem 1.5rem', borderRadius: '10px', border: '1px solid #2D3A54', flexWrap: 'wrap', justifyContent: 'center', fontSize: '0.85rem' }}>
              {detail.reference_stats.vpip_pct && (
                <div>VPIP: <strong style={{ color: '#10B981' }}>{detail.reference_stats.vpip_pct}%</strong> ({detail.reference_stats.vpip_combos} combos)</div>
              )}
              {detail.reference_stats.open_shove_pct && (
                <div>Open Shove: <strong style={{ color: '#8B0A24' }}>{detail.reference_stats.open_shove_pct}%</strong></div>
              )}
              {detail.reference_stats.or_pct && (
                <div>OR: <strong style={{ color: '#E85A5A' }}>{detail.reference_stats.or_pct}%</strong></div>
              )}
            </div>
          )}

          {/* Matriz 13x13 */}
          <RangeMatrix
            matrixData={matrixData}
            actionsConfig={detail.actions_config}
            followupsConfig={detail.followups_config}
            compact={false}
          />
        </div>
      )}
    </div>
  );
};
