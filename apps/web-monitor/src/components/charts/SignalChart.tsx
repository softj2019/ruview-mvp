import { LineChart, Line, XAxis, YAxis, CartesianGrid, ResponsiveContainer } from 'recharts';
import { useSignalStore } from '@/stores/signalStore';

export default function SignalChart() {
  const signalData = useSignalStore((s) => s.history.slice(-30));

  return (
    <div className="card h-[250px]">
      <h3 className="text-sm font-medium text-gray-400 mb-3">Signal Strength</h3>
      <ResponsiveContainer width="100%" height="85%">
        <LineChart data={signalData}>
          <CartesianGrid stroke="#222230" strokeDasharray="3 3" />
          <XAxis dataKey="time" tick={{ fill: '#666', fontSize: 10 }} />
          <YAxis tick={{ fill: '#666', fontSize: 10 }} />
          <Line type="monotone" dataKey="rssi" stroke="#00F0FF" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="snr" stroke="#00FF88" strokeWidth={1} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
