import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import WorkspacePage from '../pages/WorkspacePage';
import LlmWikiBookPage from '../pages/LlmWikiBookPage';
import PlaybookLibraryPage from '../pages/PlaybookLibraryPage';
import ProjectDetailsPage from '../pages/ProjectDetailsPage';
import OpsHomePage from '../ops/OpsHomePage';
import OpsConnectionsPage from '../ops/OpsConnectionsPage';
import OpsChatPage from '../ops/OpsChatPage';
import OpsActionsPage from '../ops/OpsActionsPage';
import OpsScmPage from '../ops/OpsScmPage';
import OpsOverviewPage from '../ops/OpsOverviewPage';
import OpsResourcesPage from '../ops/OpsResourcesPage';
import OpsSurfacePlaceholderPage from '../ops/OpsSurfacePlaceholderPage';
import OpsWorkspacesPage from '../ops/OpsWorkspacesPage';
import SharedLandingShell from '../shared/landing/SharedLandingShell';
import { buildHandoffLocation } from './handoff';
import { ROUTES } from './routes';

function AliasRedirect({ to }: { to: string }) {
  const location = useLocation();

  return (
    <Navigate
      replace
      to={buildHandoffLocation(to, location)}
    />
  );
}

export default function AppRoutes() {
  return (
    <Routes>
      <Route path={ROUTES.sharedHome} element={<SharedLandingShell />} />
      <Route path={ROUTES.pbsDetails} element={<ProjectDetailsPage />} />
      <Route path={ROUTES.pbsStudio} element={<WorkspacePage />} />
      <Route path={ROUTES.pbsWikiBook} element={<LlmWikiBookPage />} />
      <Route path={ROUTES.pbsWikiBookAlias} element={<AliasRedirect to={ROUTES.pbsWikiBook} />} />
      <Route path={ROUTES.pbsWorkspaceAlias} element={<AliasRedirect to={ROUTES.pbsStudio} />} />
      <Route path={ROUTES.pbsPlaybookLibrary} element={<PlaybookLibraryPage />} />
      <Route path={ROUTES.pbsControlTower} element={<PlaybookLibraryPage />} />
      <Route path={ROUTES.pbsRepository} element={<PlaybookLibraryPage />} />
      <Route path={ROUTES.opsHome} element={<OpsHomePage />} />
      <Route path={ROUTES.opsWorkspaces} element={<OpsWorkspacesPage />} />
      <Route path={ROUTES.opsConnections} element={<OpsConnectionsPage />} />
      <Route path={ROUTES.opsOverview} element={<OpsOverviewPage />} />
      <Route path={ROUTES.opsResources} element={<OpsResourcesPage />} />
      <Route path={ROUTES.opsChat} element={<OpsChatPage />} />
      <Route path={ROUTES.opsActions} element={<OpsActionsPage />} />
      <Route path={ROUTES.opsScm} element={<OpsScmPage />} />
      <Route
        path={ROUTES.opsDetails}
        element={(
          <OpsSurfacePlaceholderPage
            eyebrow="OCP Ops Details"
            title="Integration notes"
            description="This route keeps the shell boundary explicit while the operational pages are ported one slice at a time."
            highlights={[
              'PlayBookStudio owns document retrieval and official-doc chat',
              'OCP Ops owns workspace, cluster, action, and SCM workflows',
              'The next frontend slice is the real connections flow',
            ]}
          />
        )}
      />
      <Route path="*" element={<Navigate replace to={ROUTES.sharedHome} />} />
    </Routes>
  );
}
