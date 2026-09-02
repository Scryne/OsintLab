import { EventDetail } from "./event-detail";

export default async function EventPage({ params }: PageProps<"/events/[id]">) {
  const { id } = await params;
  return <EventDetail eventId={id} />;
}
