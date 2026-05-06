import { useNavigate } from "react-router-dom";
import { useRequiredParam } from "../utils/routeParams";
import MetavalDetailsContent from "../components/MetavalDetailsContent";

export default function MetavalDetails() {
  const metavalId = useRequiredParam("metavalId");
  const navigate = useNavigate();

  return <MetavalDetailsContent metavalId={metavalId} onBack={() => navigate(-1)} />;
}
