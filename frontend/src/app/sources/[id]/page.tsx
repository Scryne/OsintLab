import { SourceDetail } from "./source-detail";

export default async function SourcePage({ params }: PageProps<"/sources/[id]">) {
  const { id } = await params;
  return <SourceDetail sourceId={id} />;
}
