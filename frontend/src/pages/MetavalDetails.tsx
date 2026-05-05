import { useNavigate } from "react-router-dom";
import { useRequiredParam } from "../utils/routeParams";
import MetavalDetailsContent from "../components/MetavalDetailsContent";

export default function MetavalDetails() {
  const sampleId = useRequiredParam("sampleId");
  const metavalId = useRequiredParam("metavalId");
  const navigate = useNavigate();

  return (
    <MetavalDetailsContent sampleId={sampleId} metavalId={metavalId} onBack={() => navigate(-1)} />
  );
}
