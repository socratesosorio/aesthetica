import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import type { Capture } from "../types/api";

type ProductCard = {
  productId: string;
  group: string;
  similarity: number;
};

export function LookDetailPage() {
  const { id } = useParams();
  const [capture, setCapture] = useState<Capture | null>(null);

  useEffect(() => {
    if (!id) return;
    api.getCapture(id).then(setCapture);
  }, [id]);

  const groupedMatches = useMemo(() => {
    if (!capture) return [] as ProductCard[];
    return capture.matches.map((m) => ({
      productId: m.product_id,
      group: m.match_group,
      similarity: m.similarity,
    }));
  }, [capture]);

  if (!capture) return <div className="card">Loading look...</div>;

  return (
    <section>
      <h2>Look Detail</h2>
      <article className="card">
        <img className="hero" src={api.mediaUrl(capture.image_path)} alt="look" />
        <p>Status: {capture.status}</p>
      </article>

      <article className="card">
        <h3>Garments</h3>
        <div className="garment-list">
          {capture.garments.map((g) => (
            <div key={g.id} className="garment-item">
              <img src={api.mediaUrl(g.crop_path)} alt={g.garment_type} />
              <div>
                <strong>{g.garment_type}</strong>
                <pre>{JSON.stringify(g.attributes, null, 2)}</pre>
              </div>
            </div>
          ))}
        </div>
      </article>

      <article className="card">
        <h3>Matches</h3>
        <div className="chips">
          {groupedMatches.map((m, i) => (
            <span key={`${m.productId}-${i}`}>
              {m.group}: {m.productId} ({m.similarity.toFixed(3)})
            </span>
          ))}
        </div>
      </article>
    </section>
  );
}
