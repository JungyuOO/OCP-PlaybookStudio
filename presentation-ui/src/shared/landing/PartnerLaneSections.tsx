import { ArrowRight, Waypoints } from 'lucide-react';
import { Link } from 'react-router-dom';
import { ROUTES } from '../../app/routes';
import { PARTNER_SURFACES } from '../../partner/partnerLaneConfig';

export function PartnerLaneHero() {
  return (
    <div className="partner-lane-hero glass-panel">
      <div className="partner-lane-copy">
        <span className="partner-lane-eyebrow">OCP Ops</span>
        <h2 className="partner-lane-title">Operational lane, not document takeover.</h2>
        <p className="partner-lane-description">
          This lane is reserved for workspace-aware OpenShift operations.
          <strong> `/ops/*` </strong>
          will carry connections, overview, resources, operational chat, actions, and SCM without
          colliding with PlayBookStudio document routes.
        </p>
      </div>
      <div className="partner-lane-actions">
        <Link to={ROUTES.partnerHome} className="partner-primary-link">
          <span>Open OCP Ops</span>
          <ArrowRight size={18} />
        </Link>
        <Link to={ROUTES.partnerDetails} className="partner-secondary-link">
          Integration Notes
        </Link>
      </div>
    </div>
  );
}

export function PartnerSurfaceGrid() {
  return (
    <div className="partner-surface-grid">
      {PARTNER_SURFACES.map(({ path, card }) => {
        const Icon = card.icon;
        return (
          <Link key={path} to={path} className="partner-surface-card glass-panel">
            <div className="partner-surface-icon">
              <Icon size={26} />
            </div>
            <h3>{card.title}</h3>
            <p>{card.description}</p>
          </Link>
        );
      })}
    </div>
  );
}

export function PartnerGuardRail() {
  return (
    <div className="partner-lane-guard glass-panel">
      <div className="partner-lane-guard-icon">
        <Waypoints size={22} />
      </div>
      <div>
        <h3>Merge-ready guardrail</h3>
        <p>
          PlayBookStudio keeps
          <strong> `/studio`, `/llmwikibook`, `/playbook-library*` </strong>
          while OCP Ops grows as a sibling subtree rooted at
          <strong> `/ops`</strong>.
        </p>
      </div>
    </div>
  );
}
