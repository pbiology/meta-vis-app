import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth as useOidcAuth } from "react-oidc-context";

// Landing page for the OIDC redirect_uri. react-oidc-context's AuthProvider
// performs the code/state exchange automatically; this component just waits
// for the result and then hands control back to the SPA.
export default function AuthCallback() {
  const oidc = useOidcAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (oidc.isAuthenticated) {
      navigate("/", { replace: true });
    }
  }, [oidc.isAuthenticated, navigate]);

  return (
    <div className="flex h-screen items-center justify-center text-sm text-gray-400">
      {oidc.error ? `Sign-in failed: ${oidc.error.message}` : "Completing sign-in…"}
    </div>
  );
}
