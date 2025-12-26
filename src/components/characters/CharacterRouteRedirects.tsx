import { Navigate, useParams } from 'react-router-dom';

export function CharacterNewRedirect() {
  return <Navigate to="/characters?drawer=new" replace />;
}

export function CharacterEditRedirect() {
  const { id } = useParams<{ id: string }>();
  const safeId = id ? encodeURIComponent(id) : '';
  return <Navigate to={`/characters?drawer=edit&id=${safeId}`} replace />;
}


