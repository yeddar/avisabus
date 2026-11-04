import { describe, expect, it } from 'vitest';

import type { PositionResponse } from '../../../../shared/api/types';
import { initI18n } from '../../../../shared/i18n/i18n';
import type { Language } from '../../../../shared/i18n/languages';
import {
  POSITION_EN_ROUTE,
  POSITION_NO_ARRIVAL,
  POSITION_NOT_STARTED,
} from '../../../../test/fixtures/api';
import { buildSummary, summaryParts, summaryPlainText } from '../summary';

/** generated_at of the fixtures: 08:40 in València. */
const NOW = new Date('2026-11-04T07:40:00Z');
const FIRST_STOP = 'Avinguda del Cid';

function summarize(
  position: PositionResponse,
  { lang = 'es' as Language, firstStop = FIRST_STOP as string | null, now = NOW } = {},
) {
  const i18n = initI18n({ language: lang });
  const summary = buildSummary(position, firstStop, i18n.t, lang, now);
  return { ...summary, plain: summaryPlainText(summary.text) };
}

function enRoute(stopsAway: number, distance = 3403): PositionResponse {
  const p = POSITION_EN_ROUTE();
  p.position = { ...p.position!, stops_away: stopsAway, distance_to_stop_m: distance };
  return p;
}

describe('buildSummary', () => {
  it('[passenger_map_view.AC-04] EN_ROUTE: distance, stops away, next stop and minutes', () => {
    expect(summarize(POSITION_EN_ROUTE()).plain).toBe(
      'El autobús está a 3,4 km de tu parada, a 3 paradas. Próxima parada: Cid - Hospital General. Llega en 5 minutos.',
    );
  });

  it('[passenger_map_view.AC-04] EN_ROUTE in Valencian', () => {
    expect(summarize(POSITION_EN_ROUTE(), { lang: 'ca' }).plain).toBe(
      "L'autobús està a 3,4 km de la teua parada, a 3 parades. Pròxima parada: Cid - Hospital General. Arriba en 5 minuts.",
    );
  });

  it.each([
    ['es', 1, 'a 1 parada'],
    ['es', 0, 'es la siguiente parada'],
    ['ca', 1, 'a 1 parada'],
    ['ca', 0, 'és la parada següent'],
  ] as const)(
    '[passenger_map_view.AC-04] EN_ROUTE (%s) with %i stops away says "%s"',
    (lang, n, text) => {
      expect(summarize(enRoute(n, 850), { lang }).plain).toContain(
        `a 850 m de ${lang === 'es' ? 'tu' : 'la teua'} parada, ${text}.`,
      );
    },
  );

  it('[passenger_map_view.AC-04] the arrival counts down with the server time and says "Está llegando." at 0', () => {
    const p = POSITION_EN_ROUTE(); // arrival_at 07:45:00, 5 min
    expect(summarize(p, { now: new Date('2026-11-04T07:42:30Z') }).plain).toMatch(
      /Llega en 3 minutos\.$/,
    );
    expect(summarize(p, { now: new Date('2026-11-04T07:44:30Z') }).plain).toMatch(
      /Llega en 1 minuto\.$/,
    );
    expect(summarize(p, { now: new Date('2026-11-04T07:45:00Z') }).plain).toMatch(
      /Está llegando\.$/,
    );
    expect(summarize(p, { lang: 'ca', now: new Date('2026-11-04T07:45:00Z') }).plain).toMatch(
      /Està arribant\.$/,
    );
  });

  it('[passenger_map_view.AC-04] a clock-time arrival is said as "Llega a las HH:MM." in València time', () => {
    const p = POSITION_EN_ROUTE();
    p.arrival = {
      ...p.arrival!,
      kind: 'CLOCK_TIME',
      minutes: null,
      arrival_at: '2026-11-04T08:52:00Z',
    };

    expect(summarize(p).plain).toMatch(/Llega a las 09:52\.$/);
    expect(summarize(p, { lang: 'ca' }).plain).toMatch(/Arriba a les 09:52\.$/);
  });

  it('[passenger_map_view.AC-04] AT_STOP', () => {
    const p = POSITION_EN_ROUTE();
    p.status = 'AT_STOP';
    p.position = { ...p.position!, stops_away: 0, distance_to_stop_m: 0 };

    expect(summarize(p).plain).toBe('El autobús está llegando a tu parada.');
    expect(summarize(p, { lang: 'ca' }).plain).toBe("L'autobús està arribant a la teua parada.");
  });

  it('[passenger_map_view.AC-04] NOT_STARTED names the first stop of the shape, not the next stop', () => {
    const p = POSITION_NOT_STARTED(); // next_stop is the second stop, "Cid - Marconi"

    expect(summarize(p).plain).toBe(
      'El autobús aún no ha salido de Avinguda del Cid. Llega a las 08:58.',
    );
    expect(summarize(p, { lang: 'ca' }).plain).toBe(
      "L'autobús encara no ha eixit d'Avinguda del Cid. Arriba a les 08:58.",
    );
  });

  it('[passenger_map_view.AC-04] NOT_STARTED without the shape says "la primera parada del recorrido"', () => {
    const p = POSITION_NOT_STARTED();
    p.arrival = { ...p.arrival!, kind: 'MINUTES', minutes: 18, arrival_at: '2026-11-04T07:58:00Z' };

    expect(summarize(p, { firstStop: null }).plain).toBe(
      'El autobús aún no ha salido de la primera parada del recorrido. Llega en 18 minutos.',
    );
    expect(summarize(p, { firstStop: null, lang: 'ca' }).plain).toBe(
      "L'autobús encara no ha eixit de la primera parada del recorregut. Arriba en 18 minuts.",
    );
  });

  it.each([
    [
      'NO_ARRIVAL',
      'es',
      'Posición no disponible en este momento. No hay llegadas previstas de esta línea en tu parada.',
    ],
    [
      'NO_ARRIVAL',
      'ca',
      "Posició no disponible en este moment. No hi ha arribades previstes d'esta línia en la teua parada.",
    ],
    [
      'NO_VEHICLE',
      'es',
      'Posición no disponible en este momento. No se puede situar en el recorrido el autobús de la próxima llegada.',
    ],
    [
      'NO_VEHICLE',
      'ca',
      "Posició no disponible en este moment. No es pot situar en el recorregut l'autobús de la pròxima arribada.",
    ],
  ] as const)(
    '[passenger_map_view.AC-04] %s (%s): unavailable and the reason',
    (status, lang, text) => {
      const p = POSITION_NO_ARRIVAL();
      p.status = status;

      expect(summarize(p, { lang }).plain).toBe(text);
    },
  );

  it('[passenger_map_view.AC-04] distance, stops and time are emphasised and GTFS names marked', () => {
    const parts = summaryParts(summarize(POSITION_EN_ROUTE()).text);

    expect(parts.filter((part) => part.kind === 'strong').map((part) => part.text)).toEqual([
      '3,4 km',
      'a 3 paradas',
      '5 minutos',
    ]);
    expect(parts.filter((part) => part.kind === 'name').map((part) => part.text)).toEqual([
      'Cid - Hospital General',
    ]);
  });

  it.each([
    ['REALTIME', 'estimated'],
    ['SCHEDULED', 'scheduled'],
  ] as const)('[passenger_map_view.AC-05] source %s gives the badge "%s"', (source, badge) => {
    for (const p of [POSITION_EN_ROUTE(), POSITION_NO_ARRIVAL()]) {
      p.source = source;
      expect(summarize(p).badge).toBe(badge);
    }
  });
});
