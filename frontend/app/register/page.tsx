import Link from "next/link";
import { RegisterForm } from "@/components/auth/RegisterForm";

export default function RegisterPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-950">
      <div className="w-full max-w-md rounded-2xl border border-gray-800 bg-gray-900 p-8 shadow-xl">
        <h1 className="mb-2 text-2xl font-bold text-white">Create your account</h1>
        <p className="mb-6 text-sm text-gray-400">Get started with DevPulse</p>
        <RegisterForm />
        <p className="mt-4 text-center text-sm text-gray-500">
          Already have an account?{" "}
          <Link href="/login" className="text-brand-400 hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
