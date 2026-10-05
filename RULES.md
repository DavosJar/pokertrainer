# RULES.md

Reglas operativas del proyecto. Son de cumplimiento obligatorio para cualquier agente o modelo que implemente o verifique funcionalidad.

## 1. Durante el desarrollo se usa una BD temporal

Al implementar o verificar cualquier funcionalidad se trabaja contra la **base de datos temporal (`dev`)**. Está prohibido crear, responder, editar o borrar filas en la base de datos real (`prod`) como parte de una implementación o una verificación.

La base real contiene el historial de práctica y las estadísticas. Ensuciarla con datos de prueba no se puede deshacer y falsea las métricas del dashboard, así que el trabajo de desarrollo va siempre a un lado separado.

## 2. Solo existen dos entornos

| `APP_ENV` | Archivo de BD | Uso |
| --- | --- | --- |
| `dev` | `data/poker_trainer.dev.db` | Temporal. Todo el desarrollo y las verificaciones. |
| `prod` | `data/poker_trainer.db` | Real. Práctica y estadísticas. Solo cuando la pide una persona. |

No hay más entornos. No se inventan `test`, `staging`, `qa`, `local` ni equivalentes: si necesitas un tercer estado, no lo resuelvas con otro valor de `APP_ENV`.

### Cómo se resuelve

- Sin `APP_ENV` o vacía, la app usa **`prod`**.
- Un valor distinto de `dev` o `prod` detiene el arranque con un error, en vez de caer silenciosamente en la base real.
- La BD `dev` se crea sola al arrancar, con las tablas y los 2 escenarios sincronizados desde `data/scenarios/*.json`. No hace falta ningún paso previo.
- La variable se puede pasar por consola (PowerShell: `$env:APP_ENV='dev'`) o en un `.env` en la raíz del proyecto. La consola tiene prioridad sobre `.env`. Copia `.env.example` a `.env` si quieres dejar `dev` como valor por defecto.
- Al arrancar, el servidor imprime con qué entorno y contra qué archivo está escribiendo:

```text
[STARTUP] APP_ENV=dev  DB=C:\...\trainer\data\poker_trainer.dev.db
```

Si esa línea dice `prod` y no debería, detente antes de continuar.

## 3. Cómo trabajar

```powershell
# Desarrollo y verificación: siempre en dev
$env:APP_ENV='dev'
python run.py
python -m pytest -q

# La base real, solo si una persona lo pide explícitamente
$env:APP_ENV='prod'
python run.py
```

Ejecuta los tests con `APP_ENV=dev` también. Aunque `tests/conftest.py` usa una base SQLite en memoria, el arranque de la aplicación sincroniza los escenarios contra el motor real, y ese camino no pasa por el override de dependencias.

La BD `dev` es desechable. Para empezar de cero:

```powershell
Remove-Item data\poker_trainer.dev.db -Force
```

Se reconstruye sola en el siguiente arranque.

## 4. Lo que nunca se hace

- No apuntar el desarrollo a `data/poker_trainer.db`.
- No borrar filas de `data/poker_trainer.db` para "empezar de cero". Si hay que resetear algo, se resetea la `dev`.
- No crear `.env` con un valor de `APP_ENV` distinto de `dev` o `prod`.
- No relajar la validación de `APP_ENV` para que un valor inválido caiga en `prod`.

## 5. Implementación de esta regla

- `app/database.py` resuelve `APP_ENV` y construye la ruta de la BD. Es el único lugar donde se decide qué archivo se abre.
- `VALID_ENVS = ("dev", "prod")` es la lista cerrada de entornos permitidos.
- `.env.example` documenta la variable para copiar.
- `data/poker_trainer.dev.db` es la temporal. Es desechable: se puede borrar y se regenera sola.
