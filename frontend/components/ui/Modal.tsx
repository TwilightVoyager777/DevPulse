"use client";

import { cn } from "@/lib/cn";
import React, { useEffect } from "react";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  className?: string;
}

export function Modal({ open, onClose, title, children, className }: ModalProps) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    if (open) document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div
        className={cn(
          "relative z-10 w-full max-w-md rounded-2xl border border-gray-700 bg-gray-900 p-6 shadow-2xl",
          className
        )}
      >
        <h2 className="mb-4 text-lg font-semibold text-white">{title}</h2>
        {children}
      </div>
    </div>
  );
}
