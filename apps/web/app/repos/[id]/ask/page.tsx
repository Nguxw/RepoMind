import RepoWorkbench from "../workbench";

export default function RepoAskPage({ params }: { params: { id: string } }) {
  return <RepoWorkbench repoId={params.id} initialTab="ask" />;
}
