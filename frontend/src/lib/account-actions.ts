"use server";

import { redirect } from "next/navigation";

import { ApiError } from "@/api/fetcher";
import {
  forgotPassword as forgotPasswordRequest,
  resendVerification as resendVerificationRequest,
  resetPassword as resetPasswordRequest,
  signup as signupRequest,
} from "@/api/generated/endpoints/auth/auth";
import { errorMessage, field } from "@/lib/action-result";
import { setSession } from "@/lib/session";

// --- Sign-up ---

export type SignupState = {
  error?: string;
  values?: { organization_name?: string; name?: string; email?: string };
};

export async function signup(_prev: SignupState, form: FormData): Promise<SignupState> {
  const values = {
    organization_name: field(form, "organization_name"),
    name: field(form, "name"),
    email: field(form, "email"),
  };
  const password = String(form.get("password") ?? "");
  if (!values.organization_name || !values.name || !values.email || !password) {
    return { error: "Fill in every field.", values };
  }
  if (password.length < 8) {
    return { error: "Use a password of at least 8 characters.", values };
  }

  try {
    const data = await signupRequest({
      organization_name: values.organization_name,
      name: values.name,
      email: values.email,
      password,
    });
    await setSession(data.access_token, data.expires_in);
  } catch (err) {
    if (err instanceof ApiError && err.status === 422) {
      return { error: validationMessage(err.message), values };
    }
    return { error: errorMessage(err), values };
  }
  redirect("/");
}

function validationMessage(detail: string): string {
  if (detail.toLowerCase().includes("email")) return "Enter a valid email address.";
  return detail;
}

// --- Forgot password ---

export type ForgotPasswordState = { error?: string; sent?: string; email?: string };

export async function forgotPassword(
  _prev: ForgotPasswordState,
  form: FormData,
): Promise<ForgotPasswordState> {
  const email = field(form, "email");
  if (!email) return { error: "Enter your email address." };
  try {
    const res = await forgotPasswordRequest({ email });
    return { sent: res.message, email };
  } catch (err) {
    return { error: errorMessage(err), email };
  }
}

// --- Reset password ---

export type ResetPasswordState = { error?: string; done?: boolean };

export async function resetPassword(
  _prev: ResetPasswordState,
  form: FormData,
): Promise<ResetPasswordState> {
  const token = String(form.get("token") ?? "");
  const password = String(form.get("password") ?? "");
  const confirm = String(form.get("confirm") ?? "");
  if (password.length < 8) return { error: "Use a password of at least 8 characters." };
  if (password !== confirm) return { error: "The two passwords don't match." };
  try {
    await resetPasswordRequest({ token, password });
    return { done: true };
  } catch (err) {
    return { error: errorMessage(err) };
  }
}

// --- Resend the verification email (signed in) ---

export type ResendState = { error?: string; sent?: string };

export async function resendVerification(): Promise<ResendState> {
  try {
    const res = await resendVerificationRequest();
    return { sent: res.message };
  } catch (err) {
    return { error: errorMessage(err) };
  }
}
