export function StreamingMessage({ content }: { content: string }) {
  return (
    <div className="flex gap-3">
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-600 text-xs font-bold text-white">
        AI
      </div>
      <div className="flex-1 rounded-xl bg-gray-800 px-4 py-3 text-sm text-gray-100">
        {content}
        <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-brand-400 align-middle" />
      </div>
    </div>
  );
}
