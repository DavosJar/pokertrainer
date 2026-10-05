import React, { useState, useEffect, useCallback } from 'react';
import { NextHandData, AnswerResponse, SessionStatus, ActionOption, TableStateData, VillainReaction } from '../types';
import { PokerTable } from './PokerTable';
import { RangeMatrix } from './RangeMatrix';

/** Secuencia exacta de una mano: PASO 0/1 (hero) -> PASO 2/3 (rival) -> PASO 4 (feedback). */
type HandPhase = 'hero' | 'vs' | 'end';

export const TrainingCard: React.FC = () => {
  const [handData, setHandData] = useState<NextHandData | null>(null);
  const [loading, setLoading] = useState(true);
  const [evaluating, setEvaluating] = useState(false);
  const [lastAnswer, setLastAnswer] = useState<AnswerResponse | null>(null);
  const [showMatrixModal, setShowMatrixModal] = useState(false);
  const [startTime, setStartTime] = useState<number>(0);
  const [elapsedMs, setElapsedMs] = useState<number>(0);
  const [timerActive, setTimerActive] = useState(false);
  const [sessionFinished, setSessionFinished] = useState(false);
  const [showFinishConfirm, setShowFinishConfirm] = useState(false);
  const [sessionStatus, setSessionStatus] = useState<SessionStatus | null>(null);
  const [sessionRemainingSeconds, setSessionRemainingSeconds] = useState<number | null>(null);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  // Secuencia de la mano en curso
  const [phase, setPhase] = useState<HandPhase>('hero');
  const [level, setLevel] = useState<1 | 2>(1);
  const [villain, setVillain] = useState<VillainReaction | null>(null);
  const [activeActions, setActiveActions] = useState<ActionOption[]>([]);
  const [table, setTable] = useState<TableStateData | null>(null);
  // Que chose hero en el PASO 1. En el nivel 2 el backend lo necesita para
  // reconstruir la mesa y para saber si el rival respondio a un 3bet (tras OR)
  // o a un raise (tras LIMP).
  const [levelOneAction, setLevelOneAction] = useState<string | null>(null);

  const sessionId = localStorage.getItem('poker_active_session_id');

  // Reloj en tiempo real para mostrar milisegundos en pantalla.
  // Usa setInterval y no requestAnimationFrame: rAF se congela cuando la
  // pestaña no esta visible y el cronometro debe seguir corriendo igual.
  useEffect(() => {
    if (!timerActive || startTime <= 0) return;

    const updateTimer = () => setElapsedMs(Math.round(performance.now() - startTime));
    updateTimer();
    const interval = window.setInterval(updateTimer, 50);

    return () => window.clearInterval(interval);
  }, [timerActive, startTime]);

  const fetchSessionStatus = useCallback(async () => {
    if (!sessionId) return;
    try {
      const res = await fetch(`/api/training/session/${sessionId}`);
      if (!res.ok) return;
      const data: SessionStatus = await res.json();
      setSessionStatus(data);

      const baseRemaining = data.remaining_time_seconds ??
        (data.time_limit_seconds !== null && data.time_limit_seconds !== undefined
          ? Math.max(0, data.time_limit_seconds - Math.max(0, Math.floor((Date.now() - new Date(data.started_at).getTime()) / 1000)))
          : null);
      setSessionRemainingSeconds(baseRemaining);

      if (data.ended_at || data.has_reached_time_limit || data.has_reached_hand_limit) {
        setSessionFinished(true);
      }
    } catch {
      // ignore; session metadata is optional UI state
    }
  }, [sessionId]);

  // Cargar primera mano
  useEffect(() => {
    if (!sessionId) {
      // Si no hay sesión activa, redirigir al setup
      window.location.href = '/';
      return;
    }
    fetchSessionStatus();
    fetchNextHand();
  }, [sessionId, fetchSessionStatus]);

  useEffect(() => {
    if (!sessionId || sessionFinished) return;

    const interval = window.setInterval(() => {
      void fetchSessionStatus();
    }, 1000);

    return () => window.clearInterval(interval);
  }, [sessionId, sessionFinished, fetchSessionStatus]);

  const fetchNextHand = async () => {
    try {
      setLoading(true);
      setEvaluating(false);
      setLastAnswer(null);
      setVillain(null);
      setErrorBanner(null);
      setLevelOneAction(null);

      const params = new URLSearchParams({
        session_id: sessionId!,
        level: '1',
      });

      const res = await fetch(`/api/training/next-hand?${params.toString()}`);
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Error al obtener la mano');
      }

      const data: NextHandData = await res.json();

      // PASO 0 - REPARTO: mesa limpia y cronometro en marcha.
      setHandData(data);
      setTable(data.table ?? null);
      setActiveActions(data.available_actions ?? []);
      setLevel(1);
      setPhase('hero');
      setStartTime(performance.now());
      setElapsedMs(0);
      setTimerActive(true);
    } catch (err: any) {
      setErrorBanner(err.message || 'Error de conexión');
    } finally {
      setLoading(false);
    }
  };

  const handleAction = useCallback(
    async (chosenActionId: string) => {
      if (!handData || evaluating || sessionFinished) return;
      if (phase === 'end') return;

      // PASO 1/3 - Al hacer clic se detiene el cronometro y se evalua.
      const responseMs = Math.round(performance.now() - startTime);
      setTimerActive(false);
      setEvaluating(true);

      try {
        // En el nivel 1 se recuerda la accion para poder reconstruir la mesa y
        // el followup en el nivel 2.
        const parentAction = level === 2 ? levelOneAction : chosenActionId;

        const res = await fetch('/api/training/answer', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: sessionId,
            scenario_id: handData.scenario_id,
            hand: handData.hand,
            level,
            chosen_action: chosenActionId,
            response_ms: responseMs,
            effective_stack: table?.effective_stack,
            parent_action: parentAction,
            villain_actor: villain?.actor,
            villain_kind: villain?.kind,
          }),
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Error evaluando respuesta');
        }

        const answerData: AnswerResponse = await res.json();
        if (answerData.table) setTable(answerData.table);

        // PASO 2 - OR correcto: el rival responde, cambian los botones y el cronometro
        // se reinicia. La mano continua, todavia no hay feedback.
        if (answerData.needs_level_2 && answerData.villain && answerData.next_actions?.length) {
          setVillain(answerData.villain);
          setActiveActions(answerData.next_actions);
          setLevelOneAction(chosenActionId);
          setLevel(2);
          setPhase('vs');
          setStartTime(performance.now());
          setElapsedMs(0);
          setTimerActive(true);
          setEvaluating(false);
          return;
        }

        // PASO 4 - Feedback. La mesa se queda tal cual.
        setLastAnswer(answerData);
        setPhase('end');
        setEvaluating(false);
      } catch (err: any) {
        setErrorBanner(err.message || 'Error al enviar respuesta');
        setEvaluating(false);
      }
    },
    [handData, evaluating, startTime, sessionId, sessionFinished, phase, level, levelOneAction, table, villain]
  );

  const goToNextHand = useCallback(() => {
    setShowMatrixModal(false);
    void fetchNextHand();
  }, []);

  // Atajos de teclado
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Si la ventana modal está abierta y presiona Escape, cerrarla
      if (e.key === 'Escape' && showMatrixModal) {
        setShowMatrixModal(false);
        return;
      }

      // PASO 4 - Con el feedback visible, Espacio o Enter pasa a la siguiente mano
      if (phase === 'end') {
        if (e.key === ' ' || e.key === 'Enter') {
          e.preventDefault();
          goToNextHand();
        }
        return;
      }

      // Tecla 'M' abre/cierra la matriz
      if (e.key.toLowerCase() === 'm' && !e.ctrlKey && !e.altKey) {
        e.preventDefault();
        setShowMatrixModal((prev) => !prev);
        return;
      }

      if (!handData || evaluating || !timerActive) return;

      const key = e.key.toUpperCase();

      // Atajo numérico: '1', '2', '3', '4' mapeado por índice de botón
      if (['1', '2', '3', '4'].includes(key)) {
        const idx = parseInt(key, 10) - 1;
        if (idx < activeActions.length) {
          e.preventDefault();
          handleAction(activeActions[idx].id);
          return;
        }
      }

      // Atajo por hotkey configurado (ej. 'S', 'R', 'F' o 'C' para Call)
      const matchedAction = activeActions.find(
        (a) => a.hotkey && a.hotkey.toUpperCase() === key
      );
      if (matchedAction) {
        e.preventDefault();
        handleAction(matchedAction.id);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handData, evaluating, timerActive, showMatrixModal, phase, activeActions, handleAction, goToNextHand]);

  const handleFinishSession = useCallback(async () => {
    if (!sessionId || sessionFinished) return;
    setShowFinishConfirm(false);
    try {
      await fetch(`/api/training/session/${sessionId}/finish`, { method: 'POST' });
      await fetchSessionStatus();
      setSessionFinished(true);
      setSessionRemainingSeconds(0);
      localStorage.removeItem('poker_active_session_id');
    } catch {
      window.location.href = '/stats';
    }
  }, [sessionId, sessionFinished, fetchSessionStatus]);

  if (loading && !handData) {
    return (
      <div style={{ textAlign: 'center', padding: '5rem 1rem', color: '#94A3B8' }}>
        <div style={{ fontSize: '2.5rem', marginBottom: '1rem' }}>♠</div>
        <h2>Cargando mano de entrenamiento...</h2>
      </div>
    );
  }

  if (sessionFinished) {
    return (
      <div style={{ maxWidth: '700px', margin: '4rem auto', background: '#131B2E', padding: '2.5rem', borderRadius: '16px', border: '1px solid #2D3A54' }}>
        <div style={{ fontSize: '3rem', marginBottom: '1rem', textAlign: 'center' }}>🏆</div>
        <h2 style={{ fontSize: '1.75rem', fontWeight: 800, color: '#F8FAFC', marginBottom: '0.8rem', textAlign: 'center' }}>¡Sesión Finalizada!</h2>
        <p style={{ color: '#94A3B8', marginBottom: '1.5rem', textAlign: 'center' }}>
          Resumen de la sesión y acceso a la estadística general del entrenamiento.
        </p>

        {sessionStatus && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: '0.8rem', marginBottom: '1.75rem' }}>
            <div style={{ background: '#0F172A', border: '1px solid #1E293B', borderRadius: '10px', padding: '0.8rem' }}>
              <div style={{ color: '#94A3B8', fontSize: '0.75rem', textTransform: 'uppercase' }}>Manos</div>
              <div style={{ color: '#F8FAFC', fontWeight: 800, fontSize: '1.2rem' }}>{sessionStatus.total_hands}</div>
            </div>
            <div style={{ background: '#0F172A', border: '1px solid #1E293B', borderRadius: '10px', padding: '0.8rem' }}>
              <div style={{ color: '#94A3B8', fontSize: '0.75rem', textTransform: 'uppercase' }}>Aciertos</div>
              <div style={{ color: '#10B981', fontWeight: 800, fontSize: '1.2rem' }}>{sessionStatus.correct_hands}</div>
            </div>
            <div style={{ background: '#0F172A', border: '1px solid #1E293B', borderRadius: '10px', padding: '0.8rem' }}>
              <div style={{ color: '#94A3B8', fontSize: '0.75rem', textTransform: 'uppercase' }}>Precisión</div>
              <div style={{ color: '#38BDF8', fontWeight: 800, fontSize: '1.2rem' }}>{sessionStatus.accuracy_pct}%</div>
            </div>
          </div>
        )}

        <div style={{ background: '#0F172A', border: '1px solid #1E293B', borderRadius: '12px', padding: '1rem', marginBottom: '1.5rem' }}>
          <div style={{ color: '#94A3B8', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.5rem' }}>
            Estadísticas de sesión
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: '0.75rem', color: '#E2E8F0' }}>
            <div>Mediana respuesta: <strong>{sessionStatus?.median_response_ms ?? 0} ms</strong></div>
            <div>Correctas ≤ 2s: <strong>{sessionStatus?.correct_fast_pct ?? 0}%</strong></div>
            <div>Tiempo restante: <strong>{sessionStatus?.remaining_time_seconds ?? 0}s</strong></div>
            <div>Tope alcanzado: <strong>{sessionStatus?.has_reached_time_limit ? 'Tiempo' : sessionStatus?.has_reached_hand_limit ? 'Manos' : 'No'}</strong></div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap' }}>
          <a
            href="/stats"
            style={{ background: '#3B82F6', color: '#FFF', padding: '0.75rem 1.5rem', borderRadius: '8px', textDecoration: 'none', fontWeight: 700 }}
          >
            Ver estadísticas generales
          </a>
          <a
            href="/"
            style={{ background: '#10B981', color: '#FFF', padding: '0.75rem 1.5rem', borderRadius: '8px', textDecoration: 'none', fontWeight: 700 }}
          >
            Nueva sesión
          </a>
        </div>
      </div>
    );
  }

  const streak = lastAnswer ? lastAnswer.current_streak : handData?.current_streak || 0;
  const accuracy = lastAnswer ? lastAnswer.session_accuracy_pct : handData?.session_accuracy_pct || 0;
  const handsPlayed = lastAnswer ? lastAnswer.session_total_hands : handData?.session_hands_played || 0;
  const remainingSeconds = sessionRemainingSeconds ??
    (sessionStatus?.remaining_time_seconds ??
      (sessionStatus?.time_limit_seconds !== null && sessionStatus?.time_limit_seconds !== undefined
        ? Math.max(0, sessionStatus.time_limit_seconds - Math.max(0, Math.floor((Date.now() - new Date(sessionStatus.started_at).getTime()) / 1000)))
        : null));
  const formattedRemaining = remainingSeconds !== null ? `${Math.floor(remainingSeconds / 60)}:${String(remainingSeconds % 60).padStart(2, '0')}` : null;

  return (
    <div style={{ maxWidth: '1180px', width: '100%', height: '100vh', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '0.35rem', overflow: 'hidden', boxSizing: 'border-box' }}>
      {showFinishConfirm && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(2, 6, 23, 0.72)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
          <div style={{ width: 'min(440px, calc(100vw - 2rem))', background: '#131B2E', border: '1px solid #2D3A54', borderRadius: '16px', padding: '1.5rem', boxShadow: '0 20px 50px rgba(0,0,0,0.4)' }}>
            <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>⚠️</div>
            <h3 style={{ margin: '0 0 0.75rem', color: '#F8FAFC', fontSize: '1.3rem' }}>¿Seguro que quieres terminar la sesión?</h3>
            <p style={{ color: '#94A3B8', margin: '0 0 1.25rem', lineHeight: 1.5 }}>
              Se cerrará la sesión actual y podrás ver el resumen final con las estadísticas de esta tirada.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
              <button
                onClick={() => setShowFinishConfirm(false)}
                style={{ background: '#1E293B', color: '#E2E8F0', border: '1px solid #334155', padding: '0.7rem 1rem', borderRadius: '8px', cursor: 'pointer', fontWeight: 700 }}
              >
                No
              </button>
              <button
                onClick={handleFinishSession}
                style={{ background: '#EF4444', color: '#FFF', border: '1px solid rgba(239,68,68,0.6)', padding: '0.7rem 1rem', borderRadius: '8px', cursor: 'pointer', fontWeight: 700 }}
              >
                Sí, terminar
              </button>
            </div>
          </div>
        </div>
      )}

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: '#131B2E',
          padding: '0.35rem 0.7rem',
          borderRadius: '10px',
          border: '1px solid #2D3A54',
          gap: '0.35rem',
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', gap: '0.55rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <span style={{ fontSize: '0.78rem' }}>🔥</span>
            <span style={{ fontSize: '0.68rem', color: '#94A3B8' }}>Racha</span>
            <strong style={{ color: streak > 0 ? '#F59E0B' : '#E2E8F0', fontSize: '0.8rem' }}>{streak}</strong>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <span style={{ fontSize: '0.78rem' }}>🎯</span>
            <span style={{ fontSize: '0.68rem', color: '#94A3B8' }}>Precisión</span>
            <strong style={{ color: accuracy >= 80 ? '#10B981' : accuracy >= 60 ? '#F59E0B' : '#EF4444', fontSize: '0.8rem' }}>{accuracy}%</strong>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <span style={{ fontSize: '0.78rem' }}>🃏</span>
            <span style={{ fontSize: '0.68rem', color: '#94A3B8' }}>Manos</span>
            <strong style={{ color: '#E2E8F0', fontSize: '0.8rem' }}>{handsPlayed}</strong>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '0.3rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '0.72rem', color: timerActive ? '#38BDF8' : '#94A3B8', background: '#0F172A', padding: '0.22rem 0.45rem', borderRadius: '6px', border: '1px solid #1E293B', minWidth: '64px', textAlign: 'center' }}>
            ⏱ {timerActive ? `${elapsedMs}ms` : lastAnswer ? `${lastAnswer.response_ms}ms` : '0ms'}
          </div>
          {formattedRemaining && (
            <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '0.7rem', color: '#FBBF24', background: '#111827', padding: '0.22rem 0.45rem', borderRadius: '6px', border: '1px solid #374151', minWidth: '70px', textAlign: 'center' }}>
              ⏳ {formattedRemaining}
            </div>
          )}
          <button onClick={() => setShowMatrixModal((prev) => !prev)} style={{ background: '#1E293B', color: '#CBD5E1', border: '1px solid #334155', padding: '0.24rem 0.5rem', borderRadius: '6px', fontSize: '0.68rem', fontWeight: 700, cursor: 'pointer' }}>
            🗺 Matriz
          </button>
          <button onClick={() => setShowFinishConfirm(true)} style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#FCA5A5', border: '1px solid rgba(239, 68, 68, 0.4)', padding: '0.24rem 0.5rem', borderRadius: '6px', fontSize: '0.68rem', cursor: 'pointer', fontWeight: 700 }}>
            Terminar
          </button>
        </div>
      </div>

      {handData && <PokerTable handData={handData} table={table} />}

      {handData && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem', alignItems: 'center' }}>
          <div style={{ display: 'flex', gap: '0.45rem', flexWrap: 'wrap', justifyContent: 'center', width: '100%', maxWidth: '720px' }}>
            {/* PASO 4 - boton unico Siguiente, atajo Espacio */}
            {phase === 'end' ? (
              <button
                onClick={goToNextHand}
                style={{
                  flex: '1 1 200px',
                  padding: '0.58rem 0.9rem',
                  background: '#2a3340',
                  border: '1px solid rgba(255,255,255,0.12)',
                  borderRadius: '9px',
                  color: '#FFFFFF',
                  fontWeight: 800,
                  fontSize: '0.84rem',
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '0.25rem',
                }}
              >
                <span>Siguiente</span>
                <span style={{ fontSize: '0.7rem', background: 'rgba(0,0,0,0.25)', padding: '0.12rem 0.42rem', borderRadius: '4px', color: 'rgba(255,255,255,0.9)', fontFamily: 'JetBrains Mono, monospace' }}>
                  [Espacio]
                </span>
              </button>
            ) : (
              activeActions.map((act, idx) => {
                const hotkeyDisplay = act.hotkey ? `${act.hotkey}` : `${idx + 1}`;
                const isFoldAction = act.id.toUpperCase() === 'FOLD';
                const textColor = act.text_color || (isFoldAction ? '#111827' : '#FFFFFF');

                return (
                  <button
                    key={act.id}
                    onClick={() => handleAction(act.id)}
                    disabled={evaluating}
                    style={{
                      flex: '1 1 160px',
                      minWidth: '140px',
                      padding: '0.58rem 0.9rem',
                      backgroundColor: act.color,
                      border: '1px solid rgba(255, 255, 255, 0.15)',
                      borderRadius: '9px',
                      color: textColor,
                      fontWeight: 800,
                      fontSize: '0.84rem',
                      cursor: evaluating ? 'default' : 'pointer',
                      boxShadow: '0 2px 8px rgba(0, 0, 0, 0.22)',
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      gap: '0.25rem',
                      transition: 'all 0.1s ease',
                      opacity: evaluating ? 0.6 : 1,
                    }}
                  >
                    <span>{act.label}</span>
                    <span style={{ fontSize: '0.7rem', background: 'rgba(0,0,0,0.25)', padding: '0.12rem 0.42rem', borderRadius: '4px', color: isFoldAction ? '#111827' : 'rgba(255,255,255,0.9)', fontFamily: 'JetBrains Mono, monospace' }}>
                      [{hotkeyDisplay}]
                    </span>
                  </button>
                );
              })
            )}
          </div>

          <div style={{ width: '100%', maxWidth: '720px', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
              <div style={{ minHeight: '38px' }}>
              {errorBanner && (
                  <div style={{ background: 'rgba(239, 68, 68, 0.2)', border: '1px solid #EF4444', color: '#FCA5A5', padding: '0.45rem 0.65rem', borderRadius: '8px', fontSize: '0.76rem' }}>
                  ⚠ {errorBanner}
                </div>
              )}
            </div>

            {/* PASO 2 - el rival que responde, sin feedback de resultado todavia */}
            {villain && (
              <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '4px 8px', borderRadius: '999px', background: 'rgba(15, 23, 42, 0.9)', border: '1px solid rgba(59,130,246,0.4)', color: '#DBEAFE', fontSize: '11px', fontWeight: 700, alignSelf: 'center' }}>
                <span>{villain.actor}</span>
                <span>·</span>
                <span>
                  {handData?.spot === 'VS_MIN_RAISE'
                    ? '4bet all-in'
                    : levelOneAction?.toUpperCase() === 'LIMP'
                    ? (villain.kind === 'ai' ? 'raise all-in' : 'raise normal')
                    : (villain.kind === 'ai' ? '3bet all-in' : '3bet normal')}
                </span>
              </div>
            )}

            {/* PASO 4 - feedback. La mesa se queda tal cual. */}
            {lastAnswer && (
              <div style={{ padding: '0.55rem 0.75rem', borderRadius: '10px', background: lastAnswer.is_correct ? 'linear-gradient(135deg, rgba(16, 185, 129, 0.2), rgba(5, 150, 105, 0.1))' : 'linear-gradient(135deg, rgba(239, 68, 68, 0.25), rgba(185, 28, 28, 0.15))', border: lastAnswer.is_correct ? '1px solid #10B981' : '1px solid #EF4444', color: '#F8FAFC', display: 'flex', alignItems: 'center', gap: '0.7rem' }}>
                <span style={{ fontSize: '1.2rem' }}>{lastAnswer.is_correct ? '✓' : '✗'}</span>
                <div>
                  <div style={{ fontWeight: 800, fontSize: '0.9rem', color: lastAnswer.is_correct ? '#34D399' : '#F87171' }}>{lastAnswer.is_correct ? 'Correcto' : 'Incorrecto'}</div>
                  <div style={{ fontSize: '0.78rem', color: '#E2E8F0', marginTop: '0.05rem', lineHeight: 1.25 }}>{lastAnswer.explanation}</div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {showMatrixModal && handData && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.82)',
            backdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
            padding: '1rem',
          }}
          onClick={() => setShowMatrixModal(false)}
        >
          <div
            style={{
              background: '#0F172A',
              border: '1px solid #2D3A54',
              borderRadius: '16px',
              padding: '1.75rem',
              maxWidth: '720px',
              width: '100%',
              maxHeight: '92vh',
              overflowY: 'auto',
              boxShadow: '0 20px 50px rgba(0, 0, 0, 0.6)',
              display: 'flex',
              flexDirection: 'column',
              gap: '1rem',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#F8FAFC' }}>
                  Matriz de Rango: {handData.scenario_name}
                </h3>
                <p style={{ color: '#94A3B8', fontSize: '0.85rem' }}>
                  Mano resaltada: <strong style={{ color: '#F59E0B' }}>{handData.hand}</strong>
                </p>
              </div>

              <button
                onClick={() => setShowMatrixModal(false)}
                style={{
                  background: '#1E293B',
                  border: '1px solid #334155',
                  color: '#94A3B8',
                  padding: '0.35rem 0.75rem',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontSize: '0.85rem',
                }}
              >
                ✕ Cerrar [Esc]
              </button>
            </div>

            <RangeMatrix
              matrixData={lastAnswer?.full_matrix ?? {}}
              actionsConfig={lastAnswer?.actions_config ?? {}}
              followupsConfig={lastAnswer?.followups_config ?? {}}
              highlightHand={handData.hand}
              compact={false}
              defaultMode={lastAnswer && !lastAnswer.is_correct ? 'detail' : 'action'}
            />

            <div style={{ textAlign: 'center', marginTop: '0.5rem' }}>
              <button
                onClick={() => {
                  setShowMatrixModal(false);
                  if (phase === 'end') {
                    goToNextHand();
                  }
                }}
                style={{
                  background: '#3B82F6',
                  color: '#FFF',
                  border: 'none',
                  padding: '0.65rem 2rem',
                  borderRadius: '8px',
                  fontWeight: 700,
                  cursor: 'pointer',
                  fontSize: '0.95rem',
                }}
              >
                Entendido [Espacio]
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
