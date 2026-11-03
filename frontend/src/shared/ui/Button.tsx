import type { ButtonHTMLAttributes, ReactNode } from 'react';

import { ButtonIcon } from './ButtonIcon';
import { buttonClassName, type ButtonVariant } from './buttonStyles';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  /** Decorative icon (aria-hidden); the text is always visible. */
  icon?: ReactNode;
}

export function Button({
  variant = 'secondary',
  icon,
  className,
  type = 'button',
  children,
  ...props
}: ButtonProps) {
  return (
    <button type={type} className={buttonClassName(variant, className)} {...props}>
      {icon !== undefined && <ButtonIcon>{icon}</ButtonIcon>}
      {children}
    </button>
  );
}
