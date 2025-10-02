import React, { useState, useEffect } from 'react';

// --- Mock Data ---
// In a real app, this would be fetched from your API
const MOCKED_SUMMARY_DATA = [
    { date: '2025-10-01', activity_count: 120, screenshot_count: 15 },
    { date: '2025-09-30', activity_count: 250, screenshot_count: 30 },
    { date: '2025-09-29', activity_count: 180, screenshot_count: 22 },
];

const MOCKED_DETAIL_DATA = {
    '2025-10-01': { date: '2025-10-01', entries: [
        { timestamp: '10:00:00', event_type: 'app.start', window_title: 'VS Code - monitoring/App.jsx' },
        { timestamp: '10:01:30', event_type: 'screenshot', window_title: 'Chrome - localhost:5173' },
        { timestamp: '10:05:00', event_type: 'app.stop', window_title: 'VS Code - monitoring/App.jsx' },
    ]},
    '2025-09-30': { date: '2025-09-30', entries: [
        { timestamp: '11:30:00', event_type: 'app.start', window_title: 'Photoshop - new_design.psd' },
        { timestamp: '11:35:10', event_type: 'screenshot', window_title: 'Photoshop - new_design.psd' },
        { timestamp: '11:40:15', event_type: 'idle', window_title: 'Photoshop - new_design.psd' },
    ]},
    '2025-09-29': { date: '2025-09-29', entries: [] }, // Empty state for testing
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// --- Main App Component ---
function App() {
  const [summaryData, setSummaryData] = useState([]);
  const [detailData, setDetailData] = useState(null);
  const [loadingSummary, setLoadingSummary] = useState(true);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [selectedDate, setSelectedDate] = useState(null);
  const [error, setError] = useState(null);

  // --- Effects ---
  // Fetch summary data on initial load
  useEffect(() => {
    const fetchSummary = async () => {
      try {
        setLoadingSummary(true);
        const response = await fetch(`${API_BASE_URL}/api/logs/daily`);
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        setSummaryData(data);
        if (data.length > 0) {
          setSelectedDate(data[0].date);
        }
      } catch (e) {
        setError(e.message);
        // In case of API error, use mock data for demonstration
        setSummaryData(MOCKED_SUMMARY_DATA);
        if (MOCKED_SUMMARY_DATA.length > 0) {
          setSelectedDate(MOCKED_SUMMARY_DATA[0].date);
        }
      } finally {
        setLoadingSummary(false);
      }
    };
    fetchSummary();
  }, []);

  // Fetch detail data when selectedDate changes
  useEffect(() => {
    if (!selectedDate) return;
    const fetchDetails = async () => {
      try {
        setLoadingDetails(true);
        setError(null);
        const response = await fetch(`${API_BASE_URL}/api/logs/detail/${selectedDate}`);
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        setDetailData(data);
      } catch (e) {
        setError(e.message);
        // In case of API error, use mock data for demonstration
        setDetailData(MOCKED_DETAIL_DATA[selectedDate]);
      } finally {
        setLoadingDetails(false);
      }
    };
    fetchDetails();
  }, [selectedDate]);

  // --- Render Logic ---
  const renderDetailContent = () => {
    if (loadingDetails) {
      return <p className="text-gray-400">Loading details for {selectedDate}...</p>;
    }
    if (error) {
      return <p className="text-red-400">Error fetching details: {error}</p>;
    }
    if (!detailData || detailData.entries.length === 0) {
      return <p className="text-gray-500">No log entries recorded for this day.</p>;
    }
    return (
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm text-left text-gray-300">
          <thead className="text-xs text-gray-400 uppercase bg-gray-700">
            <tr>
              <th scope="col" className="px-6 py-3">Timestamp</th>
              <th scope="col" className="px-6 py-3">Event Type</th>
              <th scope="col" className="px-6 py-3">Window Title</th>
            </tr>
          </thead>
          <tbody>
            {detailData.entries.map((entry, index) => (
              <tr key={index} className="bg-gray-800 border-b border-gray-700 hover:bg-gray-600">
                <td className="px-6 py-4 font-mono">{entry.timestamp}</td>
                <td className="px-6 py-4">{entry.event_type}</td>
                <td className="px-6 py-4 truncate max-w-xs">{entry.window_title}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div className="bg-gray-900 text-gray-100 min-h-screen font-sans">
      <div className="flex" style={{ height: '100vh' }}>
        {/* Sidebar */}
        <aside className="w-1/3 lg:w-1/4 bg-gray-800 p-4 border-r border-gray-700 overflow-y-auto">
          <h2 className="text-xl font-bold mb-4 text-white">Daily Summaries</h2>
          {loadingSummary ? (
            <p>Loading summaries...</p>
          ) : (
            <ul className="space-y-3">
              {summaryData.map((summary) => (
                <li key={summary.date}>
                  <div
                    onClick={() => setSelectedDate(summary.date)}
                    className={`p-3 rounded-lg cursor-pointer transition-all duration-200 ${
                      selectedDate === summary.date
                        ? 'bg-indigo-600 shadow-lg'
                        : 'bg-gray-700 hover:bg-gray-600 hover:shadow-md'
                    }`}
                  >
                    <p className="font-bold text-md">{summary.date}</p>
                    <div className="text-xs text-gray-300 mt-1 flex justify-between">
                      <span>Events: {summary.activity_count}</span>
                      <span>Screens: {summary.screenshot_count}</span>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </aside>

        {/* Main Content */}
        <main className="w-2/3 lg:w-3/4 p-6 overflow-y-auto">
          {selectedDate && (
            <h1 className="text-2xl font-bold mb-4 text-white">
              Log Details for <span className="text-indigo-400">{selectedDate}</span>
            </h1>
          )}
          {renderDetailContent()}
        </main>
      </div>
    </div>
  );
}

export default App;