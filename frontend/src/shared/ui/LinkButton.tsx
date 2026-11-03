import type { ReactNode } from 'react';
import { Link, type LinkProps } from 'react-router-dom';

import { ButtonIcon } from './ButtonIcon';
import { buttonClassName, type ButtonVariant } from './buttonStyles';

export interface LinkButtonProps extends LinkProps {
  variant?: ButtonVariant;
  /** Decorative icon (aria-hidden); the text is always visible. */
  icon?: ReactNode;
}

/** In-app navigation styled as a button (docs/design.md §5.5). */
export function LinkButton({
  variant = 'secondary',
  icon,
  className,
  children,
  ...props
}: LinkButtonProps) {
  return (
    <Link
      className={buttonClassName(variant, typeof className === 'string' ? className : undefined)}
      {...props}
    >
      {icon !== undefined && <ButtonIcon>{icon}</ButtonIcon>}
      {children}
    </Link>
  );
}
