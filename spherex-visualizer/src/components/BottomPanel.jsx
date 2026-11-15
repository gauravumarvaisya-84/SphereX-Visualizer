import React from 'react';

export default function BottomPanel() {
  return (
    <section className="h-40 border-t border-hairline border-light dark:border-dark bg-surface-light dark:bg-surface-dark overflow-auto p-2">
      <h3 className="text-sm font-medium mb-1">Spectral Energy Distribution (102‑Band)</h3>
      {/* Placeholder chart – replace with real plot library */}
      <div className="w-full h-32 bg-muted-light dark:bg-muted-dark flex items-center justify-center text-xs text-muted-light dark:text-muted-dark">
        SED plot goes here
      </div>
      <div className="text-xs mt-1 space-x-2">
        <span className="inline-block border border-hairline px-1 rounded">H₂O</span>
        <span className="inline-block border border-hairline px-1 rounded">CH₄</span>
        <span className="inline-block border border-hairline px-1 rounded">CO₂/CO</span>
      </div>
    </section>
  );
}
