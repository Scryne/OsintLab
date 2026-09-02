import { InvestigationDetail } from "./investigation-detail";

export default async function InvestigationPage({ params }: PageProps<"/investigations/[id]">) {
  const { id } = await params;
  return <InvestigationDetail investigationId={id} />;
}
