import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ThemeProvider } from './theme/ThemeContext';
import Login from './components/auth/Login';
import Register from './components/auth/Register';
import Home from './components/Home';
import ProtectedRoute from './components/ProtectedRoute';
import CampaignList from './components/campaigns/CampaignList';
import CampaignView from './components/campaigns/CampaignView';
import { CampaignEditRedirect, CampaignNewRedirect } from './components/campaigns/CampaignRouteRedirects';
import CharacterList from './components/characters/CharacterList';
import { CharacterEditRedirect, CharacterNewRedirect } from './components/characters/CharacterRouteRedirects';
import SessionList from './components/sessions/SessionList';
import SessionView from './components/sessions/SessionView';
import VoiceAssistant from './components/VoiceAssistant';
import VoiceAssistantV2 from './components/VoiceAssistantV2';
import SectionShell from './components/layout/SectionShell';
import { SessionNewRedirect } from './components/sessions/SessionRouteRedirects';

const App = () => {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Home />
              </ProtectedRoute>
            }
          />
          <Route
            path="/campaigns"
            element={
              <ProtectedRoute>
                <SectionShell title="Campaigns">
                  <CampaignList />
                </SectionShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/campaigns/new"
            element={
              <ProtectedRoute>
                <CampaignNewRedirect />
              </ProtectedRoute>
            }
          />
          <Route
            path="/campaigns/:id"
            element={
              <ProtectedRoute>
                <SectionShell title="Campaign">
                  <CampaignView />
                </SectionShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/campaigns/:id/edit"
            element={
              <ProtectedRoute>
                <CampaignEditRedirect />
              </ProtectedRoute>
            }
          />
          <Route
            path="/characters"
            element={
              <ProtectedRoute>
                <SectionShell title="Characters">
                  <CharacterList />
                </SectionShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/characters/new"
            element={
              <ProtectedRoute>
                <CharacterNewRedirect />
              </ProtectedRoute>
            }
          />
          <Route
            path="/characters/:id/edit"
            element={
              <ProtectedRoute>
                <CharacterEditRedirect />
              </ProtectedRoute>
            }
          />
          <Route
            path="/sessions"
            element={
              <ProtectedRoute>
                <SectionShell title="Sessions">
                  <SessionList />
                </SectionShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/sessions/new"
            element={
              <ProtectedRoute>
                <SessionNewRedirect />
              </ProtectedRoute>
            }
          />
          <Route
            path="/sessions/:id"
            element={
              <ProtectedRoute>
                <SectionShell title="Session">
                  <SessionView />
                </SectionShell>
              </ProtectedRoute>
            }
          />
          
            
          
          <Route
            path="/voice-assistant"
            element={
              <ProtectedRoute>
                <SectionShell title="Voice Assistant" subtitle="AI-powered D&D assistant">
                  <VoiceAssistant />
                </SectionShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/ioun"
            element={
              <ProtectedRoute>
                <SectionShell title="Ioun Voice Assistant" subtitle="AI-powered D&D assistant">
                  <VoiceAssistantV2 />
                </SectionShell>
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
};

export default App;