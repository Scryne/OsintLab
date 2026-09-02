import { EntityDetail } from "./entity-detail";

export default async function EntityPage({ params }: PageProps<"/entities/[id]">) {
  const { id } = await params;
  return <EntityDetail entityId={id} />;
}
