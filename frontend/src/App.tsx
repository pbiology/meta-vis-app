import { ReactNode } from "react";
import { Routes, Route, Navigate, useParams } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import Login from "./pages/Login";
import SampleList from "./pages/SampleList";
import SampleDetail from "./pages/SampleDetail";
import CaseList from "./pages/CaseList";
import CaseView from "./pages/CaseView";
import Admin from "./pages/Admin";
import MetavalDetails from "./pages/MetavalDetails";
import Alerts from "./pages/Alerts";
import IgnoreList from "./pages/IgnoreList";
import KnownPathogens from "./pages/KnownPathogens";
import Layout from "./components/Layout";
import { ReportBuilderProvider } from "./context/ReportBuilderContext";
import TaxonDetail from "./pages/TaxonDetail";
import NtcTrends from "./pages/NtcTrends";
import NtcListsPage from "./pages/NtcListsPage";
import UserPreferences from "./pages/UserPreferences";
import AuthCallback from "./pages/AuthCallback";
import ErrorBoundary from "./components/ErrorBoundary";

function ProtectedRoute({ children }: Readonly<{ children: ReactNode }>) {
  const { user, authLoading } = useAuth();
  if (authLoading)
    return (
      <div className="flex h-screen items-center justify-center text-sm text-gray-400">
        Loading…
      </div>
    );
  return user ? <>{children}</> : <Navigate to="/login" replace />;
}

// Preserves bookmarks and external links to the legacy /cases/:caseId route by
// redirecting to the new sidebar-less /case/:caseId page.
function LegacyCaseRedirect() {
  const { caseId } = useParams();
  return <Navigate to={`/case/${caseId}`} replace />;
}

export default function App() {
  return (
    <ErrorBoundary label="application">
      <ReportBuilderProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/auth/callback" element={<AuthCallback />} />

          {/* Case-centric view — protected, but rendered OUTSIDE the app Layout
              so reviewers focus on the case (no app sidebar, only case nav). */}
          <Route
            path="/case/:caseId"
            element={
              <ProtectedRoute>
                <CaseView />
              </ProtectedRoute>
            }
          />

          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Navigate to="/cases" replace />} />
            <Route path="cases" element={<CaseList />} />
            <Route path="cases/:caseId" element={<LegacyCaseRedirect />} />
            <Route path="samples" element={<SampleList />} />
            <Route path="samples/:sampleId" element={<SampleDetail />} />
            <Route path="admin" element={<Admin />} />
            <Route path="samples/:sampleId/metaval/:metavalId" element={<MetavalDetails />} />
            <Route path="alerts" element={<Alerts />} />
            <Route path="alerts/ignorelist" element={<IgnoreList />} />
            <Route path="pathogens" element={<KnownPathogens />} />
            <Route path="taxa/:taxonId" element={<TaxonDetail />} />
            <Route path="samples/:sampleId/taxa/:taxonId" element={<TaxonDetail />} />
            <Route path="ntc" element={<NtcTrends />} />
            <Route path="ntc/lists" element={<NtcListsPage />} />
            <Route path="preferences" element={<UserPreferences />} />
          </Route>
        </Routes>
      </ReportBuilderProvider>
    </ErrorBoundary>
  );
}
