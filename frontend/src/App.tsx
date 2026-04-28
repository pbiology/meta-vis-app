import { ReactNode } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import Login from "./pages/Login";
import SampleList from "./pages/SampleList";
import SampleDetail from "./pages/SampleDetail";
import CaseList from "./pages/CaseList";
import CaseDetail from "./pages/CaseDetail";
import Admin from "./pages/Admin";
import MetavalDetails from "./pages/MetavalDetails";
import Alerts from "./pages/Alerts";
import IgnoreList from "./pages/IgnoreList";
import KnownPathogens from "./pages/KnownPathogens";
import Layout from "./components/Layout";
import TaxonDetail from "./pages/TaxonDetail";
import NtcTrends from "./pages/NtcTrends";
import NtcListsPage from "./pages/NtcListsPage";
import UserPreferences from "./pages/UserPreferences";
import ErrorBoundary from "./components/ErrorBoundary";

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  return user ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <ErrorBoundary label="application">
    <Routes>
      <Route path="/login" element={<Login />} />
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
        <Route path="cases/:caseId" element={<CaseDetail />} />
        <Route path="samples" element={<SampleList />} />
        <Route path="samples/:sampleId" element={<SampleDetail />} />
        <Route path="admin" element={<Admin />} />
        <Route path="samples/:sampleId/metaval/:metavalId" element={<MetavalDetails />} />
        <Route path="alerts" element={<Alerts />} />
        <Route path="alerts/ignorelist" element={<IgnoreList />} />
        <Route path="pathogens" element={<KnownPathogens />} />
        <Route path="taxa/:taxonId" element={<TaxonDetail />} />
        <Route path="ntc" element={<NtcTrends />} />
        <Route path="ntc/lists" element={<NtcListsPage />} />
        <Route path="preferences" element={<UserPreferences />} />
      </Route>
    </Routes>
    </ErrorBoundary>
  );
}
