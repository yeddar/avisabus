import type { ButtonHTMLAttributes, ReactNode, Ref } from 'react';

import { ButtonIcon } from './ButtonIcon';
import { buttonClassName, type ButtonVariant } from './buttonStyles';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  /** Decorative icon (aria-hidden); the text is always visible. */
  icon?: ReactNode;
  ref?: Ref<HTMLButtonElement>;
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
