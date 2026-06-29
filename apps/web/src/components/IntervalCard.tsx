interface RecentReview {
  token: string;
  interval_days: number;
  reviewed_at: string;
}

export function IntervalCard({ review, index }: { review: RecentReview; index: number }) {
  const bg =
    review.interval_days >= 7
      ? "bg-teal text-cream-50"
      : review.interval_days >= 3
        ? "bg-sky text-cream-50"
        : "bg-honey text-ink";

  return (
    <li
      className="card-paper !p-4 flex items-center justify-between"
      style={index % 2 === 0 ? { transform: "rotate(-1.5deg)" } : { transform: "rotate(1.5deg)" }}
    >
      <div className="flex items-center gap-3">
        <span
          className={`inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border-2 border-ink font-display text-sm font-bold ${bg}`}
        >
          {review.interval_days}d
        </span>
        <div>
          <p className="font-display text-lg font-black leading-none text-ink">{review.token}</p>
          <p className="mt-1 font-mono text-[11px] text-ink-mute">
            {new Date(review.reviewed_at).toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
              hour: "2-digit",
              minute: "2-digit",
              timeZone: "UTC",
            })}{" "}
            UTC
          </p>
        </div>
      </div>
      <span className="font-mono text-[11px] uppercase tracking-widest text-ink-mute">
        interval
      </span>
    </li>
  );
}
