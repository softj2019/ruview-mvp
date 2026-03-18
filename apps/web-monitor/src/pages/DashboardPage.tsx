import KpiCards from '@/components/charts/KpiCards';
import FloorView from '@/components/floor/FloorView';
import ObservatoryMini from '@/components/observatory/ObservatoryMini';
import AlertPanel from '@/components/alerts/AlertPanel';
import DeviceList from '@/components/devices/DeviceList';
import SignalChart from '@/components/charts/SignalChart';

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-100">대시보드</h1>
        <p className="text-sm text-gray-500 mt-0.5">실시간 센싱 모니터링</p>
      </div>
      <KpiCards />
      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-12 lg:col-span-7">
          <FloorView />
        </div>
        <div className="col-span-12 lg:col-span-5">
          <ObservatoryMini />
        </div>
      </div>
      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-12 md:col-span-4">
          <AlertPanel />
        </div>
        <div className="col-span-12 md:col-span-4">
          <DeviceList />
        </div>
        <div className="col-span-12 md:col-span-4">
          <SignalChart />
        </div>
      </div>
    </div>
  );
}
