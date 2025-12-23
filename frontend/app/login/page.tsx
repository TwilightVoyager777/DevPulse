import Link from "next/link";
import { LoginForm } from "@/components/auth/LoginForm";

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-950">
      <div className="w-full max-w-md rounded-2xl border border-gray-800 bg-gray-900 p-8 shadow-xl">
        <h1 className="mb-2 text-2xl font-bold text-white">Sign in to DevPulse</h1>
        <p className="mb-6 text-sm text-gray-400">
          AI-powered Q&A for your dev knowledge base
        </p>
        <LoginForm />
        <p className="mt-4 text-center text-sm text-gray-500">
          No account?{" "}
          <Link href="/register" className="text-brand-400 hover:underline">
            Create one
          </Link>
        </p>
      </div>
    </div>
  );
}
