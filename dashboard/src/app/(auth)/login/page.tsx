"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle, Loader2, Lock, Mail, Phone } from "lucide-react";
import { LoginIllustration } from "@/components/Auth/login-illustration";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    const success = await login(email, password);
    if (success) {
      router.push("/overview");
    } else {
      setError("Invalid email or password");
    }
    setLoading(false);
  };

  return (
    <div className="grid min-h-screen grid-cols-1 bg-white dark:bg-gray-dark xl:grid-cols-2">
      {/* Left: form */}
      <div className="flex flex-col px-6 py-10 sm:px-12 lg:px-20 xl:px-24">
        <div className="mb-12 flex items-center gap-2.5">
          <div className="flex size-10 items-center justify-center rounded-xl bg-primary">
            <Phone className="size-5 text-white" />
          </div>
          <div className="leading-tight">
            <span className="block text-lg font-bold text-dark dark:text-white">
              AI Telephone Receptionist
            </span>
            <span className="block text-xs font-medium text-dark-5 dark:text-dark-6">
              Voice Receptionist
            </span>
          </div>
        </div>

        <div className="flex flex-1 flex-col justify-center">
          <div className="mx-auto w-full max-w-md">
            <h1 className="mb-2 text-heading-4 font-bold text-dark dark:text-white">
              Sign in
            </h1>
            <p className="mb-10 text-base text-dark-5 dark:text-dark-6">
              Enter your credentials to access the dashboard.
            </p>

            <form onSubmit={handleSubmit} className="space-y-5">
              <Field label="Email">
                <Mail className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-dark-5 dark:text-dark-6" />
                <input
                  type="email"
                  autoComplete="email"
                  required
                  placeholder="you@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={INPUT}
                />
              </Field>

              <Field label="Password">
                <Lock className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-dark-5 dark:text-dark-6" />
                <input
                  type="password"
                  autoComplete="current-password"
                  required
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={INPUT}
                />
              </Field>

              {error && (
                <div className="flex items-center gap-2 rounded-lg border border-red/30 bg-red-light-5 p-3 text-sm text-red dark:border-red/40 dark:bg-red/10">
                  <AlertCircle className="size-4 shrink-0" />
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-3.5 text-sm font-medium text-white transition-colors hover:bg-primary/90 disabled:opacity-60"
              >
                {loading && <Loader2 className="size-4 animate-spin" />}
                {loading ? "Signing in…" : "Sign in"}
              </button>
            </form>

            <p className="mt-10 text-center text-sm text-dark-5 dark:text-dark-6">
              Need access? Contact your administrator.
            </p>
          </div>
        </div>

        <p className="mt-12 text-center text-xs text-dark-5 dark:text-dark-6 xl:text-left">
          &copy; 2026 YourCompany. Powered by AI Telephone Receptionist.
        </p>
      </div>

      {/* Right: hero */}
      <div
        className="relative hidden overflow-hidden xl:block"
        style={{
          background:
            "linear-gradient(135deg, #5750F1 0%, #4035C7 50%, #2D2880 100%)",
        }}
      >
        {/* decorative blobs */}
        <div
          className="pointer-events-none absolute -right-32 -top-32 size-96 rounded-full opacity-30 blur-3xl"
          style={{ background: "rgba(255,255,255,0.4)" }}
        />
        <div
          className="pointer-events-none absolute -bottom-40 -left-32 size-112 rounded-full opacity-20 blur-3xl"
          style={{ background: "rgba(255,255,255,0.5)" }}
        />

        <div className="relative flex h-full flex-col items-center justify-center px-16 py-10">
          <LoginIllustration className="w-full max-w-md" />

          <div className="mt-6 max-w-md text-center">
            <p className="mb-3 text-xl font-medium text-white/80">
              Welcome back
            </p>
            <h2 className="mb-4 text-heading-3 font-bold text-white">
              Run your AI receptionist.
            </h2>
            <p className="text-base font-medium text-white/80">
              Track every call, customer, and booking — all in one multi-tenant
              control panel.
            </p>
          </div>

          <ul className="mx-auto mt-6 grid w-fit grid-cols-2 gap-x-8 gap-y-3 text-sm font-medium text-white">
            <Bullet>24/7 voice answering</Bullet>
            <Bullet>Outlook calendar bookings</Bullet>
            <Bullet>HubSpot CRM sync</Bullet>
            <Bullet>Multi-tenant control</Bullet>
          </ul>
        </div>
      </div>
    </div>
  );
}

const INPUT =
  "block w-full rounded-lg border border-stroke bg-transparent py-3.5 pl-11 pr-4 text-sm text-dark outline-none transition-colors focus:border-primary dark:border-stroke-dark dark:bg-dark-2 dark:text-white dark:placeholder:text-dark-6";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-2 block text-xs font-medium uppercase tracking-wider text-dark-5 dark:text-dark-6">
        {label}
      </span>
      <div className="relative">{children}</div>
    </label>
  );
}

function Bullet({ children }: { children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-3">
      <span className="mt-2 size-1.5 shrink-0 rounded-full bg-white" />
      <span>{children}</span>
    </li>
  );
}
