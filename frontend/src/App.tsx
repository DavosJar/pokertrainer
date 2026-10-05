import React, { useState, useEffect } from 'react';
import { SessionSetup } from './components/SessionSetup';
import { TrainingCard } from './components/TrainingCard';
import { Dashboard } from './components/Dashboard';
import { RangeExplorer } from './components/RangeExplorer';

export const App: React.FC = () => {
  const [currentPage, setCurrentPage] = useState<string>('setup');

  useEffect(() => {
    const rootEl = document.getElementById('root');
    const dataPage = rootEl?.getAttribute('data-page');

    if (dataPage) {
      setCurrentPage(dataPage);
    } else {
      const path = window.location.pathname;
      if (path === '/train') setCurrentPage('train');
      else if (path === '/stats') setCurrentPage('stats');
      else if (path === '/ranges') setCurrentPage('ranges');
      else setCurrentPage('setup');
    }
  }, []);

  const handleSessionStart = (sessionId: string) => {
    localStorage.setItem('poker_active_session_id', sessionId);
    window.location.href = '/train';
  };

  switch (currentPage) {
    case 'train':
      return <TrainingCard />;
    case 'stats':
      return <Dashboard />;
    case 'ranges':
      return <RangeExplorer />;
    case 'setup':
    default:
      return <SessionSetup onSessionStart={handleSessionStart} />;
  }
};
