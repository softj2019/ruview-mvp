import { useMemo } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Tooltip, Legend } from 'recharts';
import { useSignalStore } from '@/stores/signalStore';
import { Card, CardHeader } from '@/components/ui';

export default function SignalChart() {
  const history = useSignalStore((s) => s.history);
  const signalData = useMemo(() => history.slice(-30), [history]);

  // Check if any vitals data is present
  const hasVitals = useMemo(
    () => signalData.some((d) => (d.breathing_rate ?? 0) > 0 || (d.heart_rate ?? 0) > 0),
    [signalData],
  );

  return (
    <Card className="h-[280px]">
      <CardHeader>
        신호 강도
        {hasVitals && <span className="ml-2 text-xs text-rose-400">+ 생체신호</span>}
      </CardHeader>
      <ResponsiveContainer width="100%" height="80%">
        <LineChart data={signalData}>
          <CartesianGrid stroke="#1f2937" strokeDasharray="3 3" />
          <XAxis dataKey="time" tick={{ fill: '#6b7280', fontSize: 10 }} />
          <YAxis yAxisId="left" tick={{ fill: '#6b7280', fontSize: 10 }} />
          <YAxis yAxisId="right" orientation="right" tick={{ fill: '#6b7280', fontSize: 10 }} domain={[0, 120]} />
          <Tooltip
            contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: 8 }}
            labelStyle={{ color: '#9ca3af' }}
          />
          <Legend wrapperStyle={{ fontSize: 10, color: '#9ca3af' }} />
          <Line yAxisId="left" type="monotone" dataKey="rssi" name="RSSI" stroke="#22d3ee" strokeWidth={2} dot={false} />
          <Line yAxisId="left" type="monotone" dataKey="snr" name="SNR" stroke="#34d399" strokeWidth={1} dot={false} />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="breathing_rate"
            name="호흡수"
            stroke="#38bdf8"
            strokeWidth={1.5}
            strokeDasharray="4 2"
            dot={false}
            connectNulls
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="heart_rate"
            name="심박수"
            stroke="#f43f5e"
            strokeWidth={1.5}
            strokeDasharray="4 2"
            dot={false}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </Card>
  );
}
