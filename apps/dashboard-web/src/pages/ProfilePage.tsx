import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { RadarChart } from "../components/RadarChart";
import { authStore } from "../lib/auth";
import type { Profile, RadarPoint } from "../types/api";

export function ProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [history, setHistory] = useState<RadarPoint[]>([]);

  useEffect(() => {
    const userId = authStore.getUserId();
    if (!userId) return;

    Promise.all([api.getProfile(userId), api.getRadarHistory(userId, 90)]).then(([p, h]) => {
      setProfile(p);
      setHistory(h);
    });
  }, []);

  const deltas = useMemo(() => {
    if (history.length < 2) return null;
    const prev = history[history.length - 2].radar_vector;
    const curr = history[history.length - 1].radar_vector;
    const out: Record<string, number> = {};
    Object.keys(curr).forEach((k) => {
      out[k] = (curr[k] ?? 0) - (prev[k] ?? 0);
    });
    return out;
  }, [history]);

  if (!profile) return <div className="card">Loading profile...</div>;

  return (
    <section>
      <h2>Taste Profile</h2>
      <article className="card">
        <RadarChart values={profile.radar_vector} />
        <p>Last updated: {profile.updated_at ? new Date(profile.updated_at).toLocaleString() : "Never"}</p>
      </article>

      <article className="card">
        <h3>Radar Delta</h3>
        {deltas ? (
          <ul className="delta-list">
            {Object.entries(deltas).map(([k, v]) => (
              <li key={k}>
                {k}: {v >= 0 ? "+" : ""}
                {v.toFixed(1)}
              </li>
            ))}
          </ul>
        ) : (
          <p>Need at least 2 captures to show deltas.</p>
        )}
      </article>
    </section>
  );
}
