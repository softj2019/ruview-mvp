import { useMemo } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, ResponsiveContainer } from 'recharts';
import { useSignalStore } from '@/stores/signalStore';
import { Card, CardHeader } from '@/components/ui';

export default function SignalChart() {
  const history = useSignalStore((s) => s.history);
  const signalData = useMemo(() => history.slice(-30), [history]);

  return (
    <Card className="h-[280px]">
      <CardHeader>신호 강도</CardHeader>
      <ResponsiveContainer width="100%" height="80%">
        <LineChart data={signalData}>
          <CartesianGrid stroke="#1f2937" strokeDasharray="3 3" />
          <XAxis dataKey="time" tick={{ fill: '#6b7280', fontSize: 10 }} />
          <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} />
          <Line type="monotone" dataKey="rssi" stroke="#22d3ee" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="snr" stroke="#34d399" strokeWidth={1} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </Card>
  );
}
