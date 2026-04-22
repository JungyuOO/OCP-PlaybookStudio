import { ArrowLeftRight, ShieldCheck, SplitSquareVertical } from 'lucide-react';
import { Link } from 'react-router-dom';
import { buildSharedLandingHref } from '../app/routes';
import './PartnerNamespacePage.css';

type PartnerNamespacePageProps = {
  eyebrow: string;
  title: string;
  description: string;
};

export default function PartnerNamespacePage({
  eyebrow,
  title,
  description,
}: PartnerNamespacePageProps) {
  return (
    <div className="partner-namespace-page">
      <div className="partner-namespace-shell">
        <Link to={buildSharedLandingHref('ops')} className="partner-namespace-back">
          <ArrowLeftRight size={18} />
          <span>Back to OCP Ops</span>
        </Link>

        <section className="partner-namespace-card glass-panel">
          <span className="partner-namespace-eyebrow">{eyebrow}</span>
          <h1 className="partner-namespace-title">{title}</h1>
          <p className="partner-namespace-description">{description}</p>
        </section>

        <div className="partner-namespace-grid">
          <section className="glass-panel">
            <SplitSquareVertical size={22} />
            <h3>Namespace isolation</h3>
            <p>
              OCP Ops lives in a sibling route family so operational workflows can grow independently
              from PlayBookStudio document experiences.
            </p>
          </section>
          <section className="glass-panel">
            <ShieldCheck size={22} />
            <h3>Truth isolation</h3>
            <p>
              PlayBookStudio owns official-document retrieval and citations. OCP Ops will own cluster
              context, actions, audit, and operational chat behavior.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
