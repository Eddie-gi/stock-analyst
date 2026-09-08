import latestData from '@/public/data/latest.json';
import { Dashboard, type Report } from './dashboard';

export default function Home() {
  return <Dashboard initialData={latestData as unknown as Report} />;
}
