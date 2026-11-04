import { describe, expect, it } from 'vitest';

import { busIcon } from '../busIcon';

function html(icon: ReturnType<typeof busIcon>): HTMLElement {
  const element = document.createElement('div');
  element.innerHTML = String(icon.options.html);
  return element;
}

describe('busIcon', () => {
  it('[passenger_map_view.AC-07] points the arrow to bearing_deg', () => {
    const icon = html(
      busIcon({ bearing: 245, scheduled: false, label: 'Estimada', color: '#e50000' }),
    );

    const arrow = icon.querySelector<SVGElement>('[data-bus-arrow]');
    expect(arrow?.getAttribute('style')).toContain('rotate(245deg)');
  });

  it('[passenger_map_view.AC-07] has no arrow without a bearing', () => {
    const icon = html(
      busIcon({ bearing: null, scheduled: false, label: 'Estimada', color: '#e50000' }),
    );

    expect(icon.querySelector('[data-bus-arrow]')).toBeNull();
    expect(icon.querySelector('[data-bus-disc]')).not.toBeNull();
  });

  it('[passenger_map_view.AC-05] carries the visible label, escaped, and hides the drawing from screen readers', () => {
    const icon = html(
      busIcon({ bearing: 0, scheduled: false, label: 'Según <b>horario</b>', color: '#e50000' }),
    );

    expect(icon.querySelector('[data-bus-label]')?.textContent).toBe('Según <b>horario</b>');
    expect(icon.querySelector('b')).toBeNull();
    for (const svg of icon.querySelectorAll('svg'))
      expect(svg).toHaveAttribute('aria-hidden', 'true');
  });

  it('[passenger_map_view.AC-07] marks a scheduled position with a dashed border', () => {
    const scheduled = html(
      busIcon({ bearing: 0, scheduled: true, label: 'Según horario', color: '#e50000' }),
    );
    const estimated = html(
      busIcon({ bearing: 0, scheduled: false, label: 'Estimada', color: '#e50000' }),
    );

    expect(scheduled.querySelector('.bus-marker--scheduled')).not.toBeNull();
    expect(estimated.querySelector('.bus-marker--scheduled')).toBeNull();
  });

  it('[passenger_map_view.AC-07] fills the disc with the line colour', () => {
    const icon = html(
      busIcon({ bearing: 0, scheduled: false, label: 'Estimada', color: '#e50000' }),
    );

    expect(icon.querySelector('[data-bus-disc]')?.getAttribute('style')).toContain('#e50000');
  });
});
