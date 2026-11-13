import type { Metadata } from "next";
import Link from "next/link";

import { AuthShell, authLinkClass } from "@/components/auth-shell";

import { SignupForm } from "./signup-form";

export const metadata: Metadata = {
  title: "Create an account · AtroNexus",
};

export default function SignupPage() {
  return (
    <AuthShell
      title="Create an account"
      description="Set up AtroNexus for your company. You'll be its owner."
      footer={
        <>
          Already have an account?{" "}
          <Link href="/login" className={authLinkClass}>
            Sign in
          </Link>
        </>
      }
    >
      <SignupForm />
    </AuthShell>
  );
}
