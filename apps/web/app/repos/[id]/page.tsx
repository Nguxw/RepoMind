import RepoWorkbench from "./workbench";

export default function RepoPage({ params }: { params: { id: string } }) {
  return <RepoWorkbench repoId={params.id} initialTab="overview" />;
}
