import React, { useState } from 'react';
import TopBar from './components/TopBar';
import CanvasView from './components/CanvasView';
import BottomPanel from './components/BottomPanel';
import SettingsPage from './components/SettingsPage';

export default function App() {
  const [page, setPage] = useState('dashboard');

  if (page === 'settings') {
    return (
      <div className="flex flex-col h-screen overflow-hidden">
        <TopBar onNavigate={setPage} />
        <SettingsPage />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <TopBar onNavigate={setPage} />
      <main className="flex-1 flex overflow-hidden">
        <aside className="w-1/3 min-w-[300px] border-r border-hairline border-light dark:border-dark bg-surface-light dark:bg-surface-dark overflow-y-auto">
          <BottomPanel />
        </aside>
        <div className="flex-1 overflow-hidden">
          <CanvasView />
        </div>
      </main>
    </div>
  );
}
