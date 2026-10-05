import React, { useState } from 'react';
import type { NextHandData } from '../types';

const RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'];

interface RangeMatrixProps {
  handData?: NextHandData;
  matrixData?: Record<string, any>; // hand -> { action, action_label, color, followup, followup_label, followup_color, frequency }
  actionsConfig?: Record<string, any>;
  followupsConfig?: Record<string, any>;
  highlightHand?: string | null;
  onCellClick?: (hand: string) => void;
  compact?: boolean;
  defaultMode?: 'action' | 'detail';
}

export const RangeMatrix: React.FC<RangeMatrixProps> = ({
  matrixData = {},
  actionsConfig = {},
  followupsConfig = {},
  highlightHand,
  onCellClick,
  compact = false,
  defaultMode = 'action'
}) => {
  const [hoveredHand, setHoveredHand] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'action' | 'detail'>(defaultMode);

  const getHandAt = (row: number, col: number): string => {
    const r1 = RANKS[row];
    const r2 = RANKS[col];
    if (row === col) return `${r1}${r2}`;
    if (row < col) return `${r1}${r2}s`;
    return `${r2}${r1}o`;
  };

  const hoveredInfo = hoveredHand ? matrixData[hoveredHand] : null;

  React.useEffect(() => {
    setViewMode(defaultMode);
  }, [defaultMode]);

  const getCellColor = (handInfo: Record<string, any> = {}): string => {
    if (!handInfo) return '#1E293B';

    if (viewMode === 'detail') {
      if (handInfo.action === 'OR' && handInfo.followup) {
        return followupsConfig[handInfo.followup]?.color || handInfo.followup_color || '#1E293B';
      }
    }

    return actionsConfig[handInfo.action]?.color || handInfo.color || '#1E293B';
  };

  const presentActionKeys = new Set(
    Object.values(matrixData)
      .filter((entry: any) => entry?.action)
      .map((entry: any) => entry.action)
  );

  const presentFollowupKeys = new Set(
    Object.values(matrixData)
      .filter((entry: any) => entry?.followup)
      .map((entry: any) => entry.followup)
  );

  const actionLegendEntries = Object.entries(actionsConfig).filter(([key]) => presentActionKeys.has(key));
  const followupLegendEntries = Object.entries(followupsConfig).filter(([key]) => presentFollowupKeys.has(key));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: compact ? '0.75rem' : '1.25rem', alignItems: 'center' }}>
      {/* Matriz 13x13 */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: `repeat(13, ${compact ? '30px' : '44px'})`,
          gridTemplateRows: `repeat(13, ${compact ? '30px' : '44px'})`,
          gap: compact ? '2px' : '3px',
          background: '#090D16',
          padding: compact ? '6px' : '10px',
          borderRadius: '12px',
          border: '1px solid #1E293B',
          boxShadow: '0 10px 30px rgba(0, 0, 0, 0.5)',
          userSelect: 'none',
        }}
      >
        {RANKS.map((_, row) =>
          RANKS.map((_, col) => {
            const hand = getHandAt(row, col);
            const info = matrixData[hand] || {};
            const isHighlighted = highlightHand === hand;
            const isHovered = hoveredHand === hand;

            const bg = getCellColor(info);
            const isFold = (info.action === 'FOLD') || !info.action;

            return (
              <div
                key={hand}
                onClick={() => onCellClick && onCellClick(hand)}
                onMouseEnter={() => setHoveredHand(hand)}
                onMouseLeave={() => setHoveredHand(null)}
                style={{
                  width: compact ? '30px' : '44px',
                  height: compact ? '30px' : '44px',
                  backgroundColor: bg,
                  borderRadius: compact ? '3px' : '5px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: compact ? '0.62rem' : '0.82rem',
                  fontWeight: 700,
                  fontFamily: 'JetBrains Mono, monospace',
                  color: isFold ? '#94A3B8' : '#FFFFFF',
                  cursor: onCellClick ? 'pointer' : 'default',
                  position: 'relative',
                  border: isHighlighted
                    ? '3px solid #F59E0B'
                    : isHovered
                    ? '2px solid #38BDF8'
                    : '1px solid rgba(255, 255, 255, 0.08)',
                  boxShadow: isHighlighted
                    ? '0 0 16px rgba(245, 158, 11, 0.9), inset 0 0 8px rgba(245, 158, 11, 0.5)'
                    : 'none',
                  transform: isHighlighted ? 'scale(1.18)' : isHovered ? 'scale(1.12)' : 'scale(1)',
                  zIndex: isHighlighted ? 20 : isHovered ? 10 : 1,
                  transition: 'all 0.12s cubic-bezier(0.4, 0, 0.2, 1)',
                }}
              >
                {hand}
              </div>
            );
          })
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
        <span style={{ fontSize: '0.72rem', letterSpacing: '0.08em', textTransform: 'uppercase', color: '#94A3B8', fontWeight: 800 }}>
          Modo vista
        </span>
        <div
          style={{
            display: 'inline-flex',
            background: 'linear-gradient(180deg, rgba(15,23,42,0.96), rgba(15,23,42,0.78))',
            borderRadius: '999px',
            padding: '0.24rem',
            border: '1px solid rgba(56, 189, 248, 0.25)',
            boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.05), 0 8px 18px rgba(2,6,23,0.35)',
          }}
        >
          {(['action', 'detail'] as const).map((modeOption) => {
            const isActive = viewMode === modeOption;
            return (
              <button
                key={modeOption}
                type="button"
                onClick={() => setViewMode(modeOption)}
                style={{
                  border: 'none',
                  borderRadius: '999px',
                  background: isActive ? 'linear-gradient(180deg, #38BDF8, #0EA5E9)' : 'transparent',
                  color: isActive ? '#031521' : '#CBD5E1',
                  padding: '0.42rem 1rem',
                  fontWeight: 800,
                  fontSize: '0.76rem',
                  letterSpacing: '0.02em',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  boxShadow: isActive ? '0 10px 20px rgba(14, 165, 233, 0.28)' : 'none',
                }}
              >
                {modeOption === 'action' ? 'Acción' : 'Detalle vs 3bet'}
              </button>
            );
          })}
        </div>
      </div>

      {/* Barra de información de la mano hover / seleccionada */}
      <div
        style={{
          minHeight: '2.5rem',
          display: 'flex',
          alignItems: 'center',
          gap: '1rem',
          background: '#131B2E',
          padding: '0.4rem 1rem',
          borderRadius: '8px',
          border: '1px solid #2D3A54',
          fontSize: '0.85rem',
          color: '#E2E8F0',
        }}
      >
        {hoveredHand ? (
          <>
            <span style={{ fontWeight: 800, fontFamily: 'JetBrains Mono, monospace', color: '#38BDF8', fontSize: '1rem' }}>
              {hoveredHand}
            </span>
            <span>
              Acción:{' '}
              <strong style={{ color: getCellColor(hoveredInfo) || '#94A3B8' }}>
                {hoveredInfo?.action_label || hoveredInfo?.action || 'FOLD'}
              </strong>
            </span>
            {hoveredInfo?.followup_label && (
              <span>
                vs 3bet:{' '}
                <strong style={{ color: viewMode === 'detail' && hoveredInfo.action === 'OR' ? (followupsConfig[hoveredInfo.followup]?.color || hoveredInfo.followup_color || '#7CC8D6') : (actionsConfig[hoveredInfo.action]?.color || hoveredInfo.color || '#7CC8D6') }}>
                  {hoveredInfo.followup_label}
                </strong>
              </span>
            )}
            <span>Frecuencia: <strong>{hoveredInfo?.frequency ?? 100}%</strong></span>
          </>
        ) : highlightHand ? (
          <>
            <span style={{ fontWeight: 800, fontFamily: 'JetBrains Mono, monospace', color: '#F59E0B', fontSize: '1rem' }}>
              ★ Mano evaluada: {highlightHand}
            </span>
            <span>
              Acción teórica:{' '}
              <strong style={{ color: getCellColor(matrixData[highlightHand]) || '#94A3B8' }}>
                {matrixData[highlightHand]?.action_label || matrixData[highlightHand]?.action || 'FOLD'}
              </strong>
            </span>
            {matrixData[highlightHand]?.followup_label && (
              <span>
                vs 3bet:{' '}
                <strong style={{ color: viewMode === 'detail' && matrixData[highlightHand]?.action === 'OR' ? (followupsConfig[matrixData[highlightHand]?.followup]?.color || matrixData[highlightHand]?.followup_color || '#7CC8D6') : (actionsConfig[matrixData[highlightHand]?.action]?.color || matrixData[highlightHand]?.color || '#7CC8D6') }}>
                  {matrixData[highlightHand]?.followup_label}
                </strong>
              </span>
            )}
          </>
        ) : (
          <span style={{ color: '#64748B' }}>Pasa el cursor sobre cualquier casilla para inspeccionar la acción y vs 3bet</span>
        )}
      </div>

      {/* Leyenda de categorías presentes en el escenario */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', justifyContent: 'center' }}>
        {actionLegendEntries.map(([key, item]: [string, any]) => (
          <div
            key={key}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              fontSize: '0.78rem',
              color: '#CBD5E1',
              background: '#0F172A',
              padding: '0.25rem 0.6rem',
              borderRadius: '6px',
              border: '1px solid #1E293B',
            }}
          >
            <div
              style={{
                width: '12px',
                height: '12px',
                borderRadius: '3px',
                backgroundColor: item.color || '#CCCCCC',
              }}
            />
            <span>{item.label || key}</span>
            {item.hotkey && (
              <span style={{ color: '#64748B', fontFamily: 'monospace', fontWeight: 700 }}>
                [{item.hotkey}]
              </span>
            )}
          </div>
        ))}

        {followupLegendEntries.map(([key, item]: [string, any]) => (
          <div
            key={key}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              fontSize: '0.78rem',
              color: '#CBD5E1',
              background: '#0F172A',
              padding: '0.25rem 0.6rem',
              borderRadius: '6px',
              border: '1px dashed #334155',
            }}
          >
            <div
              style={{
                width: '12px',
                height: '12px',
                borderRadius: '3px',
                backgroundColor: item.color || '#7CC8D6',
              }}
            />
            <span>{item.label || key}</span>
          </div>
        ))}
      </div>
    </div>
  );
};
