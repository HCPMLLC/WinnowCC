interface UsageMeterProps {
  label: string;
  used: number;
  limit: number | null;
  period?: string;
}

export default function UsageMeter({
  label,
  used,
  limit,
  period,
}: UsageMeterProps) {
  const isUnlimited = limit === null || limit >= 9999;
  const pct = isUnlimited
    ? 0
    : limit > 0
      ? Math.min(Math.round((used / limit) * 100), 100)
      : 0;

  let barColor = "bg-blue-500";
  if (!isUnlimited) {
    if (pct >= 90) barColor = "bg-red-500";
    else if (pct >= 70) barColor = "bg-amber-500";
  }

  return (
    <div>
      <div className="mb-1 flex justify-between text-sm">
        <span className="font-medium text-slate-700">
          {label}
          {period && (
            <span className="ml-1 font-normal text-slate-400">{period}</span>
          )}
        </span>
        <span
          className={
            !isUnlimited && used >= limit!
              ? "font-semibold text-red-600"
              : "text-slate-500"
          }
        >
          {isUnlimited ? `${used} used (unlimited)` : `${used} / ${limit}`}
        </span>
      </div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-100">
        <div
          className={`h-full rounded-full transition-all ${barColor}`}
          style={isUnlimited ? { width: "100%" } : { width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
