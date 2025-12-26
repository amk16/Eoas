export type StepperStep = {
  id: string;
  title: string;
  description?: string;
};

export default function Stepper({
  steps,
  activeIndex,
}: {
  steps: StepperStep[];
  activeIndex: number;
}) {
  return (
    <div className="flex items-center gap-3 flex-wrap">
      {steps.map((s, idx) => {
        const isActive = idx === activeIndex;
        const isDone = idx < activeIndex;
        return (
          <div key={s.id} className="flex items-center gap-3">
            <div
              className={[
                'h-8 w-8 rounded-full border flex items-center justify-center text-sm font-semibold',
                isActive ? 'bg-white text-black border-white' : '',
                isDone ? 'bg-white/10 text-white border-white/15' : '',
                !isActive && !isDone ? 'bg-transparent text-white/60 border-white/10' : '',
              ].join(' ')}
              aria-current={isActive ? 'step' : undefined}
            >
              {isDone ? (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path
                    d="M20 6 9 17l-5-5"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              ) : (
                idx + 1
              )}
            </div>
            <div className="min-w-0">
              <div className={isActive ? 'text-sm font-semibold text-white' : 'text-sm font-medium text-white/80'}>
                {s.title}
              </div>
              {s.description && (
                <div className={isActive ? 'text-xs text-neutral-300' : 'text-xs text-neutral-500'}>
                  {s.description}
                </div>
              )}
            </div>
            {idx !== steps.length - 1 && <div className="h-px w-6 bg-white/10" aria-hidden="true" />}
          </div>
        );
      })}
    </div>
  );
}


