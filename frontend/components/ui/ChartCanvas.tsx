"use client";

import { useEffect, useRef } from "react";
import type { ChartConfiguration } from "chart.js";

/** Thin Chart.js wrapper with ChainSentinel dark defaults. */
export default function ChartCanvas({
  config,
  height = 260,
}: {
  config: ChartConfiguration;
  height?: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const chartRef = useRef<import("chart.js").Chart | null>(null);

  useEffect(() => {
    let disposed = false;
    (async () => {
      const { Chart } = await import("chart.js/auto");
      if (disposed || !canvasRef.current) return;

      Chart.defaults.color = "#8fa1c0";
      Chart.defaults.borderColor = "rgba(31, 42, 61, 0.8)";
      Chart.defaults.font.family =
        "'Inter', -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif";

      chartRef.current?.destroy();
      chartRef.current = new Chart(canvasRef.current, config);
    })();
    return () => {
      disposed = true;
      chartRef.current?.destroy();
      chartRef.current = null;
    };
  }, [config]);

  return (
    <div style={{ position: "relative", height }}>
      <canvas ref={canvasRef} aria-label="chart" role="img" />
    </div>
  );
}
