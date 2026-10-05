import React, { useState, useEffect } from 'react';
import { ScenarioListItem } from '../types';

interface SessionSetupProps {
  onSessionStart?: (sessionId: string) => void;
}

export const SessionSetup: React.FC<SessionSetupProps> = ({ onSessionStart }) => {
  const [scenarios, setScenarios] = useState<ScenarioListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedScenarios, setSelectedScenarios] = useState<string[]>([]);
  const [selectedPosition, setSelectedPosition] = useState<string>('ALL');
  const [selectedMode, setSelectedMode] = useState<'normal' | 'errors_only' | 'borderline'>('normal');
  const [handLimit, setHandLimit] = useState<number | null>(null);
  const [timeLimit, setTimeLimit] = useState<number | null>(null);
  const [activeTag, setActiveTag] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    fetchScenarios();
  }, []);

  const fetchScenarios = async () => {
    try {
      setLoading(true);
      const res = await fetch('/api/scenarios');
      if (!res.ok) throw new Error('Error al cargar escenarios');
      const data: ScenarioListItem[] = await res.json();
      setScenarios(data);
      // Por defecto seleccionar todos los disponibles
      setSelectedScenarios(data.map((s) => s.id));
    } catch (err: any) {
      setErrorMsg(err.message || 'Error de conexión');
    } finally {
      setLoading(false);
    }
  };

  const handleToggleScenario = (id: string) => {
    setSelectedScenarios((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]
    );
  };

  const handleSelectAll = () => {
    const visibleIds = filteredScenarios.map((s) => s.id);
    setSelectedScenarios((prev) => Array.from(new Set([...prev, ...visibleIds])));
  };

  const handleDeselectAll = () => {
    const visibleIds = new Set(filteredScenarios.map((s) => s.id));
    setSelectedScenarios((prev) => prev.filter((id) => !visibleIds.has(id)));
  };

  /**
   * Al cambiar un filtro la seleccion se ajusta a lo que se ve.
   *
   * Antes el filtro solo ocultaba tarjetas: si venias con los 8 escenarios
   * tildados, filtrar por BTN dejaba los 4 HU seleccionados a escondidas y la
   * sesion sorteaba entre ellos. Con esto, lo que se ve es lo que se juega.
   */
  const handleFilterChange = (next: Partial<{ position: string; tag: string | null }>) => {
    const position = next.position !== undefined ? next.position : selectedPosition;
    const tag = next.tag !== undefined ? next.tag : activeTag;

    const visibleIds = scenarios
      .filter((s) => {
        if (position !== 'ALL' && s.position !== position) return false;
        if (tag && !(s.tags || []).includes(tag)) return false;
        return true;
      })
      .map((s) => s.id);

    if (next.position !== undefined) setSelectedPosition(next.position);
    if (next.tag !== undefined) setActiveTag(next.tag);
    setSelectedScenarios(visibleIds);
  };

  const allTags = Array.from(
    new Set(scenarios.flatMap((s) => s.tags || []))
  );

  const filteredScenarios = scenarios.filter((s) => {
    if (selectedPosition !== 'ALL' && s.position !== selectedPosition) return false;
    if (activeTag && !(s.tags || []).includes(activeTag)) return false;
    return true;
  });

  const handleStart = async () => {
    if (selectedScenarios.length === 0) {
      setErrorMsg('Debes seleccionar al menos un escenario para entrenar.');
      return;
    }

    try {
      setStarting(true);
      setErrorMsg(null);
      const res = await fetch('/api/training/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scenario_ids: selectedScenarios,
          mode: selectedMode,
          time_limit_seconds: timeLimit,
          hand_limit: handLimit,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Error al iniciar la sesión');
      }

      const sessionData = await res.json();
      localStorage.setItem('poker_active_session_id', sessionData.session_id);

      if (onSessionStart) {
        onSessionStart(sessionData.session_id);
      } else {
        window.location.href = '/train';
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'No se pudo iniciar la sesión.');
      setStarting(false);
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '4rem 1rem', color: '#94A3B8' }}>
        <div style={{ fontSize: '2rem', marginBottom: '1rem' }}>⏳</div>
        <h3>Cargando catálogo de rangos preflop...</h3>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: '1100px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {/* Cabecera del Setup */}
      <div style={{ background: '#131B2E', padding: '1.75rem 2rem', borderRadius: '16px', border: '1px solid #2D3A54' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 800, color: '#F8FAFC', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span>⚙ Configuración de Entrenamiento Preflop</span>
        </h1>
        <p style={{ color: '#94A3B8', fontSize: '0.95rem', lineHeight: 1.5 }}>
          Personaliza tu sesión de memorización rápida para Spin & Go 3-Max. Puedes combinar múltiples escenarios,
          enfocarte en tus errores pasados o afinar tu precisión en las manos límite de rango.
        </p>
      </div>

      {errorMsg && (
        <div style={{ background: 'rgba(239, 68, 68, 0.15)', border: '1px solid #EF4444', color: '#FCA5A5', padding: '1rem', borderRadius: '8px', fontSize: '0.9rem' }}>
          ⚠ {errorMsg}
        </div>
      )}

      {/* Selector de Modo de Entrenamiento */}
      <div style={{ background: '#131B2E', padding: '1.5rem', borderRadius: '16px', border: '1px solid #2D3A54' }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '1rem', color: '#E2E8F0' }}>
          1. Modo de Entrenamiento
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
          {/* Modo Normal */}
          <div
            onClick={() => setSelectedMode('normal')}
            style={{
              padding: '1.2rem',
              borderRadius: '12px',
              border: selectedMode === 'normal' ? '2px solid #10B981' : '1px solid #2D3A54',
              background: selectedMode === 'normal' ? 'rgba(16, 185, 129, 0.08)' : '#0F172A',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
              <span style={{ fontSize: '1.05rem', fontWeight: 700, color: '#F8FAFC' }}>⚡ Modo Estándar</span>
              {selectedMode === 'normal' && <span style={{ color: '#10B981', fontWeight: 800 }}>✓ Activo</span>}
            </div>
            <p style={{ fontSize: '0.85rem', color: '#94A3B8', lineHeight: 1.4 }}>
              Muestreo balanceado de todas las 169 combinaciones para los escenarios elegidos. Ideal para entrenamiento diario.
            </p>
          </div>

          {/* Modo Solo Errores */}
          <div
            onClick={() => setSelectedMode('errors_only')}
            style={{
              padding: '1.2rem',
              borderRadius: '12px',
              border: selectedMode === 'errors_only' ? '2px solid #EF4444' : '1px solid #2D3A54',
              background: selectedMode === 'errors_only' ? 'rgba(239, 68, 68, 0.08)' : '#0F172A',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
              <span style={{ fontSize: '1.05rem', fontWeight: 700, color: '#F8FAFC' }}>🎯 Solo Errores (Repetición)</span>
              {selectedMode === 'errors_only' && <span style={{ color: '#EF4444', fontWeight: 800 }}>✓ Activo</span>}
            </div>
            <p style={{ fontSize: '0.85rem', color: '#94A3B8', lineHeight: 1.4 }}>
              Repite manos que has fallado previamente con repetición espaciada. Mayor peso a fallos recientes para sellar las fugas.
            </p>
          </div>

          {/* Modo Borderline */}
          <div
            onClick={() => setSelectedMode('borderline')}
            style={{
              padding: '1.2rem',
              borderRadius: '12px',
              border: selectedMode === 'borderline' ? '2px solid #3B82F6' : '1px solid #2D3A54',
              background: selectedMode === 'borderline' ? 'rgba(59, 130, 246, 0.08)' : '#0F172A',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
              <span style={{ fontSize: '1.05rem', fontWeight: 700, color: '#F8FAFC' }}>⚖ Límite de Rango (Borderline)</span>
              {selectedMode === 'borderline' && <span style={{ color: '#3B82F6', fontWeight: 800 }}>✓ Activo</span>}
            </div>
            <p style={{ fontSize: '0.85rem', color: '#94A3B8', lineHeight: 1.4 }}>
              Prioriza las manos en las fronteras entre Open Shove, Open Raise y Fold. Donde se deciden las decisiones más difíciles.
            </p>
          </div>
        </div>
      </div>

      {/* Filtros y Selección de Escenarios */}
      <div style={{ background: '#131B2E', padding: '1.5rem', borderRadius: '16px', border: '1px solid #2D3A54' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h2 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#E2E8F0' }}>
              2. Selección de Escenarios ({selectedScenarios.length} seleccionados)
            </h2>
            <p style={{ color: '#94A3B8', fontSize: '0.85rem' }}>
              Combina múltiples tablas para poner a prueba tu adaptabilidad
            </p>
            <p style={{ color: '#64748B', fontSize: '0.78rem', marginTop: '0.3rem' }}>
              Fijate en el badge <strong style={{ color: '#38BDF8' }}>3-MAX</strong> o{' '}
              <strong style={{ color: '#F59E0B' }}>HU</strong> de cada tarjeta: el heads-up se juega
              en una mesa de 2 asientos. Filtrar por posición o tag deja tildado solo lo que se ve.
            </p>
          </div>

          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              onClick={handleSelectAll}
              style={{
                background: '#1E293B',
                color: '#E2E8F0',
                border: '1px solid #334155',
                padding: '0.35rem 0.75rem',
                borderRadius: '6px',
                fontSize: '0.8rem',
                cursor: 'pointer',
                fontWeight: 600,
              }}
            >
              Seleccionar Todos
            </button>
            <button
              onClick={handleDeselectAll}
              style={{
                background: '#1E293B',
                color: '#94A3B8',
                border: '1px solid #334155',
                padding: '0.35rem 0.75rem',
                borderRadius: '6px',
                fontSize: '0.8rem',
                cursor: 'pointer',
              }}
            >
              Limpiar
            </button>
          </div>
        </div>

        {/* Botones de Filtro por Posición */}
        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.85rem', color: '#94A3B8', alignSelf: 'center', marginRight: '0.5rem' }}>Posición:</span>
          {['ALL', 'BTN', 'SB', 'BB'].map((pos) => (
            <button
              key={pos}
              onClick={() => handleFilterChange({ position: pos })}
              style={{
                background: selectedPosition === pos ? '#3B82F6' : '#1E293B',
                color: selectedPosition === pos ? '#FFFFFF' : '#94A3B8',
                border: '1px solid #334155',
                padding: '0.35rem 0.8rem',
                borderRadius: '6px',
                fontSize: '0.82rem',
                cursor: 'pointer',
                fontWeight: 600,
              }}
            >
              {pos === 'ALL' ? 'Todas' : pos}
            </button>
          ))}
        </div>

        {/* Chips de Tags */}
        {allTags.length > 0 && (
          <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '1.25rem', flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ fontSize: '0.82rem', color: '#64748B' }}>Tags:</span>
            {allTags.map((tag) => (
              <span
                key={tag}
                onClick={() => handleFilterChange({ tag: activeTag === tag ? null : tag })}
                style={{
                  background: activeTag === tag ? 'rgba(16, 185, 129, 0.2)' : '#0F172A',
                  color: activeTag === tag ? '#10B981' : '#94A3B8',
                  border: activeTag === tag ? '1px solid #10B981' : '1px solid #1E293B',
                  padding: '0.2rem 0.55rem',
                  borderRadius: '9999px',
                  fontSize: '0.75rem',
                  cursor: 'pointer',
                  fontWeight: 600,
                }}
              >
                {tag}
              </span>
            ))}
            {activeTag && (
              <span
                onClick={() => setActiveTag(null)}
                style={{ color: '#EF4444', fontSize: '0.75rem', cursor: 'pointer', marginLeft: '0.3rem', textDecoration: 'underline' }}
              >
                Quitar filtro
              </span>
            )}
          </div>
        )}

        {/* Cuadrícula de Escenarios */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '1rem' }}>
          {filteredScenarios.map((sc) => {
            const isSelected = selectedScenarios.includes(sc.id);
            const posColor = sc.position === 'BTN' ? '#10B981' : sc.position === 'SB' ? '#8B5CF6' : '#3B82F6';
            // 3-max o heads-up. Sin esto las tarjetas de stack corto son
            // indistinguibles y una mesa de 2 asientos sorprende.
            const isHeadsUp = String(sc.game || '').toUpperCase().endsWith('_HU');
            const formatColor = isHeadsUp ? '#F59E0B' : '#38BDF8';

            return (
              <div
                key={sc.id}
                onClick={() => handleToggleScenario(sc.id)}
                style={{
                  background: isSelected ? 'rgba(30, 41, 59, 0.9)' : '#0F172A',
                  border: isSelected ? '2px solid #3B82F6' : '1px solid #1E293B',
                  borderRadius: '12px',
                  padding: '1rem 1.25rem',
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.6rem',
                  transition: 'all 0.15s ease',
                  position: 'relative',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => {}} // handled by parent div
                      style={{ cursor: 'pointer', width: '16px', height: '16px' }}
                    />
                    <span style={{ fontWeight: 800, fontSize: '1.05rem', color: '#F8FAFC' }}>
                      {sc.name}
                    </span>
                    <span
                      style={{
                        background: `${formatColor}20`,
                        color: formatColor,
                        border: `1px solid ${formatColor}60`,
                        padding: '0.1rem 0.4rem',
                        borderRadius: '4px',
                        fontSize: '0.68rem',
                        fontWeight: 800,
                        whiteSpace: 'nowrap',
                      }}
                      title={isHeadsUp ? 'Mesa de 2 asientos: hero en una ciega y un solo rival' : 'Mesa de 3 asientos: BTN, SB y BB'}
                    >
                      {isHeadsUp ? 'HU' : '3-MAX'}
                    </span>
                  </div>
                  <span
                    style={{
                      background: `${posColor}20`,
                      color: posColor,
                      border: `1px solid ${posColor}60`,
                      padding: '0.15rem 0.5rem',
                      borderRadius: '4px',
                      fontSize: '0.75rem',
                      fontWeight: 800,
                    }}
                  >
                    {sc.position}
                  </span>
                </div>

                <div style={{ display: 'flex', gap: '0.5rem', fontSize: '0.8rem', color: '#94A3B8' }}>
                  <span>Stack: <strong style={{ color: '#E2E8F0' }}>{sc.stack_range} BBs</strong></span>
                  <span>·</span>
                  <span>Spot: <strong style={{ color: '#E2E8F0' }}>{sc.spot}</strong></span>
                </div>

                {/* Desglose de acciones */}
                <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.2rem', flexWrap: 'wrap' }}>
                  {Object.entries(sc.action_counts || {}).map(([action, count]) => {
                    const color = sc.actions_config?.[action]?.color || '#64748B';
                    return (
                      <span
                        key={action}
                        style={{
                          fontSize: '0.72rem',
                          background: '#1E293B',
                          color: '#CBD5E1',
                          padding: '0.15rem 0.45rem',
                          borderRadius: '4px',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.3rem',
                        }}
                      >
                        <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: color }} />
                        {sc.actions_config?.[action]?.label || action}: {count}
                      </span>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Límites de Sesión (Manos / Tiempo) */}
      <div style={{ background: '#131B2E', padding: '1.5rem', borderRadius: '16px', border: '1px solid #2D3A54' }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '1rem', color: '#E2E8F0' }}>
          3. Límites de Sesión (Opcional)
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1.5rem' }}>
          {/* Límite de Manos */}
          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', color: '#94A3B8', marginBottom: '0.5rem' }}>
              Número de Manos:
            </label>
            <div style={{ display: 'flex', gap: '0.4rem' }}>
              {[
                { label: '25', value: 25 },
                { label: '50', value: 50 },
                { label: '100', value: 100 },
                { label: 'Infinito', value: null },
              ].map((item) => (
                <button
                  key={String(item.value)}
                  onClick={() => setHandLimit(item.value)}
                  style={{
                    flex: 1,
                    padding: '0.45rem',
                    borderRadius: '6px',
                    fontSize: '0.82rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    background: handLimit === item.value ? '#10B981' : '#0F172A',
                    color: handLimit === item.value ? '#FFFFFF' : '#94A3B8',
                    border: '1px solid #2D3A54',
                  }}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          {/* Límite de Tiempo */}
          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', color: '#94A3B8', marginBottom: '0.5rem' }}>
              Tiempo Máximo:
            </label>
            <div style={{ display: 'flex', gap: '0.4rem' }}>
              {[
                { label: '3 min', value: 180 },
                { label: '5 min', value: 300 },
                { label: '10 min', value: 600 },
                { label: '30 min', value: 1800 },
                { label: 'Sin límite', value: null },
              ].map((item) => (
                <button
                  key={String(item.value)}
                  onClick={() => setTimeLimit(item.value)}
                  style={{
                    flex: 1,
                    padding: '0.45rem',
                    borderRadius: '6px',
                    fontSize: '0.82rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    background: timeLimit === item.value ? '#10B981' : '#0F172A',
                    color: timeLimit === item.value ? '#FFFFFF' : '#94A3B8',
                    border: '1px solid #2D3A54',
                  }}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Botón de Comenzar */}
      <div style={{ textAlign: 'center', paddingBottom: '2rem' }}>
        <button
          onClick={handleStart}
          disabled={starting || selectedScenarios.length === 0}
          style={{
            background: 'linear-gradient(135deg, #10B981 0%, #059669 100%)',
            color: '#FFFFFF',
            border: 'none',
            padding: '1rem 3rem',
            borderRadius: '12px',
            fontSize: '1.2rem',
            fontWeight: 800,
            cursor: starting || selectedScenarios.length === 0 ? 'not-allowed' : 'pointer',
            boxShadow: '0 8px 24px rgba(16, 185, 129, 0.4)',
            transition: 'all 0.2s ease',
            opacity: starting || selectedScenarios.length === 0 ? 0.6 : 1,
          }}
        >
          {starting ? 'Iniciando Sesión...' : '⚡ Comenzar Entrenamiento'}
        </button>
      </div>
    </div>
  );
};
