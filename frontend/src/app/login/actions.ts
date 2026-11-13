"use server";

import { redirect } from "next/navigation";

import { ApiError } from "@/api/fetcher";
import { login as loginRequest } from "@/api/generated/endpoints/auth/auth";
import { clearSession, setSession } from "@/lib/session";

export type LoginState = {
  error?: string;
  email?: string;
};

export async function login(_prev: LoginState, formData: FormData): Promise<LoginState> {
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");

  if (!email || !password) {
    return { error: "Enter your email and password.", email };
  }

  try {
    const data = await loginRequest({ email, password });
    await setSession(data.access_token, data.expires_in);
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      return { error: "Invalid email or password.", email };
    }
    // Shows up in the Vercel function logs, so a misconfiguration is findable.
    console.error("Login request failed:", err);
    if (err instanceof ApiError && err.status === 403 && err.message.includes("suspended")) {
      return { error: err.message, email };
    }
    if (err instanceof ApiError && err.status === 403) {
      return {
        error: "The server refused the request. INTERNAL_API_KEY differs between the frontend and the backend.",
        email,
      };
    }
    if (err instanceof ApiError) {
      return { error: `Sign-in failed (${err.status}): ${err.message}`, email };
    }
    return { error: "Can't reach the server. Try again in a moment.", email };
  }

  redirect("/");
}

export async function logout() {
  await clearSession();
  redirect("/login");
}
