import { useEffect, useMemo } from 'react';
import type { ReactNode } from 'react';

export default function Drawer({
  open,
  title,
  description,
  onClose,
  children,
  footer,
}: {
  open: boolean;
  title?: string;
  description?: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const labelId = useMemo(() => `drawer-title-${Math.random().toString(16).slice(2)}`, []);
  const descId = useMemo(() => `drawer-desc-${Math.random().toString(16).slice(2)}`, []);

  useEffect(() => {
    if (!open) return;

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKeyDown);

    // Prevent background scroll while open
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = prevOverflow;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[1040]">
      <button
        type="button"
        aria-label="Close"
        className="absolute inset-0 bg-black/60"
        onClick={onClose}
      />

      <aside
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? labelId : undefined}
        aria-describedby={description ? descId : undefined}
        className="absolute right-0 top-0 h-full w-full sm:w-[560px] border-l border-neutral-800 bg-black"
      >
        <div className="h-full flex flex-col">
          <div className="px-5 py-4 border-b border-neutral-800 bg-neutral-950">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                {title && (
                  <div id={labelId} className="text-lg font-semibold text-white truncate">
                    {title}
                  </div>
                )}
                {description && (
                  <div id={descId} className="text-sm text-neutral-400 mt-1">
                    {description}
                  </div>
                )}
              </div>

              <button
                type="button"
                onClick={onClose}
                className="shrink-0 rounded-xl px-3 py-2 bg-white/5 text-white border border-white/10 hover:bg-white/10 transition-colors text-sm font-medium"
              >
                Close
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto px-5 py-5">{children}</div>

          {footer && (
            <div className="border-t border-neutral-800 bg-neutral-950 px-5 py-4">
              {footer}
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}


