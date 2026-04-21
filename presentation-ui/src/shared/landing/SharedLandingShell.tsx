import { useSearchParams } from 'react-router-dom';
import LandingPage from '../../pages/LandingPage';
import { normalizeSharedLandingTab } from '../../app/routes';
import PartnerLanePanel from './PartnerLanePanel';
import SharedLandingSwitcher from './SharedLandingSwitcher';
import './SharedLandingShell.css';

export default function SharedLandingShell() {
  const [searchParams] = useSearchParams();
  const activeTab = normalizeSharedLandingTab(searchParams.get('tab'));

  return (
    <div className="shared-landing-shell">
      <SharedLandingSwitcher activeTab={activeTab} />

      <div className="shared-shell-body">
        {activeTab === 'partner' ? <PartnerLanePanel /> : <LandingPage />}
      </div>
    </div>
  );
}
