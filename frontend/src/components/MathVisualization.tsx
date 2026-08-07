import { lazy, Suspense, useMemo, useState } from 'react';
import { LoaderCircle, Play, RotateCcw } from 'lucide-react';
import type { MathVisualizationArtifact } from '../types';

const Plot = lazy(() => import('./PlotlyChart'));

interface Props {
  artifact: MathVisualizationArtifact;
  onGenerateAnimation?: (visualizationId: string) => Promise<void>;
}

function linearGrid(matrix: number[][]): any[] {
  if (!Array.isArray(matrix) || matrix.length !== 2) return [];
  const transform = (x: number, y: number) => [
    matrix[0][0] * x + matrix[0][1] * y,
    matrix[1][0] * x + matrix[1][1] * y,
  ];
  const traces: any[] = [];
  for (let offset = -5; offset <= 5; offset += 1) {
    const lines = [
      [[offset, -5], [offset, 5]],
      [[-5, offset], [5, offset]],
    ];
    for (const line of lines) {
      const transformed = line.map(([x, y]) => transform(x, y));
      traces.push({
        type: 'scatter', mode: 'lines', x: line.map((point) => point[0]), y: line.map((point) => point[1]),
        line: { color: '#cbd5e1', width: 1, dash: 'dot' }, hoverinfo: 'skip', showlegend: false,
      });
      traces.push({
        type: 'scatter', mode: 'lines', x: transformed.map((point) => point[0]), y: transformed.map((point) => point[1]),
        line: { color: '#93c5fd', width: 1.25 }, hoverinfo: 'skip', showlegend: false,
      });
    }
  }
  return traces;
}

function plotModel(artifact: MathVisualizationArtifact): { data: any[]; layout: any } {
  const spec = artifact.spec || {};
  const data: any[] = [];
  const annotations: any[] = [];

  if (artifact.kind === 'function_2d' || artifact.kind === 'parametric_2d') {
    for (const series of spec.series || []) {
      data.push({
        type: 'scatter', mode: 'lines', name: series.label,
        x: (series.points || []).map((point: any) => point.x),
        y: (series.points || []).map((point: any) => point.y),
        line: { color: series.color, width: 2.5 },
        connectgaps: false,
      });
    }
  } else if (artifact.kind === 'vector_2d') {
    for (const vector of spec.vectors || []) {
      data.push({ type: 'scatter', mode: 'lines+markers', name: vector.label || vector.id, x: [0, vector.x], y: [0, vector.y], line: { color: vector.color, width: 3 }, marker: { color: vector.color, size: [4, 8] } });
      annotations.push({ x: vector.x, y: vector.y, ax: 0, ay: 0, axref: 'x', ayref: 'y', showarrow: true, arrowhead: 3, arrowsize: 1.2, arrowcolor: vector.color, text: vector.label || '' });
    }
    for (const point of spec.points || []) {
      data.push({ type: 'scatter', mode: 'markers+text', name: point.label || point.id, x: [point.x], y: [point.y], text: [point.label], textposition: 'top center', marker: { color: point.color, size: 9 } });
    }
    for (const segment of spec.segments || []) {
      data.push({ type: 'scatter', mode: 'lines', name: segment.label || segment.id, x: [segment.start.x, segment.end.x], y: [segment.start.y, segment.end.y], line: { color: segment.color, width: 2 } });
    }
  } else {
    data.push(...linearGrid(spec.matrix));
    for (const vector of spec.vectors || []) {
      const transformed = vector.transformed;
      data.push({ type: 'scatter', mode: 'lines+markers', name: `${vector.label || vector.id}（原）`, x: [0, vector.x], y: [0, vector.y], line: { color: vector.color, width: 2, dash: 'dot' }, marker: { size: 6 } });
      data.push({ type: 'scatter', mode: 'lines+markers', name: `${vector.label || vector.id}（变换后）`, x: [0, transformed.x], y: [0, transformed.y], line: { color: vector.color, width: 3 }, marker: { size: 8 } });
    }
  }

  return {
    data,
    layout: {
      autosize: true,
      height: 320,
      margin: { l: 46, r: 18, t: 18, b: 64 },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { family: 'system-ui, sans-serif', size: 11, color: '#64748b' },
      xaxis: { zeroline: true, zerolinecolor: '#94a3b8', gridcolor: '#e2e8f0', scaleanchor: artifact.kind.includes('vector') || artifact.kind === 'linear_transform_2d' ? 'y' : undefined },
      yaxis: { zeroline: true, zerolinecolor: '#94a3b8', gridcolor: '#e2e8f0' },
      legend: { orientation: 'h', y: -0.24, x: 0 },
      hovermode: 'closest',
      annotations,
    },
  };
}

export default function MathVisualization({ artifact, onGenerateAnimation }: Props) {
  const [requestError, setRequestError] = useState('');
  const [requesting, setRequesting] = useState(false);
  const model = useMemo(() => plotModel(artifact), [artifact]);
  const animation = artifact.animation;
  const busy = requesting || artifact.animation_status === 'queued' || artifact.animation_status === 'running';

  const generate = async () => {
    if (!onGenerateAnimation || busy) return;
    setRequestError('');
    setRequesting(true);
    try {
      await onGenerateAnimation(artifact.id);
    } catch (error) {
      setRequestError(error instanceof Error ? error.message : '动画生成失败');
    } finally {
      setRequesting(false);
    }
  };

  return (
    <section className="mt-3 w-full min-w-0 overflow-hidden rounded-md border border-slate-200 bg-white dark:border-slate-600 dark:bg-slate-800" aria-label={artifact.title}>
      <div className="flex min-h-10 items-center justify-between gap-3 border-b border-slate-200 px-3 py-2 dark:border-slate-700">
        <h4 className="min-w-0 truncate text-sm font-medium text-slate-700 dark:text-slate-200">{artifact.title}</h4>
        {artifact.animation_available && artifact.animation_status !== 'completed' && (
          <button
            type="button"
            onClick={generate}
            disabled={busy || !onGenerateAnimation}
            title={artifact.animation_status === 'failed' ? '重新生成动画' : '生成动画'}
            className="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-md bg-blue-600 px-2.5 text-xs font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : artifact.animation_status === 'failed' ? <RotateCcw className="h-4 w-4" /> : <Play className="h-4 w-4" />}
            {busy ? (artifact.animation_status === 'running' ? '渲染中' : '排队中') : artifact.animation_status === 'failed' ? '重试' : '生成动画'}
          </button>
        )}
      </div>
      <div className="h-[320px] w-full">
        <Suspense fallback={<div className="flex h-full items-center justify-center text-xs text-slate-400"><LoaderCircle className="mr-2 h-4 w-4 animate-spin" />加载图形</div>}>
          <Plot
            data={model.data}
            layout={model.layout}
            config={{
              responsive: true,
              displaylogo: false,
              displayModeBar: 'hover',
              scrollZoom: true,
              modeBarButtonsToRemove: [
                'select2d', 'lasso2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d',
                'toggleSpikelines', 'hoverClosestCartesian', 'hoverCompareCartesian',
              ],
              toImageButtonOptions: { format: 'png', filename: artifact.title || 'math-visualization' },
            }}
            useResizeHandler
            className="math-visualization-plot h-full w-full"
          />
        </Suspense>
      </div>
      {animation?.status === 'completed' && animation.video_url && (
        <video className="block w-full border-t border-slate-200 bg-black dark:border-slate-700" controls preload="metadata" poster={animation.poster_url || undefined}>
          <source src={animation.video_url} type="video/mp4" />
        </video>
      )}
      {(requestError || animation?.error) && (
        <div className="border-t border-red-200 bg-red-50 px-3 py-2 text-xs text-red-600 dark:border-red-900/60 dark:bg-red-950/20 dark:text-red-400">
          {requestError || animation?.error}
        </div>
      )}
    </section>
  );
}
