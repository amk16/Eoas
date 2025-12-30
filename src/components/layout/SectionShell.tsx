import { useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useTheme } from '../../theme';

type NavItem = {
  to: string;
  label: string;
  description?: string;
};

export default function SectionShell({
  title,
  subtitle,
  primaryAction,
  children,
}: {
  title?: string;
  subtitle?: string;
  primaryAction?: ReactNode;
  children: ReactNode;
}) {
  const { theme } = useTheme();
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const navItems: NavItem[] = useMemo(
    () => [
      { to: '/campaigns', label: 'Campaigns', description: 'Worlds' },
      { to: '/characters', label: 'Characters', description: 'Heroes' },
      { to: '/sessions', label: 'Sessions', description: 'Adventures' },
      { to: '/ioun-silence', label: 'Ioun', description: 'Fast Detection' },
    ],
    []
  );

  const activeRoot = useMemo(() => {
    const path = location.pathname;
    const match = navItems
      .map((i) => i.to)
      .sort((a, b) => b.length - a.length)
      .find((prefix) => path === prefix || path.startsWith(prefix + '/'));
    return match || '';
  }, [location.pathname, navItems]);

  const shellBg = theme.colors.background.primary;
  const panelBg = theme.colors.background.secondary;
  const border = theme.colors.border.muted;

  const Sidebar = ({ onNavigate }: { onNavigate?: () => void }) => (
    <div
      className="h-full flex flex-col"
      style={{
        backgroundColor: panelBg,
        borderColor: border,
      }}
    >
      <div className="px-4 py-4 border-b" style={{ borderColor: border }}>
        <button
          type="button"
          onClick={() => {
            navigate('/');
            onNavigate?.();
          }}
          className="w-full text-left"
        >
          <div className="text-sm tracking-wide" style={{ color: theme.colors.foreground.muted }}>
            D&D Damage Tracker
          </div>
          <div className="text-base font-semibold" style={{ color: theme.colors.foreground.primary }}>
            Dashboard
          </div>
        </button>
      </div>

      <nav className="px-2 py-3 flex-1">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={() => onNavigate?.()}
            className={({ isActive }) =>
              [
                'block rounded-xl px-3 py-3 transition-colors',
                isActive ? 'bg-white/10' : 'hover:bg-white/5',
              ].join(' ')
            }
            style={{
              border: '1px solid transparent',
            }}
          >
            <div className="flex items-baseline justify-between gap-3">
              <div className="text-sm font-medium" style={{ color: theme.colors.foreground.primary }}>
                {item.label}
              </div>
              {item.description && (
                <div className="text-xs" style={{ color: theme.colors.foreground.muted }}>
                  {item.description}
                </div>
              )}
            </div>
          </NavLink>
        ))}
      </nav>

      <div className="px-3 py-3 border-t" style={{ borderColor: border }}>
        <button
          type="button"
          onClick={() => {
            navigate('/');
            onNavigate?.();
          }}
          className="w-full rounded-xl px-3 py-2 text-sm hover:bg-white/5 transition-colors text-left"
          style={{ color: theme.colors.foreground.muted }}
        >
          Back to Home
        </button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen" style={{ backgroundColor: shellBg }}>
      {/* Mobile sidebar overlay */}
      {mobileNavOpen && (
        <div className="fixed inset-0 z-[1030] md:hidden">
          <button
            type="button"
            aria-label="Close navigation"
            className="absolute inset-0 bg-black/60"
            onClick={() => setMobileNavOpen(false)}
          />
          <div className="absolute left-0 top-0 h-full w-[84vw] max-w-xs border-r" style={{ borderColor: border }}>
            <Sidebar onNavigate={() => setMobileNavOpen(false)} />
          </div>
        </div>
      )}

      <div className="flex">
        {/* Desktop sidebar */}
        <aside className="hidden md:block w-72 border-r min-h-screen sticky top-0" style={{ borderColor: border }}>
          <Sidebar />
        </aside>

        {/* Main */}
        <div className="flex-1 min-w-0">
          {/* Topbar */}
          <header className="sticky top-0 z-[1020] border-b backdrop-blur" style={{ borderColor: border }}>
            <div
              className="px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between gap-4"
              style={{ backgroundColor: `${panelBg}CC` }}
            >
              <div className="flex items-center gap-3 min-w-0">
                <button
                  type="button"
                  className="md:hidden rounded-lg px-2 py-2 hover:bg-white/5 transition-colors"
                  aria-label="Open navigation"
                  onClick={() => setMobileNavOpen(true)}
                  style={{ color: theme.colors.foreground.primary }}
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                    <path
                      d="M4 6h16M4 12h16M4 18h16"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                    />
                  </svg>
                </button>

                <div className="min-w-0">
                  <div className="text-xs uppercase tracking-wider" style={{ color: theme.colors.foreground.muted }}>
                    {activeRoot ? navItems.find((n) => n.to === activeRoot)?.label : 'Section'}
                  </div>
                  {title && (
                    <div className="text-lg sm:text-xl font-semibold truncate" style={{ color: theme.colors.foreground.primary }}>
                      {title}
                    </div>
                  )}
                  {subtitle && (
                    <div className="text-sm truncate" style={{ color: theme.colors.foreground.muted }}>
                      {subtitle}
                    </div>
                  )}
                </div>
              </div>

              <div className="shrink-0">{primaryAction}</div>
            </div>
          </header>

          <main className="px-4 sm:px-6 lg:px-8 py-8">
            <div className="max-w-7xl mx-auto">{children}</div>
          </main>
        </div>
      </div>
    </div>
  );
}


