import type { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ROUTES } from '../app/routes';
import './ops.css';

const OPS_NAV_ITEMS = [
  { href: ROUTES.opsHome, label: 'Home' },
  { href: ROUTES.opsWorkspaces, label: 'Workspaces' },
  { href: ROUTES.opsConnections, label: 'Connections' },
  { href: ROUTES.opsOverview, label: 'Overview' },
  { href: ROUTES.opsResources, label: 'Resources' },
  { href: ROUTES.opsChat, label: 'Chat' },
  { href: ROUTES.opsActions, label: 'Actions' },
  { href: ROUTES.opsScm, label: 'SCM' },
] as const;

type OpsShellProps = {
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
  actions?: ReactNode;
};

export function OpsShell({ eyebrow, title, description, children, actions }: OpsShellProps) {
  const location = useLocation();

  return (
    <div className="ops-page">
      <div className="ops-shell">
        <section className="ops-hero glass-panel">
          <div className="ops-hero-copy">
            <span className="ops-eyebrow">{eyebrow}</span>
            <h1 className="ops-title">{title}</h1>
            <p className="ops-description">{description}</p>
          </div>
          <div className="ops-hero-actions">
            {actions}
            <Link to={ROUTES.sharedHome} className="ops-secondary-action">
              Back to shell
            </Link>
          </div>
        </section>

        <nav className="ops-nav glass-panel" aria-label="OCP Ops navigation">
          {OPS_NAV_ITEMS.map((item) => {
            const active =
              item.href === ROUTES.opsHome
                ? location.pathname === item.href
                : location.pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                to={item.href}
                className={`ops-nav-link ${active ? 'is-active' : ''}`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <section className="ops-content">{children}</section>
      </div>
    </div>
  );
}
