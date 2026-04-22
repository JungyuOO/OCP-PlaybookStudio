import { Link } from 'react-router-dom';
import { ROUTES } from '../app/routes';
import { OpsShell } from './OpsShell';

type OpsSurfacePlaceholderPageProps = {
  eyebrow: string;
  title: string;
  description: string;
  highlights: string[];
};

export default function OpsSurfacePlaceholderPage({
  eyebrow,
  title,
  description,
  highlights,
}: OpsSurfacePlaceholderPageProps) {
  return (
    <OpsShell
      eyebrow={eyebrow}
      title={title}
      description={description}
      actions={
        <Link to={ROUTES.opsWorkspaces} className="ops-primary-action">
          Go to workspaces
        </Link>
      }
    >
      <div className="ops-card glass-panel">
        <div className="ops-section-head">
          <div>
            <span className="ops-section-eyebrow">Next integration slice</span>
            <h2>This surface is reserved and route-stable</h2>
          </div>
        </div>
        <div className="ops-stack">
          {highlights.map((item) => (
            <div key={item} className="ops-list-item is-static">
              <div className="ops-list-main">
                <strong>{item}</strong>
                <span>Will be mounted from the OCP Ops codebase in the next integration steps.</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </OpsShell>
  );
}
