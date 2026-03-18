import KpiCards from '@/components/charts/KpiCards';
import FloorView from '@/components/floor/FloorView';
import ObservatoryMini from '@/components/observatory/ObservatoryMini';
import AlertPanel from '@/components/alerts/AlertPanel';
import DeviceList from '@/components/devices/DeviceList';
import SignalChart from '@/components/charts/SignalChart';

export default function DashboardPage() {
  return (
    <div className="space-y-4">
      <KpiCards />
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-7">
          <FloorView />
        </div>
        <div className="col-span-5">
          <ObservatoryMini />
        </div>
      </div>
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-4">
          <AlertPanel />
        </div>
        <div className="col-span-4">
          <DeviceList />
        </div>
        <div className="col-span-4">
          <SignalChart />
        </div>
      </div>
    </div>
  );
}
