import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '../theme';
import MagicBento, { type BentoCardProps } from './MagicBento';

export default function Home() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { theme } = useTheme();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const cards: BentoCardProps[] = [
    {
      color: theme.colors.background.secondary,
      title: 'Campaigns',
      description: 'Organize your D&D campaigns, manage characters and sessions together',
      label: 'Worlds',
      onClick: () => navigate('/campaigns')
    },
    {
      color: theme.colors.background.tertiary,
      title: 'Characters',
      description: 'Manage your D&D characters, track their stats, and organize your party',
      label: 'Heroes',
      onClick: () => navigate('/characters')
    },
    {
      color: theme.colors.background.secondary,
      title: 'Sessions',
      description: 'Create and manage your D&D game sessions, track combat events in real-time',
      label: 'Adventures',
      onClick: () => navigate('/sessions')
    },
    {
      color: theme.colors.background.quaternary,
      title: 'Ioun',
      description: 'Have the knowning mistress guide your journey',
      label: 'Voice AI',
      onClick: () => navigate('/ioun-silence')
    }
  ];

  return (
    <div 
      className="min-h-screen"
      style={{ backgroundColor: theme.colors.background.primary }}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 
              className="text-4xl font-bold mb-2"
              style={{ color: theme.colors.foreground.primary }}
            >
              PickAxe
            </h1>
            <p style={{ color: theme.colors.foreground.muted }}>
              Welcome, {user?.email}!
            </p>
          </div>
          <button
            onClick={handleLogout}
            style={{
              padding: `${theme.spacing.sm} ${theme.spacing.md}`,
              backgroundColor: theme.colors.foreground.primary,
              color: theme.colors.background.primary,
              borderRadius: theme.borderRadius.md,
              fontWeight: theme.typography.fontWeight.medium,
              transition: `all ${theme.transitions.normal} ease`,
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = theme.colors.foreground.tertiary;
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = theme.colors.foreground.primary;
            }}
          >
            Logout
          </button>
        </div>
        
        <div className="flex justify-center">
          <MagicBento
            cards={cards}
            enableStars={true}
            enableSpotlight={true}
            enableBorderGlow={true}
            glowColor={theme.colors.accent.glow}
            clickEffect={true}
            enableMagnetism={true}
          />
        </div>
      </div>
    </div>
  );
}

