# Theme System

A global theme system for consistent styling across the application.

## Usage

### Using Theme in React Components

```tsx
import { useTheme } from '../theme';

function MyComponent() {
  const { theme } = useTheme();
  
  return (
    <div style={{ 
      backgroundColor: theme.colors.background.primary,
      color: theme.colors.foreground.primary,
      padding: theme.spacing.lg,
      borderRadius: theme.borderRadius.md
    }}>
      Hello World
    </div>
  );
}
```

### Using CSS Variables

CSS variables are automatically available in all components:

```css
.my-component {
  background-color: var(--color-bg-primary);
  color: var(--color-fg-primary);
  padding: var(--spacing-lg);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
}
```

### Using with Tailwind CSS

You can extend Tailwind config to use theme values, or use inline styles with the theme object.

### Theme Structure

- **Colors**: Background, foreground, border, accent, and semantic colors
- **Typography**: Font families, sizes, weights, and line heights
- **Spacing**: Consistent spacing scale
- **Border Radius**: Standard border radius values
- **Shadows**: Box shadows including glow effects
- **Transitions**: Standard transition durations
- **Z-Index**: Layering system

### Example: Styled Component

```tsx
import { useTheme } from '../theme';

function Card({ children }) {
  const { theme } = useTheme();
  
  return (
    <div
      style={{
        backgroundColor: theme.colors.background.secondary,
        border: `1px solid ${theme.colors.border.primary}`,
        borderRadius: theme.borderRadius.xl,
        padding: theme.spacing.lg,
        boxShadow: theme.shadows.md,
        transition: `all ${theme.transitions.normal} ease`,
      }}
    >
      {children}
    </div>
  );
}
```




