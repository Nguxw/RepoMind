import RepoWorkbench from "../workbench";

export default function RepoGraphPage({ params }: { params: { id: string } }) {
  return <RepoWorkbench repoId={params.id} initialTab="graph" />;
}
