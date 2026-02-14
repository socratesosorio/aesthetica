import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { authStore } from "../lib/auth";
import type { Capture, Profile } from "../types/api";

export function AnalyticsPage() {
  const [captures, setCaptures] = useState<Capture[]>([]);
  const [profile, setProfile] = useState<Profile | null>(null);

  useEffect(() => {
    const userId = authStore.getUserId();
    if (!userId) return;

    Promise.all([api.listCaptures(userId, 90), api.getProfile(userId)]).then(([c, p]) => {
      setCaptures(c);
      setProfile(p);
    });
  }, []);

  const frequencyByDay = useMemo(() => {
    const map: Record<string, number> = {};
    captures.forEach((c) => {
      const day = c.created_at.slice(0, 10);
      map[day] = (map[day] ?? 0) + 1;
    });
    return Object.entries(map).sort((a, b) => a[0].localeCompare(b[0]));
  }, [captures]);

  if (!profile) return <div className="card">Loading analytics...</div>;

  return (
    <section>
      <h2>Analytics</h2>
      <article className="card">
        <h3>Capture Frequency</h3>
        <div className="chips">
          {frequencyByDay.map(([day, count]) => (
            <span key={day}>
              {day}: {count}
            </span>
          ))}
        </div>
      </article>

      <article className="card">
        <h3>Category Bias</h3>
        <div className="chips">
          {Object.entries(profile.category_bias).map(([k, v]) => (
            <span key={k}>
              {k}: {v}
            </span>
          ))}
        </div>
      </article>

      <article className="card">
        <h3>Color Trend</h3>
        <div className="chips">
          {Object.entries(profile.color_stats)
            .slice(0, 12)
            .map(([hex, value]) => (
              <span key={hex} style={{ borderColor: hex }}>
                {hex} {(value * 100).toFixed(1)}%
              </span>
            ))}
        </div>
      </article>
    </section>
  );
}
