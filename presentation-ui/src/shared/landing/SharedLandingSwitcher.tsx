import { Layers3, Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';
import { buildSharedLandingHref, type SharedLandingTab } from '../../app/routes';

export default function SharedLandingSwitcher({ activeTab }: { activeTab: SharedLandingTab }) {
  return (
    <div className="shared-shell-switcher glass-panel">
      <div>
        <div className="shared-shell-label">
          <Layers3 size={16} />
          <span>Shared Entry Shell</span>
        </div>
        <h1 className="shared-shell-title">
          One landing, two product lanes.
        </h1>
        <p className="shared-shell-description">
          PlayBookStudio keeps ownership of official-document and playbook knowledge experiences.
          OCP Ops enters through a sibling namespace so operational tooling can grow without disturbing PBS routes.
        </p>
      </div>
      <div className="shared-shell-tabs" aria-label="Product lane selector">
        <Link
          to={buildSharedLandingHref('pbs')}
          className={`shared-shell-tab ${activeTab === 'pbs' ? 'is-active' : ''}`}
        >
          <Sparkles size={16} />
          <span>PlayBookStudio</span>
        </Link>
        <Link
          to={buildSharedLandingHref('ops')}
          className={`shared-shell-tab ${activeTab === 'ops' ? 'is-active' : ''}`}
        >
          <Layers3 size={16} />
          <span>OCP Ops</span>
        </Link>
      </div>
    </div>
  );
}
