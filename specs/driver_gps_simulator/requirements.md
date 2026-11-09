# Simulador de recorrido del conductor — requirements

> Feature: `driver_gps_simulator` · Versión: 1.0 · Estado: DRAFT
> Requisitos: RF-34, RNF-07 · Casos de uso: CU-14 · Depende de: driver_session

## Contexto

Para probar y enseñar la vista del conductor sin subir a un autobús (OBJ-08), un comando de la
CLI hace de tablet: inicia un turno con un código, elige una salida y envía posiciones a lo largo
del trazado del viaje a la velocidad indicada, deteniéndose en las paradas; al final del
recorrido cierra el turno (CU-14). Usa **la misma API HTTP** que la tablet, así que el servidor
se comporta exactamente igual que con un conductor real.

## Alcance

- Comando `avisabus simulate`.
- Generación de posiciones sobre el trazado (puro y determinista).

## Fuera de alcance

- Simular varios conductores a la vez (se lanzan varios procesos) y carga (`nfr_validation`).

## Criterios de aceptación

- **driver_gps_simulator.AC-01** — CUANDO se ejecuta `avisabus simulate --line L --direction D
  [--departure HH:MM | --trip TRIP_ID] [--speed-kmh 20] [--interval-s 5] [--dwell-s 15]
  [--base-url http://localhost:8000]` con el código en `--code` o en `AVISABUS_SIM_CODE`, EL
  SIMULADOR DEBERÁ iniciar un turno por la API, elegir la salida (sin `--departure` ni `--trip`,
  la primera no ocupada de `GET /driver/departures`; con `--departure`, la de esa hora) y empezar
  a enviar posiciones.
  *Verificación:* integration (contra la app en proceso con `httpx.ASGITransport`, sin red)
- **driver_gps_simulator.AC-02** — LAS POSICIONES DEBERÁN recorrer el trazado del viaje desde la
  primera parada, avanzando `velocidad × intervalo` metros por envío, y detenerse `--dwell-s`
  segundos en cada parada del viaje; con `--noise-m N --seed S` DEBERÁN desplazarse como mucho
  N metros de forma reproducible.
  *Verificación:* unit (generador puro: distancias, paradas, ruido con semilla)
- **driver_gps_simulator.AC-03** — CUANDO la posición alcanza la última parada, o el usuario
  interrumpe con Ctrl+C, EL SIMULADOR DEBERÁ finalizar el turno (`DELETE …/current`) y terminar
  con código 0.
  *Verificación:* integration (interrupción simulada)
- **driver_gps_simulator.AC-04** — SI el código no es válido, la línea, el sentido o la salida no
  existen, o la salida está ocupada, ENTONCES EL SIMULADOR DEBERÁ terminar con código 1 y un
  mensaje claro (con la lista de salidas disponibles cuando la elegida no existe), sin dejar un
  turno abierto.
  *Verificación:* integration
- **driver_gps_simulator.AC-05** — EL SIMULADOR DEBERÁ mostrar por consola, en cada envío, la
  distancia recorrida, la próxima parada y el estado del turno (de `GET …/current`), y NO DEBERÁ
  mostrar el código ni el token.
  *Verificación:* integration (salida capturada)

## Trazabilidad

| Requisito | AC |
|---|---|
| RF-34 Simulador de GPS | AC-01, AC-02, AC-03 |
| RNF-07 Seguridad | AC-04, AC-05 |
| CU-14 | AC-01 … AC-04 |
