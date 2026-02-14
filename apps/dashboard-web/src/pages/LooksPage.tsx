import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { authStore } from "../lib/auth";
import type { Capture } from "../types/api";

export function LooksPage() {
  const [captures, setCaptures] = useState<Capture[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const userId = authStore.getUserId();
    if (!userId) return;

    api
      .listCaptures(userId, 60)
      .then((rows) => setCaptures(rows))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="card">Loading looks...</div>;

  return (
    <section>
      <div className="section-head">
        <h2>Looks</h2>
        <span>{captures.length} captured</span>
      </div>
      <div className="grid">
        {captures.map((capture) => (
          <Link className="look-card" key={capture.id} to={`/looks/${capture.id}`}>
            <img src={api.mediaUrl(capture.image_path)} alt="captured look" />
            <div>
              <strong>{new Date(capture.created_at).toLocaleString()}</strong>
              <small>{capture.status}</small>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
