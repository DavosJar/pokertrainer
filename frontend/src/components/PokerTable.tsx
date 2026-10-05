import React from 'react';
import type { NextHandData, TableStateData } from '../types';

interface PokerTableProps {
  handData?: NextHandData | null;
  table?: TableStateData | null;
}

const SUIT_MAP: Record<string, string> = {
  s: '♠',
  h: '♥',
  d: '♦',
  c: '♣',
};

/** Sin datos de mesa todavía: reparto base para que nunca queden fichas de la mano anterior. */
const EMPTY_TABLE: TableStateData = {
  effective_stack: 0,
  pot: 0,
  dead: 0,
  bets: { sb: 0.5, bb: 1, hero: null },
  stacks: { sb: 0, bb: 0, hero: 0 },
  all_in: { sb: false, bb: false, hero: false },
  folded: { sb: false, bb: false },
};

const formatBb = (value: number | null | undefined) => {
  if (value === null || value === undefined || Number.isNaN(value)) return '';
  return Number.isInteger(value) ? String(value) : value.toFixed(1).replace(/\.0$/, '');
};

type HeroCard = { rank: string; suit: string; color?: string };

/**
 * Baraja de 4 colores: el color lo manda el backend en cada carta
 * (spades #1E293B, hearts #EF4444, diamonds #3B82F6, clubs #10B981).
 */
const SUIT_FALLBACK_COLOR: Record<string, string> = {
  s: '#1E293B',
  h: '#EF4444',
  d: '#3B82F6',
  c: '#10B981',
};

const buildHeroCards = (cards?: NextHandData['cards']): HeroCard[] => {
  if (!cards || cards.length === 0) {
    return [
      { rank: 'K', suit: 'c' },
      { rank: '5', suit: 'c' },
    ];
  }
  return cards.slice(0, 2).map((card) => {
    const suit = (card.suit || 'c').toLowerCase();
    return {
      rank: card.rank || '?',
      suit,
      color: card.color || SUIT_FALLBACK_COLOR[suit] || '#1E293B',
    };
  });
};

/** Carta circular: "ALL-IN" arriba si la ficha iguala al stack efectivo. */
const Chip: React.FC<{ amount: number | null; allIn: boolean; hidden?: boolean }> = ({ amount, allIn, hidden }) => {
  const isEmpty = amount === null || amount === undefined;
  const size = 'clamp(52px, 7.5vw, 68px)';

  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        display: 'grid',
        placeContent: 'center',
        textAlign: 'center',
        lineHeight: 1.15,
        background: allIn ? '#8b0a24' : 'rgba(0,0,0,0.33)',
        border: allIn ? '3px solid #8b0a24' : '3px dashed #f2c14e',
        color: allIn ? '#fff' : '#f2c14e',
        fontWeight: 800,
        fontSize: '13px',
        visibility: isEmpty || hidden ? 'hidden' : 'visible',
        boxSizing: 'border-box',
      }}
    >
      {!isEmpty && (
        <>
          {allIn && <small style={{ display: 'block', fontSize: '9px', letterSpacing: '0.5px' }}>ALL-IN</small>}
          {formatBb(amount)} BB
        </>
      )}
    </div>
  );
};

const SeatCards: React.FC<{ dimmed: boolean }> = ({ dimmed }) => (
  <div style={{ display: 'flex' }}>
    {['sb', 'bb'].map((seat) => (
      <div
        key={`${seat}-1`}
        style={{
          width: 'clamp(44px, 6vw, 68px)',
          aspectRatio: '5 / 7',
          borderRadius: '6px',
          background: 'repeating-linear-gradient(45deg, #1d3b8b, #1d3b8b 4px, #16306f 4px, #16306f 8px)',
          border: '2px solid #fff',
          boxShadow: '0 4px 10px rgba(0,0,0,0.35)',
          marginLeft: seat === 'bb' ? '-30%' : 0,
          opacity: dimmed ? 0.25 : 1,
        }}
      />
    ))}
  </div>
);

export const PokerTable: React.FC<PokerTableProps> = ({ handData, table }) => {
  const state = table ?? EMPTY_TABLE;
  const heroPos = handData?.position || 'BTN';
  const spotLabel = handData?.scenario_name || `${heroPos} ${handData?.stack_range ?? ''}`.trim() || 'BTN 15-9';
  const heroCards = buildHeroCards(handData?.cards);

  // En heads-up hay un solo rival y se sienta en la ciega que NO postinga hero:
  // hero es el SB -> el rival es el BB (derecha); hero es el BB -> rival es el
  // SB (izquierda). El asiento que queda vacio no se dibuja.
  // Hero NO cambia de lugar: sigue abajo al centro, igual que en 3-handed.
  const headsUp = Boolean(handData?.heads_up);
  const heroIsBigBlind = String(heroPos).toUpperCase() === 'BB';
  const showSbSeat = !headsUp || heroIsBigBlind;
  const showBbSeat = !headsUp || !heroIsBigBlind;

  const seatStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '6px',
  };

  return (
    <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '20px', alignItems: 'center' }}>
      <div
        style={{
          alignSelf: 'flex-start',
          color: '#8a96a3',
          fontSize: '14px',
          letterSpacing: '0.02em',
          fontWeight: 600,
        }}
      >
        {spotLabel}
      </div>

      <div
        style={{
          width: 'min(720px, 100%)',
          aspectRatio: '16 / 10',
          background: '#14452f',
          border: '10px solid #0c2c1f',
          borderRadius: '999px',
          display: 'grid',
          gridTemplateColumns: '1fr 1fr 1fr',
          gridTemplateRows: '1fr 0.9fr 1.5fr',
          justifyItems: 'center',
          alignItems: 'center',
          padding: '2% 6%',
          boxSizing: 'border-box',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        {/* Fila 1: SB, BB y el pot (un poco más arriba que el centro de la fila) */}
        {showSbSeat && (
          <div style={{ ...seatStyle, gridColumn: 1, gridRow: 1 }}>
            <SeatCards dimmed={state.folded.sb} />
            <div style={{ fontWeight: 700, fontSize: '13px', color: '#e8ecef', opacity: state.folded.sb ? 0.4 : 1 }}>SB</div>
            <div style={{ color: '#f2c14e', fontWeight: 700, fontSize: '13px', opacity: state.folded.sb ? 0.4 : 1 }}>
              {formatBb(state.stacks.sb)} BB
            </div>
          </div>
        )}

        {showBbSeat && (
          <div style={{ ...seatStyle, gridColumn: 3, gridRow: 1 }}>
            <SeatCards dimmed={state.folded.bb} />
            <div style={{ fontWeight: 700, fontSize: '13px', color: '#e8ecef', opacity: state.folded.bb ? 0.4 : 1 }}>BB</div>
            <div style={{ color: '#f2c14e', fontWeight: 700, fontSize: '13px', opacity: state.folded.bb ? 0.4 : 1 }}>
              {formatBb(state.stacks.bb)} BB
            </div>
          </div>
        )}

        <div style={{ ...seatStyle, gridColumn: 2, gridRow: 1, transform: 'translateY(-10px)' }}>
          <div
            style={{
              background: 'rgba(0,0,0,0.3)',
              border: '1px solid #f2c14e',
              color: '#f2c14e',
              borderRadius: '999px',
              padding: '4px 14px',
              fontWeight: 700,
              fontSize: '16px',
              minHeight: '26px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            Pot {formatBb(state.pot)} BB
          </div>
        </div>

        {/* Fila 2: las fichas circulares de cada jugador */}
        {showSbSeat && (
          <div style={{ gridColumn: 1, gridRow: 2 }}>
            <Chip amount={state.bets.sb} allIn={state.all_in.sb} hidden={state.folded.sb} />
          </div>
        )}

        {showBbSeat && (
          <div style={{ gridColumn: 3, gridRow: 2 }}>
            <Chip amount={state.bets.bb} allIn={state.all_in.bb} hidden={state.folded.bb} />
          </div>
        )}

        <div style={{ gridColumn: 2, gridRow: 2 }}>
          <Chip amount={state.bets.hero} allIn={state.all_in.hero} />
        </div>

        {/* Fila 3: hero */}
        <div style={{ ...seatStyle, gridColumn: 2, gridRow: 3 }}>
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
            {heroCards.map((card, index) => (
              <div
                key={`${card.rank}-${card.suit}-${index}`}
                style={{
                  width: 'clamp(68px, 10vw, 108px)',
                  aspectRatio: '5 / 7',
                  background: '#fff',
                  borderRadius: '10px',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontWeight: 800,
                  lineHeight: 1,
                  boxShadow: '0 4px 10px rgba(0,0,0,0.35)',
                  color: card.color || SUIT_FALLBACK_COLOR[card.suit] || '#1E293B',
                  marginLeft: index === 0 ? 0 : '-8%',
                }}
              >
                <span style={{ fontSize: 'calc(clamp(68px, 10vw, 108px) * 0.46)' }}>{card.rank}</span>
                <span style={{ fontSize: 'calc(clamp(68px, 10vw, 108px) * 0.4)' }}>{SUIT_MAP[card.suit] || '♣'}</span>
              </div>
            ))}
          </div>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              justifyContent: 'center',
              color: '#e8ecef',
              fontWeight: 700,
              fontSize: '15px',
            }}
          >
            <span>{heroPos}</span>
            {heroPos === 'BTN' && (
              <span
                style={{
                  background: '#fff',
                  color: '#000',
                  borderRadius: '50%',
                  width: '20px',
                  height: '20px',
                  display: 'inline-grid',
                  placeItems: 'center',
                  fontSize: '11px',
                  fontWeight: 800,
                }}
              >
                D
              </span>
            )}
            <span style={{ color: '#f2c14e', fontWeight: 700 }}>{formatBb(state.stacks.hero)} BB</span>
          </div>
        </div>
      </div>
    </div>
  );
};