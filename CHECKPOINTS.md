# CHECKPOINTS.md — Puntos de control humanos

Los agentes **se detienen** en estos puntos y esperan a la persona responsable (autor del TFM).
Un checkpoint pendiente se anota en `progress/current.md` en la sección "Checkpoints pendientes".

## CP-1 · Aprobación de spec

**Cuándo:** una feature está en `spec_draft` (spec nueva o corregida).
**Qué revisa la persona:**
- [ ] `requirements.md` cubre los RF/RNF y CU indicados en `feature_list.json`.
- [ ] Cada criterio de aceptación es verificable y tiene ID `<feature>.AC-n`.
- [ ] `design.md` respeta `docs/architecture.md` y `docs/conventions.md`.
- [ ] `tasks.md` cubre todos los AC y cada tarea es atómica y verificable.
- [ ] El alcance ("Fuera de alcance") es el esperado.

**Cómo se aprueba:** cambiar `Estado: DRAFT` por `Estado: APPROVED` en la cabecera de los tres
ficheros y decir al orquestador "spec <id> aprobada". El orquestador cambia el estado en
`feature_list.json`.

## CP-2 · Escalado por revisión fallida

**Cuándo:** una feature recibe `CHANGES_REQUESTED` por **segunda** vez (`review_cycles = 2`).
**Qué decide la persona:** corregir la spec (vuelve a CP-1), aceptar con deuda anotada,
o dar instrucciones concretas al implementer.

## CP-3 · Spec bloqueada / contradicción

**Cuándo:** un agente encuentra una ambigüedad, un hueco o una contradicción entre `docs/`,
la spec y la realidad (p. ej. el formato real del SAE difiere del previsto).
**Qué hace el agente:** marca la feature `spec_blocked`, describe el problema en su fichero de
`progress/` (sección "Bloqueos") con una propuesta concreta, y se detiene.
**Qué decide la persona:** aceptar la propuesta (→ spec-writer corrige → CP-1) o indicar otra.

## CP-4 · Cambios en `docs/`

**Cuándo:** cualquier modificación de visión, requisitos, casos de uso, arquitectura o
convenciones.
**Regla:** los agentes solo proponen; la persona aplica o autoriza explícitamente.

## CP-5 · Despliegue en la Raspberry Pi

**Cuándo:** antes de desplegar o actualizar en el servidor.
**Qué revisa la persona:** `./init.sh verify` en verde en `main`, `.env` de producción revisado
(secretos, URL pública), copia de seguridad de `data/`.

## CP-6 · Fin de bloque

**Cuándo:** todas las features de un bloque están en `done`.
**Qué hace la persona:** prueba manual del bloque (demo) y confirma que se puede pasar al
siguiente. Se anota en `progress/history.md`.

| Bloque | Features |
|---|---|
| 1 · Cimientos y datos | project_scaffold, gtfs_import, stop_tokens_qr, sae_arrivals_source, occupancy_sensor, stop_arrivals_api |
| 2 · Pasajero | frontend_i18n, passenger_stop_view, position_estimation, passenger_map_view |
| 3 · Avisos | realtime_events, alert_create, alert_cancel, alert_expiry, passenger_alert_ui |
| 4 · Conductor | driver_codes_cli, driver_session, driver_demand, driver_ui, driver_gps_simulator |
| 5 · Despliegue y validación | deployment_rpi, nfr_validation |
