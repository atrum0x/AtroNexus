import type { Metadata } from "next";
import Link from "next/link";

import { AuthShell, authLinkClass } from "@/components/auth-shell";

import { LoginForm } from "./login-form";

export const metadata: Metadata = {
  title: "Sign in · AtroNexus",
};

export default function LoginPage() {
  return (
    <AuthShell
      title="Sign in"
      description="Enter your email and password to continue."
      footer={
        <>
          New to AtroNexus?{" "}
          <Link href="/signup" className={authLinkClass}>
            Create an account
          </Link>
        </>
      }
    >
      <LoginForm />
    </AuthShell>
  );
}
