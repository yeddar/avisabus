import { useCallback, useEffect, useState } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { Navigate, useNavigate } from 'react-router-dom';

import { Button } from '../../shared/ui/Button';
import { StatusNotice } from '../../shared/ui/StatusNotice';
import { usePageTitle } from '../../shared/ui/usePageTitle';
import { DemandView } from './DemandView';
import { ServicePicker } from './ServicePicker';
import {
  clearDriverToken,
  DriverAuthError,
  driverApi,
  getDriverToken,
  subscribeDriverAuthLost,
} from './session';
import type { DriverService, DriverView } from './types';
import { useDriverShift } from './useDriverShift';

const OK = 200;

type Phase =
  | { kind: 'loading' }
  | { kind: 'failed' }
  | { kind: 'picker'; initialChoice?: { line: string; directionId: number } }
  | { kind: 'demand'; service: DriverService; initialView: DriverView | null };

/**
 * /driver/shift: the picker without a departure, the demand view with one (driver_ui.AC-02, AC-03).
 * The position, the wake lock and /ws/driver live here, not in the view, so they last as long as
 * the shift, also while choosing a departure (AC-04, AC-08, AC-09 v1.1).
 */
export function ShiftPage() {
  const { t } = useTranslation();
  usePageTitle(t('driver.shift.title'));
  const navigate = useNavigate();
  const [phase, setPhase] = useState<Phase>({ kind: 'loading' });
  const [attempt, setAttempt] = useState(0);
  const hasToken = getDriverToken() !== null;

  const toLogin = useCallback(() => {
    void navigate('/driver', { replace: true });
  }, [navigate]);

  useEffect(() => subscribeDriverAuthLost(toLogin), [toLogin]);

  const shiftOpen = hasToken && (phase.kind === 'picker' || phase.kind === 'demand');
  const shift = useDriverShift(shiftOpen, (reason) => {
    clearDriverToken();
    void navigate('/driver', { replace: true, state: { closedReason: reason } });
  });

  useEffect(() => {
    if (!hasToken) return;
    let active = true;
    driverApi<DriverView>('GET', '/driver/sessions/current/view')
      .then((result) => {
        if (!active) return;
        if (result.status !== OK || result.data === null) {
          setPhase({ kind: 'failed' });
        } else if (result.data.service === null) {
          setPhase({ kind: 'picker' });
        } else {
          setPhase({ kind: 'demand', service: result.data.service, initialView: result.data });
        }
      })
      .catch((failure: unknown) => {
        if (active && !(failure instanceof DriverAuthError)) setPhase({ kind: 'failed' });
      });
    return () => {
      active = false;
    };
  }, [hasToken, attempt]);

  if (!hasToken) return <Navigate to="/driver" replace />;

  switch (phase.kind) {
    case 'loading':
      return null;
    case 'failed':
      return (
        <StatusNotice
          action={
            <Button
              onClick={() => {
                setPhase({ kind: 'loading' });
                setAttempt((value) => value + 1);
              }}
            >
              {t('stop.error.retry')}
            </Button>
          }
        >
          <Trans i18nKey="stop.error.body" components={{ strong: <strong /> }} />
        </StatusNotice>
      );
    case 'picker':
      return (
        <ServicePicker
          initialChoice={phase.initialChoice}
          onSelected={(service) => setPhase({ kind: 'demand', service, initialView: null })}
          onExit={toLogin}
        />
      );
    case 'demand':
      return (
        <DemandView
          key={`${phase.service.trip_id}-${phase.service.service_date}`}
          service={phase.service}
          initialView={phase.initialView}
          shift={shift}
          onNextDeparture={() =>
            setPhase({
              kind: 'picker',
              initialChoice: {
                line: phase.service.line,
                directionId: phase.service.direction_id,
              },
            })
          }
          onSessionEnd={(reason) => {
            void navigate('/driver', { replace: true, state: { closedReason: reason } });
          }}
        />
      );
  }
}
