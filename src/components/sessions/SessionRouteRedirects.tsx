import { Navigate } from 'react-router-dom';

export function SessionNewRedirect() {
  return <Navigate to="/sessions?drawer=new" replace />;
}


