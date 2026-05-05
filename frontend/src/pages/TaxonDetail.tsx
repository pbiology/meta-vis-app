import { useNavigate, useParams } from "react-router-dom";
import { useRequiredParam } from "../utils/routeParams";
import TaxonDetailContent from "../components/TaxonDetailContent";

export default function TaxonDetail() {
  const taxonId = useRequiredParam("taxonId");
  const { sampleId } = useParams<{ sampleId?: string }>();
  const navigate = useNavigate();

  return <TaxonDetailContent taxonId={taxonId} sampleId={sampleId} onBack={() => navigate(-1)} />;
}
