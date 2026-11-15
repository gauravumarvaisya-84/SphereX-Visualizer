import React, { useState } from 'react';
import { Search, Loader2 } from 'lucide-react';

import React, { useState } from 'react';
import { Search, Loader2, Settings } from 'lucide-react';

export default function TopBar({ onNavigate }) {
  const [target, setTarget] = useState('');
  const [queryStatus, setQueryStatus] = useState('idle'); // idle, loading, done

  const handleSubmit = (e) => {
    e.preventDefault();
    // Placeholder: trigger query
    setQueryStatus('loading');
    setTimeout(() => setQueryStatus('done'), 1000);
  };

  return (
    <header className="h-12 flex items-center justify-between px-4 border-b border-hairline border-light dark:border-dark bg-surface-light dark:bg-surface-dark">
      <h1 className="text-sm font-medium">SPHEREx Mission Visualizer · Team Pioneer Matrix</h1>
      <form className="flex items-center gap-2" onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="RA/Dec (e.g., 14h15m39s +19d10m56s)"
          className="px-2 py-1 border border-hairline border-light dark:border-dark rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-text-light dark:focus-visible:outline-primary-text-dark text-xs"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
        />
        <button type="submit" className="p-1 rounded-md hover:bg-muted-light dark:hover:bg-muted-dark transition-colors duration-150">
          <Search size={16} />
        </button>
        {queryStatus === 'loading' && <Loader2 className="animate-spin text-primary-text-light dark:text-primary-text-dark" size={16} />}
      </form>
      {/* Settings navigation button */}
      <button onClick={() => onNavigate('settings')} className="p-1 rounded-md hover:bg-muted-light dark:hover:bg-muted-dark transition-colors duration-150">
        <Settings size={16} />
      </button>
    </header>
  );
}
() {
  const [target, setTarget] = useState('');
  const [queryStatus, setQueryStatus] = useState('idle'); // idle, loading, done

  const handleSubmit = (e) => {
    e.preventDefault();
    // Placeholder: trigger query
    setQueryStatus('loading');
    setTimeout(() => setQueryStatus('done'), 1000);
  };

  return (
    <header className="h-12 flex items-center justify-between px-4 border-b border-hairline border-light dark:border-dark bg-surface-light dark:bg-surface-dark">
      <h1 className="text-sm font-medium">SPHEREx Mission Visualizer · Team Pioneer Matrix</h1>
      <form className="flex items-center gap-2" onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="RA/Dec (e.g., 14h15m39s +19d10m56s)"
          className="px-2 py-1 border border-hairline border-light dark:border-dark rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-text-light dark:focus-visible:outline-primary-text-dark text-xs"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
        />
        <button type="submit" className="p-1 rounded-md hover:bg-muted-light dark:hover:bg-muted-dark transition-colors duration-150">
          <Search size={16} />
        </button>
        {queryStatus === 'loading' && <Loader2 className="animate-spin text-primary-text-light dark:text-primary-text-dark" size={16} />}
      </form>
    </header>
  );
}
