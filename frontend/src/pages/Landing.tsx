import { useRef } from "react";
import { Navigate } from "react-router-dom";
import { useAuth as useOidcAuth } from "react-oidc-context";

// Layered card shadow and tonal vignette aren't expressible with the project's
// Tailwind config, so they're applied inline. Everything else uses utilities.
const CARD_SHADOW =
  "0 1px 1px rgba(24,24,27,0.03), 0 2px 6px rgba(24,24,27,0.04), 0 24px 48px -24px rgba(24,24,27,0.18)";

const VIGNETTE =
  "radial-gradient(120% 90% at 50% 38%, #ffffff 0%, rgba(255,255,255,0) 46%), " +
  "radial-gradient(140% 120% at 50% 120%, rgba(59,130,246,0.05) 0%, rgba(59,130,246,0) 55%)";

export default function Landing() {
  const oidc = useOidcAuth();
  const triggered = useRef(false);

  if (oidc.isAuthenticated) return <Navigate to="/cases" replace />;

  function handleSignIn() {
    if (triggered.current) return;
    triggered.current = true;
    oidc.signinRedirect().catch((err) => {
      triggered.current = false;
      console.error("signinRedirect failed", err);
    });
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-gray-50 grid place-items-center">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0"
        style={{ background: VIGNETTE }}
      />

      <div
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2"
        style={{ width: 660, height: 660 }}
      >
        <svg viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg" className="block h-full w-full">
          <g stroke="#cbced5" strokeWidth="0.5" opacity="0.6">
            <line x1="16" y1="10.5" x2="16" y2="5.5" />
            <line x1="20.8" y1="13" x2="25.84" y2="9.61" />
            <line x1="21" y1="19" x2="25.88" y2="20.88" />
            <line x1="16" y1="21.5" x2="15" y2="26.5" />
            <line x1="11.2" y1="19" x2="6.16" y2="22.39" />
            <line x1="11" y1="13" x2="6.08" y2="9.89" />
          </g>
          <g fill="#d3d6dc" opacity="0.4">
            <circle cx="16" cy="16" r="5.5" />
            <circle cx="16" cy="3" r="2.5" />
            <circle cx="27.5" cy="8.5" r="2" />
            <circle cx="28" cy="23" r="3" />
            <circle cx="15" cy="29" r="2.5" />
            <circle cx="4.5" cy="23.5" r="2" />
            <circle cx="4" cy="8.5" r="2.5" />
          </g>
        </svg>
      </div>

      <main className="relative z-10 flex w-full max-w-[392px] flex-col items-center p-6">
        <div
          className="w-full rounded-[18px] border border-[#e9e9ec] bg-white text-center"
          style={{ padding: "40px 38px 34px", boxShadow: CARD_SHADOW }}
        >
          <div className="mx-auto mb-[22px] block h-[46px] w-[46px]">
            <svg
              viewBox="0 0 32 32"
              xmlns="http://www.w3.org/2000/svg"
              className="block h-full w-full"
            >
              <circle cx="16" cy="16" r="5.5" fill="#3b82f6" />
              <line
                x1="16"
                y1="10.5"
                x2="16"
                y2="4"
                stroke="#3b82f6"
                strokeWidth="1"
                opacity="0.4"
              />
              <line
                x1="20.8"
                y1="13"
                x2="26"
                y2="9.5"
                stroke="#3b82f6"
                strokeWidth="1"
                opacity="0.3"
              />
              <line
                x1="21"
                y1="19"
                x2="27"
                y2="22"
                stroke="#ef4444"
                strokeWidth="1"
                opacity="0.35"
              />
              <line
                x1="16"
                y1="21.5"
                x2="15"
                y2="28"
                stroke="#f59e0b"
                strokeWidth="1"
                opacity="0.35"
              />
              <line
                x1="11.2"
                y1="19"
                x2="6"
                y2="22.5"
                stroke="#f59e0b"
                strokeWidth="1"
                opacity="0.3"
              />
              <line
                x1="11"
                y1="13"
                x2="5.5"
                y2="9.5"
                stroke="#a855f7"
                strokeWidth="1"
                opacity="0.35"
              />
              <circle cx="16" cy="3" r="2.5" fill="#3b82f6" />
              <circle cx="27.5" cy="8.5" r="2" fill="#3b82f6" opacity="0.7" />
              <circle cx="28" cy="23" r="3" fill="#ef4444" />
              <circle cx="15" cy="29" r="2.5" fill="#f59e0b" />
              <circle cx="4.5" cy="23.5" r="2" fill="#f59e0b" opacity="0.7" />
              <circle cx="4" cy="8.5" r="2.5" fill="#a855f7" />
            </svg>
          </div>

          <h1
            className="font-sans font-semibold leading-none text-gray-900"
            style={{ fontSize: 26, letterSpacing: "-0.02em" }}
          >
            meta<span className="text-[#3b82f6]">-vis</span>
          </h1>

          <p
            className="mx-auto mt-3 text-gray-500"
            style={{ maxWidth: "25ch", fontSize: 14, lineHeight: 1.5, textWrap: "pretty" }}
          >
            Metagenomic pathogen detection and case review.
          </p>

          <div className="my-7 h-px w-full bg-[#f1f1f3]" style={{ margin: "28px 0 24px" }} />

          <button
            type="button"
            onClick={handleSignIn}
            disabled={oidc.isLoading}
            className="group inline-flex h-[46px] w-full items-center justify-center gap-[9px] rounded-[11px] border border-gray-900 bg-gray-900 px-[18px] font-sans font-medium text-white transition-colors hover:bg-gray-700 active:translate-y-px focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#3b82f6] disabled:opacity-60"
            style={{
              fontSize: 14.5,
              letterSpacing: "-0.005em",
              boxShadow: "0 1px 2px rgba(24,24,27,0.16)",
            }}
          >
            <svg
              viewBox="0 0 16 16"
              fill="none"
              aria-hidden="true"
              className="h-[15px] w-[15px] opacity-85"
            >
              <rect
                x="3"
                y="7"
                width="10"
                height="6.5"
                rx="1.6"
                stroke="currentColor"
                strokeWidth="1.3"
              />
              <path d="M5.2 7V5.2a2.8 2.8 0 0 1 5.6 0V7" stroke="currentColor" strokeWidth="1.3" />
            </svg>
            Sign in with Keycloak
            <svg
              viewBox="0 0 16 16"
              fill="none"
              aria-hidden="true"
              className="h-[15px] w-[15px] opacity-60 transition-transform group-hover:translate-x-[2px]"
            >
              <path
                d="M3 8h9M8.5 4.5 12 8l-3.5 3.5"
                stroke="currentColor"
                strokeWidth="1.4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>

          {oidc.error ? (
            <p className="mt-[18px] font-mono text-[11px] text-red-500">
              Sign-in failed: {oidc.error.message}
            </p>
          ) : (
            <p className="mt-[18px] inline-flex items-center gap-[7px] font-mono text-[11px] text-gray-400">
              <span
                className="inline-block h-[5px] w-[5px] rounded-full bg-[#22c55e]"
                style={{ boxShadow: "0 0 0 3px rgba(34,197,94,0.14)" }}
              />
              Authorized access · single sign-on via Keycloak
            </p>
          )}
        </div>

        <div
          className="mt-[26px] text-center font-mono text-[11px] text-[#c7c7cc]"
          style={{ letterSpacing: "0.04em" }}
        >
          meta-vis
          <span className="mx-2 text-[#dcdce0]">·</span>
          clinical metagenomics platform
        </div>
      </main>
    </div>
  );
}
