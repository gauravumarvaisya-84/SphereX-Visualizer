import React, { useEffect, useRef, useState } from 'react';
import { Radio, Slider } from '@radix-ui/react-slider'; // placeholder for UI
import { Sun, Moon, ArrowRightLeft } from 'lucide-react';

import React, { useEffect, useRef, useState } from 'react';
import { Radio, Slider } from '@radix-ui/react-slider'; // placeholder for UI
import { Sun, Moon, ArrowRightLeft } from 'lucide-react';

export default function CanvasView() {
  const canvasRef = useRef(null);
  const [mode, setMode] = useState('single'); // 'single', 'blink', 'diff'
  const [fps, setFps] = useState(4);

  // Placeholder drawing
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#222';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    // Draw simple grid
    ctx.strokeStyle = '#555';
    ctx.lineWidth = 1;
    for (let x = 0; x < canvas.width; x += 40) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, canvas.height);
      ctx.stroke();
    }
    for (let y = 0; y < canvas.height; y += 40) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(canvas.width, y);
      ctx.stroke();
    }
  }, []);

  // Mode switcher UI – placed bottom‑right, minimal
  return (
    <div className="h-full flex flex-col relative">
      <canvas ref={canvasRef} className="flex-1 w-full bg-canvas-bg-light dark:bg-canvas-bg-dark" width={800} height={600} />
      <div className="absolute bottom-2 right-2 flex items-center gap-2 p-1 bg-surface-light dark:bg-surface-dark border border-hairline rounded">
        <button
          className={`px-2 py-0.5 text-xs rounded border ${mode === 'single' ? 'border-primary-text-light dark:border-primary-text-dark' : 'border-transparent'} transition-colors`}
          onClick={() => setMode('single')}
        >
          Single
        </button>
        <button
          className={`px-2 py-0.5 text-xs rounded border ${mode === 'blink' ? 'border-primary-text-light dark:border-primary-text-dark' : 'border-transparent'} transition-colors`}
          onClick={() => setMode('blink')}
        >
          Blink
        </button>
        <button
          className={`px-2 py-0.5 text-xs rounded border ${mode === 'diff' ? 'border-primary-text-light dark:border-primary-text-dark' : 'border-transparent'} transition-colors`}
          onClick={() => setMode('diff')}
        >
          Diff
        </button>
        {mode === 'blink' && (
          <div className="flex items-center gap-1">
            <span className="text-xs">{fps} fps</span>
            <input
              type="range"
              min={1}
              max={8}
              value={fps}
              onChange={(e) => setFps(Number(e.target.value))}
              className="w-16"
            />
          </div>
        )}
      </div>
    </div>
  );
}
() {
  const canvasRef = useRef(null);
  const [mode, setMode] = useState('single'); // 'single', 'blink', 'diff'
  const [fps, setFps] = useState(4);

  // Placeholder drawing
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#222';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    // Draw simple grid
    ctx.strokeStyle = '#555';
    ctx.lineWidth = 1;
    for (let x = 0; x < canvas.width; x += 40) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, canvas.height);
      ctx.stroke();
    }
    for (let y = 0; y < canvas.height; y += 40) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(canvas.width, y);
      ctx.stroke();
    }
  }, []);

  // Mode switcher UI – simple buttons
  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-center gap-4 p-2 border-b border-hairline border-light dark:border-dark bg-surface-light dark:bg-surface-dark">
        <button
          className={`px-3 py-1 rounded-md border ${mode === 'single' ? 'border-primary-text-light dark:border-primary-text-dark' : 'border-transparent'} transition-colors`}
          onClick={() => setMode('single')}
        >
          Single Epoch
        </button>
        <button
          className={`px-3 py-1 rounded-md border ${mode === 'blink' ? 'border-primary-text-light dark:border-primary-text-dark' : 'border-transparent'} transition-colors`}
          onClick={() => setMode('blink')}
        >
          Blink Comparator
        </button>
        <button
          className={`px-3 py-1 rounded-md border ${mode === 'diff' ? 'border-primary-text-light dark:border-primary-text-dark' : 'border-transparent'} transition-colors`}
          onClick={() => setMode('diff')}
        >
          Difference Imaging
        </button>
        {mode === 'blink' && (
          <div className="flex items-center gap-2 w-48">
            <span className="text-xs">{fps} fps</span>
            <input
              type="range"
              min={1}
              max={8}
              value={fps}
              onChange={(e) => setFps(Number(e.target.value))}
              className="w-full"
            />
          </div>
        )}
      </div>
      <canvas ref={canvasRef} className="flex-1 w-full bg-canvas-bg-light dark:bg-canvas-bg-dark" width={800} height={600} />
    </div>
  );
}
