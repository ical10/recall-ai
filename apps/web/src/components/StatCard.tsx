import { Card } from "@/components/ui/Card";
import { Eyebrow } from "@/components/ui/Eyebrow";
import { IconBadge } from "@/components/ui/IconBadge";
import { Icon } from "@/components/ui/Icon";

type StatIcon = "clock" | "check" | "flame";

const iconColorMap: Record<StatIcon, { bg: string; text: string }> = {
  clock: { bg: "bg-tangerine", text: "text-cream-50" },
  check: { bg: "bg-teal", text: "text-cream-50" },
  flame: { bg: "bg-honey", text: "text-ink" },
};

export function StatCard({
  label,
  value,
  subtitle,
  icon,
  tilt,
  delay = 0,
}: {
  label: string;
  value: number;
  subtitle: string;
  icon: StatIcon;
  tilt?: "l" | "r" | "l-2" | "r-2";
  delay?: number;
}) {
  const colors = iconColorMap[icon];

  return (
    <Card
      tilt={tilt ?? "l"}
      animate="rise"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="flex items-start justify-between">
        <Eyebrow>{label}</Eyebrow>
        <IconBadge size="sm" color={colors.bg}>
          <Icon name={icon} className={`h-4 w-4 ${colors.text}`} />
        </IconBadge>
      </div>
      <p className="mt-4 font-display text-6xl font-black leading-none text-ink">
        {value}
      </p>
      <p className="mt-2 text-sm font-medium text-ink-mute">{subtitle}</p>
    </Card>
  );
}
