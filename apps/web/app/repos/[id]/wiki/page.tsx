import RepoWorkbench from "../workbench";

export default function RepoWikiPage({ params }: { params: { id: string } }) {
  return <RepoWorkbench repoId={params.id} initialTab="wiki" />;
}
