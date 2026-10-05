SECUENCIA EXACTA DE UNA MANO. Respeta el ORDEN. Nada ocurre antes de su paso.
Montos en BB. Ejemplo con stack efectivo 12.5 BB, hero en BTN.

PASO 0 - REPARTO (estado inicial)
Se ve: ficha SB 0.5 BB, ficha BB 1 BB, hero SIN ficha.
Stacks: SB 12 BB, BB 11.5 BB, hero 12.5 BB. Pot 1.5 BB.
Hero ve sus 2 cartas. Los rivales muestran cartas boca abajo.
Botones: Open Shove, OR 2 BB, Fold. El cronometro arranca AQUI.
Los rivales NO han hecho nada y NO van a hacer nada hasta que hero actue.

PASO 1 - HERO ELIGE (el rival NO reacciona todavia)
Al hacer clic se detiene el cronometro y se evalua contra la accion correcta del JSON.

Caso A, hero elige Fold:
  Despues: no aparece ficha. Mano termina. Feedback: Correcto o Incorrecto, era X.

Caso B, hero elige Open Shove:
  Despues: ficha de hero ALL-IN 12.5 BB, stack hero 0 BB, pot 14 BB. Mano termina. Feedback.

Caso C, hero elige OR:
  Despues: ficha de hero 2 BB, stack hero 10.5 BB, pot 3.5 BB.
  - Si OR era INCORRECTO: la mano termina aqui con feedback. NO hay respuesta del rival.
  - Si OR era CORRECTO: pasa al PASO 2.

PASO 2 - RESPUESTA DEL RIVAL (solo si hero hizo OR correcto)
Se elige AL AZAR: que rival responde (SB o BB) y que tipo (3bet normal o 3bet all-in).
En el MISMO instante:
  - El rival que responde reemplaza su ficha: 3bet normal = ficha 4 BB. All-in = ficha ALL-IN 12.5 BB.
  - El otro rival tira la mano: su ficha desaparece, su monto pasa a dinero muerto (dead),
    sus cartas se atenuan.
Ejemplo SB 3bet normal: ficha SB 4 BB, stack SB 8.5, ficha BB desaparece, dead = 1.
  Pot = 2 (hero) + 4 (SB) + 1 (dead) = 7 BB.
Ejemplo SB all-in: ficha SB ALL-IN 12.5, stack SB 0, dead = 1. Pot = 2 + 12.5 + 1 = 15.5 BB.
Los botones CAMBIAN ahora y el cronometro se REINICIA en este punto:
  - vs 3bet normal: Fold, Call, All-in.
  - vs 3bet all-in: solo Fold, Call.
Hero NO puede responder antes de que esto aparezca.

PASO 3 - HERO RESPONDE AL 3BET (ejemplo SB 3bet normal, pot 7)
Al hacer clic se detiene el cronometro y se evalua contra followup.vs_3bet
(o followup.vs_3bet_ai si fue all-in).
  Fold:   ficha de hero desaparece, sus 2 BB pasan a dead (dead = 3). Pot = 4 + 3 = 7.
  Call:   ficha de hero pasa de 2 a 4 BB, stack hero 8.5. Pot = 4 + 4 + 1 = 9.
  All-in: ficha de hero ALL-IN 12.5, stack hero 0. Pot = 12.5 + 4 + 1 = 17.5.
Ejemplo vs all-in del SB: Call -> ficha hero 12.5, pot = 12.5 + 12.5 + 1 = 26.
                          Fold -> dead = 3, pot = 12.5 + 3 = 15.5.

PASO 4 - FEEDBACK Y SIGUIENTE
Se muestra Correcto o Incorrecto con la accion correcta. La mesa se queda tal cual
(no se limpia hasta pasar a la siguiente mano). Boton unico Siguiente, atajo Espacio.
Se guarda la respuesta en SQLite UNA vez por decision, con su tiempo propio:
nivel 1 en el paso 1, nivel 2 en el paso 3.

REGLAS DE CALCULO
- Pot = suma de todas las fichas en mesa + dinero muerto. Nunca se escribe a mano.
- Stack mostrado = stack efectivo menos la ficha de ese jugador.
- Ciegas, min raise (2) y 3bet (4) salen de CONFIG. Stack sale del stack_range del escenario.

PROHIBIDO
- Mostrar la respuesta del rival antes de que hero haga OR.
- Mostrar el resultado o el feedback antes de que hero haga clic.
- Cambiar el diseno de table_mockup.html. Solo conectar datos.
- Dejar fichas o montos de la mano anterior en la mesa al repartir.