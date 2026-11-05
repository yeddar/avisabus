# Exploración: detección de paso con el SAE (ventana de `PASSED`)
Feature(s): alert_expiry (v1.0, E-01) · Fecha: 2026-11-04 · Agente: explorer

## Pregunta(s)

**E-01** (`specs/alert_expiry/tasks.md`): con `stop_508_peak` (paradas 508 y 2070) y `gtfs_mini`,
simular la detección de paso de AC-01/AC-02 para cada viaje de las líneas en red, cada 20 s:

1. ¿Cuántos viajes desaparecen con ≤ 1, ≤ 2 y ≤ 3 min en su última observación?
2. ¿Cuántos desaparecen estando lejos (cambio de viaje del emparejamiento)?
3. ¿Algún viaje desaparece y vuelve a aparecer?
4. ¿Con qué ventana se detectan más pasos sin ningún paso prematuro?

Condición de CP-3: ninguna ventana entre 1 y 3 min evita los pasos prematuros, o casi ningún paso
es detectable.

## Hallazgos

### Método (reproducible; scripts y salidas en `progress/explore_passage_samples/`)

- **Código real del proyecto, sin red ni reloj real.** `collect.py` usa la composición de los
  tests de integración:
  - `build_stop_use_cases(stops_settings(), …)`: `GetStopArrivals` con `match_trips` y la
    configuración por defecto (`trip_match_tolerance_min = 10`, `alert_max_lead_min = 30`,
    `sae_cache_ttl_s = 20`).
  - `replay(STOP_508_PEAK, clock)` de `tests/support/stops.py`: `SaeReplayArrivalsSource` detrás
    del `CachedArrivalsSource` de producción.
  - `FakeClock` desde `started_at` (2026-11-02T19:42:23.769219Z), avanzando 20 s.
  - `gtfs_mini` importado con `import_feed` en una SQLite del *scratchpad*, no en
    `data/avisabus.sqlite`.
  - Se ejecuta en la rama `feat/alert_expiry`, que incluye alert_create.
- **Lo que se recoge.** En cada ciclo se llama a `execute("508")` y luego a `execute("2070")`. De
  cada llegada se guarda: línea, sentido, minutos, `vehicle` (`trip_id`, `service_date`) y
  `can_alert`. También la antelación `lead = arrival_at − generated_at`, que es exactamente
  `last_arrival_at − last_seen_at` de AC-02, porque alert_create fija `last_seen_at = generated_at`
  (`application/create_alert.py:134`). Por último, el retraso respecto a la parada del viaje (misma
  regla que `CreateAlert._occurrence`) y la hora programada en la parada siguiente.
- **Comandos.**
  `cd backend && uv run python ../progress/explore_passage_samples/collect.py <scratch> 20`
  da `cycles=75 sae_requests=150 rows=883`. Después,
  `python3 -I progress/explore_passage_samples/analyze.py <scratch>/observations_20.json`, cuya
  salida está en `analysis_20s.txt`, y `timeline.py`, cuya salida está en `timeline_20s.txt` (todas
  las llegadas en red, ciclo a ciclo).
- **Cobertura.** Las 150 respuestas son `REALTIME`. Las llegadas en red son la 93 y la 70 en la
  508 y la 98 en la 2070; la 73, la 95 y la 99 de la 2070 no están en `gtfs_mini` y no tienen
  `vehicle`. Todas las llegadas en red quedan emparejadas con un viaje y tienen `can_alert = true`.
  En total se siguen **13 viajes**: 5 de la 93 (`…_122` a `…_126`), 4 de la 70 (`…_070` a `…_073`)
  y 4 de la 98 (`…_059` a `…_062`).
- **Desaparición.** Hay una desaparición cuando el viaje (`trip_id` + `service_date`) está en el
  ciclo c−1 y no en el c. Lo que haría AC-02 depende de la antelación L que tenía en c−1.
- **Paso real o prematuro, sin mirar los `trip_id`.** Para saber si el autobús se ha ido de verdad
  (verdad de campo), se cuenta en c−1 y en c cuántas llegadas de la misma línea y sentido tienen
  antelación ≤ L + 120 s:
  - si el número **baja**, el autobús ha salido de la lista (**GONE**);
  - si no baja, el autobús **sigue** en la lista con otro `trip_id` (**STILL**).

  Un `PASSED` sobre un evento STILL es un **paso prematuro**. Los casos dudosos se revisaron a mano
  con el texto bruto del SAE.

### Respuesta 1: desapariciones según la antelación de la última observación (cadencia 20 s)

| Última antelación | Desapariciones | Autobús GONE | Autobús STILL (prematuro si se diera `PASSED`) |
|---|---|---|---|
| ≤ 1 min | **3** | 3 | 0 |
| ≤ 2 min | **4** | 4 | 0 |
| ≤ 3 min | **4** | 4 | 0 |
| ≤ 4 min | 6 | 5 | 1 |
| total | 20 | 7 | 13 |

Las 4 desapariciones con ≤ 3 min (extracto de `analysis_20s.txt`):

```
508  70 070 c26 t= 520s last=2m(120s) GONE  [2m:070, 12m:071] -> [11m:071]
508  70 071 c59 t=1180s last=0m(0s)   GONE  [0m:071, 12m:072] -> [11m:072, 23m:073]
508  93 122 c39 t= 780s last=0m(0s)   GONE  [0m:122, 2m:123]  -> [0m:123, 12m:124]
508  93 123 c52 t=1040s last=0m(0s)   GONE  [0m:123, 9m:124]  -> [8m:124, 17m:125]
```

Notas:

- Ninguna desaparición tiene una última antelación de 180 s. La última observación de la 070
  daba **exactamente 120 s**, porque a 20 s la caché siempre está fresca y
  `lead = minutos × 60`. Así que el `≤` de AC-02 tiene que ser inclusivo: con `<` se pierde ese
  paso.
- Coinciden con los pasos del README de las fixtures (70 a los 520 s y a los 1180 s, 93 a los
  1040 s) y añaden uno de la 93 a los 780 s, que el detector de `test_sae_fixtures.py` no ve
  porque la primera ETA pasa de 0 a 0 (el segundo autobús ya estaba a 2 min).

### Respuesta 2: desapariciones estando lejos (> 3 min)

Hay **16** desapariciones con más de 3 min:

- **13 son cambios de viaje del emparejamiento.** El autobús sigue en la lista con otro
  `trip_id`:
  - **11 en la 2070.** La segunda 98, a 24–29 min, alterna entre `…_060` (retraso ≈ +355 s) y
    `…_061` (≈ −393 s) casi en cada ciclo. Ambos están dentro de la tolerancia y gana la menor
    desviación total, que cambia cuando el reloj avanza 20 s. Va de c1 a c16.
  - **`…_060` en c45**, a 16 min: pasa a `…_061`.
  - **La 70 en c69–c70.** El SAE baja un momento la ETA de 8 a 4 min y luego la sube a 7. Ver la
    respuesta 3.
- **3 son autobuses que salen de la lista estando lejos:**
  - `98 …_059` en c17, a 4 min (240 s). Probable paso real con ETA atascada; queda sin detectar con
    W ≤ 3 min.
  - `98 …_061` en c22, a 27 min. El SAE deja de dar la segunda 98 durante 6 ciclos.
  - `93 …_125` en c61, a 15 min. El SAE la sustituye por una de 23 min.

Con cualquier ventana de 1 a 3 min, ninguna de ellas provoca `PASSED`, que es lo que pide LIM-02.

**Caso adicional, sin desaparición:** el emparejamiento traslada el viaje al autobús siguiente.

```
c14 t=280  508/93: [0m:122, 12m:123]     (SAE: "Pass. Marítim - Próximo")
c15 t=300  508/93: [7m:122, 11m:123]     (el autobús "Próximo" ya no está; aparece uno a 7 min)
```

- A los ~290 s pasa un autobús de la 93. Lo más probable es que sea el viaje 121, programado a los
  −23 s y con unos 5 min de retraso.
- El emparejamiento lo había llamado `…_122`, y en c15 asigna `…_122` al autobús siguiente
  (retraso +229 s). El viaje **no desaparece**: AC-02 no ve el paso con ninguna ventana y AC-05
  tampoco, porque el viaje sigue presente.
- Un aviso creado en c0–c14 sobre el "93 en 6 min" sigue al autobús siguiente y caduca como
  `PASSED` en c39 (780 s), **unos 490 s tarde**. Es un caso de LIM-02 (caduca tarde, no antes),
  pero no está descrito en la spec. Ver "Impacto".

### Respuesta 3: viajes que desaparecen y vuelven a aparecer

Sí: **13 eventos en 4 viajes**.

- **`…_060` y `…_061` de la 98 en la 2070** (11 eventos). Son la alternancia descrita arriba, a
  24–29 min, más el hueco de `…_061` entre c22 y c27.
- **`…_072` de la 70.** Desaparece en c69 a 8 min y vuelve en c70.
- **`…_071` de la 70.** Es el único caso con la última antelación ≤ 3 min:
  - en c59 desaparece a 0 min: es un paso real (1180 s) y `PASSED` es correcto;
  - en **c69 reaparece a 4 min**, pero es la etiqueta del autobús `…_072` durante un ciclo, porque
    el SAE baja la ETA de 8 a 4 min;
  - en c70 vuelve a desaparecer a 4 min (240 s) mientras el autobús sigue en la lista (`STILL`).

  Como en c69 tiene `can_alert = true`, un pasajero podría crear un aviso nuevo sobre `…_071`. Con
  una ventana ≥ 4 min, ese aviso caducaría como `PASSED` prematuramente en c70.

### Respuesta 4: barrido de ventanas

Supuestos de la variante A: un aviso por viaje desde su primera aparición, que caduca como
`PASSED` en la primera desaparición con L ≤ W. La variante B, además, vuelve a crear el aviso cuando
un viaje reaparece después de un `PASSED`.

| W | `PASSED` (A) | Correctos | Prematuros (A) | Prematuros (B) | Pasos reales detectados* |
|---|---|---|---|---|---|
| 0–90 s (≤ 1 min) | 3 | 3 | 0 | 0 | 3 / 6 |
| **120 s (2 min)** | **4** | **4** | **0** | **0** | **4 / 6** |
| 150–180 s (3 min) | 4 | 4 | 0 | 0 | 4 / 6 |
| 240 s (4 min) | 5 | 5 | 0 | **1** (`70 …_071` c70) | 5 / 6 |
| 600 s (10 min) | 6 | 5 | **1** (`70 …_072` c69) | 1 | 5 / 6 |

\* Hay **6 pasos reales seguros**, revisados con el texto del SAE:

| Línea | Ciclos (instante) | ¿Se detectan con W = 2 min? |
|---|---|---|
| 93 | c15 (~290 s), c39 (780 s), c52 (1040 s) | c39 y c52 sí; c15 no se puede detectar |
| 70 | c26 (520 s), c59 (1180 s) | Sí |
| 98 | c17 (340 s) | No: necesita W ≥ 4 min |

Además hay un caso dudoso, el `0m → 4m` de la 98 en c13. Y el heurístico marca la 70 en c71
(`4m → 7m`), que es un falso positivo: se descarta porque la ETA vuelve a la del autobús de c68.

- **W = 1 min** pierde el paso de la 70 a los 520 s. Su última observación era de 2 min, porque el
  SAE la había retrasado de 0 a 2 min en c24. Lo recogería `NEXT_STOP` a los 826 s, 306 s tarde.
- **W = 2 min y W = 3 min** dan el mismo resultado (4 correctos y 0 prematuros). W = 2 min deja
  120 s de margen hasta el primer caso prematuro observado (240 s); W = 3 min deja solo 60 s.
- **Los pasos que no detecta `PASSED`** (con W = 2 min):
  - `98 …_059` (c17): `NEXT_STOP` caducaría el aviso a los 803 s, 463 s después de desaparecer.
  - `93`, c15: no lo cubre ninguna regla hasta c39 (ver arriba).

### Contraste a la cadencia de producción (15 s y caché de 20 s; `analysis_15s.txt`)

- `collect.py … 15` da 99 ciclos con **100 peticiones al SAE**: con TTL 20 s, el vigilante solo ve
  una respuesta fresca cada 30 s. En los ciclos servidos desde la caché,
  `lead = minutos × 60 − 15 s`: 105 s para "2 min", 225 s para "4 min" y −15 s para "Próximo".
- Los resultados son los mismos: con W de 2 a 3 min hay 4 `PASSED` correctos y 0 prematuros, y el
  primer prematuro aparece con W ≥ 225 s (variante B, `…_071`).

### Lo que esperaría AC-11 (93 en la 508, W = 2 min, avisos al principio y con cada autobús nuevo)

| Viaje | Aviso creado | Resultado al final de la sesión |
|---|---|---|
| `…_122` | c0 | `PASSED` en c39, 1 ciclo después de su última observación con ≤ 2 min (c38) |
| `…_123` | c0 | `PASSED` en c52, 1 ciclo después de c51 |
| `…_124` | c39 | Vivo |
| `…_125` | c52 | Vivo. Se pierde lejos en c61; `NEXT_STOP` sería a los 2295 s, después del final |
| `…_126` | c61 | Vivo |

- Recuento: **PASSED = 2, NEXT_STOP = 0, TIMEOUT = 0, vivos = 3**. Ningún aviso llega a 30 min
  dentro de los 1480 s.
- Se cumplen (a) y (b). Pero (a), tal como está escrita, es tautológica: si el viaje aparece, AC-02
  no puede dar `PASSED`. Ver "Impacto".

## Impacto en la spec

1. **Ventana: sin cambios.** El valor por defecto `AVISABUS_PASSAGE_WINDOW_MIN = 2` es el mejor de
   los medidos: el máximo de pasos detectados sin ningún prematuro y el mayor margen. Está dentro
   del rango que permite design §7. **No hace falta CP-3.**
2. **AC-11 (a): reformulación recomendada, no bloqueante** (`requirements.md`, AC-11). Propuesta:
   "NINGÚN aviso DEBERÁ caducar como `PASSED` en un ciclo en el que su autobús siga en la lista
   del SAE, es decir, cuando el número de llegadas de su línea y sentido con antelación ≤ (última
   antelación del viaje + 2 min) no disminuye respecto al ciclo anterior". Así el test comprueba
   de verdad que no hay pasos prematuros. Si la persona no quiere tocar la spec, el implementer
   puede añadir esta comprobación como aserción extra en T-05.
3. **LIM-02: documentar el traslado del viaje sin desaparición** (`requirements.md`, Contexto;
   opcionalmente `docs/` LIM-02, lo decide la persona). Propuesta de texto: "si el emparejamiento
   pasa el viaje del aviso al autobús siguiente sin que desaparezca, el aviso sigue a ese autobús
   y caduca con él (observado: unos 8 min tarde)". Es una limitación de ADR-016 y del
   emparejamiento, no de la ventana. Una regla de salto de ETA (por ejemplo, `PASSED` si L ≤ W y
   la nueva antelación supera L + 3 min) la detectaría, pero **no la recomiendo**: también saltaría
   con re-predicciones del SAE como el `0 → 4 min` dudoso de la 98 en c13, en contra de "caducar
   tarde antes que antes de tiempo".
4. **Aclaraciones para la implementación**, ya compatibles con la spec:
   - el `≤` de AC-02 es inclusivo, y la tabla de AC-02 ya incluye el caso de 2 min;
   - `observed_at` debe ser `StopArrivals.generated_at`, coherente con alert_create;
   - con la caché, la antelación incluye la edad de la respuesta (hasta −20 s).

## Riesgos

- **Una sola sesión de 25 min, por la tarde y fuera de hora punta:** 6 pasos reales seguros. El
  margen entre W = 2 min y el primer prematuro (4 min) sale de un único caso (`…_071`, c70).
- **La verdad de campo es heurística**, sin GPS: el recuento de llegadas ≤ L + 120 s. Los casos
  dudosos (98 c13, 93 c15, 70 c71) se revisaron a mano. El de la 98 en c17 (4 min y desaparece)
  puede ser un paso con ETA atascada o un autobús que el SAE retira.
- **Bloque 4:** con el traslado del viaje (93 en c15), el conductor del autobús siguiente
  recibiría la solicitud de alguien que ya subió al anterior.
- **Alternancia de viajes** a 24–29 min en la 98 (2070): no afecta a `PASSED`. Para `NEXT_STOP`
  solo importa el último retraso observado, que en esos casos puede ser de unos ±6 min. No se ha
  visto ningún `NEXT_STOP` prematuro en la sesión, pero no se ha estudiado a fondo porque queda
  fuera de E-01.

## Recomendación

- Implementar alert_expiry tal cual, con `AVISABUS_PASSAGE_WINDOW_MIN = 2`.
- **No se cumple la condición de CP-3**:
  - las ventanas de 1, 2 y 3 min dan 0 pasos prematuros;
  - con 2 min se detectan 4 de los 6 pasos reales seguros;
  - de los dos que faltan, uno lo recoge `NEXT_STOP` y el otro no se puede detectar con ninguna
    ventana.
- Recomendado, no bloqueante: reformular AC-11 (a) y documentar en LIM-02 el traslado del viaje
  (puntos 2 y 3 de "Impacto"). Lo decide la persona y lo redacta el spec-writer si se acepta.
- Para T-05: contrastar con `PASSED = 2` (`…_122` en c39 y `…_123` en c52) y 3 avisos vivos en la
  93.

## Resumen para el orquestador

- E-01 hecha con el código real (`GetStopArrivals`/`match_trips`, tolerancia 10 min, caché 20 s),
  `FakeClock` y `gtfs_mini` en el *scratchpad*.
- Desapariciones: 3 con ≤ 1 min, 4 con ≤ 2 min y 4 con ≤ 3 min, todas pasos reales. Hay 16
  lejanas, de ellas 13 por cambio de viaje del emparejamiento. 13 reapariciones en 4 viajes; solo
  una tras ≤ 3 min (`70 …_071`, que vuelve como etiqueta de otro autobús).
- Ventana recomendada: **2 min** (sin cambios). Detecta 4 de 6 pasos reales sin prematuros; el
  primer prematuro aparece con 4 min. **No hay CP-3**: la spec puede implementarse tal cual.
- Mejoras opcionales: reformular AC-11 (a), que es tautológica, y documentar en LIM-02 que el
  viaje puede pasar al autobús siguiente sin desaparecer (aviso unos 8 min tarde).
