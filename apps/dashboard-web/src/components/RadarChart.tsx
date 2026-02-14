import * as d3 from "d3";
import { useEffect, useRef } from "react";

type Props = {
  values: Record<string, number>;
};

const AXES = [
  "minimal_maximal",
  "structured_relaxed",
  "neutral_color_forward",
  "classic_experimental",
  "casual_formal",
] as const;

const LABELS: Record<(typeof AXES)[number], string> = {
  minimal_maximal: "Minimal ↔ Maximal",
  structured_relaxed: "Structured ↔ Relaxed",
  neutral_color_forward: "Neutral ↔ Color",
  classic_experimental: "Classic ↔ Experimental",
  casual_formal: "Casual ↔ Formal",
};

export function RadarChart({ values }: Props) {
  const ref = useRef<SVGSVGElement | null>(null);

  useEffect(() => {
    const svg = d3.select(ref.current);
    svg.selectAll("*").remove();

    const width = 340;
    const height = 320;
    const radius = 110;
    const centerX = width / 2;
    const centerY = height / 2;

    svg.attr("viewBox", `0 0 ${width} ${height}`);

    const g = svg.append("g").attr("transform", `translate(${centerX},${centerY})`);

    const angle = d3.scaleLinear().domain([0, AXES.length]).range([0, Math.PI * 2]);
    const rScale = d3.scaleLinear().domain([0, 100]).range([0, radius]);

    [20, 40, 60, 80, 100].forEach((tick) => {
      const points = AXES.map((_, i) => {
        const a = angle(i) - Math.PI / 2;
        return [Math.cos(a) * rScale(tick), Math.sin(a) * rScale(tick)] as [number, number];
      });
      points.push(points[0]);
      g.append("path")
        .attr("d", d3.line()(points as [number, number][]) ?? "")
        .attr("fill", "none")
        .attr("stroke", "rgba(255,255,255,0.2)")
        .attr("stroke-width", 1);
    });

    AXES.forEach((axis, i) => {
      const a = angle(i) - Math.PI / 2;
      g.append("line")
        .attr("x1", 0)
        .attr("y1", 0)
        .attr("x2", Math.cos(a) * radius)
        .attr("y2", Math.sin(a) * radius)
        .attr("stroke", "rgba(255,255,255,0.35)");

      g.append("text")
        .attr("x", Math.cos(a) * (radius + 18))
        .attr("y", Math.sin(a) * (radius + 18))
        .attr("fill", "#faf7ef")
        .attr("font-size", 11)
        .attr("text-anchor", "middle")
        .text(LABELS[axis]);
    });

    const poly = AXES.map((axis, i) => {
      const val = values[axis] ?? 50;
      const a = angle(i) - Math.PI / 2;
      return [Math.cos(a) * rScale(val), Math.sin(a) * rScale(val)] as [number, number];
    });
    poly.push(poly[0]);

    g.append("path")
      .attr("d", d3.line()(poly as [number, number][]) ?? "")
      .attr("fill", "rgba(245, 179, 66, 0.35)")
      .attr("stroke", "#f5b342")
      .attr("stroke-width", 2);

    g.selectAll("circle.value")
      .data(poly.slice(0, -1))
      .enter()
      .append("circle")
      .attr("class", "value")
      .attr("cx", (d) => d[0])
      .attr("cy", (d) => d[1])
      .attr("r", 4)
      .attr("fill", "#ffd166");
  }, [values]);

  return <svg ref={ref} className="radar" />;
}
