import React, { useState, useEffect } from 'react';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import {
  StatsOverview,
  AccuracyPoint,
  CategoryAccuracy,
  HandHeatmapCell,
  TopFailedHand,
  ScenarioListItem,
} from '../types';

const RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'];

export const Dashboard: React.FC = () => {
  const [overview, setOverview] = useState<StatsOverview | null>(null);
  const [overTimeData, setOverTimeData] = useState<AccuracyPoint[]>([]);
  const [byPosData, setByPosData] = useState<CategoryAccuracy[]>([]);
  const [byStackData, setByStackData] = useState<CategoryAccuracy[]>([]);
  const [scenarios, setScenarios] = useState<ScenarioListItem[]>([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>('');
  const [heatmapCells, setHeatmapCells] = useState<HandHeatmapCell[]>([]);
  const [topMistakes, setTopMistakes] = useState<TopFailedHand[]>([]);
  const [strengthsWeaknesses, setStrengthsWeaknesses] = useState<any>(null);

  const [dateFilter, setDateFilter] = useState<'today' | '7days' | '30days' | 'all'>('all');
  const [hoveredHeatmapHand, setHoveredHeatmapHand] = useState<HandHeatmapCell | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadAllStats();
  }, [dateFilter]);

  useEffect(() => {
    if (selectedScenarioId) {
      loadHeatmap(selectedScenarioId);
    }
  }, [selectedScenarioId]);

  const getDateParams = () => {
    const now = new Date();
    let fromDate: string | null = null;
    if (dateFilter === 'today') {
      fromDate = new Date(now.getFullYear(), now.getMonth(), now.getDate()).toISOString();
    } else if (dateFilter === '7days') {
      const d = new Date();
      d.setDate(d.getDate() - 7);
      fromDate = d.toISOString();
    } else if (dateFilter === '30days') {
      const d = new Date();
      d.setDate(d.getDate() - 30);
      fromDate = d.toISOString();
    }
    return fromDate ? `?from_date=${encodeURIComponent(fromDate)}` : '';
  };

  const loadAllStats = async () => {
    try {
      setLoading(true);
      const dateParams = getDateParams();

      // Cargar lista de escenarios primero si no los tenemos
      const scenRes = await fetch('/api/scenarios');
      const scenData: ScenarioListItem[] = await scenRes.json();
      setScenarios(scenData);
      if (scenData.length > 0 && !selectedScenarioId) {
        setSelectedScenarioId(scenData[0].id);
      }

      // 1. Overview
      const ovRes = await fetch(`/api/stats/overview${dateParams}`);
      const ovData: StatsOverview = await ovRes.json();
      setOverview(ovData);

      // 2. Evolución en el tiempo
      const otRes = await fetch(`/api/stats/over-time${dateParams}`);
      const otData: AccuracyPoint[] = await otRes.json();
      setOverTimeData(otData);

      // 3. Por posición
      const posRes = await fetch(`/api/stats/by-position${dateParams}`);
      const posData: CategoryAccuracy[] = await posRes.json();
      setByPosData(posData);

      // 4. Por stack
      const stackRes = await fetch(`/api/stats/by-stack-range${dateParams}`);
      const stackData: CategoryAccuracy[] = await stackRes.json();
      setByStackData(stackData);

      // 5. Top 20 fallos
      const tmRes = await fetch('/api/stats/top-mistakes?limit=20');
      const tmData: TopFailedHand[] = await tmRes.json();
      setTopMistakes(tmData);

      // 6. Fortalezas vs Debilidades
      const swRes = await fetch('/api/stats/strengths-weaknesses');
      const swData = await swRes.json();
      setStrengthsWeaknesses(swData);

      // 7. Heatmap inicial
      if (scenData.length > 0) {
        const scId = selectedScenarioId || scenData[0].id;
        loadHeatmap(scId);
      }
    } catch (err) {
      console.error('Error cargando estadísticas:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadHeatmap = async (scId: string) => {
    try {
      const res = await fetch(`/api/stats/heatmap/${scId}`);
      if (res.ok) {
        const data: HandHeatmapCell[] = await res.json();
        setHeatmapCells(data);
      }
    } catch (e) {
      console.error('Error cargando heatmap:', e);
    }
  };

  const getHeatmapColor = (cell?: HandHeatmapCell) => {
    if (!cell || cell.total_attempts === 0 || cell.accuracy_pct === null) {
      return '#1E293B'; // Sin jugar
    }
    if (cell.total_attempts < 3) {
      return '#475569'; // Neutro hasta 2 intentos para evitar rojo/naranja prematuro
    }
    const acc = cell.accuracy_pct;
    if (acc >= 90) return '#059669'; // Excelente (verde oscuro)
    if (acc >= 75) return '#10B981'; // Bueno (verde claro)
    if (acc >= 50) return '#D97706'; // Medio (ámbar)
    return '#DC2626'; // Crítico (rojo)
  };

  const heatmapMap = heatmapCells.reduce((acc, c) => {
    acc[c.hand] = c;
    return acc;
  }, {} as Record<string, HandHeatmapCell>);

  const hasSingleCategory = (group?: any) => {
    if (!group) return false;
    return group.insufficient_data === true || (group?.best && group?.worst && group.best.label === group.worst.label);
  };

  const getHandAt = (row: number, col: number): string => {
    const r1 = RANKS[row];
    const r2 = RANKS[col];
    if (row === col) return `${r1}${r2}`;
    if (row < col) return `${r1}${r2}s`;
    return `${r2}${r1}o`;
  };

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {/* Cabecera y Filtros de Fecha */}
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
          <h1 style={{ fontSize: '1.75rem', fontWeight: 800, color: '#F8FAFC', display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <span>📊 Dashboard de Rendimiento Preflop</span>
          </h1>
          <p style={{ color: '#94A3B8', fontSize: '0.9rem', marginTop: '0.25rem' }}>
            Análisis de precisión, velocidad de respuesta y detección de fugas (leaks)
          </p>
        </div>

        {/* Selector de Rango de Fechas */}
        <div style={{ display: 'flex', gap: '0.4rem', background: '#0F172A', padding: '0.3rem', borderRadius: '8px', border: '1px solid #2D3A54' }}>
          {[
            { id: 'today', label: 'Hoy' },
            { id: '7days', label: '7 Días' },
            { id: '30days', label: '30 Días' },
            { id: 'all', label: 'Histórico Completo' },
          ].map((item) => (
            <button
              key={item.id}
              onClick={() => setDateFilter(item.id as any)}
              style={{
                background: dateFilter === item.id ? '#3B82F6' : 'transparent',
                color: dateFilter === item.id ? '#FFFFFF' : '#94A3B8',
                border: 'none',
                padding: '0.4rem 0.8rem',
                borderRadius: '6px',
                fontSize: '0.82rem',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {/* Métricas Clave (KPIs) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
        <div style={{ background: '#131B2E', padding: '1.25rem', borderRadius: '12px', border: '1px solid #2D3A54' }}>
          <div style={{ fontSize: '0.82rem', color: '#94A3B8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Precisión Global
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 800, color: (overview?.global_accuracy_pct || 0) >= 80 ? '#10B981' : '#F59E0B', marginTop: '0.35rem' }}>
            {overview?.global_accuracy_pct || 0}%
          </div>
          <div style={{ fontSize: '0.8rem', color: '#64748B', marginTop: '0.2rem' }}>
            {overview?.total_correct || 0} de {overview?.total_answers || 0} manos correctas
          </div>
        </div>

        <div style={{ background: '#131B2E', padding: '1.25rem', borderRadius: '12px', border: '1px solid #2D3A54' }}>
          <div style={{ fontSize: '0.82rem', color: '#94A3B8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Tiempo Medio
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 800, color: '#38BDF8', marginTop: '0.35rem', fontFamily: 'JetBrains Mono, monospace' }}>
            {overview?.avg_response_ms || 0} ms
          </div>
          <div style={{ fontSize: '0.8rem', color: '#64748B', marginTop: '0.2rem' }}>
            Velocidad media de decisión
          </div>
        </div>

        <div style={{ background: '#131B2E', padding: '1.25rem', borderRadius: '12px', border: '1px solid #2D3A54' }}>
          <div style={{ fontSize: '0.82rem', color: '#94A3B8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Mediana
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 800, color: '#F59E0B', marginTop: '0.35rem', fontFamily: 'JetBrains Mono, monospace' }}>
            {overview?.median_response_ms || 0} ms
          </div>
          <div style={{ fontSize: '0.8rem', color: '#64748B', marginTop: '0.2rem' }}>
            Tiempo medio típico por sesión
          </div>
        </div>

        <div style={{ background: '#131B2E', padding: '1.25rem', borderRadius: '12px', border: '1px solid #2D3A54' }}>
          <div style={{ fontSize: '0.82rem', color: '#94A3B8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Correctas rápidas
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 800, color: '#10B981', marginTop: '0.35rem' }}>
            {overview?.correct_fast_pct || 0}%
          </div>
          <div style={{ fontSize: '0.8rem', color: '#64748B', marginTop: '0.2rem' }}>
            con respuesta ≤ 2s
          </div>
        </div>

        <div style={{ background: '#131B2E', padding: '1.25rem', borderRadius: '12px', border: '1px solid #2D3A54' }}>
          <div style={{ fontSize: '0.82rem', color: '#94A3B8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Mejor Racha
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 800, color: '#F59E0B', marginTop: '0.35rem' }}>
            🔥 {overview?.best_streak || 0}
          </div>
          <div style={{ fontSize: '0.8rem', color: '#64748B', marginTop: '0.2rem' }}>
            Racha actual: {overview?.current_streak || 0} aciertos
          </div>
        </div>

        <div style={{ background: '#131B2E', padding: '1.25rem', borderRadius: '12px', border: '1px solid #2D3A54' }}>
          <div style={{ fontSize: '0.82rem', color: '#94A3B8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Sesiones Totales
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 800, color: '#8B5CF6', marginTop: '0.35rem' }}>
            {overview?.total_sessions || 0}
          </div>
          <div style={{ fontSize: '0.8rem', color: '#64748B', marginTop: '0.2rem' }}>
            Entrenamientos registrados
          </div>
        </div>
      </div>

      {/* Gráfica 1: Evolución Temporal (Precisión % y Tiempo ms) */}
      <div style={{ background: '#131B2E', padding: '1.5rem', borderRadius: '16px', border: '1px solid #2D3A54' }}>
        <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#E2E8F0', marginBottom: '1.25rem' }}>
          📈 Evolución Temporal: Precisión y Tiempo de Respuesta
        </h2>
        {overTimeData.length > 0 ? (
          <div style={{ width: '100%', height: 320 }}>
            <ResponsiveContainer>
              <LineChart data={overTimeData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2D3A54" />
                <XAxis dataKey="date" stroke="#94A3B8" fontSize={12} />
                <YAxis yAxisId="left" stroke="#10B981" domain={[0, 100]} unit="%" fontSize={12} />
                <YAxis yAxisId="right" orientation="right" stroke="#F59E0B" unit="ms" fontSize={12} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0F172A', border: '1px solid #2D3A54', borderRadius: '8px', color: '#F8FAFC' }}
                />
                <Legend />
                <Line yAxisId="left" type="monotone" dataKey="accuracy_pct" name="Precisión (%)" stroke="#10B981" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 7 }} />
                <Line yAxisId="right" type="monotone" dataKey="avg_response_ms" name="Tiempo Medio (ms)" stroke="#F59E0B" strokeWidth={2} strokeDasharray="5 5" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '3rem 1rem', color: '#64748B' }}>
            Aún no hay suficientes datos registrados en este período para trazar la evolución.
          </div>
        )}
      </div>

      {/* Gráficas 2 y 3: Desglose por Posición y por Rango de Stack */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '1.5rem' }}>
        {/* Precisión por Posición */}
        <div style={{ background: '#131B2E', padding: '1.5rem', borderRadius: '16px', border: '1px solid #2D3A54' }}>
          <h2 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#E2E8F0', marginBottom: '1rem' }}>
            🎯 Precisión por Posición (BTN · SB · BB)
          </h2>
          {byPosData.length > 0 ? (
            <div style={{ width: '100%', height: 260 }}>
              <ResponsiveContainer>
                <BarChart data={byPosData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2D3A54" />
                  <XAxis dataKey="label" stroke="#94A3B8" />
                  <YAxis domain={[0, 100]} unit="%" stroke="#94A3B8" />
                  <Tooltip contentStyle={{ backgroundColor: '#0F172A', border: '1px solid #2D3A54', borderRadius: '8px' }} />
                  <Bar dataKey="accuracy_pct" name="Precisión (%)" fill="#3B82F6" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '3rem 1rem', color: '#64748B' }}>Sin datos aún</div>
          )}
        </div>

        {/* Precisión por Rango de Stack */}
        <div style={{ background: '#131B2E', padding: '1.5rem', borderRadius: '16px', border: '1px solid #2D3A54' }}>
          <h2 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#E2E8F0', marginBottom: '1rem' }}>
            ⚖ Precisión por Rango de Stack (BBs)
          </h2>
          {byStackData.length > 0 ? (
            <div style={{ width: '100%', height: 260 }}>
              <ResponsiveContainer>
                <BarChart data={byStackData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2D3A54" />
                  <XAxis dataKey="label" stroke="#94A3B8" />
                  <YAxis domain={[0, 100]} unit="%" stroke="#94A3B8" />
                  <Tooltip contentStyle={{ backgroundColor: '#0F172A', border: '1px solid #2D3A54', borderRadius: '8px' }} />
                  <Bar dataKey="accuracy_pct" name="Precisión (%)" fill="#8B5CF6" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '3rem 1rem', color: '#64748B' }}>Sin datos aún</div>
          )}
        </div>
      </div>

      {/* Heatmap 13x13 por Escenario */}
      <div style={{ background: '#131B2E', padding: '1.75rem', borderRadius: '16px', border: '1px solid #2D3A54' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#F8FAFC' }}>
              🗺 Heatmap de Aciertos 13x13 por Escenario
            </h2>
            <p style={{ color: '#94A3B8', fontSize: '0.85rem' }}>
              Identifica visualmente las manos con fugas de memoria o bajo % de acierto
            </p>
          </div>

          {/* Selector de Escenario */}
          <select
            value={selectedScenarioId}
            onChange={(e) => setSelectedScenarioId(e.target.value)}
            style={{
              background: '#0F172A',
              color: '#F8FAFC',
              border: '1px solid #334155',
              padding: '0.5rem 1rem',
              borderRadius: '8px',
              fontSize: '0.9rem',
              fontWeight: 600,
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

        {/* Leyenda del Heatmap */}
        <div style={{ display: 'flex', gap: '0.8rem', marginBottom: '1.25rem', flexWrap: 'wrap', fontSize: '0.76rem', color: '#CBD5E1' }}>
          {[
            { color: '#059669', label: '≥90% Acierto' },
            { color: '#10B981', label: '75-89%' },
            { color: '#D97706', label: '50-74%' },
            { color: '#DC2626', label: '<50% (Fuga crítica)' },
            { color: '#1E293B', label: 'Sin practicar', border: '1px solid #334155' },
          ].map((item) => (
            <div
              key={item.label}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                background: '#0F172A',
                border: '1px solid #2D3A54',
                borderRadius: '999px',
                padding: '0.35rem 0.7rem',
              }}
            >
              <div style={{ width: 12, height: 12, borderRadius: 3, backgroundColor: item.color, border: item.border || 'none' }} />
              <span>{item.label}</span>
            </div>
          ))}
        </div>

        {/* Grid 13x13 del Heatmap */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem' }}>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(13, 38px)',
              gridTemplateRows: 'repeat(13, 38px)',
              gap: '3px',
              background: '#090D16',
              padding: '8px',
              borderRadius: '12px',
              border: '1px solid #1E293B',
              userSelect: 'none',
            }}
          >
            {RANKS.map((_, row) =>
              RANKS.map((_, col) => {
                const hand = getHandAt(row, col);
                const cell = heatmapMap[hand];
                const bg = getHeatmapColor(cell);

                return (
                  <div
                    key={hand}
                    onMouseEnter={() => setHoveredHeatmapHand(cell || null)}
                    onMouseLeave={() => setHoveredHeatmapHand(null)}
                    style={{
                      width: '38px',
                      height: '38px',
                      backgroundColor: bg,
                      borderRadius: '4px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '0.72rem',
                      fontWeight: 700,
                      fontFamily: 'JetBrains Mono, monospace',
                      color: cell && cell.total_attempts > 0 ? '#FFFFFF' : '#64748B',
                      cursor: 'pointer',
                      border: '1px solid rgba(255, 255, 255, 0.05)',
                      transition: 'transform 0.1s ease',
                    }}
                  >
                    {hand}
                  </div>
                );
              })
            )}
          </div>

          {/* Caja de información de la casilla en hover */}
          <div
            style={{
              minHeight: '2.5rem',
              display: 'flex',
              alignItems: 'center',
              gap: '1rem',
              background: '#0F172A',
              padding: '0.5rem 1.25rem',
              borderRadius: '8px',
              border: '1px solid #2D3A54',
              fontSize: '0.85rem',
              color: '#E2E8F0',
            }}
          >
            {hoveredHeatmapHand ? (
              <>
                <span style={{ fontWeight: 800, fontFamily: 'JetBrains Mono, monospace', color: '#38BDF8', fontSize: '1.05rem' }}>
                  {hoveredHeatmapHand.hand}
                </span>
                <span>
                  Precisión:{' '}
                  <strong style={{ color: getHeatmapColor(hoveredHeatmapHand) }}>
                    {hoveredHeatmapHand.accuracy_pct !== null ? `${hoveredHeatmapHand.accuracy_pct}%` : 'Sin datos'}
                  </strong>
                </span>
                <span>
                  Intentos: <strong>{hoveredHeatmapHand.total_attempts}</strong> ({hoveredHeatmapHand.correct_attempts} aciertos)
                </span>
                <span>
                  Tiempo mediano:{' '}
                  <strong style={{ color: '#38BDF8' }}>
                    {hoveredHeatmapHand.median_response_ms !== null && hoveredHeatmapHand.median_response_ms !== undefined
                      ? `${hoveredHeatmapHand.median_response_ms} ms`
                      : 'Sin datos'}
                  </strong>
                </span>
                <span>
                  Acción teórica: <strong style={{ color: hoveredHeatmapHand.default_color }}>{hoveredHeatmapHand.default_action}</strong>
                </span>
              </>
            ) : (
              <span style={{ color: '#64748B' }}>Pasa el cursor sobre cualquier mano para ver el desglose de aciertos y fallos</span>
            )}
          </div>
        </div>
      </div>

      {/* Tabla: Top 20 Manos Más Falladas */}
      <div style={{ background: '#131B2E', padding: '1.75rem', borderRadius: '16px', border: '1px solid #2D3A54' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#F8FAFC', marginBottom: '0.5rem' }}>
          🚨 Top 20 Manos Más Falladas (Fugas de Memoria)
        </h2>
        <p style={{ color: '#94A3B8', fontSize: '0.85rem', marginBottom: '1.25rem' }}>
          Estas son las combinaciones que requieren repaso urgente en tu próximo entrenamiento
        </p>

        {topMistakes.length > 0 ? (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.88rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #2D3A54', color: '#94A3B8' }}>
                  <th style={{ padding: '0.75rem 1rem' }}>Mano</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Escenario</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Posición</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Stack</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Fallos</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Intentos</th>
                  <th style={{ padding: '0.75rem 1rem' }}>% Acierto</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Acción Correcta</th>
                </tr>
              </thead>
              <tbody>
                {topMistakes.map((tm, idx) => (
                  <tr
                    key={`${tm.scenario_id}_${tm.hand}_${idx}`}
                    style={{
                      borderBottom: '1px solid #1E293B',
                      background: idx % 2 === 0 ? 'rgba(15, 23, 42, 0.4)' : 'transparent',
                    }}
                  >
                    <td style={{ padding: '0.75rem 1rem', fontWeight: 800, fontFamily: 'JetBrains Mono, monospace', color: '#F59E0B' }}>
                      {tm.hand}
                    </td>
                    <td style={{ padding: '0.75rem 1rem', color: '#F8FAFC' }}>{tm.scenario_name}</td>
                    <td style={{ padding: '0.75rem 1rem' }}>
                      <span style={{ background: 'rgba(59, 130, 246, 0.2)', color: '#60A5FA', padding: '0.15rem 0.45rem', borderRadius: '4px', fontWeight: 700, fontSize: '0.75rem' }}>
                        {tm.position}
                      </span>
                    </td>
                    <td style={{ padding: '0.75rem 1rem', color: '#CBD5E1' }}>{tm.stack_range} BBs</td>
                    <td style={{ padding: '0.75rem 1rem', color: '#EF4444', fontWeight: 800 }}>{tm.failures}</td>
                    <td style={{ padding: '0.75rem 1rem', color: '#94A3B8' }}>{tm.total_attempts}</td>
                    <td style={{ padding: '0.75rem 1rem', fontWeight: 700, color: tm.accuracy_pct < 50 ? '#EF4444' : '#F59E0B' }}>
                      {tm.accuracy_pct}%
                    </td>
                    <td style={{ padding: '0.75rem 1rem', fontWeight: 700, color: '#10B981' }}>
                      {tm.correct_action} {tm.correct_followup ? `→ ${tm.correct_followup}` : ''}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '3rem 1rem', color: '#64748B' }}>
            ¡Enhorabuena! No hay errores registrados aún. Comienza una sesión para ver tus estadísticas.
          </div>
        )}
      </div>

      {/* Comparativa: Dónde soy más vs menos preciso */}
      {strengthsWeaknesses && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.5rem' }}>
          {/* Posiciones */}
          <div style={{ background: '#131B2E', padding: '1.5rem', borderRadius: '16px', border: '1px solid #2D3A54' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#E2E8F0', marginBottom: '1rem' }}>
              📍 Fortaleza vs Debilidad por Posición
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div style={{ background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.3)', padding: '0.75rem 1rem', borderRadius: '8px' }}>
                <div style={{ fontSize: '0.75rem', color: '#10B981', fontWeight: 700 }}>MÁS FUERTE</div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.2rem' }}>
                  {hasSingleCategory(strengthsWeaknesses.positions) ? (
                    <span style={{ fontWeight: 700, color: '#94A3B8' }}>Datos insuficientes</span>
                  ) : (
                    <>
                      <span style={{ fontWeight: 800, color: '#F8FAFC' }}>{strengthsWeaknesses.positions?.best?.label || 'N/A'}</span>
                      <span style={{ fontWeight: 800, color: '#10B981' }}>{strengthsWeaknesses.positions?.best?.accuracy_pct ?? 0}%</span>
                    </>
                  )}
                </div>
              </div>

              <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', padding: '0.75rem 1rem', borderRadius: '8px' }}>
                <div style={{ fontSize: '0.75rem', color: '#EF4444', fontWeight: 700 }}>MÁS DÉBIL</div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.2rem' }}>
                  {hasSingleCategory(strengthsWeaknesses.positions) ? (
                    <span style={{ fontWeight: 700, color: '#94A3B8' }}>Datos insuficientes</span>
                  ) : (
                    <>
                      <span style={{ fontWeight: 800, color: '#F8FAFC' }}>{strengthsWeaknesses.positions?.worst?.label || 'N/A'}</span>
                      <span style={{ fontWeight: 800, color: '#EF4444' }}>{strengthsWeaknesses.positions?.worst?.accuracy_pct ?? 0}%</span>
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Stacks */}
          <div style={{ background: '#131B2E', padding: '1.5rem', borderRadius: '16px', border: '1px solid #2D3A54' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#E2E8F0', marginBottom: '1rem' }}>
              ⚖ Fortaleza vs Debilidad por Stack
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div style={{ background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.3)', padding: '0.75rem 1rem', borderRadius: '8px' }}>
                <div style={{ fontSize: '0.75rem', color: '#10B981', fontWeight: 700 }}>MÁS FUERTE</div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.2rem' }}>
                  {hasSingleCategory(strengthsWeaknesses.stack_ranges) ? (
                    <span style={{ fontWeight: 700, color: '#94A3B8' }}>Datos insuficientes</span>
                  ) : (
                    <>
                      <span style={{ fontWeight: 800, color: '#F8FAFC' }}>{strengthsWeaknesses.stack_ranges?.best?.label || 'N/A'} BBs</span>
                      <span style={{ fontWeight: 800, color: '#10B981' }}>{strengthsWeaknesses.stack_ranges?.best?.accuracy_pct ?? 0}%</span>
                    </>
                  )}
                </div>
              </div>

              <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', padding: '0.75rem 1rem', borderRadius: '8px' }}>
                <div style={{ fontSize: '0.75rem', color: '#EF4444', fontWeight: 700 }}>MÁS DÉBIL</div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.2rem' }}>
                  {hasSingleCategory(strengthsWeaknesses.stack_ranges) ? (
                    <span style={{ fontWeight: 700, color: '#94A3B8' }}>Datos insuficientes</span>
                  ) : (
                    <>
                      <span style={{ fontWeight: 800, color: '#F8FAFC' }}>{strengthsWeaknesses.stack_ranges?.worst?.label || 'N/A'} BBs</span>
                      <span style={{ fontWeight: 800, color: '#EF4444' }}>{strengthsWeaknesses.stack_ranges?.worst?.accuracy_pct ?? 0}%</span>
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
