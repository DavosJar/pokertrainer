import React from 'react';
import { VisualCard } from '../types';

interface CardVisualProps {
  card: VisualCard;
  size?: 'normal' | 'large' | 'compact';
}

export const CardVisual: React.FC<CardVisualProps> = ({ card, size = 'normal' }) => {
  const isLarge = size === 'large';
  const isCompact = size === 'compact';

  const width = isLarge ? '120px' : isCompact ? '70px' : '96px';
  const height = isLarge ? '170px' : isCompact ? '100px' : '136px';
  const rankFontSize = isLarge ? '1.8rem' : isCompact ? '1.05rem' : '1.4rem';
  const symbolFontSize = isLarge ? '3.2rem' : isCompact ? '1.8rem' : '2.4rem';
  const cornerSymbolSize = isLarge ? '1.2rem' : isCompact ? '0.75rem' : '0.95rem';

  return (
    <div
      style={{
        width,
        height,
        backgroundColor: '#FFFFFF',
        borderRadius: isCompact ? '8px' : '12px',
        border: '1.5px solid #E2E8F0',
        boxShadow: '0 12px 24px -4px rgba(0, 0, 0, 0.4), 0 4px 8px -2px rgba(0, 0, 0, 0.25)',
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        padding: isCompact ? '6px 8px' : '8px 12px',
        userSelect: 'none',
        color: card.color,
        transition: 'transform 0.15s ease',
      }}
    >
      {/* Esquina Superior Izquierda */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', lineHeight: 1 }}>
        <span style={{ fontSize: rankFontSize, fontWeight: 800, fontFamily: 'JetBrains Mono, monospace' }}>
          {card.rank}
        </span>
        <span style={{ fontSize: cornerSymbolSize, marginTop: '2px' }}>
          {card.symbol}
        </span>
      </div>

      {/* Símbolo Central Grande */}
      <div
        style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          fontSize: symbolFontSize,
          opacity: 0.95,
        }}
      >
        {card.symbol}
      </div>

      {/* Esquina Inferior Derecha (Invertida) */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          lineHeight: 1,
          transform: 'rotate(180deg)',
        }}
      >
        <span style={{ fontSize: rankFontSize, fontWeight: 800, fontFamily: 'JetBrains Mono, monospace' }}>
          {card.rank}
        </span>
        <span style={{ fontSize: cornerSymbolSize, marginTop: '2px' }}>
          {card.symbol}
        </span>
      </div>
    </div>
  );
};
