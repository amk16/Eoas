import { Navigate, useParams } from 'react-router-dom';

export function CampaignNewRedirect() {
  return <Navigate to="/campaigns?drawer=new" replace />;
}

export function CampaignEditRedirect() {
  const { id } = useParams<{ id: string }>();
  const safeId = id ? encodeURIComponent(id) : '';
  return <Navigate to={`/campaigns?drawer=edit&id=${safeId}`} replace />;
}


