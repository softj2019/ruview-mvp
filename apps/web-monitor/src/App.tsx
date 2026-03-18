import { Routes, Route } from 'react-router-dom';
import DashboardPage from './pages/DashboardPage';
import Layout from './components/Layout';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<DashboardPage />} />
      </Route>
    </Routes>
  );
}
