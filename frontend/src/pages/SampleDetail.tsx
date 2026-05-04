import { useNavigate } from "react-router-dom";
import { useRequiredParam } from "../utils/routeParams";
import SampleDetailContent from "../components/SampleDetailContent";

export default function SampleDetail() {
  const sampleId = useRequiredParam("sampleId");
  const navigate = useNavigate();
  return <SampleDetailContent sampleId={sampleId} onBack={() => navigate(-1)} />;
}
