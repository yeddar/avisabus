# Fixture `sae_recordings`

## Propósito

Respuestas del SAE de EMT València grabadas en JSON para reproducirlas en los tests mediante
`SaeReplayArrivalsSource`. Los tests nunca acceden a la red (sockets bloqueados).

## Origen de los datos

Sesiones grabadas contra el servicio de llegadas en tiempo real del SAE de EMT València con el
comando de grabación de la CLI. Cada sesión se guarda en una subcarpeta con su nombre
(p. ej. `stop_508_peak/`) y un fichero JSON por petición.

## Regeneración

El comando de grabación (`avisabus sae-record …`) lo añade la feature `sae_arrivals_source`.
Hasta entonces esta carpeta solo contiene este README.
